"""
state.py — Idempotency state for mac_reminders_bridge.

Tracks which event_ids have already been pushed to Reminders.app.
Persisted as JSONL at ~/.local/share/mac_reminders_bridge/pushed.jsonl
(one JSON object per line).

Design notes:
- Append-only, like vault/_activity.log. Never rewrite the file.
- Each line is {"event_id": str, "pushed_at": iso8601-utc}.
- On startup, load all lines to build the in-memory set. Duplicates in the
  file are harmless (the set deduplicates them).
- Thread-safe via a simple threading.Lock (the watcher is single-threaded
  in v0.1 but let's be safe).

Idempotency strategy (belt-and-suspenders):
  Fast path: pushed.jsonl in-memory set (O(1) lookup).
  Slow path: query Reminders.app for reminders whose body contains a
             [herman-id:<event_id>] sentinel. If found, self-heal.
  The body sentinel is the durable idempotency key — Reminders.app's
  AppleScript dictionary does not expose a url property (error -1700).
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
    Tracks event_ids that have been successfully pushed to Reminders.app.

    Usage::

        state = PushedState(Path("~/.local/share/mac_reminders_bridge/pushed.jsonl"))
        if not state.is_pushed("2026-09-16-kiss-the-baby"):
            # push it ...
            state.mark_pushed("2026-09-16-kiss-the-baby")
    """

    def __init__(self, state_file: Path) -> None:
        self._file = state_file
        self._lock = threading.Lock()
        self._pushed: set[str] = set()
        self._load()

    # -----------------------------------------------------------------------
    # Public API
    # -----------------------------------------------------------------------

    def is_pushed(self, event_id: str) -> bool:
        """Return True if *event_id* is in the pushed set."""
        with self._lock:
            return event_id in self._pushed

    def mark_pushed(self, event_id: str) -> None:
        """
        Record *event_id* as pushed.

        Appends a JSONL line to the state file and updates the in-memory set.
        """
        entry = {
            "event_id": event_id,
            "pushed_at": datetime.now(timezone.utc).isoformat(),
        }
        with self._lock:
            self._pushed.add(event_id)
            self._file.parent.mkdir(parents=True, exist_ok=True)
            with self._file.open("a", encoding="utf-8") as fh:
                fh.write(json.dumps(entry) + "\n")
        log.debug("State: marked %s as pushed", event_id)

    def all_pushed(self) -> frozenset[str]:
        """Return an immutable snapshot of all pushed event_ids."""
        with self._lock:
            return frozenset(self._pushed)

    def reset_from_ids(self, event_ids: set[str]) -> None:
        """
        Replace the in-memory pushed set with *event_ids*.

        Used after a slow Reminders.app query to rebuild state without
        touching the file. The file is the source of truth for persistence;
        this method only updates RAM.
        """
        with self._lock:
            self._pushed = set(event_ids)
        log.debug("State: reset in-memory pushed set (%d entries)", len(event_ids))

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
                        event_id = obj["event_id"]
                        self._pushed.add(event_id)
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
            "State loaded: %d pushed event_ids (%d bad lines skipped) from %s",
            loaded,
            bad,
            self._file,
        )
