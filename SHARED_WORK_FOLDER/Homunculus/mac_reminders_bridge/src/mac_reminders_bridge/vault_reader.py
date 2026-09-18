"""
vault_reader.py — Parse Herman vault reminder .md files into ReminderRecord objects.

Reads YAML frontmatter using python-frontmatter. No Mac-specific code; runs on Linux.

Expected frontmatter shape (from Herman v1.6.0 capture_parsed._handle_handle):
    id: 2026-09-16-kiss-the-baby
    title: kiss the baby
    starts_at: '2026-09-16T08:00:00-04:00'
    tz: America/New_York
    source: sprite
    audio_path: /path/to/audio.m4a
    confidence: 0.9
    verb: handle   (or remind)
    criticality: critical   (only present when critical)
    created_at: '2026-09-16T05:35:55.086346-04:00'

The event_id field is used as the idempotency key. It is embedded in the note body
for the Reminders.app slow-path dedup check (since Reminders.app has a `url` property
that we can use, unlike Notes.app).
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Optional

import frontmatter  # python-frontmatter

log = logging.getLogger(__name__)


@dataclass
class ReminderRecord:
    """Parsed representation of a vault/reminders/ .md file."""

    event_id: str
    title: str
    starts_at: Optional[datetime]  # aware UTC, may be None for hint-only captures
    tz: str                        # IANA zone identifier, e.g. "America/New_York"
    is_critical: bool
    verb: str                      # "handle" or "remind" — preserved for provenance
    body: str                      # raw markdown prose (frontmatter stripped)
    source_path: Path
    raw_meta: dict[str, Any] = field(default_factory=dict, repr=False)

    # -----------------------------------------------------------------------
    # Convenience properties
    # -----------------------------------------------------------------------

    @property
    def display_title(self) -> str:
        """
        Title for Reminders.app `name` property.

        No prefix markers — the vault/reminders/ location is the semantic signal.
        Returns the raw subject as-is.
        """
        return self.title

    @property
    def reminders_body(self) -> str:
        """
        Body string for Reminders.app `body` property.

        Embeds the event_id as a sentinel so the slow-path idempotency check
        can find this reminder in Reminders.app without needing a title match.
        The event_id sentinel is appended after the prose body.
        """
        prose = self.body.strip()
        return f"{prose}\n\n[herman-id:{self.event_id}]"

    @property
    def homunculus_url(self) -> str:
        """Canonical URL for this reminder — embeds event_id for deduplication.

        Reminders.app DOES expose a `url` property in its AppleScript dictionary,
        unlike Notes.app. We use `homunculus://reminder/<event_id>` so the
        slow-path can query by URL instead of by title.
        """
        return f"homunculus://reminder/{self.event_id}"


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
        dt = datetime.fromisoformat(value)
    else:
        raise ValueError(
            f"{source_path}: field '{field_name}' has unexpected type "
            f"{type(value).__name__} (expected str or datetime)"
        )

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
    """Raised when a vault file cannot be parsed into a ReminderRecord."""


def parse_reminder_file(path: Path) -> ReminderRecord:
    """
    Parse a Herman vault/reminders/ .md file and return a ReminderRecord.

    Raises:
        VaultReaderError: if the file is missing required fields or is malformed.
        FileNotFoundError: if ``path`` does not exist.
    """
    try:
        post = frontmatter.load(str(path))
    except FileNotFoundError:
        raise  # let it propagate as-is
    except Exception as exc:
        raise VaultReaderError(f"Cannot parse frontmatter in {path}: {exc}") from exc

    meta = dict(post.metadata)

    # Required fields
    missing = [f for f in ("id", "title", "tz") if f not in meta]
    if missing:
        raise VaultReaderError(
            f"{path}: missing required frontmatter fields: {missing}"
        )

    # starts_at is optional (hint-only captures may not have it yet)
    starts_at: Optional[datetime] = None
    if "starts_at" in meta:
        try:
            starts_at = _parse_dt(meta["starts_at"], "starts_at", path)
        except (ValueError, TypeError) as exc:
            log.warning("%s: cannot parse starts_at: %s; treating as None", path, exc)

    is_critical = str(meta.get("criticality", "normal")).lower() == "critical"
    verb = str(meta.get("verb", "handle"))

    # Body: the markdown prose that follows the frontmatter
    body = post.content or ""

    return ReminderRecord(
        event_id=str(meta["id"]),
        title=str(meta["title"]),
        starts_at=starts_at,
        tz=str(meta["tz"]),
        is_critical=is_critical,
        verb=verb,
        body=body,
        source_path=path,
        raw_meta=meta,
    )


def scan_vault_reminders(reminders_root: Path) -> list[ReminderRecord]:
    """
    Scan *reminders_root* for reminder .md files and parse them all.

    Skips files that fail to parse (logs a warning for each) so one corrupt
    file never stops the cold-boot sweep.

    Returns a list of ReminderRecord objects, unsorted.
    """
    records: list[ReminderRecord] = []
    if not reminders_root.exists():
        log.debug("scan_vault_reminders: reminders root does not exist: %s", reminders_root)
        return records

    md_files = sorted(reminders_root.glob("*.md"))
    log.debug("scan_vault_reminders: found %d .md files under %s", len(md_files), reminders_root)

    for md_path in md_files:
        try:
            record = parse_reminder_file(md_path)
            records.append(record)
            log.debug("Parsed %s → event_id=%s", md_path.name, record.event_id)
        except VaultReaderError as exc:
            log.warning("Skipping %s: %s", md_path, exc)
        except FileNotFoundError:
            # Race: file deleted between glob and read
            log.warning("Skipping %s: file disappeared during scan", md_path)

    return records
