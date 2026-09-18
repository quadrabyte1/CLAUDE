"""
test_state.py — Tests for mac_notifier.state.FiredState

Covers:
- Missing state file → empty state, no crash
- Load existing state file
- is_fired / mark_fired round-trip
- mark_fired appends to file
- Malformed lines in state file → skipped, rest loaded
- all_fired() snapshot
- count()
- Thread safety (basic: mark from multiple identifiers)
- Duplicate identifiers in file → deduped in memory
"""

from __future__ import annotations

import json
import threading
from datetime import datetime, timezone
from pathlib import Path

import pytest

from mac_notifier.state import FiredState


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture()
def state_file(tmp_path: Path) -> Path:
    return tmp_path / "fired.jsonl"


@pytest.fixture()
def state(state_file: Path) -> FiredState:
    return FiredState(state_file)


# ---------------------------------------------------------------------------
# Tests: missing file → empty state
# ---------------------------------------------------------------------------


class TestMissingFile:
    def test_missing_file_is_empty(self, tmp_path: Path):
        s = FiredState(tmp_path / "nonexistent.jsonl")
        assert s.count() == 0

    def test_missing_file_is_fired_returns_false(self, tmp_path: Path):
        s = FiredState(tmp_path / "nonexistent.jsonl")
        assert not s.is_fired("summary.2026-09-16:morning_summary")

    def test_missing_file_all_fired_empty(self, tmp_path: Path):
        s = FiredState(tmp_path / "nonexistent.jsonl")
        assert s.all_fired() == frozenset()


# ---------------------------------------------------------------------------
# Tests: mark_fired + is_fired round-trip
# ---------------------------------------------------------------------------


class TestMarkFired:
    def test_not_fired_before_mark(self, state: FiredState):
        assert not state.is_fired("ev.abc:strike_0")

    def test_is_fired_after_mark(self, state: FiredState):
        state.mark_fired("ev.abc:strike_0")
        assert state.is_fired("ev.abc:strike_0")

    def test_different_identifier_not_fired(self, state: FiredState):
        state.mark_fired("ev.abc:strike_0")
        assert not state.is_fired("ev.abc:strike_5")

    def test_mark_fired_creates_parent_dirs(self, tmp_path: Path):
        deep_file = tmp_path / "nested" / "deep" / "fired.jsonl"
        s = FiredState(deep_file)
        s.mark_fired("ev.xyz:morning_summary")
        assert deep_file.exists()

    def test_mark_fired_writes_jsonl_line(self, state: FiredState, state_file: Path):
        state.mark_fired("ev.abc:strike_0")
        lines = state_file.read_text().strip().splitlines()
        assert len(lines) == 1
        obj = json.loads(lines[0])
        assert obj["identifier"] == "ev.abc:strike_0"
        assert "fired_at" in obj

    def test_mark_fired_appends_multiple(self, state: FiredState, state_file: Path):
        state.mark_fired("ev.abc:strike_0")
        state.mark_fired("ev.abc:strike_5")
        lines = state_file.read_text().strip().splitlines()
        assert len(lines) == 2
        identifiers = [json.loads(l)["identifier"] for l in lines]
        assert "ev.abc:strike_0" in identifiers
        assert "ev.abc:strike_5" in identifiers

    def test_fired_at_is_utc_iso(self, state: FiredState, state_file: Path):
        state.mark_fired("ev.test:morning_summary")
        obj = json.loads(state_file.read_text().strip())
        fired_at = datetime.fromisoformat(obj["fired_at"])
        assert fired_at.tzinfo is not None


# ---------------------------------------------------------------------------
# Tests: load from existing file
# ---------------------------------------------------------------------------


class TestLoadFromFile:
    def _write_state(self, state_file: Path, entries: list[dict]) -> None:
        state_file.parent.mkdir(parents=True, exist_ok=True)
        with state_file.open("w") as fh:
            for entry in entries:
                fh.write(json.dumps(entry) + "\n")

    def test_load_existing_entries(self, state_file: Path):
        self._write_state(state_file, [
            {"identifier": "ev.a:strike_0", "fired_at": "2026-09-15T07:00:00+00:00"},
            {"identifier": "ev.b:morning_summary", "fired_at": "2026-09-15T08:00:00+00:00"},
        ])
        s = FiredState(state_file)
        assert s.is_fired("ev.a:strike_0")
        assert s.is_fired("ev.b:morning_summary")
        assert s.count() == 2

    def test_load_skips_malformed_json(self, state_file: Path):
        state_file.parent.mkdir(parents=True, exist_ok=True)
        state_file.write_text(
            '{"identifier": "ev.good:strike_0", "fired_at": "2026-09-15T07:00:00+00:00"}\n'
            'NOT VALID JSON\n'
            '{"identifier": "ev.also_good:strike_5", "fired_at": "2026-09-15T07:05:00+00:00"}\n'
        )
        s = FiredState(state_file)
        assert s.is_fired("ev.good:strike_0")
        assert s.is_fired("ev.also_good:strike_5")
        assert s.count() == 2

    def test_load_skips_missing_identifier_key(self, state_file: Path):
        state_file.parent.mkdir(parents=True, exist_ok=True)
        state_file.write_text(
            '{"event_id": "ev.a", "fired_at": "2026-09-15T07:00:00+00:00"}\n'
            '{"identifier": "ev.b:strike_0", "fired_at": "2026-09-15T07:00:00+00:00"}\n'
        )
        s = FiredState(state_file)
        # First line has wrong key — skipped. Second is valid.
        assert not s.is_fired("ev.a:strike_0")
        assert s.is_fired("ev.b:strike_0")
        assert s.count() == 1

    def test_load_deduplicates_repeated_identifier(self, state_file: Path):
        self._write_state(state_file, [
            {"identifier": "ev.dup:strike_0", "fired_at": "2026-09-15T07:00:00+00:00"},
            {"identifier": "ev.dup:strike_0", "fired_at": "2026-09-15T07:01:00+00:00"},
        ])
        s = FiredState(state_file)
        assert s.count() == 1
        assert s.is_fired("ev.dup:strike_0")

    def test_load_empty_file(self, state_file: Path):
        state_file.parent.mkdir(parents=True, exist_ok=True)
        state_file.write_text("")
        s = FiredState(state_file)
        assert s.count() == 0

    def test_load_blank_lines_skipped(self, state_file: Path):
        state_file.parent.mkdir(parents=True, exist_ok=True)
        state_file.write_text(
            '\n'
            '{"identifier": "ev.c:pre_5", "fired_at": "2026-09-15T07:00:00+00:00"}\n'
            '\n'
        )
        s = FiredState(state_file)
        assert s.count() == 1


# ---------------------------------------------------------------------------
# Tests: all_fired()
# ---------------------------------------------------------------------------


class TestAllFired:
    def test_all_fired_returns_frozenset(self, state: FiredState):
        state.mark_fired("ev.a:strike_0")
        state.mark_fired("ev.b:morning_summary")
        result = state.all_fired()
        assert isinstance(result, frozenset)
        assert result == frozenset({"ev.a:strike_0", "ev.b:morning_summary"})

    def test_all_fired_snapshot_not_mutated(self, state: FiredState):
        state.mark_fired("ev.a:strike_0")
        snap = state.all_fired()
        state.mark_fired("ev.b:strike_5")
        # Snapshot should not reflect the new entry
        assert "ev.b:strike_5" not in snap


# ---------------------------------------------------------------------------
# Tests: thread safety (basic)
# ---------------------------------------------------------------------------


class TestThreadSafety:
    def test_concurrent_mark_fired(self, state: FiredState):
        """Multiple threads marking different identifiers shouldn't corrupt state."""
        identifiers = [f"ev.thread{i}:strike_0" for i in range(20)]

        def worker(ident: str) -> None:
            state.mark_fired(ident)

        threads = [threading.Thread(target=worker, args=(ident,)) for ident in identifiers]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        for ident in identifiers:
            assert state.is_fired(ident)
        assert state.count() == 20
