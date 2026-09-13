"""whisper.cpp subprocess wrapper.

Invokes the `whisper-cli` binary (Homebrew: `brew install whisper-cpp`) as a
subprocess. Never imports MLX or any Mac-only audio library directly — the
abstraction boundary is the subprocess. On Linux, replace `whisper-cli` with
the native `whisper.cpp` binary at the same path and nothing else changes.

Output contract:
  whisper-cli --output-json-full writes a companion <file>.json with:
    {
      "transcription": [
        {
          "timestamps": {...}, "offsets": {...}, "text": "...",
          "tokens": [
            {"text": " word", "id": 1234, "p": 0.85, "timestamps": {...}, "offsets": {...}, "t_dtw": -1},
            {"text": "[_BEG_]", "id": 50363, "p": 0.67, ...},  # special — filtered out
            ...
          ]
        },
        ...
      ]
    }

  We derive "confidence" as: mean(token.p) across all non-special tokens in all
  segments, where "special" means the token text starts+ends with [ ] or < >.
  Special tokens (e.g. [_BEG_], [_TT_576], <|endoftext|>) are timing/control
  tokens emitted by whisper.cpp that do not correspond to spoken words.

  If zero real tokens survive (empty transcript or all-special), confidence = 0.0.
  There is NO silent default. We do not fall back to exp(-1.0).

M4A / AAC transcoding:
  whisper-cli's miniaudio backend does not reliably decode Apple AAC-in-MP4
  (.m4a) files written by iOS Voice Memos. We transcode M4A → 16 kHz mono WAV
  via ffmpeg before passing the file to whisper-cli. ffmpeg must be installed
  separately: `brew install ffmpeg` (macOS) or `apt install ffmpeg` (Linux).
  WAV files are passed directly without transcoding.

Portability:
  The binary name is configurable via SPRITE_WHISPER_BIN (default: whisper-cli).
  On Linux the same binary usually installs as `whisper-cli` or `main` from the
  whisper.cpp repo — override via env var.
  ffmpeg is cross-platform and available on all major platforms.
"""

from __future__ import annotations

import json
import logging
import os
import subprocess
import tempfile
from dataclasses import dataclass
from pathlib import Path
from typing import Optional

log = logging.getLogger(__name__)

# Homebrew's whisper-cpp formula installs the CLI as "whisper-cli" (renamed
# from "main" upstream). On Linux it is often "whisper-cli" or the path to
# the compiled binary. Override via env var SPRITE_WHISPER_BIN.
_DEFAULT_WHISPER_BIN = "whisper-cli"


def _transcode_to_wav(audio_path: Path, tmpdir: Path) -> Path:
    """Transcode *audio_path* to a 16 kHz mono PCM WAV file in *tmpdir*.

    Uses ffmpeg, which must be installed separately:
      macOS:  brew install ffmpeg
      Linux:  apt install ffmpeg  (or your distro's equivalent)

    Returns the Path to the transcoded .wav file.

    Raises WhisperError on:
      - ffmpeg not found (FileNotFoundError)
      - ffmpeg non-zero exit (corrupt / unsupported input)
    """
    out_wav = tmpdir / (audio_path.stem + "_16k_mono.wav")
    cmd = [
        "ffmpeg",
        "-y",               # overwrite output without prompting
        "-loglevel", "error",
        "-i", str(audio_path),
        "-ar", "16000",     # resample to 16 kHz
        "-ac", "1",         # convert to mono
        "-c:a", "pcm_s16le",
        str(out_wav),
    ]
    try:
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=120,
        )
    except FileNotFoundError as exc:
        raise WhisperError(
            f"ffmpeg not found. Install with: brew install ffmpeg (macOS) "
            f"or apt install ffmpeg (Linux). "
            f"Required to decode .{audio_path.suffix.lstrip('.')} audio files."
        ) from exc
    except subprocess.TimeoutExpired as exc:
        raise WhisperError(
            f"ffmpeg timed out transcoding {audio_path.name}"
        ) from exc

    if result.returncode != 0:
        raise WhisperError(
            f"ffmpeg failed (exit {result.returncode}) transcoding {audio_path.name}: "
            f"{result.stderr.strip()[:300]}"
        )

    return out_wav


@dataclass
class TranscriptResult:
    text: str
    confidence: float       # [0.0, 1.0] — mean token probability (non-special tokens)
    segments: list[dict]    # raw segment objects from whisper.cpp JSON (under "transcription" key)
    raw_json: dict          # complete whisper.cpp output for provenance
    transcript_json_path: Optional[Path] = None  # where we persisted it


class WhisperError(RuntimeError):
    """Raised when whisper.cpp fails (non-zero exit or no output)."""


def transcribe(
    audio_path: Path,
    *,
    model_path: Path,
    transcripts_dir: Path,
    uuid: str,
    language: str = "en",
    whisper_bin: Optional[str] = None,
) -> TranscriptResult:
    """Run whisper.cpp on *audio_path* and return a TranscriptResult.

    Persists the raw JSON to transcripts_dir/YYYY/MM/<uuid>.json for
    provenance. The transcript_json_path field in the result points there.

    Raises WhisperError on binary-not-found, non-zero exit, or unparseable
    output.
    """
    bin_name = whisper_bin or os.environ.get("SPRITE_WHISPER_BIN", _DEFAULT_WHISPER_BIN)

    # whisper-cli --output-json writes to <input>.json in the same dir as the
    # input by default, which is the archive directory. We redirect to a tmpdir
    # to keep the archive clean, then parse + copy to transcripts_dir.
    with tempfile.TemporaryDirectory() as tmpdir:
        tmpdir_path = Path(tmpdir)

        # --- Transcode non-WAV inputs to 16 kHz mono WAV before whisper-cli ---
        # whisper-cli's miniaudio backend does not reliably decode Apple AAC-in-MP4
        # (.m4a). We always transcode anything that isn't already a plain .wav file.
        # _transcode_to_wav raises WhisperError if ffmpeg is missing or fails.
        if audio_path.suffix.lower() != ".wav":
            log.info(
                "transcribe: transcoding %s → WAV (16 kHz mono) via ffmpeg",
                audio_path.name,
            )
            whisper_input = _transcode_to_wav(audio_path, tmpdir_path)
        else:
            # WAV: symlink into tmpdir so whisper-cli names its JSON output predictably.
            whisper_input = tmpdir_path / audio_path.name
            try:
                whisper_input.symlink_to(audio_path)
            except OSError:
                import shutil
                shutil.copy2(str(audio_path), str(whisper_input))

        cmd = [
            bin_name,
            "--model", str(model_path),
            "--language", language,
            "--output-json-full",   # includes per-token 'p' (probability) fields
            "--output-file", str(tmpdir_path / uuid),
            str(whisper_input),
        ]
        log.info("transcribe: running %s on %s", bin_name, audio_path.name)
        try:
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=120,  # 120 s is generous for small.en on short memos
            )
        except FileNotFoundError as exc:
            raise WhisperError(
                f"whisper-cli binary not found: {bin_name!r}. "
                "Install with: brew install whisper-cpp"
            ) from exc
        except subprocess.TimeoutExpired as exc:
            raise WhisperError(
                f"whisper-cli timed out after 120s on {audio_path.name}"
            ) from exc

        if result.returncode != 0:
            raise WhisperError(
                f"whisper-cli exited {result.returncode} for {audio_path.name}: "
                f"{result.stderr.strip()[:300]}"
            )

        # whisper-cli writes <output_file>.json
        json_out = tmpdir_path / f"{uuid}.json"
        if not json_out.exists():
            raise WhisperError(
                f"whisper-cli produced no JSON output for {audio_path.name}"
            )

        raw_json = json.loads(json_out.read_text(encoding="utf-8"))

    # Persist transcript JSON to transcripts_dir.
    from datetime import datetime, timezone
    now = datetime.now(timezone.utc)
    dest_dir = transcripts_dir / now.strftime("%Y") / now.strftime("%m")
    dest_dir.mkdir(parents=True, exist_ok=True)
    dest_json = dest_dir / f"{uuid}.json"
    dest_json.write_text(json.dumps(raw_json, ensure_ascii=False, indent=2), encoding="utf-8")

    # Parse segments and compute confidence.
    segments = raw_json.get("transcription", [])
    text = " ".join(seg.get("text", "").strip() for seg in segments).strip()
    confidence = _compute_confidence(segments)

    log.info(
        "transcribe: %s → %d chars, conf=%.3f, saved %s",
        audio_path.name,
        len(text),
        confidence,
        dest_json,
    )
    return TranscriptResult(
        text=text,
        confidence=confidence,
        segments=segments,
        raw_json=raw_json,
        transcript_json_path=dest_json,
    )


def _is_special_token(token_text: str) -> bool:
    """Return True if this whisper token is a special/control token to be filtered.

    whisper.cpp emits special tokens in two forms:
      - Square-bracket:  [_BEG_], [_TT_576], [_SOT_], [_EOT_], [_NOT_]
      - Angle-bracket:   <|endoftext|>, <|startoftranscript|>, <|en|>, etc.

    These do not correspond to spoken words and must not contribute to the
    confidence score. We detect them by checking the first and last character
    of the token text (after stripping whitespace).
    """
    t = token_text.strip()
    return (t.startswith("[") and t.endswith("]")) or (t.startswith("<") and t.endswith(">"))


def _compute_confidence(segments: list[dict]) -> float:
    """Derive a [0.0, 1.0] confidence score from whisper-cli --output-json-full token probs.

    Each segment in the --output-json-full output carries a 'tokens' list.
    Each token has a 'p' field (probability in [0, 1]).  We compute the
    arithmetic mean of 'p' across all non-special tokens in all segments.

    Special tokens ([_BEG_], [_TT_576], <|endoftext|>, etc.) are filtered out
    because they are timing/control tokens, not spoken words.

    Returns 0.0 if:
      - segments is empty
      - no segment contains a 'tokens' list
      - all tokens are special (nothing real to score)

    There is NO silent default. We never return exp(-1.0).
    """
    real_probs: list[float] = []
    for seg in segments:
        for tok in seg.get("tokens", []):
            text = tok.get("text", "")
            if not _is_special_token(text):
                p = tok.get("p")
                if p is not None:
                    real_probs.append(p)

    if not real_probs:
        return 0.0

    # Python does the arithmetic — never the LLM.
    return sum(real_probs) / len(real_probs)
