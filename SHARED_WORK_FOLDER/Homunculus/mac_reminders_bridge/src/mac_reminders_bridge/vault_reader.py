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

v0.1.2 idempotency change: the [herman-id:<event_id>] body sentinel was removed.
Idempotency is now via pushed.jsonl fast-path + name-matching slow-path.
reminders_body contains only the clean utterance — no heading, no italic caption,
no sentinel, no blank lines.
"""

from __future__ import annotations

import logging
import re
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Optional

import frontmatter  # python-frontmatter

log = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Body-cleaning regexes (v0.1.2)
# ---------------------------------------------------------------------------

# Matches a markdown heading line: # heading, ## heading, etc.
_HEADING_RE = re.compile(r"^#{1,6}\s+.*$", re.MULTILINE)

# Matches the Sprite-inserted italic caption: *Captured <date/time> UTC via Sprite.*
_CAPTION_RE = re.compile(r"^\*Captured [^*]+via [^*]+\.\*\s*$", re.MULTILINE)

# Matches the legacy [herman-id:<anything>] sentinel
_HERMAN_ID_RE = re.compile(r"\[herman-id:[^\]]*\]")


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
        Body string for Reminders.app ``body`` property.

        v0.1.2: returns only the raw utterance — one clean line, no chrome.

        Strips from the raw vault body:
          - ``# heading`` lines (duplicate the title field)
          - ``*Captured ... via Sprite.*`` italic captions (metadata already
            in Reminders.app's own timestamp)
          - ``[herman-id:...]`` legacy sentinels (v0.1.1 idempotency key,
            now removed — idempotency via pushed.jsonl + name matching)
          - Leading/trailing blank lines
          - Consecutive interior blank lines (collapsed to zero)

        Falls back to ``self.title`` if the body is empty after stripping.

        No ``[herman-id:...]`` sentinel is appended. The sentinel was a UX
        leak and is not needed: idempotency is now belt-and-suspenders via
        pushed.jsonl (fast path) + query_pushed_reminder_names() (slow path).
        """
        return _clean_body(self.body, fallback=self.title)

# ---------------------------------------------------------------------------
# Body-cleaning helper (v0.1.2)
# ---------------------------------------------------------------------------

def _clean_body(raw: str, fallback: str = "") -> str:
    """
    Strip all chrome from a vault reminder body and return the clean utterance.

    Removes:
      - Markdown heading lines (# / ## / …)
      - Sprite italic captions (*Captured … via Sprite.*)
      - Legacy [herman-id:…] sentinels
      - Leading/trailing blank lines
      - Consecutive interior blank lines

    Falls back to *fallback* (the reminder's frontmatter title) if the result
    is empty after stripping.

    Returns a single stripped string with no leading/trailing whitespace.
    """
    text = raw

    # Strip heading lines
    text = _HEADING_RE.sub("", text)

    # Strip italic caption lines
    text = _CAPTION_RE.sub("", text)

    # Strip [herman-id:...] sentinels (inline or on their own line)
    text = _HERMAN_ID_RE.sub("", text)

    # Remove blank lines entirely — collapse all interior blank lines to zero.
    # Per Thomas's requirement: no blank lines between lines in Reminders.app.
    # First normalise \r\n to \n
    text = text.replace("\r\n", "\n").replace("\r", "\n")

    # Keep only non-empty lines (strips all blank lines — leading, trailing, interior)
    result_lines = [line.rstrip() for line in text.splitlines() if line.strip()]

    cleaned = "\n".join(result_lines).strip()

    if not cleaned:
        return fallback.strip()

    return cleaned


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
