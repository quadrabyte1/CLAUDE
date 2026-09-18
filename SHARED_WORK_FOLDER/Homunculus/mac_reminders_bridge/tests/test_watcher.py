"""
test_watcher.py — Tests for mac_reminders_bridge.watcher.

Tests push_if_new, periodic_sweep, cold_boot_sweep, and VaultRemindersHandler.
AppleScript functions are always mocked; never invoke real osascript.
"""

from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock, call, patch

import pytest

from mac_reminders_bridge.applescript import AppleScriptError
from mac_reminders_bridge.state import PushedState
from mac_reminders_bridge.vault_reader import ReminderRecord
from mac_reminders_bridge.watcher import (
    VaultRemindersHandler,
    cold_boot_sweep,
    periodic_sweep,
    push_if_new,
)
from watchdog.events import FileCreatedEvent, FileModifiedEvent, FileMovedEvent


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _write_md(path: Path, event_id="2026-09-16-test", title="test") -> Path:
    import yaml
    fm = {"id": event_id, "title": title, "tz": "America/New_York"}
    lines = ["---", yaml.safe_dump(fm).strip(), "---", "", "body here"]
    path.write_text("\n".join(lines), encoding="utf-8")
    return path


def _make_state(tmp_path: Path) -> PushedState:
    return PushedState(tmp_path / "pushed.jsonl")


# ---------------------------------------------------------------------------
# push_if_new — fast path (already pushed)
# ---------------------------------------------------------------------------

class TestPushIfNewFastPath:
    def test_skips_if_already_in_state(self, tmp_path):
        path = _write_md(tmp_path / "ev.md", event_id="ev-1")
        state = _make_state(tmp_path)
        state.mark_pushed("ev-1")
        with patch("mac_reminders_bridge.watcher.push_reminder") as mock_push:
            push_if_new(path, state, "Homunculus")
        mock_push.assert_not_called()

    def test_does_nothing_for_non_md_file(self, tmp_path):
        txt_path = tmp_path / "note.txt"
        txt_path.write_text("hello", encoding="utf-8")
        state = _make_state(tmp_path)
        with patch("mac_reminders_bridge.watcher.push_reminder") as mock_push:
            push_if_new(txt_path, state, "Homunculus")
        mock_push.assert_not_called()


# ---------------------------------------------------------------------------
# push_if_new — slow path (Reminders.app query)
# ---------------------------------------------------------------------------

class TestPushIfNewSlowPath:
    def test_self_heals_when_in_reminders_but_not_state(self, tmp_path):
        path = _write_md(tmp_path / "ev.md", event_id="ev-heal")
        state = _make_state(tmp_path)
        with (
            patch(
                "mac_reminders_bridge.watcher.query_pushed_reminder_ids",
                return_value=["ev-heal"],
            ),
            patch("mac_reminders_bridge.watcher.push_reminder") as mock_push,
        ):
            push_if_new(path, state, "Homunculus")
        mock_push.assert_not_called()
        assert state.is_pushed("ev-heal") is True

    def test_pushes_when_not_in_reminders(self, tmp_path):
        path = _write_md(tmp_path / "ev.md", event_id="ev-new")
        state = _make_state(tmp_path)
        with (
            patch(
                "mac_reminders_bridge.watcher.query_pushed_reminder_ids",
                return_value=[],
            ),
            patch("mac_reminders_bridge.watcher.push_reminder") as mock_push,
        ):
            push_if_new(path, state, "Homunculus")
        mock_push.assert_called_once()

    def test_proceeds_to_push_when_slow_path_raises(self, tmp_path):
        """If Reminders.app is unreachable, fall through to push attempt."""
        path = _write_md(tmp_path / "ev.md", event_id="ev-fallthrough")
        state = _make_state(tmp_path)
        with (
            patch(
                "mac_reminders_bridge.watcher.query_pushed_reminder_ids",
                side_effect=AppleScriptError("timeout"),
            ),
            patch("mac_reminders_bridge.watcher.push_reminder") as mock_push,
        ):
            push_if_new(path, state, "Homunculus")
        mock_push.assert_called_once()

    def test_proceeds_when_slow_path_raises_not_implemented(self, tmp_path):
        path = _write_md(tmp_path / "ev.md", event_id="ev-ni")
        state = _make_state(tmp_path)
        with (
            patch(
                "mac_reminders_bridge.watcher.query_pushed_reminder_ids",
                side_effect=NotImplementedError(),
            ),
            patch("mac_reminders_bridge.watcher.push_reminder") as mock_push,
        ):
            push_if_new(path, state, "Homunculus")
        mock_push.assert_called_once()


# ---------------------------------------------------------------------------
# push_if_new — push step
# ---------------------------------------------------------------------------

class TestPushIfNewPushStep:
    def test_marks_pushed_after_success(self, tmp_path):
        path = _write_md(tmp_path / "ev.md", event_id="ev-mark")
        state = _make_state(tmp_path)
        with (
            patch("mac_reminders_bridge.watcher.query_pushed_reminder_ids", return_value=[]),
            patch("mac_reminders_bridge.watcher.push_reminder"),
        ):
            push_if_new(path, state, "Homunculus")
        assert state.is_pushed("ev-mark") is True

    def test_does_not_mark_if_push_raises(self, tmp_path):
        path = _write_md(tmp_path / "ev.md", event_id="ev-fail")
        state = _make_state(tmp_path)
        with (
            patch("mac_reminders_bridge.watcher.query_pushed_reminder_ids", return_value=[]),
            patch(
                "mac_reminders_bridge.watcher.push_reminder",
                side_effect=AppleScriptError("oh no"),
            ),
        ):
            push_if_new(path, state, "Homunculus")  # should NOT raise
        assert state.is_pushed("ev-fail") is False

    def test_skips_unparseable_file(self, tmp_path):
        bad = tmp_path / "bad.md"
        bad.write_text("---\nno_id: true\n---\nbody\n", encoding="utf-8")
        state = _make_state(tmp_path)
        with patch("mac_reminders_bridge.watcher.push_reminder") as mock_push:
            push_if_new(bad, state, "Homunculus")  # should NOT raise
        mock_push.assert_not_called()

    def test_skips_missing_file(self, tmp_path):
        state = _make_state(tmp_path)
        with patch("mac_reminders_bridge.watcher.push_reminder") as mock_push:
            push_if_new(tmp_path / "gone.md", state, "Homunculus")
        mock_push.assert_not_called()


# ---------------------------------------------------------------------------
# periodic_sweep
# ---------------------------------------------------------------------------

class TestPeriodicSweep:
    def test_returns_zero_for_empty_dir(self, tmp_path):
        state = _make_state(tmp_path)
        result = periodic_sweep(tmp_path, state, "Homunculus")
        assert result == 0

    def test_returns_zero_for_nonexistent_dir(self, tmp_path):
        state = _make_state(tmp_path)
        result = periodic_sweep(tmp_path / "nope", state, "Homunculus")
        assert result == 0

    def test_pushes_new_reminders(self, tmp_path):
        _write_md(tmp_path / "ev1.md", event_id="ev-sweep-1")
        _write_md(tmp_path / "ev2.md", event_id="ev-sweep-2")
        state = _make_state(tmp_path)
        with patch("mac_reminders_bridge.watcher.push_reminder") as mock_push:
            result = periodic_sweep(tmp_path, state, "Homunculus")
        assert result == 2
        assert mock_push.call_count == 2

    def test_skips_already_pushed(self, tmp_path):
        _write_md(tmp_path / "ev.md", event_id="ev-already")
        state = _make_state(tmp_path)
        state.mark_pushed("ev-already")
        with patch("mac_reminders_bridge.watcher.push_reminder") as mock_push:
            result = periodic_sweep(tmp_path, state, "Homunculus")
        assert result == 0
        mock_push.assert_not_called()

    def test_continues_after_push_error(self, tmp_path):
        _write_md(tmp_path / "ev1.md", event_id="ev-err-1")
        _write_md(tmp_path / "ev2.md", event_id="ev-ok-2")
        state = _make_state(tmp_path)

        push_calls = []

        def mock_push(record, list_name):
            push_calls.append(record.event_id)
            if record.event_id == "ev-err-1":
                raise AppleScriptError("fail")

        with patch("mac_reminders_bridge.watcher.push_reminder", side_effect=mock_push):
            result = periodic_sweep(tmp_path, state, "Homunculus")

        # One of two should have succeeded despite the error
        assert "ev-ok-2" in push_calls or "ev-err-1" in push_calls
        # Only successful one is counted
        assert result == 1


# ---------------------------------------------------------------------------
# cold_boot_sweep
# ---------------------------------------------------------------------------

class TestColdBootSweep:
    def test_returns_zero_for_empty_dir(self, tmp_path):
        state = _make_state(tmp_path)
        result = cold_boot_sweep(tmp_path, state, "Homunculus")
        assert result == 0

    def test_returns_zero_for_nonexistent_dir(self, tmp_path):
        state = _make_state(tmp_path)
        result = cold_boot_sweep(tmp_path / "nope", state, "Homunculus")
        assert result == 0

    def test_pushes_all_untracked_on_cold_boot(self, tmp_path):
        _write_md(tmp_path / "ev1.md", event_id="cb-1")
        _write_md(tmp_path / "ev2.md", event_id="cb-2")
        _write_md(tmp_path / "ev3.md", event_id="cb-3")
        state = _make_state(tmp_path)
        with patch("mac_reminders_bridge.watcher.push_reminder") as mock_push:
            result = cold_boot_sweep(tmp_path, state, "Homunculus")
        assert result == 3
        assert mock_push.call_count == 3

    def test_does_not_re_push_known_ids(self, tmp_path):
        _write_md(tmp_path / "ev1.md", event_id="cb-known")
        state = _make_state(tmp_path)
        state.mark_pushed("cb-known")
        with patch("mac_reminders_bridge.watcher.push_reminder") as mock_push:
            result = cold_boot_sweep(tmp_path, state, "Homunculus")
        assert result == 0
        mock_push.assert_not_called()

    def test_marks_pushed_after_success(self, tmp_path):
        _write_md(tmp_path / "ev.md", event_id="cb-mark")
        state = _make_state(tmp_path)
        with patch("mac_reminders_bridge.watcher.push_reminder"):
            cold_boot_sweep(tmp_path, state, "Homunculus")
        assert state.is_pushed("cb-mark") is True


# ---------------------------------------------------------------------------
# VaultRemindersHandler
# ---------------------------------------------------------------------------

class TestVaultRemindersHandlerCreated:
    def test_on_created_md_file_triggers_push_if_new(self, tmp_path):
        state = _make_state(tmp_path)
        handler = VaultRemindersHandler(state, "Homunculus")
        path = _write_md(tmp_path / "ev.md", event_id="h-created")

        with (
            patch("mac_reminders_bridge.watcher.query_pushed_reminder_ids", return_value=[]),
            patch("mac_reminders_bridge.watcher.push_reminder") as mock_push,
        ):
            event = FileCreatedEvent(str(path))
            handler.on_created(event)
        mock_push.assert_called_once()

    def test_on_created_ignores_tmp_files(self, tmp_path):
        state = _make_state(tmp_path)
        handler = VaultRemindersHandler(state, "Homunculus")
        tmp_file = tmp_path / "ev.md.tmp.12345.0"
        tmp_file.write_text("---\nid: ev-tmp\ntitle: t\ntz: UTC\n---\n", encoding="utf-8")

        with patch("mac_reminders_bridge.watcher.push_reminder") as mock_push:
            event = FileCreatedEvent(str(tmp_file))
            handler.on_created(event)
        mock_push.assert_not_called()

    def test_on_created_ignores_directories(self, tmp_path):
        state = _make_state(tmp_path)
        handler = VaultRemindersHandler(state, "Homunculus")

        with patch("mac_reminders_bridge.watcher.push_reminder") as mock_push:
            event = FileCreatedEvent(str(tmp_path))
            event.is_directory = True
            handler.on_created(event)
        mock_push.assert_not_called()


class TestVaultRemindersHandlerMoved:
    def test_on_moved_dispatches_on_dest_md(self, tmp_path):
        state = _make_state(tmp_path)
        handler = VaultRemindersHandler(state, "Homunculus")
        dest = _write_md(tmp_path / "ev.md", event_id="h-moved")
        src = tmp_path / "ev.md.tmp.999"

        with (
            patch("mac_reminders_bridge.watcher.query_pushed_reminder_ids", return_value=[]),
            patch("mac_reminders_bridge.watcher.push_reminder") as mock_push,
        ):
            event = FileMovedEvent(str(src), str(dest))
            handler.on_moved(event)
        mock_push.assert_called_once()

    def test_on_moved_ignores_non_md_destination(self, tmp_path):
        state = _make_state(tmp_path)
        handler = VaultRemindersHandler(state, "Homunculus")
        src = tmp_path / "something.tmp"
        dest = tmp_path / "something.txt"

        with patch("mac_reminders_bridge.watcher.push_reminder") as mock_push:
            event = FileMovedEvent(str(src), str(dest))
            handler.on_moved(event)
        mock_push.assert_not_called()

    def test_on_moved_ignores_directories(self, tmp_path):
        state = _make_state(tmp_path)
        handler = VaultRemindersHandler(state, "Homunculus")

        with patch("mac_reminders_bridge.watcher.push_reminder") as mock_push:
            event = FileMovedEvent(str(tmp_path / "a"), str(tmp_path / "b"))
            event.is_directory = True
            handler.on_moved(event)
        mock_push.assert_not_called()


class TestVaultRemindersHandlerModified:
    def test_on_modified_pushes_unpushed_md(self, tmp_path):
        state = _make_state(tmp_path)
        handler = VaultRemindersHandler(state, "Homunculus")
        path = _write_md(tmp_path / "ev.md", event_id="h-modified")

        with (
            patch("mac_reminders_bridge.watcher.query_pushed_reminder_ids", return_value=[]),
            patch("mac_reminders_bridge.watcher.push_reminder") as mock_push,
        ):
            event = FileModifiedEvent(str(path))
            handler.on_modified(event)
        mock_push.assert_called_once()

    def test_on_modified_skips_already_pushed(self, tmp_path):
        state = _make_state(tmp_path)
        state.mark_pushed("h-mod-pushed")
        handler = VaultRemindersHandler(state, "Homunculus")
        path = _write_md(tmp_path / "ev.md", event_id="h-mod-pushed")

        with patch("mac_reminders_bridge.watcher.push_reminder") as mock_push:
            event = FileModifiedEvent(str(path))
            handler.on_modified(event)
        mock_push.assert_not_called()

    def test_on_modified_ignores_non_md(self, tmp_path):
        state = _make_state(tmp_path)
        handler = VaultRemindersHandler(state, "Homunculus")
        txt = tmp_path / "note.txt"
        txt.write_text("hello", encoding="utf-8")

        with patch("mac_reminders_bridge.watcher.push_reminder") as mock_push:
            event = FileModifiedEvent(str(txt))
            handler.on_modified(event)
        mock_push.assert_not_called()
