"""Tool notes, prompt notes, and inbox writers.

Each tool/prompt note is one markdown file in its own folder. Backlinks via
``[[wikilinks]]`` are written into the body so Obsidian's backlinks panel
surfaces the connections without any manual organization.
"""

from __future__ import annotations

from datetime import datetime
from pathlib import Path
from typing import Optional

from . import vault
from .schemas import ToolNote, PromptNote


def write_tool_note(
    vault_path: Path,
    title: str,
    captured_at: datetime,
    tags: Optional[list[str]] = None,
    source: str = "voice",
    source_utterance: Optional[str] = None,
    context: Optional[str] = None,
) -> tuple[ToolNote, Path]:
    tags = tags or []
    # Always tag with [[tools]] so the index note shows backlinks from everything.
    if "tools" not in tags:
        tags = ["tools", *tags]

    note = ToolNote(
        id=vault.note_id(captured_at, title),
        title=title,
        tags=tags,
        captured_at=captured_at,
        source=source,  # type: ignore[arg-type]
        source_utterance=source_utterance,
        context=context,
    )
    path = vault.tool_path(vault_path, title)
    vault.write_markdown(path, _tool_fm(note), _tool_body(note))
    return note, path


def _tool_fm(n: ToolNote) -> dict:
    return {
        "id": n.id,
        "title": n.title,
        "tags": n.tags,
        "captured_at": n.captured_at.isoformat(),
        "source": n.source,
        "source_utterance": n.source_utterance,
        "context": n.context,
    }


def _tool_body(n: ToolNote) -> str:
    tag_links = " ".join(f"[[{t}]]" for t in n.tags)
    ctx = f"\n*Context: {n.context}*\n" if n.context else ""
    return f"# {n.title}\n\nCaptured {n.captured_at.strftime('%Y-%m-%d')} from {n.source}.{ctx}\n\n{tag_links}".rstrip()


def write_prompt_note(
    vault_path: Path,
    title: str,
    captured_at: datetime,
    source: str = "voice",
    source_utterance: Optional[str] = None,
    body: Optional[str] = None,
) -> tuple[PromptNote, Path]:
    note = PromptNote(
        id=vault.note_id(captured_at, title),
        title=title,
        captured_at=captured_at,
        source=source,  # type: ignore[arg-type]
        source_utterance=source_utterance,
        body=body,
    )
    path = vault.prompt_path(vault_path, captured_at, title)
    vault.write_markdown(path, _prompt_fm(note), _prompt_body(note))
    return note, path


def _prompt_fm(n: PromptNote) -> dict:
    return {
        "id": n.id,
        "title": n.title,
        "captured_at": n.captured_at.isoformat(),
        "source": n.source,
        "source_utterance": n.source_utterance,
    }


def _prompt_body(n: PromptNote) -> str:
    body = n.body or "*(Body not yet captured. Add the prompt/answer text here.)*"
    return f"# {n.title}\n\nCaptured {n.captured_at.strftime('%Y-%m-%d')} from {n.source}.\n\n{body}\n\n[[claude-prompts]]".rstrip()


def write_inbox(
    vault_path: Path,
    captured_at: datetime,
    raw_text: str,
    best_guess: Optional[str],
    reason: str,
) -> Path:
    return vault.append_inbox(vault_path, captured_at, raw_text, best_guess, reason)
