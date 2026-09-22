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

    def test_reminders_body_does_not_contain_sentinel(self):
        """v0.1.2: [herman-id:...] sentinel removed from reminders_body.
        Idempotency is now via pushed.jsonl + name matching."""
        record = self._make_record(event_id="2026-09-16-kiss-the-baby")
        assert "[herman-id:" not in record.reminders_body

    def test_reminders_body_contains_prose(self):
        record = self._make_record(body="Kiss the baby again.")
        assert "Kiss the baby again" in record.reminders_body

    def test_reminders_body_is_clean_utterance(self):
        """v0.1.2: reminders_body is the clean utterance, no chrome."""
        record = self._make_record(body="Kiss the baby again.")
        assert record.reminders_body == "Kiss the baby again."


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


# ---------------------------------------------------------------------------
# v0.1.2 — Body composition: clean utterance, no chrome
# ---------------------------------------------------------------------------

# The raw vault file content for the live regression test
_LIVE_VAULT_BODY = """\
---
id: 2026-10-30-renew-car-registration
title: renew car registration
starts_at: '2026-10-30T10:00:00-04:00'
tz: America/New_York
source: sprite
audio_path: /path/to/audio.m4a
confidence: 0.9
verb: remind
created_at: '2026-09-22T09:43:18.382675-04:00'
---

# renew car registration

*Captured 2026-09-22 13:43 UTC via Sprite.*

Remind me to renew the car registration on October 30th at 10 a.m.
"""

_EXPECTED_UTTERANCE = "Remind me to renew the car registration on October 30th at 10 a.m."


class TestBodyCompositionV012:
    """
    v0.1.2 body-cleaning tests.

    All assertions are against record.reminders_body (the value that gets
    written to Reminders.app's note field). The field must contain ONLY
    the raw utterance — no heading, no italic caption, no sentinel, no
    leading/trailing blank lines.
    """

    def _write_live_file(self, path: Path) -> Path:
        """Write a synthetic vault file matching the real 2026-10-30 reminder."""
        path.write_text(_LIVE_VAULT_BODY, encoding="utf-8")
        return path

    # --- Live regression ---

    def test_live_regression_exact_body(self, tmp_path):
        """
        Regression: parsing the 2026-10-30-renew-car-registration vault file
        must yield exactly the raw utterance as reminders_body — one line,
        no trailing whitespace, no newlines.
        """
        path = self._write_live_file(tmp_path / "2026-10-30-renew-car-registration.md")
        record = parse_reminder_file(path)
        assert record.reminders_body == _EXPECTED_UTTERANCE, (
            f"reminders_body mismatch.\n"
            f"Got:      {record.reminders_body!r}\n"
            f"Expected: {_EXPECTED_UTTERANCE!r}"
        )

    def test_live_regression_no_leading_trailing_whitespace(self, tmp_path):
        path = self._write_live_file(tmp_path / "2026-10-30-renew-car-registration.md")
        record = parse_reminder_file(path)
        assert record.reminders_body == record.reminders_body.strip()

    def test_live_regression_no_newlines(self, tmp_path):
        path = self._write_live_file(tmp_path / "2026-10-30-renew-car-registration.md")
        record = parse_reminder_file(path)
        assert "\n" not in record.reminders_body

    # --- Strip # heading ---

    def test_strips_h1_heading_line(self, tmp_path):
        path = tmp_path / "test.md"
        _write_reminder(
            path,
            _minimal_fm(),
            body="# kiss the baby\n\nKiss the baby please.",
        )
        record = parse_reminder_file(path)
        assert not record.reminders_body.startswith("#")
        assert "# kiss" not in record.reminders_body

    def test_strips_h2_heading_line(self, tmp_path):
        path = tmp_path / "test.md"
        _write_reminder(
            path,
            _minimal_fm(),
            body="## some heading\n\nActual utterance here.",
        )
        record = parse_reminder_file(path)
        assert "##" not in record.reminders_body

    def test_heading_strip_preserves_utterance(self, tmp_path):
        path = tmp_path / "test.md"
        _write_reminder(
            path,
            _minimal_fm(),
            body="# kiss the baby\n\nKiss the baby please.",
        )
        record = parse_reminder_file(path)
        assert "Kiss the baby please." in record.reminders_body

    # --- Strip italic caption ---

    def test_strips_italic_captured_caption(self, tmp_path):
        path = tmp_path / "test.md"
        _write_reminder(
            path,
            _minimal_fm(),
            body="*Captured 2026-09-22 13:43 UTC via Sprite.*\n\nActual utterance.",
        )
        record = parse_reminder_file(path)
        assert "Captured" not in record.reminders_body
        assert "Sprite" not in record.reminders_body

    def test_strips_italic_caption_various_dates(self, tmp_path):
        path = tmp_path / "test.md"
        _write_reminder(
            path,
            _minimal_fm(),
            body="*Captured 2025-12-31 23:59 UTC via Sprite.*\n\nDo the thing.",
        )
        record = parse_reminder_file(path)
        assert "*Captured" not in record.reminders_body
        assert "Do the thing." in record.reminders_body

    # --- Strip [herman-id:...] legacy sentinel ---

    def test_strips_legacy_herman_id_sentinel(self, tmp_path):
        path = tmp_path / "test.md"
        _write_reminder(
            path,
            _minimal_fm(event_id="test-id"),
            body="Do the thing.\n\n[herman-id:test-id]",
        )
        record = parse_reminder_file(path)
        assert "[herman-id:" not in record.reminders_body

    def test_strips_sentinel_from_any_position(self, tmp_path):
        """Sentinel at the start, middle, or end must all be stripped."""
        for body in [
            "[herman-id:x]\nDo the thing.",
            "Do the thing.\n[herman-id:x]",
            "Do [herman-id:x] the thing.",
        ]:
            path = tmp_path / "test.md"
            _write_reminder(path, _minimal_fm(), body=body)
            record = parse_reminder_file(path)
            assert "[herman-id:" not in record.reminders_body

    # --- Collapse blank lines ---

    def test_collapses_consecutive_blank_lines(self, tmp_path):
        path = tmp_path / "test.md"
        _write_reminder(
            path,
            _minimal_fm(),
            body="First line.\n\n\n\nSecond line.",
        )
        record = parse_reminder_file(path)
        # After cleaning, consecutive blank lines must be gone
        assert "\n\n" not in record.reminders_body

    def test_no_leading_blank_lines(self, tmp_path):
        path = tmp_path / "test.md"
        _write_reminder(path, _minimal_fm(), body="\n\n\nActual content.")
        record = parse_reminder_file(path)
        assert not record.reminders_body.startswith("\n")

    def test_no_trailing_blank_lines(self, tmp_path):
        path = tmp_path / "test.md"
        _write_reminder(path, _minimal_fm(), body="Actual content.\n\n\n")
        record = parse_reminder_file(path)
        assert not record.reminders_body.endswith("\n")

    # --- Fallback: empty body → use title ---

    def test_fallback_empty_body_returns_title(self, tmp_path):
        path = tmp_path / "test.md"
        _write_reminder(path, _minimal_fm(title="renew car registration"), body="")
        record = parse_reminder_file(path)
        assert record.reminders_body == "renew car registration"

    def test_fallback_only_heading_body_returns_title(self, tmp_path):
        """A body that has ONLY the heading (no utterance) should fall back to title."""
        path = tmp_path / "test.md"
        _write_reminder(
            path,
            _minimal_fm(title="kiss the baby"),
            body="# kiss the baby\n",
        )
        record = parse_reminder_file(path)
        assert record.reminders_body == "kiss the baby"

    def test_fallback_only_caption_body_returns_title(self, tmp_path):
        """A body with only the italic caption and sentinel should fall back to title."""
        path = tmp_path / "test.md"
        _write_reminder(
            path,
            _minimal_fm(title="check the mail"),
            body="*Captured 2026-09-22 13:43 UTC via Sprite.*\n\n[herman-id:check-the-mail]",
        )
        record = parse_reminder_file(path)
        assert record.reminders_body == "check the mail"

    # --- No sentinel in reminders_body ---

    def test_reminders_body_contains_no_sentinel(self, tmp_path):
        """v0.1.2: [herman-id:...] must NOT appear in reminders_body."""
        path = tmp_path / "test.md"
        _write_reminder(
            path,
            _minimal_fm(event_id="2026-09-16-kiss-the-baby"),
            body="Kiss the baby please.",
        )
        record = parse_reminder_file(path)
        assert "[herman-id:" not in record.reminders_body

    def test_reminders_body_is_single_line_for_typical_vault(self, tmp_path):
        """For the typical Herman vault file structure, body is exactly one line."""
        path = self._write_live_file(tmp_path / "2026-10-30-renew-car-registration.md")
        record = parse_reminder_file(path)
        lines = [l for l in record.reminders_body.splitlines() if l.strip()]
        assert len(lines) == 1
