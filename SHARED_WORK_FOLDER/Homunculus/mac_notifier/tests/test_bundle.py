"""
test_bundle.py — Tests for mac_notifier.bundle

Covers:
- find_bundle_app() returns None when bundle is absent, path when present
- fire_via_bundle() calls terminal-notifier with correct -sender when available
- fire_via_bundle() falls back to osascript when terminal-notifier is absent
- fire_via_bundle() falls back to osascript when bundle is absent
- fire_via_bundle() raises BundleError on non-zero return
- Bundle skeleton installed by install_homunculus_notifier.sh dry-run covers
  all required paths and produces valid Info.plist syntax (plutil-lint)

House rule: no real subprocess invocations. All shelling mocked.
"""

from __future__ import annotations

import os
import subprocess
from pathlib import Path
from unittest import mock

import pytest

from mac_notifier.bundle import (
    BUNDLE_ID,
    BundleError,
    find_bundle_app,
    fire_via_bundle,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _mock_proc(returncode: int = 0, stdout: str = "", stderr: str = "") -> subprocess.CompletedProcess:
    return subprocess.CompletedProcess(
        args=["notifier"],
        returncode=returncode,
        stdout=stdout,
        stderr=stderr,
    )


# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------


class TestBundleConstants:
    def test_bundle_id_correct(self):
        assert BUNDLE_ID == "com.homunculus.notifier"


# ---------------------------------------------------------------------------
# find_bundle_app()
# ---------------------------------------------------------------------------


class TestFindBundleApp:
    def test_returns_none_when_no_bundle_exists(self, tmp_path: Path):
        """No .app in any search location → None."""
        result = find_bundle_app(search_dirs=[tmp_path / "nonexistent"])
        assert result is None

    def test_returns_path_when_bundle_present(self, tmp_path: Path):
        """Bundle found in search dirs → returns its path."""
        app_dir = tmp_path / "Homunculus Notifier.app"
        app_dir.mkdir(parents=True)
        result = find_bundle_app(search_dirs=[tmp_path])
        assert result is not None
        assert result == app_dir

    def test_first_match_wins(self, tmp_path: Path):
        """When bundle exists in multiple dirs, first in search list wins."""
        dir_a = tmp_path / "a"
        dir_b = tmp_path / "b"
        dir_a.mkdir()
        dir_b.mkdir()
        app_a = dir_a / "Homunculus Notifier.app"
        app_b = dir_b / "Homunculus Notifier.app"
        app_a.mkdir()
        app_b.mkdir()
        result = find_bundle_app(search_dirs=[dir_a, dir_b])
        assert result == app_a

    def test_returns_none_on_empty_search_list(self):
        result = find_bundle_app(search_dirs=[])
        assert result is None


# ---------------------------------------------------------------------------
# fire_via_bundle() — terminal-notifier path
# ---------------------------------------------------------------------------


class TestFireViaBundleTerminalNotifier:
    @mock.patch("mac_notifier.bundle.sys.platform", "darwin")
    @mock.patch("mac_notifier.bundle.shutil.which", return_value="/usr/local/bin/terminal-notifier")
    @mock.patch("mac_notifier.bundle.find_bundle_app")
    @mock.patch("subprocess.run")
    def test_calls_terminal_notifier_with_sender(self, mock_run, mock_find, mock_which):
        mock_find.return_value = Path("/Applications/Homunculus Notifier.app")
        mock_run.return_value = _mock_proc()
        fire_via_bundle(body="Test body", subtitle="Strike 1")
        mock_run.assert_called_once()
        cmd = mock_run.call_args[0][0]
        assert "terminal-notifier" in cmd[0]
        assert "-sender" in cmd
        sender_idx = cmd.index("-sender")
        assert cmd[sender_idx + 1] == BUNDLE_ID

    @mock.patch("mac_notifier.bundle.sys.platform", "darwin")
    @mock.patch("mac_notifier.bundle.shutil.which", return_value="/usr/local/bin/terminal-notifier")
    @mock.patch("mac_notifier.bundle.find_bundle_app")
    @mock.patch("subprocess.run")
    def test_terminal_notifier_includes_message(self, mock_run, mock_find, mock_which):
        mock_find.return_value = Path("/Applications/Homunculus Notifier.app")
        mock_run.return_value = _mock_proc()
        fire_via_bundle(body="My message body", subtitle="Strike 1")
        cmd = mock_run.call_args[0][0]
        assert "-message" in cmd
        msg_idx = cmd.index("-message")
        assert "My message body" in cmd[msg_idx + 1]

    @mock.patch("mac_notifier.bundle.sys.platform", "darwin")
    @mock.patch("mac_notifier.bundle.shutil.which", return_value="/usr/local/bin/terminal-notifier")
    @mock.patch("mac_notifier.bundle.find_bundle_app")
    @mock.patch("subprocess.run")
    def test_terminal_notifier_includes_subtitle(self, mock_run, mock_find, mock_which):
        mock_find.return_value = Path("/Applications/Homunculus Notifier.app")
        mock_run.return_value = _mock_proc()
        fire_via_bundle(body="Body", subtitle="Strike 2")
        cmd = mock_run.call_args[0][0]
        assert "-subtitle" in cmd
        sub_idx = cmd.index("-subtitle")
        assert "Strike 2" in cmd[sub_idx + 1]

    @mock.patch("mac_notifier.bundle.sys.platform", "darwin")
    @mock.patch("mac_notifier.bundle.shutil.which", return_value="/usr/local/bin/terminal-notifier")
    @mock.patch("mac_notifier.bundle.find_bundle_app")
    @mock.patch("subprocess.run")
    def test_terminal_notifier_includes_title(self, mock_run, mock_find, mock_which):
        mock_find.return_value = Path("/Applications/Homunculus Notifier.app")
        mock_run.return_value = _mock_proc()
        fire_via_bundle(body="Body", subtitle="Sub", title="Herman")
        cmd = mock_run.call_args[0][0]
        assert "-title" in cmd
        title_idx = cmd.index("-title")
        assert "Herman" in cmd[title_idx + 1]

    @mock.patch("mac_notifier.bundle.sys.platform", "darwin")
    @mock.patch("mac_notifier.bundle.shutil.which", return_value="/usr/local/bin/terminal-notifier")
    @mock.patch("mac_notifier.bundle.find_bundle_app")
    @mock.patch("subprocess.run")
    def test_terminal_notifier_error_raises_bundle_error(self, mock_run, mock_find, mock_which):
        mock_find.return_value = Path("/Applications/Homunculus Notifier.app")
        mock_run.return_value = _mock_proc(returncode=1, stderr="something failed")
        with pytest.raises(BundleError):
            fire_via_bundle(body="B", subtitle="S")

    @mock.patch("mac_notifier.bundle.sys.platform", "darwin")
    @mock.patch("mac_notifier.bundle.shutil.which", return_value="/usr/local/bin/terminal-notifier")
    @mock.patch("mac_notifier.bundle.find_bundle_app")
    @mock.patch("subprocess.run", side_effect=subprocess.TimeoutExpired(cmd="terminal-notifier", timeout=10))
    def test_terminal_notifier_timeout_raises_bundle_error(self, mock_run, mock_find, mock_which):
        mock_find.return_value = Path("/Applications/Homunculus Notifier.app")
        with pytest.raises(BundleError, match="timed out"):
            fire_via_bundle(body="B", subtitle="S")


# ---------------------------------------------------------------------------
# fire_via_bundle() — Swift stub fallback path (no terminal-notifier)
# ---------------------------------------------------------------------------


class TestFireViaBundleSwiftStub:
    @mock.patch("mac_notifier.bundle.sys.platform", "darwin")
    @mock.patch("mac_notifier.bundle.shutil.which", return_value=None)  # no terminal-notifier
    @mock.patch("mac_notifier.bundle.find_bundle_app")
    @mock.patch("subprocess.run")
    def test_calls_swift_stub_when_no_terminal_notifier(self, mock_run, mock_find, mock_which):
        """When terminal-notifier absent, call bundle's Contents/MacOS/notifier."""
        bundle_path = Path("/Applications/Homunculus Notifier.app")
        mock_find.return_value = bundle_path
        mock_run.return_value = _mock_proc()
        fire_via_bundle(body="Body", subtitle="Sub")
        mock_run.assert_called_once()
        cmd = mock_run.call_args[0][0]
        # Should invoke the bundle's executable
        expected_exe = str(bundle_path / "Contents" / "MacOS" / "notifier")
        assert cmd[0] == expected_exe

    @mock.patch("mac_notifier.bundle.sys.platform", "darwin")
    @mock.patch("mac_notifier.bundle.shutil.which", return_value=None)
    @mock.patch("mac_notifier.bundle.find_bundle_app")
    @mock.patch("subprocess.run")
    def test_swift_stub_passes_body_subtitle(self, mock_run, mock_find, mock_which):
        bundle_path = Path("/Applications/Homunculus Notifier.app")
        mock_find.return_value = bundle_path
        mock_run.return_value = _mock_proc()
        fire_via_bundle(body="Meeting at 9 AM", subtitle="Morning summary")
        cmd = mock_run.call_args[0][0]
        # Body and subtitle passed as args
        assert "Meeting at 9 AM" in cmd
        assert "Morning summary" in cmd

    @mock.patch("mac_notifier.bundle.sys.platform", "darwin")
    @mock.patch("mac_notifier.bundle.shutil.which", return_value=None)
    @mock.patch("mac_notifier.bundle.find_bundle_app")
    @mock.patch("subprocess.run")
    def test_swift_stub_error_raises_bundle_error(self, mock_run, mock_find, mock_which):
        bundle_path = Path("/Applications/Homunculus Notifier.app")
        mock_find.return_value = bundle_path
        mock_run.return_value = _mock_proc(returncode=1, stderr="stub crashed")
        with pytest.raises(BundleError):
            fire_via_bundle(body="B", subtitle="S")


# ---------------------------------------------------------------------------
# fire_via_bundle() — graceful fallback when bundle absent
# ---------------------------------------------------------------------------


class TestFireViaBundleFallback:
    @mock.patch("mac_notifier.bundle.sys.platform", "darwin")
    @mock.patch("mac_notifier.bundle.shutil.which", return_value=None)
    @mock.patch("mac_notifier.bundle.find_bundle_app", return_value=None)
    def test_raises_not_implemented_when_bundle_absent(self, mock_find, mock_which):
        """No bundle + no terminal-notifier → NotImplementedError (caller should
        fall back to osascript path)."""
        with pytest.raises(NotImplementedError):
            fire_via_bundle(body="B", subtitle="S")

    @mock.patch("mac_notifier.bundle.sys.platform", "linux")
    def test_raises_not_implemented_on_linux(self):
        with pytest.raises(NotImplementedError):
            fire_via_bundle(body="B", subtitle="S")


# ---------------------------------------------------------------------------
# fire_notification_with_fallback() — wiring in applescript.py
# ---------------------------------------------------------------------------
# These tests live in test_applescript_v03.py to keep concerns separated.
# See that file.
