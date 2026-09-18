"""
test_applescript.py — Tests for mac_notifier.applescript

House rule: NEVER invoke real osascript in tests. All subprocess.run calls
are mocked. No real notifications are fired.

Covers:
- fire_notification builds correct osascript command
- fire_notification raises NotImplementedError on non-Darwin platforms
- fire_notification raises AppleScriptError on non-zero returncode
- fire_notification raises AppleScriptError on timeout
- String escaping (quotes, backslashes in body/subtitle)
- Default title and sound values
"""

from __future__ import annotations

import subprocess
import sys
from unittest import mock

import pytest

from mac_notifier.applescript import AppleScriptError, fire_notification


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_completed_process(returncode: int = 0, stdout: str = "", stderr: str = "") -> subprocess.CompletedProcess:
    return subprocess.CompletedProcess(
        args=["osascript", "-e", "..."],
        returncode=returncode,
        stdout=stdout,
        stderr=stderr,
    )


# ---------------------------------------------------------------------------
# Tests: fire_notification on Darwin (mocked)
# ---------------------------------------------------------------------------


class TestFireNotification:
    @mock.patch("mac_notifier.applescript.sys.platform", "darwin")
    @mock.patch("subprocess.run")
    def test_calls_osascript(self, mock_run):
        mock_run.return_value = _make_completed_process()
        fire_notification(body="You have a meeting.", subtitle="Morning summary")
        mock_run.assert_called_once()
        args = mock_run.call_args[0][0]
        assert args[0] == "osascript"
        assert args[1] == "-e"

    @mock.patch("mac_notifier.applescript.sys.platform", "darwin")
    @mock.patch("subprocess.run")
    def test_script_contains_body(self, mock_run):
        mock_run.return_value = _make_completed_process()
        fire_notification(body="Today: meeting at 9 AM", subtitle="Morning summary")
        script = mock_run.call_args[0][0][2]
        assert "Today: meeting at 9 AM" in script

    @mock.patch("mac_notifier.applescript.sys.platform", "darwin")
    @mock.patch("subprocess.run")
    def test_script_contains_subtitle(self, mock_run):
        mock_run.return_value = _make_completed_process()
        fire_notification(body="Body text", subtitle="Strike 1")
        script = mock_run.call_args[0][0][2]
        assert "Strike 1" in script

    @mock.patch("mac_notifier.applescript.sys.platform", "darwin")
    @mock.patch("subprocess.run")
    def test_default_title_is_homunculus(self, mock_run):
        mock_run.return_value = _make_completed_process()
        fire_notification(body="Body", subtitle="Sub")
        script = mock_run.call_args[0][0][2]
        assert "Homunculus" in script

    @mock.patch("mac_notifier.applescript.sys.platform", "darwin")
    @mock.patch("subprocess.run")
    def test_default_sound_is_default(self, mock_run):
        mock_run.return_value = _make_completed_process()
        fire_notification(body="Body", subtitle="Sub")
        script = mock_run.call_args[0][0][2]
        assert "default" in script

    @mock.patch("mac_notifier.applescript.sys.platform", "darwin")
    @mock.patch("subprocess.run")
    def test_custom_title(self, mock_run):
        mock_run.return_value = _make_completed_process()
        fire_notification(body="Body", subtitle="Sub", title="CustomTitle")
        script = mock_run.call_args[0][0][2]
        assert "CustomTitle" in script

    @mock.patch("mac_notifier.applescript.sys.platform", "darwin")
    @mock.patch("subprocess.run")
    def test_display_notification_keyword_in_script(self, mock_run):
        mock_run.return_value = _make_completed_process()
        fire_notification(body="B", subtitle="S")
        script = mock_run.call_args[0][0][2]
        assert "display notification" in script

    @mock.patch("mac_notifier.applescript.sys.platform", "darwin")
    @mock.patch("subprocess.run")
    def test_with_title_keyword_in_script(self, mock_run):
        mock_run.return_value = _make_completed_process()
        fire_notification(body="B", subtitle="S")
        script = mock_run.call_args[0][0][2]
        assert "with title" in script

    @mock.patch("mac_notifier.applescript.sys.platform", "darwin")
    @mock.patch("subprocess.run")
    def test_subtitle_keyword_in_script(self, mock_run):
        mock_run.return_value = _make_completed_process()
        fire_notification(body="B", subtitle="S")
        script = mock_run.call_args[0][0][2]
        assert "subtitle" in script

    @mock.patch("mac_notifier.applescript.sys.platform", "darwin")
    @mock.patch("subprocess.run")
    def test_sound_name_keyword_in_script(self, mock_run):
        mock_run.return_value = _make_completed_process()
        fire_notification(body="B", subtitle="S")
        script = mock_run.call_args[0][0][2]
        assert "sound name" in script


# ---------------------------------------------------------------------------
# Tests: string escaping
# ---------------------------------------------------------------------------


class TestStringEscaping:
    @mock.patch("mac_notifier.applescript.sys.platform", "darwin")
    @mock.patch("subprocess.run")
    def test_double_quote_in_body_escaped(self, mock_run):
        mock_run.return_value = _make_completed_process()
        fire_notification(body='He said "hello"', subtitle="Sub")
        script = mock_run.call_args[0][0][2]
        assert '\\"' in script

    @mock.patch("mac_notifier.applescript.sys.platform", "darwin")
    @mock.patch("subprocess.run")
    def test_double_quote_in_subtitle_escaped(self, mock_run):
        mock_run.return_value = _make_completed_process()
        fire_notification(body="Body", subtitle='Strike "1"')
        script = mock_run.call_args[0][0][2]
        assert '\\"' in script

    @mock.patch("mac_notifier.applescript.sys.platform", "darwin")
    @mock.patch("subprocess.run")
    def test_backslash_in_body_escaped(self, mock_run):
        mock_run.return_value = _make_completed_process()
        fire_notification(body="path\\to\\file", subtitle="Sub")
        script = mock_run.call_args[0][0][2]
        assert "\\\\" in script


# ---------------------------------------------------------------------------
# Tests: error handling
# ---------------------------------------------------------------------------


class TestErrorHandling:
    @mock.patch("mac_notifier.applescript.sys.platform", "linux")
    def test_raises_not_implemented_on_linux(self):
        with pytest.raises(NotImplementedError):
            fire_notification(body="B", subtitle="S")

    @mock.patch("mac_notifier.applescript.sys.platform", "win32")
    def test_raises_not_implemented_on_windows(self):
        with pytest.raises(NotImplementedError):
            fire_notification(body="B", subtitle="S")

    @mock.patch("mac_notifier.applescript.sys.platform", "darwin")
    @mock.patch("subprocess.run")
    def test_raises_applescript_error_on_nonzero_returncode(self, mock_run):
        mock_run.return_value = _make_completed_process(
            returncode=1, stderr="execution error: -1708"
        )
        with pytest.raises(AppleScriptError):
            fire_notification(body="B", subtitle="S")

    @mock.patch("mac_notifier.applescript.sys.platform", "darwin")
    @mock.patch("subprocess.run", side_effect=subprocess.TimeoutExpired(cmd="osascript", timeout=10))
    def test_raises_applescript_error_on_timeout(self, mock_run):
        with pytest.raises(AppleScriptError, match="timed out"):
            fire_notification(body="B", subtitle="S")

    @mock.patch("mac_notifier.applescript.sys.platform", "darwin")
    @mock.patch("subprocess.run")
    def test_no_exception_on_zero_returncode(self, mock_run):
        mock_run.return_value = _make_completed_process(returncode=0)
        # Should not raise
        fire_notification(body="B", subtitle="S")
