"""whisper.cpp subprocess wrapper.

Invokes the `whisper-cpp` binary (Homebrew: `brew install whisper-cpp`) as a
subprocess. Never imports MLX or any Mac-only audio library directly — the
abstraction boundary is the subprocess. On Linux, replace `whisper-cpp` with
the native `whisper.cpp` binary at the same path and nothing else changes.

Output contract:
  whisper.cpp --output-json writes a companion <file>.json with:
    {
      "transcription": [
        {"offsets": {...}, "timestamps": {...}, "text": "...", "avg_logprob": -0.12, ...},
        ...
      ]
    }

  We derive "confidence" as:  exp(mean(avg_logprob)) across all segments,
  clamped to [0.0, 1.0]. avg_logprob is always ≤ 0, so exp() ∈ (0, 1].
  A logprob of 0 means certainty; -1 means about 37% confidence. This is
  the standard whisper.cpp per-segment log probability field.

Portability:
  The binary name is configurable via SPRITE_WHISPER_BIN (default: whisper-cpp).
  On Linux the same binary usually installs as `whisper` or `main` from the
  whisper.cpp repo — override via env var.
"""

from __future__ import annotations

import json
import logging
import math
import os
import subprocess
import tempfile
from dataclasses import dataclass
from pathlib import Path
from typing import Optional

log = logging.getLogger(__name__)

# Homebrew installs the CLI as "whisper-cpp" on macOS. On Linux it is often
# "whisper" or the path to the compiled binary. Override via env var.
_DEFAULT_WHISPER_BIN = "whisper-cpp"


@dataclass
class TranscriptResult:
    text: str
    confidence: float       # [0.0, 1.0] — derived from avg_logprob
    segments: list[dict]    # raw segment objects from whisper.cpp JSON
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

    # whisper.cpp --output-json writes to <input>.json in the same dir as the
    # input by default, which is the archive directory. We redirect to a tmpdir
    # to keep the archive clean, then parse + copy to transcripts_dir.
    with tempfile.TemporaryDirectory() as tmpdir:
        tmp_audio = Path(tmpdir) / audio_path.name
        # Symlink so whisper.cpp names its output correctly without copying the
        # potentially large audio file.
        try:
            tmp_audio.symlink_to(audio_path)
        except OSError:
            # If symlinks are not supported, copy.
            import shutil
            shutil.copy2(str(audio_path), str(tmp_audio))

        cmd = [
            bin_name,
            "--model", str(model_path),
            "--language", language,
            "--output-json",
            "--output-file", str(Path(tmpdir) / uuid),
            str(tmp_audio),
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
                f"whisper-cpp binary not found: {bin_name!r}. "
                "Install with: brew install whisper-cpp"
            ) from exc
        except subprocess.TimeoutExpired as exc:
            raise WhisperError(
                f"whisper-cpp timed out after 120s on {audio_path.name}"
            ) from exc

        if result.returncode != 0:
            raise WhisperError(
                f"whisper-cpp exited {result.returncode} for {audio_path.name}: "
                f"{result.stderr.strip()[:300]}"
            )

        # whisper.cpp writes <output_file>.json
        json_out = Path(tmpdir) / f"{uuid}.json"
        if not json_out.exists():
            raise WhisperError(
                f"whisper-cpp produced no JSON output for {audio_path.name}"
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


def _compute_confidence(segments: list[dict]) -> float:
    """Derive a [0.0, 1.0] confidence score from whisper.cpp segment log-probs.

    avg_logprob is per-segment and always ≤ 0. We take the mean across all
    segments and apply exp() to map to (0, 1]. A completely silent or empty
    transcript gets 0.0.
    """
    if not segments:
        return 0.0
    logprobs = [seg.get("avg_logprob", -1.0) for seg in segments]
    mean_logprob = sum(logprobs) / len(logprobs)
    return max(0.0, min(1.0, math.exp(mean_logprob)))
