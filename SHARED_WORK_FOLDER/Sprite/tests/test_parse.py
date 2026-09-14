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
