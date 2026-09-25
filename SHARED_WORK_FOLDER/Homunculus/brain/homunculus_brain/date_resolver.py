"""Deterministic date/time resolution.

The LLM is good at extracting the *words* ("Thursday at 10am", "tomorrow
morning"). It is unreliable at turning those words into an actual calendar
date. Everything below is pure Python so the math is testable and never
guesses.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from datetime import datetime, time, timedelta
from typing import Optional
from zoneinfo import ZoneInfo


WEEKDAYS = {
    "monday": 0, "mon": 0,
    "tuesday": 1, "tue": 1, "tues": 1,
    "wednesday": 2, "wed": 2,
    "thursday": 3, "thu": 3, "thurs": 3,
    "friday": 4, "fri": 4,
    "saturday": 5, "sat": 5,
    "sunday": 6, "sun": 6,
}

TIME_OF_DAY_ANCHORS = {
    # Hour-only anchors used when only a fuzzy time-of-day is given.
    "morning": None,    # filled in from config morning_anchor_hour
    "afternoon": 13,
    "evening": 18,
    "night": 21,
    "noon": 12,
    "midnight": 0,
}


@dataclass
class ResolvedDateTime:
    resolved_at: Optional[datetime]
    ambiguous: list[str] = field(default_factory=list)  # e.g. ["day", "time"]
    note: Optional[str] = None  # human-readable explanation of the resolution


def _normalize(s: Optional[str]) -> str:
    return (s or "").strip().lower()


def resolve(
    day_hint: Optional[str],
    time_hint: Optional[str],
    now: datetime,
    tz: ZoneInfo,
    morning_anchor_hour: int = 9,
    verb: Optional[str] = None,
) -> ResolvedDateTime:
    """Combine day + time hints into a single tz-aware datetime.

    `now` must be tz-aware. Returns an `ambiguous` list naming any field we
    couldn't pin down; the router uses that to decide whether to ask a
    clarifying question.

    ``verb`` is optional context from the capture verb (e.g. "schedule",
    "handle", "remind"). When ``verb == "schedule"`` and ``time_hint`` is a
    bare hour in {1, 2, 3, 4, 5} with no AM/PM marker, the resolver assumes
    PM (adds 12) instead of flagging ambiguity. The user's explicit direction:
    "if I put something at 3 and I meant 3 AM, that's on me to correct it."
    Hours 6-12 remain ambiguous for all verbs (6 AM vs 6 PM are both common).
    Non-schedule verbs (handle, remind, etc.) keep the original caution for all
    bare hours — reminders can legitimately fire at 3 AM.
    """
    if now.tzinfo is None:
        raise ValueError("now must be tz-aware")

    now_local = now.astimezone(tz)

    resolved_date, day_ambiguous, day_note = _resolve_day(day_hint, now_local)
    resolved_time, time_ambiguous, time_note = _resolve_time(
        time_hint, morning_anchor_hour, verb=verb
    )

    ambiguous: list[str] = []
    if day_ambiguous:
        ambiguous.append("day")
    if time_ambiguous:
        ambiguous.append("time")

    if resolved_date is None or resolved_time is None:
        return ResolvedDateTime(
            resolved_at=None,
            ambiguous=ambiguous,
            note=(day_note or "") + ((" " + time_note) if time_note else ""),
        )

    combined = datetime.combine(resolved_date, resolved_time, tzinfo=tz)

    # If only a time was given and the time has already passed today, roll to
    # tomorrow. Don't roll if the user gave an explicit day.
    if day_hint is None and combined < now_local:
        combined = combined + timedelta(days=1)

    return ResolvedDateTime(
        resolved_at=combined,
        ambiguous=ambiguous,
        note=((day_note or "") + ((" " + time_note) if time_note else "")).strip() or None,
    )


def _resolve_day(day_hint: Optional[str], now_local: datetime):
    hint = _normalize(day_hint)

    if not hint:
        # Default: today. Caller may flag this as ambiguous if there was no
        # day in the utterance at all.
        return now_local.date(), False, "defaulted to today"

    if hint in ("today",):
        return now_local.date(), False, "today"

    if hint in ("tomorrow", "tmrw", "tmw"):
        return (now_local + timedelta(days=1)).date(), False, "tomorrow"

    if hint in ("yesterday",):
        return (now_local - timedelta(days=1)).date(), False, "yesterday"

    # Strip an optional "this " / "next " modifier.
    modifier: Optional[str] = None
    for prefix in ("this ", "next ", "coming "):
        if hint.startswith(prefix):
            modifier = prefix.strip()
            hint = hint[len(prefix):]
            break

    weekday = WEEKDAYS.get(hint)
    if weekday is None:
        # Try matching an absolute date like "2026-06-12" or "june 12".
        absolute = _try_absolute_date(hint, now_local)
        if absolute is not None:
            return absolute, False, f"parsed absolute date {absolute}"
        return None, True, f"could not parse day '{day_hint}'"

    today_weekday = now_local.weekday()
    days_ahead = (weekday - today_weekday) % 7

    if days_ahead == 0:
        # User said the name of today's weekday. Mori's rule: prefer today if
        # before noon, otherwise next week. Same intent here.
        if modifier == "next":
            days_ahead = 7
        elif now_local.hour >= 12:
            days_ahead = 7

    if modifier == "next" and days_ahead < 7:
        # "next Tuesday" said on Monday should be a week-and-a-day out, not
        # tomorrow. Add a week.
        days_ahead += 7

    return (
        (now_local + timedelta(days=days_ahead)).date(),
        False,
        f"resolved '{day_hint}' -> {(now_local + timedelta(days=days_ahead)).date()}",
    )


_TIME_REGEX = re.compile(
    r"""^\s*
        (?P<hour>\d{1,2})
        (?:[:.](?P<minute>\d{2}))?
        \s*
        (?P<ampm>am|pm|a\.m\.|p\.m\.)?
        \s*$
    """,
    re.IGNORECASE | re.VERBOSE,
)

# v2.3.0 — strip "o'clock" (and variants) from time_hint before parsing.
# "9 o'clock a.m." → "9 a.m.", "3 o'clock p.m." → "3 p.m.",
# "9 o'clock" → "9" (which is then correctly flagged as ambiguous without AM/PM).
# Variants: "o'clock", "oclock", "o clock" — all case-insensitive.
# The word sits between the digit and the AM/PM qualifier and confuses
# _TIME_REGEX which expects the format: digit [colon minute] [AM/PM].
_OCLOCK_RE = re.compile(r"\bo'?clock\b", re.IGNORECASE)

_SCHEDULE_PM_HOURS = frozenset({1, 2, 3, 4, 5})


def _resolve_time(time_hint: Optional[str], morning_anchor_hour: int, verb: Optional[str] = None):
    # v2.3.0 — strip "o'clock" variants before normalizing so that
    # "9 o'clock a.m." → "9 a.m." and "3 o'clock p.m." → "3 p.m."
    # The word sits between the digit and the AM/PM qualifier and confuses
    # _TIME_REGEX.  Stripping it (case-insensitive) is safe because it carries
    # no time information beyond marking the preceding digit as an hour.
    if time_hint:
        time_hint = _OCLOCK_RE.sub("", time_hint).strip()

    hint = _normalize(time_hint)

    if not hint:
        return None, True, "no time given"

    if hint in TIME_OF_DAY_ANCHORS:
        if hint == "morning":
            return time(hour=morning_anchor_hour), False, f"morning -> {morning_anchor_hour:02d}:00"
        return time(hour=TIME_OF_DAY_ANCHORS[hint]), False, f"{hint} -> {TIME_OF_DAY_ANCHORS[hint]:02d}:00"

    match = _TIME_REGEX.match(hint)
    if not match:
        return None, True, f"could not parse time '{time_hint}'"

    hour = int(match.group("hour"))
    minute = int(match.group("minute") or 0)
    ampm = (match.group("ampm") or "").replace(".", "").lower()

    # v1.8.0 — schedule verb PM inference for bare hours 1-5.
    #
    # For verb=schedule AND a bare hour in {1,2,3,4,5} (no AM/PM marker, no
    # minutes qualifier), assume PM. Design rationale from Thomas (2026-09-21):
    # "a whole chunk of the day can't possibly be scheduled at those hours.
    # If I put something at 3 and I meant 3 AM, that's on me to correct it."
    # Hours 6-12 remain ambiguous (6 AM breakfast call vs 6 PM dinner are
    # both common). Non-schedule verbs (handle, remind) keep the original
    # caution — reminders can legitimately fire at 3 AM (medication, alarms).
    if not ampm and verb == "schedule" and hour in _SCHEDULE_PM_HOURS and minute == 0:
        hour += 12
        return time(hour=hour, minute=minute), False, f"schedule bare-hour inferred PM: '{time_hint}' -> {hour:02d}:00"

    # v1.2.2 fix — silent guessing is the failure mode that destroys trust in
    # a memory-support product (persona rule: `ambiguous_fields` is a first-
    # class output; never silently choose for the user). When the user says a
    # bare hour 1-12 with no AM/PM marker and no 24-hour context, we cannot
    # tell what they meant. The cost of guessing wrong is the user misses the
    # event entirely. The cost of asking is one extra round-trip ("AM or
    # PM?"). Asking wins. Hour 0 or 13-23 is unambiguous — only a 24-hour
    # clock can produce those — so we resolve those normally.
    if not ampm and 1 <= hour <= 12:
        return None, True, f"'{time_hint}' is ambiguous — AM or PM?"

    if ampm == "pm" and hour < 12:
        hour += 12
    elif ampm == "am" and hour == 12:
        hour = 0

    if not (0 <= hour < 24) or not (0 <= minute < 60):
        return None, True, f"time out of range: {hour}:{minute}"

    return time(hour=hour, minute=minute), False, f"resolved '{time_hint}' -> {hour:02d}:{minute:02d}"


_MONTHS = {
    "january": 1, "jan": 1,
    "february": 2, "feb": 2,
    "march": 3, "mar": 3,
    "april": 4, "apr": 4,
    "may": 5,
    "june": 6, "jun": 6,
    "july": 7, "jul": 7,
    "august": 8, "aug": 8,
    "september": 9, "sep": 9, "sept": 9,
    "october": 10, "oct": 10,
    "november": 11, "nov": 11,
    "december": 12, "dec": 12,
}


def _try_absolute_date(hint: str, now_local: datetime):
    iso = re.match(r"^(\d{4})-(\d{2})-(\d{2})$", hint)
    if iso:
        return datetime(int(iso.group(1)), int(iso.group(2)), int(iso.group(3))).date()

    # Strip ordinal suffixes from the day number ("20th" → "20", "1st" → "1",
    # "2nd" → "2", "3rd" → "3"). This allows natural speech forms like
    # "September 20th", "October 1st", "February 2nd", "March 3rd".
    hint_stripped = re.sub(r"(\d+)(?:st|nd|rd|th)\b", r"\1", hint)

    # "Month Day Year" — explicit year given; roll-forward does not apply.
    month_day_year = re.match(r"^([a-z]+)\s+(\d{1,2})\s+(\d{4})$", hint_stripped)
    if month_day_year:
        month_name = month_day_year.group(1)
        month = _MONTHS.get(month_name)
        if month is not None:
            day = int(month_day_year.group(2))
            year = int(month_day_year.group(3))
            try:
                return datetime(year, month, day).date()
            except ValueError:
                return None  # invalid date (e.g. Feb 29 in a non-leap year given explicitly)

    # "Month Day" — no year. Apply the roll-forward rule:
    #   today or future → current year
    #   already passed  → next year
    # Special case: February 29 in a non-leap year → scan forward to the next
    # leap year rather than silently degrading to Feb 28 or raising.
    month_day = re.match(r"^([a-z]+)\s+(\d{1,2})$", hint_stripped)
    if month_day:
        month_name = month_day.group(1)
        month = _MONTHS.get(month_name)
        if month is not None:
            day = int(month_day.group(2))
            today = now_local.date()

            # Feb 29 requires a leap year — find the right one.
            if month == 2 and day == 29:
                return _next_feb29(today)

            year = today.year
            try:
                candidate = datetime(year, month, day).date()
            except ValueError:
                return None  # invalid month/day combination (e.g. June 31)
            if candidate < today:
                candidate = datetime(year + 1, month, day).date()
            return candidate

    return None


def _next_feb29(today):
    """Return the date of the next (or current) February 29th on or after today.

    If today is exactly Feb 29, returns today.  Otherwise scans forward through
    leap years until it finds the first Feb 29 >= today.
    """
    import calendar as _cal

    year = today.year
    # Scan at most 8 years forward (worst case: just missed a leap year).
    for _ in range(8):
        if _cal.isleap(year):
            candidate = datetime(year, 2, 29).date()
            if candidate >= today:
                return candidate
        year += 1
    return None  # should never happen in practice
