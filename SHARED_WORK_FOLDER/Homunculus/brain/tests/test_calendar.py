"""Tests for calendar creation, listing, and conflict detection."""

from __future__ import annotations

from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

import pytest

from homunculus_brain import calendar as cal


TZ = ZoneInfo("America/New_York")


def _ev(vault_path: Path, title: str, when: datetime, duration: int = 30):
    return cal.create_event(
        vault_path,
        title=title,
        starts_at=when,
        duration_minutes=duration,
        tz_name="America/New_York",
        source="voice",
    )


def test_create_and_round_trip(tmp_path: Path):
    when = datetime(2026, 6, 12, 10, 0, tzinfo=TZ)
    ev = _ev(tmp_path, "Coffee with Jane", when)
    events = cal.list_events(tmp_path)
    assert len(events) == 1
    assert events[0].id == ev.id
    assert events[0].title == "Coffee with Jane"
    assert events[0].starts_at == when


def test_naive_starts_at_rejected(tmp_path: Path):
    with pytest.raises(ValueError):
        cal.create_event(
            tmp_path,
            title="bad",
            starts_at=datetime(2026, 6, 12, 10, 0),
            duration_minutes=30,
            tz_name="America/New_York",
        )


def test_direct_conflict_detected(tmp_path: Path):
    when = datetime(2026, 6, 12, 10, 0, tzinfo=TZ)
    _ev(tmp_path, "Coffee with Jane", when, duration=60)
    report = cal.check_conflicts(
        tmp_path,
        starts_at=datetime(2026, 6, 12, 10, 30, tzinfo=TZ),
        ends_at=datetime(2026, 6, 12, 11, 0, tzinfo=TZ),
        fuzz_minutes=30,
    )
    assert report.has_direct_conflict
    assert len(report.direct) == 1


def test_fuzzy_conflict_within_30min(tmp_path: Path):
    _ev(tmp_path, "Coffee with Jane", datetime(2026, 6, 12, 10, 0, tzinfo=TZ), duration=30)
    report = cal.check_conflicts(
        tmp_path,
        starts_at=datetime(2026, 6, 12, 10, 45, tzinfo=TZ),
        ends_at=datetime(2026, 6, 12, 11, 15, tzinfo=TZ),
        fuzz_minutes=30,
    )
    assert not report.has_direct_conflict
    assert report.has_fuzzy_conflict


def test_no_conflict_far_apart(tmp_path: Path):
    _ev(tmp_path, "Coffee with Jane", datetime(2026, 6, 12, 10, 0, tzinfo=TZ), duration=30)
    report = cal.check_conflicts(
        tmp_path,
        starts_at=datetime(2026, 6, 12, 15, 0, tzinfo=TZ),
        ends_at=datetime(2026, 6, 12, 15, 30, tzinfo=TZ),
        fuzz_minutes=30,
    )
    assert not report.has_direct_conflict
    assert not report.has_fuzzy_conflict


def test_list_events_between(tmp_path: Path):
    _ev(tmp_path, "A", datetime(2026, 6, 12, 10, 0, tzinfo=TZ))
    _ev(tmp_path, "B", datetime(2026, 6, 14, 14, 0, tzinfo=TZ))
    found = cal.list_events_between(
        tmp_path,
        start=datetime(2026, 6, 12, 0, 0, tzinfo=TZ),
        end=datetime(2026, 6, 13, 0, 0, tzinfo=TZ),
    )
    assert len(found) == 1
    assert found[0].title == "A"
