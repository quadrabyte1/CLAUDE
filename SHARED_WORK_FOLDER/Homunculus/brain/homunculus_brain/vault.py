"""Markdown vault — the single source of truth.

Layout under ``vault_path``:

    calendar/2026-06/2026-06-12-coffee-with-jane.md   (one file per event)
    tools/craftsman-open-end-wrench.md                (one file per tool note)
    prompts/2026-06-07-rendering-rules.md             (one file per saved prompt)
    inbox.md                                          (append-only low-conf log)
    _reminders/<event-id>.json                        (reminder schedule sidecar)

Files are the truth. Anything that reads vault state reads the files; nothing
is cached in a separate database.

Concurrency / crash-safety discipline (v1.2):
- Every mutation goes through ``_atomic_write_text`` — write to a sibling
  ``<name>.tmp.<pid>.<counter>`` file, fsync, then ``os.replace`` onto the
  target. ``os.replace`` is atomic on POSIX filesystems, so a crash mid-write
  cannot leave a half-written event file in the vault.
- The inbox append is wrapped in an OS-level file lock via ``fcntl.flock``
  so two concurrent captures cannot interleave their writes or both write
  the header. ``fcntl`` is POSIX-only (macOS + Linux); that is the
  portability scope we care about. Windows is not a supported brain host.
"""

from __future__ import annotations

import contextlib
import fcntl
import itertools
import json
import os
import re
from datetime import date, datetime
from pathlib import Path
from typing import Any, Iterable, Iterator, Optional

import yaml


# Counter used to make per-process tmp filenames unique even when two threads
# write to the same target file within the same microsecond.
_TMP_COUNTER = itertools.count()


# --- slug + id generation -----------------------------------------------------


_SLUG_STRIP = re.compile(r"[^a-z0-9]+")


def slugify(text: str, max_length: int = 60) -> str:
    """Return a filesystem-safe slug. Empty input → 'untitled'."""
    s = text.strip().lower()
    s = _SLUG_STRIP.sub("-", s).strip("-")
    if not s:
        return "untitled"
    return s[:max_length].rstrip("-")


def event_id(starts_at: datetime, title: str) -> str:
    return f"{starts_at.date().isoformat()}-{slugify(title)}"


def note_id(captured_at: datetime, title: str) -> str:
    return f"{captured_at.date().isoformat()}-{slugify(title)}"


# --- frontmatter I/O ----------------------------------------------------------


_FRONTMATTER_FENCE = "---"


def _atomic_write_text(path: Path, content: str) -> None:
    """Write `content` to `path` atomically.

    Writes to a sibling temp file in the same directory (must be the same
    filesystem so that ``os.replace`` is atomic), fsyncs the bytes, then
    renames over the target. A crash before the rename leaves a stray .tmp
    file but never a half-written target. Two writes targeting the same
    path with different tmp names will both succeed; the second rename
    wins, but neither leaves a corrupt file behind.
    """
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp_name = f"{path.name}.tmp.{os.getpid()}.{next(_TMP_COUNTER)}"
    tmp_path = path.with_name(tmp_name)
    try:
        with open(tmp_path, "w", encoding="utf-8") as f:
            f.write(content)
            f.flush()
            os.fsync(f.fileno())
        os.replace(tmp_path, path)
    except Exception:
        # Best-effort cleanup; never raise from the cleanup branch.
        with contextlib.suppress(FileNotFoundError):
            os.unlink(tmp_path)
        raise


def write_markdown(path: Path, frontmatter: dict[str, Any], body: str) -> Path:
    rendered = (
        f"{_FRONTMATTER_FENCE}\n"
        f"{yaml.safe_dump(_jsonable(frontmatter), sort_keys=False).strip()}\n"
        f"{_FRONTMATTER_FENCE}\n\n"
        f"{body.rstrip()}\n"
    )
    _atomic_write_text(path, rendered)
    return path


def read_markdown(path: Path) -> tuple[dict[str, Any], str]:
    raw = path.read_text(encoding="utf-8")
    if not raw.startswith(_FRONTMATTER_FENCE):
        return {}, raw

    parts = raw.split(_FRONTMATTER_FENCE, 2)
    if len(parts) < 3:
        return {}, raw

    fm = yaml.safe_load(parts[1]) or {}
    body = parts[2].lstrip("\n")
    return fm, body


def _jsonable(d: dict[str, Any]) -> dict[str, Any]:
    """Convert datetimes/dates/sets to YAML-friendly primitives."""
    out: dict[str, Any] = {}
    for k, v in d.items():
        out[k] = _convert(v)
    return out


def _convert(v: Any) -> Any:
    if isinstance(v, datetime):
        return v.isoformat()
    if isinstance(v, date):
        return v.isoformat()
    if isinstance(v, (set, tuple)):
        return [_convert(x) for x in v]
    if isinstance(v, list):
        return [_convert(x) for x in v]
    if isinstance(v, dict):
        return {k: _convert(x) for k, x in v.items()}
    return v


# --- folder helpers -----------------------------------------------------------


def calendar_dir(vault_path: Path, when: datetime) -> Path:
    return vault_path / "calendar" / when.strftime("%Y-%m")


def calendar_event_path(vault_path: Path, starts_at: datetime, title: str) -> Path:
    return calendar_dir(vault_path, starts_at) / f"{event_id(starts_at, title)}.md"


def tools_dir(vault_path: Path) -> Path:
    return vault_path / "tools"


def tool_path(vault_path: Path, title: str) -> Path:
    return tools_dir(vault_path) / f"{slugify(title)}.md"


def prompts_dir(vault_path: Path) -> Path:
    return vault_path / "prompts"


def prompt_path(vault_path: Path, captured_at: datetime, title: str) -> Path:
    return prompts_dir(vault_path) / f"{note_id(captured_at, title)}.md"


def reminders_dir(vault_path: Path) -> Path:
    return vault_path / "_reminders"


def reminder_path(vault_path: Path, event_id_: str) -> Path:
    return reminders_dir(vault_path) / f"{event_id_}.json"


def inbox_path(vault_path: Path) -> Path:
    return vault_path / "inbox.md"


# --- inbox --------------------------------------------------------------------


_INBOX_HEADER = (
    "# Homunculus Inbox\n\nLow-confidence captures land here for manual sorting.\n\n"
)


@contextlib.contextmanager
def _flocked(path: Path) -> Iterator[None]:
    """Acquire an exclusive POSIX file lock against `<path>.lock`.

    The lock file is created next to the target. ``fcntl.flock`` is
    advisory; everyone who appends through this helper participates, so
    concurrent captures cannot interleave their writes. POSIX-only —
    macOS and Linux, which is the brain's supported portability scope.
    """
    path.parent.mkdir(parents=True, exist_ok=True)
    lock_path = path.with_name(path.name + ".lock")
    # Open for writing without truncation so a stale lockfile is harmless.
    fd = os.open(lock_path, os.O_WRONLY | os.O_CREAT, 0o644)
    try:
        fcntl.flock(fd, fcntl.LOCK_EX)
        try:
            yield
        finally:
            fcntl.flock(fd, fcntl.LOCK_UN)
    finally:
        os.close(fd)


def append_inbox(vault_path: Path, captured_at: datetime, raw_text: str, best_guess: Optional[str], reason: str) -> Path:
    path = inbox_path(vault_path)
    path.parent.mkdir(parents=True, exist_ok=True)

    entry = (
        f"## {captured_at.strftime('%Y-%m-%d %H:%M')} — {raw_text!r}\n"
        f"- Best guess: {best_guess or 'unknown'}\n"
        f"- Reason: {reason}\n\n"
    )

    with _flocked(path):
        # Re-check existence inside the lock so two simultaneous appenders
        # don't both decide to write the header.
        needs_header = not path.exists() or path.stat().st_size == 0
        with path.open("a", encoding="utf-8") as f:
            if needs_header:
                f.write(_INBOX_HEADER)
            f.write(entry)
            f.flush()
            os.fsync(f.fileno())
    return path


# --- listing helpers ---------------------------------------------------------


def iter_calendar_files(vault_path: Path) -> Iterable[Path]:
    cal = vault_path / "calendar"
    if not cal.exists():
        return iter(())
    return sorted(cal.glob("*/*.md"))


# --- reminder sidecar persistence --------------------------------------------


def write_reminder_schedule(vault_path: Path, event_id_: str, schedule: list[dict[str, Any]]) -> Path:
    path = reminder_path(vault_path, event_id_)
    payload = json.dumps(
        _jsonable({"event_id": event_id_, "schedule": schedule}),
        indent=2,
        default=str,
    )
    _atomic_write_text(path, payload)
    return path


def read_reminder_schedule(vault_path: Path, event_id_: str) -> Optional[dict[str, Any]]:
    path = reminder_path(vault_path, event_id_)
    if not path.exists():
        return None
    return json.loads(path.read_text(encoding="utf-8"))
