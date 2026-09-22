"""
test_applescript.py — Tests for mac_reminders_bridge.applescript.

All AppleScript tests mock subprocess.run. osascript is NEVER invoked.
Platform-guard tests are exercised by patching sys.platform.
"""

from __future__ import annotations

import importlib
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from mac_reminders_bridge.applescript import (
    AppleScriptError,
    format_applescript_date,
    push_reminder,
    query_pushed_reminder_names,
    run_applescript,
    verify_list_exists,
)
from mac_reminders_bridge.vault_reader import ReminderRecord


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_record(
    event_id="2026-09-16-kiss-the-baby",
    title="kiss the baby",
    starts_at=None,
    tz="America/New_York",
    is_critical=False,
    verb="handle",
    body="Kiss the baby again.",
    source_path=None,
) -> ReminderRecord:
    return ReminderRecord(
        event_id=event_id,
        title=title,
        starts_at=starts_at,
        tz=tz,
        is_critical=is_critical,
        verb=verb,
        body=body,
        source_path=source_path or Path("/tmp/fake.md"),
    )


def _subprocess_ok(stdout: str = "") -> MagicMock:
    """Return a mock subprocess.CompletedProcess with returncode=0."""
    m = MagicMock()
    m.returncode = 0
    m.stdout = stdout
    m.stderr = ""
    return m


def _subprocess_fail(returncode: int = 1, stderr: str = "error") -> MagicMock:
    m = MagicMock()
    m.returncode = returncode
    m.stdout = ""
    m.stderr = stderr
    return m


# ---------------------------------------------------------------------------
# format_applescript_date
# ---------------------------------------------------------------------------

class TestFormatApplescriptDate:
    def test_basic_format(self):
        dt = datetime(2026, 9, 16, 12, 0, 0, tzinfo=timezone.utc)
        result = format_applescript_date(dt, "America/New_York")
        # 12:00 UTC = 08:00 AM EDT (UTC-4)
        assert "Wednesday" in result
        assert "September" in result
        assert "2026" in result

    def test_am_pm_morning(self):
        dt = datetime(2026, 9, 16, 12, 0, 0, tzinfo=timezone.utc)
        result = format_applescript_date(dt, "America/New_York")
        assert "AM" in result

    def test_am_pm_afternoon(self):
        dt = datetime(2026, 9, 16, 20, 0, 0, tzinfo=timezone.utc)
        result = format_applescript_date(dt, "America/New_York")
        assert "PM" in result

    def test_noon_is_pm(self):
        # 16:00 UTC = 12:00 PM EDT
        dt = datetime(2026, 9, 16, 16, 0, 0, tzinfo=timezone.utc)
        result = format_applescript_date(dt, "America/New_York")
        assert "PM" in result
        assert "12:00" in result

    def test_midnight_is_am(self):
        # 04:00 UTC = 00:00 AM EDT
        dt = datetime(2026, 9, 16, 4, 0, 0, tzinfo=timezone.utc)
        result = format_applescript_date(dt, "America/New_York")
        assert "AM" in result
        assert "12:00" in result

    def test_minute_zero_padding(self):
        dt = datetime(2026, 9, 16, 14, 5, 0, tzinfo=timezone.utc)
        result = format_applescript_date(dt, "America/New_York")
        assert ":05" in result

    def test_uses_target_timezone(self):
        dt = datetime(2026, 9, 16, 12, 0, 0, tzinfo=timezone.utc)
        ny = format_applescript_date(dt, "America/New_York")
        la = format_applescript_date(dt, "America/Los_Angeles")
        # Same UTC time → different local hours
        assert ny != la


# ---------------------------------------------------------------------------
# run_applescript
# ---------------------------------------------------------------------------

class TestRunApplescript:
    def test_success_returns_stripped_stdout(self):
        with patch("subprocess.run", return_value=_subprocess_ok("  hello  ")):
            result = run_applescript("-- test")
        assert result == "hello"

    def test_raises_on_nonzero_returncode(self):
        with patch("subprocess.run", return_value=_subprocess_fail(1, "syntax error")):
            with pytest.raises(AppleScriptError, match="syntax error"):
                run_applescript("bad script")

    def test_raises_on_timeout(self):
        with patch("subprocess.run", side_effect=subprocess.TimeoutExpired("osascript", 30)):
            with pytest.raises(AppleScriptError, match="timed out"):
                run_applescript("slow script")

    def test_raises_not_implemented_on_linux(self):
        with patch.object(sys, "platform", "linux"):
            with pytest.raises(NotImplementedError):
                run_applescript("-- test")

    def test_calls_osascript_with_e_flag(self):
        with patch("subprocess.run", return_value=_subprocess_ok("")) as mock_run:
            run_applescript("tell application \"Reminders\" to quit")
        args = mock_run.call_args[0][0]
        assert args[0] == "osascript"
        assert args[1] == "-e"

    def test_timeout_passed_to_subprocess(self):
        with patch("subprocess.run", return_value=_subprocess_ok("")) as mock_run:
            run_applescript("-- test", timeout=45)
        kwargs = mock_run.call_args[1]
        assert kwargs["timeout"] == 45


# ---------------------------------------------------------------------------
# verify_list_exists
# ---------------------------------------------------------------------------

class TestVerifyListExists:
    def test_returns_true_when_list_exists(self):
        with patch("mac_reminders_bridge.applescript.run_applescript", return_value="true"):
            assert verify_list_exists("Homunculus") is True

    def test_returns_false_when_list_absent(self):
        with patch("mac_reminders_bridge.applescript.run_applescript", return_value="false"):
            assert verify_list_exists("Homunculus") is False

    def test_case_insensitive_true(self):
        with patch("mac_reminders_bridge.applescript.run_applescript", return_value="True"):
            assert verify_list_exists("Homunculus") is True

    def test_raises_not_implemented_on_linux(self):
        with patch.object(sys, "platform", "linux"):
            with pytest.raises(NotImplementedError):
                verify_list_exists("Homunculus")

    def test_script_contains_list_name(self):
        with patch("mac_reminders_bridge.applescript.run_applescript", return_value="true") as mock_run:
            verify_list_exists("MyCustomList")
        script = mock_run.call_args[0][0]
        assert "MyCustomList" in script

    def test_propagates_applescript_error(self):
        with patch(
            "mac_reminders_bridge.applescript.run_applescript",
            side_effect=AppleScriptError("connection refused"),
        ):
            with pytest.raises(AppleScriptError):
                verify_list_exists("Homunculus")


# ---------------------------------------------------------------------------
# query_pushed_reminder_names (v0.1.2 — replaced query_pushed_reminder_ids)
# ---------------------------------------------------------------------------

class TestQueryPushedReminderNamesCompat:
    """Basic contract tests for query_pushed_reminder_names — kept in the
    pre-v0.1.2 test class location for continuity; full tests in
    TestQueryPushedReminderNames below."""

    def test_returns_empty_for_no_reminders(self):
        with patch("mac_reminders_bridge.applescript.run_applescript", return_value=""):
            names = query_pushed_reminder_names("Homunculus")
        assert names == []

    def test_returns_names_from_osascript_output(self):
        raw = "kiss the baby, call the vet"
        with patch("mac_reminders_bridge.applescript.run_applescript", return_value=raw):
            names = query_pushed_reminder_names("Homunculus")
        assert "kiss the baby" in names
        assert "call the vet" in names

    def test_raises_not_implemented_on_linux(self):
        with patch.object(sys, "platform", "linux"):
            with pytest.raises(NotImplementedError):
                query_pushed_reminder_names("Homunculus")

    def test_script_contains_list_name(self):
        with patch("mac_reminders_bridge.applescript.run_applescript", return_value="") as mock_run:
            query_pushed_reminder_names("MyList")
        script = mock_run.call_args[0][0]
        assert "MyList" in script

    def test_propagates_applescript_error(self):
        with patch(
            "mac_reminders_bridge.applescript.run_applescript",
            side_effect=AppleScriptError("timeout"),
        ):
            with pytest.raises(AppleScriptError):
                query_pushed_reminder_names("Homunculus")


# ---------------------------------------------------------------------------
# push_reminder
# ---------------------------------------------------------------------------

class TestPushReminder:
    def test_calls_run_applescript(self):
        record = _make_record()
        with patch("mac_reminders_bridge.applescript.run_applescript", return_value="") as mock_run:
            push_reminder(record, "Homunculus")
        mock_run.assert_called_once()

    def test_script_contains_display_title(self):
        record = _make_record(title="call the vet")
        with patch("mac_reminders_bridge.applescript.run_applescript", return_value="") as mock_run:
            push_reminder(record, "Homunculus")
        script = mock_run.call_args[0][0]
        assert "call the vet" in script

    def test_script_does_not_contain_url_property(self):
        """v0.1.1: url: removed from properties dict — Reminders.app rejects it (-1700)."""
        record = _make_record(event_id="2026-09-16-kiss-the-baby")
        with patch("mac_reminders_bridge.applescript.run_applescript", return_value="") as mock_run:
            push_reminder(record, "Homunculus")
        script = mock_run.call_args[0][0]
        props_start = script.index("{")
        props_end = script.rindex("}")
        props_block = script[props_start : props_end + 1].lower()
        assert "url:" not in props_block

    def test_script_does_not_contain_body_sentinel(self):
        """v0.1.2: [herman-id:...] sentinel removed — body must be clean utterance only."""
        record = _make_record(event_id="2026-09-16-kiss-the-baby")
        with patch("mac_reminders_bridge.applescript.run_applescript", return_value="") as mock_run:
            push_reminder(record, "Homunculus")
        script = mock_run.call_args[0][0]
        assert "[herman-id:" not in script

    def test_script_contains_list_name(self):
        record = _make_record()
        with patch("mac_reminders_bridge.applescript.run_applescript", return_value="") as mock_run:
            push_reminder(record, "Homunculus")
        script = mock_run.call_args[0][0]
        assert "Homunculus" in script

    def test_script_has_due_date_when_starts_at_set(self):
        dt = datetime(2026, 9, 16, 12, 0, 0, tzinfo=timezone.utc)
        record = _make_record(starts_at=dt)
        with patch("mac_reminders_bridge.applescript.run_applescript", return_value="") as mock_run:
            push_reminder(record, "Homunculus")
        script = mock_run.call_args[0][0]
        assert "due date" in script

    def test_script_has_no_due_date_when_starts_at_absent(self):
        record = _make_record(starts_at=None)
        with patch("mac_reminders_bridge.applescript.run_applescript", return_value="") as mock_run:
            push_reminder(record, "Homunculus")
        script = mock_run.call_args[0][0]
        assert "due date" not in script

    def test_script_has_no_remind_me_date(self):
        """No alarm — mac_notifier is authoritative (no double-fire)."""
        dt = datetime(2026, 9, 16, 12, 0, 0, tzinfo=timezone.utc)
        record = _make_record(starts_at=dt)
        with patch("mac_reminders_bridge.applescript.run_applescript", return_value="") as mock_run:
            push_reminder(record, "Homunculus")
        script = mock_run.call_args[0][0]
        assert "remind me date" not in script

    def test_raises_not_implemented_on_linux(self):
        record = _make_record()
        with patch.object(sys, "platform", "linux"):
            with pytest.raises(NotImplementedError):
                push_reminder(record, "Homunculus")

    def test_propagates_applescript_error(self):
        record = _make_record()
        with patch(
            "mac_reminders_bridge.applescript.run_applescript",
            side_effect=AppleScriptError("list not found"),
        ):
            with pytest.raises(AppleScriptError):
                push_reminder(record, "Homunculus")

    def test_title_quotes_escaped(self):
        """Double-quotes in title must not break the AppleScript string."""
        record = _make_record(title='say "hello" to Alice')
        with patch("mac_reminders_bridge.applescript.run_applescript", return_value="") as mock_run:
            push_reminder(record, "Homunculus")
        script = mock_run.call_args[0][0]
        # Unescaped " inside an AppleScript string literal would break it
        assert '\\"hello\\"' in script or 'say \\"hello\\"' in script

    def test_uses_single_make_new_reminder_command(self):
        """Atomic creation — only ONE 'make new reminder' call."""
        record = _make_record()
        with patch("mac_reminders_bridge.applescript.run_applescript", return_value="") as mock_run:
            push_reminder(record, "Homunculus")
        script = mock_run.call_args[0][0]
        assert script.count("make new reminder") == 1


# ---------------------------------------------------------------------------
# v0.1.1 regression tests — URL: property removed (AppleScript -1700 fix)
# ---------------------------------------------------------------------------

class TestV011RegressionNoUrlProperty:
    """
    Regression guard: Reminders.app rejects any properties dict that includes
    a URL: field, erroring with AppleScript error -1700.

    Empirically confirmed on Thomas's Mac 2026-09-19:
        {name:"test-url", body:"...", URL:"homunculus://reminder/test"} → -1700
        {name:"test-body", body:"..."} → success

    The body [herman-id:<event_id>] marker is the durable idempotency key.
    No URL property is needed.
    """

    def test_push_reminder_script_does_not_contain_url_property(self):
        """
        Regression #1: push_reminder must NOT emit URL: in the properties dict.

        This is the direct cause of the -1700 errors on cold-boot sweep.
        All 9 reminders failed because URL: appeared in the properties dict.
        """
        record = _make_record(event_id="2026-09-16-kiss-the-baby")
        with patch("mac_reminders_bridge.applescript.run_applescript", return_value="") as mock_run:
            push_reminder(record, "Homunculus")
        script = mock_run.call_args[0][0]
        # URL: must not appear inside the properties dict
        # (check for 'url:' case-insensitively — AppleScript is case-insensitive)
        props_start = script.index("{")
        props_end = script.rindex("}")
        props_block = script[props_start : props_end + 1].lower()
        assert "url:" not in props_block, (
            f"push_reminder emitted 'url:' in properties dict — Reminders.app "
            f"rejects this with -1700. Properties block: {props_block!r}"
        )

    def test_push_reminder_script_does_not_contain_body_sentinel(self):
        """
        Regression #2 (updated v0.1.2): body must NOT contain [herman-id:<event_id>].

        v0.1.1 used the body marker as the idempotency key. v0.1.2 removes it
        to keep the Reminders.app body field clean for the user.
        Idempotency is now via pushed.jsonl + name matching.
        """
        record = _make_record(event_id="2026-09-16-kiss-the-baby")
        with patch("mac_reminders_bridge.applescript.run_applescript", return_value="") as mock_run:
            push_reminder(record, "Homunculus")
        script = mock_run.call_args[0][0]
        assert "[herman-id:" not in script, (
            "body sentinel still present in v0.1.2 — must be removed"
        )

    def test_query_pushed_reminder_names_returns_names(self):
        """
        Regression #3 (updated v0.1.2): query_pushed_reminder_names returns
        reminder names (not event_ids extracted from body sentinels).
        """
        raw_names = "kiss the baby, renew car registration, call the vet"
        with patch("mac_reminders_bridge.applescript.run_applescript", return_value=raw_names):
            names = query_pushed_reminder_names("Homunculus")
        assert "kiss the baby" in names
        assert "renew car registration" in names

    def test_push_if_new_skips_when_title_in_reminders(self):
        """
        Regression #4 (updated v0.1.2): idempotency end-to-end via mock.

        push_if_new should skip a reminder whose display_title is already
        returned by query_pushed_reminder_names (name-based slow path).
        """
        from mac_reminders_bridge.watcher import push_if_new
        from mac_reminders_bridge.state import PushedState

        event_id = "2026-09-16-kiss-the-baby"

        import tempfile, os
        with tempfile.TemporaryDirectory() as tmpdir:
            state = PushedState(Path(tmpdir) / "pushed.jsonl")

            md_path = Path(tmpdir) / f"{event_id}.md"
            md_path.write_text(
                f"---\nid: {event_id}\ntitle: kiss the baby\ntz: America/New_York\nverb: handle\n---\nKiss the baby.\n",
                encoding="utf-8",
            )

            push_reminder_calls = []

            def fake_push(record, list_name):
                push_reminder_calls.append(record.event_id)

            # Slow path returns title already present
            with patch(
                "mac_reminders_bridge.watcher.query_pushed_reminder_names",
                return_value=["kiss the baby"],
            ), patch(
                "mac_reminders_bridge.watcher.push_reminder",
                side_effect=fake_push,
            ):
                push_if_new(md_path, state, "Homunculus")

        assert push_reminder_calls == [], (
            f"push_reminder was called despite title being in Reminders.app: "
            f"{push_reminder_calls}"
        )

    def test_no_url_scheme_in_applescript_module(self):
        """
        Regression #5: codebase guard.

        After the fix, the string 'homunculus://reminder/' must not appear
        in the AppleScript source module, and 'url:' must not appear in any
        AppleScript template strings in applescript.py.
        """
        import mac_reminders_bridge.applescript as as_mod
        src_path = Path(as_mod.__file__)
        src_text = src_path.read_text(encoding="utf-8")

        assert "homunculus://reminder/" not in src_text, (
            "homunculus://reminder/ URL scheme still present in applescript.py — "
            "Reminders.app does not support a url: property"
        )

        # Also assert 'url:' does not appear in any AppleScript template block
        # (i.e., inside an f-string that contains 'make new reminder with properties')
        # We do a focused check: if a line has 'url:' and 'properties' nearby, fail.
        lines = src_text.splitlines()
        for i, line in enumerate(lines):
            stripped = line.strip().lower()
            if "url:" in stripped and "name:" in stripped:
                raise AssertionError(
                    f"applescript.py line {i+1} looks like it emits url: in a "
                    f"properties dict: {line.strip()!r}"
                )


# ---------------------------------------------------------------------------
# v0.1.2 — Sentinel removed from AppleScript; name-based slow path
# ---------------------------------------------------------------------------

class TestV012NoSentinelInPushedBody:
    """
    v0.1.2: push_reminder must NOT embed [herman-id:...] in the AppleScript body.
    The sentinel was the v0.1.1 idempotency key; v0.1.2 uses name matching instead.
    """

    def test_push_reminder_body_has_no_herman_id_sentinel(self):
        """Primary assertion: no [herman-id:...] anywhere in the generated script."""
        record = _make_record(event_id="2026-09-16-kiss-the-baby", body="Kiss the baby.")
        with patch("mac_reminders_bridge.applescript.run_applescript", return_value="") as mock_run:
            push_reminder(record, "Homunculus")
        script = mock_run.call_args[0][0]
        assert "[herman-id:" not in script, (
            f"[herman-id:...] sentinel found in generated AppleScript — "
            f"must be removed in v0.1.2.\nScript:\n{script}"
        )

    def test_push_reminder_body_has_no_heading_line(self):
        """Body must not contain # heading lines — strip before embedding."""
        record = _make_record(body="# kiss the baby\n\nKiss the baby.")
        with patch("mac_reminders_bridge.applescript.run_applescript", return_value="") as mock_run:
            push_reminder(record, "Homunculus")
        script = mock_run.call_args[0][0]
        assert "# kiss" not in script, (
            "Heading line found in generated AppleScript body"
        )

    def test_push_reminder_body_has_no_captured_caption(self):
        """Body must not contain *Captured ... via Sprite.* caption."""
        record = _make_record(
            body="*Captured 2026-09-22 13:43 UTC via Sprite.*\n\nKiss the baby."
        )
        with patch("mac_reminders_bridge.applescript.run_applescript", return_value="") as mock_run:
            push_reminder(record, "Homunculus")
        script = mock_run.call_args[0][0]
        assert "Captured" not in script or "Sprite" not in script, (
            "Italic caption found in generated AppleScript body"
        )

    def test_no_herman_id_anywhere_in_applescript_module_source(self):
        """
        Hard codebase guard: the string '[herman-id:' must not appear anywhere
        in applescript.py after v0.1.2 (not in templates, not in comments,
        not in regex patterns).
        """
        import mac_reminders_bridge.applescript as as_mod
        src_path = Path(as_mod.__file__)
        src_text = src_path.read_text(encoding="utf-8")
        assert "[herman-id:" not in src_text, (
            "applescript.py still contains '[herman-id:' — this string must be "
            "completely removed in v0.1.2 (sentinel removed from UX + slow path)"
        )


class TestQueryPushedReminderNames:
    """
    v0.1.2: query_pushed_reminder_names() replaces query_pushed_reminder_ids().
    It queries `name of every reminder` (not `body of r`) and returns reminder
    names. Callers compare against the name they're about to push to detect dupes.
    """

    def test_returns_empty_for_no_reminders(self):
        with patch("mac_reminders_bridge.applescript.run_applescript", return_value=""):
            names = query_pushed_reminder_names("Homunculus")
        assert names == []

    def test_returns_single_name(self):
        with patch("mac_reminders_bridge.applescript.run_applescript", return_value="kiss the baby"):
            names = query_pushed_reminder_names("Homunculus")
        assert names == ["kiss the baby"]

    def test_returns_multiple_names(self):
        # osascript serialises an AppleScript list as comma-separated items
        raw = "kiss the baby, renew car registration, call the vet"
        with patch("mac_reminders_bridge.applescript.run_applescript", return_value=raw):
            names = query_pushed_reminder_names("Homunculus")
        assert len(names) == 3
        assert "kiss the baby" in names
        assert "renew car registration" in names

    def test_script_queries_name_not_body(self):
        """The AppleScript must query name, not body."""
        with patch("mac_reminders_bridge.applescript.run_applescript", return_value="") as mock_run:
            query_pushed_reminder_names("Homunculus")
        script = mock_run.call_args[0][0]
        assert "name" in script.lower()
        assert "body" not in script.lower(), (
            "query_pushed_reminder_names script queries body — should query name"
        )

    def test_script_contains_list_name(self):
        with patch("mac_reminders_bridge.applescript.run_applescript", return_value="") as mock_run:
            query_pushed_reminder_names("MyList")
        script = mock_run.call_args[0][0]
        assert "MyList" in script

    def test_raises_not_implemented_on_linux(self):
        with patch.object(sys, "platform", "linux"):
            with pytest.raises(NotImplementedError):
                query_pushed_reminder_names("Homunculus")

    def test_propagates_applescript_error(self):
        with patch(
            "mac_reminders_bridge.applescript.run_applescript",
            side_effect=AppleScriptError("timeout"),
        ):
            with pytest.raises(AppleScriptError):
                query_pushed_reminder_names("Homunculus")
