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


# --- v1.2.2 regression: ambiguous-time bug ("Feed Jake at 5:35") -------------
#
# Bug observed 2026-06-10 17:31:40 EDT: utterance "Feed Jake at 5:35" was
# resolved as Thursday June 11 at 05:35 AM. The user almost certainly meant
# 17:35 today (4 minutes from "now"). Two problems:
#   1. AM/PM was ambiguous and the resolver silently chose AM.
#   2. The chosen default ("AM tomorrow") is ~12 hours further away than the
#      nearest-future interpretation.
# Per the locked UX rule ("Missing info: one specific clarifying question")
# and Rune's persona ("ambiguous_fields is a first-class output; never
# silently guess"), a bare hour:minute in the 1-12 range with no AM/PM
# marker and no 24-hour context (hour 0 or 13+) must surface as ambiguous
# and the router must ask. Tests below cover the regression and the edges
# we must NOT regress (explicit am/pm, 24-hour times, named time-of-day).


def test_bare_hour_minute_no_ampm_is_ambiguous():
    # The bug case: "5:35" with no AM/PM marker. Hour 5 could be either,
    # so we don't guess.
    r = resolve(None, "5:35", NOW, TZ)
    assert r.resolved_at is None
    assert "time" in r.ambiguous


def test_bare_hour_no_minute_no_ampm_is_ambiguous():
    # "5" alone (e.g. "feed Jake at 5") is ambiguous for the same reason.
    r = resolve(None, "5", NOW, TZ)
    assert r.resolved_at is None
    assert "time" in r.ambiguous


def test_bare_hour_minute_with_explicit_pm_is_unambiguous():
    # Regression guard: the boss's retry "5:35pm" must still resolve cleanly.
    r = resolve(None, "5:35pm", NOW, TZ)
    assert r.resolved_at == datetime(2026, 6, 8, 17, 35, tzinfo=TZ)
    assert r.ambiguous == []


def test_bare_hour_minute_with_explicit_am_is_unambiguous():
    r = resolve(None, "5:35am", NOW, TZ)
    # NOW is 9 AM Monday; 5:35 AM has passed today, default-day path rolls
    # to tomorrow.
    assert r.resolved_at == datetime(2026, 6, 9, 5, 35, tzinfo=TZ)
    assert r.ambiguous == []


def test_24_hour_time_is_unambiguous():
    # "17:35" is unambiguous — hour ≥ 13 forces a 24-hour reading.
    r = resolve(None, "17:35", NOW, TZ)
    assert r.resolved_at == datetime(2026, 6, 8, 17, 35, tzinfo=TZ)
    assert r.ambiguous == []


def test_hour_zero_is_unambiguous_24_hour():
    # "0:30" is unambiguous (it cannot be a 12-hour clock reading).
    r = resolve(None, "0:30", NOW, TZ)
    # 0:30 has passed today, default-day path rolls to tomorrow.
    assert r.resolved_at == datetime(2026, 6, 9, 0, 30, tzinfo=TZ)
    assert r.ambiguous == []


def test_noon_and_midnight_are_unambiguous():
    # Named anchors are not affected by the new rule.
    r_noon = resolve(None, "noon", NOW, TZ)
    assert r_noon.resolved_at == datetime(2026, 6, 8, 12, 0, tzinfo=TZ)
    assert r_noon.ambiguous == []


def test_twelve_with_ampm_still_works():
    # Edge: "12:30am" → 00:30, "12:30pm" → 12:30. Already covered by existing
    # logic; this guards against the new rule mis-flagging them.
    r_pm = resolve("today", "12:30pm", NOW, TZ)
    assert r_pm.resolved_at == datetime(2026, 6, 8, 12, 30, tzinfo=TZ)
    assert r_pm.ambiguous == []
    r_am = resolve("today", "12:30am", NOW, TZ)
    assert r_am.resolved_at == datetime(2026, 6, 8, 0, 30, tzinfo=TZ)
    assert r_am.ambiguous == []
