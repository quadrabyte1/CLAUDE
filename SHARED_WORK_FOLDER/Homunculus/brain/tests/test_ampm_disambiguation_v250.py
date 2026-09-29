"""v2.5.0 AM/PM disambiguation — RED tests written first (TDD).

Three signals layered by precedence:

  1. Explicit AM/PM in memo              → keep current behavior (tested here as regression)
  2. Explicit qualifier in memo           → Signal C (e.g. "in the morning")
  3. Verb / meal / profession context    → Signal A (e.g. "breakfast", "plumber")
  4. schedule + hour 1-5 = PM rule       → existing v0.8.1 (regression test here)
  5. Speaker-time roll-forward           → Signal B (nearest future interpretation)
  6. None of above → clarifying question → existing fallback (regression test here)

These tests are written AGAINST THE CURRENT CODE BEFORE THE FEATURE IS ADDED.
They all start RED. After implementation they all go GREEN.
The existing 312 tests must stay green throughout.

Reference "now" values:
  NOW_10AM — 10:00 AM Eastern (morning context)
  NOW_5PM  — 17:00 Eastern (afternoon context)
  NOW_11PM — 23:00 Eastern (late night context)
  NOW_8AM  — 08:00 Eastern (morning, before 9 AM anchor)
"""

from __future__ import annotations

from datetime import datetime
from zoneinfo import ZoneInfo

import pytest

from homunculus_brain.date_resolver import resolve

TZ = ZoneInfo("America/New_York")

# Pinned reference datetimes for reproducible tests.
# These intentionally cover different parts of the day so Signal B (roll-forward)
# has well-defined expected outcomes.

NOW_10AM = datetime(2026, 9, 29, 10, 0, tzinfo=TZ)   # Tuesday 10:00 AM
NOW_5PM  = datetime(2026, 9, 29, 17, 0, tzinfo=TZ)   # Tuesday 17:00 (5 PM)
NOW_11PM = datetime(2026, 9, 29, 23, 0, tzinfo=TZ)   # Tuesday 23:00 (11 PM)
NOW_8AM  = datetime(2026, 9, 29, 8,  0, tzinfo=TZ)   # Tuesday  8:00 AM


# ===========================================================================
# SIGNAL A — Verb / meal / profession context
# ===========================================================================


class TestSignalA_Meals:
    """Meal context words override AM/PM ambiguity."""

    def test_breakfast_at_7_resolves_am(self):
        """'Schedule breakfast at 7' → 7 AM. Meal window: 5-11 AM."""
        r = resolve(None, "7", NOW_10AM, TZ, verb="schedule",
                    context_text="Schedule breakfast at 7")
        assert r.ambiguous == [], f"breakfast at 7 must resolve to AM, got {r.ambiguous}"
        assert r.resolved_at is not None
        assert r.resolved_at.hour == 7
        # 7 AM has passed (NOW_10AM = 10 AM), so rolls to tomorrow.
        assert r.resolved_at.date() == (NOW_10AM + __import__('datetime').timedelta(days=1)).date()

    def test_dinner_at_7_resolves_pm(self):
        """'Schedule dinner at 7' → 7 PM. Meal window: 5-9 PM."""
        r = resolve(None, "7", NOW_10AM, TZ, verb="schedule",
                    context_text="Schedule dinner at 7")
        assert r.ambiguous == [], f"dinner at 7 must resolve to PM, got {r.ambiguous}"
        assert r.resolved_at is not None
        assert r.resolved_at.hour == 19  # 7 PM

    def test_lunch_at_12_resolves_pm_default(self):
        """'Lunch at 12' → 12 PM (noon). Default lunch hour when no hour given but 12 matches noon."""
        r = resolve(None, "12", NOW_8AM, TZ, verb="schedule",
                    context_text="Schedule lunch at 12")
        assert r.ambiguous == []
        assert r.resolved_at is not None
        assert r.resolved_at.hour == 12  # noon

    def test_supper_at_6_resolves_pm(self):
        """'Supper at 6' → 6 PM. Supper is an alias for dinner."""
        r = resolve(None, "6", NOW_10AM, TZ, verb="schedule",
                    context_text="Supper at 6")
        assert r.ambiguous == [], f"supper at 6 must resolve to PM, got {r.ambiguous}"
        assert r.resolved_at is not None
        assert r.resolved_at.hour == 18  # 6 PM


class TestSignalA_Professions:
    """Profession / appointment keywords → business-hours PM for bare 1-5 range."""

    def test_plumber_at_3_resolves_pm(self):
        """'The plumber comes at 3' → 3 PM. Profession keyword → business hours bias."""
        r = resolve(None, "3", NOW_10AM, TZ, verb="schedule",
                    context_text="Remind me the plumber comes at 3")
        assert r.ambiguous == [], f"plumber at 3 must resolve PM, got {r.ambiguous}"
        assert r.resolved_at is not None
        assert r.resolved_at.hour == 15  # 3 PM

    def test_doctor_at_2_resolves_pm(self):
        """'Doctor appointment at 2' → 2 PM."""
        r = resolve(None, "2", NOW_10AM, TZ, verb="schedule",
                    context_text="Doctor appointment at 2")
        assert r.ambiguous == []
        assert r.resolved_at is not None
        assert r.resolved_at.hour == 14

    def test_meeting_at_9_no_context_neutral(self):
        """'Meeting at 9' with no other context → neutral (falls through to roll-forward).

        'Meeting' alone doesn't push to AM or PM — it's generic business context.
        The result should not be ambiguous (roll-forward picks the next future 9).
        """
        r = resolve(None, "9", NOW_10AM, TZ, verb="schedule",
                    context_text="Schedule call at 9")
        # 9 AM has passed (NOW_10AM = 10 AM), so next future 9 = 9 PM today.
        assert r.ambiguous == [], f"call at 9 should resolve via roll-forward, got {r.ambiguous}"
        assert r.resolved_at is not None
        assert r.resolved_at.hour == 21  # 9 PM (next future 9 after 10 AM)

    def test_appointment_at_3_resolves_pm(self):
        """'Appointment at 3' → 3 PM (appointment keyword → business hours)."""
        r = resolve(None, "3", NOW_10AM, TZ, verb="schedule",
                    context_text="Appointment at 3")
        assert r.ambiguous == []
        assert r.resolved_at is not None
        assert r.resolved_at.hour == 15


class TestSignalA_PersonalActivity:
    """Personal activity keywords bias toward morning or evening."""

    def test_wake_up_at_6_resolves_am(self):
        """'Wake up call at 6' → 6 AM. Wake-up is a morning keyword."""
        r = resolve(None, "6", NOW_10AM, TZ, verb="schedule",
                    context_text="Wake up call at 6")
        # 6 AM has passed (NOW_10AM), so rolls to tomorrow 6 AM.
        assert r.ambiguous == [], f"wake up at 6 must resolve to AM, got {r.ambiguous}"
        assert r.resolved_at is not None
        assert r.resolved_at.hour == 6  # 6 AM
        from datetime import timedelta
        assert r.resolved_at.date() == (NOW_10AM + timedelta(days=1)).date()

    def test_gym_at_6_resolves_am(self):
        """'Gym at 6' → 6 AM (gym = morning activity)."""
        r = resolve(None, "6", NOW_10AM, TZ, verb="schedule",
                    context_text="Gym at 6")
        assert r.ambiguous == [], f"gym at 6 must resolve to AM, got {r.ambiguous}"
        assert r.resolved_at is not None
        assert r.resolved_at.hour == 6

    def test_bedtime_meds_at_9_resolves_pm(self):
        """'Bedtime meds at 9' → 9 PM. Bedtime keyword → evening bias."""
        r = resolve(None, "9", NOW_10AM, TZ, verb="schedule",
                    context_text="Bedtime meds at 9")
        assert r.ambiguous == [], f"bedtime meds at 9 must resolve to PM, got {r.ambiguous}"
        assert r.resolved_at is not None
        assert r.resolved_at.hour == 21  # 9 PM

    def test_workout_at_7_resolves_am(self):
        """'Workout at 7' → 7 AM (workout = morning bias)."""
        r = resolve(None, "7", NOW_10AM, TZ, verb="schedule",
                    context_text="Workout at 7")
        assert r.ambiguous == [], f"workout at 7 must resolve AM, got {r.ambiguous}"
        assert r.resolved_at is not None
        assert r.resolved_at.hour == 7


class TestSignalA_NeutralContext:
    """Neutral / missing context falls through to Signal B (roll-forward), not asking."""

    def test_neutral_verb_at_3_falls_through(self):
        """'Do the thing at 3' — no meal/profession/activity keyword → Signal A does not fire.

        Falls through to Signal B (roll-forward). Must NOT ask AM/PM question for
        verb=schedule + bare hour in 1-5 range (covered by existing v0.8.1 rule).
        """
        r = resolve(None, "3", NOW_10AM, TZ, verb="schedule",
                    context_text="Do the thing at 3")
        # v0.8.1 rule: schedule + bare 1-5 → PM assumed. So this resolves to 3 PM.
        assert r.ambiguous == []
        assert r.resolved_at is not None
        assert r.resolved_at.hour == 15  # v0.8.1 PM assumption

    def test_neutral_verb_handle_at_3_falls_to_rollforward(self):
        """'Do the thing at 3' with verb=handle — falls to Signal B."""
        r = resolve(None, "3", NOW_10AM, TZ, verb="handle",
                    context_text="Do the thing at 3")
        # handle verb doesn't get v0.8.1 PM rule, and no keyword → Signal B fires.
        # 10 AM now, next future 3 = 3 PM today.
        assert r.ambiguous == [], f"roll-forward should resolve, got {r.ambiguous}"
        assert r.resolved_at is not None
        assert r.resolved_at.hour == 15  # 3 PM (next future 3 from 10 AM)


# ===========================================================================
# SIGNAL B — Speaker-time roll-forward
# ===========================================================================


class TestSignalB_RollForward:
    """Roll-forward: pick the nearest future interpretation of a bare hour."""

    def test_now_10am_at_3_resolves_3pm_today(self):
        """Current time 10 AM, 'at 3' → 3 PM today (next future 3)."""
        r = resolve(None, "3", NOW_10AM, TZ, verb="handle")
        assert r.ambiguous == [], f"roll-forward should work, got {r.ambiguous}"
        assert r.resolved_at is not None
        assert r.resolved_at.date() == NOW_10AM.date()
        assert r.resolved_at.hour == 15  # 3 PM

    def test_now_5pm_at_3_resolves_3pm_tomorrow(self):
        """Current time 5 PM, 'at 3' with no keyword → nearest future 3.

        Decision: skip sleep hours (12 AM - 5 AM) to avoid suggesting 3 AM tomorrow
        during the night-time window. Next non-sleep future 3 after 5 PM = 3 PM tomorrow.

        Sleep window: 12:00 AM (0) through 5:59 AM (5). Hours 0-5 are skipped.
        Candidates in order: 3 PM today (passed), 3 AM tomorrow (sleep window, skip),
        3 PM tomorrow (pick this).
        """
        r = resolve(None, "3", NOW_5PM, TZ, verb="handle")
        assert r.ambiguous == [], f"roll-forward should skip sleep window, got {r.ambiguous}"
        assert r.resolved_at is not None
        assert r.resolved_at.hour == 15  # 3 PM
        from datetime import timedelta
        assert r.resolved_at.date() == (NOW_5PM + timedelta(days=1)).date()  # tomorrow

    def test_now_11pm_at_3_resolves_3am_tomorrow(self):
        """Current time 11 PM, 'at 3' → 3 AM tomorrow.

        At 11 PM, 3 AM tomorrow is only 4 hours away and a legitimate near-future
        time (alarm, medication). The sleep window starts at midnight; at 11 PM the
        user asking about '3' is more likely asking about tomorrow morning 3 AM than
        3 PM tomorrow. Decision: 11 PM is close enough to midnight that 3 AM tomorrow
        IS a reasonable next future (unlike 5 PM where it would be weird).

        3 AM tomorrow < 3 PM tomorrow in wall-clock distance from 11 PM.
        """
        r = resolve(None, "3", NOW_11PM, TZ, verb="handle")
        assert r.ambiguous == [], f"roll-forward should work at 11 PM, got {r.ambiguous}"
        assert r.resolved_at is not None
        assert r.resolved_at.hour == 3  # 3 AM
        from datetime import timedelta
        assert r.resolved_at.date() == (NOW_11PM + timedelta(days=1)).date()

    def test_now_8am_at_6_resolves_6pm_today(self):
        """Current time 8 AM, 'at 6' → 6 PM today.

        Both 6 AM (past) and 6 PM (future) are same-day candidates; 6 AM has passed,
        so the earliest future 6 is 6 PM today.
        """
        r = resolve(None, "6", NOW_8AM, TZ, verb="handle")
        assert r.ambiguous == [], f"roll-forward at 6 should work, got {r.ambiguous}"
        assert r.resolved_at is not None
        assert r.resolved_at.date() == NOW_8AM.date()
        assert r.resolved_at.hour == 18  # 6 PM

    def test_roll_forward_with_explicit_day_does_not_guess(self):
        """When a day is given and time is bare, roll-forward applies within that day.

        'Tomorrow at 3' → 3 PM tomorrow (closest future interpretation on that day).
        """
        r = resolve("tomorrow", "3", NOW_10AM, TZ, verb="handle")
        # Tomorrow at 3 AM vs 3 PM — both are future. Pick nearest: 3 AM tomorrow first,
        # but sleep-window logic skips it if defined. Decision: for an explicit-day request
        # the sleep-skip doesn't apply (the user explicitly said "tomorrow at 3").
        # Pick nearest future on that day = 3 AM tomorrow if < sleep window, else 3 PM.
        # Per our rule: sleep skip applies globally. 3 AM is in sleep window → skip to 3 PM.
        assert r.ambiguous == []
        assert r.resolved_at is not None
        assert r.resolved_at.hour == 15  # 3 PM (sleep-skip applied)

    def test_roll_forward_does_not_fire_when_explicit_ampm(self):
        """When AM/PM is explicit, roll-forward is irrelevant — explicit wins."""
        r = resolve(None, "3pm", NOW_10AM, TZ, verb="handle")
        assert r.ambiguous == []
        assert r.resolved_at is not None
        assert r.resolved_at.hour == 15  # honors explicit PM


# ===========================================================================
# SIGNAL C — Natural qualifier vocabulary
# ===========================================================================


class TestSignalC_Qualifiers:
    """Natural qualifier phrases override AM/PM ambiguity."""

    def test_in_the_morning_resolves_am(self):
        """'Meeting at 9 in the morning' → 9 AM."""
        r = resolve(None, "9", NOW_5PM, TZ, verb="schedule",
                    context_text="Meeting at 9 in the morning")
        assert r.ambiguous == [], f"'in the morning' must resolve AM, got {r.ambiguous}"
        assert r.resolved_at is not None
        assert r.resolved_at.hour == 9

    def test_tonight_resolves_pm(self):
        """'Call mom at 8 tonight' → 8 PM today."""
        r = resolve(None, "8", NOW_5PM, TZ, verb="schedule",
                    context_text="Call mom at 8 tonight")
        assert r.ambiguous == [], f"'tonight' must resolve PM, got {r.ambiguous}"
        assert r.resolved_at is not None
        assert r.resolved_at.hour == 20  # 8 PM
        assert r.resolved_at.date() == NOW_5PM.date()  # today

    def test_in_the_evening_resolves_pm(self):
        """'Dinner at 7 in the evening' → 7 PM."""
        r = resolve(None, "7", NOW_10AM, TZ, verb="schedule",
                    context_text="Dinner at 7 in the evening")
        assert r.ambiguous == []
        assert r.resolved_at is not None
        assert r.resolved_at.hour == 19  # 7 PM

    def test_in_the_afternoon_resolves_pm(self):
        """'Meeting at 2 in the afternoon' → 2 PM."""
        r = resolve(None, "2", NOW_10AM, TZ, verb="schedule",
                    context_text="Meeting at 2 in the afternoon")
        assert r.ambiguous == []
        assert r.resolved_at is not None
        assert r.resolved_at.hour == 14  # 2 PM

    def test_this_morning_resolves_am(self):
        """'Reminder at 7 this morning' → 7 AM today (or tomorrow if passed)."""
        r = resolve(None, "7", NOW_5PM, TZ, verb="handle",
                    context_text="Reminder at 7 this morning")
        # 7 AM today has passed (NOW_5PM = 5 PM). Roll to tomorrow 7 AM.
        assert r.ambiguous == []
        assert r.resolved_at is not None
        assert r.resolved_at.hour == 7
        from datetime import timedelta
        assert r.resolved_at.date() == (NOW_5PM + timedelta(days=1)).date()

    def test_this_evening_resolves_pm(self):
        """'Call at 8 this evening' → 8 PM today."""
        r = resolve(None, "8", NOW_10AM, TZ, verb="schedule",
                    context_text="Call at 8 this evening")
        assert r.ambiguous == []
        assert r.resolved_at is not None
        assert r.resolved_at.hour == 20  # 8 PM

    def test_tomorrow_morning_resolves_am_next_day(self):
        """'Doctor tomorrow morning at 10' → 10 AM tomorrow."""
        r = resolve("tomorrow", "10", NOW_10AM, TZ, verb="schedule",
                    context_text="Doctor tomorrow morning at 10")
        assert r.ambiguous == []
        assert r.resolved_at is not None
        assert r.resolved_at.hour == 10
        from datetime import timedelta
        assert r.resolved_at.date() == (NOW_10AM + timedelta(days=1)).date()

    def test_tomorrow_night_resolves_pm_next_day(self):
        """'Meeting tomorrow night at 9' → 9 PM tomorrow."""
        r = resolve("tomorrow", "9", NOW_10AM, TZ, verb="schedule",
                    context_text="Meeting tomorrow night at 9")
        assert r.ambiguous == []
        assert r.resolved_at is not None
        assert r.resolved_at.hour == 21  # 9 PM
        from datetime import timedelta
        assert r.resolved_at.date() == (NOW_10AM + timedelta(days=1)).date()

    def test_noon_resolves_12pm(self):
        """'Lunch at noon' — 'noon' is already a named anchor but verify it still works."""
        r = resolve(None, "noon", NOW_10AM, TZ, verb="schedule",
                    context_text="Lunch at noon")
        assert r.ambiguous == []
        assert r.resolved_at is not None
        assert r.resolved_at.hour == 12

    def test_at_night_resolves_pm(self):
        """'Reminder at 10 at night' → 10 PM."""
        r = resolve(None, "10", NOW_10AM, TZ, verb="handle",
                    context_text="Reminder at 10 at night")
        assert r.ambiguous == []
        assert r.resolved_at is not None
        assert r.resolved_at.hour == 22  # 10 PM

    def test_late_morning_resolves_am(self):
        """'Schedule call late morning at 11' → 11 AM."""
        r = resolve(None, "11", NOW_8AM, TZ, verb="schedule",
                    context_text="Schedule call late morning at 11")
        assert r.ambiguous == []
        assert r.resolved_at is not None
        assert r.resolved_at.hour == 11

    def test_early_afternoon_resolves_pm(self):
        """'Meeting early afternoon at 1' → 1 PM."""
        r = resolve(None, "1", NOW_10AM, TZ, verb="schedule",
                    context_text="Meeting early afternoon at 1")
        assert r.ambiguous == []
        assert r.resolved_at is not None
        assert r.resolved_at.hour == 13  # 1 PM

    def test_qualifier_combined_with_verb_context(self):
        """'Schedule dinner at 7 in the evening' → 7 PM. Both Signal A and C agree."""
        r = resolve(None, "7", NOW_10AM, TZ, verb="schedule",
                    context_text="Schedule dinner at 7 in the evening")
        assert r.ambiguous == []
        assert r.resolved_at is not None
        assert r.resolved_at.hour == 19  # 7 PM


# ===========================================================================
# PRECEDENCE TESTS — higher signals override lower ones
# ===========================================================================


class TestPrecedence:
    """Explicit AM/PM wins over everything; qualifiers win over verb context; etc."""

    def test_explicit_ampm_beats_qualifier(self):
        """'Meeting at 3 PM in the morning' — contradictory. Explicit PM wins.

        The phrase 'in the morning' is contradicted by 'PM'. Explicit marker is
        authoritative — result is 3 PM, not 3 AM.
        """
        r = resolve(None, "3 PM", NOW_10AM, TZ, verb="schedule",
                    context_text="Meeting at 3 PM in the morning")
        assert r.ambiguous == []
        assert r.resolved_at is not None
        assert r.resolved_at.hour == 15  # explicit PM wins

    def test_explicit_ampm_beats_meal_context(self):
        """'Breakfast at 8 PM' — explicit PM wins over breakfast AM context."""
        r = resolve(None, "8 PM", NOW_10AM, TZ, verb="schedule",
                    context_text="Breakfast at 8 PM")
        assert r.ambiguous == []
        assert r.resolved_at is not None
        assert r.resolved_at.hour == 20  # explicit PM wins

    def test_qualifier_beats_verb_context(self):
        """'Dinner at 7 in the morning' — qualifier 'morning' overrides dinner PM context.

        Signal C (qualifier) precedes Signal A (verb context) in the stack.
        'in the morning' is an explicit phrase that wins over meal default.
        Result: 7 AM.
        """
        r = resolve(None, "7", NOW_10AM, TZ, verb="schedule",
                    context_text="Dinner at 7 in the morning")
        assert r.ambiguous == []
        assert r.resolved_at is not None
        assert r.resolved_at.hour == 7  # qualifier wins over dinner context

    def test_signal_a_beats_rollforward(self):
        """'Dinner at 3' — verb context (Signal A) assigns PM before roll-forward fires.

        Roll-forward would also pick 3 PM here (since 10 AM < 3 PM), but Signal A
        locks in PM first. Outcome is the same; test documents the ordering.
        """
        r = resolve(None, "3", NOW_10AM, TZ, verb="schedule",
                    context_text="Dinner at 3")
        assert r.ambiguous == []
        assert r.resolved_at is not None
        assert r.resolved_at.hour == 15  # 3 PM

    def test_meeting_at_6_rollforward_no_keyword(self):
        """'Meeting at 6' — 'meeting' is neutral, no qualifier → roll-forward (Signal B).

        NOW_10AM = 10 AM. 6 AM has passed. Next future 6 = 6 PM today.
        """
        r = resolve(None, "6", NOW_10AM, TZ, verb="schedule",
                    context_text="Meeting at 6")
        assert r.ambiguous == []
        assert r.resolved_at is not None
        assert r.resolved_at.hour == 18  # 6 PM via roll-forward

    def test_schedule_call_at_9_rollforward(self):
        """'Schedule call at 9' — depends on NOW.

        NOW_10AM = 10 AM. 9 AM has just passed. Next future 9 = 9 PM today.
        """
        r = resolve(None, "9", NOW_10AM, TZ, verb="schedule",
                    context_text="Schedule call at 9")
        assert r.ambiguous == []
        assert r.resolved_at is not None
        assert r.resolved_at.hour == 21  # 9 PM via roll-forward

    def test_breakfast_context_overrides_v081_schedule_pm_rule(self):
        """'Schedule breakfast at 3' — breakfast AM beats the v0.8.1 schedule+1-5=PM rule.

        Signal A fires first (breakfast → AM). The v0.8.1 rule is a tie-breaker that
        only applies when no other signal fires.
        """
        r = resolve(None, "3", NOW_10AM, TZ, verb="schedule",
                    context_text="Schedule breakfast at 3")
        # Breakfast window is 5-11 AM → 3 is below that window, but meal default
        # is AM bias. So 3 AM (not 3 PM).
        # 3 AM has passed (NOW_10AM = 10 AM) → roll to tomorrow 3 AM.
        assert r.ambiguous == []
        assert r.resolved_at is not None
        assert r.resolved_at.hour == 3  # AM, not PM


# ===========================================================================
# REGRESSION PRESERVATION — existing behavior must stay green
# ===========================================================================


class TestRegressions:
    """The new signals must not break existing behavior."""

    def test_v081_schedule_bare_1_still_pm(self):
        """v0.8.1: schedule + bare hour 1 → PM still works without context."""
        r = resolve(None, "1", NOW_10AM, TZ, verb="schedule")
        assert r.ambiguous == []
        assert r.resolved_at is not None
        assert r.resolved_at.hour == 13  # 1 PM

    def test_v081_schedule_bare_5_still_pm(self):
        """v0.8.1: schedule + bare hour 5 → PM still works without context."""
        r = resolve(None, "5", NOW_10AM, TZ, verb="schedule")
        assert r.ambiguous == []
        assert r.resolved_at is not None
        assert r.resolved_at.hour == 17  # 5 PM

    def test_explicit_am_still_resolves(self):
        """Explicit 9 AM still resolves unambiguously."""
        r = resolve(None, "9am", NOW_10AM, TZ, verb="schedule")
        # 9 AM has passed (10 AM now), rolls to tomorrow.
        assert r.ambiguous == []
        assert r.resolved_at is not None
        assert r.resolved_at.hour == 9

    def test_explicit_pm_still_resolves(self):
        """Explicit 3 PM still resolves unambiguously."""
        r = resolve(None, "3pm", NOW_10AM, TZ, verb="schedule")
        assert r.ambiguous == []
        assert r.resolved_at is not None
        assert r.resolved_at.hour == 15

    def test_noon_anchor_still_works(self):
        """Named anchor 'noon' is unaffected."""
        r = resolve(None, "noon", NOW_10AM, TZ)
        assert r.ambiguous == []
        assert r.resolved_at is not None
        assert r.resolved_at.hour == 12

    def test_oclock_normalization_intact(self):
        """v2.3.0 o'clock stripping still works."""
        r = resolve("today", "9 o'clock a.m.", NOW_10AM, TZ)
        assert r.ambiguous == []
        assert r.resolved_at is not None
        assert r.resolved_at.hour == 9  # AM from explicit qualifier in time_hint

    def test_no_context_handle_at_6_no_longer_asks_ampm(self):
        """After v2.5.0, bare hour 6 with verb=handle no longer produces a clarifying
        question — roll-forward (Signal B) resolves it.

        Before v2.5.0: bare 6 + handle → ambiguous=['time'] (question asked).
        After v2.5.0: roll-forward picks the next future 6 (6 PM today, since 10 AM < 6 PM).
        This test IS the main regression target — it was breaking Thomas's flow.
        """
        r = resolve(None, "6", NOW_10AM, TZ, verb="handle")
        assert r.ambiguous == [], (
            f"After v2.5.0, bare 6 with handle must resolve via roll-forward "
            f"(no clarifying question). Got ambiguous={r.ambiguous!r}"
        )
        assert r.resolved_at is not None
        assert r.resolved_at.hour == 18  # 6 PM, next future 6 from 10 AM

    def test_no_context_schedule_at_6_no_longer_asks_ampm(self):
        """After v2.5.0, bare hour 6 with verb=schedule resolves via roll-forward.

        Schedule verb + hour 6 used to ask AM/PM (outside 1-5 PM window).
        After v2.5.0, roll-forward fires: next future 6 from 10 AM = 6 PM today.
        """
        r = resolve(None, "6", NOW_10AM, TZ, verb="schedule")
        assert r.ambiguous == [], (
            f"After v2.5.0, schedule at bare 6 must resolve via roll-forward. "
            f"Got ambiguous={r.ambiguous!r}"
        )
        assert r.resolved_at is not None
        assert r.resolved_at.hour == 18  # 6 PM via roll-forward

    def test_legacy_no_context_no_verb_bare_9_resolves(self):
        """After v2.5.0, bare 9 with no verb and no context resolves via roll-forward.

        Before v2.5.0: bare 9, no verb → ambiguous=['time'].
        After v2.5.0: roll-forward → next future 9 from NOW_10AM (10 AM) = 9 PM today.
        """
        r = resolve(None, "9", NOW_10AM, TZ)
        assert r.ambiguous == [], (
            f"After v2.5.0, bare 9 with no context must resolve via roll-forward. "
            f"Got ambiguous={r.ambiguous!r}"
        )
        assert r.resolved_at is not None
        assert r.resolved_at.hour == 21  # 9 PM


# ===========================================================================
# THOMAS'S TEST DRIVE SCENARIOS (from the assignment)
# ===========================================================================


class TestThomasTestDrive:
    """The three 'say this out loud' test scenarios from the assignment."""

    def test_schedule_dinner_at_7(self):
        """'Schedule dinner at 7' → 7 PM without clarifying question."""
        r = resolve(None, "7", NOW_10AM, TZ, verb="schedule",
                    context_text="Schedule dinner at 7")
        assert r.ambiguous == [], "Thomas's test: dinner at 7 must NOT ask AM/PM"
        assert r.resolved_at is not None
        assert r.resolved_at.hour == 19  # 7 PM

    def test_meeting_at_3_during_afternoon(self):
        """'Meeting at 3' during afternoon (NOW_5PM) — expect 3 PM tomorrow (5 PM > 3 PM)."""
        r = resolve(None, "3", NOW_5PM, TZ, verb="schedule",
                    context_text="Meeting at 3")
        assert r.ambiguous == [], "Thomas's test: meeting at 3 during afternoon must resolve"
        assert r.resolved_at is not None
        assert r.resolved_at.hour == 15  # 3 PM
        from datetime import timedelta
        assert r.resolved_at.date() == (NOW_5PM + timedelta(days=1)).date()  # tomorrow

    def test_at_3_no_verb_midday_rollforward(self):
        """'At 3' with no verb during midday (NOW_10AM) → roll-forward to next future 3.

        10 AM now. 3 AM passed. 3 PM not yet arrived. Next future 3 = 3 PM today.
        Note: no verb given — resolver must handle context_text=None gracefully.
        """
        r = resolve(None, "3", NOW_10AM, TZ)
        assert r.ambiguous == [], "Thomas's test: 'at 3' mid-morning must roll to 3 PM"
        assert r.resolved_at is not None
        assert r.resolved_at.hour == 15  # 3 PM
        assert r.resolved_at.date() == NOW_10AM.date()
