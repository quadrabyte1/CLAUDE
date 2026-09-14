"""
test_state.py — Tests for state.py (idempotency / pushed.jsonl).

All tests use tmp_path; nothing touches the real state file.
"""

from __future__ import annotations

import json
import threading
import time
from pathlib import Path

import pytest

from mac_calendar_bridge.state import PushedState


# ---------------------------------------------------------------------------
# Basic lifecycle
# ---------------------------------------------------------------------------

class TestPushedStateBasic:
    def test_empty_on_init_no_file(self, tmp_path):
        state = PushedState(tmp_path / "pushed.jsonl")
        assert state.all_pushed() == frozenset()

    def test_is_pushed_false_initially(self, tmp_path):
        state = PushedState(tmp_path / "pushed.jsonl")
        assert not state.is_pushed("event-123")

    def test_mark_pushed_sets_flag(self, tmp_path):
        state = PushedState(tmp_path / "pushed.jsonl")
        state.mark_pushed("event-abc")
        assert state.is_pushed("event-abc")

    def test_mark_pushed_other_id_not_affected(self, tmp_path):
        state = PushedState(tmp_path / "pushed.jsonl")
        state.mark_pushed("event-a")
        assert not state.is_pushed("event-b")

    def test_all_pushed_returns_frozenset(self, tmp_path):
        state = PushedState(tmp_path / "pushed.jsonl")
        state.mark_pushed("event-x")
        result = state.all_pushed()
        assert isinstance(result, frozenset)
        assert "event-x" in result

    def test_mark_pushed_multiple(self, tmp_path):
        state = PushedState(tmp_path / "pushed.jsonl")
        ids = ["event-1", "event-2", "event-3"]
        for eid in ids:
            state.mark_pushed(eid)
        assert state.all_pushed() == frozenset(ids)


# ---------------------------------------------------------------------------
# Persistence — JSONL file is written correctly
# ---------------------------------------------------------------------------

class TestPushedStatePersistence:
    def test_creates_state_file(self, tmp_path):
        sf = tmp_path / "pushed.jsonl"
        state = PushedState(sf)
        state.mark_pushed("event-1")
        assert sf.exists()

    def test_creates_parent_dirs(self, tmp_path):
        sf = tmp_path / "deep" / "dir" / "pushed.jsonl"
        state = PushedState(sf)
        state.mark_pushed("event-1")
        assert sf.exists()

    def test_jsonl_format(self, tmp_path):
        sf = tmp_path / "pushed.jsonl"
        state = PushedState(sf)
        state.mark_pushed("event-42")

        lines = sf.read_text(encoding="utf-8").strip().splitlines()
        assert len(lines) == 1
        obj = json.loads(lines[0])
        assert obj["event_id"] == "event-42"
        assert "pushed_at" in obj

    def test_appends_not_overwrites(self, tmp_path):
        sf = tmp_path / "pushed.jsonl"
        state = PushedState(sf)
        state.mark_pushed("event-a")
        state.mark_pushed("event-b")

        lines = sf.read_text(encoding="utf-8").strip().splitlines()
        assert len(lines) == 2

    def test_reload_restores_state(self, tmp_path):
        sf = tmp_path / "pushed.jsonl"
        s1 = PushedState(sf)
        s1.mark_pushed("event-persist")

        # Fresh load from the same file
        s2 = PushedState(sf)
        assert s2.is_pushed("event-persist")

    def test_reload_deduplicates(self, tmp_path):
        """Duplicate lines in the file don't double-count."""
        sf = tmp_path / "pushed.jsonl"
        line = json.dumps({"event_id": "dup-event", "pushed_at": "2026-09-14T00:00:00+00:00"})
        sf.write_text(line + "\n" + line + "\n", encoding="utf-8")

        state = PushedState(sf)
        assert state.is_pushed("dup-event")
        assert len(state.all_pushed()) == 1

    def test_reload_skips_bad_lines(self, tmp_path):
        sf = tmp_path / "pushed.jsonl"
        good = json.dumps({"event_id": "good-event", "pushed_at": "2026-09-14T00:00:00+00:00"})
        sf.write_text("not json\n" + good + "\n", encoding="utf-8")

        state = PushedState(sf)
        assert state.is_pushed("good-event")
        assert not state.is_pushed("not json")

    def test_reload_empty_lines_ignored(self, tmp_path):
        sf = tmp_path / "pushed.jsonl"
        good = json.dumps({"event_id": "event-ok", "pushed_at": "2026-09-14T00:00:00+00:00"})
        sf.write_text("\n\n" + good + "\n\n", encoding="utf-8")

        state = PushedState(sf)
        assert state.is_pushed("event-ok")


# ---------------------------------------------------------------------------
# reset_from_ids
# ---------------------------------------------------------------------------

class TestResetFromIds:
    def test_reset_replaces_in_memory(self, tmp_path):
        state = PushedState(tmp_path / "pushed.jsonl")
        state.mark_pushed("old-event")
        state.reset_from_ids({"new-event-a", "new-event-b"})
        assert state.is_pushed("new-event-a")
        assert state.is_pushed("new-event-b")
        assert not state.is_pushed("old-event")

    def test_reset_does_not_touch_file(self, tmp_path):
        sf = tmp_path / "pushed.jsonl"
        state = PushedState(sf)
        state.mark_pushed("file-event")
        file_content_before = sf.read_text()

        state.reset_from_ids({"memory-event"})
        assert sf.read_text() == file_content_before  # file unchanged

    def test_reset_empty_set(self, tmp_path):
        state = PushedState(tmp_path / "pushed.jsonl")
        state.mark_pushed("event-x")
        state.reset_from_ids(set())
        assert state.all_pushed() == frozenset()


# ---------------------------------------------------------------------------
# Thread safety
# ---------------------------------------------------------------------------

class TestThreadSafety:
    def test_concurrent_mark_pushed(self, tmp_path):
        """Multiple threads marking different events don't corrupt the set."""
        sf = tmp_path / "pushed.jsonl"
        state = PushedState(sf)
        ids = [f"event-{i}" for i in range(50)]
        errors: list[Exception] = []

        def worker(eid: str) -> None:
            try:
                state.mark_pushed(eid)
            except Exception as exc:
                errors.append(exc)

        threads = [threading.Thread(target=worker, args=(eid,)) for eid in ids]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        assert not errors
        assert state.all_pushed() == frozenset(ids)

    def test_concurrent_reads_are_safe(self, tmp_path):
        state = PushedState(tmp_path / "pushed.jsonl")
        state.mark_pushed("event-read-test")
        results: list[bool] = []

        def reader() -> None:
            results.append(state.is_pushed("event-read-test"))

        threads = [threading.Thread(target=reader) for _ in range(20)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        assert all(results)
