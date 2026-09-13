"""Wire-shape tests for sprite.herman — build_request must match Herman's
ParsedCaptureRequest schema exactly.

These tests do NOT call a live Herman instance. They verify:
1. build_request produces the exact field set Herman expects.
2. The payload can be validated by Herman's Pydantic model (ParsedCaptureRequest).
3. Retry logic: 5xx retries, 4xx does not retry, success on 200.
4. HermanResponse fields are parsed correctly.

The wire-shape test imports Herman's schemas directly to cross-validate.
This is the CI guard that catches contract drift.
"""

from __future__ import annotations

import json
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from unittest.mock import MagicMock, call, patch

import pytest

from sprite.herman import HermanError, HermanResponse, build_request, post_to_herman

# ---------------------------------------------------------------------------
# Import Herman schemas for wire-shape cross-validation.
# We need the Herman package on sys.path. It lives at:
#   /Volumes/GIT/CLAUDE/SHARED_WORK_FOLDER/Homunculus/brain/
# ---------------------------------------------------------------------------

_HERMAN_BRAIN_SRC = Path("/Volumes/GIT/CLAUDE/SHARED_WORK_FOLDER/Homunculus/brain")

if str(_HERMAN_BRAIN_SRC) not in sys.path:
    sys.path.insert(0, str(_HERMAN_BRAIN_SRC))

try:
    from homunculus_brain.schemas import ParsedCaptureRequest
    _HERMAN_AVAILABLE = True
except ImportError:
    _HERMAN_AVAILABLE = False

_NOW = datetime(2026, 9, 13, 14, 0, 0, tzinfo=timezone.utc)

# ---------------------------------------------------------------------------
# Helper
# ---------------------------------------------------------------------------


def _base_payload(**overrides) -> dict:
    p = dict(
        verb="handle",
        subject="call deck contractor",
        when="2026-09-17T09:00:00-04:00",
        criticality="normal",
        confidence=0.85,
        raw_transcript="remember to call the deck contractor Thursday",
        audio_path="/Users/thomas/sprite/audio/2026/09/abc123.m4a",
        captured_at=_NOW,
        speaker_tz="America/New_York",
    )
    p.update(overrides)
    return p


# ---------------------------------------------------------------------------
# build_request — field coverage
# ---------------------------------------------------------------------------


def test_build_request_includes_all_required_fields():
    payload = build_request(**_base_payload())
    required = {"verb", "subject", "when", "criticality", "confidence",
                 "raw_transcript", "audio_path", "captured_at"}
    missing = required - set(payload.keys())
    assert not missing, f"Missing fields: {missing}"


def test_build_request_verb_values():
    for verb in ("schedule", "note", "handle", "avoid"):
        p = build_request(**_base_payload(verb=verb))
        assert p["verb"] == verb


def test_build_request_captured_at_is_iso_string():
    p = build_request(**_base_payload())
    # Must be parseable ISO-8601.
    dt = datetime.fromisoformat(p["captured_at"])
    assert dt.tzinfo is not None


def test_build_request_null_when_passes_through():
    p = build_request(**_base_payload(when=None))
    assert p["when"] is None


def test_build_request_includes_speaker_tz():
    p = build_request(**_base_payload(speaker_tz="America/Chicago"))
    assert p["speaker_tz"] == "America/Chicago"


def test_build_request_includes_sprite_uuid_when_given():
    p = build_request(**_base_payload(sprite_uuid="abc123"))
    assert p["sprite_uuid"] == "abc123"


def test_build_request_no_sprite_uuid_by_default():
    p = build_request(**_base_payload())
    assert "sprite_uuid" not in p


def test_build_request_includes_day_hint_when_given():
    """day_hint must survive the wire hop to Herman."""
    p = build_request(**_base_payload(day_hint="thursday"))
    assert p["day_hint"] == "thursday"


def test_build_request_includes_time_hint_when_given():
    """time_hint must survive the wire hop to Herman."""
    p = build_request(**_base_payload(time_hint="9am"))
    assert p["time_hint"] == "9am"


def test_build_request_no_day_hint_by_default():
    """Callers that don't pass hints get no hint keys in the payload (keeps wire clean)."""
    p = build_request(**_base_payload())
    assert "day_hint" not in p


def test_build_request_no_time_hint_by_default():
    p = build_request(**_base_payload())
    assert "time_hint" not in p


def test_build_request_both_hints_together():
    p = build_request(**_base_payload(day_hint="tomorrow", time_hint="2pm", when=None))
    assert p["day_hint"] == "tomorrow"
    assert p["time_hint"] == "2pm"
    assert p["when"] is None


def test_build_request_criticality_values():
    for crit in ("normal", "critical"):
        p = build_request(**_base_payload(criticality=crit))
        assert p["criticality"] == crit


def test_build_request_confidence_range():
    for conf in (0.0, 0.6, 0.85, 1.0):
        p = build_request(**_base_payload(confidence=conf))
        assert p["confidence"] == conf


# ---------------------------------------------------------------------------
# Wire-shape: validate against Herman's actual Pydantic model
# ---------------------------------------------------------------------------


@pytest.mark.skipif(not _HERMAN_AVAILABLE, reason="Herman package not on path")
def test_build_request_validates_against_herman_schema():
    """The payload build_request produces must be accepted by Herman's
    ParsedCaptureRequest Pydantic model. This is the cross-repo wire guard."""
    payload = build_request(**_base_payload())
    # Remove sprite_uuid (Herman ignores unknown fields by default in Pydantic v2).
    req = ParsedCaptureRequest(**payload)
    assert req.verb.value == "handle"
    assert req.subject == "call deck contractor"
    assert req.confidence == 0.85
    assert req.criticality.value == "normal"


@pytest.mark.skipif(not _HERMAN_AVAILABLE, reason="Herman package not on path")
def test_wire_shape_schedule_verb():
    payload = build_request(**_base_payload(verb="schedule"))
    req = ParsedCaptureRequest(**payload)
    assert req.verb.value == "schedule"


@pytest.mark.skipif(not _HERMAN_AVAILABLE, reason="Herman package not on path")
def test_wire_shape_null_when():
    payload = build_request(**_base_payload(when=None))
    req = ParsedCaptureRequest(**payload)
    assert req.when is None


@pytest.mark.skipif(not _HERMAN_AVAILABLE, reason="Herman package not on path")
def test_wire_shape_critical_criticality():
    payload = build_request(**_base_payload(criticality="critical"))
    req = ParsedCaptureRequest(**payload)
    assert req.criticality.value == "critical"


@pytest.mark.skipif(not _HERMAN_AVAILABLE, reason="Herman package not on path")
def test_wire_shape_day_and_time_hints_round_trip():
    """day_hint + time_hint must survive build_request → ParsedCaptureRequest
    validation. This is the cross-repo drift-detection guard for M3."""
    payload = build_request(
        **_base_payload(when=None, day_hint="thursday", time_hint="9am")
    )
    req = ParsedCaptureRequest(**payload)
    assert req.day_hint == "thursday"
    assert req.time_hint == "9am"
    assert req.when is None


@pytest.mark.skipif(not _HERMAN_AVAILABLE, reason="Herman package not on path")
def test_wire_shape_hints_not_present_when_not_given():
    """When no hints are passed, the fields are None in Herman's model."""
    payload = build_request(**_base_payload())
    req = ParsedCaptureRequest(**payload)
    assert req.day_hint is None
    assert req.time_hint is None


# ---------------------------------------------------------------------------
# post_to_herman — mocked HTTP
# ---------------------------------------------------------------------------


def _make_mock_client(status_code: int, body: dict):
    """Return a mock httpx.Client context manager that returns the given response."""
    mock_resp = MagicMock()
    mock_resp.status_code = status_code
    mock_resp.json.return_value = body

    mock_instance = MagicMock()
    mock_instance.post.return_value = mock_resp
    mock_instance.__enter__ = MagicMock(return_value=mock_instance)
    mock_instance.__exit__ = MagicMock(return_value=False)
    return mock_instance


def test_post_to_herman_success_200():
    body = {
        "stored": True,
        "record_id": "rec_abc123",
        "verb": "handle",
        "written_path": "calendar/2026-09-17-call-deck-contractor.md",
        "event_id": "ev_xyz789",
    }
    mock_instance = _make_mock_client(200, body)

    with patch("sprite.herman.httpx.Client", return_value=mock_instance):
        payload = build_request(**_base_payload())
        resp = post_to_herman(payload, herman_base_url="http://localhost:8765")

    assert resp.status_code == 200
    assert resp.stored is True
    assert resp.record_id == "rec_abc123"
    assert resp.event_id == "ev_xyz789"
    assert resp.written_path == "calendar/2026-09-17-call-deck-contractor.md"


def test_post_to_herman_422_low_confidence_raises_immediately():
    body = {"stored": False, "reason": "low_confidence"}
    mock_instance = _make_mock_client(422, body)

    with patch("sprite.herman.httpx.Client", return_value=mock_instance):
        payload = build_request(**_base_payload(confidence=0.3))
        with pytest.raises(HermanError, match="low_confidence"):
            post_to_herman(payload, herman_base_url="http://localhost:8765")


def test_post_to_herman_400_schema_violation_raises_no_retry():
    body = {"stored": False, "reason": "schema_violation"}
    mock_instance = _make_mock_client(400, body)

    with patch("sprite.herman.httpx.Client", return_value=mock_instance) as mock_cls:
        payload = build_request(**_base_payload())
        with pytest.raises(HermanError, match="schema_violation"):
            post_to_herman(payload, herman_base_url="http://localhost:8765")
    # 400 must not retry — only 1 call.
    assert mock_instance.post.call_count == 1


def test_post_to_herman_5xx_retries_and_eventually_raises():
    body = {"error": "internal server error"}
    mock_instance = _make_mock_client(500, body)

    with patch("sprite.herman.time.sleep"):  # don't actually sleep in tests
        with patch("sprite.herman.httpx.Client", return_value=mock_instance):
            payload = build_request(**_base_payload())
            with pytest.raises(HermanError):
                post_to_herman(payload, herman_base_url="http://localhost:8765")

    # 3 retry attempts (MAX_RETRIES=3)
    assert mock_instance.post.call_count == 3


def test_post_to_herman_succeeds_on_second_attempt():
    """First call returns 500, second returns 200 — should succeed."""
    success_body = {
        "stored": True,
        "record_id": "rec_retry_ok",
        "verb": "note",
        "written_path": "notes/2026-09-13-test.md",
        "event_id": None,
    }

    fail_resp = MagicMock()
    fail_resp.status_code = 500
    fail_resp.json.return_value = {"error": "server error"}

    ok_resp = MagicMock()
    ok_resp.status_code = 200
    ok_resp.json.return_value = success_body

    mock_instance = MagicMock()
    mock_instance.post.side_effect = [fail_resp, ok_resp]
    mock_instance.__enter__ = MagicMock(return_value=mock_instance)
    mock_instance.__exit__ = MagicMock(return_value=False)

    with patch("sprite.herman.time.sleep"):
        with patch("sprite.herman.httpx.Client", return_value=mock_instance):
            payload = build_request(**_base_payload(verb="note"))
            resp = post_to_herman(payload, herman_base_url="http://localhost:8765")

    assert resp.stored is True
    assert resp.record_id == "rec_retry_ok"
    assert mock_instance.post.call_count == 2


def test_post_to_herman_network_error_retries():
    import httpx

    mock_instance = MagicMock()
    mock_instance.post.side_effect = httpx.ConnectError("refused")
    mock_instance.__enter__ = MagicMock(return_value=mock_instance)
    mock_instance.__exit__ = MagicMock(return_value=False)

    with patch("sprite.herman.time.sleep"):
        with patch("sprite.herman.httpx.Client", return_value=mock_instance):
            with pytest.raises(HermanError):
                post_to_herman(
                    build_request(**_base_payload()),
                    herman_base_url="http://localhost:8765",
                )
    assert mock_instance.post.call_count == 3  # all 3 attempts tried
