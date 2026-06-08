"""Tests for the deterministic date resolver.

`now` is fixed to a known wall-clock so weekday math is predictable.
"""

from __future__ import annotations

from datetime import datetime
from zoneinfo import ZoneInfo

import pytest

from homunculus_brain.date_resolver import resolve


TZ = ZoneInfo("America/New_York")
# Monday, June 8 2026, 9:00 AM Eastern.
NOW = datetime(2026, 6, 8, 9, 0, tzinfo=TZ)


def test_today_at_explicit_time():
    r = resolve("today", "2pm", NOW, TZ)
    assert r.resolved_at == datetime(2026, 6, 8, 14, 0, tzinfo=TZ)
    assert r.ambiguous == []


def test_tomorrow_morning_uses_anchor():
    r = resolve("tomorrow", "morning", NOW, TZ, morning_anchor_hour=9)
    assert r.resolved_at == datetime(2026, 6, 9, 9, 0, tzinfo=TZ)


def test_thursday_resolves_to_this_thursday():
    r = resolve("Thursday", "10am", NOW, TZ)
    # Monday → Thursday is +3 days.
    assert r.resolved_at == datetime(2026, 6, 11, 10, 0, tzinfo=TZ)


def test_today_named_weekday_before_noon_stays_today():
    # NOW is Monday 9am — "Monday" should resolve to today.
    r = resolve("Monday", "3pm", NOW, TZ)
    assert r.resolved_at == datetime(2026, 6, 8, 15, 0, tzinfo=TZ)


def test_today_named_weekday_after_noon_rolls_forward():
    afternoon = NOW.replace(hour=14)
    r = resolve("Monday", "3pm", afternoon, TZ)
    # Monday afternoon, "Monday" at 3pm → next Monday.
    assert r.resolved_at == datetime(2026, 6, 15, 15, 0, tzinfo=TZ)


def test_next_thursday_rolls_a_week_further():
    r = resolve("next Thursday", "10am", NOW, TZ)
    # This Thursday would be 6/11; "next" → 6/18.
    assert r.resolved_at == datetime(2026, 6, 18, 10, 0, tzinfo=TZ)


def test_missing_time_is_ambiguous():
    r = resolve("Thursday", None, NOW, TZ)
    assert r.resolved_at is None
    assert "time" in r.ambiguous


def test_unknown_day_is_ambiguous():
    r = resolve("whenever", "10am", NOW, TZ)
    assert r.resolved_at is None
    assert "day" in r.ambiguous


def test_default_today_when_day_omitted_and_time_in_future():
    r = resolve(None, "10pm", NOW, TZ)
    # NOW is 9am; 10pm today is still in the future.
    assert r.resolved_at == datetime(2026, 6, 8, 22, 0, tzinfo=TZ)


def test_default_tomorrow_when_day_omitted_and_time_in_past():
    morning_after = NOW.replace(hour=15)  # 3pm
    r = resolve(None, "10am", morning_after, TZ)
    # 10am has passed today; roll to tomorrow.
    assert r.resolved_at == datetime(2026, 6, 9, 10, 0, tzinfo=TZ)


def test_absolute_iso_date():
    r = resolve("2026-07-04", "11:30am", NOW, TZ)
    assert r.resolved_at == datetime(2026, 7, 4, 11, 30, tzinfo=TZ)


def test_month_day_absolute():
    r = resolve("July 4", "11:30am", NOW, TZ)
    assert r.resolved_at == datetime(2026, 7, 4, 11, 30, tzinfo=TZ)


def test_naive_now_raises():
    naive = datetime(2026, 6, 8, 9, 0)
    with pytest.raises(ValueError):
        resolve("Thursday", "10am", naive, TZ)
