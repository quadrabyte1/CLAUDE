"""Sprite v0.7.0 — remind verb TDD suite.

RED-first tests written before the implementation.

What is under test:
  1. _INTENT_JSON_SCHEMA includes "remind" in the verb enum
  2. _SYSTEM_PROMPT teaches the remind/handle distinction
  3. parse_intent accepts verb=remind from Ollama output
  4. build_request forwards verb=remind as-is (not rewritten to handle)
  5. ParseResult can carry verb=remind without error
  6. Cross-repo wire test: verb=remind passes through Herman's schema
"""

from __future__ import annotations

import json
import sys
from datetime import datetime, timezone
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from sprite.parse import (
    ParseResult,
    _INTENT_JSON_SCHEMA,
    _SYSTEM_PROMPT,
    parse_intent,
)

_NOW = datetime(2026, 9, 17, 14, 0, 0, tzinfo=timezone.utc)

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
# Helper
# ---------------------------------------------------------------------------


def _call_parse(transcript: str, llm_body: dict) -> ParseResult:
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


# ---------------------------------------------------------------------------
# 1. Schema includes remind in verb enum
# ---------------------------------------------------------------------------


def test_schema_verb_enum_includes_remind():
    """_INTENT_JSON_SCHEMA verb enum must include 'remind'."""
    verb_prop = _INTENT_JSON_SCHEMA["properties"]["verb"]
    enum_values = verb_prop.get("enum", [])
    assert "remind" in enum_values, (
        f"'remind' must be in verb enum. Got: {enum_values}"
    )


# ---------------------------------------------------------------------------
# 2. System prompt teaches remind/handle distinction
# ---------------------------------------------------------------------------


def test_system_prompt_teaches_remind_verb():
    """_SYSTEM_PROMPT must mention 'remind' as a verb with its distinction from handle."""
    prompt_lower = _SYSTEM_PROMPT.lower()
    assert "remind" in prompt_lower, "_SYSTEM_PROMPT must mention 'remind' as a verb"


def test_system_prompt_has_remind_few_shot_example():
    """_SYSTEM_PROMPT must include at least one few-shot example with verb=remind."""
    assert '"verb":"remind"' in _SYSTEM_PROMPT or '"verb": "remind"' in _SYSTEM_PROMPT, (
        "_SYSTEM_PROMPT must include a few-shot example with verb='remind'"
    )


def test_system_prompt_clarifies_remind_vs_handle():
    """_SYSTEM_PROMPT must explain when to use remind vs handle."""
    # The prompt should clarify that remind is for "remind me" phrasing
    # and handle is for bare imperatives.
    assert "remind me" in _SYSTEM_PROMPT.lower(), (
        "_SYSTEM_PROMPT should mention 'remind me' as the trigger for verb=remind"
    )


# ---------------------------------------------------------------------------
# 3. parse_intent accepts verb=remind from Ollama output
# ---------------------------------------------------------------------------


def test_parse_intent_accepts_verb_remind():
    """parse_intent must return verb='remind' when Ollama emits it."""
    result = _call_parse(
        "remind me to pick up the dry cleaning",
        {
            "verb": "remind",
            "subject": "pick up dry cleaning",
            "day_hint": None,
            "time_hint": None,
            "criticality": "normal",
            "confidence": 0.90,
            "ambiguous_fields": [],
        },
    )
    assert result.verb == "remind", (
        f"Expected verb='remind', got {result.verb!r}"
    )


def test_parse_intent_remind_has_correct_subject():
    result = _call_parse(
        "remind me to call the dentist back",
        {
            "verb": "remind",
            "subject": "call dentist back",
            "day_hint": None,
            "time_hint": None,
            "criticality": "normal",
            "confidence": 0.88,
            "ambiguous_fields": [],
        },
    )
    assert result.subject == "call dentist back"
    assert result.verb == "remind"


def test_parse_intent_remind_with_day_hint():
    result = _call_parse(
        "remind me Thursday to call the plumber",
        {
            "verb": "remind",
            "subject": "call the plumber",
            "day_hint": "Thursday",
            "time_hint": None,
            "criticality": "normal",
            "confidence": 0.87,
            "ambiguous_fields": [],
        },
    )
    assert result.verb == "remind"
    assert result.day_hint == "Thursday"


# ---------------------------------------------------------------------------
# 4. build_request forwards verb=remind as-is
# ---------------------------------------------------------------------------


def test_build_request_forwards_verb_remind():
    """build_request must forward verb='remind' unchanged to Herman."""
    from sprite.herman import build_request

    payload = build_request(
        verb="remind",
        subject="pick up dry cleaning",
        when=None,
        criticality="normal",
        confidence=0.90,
        raw_transcript="remind me to pick up the dry cleaning",
        audio_path="/tmp/test.m4a",
        captured_at=datetime(2026, 9, 17, 12, 0, 0, tzinfo=timezone.utc),
    )
    assert payload["verb"] == "remind", (
        f"build_request must forward verb='remind' unchanged, got {payload['verb']!r}"
    )


def test_build_request_does_not_rewrite_remind_to_handle():
    """build_request must NOT silently rewrite remind → handle."""
    from sprite.herman import build_request

    payload = build_request(
        verb="remind",
        subject="water the plants",
        when=None,
        criticality="normal",
        confidence=0.85,
        raw_transcript="remind me to water the plants",
        audio_path="/tmp/test.m4a",
        captured_at=datetime(2026, 9, 17, 12, 0, 0, tzinfo=timezone.utc),
    )
    assert payload["verb"] != "handle", (
        "build_request must not rewrite 'remind' to 'handle'. "
        "Herman accepts both; preserve the original."
    )
    assert payload["verb"] == "remind"


# ---------------------------------------------------------------------------
# 5. ParseResult can carry verb=remind without error
# ---------------------------------------------------------------------------


def test_parse_result_accepts_remind_verb():
    """ParseResult can be constructed with verb='remind' (no exception)."""
    result = ParseResult(
        verb="remind",
        subject="call mom",
        day_hint=None,
        time_hint=None,
        criticality="normal",
        confidence=0.9,
        ambiguous_fields=[],
        raw_llm_json={"verb": "remind"},
    )
    assert result.verb == "remind"


# ---------------------------------------------------------------------------
# 6. Cross-repo wire test: verb=remind passes through Herman's schema
# ---------------------------------------------------------------------------


@pytest.mark.skipif(not _HERMAN_AVAILABLE, reason="Herman package not on path")
def test_verb_remind_round_trips_through_herman_schema():
    """payload with verb=remind must validate through Herman's ParsedCaptureRequest."""
    from sprite.herman import build_request

    payload = build_request(
        verb="remind",
        subject="pick up dry cleaning",
        when=None,
        criticality="normal",
        confidence=0.90,
        raw_transcript="remind me to pick up the dry cleaning",
        audio_path="/tmp/test.m4a",
        captured_at=datetime(2026, 9, 17, 12, 0, 0, tzinfo=timezone.utc),
    )
    req = ParsedCaptureRequest.model_validate_json(json.dumps(payload))
    assert req.verb.value == "remind", (
        f"verb='remind' must survive wire round-trip. Got: {req.verb!r}"
    )


@pytest.mark.skipif(not _HERMAN_AVAILABLE, reason="Herman package not on path")
def test_verb_remind_round_trips_with_day_hint():
    """verb=remind + day_hint must both survive the wire round-trip."""
    from sprite.herman import build_request

    payload = build_request(
        verb="remind",
        subject="call the plumber",
        when=None,
        criticality="normal",
        confidence=0.87,
        raw_transcript="remind me Thursday to call the plumber",
        audio_path="/tmp/test.m4a",
        captured_at=datetime(2026, 9, 17, 12, 0, 0, tzinfo=timezone.utc),
        day_hint="Thursday",
        time_hint=None,
    )
    req = ParsedCaptureRequest.model_validate_json(json.dumps(payload))
    assert req.verb.value == "remind"
    assert req.day_hint == "Thursday"
