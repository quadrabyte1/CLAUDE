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
) -> ResolvedDateTime:
    """Combine day + time hints into a single tz-aware datetime.

    `now` must be tz-aware. Returns an `ambiguous` list naming any field we
    couldn't pin down; the router uses that to decide whether to ask a
    clarifying question.
    """
    if now.tzinfo is None:
        raise ValueError("now must be tz-aware")

    now_local = now.astimezone(tz)

    resolved_date, day_ambiguous, day_note = _resolve_day(day_hint, now_local)
    resolved_time, time_ambiguous, time_note = _resolve_time(
        time_hint, morning_anchor_hour
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


def _resolve_time(time_hint: Optional[str], morning_anchor_hour: int):
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

    month_day = re.match(r"^([a-z]+)\s+(\d{1,2})$", hint)
    if month_day:
        month_name = month_day.group(1)
        month = _MONTHS.get(month_name)
        if month is not None:
            day = int(month_day.group(2))
            year = now_local.year
            candidate = datetime(year, month, day).date()
            # If the date is more than 30 days in the past, assume next year.
            if (now_local.date() - candidate).days > 30:
                candidate = datetime(year + 1, month, day).date()
            return candidate

    return None
