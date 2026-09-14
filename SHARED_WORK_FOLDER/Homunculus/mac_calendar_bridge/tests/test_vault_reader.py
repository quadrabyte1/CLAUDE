"""
test_vault_reader.py — Tests for vault_reader.py.

Uses tmp_path fixtures — never touches the live vault.
Includes fixtures based on the two real event files that exist in the vault
(Sep 15 + Sep 18 events) so the parse logic is validated against them.
"""

from __future__ import annotations

import textwrap
from datetime import datetime, timezone
from pathlib import Path

import pytest

from mac_calendar_bridge.vault_reader import (
    EventRecord,
    VaultReaderError,
    parse_event_file,
    scan_vault_calendar,
)


# ---------------------------------------------------------------------------
# Fixtures — vault event content mirroring the real files
# ---------------------------------------------------------------------------

MEETING_MD = textwrap.dedent("""\
    ---
    id: 2026-09-15-meeting-with-myself
    title: meeting with myself
    starts_at: '2026-09-15T09:00:00-04:00'
    ends_at: '2026-09-15T09:30:00-04:00'
    tz: America/New_York
    duration_minutes: 30
    people: []
    tags: []
    source: voice
    source_utterance: Sprite test one. Schedule a meeting with myself on September 15th at 9 a.m.
    created_at: '2026-09-13T17:53:46.985075-04:00'
    updated_at: '2026-09-13T17:53:46.985075-04:00'
    ---

    # meeting with myself

    Tuesday September 15 at 9:00 AM -04:00 (30 min).
""")

CODE_REVIEW_MD = textwrap.dedent("""\
    ---
    id: 2026-09-18-code-review-with-myself
    title: code review with myself
    starts_at: '2026-09-18T10:00:00-04:00'
    ends_at: '2026-09-18T10:30:00-04:00'
    tz: America/New_York
    duration_minutes: 30
    people: []
    tags: []
    source: voice
    source_utterance: Sprite test two schedule a code review with myself on September 18th at 10 a.m.
    created_at: '2026-09-14T15:13:34.171898-04:00'
    updated_at: '2026-09-14T15:13:34.171898-04:00'
    ---

    # code review with myself

    Friday September 18 at 10:00 AM -04:00 (30 min).
""")


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def write_md(tmp_path: Path, filename: str, content: str) -> Path:
    p = tmp_path / filename
    p.write_text(content, encoding="utf-8")
    return p


# ---------------------------------------------------------------------------
# Tests: parse the Sep 15 "meeting with myself" event
# ---------------------------------------------------------------------------

class TestParseMeetingEvent:
    def test_event_id(self, tmp_path):
        path = write_md(tmp_path, "meeting.md", MEETING_MD)
        rec = parse_event_file(path)
        assert rec.event_id == "2026-09-15-meeting-with-myself"

    def test_title(self, tmp_path):
        path = write_md(tmp_path, "meeting.md", MEETING_MD)
        rec = parse_event_file(path)
        assert rec.title == "meeting with myself"

    def test_starts_at_utc(self, tmp_path):
        path = write_md(tmp_path, "meeting.md", MEETING_MD)
        rec = parse_event_file(path)
        # 09:00 AM EDT (UTC-4) → 13:00 UTC
        expected = datetime(2026, 9, 15, 13, 0, 0, tzinfo=timezone.utc)
        assert rec.starts_at == expected

    def test_ends_at_utc(self, tmp_path):
        path = write_md(tmp_path, "meeting.md", MEETING_MD)
        rec = parse_event_file(path)
        # 09:30 AM EDT (UTC-4) → 13:30 UTC
        expected = datetime(2026, 9, 15, 13, 30, 0, tzinfo=timezone.utc)
        assert rec.ends_at == expected

    def test_tz(self, tmp_path):
        path = write_md(tmp_path, "meeting.md", MEETING_MD)
        rec = parse_event_file(path)
        assert rec.tz == "America/New_York"

    def test_duration_minutes(self, tmp_path):
        path = write_md(tmp_path, "meeting.md", MEETING_MD)
        rec = parse_event_file(path)
        assert rec.duration_minutes == 30

    def test_source_path(self, tmp_path):
        path = write_md(tmp_path, "meeting.md", MEETING_MD)
        rec = parse_event_file(path)
        assert rec.source_path == path

    def test_homunculus_url(self, tmp_path):
        path = write_md(tmp_path, "meeting.md", MEETING_MD)
        rec = parse_event_file(path)
        assert rec.homunculus_url == "homunculus://event/2026-09-15-meeting-with-myself"

    def test_starts_at_local(self, tmp_path):
        path = write_md(tmp_path, "meeting.md", MEETING_MD)
        rec = parse_event_file(path)
        local = rec.starts_at_local
        assert local.hour == 9
        assert local.minute == 0

    def test_ends_at_local(self, tmp_path):
        path = write_md(tmp_path, "meeting.md", MEETING_MD)
        rec = parse_event_file(path)
        local = rec.ends_at_local
        assert local.hour == 9
        assert local.minute == 30


# ---------------------------------------------------------------------------
# Tests: parse the Sep 18 "code review with myself" event
# ---------------------------------------------------------------------------

class TestParseCodeReviewEvent:
    def test_event_id(self, tmp_path):
        path = write_md(tmp_path, "code_review.md", CODE_REVIEW_MD)
        rec = parse_event_file(path)
        assert rec.event_id == "2026-09-18-code-review-with-myself"

    def test_title(self, tmp_path):
        path = write_md(tmp_path, "code_review.md", CODE_REVIEW_MD)
        rec = parse_event_file(path)
        assert rec.title == "code review with myself"

    def test_starts_at_utc(self, tmp_path):
        path = write_md(tmp_path, "code_review.md", CODE_REVIEW_MD)
        rec = parse_event_file(path)
        # 10:00 AM EDT (UTC-4) → 14:00 UTC
        expected = datetime(2026, 9, 18, 14, 0, 0, tzinfo=timezone.utc)
        assert rec.starts_at == expected

    def test_ends_at_utc(self, tmp_path):
        path = write_md(tmp_path, "code_review.md", CODE_REVIEW_MD)
        rec = parse_event_file(path)
        # 10:30 AM EDT (UTC-4) → 14:30 UTC
        expected = datetime(2026, 9, 18, 14, 30, 0, tzinfo=timezone.utc)
        assert rec.ends_at == expected

    def test_duration_minutes(self, tmp_path):
        path = write_md(tmp_path, "code_review.md", CODE_REVIEW_MD)
        rec = parse_event_file(path)
        assert rec.duration_minutes == 30

    def test_homunculus_url(self, tmp_path):
        path = write_md(tmp_path, "code_review.md", CODE_REVIEW_MD)
        rec = parse_event_file(path)
        assert rec.homunculus_url == "homunculus://event/2026-09-18-code-review-with-myself"

    def test_starts_at_local_friday(self, tmp_path):
        """Sep 18, 2026 is a Friday."""
        path = write_md(tmp_path, "code_review.md", CODE_REVIEW_MD)
        rec = parse_event_file(path)
        assert rec.starts_at_local.weekday() == 4  # Friday


# ---------------------------------------------------------------------------
# Tests: error handling
# ---------------------------------------------------------------------------

class TestVaultReaderErrors:
    def test_missing_id_field(self, tmp_path):
        content = textwrap.dedent("""\
            ---
            title: no id
            starts_at: '2026-09-15T09:00:00-04:00'
            ends_at: '2026-09-15T09:30:00-04:00'
            tz: America/New_York
            ---
            body
        """)
        path = write_md(tmp_path, "bad.md", content)
        with pytest.raises(VaultReaderError, match="missing required frontmatter"):
            parse_event_file(path)

    def test_missing_starts_at(self, tmp_path):
        content = textwrap.dedent("""\
            ---
            id: test-event
            title: Test
            ends_at: '2026-09-15T09:30:00-04:00'
            tz: America/New_York
            ---
        """)
        path = write_md(tmp_path, "bad.md", content)
        with pytest.raises(VaultReaderError, match="missing required frontmatter"):
            parse_event_file(path)

    def test_missing_tz(self, tmp_path):
        content = textwrap.dedent("""\
            ---
            id: test-event
            title: Test
            starts_at: '2026-09-15T09:00:00-04:00'
            ends_at: '2026-09-15T09:30:00-04:00'
            ---
        """)
        path = write_md(tmp_path, "bad.md", content)
        with pytest.raises(VaultReaderError, match="missing required frontmatter"):
            parse_event_file(path)

    def test_ends_before_starts(self, tmp_path):
        content = textwrap.dedent("""\
            ---
            id: inverted
            title: Inverted
            starts_at: '2026-09-15T09:30:00-04:00'
            ends_at: '2026-09-15T09:00:00-04:00'
            tz: America/New_York
            ---
        """)
        path = write_md(tmp_path, "bad.md", content)
        with pytest.raises(VaultReaderError, match="ends_at.*must be after"):
            parse_event_file(path)

    def test_file_not_found(self, tmp_path):
        with pytest.raises(FileNotFoundError):
            parse_event_file(tmp_path / "ghost.md")

    def test_bad_frontmatter(self, tmp_path):
        path = write_md(tmp_path, "bad.md", "not yaml at all\n\nbody")
        # python-frontmatter treats this as body-only with no metadata —
        # so we get a VaultReaderError about missing fields, not a parse crash
        with pytest.raises(VaultReaderError):
            parse_event_file(path)


# ---------------------------------------------------------------------------
# Tests: scan_vault_calendar
# ---------------------------------------------------------------------------

class TestScanVaultCalendar:
    def test_empty_dir(self, tmp_path):
        cal_dir = tmp_path / "calendar"
        cal_dir.mkdir()
        result = scan_vault_calendar(cal_dir)
        assert result == []

    def test_missing_dir(self, tmp_path):
        result = scan_vault_calendar(tmp_path / "nonexistent")
        assert result == []

    def test_finds_both_events(self, tmp_path):
        cal_dir = tmp_path / "calendar"
        month_dir = cal_dir / "2026-09"
        month_dir.mkdir(parents=True)
        write_md(month_dir, "2026-09-15-meeting-with-myself.md", MEETING_MD)
        write_md(month_dir, "2026-09-18-code-review-with-myself.md", CODE_REVIEW_MD)

        records = scan_vault_calendar(cal_dir)
        assert len(records) == 2
        ids = {r.event_id for r in records}
        assert "2026-09-15-meeting-with-myself" in ids
        assert "2026-09-18-code-review-with-myself" in ids

    def test_skips_bad_files(self, tmp_path):
        cal_dir = tmp_path / "calendar"
        cal_dir.mkdir()
        # Good file
        write_md(cal_dir, "good.md", MEETING_MD)
        # Bad file (missing fields)
        write_md(cal_dir, "bad.md", "---\ntitle: broken\n---\n")

        records = scan_vault_calendar(cal_dir)
        assert len(records) == 1
        assert records[0].event_id == "2026-09-15-meeting-with-myself"

    def test_recursive_scan(self, tmp_path):
        """Events in month subdirectories are found."""
        cal_dir = tmp_path / "calendar"
        month_dir = cal_dir / "2026-09"
        month_dir.mkdir(parents=True)
        write_md(month_dir, "2026-09-15-meeting-with-myself.md", MEETING_MD)

        records = scan_vault_calendar(cal_dir)
        assert len(records) == 1

    def test_ignores_non_md(self, tmp_path):
        cal_dir = tmp_path / "calendar"
        cal_dir.mkdir()
        (cal_dir / "notes.txt").write_text("not an event")
        write_md(cal_dir, "event.md", MEETING_MD)

        records = scan_vault_calendar(cal_dir)
        assert len(records) == 1

    def test_returns_event_records(self, tmp_path):
        cal_dir = tmp_path / "calendar"
        cal_dir.mkdir()
        write_md(cal_dir, "event.md", MEETING_MD)
        records = scan_vault_calendar(cal_dir)
        assert all(isinstance(r, EventRecord) for r in records)

    def test_duration_mismatch_uses_computed(self, tmp_path):
        """When frontmatter duration_minutes disagrees with timestamps, use timestamps."""
        content = textwrap.dedent("""\
            ---
            id: mismatch-event
            title: Duration Mismatch
            starts_at: '2026-09-15T09:00:00-04:00'
            ends_at: '2026-09-15T10:00:00-04:00'
            tz: America/New_York
            duration_minutes: 30
            ---
        """)
        cal_dir = tmp_path / "calendar"
        cal_dir.mkdir()
        write_md(cal_dir, "mismatch.md", content)
        records = scan_vault_calendar(cal_dir)
        assert len(records) == 1
        assert records[0].duration_minutes == 60  # computed from 9:00-10:00
