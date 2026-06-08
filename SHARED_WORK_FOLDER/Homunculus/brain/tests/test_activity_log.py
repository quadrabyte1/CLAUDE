"""Tests for the append-only activity log."""

from __future__ import annotations

from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

from homunculus_brain import activity_log


TZ = ZoneInfo("America/New_York")


def test_log_appends_line(tmp_path: Path):
    activity_log.log(tmp_path, "parse", raw_text="hello", details={"foo": "bar"})
    entries = activity_log.tail(tmp_path)
    assert len(entries) == 1
    assert entries[0]["kind"] == "parse"
    assert entries[0]["raw_text"] == "hello"
    assert entries[0]["details"]["foo"] == "bar"


def test_tail_returns_last_n(tmp_path: Path):
    for i in range(10):
        activity_log.log(tmp_path, "parse", raw_text=f"line {i}")
    entries = activity_log.tail(tmp_path, n=3)
    assert len(entries) == 3
    assert entries[-1]["raw_text"] == "line 9"
    assert entries[0]["raw_text"] == "line 7"


def test_tail_handles_empty_log(tmp_path: Path):
    assert activity_log.tail(tmp_path) == []


def test_log_with_explicit_timestamp(tmp_path: Path):
    when = datetime(2026, 6, 8, 12, 0, tzinfo=TZ)
    activity_log.log(tmp_path, "write", at=when, event_id="x", details={"path": "y"})
    e = activity_log.tail(tmp_path)[0]
    assert e["at"].startswith("2026-06-08T12:00:00")
    assert e["event_id"] == "x"


def test_iter_entries_streams_all(tmp_path: Path):
    for i in range(5):
        activity_log.log(tmp_path, "parse", raw_text=f"x{i}")
    collected = list(activity_log.iter_entries(tmp_path))
    assert len(collected) == 5
