"""Sprite idempotency state — processed.jsonl (append-only).

No SQLite. One JSON object per line. Each line records a memo that Sprite has
successfully dispatched to Herman (or routed to inbox). The idempotency key is
the SHA-256 of the first 64 KB of the file bytes — stable across copies,
renames, and partial re-downloads.

Thread safety: file-level append is atomic on POSIX (O_APPEND). We never seek
or truncate, so concurrent appends from the same process are safe.
"""

from __future__ import annotations

import hashlib
import json
import logging
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

log = logging.getLogger(__name__)

_CHUNK = 64 * 1024  # 64 KB for the idempotency hash


# ---------------------------------------------------------------------------
# Public helpers
# ---------------------------------------------------------------------------


def file_key(path: Path) -> str:
    """Compute a stable idempotency key from the first 64 KB of a file.

    Using file content (not path or mtime) means the same audio data is
    idempotent even if the file moves or is renamed on re-download.
    Returns a 16-char hex prefix of SHA-256 — sufficient for uniqueness
    within a user's lifetime of voice memos.
    """
    h = hashlib.sha256()
    with path.open("rb") as f:
        chunk = f.read(_CHUNK)
    h.update(chunk)
    return h.hexdigest()[:16]


def is_processed(state_file: Path, key: str) -> bool:
    """Return True if *key* appears in the state log."""
    if not state_file.exists():
        return False
    try:
        text = state_file.read_text(encoding="utf-8")
    except OSError:
        return False
    for line in text.splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            row = json.loads(line)
        except json.JSONDecodeError:
            continue
        if row.get("key") == key:
            return True
    return False


def mark_processed(
    state_file: Path,
    key: str,
    *,
    audio_path: Optional[str] = None,
    record_id: Optional[str] = None,
    disposition: str = "posted",
    details: Optional[dict] = None,
) -> None:
    """Append a processed-record entry for *key*.

    ``disposition`` is one of:
      - ``"posted"``      — sent to Herman, stored=True (accepted)
      - ``"inbox"``       — low confidence / ambiguous, written to inbox BEFORE Herman
      - ``"clarifying"``  — sent to Herman, stored=False; Herman asked a clarifying
                            question surfaced to inbox. Cold-boot skips it (already
                            dispatched) but it is NOT the same as "posted".
      - ``"error"``       — pipeline error (details carries the message)
    """
    state_file.parent.mkdir(parents=True, exist_ok=True)
    entry = {
        "key": key,
        "processed_at": datetime.now(timezone.utc).isoformat(),
        "disposition": disposition,
        "audio_path": audio_path,
        "record_id": record_id,
        **(details or {}),
    }
    # O_APPEND is atomic on POSIX; no lock needed for single-line appends.
    with state_file.open("a", encoding="utf-8") as f:
        f.write(json.dumps(entry, ensure_ascii=False) + "\n")
    log.debug("state: marked %s as %s", key, disposition)
