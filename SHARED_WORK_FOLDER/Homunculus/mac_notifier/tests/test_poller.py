"""
test_poller.py — Tests for mac_notifier.poller

House rule: NEVER invoke real osascript or hit real Herman in tests.
All external calls are mocked.

Covers all mandatory test cases from the assignment:
1. Row due + not in state → fire + mark
2. Row due + already in state → skip (DEBUG)
3. Row too far in future → skip
4. Row too far in past (missed) → skip (INFO)
5. Malformed row (missing fire_at) → already handled in HermanClient; here
   we test that poller handles a clean list (HermanClient already filters)
6. Herman unreachable → log error, keep polling
7. State file missing → treat as empty, don't crash
8. Grace window boundary: exactly at now, at now-89s, at now+89s → fire
   At now-91s, at now+91s → skip

Also covers:
- is_due() and classify_row() boundary logic
- run_poll_cycle() counts
- osascript failure → not marked, will retry
- NotImplementedError (non-Darwin) → marked fired (no retry storm)
- Multiple rows, mixed due/future/past/already-fired
"""

from __future__ import annotations

import subprocess
from datetime import datetime, timedelta, timezone
from pathlib import Path
from unittest import mock

import pytest

from mac_notifier.herman_client import HermanClient, ReminderRow
from mac_notifier.poller import classify_row, is_due, run_poll_cycle
from mac_notifier.state import FiredState


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture()
def state_file(tmp_path: Path) -> Path:
    return tmp_path / "fired.jsonl"


@pytest.fixture()
def state(state_file: Path) -> FiredState:
    return FiredState(state_file)


# "now" used across all timing tests
NOW = datetime(2026, 9, 16, 11, 0, 0, tzinfo=timezone.utc)
GRACE = 90  # seconds


def _make_row(
    event_id: str = "ev.test",
    kind: str = "morning_summary",
    offset_seconds: int = 0,
    body: str = "Test body",
) -> ReminderRow:
    """Create a ReminderRow with fire_at = NOW + offset_seconds."""
    return ReminderRow(
        event_id=event_id,
        kind=kind,
        fire_at=NOW + timedelta(seconds=offset_seconds),
        body=body,
        tz="America/New_York",
    )


def _make_client_returning(rows: list[ReminderRow]) -> HermanClient:
    client = mock.MagicMock(spec=HermanClient)
    client.fetch_upcoming.return_value = rows
    return client


# ---------------------------------------------------------------------------
# Tests: is_due() boundary logic
# ---------------------------------------------------------------------------


class TestIsDue:
    def test_exactly_at_now(self):
        row = _make_row(offset_seconds=0)
        assert is_due(row, NOW, GRACE) is True

    def test_within_grace_before_now(self):
        row = _make_row(offset_seconds=-89)
        assert is_due(row, NOW, GRACE) is True

    def test_exactly_at_grace_before_now(self):
        row = _make_row(offset_seconds=-90)
        assert is_due(row, NOW, GRACE) is True

    def test_just_past_grace_before_now(self):
        row = _make_row(offset_seconds=-91)
        assert is_due(row, NOW, GRACE) is False

    def test_within_grace_after_now(self):
        row = _make_row(offset_seconds=89)
        assert is_due(row, NOW, GRACE) is True

    def test_exactly_at_grace_after_now(self):
        row = _make_row(offset_seconds=90)
        assert is_due(row, NOW, GRACE) is True

    def test_just_past_grace_after_now(self):
        row = _make_row(offset_seconds=91)
        assert is_due(row, NOW, GRACE) is False

    def test_far_future(self):
        row = _make_row(offset_seconds=3600)
        assert is_due(row, NOW, GRACE) is False

    def test_far_past(self):
        row = _make_row(offset_seconds=-3600)
        assert is_due(row, NOW, GRACE) is False


# ---------------------------------------------------------------------------
# Tests: classify_row()
# ---------------------------------------------------------------------------


class TestClassifyRow:
    def test_exactly_at_now_is_due(self):
        row = _make_row(offset_seconds=0)
        assert classify_row(row, NOW, GRACE) == "due"

    def test_89s_before_is_due(self):
        row = _make_row(offset_seconds=-89)
        assert classify_row(row, NOW, GRACE) == "due"

    def test_91s_before_is_missed(self):
        row = _make_row(offset_seconds=-91)
        assert classify_row(row, NOW, GRACE) == "missed"

    def test_89s_after_is_due(self):
        row = _make_row(offset_seconds=89)
        assert classify_row(row, NOW, GRACE) == "due"

    def test_91s_after_is_future(self):
        row = _make_row(offset_seconds=91)
        assert classify_row(row, NOW, GRACE) == "future"

    def test_far_past_is_missed(self):
        row = _make_row(offset_seconds=-7200)
        assert classify_row(row, NOW, GRACE) == "missed"

    def test_far_future_is_future(self):
        row = _make_row(offset_seconds=7200)
        assert classify_row(row, NOW, GRACE) == "future"


# ---------------------------------------------------------------------------
# Tests: run_poll_cycle — core scenarios (mandatory from assignment)
# ---------------------------------------------------------------------------


class TestPollCycleCoreScenarios:
    @mock.patch("mac_notifier.poller.fire_notification")
    @mock.patch("mac_notifier.applescript.sys.platform", "darwin")
    def test_due_not_fired_fires_and_marks(self, mock_fire, state: FiredState):
        """Case 1: Row due + not in state → fire + mark."""
        row = _make_row(event_id="ev.abc", kind="morning_summary", offset_seconds=0)
        client = _make_client_returning([row])

        counts = run_poll_cycle(client, state, GRACE, now=NOW)

        mock_fire.assert_called_once()
        assert counts["fired"] == 1
        assert state.is_fired("ev.abc:morning_summary")

    @mock.patch("mac_notifier.poller.fire_notification")
    def test_due_already_fired_skips(self, mock_fire, state: FiredState):
        """Case 2: Row due + already in state → skip."""
        row = _make_row(event_id="ev.abc", kind="morning_summary", offset_seconds=0)
        state.mark_fired(row.identifier)  # pre-fire
        client = _make_client_returning([row])

        counts = run_poll_cycle(client, state, GRACE, now=NOW)

        mock_fire.assert_not_called()
        assert counts["skipped_fired"] == 1
        assert counts["fired"] == 0

    @mock.patch("mac_notifier.poller.fire_notification")
    def test_future_row_skipped(self, mock_fire, state: FiredState):
        """Case 3: Row too far in future → skip."""
        row = _make_row(offset_seconds=3600)  # 1 hour from now
        client = _make_client_returning([row])

        counts = run_poll_cycle(client, state, GRACE, now=NOW)

        mock_fire.assert_not_called()
        assert counts["skipped_future"] == 1

    @mock.patch("mac_notifier.poller.fire_notification")
    def test_past_row_skipped_missed(self, mock_fire, state: FiredState):
        """Case 4: Row too far in past → skip (missed)."""
        row = _make_row(offset_seconds=-3600)  # 1 hour ago
        client = _make_client_returning([row])

        counts = run_poll_cycle(client, state, GRACE, now=NOW)

        mock_fire.assert_not_called()
        assert counts["skipped_missed"] == 1

    @mock.patch("mac_notifier.poller.fire_notification")
    def test_herman_unreachable_no_crash(self, mock_fire, state: FiredState):
        """Case 6: Herman unreachable → empty list returned by client, no crash."""
        client = _make_client_returning([])  # HermanClient already returns [] on error
        counts = run_poll_cycle(client, state, GRACE, now=NOW)

        mock_fire.assert_not_called()
        assert counts["fetched"] == 0

    def test_state_file_missing_no_crash(self, tmp_path: Path):
        """Case 7: State file missing → empty state, no crash."""
        missing_state = FiredState(tmp_path / "nonexistent" / "fired.jsonl")
        row = _make_row(offset_seconds=0)
        client = _make_client_returning([row])

        with mock.patch("mac_notifier.poller.fire_notification") as mock_fire:
            mock_fire.return_value = None
            with mock.patch("mac_notifier.applescript.sys.platform", "darwin"):
                # Should not crash even though parent dir doesn't exist yet
                counts = run_poll_cycle(client, missing_state, GRACE, now=NOW)
        # If it didn't crash, the test passes. Fired count may be 1 (notification + mark).
        assert counts is not None


# ---------------------------------------------------------------------------
# Tests: grace window boundary (assignment requirement)
# ---------------------------------------------------------------------------


class TestGraceWindowBoundary:
    @mock.patch("mac_notifier.poller.fire_notification")
    def test_exactly_at_now_fires(self, mock_fire, state: FiredState):
        row = _make_row(offset_seconds=0)
        client = _make_client_returning([row])
        counts = run_poll_cycle(client, state, GRACE, now=NOW)
        mock_fire.assert_called_once()
        assert counts["fired"] == 1

    @mock.patch("mac_notifier.poller.fire_notification")
    def test_89s_before_fires(self, mock_fire, state: FiredState):
        row = _make_row(offset_seconds=-89)
        client = _make_client_returning([row])
        counts = run_poll_cycle(client, state, GRACE, now=NOW)
        mock_fire.assert_called_once()
        assert counts["fired"] == 1

    @mock.patch("mac_notifier.poller.fire_notification")
    def test_89s_after_fires(self, mock_fire, state: FiredState):
        row = _make_row(offset_seconds=89)
        client = _make_client_returning([row])
        counts = run_poll_cycle(client, state, GRACE, now=NOW)
        mock_fire.assert_called_once()
        assert counts["fired"] == 1

    @mock.patch("mac_notifier.poller.fire_notification")
    def test_91s_before_skips_missed(self, mock_fire, state: FiredState):
        row = _make_row(offset_seconds=-91)
        client = _make_client_returning([row])
        counts = run_poll_cycle(client, state, GRACE, now=NOW)
        mock_fire.assert_not_called()
        assert counts["skipped_missed"] == 1

    @mock.patch("mac_notifier.poller.fire_notification")
    def test_91s_after_skips_future(self, mock_fire, state: FiredState):
        row = _make_row(offset_seconds=91)
        client = _make_client_returning([row])
        counts = run_poll_cycle(client, state, GRACE, now=NOW)
        mock_fire.assert_not_called()
        assert counts["skipped_future"] == 1


# ---------------------------------------------------------------------------
# Tests: run_poll_cycle — error handling
# ---------------------------------------------------------------------------


class TestPollCycleErrorHandling:
    @mock.patch("mac_notifier.poller.fire_notification")
    @mock.patch("mac_notifier.applescript.sys.platform", "darwin")
    def test_applescript_error_not_marked_fired(self, mock_fire, state: FiredState):
        """osascript failure → row NOT marked fired → will retry next cycle."""
        from mac_notifier.applescript import AppleScriptError
        mock_fire.side_effect = AppleScriptError("osascript failed")
        row = _make_row(offset_seconds=0)
        client = _make_client_returning([row])

        counts = run_poll_cycle(client, state, GRACE, now=NOW)

        # Not marked — will retry
        assert not state.is_fired(row.identifier)
        assert counts["errors"] == 1
        assert counts["fired"] == 0

    @mock.patch("mac_notifier.poller.fire_notification")
    @mock.patch("mac_notifier.applescript.sys.platform", "linux")
    def test_not_implemented_on_linux_marks_fired(self, mock_fire, state: FiredState):
        """NotImplementedError (non-Darwin) → marked fired to prevent retry storm."""
        mock_fire.side_effect = NotImplementedError("not macOS")
        row = _make_row(offset_seconds=0)
        client = _make_client_returning([row])

        counts = run_poll_cycle(client, state, GRACE, now=NOW)

        # Marked fired — no retry storm on Linux
        assert state.is_fired(row.identifier)
        assert counts["fired"] == 1

    @mock.patch("mac_notifier.poller.fire_notification")
    def test_multiple_rows_mixed(self, mock_fire, state: FiredState):
        """Multiple rows: due/future/past/already-fired all handled correctly."""
        rows = [
            _make_row(event_id="ev.due", kind="morning_summary", offset_seconds=0),
            _make_row(event_id="ev.future", kind="heads_up_30", offset_seconds=3600),
            _make_row(event_id="ev.past", kind="strike_0", offset_seconds=-3600),
            _make_row(event_id="ev.already", kind="strike_5", offset_seconds=0),
        ]
        state.mark_fired("ev.already:strike_5")
        client = _make_client_returning(rows)

        counts = run_poll_cycle(client, state, GRACE, now=NOW)

        assert counts["fired"] == 1
        assert counts["skipped_future"] == 1
        assert counts["skipped_missed"] == 1
        assert counts["skipped_fired"] == 1

    @mock.patch("mac_notifier.poller.fire_notification")
    def test_fire_called_with_correct_args(self, mock_fire, state: FiredState):
        """Notification is fired with body=row.body and subtitle=row.subtitle."""
        row = _make_row(
            event_id="summary.2026-09-16",
            kind="morning_summary",
            offset_seconds=0,
            body="Good morning. Today: test.",
        )
        client = _make_client_returning([row])

        run_poll_cycle(client, state, GRACE, now=NOW)

        mock_fire.assert_called_once_with(
            body="Good morning. Today: test.",
            subtitle="Morning summary",
        )

    @mock.patch("mac_notifier.poller.fire_notification")
    def test_counts_are_complete(self, mock_fire, state: FiredState):
        """run_poll_cycle always returns all expected count keys."""
        client = _make_client_returning([])
        counts = run_poll_cycle(client, state, GRACE, now=NOW)

        expected_keys = {
            "fetched", "fired", "skipped_fired",
            "skipped_future", "skipped_missed", "skipped_malformed", "errors"
        }
        assert set(counts.keys()) == expected_keys

    @mock.patch("mac_notifier.poller.fire_notification")
    def test_empty_rows_all_zero_counts(self, mock_fire, state: FiredState):
        client = _make_client_returning([])
        counts = run_poll_cycle(client, state, GRACE, now=NOW)

        assert counts["fetched"] == 0
        assert counts["fired"] == 0
        assert counts["errors"] == 0

    @mock.patch("mac_notifier.poller.fire_notification")
    def test_dedup_same_identifier_in_rows(self, mock_fire, state: FiredState):
        """Same identifier appearing twice → fired once, second skipped."""
        row_a = _make_row(event_id="ev.dup", kind="morning_summary", offset_seconds=0)
        row_b = _make_row(event_id="ev.dup", kind="morning_summary", offset_seconds=5)
        client = _make_client_returning([row_a, row_b])

        counts = run_poll_cycle(client, state, GRACE, now=NOW)

        assert counts["fired"] == 1
        assert counts["skipped_fired"] == 1

    @mock.patch("mac_notifier.poller.fire_notification")
    def test_different_kinds_same_event_id_both_fire(self, mock_fire, state: FiredState):
        """Same event_id, different kinds → both fire (different identifiers)."""
        row_a = _make_row(event_id="ev.abc", kind="pre_5", offset_seconds=0)
        row_b = _make_row(event_id="ev.abc", kind="strike_0", offset_seconds=0)
        client = _make_client_returning([row_a, row_b])

        counts = run_poll_cycle(client, state, GRACE, now=NOW)

        assert counts["fired"] == 2
        assert state.is_fired("ev.abc:pre_5")
        assert state.is_fired("ev.abc:strike_0")
