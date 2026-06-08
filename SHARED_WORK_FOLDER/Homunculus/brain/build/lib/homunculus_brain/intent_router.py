"""Dispatch a ParsedIntent to the right handler.

Returns a CaptureResponse that the server (and eventually the phone) can
act on: write the file, speak the reply, ask a clarifying question, or
park the utterance in the inbox.

Confidence and ambiguity-driven branches:
  - Calendar writes ALWAYS need confirmation, even on high confidence —
    the consequence of a wrong event is too high to act silently.
  - Notes (tool / prompt) write immediately on high or medium confidence.
  - Low confidence on anything → inbox + spoken "wasn't sure, in the inbox".
"""

from __future__ import annotations

import logging
from datetime import datetime, timedelta
from pathlib import Path
from typing import Optional
from zoneinfo import ZoneInfo

from . import activity_log
from . import calendar as cal
from . import notes
from . import reminders
from .config import Config
from .date_resolver import resolve as resolve_datetime
from .schemas import (
    CaptureResponse,
    Confidence,
    ConflictReport,
    IntentKind,
    ParsedIntent,
)


log = logging.getLogger(__name__)


def route(
    intent: ParsedIntent,
    *,
    config: Config,
    now: datetime,
    tz: Optional[ZoneInfo] = None,
) -> CaptureResponse:
    """Top-level dispatcher.

    ``tz`` is the speaker's zone, derived from ``CaptureRequest.speaker_tz``
    when the phone supplied one. When omitted, fall back to the server's
    configured default. Honors the persona rule: phone-reported zone wins
    over server default.
    """
    tz = tz or ZoneInfo(config.default_tz_name)

    activity_log.log(
        config.vault_path,
        "parse",
        at=now,
        raw_text=intent.raw_text,
        details={
            "kind": intent.kind.value,
            "confidence": intent.confidence.value,
            "ambiguous_fields": intent.ambiguous_fields,
        },
    )

    if intent.confidence is Confidence.LOW:
        return _drop_to_inbox(intent, config=config, now=now, reason="low confidence")

    if intent.kind is IntentKind.CALENDAR_EVENT:
        return _handle_calendar_event(intent, config=config, now=now, tz=tz)
    if intent.kind is IntentKind.CALENDAR_QUERY:
        return _handle_calendar_query(intent, config=config, now=now, tz=tz)
    if intent.kind is IntentKind.TOOL_NOTE:
        return _handle_tool_note(intent, config=config, now=now)
    if intent.kind is IntentKind.PROMPT_NOTE:
        return _handle_prompt_note(intent, config=config, now=now)

    return _drop_to_inbox(intent, config=config, now=now, reason="unknown intent")


# --- calendar event (write requires confirmation) ----------------------------


def _handle_calendar_event(
    intent: ParsedIntent, *, config: Config, now: datetime, tz: Optional[ZoneInfo] = None
) -> CaptureResponse:
    tz = tz or ZoneInfo(config.default_tz_name)
    resolved = resolve_datetime(
        intent.day_hint,
        intent.time_hint,
        now=now,
        tz=tz,
        morning_anchor_hour=config.morning_anchor_hour,
    )

    if resolved.resolved_at is None:
        return CaptureResponse(
            kind=intent.kind,
            confidence=intent.confidence,
            action="needs_clarification",
            spoken_reply=_clarifying_question(resolved.ambiguous, intent),
            clarifying_question=_clarifying_question(resolved.ambiguous, intent),
            raw_text=intent.raw_text,
        )

    duration = intent.duration_minutes or config.default_event_duration_minutes
    ends_at = resolved.resolved_at + timedelta(minutes=duration)
    conflicts = cal.check_conflicts(
        config.vault_path,
        starts_at=resolved.resolved_at,
        ends_at=ends_at,
        fuzz_minutes=config.conflict_fuzz_minutes,
    )

    title = intent.title or "event"
    readback = _readback(title, resolved.resolved_at, duration, conflicts)

    return CaptureResponse(
        kind=intent.kind,
        confidence=intent.confidence,
        action="needs_confirmation",
        spoken_reply=readback,
        written_path=None,
        conflicts=conflicts,
        raw_text=intent.raw_text,
    )


def commit_calendar_event(
    intent: ParsedIntent,
    *,
    config: Config,
    now: datetime,
    tz: Optional[ZoneInfo] = None,
) -> CaptureResponse:
    """Called by the /confirm endpoint after the user says yes.

    ``tz`` is the speaker's zone (from ``CaptureRequest.speaker_tz``). The
    event is persisted in that zone — so a "10 AM Thursday" said in Pacific
    travel mode lands as 10 AM Pacific, not 10 AM Eastern. Falls back to
    the server default when no speaker zone was given.
    """
    tz = tz or ZoneInfo(config.default_tz_name)
    tz_name = str(tz)
    resolved = resolve_datetime(
        intent.day_hint,
        intent.time_hint,
        now=now,
        tz=tz,
        morning_anchor_hour=config.morning_anchor_hour,
    )
    if resolved.resolved_at is None:
        return _drop_to_inbox(intent, config=config, now=now, reason="could not resolve time at commit")

    duration = intent.duration_minutes or config.default_event_duration_minutes
    title = intent.title or "event"

    event = cal.create_event(
        config.vault_path,
        title=title,
        starts_at=resolved.resolved_at,
        duration_minutes=duration,
        tz_name=tz_name,
        people=intent.people,
        tags=intent.tags,
        source_utterance=intent.raw_text,
    )

    rows = reminders.build_event_schedule(event)
    reminders.persist_event_schedule(config.vault_path, event, rows)
    reminders.push_to_phone(rows)

    activity_log.log(
        config.vault_path,
        "event_create",
        at=now,
        event_id=event.id,
        raw_text=intent.raw_text,
        details={
            "title": event.title,
            "starts_at": event.starts_at.isoformat(),
            "duration_minutes": event.duration_minutes,
            "reminder_rows": len(rows),
        },
    )

    return CaptureResponse(
        kind=intent.kind,
        confidence=intent.confidence,
        action="wrote",
        spoken_reply=f"Saved. {event.title} on {event.starts_at.strftime('%A %B %-d at %-I:%M %p')}.",
        written_path=str(_relative(config.vault_path, _event_file(config.vault_path, event.starts_at, event.title))),
        raw_text=intent.raw_text,
    )


def _event_file(vault_path: Path, starts_at: datetime, title: str) -> Path:
    from . import vault as v
    return v.calendar_event_path(vault_path, starts_at, title)


# --- calendar query (read, never write) -------------------------------------


def _handle_calendar_query(
    intent: ParsedIntent, *, config: Config, now: datetime, tz: Optional[ZoneInfo] = None
) -> CaptureResponse:
    tz = tz or ZoneInfo(config.default_tz_name)
    resolved = resolve_datetime(intent.day_hint, intent.time_hint, now=now, tz=tz, morning_anchor_hour=config.morning_anchor_hour)
    if resolved.resolved_at is None:
        return CaptureResponse(
            kind=intent.kind,
            confidence=intent.confidence,
            action="needs_clarification",
            spoken_reply=_clarifying_question(resolved.ambiguous, intent),
            clarifying_question=_clarifying_question(resolved.ambiguous, intent),
            raw_text=intent.raw_text,
        )

    duration = intent.duration_minutes or config.default_event_duration_minutes
    ends_at = resolved.resolved_at + timedelta(minutes=duration)
    conflicts = cal.check_conflicts(
        config.vault_path,
        starts_at=resolved.resolved_at,
        ends_at=ends_at,
        fuzz_minutes=config.conflict_fuzz_minutes,
    )

    when_str = resolved.resolved_at.strftime("%A %B %-d at %-I:%M %p")
    if conflicts.has_direct_conflict:
        existing = conflicts.direct[0]
        reply = f"You have '{existing.title}' at {existing.starts_at.strftime('%-I:%M %p')}. That's a conflict."
    elif conflicts.has_fuzzy_conflict:
        existing = conflicts.fuzzy[0]
        reply = f"You have '{existing.title}' at {existing.starts_at.strftime('%-I:%M %p')} — close to {when_str.split('at ')[-1]}, but no direct conflict."
    else:
        reply = f"You're clear {when_str}."

    return CaptureResponse(
        kind=intent.kind,
        confidence=intent.confidence,
        action="wrote",  # nothing written, but the action completed
        spoken_reply=reply,
        conflicts=conflicts,
        raw_text=intent.raw_text,
    )


# --- tool / prompt notes (write fast, confirm briefly) ----------------------


def _handle_tool_note(intent: ParsedIntent, *, config: Config, now: datetime) -> CaptureResponse:
    if not intent.title:
        return _drop_to_inbox(intent, config=config, now=now, reason="tool note missing title")
    note, path = notes.write_tool_note(
        config.vault_path,
        title=intent.title,
        captured_at=now,
        tags=intent.tags,
        source_utterance=intent.raw_text,
    )
    activity_log.log(
        config.vault_path,
        "tool_note_create",
        at=now,
        raw_text=intent.raw_text,
        details={"title": note.title, "path": str(_relative(config.vault_path, path))},
    )
    return CaptureResponse(
        kind=intent.kind,
        confidence=intent.confidence,
        action="wrote",
        spoken_reply=f"Noted — {intent.title}, in tools.",
        written_path=str(_relative(config.vault_path, path)),
        raw_text=intent.raw_text,
    )


def _handle_prompt_note(intent: ParsedIntent, *, config: Config, now: datetime) -> CaptureResponse:
    title = intent.title or f"Saved prompt {now.strftime('%Y-%m-%d %H:%M')}"
    _, path = notes.write_prompt_note(
        config.vault_path,
        title=title,
        captured_at=now,
        source_utterance=intent.raw_text,
        body=intent.body,
    )
    activity_log.log(
        config.vault_path,
        "prompt_note_create",
        at=now,
        raw_text=intent.raw_text,
        details={
            "title": title,
            "path": str(_relative(config.vault_path, path)),
            "body_chars": len(intent.body or ""),
        },
    )
    return CaptureResponse(
        kind=intent.kind,
        confidence=intent.confidence,
        action="wrote",
        spoken_reply=f"Saved that prompt — {title}.",
        written_path=str(_relative(config.vault_path, path)),
        raw_text=intent.raw_text,
    )


# --- inbox -------------------------------------------------------------------


def _drop_to_inbox(intent: ParsedIntent, *, config: Config, now: datetime, reason: str) -> CaptureResponse:
    path = notes.write_inbox(
        config.vault_path,
        captured_at=now,
        raw_text=intent.raw_text,
        best_guess=intent.kind.value,
        reason=reason,
    )
    activity_log.log(
        config.vault_path,
        "inbox_drop",
        at=now,
        raw_text=intent.raw_text,
        details={"reason": reason, "best_guess": intent.kind.value},
    )
    return CaptureResponse(
        kind=IntentKind.UNKNOWN,
        confidence=intent.confidence,
        action="inbox",
        spoken_reply=f"I wasn't sure where this goes — it's in the inbox. {reason}.",
        written_path=str(_relative(config.vault_path, path)),
        raw_text=intent.raw_text,
    )


# --- helpers -----------------------------------------------------------------


def _readback(title: str, starts_at: datetime, duration: int, conflicts: ConflictReport) -> str:
    base = f"Got it — {title}, {starts_at.strftime('%A %B %-d at %-I:%M %p')} for {duration} minutes."
    if conflicts.has_direct_conflict:
        ex = conflicts.direct[0]
        return base + f" That overlaps with '{ex.title}' at {ex.starts_at.strftime('%-I:%M %p')}. Save anyway?"
    if conflicts.has_fuzzy_conflict:
        ex = conflicts.fuzzy[0]
        return base + f" Note: '{ex.title}' is at {ex.starts_at.strftime('%-I:%M %p')} — close but not a direct conflict. Sound right?"
    return base + " Sound right?"


def _clarifying_question(ambiguous: list[str], intent: ParsedIntent) -> str:
    if "day" in ambiguous and "time" in ambiguous:
        return "What day and time?"
    if "day" in ambiguous:
        return "Which day?"
    if "time" in ambiguous:
        return "What time?"
    return "Can you say that again?"


def _relative(vault_path: Path, p: Path) -> Path:
    try:
        return p.relative_to(vault_path)
    except ValueError:
        return p
