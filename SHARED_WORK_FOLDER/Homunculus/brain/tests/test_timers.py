"""TDD tests for Herman v2.0.0 timers module.

Written RED first. These must fail against v1.9.0 code and pass after v2.0.0.

Tests cover:
  7.  TimerManager.start creates vault/timers/<slug>.json
  8.  Idempotent start: calling start() twice preserves original started_at
  9.  TimerManager.stop: duration, total, session appended, running cleared
  10. Stop no-running timer raises NoRunningTimer
  11. Slug normalization: "Gym", "the Gym", "gym" → same file
  12. get_running() empty/non-empty with elapsed_seconds
  13. get_totals() sorted by last_touched_at desc
  14. Atomic write: os.replace called (write-rename discipline)
  15. Activity log records timer_start and timer_stop kinds
  16-20 covered in test_timers_routes.py
  25-27. format_duration helper
"""

from __future__ import annotations

import json
import os
from datetime import datetime, timezone
from pathlib import Path
from unittest.mock import patch

import pytest
from zoneinfo import ZoneInfo


TZ = ZoneInfo("America/New_York")

# We defer imports until tests run to allow RED state to be confirmed cleanly.


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _now(offset_seconds: int = 0) -> datetime:
    """Return a TZ-aware datetime offset from a fixed base."""
    from datetime import timedelta
    base = datetime(2026, 9, 22, 10, 30, 0, tzinfo=TZ)
    return base + timedelta(seconds=offset_seconds)


def _make_manager(tmp_path: Path):
    """Return a TimerManager with vault/timers/ inside tmp_path."""
    from homunculus_brain.timers import TimerManager
    return TimerManager(vault_path=tmp_path)


# ---------------------------------------------------------------------------
# Test 7: start() creates file with correct initial state
# ---------------------------------------------------------------------------


def test_start_creates_timer_file(tmp_path: Path):
    """start(project='gym') creates vault/timers/gym.json with running set."""
    manager = _make_manager(tmp_path)
    result = manager.start(project="gym", captured_at=_now(), tz=TZ)

    assert result.stored is True
    timer_path = tmp_path / "timers" / "gym.json"
    assert timer_path.exists(), f"Expected timer file at {timer_path}"

    data = json.loads(timer_path.read_text())
    assert data["project"] == "gym"
    assert data["slug"] == "gym"
    assert data["running"] is not None
    assert data["sessions"] == []
    assert data["total_seconds"] == 0


def test_start_populates_started_at(tmp_path: Path):
    """started_at in the file matches the captured_at argument."""
    started = _now()
    manager = _make_manager(tmp_path)
    manager.start(project="gym", captured_at=started, tz=TZ)

    data = json.loads((tmp_path / "timers" / "gym.json").read_text())
    # Parse the stored ISO string and compare
    stored_dt = datetime.fromisoformat(data["running"]["started_at"])
    assert abs((stored_dt.utctimetuple()[5] - started.second)) < 2  # same second


# ---------------------------------------------------------------------------
# Test 8: Idempotent start — second call preserves original started_at
# ---------------------------------------------------------------------------


def test_start_idempotent_double_call(tmp_path: Path):
    """Calling start() twice on same project returns original started_at."""
    first_time = _now(0)
    second_time = _now(60)

    manager = _make_manager(tmp_path)
    result1 = manager.start(project="gym", captured_at=first_time, tz=TZ)
    result2 = manager.start(project="gym", captured_at=second_time, tz=TZ)

    # Both return stored=True (idempotent success)
    assert result1.stored is True
    assert result2.stored is True

    # The file still contains the FIRST started_at
    data = json.loads((tmp_path / "timers" / "gym.json").read_text())
    stored_dt = datetime.fromisoformat(data["running"]["started_at"])
    # Should be closer to first_time than second_time
    diff_from_first = abs((stored_dt - first_time.astimezone(timezone.utc)).total_seconds())
    diff_from_second = abs((stored_dt - second_time.astimezone(timezone.utc)).total_seconds())
    assert diff_from_first < diff_from_second, (
        "Idempotent start must preserve the ORIGINAL started_at"
    )


# ---------------------------------------------------------------------------
# Test 9: stop() — duration, total, session, running cleared
# ---------------------------------------------------------------------------


def test_stop_after_start_returns_correct_duration(tmp_path: Path):
    """stop() returns duration_seconds matching (ended_at - started_at)."""
    from datetime import timedelta
    start_time = _now(0)
    stop_time = _now(2712)  # 45 minutes 12 seconds later

    manager = _make_manager(tmp_path)
    manager.start(project="gym", captured_at=start_time, tz=TZ)
    result = manager.stop(project="gym", captured_at=stop_time, tz=TZ)

    assert result.stored is True
    # Allow 1-second tolerance for datetime rounding
    assert abs(result.duration_seconds - 2712) <= 1, (
        f"Expected duration ~2712s, got {result.duration_seconds}"
    )
    assert result.total_seconds == result.duration_seconds


def test_stop_clears_running_and_appends_session(tmp_path: Path):
    """After stop(), running=null and sessions has one entry."""
    start_time = _now(0)
    stop_time = _now(1800)

    manager = _make_manager(tmp_path)
    manager.start(project="gym", captured_at=start_time, tz=TZ)
    manager.stop(project="gym", captured_at=stop_time, tz=TZ)

    data = json.loads((tmp_path / "timers" / "gym.json").read_text())
    assert data["running"] is None, "running must be null after stop"
    assert len(data["sessions"]) == 1
    session = data["sessions"][0]
    assert "started_at" in session
    assert "ended_at" in session
    assert "duration_seconds" in session


def test_stop_accumulates_total_across_sessions(tmp_path: Path):
    """Two start/stop cycles accumulate total_seconds correctly."""
    manager = _make_manager(tmp_path)

    manager.start(project="gym", captured_at=_now(0), tz=TZ)
    manager.stop(project="gym", captured_at=_now(1800), tz=TZ)  # 30 min

    manager.start(project="gym", captured_at=_now(7200), tz=TZ)  # 2h later
    result = manager.stop(project="gym", captured_at=_now(9000), tz=TZ)  # 30 min again

    data = json.loads((tmp_path / "timers" / "gym.json").read_text())
    # total should be ~3600 (two 30-min sessions)
    assert abs(data["total_seconds"] - 3600) <= 2
    assert len(data["sessions"]) == 2
    assert abs(result.total_seconds - 3600) <= 2


# ---------------------------------------------------------------------------
# Test 10: stop() with no running timer → raises NoRunningTimer
# ---------------------------------------------------------------------------


def test_stop_no_running_timer_raises(tmp_path: Path):
    """stop() on a project with no running timer raises NoRunningTimer."""
    from homunculus_brain.timers import NoRunningTimer
    manager = _make_manager(tmp_path)

    with pytest.raises(NoRunningTimer):
        manager.stop(project="gym", captured_at=_now(), tz=TZ)


def test_stop_after_stop_raises(tmp_path: Path):
    """Stopping an already-stopped timer raises NoRunningTimer."""
    from homunculus_brain.timers import NoRunningTimer
    manager = _make_manager(tmp_path)

    manager.start(project="gym", captured_at=_now(0), tz=TZ)
    manager.stop(project="gym", captured_at=_now(1800), tz=TZ)

    with pytest.raises(NoRunningTimer):
        manager.stop(project="gym", captured_at=_now(3600), tz=TZ)


# ---------------------------------------------------------------------------
# Test 11: Slug normalization
# ---------------------------------------------------------------------------


def test_slug_normalization_lowercase(tmp_path: Path):
    """start(project='Gym') → file is vault/timers/gym.json."""
    manager = _make_manager(tmp_path)
    manager.start(project="Gym", captured_at=_now(), tz=TZ)
    assert (tmp_path / "timers" / "gym.json").exists()


def test_slug_normalization_strips_leading_article_the(tmp_path: Path):
    """'the Gym' and 'gym' resolve to the same slug 'gym'."""
    manager = _make_manager(tmp_path)
    manager.start(project="the Gym", captured_at=_now(0), tz=TZ)

    # The file should be gym.json (article 'the' stripped)
    assert (tmp_path / "timers" / "gym.json").exists()

    # Starting with bare 'gym' should be idempotent (same file)
    result = manager.start(project="gym", captured_at=_now(60), tz=TZ)
    assert result.stored is True

    # Only one file
    timer_files = list((tmp_path / "timers").glob("*.json"))
    assert len(timer_files) == 1, (
        f"Expected 1 timer file, got {len(timer_files)}: {timer_files}"
    )


def test_slug_normalization_strips_article_a(tmp_path: Path):
    """'a meeting' strips the article 'a' → 'meeting'."""
    from homunculus_brain.timers import _normalize_project
    assert _normalize_project("a meeting") == "meeting"


def test_slug_normalization_strips_article_an(tmp_path: Path):
    """'an apple' strips the article 'an' → 'apple'."""
    from homunculus_brain.timers import _normalize_project
    assert _normalize_project("an apple") == "apple"


def test_slug_normalization_preserves_non_article_prefix(tmp_path: Path):
    """'deck construction' must NOT strip 'deck' (not an article)."""
    from homunculus_brain.timers import _normalize_project
    result = _normalize_project("deck construction")
    assert "deck" in result


# ---------------------------------------------------------------------------
# Test 12: get_running() — empty and non-empty
# ---------------------------------------------------------------------------


def test_get_running_empty_when_no_timers(tmp_path: Path):
    """get_running() returns empty list when no timers exist."""
    manager = _make_manager(tmp_path)
    assert manager.get_running() == []


def test_get_running_returns_active_timers(tmp_path: Path):
    """get_running() returns running timers with elapsed_seconds computed."""
    from datetime import timedelta
    manager = _make_manager(tmp_path)
    manager.start(project="gym", captured_at=_now(0), tz=TZ)

    running = manager.get_running()
    assert len(running) == 1
    r = running[0]
    assert r.project == "gym"
    assert r.slug == "gym"
    assert r.elapsed_seconds >= 0  # computed at query time


def test_get_running_omits_stopped_timers(tmp_path: Path):
    """Stopped timers don't appear in get_running()."""
    manager = _make_manager(tmp_path)
    manager.start(project="gym", captured_at=_now(0), tz=TZ)
    manager.stop(project="gym", captured_at=_now(1800), tz=TZ)

    assert manager.get_running() == []


# ---------------------------------------------------------------------------
# Test 13: get_totals() sorted by last_touched_at desc
# ---------------------------------------------------------------------------


def test_get_totals_sorted_by_last_touched_desc(tmp_path: Path):
    """get_totals() returns projects sorted by last_touched_at descending."""
    manager = _make_manager(tmp_path)

    # Start+stop gym first
    manager.start(project="gym", captured_at=_now(0), tz=TZ)
    manager.stop(project="gym", captured_at=_now(1800), tz=TZ)

    # Start+stop deck later
    manager.start(project="deck", captured_at=_now(3600), tz=TZ)
    manager.stop(project="deck", captured_at=_now(5400), tz=TZ)

    totals = manager.get_totals()
    assert len(totals) == 2
    # deck was touched last → should be first
    assert totals[0].slug == "deck"
    assert totals[1].slug == "gym"


def test_get_totals_includes_running_timer(tmp_path: Path):
    """get_totals() includes projects with running timers (is_running=True)."""
    manager = _make_manager(tmp_path)
    manager.start(project="gym", captured_at=_now(0), tz=TZ)

    totals = manager.get_totals()
    assert len(totals) == 1
    assert totals[0].is_running is True


# ---------------------------------------------------------------------------
# Test 14: Atomic write — os.replace called
# ---------------------------------------------------------------------------


def test_timer_write_uses_os_replace(tmp_path: Path):
    """Timer writes use atomic write-rename (os.replace called at least once)."""
    manager = _make_manager(tmp_path)

    with patch("homunculus_brain.timers.os.replace", wraps=os.replace) as mock_replace:
        manager.start(project="gym", captured_at=_now(), tz=TZ)
        assert mock_replace.called, (
            "TimerManager must use os.replace for atomic writes"
        )


# ---------------------------------------------------------------------------
# Test 25-27: format_duration helper
# ---------------------------------------------------------------------------


def test_format_duration_seconds_only():
    """format_duration(0) → '0 seconds'."""
    from homunculus_brain.timers import format_duration
    assert format_duration(0) == "0 seconds"


def test_format_duration_minutes_and_seconds():
    """format_duration(2712) → '45 minutes 12 seconds'."""
    from homunculus_brain.timers import format_duration
    result = format_duration(2712)
    assert "45" in result
    assert "12" in result
    assert "minutes" in result
    assert "seconds" in result


def test_format_duration_hours_drops_seconds():
    """format_duration(15012) = 4h 10m 12s → '4 hours 10 minutes' (no seconds)."""
    from homunculus_brain.timers import format_duration
    result = format_duration(15012)
    assert "4" in result
    assert "hours" in result
    assert "10" in result
    assert "minutes" in result
    # Seconds must be omitted when hours >= 1
    assert "seconds" not in result.lower()


def test_format_duration_exactly_one_hour():
    """format_duration(3600) → '1 hour 0 minutes'."""
    from homunculus_brain.timers import format_duration
    result = format_duration(3600)
    assert "1" in result
    assert "hour" in result


def test_format_duration_sub_minute():
    """format_duration(45) → '45 seconds'."""
    from homunculus_brain.timers import format_duration
    result = format_duration(45)
    assert "45" in result
    assert "seconds" in result


def test_format_duration_exactly_one_minute():
    """format_duration(60) → '1 minute 0 seconds'."""
    from homunculus_brain.timers import format_duration
    result = format_duration(60)
    assert "1" in result
    assert "minute" in result


# ---------------------------------------------------------------------------
# Activity log integration
# ---------------------------------------------------------------------------


def test_start_logs_timer_start_to_activity(tmp_path: Path):
    """start() appends a timer_start row to _activity.jsonl."""
    manager = _make_manager(tmp_path)
    manager.start(project="gym", captured_at=_now(), tz=TZ)

    activity_path = tmp_path / "_activity.jsonl"
    assert activity_path.exists(), "No _activity.jsonl written"
    entries = [json.loads(ln) for ln in activity_path.read_text().splitlines() if ln.strip()]
    timer_starts = [e for e in entries if e.get("kind") == "timer_start"]
    assert timer_starts, "No timer_start entry in activity log"
    assert timer_starts[0].get("project") == "gym" or \
           timer_starts[0].get("details", {}).get("project") == "gym"


def test_stop_logs_timer_stop_to_activity(tmp_path: Path):
    """stop() appends a timer_stop row to _activity.jsonl."""
    manager = _make_manager(tmp_path)
    manager.start(project="gym", captured_at=_now(0), tz=TZ)
    manager.stop(project="gym", captured_at=_now(1800), tz=TZ)

    activity_path = tmp_path / "_activity.jsonl"
    entries = [json.loads(ln) for ln in activity_path.read_text().splitlines() if ln.strip()]
    timer_stops = [e for e in entries if e.get("kind") == "timer_stop"]
    assert timer_stops, "No timer_stop entry in activity log"
    stop_entry = timer_stops[0]
    details = stop_entry.get("details", stop_entry)
    assert details.get("project") == "gym" or stop_entry.get("project") == "gym"


# ===========================================================================
# v2.1.0 TDD — stop_all_timers + reset_timer
# ===========================================================================


# ---------------------------------------------------------------------------
# Test 6: stop_all() with 0 running timers — no-op, empty list
# ---------------------------------------------------------------------------


def test_stop_all_empty_returns_empty_list(tmp_path: Path):
    """stop_all() with 0 running timers returns [] with no state change."""
    manager = _make_manager(tmp_path)
    result = manager.stop_all(captured_at=_now(), tz=TZ)
    assert result == [], f"Expected [], got {result!r}"


def test_stop_all_empty_no_files_created(tmp_path: Path):
    """stop_all() with 0 timers does not create any files."""
    manager = _make_manager(tmp_path)
    manager.stop_all(captured_at=_now(), tz=TZ)
    timers_dir = tmp_path / "timers"
    if timers_dir.exists():
        assert list(timers_dir.glob("*.json")) == []


# ---------------------------------------------------------------------------
# Test 7: stop_all() with 2 running timers stops both
# ---------------------------------------------------------------------------


def test_stop_all_stops_all_running_timers(tmp_path: Path):
    """stop_all() with 2 running timers returns 2 TimerStopResult entries."""
    manager = _make_manager(tmp_path)
    manager.start(project="gym", captured_at=_now(0), tz=TZ)
    manager.start(project="deck", captured_at=_now(60), tz=TZ)

    results = manager.stop_all(captured_at=_now(1800), tz=TZ)
    assert len(results) == 2
    slugs = {r.slug for r in results}
    assert slugs == {"gym", "deck"}


def test_stop_all_files_show_running_none(tmp_path: Path):
    """After stop_all(), both timer files have running=null."""
    manager = _make_manager(tmp_path)
    manager.start(project="gym", captured_at=_now(0), tz=TZ)
    manager.start(project="deck", captured_at=_now(60), tz=TZ)
    manager.stop_all(captured_at=_now(1800), tz=TZ)

    for slug in ("gym", "deck"):
        data = json.loads((tmp_path / "timers" / f"{slug}.json").read_text())
        assert data["running"] is None, f"{slug}.json still shows running"
        assert data["total_seconds"] > 0, f"{slug}.json total_seconds should be > 0"


def test_stop_all_each_result_is_timer_stop_result(tmp_path: Path):
    """Each entry in stop_all result is a TimerStopResult dataclass."""
    from homunculus_brain.timers import TimerStopResult
    manager = _make_manager(tmp_path)
    manager.start(project="gym", captured_at=_now(0), tz=TZ)
    results = manager.stop_all(captured_at=_now(1800), tz=TZ)
    assert len(results) == 1
    assert isinstance(results[0], TimerStopResult)


# ---------------------------------------------------------------------------
# Test 8: reset() on a non-running project
# ---------------------------------------------------------------------------


def test_reset_nonrunning_clears_sessions_and_total(tmp_path: Path):
    """reset() on a stopped project zeroes total_seconds and clears sessions."""
    manager = _make_manager(tmp_path)
    manager.start(project="gym", captured_at=_now(0), tz=TZ)
    manager.stop(project="gym", captured_at=_now(1800), tz=TZ)

    from homunculus_brain.timers import TimerResetResult
    result = manager.reset(project="gym", captured_at=_now(3600), tz=TZ)

    assert result.stored is True
    assert result.cleared_seconds == 1800  # ~30 min, allow tolerance in check below
    data = json.loads((tmp_path / "timers" / "gym.json").read_text())
    assert data["total_seconds"] == 0
    assert data["sessions"] == []


def test_reset_nonrunning_clears_seconds_matches_old_total(tmp_path: Path):
    """reset() cleared_seconds matches the pre-reset total."""
    manager = _make_manager(tmp_path)
    manager.start(project="gym", captured_at=_now(0), tz=TZ)
    manager.stop(project="gym", captured_at=_now(1800), tz=TZ)

    pre_data = json.loads((tmp_path / "timers" / "gym.json").read_text())
    old_total = pre_data["total_seconds"]

    from homunculus_brain.timers import TimerResetResult
    result = manager.reset(project="gym", captured_at=_now(3600), tz=TZ)

    assert result.cleared_seconds == old_total


# ---------------------------------------------------------------------------
# Test 9: reset() on a running project — silent stop first, then reset
# ---------------------------------------------------------------------------


def test_reset_running_stops_first_then_resets(tmp_path: Path):
    """reset() on a running timer stops it silently then zeros state."""
    manager = _make_manager(tmp_path)
    manager.start(project="gym", captured_at=_now(0), tz=TZ)

    from homunculus_brain.timers import TimerResetResult
    result = manager.reset(project="gym", captured_at=_now(1800), tz=TZ)

    assert result.stored is True
    data = json.loads((tmp_path / "timers" / "gym.json").read_text())
    assert data["running"] is None, "Timer should be stopped after reset"
    assert data["total_seconds"] == 0
    assert data["sessions"] == []


# ---------------------------------------------------------------------------
# Test 10: reset() on nonexistent project returns stored=False
# ---------------------------------------------------------------------------


def test_reset_nonexistent_project_returns_stored_false(tmp_path: Path):
    """reset() on unknown project returns stored=False with clarifying message."""
    manager = _make_manager(tmp_path)
    from homunculus_brain.timers import TimerResetResult
    result = manager.reset(project="nonexistent", captured_at=_now(), tz=TZ)
    assert result.stored is False
    assert result.clarifying_question is not None
    assert "nonexistent" in result.clarifying_question.lower() or "no timer" in result.clarifying_question.lower()


# ---------------------------------------------------------------------------
# Test 11: Idempotent reset — second reset is a no-op
# ---------------------------------------------------------------------------


def test_reset_idempotent_second_call(tmp_path: Path):
    """Resetting twice in a row — second call sees total=0 already, clears 0."""
    manager = _make_manager(tmp_path)
    manager.start(project="gym", captured_at=_now(0), tz=TZ)
    manager.stop(project="gym", captured_at=_now(1800), tz=TZ)

    from homunculus_brain.timers import TimerResetResult
    result1 = manager.reset(project="gym", captured_at=_now(3600), tz=TZ)
    result2 = manager.reset(project="gym", captured_at=_now(7200), tz=TZ)

    assert result1.stored is True
    assert result2.stored is True
    assert result2.cleared_seconds == 0  # already at 0


# ---------------------------------------------------------------------------
# Test 12: reset preserves the project file (file exists after reset)
# ---------------------------------------------------------------------------


def test_reset_preserves_project_file(tmp_path: Path):
    """reset() must NOT delete the timer file — it zeroes it in place."""
    manager = _make_manager(tmp_path)
    manager.start(project="gym", captured_at=_now(0), tz=TZ)
    manager.stop(project="gym", captured_at=_now(1800), tz=TZ)
    manager.reset(project="gym", captured_at=_now(3600), tz=TZ)

    timer_path = tmp_path / "timers" / "gym.json"
    assert timer_path.exists(), "Timer file must exist after reset (project preserved)"

    data = json.loads(timer_path.read_text())
    assert data["project"] == "gym"
    assert data["slug"] == "gym"


# ---------------------------------------------------------------------------
# Test 13: Silent stop in reset does NOT enqueue a mac_notifier row
# ---------------------------------------------------------------------------


def test_reset_silent_stop_no_notification_sidecar(tmp_path: Path):
    """reset() stopping a running timer does NOT write a _reminders sidecar."""
    manager = _make_manager(tmp_path)
    manager.start(project="gym", captured_at=_now(0), tz=TZ)
    manager.reset(project="gym", captured_at=_now(1800), tz=TZ)

    reminders_dir = tmp_path / "_reminders"
    if reminders_dir.exists():
        timer_sidecars = list(reminders_dir.glob("timer.gym.*.json"))
        assert timer_sidecars == [], (
            f"reset() must not enqueue a notification. Found: {timer_sidecars}"
        )


# ---------------------------------------------------------------------------
# Activity log rows for stop_all and reset
# ---------------------------------------------------------------------------


def test_stop_all_writes_timer_stop_activity_per_project(tmp_path: Path):
    """stop_all() writes one timer_stop activity row per project stopped."""
    manager = _make_manager(tmp_path)
    manager.start(project="gym", captured_at=_now(0), tz=TZ)
    manager.start(project="deck", captured_at=_now(60), tz=TZ)
    manager.stop_all(captured_at=_now(1800), tz=TZ)

    activity_path = tmp_path / "_activity.jsonl"
    entries = [json.loads(ln) for ln in activity_path.read_text().splitlines() if ln.strip()]
    timer_stops = [e for e in entries if e.get("kind") == "timer_stop"]
    slugs = {e.get("details", {}).get("slug") for e in timer_stops}
    assert "gym" in slugs
    assert "deck" in slugs


def test_reset_writes_timer_reset_activity_row(tmp_path: Path):
    """reset() writes a timer_reset activity row with the pre-reset total."""
    manager = _make_manager(tmp_path)
    manager.start(project="gym", captured_at=_now(0), tz=TZ)
    manager.stop(project="gym", captured_at=_now(1800), tz=TZ)
    old_total = json.loads((tmp_path / "timers" / "gym.json").read_text())["total_seconds"]

    manager.reset(project="gym", captured_at=_now(3600), tz=TZ)

    activity_path = tmp_path / "_activity.jsonl"
    entries = [json.loads(ln) for ln in activity_path.read_text().splitlines() if ln.strip()]
    resets = [e for e in entries if e.get("kind") == "timer_reset"]
    assert resets, "Expected a timer_reset row in _activity.jsonl"
    details = resets[0].get("details", {})
    assert details.get("cleared_seconds") == old_total


def test_reset_running_writes_timer_stop_activity_row(tmp_path: Path):
    """reset() on a running project writes a timer_stop row (silent audit)."""
    manager = _make_manager(tmp_path)
    manager.start(project="gym", captured_at=_now(0), tz=TZ)
    manager.reset(project="gym", captured_at=_now(1800), tz=TZ)

    activity_path = tmp_path / "_activity.jsonl"
    entries = [json.loads(ln) for ln in activity_path.read_text().splitlines() if ln.strip()]
    timer_stops = [e for e in entries if e.get("kind") == "timer_stop"]
    assert timer_stops, "reset() on running timer must write a timer_stop activity row"


# ---------------------------------------------------------------------------
# stop_all notifications — each stop fires individual notification
# ---------------------------------------------------------------------------


def test_stop_all_fires_individual_notifications(tmp_path: Path):
    """stop_all() with 2 running timers writes 2 notification sidecars."""
    manager = _make_manager(tmp_path)
    manager.start(project="gym", captured_at=_now(0), tz=TZ)
    manager.start(project="deck", captured_at=_now(60), tz=TZ)
    manager.stop_all(captured_at=_now(1800), tz=TZ)

    reminders_dir = tmp_path / "_reminders"
    assert reminders_dir.exists()
    timer_sidecars = [f for f in reminders_dir.glob("timer.*.json")]
    assert len(timer_sidecars) == 2, (
        f"Expected 2 notification sidecars, got {len(timer_sidecars)}: {timer_sidecars}"
    )
