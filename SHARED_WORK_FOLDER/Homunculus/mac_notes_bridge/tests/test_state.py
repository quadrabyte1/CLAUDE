"""
test_state.py — Tests for state.py (idempotency / pushed.jsonl).

All tests use tmp_path; nothing touches the real state file.

Key difference from calendar bridge: state key is note_id (not event_id).
"""

from __future__ import annotations

import json
import threading
from pathlib import Path

import pytest

from mac_notes_bridge.state import PushedState


# ---------------------------------------------------------------------------
# Basic lifecycle
# ---------------------------------------------------------------------------

class TestPushedStateBasic:
    def test_empty_on_init_no_file(self, tmp_path):
        state = PushedState(tmp_path / "pushed.jsonl")
        assert state.all_pushed() == frozenset()

    def test_is_pushed_false_initially(self, tmp_path):
        state = PushedState(tmp_path / "pushed.jsonl")
        assert not state.is_pushed("2026-09-15-test-notes-mechanism")

    def test_mark_pushed_sets_flag(self, tmp_path):
        state = PushedState(tmp_path / "pushed.jsonl")
        state.mark_pushed("2026-09-15-test-notes-mechanism")
        assert state.is_pushed("2026-09-15-test-notes-mechanism")

    def test_mark_pushed_other_id_not_affected(self, tmp_path):
        state = PushedState(tmp_path / "pushed.jsonl")
        state.mark_pushed("note-a")
        assert not state.is_pushed("note-b")

    def test_all_pushed_returns_frozenset(self, tmp_path):
        state = PushedState(tmp_path / "pushed.jsonl")
        state.mark_pushed("note-x")
        result = state.all_pushed()
        assert isinstance(result, frozenset)
        assert "note-x" in result

    def test_mark_pushed_multiple(self, tmp_path):
        state = PushedState(tmp_path / "pushed.jsonl")
        ids = ["note-1", "note-2", "note-3"]
        for nid in ids:
            state.mark_pushed(nid)
        assert state.all_pushed() == frozenset(ids)


# ---------------------------------------------------------------------------
# Persistence — JSONL file is written correctly
# ---------------------------------------------------------------------------

class TestPushedStatePersistence:
    def test_creates_state_file(self, tmp_path):
        sf = tmp_path / "pushed.jsonl"
        state = PushedState(sf)
        state.mark_pushed("note-1")
        assert sf.exists()

    def test_creates_parent_dirs(self, tmp_path):
        sf = tmp_path / "deep" / "dir" / "pushed.jsonl"
        state = PushedState(sf)
        state.mark_pushed("note-1")
        assert sf.exists()

    def test_jsonl_format(self, tmp_path):
        sf = tmp_path / "pushed.jsonl"
        state = PushedState(sf)
        state.mark_pushed("2026-09-15-test-note")

        lines = sf.read_text(encoding="utf-8").strip().splitlines()
        assert len(lines) == 1
        obj = json.loads(lines[0])
        assert obj["note_id"] == "2026-09-15-test-note"
        assert "pushed_at" in obj

    def test_uses_note_id_key_not_event_id(self, tmp_path):
        """The JSONL key must be 'note_id', not 'event_id' (calendar bridge key)."""
        sf = tmp_path / "pushed.jsonl"
        state = PushedState(sf)
        state.mark_pushed("my-note")
        line = sf.read_text().strip()
        obj = json.loads(line)
        assert "note_id" in obj
        assert "event_id" not in obj

    def test_appends_not_overwrites(self, tmp_path):
        sf = tmp_path / "pushed.jsonl"
        state = PushedState(sf)
        state.mark_pushed("note-a")
        state.mark_pushed("note-b")

        lines = sf.read_text(encoding="utf-8").strip().splitlines()
        assert len(lines) == 2

    def test_reload_restores_state(self, tmp_path):
        sf = tmp_path / "pushed.jsonl"
        s1 = PushedState(sf)
        s1.mark_pushed("note-persist")

        s2 = PushedState(sf)
        assert s2.is_pushed("note-persist")

    def test_reload_deduplicates(self, tmp_path):
        """Duplicate lines in the file don't double-count."""
        sf = tmp_path / "pushed.jsonl"
        line = json.dumps({"note_id": "dup-note", "pushed_at": "2026-09-15T00:00:00+00:00"})
        sf.write_text(line + "\n" + line + "\n", encoding="utf-8")

        state = PushedState(sf)
        assert state.is_pushed("dup-note")
        assert len(state.all_pushed()) == 1

    def test_reload_skips_bad_lines(self, tmp_path):
        sf = tmp_path / "pushed.jsonl"
        good = json.dumps({"note_id": "good-note", "pushed_at": "2026-09-15T00:00:00+00:00"})
        sf.write_text("not json\n" + good + "\n", encoding="utf-8")

        state = PushedState(sf)
        assert state.is_pushed("good-note")
        assert not state.is_pushed("not json")

    def test_reload_skips_lines_missing_note_id_key(self, tmp_path):
        """Lines with wrong key (e.g. event_id from calendar bridge) are skipped."""
        sf = tmp_path / "pushed.jsonl"
        wrong_key = json.dumps({"event_id": "wrong-key-note", "pushed_at": "2026-09-15T00:00:00+00:00"})
        good = json.dumps({"note_id": "good-note", "pushed_at": "2026-09-15T00:00:00+00:00"})
        sf.write_text(wrong_key + "\n" + good + "\n", encoding="utf-8")

        state = PushedState(sf)
        assert state.is_pushed("good-note")
        assert not state.is_pushed("wrong-key-note")

    def test_reload_empty_lines_ignored(self, tmp_path):
        sf = tmp_path / "pushed.jsonl"
        good = json.dumps({"note_id": "note-ok", "pushed_at": "2026-09-15T00:00:00+00:00"})
        sf.write_text("\n\n" + good + "\n\n", encoding="utf-8")

        state = PushedState(sf)
        assert state.is_pushed("note-ok")


# ---------------------------------------------------------------------------
# reset_from_ids
# ---------------------------------------------------------------------------

class TestResetFromIds:
    def test_reset_replaces_in_memory(self, tmp_path):
        state = PushedState(tmp_path / "pushed.jsonl")
        state.mark_pushed("old-note")
        state.reset_from_ids({"new-note-a", "new-note-b"})
        assert state.is_pushed("new-note-a")
        assert state.is_pushed("new-note-b")
        assert not state.is_pushed("old-note")

    def test_reset_does_not_touch_file(self, tmp_path):
        sf = tmp_path / "pushed.jsonl"
        state = PushedState(sf)
        state.mark_pushed("file-note")
        file_content_before = sf.read_text()

        state.reset_from_ids({"memory-note"})
        assert sf.read_text() == file_content_before  # file unchanged

    def test_reset_empty_set(self, tmp_path):
        state = PushedState(tmp_path / "pushed.jsonl")
        state.mark_pushed("note-x")
        state.reset_from_ids(set())
        assert state.all_pushed() == frozenset()


# ---------------------------------------------------------------------------
# Thread safety
# ---------------------------------------------------------------------------

class TestThreadSafety:
    def test_concurrent_mark_pushed(self, tmp_path):
        """Multiple threads marking different notes don't corrupt the set."""
        sf = tmp_path / "pushed.jsonl"
        state = PushedState(sf)
        ids = [f"note-{i}" for i in range(50)]
        errors: list[Exception] = []

        def worker(nid: str) -> None:
            try:
                state.mark_pushed(nid)
            except Exception as exc:
                errors.append(exc)

        threads = [threading.Thread(target=worker, args=(nid,)) for nid in ids]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        assert not errors
        assert state.all_pushed() == frozenset(ids)

    def test_concurrent_reads_are_safe(self, tmp_path):
        state = PushedState(tmp_path / "pushed.jsonl")
        state.mark_pushed("note-read-test")
        results: list[bool] = []

        def reader() -> None:
            results.append(state.is_pushed("note-read-test"))

        threads = [threading.Thread(target=reader) for _ in range(20)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        assert all(results)
