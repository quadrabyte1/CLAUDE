"""Tests for sprite.inbox — atomic append and ambiguity gate writes."""

from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path

import pytest

from sprite.inbox import append_to_inbox, inbox_path


_NOW = datetime(2026, 9, 13, 14, 30, 0, tzinfo=timezone.utc)


# ---------------------------------------------------------------------------
# inbox_path
# ---------------------------------------------------------------------------


def test_inbox_path_uses_utc_date(tmp_path):
    p = inbox_path(tmp_path, _NOW)
    assert p.name == "2026-09-13.md"
    assert p.parent == tmp_path


def test_inbox_path_different_days_differ(tmp_path):
    from datetime import timedelta
    d1 = _NOW
    d2 = _NOW + timedelta(days=1)
    assert inbox_path(tmp_path, d1) != inbox_path(tmp_path, d2)


# ---------------------------------------------------------------------------
# append_to_inbox
# ---------------------------------------------------------------------------


def test_creates_inbox_dir_and_file(tmp_path):
    inbox_dir = tmp_path / "inbox"
    assert not inbox_dir.exists()
    result = append_to_inbox(
        inbox_dir,
        captured_at=_NOW,
        transcript="call the deck contractor Thursday",
        verb_hint="handle",
        subject_hint="call deck contractor",
        confidence=0.45,
        ambiguous_fields=["when"],
        audio_path="/tmp/test.m4a",
    )
    assert inbox_dir.exists()
    assert result.exists()
    assert result.name == "2026-09-13.md"


def test_inbox_file_contains_header_on_first_write(tmp_path):
    inbox_dir = tmp_path / "inbox"
    result = append_to_inbox(
        inbox_dir,
        captured_at=_NOW,
        transcript="some memo",
        verb_hint="note",
        subject_hint="something",
        confidence=0.4,
        ambiguous_fields=[],
        audio_path="/tmp/x.m4a",
    )
    text = result.read_text()
    assert "# Sprite inbox — 2026-09-13" in text


def test_inbox_entry_contains_key_fields(tmp_path):
    inbox_dir = tmp_path / "inbox"
    append_to_inbox(
        inbox_dir,
        captured_at=_NOW,
        transcript="remember to call the contractor",
        verb_hint="handle",
        subject_hint="call contractor",
        confidence=0.42,
        ambiguous_fields=["when", "subject"],
        audio_path="/Users/thomas/sprite/audio/x.m4a",
    )
    text = (inbox_dir / "2026-09-13.md").read_text()
    assert "0.42" in text
    assert "when, subject" in text
    assert "handle" in text
    assert "call contractor" in text
    assert "/Users/thomas/sprite/audio/x.m4a" in text
    assert "remember to call the contractor" in text


def test_append_twice_does_not_duplicate_header(tmp_path):
    inbox_dir = tmp_path / "inbox"
    for i in range(2):
        from datetime import timedelta
        append_to_inbox(
            inbox_dir,
            captured_at=_NOW + timedelta(minutes=i * 5),
            transcript=f"memo {i}",
            verb_hint="note",
            subject_hint=f"subject {i}",
            confidence=0.3,
            ambiguous_fields=[],
            audio_path="/tmp/x.m4a",
        )
    text = (inbox_dir / "2026-09-13.md").read_text()
    assert text.count("# Sprite inbox") == 1
    assert "memo 0" in text
    assert "memo 1" in text


def test_empty_ambiguous_fields_shown_as_dash(tmp_path):
    inbox_dir = tmp_path / "inbox"
    append_to_inbox(
        inbox_dir,
        captured_at=_NOW,
        transcript="just a note",
        verb_hint="note",
        subject_hint="note",
        confidence=0.55,
        ambiguous_fields=[],
        audio_path="/tmp/x.m4a",
    )
    text = (inbox_dir / "2026-09-13.md").read_text()
    assert "**Ambiguous fields:** —" in text


def test_atomic_write_no_partial_on_existing_content(tmp_path):
    """Verify that appending to existing file preserves original content."""
    inbox_dir = tmp_path / "inbox"
    inbox_file = inbox_dir / "2026-09-13.md"
    inbox_dir.mkdir()
    original = "# Sprite inbox — 2026-09-13\n\nOriginal content.\n\n"
    inbox_file.write_text(original)

    append_to_inbox(
        inbox_dir,
        captured_at=_NOW,
        transcript="new entry",
        verb_hint="handle",
        subject_hint="new",
        confidence=0.3,
        ambiguous_fields=["when"],
        audio_path="/tmp/y.m4a",
    )
    text = inbox_file.read_text()
    assert "Original content." in text
    assert "new entry" in text
