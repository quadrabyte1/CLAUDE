"""
test_applescript.py — Tests for mac_reminders_bridge.applescript.

All AppleScript tests mock subprocess.run. osascript is NEVER invoked.
Platform-guard tests are exercised by patching sys.platform.
"""

from __future__ import annotations

import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from mac_reminders_bridge.applescript import (
    AppleScriptError,
    format_applescript_date,
    push_reminder,
    query_pushed_reminder_ids,
    run_applescript,
    verify_list_exists,
)
from mac_reminders_bridge.vault_reader import ReminderRecord


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_record(
    event_id="2026-09-16-kiss-the-baby",
    title="kiss the baby",
    starts_at=None,
    tz="America/New_York",
    is_critical=False,
    verb="handle",
    body="Kiss the baby again.",
    source_path=None,
) -> ReminderRecord:
    return ReminderRecord(
        event_id=event_id,
        title=title,
        starts_at=starts_at,
        tz=tz,
        is_critical=is_critical,
        verb=verb,
        body=body,
        source_path=source_path or Path("/tmp/fake.md"),
    )


def _subprocess_ok(stdout: str = "") -> MagicMock:
    """Return a mock subprocess.CompletedProcess with returncode=0."""
    m = MagicMock()
    m.returncode = 0
    m.stdout = stdout
    m.stderr = ""
    return m


def _subprocess_fail(returncode: int = 1, stderr: str = "error") -> MagicMock:
    m = MagicMock()
    m.returncode = returncode
    m.stdout = ""
    m.stderr = stderr
    return m


# ---------------------------------------------------------------------------
# format_applescript_date
# ---------------------------------------------------------------------------

class TestFormatApplescriptDate:
    def test_basic_format(self):
        dt = datetime(2026, 9, 16, 12, 0, 0, tzinfo=timezone.utc)
        result = format_applescript_date(dt, "America/New_York")
        # 12:00 UTC = 08:00 AM EDT (UTC-4)
        assert "Wednesday" in result
        assert "September" in result
        assert "2026" in result

    def test_am_pm_morning(self):
        dt = datetime(2026, 9, 16, 12, 0, 0, tzinfo=timezone.utc)
        result = format_applescript_date(dt, "America/New_York")
        assert "AM" in result

    def test_am_pm_afternoon(self):
        dt = datetime(2026, 9, 16, 20, 0, 0, tzinfo=timezone.utc)
        result = format_applescript_date(dt, "America/New_York")
        assert "PM" in result

    def test_noon_is_pm(self):
        # 16:00 UTC = 12:00 PM EDT
        dt = datetime(2026, 9, 16, 16, 0, 0, tzinfo=timezone.utc)
        result = format_applescript_date(dt, "America/New_York")
        assert "PM" in result
        assert "12:00" in result

    def test_midnight_is_am(self):
        # 04:00 UTC = 00:00 AM EDT
        dt = datetime(2026, 9, 16, 4, 0, 0, tzinfo=timezone.utc)
        result = format_applescript_date(dt, "America/New_York")
        assert "AM" in result
        assert "12:00" in result

    def test_minute_zero_padding(self):
        dt = datetime(2026, 9, 16, 14, 5, 0, tzinfo=timezone.utc)
        result = format_applescript_date(dt, "America/New_York")
        assert ":05" in result

    def test_uses_target_timezone(self):
        dt = datetime(2026, 9, 16, 12, 0, 0, tzinfo=timezone.utc)
        ny = format_applescript_date(dt, "America/New_York")
        la = format_applescript_date(dt, "America/Los_Angeles")
        # Same UTC time → different local hours
        assert ny != la


# ---------------------------------------------------------------------------
# run_applescript
# ---------------------------------------------------------------------------

class TestRunApplescript:
    def test_success_returns_stripped_stdout(self):
        with patch("subprocess.run", return_value=_subprocess_ok("  hello  ")):
            result = run_applescript("-- test")
        assert result == "hello"

    def test_raises_on_nonzero_returncode(self):
        with patch("subprocess.run", return_value=_subprocess_fail(1, "syntax error")):
            with pytest.raises(AppleScriptError, match="syntax error"):
                run_applescript("bad script")

    def test_raises_on_timeout(self):
        with patch("subprocess.run", side_effect=subprocess.TimeoutExpired("osascript", 30)):
            with pytest.raises(AppleScriptError, match="timed out"):
                run_applescript("slow script")

    def test_raises_not_implemented_on_linux(self):
        with patch.object(sys, "platform", "linux"):
            with pytest.raises(NotImplementedError):
                run_applescript("-- test")

    def test_calls_osascript_with_e_flag(self):
        with patch("subprocess.run", return_value=_subprocess_ok("")) as mock_run:
            run_applescript("tell application \"Reminders\" to quit")
        args = mock_run.call_args[0][0]
        assert args[0] == "osascript"
        assert args[1] == "-e"

    def test_timeout_passed_to_subprocess(self):
        with patch("subprocess.run", return_value=_subprocess_ok("")) as mock_run:
            run_applescript("-- test", timeout=45)
        kwargs = mock_run.call_args[1]
        assert kwargs["timeout"] == 45


# ---------------------------------------------------------------------------
# verify_list_exists
# ---------------------------------------------------------------------------

class TestVerifyListExists:
    def test_returns_true_when_list_exists(self):
        with patch("mac_reminders_bridge.applescript.run_applescript", return_value="true"):
            assert verify_list_exists("Homunculus") is True

    def test_returns_false_when_list_absent(self):
        with patch("mac_reminders_bridge.applescript.run_applescript", return_value="false"):
            assert verify_list_exists("Homunculus") is False

    def test_case_insensitive_true(self):
        with patch("mac_reminders_bridge.applescript.run_applescript", return_value="True"):
            assert verify_list_exists("Homunculus") is True

    def test_raises_not_implemented_on_linux(self):
        with patch.object(sys, "platform", "linux"):
            with pytest.raises(NotImplementedError):
                verify_list_exists("Homunculus")

    def test_script_contains_list_name(self):
        with patch("mac_reminders_bridge.applescript.run_applescript", return_value="true") as mock_run:
            verify_list_exists("MyCustomList")
        script = mock_run.call_args[0][0]
        assert "MyCustomList" in script

    def test_propagates_applescript_error(self):
        with patch(
            "mac_reminders_bridge.applescript.run_applescript",
            side_effect=AppleScriptError("connection refused"),
        ):
            with pytest.raises(AppleScriptError):
                verify_list_exists("Homunculus")


# ---------------------------------------------------------------------------
# query_pushed_reminder_ids
# ---------------------------------------------------------------------------

class TestQueryPushedReminderIds:
    def test_returns_empty_for_no_reminders(self):
        with patch("mac_reminders_bridge.applescript.run_applescript", return_value=""):
            ids = query_pushed_reminder_ids("Homunculus")
        assert ids == []

    def test_parses_single_url(self):
        raw = "homunculus://reminder/2026-09-16-kiss-the-baby"
        with patch("mac_reminders_bridge.applescript.run_applescript", return_value=raw):
            ids = query_pushed_reminder_ids("Homunculus")
        assert ids == ["2026-09-16-kiss-the-baby"]

    def test_parses_multiple_urls(self):
        raw = "homunculus://reminder/abc123, homunculus://reminder/def456"
        with patch("mac_reminders_bridge.applescript.run_applescript", return_value=raw):
            ids = query_pushed_reminder_ids("Homunculus")
        assert set(ids) == {"abc123", "def456"}

    def test_ignores_non_homunculus_urls(self):
        raw = "https://example.com, homunculus://reminder/real-id"
        with patch("mac_reminders_bridge.applescript.run_applescript", return_value=raw):
            ids = query_pushed_reminder_ids("Homunculus")
        assert ids == ["real-id"]

    def test_raises_not_implemented_on_linux(self):
        with patch.object(sys, "platform", "linux"):
            with pytest.raises(NotImplementedError):
                query_pushed_reminder_ids("Homunculus")

    def test_script_contains_list_name(self):
        with patch("mac_reminders_bridge.applescript.run_applescript", return_value="") as mock_run:
            query_pushed_reminder_ids("MyList")
        script = mock_run.call_args[0][0]
        assert "MyList" in script

    def test_propagates_applescript_error(self):
        with patch(
            "mac_reminders_bridge.applescript.run_applescript",
            side_effect=AppleScriptError("timeout"),
        ):
            with pytest.raises(AppleScriptError):
                query_pushed_reminder_ids("Homunculus")


# ---------------------------------------------------------------------------
# push_reminder
# ---------------------------------------------------------------------------

class TestPushReminder:
    def test_calls_run_applescript(self):
        record = _make_record()
        with patch("mac_reminders_bridge.applescript.run_applescript", return_value="") as mock_run:
            push_reminder(record, "Homunculus")
        mock_run.assert_called_once()

    def test_script_contains_display_title(self):
        record = _make_record(title="call the vet")
        with patch("mac_reminders_bridge.applescript.run_applescript", return_value="") as mock_run:
            push_reminder(record, "Homunculus")
        script = mock_run.call_args[0][0]
        assert "call the vet" in script

    def test_script_contains_homunculus_url(self):
        record = _make_record(event_id="2026-09-16-kiss-the-baby")
        with patch("mac_reminders_bridge.applescript.run_applescript", return_value="") as mock_run:
            push_reminder(record, "Homunculus")
        script = mock_run.call_args[0][0]
        assert "homunculus://reminder/2026-09-16-kiss-the-baby" in script

    def test_script_contains_body_sentinel(self):
        record = _make_record(event_id="2026-09-16-kiss-the-baby")
        with patch("mac_reminders_bridge.applescript.run_applescript", return_value="") as mock_run:
            push_reminder(record, "Homunculus")
        script = mock_run.call_args[0][0]
        assert "[herman-id:2026-09-16-kiss-the-baby]" in script

    def test_script_contains_list_name(self):
        record = _make_record()
        with patch("mac_reminders_bridge.applescript.run_applescript", return_value="") as mock_run:
            push_reminder(record, "Homunculus")
        script = mock_run.call_args[0][0]
        assert "Homunculus" in script

    def test_script_has_due_date_when_starts_at_set(self):
        dt = datetime(2026, 9, 16, 12, 0, 0, tzinfo=timezone.utc)
        record = _make_record(starts_at=dt)
        with patch("mac_reminders_bridge.applescript.run_applescript", return_value="") as mock_run:
            push_reminder(record, "Homunculus")
        script = mock_run.call_args[0][0]
        assert "due date" in script

    def test_script_has_no_due_date_when_starts_at_absent(self):
        record = _make_record(starts_at=None)
        with patch("mac_reminders_bridge.applescript.run_applescript", return_value="") as mock_run:
            push_reminder(record, "Homunculus")
        script = mock_run.call_args[0][0]
        assert "due date" not in script

    def test_script_has_no_remind_me_date(self):
        """No alarm — mac_notifier is authoritative (no double-fire)."""
        dt = datetime(2026, 9, 16, 12, 0, 0, tzinfo=timezone.utc)
        record = _make_record(starts_at=dt)
        with patch("mac_reminders_bridge.applescript.run_applescript", return_value="") as mock_run:
            push_reminder(record, "Homunculus")
        script = mock_run.call_args[0][0]
        assert "remind me date" not in script

    def test_raises_not_implemented_on_linux(self):
        record = _make_record()
        with patch.object(sys, "platform", "linux"):
            with pytest.raises(NotImplementedError):
                push_reminder(record, "Homunculus")

    def test_propagates_applescript_error(self):
        record = _make_record()
        with patch(
            "mac_reminders_bridge.applescript.run_applescript",
            side_effect=AppleScriptError("list not found"),
        ):
            with pytest.raises(AppleScriptError):
                push_reminder(record, "Homunculus")

    def test_title_quotes_escaped(self):
        """Double-quotes in title must not break the AppleScript string."""
        record = _make_record(title='say "hello" to Alice')
        with patch("mac_reminders_bridge.applescript.run_applescript", return_value="") as mock_run:
            push_reminder(record, "Homunculus")
        script = mock_run.call_args[0][0]
        # Unescaped " inside an AppleScript string literal would break it
        assert '\\"hello\\"' in script or 'say \\"hello\\"' in script

    def test_uses_single_make_new_reminder_command(self):
        """Atomic creation — only ONE 'make new reminder' call."""
        record = _make_record()
        with patch("mac_reminders_bridge.applescript.run_applescript", return_value="") as mock_run:
            push_reminder(record, "Homunculus")
        script = mock_run.call_args[0][0]
        assert script.count("make new reminder") == 1
