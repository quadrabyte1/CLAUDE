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


# ---------------------------------------------------------------------------
# v1.7 — roll-forward: bare month+day in the past → next year
#
# Design rule: when the hint gives a specific month+day but no year,
#   - month+day > today  → current year (still upcoming)
#   - month+day == today → current year (today itself)
#   - month+day < today  → current year + 1  (already passed → roll forward)
#
# Tests are written RED first (failing before the fix), then the
# implementation turns them GREEN. The red→green table is shown in the
# handoff report.
# ---------------------------------------------------------------------------


# Fixed reference time for all v1.7 roll-forward tests:
# Monday, 2026-09-21 11:02 EDT (the exact wall-clock of Thomas's live incident)
NOW_V17 = datetime(2026, 9, 21, 11, 2, tzinfo=TZ)


def test_v17_live_regression_sept20_rolls_to_next_year():
    """September 20th said on Sept 21 → 2027-09-20. Ambiguous must be empty."""
    r = resolve("September 20th", "10am", NOW_V17, TZ)
    assert r.ambiguous == [], f"expected no ambiguity, got {r.ambiguous}"
    assert r.resolved_at is not None
    assert r.resolved_at == datetime(2027, 9, 20, 10, 0, tzinfo=TZ)


def test_v17_not_yet_past_same_year():
    """September 22nd said on Sept 21 → 2026-09-22 (still upcoming, not rolled)."""
    r = resolve("September 22nd", "9am", NOW_V17, TZ)
    assert r.ambiguous == []
    assert r.resolved_at == datetime(2026, 9, 22, 9, 0, tzinfo=TZ)


def test_v17_same_day_no_roll():
    """September 21st said on Sept 21 → 2026-09-21 (today, not rolled)."""
    r = resolve("September 21st", "2pm", NOW_V17, TZ)
    assert r.ambiguous == []
    assert r.resolved_at == datetime(2026, 9, 21, 14, 0, tzinfo=TZ)


def test_v17_year_boundary_near_future():
    """January 1st said on Dec 31 → 2027-01-01 (rolls to next year)."""
    dec31 = datetime(2026, 12, 31, 10, 0, tzinfo=TZ)
    r = resolve("January 1st", "9am", dec31, TZ)
    assert r.ambiguous == []
    assert r.resolved_at == datetime(2027, 1, 1, 9, 0, tzinfo=TZ)


def test_v17_year_boundary_mid_year():
    """December 31st said on Jan 1 → 2026-12-31 (still upcoming, no roll)."""
    jan1 = datetime(2026, 1, 1, 10, 0, tzinfo=TZ)
    r = resolve("December 31st", "9am", jan1, TZ)
    assert r.ambiguous == []
    assert r.resolved_at == datetime(2026, 12, 31, 9, 0, tzinfo=TZ)


def test_v17_explicit_year_preserved():
    """September 20th 2027 said on Sept 21 2026 → keeps 2027, roll-logic doesn't fire."""
    r = resolve("September 20th 2027", "10am", NOW_V17, TZ)
    assert r.ambiguous == []
    assert r.resolved_at == datetime(2027, 9, 20, 10, 0, tzinfo=TZ)


def test_v17_feb29_edge_case():
    """February 29th said on 2026-03-01 (non-leap year).

    Decision: roll forward to the next leap year (2028-02-29).
    Rationale: silently degrading to Feb 28 would be a date error — the user
    said 'the 29th'.  Asking via ambiguous=['day'] would be correct but adds
    friction for a well-understood calendar edge.  Jumping to the actual next
    Feb 29 is the most honest interpretation: the user almost certainly means
    the leap-day appointment.

    This test locks the chosen behavior in.  See handoff report for the
    full decision record.
    """
    mar1_2026 = datetime(2026, 3, 1, 10, 0, tzinfo=TZ)
    r = resolve("February 29th", "noon", mar1_2026, TZ)
    assert r.ambiguous == []
    assert r.resolved_at == datetime(2028, 2, 29, 12, 0, tzinfo=TZ)


def test_v17_relative_day_untouched():
    """'tomorrow' still resolves via existing relative logic; roll-forward doesn't apply."""
    r = resolve("tomorrow", "9am", NOW_V17, TZ)
    assert r.ambiguous == []
    assert r.resolved_at == datetime(2026, 9, 22, 9, 0, tzinfo=TZ)


# Ordinal-suffix variations (1st, 2nd, 3rd, 5th … 11th … 21st … 23rd)
def test_v17_ordinal_first():
    r = resolve("October 1st", "9am", NOW_V17, TZ)
    assert r.ambiguous == []
    assert r.resolved_at == datetime(2026, 10, 1, 9, 0, tzinfo=TZ)


def test_v17_ordinal_second():
    jan2 = datetime(2026, 1, 2, 10, 0, tzinfo=TZ)
    r = resolve("January 2nd", "9am", jan2, TZ)
    assert r.ambiguous == []
    assert r.resolved_at == datetime(2026, 1, 2, 9, 0, tzinfo=TZ)


def test_v17_ordinal_third():
    r = resolve("October 3rd", "9am", NOW_V17, TZ)
    assert r.ambiguous == []
    assert r.resolved_at == datetime(2026, 10, 3, 9, 0, tzinfo=TZ)


def test_v17_no_ordinal_still_works():
    """Plain 'September 20' (no ordinal suffix) keeps working after the refactor."""
    r = resolve("September 20", "10am", NOW_V17, TZ)
    assert r.ambiguous == []
    assert r.resolved_at == datetime(2027, 9, 20, 10, 0, tzinfo=TZ)


# ===========================================================================
# TDD REGRESSION SUITE — v1.8.0 (must fail before fix, pass after fix)
#
# Design rule: resolve() gains an optional `verb` parameter.
# When verb="schedule" AND time_hint is a bare hour in {1,2,3,4,5} (no AM/PM,
# no minutes), resolve treats the hour as PM (adds 12). All other cases
# retain the current caution (ambiguous returned).
# ===========================================================================

# Reference "now" for the v1.8.0 tests — matches the live incident timestamp.
NOW_V18 = datetime(2026, 9, 21, 13, 36, tzinfo=TZ)  # 13:36 EDT on Sept 21


# --- Test 5: schedule + bare hour 3 → resolves to PM, no ambiguity

def test_v180_schedule_bare_hour_3_resolves_pm():
    """resolve(day_hint='September 20th', time_hint='3', verb='schedule', ...)
    must return datetime(2027, 9, 20, 15, 0, tzinfo=EDT) with ambiguous=[].

    This is the Jake's VCA fix: 3 → 15:00 (3 PM), not ambiguous.
    Roll-forward applies because Sept 20 < Sept 21 (today).
    """
    r = resolve("September 20th", "3", NOW_V18, TZ, verb="schedule")
    assert r.ambiguous == [], (
        f"verb=schedule + bare hour 3 must be unambiguous (PM assumed). "
        f"Got ambiguous={r.ambiguous!r}"
    )
    assert r.resolved_at is not None
    assert r.resolved_at == datetime(2027, 9, 20, 15, 0, tzinfo=TZ), (
        f"Expected 2027-09-20 15:00 EDT, got {r.resolved_at!r}"
    )


# --- Test 6: handle + bare hour 3 → ambiguous (old behavior kept)

def test_v180_handle_bare_hour_3_still_ambiguous():
    """resolve(time_hint='3', verb='handle', ...) must still return ambiguous=['time'].

    Reminders can legitimately be set for 3 AM (medication, alarms). Only
    verb=schedule gets PM inference.
    """
    r = resolve("September 20th", "3", NOW_V18, TZ, verb="handle")
    assert "time" in r.ambiguous, (
        f"verb=handle + bare hour must remain ambiguous. Got {r.ambiguous!r}"
    )
    assert r.resolved_at is None


# --- Test 7: schedule + bare hour 6 → still ambiguous (out of PM window)

def test_v180_schedule_bare_hour_6_still_ambiguous():
    """resolve(time_hint='6', verb='schedule', ...) must still return ambiguous=['time'].

    6 AM (breakfast call) vs 6 PM (after-work dinner) are both common — too
    close to call. The PM window is locked to hours 1-5 by design.
    """
    r = resolve("September 22nd", "6", NOW_V18, TZ, verb="schedule")
    assert "time" in r.ambiguous, (
        f"Hour 6 + verb=schedule must remain ambiguous (not in 1-5 window). "
        f"Got {r.ambiguous!r}"
    )
    assert r.resolved_at is None


# --- Test 8: schedule + explicit '3 AM' respects the user (no coercion to PM)

def test_v180_schedule_explicit_am_not_coerced():
    """resolve(time_hint='3 AM', verb='schedule', ...) must return 03:00, NOT 15:00.

    If the user said 'three AM' explicitly, we respect it. The PM inference
    only fires for BARE hours (no AM/PM marker). This is the regression guard
    against overzealous coercion.
    """
    r = resolve("September 22nd", "3 AM", NOW_V18, TZ, verb="schedule")
    assert r.ambiguous == [], f"Explicit AM should be unambiguous. Got {r.ambiguous!r}"
    assert r.resolved_at is not None
    assert r.resolved_at.hour == 3, (
        f"Explicit 3 AM must resolve to hour 3, not hour 15. Got hour={r.resolved_at.hour}"
    )


# --- Test 9: schedule + explicit '3 PM' resolves correctly (same as bare '3' but tested separately)

def test_v180_schedule_explicit_pm_resolves_correctly():
    """resolve(time_hint='3 PM', verb='schedule', ...) must return 15:00.

    Explicit PM continues to work as before. This test is distinct from the
    bare-'3' case to guard against the new code accidentally breaking explicit PM.
    """
    r = resolve("September 22nd", "3 PM", NOW_V18, TZ, verb="schedule")
    assert r.ambiguous == [], f"Explicit PM should be unambiguous. Got {r.ambiguous!r}"
    assert r.resolved_at is not None
    assert r.resolved_at.hour == 15, (
        f"Explicit 3 PM must resolve to hour 15. Got hour={r.resolved_at.hour}"
    )


# --- Regression guard: no-verb call still works (backward compatibility)

def test_v180_no_verb_bare_hour_still_ambiguous():
    """resolve() without verb= arg must retain the existing ambiguous behavior.

    Callers that don't pass verb= (existing tests, other verb handlers) must
    be unaffected by the new parameter. Default is None → existing logic.
    """
    r = resolve(None, "3", NOW_V18, TZ)  # no verb keyword
    assert "time" in r.ambiguous, (
        f"Without verb=, bare hour 3 must remain ambiguous. Got {r.ambiguous!r}"
    )
    assert r.resolved_at is None


# --- v1.8.0 Defensive test: resolve() output is always fresh — not tainted by
#     any caller-side ambiguous_fields list (e.g. from a legacy Sprite version).
#
# The assignment asks: confirm that the resolver's PM-inference for
# schedule+bare-1-5 produces ambiguous=[] even if a caller *had* built an
# ambiguous list with 'time' before calling resolve(). This is guaranteed by
# design — resolve() constructs its own list from resolution outcomes and never
# accepts an incoming ambiguous_fields parameter — but the test documents it
# explicitly as a contract.

def test_v180_defensive_resolve_output_not_tainted_by_legacy_ambiguous():
    """resolve(day_hint='Sept 20th', time_hint='3', verb='schedule', ...)
    returns ambiguous=[] regardless of what the caller believed was ambiguous
    before making the call (e.g. a legacy Sprite sending ambiguous=['time']).

    The resolver builds its own ambiguous list from outcomes — it does not
    accept or carry forward any caller-supplied ambiguous_fields. This test
    is the explicit contract lock.
    """
    # Simulate a legacy Sprite that passed time_hint='3' but had flagged
    # ambiguous_fields=['time'] on its side. The resolver call itself has no
    # such state — it resolves fresh from time_hint + verb.
    r = resolve("September 20th", "3", NOW_V18, TZ, verb="schedule")

    # Must resolve cleanly to PM with empty ambiguous list.
    assert r.ambiguous == [], (
        f"resolve() must produce ambiguous=[] for schedule+bare-3 "
        f"regardless of caller-side ambiguous state. Got {r.ambiguous!r}"
    )
    assert r.resolved_at is not None, "Must resolve to a datetime, not None"
    assert r.resolved_at.hour == 15, (
        f"Bare '3' with verb=schedule must resolve to 15:00 (3 PM). "
        f"Got hour={r.resolved_at.hour}"
    )
