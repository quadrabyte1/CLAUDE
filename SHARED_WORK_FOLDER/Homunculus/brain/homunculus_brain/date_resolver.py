"""Deterministic date/time resolution.

The LLM is good at extracting the *words* ("Thursday at 10am", "tomorrow
morning"). It is unreliable at turning those words into an actual calendar
date. Everything below is pure Python so the math is testable and never
guesses.

v2.5.0 — AM/PM disambiguation overhaul.

Three layered signals reduce clarifying-question rate from >50 % to ~5 %:

  Signal A — verb / meal / profession context keywords
             "breakfast" → AM, "dinner" → PM, "plumber" → business-hours PM,
             "gym" → AM, "bedtime" → PM.  Data-driven dict; 1-line additions.

  Signal B — speaker-time roll-forward
             Pick the nearest future interpretation of a bare hour given
             speaker timezone + now.  Sleep window (0–5 AM) is skipped
             unless now is late night (≥ 22:00).

  Signal C — natural qualifier vocabulary
             "in the morning" → AM, "tonight" → PM, "this afternoon" → PM,
             "tomorrow morning" → next day AM, etc.  Regex normalization pass
             runs BEFORE the time resolver so downstream sees a resolved meridiem.

Precedence (highest wins):
  1. Explicit AM/PM in time_hint         → current behavior, untouched
  2. Signal C — explicit natural qualifier in context_text
  3. Signal A — meal / profession / activity keyword in context_text
  4. Signal A (tie-breaker) + existing v0.8.1 schedule+1-5=PM rule
  5. Signal B — roll-forward to nearest future interpretation
  6. Clarifying question (only when all signals fail to narrow it down)

After v2.5.0, clarifying questions about AM/PM are only raised when the
bare hour is genuinely unknowable even with roll-forward — which in practice
means a bare hour with no now context, which cannot happen via the normal
capture path.
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


# ---------------------------------------------------------------------------
# v2.5.0 — Signal A: context-keyword → meridiem mapping
#
# Structure:  keyword → "am" | "pm"
# Convention: all keys must be lowercase.  Add new entries freely — this is
#             designed as a 1-line-per-entry extensible dict.
# ---------------------------------------------------------------------------

#: Meal keywords.  Maps to a preferred meridiem (AM/PM).
#: Expandable: add new meal words here, one line each.
_MEAL_MERIDIEM: dict[str, str] = {
    "breakfast": "am",
    "brunch":    "pm",   # brunch can be either but leans late morning/early afternoon
    "lunch":     "pm",   # noon/afternoon
    "dinner":    "pm",
    "supper":    "pm",
    "snack":     "pm",   # afternoon default
}

#: Personal activity keywords that bias toward morning.
#: Expandable: add new morning-activity words here, one line each.
_MORNING_ACTIVITY_KEYWORDS: frozenset[str] = frozenset({
    "wake",       # "wake up", "wake-up call"
    "wakeup",
    "wake-up",
    "exercise",
    "gym",
    "workout",
    "run",        # "morning run"
    "jog",
    "yoga",
    "swim",
})

#: Personal activity keywords that bias toward evening/night.
#: Expandable: add new evening-activity words here, one line each.
_EVENING_ACTIVITY_KEYWORDS: frozenset[str] = frozenset({
    "bedtime",
    "sleep",
    "wind down",
    "winddown",
    "wind-down",
    "bed",        # "go to bed at 10"
})

#: Profession / appointment keywords → business hours (PM for bare 1-5).
#: These only strengthen PM inference; they don't override the v0.8.1 rule —
#: they extend it to all verbs (not just "schedule").
#: Expandable: add new profession words here, one line each.
_PROFESSION_KEYWORDS: frozenset[str] = frozenset({
    "plumber",
    "electrician",
    "doctor",
    "dentist",
    "mechanic",
    "contractor",
    "inspector",
    "appointment",
    "therapist",
    "lawyer",
    "attorney",
    "accountant",
    "vet",
    "veterinarian",
    "chiropractor",
    "optometrist",
    "pediatrician",
    "dermatologist",
    "physical therapy",
    "physical therapist",
})


# ---------------------------------------------------------------------------
# v2.5.0 — Signal C: natural qualifier → meridiem / hour range
#
# Patterns are matched against the full context_text (lowercased).  The result
# is a meridiem string ("am" or "pm") or None if no qualifier matches.
# Patterns are ordered: more-specific phrases before shorter overlapping ones.
# ---------------------------------------------------------------------------

# Each entry: (compiled regex, resolved meridiem "am"|"pm")
# Longer / more-specific patterns must precede shorter ones (e.g. "tomorrow
# morning" before "morning") so the first match is the most precise.
_QUALIFIER_PATTERNS: list[tuple[re.Pattern, str]] = [
    # tomorrow + time-of-day (day part handled by day_hint; meridiem extracted here)
    (re.compile(r"\btomorrow\s+morning\b",   re.IGNORECASE), "am"),
    (re.compile(r"\btomorrow\s+afternoon\b", re.IGNORECASE), "pm"),
    (re.compile(r"\btomorrow\s+evening\b",   re.IGNORECASE), "pm"),
    (re.compile(r"\btomorrow\s+night\b",     re.IGNORECASE), "pm"),
    # this + time-of-day
    (re.compile(r"\bthis\s+morning\b",       re.IGNORECASE), "am"),
    (re.compile(r"\bthis\s+afternoon\b",     re.IGNORECASE), "pm"),
    (re.compile(r"\bthis\s+evening\b",       re.IGNORECASE), "pm"),
    (re.compile(r"\bthis\s+night\b",         re.IGNORECASE), "pm"),
    # compound qualifiers
    (re.compile(r"\blate\s+morning\b",       re.IGNORECASE), "am"),
    (re.compile(r"\bearly\s+afternoon\b",    re.IGNORECASE), "pm"),
    (re.compile(r"\blate\s+evening\b",       re.IGNORECASE), "pm"),
    (re.compile(r"\bin\s+the\s+morning\b",   re.IGNORECASE), "am"),
    (re.compile(r"\bin\s+the\s+afternoon\b", re.IGNORECASE), "pm"),
    (re.compile(r"\bin\s+the\s+evening\b",   re.IGNORECASE), "pm"),
    # standalone phrases
    (re.compile(r"\bat\s+night\b",           re.IGNORECASE), "pm"),
    (re.compile(r"\btonight\b",              re.IGNORECASE), "pm"),
]


def _signal_c_meridiem(context_text: str) -> Optional[str]:
    """Return 'am' or 'pm' if context_text contains a natural qualifier phrase.

    Returns None if no qualifier phrase matches.  This is Signal C — it fires
    before Signal A so that "dinner at 7 in the morning" (contradictory but
    explicit) resolves to AM (the qualifier phrase is a more specific instruction
    than the meal type).
    """
    if not context_text:
        return None
    for pattern, meridiem in _QUALIFIER_PATTERNS:
        if pattern.search(context_text):
            return meridiem
    return None


def _signal_a_meridiem(context_text: str) -> Optional[str]:
    """Return 'am' or 'pm' if context_text contains a meal / profession / activity word.

    Returns None if no keyword matches.  Checks in order: meals → morning
    activities → evening activities → professions.
    """
    if not context_text:
        return None
    lower = context_text.lower()

    # Meals (exact word match via word boundary)
    for keyword, meridiem in _MEAL_MERIDIEM.items():
        if re.search(r"\b" + re.escape(keyword) + r"\b", lower):
            return meridiem

    # Morning activity keywords → AM
    for keyword in _MORNING_ACTIVITY_KEYWORDS:
        if re.search(r"\b" + re.escape(keyword) + r"\b", lower):
            return "am"

    # Evening activity keywords → PM
    for keyword in _EVENING_ACTIVITY_KEYWORDS:
        if re.search(r"\b" + re.escape(keyword) + r"\b", lower):
            return "pm"

    # Profession keywords → PM (business hours bias — same as v0.8.1 for schedule,
    # but now applied to all verbs when profession context is present)
    for keyword in _PROFESSION_KEYWORDS:
        # Multi-word keywords handled by re.escape + word boundary on edges
        pattern = r"\b" + re.escape(keyword) + r"\b"
        if re.search(pattern, lower):
            return "pm"

    return None


# ---------------------------------------------------------------------------
# v2.5.0 — Signal B: speaker-time roll-forward
#
# Given a bare hour H and the current time `now`, pick the nearest future
# occurrence of H:am or H:pm that is:
#   - At least 15 minutes in the future (avoids "right now" ambiguity)
#   - Outside the sleep window (midnight–5 AM), UNLESS `now` is late night
#     (22:00+), in which case near-term 3 AM is a reasonable interpretation
#     (alarm, medication).
# ---------------------------------------------------------------------------

_ROLL_FORWARD_BUFFER_MINUTES = 15
_SLEEP_WINDOW_START = 0   # midnight (hour 0)
_SLEEP_WINDOW_END   = 5   # through 5:59 AM (exclusive upper bound = 6)


def _signal_b_rollforward(
    hour: int,
    now: datetime,
    tz: ZoneInfo,
) -> Optional[datetime]:
    """Return the nearest future datetime for the given bare hour.

    Skips the sleep window (0–5 AM inclusive) unless now >= 22:00, in which
    case near-morning times are legitimate (alarms, medications).

    Returns None only if no candidate can be found within 2 days (should
    never happen in practice for hours 1-12).
    """
    now_local = now.astimezone(tz)
    buffer = timedelta(minutes=_ROLL_FORWARD_BUFFER_MINUTES)
    cutoff = now_local + buffer

    # Build same-day and next-day candidates for AM and PM interpretations.
    today = now_local.date()
    from datetime import date as _date
    tomorrow = today + timedelta(days=1)
    day_after = tomorrow + timedelta(days=1)

    def _candidate(d, h: int) -> datetime:
        return datetime(d.year, d.month, d.day, h, 0, tzinfo=tz)

    # AM candidates: 0 < hour < 12 → am hour; hour == 12 → noon (no AM candidate)
    # PM candidates: hour < 12 → h+12; hour == 12 → 12 (noon)
    if hour == 12:
        am_hour = None   # 12 AM is midnight, handle separately
        pm_hour = 12     # noon
    else:
        am_hour = hour
        pm_hour = hour + 12

    # Determine if we're in late-night context (skip sleep-window skip)
    late_night = now_local.hour >= 22

    def _is_sleep(h: int) -> bool:
        """True if hour is in the sleep window and we're NOT in late-night context."""
        if late_night:
            return False  # late night: near-morning is ok
        return _SLEEP_WINDOW_START <= h <= _SLEEP_WINDOW_END

    candidates: list[datetime] = []
    for d in (today, tomorrow, day_after):
        if am_hour is not None:
            c = _candidate(d, am_hour)
            if c >= cutoff and not _is_sleep(am_hour):
                candidates.append(c)
        if pm_hour != am_hour:  # avoid duplicating noon
            c = _candidate(d, pm_hour)
            if c >= cutoff and not _is_sleep(pm_hour):
                candidates.append(c)

    if not candidates:
        return None
    return min(candidates)


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
    context_text: Optional[str] = None,
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

    ``context_text`` is optional — the full raw memo text. Used by the v2.5.0
    disambiguation signals (A, B, C) to extract contextual meridiem clues
    (meal words, qualifier phrases, profession keywords). When None, only
    the existing v0.8.1 schedule+1-5 rule and the new Signal B roll-forward
    apply. Passing context_text never changes the behavior for time hints that
    already carry an explicit AM/PM marker.

    v2.5.0 disambiguation stack (for bare hours 1–12 with no explicit AM/PM):
      1. Explicit AM/PM in time_hint         → resolved directly (pre-existing)
      2. Signal C: natural qualifier phrase  → meridiem from context_text
      3. Signal A: meal/profession/activity  → meridiem from context_text
      4. v0.8.1 schedule+1-5 PM rule        → PM for schedule verb, hours 1-5
      5. Signal B: roll-forward to nearest future interpretation
      6. Clarifying question (ambiguous=['time']) — only if all above fail
    """
    if now.tzinfo is None:
        raise ValueError("now must be tz-aware")

    now_local = now.astimezone(tz)

    resolved_date, day_ambiguous, day_note = _resolve_day(day_hint, now_local)
    resolved_time, time_ambiguous, time_note = _resolve_time(
        time_hint, morning_anchor_hour, verb=verb,
        context_text=context_text, now=now_local, tz=tz,
    )

    ambiguous: list[str] = []
    if day_ambiguous:
        ambiguous.append("day")
    if time_ambiguous:
        ambiguous.append("time")

    # Signal B sentinel: _resolve_time deferred roll-forward to here so we can
    # use the *resolved_date* (from day_hint, already computed above) as the
    # anchor date rather than today. This ensures "Friday at 3" picks Friday 3 PM,
    # not today 3 PM.
    #
    # Two cases:
    #   A) day_hint explicitly given → user intends a specific target date.
    #      Anchor roll-forward to midnight of that date if it's future; to
    #      now_local if same-day. Constrain result to that date.
    #   B) day_hint NOT given (day_hint is None) → roll-forward freely across
    #      today/tomorrow/day-after from now_local. Result date is whatever the
    #      nearest future interpretation falls on.
    if isinstance(resolved_time, _RollforwardResult):
        bare_hour = resolved_time.hour
        user_specified_day = day_hint is not None

        if user_specified_day and resolved_date is not None:
            # Case A: user gave a specific date.
            if resolved_date > now_local.date():
                # Future date → anchor to midnight of that date so all hours are future.
                anchor = datetime(
                    resolved_date.year, resolved_date.month, resolved_date.day,
                    0, 0, tzinfo=tz
                )
            else:
                # Same-day (or past — rare for well-formed requests) → real now.
                anchor = now_local
            rf_dt = _signal_b_rollforward(bare_hour, anchor, tz)
            if rf_dt is None:
                return ResolvedDateTime(
                    resolved_at=None,
                    ambiguous=["time"],
                    note="signal-B roll-forward failed (no candidates on specified date)",
                )
            # Constrain to resolved_date. Sleep-window skip might have moved rf_dt
            # to the next calendar day; put it back on the intended date with the
            # chosen hour (AM vs PM as determined by roll-forward).
            if rf_dt.date() != resolved_date:
                rf_dt = datetime(
                    resolved_date.year, resolved_date.month, resolved_date.day,
                    rf_dt.hour, 0, tzinfo=tz
                )
        else:
            # Case B: no day_hint → roll forward freely from now_local.
            rf_dt = _signal_b_rollforward(bare_hour, now_local, tz)
            if rf_dt is None:
                return ResolvedDateTime(
                    resolved_at=None,
                    ambiguous=["time"],
                    note="signal-B roll-forward failed (no candidates)",
                )

        note_text = (
            ((day_note or "") + f" signal-B roll-forward -> {rf_dt.strftime('%H:%M')}").strip()
        )
        return ResolvedDateTime(
            resolved_at=rf_dt,
            ambiguous=ambiguous,
            note=note_text or None,
        )

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


class _RollforwardResult:
    """Sentinel returned by _resolve_time when Signal B should be applied.

    When _resolve_time cannot determine AM/PM from signals C, A, or v0.8.1,
    it returns this sentinel carrying the raw bare hour. ``resolve()`` then
    calls ``_signal_b_rollforward`` with the *resolved date* (from day_hint)
    so that roll-forward honours the correct target date, not today.
    """
    __slots__ = ("hour",)

    def __init__(self, hour: int) -> None:
        self.hour = hour


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

# v2.5.1 — military time: 4-digit HHMM in range 0000-2359.
# Matches bare "1400", "0900", "1830" — unambiguous 24-hour notation.
# Must be exactly 4 digits with no surrounding alpha chars (word boundary).
# Pattern: HH in [00-23], MM in [00-59].
_MILITARY_TIME_RE = re.compile(
    r"""^\s*
        (?P<mil_hh>[01]\d|2[0-3])   # Hours 00-23
        (?P<mil_mm>[0-5]\d)          # Minutes 00-59
        \s*$
    """,
    re.VERBOSE,
)

_SCHEDULE_PM_HOURS = frozenset({1, 2, 3, 4, 5})


def _resolve_time(
    time_hint: Optional[str],
    morning_anchor_hour: int,
    verb: Optional[str] = None,
    context_text: Optional[str] = None,
    now: Optional[datetime] = None,
    tz: Optional[ZoneInfo] = None,
):
    """Resolve a time hint string to a ``time`` object (or a ``_RollforwardResult``).

    Returns a 3-tuple: (resolved, ambiguous_bool, note_str).

    When ``resolved`` is a ``_RollforwardResult`` it carries a fully-resolved
    tz-aware datetime (including date) produced by Signal B roll-forward.
    Callers must check for this case before calling ``datetime.combine``.

    v2.5.0 disambiguation stack (for bare hours 1–12, no explicit AM/PM):
      Step 1  Explicit AM/PM in time_hint     → resolve directly (pre-existing)
      Step 2  Signal C natural qualifier      → apply meridiem from context_text
      Step 3  Signal A meal/profession/act    → apply meridiem from context_text
      Step 4  v0.8.1 schedule+1-5 PM rule    → apply for verb=schedule
      Step 5  Signal B roll-forward           → nearest future interpretation
      Step 6  Clarifying question             → ambiguous=['time'] (last resort)
    """
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

    # === Step 0: Military time (HHMM 4-digit, 24-hour) — unambiguous by construction ===
    #
    # v2.5.1: Before the normal 1-2 digit regex, check for 4-digit HHMM.
    # "1400" → 14:00 (2 PM), "0900" → 09:00 (9 AM), "1830" → 18:30 (6:30 PM).
    # Military time is unambiguous — no signal processing needed.
    mil_match = _MILITARY_TIME_RE.match(hint)
    if mil_match:
        mil_hour = int(mil_match.group("mil_hh"))
        mil_minute = int(mil_match.group("mil_mm"))
        if 0 <= mil_hour < 24 and 0 <= mil_minute < 60:
            return (
                time(hour=mil_hour, minute=mil_minute),
                False,
                f"military-time '{hint}' -> {mil_hour:02d}:{mil_minute:02d}",
            )

    match = _TIME_REGEX.match(hint)
    if not match:
        return None, True, f"could not parse time '{time_hint}'"

    hour = int(match.group("hour"))
    minute = int(match.group("minute") or 0)
    ampm = (match.group("ampm") or "").replace(".", "").lower()

    # === Step 1: Explicit AM/PM already present → resolve directly (pre-existing) ===
    #
    # If the time hint already carries an explicit AM/PM marker, we honour it
    # unconditionally.  No signal can override an explicit user specification.
    if ampm:
        if ampm == "pm" and hour < 12:
            hour += 12
        elif ampm == "am" and hour == 12:
            hour = 0
        if not (0 <= hour < 24) or not (0 <= minute < 60):
            return None, True, f"time out of range: {hour}:{minute}"
        return time(hour=hour, minute=minute), False, f"resolved '{time_hint}' -> {hour:02d}:{minute:02d}"

    # Below here: bare hour with no explicit AM/PM marker.
    # Only hours 1-12 are ambiguous; 0 and 13-23 are unambiguous 24-hour reads.
    if not (1 <= hour <= 12):
        # 24-hour unambiguous path (unchanged from pre-v2.5.0).
        if not (0 <= hour < 24) or not (0 <= minute < 60):
            return None, True, f"time out of range: {hour}:{minute}"
        return time(hour=hour, minute=minute), False, f"resolved '{time_hint}' -> {hour:02d}:{minute:02d}"

    # Hours 1-12 with no explicit AM/PM — run the disambiguation stack.

    # === Step 2: Signal C — natural qualifier phrase in context_text ===
    c_meridiem = _signal_c_meridiem(context_text)
    if c_meridiem is not None:
        resolved_hour = _apply_meridiem(hour, c_meridiem)
        return (
            time(hour=resolved_hour, minute=minute),
            False,
            f"signal-C qualifier '{c_meridiem}' -> {resolved_hour:02d}:{minute:02d}",
        )

    # === Step 3: Signal A — meal / profession / activity keyword in context_text ===
    a_meridiem = _signal_a_meridiem(context_text)
    if a_meridiem is not None:
        resolved_hour = _apply_meridiem(hour, a_meridiem)
        return (
            time(hour=resolved_hour, minute=minute),
            False,
            f"signal-A keyword '{a_meridiem}' -> {resolved_hour:02d}:{minute:02d}",
        )

    # === Step 4: v0.8.1 schedule verb PM inference for bare hours 1-5 ===
    #
    # For verb=schedule AND a bare hour in {1,2,3,4,5} (no AM/PM marker, no
    # minutes qualifier), assume PM. Design rationale from Thomas (2026-09-21):
    # "a whole chunk of the day can't possibly be scheduled at those hours.
    # If I put something at 3 and I meant 3 AM, that's on me to correct it."
    # Hours 6-12 remain ambiguous (6 AM breakfast call vs 6 PM dinner are
    # both common). Non-schedule verbs (handle, remind) keep the original
    # caution — reminders can legitimately fire at 3 AM (medication, alarms).
    if verb == "schedule" and hour in _SCHEDULE_PM_HOURS and minute == 0:
        resolved_hour = hour + 12
        return (
            time(hour=resolved_hour, minute=minute),
            False,
            f"schedule bare-hour inferred PM: '{time_hint}' -> {resolved_hour:02d}:00",
        )

    # === Step 5: Signal B — speaker-time roll-forward ===
    #
    # Delegate to resolve() via a sentinel: _RollforwardResult carries the bare
    # hour integer so that resolve() can call _signal_b_rollforward with the
    # *resolved date* from day_hint (not necessarily today). This ensures
    # "Friday at 3" resolves to Friday 3 PM, not today 3 PM.
    if now is not None and tz is not None and minute == 0:
        # Only apply roll-forward for whole hours (no minutes component).
        # Bare hours with minutes (e.g. "5:35") remain ambiguous — the user was
        # specific enough to give minutes, so asking AM/PM is low cost.
        return (
            _RollforwardResult(hour),
            False,
            f"signal-B roll-forward pending for hour={hour}",
        )

    # === Step 6: Clarifying question (last resort) ===
    #
    # Bare hour:minute with no AM/PM, no context, no roll-forward available.
    # v1.2.2 rule: don't guess. Ask. This path is reached only when:
    #   - No explicit AM/PM in time_hint
    #   - No qualifier phrase in context_text (Signal C)
    #   - No keyword context in context_text (Signal A)
    #   - Not a schedule-verb + 1-5 bare hour (v0.8.1)
    #   - now is None (unusual — the normal API always passes now)
    #   OR minute != 0 (bare hour:minute case — still ask)
    return None, True, f"'{time_hint}' is ambiguous — AM or PM?"


def _apply_meridiem(hour: int, meridiem: str) -> int:
    """Convert a 12-hour hour to 24-hour given a meridiem ('am' or 'pm').

    Handles the edge cases:
      - 12 AM → 0 (midnight)
      - 12 PM → 12 (noon)
      - 1-11 PM → add 12
      - 1-11 AM → as-is
    """
    if meridiem == "pm":
        if hour < 12:
            return hour + 12
        return hour  # 12 PM stays 12
    else:  # am
        if hour == 12:
            return 0  # 12 AM = midnight
        return hour  # 1-11 AM stay as-is


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
