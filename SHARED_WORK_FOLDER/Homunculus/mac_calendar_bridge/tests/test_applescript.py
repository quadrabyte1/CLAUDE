"""
test_applescript.py — Tests for applescript.py.

Strategy:
- All osascript invocations are mocked via unittest.mock.patch.
  Never run real osascript against Calendar.app in automated tests.
- Platform-dependent tests are skipped on Linux via pytest.mark.skipif.
- format_applescript_date() is platform-neutral and always runs.

v0.1.2: removed ensure_calendar tests (function deleted). Removed account-
scoping tests (tell account is invalid in Calendar.app AppleScript). Added
verify_calendar_exists tests (now in test_v012_no_account.py as well).
"""

from __future__ import annotations

import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path
from unittest.mock import MagicMock, patch
from zoneinfo import ZoneInfo

import pytest

from mac_calendar_bridge.applescript import (
    AppleScriptError,
    format_applescript_date,
    push_event,
    query_pushed_event_ids,
    run_applescript,
    verify_calendar_exists,
)
from mac_calendar_bridge.vault_reader import EventRecord

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _utc(year, month, day, hour, minute, second=0) -> datetime:
    return datetime(year, month, day, hour, minute, second, tzinfo=timezone.utc)


def _make_event(
    event_id="2026-09-15-meeting-with-myself",
    title="meeting with myself",
    starts_at=None,
    ends_at=None,
    tz="America/New_York",
) -> EventRecord:
    if starts_at is None:
        starts_at = _utc(2026, 9, 15, 13, 0)  # 9 AM EDT
    if ends_at is None:
        ends_at = _utc(2026, 9, 15, 13, 30)
    return EventRecord(
        event_id=event_id,
        title=title,
        starts_at=starts_at,
        ends_at=ends_at,
        tz=tz,
        duration_minutes=30,
        source_path=Path("/tmp/fake.md"),
    )


# ---------------------------------------------------------------------------
# Tests: format_applescript_date (platform-neutral)
# ---------------------------------------------------------------------------

class TestFormatAppleScriptDate:
    def test_tuesday_sep_15_9am(self):
        dt = _utc(2026, 9, 15, 13, 0)  # 9:00 AM EDT
        result = format_applescript_date(dt, "America/New_York")
        assert result == "Tuesday, September 15, 2026 at 9:00 AM"

    def test_friday_sep_18_10am(self):
        dt = _utc(2026, 9, 18, 14, 0)  # 10:00 AM EDT
        result = format_applescript_date(dt, "America/New_York")
        assert result == "Friday, September 18, 2026 at 10:00 AM"

    def test_pm_time(self):
        dt = _utc(2026, 9, 15, 17, 30)  # 1:30 PM EDT
        result = format_applescript_date(dt, "America/New_York")
        assert result == "Tuesday, September 15, 2026 at 1:30 PM"

    def test_noon_is_pm(self):
        dt = _utc(2026, 9, 15, 16, 0)  # noon EDT
        result = format_applescript_date(dt, "America/New_York")
        assert result == "Tuesday, September 15, 2026 at 12:00 PM"

    def test_midnight_is_am(self):
        dt = _utc(2026, 9, 15, 4, 0)  # midnight EDT
        result = format_applescript_date(dt, "America/New_York")
        assert result == "Tuesday, September 15, 2026 at 12:00 AM"

    def test_eleven_am(self):
        dt = _utc(2026, 9, 15, 15, 0)  # 11 AM EDT
        result = format_applescript_date(dt, "America/New_York")
        assert result == "Tuesday, September 15, 2026 at 11:00 AM"

    def test_eleven_pm(self):
        dt = _utc(2026, 9, 16, 3, 0)  # 11 PM EDT on Sep 15
        result = format_applescript_date(dt, "America/New_York")
        assert result == "Tuesday, September 15, 2026 at 11:00 PM"

    def test_pacific_tz(self):
        # Same UTC instant, expressed in Pacific time (PDT = UTC-7)
        dt = _utc(2026, 9, 15, 16, 0)  # 9 AM PDT
        result = format_applescript_date(dt, "America/Los_Angeles")
        assert result == "Tuesday, September 15, 2026 at 9:00 AM"

    def test_dst_spring_forward(self):
        """2026-03-08 at 9 AM ET — week before spring-forward (2026-03-08 is the day OF)."""
        # 2026-03-08 is DST changeover in the US. Before 2 AM: EST (UTC-5). After: EDT (UTC-4).
        # So 9 AM EDT on Mar 8 = 13:00 UTC
        dt = _utc(2026, 3, 8, 14, 0)  # 9 AM after spring-forward on Mar 8
        result = format_applescript_date(dt, "America/New_York")
        assert result == "Sunday, March 8, 2026 at 10:00 AM"

    def test_minutes_zero_padded(self):
        dt = _utc(2026, 9, 15, 13, 5)  # 9:05 AM EDT
        result = format_applescript_date(dt, "America/New_York")
        assert result == "Tuesday, September 15, 2026 at 9:05 AM"

    def test_includes_weekday(self):
        result = format_applescript_date(_utc(2026, 9, 15, 13, 0), "America/New_York")
        assert "Tuesday" in result

    def test_includes_month_name(self):
        result = format_applescript_date(_utc(2026, 9, 15, 13, 0), "America/New_York")
        assert "September" in result


# ---------------------------------------------------------------------------
# Tests: run_applescript (mocked subprocess)
# ---------------------------------------------------------------------------

_DARWIN_ONLY = pytest.mark.skipif(
    sys.platform != "darwin", reason="AppleScript only available on macOS"
)


@_DARWIN_ONLY
class TestRunAppleScript:
    def test_returns_stdout(self):
        mock_result = MagicMock()
        mock_result.returncode = 0
        mock_result.stdout = "hello\n"
        mock_result.stderr = ""
        with patch("subprocess.run", return_value=mock_result) as mock_run:
            result = run_applescript('return "hello"')
        assert result == "hello"
        mock_run.assert_called_once()

    def test_raises_on_nonzero_exit(self):
        mock_result = MagicMock()
        mock_result.returncode = 1
        mock_result.stdout = ""
        mock_result.stderr = "error: not allowed"
        with patch("subprocess.run", return_value=mock_result):
            with pytest.raises(AppleScriptError, match="osascript exited 1"):
                run_applescript("bad script")

    def test_raises_on_timeout(self):
        with patch("subprocess.run", side_effect=subprocess.TimeoutExpired(cmd="osascript", timeout=30)):
            with pytest.raises(AppleScriptError, match="timed out"):
                run_applescript("slow script")

    def test_passes_script_as_e_flag(self):
        mock_result = MagicMock()
        mock_result.returncode = 0
        mock_result.stdout = ""
        mock_result.stderr = ""
        with patch("subprocess.run", return_value=mock_result) as mock_run:
            run_applescript("my script")
        args = mock_run.call_args[0][0]
        assert args[0] == "osascript"
        assert args[1] == "-e"
        assert args[2] == "my script"

    def test_strips_whitespace_from_output(self):
        mock_result = MagicMock()
        mock_result.returncode = 0
        mock_result.stdout = "  result  \n"
        mock_result.stderr = ""
        with patch("subprocess.run", return_value=mock_result):
            result = run_applescript("return 1")
        assert result == "result"


# ---------------------------------------------------------------------------
# Tests: verify_calendar_exists (mocked) — replaces ensure_calendar
# ---------------------------------------------------------------------------

@_DARWIN_ONLY
class TestVerifyCalendarExists:
    def test_returns_true_when_calendar_found(self):
        with patch("mac_calendar_bridge.applescript.run_applescript", return_value="true"):
            result = verify_calendar_exists("Homunculus")
        assert result is True

    def test_returns_false_when_calendar_missing(self):
        with patch("mac_calendar_bridge.applescript.run_applescript", return_value="false"):
            result = verify_calendar_exists("Homunculus")
        assert result is False

    def test_calls_osascript(self):
        with patch("mac_calendar_bridge.applescript.run_applescript") as mock_run:
            mock_run.return_value = "true"
            verify_calendar_exists("Homunculus")
        mock_run.assert_called_once()
        script = mock_run.call_args[0][0]
        assert "Homunculus" in script
        assert "Calendar" in script

    def test_raises_applescript_error_on_failure(self):
        with patch(
            "mac_calendar_bridge.applescript.run_applescript",
            side_effect=AppleScriptError("denied"),
        ):
            with pytest.raises(AppleScriptError, match="denied"):
                verify_calendar_exists("Homunculus")


def test_verify_calendar_exists_raises_on_linux():
    if sys.platform == "darwin":
        pytest.skip("Only tests Linux behavior")
    with pytest.raises(NotImplementedError):
        verify_calendar_exists("Homunculus")


# ---------------------------------------------------------------------------
# Tests: push_event (mocked)
# ---------------------------------------------------------------------------

@_DARWIN_ONLY
class TestPushEvent:
    def test_calls_osascript_with_event_details(self):
        event = _make_event()
        with patch("mac_calendar_bridge.applescript.run_applescript") as mock_run:
            mock_run.return_value = ""
            push_event(event, "Homunculus")
        script = mock_run.call_args[0][0]
        assert "meeting with myself" in script
        assert "Homunculus" in script
        assert "homunculus://event/2026-09-15-meeting-with-myself" in script

    def test_event_url_contains_event_id(self):
        event = _make_event()
        with patch("mac_calendar_bridge.applescript.run_applescript") as mock_run:
            mock_run.return_value = ""
            push_event(event, "Homunculus")
        script = mock_run.call_args[0][0]
        assert "homunculus://event/2026-09-15-meeting-with-myself" in script

    def test_starts_at_in_script(self):
        event = _make_event(starts_at=_utc(2026, 9, 15, 13, 0))
        with patch("mac_calendar_bridge.applescript.run_applescript") as mock_run:
            mock_run.return_value = ""
            push_event(event, "Homunculus")
        script = mock_run.call_args[0][0]
        assert "Tuesday, September 15, 2026 at 9:00 AM" in script

    def test_ends_at_in_script(self):
        event = _make_event(ends_at=_utc(2026, 9, 15, 13, 30))
        with patch("mac_calendar_bridge.applescript.run_applescript") as mock_run:
            mock_run.return_value = ""
            push_event(event, "Homunculus")
        script = mock_run.call_args[0][0]
        assert "Tuesday, September 15, 2026 at 9:30 AM" in script

    def test_raises_applescript_error_on_failure(self):
        event = _make_event()
        with patch(
            "mac_calendar_bridge.applescript.run_applescript",
            side_effect=AppleScriptError("not allowed"),
        ):
            with pytest.raises(AppleScriptError):
                push_event(event, "Homunculus")

    def test_title_quotes_escaped(self):
        event = _make_event(title='say "hello"')
        with patch("mac_calendar_bridge.applescript.run_applescript") as mock_run:
            mock_run.return_value = ""
            push_event(event, "Homunculus")
        script = mock_run.call_args[0][0]
        assert '\\"hello\\"' in script or '"hello"' not in script.replace('\\"hello\\"', "ESCAPED")

    def test_code_review_event(self):
        """Push the Sep 18 code review event."""
        event = _make_event(
            event_id="2026-09-18-code-review-with-myself",
            title="code review with myself",
            starts_at=_utc(2026, 9, 18, 14, 0),  # 10 AM EDT
            ends_at=_utc(2026, 9, 18, 14, 30),
        )
        with patch("mac_calendar_bridge.applescript.run_applescript") as mock_run:
            mock_run.return_value = ""
            push_event(event, "Homunculus")
        script = mock_run.call_args[0][0]
        assert "code review with myself" in script
        assert "Friday, September 18, 2026 at 10:00 AM" in script
        assert "homunculus://event/2026-09-18-code-review-with-myself" in script

    def test_script_uses_tell_calendar_directly(self):
        """push_event must use tell calendar directly, not tell account."""
        event = _make_event()
        with patch("mac_calendar_bridge.applescript.run_applescript") as mock_run:
            mock_run.return_value = ""
            push_event(event, "Homunculus")
        script = mock_run.call_args[0][0]
        assert 'tell calendar "Homunculus"' in script
        assert "tell account" not in script


def test_push_event_raises_on_linux():
    if sys.platform == "darwin":
        pytest.skip("Only tests Linux behavior")
    event = _make_event()
    with pytest.raises(NotImplementedError):
        push_event(event, "Homunculus")


# ---------------------------------------------------------------------------
# Tests: query_pushed_event_ids (mocked)
# ---------------------------------------------------------------------------

@_DARWIN_ONLY
class TestQueryPushedEventIds:
    def test_empty_result(self):
        with patch("mac_calendar_bridge.applescript.run_applescript", return_value=""):
            result = query_pushed_event_ids("Homunculus", "Monday, September 15, 2026 at 12:00 AM")
        assert result == []

    def test_parses_single_url(self):
        raw = "homunculus://event/2026-09-15-meeting-with-myself"
        with patch("mac_calendar_bridge.applescript.run_applescript", return_value=raw):
            result = query_pushed_event_ids("Homunculus", "Monday, September 15, 2026 at 12:00 AM")
        assert result == ["2026-09-15-meeting-with-myself"]

    def test_parses_multiple_urls(self):
        raw = "homunculus://event/event-a, homunculus://event/event-b"
        with patch("mac_calendar_bridge.applescript.run_applescript", return_value=raw):
            result = query_pushed_event_ids("Homunculus", "any date")
        assert set(result) == {"event-a", "event-b"}

    def test_filters_non_homunculus_urls(self):
        raw = "https://example.com, homunculus://event/my-event"
        with patch("mac_calendar_bridge.applescript.run_applescript", return_value=raw):
            result = query_pushed_event_ids("Homunculus", "any date")
        assert result == ["my-event"]

    def test_script_uses_tell_calendar_directly(self):
        """query_pushed_event_ids must use tell calendar directly, not tell account."""
        with patch("mac_calendar_bridge.applescript.run_applescript", return_value="") as mock_run:
            query_pushed_event_ids("Homunculus", "Monday, September 15, 2026 at 12:00 AM")
        script = mock_run.call_args[0][0]
        assert 'tell calendar "Homunculus"' in script
        assert "tell account" not in script


# ---------------------------------------------------------------------------
# Tests: Config (v0.1.2 — no calendar_account)
# ---------------------------------------------------------------------------

class TestConfigV012:
    """Config must not have calendar_account in v0.1.2."""

    def test_config_has_no_calendar_account(self):
        from mac_calendar_bridge.config import Config
        cfg = Config.from_env()
        assert not hasattr(cfg, "calendar_account")

    def test_config_has_calendar_name(self):
        from mac_calendar_bridge.config import Config
        cfg = Config.from_env()
        assert cfg.calendar_name == "Homunculus"

    def test_config_from_env_sets_calendar_name(self, monkeypatch):
        monkeypatch.setenv("BRIDGE_CALENDAR_NAME", "MyCalendar")
        from mac_calendar_bridge.config import Config
        cfg = Config.from_env()
        assert cfg.calendar_name == "MyCalendar"
