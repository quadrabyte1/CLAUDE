"""Tests for the vault read/write layer."""

from __future__ import annotations

from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

import pytest

from homunculus_brain import vault


TZ = ZoneInfo("America/New_York")


def test_slugify_basic():
    assert vault.slugify("Coffee with Jane") == "coffee-with-jane"
    assert vault.slugify("Craftsman Open-End Wrench") == "craftsman-open-end-wrench"
    assert vault.slugify("   ") == "untitled"
    assert vault.slugify("...???") == "untitled"


def test_event_id_combines_date_and_title():
    when = datetime(2026, 6, 12, 10, 0, tzinfo=TZ)
    assert vault.event_id(when, "Coffee with Jane") == "2026-06-12-coffee-with-jane"


def test_write_and_read_markdown_roundtrip(tmp_path: Path):
    path = tmp_path / "calendar" / "2026-06" / "test.md"
    frontmatter = {
        "id": "2026-06-12-coffee-with-jane",
        "title": "Coffee with Jane",
        "starts_at": datetime(2026, 6, 12, 10, 0, tzinfo=TZ),
        "people": ["Jane"],
    }
    body = "# Coffee with Jane\n\nNotes go here."

    vault.write_markdown(path, frontmatter, body)
    fm, returned_body = vault.read_markdown(path)

    assert fm["id"] == "2026-06-12-coffee-with-jane"
    assert fm["title"] == "Coffee with Jane"
    assert fm["people"] == ["Jane"]
    assert "Notes go here." in returned_body


def test_append_inbox_creates_header_once(tmp_path: Path):
    now = datetime(2026, 6, 7, 15, 23, tzinfo=TZ)
    vault.append_inbox(tmp_path, now, "did dot something", best_guess="tool_note", reason="low confidence")
    vault.append_inbox(tmp_path, now, "another fragment", best_guess=None, reason="unparseable")

    content = (tmp_path / "inbox.md").read_text(encoding="utf-8")
    assert content.count("# Homunculus Inbox") == 1
    assert "did dot something" in content
    assert "another fragment" in content


def test_iter_calendar_files_empty(tmp_path: Path):
    assert list(vault.iter_calendar_files(tmp_path)) == []


def test_iter_calendar_files_returns_written(tmp_path: Path):
    when = datetime(2026, 6, 12, 10, 0, tzinfo=TZ)
    path = vault.calendar_event_path(tmp_path, when, "Coffee with Jane")
    vault.write_markdown(path, {"id": "x", "title": "x"}, "body")
    files = list(vault.iter_calendar_files(tmp_path))
    assert len(files) == 1
    assert files[0].name.endswith("coffee-with-jane.md")


def test_reminder_schedule_roundtrip(tmp_path: Path):
    schedule = [{"kind": "strike_0", "fire_at": datetime(2026, 6, 12, 10, 0, tzinfo=TZ).isoformat()}]
    vault.write_reminder_schedule(tmp_path, "test-event", schedule)
    loaded = vault.read_reminder_schedule(tmp_path, "test-event")
    assert loaded is not None
    assert loaded["event_id"] == "test-event"
    assert loaded["schedule"][0]["kind"] == "strike_0"
