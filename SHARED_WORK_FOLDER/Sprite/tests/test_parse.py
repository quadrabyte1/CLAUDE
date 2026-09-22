"""Tests for sprite.parse — preprocessor regex and Ollama-mocked parse.

v0.5.0 additions (M3 alignment — day_hint / time_hint schema):
  Tests 1–8 below are the TDD regression suite written BEFORE the fix was
  implemented. They must fail against v0.4.0 code and pass after v0.5.0.
"""

from __future__ import annotations

import sys
from datetime import datetime, timezone
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from sprite.parse import (
    OllamaParseError,
    OllamaUnreachable,
    ParseResult,
    _INTENT_JSON_SCHEMA,
    _SYSTEM_PROMPT,
    _preprocess,
    parse_intent,
)


_NOW = datetime(2026, 9, 13, 14, 0, 0, tzinfo=timezone.utc)

# ---------------------------------------------------------------------------
# Herman cross-repo import (for wire tests)
# ---------------------------------------------------------------------------

_HERMAN_BRAIN_SRC = Path("/Volumes/GIT/CLAUDE/SHARED_WORK_FOLDER/Homunculus/brain")
if str(_HERMAN_BRAIN_SRC) not in sys.path:
    sys.path.insert(0, str(_HERMAN_BRAIN_SRC))

try:
    from homunculus_brain.schemas import ParsedCaptureRequest
    _HERMAN_AVAILABLE = True
except ImportError:
    _HERMAN_AVAILABLE = False


# ---------------------------------------------------------------------------
# Helper: call parse_intent with a mocked Ollama response
# ---------------------------------------------------------------------------


def _call_parse(transcript: str, llm_body: dict) -> ParseResult:
    """Helper: parse_intent with a mocked Ollama returning llm_body."""
    import json

    mock_resp = MagicMock()
    mock_resp.status_code = 200
    mock_resp.json.return_value = {"response": json.dumps(llm_body)}
    mock_resp.raise_for_status.return_value = None

    mock_client_instance = MagicMock()
    mock_client_instance.post.return_value = mock_resp
    mock_client_instance.__enter__ = MagicMock(return_value=mock_client_instance)
    mock_client_instance.__exit__ = MagicMock(return_value=False)

    with patch("sprite.parse.httpx.Client", return_value=mock_client_instance):
        return parse_intent(
            transcript,
            ollama_base_url="http://mock-ollama",
            ollama_model="qwen2.5:7b",
            captured_at=_NOW,
        )


# ===========================================================================
# TDD REGRESSION SUITE — v0.5.0 (must fail against v0.4.0, pass after fix)
# ===========================================================================

# --- Test 1: Regression from live incident ----------------------------------

def test_regression_tomorrow_at_10am_yields_hints_not_when_string():
    """Live incident 2026-09-14: Ollama returned when='thursday at 10am' which
    Herman rejected with HTTP 400. After v0.5.0 the LLM emits day_hint and
    time_hint, never a raw 'when' string that bypasses Herman's date_resolver.

    Mock Ollama returning the corrected v0.5 shape:
      day_hint='tomorrow', time_hint='10am', no 'when' key.
    ParsedIntent must have day_hint/time_hint set, when absent entirely.
    """
    result = _call_parse(
        "Let's set a second meeting with myself tomorrow at 10am.",
        {
            "verb": "schedule",
            "subject": "second meeting with myself",
            "day_hint": "tomorrow",
            "time_hint": "10am",
            "criticality": "normal",
            "confidence": 0.92,
            "ambiguous_fields": [],
        },
    )
    assert result.day_hint == "tomorrow", (
        f"Expected day_hint='tomorrow', got {result.day_hint!r}. "
        "LLM must emit day_hint, not compute a resolved date."
    )
    assert result.time_hint == "10am", (
        f"Expected time_hint='10am', got {result.time_hint!r}."
    )
    # The old `when` field must not exist on ParseResult at all.
    assert not hasattr(result, "when"), (
        "ParseResult must NOT have a 'when' field in v0.5.0. "
        "The old string-when path is gone."
    )


# --- Test 2: Schema-shape guard ---------------------------------------------

def test_schema_does_not_require_when_and_requires_hints():
    """_INTENT_JSON_SCHEMA must NOT list 'when' in 'required'.
    It MUST list 'day_hint' and 'time_hint' in 'required'.
    """
    required = _INTENT_JSON_SCHEMA.get("required", [])
    assert "when" not in required, (
        f"'when' must not be in schema required list. Got: {required}"
    )
    assert "day_hint" in required, (
        f"'day_hint' must be in schema required list. Got: {required}"
    )
    assert "time_hint" in required, (
        f"'time_hint' must be in schema required list. Got: {required}"
    )


# --- Test 3: Prompt teaches no math -----------------------------------------

def test_system_prompt_teaches_no_date_math():
    """_SYSTEM_PROMPT must instruct the LLM NOT to compute dates, and must
    include at least one few-shot example showing day_hint='tomorrow'.
    """
    prompt_lower = _SYSTEM_PROMPT.lower()

    # Must contain an explicit no-math instruction.
    no_math_phrases = ["do not compute", "do not know what today is", "do not resolve"]
    found_no_math = any(p in prompt_lower for p in no_math_phrases)
    assert found_no_math, (
        f"_SYSTEM_PROMPT must contain a 'do not compute' (or equivalent) instruction. "
        f"None of {no_math_phrases!r} found in prompt."
    )

    # Must have a few-shot example with day_hint="tomorrow".
    assert '"day_hint": "tomorrow"' in _SYSTEM_PROMPT or "'day_hint': 'tomorrow'" in _SYSTEM_PROMPT or 'day_hint":"tomorrow"' in _SYSTEM_PROMPT, (
        "_SYSTEM_PROMPT must include a few-shot example with day_hint='tomorrow'."
    )


# --- Test 4: build_request routing — hints-only path -----------------------

def test_build_request_with_hints_only_sends_none_when():
    """Given a ParseResult with day_hint/time_hint and no ISO when,
    build_request must produce when=None with hints present.
    """
    from sprite.herman import build_request
    from datetime import timezone

    # Simulate what the watcher does with a ParseResult that has no resolved date.
    payload = build_request(
        verb="schedule",
        subject="second meeting with myself",
        when=None,
        criticality="normal",
        confidence=0.92,
        raw_transcript="Let's set a second meeting with myself tomorrow at 10am.",
        audio_path="/tmp/test.m4a",
        captured_at=datetime(2026, 9, 14, 16, 42, 33, tzinfo=timezone.utc),
        day_hint="tomorrow",
        time_hint="10am",
    )
    assert payload["when"] is None, (
        f"when must be None when only hints are set, got {payload['when']!r}"
    )
    assert payload["day_hint"] == "tomorrow", (
        f"day_hint must be 'tomorrow', got {payload.get('day_hint')!r}"
    )
    assert payload["time_hint"] == "10am", (
        f"time_hint must be '10am', got {payload.get('time_hint')!r}"
    )


# --- Test 5: ISO precedence — explicit when clears hints --------------------

def test_build_request_iso_when_takes_precedence_over_hints():
    """When a clean ISO-8601 datetime is available, build_request sends
    when=<datetime-string> and the caller should pass no hints (or None hints
    are omitted from the wire payload).

    This validates that the explicit-when path is preserved for the rare case
    where the LLM or a future typed-text path provides a confirmed ISO datetime.
    """
    from sprite.herman import build_request
    from datetime import timezone

    iso_str = "2026-09-18T10:00:00-04:00"
    payload = build_request(
        verb="schedule",
        subject="dentist appointment",
        when=iso_str,
        criticality="normal",
        confidence=0.95,
        raw_transcript="dentist appointment September 18th at 10 AM",
        audio_path="/tmp/test.m4a",
        captured_at=datetime(2026, 9, 14, 12, 0, 0, tzinfo=timezone.utc),
        day_hint=None,    # No hints — explicit when is the source
        time_hint=None,
    )
    assert payload["when"] == iso_str, (
        f"Explicit when must pass through unchanged. Got {payload['when']!r}"
    )
    assert "day_hint" not in payload, (
        "day_hint must NOT appear in wire payload when it is None"
    )
    assert "time_hint" not in payload, (
        "time_hint must NOT appear in wire payload when it is None"
    )


# --- Test 6: v0.4 'when as string' path is gone -----------------------------

def test_parse_result_has_no_when_field():
    """ParseResult must NOT have a 'when' field. Constructing one with 'when'
    keyword must raise TypeError (unexpected keyword argument).

    This guards against silent reversion to the v0.4 shape where a raw
    string when='thursday at 10am' was passed to Herman and caused HTTP 400.
    """
    with pytest.raises(TypeError):
        # dataclass with no 'when' field must reject this kwarg
        ParseResult(
            verb="schedule",
            subject="test",
            when="thursday at 10am",   # must raise TypeError in v0.5
            criticality="normal",
            confidence=0.9,
            ambiguous_fields=[],
            raw_llm_json={},
        )


# --- Test 7: Cross-repo wire test — hints round-trip through Herman ---------

@pytest.mark.skipif(not _HERMAN_AVAILABLE, reason="Herman package not on path")
def test_wire_shape_hints_round_trip_through_herman_schema():
    """Payload from build_request(day_hint=..., time_hint=..., when=None) must
    validate cleanly through Herman's ParsedCaptureRequest.model_validate_json().
    This is the exact drift-detection pattern from Sprite M2.
    """
    import json
    from sprite.herman import build_request

    payload = build_request(
        verb="schedule",
        subject="second meeting with myself",
        when=None,
        criticality="normal",
        confidence=0.92,
        raw_transcript="Let's set a second meeting with myself tomorrow at 10am.",
        audio_path="/tmp/test.m4a",
        captured_at=datetime(2026, 9, 14, 16, 42, 33, tzinfo=timezone.utc),
        day_hint="tomorrow",
        time_hint="10am",
    )
    # Round-trip through Herman's Pydantic model.
    req = ParsedCaptureRequest.model_validate_json(json.dumps(payload))
    assert req.day_hint == "tomorrow", (
        f"day_hint did not survive the wire round-trip: {req.day_hint!r}"
    )
    assert req.time_hint == "10am", (
        f"time_hint did not survive the wire round-trip: {req.time_hint!r}"
    )
    assert req.when is None, (
        f"when must be None after round-trip, got {req.when!r}"
    )


# --- Test 8: End-to-end mock — "tomorrow at 10am" goes through clean --------

def test_end_to_end_tomorrow_at_10am_clean_dispatch():
    """Feed 'tomorrow at 10am' through parse_intent (Ollama mocked with v0.5
    shape), extract hints, build payload, verify it matches Herman's expected
    schema shape (when=None, day_hint/time_hint set, no 400-causing strings).
    """
    import json
    from sprite.herman import build_request

    # Step 1: parse (Ollama mock returns v0.5 hint shape)
    result = _call_parse(
        "Let's set a second meeting with myself tomorrow at 10am.",
        {
            "verb": "schedule",
            "subject": "second meeting with myself",
            "day_hint": "tomorrow",
            "time_hint": "10am",
            "criticality": "normal",
            "confidence": 0.92,
            "ambiguous_fields": [],
        },
    )

    # Step 2: build the Herman payload using hints from ParseResult
    payload = build_request(
        verb=result.verb,
        subject=result.subject,
        when=None,           # no ISO datetime from parse
        criticality=result.criticality,
        confidence=result.confidence,
        raw_transcript="Let's set a second meeting with myself tomorrow at 10am.",
        audio_path="/tmp/test.m4a",
        captured_at=datetime(2026, 9, 14, 16, 42, 33, tzinfo=timezone.utc),
        day_hint=result.day_hint,
        time_hint=result.time_hint,
    )

    # Step 3: assert the payload shape that Herman accepts
    assert payload["when"] is None, "when must be None — not a raw string"
    assert payload["day_hint"] == "tomorrow"
    assert payload["time_hint"] == "10am"
    assert "verb" in payload
    assert "subject" in payload
    assert payload["confidence"] >= 0.6

    # Step 4: verify Herman's schema accepts it (if available)
    if _HERMAN_AVAILABLE:
        req = ParsedCaptureRequest.model_validate_json(json.dumps(payload))
        assert req.when is None
        assert req.day_hint == "tomorrow"
        assert req.time_hint == "10am"


# ===========================================================================
# Preprocessor tests (no LLM) — unchanged from v0.4
# ===========================================================================


@pytest.mark.parametrize("text,expected_critical", [
    ("remember to call mark critical", True),
    ("this is important", True),
    ("urgent — fix the roof", True),
    ("don't let me forget the dentist", True),
    ("mark urgent", True),
    ("just a normal memo", False),
    ("mark the calendar", False),  # "mark" alone without critical/urgent
])
def test_preprocess_criticality(text, expected_critical):
    hints = _preprocess(text)
    assert hints.forced_critical == expected_critical, f"text={text!r}"


@pytest.mark.parametrize("text,expected_verb", [
    ("schedule a meeting with Jane", "schedule"),
    ("book a dentist appointment", "schedule"),
    ("avoid scheduling anything Friday", "avoid"),
    ("Sam is allergic to peanuts", "avoid"),
    ("note that the LED reflects off the terrazzo", "note"),
    ("remember this: the deck is 23 feet wide", "note"),
    ("call the plumber back", "handle"),
    ("remind me to pick up the dry cleaning", "handle"),
    ("handle the invoice", "handle"),
    ("this is a random utterance xyz", None),
])
def test_preprocess_verb_hint(text, expected_verb):
    hints = _preprocess(text)
    assert hints.verb_hint == expected_verb, f"text={text!r} got verb_hint={hints.verb_hint!r}"


def test_preprocess_critical_and_verb_together():
    hints = _preprocess("schedule the roofing inspection, mark critical")
    assert hints.forced_critical is True
    assert hints.verb_hint == "schedule"


# ===========================================================================
# Ollama mock — happy path (v0.5 schema shape)
# ===========================================================================


def test_parse_schedule_verb():
    result = _call_parse(
        "coffee with Jane tomorrow at 10am",
        {
            "verb": "schedule",
            "subject": "coffee with Jane",
            "day_hint": "tomorrow",
            "time_hint": "10am",
            "criticality": "normal",
            "confidence": 0.9,
            "ambiguous_fields": [],
        },
    )
    assert result.verb == "schedule"
    assert result.subject == "coffee with Jane"
    assert result.day_hint == "tomorrow"
    assert result.time_hint == "10am"
    assert result.criticality == "normal"
    assert result.confidence == 0.9
    assert result.ambiguous_fields == []


def test_parse_note_verb_no_time():
    result = _call_parse(
        "note that the LED reflects off the terrazzo",
        {
            "verb": "note",
            "subject": "LED reflects off terrazzo",
            "day_hint": None,
            "time_hint": None,
            "criticality": "normal",
            "confidence": 0.85,
            "ambiguous_fields": [],
        },
    )
    assert result.verb == "note"
    assert result.day_hint is None
    assert result.time_hint is None


def test_parse_handle_verb():
    result = _call_parse(
        "call the plumber back",
        {
            "verb": "handle",
            "subject": "call plumber back",
            "day_hint": None,
            "time_hint": None,
            "criticality": "normal",
            "confidence": 0.88,
            "ambiguous_fields": [],
        },
    )
    assert result.verb == "handle"


def test_parse_avoid_verb():
    result = _call_parse(
        "Sam is allergic to dairy — avoid dairy at all our meetings",
        {
            "verb": "avoid",
            "subject": "Sam dairy allergy",
            "day_hint": None,
            "time_hint": None,
            "criticality": "normal",
            "confidence": 0.92,
            "ambiguous_fields": [],
        },
    )
    assert result.verb == "avoid"


def test_preprocessor_forces_critical_over_llm_normal():
    """Even if LLM returns normal, preprocessor's forced_critical wins."""
    result = _call_parse(
        "call the deck contractor, mark critical",
        {
            "verb": "handle",
            "subject": "call deck contractor",
            "day_hint": None,
            "time_hint": None,
            "criticality": "normal",  # LLM says normal — preprocessor overrides
            "confidence": 0.85,
            "ambiguous_fields": [],
        },
    )
    assert result.criticality == "critical"


def test_preprocessor_does_not_downgrade_llm_critical():
    """LLM can independently signal critical even without preprocessor trigger."""
    result = _call_parse(
        "call the deck contractor",
        {
            "verb": "handle",
            "subject": "call deck contractor",
            "day_hint": None,
            "time_hint": None,
            "criticality": "critical",  # LLM decided critical
            "confidence": 0.85,
            "ambiguous_fields": [],
        },
    )
    assert result.criticality == "critical"


# ===========================================================================
# Confidence gate and ambiguous_fields
# ===========================================================================


def test_parse_low_confidence_still_returns_result():
    """parse_intent returns the result even with low confidence; the caller gates."""
    result = _call_parse(
        "mumble mumble something",
        {
            "verb": "note",
            "subject": "something",
            "day_hint": None,
            "time_hint": None,
            "criticality": "normal",
            "confidence": 0.3,
            "ambiguous_fields": ["subject"],
        },
    )
    assert result.confidence == 0.3
    assert "subject" in result.ambiguous_fields


def test_parse_ambiguous_fields_propagated():
    result = _call_parse(
        "meet with someone next week sometime",
        {
            "verb": "schedule",
            "subject": "meeting",
            "day_hint": "next week",
            "time_hint": None,
            "criticality": "normal",
            "confidence": 0.55,
            "ambiguous_fields": ["day_hint", "subject"],
        },
    )
    assert set(result.ambiguous_fields) == {"day_hint", "subject"}


def test_parse_absolute_date_in_day_hint():
    """'September 18th at 10 AM' → day_hint='September 18th', time_hint='10 AM'."""
    result = _call_parse(
        "dentist appointment September 18th at 10 AM",
        {
            "verb": "schedule",
            "subject": "dentist appointment",
            "day_hint": "September 18th",
            "time_hint": "10 AM",
            "criticality": "normal",
            "confidence": 0.93,
            "ambiguous_fields": [],
        },
    )
    assert result.day_hint == "September 18th"
    assert result.time_hint == "10 AM"


def test_parse_relative_day_no_time():
    """'next Tuesday' → day_hint='next Tuesday', time_hint=None."""
    result = _call_parse(
        "gym next Tuesday",
        {
            "verb": "schedule",
            "subject": "gym",
            "day_hint": "next Tuesday",
            "time_hint": None,
            "criticality": "normal",
            "confidence": 0.88,
            "ambiguous_fields": [],
        },
    )
    assert result.day_hint == "next Tuesday"
    assert result.time_hint is None


def test_parse_bare_time_without_ampm_in_time_hint():
    """'5:35' (no AM/PM) must go into time_hint as-is.
    Sprite's LLM must NOT guess AM or PM. Herman's date_resolver flags ambiguity.
    """
    result = _call_parse(
        "call the contractor at 5:35",
        {
            "verb": "handle",
            "subject": "call the contractor",
            "day_hint": None,
            "time_hint": "5:35",   # verbatim — no AM/PM added
            "criticality": "normal",
            "confidence": 0.85,
            "ambiguous_fields": ["time_hint"],   # ambiguous: AM vs PM unknown
        },
    )
    # time_hint must be exactly as spoken — no AM/PM suffix added by Sprite
    assert result.time_hint == "5:35", (
        f"LLM must not guess AM/PM. Expected '5:35', got {result.time_hint!r}"
    )
    assert "time_hint" in result.ambiguous_fields, (
        "Bare time without AM/PM should be listed in ambiguous_fields"
    )


# ===========================================================================
# Error paths — unchanged from v0.4
# ===========================================================================


def test_ollama_unreachable_raises():
    import httpx

    mock_client_instance = MagicMock()
    mock_client_instance.post.side_effect = httpx.ConnectError("refused")
    mock_client_instance.__enter__ = MagicMock(return_value=mock_client_instance)
    mock_client_instance.__exit__ = MagicMock(return_value=False)

    with patch("sprite.parse.httpx.Client", return_value=mock_client_instance):
        with pytest.raises(OllamaUnreachable):
            parse_intent(
                "test",
                ollama_base_url="http://localhost:11434",
                ollama_model="qwen2.5:7b",
            )


def test_ollama_bad_json_raises_parse_error():
    mock_resp = MagicMock()
    mock_resp.status_code = 200
    mock_resp.json.return_value = {"response": "not json at all {{{"}
    mock_resp.raise_for_status.return_value = None

    mock_client_instance = MagicMock()
    mock_client_instance.post.return_value = mock_resp
    mock_client_instance.__enter__ = MagicMock(return_value=mock_client_instance)
    mock_client_instance.__exit__ = MagicMock(return_value=False)

    with patch("sprite.parse.httpx.Client", return_value=mock_client_instance):
        with pytest.raises(OllamaParseError):
            parse_intent(
                "test",
                ollama_base_url="http://mock",
                ollama_model="qwen2.5:7b",
            )


def test_ollama_missing_required_key_raises_parse_error():
    """If Ollama JSON is valid but missing a required key, we raise OllamaParseError."""
    import json

    body_missing_confidence = {
        "verb": "note",
        "subject": "test",
        "day_hint": None,
        "time_hint": None,
        "criticality": "normal",
        # "confidence" is missing
        "ambiguous_fields": [],
    }

    mock_resp = MagicMock()
    mock_resp.status_code = 200
    mock_resp.json.return_value = {"response": json.dumps(body_missing_confidence)}
    mock_resp.raise_for_status.return_value = None

    mock_client_instance = MagicMock()
    mock_client_instance.post.return_value = mock_resp
    mock_client_instance.__enter__ = MagicMock(return_value=mock_client_instance)
    mock_client_instance.__exit__ = MagicMock(return_value=False)

    with patch("sprite.parse.httpx.Client", return_value=mock_client_instance):
        with pytest.raises(OllamaParseError):
            parse_intent(
                "test",
                ollama_base_url="http://mock",
                ollama_model="qwen2.5:7b",
            )


# ===========================================================================
# TDD REGRESSION SUITE — v0.8.0 (must fail before fix, pass after fix)
#
# Design rule: for verb=schedule AND time_hint is a bare hour in {1,2,3,4,5}
# (no AM/PM marker, no minutes) → LLM must emit ambiguous_fields=[] (PM assumed).
# All other cases keep the existing caution (ambiguous_fields=["time_hint"]).
# ===========================================================================


# --- Sprite Test 1: Jake's VCA incident — schedule at bare-hour 3 → NOT ambiguous

def test_v080_schedule_bare_hour_3_not_ambiguous():
    """Live incident: 'Schedule Jake's VCA check on September 20th at 3'
    → verb=schedule, time_hint='3', ambiguous_fields=[] (PM assumed, no question).

    The LLM must emit an empty ambiguous_fields for verb=schedule + bare hour 1-5.
    The _SYSTEM_PROMPT must teach this rule with a few-shot example.
    ParseResult.ambiguous_fields must be [] when the LLM says so.
    """
    result = _call_parse(
        "Schedule Jake's VCA check on September 20th at 3",
        {
            "verb": "schedule",
            "subject": "Jake's VCA check",
            "day_hint": "September 20th",
            "time_hint": "3",
            "criticality": "normal",
            "confidence": 0.87,
            "ambiguous_fields": [],   # <-- new behavior: PM inferred, no flag
        },
    )
    assert result.verb == "schedule"
    assert result.time_hint == "3"
    assert result.ambiguous_fields == [], (
        f"For verb=schedule + bare hour 1-5, ambiguous_fields must be [] "
        f"(PM assumed). Got {result.ambiguous_fields!r}"
    )


# --- Sprite Test 2: verb=remind + bare hour 3 → STILL ambiguous

def test_v080_remind_bare_hour_3_still_ambiguous():
    """Remind at bare-hour 3 MUST still flag time_hint as ambiguous.

    The PM-inference rule is scoped to verb=schedule only. Reminders can be
    middle-of-night (medication, alarm clocks). Only schedule gets the inference.
    """
    result = _call_parse(
        "Remind me at 3 to call the vet",
        {
            "verb": "remind",
            "subject": "call the vet",
            "day_hint": None,
            "time_hint": "3",
            "criticality": "normal",
            "confidence": 0.85,
            "ambiguous_fields": ["time_hint"],   # <-- kept: AM or PM?
        },
    )
    assert result.verb == "remind"
    assert result.time_hint == "3"
    assert "time_hint" in result.ambiguous_fields, (
        f"For verb=remind + bare hour, time_hint must remain in ambiguous_fields. "
        f"Got {result.ambiguous_fields!r}"
    )


# --- Sprite Test 3: schedule at hour 6 → STILL ambiguous (6 out of PM window)

def test_v080_schedule_bare_hour_6_still_ambiguous():
    """Schedule at bare hour 6 must still be ambiguous.

    6 AM (early-morning call) vs 6 PM (after-work meeting) are both common.
    The PM-inference window is locked to hours 1-5 only (per design rule).
    """
    result = _call_parse(
        "Schedule the team sync on Tuesday at 6",
        {
            "verb": "schedule",
            "subject": "team sync",
            "day_hint": "Tuesday",
            "time_hint": "6",
            "criticality": "normal",
            "confidence": 0.84,
            "ambiguous_fields": ["time_hint"],   # 6 stays ambiguous
        },
    )
    assert result.verb == "schedule"
    assert result.time_hint == "6"
    assert "time_hint" in result.ambiguous_fields, (
        f"Hour 6 must stay ambiguous (not in the 1-5 PM window). "
        f"Got {result.ambiguous_fields!r}"
    )


# --- Sprite Test 4: schema guard — _SYSTEM_PROMPT contains the new few-shot examples

def test_v080_system_prompt_contains_schedule_bare_hour_pm_example():
    """_SYSTEM_PROMPT must contain a few-shot example demonstrating that
    verb=schedule + time_hint='3' (bare hour) → ambiguous_fields=[].

    This documents the rule in the prompt so the LLM can follow it.
    The example must be distinguishable from the 'remind at 3 → ambiguous' example.
    """
    prompt = _SYSTEM_PROMPT

    # Must contain an example with schedule + bare hour + empty ambiguous list.
    schedule_bare_pm = (
        '"verb":"schedule"' in prompt.replace(" ", "") and
        '"ambiguous_fields":[]' in prompt.replace(" ", "")
    )
    assert schedule_bare_pm, (
        "_SYSTEM_PROMPT must include a few-shot example showing "
        "verb=schedule + bare time_hint + ambiguous_fields=[] (PM assumed). "
        "This teaches the LLM the new PM-inference rule."
    )

    # Must also show that remind/handle with the same bare hour stays ambiguous.
    has_remind_stays_ambiguous = (
        '"verb":"remind"' in prompt.replace(" ", "") or
        '"verb":"handle"' in prompt.replace(" ", "")
    )
    assert has_remind_stays_ambiguous, (
        "_SYSTEM_PROMPT must include at least one remind/handle few-shot example "
        "showing that bare-hour ambiguity is KEPT for non-schedule verbs."
    )


# --- Sprite Test 12: cross-repo wire-shape round-trip (v0.8.0 PM-inferred payload)

@pytest.mark.skipif(not _HERMAN_AVAILABLE, reason="Herman package not on path")
def test_v080_wire_shape_schedule_bare_hour_round_trips_herman():
    """Sprite's build_request() with verb=schedule, time_hint='3', ambiguous=[]
    must survive ParsedCaptureRequest.model_validate_json() round-trip.

    This is the cross-repo wire-shape drift-detection guard: if Sprite emits
    time_hint='3' without flagging it ambiguous, Herman must accept it cleanly
    (not reject it for schema reasons). The clarifying-question vs. PM-inference
    decision lives in date_resolver at request-dispatch time, not at the schema
    level.
    """
    import json
    from sprite.herman import build_request

    payload = build_request(
        verb="schedule",
        subject="Jake's VCA check",
        when=None,
        criticality="normal",
        confidence=0.87,
        raw_transcript="Let's set Jake's VCA annual check-up on September 20th at three.",
        audio_path="/Users/thomas/sprite/audio/2026-09-21.m4a",
        captured_at=datetime(2026, 9, 21, 13, 36, 0, tzinfo=timezone.utc),
        day_hint="September 20th",
        time_hint="3",
    )
    # The payload must be accepted by Herman's ParsedCaptureRequest without error.
    req = ParsedCaptureRequest.model_validate_json(json.dumps(payload))
    assert req.verb.value == "schedule"
    assert req.time_hint == "3"
    assert req.day_hint == "September 20th"
    assert req.when is None, "when must be None — hints are the source"


# ===========================================================================
# TDD REGRESSION SUITE — v0.8.1 (must fail before fix, pass after fix)
#
# Root cause: The 7B model ignores the prompt's exception rule and flags
# time_hint as ambiguous even for verb=schedule + bare 1-5. Prompt-only
# fixes don't hold reliably. The fix is a post-LLM code override in
# parse_intent() that mirrors the existing preprocessor-criticality override:
# "LLM output is a suggestion; code has authority on the conditional."
#
# These tests simulate the LLM's known-bad output (ambiguous_fields includes
# "time_hint") and assert that the post-processor strips it.
# ===========================================================================


# --- v0.8.1 Test 1: Live incident regression — LLM returns time_hint ambiguous
#     for schedule + bare-3. Post-processor must strip it.

def test_v081_live_incident_schedule_bare_3_llm_returns_ambiguous_post_strips():
    """Live incident 2026-09-21: LLM returned
      {verb='schedule', time_hint='3', ambiguous_fields=['time_hint']}
    even with the v0.8.0 prompt teaching the exception. The 7B model ignored
    the rule. After v0.8.1 the post-LLM code override strips 'time_hint' from
    ambiguous_fields for verb=schedule + bare 1-5.

    This test simulates the exact bad LLM output and asserts the fix.
    """
    result = _call_parse(
        "Schedule Jake's VCA annual check-up on September 20th at three.",
        {
            "verb": "schedule",
            "subject": "Jake's VCA annual check-up",
            "day_hint": "September 20th",
            "time_hint": "3",
            "criticality": "normal",
            "confidence": 0.844,
            "ambiguous_fields": ["time_hint"],  # LLM's bad output — must be stripped
        },
    )
    assert result.ambiguous_fields == [], (
        f"Post-processor must strip 'time_hint' for verb=schedule + bare hour 1-5. "
        f"LLM returned ambiguous_fields=['time_hint'] but code override must clear it. "
        f"Got {result.ambiguous_fields!r}"
    )


# --- v0.8.1 Test 2: Pattern coverage — all 10 bare values stripped for schedule

_BARE_1_5_DIGIT = ["1", "2", "3", "4", "5"]
_BARE_1_5_WORD = ["one", "two", "three", "four", "five"]


@pytest.mark.parametrize("time_hint_val", _BARE_1_5_DIGIT + _BARE_1_5_WORD)
def test_v081_schedule_all_bare_1_5_llm_ambiguous_stripped(time_hint_val):
    """For all 10 bare-1-5 values (digit and word), if LLM flags time_hint
    ambiguous and verb=schedule, the post-processor must strip it.
    """
    result = _call_parse(
        f"Schedule something at {time_hint_val}",
        {
            "verb": "schedule",
            "subject": "something",
            "day_hint": "tomorrow",
            "time_hint": time_hint_val,
            "criticality": "normal",
            "confidence": 0.85,
            "ambiguous_fields": ["time_hint"],  # LLM's bad output
        },
    )
    assert result.ambiguous_fields == [], (
        f"time_hint={time_hint_val!r}: post-processor must strip 'time_hint' "
        f"for verb=schedule + bare 1-5. Got {result.ambiguous_fields!r}"
    )


# --- v0.8.1 Test 3: Scoping — remind verb keeps caution (no stripping)

def test_v081_remind_bare_3_llm_ambiguous_not_stripped():
    """verb=remind + bare hour 3 + LLM flags ambiguous → post-processor must
    NOT strip it. The PM-inference rule is schedule-only.
    Reminders can legitimately fire at 3 AM (medication, alarms).
    """
    result = _call_parse(
        "Remind me at 3 to take the medication",
        {
            "verb": "remind",
            "subject": "take the medication",
            "day_hint": None,
            "time_hint": "3",
            "criticality": "normal",
            "confidence": 0.85,
            "ambiguous_fields": ["time_hint"],
        },
    )
    assert "time_hint" in result.ambiguous_fields, (
        f"For verb=remind + bare hour, 'time_hint' must remain in ambiguous_fields. "
        f"Got {result.ambiguous_fields!r}"
    )


# --- v0.8.1 Test 4: Scoping — handle verb keeps caution (no stripping)

def test_v081_handle_bare_3_llm_ambiguous_not_stripped():
    """verb=handle + bare hour 3 + LLM flags ambiguous → post-processor must
    NOT strip it. Bare-hour do-items can be AM or PM.
    """
    result = _call_parse(
        "Call the vet at 3",
        {
            "verb": "handle",
            "subject": "call the vet",
            "day_hint": None,
            "time_hint": "3",
            "criticality": "normal",
            "confidence": 0.85,
            "ambiguous_fields": ["time_hint"],
        },
    )
    assert "time_hint" in result.ambiguous_fields, (
        f"For verb=handle + bare hour, 'time_hint' must remain in ambiguous_fields. "
        f"Got {result.ambiguous_fields!r}"
    )


# --- v0.8.1 Test 5: Hour 6 preserved for schedule verb (out of PM window)

def test_v081_schedule_bare_6_llm_ambiguous_not_stripped():
    """verb=schedule + bare hour 6 + LLM flags ambiguous → post-processor must
    NOT strip it. Hour 6 is outside the 1-5 PM-inference window by design.
    """
    result = _call_parse(
        "Schedule the team call on Tuesday at 6",
        {
            "verb": "schedule",
            "subject": "team call",
            "day_hint": "Tuesday",
            "time_hint": "6",
            "criticality": "normal",
            "confidence": 0.84,
            "ambiguous_fields": ["time_hint"],
        },
    )
    assert "time_hint" in result.ambiguous_fields, (
        f"Hour 6 must stay ambiguous (not in 1-5 PM window). "
        f"Got {result.ambiguous_fields!r}"
    )


# --- v0.8.1 Test 6: Explicit AM/PM present — no stripping, not an override case

def test_v081_schedule_explicit_pm_llm_sends_clean_no_change():
    """verb=schedule + time_hint='3 PM' (explicit AM/PM) + LLM sends ambiguous=[]
    → post-processor leaves it alone. Not an override case — explicit is fine.
    """
    result = _call_parse(
        "Schedule the meeting at 3 PM",
        {
            "verb": "schedule",
            "subject": "the meeting",
            "day_hint": "tomorrow",
            "time_hint": "3 PM",
            "criticality": "normal",
            "confidence": 0.90,
            "ambiguous_fields": [],
        },
    )
    assert result.ambiguous_fields == [], (
        f"Explicit PM with clean ambiguous_fields must stay clean. "
        f"Got {result.ambiguous_fields!r}"
    )


# --- v0.8.1 Test 7: Colon present (minutes qualifier) — not stripped

def test_v081_schedule_colon_time_ambiguous_not_stripped():
    """verb=schedule + time_hint='3:30' (has colon/minutes) + LLM flags ambiguous
    → post-processor must NOT strip. The rule only covers bare hours with
    no colon (no minutes qualifier).
    """
    result = _call_parse(
        "Schedule the call at 3:30",
        {
            "verb": "schedule",
            "subject": "the call",
            "day_hint": "tomorrow",
            "time_hint": "3:30",
            "criticality": "normal",
            "confidence": 0.85,
            "ambiguous_fields": ["time_hint"],
        },
    )
    assert "time_hint" in result.ambiguous_fields, (
        f"time_hint='3:30' has minutes; must NOT be stripped by bare-hour rule. "
        f"Got {result.ambiguous_fields!r}"
    )


# --- v0.8.1 Test 8: Only time_hint stripped, other ambiguous fields preserved

def test_v081_schedule_strips_only_time_hint_preserves_others():
    """When verb=schedule + bare 1-5 + LLM flags ['time_hint', 'day_hint'],
    the post-processor strips ONLY 'time_hint' and leaves 'day_hint' intact.
    """
    result = _call_parse(
        "Schedule something at 3 some time soon",
        {
            "verb": "schedule",
            "subject": "something",
            "day_hint": "some time soon",
            "time_hint": "3",
            "criticality": "normal",
            "confidence": 0.60,
            "ambiguous_fields": ["time_hint", "day_hint"],
        },
    )
    assert "time_hint" not in result.ambiguous_fields, (
        f"'time_hint' must be stripped for schedule + bare 1-5. "
        f"Got {result.ambiguous_fields!r}"
    )
    assert "day_hint" in result.ambiguous_fields, (
        f"'day_hint' must be preserved (not stripped). "
        f"Got {result.ambiguous_fields!r}"
    )


# ===========================================================================
# v0.10.0 TDD — stop_all_timers and reset_timer new verbs
# ===========================================================================


# ---------------------------------------------------------------------------
# Test 1 (v0.10): LLM mocked → stop_all_timers on "Stop all timers"
# ---------------------------------------------------------------------------

def test_stop_all_timers_verb_parsed_from_mock():
    """LLM mock returning stop_all_timers → ParsedIntent.verb == 'stop_all_timers'."""
    result = _call_parse(
        "Stop all timers",
        {
            "verb": "stop_all_timers",
            "subject": "all timers",
            "project": None,
            "day_hint": None,
            "time_hint": None,
            "criticality": "normal",
            "confidence": 0.97,
            "ambiguous_fields": [],
        },
    )
    assert result.verb == "stop_all_timers", f"Expected stop_all_timers, got {result.verb!r}"
    assert result.project is None, f"project must be None for stop_all_timers, got {result.project!r}"


def test_stop_all_timers_stop_everything_variant():
    """LLM mock on 'Stop everything' → verb=stop_all_timers."""
    result = _call_parse(
        "Stop everything",
        {
            "verb": "stop_all_timers",
            "subject": "everything",
            "project": None,
            "day_hint": None,
            "time_hint": None,
            "criticality": "normal",
            "confidence": 0.95,
            "ambiguous_fields": [],
        },
    )
    assert result.verb == "stop_all_timers"


def test_stop_all_timers_stop_all_variant():
    """LLM mock on 'Stop all' → verb=stop_all_timers."""
    result = _call_parse(
        "Stop all",
        {
            "verb": "stop_all_timers",
            "subject": "all",
            "project": None,
            "day_hint": None,
            "time_hint": None,
            "criticality": "normal",
            "confidence": 0.96,
            "ambiguous_fields": [],
        },
    )
    assert result.verb == "stop_all_timers"


# ---------------------------------------------------------------------------
# Test 2 (v0.10): LLM mocked → reset_timer on "Reset gym"
# ---------------------------------------------------------------------------

def test_reset_timer_verb_parsed_from_mock():
    """LLM mock returning reset_timer → ParsedIntent.verb == 'reset_timer', project='gym'."""
    result = _call_parse(
        "Reset gym",
        {
            "verb": "reset_timer",
            "subject": "gym",
            "project": "gym",
            "day_hint": None,
            "time_hint": None,
            "criticality": "normal",
            "confidence": 0.96,
            "ambiguous_fields": [],
        },
    )
    assert result.verb == "reset_timer", f"Expected reset_timer, got {result.verb!r}"
    assert result.project == "gym", f"Expected project='gym', got {result.project!r}"


def test_reset_timer_clear_variant():
    """LLM mock on 'Clear gym timer' → verb=reset_timer, project='gym'."""
    result = _call_parse(
        "Clear gym timer",
        {
            "verb": "reset_timer",
            "subject": "gym",
            "project": "gym",
            "day_hint": None,
            "time_hint": None,
            "criticality": "normal",
            "confidence": 0.94,
            "ambiguous_fields": [],
        },
    )
    assert result.verb == "reset_timer"
    assert result.project == "gym"


# ---------------------------------------------------------------------------
# Test 3 (v0.10): Schema enum guard — both new verbs in enum
# ---------------------------------------------------------------------------

def test_schema_enum_contains_stop_all_timers():
    """_INTENT_JSON_SCHEMA verb enum must include 'stop_all_timers'."""
    verb_enum = _INTENT_JSON_SCHEMA["properties"]["verb"]["enum"]
    assert "stop_all_timers" in verb_enum, (
        f"'stop_all_timers' not in verb enum. Current enum: {verb_enum}"
    )


def test_schema_enum_contains_reset_timer():
    """_INTENT_JSON_SCHEMA verb enum must include 'reset_timer'."""
    verb_enum = _INTENT_JSON_SCHEMA["properties"]["verb"]["enum"]
    assert "reset_timer" in verb_enum, (
        f"'reset_timer' not in verb enum. Current enum: {verb_enum}"
    )


# ---------------------------------------------------------------------------
# Test 4 (v0.10): Prompt guard — few-shot examples in _SYSTEM_PROMPT
# ---------------------------------------------------------------------------

def test_system_prompt_has_stop_all_timers_example():
    """_SYSTEM_PROMPT must contain a few-shot example for stop_all_timers."""
    assert "stop_all_timers" in _SYSTEM_PROMPT, (
        "_SYSTEM_PROMPT must include at least one 'stop_all_timers' example."
    )


def test_system_prompt_has_reset_timer_example():
    """_SYSTEM_PROMPT must contain a few-shot example for reset_timer."""
    assert "reset_timer" in _SYSTEM_PROMPT, (
        "_SYSTEM_PROMPT must include at least one 'reset_timer' example."
    )


# ---------------------------------------------------------------------------
# Test 5 (v0.10): Disambiguation — "Stop gym" stays stop_timer, not stop_all_timers
# ---------------------------------------------------------------------------

def test_stop_gym_stays_stop_timer_not_stop_all():
    """'Stop gym' must parse as stop_timer (single project), not stop_all_timers."""
    result = _call_parse(
        "Stop gym",
        {
            "verb": "stop_timer",
            "subject": "gym",
            "project": "gym",
            "day_hint": None,
            "time_hint": None,
            "criticality": "normal",
            "confidence": 0.96,
            "ambiguous_fields": [],
        },
    )
    assert result.verb == "stop_timer", (
        f"'Stop gym' must be stop_timer (not stop_all_timers). Got: {result.verb!r}"
    )
    assert result.project == "gym"
