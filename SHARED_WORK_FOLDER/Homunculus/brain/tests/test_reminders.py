"""Tests for reminder schedule generation."""

from __future__ import annotations

from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

from homunculus_brain.reminders import (
    build_event_schedule,
    build_morning_summary,
    _compose_summary_body,
)
from homunculus_brain.schemas import CalendarEvent, ReminderKind


TZ = ZoneInfo("America/New_York")


def _event(title: str, when: datetime, duration: int = 30) -> CalendarEvent:
    return CalendarEvent(
        id="test-id",
        title=title,
        starts_at=when,
        ends_at=when + timedelta(minutes=duration),
        tz="America/New_York",
        duration_minutes=duration,
        created_at=when,
        updated_at=when,
    )


def test_event_schedule_has_six_rows():
    e = _event("Coffee with Jane", datetime(2026, 6, 12, 10, 0, tzinfo=TZ))
    rows = build_event_schedule(e)
    assert len(rows) == 6
    kinds = [r.kind for r in rows]
    assert ReminderKind.HEADS_UP_30 in kinds
    assert ReminderKind.PRE_5 in kinds
    assert ReminderKind.STRIKE_0 in kinds
    assert ReminderKind.STRIKE_15 in kinds


def test_strike_offsets_correct():
    e = _event("X", datetime(2026, 6, 12, 10, 0, tzinfo=TZ))
    rows = {r.kind: r for r in build_event_schedule(e)}
    assert rows[ReminderKind.HEADS_UP_30].fire_at == datetime(2026, 6, 12, 9, 30, tzinfo=TZ)
    assert rows[ReminderKind.PRE_5].fire_at == datetime(2026, 6, 12, 9, 55, tzinfo=TZ)
    assert rows[ReminderKind.STRIKE_0].fire_at == datetime(2026, 6, 12, 10, 0, tzinfo=TZ)
    assert rows[ReminderKind.STRIKE_15].fire_at == datetime(2026, 6, 12, 10, 15, tzinfo=TZ)


def test_strike_bodies_distinct():
    e = _event("Coffee with Jane", datetime(2026, 6, 12, 10, 0, tzinfo=TZ))
    bodies = {r.kind: r.body for r in build_event_schedule(e)}
    # Each strike has a distinct, escalating tone.
    assert "starting now" in bodies[ReminderKind.STRIKE_0]
    assert "Final reminder" in bodies[ReminderKind.STRIKE_15]


def test_morning_summary_fires_at_local_time():
    summary = build_morning_summary(
        events_today=[],
        missed_yesterday=[],
        summary_date=datetime(2026, 6, 12, 0, 0, tzinfo=TZ),
        summary_time_local="07:00",
        tz=TZ,
    )
    assert summary.fire_at == datetime(2026, 6, 12, 7, 0, tzinfo=TZ)
    assert summary.kind == ReminderKind.MORNING_SUMMARY


def test_morning_summary_empty_day_copy():
    body = _compose_summary_body([], [])
    assert "No events today" in body


def test_morning_summary_lists_events_and_missed():
    e1 = _event("Coffee with Jane", datetime(2026, 6, 12, 10, 0, tzinfo=TZ))
    e2 = _event("Dentist", datetime(2026, 6, 12, 14, 0, tzinfo=TZ))
    body = _compose_summary_body([e1, e2], [_event("Pills", datetime(2026, 6, 11, 9, 0, tzinfo=TZ))])
    assert "Coffee with Jane" in body
    assert "Dentist" in body
    assert "Pills" in body
