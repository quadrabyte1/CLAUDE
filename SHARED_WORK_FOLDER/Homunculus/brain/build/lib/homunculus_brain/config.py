"""Runtime configuration.

Everything here is overridable via environment variables so the brain can be
moved between machines (Mac today, Linux/NVIDIA box tomorrow) without code
changes.
"""

from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path
from zoneinfo import ZoneInfo


_DEFAULT_VAULT = Path(__file__).resolve().parents[2] / "vault"


@dataclass(frozen=True)
class Config:
    vault_path: Path
    default_tz_name: str
    morning_summary_time: str  # "HH:MM" 24h, local to default_tz
    morning_anchor_hour: int  # hour for "tomorrow morning" / "morning"
    conflict_fuzz_minutes: int
    default_event_duration_minutes: int
    reminder_undo_window_seconds: int
    ollama_base_url: str
    ollama_model: str
    server_host: str
    server_port: int

    @property
    def default_tz(self) -> ZoneInfo:
        return ZoneInfo(self.default_tz_name)


def load_config() -> Config:
    return Config(
        vault_path=Path(os.environ.get("HOMUNCULUS_VAULT", str(_DEFAULT_VAULT))),
        default_tz_name=os.environ.get("HOMUNCULUS_TZ", "America/New_York"),
        morning_summary_time=os.environ.get("HOMUNCULUS_MORNING_SUMMARY", "07:00"),
        morning_anchor_hour=int(os.environ.get("HOMUNCULUS_MORNING_ANCHOR", "9")),
        conflict_fuzz_minutes=int(os.environ.get("HOMUNCULUS_FUZZ_MIN", "30")),
        default_event_duration_minutes=int(os.environ.get("HOMUNCULUS_DEFAULT_DURATION", "30")),
        reminder_undo_window_seconds=int(os.environ.get("HOMUNCULUS_UNDO_WINDOW", "300")),
        ollama_base_url=os.environ.get("OLLAMA_BASE_URL", "http://localhost:11434"),
        ollama_model=os.environ.get("OLLAMA_MODEL", "qwen2.5:7b"),
        server_host=os.environ.get("HOMUNCULUS_HOST", "0.0.0.0"),
        server_port=int(os.environ.get("HOMUNCULUS_PORT", "8765")),
    )
