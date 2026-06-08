"""Daily summary rows are composed from the live vault (v1.2 item 3).

The morning summary used to exist as `build_morning_summary` but nothing
called it. v1.2 wires it into the /reminders/upcoming path via
`build_daily_summary_rows` which reads the day's events from the vault
and composes one row per day.
"""

from __future__ import annotations

from datetime import datetime, timedelta
from pathlib import Path
from zoneinfo import ZoneInfo

from homunculus_brain import calendar as cal
from homunculus_brain import reminders as rem
from homunculus_brain.schemas import ReminderKind


TZ = ZoneInfo("America/New_York")


def test_summary_lists_tomorrow_event_time_and_title(tmp_path: Path):
    """One event tomorrow at 10am. The summary body for tomorrow must contain
    the event title and "10:00 AM"."""
    now = datetime(2026, 6, 8, 9, 0, tzinfo=TZ)  # Monday 9am
    tomorrow = now + timedelta(days=1)
    when = tomorrow.replace(hour=10, minute=0, second=0, microsecond=0)

    cal.create_event(
        tmp_path,
        title="Coffee with Jane",
        starts_at=when,
        duration_minutes=30,
        tz_name="America/New_York",
    )

    rows = rem.build_daily_summary_rows(
        tmp_path,
        now=now,
        days_ahead=3,
        summary_time="07:00",
        anchor_tz=TZ,
    )
    assert len(rows) == 3
    # The row for tomorrow.
    tomorrow_row = next(r for r in rows if r.event_id == f"summary.{tomorrow.date().isoformat()}")
    assert tomorrow_row.kind == ReminderKind.MORNING_SUMMARY
    assert tomorrow_row.fire_at == datetime(2026, 6, 9, 7, 0, tzinfo=TZ)
    assert "10:00 AM" in tomorrow_row.body
    assert "Coffee with Jane" in tomorrow_row.body


def test_summary_empty_day_says_no_events(tmp_path: Path):
    now = datetime(2026, 6, 8, 9, 0, tzinfo=TZ)
    rows = rem.build_daily_summary_rows(
        tmp_path,
        now=now,
        days_ahead=1,
        summary_time="07:00",
        anchor_tz=TZ,
    )
    assert len(rows) == 1
    assert "No events today" in rows[0].body


def test_summary_id_scheme_matches_ios_spec(tmp_path: Path):
    """Identifier scheme is ``summary.<yyyy-mm-dd>`` — what the iOS spec
    declares so UNUserNotificationCenter can dedupe across reboots."""
    now = datetime(2026, 6, 8, 9, 0, tzinfo=TZ)
    rows = rem.build_daily_summary_rows(
        tmp_path,
        now=now,
        days_ahead=2,
        summary_time="07:00",
        anchor_tz=TZ,
    )
    ids = [r.event_id for r in rows]
    assert "summary.2026-06-08" in ids
    assert "summary.2026-06-09" in ids
