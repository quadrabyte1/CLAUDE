"""
vault_reader.py — Parse Herman vault event .md files into structured EventRecord objects.

Reads YAML frontmatter using python-frontmatter. No Mac-specific code; runs on Linux.

Expected frontmatter shape (from Herman v1.4.0):
    id: 2026-09-15-meeting-with-myself
    title: meeting with myself
    starts_at: '2026-09-15T09:00:00-04:00'
    ends_at:   '2026-09-15T09:30:00-04:00'
    tz: America/New_York
    duration_minutes: 30
    people: []
    tags: []
    ...
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from zoneinfo import ZoneInfo

import frontmatter  # python-frontmatter

log = logging.getLogger(__name__)


@dataclass
class EventRecord:
    """Parsed representation of a vault event file."""

    event_id: str
    title: str
    starts_at: datetime   # aware UTC
    ends_at: datetime     # aware UTC
    tz: str               # IANA zone identifier, e.g. "America/New_York"
    duration_minutes: int
    source_path: Path
    raw_meta: dict[str, Any] = field(default_factory=dict, repr=False)

    # -----------------------------------------------------------------------
    # Convenience properties
    # -----------------------------------------------------------------------

    @property
    def starts_at_local(self) -> datetime:
        """starts_at expressed in the event's declared timezone."""
        return self.starts_at.astimezone(ZoneInfo(self.tz))

    @property
    def ends_at_local(self) -> datetime:
        """ends_at expressed in the event's declared timezone."""
        return self.ends_at.astimezone(ZoneInfo(self.tz))

    @property
    def display_title(self) -> str:
        """
        Calendar-surface title: strips Herman's vault prefixes and replaces them
        with a compact visual marker suited to Calendar.app, iPhone, and Watch.

        Mapping:
            "[handle] <subject>"  → "✓ <subject>"   (to-do, normal criticality)
            "[handle!] <subject>" → "🔥 <subject>"  (to-do, critical)
            "<anything else>"     → unchanged        (regular meetings need no marker)

        Only a *leading* prefix is stripped — if "[handle]" appears mid-subject
        it is left as-is, preserving the vault author's intent for whatever odd
        reason they might have had.

        The raw ``title`` field is never mutated; vault truth is preserved.
        """
        if self.title.startswith("[handle!]"):
            remainder = self.title[len("[handle!]"):]
            subject = remainder.lstrip(" ")
            return f"🔥 {subject}" if subject else "🔥"
        if self.title.startswith("[handle]"):
            remainder = self.title[len("[handle]"):]
            subject = remainder.lstrip(" ")
            return f"✓ {subject}" if subject else "✓"
        return self.title

    @property
    def homunculus_url(self) -> str:
        """Canonical URL used to identify this event in Calendar.app."""
        return f"homunculus://event/{self.event_id}"


# ---------------------------------------------------------------------------
# Parsing helpers
# ---------------------------------------------------------------------------

def _parse_dt(value: Any, field_name: str, source_path: Path) -> datetime:
    """
    Parse an ISO 8601 string into an aware datetime (UTC).

    python-frontmatter may have already parsed it as a datetime object
    (PyYAML tries datetime parsing on unquoted values). Accept both.
    Raises ValueError on failure.
    """
    if isinstance(value, datetime):
        dt = value
    elif isinstance(value, str):
        # Python 3.11+ fromisoformat handles offset-aware strings like
        # '2026-09-15T09:00:00-04:00' directly.
        dt = datetime.fromisoformat(value)
    else:
        raise ValueError(
            f"{source_path}: field '{field_name}' has unexpected type "
            f"{type(value).__name__} (expected str or datetime)"
        )

    # Ensure aware; if naive, assume UTC (defensive only — Herman always writes offsets)
    if dt.tzinfo is None:
        log.warning(
            "%s: field '%s' is naive datetime; assuming UTC", source_path, field_name
        )
        dt = dt.replace(tzinfo=timezone.utc)

    return dt.astimezone(timezone.utc)


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

class VaultReaderError(Exception):
    """Raised when a vault file cannot be parsed into an EventRecord."""


def parse_event_file(path: Path) -> EventRecord:
    """
    Parse a Herman vault calendar .md file and return an EventRecord.

    Raises:
        VaultReaderError: if the file is missing required fields or is malformed.
        FileNotFoundError: if ``path`` does not exist.
    """
    try:
        post = frontmatter.load(str(path))
    except FileNotFoundError:
        raise  # let it propagate as-is for the caller's FileNotFoundError handling
    except Exception as exc:
        raise VaultReaderError(f"Cannot parse frontmatter in {path}: {exc}") from exc

    meta = dict(post.metadata)

    # Required fields
    missing = [f for f in ("id", "title", "starts_at", "ends_at", "tz") if f not in meta]
    if missing:
        raise VaultReaderError(
            f"{path}: missing required frontmatter fields: {missing}"
        )

    try:
        starts_at = _parse_dt(meta["starts_at"], "starts_at", path)
        ends_at = _parse_dt(meta["ends_at"], "ends_at", path)
    except (ValueError, TypeError) as exc:
        raise VaultReaderError(str(exc)) from exc

    if ends_at <= starts_at:
        raise VaultReaderError(
            f"{path}: ends_at ({meta['ends_at']}) must be after starts_at ({meta['starts_at']})"
        )

    # duration_minutes: derive from timestamps; fall back to frontmatter field
    computed_minutes = int((ends_at - starts_at).total_seconds() // 60)
    fm_minutes = meta.get("duration_minutes")
    if fm_minutes is not None and fm_minutes != computed_minutes:
        log.warning(
            "%s: duration_minutes=%d in frontmatter but computed=%d from timestamps; "
            "using computed value",
            path,
            fm_minutes,
            computed_minutes,
        )
    duration_minutes = computed_minutes

    return EventRecord(
        event_id=str(meta["id"]),
        title=str(meta["title"]),
        starts_at=starts_at,
        ends_at=ends_at,
        tz=str(meta["tz"]),
        duration_minutes=duration_minutes,
        source_path=path,
        raw_meta=meta,
    )


def scan_vault_calendar(calendar_root: Path) -> list[EventRecord]:
    """
    Recursively scan *calendar_root* for event .md files and parse them all.

    Skips files that fail to parse (logs a warning for each) so one corrupt
    file never stops the cold-boot sweep.

    Returns a list of EventRecord objects, unsorted.
    """
    records: list[EventRecord] = []
    md_files = sorted(calendar_root.rglob("*.md"))
    log.debug("scan_vault_calendar: found %d .md files under %s", len(md_files), calendar_root)

    for md_path in md_files:
        try:
            record = parse_event_file(md_path)
            records.append(record)
            log.debug("Parsed %s → event_id=%s", md_path.name, record.event_id)
        except VaultReaderError as exc:
            log.warning("Skipping %s: %s", md_path, exc)
        except FileNotFoundError:
            # Race: file deleted between glob and read
            log.warning("Skipping %s: file disappeared during scan", md_path)

    return records
