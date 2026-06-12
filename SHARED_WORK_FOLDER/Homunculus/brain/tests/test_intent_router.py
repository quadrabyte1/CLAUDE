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


def test_feed_jake_at_535_asks_am_or_pm(tmp_path: Path):
    """v1.2.2 regression: the live bug from 2026-06-10 17:31:40 EDT.

    Boss spoke "Feed Jake at 5:35" at 5:31 PM. Old behavior: brain silently
    chose 5:35 AM the next morning (~12 hours away, almost certainly wrong;
    the nearest-future 5:35 was just 4 minutes away). New behavior: bare
    hour:minute with no AM/PM and no 24-hour context (hour 0 or 13+) is
    ambiguous; ask the user instead of guessing.
    """
    # Wed Jun 10 17:31:40 EDT 2026 — the moment the bug was observed.
    bug_now = datetime(2026, 6, 10, 17, 31, 40, tzinfo=TZ)
    intent = heuristic_parse("Feed Jake at 5:35")
    intent.kind = IntentKind.CALENDAR_EVENT  # router-level decision, force it
    from homunculus_brain.schemas import Confidence
    intent.confidence = Confidence.HIGH  # the LLM gave this medium/high in prod
    cfg = _config(tmp_path)
    resp = route(intent, config=cfg, now=bug_now)
    assert resp.action == "needs_clarification", (
        f"expected needs_clarification for ambiguous bare-hour-minute time; "
        f"got {resp.action!r} with reply={resp.spoken_reply!r}"
    )
    assert (resp.clarifying_question or "").strip(), "must surface a question"
    # The question should be about the missing am/pm — not "what day".
    q = (resp.clarifying_question or "").lower()
    assert "am" in q and "pm" in q, (
        f"clarifying question should ask AM vs PM; got {resp.clarifying_question!r}"
    )


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
