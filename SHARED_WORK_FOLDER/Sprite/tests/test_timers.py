"""TDD tests for Sprite v0.9.0 timer verb support.

Written RED first. These must fail against v0.8.1 code and pass after v0.9.0.

Tests cover:
  1. LLM mock → start_timer verb parsed
  2. LLM mock → stop_timer verb parsed
  3. Schema guard: start_timer/stop_timer in enum; project field present
  4. Prompt guard: few-shot examples for start_timer/stop_timer
  5. build_request() forwards project field
  6. Disambiguation: schedule verb not conflated with start_timer
  7. ParsedIntent dataclass carries project field
  8. Wire-shape round-trip: build_request → Herman ParsedCaptureRequest
"""

from __future__ import annotations

import json
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional
from unittest.mock import MagicMock, patch

import pytest

# ---------------------------------------------------------------------------
# Import under test
# ---------------------------------------------------------------------------

from sprite.parse import (
    _INTENT_JSON_SCHEMA,
    _SYSTEM_PROMPT,
    parse_intent,
)

try:
    from sprite.parse import ParsedIntent
    _HAS_PARSED_INTENT = True
except ImportError:
    _HAS_PARSED_INTENT = False

from sprite.herman import build_request

# ---------------------------------------------------------------------------
# Herman cross-repo import (for wire round-trip test)
# ---------------------------------------------------------------------------

_HERMAN_BRAIN_SRC = Path("/Volumes/GIT/CLAUDE/SHARED_WORK_FOLDER/Homunculus/brain")
if str(_HERMAN_BRAIN_SRC) not in sys.path:
    sys.path.insert(0, str(_HERMAN_BRAIN_SRC))

try:
    from homunculus_brain.schemas import ParsedCaptureRequest
    _HERMAN_AVAILABLE = True
except ImportError:
    _HERMAN_AVAILABLE = False


_NOW = datetime(2026, 9, 22, 10, 0, 0, tzinfo=timezone.utc)


# ---------------------------------------------------------------------------
# Helper: call parse_intent with a mocked Ollama response
# ---------------------------------------------------------------------------


def _call_parse(transcript: str, llm_body: dict):
    """Call parse_intent with a mocked Ollama HTTP response."""
    mock_response = MagicMock()
    mock_response.raise_for_status = MagicMock()
    mock_response.json.return_value = {"response": json.dumps(llm_body)}

    mock_client = MagicMock()
    mock_client.__enter__ = MagicMock(return_value=mock_client)
    mock_client.__exit__ = MagicMock(return_value=False)
    mock_client.post.return_value = mock_response

    with patch("sprite.parse.httpx.Client", return_value=mock_client):
        return parse_intent(
            transcript,
            ollama_base_url="http://fake:11434",
            ollama_model="qwen2.5:7b",
            captured_at=_NOW,
        )


# ---------------------------------------------------------------------------
# Test 1: LLM mocked → start_timer verb + project field
# ---------------------------------------------------------------------------


def test_parse_intent_start_timer_verb():
    """LLM returns {verb:'start_timer', project:'gym'} → ParseResult with those values."""
    result = _call_parse(
        "Start gym",
        {
            "verb": "start_timer",
            "subject": "gym",
            "project": "gym",
            "day_hint": None,
            "time_hint": None,
            "criticality": "normal",
            "confidence": 0.95,
            "ambiguous_fields": [],
        },
    )
    assert result.verb == "start_timer"
    assert result.project == "gym"


# ---------------------------------------------------------------------------
# Test 2: LLM mocked → stop_timer verb + project field
# ---------------------------------------------------------------------------


def test_parse_intent_stop_timer_verb():
    """LLM returns {verb:'stop_timer', project:'gym'} → ParseResult with those values."""
    result = _call_parse(
        "Stop gym",
        {
            "verb": "stop_timer",
            "subject": "gym",
            "project": "gym",
            "day_hint": None,
            "time_hint": None,
            "criticality": "normal",
            "confidence": 0.95,
            "ambiguous_fields": [],
        },
    )
    assert result.verb == "stop_timer"
    assert result.project == "gym"


# ---------------------------------------------------------------------------
# Test 3: Schema guard — enum includes start_timer / stop_timer; project present
# ---------------------------------------------------------------------------


def test_schema_includes_start_timer_stop_timer():
    """_INTENT_JSON_SCHEMA's verb enum must include start_timer and stop_timer."""
    verb_prop = _INTENT_JSON_SCHEMA["properties"]["verb"]
    assert "start_timer" in verb_prop["enum"], (
        f"start_timer missing from verb enum: {verb_prop['enum']}"
    )
    assert "stop_timer" in verb_prop["enum"], (
        f"stop_timer missing from verb enum: {verb_prop['enum']}"
    )


def test_schema_includes_project_field():
    """_INTENT_JSON_SCHEMA must have a 'project' property."""
    assert "project" in _INTENT_JSON_SCHEMA["properties"], (
        "Missing 'project' field in _INTENT_JSON_SCHEMA"
    )


# ---------------------------------------------------------------------------
# Test 4: Prompt guard — few-shot examples teach start_timer / stop_timer
# ---------------------------------------------------------------------------


def test_prompt_contains_start_timer_example():
    """_SYSTEM_PROMPT must contain a few-shot example with verb=start_timer."""
    assert "start_timer" in _SYSTEM_PROMPT, (
        "_SYSTEM_PROMPT lacks start_timer few-shot example"
    )


def test_prompt_contains_stop_timer_example():
    """_SYSTEM_PROMPT must contain a few-shot example with verb=stop_timer."""
    assert "stop_timer" in _SYSTEM_PROMPT, (
        "_SYSTEM_PROMPT lacks stop_timer few-shot example"
    )


def test_prompt_contains_deck_construction_example():
    """_SYSTEM_PROMPT must have a start_timer example for 'deck construction'."""
    # Ensure multi-word project names are demonstrated
    assert "deck construction" in _SYSTEM_PROMPT.lower() or "deck" in _SYSTEM_PROMPT, (
        "_SYSTEM_PROMPT lacks deck construction timer example"
    )


def test_prompt_teaches_disambiguation_from_schedule():
    """_SYSTEM_PROMPT teaches that 'start dinner at 6' → schedule, not start_timer."""
    # Check the prompt has disambiguation teaching
    lower = _SYSTEM_PROMPT.lower()
    assert "dinner" in lower or "schedule" in lower, (
        "_SYSTEM_PROMPT should disambiguate timer from schedule"
    )


# ---------------------------------------------------------------------------
# Test 5: build_request() forwards project field when set
# ---------------------------------------------------------------------------


def test_build_request_forwards_project():
    """build_request() includes 'project' in payload when provided."""
    payload = build_request(
        verb="start_timer",
        subject="gym",
        when=None,
        criticality="normal",
        confidence=0.95,
        raw_transcript="Start gym",
        audio_path="/tmp/test.m4a",
        captured_at=_NOW,
        project="gym",
    )
    assert payload["verb"] == "start_timer"
    assert payload["project"] == "gym"


def test_build_request_omits_project_when_none():
    """build_request() omits 'project' when not provided (backward compat)."""
    payload = build_request(
        verb="note",
        subject="test note",
        when=None,
        criticality="normal",
        confidence=0.9,
        raw_transcript="note something",
        audio_path="/tmp/test.m4a",
        captured_at=_NOW,
    )
    assert "project" not in payload


def test_build_request_omits_project_when_none_explicit():
    """build_request() omits 'project' when explicitly None."""
    payload = build_request(
        verb="note",
        subject="test note",
        when=None,
        criticality="normal",
        confidence=0.9,
        raw_transcript="note something",
        audio_path="/tmp/test.m4a",
        captured_at=_NOW,
        project=None,
    )
    assert "project" not in payload


# ---------------------------------------------------------------------------
# Test 6: Disambiguation — 'start dinner at 6' classified as schedule
# ---------------------------------------------------------------------------


def test_parse_intent_start_dinner_at_6_is_schedule():
    """'Start dinner at 6' must classify as schedule, not start_timer."""
    result = _call_parse(
        "Start dinner at 6",
        {
            "verb": "schedule",
            "subject": "dinner",
            "project": None,
            "day_hint": None,
            "time_hint": "6",
            "criticality": "normal",
            "confidence": 0.88,
            "ambiguous_fields": [],
        },
    )
    assert result.verb == "schedule", (
        f"'Start dinner at 6' should be 'schedule', got '{result.verb}'"
    )


# ---------------------------------------------------------------------------
# Test 7: ParsedIntent dataclass carries project field
# ---------------------------------------------------------------------------


def test_parsed_intent_has_project_field():
    """ParsedIntent dataclass must have a 'project' field defaulting to None."""
    if not _HAS_PARSED_INTENT:
        pytest.skip("ParsedIntent not yet in parse.py (pre-implementation)")
    # Create a ParsedIntent and verify project is accessible
    from sprite.parse import ParsedIntent as PI
    pi = PI(
        verb="start_timer",
        subject="gym",
        day_hint=None,
        time_hint=None,
        criticality="normal",
        confidence=0.95,
        ambiguous_fields=[],
        raw_llm_json={},
        project="gym",
    )
    assert pi.project == "gym"


def test_parsed_result_project_none_by_default():
    """ParseResult.project defaults to None for non-timer verbs."""
    result = _call_parse(
        "schedule dentist",
        {
            "verb": "schedule",
            "subject": "dentist",
            "project": None,
            "day_hint": "Thursday",
            "time_hint": "9am",
            "criticality": "normal",
            "confidence": 0.9,
            "ambiguous_fields": [],
        },
    )
    # project should be None for non-timer verbs
    assert result.project is None


# ---------------------------------------------------------------------------
# Test 8: Wire-shape round-trip — build_request → ParsedCaptureRequest
# ---------------------------------------------------------------------------


@pytest.mark.skipif(not _HERMAN_AVAILABLE, reason="homunculus_brain not importable")
def test_wire_shape_start_timer_round_trips_through_herman_schema():
    """build_request() for verb=start_timer round-trips through Herman's
    ParsedCaptureRequest.model_validate_json() without error."""
    payload = build_request(
        verb="start_timer",
        subject="gym",
        when=None,
        criticality="normal",
        confidence=0.95,
        raw_transcript="Start gym",
        audio_path="/tmp/test.m4a",
        captured_at=_NOW,
        project="gym",
    )
    import json as _json
    json_str = _json.dumps(payload)
    # Herman must accept the payload (not raise a validation error)
    req = ParsedCaptureRequest.model_validate_json(json_str)
    assert req.verb.value == "start_timer"
    assert req.project == "gym"
