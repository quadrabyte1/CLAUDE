"""Sprite ambiguous-capture inbox — ~/sprite/inbox/YYYY-MM-DD.md.

When confidence < 0.6 (or ambiguous_fields is non-empty), the record is NOT
sent to Herman. Instead it is appended to a per-day markdown file in the
inbox directory. The user (or a future UI) can review and forward manually.

Atomicity discipline:
- Write to a temp file in the same directory (same filesystem → atomic rename).
- Existing content is read, new line appended, and the combined result
  written to the temp file, then renamed over the target.
- This guarantees two concurrent writes (rare but possible) don't corrupt.
"""

from __future__ import annotations

import logging
import os
import tempfile
from datetime import datetime, timezone
from pathlib import Path

log = logging.getLogger(__name__)

_HEADER = "# Sprite inbox — {date}\n\nAmbiguous or low-confidence captures for manual review.\n\n"


def inbox_path(inbox_dir: Path, at: datetime) -> Path:
    """Return the path for the inbox file for the given datetime's date (UTC)."""
    date_str = at.astimezone(timezone.utc).strftime("%Y-%m-%d")
    return inbox_dir / f"{date_str}.md"


def append_to_inbox(
    inbox_dir: Path,
    *,
    captured_at: datetime,
    transcript: str,
    verb_hint: str,
    subject_hint: str,
    confidence: float,
    ambiguous_fields: list[str],
    audio_path: str,
) -> Path:
    """Atomically append an ambiguous capture to the day's inbox file.

    Returns the path of the inbox file written.
    """
    inbox_dir.mkdir(parents=True, exist_ok=True)
    target = inbox_path(inbox_dir, captured_at)

    # Read existing content (or bootstrap header).
    if target.exists():
        existing = target.read_text(encoding="utf-8")
    else:
        date_str = captured_at.astimezone(timezone.utc).strftime("%Y-%m-%d")
        existing = _HEADER.format(date=date_str)

    # Build the new entry block.
    ts = captured_at.astimezone(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
    ambig = ", ".join(ambiguous_fields) if ambiguous_fields else "—"
    entry = (
        f"---\n"
        f"**Captured:** {ts}  \n"
        f"**Confidence:** {confidence:.2f}  \n"
        f"**Ambiguous fields:** {ambig}  \n"
        f"**Verb hint:** {verb_hint}  \n"
        f"**Subject hint:** {subject_hint}  \n"
        f"**Audio:** `{audio_path}`  \n"
        f"\n"
        f"> {transcript.strip()}\n\n"
    )
    new_content = existing + entry

    # Atomic write-rename (same directory → same filesystem guaranteed).
    fd, tmp_path = tempfile.mkstemp(dir=inbox_dir, suffix=".tmp")
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            f.write(new_content)
            f.flush()
            os.fsync(f.fileno())
        os.rename(tmp_path, target)
    except Exception:
        # Clean up temp on failure.
        try:
            os.unlink(tmp_path)
        except OSError:
            pass
        raise

    log.info("inbox: wrote ambiguous capture to %s (conf=%.2f)", target, confidence)
    return target
