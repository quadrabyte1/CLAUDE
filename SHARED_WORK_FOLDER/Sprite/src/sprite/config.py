"""Sprite runtime configuration — all overridable via environment variables.

Portability religion: no Mac-only env var names. Every name is neutral so the
pipeline runs unchanged on Linux (different paths, same names).
"""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path


@dataclass(frozen=True)
class SpriteConfig:
    # --- Paths ----------------------------------------------------------------
    # Root under which processed audio is archived: YYYY/MM/<uuid>.m4a
    audio_archive: Path
    # Append-only state log for idempotency: processed.jsonl
    state_file: Path
    # Ambiguous-capture inbox: YYYY-MM-DD.md (atomic append per day)
    inbox_dir: Path
    # Whisper transcript output: YYYY/MM/<uuid>.json
    transcripts_dir: Path
    # Sprite warnings file (shared with Herman's morning summary)
    warnings_path: Path
    # Directory to watch for new Voice Memo recordings
    recordings_dir: Path
    # whisper.cpp model path
    models_dir: Path

    # --- Service URLs ---------------------------------------------------------
    ollama_base_url: str
    ollama_model: str
    herman_base_url: str

    # --- Tuning ---------------------------------------------------------------
    # mtime-stable window before whisper is invoked (seconds)
    debounce_seconds: float
    # minimum file size before we treat the .m4a as complete
    min_file_bytes: int
    # confidence floor: below this → inbox, not Herman
    min_confidence: float
    # max time to wait for Ollama response (seconds)
    ollama_timeout: float
    # max time to wait for Herman POST (seconds)
    herman_timeout: float
    # cold-boot sweep: how far back to look for unprocessed memos (seconds; 0 = unlimited)
    cold_boot_window_seconds: float


def load_config() -> SpriteConfig:
    home = Path.home()
    sprite_root = home / "sprite"

    recordings_dir_default = str(
        home
        / "Library"
        / "Group Containers"
        / "group.com.apple.VoiceMemos.shared"
        / "Recordings"
    )

    return SpriteConfig(
        audio_archive=Path(
            os.environ.get("SPRITE_AUDIO_ARCHIVE", str(sprite_root / "audio"))
        ),
        state_file=Path(
            os.environ.get("SPRITE_STATE_FILE", str(sprite_root / "state" / "processed.jsonl"))
        ),
        inbox_dir=Path(
            os.environ.get("SPRITE_INBOX_DIR", str(sprite_root / "inbox"))
        ),
        transcripts_dir=Path(
            os.environ.get("SPRITE_TRANSCRIPTS_DIR", str(sprite_root / "transcripts"))
        ),
        warnings_path=Path(
            os.environ.get(
                "SPRITE_WARNINGS_PATH", str(sprite_root / "warnings.md")
            )
        ),
        recordings_dir=Path(
            os.environ.get("SPRITE_RECORDINGS_DIR", recordings_dir_default)
        ),
        models_dir=Path(
            os.environ.get("SPRITE_MODELS_DIR", str(sprite_root / "models"))
        ),
        ollama_base_url=os.environ.get("OLLAMA_BASE_URL", "http://localhost:11434"),
        ollama_model=os.environ.get("SPRITE_OLLAMA_MODEL", "qwen2.5:7b-instruct"),
        herman_base_url=os.environ.get("SPRITE_HERMAN_URL", "http://localhost:8765"),
        debounce_seconds=float(os.environ.get("SPRITE_DEBOUNCE_SECONDS", "3.0")),
        min_file_bytes=int(os.environ.get("SPRITE_MIN_FILE_BYTES", str(10 * 1024))),
        min_confidence=float(os.environ.get("SPRITE_MIN_CONFIDENCE", "0.6")),
        ollama_timeout=float(os.environ.get("SPRITE_OLLAMA_TIMEOUT", "30.0")),
        herman_timeout=float(os.environ.get("SPRITE_HERMAN_TIMEOUT", "15.0")),
        cold_boot_window_seconds=float(
            os.environ.get("SPRITE_COLD_BOOT_WINDOW", "0")
        ),
    )
