"""
test_watcher.py — Tests for watcher.py.

Tests the cold_boot_sweep, push_if_new, and VaultCalendarHandler.
AppleScript calls are fully mocked; no real Calendar.app interaction.
"""

from __future__ import annotations

import textwrap
from pathlib import Path
from unittest.mock import MagicMock, call, patch

import pytest

from mac_calendar_bridge.state import PushedState
from mac_calendar_bridge.vault_reader import EventRecord, VaultReaderError
from mac_calendar_bridge.watcher import VaultCalendarHandler, cold_boot_sweep, push_if_new


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

MEETING_MD = textwrap.dedent("""\
    ---
    id: 2026-09-15-meeting-with-myself
    title: meeting with myself
    starts_at: '2026-09-15T09:00:00-04:00'
    ends_at: '2026-09-15T09:30:00-04:00'
    tz: America/New_York
    duration_minutes: 30
    people: []
    tags: []
    source: voice
    created_at: '2026-09-13T17:53:46.985075-04:00'
    updated_at: '2026-09-13T17:53:46.985075-04:00'
    ---
    # meeting with myself
""")

CODE_REVIEW_MD = textwrap.dedent("""\
    ---
    id: 2026-09-18-code-review-with-myself
    title: code review with myself
    starts_at: '2026-09-18T10:00:00-04:00'
    ends_at: '2026-09-18T10:30:00-04:00'
    tz: America/New_York
    duration_minutes: 30
    people: []
    tags: []
    source: voice
    created_at: '2026-09-14T15:13:34.171898-04:00'
    updated_at: '2026-09-14T15:13:34.171898-04:00'
    ---
    # code review with myself
""")


def write_md(directory: Path, filename: str, content: str) -> Path:
    p = directory / filename
    p.write_text(content, encoding="utf-8")
    return p


# ---------------------------------------------------------------------------
# Tests: push_if_new
# ---------------------------------------------------------------------------

class TestPushIfNew:
    def test_pushes_unpushed_event(self, tmp_path):
        p = write_md(tmp_path, "event.md", MEETING_MD)
        state = PushedState(tmp_path / "state.jsonl")

        with patch("mac_calendar_bridge.watcher.push_event") as mock_push:
            push_if_new(p, state, "Homunculus")

        mock_push.assert_called_once()
        assert state.is_pushed("2026-09-15-meeting-with-myself")

    def test_skips_already_pushed(self, tmp_path):
        p = write_md(tmp_path, "event.md", MEETING_MD)
        state = PushedState(tmp_path / "state.jsonl")
        state.mark_pushed("2026-09-15-meeting-with-myself")

        with patch("mac_calendar_bridge.watcher.push_event") as mock_push:
            push_if_new(p, state, "Homunculus")

        mock_push.assert_not_called()

    def test_ignores_non_md_file(self, tmp_path):
        txt_file = tmp_path / "notes.txt"
        txt_file.write_text("not an event")
        state = PushedState(tmp_path / "state.jsonl")

        with patch("mac_calendar_bridge.watcher.push_event") as mock_push:
            push_if_new(txt_file, state, "Homunculus")

        mock_push.assert_not_called()

    def test_handles_parse_error_gracefully(self, tmp_path):
        p = write_md(tmp_path, "bad.md", "---\ntitle: broken\n---\n")
        state = PushedState(tmp_path / "state.jsonl")

        with patch("mac_calendar_bridge.watcher.push_event") as mock_push:
            push_if_new(p, state, "Homunculus")  # should not raise

        mock_push.assert_not_called()

    def test_handles_missing_file_gracefully(self, tmp_path):
        missing = tmp_path / "gone.md"
        state = PushedState(tmp_path / "state.jsonl")

        with patch("mac_calendar_bridge.watcher.push_event") as mock_push:
            push_if_new(missing, state, "Homunculus")  # should not raise

        mock_push.assert_not_called()

    def test_does_not_mark_pushed_on_applescript_error(self, tmp_path):
        from mac_calendar_bridge.applescript import AppleScriptError
        p = write_md(tmp_path, "event.md", MEETING_MD)
        state = PushedState(tmp_path / "state.jsonl")

        with patch(
            "mac_calendar_bridge.watcher.push_event",
            side_effect=AppleScriptError("denied"),
        ):
            push_if_new(p, state, "Homunculus")

        assert not state.is_pushed("2026-09-15-meeting-with-myself")

    def test_marks_pushed_on_success(self, tmp_path):
        p = write_md(tmp_path, "event.md", MEETING_MD)
        state = PushedState(tmp_path / "state.jsonl")

        with patch("mac_calendar_bridge.watcher.push_event"):
            push_if_new(p, state, "Homunculus")

        assert state.is_pushed("2026-09-15-meeting-with-myself")

    def test_passes_calendar_name_to_push_event(self, tmp_path):
        p = write_md(tmp_path, "event.md", MEETING_MD)
        state = PushedState(tmp_path / "state.jsonl")

        with patch("mac_calendar_bridge.watcher.push_event") as mock_push:
            push_if_new(p, state, "MyCustomCalendar")

        _, kwargs_positional = mock_push.call_args[0], mock_push.call_args[0]
        assert mock_push.call_args[0][1] == "MyCustomCalendar"


# ---------------------------------------------------------------------------
# Tests: cold_boot_sweep
# ---------------------------------------------------------------------------

class TestColdBootSweep:
    def test_pushes_both_existing_events(self, tmp_path):
        """Backfills the Sep 15 + Sep 18 events on first run."""
        cal_dir = tmp_path / "calendar" / "2026-09"
        cal_dir.mkdir(parents=True)
        write_md(cal_dir, "2026-09-15-meeting-with-myself.md", MEETING_MD)
        write_md(cal_dir, "2026-09-18-code-review-with-myself.md", CODE_REVIEW_MD)

        state = PushedState(tmp_path / "state.jsonl")

        with patch("mac_calendar_bridge.watcher.push_event") as mock_push:
            count = cold_boot_sweep(tmp_path / "calendar", state, "Homunculus")

        assert count == 2
        assert mock_push.call_count == 2
        assert state.is_pushed("2026-09-15-meeting-with-myself")
        assert state.is_pushed("2026-09-18-code-review-with-myself")

    def test_skips_already_pushed(self, tmp_path):
        cal_dir = tmp_path / "calendar"
        cal_dir.mkdir()
        write_md(cal_dir, "event.md", MEETING_MD)
        state = PushedState(tmp_path / "state.jsonl")
        state.mark_pushed("2026-09-15-meeting-with-myself")

        with patch("mac_calendar_bridge.watcher.push_event") as mock_push:
            count = cold_boot_sweep(cal_dir, state, "Homunculus")

        assert count == 0
        mock_push.assert_not_called()

    def test_returns_zero_on_empty_dir(self, tmp_path):
        cal_dir = tmp_path / "calendar"
        cal_dir.mkdir()
        state = PushedState(tmp_path / "state.jsonl")

        with patch("mac_calendar_bridge.watcher.push_event"):
            count = cold_boot_sweep(cal_dir, state, "Homunculus")

        assert count == 0

    def test_returns_zero_on_missing_dir(self, tmp_path):
        state = PushedState(tmp_path / "state.jsonl")
        with patch("mac_calendar_bridge.watcher.push_event"):
            count = cold_boot_sweep(tmp_path / "nonexistent", state, "Homunculus")
        assert count == 0

    def test_partial_push_on_applescript_error(self, tmp_path):
        """If one push fails, the other still proceeds."""
        from mac_calendar_bridge.applescript import AppleScriptError
        cal_dir = tmp_path / "calendar"
        cal_dir.mkdir()
        write_md(cal_dir, "2026-09-15-meeting-with-myself.md", MEETING_MD)
        write_md(cal_dir, "2026-09-18-code-review-with-myself.md", CODE_REVIEW_MD)

        state = PushedState(tmp_path / "state.jsonl")
        calls = []

        def side_effect(event, cal_name, **kwargs):
            calls.append(event.event_id)
            if event.event_id == "2026-09-15-meeting-with-myself":
                raise AppleScriptError("permission denied")

        with patch("mac_calendar_bridge.watcher.push_event", side_effect=side_effect):
            count = cold_boot_sweep(cal_dir, state, "Homunculus")

        # Only the successful one is marked
        assert count == 1
        assert state.is_pushed("2026-09-18-code-review-with-myself")
        assert not state.is_pushed("2026-09-15-meeting-with-myself")

    def test_handles_bad_md_files_in_sweep(self, tmp_path):
        cal_dir = tmp_path / "calendar"
        cal_dir.mkdir()
        write_md(cal_dir, "good.md", MEETING_MD)
        write_md(cal_dir, "bad.md", "---\ntitle: broken\n---\n")

        state = PushedState(tmp_path / "state.jsonl")
        with patch("mac_calendar_bridge.watcher.push_event") as mock_push:
            count = cold_boot_sweep(cal_dir, state, "Homunculus")

        assert count == 1

    def test_idempotent_on_second_run(self, tmp_path):
        cal_dir = tmp_path / "calendar"
        cal_dir.mkdir()
        write_md(cal_dir, "event.md", MEETING_MD)
        state = PushedState(tmp_path / "state.jsonl")

        with patch("mac_calendar_bridge.watcher.push_event") as mock_push:
            count1 = cold_boot_sweep(cal_dir, state, "Homunculus")
            count2 = cold_boot_sweep(cal_dir, state, "Homunculus")

        assert count1 == 1
        assert count2 == 0
        assert mock_push.call_count == 1


# ---------------------------------------------------------------------------
# Tests: VaultCalendarHandler
# ---------------------------------------------------------------------------

class TestVaultCalendarHandler:
    def _make_handler(self, tmp_path: Path):
        state = PushedState(tmp_path / "state.jsonl")
        return VaultCalendarHandler(state, "Homunculus"), state

    def test_on_created_pushes_new_event(self, tmp_path):
        handler, state = self._make_handler(tmp_path)
        p = write_md(tmp_path, "event.md", MEETING_MD)

        from watchdog.events import FileCreatedEvent
        event = FileCreatedEvent(str(p))

        with patch("mac_calendar_bridge.watcher.push_event") as mock_push:
            handler.on_created(event)

        mock_push.assert_called_once()
        assert state.is_pushed("2026-09-15-meeting-with-myself")

    def test_on_created_skips_directories(self, tmp_path):
        handler, state = self._make_handler(tmp_path)
        new_dir = tmp_path / "subdir"
        new_dir.mkdir()

        from watchdog.events import FileCreatedEvent
        event = FileCreatedEvent(str(new_dir))
        event.is_directory = True

        with patch("mac_calendar_bridge.watcher.push_event") as mock_push:
            handler.on_created(event)

        mock_push.assert_not_called()

    def test_on_modified_skips_already_pushed(self, tmp_path):
        handler, state = self._make_handler(tmp_path)
        p = write_md(tmp_path, "event.md", MEETING_MD)
        state.mark_pushed("2026-09-15-meeting-with-myself")

        from watchdog.events import FileModifiedEvent
        event = FileModifiedEvent(str(p))

        with patch("mac_calendar_bridge.watcher.push_event") as mock_push:
            handler.on_modified(event)

        mock_push.assert_not_called()

    def test_on_modified_pushes_if_not_yet_pushed(self, tmp_path):
        handler, state = self._make_handler(tmp_path)
        p = write_md(tmp_path, "event.md", MEETING_MD)

        from watchdog.events import FileModifiedEvent
        event = FileModifiedEvent(str(p))

        with patch("mac_calendar_bridge.watcher.push_event") as mock_push:
            handler.on_modified(event)

        mock_push.assert_called_once()

    def test_on_modified_ignores_directories(self, tmp_path):
        handler, state = self._make_handler(tmp_path)

        from watchdog.events import FileModifiedEvent
        event = FileModifiedEvent(str(tmp_path))
        event.is_directory = True

        with patch("mac_calendar_bridge.watcher.push_event") as mock_push:
            handler.on_modified(event)

        mock_push.assert_not_called()

    def test_on_modified_ignores_non_md(self, tmp_path):
        handler, state = self._make_handler(tmp_path)
        txt = tmp_path / "notes.txt"
        txt.write_text("not an event")

        from watchdog.events import FileModifiedEvent
        event = FileModifiedEvent(str(txt))

        with patch("mac_calendar_bridge.watcher.push_event") as mock_push:
            handler.on_modified(event)

        mock_push.assert_not_called()

    def test_second_created_event_is_idempotent(self, tmp_path):
        """File-system watchers can fire multiple times. Should only push once."""
        handler, state = self._make_handler(tmp_path)
        p = write_md(tmp_path, "event.md", MEETING_MD)

        from watchdog.events import FileCreatedEvent
        event = FileCreatedEvent(str(p))

        with patch("mac_calendar_bridge.watcher.push_event") as mock_push:
            handler.on_created(event)
            handler.on_created(event)

        assert mock_push.call_count == 1
