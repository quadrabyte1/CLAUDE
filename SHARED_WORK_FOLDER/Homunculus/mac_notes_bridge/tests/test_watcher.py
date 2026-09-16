"""
test_watcher.py — Tests for watcher.py.

Tests the cold_boot_sweep, push_if_new, periodic_sweep, and VaultNotesHandler.
All AppleScript calls are fully mocked; no real Notes.app interaction.
"""

from __future__ import annotations

import logging
import textwrap
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from mac_notes_bridge.applescript import AppleScriptError
from mac_notes_bridge.state import PushedState
from mac_notes_bridge.vault_reader import NoteRecord, VaultReaderError
from mac_notes_bridge.watcher import (
    VaultNotesHandler,
    cold_boot_sweep,
    periodic_sweep,
    push_if_new,
)


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

TEST_NOTE_MD = textwrap.dedent("""\
    ---
    id: 2026-09-15-test-notes-mechanism
    title: test notes mechanism
    captured_at: '2026-09-15T22:38:55.659511+00:00'
    source: sprite
    audio_path: /Users/fourierflight/sprite/audio/2026/09/2f68955efbe092cc3647e35d763f78ce.m4a
    confidence: 0.85
    ---

    # test notes mechanism

    *Captured 2026-09-15 22:38 UTC via Sprite.*

    Take a note. We have to test that the notes mechanism works like it's supposed to.
""")

MECHANISM_NOTE_MD = textwrap.dedent("""\
    ---
    id: 2026-09-15-mechanism-to-close-the-loop-between-phone-and-mac
    title: mechanism to close the loop between phone and Mac
    captured_at: '2026-09-15T23:06:27.657772+00:00'
    source: sprite
    audio_path: /Users/fourierflight/sprite/audio/2026/09/1553dfc249048c691ac8ce070bd2edd8.m4a
    confidence: 0.85
    ---

    # mechanism to close the loop between phone and Mac

    *Captured 2026-09-15 23:06 UTC via Sprite.*

    Maybe a mechanism to close the loop between the phone and the Mac.
""")

SECOND_NOTE_MD = textwrap.dedent("""\
    ---
    id: 2026-09-15-a-way
    title: a way
    captured_at: '2026-09-15T23:04:54.394151+00:00'
    source: sprite
    audio_path: /Users/fourierflight/sprite/audio/2026/09/ae0a7042ae646fb5d25f7da165cda928.m4a
    confidence: 0.7296503375
    ---

    # a way

    *Captured 2026-09-15 23:04 UTC via Sprite.*

    Take a note I thought maybe a way
""")


def write_md(directory: Path, filename: str, content: str) -> Path:
    p = directory / filename
    p.write_text(content, encoding="utf-8")
    return p


# ---------------------------------------------------------------------------
# Tests: push_if_new
# ---------------------------------------------------------------------------

class TestPushIfNew:
    def test_pushes_unpushed_note(self, tmp_path):
        p = write_md(tmp_path, "note.md", TEST_NOTE_MD)
        state = PushedState(tmp_path / "state.jsonl")

        with patch("mac_notes_bridge.watcher.push_note") as mock_push, \
             patch("mac_notes_bridge.watcher.query_pushed_note_ids", return_value=[]):
            push_if_new(p, state, "Homunculus", "iCloud")

        mock_push.assert_called_once()
        assert state.is_pushed("2026-09-15-test-notes-mechanism")

    def test_skips_already_pushed_fast_path(self, tmp_path):
        p = write_md(tmp_path, "note.md", TEST_NOTE_MD)
        state = PushedState(tmp_path / "state.jsonl")
        state.mark_pushed("2026-09-15-test-notes-mechanism")

        with patch("mac_notes_bridge.watcher.push_note") as mock_push, \
             patch("mac_notes_bridge.watcher.query_pushed_note_ids") as mock_query:
            push_if_new(p, state, "Homunculus", "iCloud")

        mock_push.assert_not_called()
        # query must NOT be called when fast path hits
        mock_query.assert_not_called()

    def test_ignores_non_md_file(self, tmp_path):
        txt_file = tmp_path / "notes.txt"
        txt_file.write_text("not a note")
        state = PushedState(tmp_path / "state.jsonl")

        with patch("mac_notes_bridge.watcher.push_note") as mock_push, \
             patch("mac_notes_bridge.watcher.query_pushed_note_ids", return_value=[]):
            push_if_new(txt_file, state, "Homunculus", "iCloud")

        mock_push.assert_not_called()

    def test_handles_parse_error_gracefully(self, tmp_path):
        p = write_md(tmp_path, "bad.md", "---\ntitle: broken\n---\n")
        state = PushedState(tmp_path / "state.jsonl")

        with patch("mac_notes_bridge.watcher.push_note") as mock_push, \
             patch("mac_notes_bridge.watcher.query_pushed_note_ids", return_value=[]):
            push_if_new(p, state, "Homunculus", "iCloud")  # should not raise

        mock_push.assert_not_called()

    def test_handles_missing_file_gracefully(self, tmp_path):
        missing = tmp_path / "gone.md"
        state = PushedState(tmp_path / "state.jsonl")

        with patch("mac_notes_bridge.watcher.push_note") as mock_push, \
             patch("mac_notes_bridge.watcher.query_pushed_note_ids", return_value=[]):
            push_if_new(missing, state, "Homunculus", "iCloud")  # should not raise

        mock_push.assert_not_called()

    def test_does_not_mark_pushed_on_applescript_error(self, tmp_path):
        p = write_md(tmp_path, "note.md", TEST_NOTE_MD)
        state = PushedState(tmp_path / "state.jsonl")

        with patch(
            "mac_notes_bridge.watcher.push_note",
            side_effect=AppleScriptError("denied"),
        ), patch("mac_notes_bridge.watcher.query_pushed_note_ids", return_value=[]):
            push_if_new(p, state, "Homunculus", "iCloud")

        assert not state.is_pushed("2026-09-15-test-notes-mechanism")

    def test_marks_pushed_on_success(self, tmp_path):
        p = write_md(tmp_path, "note.md", TEST_NOTE_MD)
        state = PushedState(tmp_path / "state.jsonl")

        with patch("mac_notes_bridge.watcher.push_note"), \
             patch("mac_notes_bridge.watcher.query_pushed_note_ids", return_value=[]):
            push_if_new(p, state, "Homunculus", "iCloud")

        assert state.is_pushed("2026-09-15-test-notes-mechanism")

    def test_passes_folder_name_to_push_note(self, tmp_path):
        p = write_md(tmp_path, "note.md", TEST_NOTE_MD)
        state = PushedState(tmp_path / "state.jsonl")

        with patch("mac_notes_bridge.watcher.push_note") as mock_push, \
             patch("mac_notes_bridge.watcher.query_pushed_note_ids", return_value=[]):
            push_if_new(p, state, "MyCustomFolder", "iCloud")

        assert mock_push.call_args[0][1] == "MyCustomFolder"

    def test_passes_account_name_to_push_note(self, tmp_path):
        p = write_md(tmp_path, "note.md", TEST_NOTE_MD)
        state = PushedState(tmp_path / "state.jsonl")

        with patch("mac_notes_bridge.watcher.push_note") as mock_push, \
             patch("mac_notes_bridge.watcher.query_pushed_note_ids", return_value=[]):
            push_if_new(p, state, "Homunculus", "Work")

        assert mock_push.call_args[0][2] == "Work"


# ---------------------------------------------------------------------------
# Tests: push_if_new — belt-and-suspenders idempotency (slow path)
# ---------------------------------------------------------------------------

class TestPushIfNewBeltAndSuspenders:
    """The slow-path Notes.app query prevents re-pushing when pushed.jsonl is wiped."""

    def test_notes_already_has_title_no_push_when_jsonl_wiped(self, tmp_path):
        """pushed.jsonl is empty; Notes.app already has the note → must NOT re-push."""
        p = write_md(tmp_path, "note.md", TEST_NOTE_MD)
        state = PushedState(tmp_path / "state.jsonl")
        assert not state.is_pushed("2026-09-15-test-notes-mechanism")

        with patch(
            "mac_notes_bridge.watcher.query_pushed_note_ids",
            return_value=["test notes mechanism"],  # title matches
        ) as mock_query, patch(
            "mac_notes_bridge.watcher.push_note",
        ) as mock_push:
            push_if_new(p, state, "Homunculus", "iCloud")

        mock_push.assert_not_called()
        mock_query.assert_called_once()

    def test_self_heal_writes_to_jsonl_when_found_in_notes(self, tmp_path):
        """When Notes.app has the note but pushed.jsonl doesn't, self-heal."""
        p = write_md(tmp_path, "note.md", TEST_NOTE_MD)
        state = PushedState(tmp_path / "state.jsonl")

        with patch(
            "mac_notes_bridge.watcher.query_pushed_note_ids",
            return_value=["test notes mechanism"],
        ), patch("mac_notes_bridge.watcher.push_note"):
            push_if_new(p, state, "Homunculus", "iCloud")

        assert state.is_pushed("2026-09-15-test-notes-mechanism")

    def test_self_heal_message_logged(self, tmp_path, caplog):
        """Self-heal must log a recognisable message."""
        p = write_md(tmp_path, "note.md", TEST_NOTE_MD)
        state = PushedState(tmp_path / "state.jsonl")

        with caplog.at_level(logging.INFO, logger="mac_notes_bridge.watcher"):
            with patch(
                "mac_notes_bridge.watcher.query_pushed_note_ids",
                return_value=["test notes mechanism"],
            ), patch("mac_notes_bridge.watcher.push_note"):
                push_if_new(p, state, "Homunculus", "iCloud")

        assert any(
            "self-heal" in r.message.lower() or "self_heal" in r.message.lower()
            for r in caplog.records
        ), f"No self-heal log. Records: {[r.message for r in caplog.records]}"

    def test_normal_push_path_when_not_in_notes(self, tmp_path):
        """Not in pushed.jsonl AND not in Notes.app → push must be called."""
        p = write_md(tmp_path, "note.md", TEST_NOTE_MD)
        state = PushedState(tmp_path / "state.jsonl")

        with patch(
            "mac_notes_bridge.watcher.query_pushed_note_ids",
            return_value=[],
        ) as mock_query, patch(
            "mac_notes_bridge.watcher.push_note",
        ) as mock_push:
            push_if_new(p, state, "Homunculus", "iCloud")

        mock_push.assert_called_once()
        assert state.is_pushed("2026-09-15-test-notes-mechanism")
        mock_query.assert_called_once()

    def test_query_not_called_when_fast_path_hits(self, tmp_path):
        """If fast-path says already-pushed, query_pushed_note_ids must NOT be called."""
        p = write_md(tmp_path, "note.md", TEST_NOTE_MD)
        state = PushedState(tmp_path / "state.jsonl")
        state.mark_pushed("2026-09-15-test-notes-mechanism")

        with patch(
            "mac_notes_bridge.watcher.query_pushed_note_ids",
        ) as mock_query, patch(
            "mac_notes_bridge.watcher.push_note",
        ) as mock_push:
            push_if_new(p, state, "Homunculus", "iCloud")

        mock_push.assert_not_called()
        mock_query.assert_not_called()

    def test_title_mismatch_does_not_self_heal(self, tmp_path):
        """If Notes.app has a different title, don't self-heal — push the note."""
        p = write_md(tmp_path, "note.md", TEST_NOTE_MD)
        state = PushedState(tmp_path / "state.jsonl")

        with patch(
            "mac_notes_bridge.watcher.query_pushed_note_ids",
            return_value=["some other note"],
        ), patch("mac_notes_bridge.watcher.push_note") as mock_push:
            push_if_new(p, state, "Homunculus", "iCloud")

        mock_push.assert_called_once()

    def test_notes_applescript_error_does_not_block_push(self, tmp_path):
        """If the Notes.app slow-path query fails, proceed to push anyway."""
        p = write_md(tmp_path, "note.md", TEST_NOTE_MD)
        state = PushedState(tmp_path / "state.jsonl")

        with patch(
            "mac_notes_bridge.watcher.query_pushed_note_ids",
            side_effect=AppleScriptError("Notes.app unavailable"),
        ), patch("mac_notes_bridge.watcher.push_note") as mock_push:
            push_if_new(p, state, "Homunculus", "iCloud")

        mock_push.assert_called_once()


# ---------------------------------------------------------------------------
# Tests: cold_boot_sweep
# ---------------------------------------------------------------------------

class TestColdBootSweep:
    def test_pushes_all_vault_notes(self, tmp_path):
        notes_dir = tmp_path / "notes"
        notes_dir.mkdir()
        write_md(notes_dir, "2026-09-15-test-notes-mechanism.md", TEST_NOTE_MD)
        write_md(notes_dir, "2026-09-15-mechanism.md", MECHANISM_NOTE_MD)

        state = PushedState(tmp_path / "state.jsonl")

        with patch("mac_notes_bridge.watcher.push_note") as mock_push, \
             patch("mac_notes_bridge.watcher.query_pushed_note_ids", return_value=[]):
            count = cold_boot_sweep(notes_dir, state, "Homunculus", "iCloud")

        assert count == 2
        assert mock_push.call_count == 2
        assert state.is_pushed("2026-09-15-test-notes-mechanism")
        assert state.is_pushed("2026-09-15-mechanism-to-close-the-loop-between-phone-and-mac")

    def test_skips_already_pushed(self, tmp_path):
        notes_dir = tmp_path / "notes"
        notes_dir.mkdir()
        write_md(notes_dir, "note.md", TEST_NOTE_MD)
        state = PushedState(tmp_path / "state.jsonl")
        state.mark_pushed("2026-09-15-test-notes-mechanism")

        with patch("mac_notes_bridge.watcher.push_note") as mock_push, \
             patch("mac_notes_bridge.watcher.query_pushed_note_ids", return_value=[]):
            count = cold_boot_sweep(notes_dir, state, "Homunculus", "iCloud")

        assert count == 0
        mock_push.assert_not_called()

    def test_returns_zero_on_empty_dir(self, tmp_path):
        notes_dir = tmp_path / "notes"
        notes_dir.mkdir()
        state = PushedState(tmp_path / "state.jsonl")

        with patch("mac_notes_bridge.watcher.push_note"), \
             patch("mac_notes_bridge.watcher.query_pushed_note_ids", return_value=[]):
            count = cold_boot_sweep(notes_dir, state, "Homunculus", "iCloud")

        assert count == 0

    def test_returns_zero_on_missing_dir(self, tmp_path):
        state = PushedState(tmp_path / "state.jsonl")
        with patch("mac_notes_bridge.watcher.push_note"), \
             patch("mac_notes_bridge.watcher.query_pushed_note_ids", return_value=[]):
            count = cold_boot_sweep(tmp_path / "nonexistent", state, "Homunculus", "iCloud")
        assert count == 0

    def test_partial_push_on_applescript_error(self, tmp_path):
        """If one push fails, the other still proceeds."""
        notes_dir = tmp_path / "notes"
        notes_dir.mkdir()
        write_md(notes_dir, "2026-09-15-test-notes-mechanism.md", TEST_NOTE_MD)
        write_md(notes_dir, "2026-09-15-mechanism.md", MECHANISM_NOTE_MD)

        state = PushedState(tmp_path / "state.jsonl")
        calls = []

        def side_effect(note, folder, account, **kwargs):
            calls.append(note.note_id)
            if note.note_id == "2026-09-15-test-notes-mechanism":
                raise AppleScriptError("permission denied")

        with patch("mac_notes_bridge.watcher.push_note", side_effect=side_effect), \
             patch("mac_notes_bridge.watcher.query_pushed_note_ids", return_value=[]):
            count = cold_boot_sweep(notes_dir, state, "Homunculus", "iCloud")

        # Only the successful one is marked
        assert count == 1
        assert state.is_pushed("2026-09-15-mechanism-to-close-the-loop-between-phone-and-mac")
        assert not state.is_pushed("2026-09-15-test-notes-mechanism")

    def test_handles_bad_md_files_in_sweep(self, tmp_path):
        notes_dir = tmp_path / "notes"
        notes_dir.mkdir()
        write_md(notes_dir, "good.md", TEST_NOTE_MD)
        write_md(notes_dir, "bad.md", "---\ntitle: broken\n---\n")

        state = PushedState(tmp_path / "state.jsonl")
        with patch("mac_notes_bridge.watcher.push_note") as mock_push, \
             patch("mac_notes_bridge.watcher.query_pushed_note_ids", return_value=[]):
            count = cold_boot_sweep(notes_dir, state, "Homunculus", "iCloud")

        assert count == 1

    def test_idempotent_on_second_run(self, tmp_path):
        notes_dir = tmp_path / "notes"
        notes_dir.mkdir()
        write_md(notes_dir, "note.md", TEST_NOTE_MD)
        state = PushedState(tmp_path / "state.jsonl")

        with patch("mac_notes_bridge.watcher.push_note") as mock_push, \
             patch("mac_notes_bridge.watcher.query_pushed_note_ids", return_value=[]):
            count1 = cold_boot_sweep(notes_dir, state, "Homunculus", "iCloud")
            count2 = cold_boot_sweep(notes_dir, state, "Homunculus", "iCloud")

        assert count1 == 1
        assert count2 == 0
        assert mock_push.call_count == 1


# ---------------------------------------------------------------------------
# Tests: VaultNotesHandler
# ---------------------------------------------------------------------------

class TestVaultNotesHandler:
    def _make_handler(self, tmp_path: Path):
        state = PushedState(tmp_path / "state.jsonl")
        return VaultNotesHandler(state, "Homunculus", "iCloud"), state

    def test_on_created_pushes_new_note(self, tmp_path):
        handler, state = self._make_handler(tmp_path)
        p = write_md(tmp_path, "note.md", TEST_NOTE_MD)

        from watchdog.events import FileCreatedEvent
        event = FileCreatedEvent(str(p))

        with patch("mac_notes_bridge.watcher.push_note") as mock_push, \
             patch("mac_notes_bridge.watcher.query_pushed_note_ids", return_value=[]):
            handler.on_created(event)

        mock_push.assert_called_once()
        assert state.is_pushed("2026-09-15-test-notes-mechanism")

    def test_on_created_skips_directories(self, tmp_path):
        handler, state = self._make_handler(tmp_path)
        new_dir = tmp_path / "subdir"
        new_dir.mkdir()

        from watchdog.events import FileCreatedEvent
        event = FileCreatedEvent(str(new_dir))
        event.is_directory = True

        with patch("mac_notes_bridge.watcher.push_note") as mock_push, \
             patch("mac_notes_bridge.watcher.query_pushed_note_ids", return_value=[]):
            handler.on_created(event)

        mock_push.assert_not_called()

    def test_on_created_skips_tmp_files(self, tmp_path, caplog):
        """Temp files (.tmp) must be logged at DEBUG and not dispatched."""
        handler, state = self._make_handler(tmp_path)

        tmp_file = tmp_path / "2026-09-15-test-notes-mechanism.md.tmp.4010.2"
        tmp_file.write_bytes(b"not a note yet")

        from watchdog.events import FileCreatedEvent
        event = FileCreatedEvent(str(tmp_file))

        with caplog.at_level(logging.DEBUG, logger="mac_notes_bridge.watcher"):
            with patch("mac_notes_bridge.watcher.push_note") as mock_push, \
                 patch("mac_notes_bridge.watcher.query_pushed_note_ids", return_value=[]):
                handler.on_created(event)

        mock_push.assert_not_called()
        assert any("skipping temp file" in r.message.lower() for r in caplog.records)

    def test_on_modified_skips_already_pushed(self, tmp_path):
        handler, state = self._make_handler(tmp_path)
        p = write_md(tmp_path, "note.md", TEST_NOTE_MD)
        state.mark_pushed("2026-09-15-test-notes-mechanism")

        from watchdog.events import FileModifiedEvent
        event = FileModifiedEvent(str(p))

        with patch("mac_notes_bridge.watcher.push_note") as mock_push, \
             patch("mac_notes_bridge.watcher.query_pushed_note_ids", return_value=[]):
            handler.on_modified(event)

        mock_push.assert_not_called()

    def test_on_modified_pushes_if_not_yet_pushed(self, tmp_path):
        handler, state = self._make_handler(tmp_path)
        p = write_md(tmp_path, "note.md", TEST_NOTE_MD)

        from watchdog.events import FileModifiedEvent
        event = FileModifiedEvent(str(p))

        with patch("mac_notes_bridge.watcher.push_note") as mock_push, \
             patch("mac_notes_bridge.watcher.query_pushed_note_ids", return_value=[]):
            handler.on_modified(event)

        mock_push.assert_called_once()

    def test_on_modified_ignores_directories(self, tmp_path):
        handler, state = self._make_handler(tmp_path)

        from watchdog.events import FileModifiedEvent
        event = FileModifiedEvent(str(tmp_path))
        event.is_directory = True

        with patch("mac_notes_bridge.watcher.push_note") as mock_push, \
             patch("mac_notes_bridge.watcher.query_pushed_note_ids", return_value=[]):
            handler.on_modified(event)

        mock_push.assert_not_called()

    def test_on_modified_ignores_non_md(self, tmp_path):
        handler, state = self._make_handler(tmp_path)
        txt = tmp_path / "notes.txt"
        txt.write_text("not a note")

        from watchdog.events import FileModifiedEvent
        event = FileModifiedEvent(str(txt))

        with patch("mac_notes_bridge.watcher.push_note") as mock_push, \
             patch("mac_notes_bridge.watcher.query_pushed_note_ids", return_value=[]):
            handler.on_modified(event)

        mock_push.assert_not_called()

    def test_second_created_event_is_idempotent(self, tmp_path):
        """Watchdog can fire multiple times; push must only happen once."""
        handler, state = self._make_handler(tmp_path)
        p = write_md(tmp_path, "note.md", TEST_NOTE_MD)

        from watchdog.events import FileCreatedEvent
        event = FileCreatedEvent(str(p))

        with patch("mac_notes_bridge.watcher.push_note") as mock_push, \
             patch("mac_notes_bridge.watcher.query_pushed_note_ids", return_value=[]):
            handler.on_created(event)
            handler.on_created(event)

        assert mock_push.call_count == 1

    def test_on_moved_md_destination_dispatches(self, tmp_path):
        """Watchdog MOVE event to a .md destination must trigger push_if_new.
        Sprite/Herman writes atomically: .tmp → os.replace → .md.
        Watchdog sees a MOVE event with dest_path = <file>.md.
        """
        from watchdog.events import FileMovedEvent
        handler, state = self._make_handler(tmp_path)

        final_path = write_md(tmp_path, "2026-09-15-test-notes-mechanism.md", TEST_NOTE_MD)
        tmp_src = str(tmp_path / "2026-09-15-test-notes-mechanism.md.tmp.4010.2")

        event = FileMovedEvent(src_path=tmp_src, dest_path=str(final_path))

        with patch("mac_notes_bridge.watcher.push_note") as mock_push, \
             patch("mac_notes_bridge.watcher.query_pushed_note_ids", return_value=[]):
            handler.on_moved(event)

        mock_push.assert_called_once()
        assert state.is_pushed("2026-09-15-test-notes-mechanism")

    def test_on_moved_non_md_destination_ignored(self, tmp_path):
        """MOVE events whose destination is not .md must be ignored."""
        from watchdog.events import FileMovedEvent
        handler, state = self._make_handler(tmp_path)

        event = FileMovedEvent(
            src_path=str(tmp_path / "notes.txt.tmp"),
            dest_path=str(tmp_path / "notes.txt"),
        )

        with patch("mac_notes_bridge.watcher.push_note") as mock_push, \
             patch("mac_notes_bridge.watcher.query_pushed_note_ids", return_value=[]):
            handler.on_moved(event)

        mock_push.assert_not_called()

    def test_on_moved_directory_ignored(self, tmp_path):
        """Directory MOVE events must be ignored."""
        from watchdog.events import DirMovedEvent
        handler, state = self._make_handler(tmp_path)

        event = DirMovedEvent(
            src_path=str(tmp_path / "old_dir"),
            dest_path=str(tmp_path / "new_dir"),
        )

        with patch("mac_notes_bridge.watcher.push_note") as mock_push, \
             patch("mac_notes_bridge.watcher.query_pushed_note_ids", return_value=[]):
            handler.on_moved(event)

        mock_push.assert_not_called()


# ---------------------------------------------------------------------------
# Tests: periodic_sweep
# ---------------------------------------------------------------------------

class TestPeriodicSweep:
    def test_pushes_missed_note(self, tmp_path):
        """Vault has a .md with no entry in pushed.jsonl → sweep dispatches it."""
        notes_dir = tmp_path / "notes"
        notes_dir.mkdir(parents=True)
        write_md(notes_dir, "2026-09-15-test-notes-mechanism.md", TEST_NOTE_MD)

        state = PushedState(tmp_path / "state.jsonl")

        with patch("mac_notes_bridge.watcher.push_note") as mock_push, \
             patch("mac_notes_bridge.watcher.query_pushed_note_ids", return_value=[]):
            count = periodic_sweep(notes_dir, state, "Homunculus", "iCloud")

        assert count == 1
        mock_push.assert_called_once()
        assert state.is_pushed("2026-09-15-test-notes-mechanism")

    def test_skips_already_pushed(self, tmp_path):
        """Periodic sweep must not re-push notes already in pushed.jsonl."""
        notes_dir = tmp_path / "notes"
        notes_dir.mkdir()
        write_md(notes_dir, "note.md", TEST_NOTE_MD)

        state = PushedState(tmp_path / "state.jsonl")
        state.mark_pushed("2026-09-15-test-notes-mechanism")

        with patch("mac_notes_bridge.watcher.push_note") as mock_push, \
             patch("mac_notes_bridge.watcher.query_pushed_note_ids", return_value=[]):
            count = periodic_sweep(notes_dir, state, "Homunculus", "iCloud")

        assert count == 0
        mock_push.assert_not_called()

    def test_returns_zero_on_empty_vault(self, tmp_path):
        notes_dir = tmp_path / "notes"
        notes_dir.mkdir()
        state = PushedState(tmp_path / "state.jsonl")

        with patch("mac_notes_bridge.watcher.push_note"), \
             patch("mac_notes_bridge.watcher.query_pushed_note_ids", return_value=[]):
            count = periodic_sweep(notes_dir, state, "Homunculus", "iCloud")

        assert count == 0

    def test_returns_zero_on_missing_root(self, tmp_path):
        state = PushedState(tmp_path / "state.jsonl")
        with patch("mac_notes_bridge.watcher.push_note"), \
             patch("mac_notes_bridge.watcher.query_pushed_note_ids", return_value=[]):
            count = periodic_sweep(tmp_path / "nonexistent", state, "Homunculus", "iCloud")
        assert count == 0
