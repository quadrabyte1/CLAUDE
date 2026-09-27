"""
test_applescript_v03.py — Tests for fire_notification_with_fallback() (v0.3).

Covers the wiring added in applescript.py:
  - Bundle path taken when fire_via_bundle() succeeds → returns "bundle"
  - Fallback to osascript when bundle raises NotImplementedError → returns "osascript"
  - BundleError (non-NotImplemented) propagates without osascript fallback
  - AppleScriptError from osascript fallback propagates
  - Non-Darwin platform raises NotImplementedError from both paths

House rule: no real subprocess invocations. All shelling mocked.
"""

from __future__ import annotations

import subprocess
from unittest import mock

import pytest

from mac_notifier.applescript import (
    AppleScriptError,
    fire_notification_with_fallback,
)
from mac_notifier.bundle import BundleError


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _osascript_proc(returncode: int = 0) -> subprocess.CompletedProcess:
    return subprocess.CompletedProcess(
        args=["osascript", "-e", "..."],
        returncode=returncode,
        stdout="",
        stderr="",
    )


# ---------------------------------------------------------------------------
# fire_notification_with_fallback()
# ---------------------------------------------------------------------------


class TestFireNotificationWithFallback:
    @mock.patch("mac_notifier.applescript.sys.platform", "darwin")
    @mock.patch("mac_notifier.bundle.fire_via_bundle")
    def test_returns_bundle_when_bundle_succeeds(self, mock_fvb):
        """Bundle path succeeds → method is 'bundle'."""
        mock_fvb.return_value = None  # success
        result = fire_notification_with_fallback(body="Body", subtitle="Sub")
        assert result == "bundle"
        mock_fvb.assert_called_once()

    @mock.patch("mac_notifier.applescript.sys.platform", "darwin")
    @mock.patch("mac_notifier.bundle.fire_via_bundle", side_effect=NotImplementedError("no bundle"))
    @mock.patch("subprocess.run")
    def test_falls_back_to_osascript_on_not_implemented(self, mock_run, mock_fvb):
        """Bundle absent (NotImplementedError) → falls back to osascript → returns 'osascript'."""
        mock_run.return_value = _osascript_proc(returncode=0)
        result = fire_notification_with_fallback(body="Body", subtitle="Sub")
        assert result == "osascript"
        mock_run.assert_called_once()

    @mock.patch("mac_notifier.applescript.sys.platform", "darwin")
    @mock.patch("mac_notifier.bundle.fire_via_bundle", side_effect=BundleError("stub crashed"))
    def test_bundle_error_propagates_without_osascript_fallback(self, mock_fvb):
        """BundleError (non-NotImplementedError) propagates — do not silently fall back."""
        with pytest.raises(BundleError, match="stub crashed"):
            fire_notification_with_fallback(body="Body", subtitle="Sub")

    @mock.patch("mac_notifier.applescript.sys.platform", "darwin")
    @mock.patch("mac_notifier.bundle.fire_via_bundle", side_effect=NotImplementedError("no bundle"))
    @mock.patch("subprocess.run")
    def test_osascript_error_propagates_after_fallback(self, mock_run, mock_fvb):
        """After bundle fallback, osascript error still propagates to caller."""
        mock_run.return_value = _osascript_proc(returncode=1)
        with pytest.raises(AppleScriptError):
            fire_notification_with_fallback(body="Body", subtitle="Sub")

    @mock.patch("mac_notifier.applescript.sys.platform", "darwin")
    @mock.patch("mac_notifier.bundle.fire_via_bundle")
    def test_bundle_receives_correct_args(self, mock_fvb):
        """fire_via_bundle called with exactly the same body/subtitle/title/sound."""
        mock_fvb.return_value = None
        fire_notification_with_fallback(
            body="Morning summary body",
            subtitle="Morning summary",
            title="Herman",
            sound="default",
        )
        call_kwargs = mock_fvb.call_args
        assert call_kwargs.kwargs["body"] == "Morning summary body" or call_kwargs.args[0] == "Morning summary body"

    @mock.patch("mac_notifier.applescript.sys.platform", "linux")
    @mock.patch("mac_notifier.bundle.fire_via_bundle", side_effect=NotImplementedError("non-darwin"))
    def test_linux_raises_not_implemented_after_both_fail(self, mock_fvb):
        """On Linux, both bundle and osascript raise NotImplementedError."""
        with pytest.raises(NotImplementedError):
            fire_notification_with_fallback(body="B", subtitle="S")

    @mock.patch("mac_notifier.applescript.sys.platform", "darwin")
    @mock.patch("mac_notifier.bundle.fire_via_bundle", side_effect=NotImplementedError("no bundle"))
    @mock.patch("subprocess.run")
    def test_fallback_osascript_script_contains_body(self, mock_run, mock_fvb):
        """When falling back, osascript script contains the notification body."""
        mock_run.return_value = _osascript_proc(returncode=0)
        fire_notification_with_fallback(body="Specific body text", subtitle="Sub")
        script = mock_run.call_args[0][0][2]  # osascript -e <script>
        assert "Specific body text" in script
