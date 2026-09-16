"""
state.py — Idempotency state for mac_notes_bridge.

Tracks which note_ids have already been pushed to Notes.app.
Persisted as JSONL at ~/.local/share/mac_notes_bridge/pushed.jsonl
(one JSON object per line).

Design notes:
- Append-only, like vault/_activity.log. Never rewrite the file.
- Each line is {"note_id": str, "pushed_at": iso8601-utc}.
- On startup, load all lines to build the in-memory set. Duplicates in the
  file are harmless (the set deduplicates them).
- Thread-safe via a simple threading.Lock (the watcher is single-threaded
  in v0.1 but let's be safe).

Idempotency strategy for Notes.app (different from Calendar bridge):
- Notes.app has no URL field or unique key accessible from AppleScript.
- We use a belt-and-suspenders approach:
    Fast path: pushed.jsonl in-memory set (O(1) lookup).
    Slow path: query Notes.app for a note with the exact title matching
               note_id (unique sentinel title check). If found, self-heal.
- We do NOT stash a marker in the note body — that would pollute the note
  content the user sees. The pushed.jsonl state file is the primary guard.
- The slow path (Notes.app query) exists so that if pushed.jsonl is wiped,
  a cold-boot sweep does not re-push every note and create duplicates.
"""

from __future__ import annotations

import json
import logging
import threading
from datetime import datetime, timezone
from pathlib import Path

log = logging.getLogger(__name__)


class PushedState:
    """
    Tracks note_ids that have been successfully pushed to Notes.app.

    Usage::

        state = PushedState(Path("~/.local/share/mac_notes_bridge/pushed.jsonl"))
        if not state.is_pushed("2026-09-15-test-notes-mechanism"):
            # push it ...
            state.mark_pushed("2026-09-15-test-notes-mechanism")
    """

    def __init__(self, state_file: Path) -> None:
        self._file = state_file
        self._lock = threading.Lock()
        self._pushed: set[str] = set()
        self._load()

    # -----------------------------------------------------------------------
    # Public API
    # -----------------------------------------------------------------------

    def is_pushed(self, note_id: str) -> bool:
        """Return True if *note_id* is in the pushed set."""
        with self._lock:
            return note_id in self._pushed

    def mark_pushed(self, note_id: str) -> None:
        """
        Record *note_id* as pushed.

        Appends a JSONL line to the state file and updates the in-memory set.
        """
        entry = {
            "note_id": note_id,
            "pushed_at": datetime.now(timezone.utc).isoformat(),
        }
        with self._lock:
            self._pushed.add(note_id)
            self._file.parent.mkdir(parents=True, exist_ok=True)
            with self._file.open("a", encoding="utf-8") as fh:
                fh.write(json.dumps(entry) + "\n")
        log.debug("State: marked %s as pushed", note_id)

    def all_pushed(self) -> frozenset[str]:
        """Return an immutable snapshot of all pushed note_ids."""
        with self._lock:
            return frozenset(self._pushed)

    def reset_from_ids(self, note_ids: set[str]) -> None:
        """
        Replace the in-memory pushed set with *note_ids*.

        Used after a slow Notes.app query to rebuild state without
        touching the file. The file is the source of truth for persistence;
        this method only updates RAM.
        """
        with self._lock:
            self._pushed = set(note_ids)
        log.debug("State: reset in-memory pushed set (%d entries)", len(note_ids))

    # -----------------------------------------------------------------------
    # Internal
    # -----------------------------------------------------------------------

    def _load(self) -> None:
        """Load existing pushed.jsonl into the in-memory set."""
        if not self._file.exists():
            log.debug("State file not found at %s; starting empty", self._file)
            return

        loaded = 0
        bad = 0
        try:
            with self._file.open("r", encoding="utf-8") as fh:
                for lineno, raw in enumerate(fh, 1):
                    raw = raw.strip()
                    if not raw:
                        continue
                    try:
                        obj = json.loads(raw)
                        note_id = obj["note_id"]
                        self._pushed.add(note_id)
                        loaded += 1
                    except (json.JSONDecodeError, KeyError) as exc:
                        log.warning(
                            "State file %s line %d: parse error (%s); skipping",
                            self._file,
                            lineno,
                            exc,
                        )
                        bad += 1
        except OSError as exc:
            log.error("Cannot read state file %s: %s", self._file, exc)
            return

        log.info(
            "State loaded: %d pushed note_ids (%d bad lines skipped) from %s",
            loaded,
            bad,
            self._file,
        )
