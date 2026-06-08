"""Append-only activity log.

One JSON object per line at ``vault/_activity.jsonl``. The log captures
every meaningful action the brain takes so we can answer "why did it
think I said that?" or "when did that reminder get scheduled?" months
from now without re-deriving from code.

Append-only is deliberate. Editing or rewriting the log defeats its
audit-trail purpose. Rotation/truncation is a future concern; at one
line per capture, the file will stay tractable for years.
"""

from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path
from typing import Any, Iterable, Optional
from zoneinfo import ZoneInfo


_ACTIVITY_FILENAME = "_activity.jsonl"


def activity_path(vault_path: Path) -> Path:
    return vault_path / _ACTIVITY_FILENAME


def log(
    vault_path: Path,
    kind: str,
    *,
    at: Optional[datetime] = None,
    event_id: Optional[str] = None,
    raw_text: Optional[str] = None,
    details: Optional[dict[str, Any]] = None,
) -> None:
    """Append a single activity entry."""
    if at is None:
        at = datetime.now(ZoneInfo("America/New_York"))
    elif at.tzinfo is None:
        at = at.replace(tzinfo=ZoneInfo("America/New_York"))

    record = {
        "at": at.isoformat(),
        "kind": kind,
        "event_id": event_id,
        "raw_text": raw_text,
        "details": details or {},
    }

    path = activity_path(vault_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as f:
        f.write(json.dumps(record, default=str, ensure_ascii=False) + "\n")


def tail(vault_path: Path, n: int = 50) -> list[dict[str, Any]]:
    """Return the last `n` activity entries (oldest → newest within the slice)."""
    path = activity_path(vault_path)
    if not path.exists():
        return []
    lines = path.read_text(encoding="utf-8").splitlines()
    out: list[dict[str, Any]] = []
    for line in lines[-n:]:
        line = line.strip()
        if not line:
            continue
        try:
            out.append(json.loads(line))
        except json.JSONDecodeError:
            continue
    return out


def iter_entries(vault_path: Path) -> Iterable[dict[str, Any]]:
    """Stream every entry. Used by future tooling that wants the full log."""
    path = activity_path(vault_path)
    if not path.exists():
        return
    with path.open("r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                yield json.loads(line)
            except json.JSONDecodeError:
                continue
