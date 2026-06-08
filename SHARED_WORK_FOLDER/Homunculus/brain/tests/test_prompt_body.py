"""The prompt-note flow must persist an inline body when the user provides one."""

from __future__ import annotations

from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

from homunculus_brain.config import Config
from homunculus_brain.intent_router import route
from homunculus_brain.schemas import Confidence, IntentKind, ParsedIntent


TZ = ZoneInfo("America/New_York")
NOW = datetime(2026, 6, 8, 12, 0, tzinfo=TZ)


def _config(tmp_path: Path) -> Config:
    return Config(
        vault_path=tmp_path,
        default_tz_name="America/New_York",
        morning_summary_time="07:00",
        morning_anchor_hour=9,
        conflict_fuzz_minutes=30,
        default_event_duration_minutes=30,
        reminder_undo_window_seconds=300,
        ollama_base_url="http://localhost:11434",
        ollama_model="qwen2.5:7b",
        server_host="0.0.0.0",
        server_port=8765,
    )


def test_prompt_note_persists_body(tmp_path: Path):
    intent = ParsedIntent(
        kind=IntentKind.PROMPT_NOTE,
        confidence=Confidence.HIGH,
        title="Rendering rules for golf moments",
        raw_text="save this prompt — body: the prompt was X, the answer was Y",
        body="the prompt was X, the answer was Y",
    )
    resp = route(intent, config=_config(tmp_path), now=NOW)
    assert resp.action == "wrote"
    assert resp.written_path is not None
    on_disk = (tmp_path / resp.written_path).read_text(encoding="utf-8")
    assert "the prompt was X, the answer was Y" in on_disk


def test_prompt_note_without_body_uses_placeholder(tmp_path: Path):
    intent = ParsedIntent(
        kind=IntentKind.PROMPT_NOTE,
        confidence=Confidence.HIGH,
        title="Golf rendering rules",
        raw_text="save that prompt about golf rendering rules",
        body=None,
    )
    resp = route(intent, config=_config(tmp_path), now=NOW)
    assert resp.action == "wrote"
    on_disk = (tmp_path / resp.written_path).read_text(encoding="utf-8")
    # The placeholder marker should appear when no body was given.
    assert "Body not yet captured" in on_disk
