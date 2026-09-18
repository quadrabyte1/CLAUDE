"""
state.py — Fired-notification dedup state for mac_notifier.

Tracks which reminder identifiers have already been fired as notifications.
Persisted as JSONL at ~/.local/share/mac_notifier/fired.jsonl
(one JSON object per line).

Identifier convention: "<event_id>:<kind>"
    e.g. "2026-09-16-handle-check-on-frozen-auditions:strike_0"

This scopes dedup to the specific reminder kind — the same event_id
appears with multiple kinds (heads_up_30, pre_5, strike_0, …), and all
of them should fire independently.

Design:
- Append-only, like vault/_activity.log. Never rewrite the file.
- Each line: {"identifier": str, "fired_at": iso8601-utc}
- On startup: load all lines to build the in-memory set. File duplicates
  are harmless (the set deduplicates them).
- Thread-safe via threading.Lock (single-threaded in v0.1 but safe for future).
- Missing state file → treated as empty. No crash.
- Malformed lines in state file → logged at WARNING, skipped. No crash.
"""

from __future__ import annotations

import json
import logging
import threading
from datetime import datetime, timezone
from pathlib import Path

log = logging.getLogger(__name__)


class FiredState:
    """
    Tracks reminder identifiers that have been fired as notifications.

    Usage::

        state = FiredState(Path("~/.local/share/mac_notifier/fired.jsonl"))
        if not state.is_fired("summary.2026-09-16:morning_summary"):
            # fire notification ...
            state.mark_fired("summary.2026-09-16:morning_summary")
    """

    def __init__(self, state_file: Path) -> None:
        self._file = state_file
        self._lock = threading.Lock()
        self._fired: set[str] = set()
        self._load()

    # -----------------------------------------------------------------------
    # Public API
    # -----------------------------------------------------------------------

    def is_fired(self, identifier: str) -> bool:
        """Return True if *identifier* has already been fired."""
        with self._lock:
            return identifier in self._fired

    def mark_fired(self, identifier: str) -> None:
        """
        Record *identifier* as fired.

        Appends a JSONL line to the state file and updates the in-memory set.
        """
        entry = {
            "identifier": identifier,
            "fired_at": datetime.now(timezone.utc).isoformat(),
        }
        with self._lock:
            self._fired.add(identifier)
            self._file.parent.mkdir(parents=True, exist_ok=True)
            with self._file.open("a", encoding="utf-8") as fh:
                fh.write(json.dumps(entry) + "\n")
        log.debug("State: marked %r as fired", identifier)

    def all_fired(self) -> frozenset[str]:
        """Return an immutable snapshot of all fired identifiers."""
        with self._lock:
            return frozenset(self._fired)

    def count(self) -> int:
        """Return the number of identifiers in the in-memory set."""
        with self._lock:
            return len(self._fired)

    # -----------------------------------------------------------------------
    # Internal
    # -----------------------------------------------------------------------

    def _load(self) -> None:
        """Load existing fired.jsonl into the in-memory set."""
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
                        identifier = obj["identifier"]
                        self._fired.add(identifier)
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
            "State loaded: %d fired identifiers (%d bad lines skipped) from %s",
            loaded,
            bad,
            self._file,
        )
