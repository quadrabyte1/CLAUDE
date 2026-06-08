"""Markdown vault — the single source of truth.

Layout under ``vault_path``:

    calendar/2026-06/2026-06-12-coffee-with-jane.md   (one file per event)
    tools/craftsman-open-end-wrench.md                (one file per tool note)
    prompts/2026-06-07-rendering-rules.md             (one file per saved prompt)
    inbox.md                                          (append-only low-conf log)
    _reminders/<event-id>.json                        (reminder schedule sidecar)

Files are the truth. Anything that reads vault state reads the files; nothing
is cached in a separate database.
"""

from __future__ import annotations

import json
import re
from datetime import date, datetime
from pathlib import Path
from typing import Any, Iterable, Optional

import yaml


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


def write_markdown(path: Path, frontmatter: dict[str, Any], body: str) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    rendered = (
        f"{_FRONTMATTER_FENCE}\n"
        f"{yaml.safe_dump(_jsonable(frontmatter), sort_keys=False).strip()}\n"
        f"{_FRONTMATTER_FENCE}\n\n"
        f"{body.rstrip()}\n"
    )
    path.write_text(rendered, encoding="utf-8")
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


def append_inbox(vault_path: Path, captured_at: datetime, raw_text: str, best_guess: Optional[str], reason: str) -> Path:
    path = inbox_path(vault_path)
    path.parent.mkdir(parents=True, exist_ok=True)

    header = "" if path.exists() else "# Homunculus Inbox\n\nLow-confidence captures land here for manual sorting.\n\n"

    entry = (
        f"## {captured_at.strftime('%Y-%m-%d %H:%M')} — {raw_text!r}\n"
        f"- Best guess: {best_guess or 'unknown'}\n"
        f"- Reason: {reason}\n\n"
    )

    with path.open("a", encoding="utf-8") as f:
        if header:
            f.write(header)
        f.write(entry)
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
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(_jsonable({"event_id": event_id_, "schedule": schedule}), indent=2, default=str), encoding="utf-8")
    return path


def read_reminder_schedule(vault_path: Path, event_id_: str) -> Optional[dict[str, Any]]:
    path = reminder_path(vault_path, event_id_)
    if not path.exists():
        return None
    return json.loads(path.read_text(encoding="utf-8"))
