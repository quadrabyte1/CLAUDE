"""TDD tests for Herman v2.0.0 timer HTTP routes and capture_parsed dispatch.

Written RED first. These must fail against v1.9.0 code and pass after v2.0.0.

Tests cover:
  15. POST /timer/start returns 200 with TimerStartResponse
  16. POST /capture/parsed with verb=start_timer dispatches correctly
  17. POST /timer/stop returns TimerStopResponse with duration + total
  18. Stop enqueues a notification visible via GET /reminders/upcoming
  19. GET /timers/running reflects state
  20. GET /timers/totals reflects state
  21. _activity.jsonl records timer_start and timer_stop kinds
"""

from __future__ import annotations

import json
from datetime import datetime, timedelta
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from zoneinfo import ZoneInfo


TZ = ZoneInfo("America/New_York")
NOW = datetime(2026, 9, 22, 10, 30, 0, tzinfo=TZ)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _client(tmp_path: Path, monkeypatch) -> TestClient:
    monkeypatch.setenv("HOMUNCULUS_VAULT", str(tmp_path))
    monkeypatch.setenv("HOMUNCULUS_TZ", "America/New_York")
    monkeypatch.setenv("OLLAMA_BASE_URL", "http://127.0.0.1:1")
    monkeypatch.setenv("SPRITE_WARNINGS_PATH", str(tmp_path / "sprite" / "warnings.md"))
    monkeypatch.setenv("HOMUNCULUS_MIN_CONFIDENCE", "0.6")
    from homunculus_brain.server import create_app
    return TestClient(create_app())


def _start_payload(project: str = "gym", offset_seconds: int = 0) -> dict:
    return {
        "project": project,
        "captured_at": (NOW + timedelta(seconds=offset_seconds)).isoformat(),
        "speaker_tz": "America/New_York",
    }


def _stop_payload(project: str = "gym", offset_seconds: int = 1800) -> dict:
    return {
        "project": project,
        "captured_at": (NOW + timedelta(seconds=offset_seconds)).isoformat(),
        "speaker_tz": "America/New_York",
    }


# ---------------------------------------------------------------------------
# Test 15: POST /timer/start
# ---------------------------------------------------------------------------


def test_timer_start_returns_200(tmp_path: Path, monkeypatch):
    """POST /timer/start returns 200 with TimerStartResponse shape."""
    with _client(tmp_path, monkeypatch) as client:
        r = client.post("/timer/start", json=_start_payload())
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["stored"] is True
    assert body["project"] == "gym"
    assert body["slug"] == "gym"
    assert "started_at" in body
    assert "record_id" in body


def test_timer_start_idempotent(tmp_path: Path, monkeypatch):
    """POST /timer/start twice on same project returns original started_at."""
    with _client(tmp_path, monkeypatch) as client:
        r1 = client.post("/timer/start", json=_start_payload(offset_seconds=0))
        r2 = client.post("/timer/start", json=_start_payload(offset_seconds=60))
    assert r1.status_code == 200
    assert r2.status_code == 200

    body1 = r1.json()
    body2 = r2.json()
    # Both return stored=True; started_at must be from the FIRST call
    # (or at least the record_id should match)
    assert body1["started_at"] == body2["started_at"], (
        "Idempotent start must preserve original started_at"
    )


# ---------------------------------------------------------------------------
# Test 16: POST /capture/parsed with verb=start_timer dispatches correctly
# ---------------------------------------------------------------------------


def test_capture_parsed_start_timer_dispatches(tmp_path: Path, monkeypatch):
    """POST /capture/parsed with verb=start_timer routes to timer start handler."""
    payload = {
        "verb": "start_timer",
        "subject": "gym",
        "project": "gym",
        "when": None,
        "criticality": "normal",
        "confidence": 0.95,
        "raw_transcript": "Start gym",
        "audio_path": "/tmp/test.m4a",
        "captured_at": NOW.isoformat(),
        "speaker_tz": "America/New_York",
    }
    with _client(tmp_path, monkeypatch) as client:
        r = client.post("/capture/parsed", json=payload)
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["stored"] is True
    assert body["verb"] == "start_timer"

    # Timer file should exist
    timer_file = tmp_path / "timers" / "gym.json"
    assert timer_file.exists()


def test_capture_parsed_stop_timer_dispatches(tmp_path: Path, monkeypatch):
    """POST /capture/parsed with verb=stop_timer routes to timer stop handler."""
    # First start it
    start_payload = {
        "verb": "start_timer",
        "subject": "gym",
        "project": "gym",
        "when": None,
        "criticality": "normal",
        "confidence": 0.95,
        "raw_transcript": "Start gym",
        "audio_path": "/tmp/test.m4a",
        "captured_at": NOW.isoformat(),
        "speaker_tz": "America/New_York",
    }
    stop_payload = {
        "verb": "stop_timer",
        "subject": "gym",
        "project": "gym",
        "when": None,
        "criticality": "normal",
        "confidence": 0.95,
        "raw_transcript": "Stop gym",
        "audio_path": "/tmp/test.m4a",
        "captured_at": (NOW + timedelta(seconds=1800)).isoformat(),
        "speaker_tz": "America/New_York",
    }
    with _client(tmp_path, monkeypatch) as client:
        client.post("/capture/parsed", json=start_payload)
        r = client.post("/capture/parsed", json=stop_payload)
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["stored"] is True
    assert body["verb"] == "stop_timer"


# ---------------------------------------------------------------------------
# Test 17: POST /timer/stop
# ---------------------------------------------------------------------------


def test_timer_stop_returns_duration_and_total(tmp_path: Path, monkeypatch):
    """POST /timer/stop returns duration_seconds and total_seconds."""
    with _client(tmp_path, monkeypatch) as client:
        client.post("/timer/start", json=_start_payload(offset_seconds=0))
        r = client.post("/timer/stop", json=_stop_payload(offset_seconds=1800))
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["stored"] is True
    assert "duration_seconds" in body
    assert "total_seconds" in body
    assert body["duration_seconds"] > 0
    assert body["total_seconds"] == body["duration_seconds"]


def test_timer_stop_no_running_returns_400(tmp_path: Path, monkeypatch):
    """POST /timer/stop on non-running project returns an error (400 or 200 with error body)."""
    with _client(tmp_path, monkeypatch) as client:
        r = client.post("/timer/stop", json=_stop_payload())
    # Either 400 or 200 with stored=False/error message
    body = r.json()
    if r.status_code == 200:
        assert body.get("stored") is False or "error" in body or "message" in body
    else:
        assert r.status_code in (400, 404, 422)


# ---------------------------------------------------------------------------
# Test 18: Stop enqueues notification
# ---------------------------------------------------------------------------


def test_timer_stop_enqueues_notification(tmp_path: Path, monkeypatch):
    """After /timer/stop, GET /reminders/upcoming?include_fired=true has a timer_stop row."""
    with _client(tmp_path, monkeypatch) as client:
        client.post("/timer/start", json=_start_payload(offset_seconds=0))
        client.post("/timer/stop", json=_stop_payload(offset_seconds=1800))
        r = client.get("/reminders/upcoming?include_fired=true")

    assert r.status_code == 200, r.text
    rows = r.json()
    timer_stop_rows = [row for row in rows if row.get("kind") == "timer_stop"]
    assert timer_stop_rows, (
        f"Expected a timer_stop notification row. Got: {[r.get('kind') for r in rows]}"
    )
    row = timer_stop_rows[0]
    assert "body" in row
    assert "gym" in row["body"].lower() or "minutes" in row["body"].lower()


def test_timer_stop_notification_body_format(tmp_path: Path, monkeypatch):
    """Timer stop notification body contains duration and total."""
    with _client(tmp_path, monkeypatch) as client:
        client.post("/timer/start", json=_start_payload(offset_seconds=0))
        client.post("/timer/stop", json=_stop_payload(offset_seconds=3672))  # ~1h 1m 12s
        r = client.get("/reminders/upcoming?include_fired=true")

    rows = r.json()
    timer_stop_rows = [row for row in rows if row.get("kind") == "timer_stop"]
    assert timer_stop_rows
    body = timer_stop_rows[0]["body"]
    # Should mention gym and time
    assert "gym" in body.lower()
    # For > 1h: no "seconds" word in body
    assert "seconds" not in body.lower(), (
        f"Duration >= 1h should drop seconds from body. Got: {body}"
    )


# ---------------------------------------------------------------------------
# Test 19: GET /timers/running
# ---------------------------------------------------------------------------


def test_timers_running_empty_initially(tmp_path: Path, monkeypatch):
    """GET /timers/running returns empty list when no timers active."""
    with _client(tmp_path, monkeypatch) as client:
        r = client.get("/timers/running")
    assert r.status_code == 200, r.text
    assert r.json() == []


def test_timers_running_reflects_active_timer(tmp_path: Path, monkeypatch):
    """GET /timers/running returns running timer after start."""
    with _client(tmp_path, monkeypatch) as client:
        client.post("/timer/start", json=_start_payload())
        r = client.get("/timers/running")
    assert r.status_code == 200, r.text
    running = r.json()
    assert len(running) == 1
    assert running[0]["project"] == "gym"
    assert "elapsed_seconds" in running[0]
    assert running[0]["elapsed_seconds"] >= 0


def test_timers_running_clears_after_stop(tmp_path: Path, monkeypatch):
    """GET /timers/running is empty after stop."""
    with _client(tmp_path, monkeypatch) as client:
        client.post("/timer/start", json=_start_payload(offset_seconds=0))
        client.post("/timer/stop", json=_stop_payload(offset_seconds=1800))
        r = client.get("/timers/running")
    assert r.json() == []


# ---------------------------------------------------------------------------
# Test 20: GET /timers/totals
# ---------------------------------------------------------------------------


def test_timers_totals_empty_initially(tmp_path: Path, monkeypatch):
    """GET /timers/totals returns empty list when no timers exist."""
    with _client(tmp_path, monkeypatch) as client:
        r = client.get("/timers/totals")
    assert r.status_code == 200, r.text
    assert r.json() == []


def test_timers_totals_after_session(tmp_path: Path, monkeypatch):
    """GET /timers/totals returns project with total_seconds after stop."""
    with _client(tmp_path, monkeypatch) as client:
        client.post("/timer/start", json=_start_payload(offset_seconds=0))
        client.post("/timer/stop", json=_stop_payload(offset_seconds=1800))
        r = client.get("/timers/totals")
    assert r.status_code == 200, r.text
    totals = r.json()
    assert len(totals) == 1
    assert totals[0]["project"] == "gym"
    assert totals[0]["total_seconds"] > 0
    assert "last_touched_at" in totals[0]
    assert totals[0]["is_running"] is False


def test_timers_totals_is_running_flag(tmp_path: Path, monkeypatch):
    """GET /timers/totals shows is_running=True for active timer."""
    with _client(tmp_path, monkeypatch) as client:
        client.post("/timer/start", json=_start_payload())
        r = client.get("/timers/totals")
    totals = r.json()
    assert len(totals) == 1
    assert totals[0]["is_running"] is True


# ---------------------------------------------------------------------------
# Test 21: _activity.jsonl records
# ---------------------------------------------------------------------------


def test_activity_log_has_timer_start_row(tmp_path: Path, monkeypatch):
    """After /timer/start, _activity.jsonl has a timer_start row."""
    with _client(tmp_path, monkeypatch) as client:
        client.post("/timer/start", json=_start_payload())

    activity_path = tmp_path / "_activity.jsonl"
    assert activity_path.exists()
    entries = [json.loads(ln) for ln in activity_path.read_text().splitlines() if ln.strip()]
    timer_starts = [e for e in entries if e.get("kind") == "timer_start"]
    assert timer_starts, "No timer_start row in _activity.jsonl"
    entry = timer_starts[0]
    details = entry.get("details", {})
    assert details.get("project") == "gym"


def test_activity_log_has_timer_stop_row(tmp_path: Path, monkeypatch):
    """After /timer/stop, _activity.jsonl has a timer_stop row."""
    with _client(tmp_path, monkeypatch) as client:
        client.post("/timer/start", json=_start_payload(offset_seconds=0))
        client.post("/timer/stop", json=_stop_payload(offset_seconds=1800))

    activity_path = tmp_path / "_activity.jsonl"
    entries = [json.loads(ln) for ln in activity_path.read_text().splitlines() if ln.strip()]
    timer_stops = [e for e in entries if e.get("kind") == "timer_stop"]
    assert timer_stops, "No timer_stop row in _activity.jsonl"
    entry = timer_stops[0]
    details = entry.get("details", {})
    assert details.get("project") == "gym"
    assert "duration_seconds" in details
    assert "total_seconds" in details


# ---------------------------------------------------------------------------
# GET /dashboard/timers endpoint
# ---------------------------------------------------------------------------


def test_dashboard_timers_endpoint_exists(tmp_path: Path, monkeypatch):
    """GET /dashboard/timers returns 200 with running and totals keys."""
    with _client(tmp_path, monkeypatch) as client:
        r = client.get("/dashboard/timers")
    assert r.status_code == 200, r.text
    body = r.json()
    assert "running" in body
    assert "totals" in body
    assert isinstance(body["running"], list)
    assert isinstance(body["totals"], list)


def test_dashboard_timers_reflects_active_timer(tmp_path: Path, monkeypatch):
    """GET /dashboard/timers shows running timer under 'running' key."""
    with _client(tmp_path, monkeypatch) as client:
        client.post("/timer/start", json=_start_payload())
        r = client.get("/dashboard/timers")
    body = r.json()
    assert len(body["running"]) == 1
    assert body["running"][0]["project"] == "gym"


# ---------------------------------------------------------------------------
# Dashboard data includes timer_start / timer_stop rows
# ---------------------------------------------------------------------------


def test_dashboard_data_includes_timer_kinds(tmp_path: Path, monkeypatch):
    """GET /dashboard/data shows timer_start and timer_stop rows."""
    with _client(tmp_path, monkeypatch) as client:
        client.post("/timer/start", json=_start_payload(offset_seconds=0))
        client.post("/timer/stop", json=_stop_payload(offset_seconds=1800))
        r = client.get("/dashboard/data")

    body = r.json()
    kinds = {row["kind"] for row in body["rows"]}
    assert "timer_start" in kinds, f"Expected timer_start in dashboard rows. Got: {kinds}"
    assert "timer_stop" in kinds, f"Expected timer_stop in dashboard rows. Got: {kinds}"


def test_dashboard_data_timer_rows_have_stopwatch_icon(tmp_path: Path, monkeypatch):
    """timer_start/stop rows carry the stopwatch icon."""
    with _client(tmp_path, monkeypatch) as client:
        client.post("/timer/start", json=_start_payload(offset_seconds=0))
        client.post("/timer/stop", json=_stop_payload(offset_seconds=1800))
        r = client.get("/dashboard/data")

    body = r.json()
    timer_rows = [row for row in body["rows"] if row["kind"] in ("timer_start", "timer_stop")]
    for row in timer_rows:
        assert row["icon"] == "⏱", f"Expected ⏱ icon, got {row['icon']!r}"
