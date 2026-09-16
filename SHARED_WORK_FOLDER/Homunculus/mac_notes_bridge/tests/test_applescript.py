"""
test_applescript.py — Tests for applescript.py.

Strategy:
- All osascript invocations are mocked via unittest.mock.patch.
  Never run real osascript against Notes.app in automated tests.
- Platform-dependent tests are skipped on Linux via pytest.mark.skipif.
- run_applescript() error/timeout paths are platform-neutral (mocked subprocess).

Key differences from Calendar bridge applescript tests:
- Notes.app uses `tell account "iCloud"` (valid in Notes.app AppleScript,
  unlike Calendar.app which has no account concept).
- Idempotency uses title matching (not URL matching).
- push_note builds a `make new note with properties {name:..., body:...}` call.
"""

from __future__ import annotations

import subprocess
import sys
import textwrap
from datetime import datetime, timezone
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from mac_notes_bridge.applescript import (
    AppleScriptError,
    push_note,
    query_pushed_note_ids,
    run_applescript,
    verify_folder_exists,
)
from mac_notes_bridge.vault_reader import NoteRecord


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _utc(year, month, day, hour, minute, second=0) -> datetime:
    return datetime(year, month, day, hour, minute, second, tzinfo=timezone.utc)


def _make_note(
    note_id="2026-09-15-test-notes-mechanism",
    title="test notes mechanism",
    body="Take a note. We have to test that the notes mechanism works.",
    captured_at=None,
) -> NoteRecord:
    if captured_at is None:
        captured_at = _utc(2026, 9, 15, 22, 38, 55)
    return NoteRecord(
        note_id=note_id,
        title=title,
        captured_at=captured_at,
        body=body,
        source_path=Path("/tmp/fake.md"),
    )


# ---------------------------------------------------------------------------
# Platform guard
# ---------------------------------------------------------------------------

_DARWIN_ONLY = pytest.mark.skipif(
    sys.platform != "darwin", reason="AppleScript only available on macOS"
)


# ---------------------------------------------------------------------------
# Tests: run_applescript (mocked subprocess)
# ---------------------------------------------------------------------------

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


def test_run_applescript_raises_on_linux():
    if sys.platform == "darwin":
        pytest.skip("Only tests Linux behavior")
    with pytest.raises(NotImplementedError):
        run_applescript("some script")


# ---------------------------------------------------------------------------
# Tests: verify_folder_exists (mocked)
# ---------------------------------------------------------------------------

@_DARWIN_ONLY
class TestVerifyFolderExists:
    def test_returns_true_when_folder_found(self):
        with patch("mac_notes_bridge.applescript.run_applescript", return_value="true"):
            result = verify_folder_exists("Homunculus", "iCloud")
        assert result is True

    def test_returns_false_when_folder_missing(self):
        with patch("mac_notes_bridge.applescript.run_applescript", return_value="false"):
            result = verify_folder_exists("Homunculus", "iCloud")
        assert result is False

    def test_script_contains_folder_name(self):
        with patch("mac_notes_bridge.applescript.run_applescript") as mock_run:
            mock_run.return_value = "true"
            verify_folder_exists("Homunculus", "iCloud")
        script = mock_run.call_args[0][0]
        assert "Homunculus" in script

    def test_script_contains_account_name(self):
        with patch("mac_notes_bridge.applescript.run_applescript") as mock_run:
            mock_run.return_value = "true"
            verify_folder_exists("Homunculus", "iCloud")
        script = mock_run.call_args[0][0]
        assert "iCloud" in script

    def test_script_targets_notes_app(self):
        with patch("mac_notes_bridge.applescript.run_applescript") as mock_run:
            mock_run.return_value = "true"
            verify_folder_exists("Homunculus", "iCloud")
        script = mock_run.call_args[0][0]
        assert "Notes" in script

    def test_uses_tell_account_syntax(self):
        """Notes.app supports tell account (unlike Calendar.app which has no account)."""
        with patch("mac_notes_bridge.applescript.run_applescript") as mock_run:
            mock_run.return_value = "true"
            verify_folder_exists("Homunculus", "iCloud")
        script = mock_run.call_args[0][0]
        assert 'tell account "iCloud"' in script

    def test_raises_applescript_error_on_failure(self):
        with patch(
            "mac_notes_bridge.applescript.run_applescript",
            side_effect=AppleScriptError("denied"),
        ):
            with pytest.raises(AppleScriptError, match="denied"):
                verify_folder_exists("Homunculus", "iCloud")

    def test_custom_account_name(self):
        with patch("mac_notes_bridge.applescript.run_applescript") as mock_run:
            mock_run.return_value = "true"
            verify_folder_exists("Homunculus", "Personal")
        script = mock_run.call_args[0][0]
        assert "Personal" in script


def test_verify_folder_exists_raises_on_linux():
    if sys.platform == "darwin":
        pytest.skip("Only tests Linux behavior")
    with pytest.raises(NotImplementedError):
        verify_folder_exists("Homunculus", "iCloud")


# ---------------------------------------------------------------------------
# Tests: query_pushed_note_ids (mocked)
# ---------------------------------------------------------------------------

@_DARWIN_ONLY
class TestQueryPushedNoteIds:
    def test_empty_result(self):
        with patch("mac_notes_bridge.applescript.run_applescript", return_value=""):
            result = query_pushed_note_ids("Homunculus", "iCloud")
        assert result == []

    def test_parses_single_title(self):
        raw = "test notes mechanism"
        with patch("mac_notes_bridge.applescript.run_applescript", return_value=raw):
            result = query_pushed_note_ids("Homunculus", "iCloud")
        assert result == ["test notes mechanism"]

    def test_parses_multiple_titles(self):
        raw = "first note, second note, third note"
        with patch("mac_notes_bridge.applescript.run_applescript", return_value=raw):
            result = query_pushed_note_ids("Homunculus", "iCloud")
        assert len(result) == 3
        assert "first note" in result
        assert "second note" in result
        assert "third note" in result

    def test_script_targets_notes_app(self):
        with patch("mac_notes_bridge.applescript.run_applescript", return_value="") as mock_run:
            query_pushed_note_ids("Homunculus", "iCloud")
        script = mock_run.call_args[0][0]
        assert "Notes" in script

    def test_script_uses_tell_account(self):
        with patch("mac_notes_bridge.applescript.run_applescript", return_value="") as mock_run:
            query_pushed_note_ids("Homunculus", "iCloud")
        script = mock_run.call_args[0][0]
        assert 'tell account "iCloud"' in script

    def test_script_uses_tell_folder(self):
        with patch("mac_notes_bridge.applescript.run_applescript", return_value="") as mock_run:
            query_pushed_note_ids("Homunculus", "iCloud")
        script = mock_run.call_args[0][0]
        assert 'tell folder "Homunculus"' in script

    def test_strips_whitespace_from_titles(self):
        raw = "  first note  ,  second note  "
        with patch("mac_notes_bridge.applescript.run_applescript", return_value=raw):
            result = query_pushed_note_ids("Homunculus", "iCloud")
        assert "first note" in result
        assert "second note" in result


def test_query_pushed_note_ids_raises_on_linux():
    if sys.platform == "darwin":
        pytest.skip("Only tests Linux behavior")
    with pytest.raises(NotImplementedError):
        query_pushed_note_ids("Homunculus", "iCloud")


# ---------------------------------------------------------------------------
# Tests: push_note (mocked)
# ---------------------------------------------------------------------------

@_DARWIN_ONLY
class TestPushNote:
    def test_calls_osascript(self):
        note = _make_note()
        with patch("mac_notes_bridge.applescript.run_applescript") as mock_run:
            mock_run.return_value = ""
            push_note(note, "Homunculus", "iCloud")
        mock_run.assert_called_once()

    def test_script_contains_title(self):
        note = _make_note(title="test notes mechanism")
        with patch("mac_notes_bridge.applescript.run_applescript") as mock_run:
            mock_run.return_value = ""
            push_note(note, "Homunculus", "iCloud")
        script = mock_run.call_args[0][0]
        assert "test notes mechanism" in script

    def test_script_contains_body(self):
        note = _make_note(body="Take a note. Test content here.")
        with patch("mac_notes_bridge.applescript.run_applescript") as mock_run:
            mock_run.return_value = ""
            push_note(note, "Homunculus", "iCloud")
        script = mock_run.call_args[0][0]
        assert "Test content here" in script

    def test_script_targets_notes_app(self):
        note = _make_note()
        with patch("mac_notes_bridge.applescript.run_applescript") as mock_run:
            mock_run.return_value = ""
            push_note(note, "Homunculus", "iCloud")
        script = mock_run.call_args[0][0]
        assert "Notes" in script

    def test_script_uses_tell_account(self):
        """Notes.app push_note must use tell account (not available in Calendar.app)."""
        note = _make_note()
        with patch("mac_notes_bridge.applescript.run_applescript") as mock_run:
            mock_run.return_value = ""
            push_note(note, "Homunculus", "iCloud")
        script = mock_run.call_args[0][0]
        assert 'tell account "iCloud"' in script

    def test_script_uses_tell_folder(self):
        note = _make_note()
        with patch("mac_notes_bridge.applescript.run_applescript") as mock_run:
            mock_run.return_value = ""
            push_note(note, "Homunculus", "iCloud")
        script = mock_run.call_args[0][0]
        assert 'tell folder "Homunculus"' in script

    def test_name_and_body_in_make_properties(self):
        """CRITICAL: both name and body must be in the make new note with properties
        dict — atomic creation, no two-step make-then-set-body.
        Lesson from Calendar bridge v0.1.5: two-step patterns can silently roll back."""
        note = _make_note()
        with patch("mac_notes_bridge.applescript.run_applescript") as mock_run:
            mock_run.return_value = ""
            push_note(note, "Homunculus", "iCloud")
        script = mock_run.call_args[0][0]
        assert "make new note with properties" in script
        assert "name:" in script
        assert "body:" in script

    def test_no_two_step_set_body(self):
        """The 'set body of newNote' two-step pattern must NOT appear.
        It can silently fail on macOS 15.x — same bug as Calendar bridge."""
        note = _make_note()
        with patch("mac_notes_bridge.applescript.run_applescript") as mock_run:
            mock_run.return_value = ""
            push_note(note, "Homunculus", "iCloud")
        script = mock_run.call_args[0][0]
        assert "set body of" not in script

    def test_title_quotes_escaped(self):
        note = _make_note(title='say "hello"')
        with patch("mac_notes_bridge.applescript.run_applescript") as mock_run:
            mock_run.return_value = ""
            push_note(note, "Homunculus", "iCloud")
        script = mock_run.call_args[0][0]
        # The raw unescaped double-quote inside the AppleScript string must be escaped
        assert '\\"hello\\"' in script

    def test_body_quotes_escaped(self):
        note = _make_note(body='Contains "quoted" text.')
        with patch("mac_notes_bridge.applescript.run_applescript") as mock_run:
            mock_run.return_value = ""
            push_note(note, "Homunculus", "iCloud")
        script = mock_run.call_args[0][0]
        assert '\\"quoted\\"' in script

    def test_raises_applescript_error_on_failure(self):
        note = _make_note()
        with patch(
            "mac_notes_bridge.applescript.run_applescript",
            side_effect=AppleScriptError("not allowed"),
        ):
            with pytest.raises(AppleScriptError):
                push_note(note, "Homunculus", "iCloud")

    def test_applescript_error_propagates_loudly(self):
        """push_note must re-raise AppleScriptError — never swallow it."""
        note = _make_note()
        with patch(
            "mac_notes_bridge.applescript.run_applescript",
            side_effect=AppleScriptError("Notes.app rejected the note"),
        ):
            with pytest.raises(AppleScriptError, match="Notes.app rejected the note"):
                push_note(note, "Homunculus", "iCloud")

    def test_custom_folder_and_account(self):
        note = _make_note()
        with patch("mac_notes_bridge.applescript.run_applescript") as mock_run:
            mock_run.return_value = ""
            push_note(note, "MyFolder", "Work")
        script = mock_run.call_args[0][0]
        assert 'tell folder "MyFolder"' in script
        assert 'tell account "Work"' in script

    def test_real_note_all_four_vault_notes(self):
        """Push all four real vault notes (from vault/notes/ inspection)."""
        real_notes = [
            ("2026-09-15-a-way", "a way", "Take a note I thought maybe a way"),
            ("2026-09-15-mechanism-to-close-the-loop-between-phone-and-mac",
             "mechanism to close the loop between phone and Mac",
             "Maybe a mechanism to close the loop between the phone and the Mac."),
            ("2026-09-15-test-notes-mechanism",
             "test notes mechanism",
             "We have to test that the notes mechanism works."),
            ("2026-09-15-voice-message-deletion-and-cancellation",
             "voice message deletion and cancellation",
             "What happens if a voice message is deleted."),
        ]
        for note_id, title, body in real_notes:
            note = _make_note(note_id=note_id, title=title, body=body)
            with patch("mac_notes_bridge.applescript.run_applescript") as mock_run:
                mock_run.return_value = ""
                push_note(note, "Homunculus", "iCloud")
            script = mock_run.call_args[0][0]
            assert title in script or title.replace('"', '\\"') in script


def test_push_note_raises_on_linux():
    if sys.platform == "darwin":
        pytest.skip("Only tests Linux behavior")
    note = _make_note()
    with pytest.raises(NotImplementedError):
        push_note(note, "Homunculus", "iCloud")


# ---------------------------------------------------------------------------
# Tests: Config values for notes bridge
# ---------------------------------------------------------------------------

class TestConfigNotesBridge:
    def test_config_has_folder_name(self):
        from mac_notes_bridge.config import Config
        cfg = Config.from_env()
        assert cfg.folder_name == "Homunculus"

    def test_config_has_notes_account(self):
        from mac_notes_bridge.config import Config
        cfg = Config.from_env()
        assert cfg.notes_account == "iCloud"

    def test_config_from_env_sets_folder_name(self, monkeypatch):
        monkeypatch.setenv("BRIDGE_FOLDER_NAME", "MyNotes")
        from mac_notes_bridge.config import Config
        cfg = Config.from_env()
        assert cfg.folder_name == "MyNotes"

    def test_config_from_env_sets_account(self, monkeypatch):
        monkeypatch.setenv("BRIDGE_NOTES_ACCOUNT", "Work")
        from mac_notes_bridge.config import Config
        cfg = Config.from_env()
        assert cfg.notes_account == "Work"

    def test_config_has_no_calendar_fields(self):
        """Notes config must not accidentally carry Calendar bridge fields."""
        from mac_notes_bridge.config import Config
        cfg = Config.from_env()
        assert not hasattr(cfg, "calendar_name")
        assert not hasattr(cfg, "calendar_root")
