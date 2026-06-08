"""Calendar primitives: event creation, listing, conflict detection.

All persistence goes through ``vault`` — one markdown file per event. Reads
walk the filesystem; there is no in-memory cache. That keeps the file
on disk authoritative: if you hand-edit an event file, the next call
reflects the edit.
"""

from __future__ import annotations

from datetime import datetime, timedelta
from pathlib import Path
from typing import Optional
from zoneinfo import ZoneInfo

from . import vault
from .schemas import CalendarEvent, ConflictReport


def create_event(
    vault_path: Path,
    title: str,
    starts_at: datetime,
    duration_minutes: int,
    tz_name: str,
    people: Optional[list[str]] = None,
    tags: Optional[list[str]] = None,
    source: str = "voice",
    source_utterance: Optional[str] = None,
    now: Optional[datetime] = None,
) -> CalendarEvent:
    """Persist a new event to the vault and return the model."""
    if starts_at.tzinfo is None:
        raise ValueError("starts_at must be tz-aware")
    ends_at = starts_at + timedelta(minutes=duration_minutes)
    created = now or datetime.now(starts_at.tzinfo)

    event = CalendarEvent(
        id=vault.event_id(starts_at, title),
        title=title,
        starts_at=starts_at,
        ends_at=ends_at,
        tz=tz_name,
        duration_minutes=duration_minutes,
        people=people or [],
        tags=tags or [],
        source=source,  # type: ignore[arg-type]
        source_utterance=source_utterance,
        created_at=created,
        updated_at=created,
    )

    path = vault.calendar_event_path(vault_path, starts_at, title)
    vault.write_markdown(path, _frontmatter(event), _body(event))
    return event


def _frontmatter(e: CalendarEvent) -> dict:
    return {
        "id": e.id,
        "title": e.title,
        "starts_at": e.starts_at.isoformat(),
        "ends_at": e.ends_at.isoformat(),
        "tz": e.tz,
        "duration_minutes": e.duration_minutes,
        "people": e.people,
        "tags": e.tags,
        "source": e.source,
        "source_utterance": e.source_utterance,
        "created_at": e.created_at.isoformat(),
        "updated_at": e.updated_at.isoformat(),
    }


def _body(e: CalendarEvent) -> str:
    when = e.starts_at.strftime("%A %B %-d at %-I:%M %p %Z")
    links = "".join(f"[[{p}]] " for p in e.people).strip()
    return f"# {e.title}\n\n{when} ({e.duration_minutes} min).\n\n{links}".rstrip()


def list_events(vault_path: Path) -> list[CalendarEvent]:
    events: list[CalendarEvent] = []
    for path in vault.iter_calendar_files(vault_path):
        fm, _ = vault.read_markdown(path)
        try:
            events.append(_event_from_fm(fm))
        except Exception:
            # Skip malformed entries — don't crash a list because one file is broken.
            continue
    return events


def list_events_between(vault_path: Path, start: datetime, end: datetime) -> list[CalendarEvent]:
    out: list[CalendarEvent] = []
    for e in list_events(vault_path):
        if e.starts_at < end and e.ends_at > start:
            out.append(e)
    return out


def check_conflicts(
    vault_path: Path,
    starts_at: datetime,
    ends_at: datetime,
    fuzz_minutes: int,
) -> ConflictReport:
    fuzz = timedelta(minutes=fuzz_minutes)
    direct: list[CalendarEvent] = []
    fuzzy: list[CalendarEvent] = []

    for e in list_events(vault_path):
        # Direct: any overlap.
        if e.starts_at < ends_at and e.ends_at > starts_at:
            direct.append(e)
            continue
        # Fuzzy: any edge of the existing event lies within ±fuzz of any edge
        # of the proposed event. Catches "ends 15 min before this starts" and
        # "starts 15 min after this ends" cases that aren't direct overlaps
        # but are close enough to warrant a warning.
        edges_existing = (e.starts_at, e.ends_at)
        edges_proposed = (starts_at, ends_at)
        if any(abs(a - b) <= fuzz for a in edges_existing for b in edges_proposed):
            fuzzy.append(e)

    return ConflictReport(
        has_direct_conflict=bool(direct),
        has_fuzzy_conflict=bool(fuzzy),
        direct=direct,
        fuzzy=fuzzy,
    )


def _event_from_fm(fm: dict) -> CalendarEvent:
    return CalendarEvent(
        id=fm["id"],
        title=fm["title"],
        starts_at=_parse_dt(fm["starts_at"]),
        ends_at=_parse_dt(fm["ends_at"]),
        tz=fm.get("tz", "America/New_York"),
        duration_minutes=int(fm.get("duration_minutes", 30)),
        people=list(fm.get("people") or []),
        tags=list(fm.get("tags") or []),
        source=fm.get("source", "voice"),
        source_utterance=fm.get("source_utterance"),
        created_at=_parse_dt(fm.get("created_at") or fm["starts_at"]),
        updated_at=_parse_dt(fm.get("updated_at") or fm["starts_at"]),
    )


def _parse_dt(value) -> datetime:
    if isinstance(value, datetime):
        return value if value.tzinfo else value.replace(tzinfo=ZoneInfo("America/New_York"))
    return datetime.fromisoformat(str(value))
