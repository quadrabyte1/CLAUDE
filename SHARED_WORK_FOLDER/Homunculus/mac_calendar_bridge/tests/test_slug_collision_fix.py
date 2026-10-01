"""
test_slug_collision_fix.py — TDD tests for the same-slug dedup bug.

Root cause (discovered 2026-09-30):
    vault.event_id() generates ids as "<date>-<title-slug>".
    Two voice memos on the same day with the same title word ("dinner") but
    different times both produce event_id = "2026-09-30-dinner".

    The bridge's pushed.jsonl marks "2026-09-30-dinner" pushed on the first
    event.  The second memo (different time, same title) hits the fast-path
    dedup check and is silently skipped — never appears in Calendar.app.

Bugs addressed:
  Bug A — vault.event_id() collision: same-day same-title → same id even with
           different start times.  Fix: include HH:MM (local time) in the slug.

  Bug B — Silent skip visibility: when push_if_new hits the fast-path, it logs
           at DEBUG level.  At INFO (the default), there is no log entry.
           Thomas sees nothing; the calendar stays empty; trust erodes.
           Fix: promote the "already pushed — skipping" message to INFO and
           include both the event_id AND the event's starts_at so a re-schedule
           collision is immediately diagnosable.

  Bug C — Permission-denied must surface as ERROR (not silent).
           Already partially tested in test_watcher.py but not validated that
           log.error() is actually called.

v0.2.1 regression suite.
"""

from __future__ import annotations

import logging
import textwrap
from datetime import datetime, timezone
from pathlib import Path
from unittest.mock import patch

import pytest

from mac_calendar_bridge.state import PushedState
from mac_calendar_bridge.watcher import push_if_new


# ---------------------------------------------------------------------------
# Shared MD fixtures — same title, different times
# ---------------------------------------------------------------------------

# "Schedule dinner at 7 PM" — event at 19:00 local
DINNER_7PM_MD = textwrap.dedent("""\
    ---
    id: 2026-09-30-dinner-19-00
    title: dinner
    starts_at: '2026-09-30T19:00:00-04:00'
    ends_at: '2026-09-30T19:30:00-04:00'
    tz: America/New_York
    duration_minutes: 30
    people: []
    tags: []
    source: voice
    source_utterance: Schedule dinner at 7.
    created_at: '2026-09-30T15:38:12.000000-04:00'
    updated_at: '2026-09-30T15:38:12.000000-04:00'
    ---

    # dinner

    Wednesday September 30 at 7:00 PM EDT (30 min).
""")

# "Scheduled dinner at 8 PM" — event at 20:00 local, same date+title
DINNER_8PM_MD = textwrap.dedent("""\
    ---
    id: 2026-09-30-dinner-20-00
    title: dinner
    starts_at: '2026-09-30T20:00:00-04:00'
    ends_at: '2026-09-30T20:30:00-04:00'
    tz: America/New_York
    duration_minutes: 30
    people: []
    tags: []
    source: voice
    source_utterance: Scheduled dinner at 8.
    created_at: '2026-09-30T11:41:03.000000-04:00'
    updated_at: '2026-09-30T11:41:03.000000-04:00'
    ---

    # dinner

    Wednesday September 30 at 8:00 PM EDT (30 min).
""")

# A memo whose event_id slug collides with a previously pushed one —
# the old-style slug without time component (simulates pre-fix Herman output).
DINNER_OLD_SLUG_MD = textwrap.dedent("""\
    ---
    id: 2026-09-30-dinner
    title: dinner
    starts_at: '2026-09-30T19:00:00-04:00'
    ends_at: '2026-09-30T19:30:00-04:00'
    tz: America/New_York
    duration_minutes: 30
    people: []
    tags: []
    source: voice
    source_utterance: Schedule dinner at 7.
    created_at: '2026-09-30T15:38:12.000000-04:00'
    updated_at: '2026-09-30T15:38:12.000000-04:00'
    ---

    # dinner
""")


def _write(tmp_path: Path, name: str, content: str) -> Path:
    p = tmp_path / name
    p.write_text(content, encoding="utf-8")
    return p


# ---------------------------------------------------------------------------
# RED → GREEN  Bug A: vault slug must include HH:MM so distinct-time memos
# have distinct event_ids (tested via the brain's vault.event_id directly)
# ---------------------------------------------------------------------------

class TestVaultEventIdIncludesTime:
    """Bug A: vault.event_id() must include local HH-MM so two captures of
    'dinner' at different times on the same day get different IDs.

    These tests are RED before the fix to vault.event_id() and GREEN after.
    """

    def test_same_day_same_title_different_hour_produces_different_ids(self):
        """RED (pre-fix): event_id must differ when starts_at time differs.

        Current impl: event_id = "<date>-<title-slug>"
        → both produce "2026-09-30-dinner"  ← COLLISION

        Fixed impl: event_id = "<date>-<HHMM>-<title-slug>"
        → "2026-09-30-1900-dinner" vs "2026-09-30-2000-dinner"  ← DISTINCT
        """
        from zoneinfo import ZoneInfo
        from homunculus_brain import vault

        tz = ZoneInfo("America/New_York")
        dinner_7pm = datetime(2026, 9, 30, 19, 0, tzinfo=tz)
        dinner_8pm = datetime(2026, 9, 30, 20, 0, tzinfo=tz)

        id_7pm = vault.event_id(dinner_7pm, "dinner")
        id_8pm = vault.event_id(dinner_8pm, "dinner")

        assert id_7pm != id_8pm, (
            f"Two 'dinner' events at different times must produce different IDs. "
            f"Got same id='{id_7pm}' for both 7 PM and 8 PM."
        )

    def test_same_day_same_title_same_time_produces_same_id(self):
        """Fixed: identical time+title should still be idempotent (same id)."""
        from zoneinfo import ZoneInfo
        from homunculus_brain import vault

        tz = ZoneInfo("America/New_York")
        dt = datetime(2026, 9, 30, 19, 0, tzinfo=tz)

        id_1 = vault.event_id(dt, "dinner")
        id_2 = vault.event_id(dt, "dinner")
        assert id_1 == id_2, "Same time+title must always produce the same id (idempotent)."

    def test_event_id_contains_time_component(self):
        """Fixed: the event_id string must encode time (HH and MM)."""
        from zoneinfo import ZoneInfo
        from homunculus_brain import vault

        tz = ZoneInfo("America/New_York")
        dt = datetime(2026, 9, 30, 19, 0, tzinfo=tz)
        eid = vault.event_id(dt, "dinner")

        # After fix, id should contain "1900" or "19-00" or "19h00" etc.
        # We just require it's NOT the bare date-only form "2026-09-30-dinner".
        assert eid != "2026-09-30-dinner", (
            f"event_id must include time so same-day re-schedules get distinct IDs. "
            f"Got bare date-only id: '{eid}'"
        )

    def test_different_titles_same_time_produce_different_ids(self):
        """Regression: different titles must still differ."""
        from zoneinfo import ZoneInfo
        from homunculus_brain import vault

        tz = ZoneInfo("America/New_York")
        dt = datetime(2026, 9, 30, 19, 0, tzinfo=tz)

        id_dinner = vault.event_id(dt, "dinner")
        id_meeting = vault.event_id(dt, "meeting")
        assert id_dinner != id_meeting


# ---------------------------------------------------------------------------
# RED → GREEN  Bug B: same-slug distinct-content memos are BOTH pushed
# (bridge side — push_if_new must push both given distinct event_ids)
# ---------------------------------------------------------------------------

class TestDistinctEventIdsBothPushed:
    """Bug B (bridge): two memos with DISTINCT event_ids (after vault fix)
    must both be pushed, even if they share the same title word.

    These tests verify the bridge respects unique event_ids. They are
    already GREEN before the bridge fix — the bridge logic is correct once
    the vault generates distinct ids. But they serve as regression guards
    and are RED under the old slug scheme (where both files shared the same
    event_id and the second was silently skipped).
    """

    def test_two_dinners_at_different_times_both_pushed(self, tmp_path):
        """Given two .md files with distinct event_ids (one at 19:00, one at 20:00),
        BOTH must be pushed to Calendar.app.

        RED pre-vault-fix (both files had id='2026-09-30-dinner').
        GREEN post-vault-fix (ids are '2026-09-30-dinner-19-00' and '2026-09-30-dinner-20-00').
        """
        p7 = _write(tmp_path, "dinner-1900.md", DINNER_7PM_MD)
        p8 = _write(tmp_path, "dinner-2000.md", DINNER_8PM_MD)
        state = PushedState(tmp_path / "state.jsonl")

        pushed_ids: list[str] = []

        def fake_push(event, cal_name):
            pushed_ids.append(event.event_id)

        with patch("mac_calendar_bridge.watcher.push_event", side_effect=fake_push), \
             patch("mac_calendar_bridge.watcher.query_pushed_event_ids", return_value=[]):
            push_if_new(p7, state, "Homunculus")
            push_if_new(p8, state, "Homunculus")

        assert len(pushed_ids) == 2, (
            f"Both dinner events must be pushed. Only got: {pushed_ids}"
        )
        assert "2026-09-30-dinner-19-00" in pushed_ids
        assert "2026-09-30-dinner-20-00" in pushed_ids

    def test_second_dinner_not_skipped_when_first_already_pushed(self, tmp_path):
        """Even after the 7-PM dinner is in pushed.jsonl, the 8-PM dinner
        (a distinct event_id) must still be pushed.

        This is the exact scenario that failed on 2026-09-30.
        """
        p7 = _write(tmp_path, "dinner-1900.md", DINNER_7PM_MD)
        p8 = _write(tmp_path, "dinner-2000.md", DINNER_8PM_MD)
        state = PushedState(tmp_path / "state.jsonl")

        with patch("mac_calendar_bridge.watcher.push_event"), \
             patch("mac_calendar_bridge.watcher.query_pushed_event_ids", return_value=[]):
            push_if_new(p7, state, "Homunculus")

        # 7 PM dinner is now marked pushed
        assert state.is_pushed("2026-09-30-dinner-19-00")

        # 8 PM dinner has a DIFFERENT event_id — must not be skipped
        with patch("mac_calendar_bridge.watcher.push_event") as mock_push, \
             patch("mac_calendar_bridge.watcher.query_pushed_event_ids", return_value=[]):
            push_if_new(p8, state, "Homunculus")

        mock_push.assert_called_once(), (
            "8 PM dinner has a distinct event_id and must be pushed, "
            "not skipped because 7 PM dinner shares the same title."
        )


# ---------------------------------------------------------------------------
# RED → GREEN  Bug B visibility: push_if_new must log at INFO when it skips
# ---------------------------------------------------------------------------

class TestSkipVisibility:
    """Bug B (logging): the fast-path skip must log at INFO (not just DEBUG)
    so Thomas can diagnose a collision without restarting with --log-level=DEBUG.

    RED pre-fix: log.debug("Already pushed %s; skipping", record.event_id)
    Green post-fix: log.info("Already pushed %s (%s); skipping", eid, starts_at)
    """

    def test_already_pushed_skip_logged_at_info(self, tmp_path, caplog):
        """push_if_new must emit an INFO message when the fast-path dedup fires."""
        p = _write(tmp_path, "dinner.md", DINNER_7PM_MD)
        state = PushedState(tmp_path / "state.jsonl")
        state.mark_pushed("2026-09-30-dinner-19-00")

        with caplog.at_level(logging.INFO, logger="mac_calendar_bridge.watcher"), \
             patch("mac_calendar_bridge.watcher.push_event") as mock_push:
            push_if_new(p, state, "Homunculus")

        mock_push.assert_not_called()
        # Must produce at least one INFO record mentioning the skip
        skip_records = [
            r for r in caplog.records
            if r.levelno >= logging.INFO and (
                "skip" in r.message.lower() or "already pushed" in r.message.lower()
            )
        ]
        assert skip_records, (
            "push_if_new must log at INFO (not just DEBUG) when it skips a "
            "previously-pushed event. No INFO skip record found. "
            f"All records: {[(r.levelno, r.message) for r in caplog.records]}"
        )

    def test_skip_log_includes_event_id(self, tmp_path, caplog):
        """The INFO skip message must include the event_id for diagnostics."""
        p = _write(tmp_path, "dinner.md", DINNER_7PM_MD)
        state = PushedState(tmp_path / "state.jsonl")
        state.mark_pushed("2026-09-30-dinner-19-00")

        with caplog.at_level(logging.INFO, logger="mac_calendar_bridge.watcher"), \
             patch("mac_calendar_bridge.watcher.push_event"):
            push_if_new(p, state, "Homunculus")

        relevant = [
            r for r in caplog.records
            if r.levelno >= logging.INFO and "2026-09-30-dinner-19-00" in r.message
        ]
        assert relevant, (
            "The INFO skip message must include the event_id '2026-09-30-dinner-19-00'. "
            f"Records: {[r.message for r in caplog.records]}"
        )


# ---------------------------------------------------------------------------
# RED → GREEN  Bug C: Calendar permission denied must surface as ERROR log
# ---------------------------------------------------------------------------

class TestPermissionDeniedVisibility:
    """Bug C: if Calendar.app rejects the AppleScript call (permission denied,
    or any other AppleScriptError), push_if_new must log at ERROR level.

    This gives Thomas a visible, actionable signal in the bridge log rather
    than a silent gap in the calendar.
    """

    def test_applescript_error_logged_at_error_level(self, tmp_path, caplog):
        """When push_event raises AppleScriptError, push_if_new must log ERROR."""
        from mac_calendar_bridge.applescript import AppleScriptError

        p = _write(tmp_path, "dinner.md", DINNER_7PM_MD)
        state = PushedState(tmp_path / "state.jsonl")

        with caplog.at_level(logging.ERROR, logger="mac_calendar_bridge.watcher"), \
             patch(
                 "mac_calendar_bridge.watcher.push_event",
                 side_effect=AppleScriptError("not authorized to send Apple events"),
             ), \
             patch("mac_calendar_bridge.watcher.query_pushed_event_ids", return_value=[]):
            push_if_new(p, state, "Homunculus")

        error_records = [r for r in caplog.records if r.levelno >= logging.ERROR]
        assert error_records, (
            "push_if_new must log at ERROR when AppleScriptError is raised. "
            "No ERROR record found — permission denials are currently invisible."
        )

    def test_applescript_error_message_contains_event_id(self, tmp_path, caplog):
        """The ERROR log for a push failure must name the event_id."""
        from mac_calendar_bridge.applescript import AppleScriptError

        p = _write(tmp_path, "dinner.md", DINNER_7PM_MD)
        state = PushedState(tmp_path / "state.jsonl")

        with caplog.at_level(logging.ERROR, logger="mac_calendar_bridge.watcher"), \
             patch(
                 "mac_calendar_bridge.watcher.push_event",
                 side_effect=AppleScriptError("not authorized"),
             ), \
             patch("mac_calendar_bridge.watcher.query_pushed_event_ids", return_value=[]):
            push_if_new(p, state, "Homunculus")

        error_records = [r for r in caplog.records if r.levelno >= logging.ERROR]
        assert any("2026-09-30-dinner-19-00" in r.message for r in error_records), (
            "The ERROR log must include the event_id so the failing event is identifiable. "
            f"ERROR records: {[r.message for r in error_records]}"
        )

    def test_permission_error_does_not_mark_pushed(self, tmp_path):
        """Event must NOT be marked pushed after a permission error (existing behaviour guard)."""
        from mac_calendar_bridge.applescript import AppleScriptError

        p = _write(tmp_path, "dinner.md", DINNER_7PM_MD)
        state = PushedState(tmp_path / "state.jsonl")

        with patch(
            "mac_calendar_bridge.watcher.push_event",
            side_effect=AppleScriptError("not authorized"),
        ), patch("mac_calendar_bridge.watcher.query_pushed_event_ids", return_value=[]):
            push_if_new(p, state, "Homunculus")

        assert not state.is_pushed("2026-09-30-dinner-19-00"), (
            "A failed push must not mark the event as pushed — it must be retried."
        )
