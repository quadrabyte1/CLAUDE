"""
test_vault_reader.py — Tests for mac_reminders_bridge.vault_reader.

Tests parse_reminder_file() and scan_vault_reminders() against tmp_path
fixtures. Never touches the live vault or real Reminders.app.
"""

from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path

import pytest

from mac_reminders_bridge.vault_reader import (
    ReminderRecord,
    VaultReaderError,
    parse_reminder_file,
    scan_vault_reminders,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _write_reminder(path: Path, frontmatter: dict, body: str = "") -> Path:
    """Write a reminder .md file with YAML frontmatter."""
    import yaml
    lines = ["---"]
    lines.append(yaml.safe_dump(frontmatter, sort_keys=False).strip())
    lines.append("---")
    lines.append("")
    lines.append(body)
    path.write_text("\n".join(lines), encoding="utf-8")
    return path


def _minimal_fm(
    event_id="2026-09-16-kiss-the-baby",
    title="kiss the baby",
    tz="America/New_York",
    **extra,
) -> dict:
    fm = {"id": event_id, "title": title, "tz": tz}
    fm.update(extra)
    return fm


# ---------------------------------------------------------------------------
# parse_reminder_file — happy paths
# ---------------------------------------------------------------------------

class TestParseReminderFileHappy:
    def test_parses_required_fields(self, tmp_path):
        path = tmp_path / "2026-09-16-kiss-the-baby.md"
        _write_reminder(path, _minimal_fm())
        record = parse_reminder_file(path)
        assert record.event_id == "2026-09-16-kiss-the-baby"
        assert record.title == "kiss the baby"
        assert record.tz == "America/New_York"

    def test_parses_starts_at(self, tmp_path):
        path = tmp_path / "test.md"
        _write_reminder(path, _minimal_fm(starts_at="2026-09-16T08:00:00-04:00"))
        record = parse_reminder_file(path)
        assert record.starts_at is not None
        # Stored as UTC
        assert record.starts_at.tzinfo is not None

    def test_starts_at_none_when_absent(self, tmp_path):
        path = tmp_path / "test.md"
        _write_reminder(path, _minimal_fm())
        record = parse_reminder_file(path)
        assert record.starts_at is None

    def test_is_critical_true_when_set(self, tmp_path):
        path = tmp_path / "test.md"
        _write_reminder(path, _minimal_fm(criticality="critical"))
        record = parse_reminder_file(path)
        assert record.is_critical is True

    def test_is_critical_false_when_normal(self, tmp_path):
        path = tmp_path / "test.md"
        _write_reminder(path, _minimal_fm(criticality="normal"))
        record = parse_reminder_file(path)
        assert record.is_critical is False

    def test_is_critical_false_when_absent(self, tmp_path):
        path = tmp_path / "test.md"
        _write_reminder(path, _minimal_fm())
        record = parse_reminder_file(path)
        assert record.is_critical is False

    def test_verb_handle(self, tmp_path):
        path = tmp_path / "test.md"
        _write_reminder(path, _minimal_fm(verb="handle"))
        record = parse_reminder_file(path)
        assert record.verb == "handle"

    def test_verb_remind(self, tmp_path):
        path = tmp_path / "test.md"
        _write_reminder(path, _minimal_fm(verb="remind"))
        record = parse_reminder_file(path)
        assert record.verb == "remind"

    def test_verb_defaults_to_handle(self, tmp_path):
        path = tmp_path / "test.md"
        _write_reminder(path, _minimal_fm())
        record = parse_reminder_file(path)
        assert record.verb == "handle"

    def test_body_parsed(self, tmp_path):
        path = tmp_path / "test.md"
        _write_reminder(path, _minimal_fm(), body="Kiss the baby again, please.")
        record = parse_reminder_file(path)
        assert "Kiss the baby" in record.body

    def test_source_path_preserved(self, tmp_path):
        path = tmp_path / "test.md"
        _write_reminder(path, _minimal_fm())
        record = parse_reminder_file(path)
        assert record.source_path == path


# ---------------------------------------------------------------------------
# parse_reminder_file — error paths
# ---------------------------------------------------------------------------

class TestParseReminderFileErrors:
    def test_raises_file_not_found(self, tmp_path):
        with pytest.raises(FileNotFoundError):
            parse_reminder_file(tmp_path / "nonexistent.md")

    def test_raises_vault_reader_error_missing_id(self, tmp_path):
        path = tmp_path / "test.md"
        _write_reminder(path, {"title": "test", "tz": "America/New_York"})
        with pytest.raises(VaultReaderError, match="id"):
            parse_reminder_file(path)

    def test_raises_vault_reader_error_missing_title(self, tmp_path):
        path = tmp_path / "test.md"
        _write_reminder(path, {"id": "test-id", "tz": "America/New_York"})
        with pytest.raises(VaultReaderError, match="title"):
            parse_reminder_file(path)

    def test_raises_vault_reader_error_missing_tz(self, tmp_path):
        path = tmp_path / "test.md"
        _write_reminder(path, {"id": "test-id", "title": "test"})
        with pytest.raises(VaultReaderError, match="tz"):
            parse_reminder_file(path)


# ---------------------------------------------------------------------------
# ReminderRecord — properties
# ---------------------------------------------------------------------------

class TestReminderRecordProperties:
    def _make_record(self, **kwargs) -> ReminderRecord:
        defaults = {
            "event_id": "2026-09-16-kiss-the-baby",
            "title": "kiss the baby",
            "starts_at": None,
            "tz": "America/New_York",
            "is_critical": False,
            "verb": "handle",
            "body": "Kiss the baby again.",
            "source_path": Path("/tmp/fake.md"),
        }
        defaults.update(kwargs)
        return ReminderRecord(**defaults)

    def test_display_title_is_plain_subject(self):
        record = self._make_record(title="kiss the baby")
        assert record.display_title == "kiss the baby"

    def test_display_title_no_handle_prefix(self):
        """display_title must not carry [handle] or [handle!] markers."""
        record = self._make_record(title="call the vet")
        assert "[handle]" not in record.display_title
        assert "[handle!]" not in record.display_title

    def test_reminders_body_contains_event_id_sentinel(self):
        record = self._make_record(event_id="2026-09-16-kiss-the-baby")
        assert "[herman-id:2026-09-16-kiss-the-baby]" in record.reminders_body

    def test_reminders_body_contains_prose(self):
        record = self._make_record(body="Kiss the baby again.")
        assert "Kiss the baby again" in record.reminders_body

    def test_homunculus_url_format(self):
        record = self._make_record(event_id="2026-09-16-kiss-the-baby")
        assert record.homunculus_url == "homunculus://reminder/2026-09-16-kiss-the-baby"

    def test_homunculus_url_prefix(self):
        record = self._make_record(event_id="abc123")
        assert record.homunculus_url.startswith("homunculus://reminder/")


# ---------------------------------------------------------------------------
# scan_vault_reminders
# ---------------------------------------------------------------------------

class TestScanVaultReminders:
    def test_empty_dir_returns_empty_list(self, tmp_path):
        result = scan_vault_reminders(tmp_path)
        assert result == []

    def test_nonexistent_dir_returns_empty_list(self, tmp_path):
        result = scan_vault_reminders(tmp_path / "nope")
        assert result == []

    def test_parses_multiple_files(self, tmp_path):
        for i in range(3):
            _write_reminder(
                tmp_path / f"2026-09-16-test-{i:02d}.md",
                _minimal_fm(event_id=f"2026-09-16-test-{i:02d}", title=f"test {i}"),
            )
        records = scan_vault_reminders(tmp_path)
        assert len(records) == 3

    def test_skips_corrupt_file_and_continues(self, tmp_path):
        # Good file
        _write_reminder(
            tmp_path / "good.md",
            _minimal_fm(event_id="good-id", title="good"),
        )
        # Corrupt file (missing required fields)
        bad = tmp_path / "bad.md"
        bad.write_text("---\nbroken: no id here\n---\n\nbody\n", encoding="utf-8")

        records = scan_vault_reminders(tmp_path)
        assert len(records) == 1
        assert records[0].event_id == "good-id"

    def test_ignores_non_md_files(self, tmp_path):
        (tmp_path / "not_a_reminder.txt").write_text("hello", encoding="utf-8")
        _write_reminder(tmp_path / "reminder.md", _minimal_fm())
        records = scan_vault_reminders(tmp_path)
        assert len(records) == 1
