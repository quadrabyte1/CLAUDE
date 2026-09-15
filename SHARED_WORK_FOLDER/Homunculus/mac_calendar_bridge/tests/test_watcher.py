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


# ---------------------------------------------------------------------------
# v0.1.3 TDD: atomic-rename (MOVE) events, tmp-file guard, periodic sweep
# ---------------------------------------------------------------------------

SECOND_MEETING_MD = textwrap.dedent("""\
    ---
    id: 2026-09-15-second-meeting-with-myself
    title: second meeting with myself
    starts_at: '2026-09-15T16:53:14-04:00'
    ends_at: '2026-09-15T17:23:14-04:00'
    tz: America/New_York
    duration_minutes: 30
    people: []
    tags: []
    source: voice
    created_at: '2026-09-14T16:53:14.000000-04:00'
    updated_at: '2026-09-14T16:53:14.000000-04:00'
    ---
    # second meeting with myself
""")


class TestAtomicRenameAndSweep:
    """v0.1.3 regression suite: MOVE events, tmp-file guard, periodic sweep."""

    def _make_handler(self, tmp_path: Path):
        state = PushedState(tmp_path / "state.jsonl")
        return VaultCalendarHandler(state, "Homunculus"), state

    # ------------------------------------------------------------------
    # TDD-1: on_moved with .md destination → dispatches push_if_new
    # ------------------------------------------------------------------

    def test_on_moved_md_destination_dispatches(self, tmp_path):
        """Watchdog MOVE event to a .md destination must trigger push_if_new.

        Herman writes atomically: <file>.tmp.PID.N → os.replace → <file>.md.
        Watchdog sees a MOVE event with dest_path = <file>.md.
        Before v0.1.3, on_moved was not handled → silent loss.
        """
        from watchdog.events import FileMovedEvent
        handler, state = self._make_handler(tmp_path)

        # The .md is already on disk (rename has completed by the time we handle).
        final_path = write_md(tmp_path, "2026-09-15-second-meeting-with-myself.md", SECOND_MEETING_MD)
        tmp_src = str(tmp_path / "2026-09-15-second-meeting-with-myself.md.tmp.4010.2")

        event = FileMovedEvent(src_path=tmp_src, dest_path=str(final_path))

        with patch("mac_calendar_bridge.watcher.push_event") as mock_push:
            handler.on_moved(event)

        mock_push.assert_called_once()
        assert state.is_pushed("2026-09-15-second-meeting-with-myself")

    def test_on_moved_non_md_destination_ignored(self, tmp_path):
        """MOVE events whose destination is NOT a .md must be ignored."""
        from watchdog.events import FileMovedEvent
        handler, state = self._make_handler(tmp_path)

        event = FileMovedEvent(
            src_path=str(tmp_path / "notes.txt.tmp"),
            dest_path=str(tmp_path / "notes.txt"),
        )

        with patch("mac_calendar_bridge.watcher.push_event") as mock_push:
            handler.on_moved(event)

        mock_push.assert_not_called()

    def test_on_moved_directory_ignored(self, tmp_path):
        """Directory MOVE events must be ignored."""
        from watchdog.events import FileMovedEvent, DirMovedEvent
        handler, state = self._make_handler(tmp_path)

        # DirMovedEvent marks is_directory=True
        event = DirMovedEvent(
            src_path=str(tmp_path / "old_dir"),
            dest_path=str(tmp_path / "new_dir"),
        )

        with patch("mac_calendar_bridge.watcher.push_event") as mock_push:
            handler.on_moved(event)

        mock_push.assert_not_called()

    # ------------------------------------------------------------------
    # TDD-2: .tmp CREATE events → logged at DEBUG, NOT dispatched
    # ------------------------------------------------------------------

    def test_on_created_tmp_file_not_dispatched(self, tmp_path, caplog):
        """A .tmp file creation must be skipped (logged at DEBUG, not pushed).

        Regression guard: ensures the silence is replaced with explicit logging.
        """
        import logging
        handler, state = self._make_handler(tmp_path)

        tmp_file = tmp_path / "2026-09-15-second-meeting-with-myself.md.tmp.4010.2"
        tmp_file.write_bytes(b"not an md yet")

        from watchdog.events import FileCreatedEvent
        event = FileCreatedEvent(str(tmp_file))

        with caplog.at_level(logging.DEBUG, logger="mac_calendar_bridge.watcher"):
            with patch("mac_calendar_bridge.watcher.push_event") as mock_push:
                handler.on_created(event)

        mock_push.assert_not_called()
        # Must log the skip — not fall through silently.
        assert any("skipping temp file" in r.message.lower() for r in caplog.records)

    # ------------------------------------------------------------------
    # TDD-3: periodic sweep — finds unpushed .md, calls push_if_new
    # ------------------------------------------------------------------

    def test_periodic_sweep_pushes_missed_event(self, tmp_path):
        """Vault has a .md with no entry in pushed.jsonl → sweep dispatches it.

        Simulates the safety net: watchdog missed the MOVE event (e.g. bug,
        dropped inotify), but the 60-second sweep catches it.
        """
        from mac_calendar_bridge.watcher import periodic_sweep

        cal_dir = tmp_path / "calendar"
        cal_dir.mkdir(parents=True)
        write_md(cal_dir, "2026-09-15-second-meeting-with-myself.md", SECOND_MEETING_MD)

        state = PushedState(tmp_path / "state.jsonl")

        with patch("mac_calendar_bridge.watcher.push_event") as mock_push:
            count = periodic_sweep(cal_dir, state, "Homunculus")

        assert count == 1
        mock_push.assert_called_once()
        assert state.is_pushed("2026-09-15-second-meeting-with-myself")

    def test_periodic_sweep_skips_already_pushed(self, tmp_path):
        """Periodic sweep must not re-push events already in pushed.jsonl."""
        from mac_calendar_bridge.watcher import periodic_sweep

        cal_dir = tmp_path / "calendar"
        cal_dir.mkdir()
        write_md(cal_dir, "event.md", SECOND_MEETING_MD)

        state = PushedState(tmp_path / "state.jsonl")
        state.mark_pushed("2026-09-15-second-meeting-with-myself")

        with patch("mac_calendar_bridge.watcher.push_event") as mock_push:
            count = periodic_sweep(cal_dir, state, "Homunculus")

        assert count == 0
        mock_push.assert_not_called()

    def test_periodic_sweep_returns_zero_on_empty_vault(self, tmp_path):
        """Empty vault → sweep returns 0 without error."""
        from mac_calendar_bridge.watcher import periodic_sweep

        cal_dir = tmp_path / "calendar"
        cal_dir.mkdir()
        state = PushedState(tmp_path / "state.jsonl")

        with patch("mac_calendar_bridge.watcher.push_event"):
            count = periodic_sweep(cal_dir, state, "Homunculus")

        assert count == 0


# ---------------------------------------------------------------------------
# v0.1.5 TDD Bug 1: belt-and-suspenders dup-prevention wired into push_if_new
# ---------------------------------------------------------------------------

class TestPushIfNewBeltAndSuspenders:
    """Bug 1 regression suite: query_pushed_event_ids() must be called as the
    slow-but-authoritative second idempotency check in push_if_new() when the
    fast-path (pushed.jsonl) says the event hasn't been pushed.

    Scenario that prompted the bug: Thomas wiped pushed.jsonl during v0.1.4
    migration.  Bridge cold-booted, state.is_pushed() returned False for every
    event, and all 5 events got re-pushed → duplicates in Calendar.

    Fix contract:
      1. Fast path (pushed.jsonl) — if found, skip, done.
      2. Slow path (query_pushed_event_ids) — if found in Calendar, self-heal
         pushed.jsonl, skip (no push call).
      3. Only if BOTH say "not present" → push, then mark in pushed.jsonl.
    """

    def test_bug1_calendar_already_has_event_no_push_when_jsonl_wiped(self, tmp_path):
        """FAILING (pre-fix): pushed.jsonl is empty, Calendar already has the
        event → push_if_new must NOT re-push it.

        query_pushed_event_ids must be called and its result must block the push.
        """
        p = write_md(tmp_path, "event.md", CODE_REVIEW_MD)
        # pushed.jsonl is empty (wiped)
        state = PushedState(tmp_path / "state.jsonl")
        assert not state.is_pushed("2026-09-18-code-review-with-myself")

        # Calendar.app already has this event — query returns the event_id
        with patch(
            "mac_calendar_bridge.watcher.query_pushed_event_ids",
            return_value=["2026-09-18-code-review-with-myself"],
        ) as mock_query, patch(
            "mac_calendar_bridge.watcher.push_event",
        ) as mock_push:
            push_if_new(p, state, "Homunculus")

        # Must NOT push — event already in Calendar
        mock_push.assert_not_called()
        # query_pushed_event_ids must have been called
        mock_query.assert_called_once()

    def test_bug1_self_heal_writes_to_jsonl_when_found_in_calendar(self, tmp_path):
        """FAILING (pre-fix): when Calendar.app has the event but pushed.jsonl
        doesn't, push_if_new must self-heal by writing the event_id to
        pushed.jsonl so future fast-path checks work.
        """
        p = write_md(tmp_path, "event.md", CODE_REVIEW_MD)
        state = PushedState(tmp_path / "state.jsonl")

        with patch(
            "mac_calendar_bridge.watcher.query_pushed_event_ids",
            return_value=["2026-09-18-code-review-with-myself"],
        ), patch("mac_calendar_bridge.watcher.push_event"):
            push_if_new(p, state, "Homunculus")

        # Self-heal: event_id must now be in the in-memory state
        assert state.is_pushed("2026-09-18-code-review-with-myself")

    def test_bug1_self_heal_message_logged(self, tmp_path, caplog):
        """FAILING (pre-fix): self-heal must log a recognisable message so
        Thomas can confirm the heal in the log after migration.
        """
        import logging
        p = write_md(tmp_path, "event.md", CODE_REVIEW_MD)
        state = PushedState(tmp_path / "state.jsonl")

        with caplog.at_level(logging.INFO, logger="mac_calendar_bridge.watcher"):
            with patch(
                "mac_calendar_bridge.watcher.query_pushed_event_ids",
                return_value=["2026-09-18-code-review-with-myself"],
            ), patch("mac_calendar_bridge.watcher.push_event"):
                push_if_new(p, state, "Homunculus")

        assert any(
            "self-heal" in r.message.lower() or "self_heal" in r.message.lower()
            for r in caplog.records
        ), f"No self-heal log found. Records: {[r.message for r in caplog.records]}"

    def test_bug1_normal_push_path_still_works(self, tmp_path):
        """Regression: event is not in pushed.jsonl AND not in Calendar →
        push_event must be called exactly once.
        """
        p = write_md(tmp_path, "event.md", CODE_REVIEW_MD)
        state = PushedState(tmp_path / "state.jsonl")

        with patch(
            "mac_calendar_bridge.watcher.query_pushed_event_ids",
            return_value=[],  # Calendar says not present
        ) as mock_query, patch(
            "mac_calendar_bridge.watcher.push_event",
        ) as mock_push:
            push_if_new(p, state, "Homunculus")

        mock_push.assert_called_once()
        assert state.is_pushed("2026-09-18-code-review-with-myself")
        mock_query.assert_called_once()

    def test_bug1_query_not_called_when_fast_path_hits(self, tmp_path):
        """Optimization: if fast-path says already-pushed, query_pushed_event_ids
        must NOT be called (it's expensive — involves a Calendar.app round-trip).
        """
        p = write_md(tmp_path, "event.md", CODE_REVIEW_MD)
        state = PushedState(tmp_path / "state.jsonl")
        state.mark_pushed("2026-09-18-code-review-with-myself")

        with patch(
            "mac_calendar_bridge.watcher.query_pushed_event_ids",
        ) as mock_query, patch(
            "mac_calendar_bridge.watcher.push_event",
        ) as mock_push:
            push_if_new(p, state, "Homunculus")

        mock_push.assert_not_called()
        mock_query.assert_not_called()

    def test_bug1_query_date_str_is_midnight_on_event_date(self, tmp_path):
        """The date_str passed to query_pushed_event_ids must be midnight on
        the event's local date so the AppleScript window covers the full day.
        """
        p = write_md(tmp_path, "event.md", CODE_REVIEW_MD)
        state = PushedState(tmp_path / "state.jsonl")

        with patch(
            "mac_calendar_bridge.watcher.query_pushed_event_ids",
            return_value=[],
        ) as mock_query, patch("mac_calendar_bridge.watcher.push_event"):
            push_if_new(p, state, "Homunculus")

        call_args = mock_query.call_args
        date_str = call_args[0][1]  # second positional arg
        # Sep 18 2026 is a Friday; midnight should be in the string
        assert "September 18, 2026" in date_str
        assert "12:00 AM" in date_str
