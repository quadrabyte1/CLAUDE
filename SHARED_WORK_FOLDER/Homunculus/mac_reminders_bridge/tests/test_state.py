"""
test_state.py — Tests for mac_reminders_bridge.state.PushedState.

All tests use tmp_path; never touch ~/.local/share/mac_reminders_bridge/.
"""

from __future__ import annotations

import json
import threading
from pathlib import Path

import pytest

from mac_reminders_bridge.state import PushedState


# ---------------------------------------------------------------------------
# Construction and loading
# ---------------------------------------------------------------------------

class TestPushedStateLoad:
    def test_starts_empty_when_file_absent(self, tmp_path):
        state = PushedState(tmp_path / "pushed.jsonl")
        assert state.all_pushed() == frozenset()

    def test_loads_existing_entries(self, tmp_path):
        f = tmp_path / "pushed.jsonl"
        f.write_text(
            '{"event_id": "id-1", "pushed_at": "2026-09-16T00:00:00+00:00"}\n'
            '{"event_id": "id-2", "pushed_at": "2026-09-16T00:01:00+00:00"}\n',
            encoding="utf-8",
        )
        state = PushedState(f)
        assert "id-1" in state.all_pushed()
        assert "id-2" in state.all_pushed()

    def test_skips_blank_lines_in_file(self, tmp_path):
        f = tmp_path / "pushed.jsonl"
        f.write_text(
            '{"event_id": "good-id", "pushed_at": "2026-09-16T00:00:00+00:00"}\n'
            "\n"
            "\n",
            encoding="utf-8",
        )
        state = PushedState(f)
        assert len(state.all_pushed()) == 1

    def test_skips_malformed_lines(self, tmp_path):
        f = tmp_path / "pushed.jsonl"
        f.write_text(
            'NOT JSON\n'
            '{"event_id": "real-id", "pushed_at": "2026-09-16T00:00:00+00:00"}\n',
            encoding="utf-8",
        )
        state = PushedState(f)
        assert "real-id" in state.all_pushed()
        assert len(state.all_pushed()) == 1

    def test_skips_line_missing_event_id_key(self, tmp_path):
        f = tmp_path / "pushed.jsonl"
        f.write_text(
            '{"other_key": "value", "pushed_at": "2026-09-16T00:00:00+00:00"}\n'
            '{"event_id": "good-id", "pushed_at": "2026-09-16T00:00:00+00:00"}\n',
            encoding="utf-8",
        )
        state = PushedState(f)
        assert "good-id" in state.all_pushed()
        assert len(state.all_pushed()) == 1

    def test_duplicate_entries_deduplicated(self, tmp_path):
        f = tmp_path / "pushed.jsonl"
        f.write_text(
            '{"event_id": "dup-id", "pushed_at": "2026-09-16T00:00:00+00:00"}\n'
            '{"event_id": "dup-id", "pushed_at": "2026-09-16T00:01:00+00:00"}\n',
            encoding="utf-8",
        )
        state = PushedState(f)
        assert len(state.all_pushed()) == 1


# ---------------------------------------------------------------------------
# is_pushed
# ---------------------------------------------------------------------------

class TestIsPushed:
    def test_returns_false_for_unknown(self, tmp_path):
        state = PushedState(tmp_path / "pushed.jsonl")
        assert state.is_pushed("unknown-id") is False

    def test_returns_true_after_mark(self, tmp_path):
        state = PushedState(tmp_path / "pushed.jsonl")
        state.mark_pushed("my-event")
        assert state.is_pushed("my-event") is True

    def test_returns_true_for_loaded_id(self, tmp_path):
        f = tmp_path / "pushed.jsonl"
        f.write_text(
            '{"event_id": "pre-loaded", "pushed_at": "2026-09-16T00:00:00+00:00"}\n',
            encoding="utf-8",
        )
        state = PushedState(f)
        assert state.is_pushed("pre-loaded") is True


# ---------------------------------------------------------------------------
# mark_pushed
# ---------------------------------------------------------------------------

class TestMarkPushed:
    def test_creates_file_if_absent(self, tmp_path):
        state_file = tmp_path / "subdir" / "pushed.jsonl"
        state = PushedState(state_file)
        state.mark_pushed("new-event")
        assert state_file.exists()

    def test_appends_jsonl_line(self, tmp_path):
        state_file = tmp_path / "pushed.jsonl"
        state = PushedState(state_file)
        state.mark_pushed("ev-1")
        state.mark_pushed("ev-2")
        lines = [l for l in state_file.read_text().splitlines() if l.strip()]
        assert len(lines) == 2

    def test_written_line_is_valid_json(self, tmp_path):
        state_file = tmp_path / "pushed.jsonl"
        state = PushedState(state_file)
        state.mark_pushed("ev-json")
        line = state_file.read_text().strip()
        obj = json.loads(line)
        assert obj["event_id"] == "ev-json"
        assert "pushed_at" in obj

    def test_pushed_at_is_utc_iso8601(self, tmp_path):
        state_file = tmp_path / "pushed.jsonl"
        state = PushedState(state_file)
        state.mark_pushed("ev-utc")
        line = state_file.read_text().strip()
        obj = json.loads(line)
        assert "+00:00" in obj["pushed_at"] or "Z" in obj["pushed_at"]

    def test_persists_across_reload(self, tmp_path):
        state_file = tmp_path / "pushed.jsonl"
        s1 = PushedState(state_file)
        s1.mark_pushed("persist-me")
        # New instance reads same file
        s2 = PushedState(state_file)
        assert s2.is_pushed("persist-me") is True


# ---------------------------------------------------------------------------
# all_pushed
# ---------------------------------------------------------------------------

class TestAllPushed:
    def test_returns_frozenset(self, tmp_path):
        state = PushedState(tmp_path / "pushed.jsonl")
        result = state.all_pushed()
        assert isinstance(result, frozenset)

    def test_snapshot_does_not_mutate(self, tmp_path):
        state = PushedState(tmp_path / "pushed.jsonl")
        snap = state.all_pushed()
        state.mark_pushed("after-snapshot")
        # snapshot is immutable — adding to the state doesn't change it
        assert "after-snapshot" not in snap


# ---------------------------------------------------------------------------
# reset_from_ids
# ---------------------------------------------------------------------------

class TestResetFromIds:
    def test_replaces_in_memory_set(self, tmp_path):
        state = PushedState(tmp_path / "pushed.jsonl")
        state.mark_pushed("old-id")
        state.reset_from_ids({"new-id-1", "new-id-2"})
        assert state.is_pushed("new-id-1") is True
        assert state.is_pushed("new-id-2") is True
        assert state.is_pushed("old-id") is False

    def test_reset_does_not_touch_file(self, tmp_path):
        state_file = tmp_path / "pushed.jsonl"
        state = PushedState(state_file)
        state.mark_pushed("persisted")
        original_content = state_file.read_text()
        state.reset_from_ids({"ram-only"})
        # File must be unchanged
        assert state_file.read_text() == original_content


# ---------------------------------------------------------------------------
# Thread safety (basic smoke test)
# ---------------------------------------------------------------------------

class TestThreadSafety:
    def test_concurrent_marks_are_safe(self, tmp_path):
        state_file = tmp_path / "pushed.jsonl"
        state = PushedState(state_file)
        n = 50
        errors = []

        def worker(i: int) -> None:
            try:
                state.mark_pushed(f"event-{i:04d}")
            except Exception as exc:  # noqa: BLE001
                errors.append(exc)

        threads = [threading.Thread(target=worker, args=(i,)) for i in range(n)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        assert errors == [], f"Thread errors: {errors}"
        assert len(state.all_pushed()) == n
