"""Timer manager — project stopwatch feature (Herman v2.0.0).

Design:
  - One JSON file per project: vault/timers/<slug>.json
  - Atomic write-rename (tmp + os.replace) — crash-safe
  - Article stripping before slugification: "the gym" → "gym"
  - Idempotent start: duplicate start returns original started_at
  - Notification-via-reminder: stop writes a ReminderRow-compatible row
    to vault/_reminders/ that /reminders/upcoming returns within 90 sec

Storage schema (vault/timers/<slug>.json):
  {
    "project": "gym",
    "slug": "gym",
    "running": {"started_at": "...", "record_id": "..."} | null,
    "sessions": [
      {"started_at": "...", "ended_at": "...", "duration_seconds": 2712, "record_id": "..."}
    ],
    "total_seconds": 15012,
    "last_touched_at": "..."
  }

Portability: no Mac-only imports. os.replace atomic on POSIX (macOS + Linux).
"""

from __future__ import annotations

import itertools
import json
import logging
import os
import re
import uuid as _uuid_module
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional
from zoneinfo import ZoneInfo

from . import activity_log
from .vault import slugify

log = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Tmp file counter (same pattern as vault.py)
# ---------------------------------------------------------------------------

_TMP_COUNTER = itertools.count()

# ---------------------------------------------------------------------------
# Article normalization
# ---------------------------------------------------------------------------

_LEADING_ARTICLES_RE = re.compile(
    r"^\s*(the|a|an)\s+", re.IGNORECASE
)


def _normalize_project(name: str) -> str:
    """Strip leading articles and normalize whitespace.

    'the Gym' → 'gym', 'a meeting' → 'meeting', 'an apple' → 'apple',
    'deck construction' → 'deck-construction' (after slugify).
    """
    cleaned = _LEADING_ARTICLES_RE.sub("", name.strip())
    return cleaned.strip()


def _project_slug(name: str) -> str:
    """Normalize articles, then slugify."""
    return slugify(_normalize_project(name))


# ---------------------------------------------------------------------------
# Exceptions
# ---------------------------------------------------------------------------


class NoRunningTimer(ValueError):
    """Raised when stop() is called for a project with no running timer."""
    pass


# ---------------------------------------------------------------------------
# Return types (plain dataclasses — no Pydantic overhead in the module layer)
# ---------------------------------------------------------------------------


@dataclass
class TimerStartResult:
    stored: bool
    record_id: str
    project: str
    slug: str
    started_at: datetime


@dataclass
class TimerStopResult:
    stored: bool
    record_id: str
    project: str
    slug: str
    duration_seconds: int
    total_seconds: int
    session_started_at: datetime
    session_ended_at: datetime


@dataclass
class RunningTimer:
    project: str
    slug: str
    started_at: datetime
    elapsed_seconds: int


@dataclass
class ProjectTotal:
    project: str
    slug: str
    total_seconds: int
    last_touched_at: datetime
    is_running: bool


# ---------------------------------------------------------------------------
# Atomic write helper
# ---------------------------------------------------------------------------


def _atomic_write_json(path: Path, data: dict) -> None:
    """Write a JSON dict to path atomically (tmp + os.replace)."""
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp_name = f"{path.name}.tmp.{os.getpid()}.{next(_TMP_COUNTER)}"
    tmp_path = path.with_name(tmp_name)
    try:
        with open(tmp_path, "w", encoding="utf-8") as f:
            f.write(json.dumps(data, indent=2, ensure_ascii=False, default=str))
            f.flush()
            os.fsync(f.fileno())
        os.replace(tmp_path, path)
    except Exception:
        import contextlib
        with contextlib.suppress(FileNotFoundError):
            os.unlink(tmp_path)
        raise


# ---------------------------------------------------------------------------
# Duration formatting
# ---------------------------------------------------------------------------


def format_duration(seconds: int) -> str:
    """Format a duration in seconds into human-readable text.

    - < 60 s:  "N seconds"
    - < 3600 s: "N minutes M seconds"
    - >= 3600 s: "N hours M minutes" (seconds omitted)
    """
    if seconds < 60:
        return f"{seconds} second{'s' if seconds != 1 else ''}"
    if seconds < 3600:
        mins = seconds // 60
        secs = seconds % 60
        if secs == 0:
            return f"{mins} minute{'s' if mins != 1 else ''} 0 seconds"
        return f"{mins} minute{'s' if mins != 1 else ''} {secs} second{'s' if secs != 1 else ''}"
    hours = seconds // 3600
    mins = (seconds % 3600) // 60
    return f"{hours} hour{'s' if hours != 1 else ''} {mins} minute{'s' if mins != 1 else ''}"


# ---------------------------------------------------------------------------
# TimerManager
# ---------------------------------------------------------------------------


class TimerManager:
    """Manages project stopwatch state in vault/timers/<slug>.json."""

    def __init__(self, vault_path: Path) -> None:
        self._vault = vault_path
        self._timers_dir = vault_path / "timers"

    def _timer_path(self, slug: str) -> Path:
        return self._timers_dir / f"{slug}.json"

    def _load(self, slug: str) -> Optional[dict]:
        path = self._timer_path(slug)
        if not path.exists():
            return None
        return json.loads(path.read_text(encoding="utf-8"))

    def _save(self, data: dict) -> None:
        _atomic_write_json(self._timer_path(data["slug"]), data)

    # --- Public API -------------------------------------------------------

    def start(self, project: str, captured_at: datetime, tz: ZoneInfo) -> TimerStartResult:
        """Start a stopwatch for *project*.

        Idempotent: if the timer is already running, return the original
        started_at without resetting. Logs a warning.
        """
        slug = _project_slug(project)
        # Canonical name: after article-strip but before slugify
        canonical = _normalize_project(project)

        data = self._load(slug)
        now_iso = captured_at.isoformat()
        record_id = str(_uuid_module.uuid4())

        if data is None:
            data = {
                "project": canonical,
                "slug": slug,
                "running": {
                    "started_at": now_iso,
                    "record_id": record_id,
                },
                "sessions": [],
                "total_seconds": 0,
                "last_touched_at": now_iso,
            }
        elif data.get("running") is not None:
            # Already running — idempotent: return existing state
            log.warning(
                "timer: start() called on already-running timer '%s' — ignoring", slug
            )
            started_at = datetime.fromisoformat(data["running"]["started_at"])
            return TimerStartResult(
                stored=True,
                record_id=data["running"]["record_id"],
                project=data["project"],
                slug=slug,
                started_at=started_at,
            )
        else:
            # Exists but stopped — restart
            data["running"] = {
                "started_at": now_iso,
                "record_id": record_id,
            }
            data["last_touched_at"] = now_iso

        self._save(data)

        # Activity log
        activity_log.log(
            self._vault,
            "timer_start",
            at=captured_at,
            details={
                "project": canonical,
                "slug": slug,
                "record_id": record_id,
            },
        )

        started_at = datetime.fromisoformat(data["running"]["started_at"])
        return TimerStartResult(
            stored=True,
            record_id=record_id,
            project=canonical,
            slug=slug,
            started_at=started_at,
        )

    def stop(self, project: str, captured_at: datetime, tz: ZoneInfo) -> TimerStopResult:
        """Stop a running timer for *project*.

        Raises NoRunningTimer if the project has no active stopwatch.
        Appends a session, updates total_seconds, clears running.
        """
        slug = _project_slug(project)
        data = self._load(slug)

        if data is None or data.get("running") is None:
            raise NoRunningTimer(
                f"No running timer for '{project}'. Say 'start {project}' first."
            )

        started_at = datetime.fromisoformat(data["running"]["started_at"])
        ended_at = captured_at
        # Ensure both are tz-aware for the subtraction
        if started_at.tzinfo is None:
            started_at = started_at.replace(tzinfo=tz)
        if ended_at.tzinfo is None:
            ended_at = ended_at.replace(tzinfo=tz)

        duration_seconds = max(0, int((ended_at - started_at).total_seconds()))
        record_id = str(_uuid_module.uuid4())

        session = {
            "started_at": started_at.isoformat(),
            "ended_at": ended_at.isoformat(),
            "duration_seconds": duration_seconds,
            "record_id": record_id,
        }
        data["sessions"].append(session)
        data["total_seconds"] = data.get("total_seconds", 0) + duration_seconds
        data["running"] = None
        data["last_touched_at"] = ended_at.isoformat()

        self._save(data)

        total_seconds = data["total_seconds"]

        # Activity log
        activity_log.log(
            self._vault,
            "timer_stop",
            at=captured_at,
            details={
                "project": data["project"],
                "slug": slug,
                "duration_seconds": duration_seconds,
                "total_seconds": total_seconds,
                "record_id": record_id,
            },
        )

        # Enqueue a notification via _reminders sidecar
        # Uses the same shape mac_notifier polls via /reminders/upcoming
        self._enqueue_stop_notification(
            project=data["project"],
            slug=slug,
            duration_seconds=duration_seconds,
            total_seconds=total_seconds,
            fired_at=ended_at,
            record_id=record_id,
        )

        return TimerStopResult(
            stored=True,
            record_id=record_id,
            project=data["project"],
            slug=slug,
            duration_seconds=duration_seconds,
            total_seconds=total_seconds,
            session_started_at=started_at,
            session_ended_at=ended_at,
        )

    def get_running(self) -> list[RunningTimer]:
        """Return all currently-running timers with elapsed_seconds at query time."""
        result: list[RunningTimer] = []
        if not self._timers_dir.exists():
            return result
        now = datetime.now(timezone.utc)
        for path in sorted(self._timers_dir.glob("*.json")):
            try:
                data = json.loads(path.read_text(encoding="utf-8"))
            except Exception:
                continue
            if data.get("running") is None:
                continue
            started_at = datetime.fromisoformat(data["running"]["started_at"])
            if started_at.tzinfo is None:
                started_at = started_at.replace(tzinfo=timezone.utc)
            elapsed = max(0, int((now - started_at.astimezone(timezone.utc)).total_seconds()))
            result.append(RunningTimer(
                project=data["project"],
                slug=data["slug"],
                started_at=started_at,
                elapsed_seconds=elapsed,
            ))
        return result

    def get_totals(self) -> list[ProjectTotal]:
        """Return cumulative totals for all projects, sorted by last_touched_at desc."""
        result: list[ProjectTotal] = []
        if not self._timers_dir.exists():
            return result
        for path in self._timers_dir.glob("*.json"):
            try:
                data = json.loads(path.read_text(encoding="utf-8"))
            except Exception:
                continue
            last_touched = datetime.fromisoformat(data["last_touched_at"])
            if last_touched.tzinfo is None:
                last_touched = last_touched.replace(tzinfo=timezone.utc)
            result.append(ProjectTotal(
                project=data["project"],
                slug=data["slug"],
                total_seconds=data.get("total_seconds", 0),
                last_touched_at=last_touched,
                is_running=data.get("running") is not None,
            ))
        result.sort(key=lambda t: t.last_touched_at, reverse=True)
        return result

    # --- Private helpers --------------------------------------------------

    def _enqueue_stop_notification(
        self,
        *,
        project: str,
        slug: str,
        duration_seconds: int,
        total_seconds: int,
        fired_at: datetime,
        record_id: str,
    ) -> None:
        """Write a _reminders sidecar row for the timer_stop notification.

        The mac_notifier polls /reminders/upcoming which reads these sidecars.
        fire_at = fired_at (now) → within 90s grace window mac_notifier fires it.
        """
        from . import vault

        identifier = f"timer.{slug}.{record_id}"
        duration_str = format_duration(duration_seconds)
        total_str = format_duration(total_seconds)
        # Capitalize project name for notification readability
        display_project = project.title() if project else project
        body = (
            f"{display_project} session: {duration_str}. "
            f"Total: {total_str} (all-time)."
        )

        sidecar = {
            "event_id": identifier,
            "kind": "timer_stop",
            "fire_at": fired_at.isoformat(),
            "tz": "UTC",
            "body": body,
            "status": "pending",
        }

        sidecar_path = vault.reminders_dir(self._vault) / f"{identifier}.json"
        _atomic_write_json(sidecar_path, {"event_id": identifier, "schedule": [sidecar]})
