"""Integration-shaped tests for the intent router.

Uses the heuristic parser (no Ollama) so tests are hermetic.
"""

from __future__ import annotations

from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

import pytest

from homunculus_brain.config import Config
from homunculus_brain.intent_router import commit_calendar_event, route
from homunculus_brain.llm import heuristic_parse
from homunculus_brain.schemas import IntentKind


TZ = ZoneInfo("America/New_York")
NOW = datetime(2026, 6, 8, 9, 0, tzinfo=TZ)  # Monday 9am


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
        ollama_model="qwen2.5:14b",
        server_host="0.0.0.0",
        server_port=8765,
    )


def test_calendar_event_needs_confirmation(tmp_path: Path):
    intent = heuristic_parse("add a meeting with Jane on Thursday at 2pm")
    cfg = _config(tmp_path)
    resp = route(intent, config=cfg, now=NOW)
    assert resp.action == "needs_confirmation"
    assert "Sound right" in resp.spoken_reply


def test_calendar_query_replies_when_clear(tmp_path: Path):
    intent = heuristic_parse("can we meet for coffee Thursday at 10am")
    cfg = _config(tmp_path)
    resp = route(intent, config=cfg, now=NOW)
    assert resp.action == "wrote"
    assert "clear" in resp.spoken_reply.lower() or "no conflict" in resp.spoken_reply.lower()


def test_tool_note_writes_immediately(tmp_path: Path):
    intent = heuristic_parse("note that tool — Craftsman open-end wrench")
    cfg = _config(tmp_path)
    resp = route(intent, config=cfg, now=NOW)
    assert resp.action == "wrote"
    assert "Noted" in resp.spoken_reply
    assert resp.written_path is not None


def test_unknown_lands_in_inbox(tmp_path: Path):
    intent = heuristic_parse("the weather is nice today")
    cfg = _config(tmp_path)
    resp = route(intent, config=cfg, now=NOW)
    assert resp.action == "inbox"
    assert "inbox" in resp.spoken_reply.lower()


def test_ambiguous_time_triggers_clarification(tmp_path: Path):
    intent = heuristic_parse("add a meeting on Thursday")
    cfg = _config(tmp_path)
    resp = route(intent, config=cfg, now=NOW)
    assert resp.action == "needs_clarification"
    assert "time" in (resp.clarifying_question or "").lower()


def test_commit_creates_event_and_schedule(tmp_path: Path):
    intent = heuristic_parse("add a meeting with Jane on Thursday at 2pm")
    cfg = _config(tmp_path)
    # Override the heuristic-parser intent to ensure it routes as event, not query.
    from homunculus_brain.schemas import IntentKind as IK
    intent.kind = IK.CALENDAR_EVENT
    intent.title = "meeting with Jane"

    resp = commit_calendar_event(intent, config=cfg, now=NOW)
    assert resp.action == "wrote"
    assert resp.written_path is not None
    assert (tmp_path / "_reminders").exists()
    files = list((tmp_path / "_reminders").glob("*.json"))
    assert len(files) == 1
