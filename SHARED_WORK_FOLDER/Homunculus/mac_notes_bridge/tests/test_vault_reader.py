"""
test_vault_reader.py — Tests for vault_reader.py.

Uses tmp_path fixtures — never touches the live vault.
Includes fixtures based on the real note files that exist in the vault
(2026-09-15 notes from Sprite) so the parse logic is validated against them.
"""

from __future__ import annotations

import textwrap
from datetime import datetime, timezone
from pathlib import Path

import pytest

from mac_notes_bridge.vault_reader import (
    NoteRecord,
    VaultReaderError,
    parse_note_file,
    scan_vault_notes,
)


# ---------------------------------------------------------------------------
# Fixtures — vault note content mirroring the real files
# ---------------------------------------------------------------------------

TEST_NOTE_MD = textwrap.dedent("""\
    ---
    id: 2026-09-15-test-notes-mechanism
    title: test notes mechanism
    captured_at: '2026-09-15T22:38:55.659511+00:00'
    source: sprite
    audio_path: /Users/fourierflight/sprite/audio/2026/09/2f68955efbe092cc3647e35d763f78ce.m4a
    confidence: 0.85
    ---

    # test notes mechanism

    *Captured 2026-09-15 22:38 UTC via Sprite.*

    Take a note. We have to test that the notes mechanism works like it's supposed to.
""")

MECHANISM_NOTE_MD = textwrap.dedent("""\
    ---
    id: 2026-09-15-mechanism-to-close-the-loop-between-phone-and-mac
    title: mechanism to close the loop between phone and Mac
    captured_at: '2026-09-15T23:06:27.657772+00:00'
    source: sprite
    audio_path: /Users/fourierflight/sprite/audio/2026/09/1553dfc249048c691ac8ce070bd2edd8.m4a
    confidence: 0.85
    ---

    # mechanism to close the loop between phone and Mac

    *Captured 2026-09-15 23:06 UTC via Sprite.*

    Take a note. Maybe a mechanism to close the loop between the phone and the Mac.
""")


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def write_md(tmp_path: Path, filename: str, content: str) -> Path:
    p = tmp_path / filename
    p.write_text(content, encoding="utf-8")
    return p


# ---------------------------------------------------------------------------
# Tests: parse_note_file — the "test notes mechanism" note
# ---------------------------------------------------------------------------

class TestParseTestNote:
    def test_note_id(self, tmp_path):
        path = write_md(tmp_path, "note.md", TEST_NOTE_MD)
        rec = parse_note_file(path)
        assert rec.note_id == "2026-09-15-test-notes-mechanism"

    def test_title(self, tmp_path):
        path = write_md(tmp_path, "note.md", TEST_NOTE_MD)
        rec = parse_note_file(path)
        assert rec.title == "test notes mechanism"

    def test_captured_at_utc(self, tmp_path):
        path = write_md(tmp_path, "note.md", TEST_NOTE_MD)
        rec = parse_note_file(path)
        # 2026-09-15T22:38:55.659511+00:00 → UTC
        expected = datetime(2026, 9, 15, 22, 38, 55, 659511, tzinfo=timezone.utc)
        assert rec.captured_at == expected

    def test_body_not_empty(self, tmp_path):
        path = write_md(tmp_path, "note.md", TEST_NOTE_MD)
        rec = parse_note_file(path)
        assert rec.body.strip()

    def test_body_contains_prose(self, tmp_path):
        path = write_md(tmp_path, "note.md", TEST_NOTE_MD)
        rec = parse_note_file(path)
        assert "notes mechanism" in rec.body

    def test_body_does_not_contain_frontmatter(self, tmp_path):
        path = write_md(tmp_path, "note.md", TEST_NOTE_MD)
        rec = parse_note_file(path)
        # Frontmatter fields must not bleed into the body
        assert "captured_at:" not in rec.body
        assert "audio_path:" not in rec.body

    def test_source_path(self, tmp_path):
        path = write_md(tmp_path, "note.md", TEST_NOTE_MD)
        rec = parse_note_file(path)
        assert rec.source_path == path

    def test_display_title_equals_title(self, tmp_path):
        path = write_md(tmp_path, "note.md", TEST_NOTE_MD)
        rec = parse_note_file(path)
        assert rec.display_title == rec.title

    def test_notes_body_stripped(self, tmp_path):
        path = write_md(tmp_path, "note.md", TEST_NOTE_MD)
        rec = parse_note_file(path)
        # notes_body must have no leading/trailing whitespace
        body = rec.notes_body
        assert body == body.strip()

    def test_raw_meta_available(self, tmp_path):
        path = write_md(tmp_path, "note.md", TEST_NOTE_MD)
        rec = parse_note_file(path)
        assert "source" in rec.raw_meta
        assert rec.raw_meta["source"] == "sprite"


# ---------------------------------------------------------------------------
# Tests: parse_note_file — the mechanism note
# ---------------------------------------------------------------------------

class TestParseMechanismNote:
    def test_note_id(self, tmp_path):
        path = write_md(tmp_path, "mechanism.md", MECHANISM_NOTE_MD)
        rec = parse_note_file(path)
        assert rec.note_id == "2026-09-15-mechanism-to-close-the-loop-between-phone-and-mac"

    def test_title(self, tmp_path):
        path = write_md(tmp_path, "mechanism.md", MECHANISM_NOTE_MD)
        rec = parse_note_file(path)
        assert rec.title == "mechanism to close the loop between phone and Mac"

    def test_captured_at_utc(self, tmp_path):
        path = write_md(tmp_path, "mechanism.md", MECHANISM_NOTE_MD)
        rec = parse_note_file(path)
        expected = datetime(2026, 9, 15, 23, 6, 27, 657772, tzinfo=timezone.utc)
        assert rec.captured_at == expected

    def test_body_contains_prose(self, tmp_path):
        path = write_md(tmp_path, "mechanism.md", MECHANISM_NOTE_MD)
        rec = parse_note_file(path)
        assert "mechanism" in rec.body


# ---------------------------------------------------------------------------
# Tests: parse_note_file — minimal valid note (no optional fields)
# ---------------------------------------------------------------------------

class TestParseMinimalNote:
    def test_minimal_note_parses(self, tmp_path):
        content = textwrap.dedent("""\
            ---
            id: 2026-09-15-simple
            title: simple note
            captured_at: '2026-09-15T10:00:00+00:00'
            ---
            Body text here.
        """)
        path = write_md(tmp_path, "simple.md", content)
        rec = parse_note_file(path)
        assert rec.note_id == "2026-09-15-simple"
        assert rec.title == "simple note"
        assert rec.body.strip() == "Body text here."

    def test_note_with_empty_body(self, tmp_path):
        """Notes with no prose body (just frontmatter) parse cleanly."""
        content = textwrap.dedent("""\
            ---
            id: 2026-09-15-empty-body
            title: empty body
            captured_at: '2026-09-15T10:00:00+00:00'
            ---
        """)
        path = write_md(tmp_path, "empty.md", content)
        rec = parse_note_file(path)
        assert rec.note_id == "2026-09-15-empty-body"
        assert rec.notes_body == ""


# ---------------------------------------------------------------------------
# Tests: parse_note_file — error handling
# ---------------------------------------------------------------------------

class TestVaultReaderErrors:
    def test_missing_id_field(self, tmp_path):
        content = textwrap.dedent("""\
            ---
            title: no id
            captured_at: '2026-09-15T10:00:00+00:00'
            ---
            body
        """)
        path = write_md(tmp_path, "bad.md", content)
        with pytest.raises(VaultReaderError, match="missing required frontmatter"):
            parse_note_file(path)

    def test_missing_title_field(self, tmp_path):
        content = textwrap.dedent("""\
            ---
            id: 2026-09-15-no-title
            captured_at: '2026-09-15T10:00:00+00:00'
            ---
            body
        """)
        path = write_md(tmp_path, "bad.md", content)
        with pytest.raises(VaultReaderError, match="missing required frontmatter"):
            parse_note_file(path)

    def test_missing_captured_at(self, tmp_path):
        content = textwrap.dedent("""\
            ---
            id: 2026-09-15-no-ts
            title: no timestamp
            ---
            body
        """)
        path = write_md(tmp_path, "bad.md", content)
        with pytest.raises(VaultReaderError, match="missing required frontmatter"):
            parse_note_file(path)

    def test_bad_captured_at_format(self, tmp_path):
        content = textwrap.dedent("""\
            ---
            id: 2026-09-15-bad-ts
            title: bad timestamp
            captured_at: 'not-a-date'
            ---
            body
        """)
        path = write_md(tmp_path, "bad.md", content)
        with pytest.raises(VaultReaderError):
            parse_note_file(path)

    def test_file_not_found(self, tmp_path):
        with pytest.raises(FileNotFoundError):
            parse_note_file(tmp_path / "ghost.md")

    def test_no_frontmatter_raises(self, tmp_path):
        path = write_md(tmp_path, "bad.md", "just plain text with no frontmatter\n\nbody")
        with pytest.raises(VaultReaderError):
            parse_note_file(path)


# ---------------------------------------------------------------------------
# Tests: captured_at timezone handling
# ---------------------------------------------------------------------------

class TestCapturedAtTimezone:
    def test_aware_datetime_stored_as_utc(self, tmp_path):
        content = textwrap.dedent("""\
            ---
            id: 2026-09-15-tz-test
            title: tz test
            captured_at: '2026-09-15T18:00:00-04:00'
            ---
            body
        """)
        path = write_md(tmp_path, "tz.md", content)
        rec = parse_note_file(path)
        # 18:00 EDT (UTC-4) → 22:00 UTC
        assert rec.captured_at == datetime(2026, 9, 15, 22, 0, 0, tzinfo=timezone.utc)

    def test_utc_plus_zero_stored_as_utc(self, tmp_path):
        content = textwrap.dedent("""\
            ---
            id: 2026-09-15-utc
            title: utc test
            captured_at: '2026-09-15T12:00:00+00:00'
            ---
            body
        """)
        path = write_md(tmp_path, "utc.md", content)
        rec = parse_note_file(path)
        assert rec.captured_at == datetime(2026, 9, 15, 12, 0, 0, tzinfo=timezone.utc)

    def test_captured_at_is_aware(self, tmp_path):
        path = write_md(tmp_path, "note.md", TEST_NOTE_MD)
        rec = parse_note_file(path)
        assert rec.captured_at.tzinfo is not None


# ---------------------------------------------------------------------------
# Tests: scan_vault_notes
# ---------------------------------------------------------------------------

class TestScanVaultNotes:
    def test_empty_dir(self, tmp_path):
        notes_dir = tmp_path / "notes"
        notes_dir.mkdir()
        result = scan_vault_notes(notes_dir)
        assert result == []

    def test_missing_dir(self, tmp_path):
        result = scan_vault_notes(tmp_path / "nonexistent")
        assert result == []

    def test_finds_multiple_notes(self, tmp_path):
        notes_dir = tmp_path / "notes"
        notes_dir.mkdir()
        write_md(notes_dir, "2026-09-15-test-notes-mechanism.md", TEST_NOTE_MD)
        write_md(notes_dir, "2026-09-15-mechanism.md", MECHANISM_NOTE_MD)

        records = scan_vault_notes(notes_dir)
        assert len(records) == 2
        ids = {r.note_id for r in records}
        assert "2026-09-15-test-notes-mechanism" in ids
        assert "2026-09-15-mechanism-to-close-the-loop-between-phone-and-mac" in ids

    def test_skips_bad_files(self, tmp_path):
        notes_dir = tmp_path / "notes"
        notes_dir.mkdir()
        write_md(notes_dir, "good.md", TEST_NOTE_MD)
        write_md(notes_dir, "bad.md", "---\ntitle: broken\n---\n")

        records = scan_vault_notes(notes_dir)
        assert len(records) == 1
        assert records[0].note_id == "2026-09-15-test-notes-mechanism"

    def test_recursive_scan(self, tmp_path):
        notes_dir = tmp_path / "notes"
        sub = notes_dir / "2026-09"
        sub.mkdir(parents=True)
        write_md(sub, "2026-09-15-test-notes-mechanism.md", TEST_NOTE_MD)

        records = scan_vault_notes(notes_dir)
        assert len(records) == 1

    def test_ignores_non_md(self, tmp_path):
        notes_dir = tmp_path / "notes"
        notes_dir.mkdir()
        (notes_dir / "audio.m4a").write_bytes(b"not a note")
        write_md(notes_dir, "note.md", TEST_NOTE_MD)

        records = scan_vault_notes(notes_dir)
        assert len(records) == 1

    def test_returns_note_records(self, tmp_path):
        notes_dir = tmp_path / "notes"
        notes_dir.mkdir()
        write_md(notes_dir, "note.md", TEST_NOTE_MD)
        records = scan_vault_notes(notes_dir)
        assert all(isinstance(r, NoteRecord) for r in records)
