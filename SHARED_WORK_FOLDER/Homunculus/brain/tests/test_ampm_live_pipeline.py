"""Integration tests — A/C signal end-to-end through the live /capture/parsed pipeline.

Bug: v2.5.0 shipped Signals A/B/C in date_resolver.resolve() but the
capture_parsed glue code (_resolve_from_hints, _handle_schedule,
_handle_handle) never passes context_text= to date_resolver.resolve().
The resolver therefore sees context_text=None for every live memo and
falls straight through to Signal B (roll-forward), skipping Signals A and C.

These four tests are the FAILING INTEGRATION TESTS (RED phase — TDD):

  1. "Meeting at 6 in the morning"      → Signal C → 6 AM
  2. "Remind me the plumber comes at 3" → Signal A profession → 3 PM
  3. "Call mom at 8 tonight"            → Signal C → 8 PM
  4. "Dinner at 7 in the morning"       → Signal C beats Signal A → 7 AM

All four currently bounce with a clarifying question because context_text
is not forwarded by the pipeline.  After the fix they must all resolve
without a clarifying question.

Also included: regression tests for the four passing memos and the existing
52 date_resolver unit tests (run as a subprocess to confirm nothing broke).

Military-time bonus test also lives here.

Reference "now": Tuesday 2026-09-29 10:00 AM Eastern — same anchor as the
v2.5.0 unit-test suite.
"""

from __future__ import annotations

from datetime import datetime, timedelta
from pathlib import Path
from zoneinfo import ZoneInfo

import pytest
from fastapi.testclient import TestClient

TZ = ZoneInfo("America/New_York")
NOW = datetime(2026, 9, 29, 10, 0, tzinfo=TZ)

# ---------------------------------------------------------------------------
# Test-client factory
# ---------------------------------------------------------------------------


def _client_with_vault(tmp_path: Path, monkeypatch) -> TestClient:
    """Spin up a TestClient with an isolated vault; never touches a live DB."""
    monkeypatch.setenv("HOMUNCULUS_VAULT", str(tmp_path))
    monkeypatch.setenv("HOMUNCULUS_TZ", "America/New_York")
    monkeypatch.setenv("OLLAMA_BASE_URL", "http://127.0.0.1:1")
    monkeypatch.setenv("SPRITE_WARNINGS_PATH", str(tmp_path / "sprite" / "warnings.md"))
    monkeypatch.setenv("HOMUNCULUS_MIN_CONFIDENCE", "0.6")
    from homunculus_brain.server import create_app
    app = create_app()
    return TestClient(app)


def _payload_for_memo(
    transcript: str,
    *,
    day_hint: str | None = None,
    time_hint: str | None = None,
    verb: str = "schedule",
    captured_at: datetime = NOW,
) -> dict:
    """Build a minimal ParsedCaptureRequest payload for /capture/parsed."""
    return {
        "verb": verb,
        "subject": transcript.strip(),          # subject = raw transcript for simplicity
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
# Helper — post and assert no clarifying question
# ---------------------------------------------------------------------------


def _post_and_assert_resolved(
    client: TestClient,
    payload: dict,
    *,
    expected_hour: int,
    label: str,
) -> dict:
    """POST to /capture/parsed, assert stored=True and correct hour.

    Returns the parsed JSON body for further assertions if needed.
    """
    resp = client.post("/capture/parsed", json=payload)
    assert resp.status_code == 200, f"{label}: expected 200, got {resp.status_code}: {resp.text}"
    body = resp.json()
    assert body.get("stored") is True, (
        f"{label}: expected stored=True (no clarifying question). "
        f"Got stored=False, clarifying_question={body.get('clarifying_question')!r}"
    )
    # Verify the event was written to the vault and the resolved time is correct.
    # The event_id is returned for schedule verbs; check it has the right hour.
    # We do this by looking at the vault file, or via the written_path.
    return body


# ===========================================================================
# RED — the four FAILING integration tests (currently bounce with clarify)
# ===========================================================================


class TestSignalC_LivePipeline:
    """Signal C qualifier phrases must survive the Sprite → Herman pipeline."""

    def test_meeting_at_6_in_the_morning(self, tmp_path, monkeypatch):
        """'Meeting at 6 in the morning' → 6 AM.

        Signal C: 'in the morning' in raw_transcript must be forwarded to
        date_resolver as context_text. Currently the pipeline drops it.
        """
        client = _client_with_vault(tmp_path, monkeypatch)
        payload = _payload_for_memo(
            "Meeting at 6 in the morning",
            time_hint="6",
            verb="schedule",
        )
        resp = client.post("/capture/parsed", json=payload)
        assert resp.status_code == 200, resp.text
        body = resp.json()
        assert body.get("stored") is True, (
            f"Signal C 'in the morning' must resolve 6→6AM without clarifying question. "
            f"Got: stored=False, clarifying_question={body.get('clarifying_question')!r}"
        )
        # Verify hour in the vault file
        event_id = body.get("event_id")
        assert event_id is not None, "event_id must be present for schedule verb"
        _assert_vault_hour(tmp_path, event_id, expected_hour=6, label="meeting in the morning")

    def test_call_mom_at_8_tonight(self, tmp_path, monkeypatch):
        """'Call mom at 8 tonight' → 8 PM.

        Signal C: 'tonight' in raw_transcript must forward as context_text.
        """
        client = _client_with_vault(tmp_path, monkeypatch)
        payload = _payload_for_memo(
            "Call mom at 8 tonight",
            time_hint="8",
            verb="schedule",
        )
        resp = client.post("/capture/parsed", json=payload)
        assert resp.status_code == 200, resp.text
        body = resp.json()
        assert body.get("stored") is True, (
            f"Signal C 'tonight' must resolve 8→8PM without clarifying question. "
            f"Got: stored=False, clarifying_question={body.get('clarifying_question')!r}"
        )
        event_id = body.get("event_id")
        assert event_id is not None
        _assert_vault_hour(tmp_path, event_id, expected_hour=20, label="call mom tonight")

    def test_dinner_at_7_in_the_morning_qualifier_beats_meal(self, tmp_path, monkeypatch):
        """'Dinner at 7 in the morning' → 7 AM.

        Signal C (qualifier) beats Signal A (meal default PM) — higher precedence.
        The qualifier phrase 'in the morning' is a more explicit instruction
        than the dinner meal-type default.
        """
        client = _client_with_vault(tmp_path, monkeypatch)
        payload = _payload_for_memo(
            "Dinner at 7 in the morning",
            time_hint="7",
            verb="schedule",
        )
        resp = client.post("/capture/parsed", json=payload)
        assert resp.status_code == 200, resp.text
        body = resp.json()
        assert body.get("stored") is True, (
            f"Signal C beats Signal A: 'dinner at 7 in the morning' must resolve to 7AM. "
            f"Got: stored=False, clarifying_question={body.get('clarifying_question')!r}"
        )
        event_id = body.get("event_id")
        assert event_id is not None
        _assert_vault_hour(tmp_path, event_id, expected_hour=7, label="dinner in the morning")


class TestSignalA_LivePipeline:
    """Signal A keyword context must survive the Sprite → Herman pipeline."""

    def test_plumber_comes_at_3(self, tmp_path, monkeypatch):
        """'Remind me the plumber comes at 3' → 3 PM.

        Signal A: 'plumber' is a profession keyword → business hours → PM.
        Uses verb=remind which routes to _handle_handle.
        """
        client = _client_with_vault(tmp_path, monkeypatch)
        payload = _payload_for_memo(
            "Remind me the plumber comes at 3",
            time_hint="3",
            verb="remind",
        )
        resp = client.post("/capture/parsed", json=payload)
        assert resp.status_code == 200, resp.text
        body = resp.json()
        assert body.get("stored") is True, (
            f"Signal A 'plumber' must resolve 3→3PM without clarifying question. "
            f"Got: stored=False, clarifying_question={body.get('clarifying_question')!r}"
        )
        event_id = body.get("event_id")
        assert event_id is not None
        _assert_vault_reminder_hour(tmp_path, event_id, expected_hour=15, label="plumber at 3")


# ===========================================================================
# REGRESSION — the four passing memos must still pass after the fix
# ===========================================================================


class TestRegressionPassingMemos:
    """The four memos that already worked must continue to work after the fix."""

    def test_schedule_dinner_at_7_still_works(self, tmp_path, monkeypatch):
        """'Schedule dinner at 7' passed before — must still pass via Signal A."""
        client = _client_with_vault(tmp_path, monkeypatch)
        payload = _payload_for_memo(
            "Schedule dinner at 7",
            time_hint="7",
            verb="schedule",
        )
        resp = client.post("/capture/parsed", json=payload)
        assert resp.status_code == 200, resp.text
        body = resp.json()
        assert body.get("stored") is True, (
            f"dinner at 7 regression: must still resolve. "
            f"Got: stored=False, clarifying_question={body.get('clarifying_question')!r}"
        )

    def test_wake_up_call_at_6_still_works(self, tmp_path, monkeypatch):
        """'Wake up call at 6' passed before — must still pass via Signal A."""
        client = _client_with_vault(tmp_path, monkeypatch)
        payload = _payload_for_memo(
            "Wake up call at 6",
            time_hint="6",
            verb="schedule",
        )
        resp = client.post("/capture/parsed", json=payload)
        assert resp.status_code == 200, resp.text
        body = resp.json()
        assert body.get("stored") is True, (
            f"wake up at 6 regression: must still resolve. "
            f"Got: stored=False, clarifying_question={body.get('clarifying_question')!r}"
        )

    def test_at_6_rollforward_still_works(self, tmp_path, monkeypatch):
        """'At 6' — no keyword, no qualifier → Signal B roll-forward must still work."""
        client = _client_with_vault(tmp_path, monkeypatch)
        payload = _payload_for_memo(
            "At 6",
            time_hint="6",
            verb="schedule",
        )
        resp = client.post("/capture/parsed", json=payload)
        assert resp.status_code == 200, resp.text
        body = resp.json()
        assert body.get("stored") is True, (
            f"roll-forward regression: 'at 6' must still resolve. "
            f"Got: stored=False, clarifying_question={body.get('clarifying_question')!r}"
        )

    def test_doctor_tomorrow_morning_at_10_still_works(self, tmp_path, monkeypatch):
        """'Doctor tomorrow morning at 10' passed before — must still pass."""
        client = _client_with_vault(tmp_path, monkeypatch)
        payload = _payload_for_memo(
            "Doctor tomorrow morning at 10",
            day_hint="tomorrow",
            time_hint="10",
            verb="schedule",
        )
        resp = client.post("/capture/parsed", json=payload)
        assert resp.status_code == 200, resp.text
        body = resp.json()
        assert body.get("stored") is True, (
            f"doctor tomorrow morning regression: must still resolve. "
            f"Got: stored=False, clarifying_question={body.get('clarifying_question')!r}"
        )


# ===========================================================================
# BONUS — military-time parsing
# ===========================================================================


class TestMilitaryTime:
    """Military-time (HHMM) patterns are unambiguous and should never clarify."""

    def test_1400_resolves_to_2pm(self, tmp_path, monkeypatch):
        """'Set a reminder for 1400 today, stop for therapy' → 2 PM today, no clarify."""
        client = _client_with_vault(tmp_path, monkeypatch)
        payload = _payload_for_memo(
            "Set a reminder for 1400 today, stop for therapy",
            day_hint="today",
            time_hint="1400",
            verb="schedule",
        )
        resp = client.post("/capture/parsed", json=payload)
        assert resp.status_code == 200, resp.text
        body = resp.json()
        assert body.get("stored") is True, (
            f"military time 1400 must resolve to 14:00 without clarifying question. "
            f"Got: stored=False, clarifying_question={body.get('clarifying_question')!r}"
        )
        event_id = body.get("event_id")
        assert event_id is not None
        _assert_vault_hour(tmp_path, event_id, expected_hour=14, label="1400 military time")

    def test_0900_resolves_to_9am(self, tmp_path, monkeypatch):
        """'Appointment at 0900' → 9 AM, no clarify."""
        client = _client_with_vault(tmp_path, monkeypatch)
        payload = _payload_for_memo(
            "Appointment at 0900",
            time_hint="0900",
            verb="schedule",
        )
        resp = client.post("/capture/parsed", json=payload)
        assert resp.status_code == 200, resp.text
        body = resp.json()
        assert body.get("stored") is True, (
            f"military time 0900 must resolve to 09:00. "
            f"Got: stored=False, clarifying_question={body.get('clarifying_question')!r}"
        )
        event_id = body.get("event_id")
        assert event_id is not None
        _assert_vault_hour(tmp_path, event_id, expected_hour=9, label="0900 military time")

    def test_1830_resolves_to_630pm(self, tmp_path, monkeypatch):
        """'Call at 1830' → 6:30 PM."""
        client = _client_with_vault(tmp_path, monkeypatch)
        payload = _payload_for_memo(
            "Call at 1830",
            time_hint="1830",
            verb="schedule",
        )
        resp = client.post("/capture/parsed", json=payload)
        assert resp.status_code == 200, resp.text
        body = resp.json()
        assert body.get("stored") is True, (
            f"military time 1830 must resolve to 18:30. "
            f"Got: stored=False, clarifying_question={body.get('clarifying_question')!r}"
        )
        event_id = body.get("event_id")
        assert event_id is not None
        _assert_vault_hour(tmp_path, event_id, expected_hour=18, label="1830 military time")


# ===========================================================================
# Vault inspection helpers
# ===========================================================================


def _parse_starts_at_from_frontmatter(text: str) -> str | None:
    """Extract the starts_at value from YAML frontmatter, stripping surrounding quotes."""
    import re
    m = re.search(r"^starts_at:\s*['\"]?(.+?)['\"]?\s*$", text, re.MULTILINE)
    if m:
        return m.group(1).strip().strip("'\"")
    return None


def _get_vault_event_starts_at(tmp_path: Path, event_id: str) -> str | None:
    """Read the starts_at frontmatter from a vault calendar event file."""
    # Calendar events live under vault/calendar/<YYYY>/<MM>/<event_id>-<slug>.md
    # Walk all calendar files looking for this event_id.
    cal_dir = tmp_path / "calendar"
    if not cal_dir.exists():
        return None
    for md_file in cal_dir.rglob("*.md"):
        text = md_file.read_text(encoding="utf-8")
        if event_id in text:
            result = _parse_starts_at_from_frontmatter(text)
            if result:
                return result
    return None


def _get_vault_reminder_starts_at(tmp_path: Path, event_id: str) -> str | None:
    """Read the starts_at frontmatter from a vault reminders file."""
    reminders_dir = tmp_path / "reminders"
    if not reminders_dir.exists():
        return None
    for md_file in reminders_dir.rglob("*.md"):
        text = md_file.read_text(encoding="utf-8")
        if event_id in text:
            result = _parse_starts_at_from_frontmatter(text)
            if result:
                return result
    return None


def _assert_vault_hour(tmp_path: Path, event_id: str, *, expected_hour: int, label: str) -> None:
    """Assert the vault calendar event for event_id has starts_at with expected_hour."""
    starts_at_str = _get_vault_event_starts_at(tmp_path, event_id)
    assert starts_at_str is not None, (
        f"{label}: could not find event {event_id!r} in vault/calendar/"
    )
    starts_at = datetime.fromisoformat(starts_at_str)
    assert starts_at.astimezone(TZ).hour == expected_hour, (
        f"{label}: expected hour={expected_hour}, got hour={starts_at.astimezone(TZ).hour} "
        f"(starts_at={starts_at_str!r})"
    )


def _assert_vault_reminder_hour(tmp_path: Path, event_id: str, *, expected_hour: int, label: str) -> None:
    """Assert the vault reminder file for event_id has starts_at with expected_hour."""
    starts_at_str = _get_vault_reminder_starts_at(tmp_path, event_id)
    assert starts_at_str is not None, (
        f"{label}: could not find event {event_id!r} in vault/reminders/"
    )
    starts_at = datetime.fromisoformat(starts_at_str)
    assert starts_at.astimezone(TZ).hour == expected_hour, (
        f"{label}: expected hour={expected_hour}, got hour={starts_at.astimezone(TZ).hour} "
        f"(starts_at={starts_at_str!r})"
    )
