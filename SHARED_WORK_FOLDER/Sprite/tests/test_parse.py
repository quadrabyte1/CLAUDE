"""Tests for sprite.parse — preprocessor regex and Ollama-mocked parse."""

from __future__ import annotations

from datetime import datetime, timezone
from unittest.mock import MagicMock, patch

import pytest

from sprite.parse import (
    OllamaParseError,
    OllamaUnreachable,
    ParseResult,
    _preprocess,
    parse_intent,
)


_NOW = datetime(2026, 9, 13, 14, 0, 0, tzinfo=timezone.utc)


# ---------------------------------------------------------------------------
# Preprocessor tests (no LLM)
# ---------------------------------------------------------------------------


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


# ---------------------------------------------------------------------------
# Ollama mock — happy path
# ---------------------------------------------------------------------------


def _make_ollama_response(body: dict) -> MagicMock:
    """Return a mock httpx.Response that returns `body` as JSON."""
    import json
    resp = MagicMock()
    resp.status_code = 200
    resp.json.return_value = {"response": json.dumps(body)}
    resp.raise_for_status.return_value = None
    return resp


def _patch_ollama(llm_body: dict):
    """Context manager: patches httpx.Client.post to return llm_body."""
    resp = _make_ollama_response(llm_body)
    return patch("sprite.parse.httpx.Client", autospec=True), resp


def _call_parse(transcript: str, llm_body: dict) -> ParseResult:
    """Helper: parse_intent with a mocked Ollama returning llm_body."""
    import json
    from unittest.mock import MagicMock, patch

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
            ollama_model="qwen2.5:7b-instruct",
            captured_at=_NOW,
        )


def test_parse_schedule_verb():
    result = _call_parse(
        "coffee with Jane tomorrow at 10am",
        {
            "verb": "schedule",
            "subject": "coffee with Jane",
            "when": "tomorrow at 10am",
            "criticality": "normal",
            "confidence": 0.9,
            "ambiguous_fields": [],
        },
    )
    assert result.verb == "schedule"
    assert result.subject == "coffee with Jane"
    assert result.when == "tomorrow at 10am"
    assert result.criticality == "normal"
    assert result.confidence == 0.9
    assert result.ambiguous_fields == []


def test_parse_note_verb():
    result = _call_parse(
        "note that the LED reflects off the terrazzo",
        {
            "verb": "note",
            "subject": "LED reflects off terrazzo",
            "when": None,
            "criticality": "normal",
            "confidence": 0.85,
            "ambiguous_fields": [],
        },
    )
    assert result.verb == "note"
    assert result.when is None


def test_parse_handle_verb():
    result = _call_parse(
        "call the plumber back",
        {
            "verb": "handle",
            "subject": "call plumber back",
            "when": None,
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
            "when": None,
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
            "when": None,
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
            "when": None,
            "criticality": "critical",  # LLM decided critical
            "confidence": 0.85,
            "ambiguous_fields": [],
        },
    )
    assert result.criticality == "critical"


# ---------------------------------------------------------------------------
# Confidence gate and ambiguous_fields
# ---------------------------------------------------------------------------


def test_parse_low_confidence_still_returns_result():
    """parse_intent returns the result even with low confidence; the caller gates."""
    result = _call_parse(
        "mumble mumble something",
        {
            "verb": "note",
            "subject": "something",
            "when": None,
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
            "when": "next week",
            "criticality": "normal",
            "confidence": 0.55,
            "ambiguous_fields": ["when", "subject"],
        },
    )
    assert set(result.ambiguous_fields) == {"when", "subject"}


# ---------------------------------------------------------------------------
# Error paths
# ---------------------------------------------------------------------------


def test_ollama_unreachable_raises():
    import httpx
    from unittest.mock import patch, MagicMock

    mock_client_instance = MagicMock()
    mock_client_instance.post.side_effect = httpx.ConnectError("refused")
    mock_client_instance.__enter__ = MagicMock(return_value=mock_client_instance)
    mock_client_instance.__exit__ = MagicMock(return_value=False)

    with patch("sprite.parse.httpx.Client", return_value=mock_client_instance):
        with pytest.raises(OllamaUnreachable):
            parse_intent(
                "test",
                ollama_base_url="http://localhost:11434",
                ollama_model="qwen2.5:7b-instruct",
            )


def test_ollama_bad_json_raises_parse_error():
    from unittest.mock import patch, MagicMock

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
                ollama_model="qwen2.5:7b-instruct",
            )


def test_ollama_missing_required_key_raises_parse_error():
    """If Ollama JSON is valid but missing a required key, we raise OllamaParseError."""
    import json
    from unittest.mock import MagicMock, patch

    body_missing_confidence = {
        "verb": "note",
        "subject": "test",
        "when": None,
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
                ollama_model="qwen2.5:7b-instruct",
            )
