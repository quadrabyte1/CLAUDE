"""Integration tests — word-form time hints (v2.5.2 regression test).

Root cause: Sprite's LLM sometimes emits ``time_hint`` as a word-form number
("three", "eight") rather than a digit ("3", "8").  Herman's ``_TIME_REGEX``
only matches digit forms, so word-form hints fall through to the clarifying
question, bypassing Signals A and C entirely.

These tests are the RED phase for v2.5.2.  They cover the three verbatim
memos from the live failure report on 2026-09-30:

  1. "Meeting at 9 in the morning"       time_hint="nine"  → Signal C → 9 AM
  2. "Remind me the plumber comes at 3"  time_hint="three" → Signal A → 3 PM
  3. "Call mom at 8 tonight"             time_hint="eight" → Signal C → 8 PM

Also a regression test for the digit-form equivalents (must still pass).

Reference "now": same anchor as v2.5.0 suite — Tuesday 2026-09-29 10:00 AM ET.
"""

from __future__ import annotations

from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

import pytest

TZ = ZoneInfo("America/New_York")
NOW = datetime(2026, 9, 29, 10, 0, tzinfo=TZ)


# ---------------------------------------------------------------------------
# Test-client factory (copied from test_ampm_live_pipeline.py pattern)
# ---------------------------------------------------------------------------


def _client_with_vault(tmp_path: Path, monkeypatch):
    """Spin up a TestClient with an isolated vault."""
    monkeypatch.setenv("HOMUNCULUS_VAULT", str(tmp_path))
    monkeypatch.setenv("HOMUNCULUS_TZ", "America/New_York")
    monkeypatch.setenv("OLLAMA_BASE_URL", "http://127.0.0.1:1")
    monkeypatch.setenv("SPRITE_WARNINGS_PATH", str(tmp_path / "sprite" / "warnings.md"))
    monkeypatch.setenv("HOMUNCULUS_MIN_CONFIDENCE", "0.6")
    from fastapi.testclient import TestClient
    from homunculus_brain.server import create_app
    app = create_app()
    return TestClient(app)


def _payload(
    transcript: str,
    *,
    time_hint: str | None,
    verb: str = "schedule",
    day_hint: str | None = None,
    captured_at: datetime = NOW,
) -> dict:
    return {
        "verb": verb,
        "subject": transcript.strip(),
        "when": None,
        "day_hint": day_hint,
        "time_hint": time_hint,
        "criticality": "normal",
        "confidence": 0.9,
        "raw_transcript": transcript,
        "audio_path": "/Users/thomas/sprite/inbox/test.m4a",
        "captured_at": captured_at.isoformat(),
        "speaker_tz": "America/New_York",
    }


# ---------------------------------------------------------------------------
# Vault helpers
# ---------------------------------------------------------------------------


def _starts_at_hour(tmp_path: Path, event_id: str, *, directory: str) -> int | None:
    """Return the local hour from starts_at frontmatter for the given event."""
    import re
    base = tmp_path / directory
    if not base.exists():
        return None
    for md in base.rglob("*.md"):
        text = md.read_text(encoding="utf-8")
        if event_id not in text:
            continue
        m = re.search(r"^starts_at:\s*['\"]?(.+?)['\"]?\s*$", text, re.MULTILINE)
        if m:
            starts_at = datetime.fromisoformat(m.group(1).strip().strip("'\""))
            return starts_at.astimezone(TZ).hour
    return None


# ===========================================================================
# RED tests — word-form time hints that currently bounce with clarify question
# ===========================================================================


class TestWordFormTimeHints:
    """Word-form numbers in time_hint must not trigger a clarifying question.

    These three memos bounce with v2.5.1 because _TIME_REGEX only matches
    digits.  The fix (v2.5.2) normalises word-form hours to digit form before
    the regex so that Signal C and Signal A get a chance to fire.
    """

    def test_meeting_at_nine_in_the_morning(self, tmp_path, monkeypatch):
        """'Meeting at 9 in the morning' with time_hint='nine' → 9 AM.

        Sprite LLM emits the word 'nine' rather than the digit '9'.
        Signal C ('in the morning') must still fire and resolve to 9 AM.
        """
        client = _client_with_vault(tmp_path, monkeypatch)
        resp = client.post("/capture/parsed", json=_payload(
            "Meeting at 9 in the morning",
            time_hint="nine",
            verb="schedule",
        ))
        assert resp.status_code == 200, resp.text
        body = resp.json()
        assert body.get("stored") is True, (
            f"word-form 'nine' + Signal C 'in the morning' must resolve to 9 AM, no clarify. "
            f"Got stored=False, clarifying_question={body.get('clarifying_question')!r}"
        )
        event_id = body.get("event_id")
        assert event_id is not None
        hour = _starts_at_hour(tmp_path, event_id, directory="calendar")
        assert hour == 9, f"Expected hour=9, got hour={hour}"

    def test_plumber_comes_at_three(self, tmp_path, monkeypatch):
        """'Remind me the plumber comes at 3' with time_hint='three' → 3 PM.

        Sprite LLM emits 'three' for the word form.  Signal A ('plumber'
        profession keyword) must still fire and resolve to 3 PM.
        """
        client = _client_with_vault(tmp_path, monkeypatch)
        resp = client.post("/capture/parsed", json=_payload(
            "Remind me the plumber comes at three",
            time_hint="three",
            verb="remind",
        ))
        assert resp.status_code == 200, resp.text
        body = resp.json()
        assert body.get("stored") is True, (
            f"word-form 'three' + Signal A 'plumber' must resolve to 3 PM, no clarify. "
            f"Got stored=False, clarifying_question={body.get('clarifying_question')!r}"
        )
        event_id = body.get("event_id")
        assert event_id is not None
        hour = _starts_at_hour(tmp_path, event_id, directory="reminders")
        assert hour == 15, f"Expected hour=15 (3 PM), got hour={hour}"

    def test_call_mom_at_eight_tonight(self, tmp_path, monkeypatch):
        """'Call mom at 8 tonight' with time_hint='eight' → 8 PM.

        Sprite LLM emits 'eight' for the word form.  Signal C ('tonight')
        must still fire and resolve to 8 PM.
        """
        client = _client_with_vault(tmp_path, monkeypatch)
        resp = client.post("/capture/parsed", json=_payload(
            "Call mom at 8 tonight",
            time_hint="eight",
            verb="schedule",
        ))
        assert resp.status_code == 200, resp.text
        body = resp.json()
        assert body.get("stored") is True, (
            f"word-form 'eight' + Signal C 'tonight' must resolve to 8 PM, no clarify. "
            f"Got stored=False, clarifying_question={body.get('clarifying_question')!r}"
        )
        event_id = body.get("event_id")
        assert event_id is not None
        hour = _starts_at_hour(tmp_path, event_id, directory="calendar")
        assert hour == 20, f"Expected hour=20 (8 PM), got hour={hour}"


# ===========================================================================
# Regression — digit-form equivalents must still work (not broken by fix)
# ===========================================================================


class TestDigitFormRegression:
    """Digit-form time hints must still work after the word-form normalisation."""

    def test_meeting_at_9_digit_in_the_morning(self, tmp_path, monkeypatch):
        """'Meeting at 9 in the morning' with time_hint='9' → 9 AM."""
        client = _client_with_vault(tmp_path, monkeypatch)
        resp = client.post("/capture/parsed", json=_payload(
            "Meeting at 9 in the morning",
            time_hint="9",
            verb="schedule",
        ))
        body = resp.json()
        assert body.get("stored") is True, f"digit '9' regression. Got: {body!r}"
        event_id = body.get("event_id")
        hour = _starts_at_hour(tmp_path, event_id, directory="calendar")
        assert hour == 9, f"Expected 9 AM, got hour={hour}"

    def test_plumber_at_3_digit(self, tmp_path, monkeypatch):
        """'Remind me the plumber comes at 3' with time_hint='3' → 3 PM."""
        client = _client_with_vault(tmp_path, monkeypatch)
        resp = client.post("/capture/parsed", json=_payload(
            "Remind me the plumber comes at 3",
            time_hint="3",
            verb="remind",
        ))
        body = resp.json()
        assert body.get("stored") is True, f"digit '3' regression. Got: {body!r}"
        event_id = body.get("event_id")
        hour = _starts_at_hour(tmp_path, event_id, directory="reminders")
        assert hour == 15, f"Expected 3 PM (15), got hour={hour}"

    def test_call_mom_at_8_digit_tonight(self, tmp_path, monkeypatch):
        """'Call mom at 8 tonight' with time_hint='8' → 8 PM."""
        client = _client_with_vault(tmp_path, monkeypatch)
        resp = client.post("/capture/parsed", json=_payload(
            "Call mom at 8 tonight",
            time_hint="8",
            verb="schedule",
        ))
        body = resp.json()
        assert body.get("stored") is True, f"digit '8' tonight regression. Got: {body!r}"
        event_id = body.get("event_id")
        hour = _starts_at_hour(tmp_path, event_id, directory="calendar")
        assert hour == 20, f"Expected 8 PM (20), got hour={hour}"


# ===========================================================================
# Additional word-form coverage — all twelve hours
# ===========================================================================


class TestWordFormNormalization:
    """Word-form numbers one through twelve all resolve to their digit equivalents.

    These use Signal B roll-forward (no context qualifier) so we just check
    that stored=True (no clarifying question).  The specific hour depends on
    now-time but the key assertion is no bounce.
    """

    @pytest.mark.parametrize("word,digit", [
        ("one", 1), ("two", 2), ("three", 3), ("four", 4),
        ("five", 5), ("six", 6), ("seven", 7), ("eight", 8),
        ("nine", 9), ("ten", 10), ("eleven", 11), ("twelve", 12),
    ])
    def test_word_form_no_context_resolves_via_rollforward(
        self, tmp_path, monkeypatch, word, digit
    ):
        """Word form 'N' with no qualifier resolves via Signal B (no clarify)."""
        client = _client_with_vault(tmp_path, monkeypatch)
        # Use distinct captured_at for each to avoid idempotency cache
        offset_now = NOW.replace(second=digit)
        resp = client.post("/capture/parsed", json=_payload(
            f"Appointment at {word}",
            time_hint=word,
            verb="schedule",
            captured_at=offset_now,
        ))
        body = resp.json()
        assert body.get("stored") is True, (
            f"word-form '{word}' must resolve via roll-forward (no clarify). "
            f"Got stored=False, clarifying_question={body.get('clarifying_question')!r}"
        )
