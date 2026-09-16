"""
vault_reader.py — Parse Herman vault note .md files into structured NoteRecord objects.

Reads YAML frontmatter using python-frontmatter. No Mac-specific code; runs on Linux.

Expected frontmatter shape (from Herman/Sprite note writer):
    id: 2026-09-15-test-notes-mechanism
    title: test notes mechanism
    captured_at: '2026-09-15T22:38:55.659511+00:00'
    source: sprite
    audio_path: /path/to/audio.m4a
    confidence: 0.85

Body choice (per assignment spec):
    Pass raw markdown text as the note body. Notes.app renders it as plain text,
    which is readable and preserves the user's intent. This is the simplest
    approach — no markdown-to-HTML conversion dep, no rendering edge cases.
    The YAML frontmatter is stripped before body delivery; the user sees only
    the markdown prose.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import frontmatter  # python-frontmatter

log = logging.getLogger(__name__)


@dataclass
class NoteRecord:
    """Parsed representation of a vault note file."""

    note_id: str
    title: str
    captured_at: datetime   # aware UTC
    body: str               # raw markdown prose (frontmatter stripped)
    source_path: Path
    raw_meta: dict[str, Any] = field(default_factory=dict, repr=False)

    # -----------------------------------------------------------------------
    # Convenience properties
    # -----------------------------------------------------------------------

    @property
    def display_title(self) -> str:
        """
        Title for Notes.app `name` property.

        Notes titles are plain text — no transformation needed. The vault
        `title` field is clean prose (set by Herman's intent parse).
        """
        return self.title

    @property
    def notes_body(self) -> str:
        """
        Body string for Notes.app `body` property.

        We pass the raw markdown prose text from the vault body. Notes.app
        renders it as plain text — readable and correct. We do NOT convert
        to HTML: adding a markdown dependency for a feature the user never
        asked for is scope creep, and plain text in Notes.app is fine.

        The YAML frontmatter is already excluded because python-frontmatter
        gives us only the post.content (prose body). We strip leading/trailing
        whitespace and return the result.
        """
        return self.body.strip()


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
        # '2026-09-15T22:38:55.659511+00:00' directly.
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
    """Raised when a vault note file cannot be parsed into a NoteRecord."""


def parse_note_file(path: Path) -> NoteRecord:
    """
    Parse a Herman vault notes .md file and return a NoteRecord.

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
    missing = [f for f in ("id", "title", "captured_at") if f not in meta]
    if missing:
        raise VaultReaderError(
            f"{path}: missing required frontmatter fields: {missing}"
        )

    try:
        captured_at = _parse_dt(meta["captured_at"], "captured_at", path)
    except (ValueError, TypeError) as exc:
        raise VaultReaderError(str(exc)) from exc

    # Body: the markdown prose that follows the frontmatter
    body = post.content or ""

    return NoteRecord(
        note_id=str(meta["id"]),
        title=str(meta["title"]),
        captured_at=captured_at,
        body=body,
        source_path=path,
        raw_meta=meta,
    )


def scan_vault_notes(notes_root: Path) -> list[NoteRecord]:
    """
    Recursively scan *notes_root* for note .md files and parse them all.

    Skips files that fail to parse (logs a warning for each) so one corrupt
    file never stops the cold-boot sweep.

    Returns a list of NoteRecord objects, unsorted.
    """
    records: list[NoteRecord] = []
    if not notes_root.exists():
        log.debug("scan_vault_notes: notes root does not exist: %s", notes_root)
        return records

    md_files = sorted(notes_root.rglob("*.md"))
    log.debug("scan_vault_notes: found %d .md files under %s", len(md_files), notes_root)

    for md_path in md_files:
        try:
            record = parse_note_file(md_path)
            records.append(record)
            log.debug("Parsed %s → note_id=%s", md_path.name, record.note_id)
        except VaultReaderError as exc:
            log.warning("Skipping %s: %s", md_path, exc)
        except FileNotFoundError:
            # Race: file deleted between glob and read
            log.warning("Skipping %s: file disappeared during scan", md_path)

    return records
