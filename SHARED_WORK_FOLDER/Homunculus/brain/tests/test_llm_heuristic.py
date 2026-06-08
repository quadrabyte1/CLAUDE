"""Tests for the offline heuristic fallback parser."""

from __future__ import annotations

from homunculus_brain.llm import heuristic_parse
from homunculus_brain.schemas import IntentKind


def test_coffee_request_is_calendar_event():
    out = heuristic_parse("Can we meet for coffee Thursday at 10?")
    assert out.kind == IntentKind.CALENDAR_QUERY
    assert out.day_hint and "thursday" in out.day_hint.lower()
    assert out.time_hint and "10" in out.time_hint


def test_add_event_phrasing_routes_to_event():
    out = heuristic_parse("Add a meeting with Jane on Friday at 2pm")
    assert out.kind == IntentKind.CALENDAR_EVENT


def test_tool_note_detected():
    out = heuristic_parse("Note that tool — Craftsman open-end wrench")
    assert out.kind == IntentKind.TOOL_NOTE
    assert out.title and "Craftsman" in out.title


def test_prompt_note_detected():
    out = heuristic_parse("Save that prompt about Claude's rendering rules")
    assert out.kind == IntentKind.PROMPT_NOTE


def test_unknown_for_random_text():
    out = heuristic_parse("the weather is nice today")
    assert out.kind == IntentKind.UNKNOWN


def test_ambiguous_fields_flagged_when_time_missing():
    out = heuristic_parse("Can we meet Thursday?")
    assert "time" in out.ambiguous_fields
