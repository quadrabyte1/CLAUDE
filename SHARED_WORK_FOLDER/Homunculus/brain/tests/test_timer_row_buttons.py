"""TDD tests for Herman v2.4.0 — timer row buttons on the dashboard.

Tests are written RED first against v2.3.0 code, then turn GREEN after
the feature is implemented.

Coverage:
  T1. POST /timer/start?project=foo → timer 'foo' is running. Idempotent.
  T2. POST /timer/stop?project=foo → timer 'foo' is stopped. Idempotent.
  T3. POST /timer/delete?project=foo → file gone. Nonexistent → 200 no-op.
  T4. GET /dashboard/ → HTML contains Start/Stop/Delete button text per timer.
  T5. Running timer row shows Stop enabled, Start disabled (disabled attr).
  T6. No server-side guard for delete confirm (browser confirm() is enough).
  T7. Dashboard version bumped to v0.6.
  T8. Herman VERSION bumped to 2.4.0.
"""

from __future__ import annotations

import json
from datetime import datetime, timedelta
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from zoneinfo import ZoneInfo


TZ = ZoneInfo("America/New_York")
NOW = datetime(2026, 9, 27, 10, 30, 0, tzinfo=TZ)


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


def _start_payload(project: str = "foo", offset_seconds: int = 0) -> dict:
    return {
        "project": project,
        "captured_at": (NOW + timedelta(seconds=offset_seconds)).isoformat(),
        "speaker_tz": "America/New_York",
    }


def _stop_payload(project: str = "foo", offset_seconds: int = 1800) -> dict:
    return {
        "project": project,
        "captured_at": (NOW + timedelta(seconds=offset_seconds)).isoformat(),
        "speaker_tz": "America/New_York",
    }


# ---------------------------------------------------------------------------
# T1: POST /timer/start via query param (dashboard form action)
# ---------------------------------------------------------------------------


def test_dashboard_timer_start_endpoint_via_form_post(tmp_path: Path, monkeypatch):
    """POST /timer/start with project in body starts the timer (200, running=True)."""
    with _client(tmp_path, monkeypatch) as client:
        r = client.post("/timer/start", json=_start_payload("foo"))
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["stored"] is True
    assert body["project"] == "foo"

    # Timer file must exist
    timer_file = tmp_path / "timers" / "foo.json"
    assert timer_file.exists()
    data = json.loads(timer_file.read_text())
    assert data["running"] is not None


def test_dashboard_timer_start_idempotent_double_post(tmp_path: Path, monkeypatch):
    """POST /timer/start twice doesn't error — idempotent, returns original started_at."""
    with _client(tmp_path, monkeypatch) as client:
        r1 = client.post("/timer/start", json=_start_payload("foo", offset_seconds=0))
        r2 = client.post("/timer/start", json=_start_payload("foo", offset_seconds=60))
    assert r1.status_code == 200
    assert r2.status_code == 200
    assert r1.json()["started_at"] == r2.json()["started_at"]


# ---------------------------------------------------------------------------
# T2: POST /timer/stop via query param (dashboard form action)
# ---------------------------------------------------------------------------


def test_dashboard_timer_stop_endpoint_via_form_post(tmp_path: Path, monkeypatch):
    """POST /timer/stop with project in body stops the timer (200, running=None)."""
    with _client(tmp_path, monkeypatch) as client:
        client.post("/timer/start", json=_start_payload("foo", offset_seconds=0))
        r = client.post("/timer/stop", json=_stop_payload("foo", offset_seconds=1800))
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["stored"] is True
    assert "duration_seconds" in body

    # Timer file: running must be None
    timer_file = tmp_path / "timers" / "foo.json"
    data = json.loads(timer_file.read_text())
    assert data["running"] is None


def test_dashboard_timer_stop_idempotent_not_running(tmp_path: Path, monkeypatch):
    """POST /timer/stop on an already-stopped timer returns 200 (no error crash)."""
    with _client(tmp_path, monkeypatch) as client:
        client.post("/timer/start", json=_start_payload("foo", offset_seconds=0))
        client.post("/timer/stop", json=_stop_payload("foo", offset_seconds=1800))
        # Stop again — already stopped
        r = client.post("/timer/stop", json=_stop_payload("foo", offset_seconds=3600))
    # The existing endpoint returns 400 for NoRunningTimer — that's fine for
    # the voice path. For the dashboard button we need either 200 or 400
    # (both acceptable — dashboard JS does a page-refresh regardless).
    assert r.status_code in (200, 400), r.text


def test_dashboard_timer_stop_nonexistent_project_does_not_500(tmp_path: Path, monkeypatch):
    """POST /timer/stop for a project that has never existed returns non-500."""
    with _client(tmp_path, monkeypatch) as client:
        r = client.post("/timer/stop", json=_stop_payload("ghost", offset_seconds=0))
    assert r.status_code != 500, f"Server crashed on stop of nonexistent project: {r.text}"


# ---------------------------------------------------------------------------
# T3: POST /timer/delete — new endpoint
# ---------------------------------------------------------------------------


def test_timer_delete_removes_file(tmp_path: Path, monkeypatch):
    """POST /timer/delete with project=foo removes vault/timers/foo.json."""
    with _client(tmp_path, monkeypatch) as client:
        client.post("/timer/start", json=_start_payload("foo", offset_seconds=0))
        client.post("/timer/stop", json=_stop_payload("foo", offset_seconds=1800))

        timer_file = tmp_path / "timers" / "foo.json"
        assert timer_file.exists(), "Precondition: timer file must exist before delete"

        r = client.post("/timer/delete", json={"project": "foo"})
    assert r.status_code == 200, r.text
    body = r.json()
    assert body.get("deleted") is True
    assert not timer_file.exists(), "Timer file must be gone after /timer/delete"


def test_timer_delete_nonexistent_project_is_noop(tmp_path: Path, monkeypatch):
    """POST /timer/delete for an unknown project returns 200 no-op (deleted=False)."""
    with _client(tmp_path, monkeypatch) as client:
        r = client.post("/timer/delete", json={"project": "ghost"})
    assert r.status_code == 200, r.text
    body = r.json()
    # deleted=False or deleted=True both accepted — no error, no 404
    assert "deleted" in body


def test_timer_delete_running_timer_stops_first(tmp_path: Path, monkeypatch):
    """POST /timer/delete on a running timer stops it silently then deletes file."""
    with _client(tmp_path, monkeypatch) as client:
        client.post("/timer/start", json=_start_payload("foo", offset_seconds=0))

        timer_file = tmp_path / "timers" / "foo.json"
        assert timer_file.exists()

        r = client.post("/timer/delete", json={"project": "foo"})
    assert r.status_code == 200, r.text
    assert not timer_file.exists(), "Timer file must be deleted even when it was running"


def test_timer_delete_writes_activity_log(tmp_path: Path, monkeypatch):
    """POST /timer/delete writes a timer_delete row to _activity.jsonl."""
    with _client(tmp_path, monkeypatch) as client:
        client.post("/timer/start", json=_start_payload("foo", offset_seconds=0))
        client.post("/timer/delete", json={"project": "foo"})

    activity = tmp_path / "_activity.jsonl"
    assert activity.exists()
    entries = [json.loads(ln) for ln in activity.read_text().splitlines() if ln.strip()]
    deletes = [e for e in entries if e.get("kind") == "timer_delete"]
    assert deletes, "No timer_delete row in _activity.jsonl"


def test_timer_delete_removed_project_not_in_totals(tmp_path: Path, monkeypatch):
    """After /timer/delete, the project no longer appears in /timers/totals."""
    with _client(tmp_path, monkeypatch) as client:
        client.post("/timer/start", json=_start_payload("foo", offset_seconds=0))
        client.post("/timer/stop", json=_stop_payload("foo", offset_seconds=1800))
        client.post("/timer/delete", json={"project": "foo"})
        r = client.get("/timers/totals")
    totals = r.json()
    slugs = [t["slug"] for t in totals]
    assert "foo" not in slugs, f"Deleted project 'foo' still in totals: {slugs}"


# ---------------------------------------------------------------------------
# T4: GET /dashboard/ HTML contains Start / Stop / Delete per timer row
# ---------------------------------------------------------------------------


def test_dashboard_html_contains_timer_button_names(tmp_path: Path, monkeypatch):
    """GET /dashboard/ HTML contains 'Start', 'Stop', 'Delete' button text."""
    with _client(tmp_path, monkeypatch) as client:
        r = client.get("/dashboard/")
    assert r.status_code == 200, r.text
    html = r.text
    # The buttons must appear somewhere in the static HTML (the template renders
    # them unconditionally; JS updates disabled state dynamically).
    assert "Start" in html, "Dashboard HTML must contain 'Start' button"
    assert "Stop" in html, "Dashboard HTML must contain 'Stop' button"
    assert "Delete" in html, "Dashboard HTML must contain 'Delete' button"


def test_dashboard_html_uses_post_forms_for_timer_actions(tmp_path: Path, monkeypatch):
    """Dashboard timer buttons use POST (not GET) for state-changing actions."""
    with _client(tmp_path, monkeypatch) as client:
        r = client.get("/dashboard/")
    html = r.text
    # Should see POST forms or fetch with method POST (not <a> href with timer actions)
    assert "timer/start" in html or "timer-start" in html, \
        "Dashboard must reference /timer/start endpoint"
    assert "timer/stop" in html or "timer-stop" in html, \
        "Dashboard must reference /timer/stop endpoint"
    assert "timer/delete" in html or "timer-delete" in html, \
        "Dashboard must reference /timer/delete endpoint"


# ---------------------------------------------------------------------------
# T5: Running timer row — Stop enabled, Start disabled
# ---------------------------------------------------------------------------


def test_dashboard_timers_api_running_flag(tmp_path: Path, monkeypatch):
    """GET /dashboard/timers with a running timer has is_running=True in totals."""
    with _client(tmp_path, monkeypatch) as client:
        client.post("/timer/start", json=_start_payload("foo", offset_seconds=0))
        r = client.get("/dashboard/timers")
    body = r.json()
    running_slugs = {t["slug"] for t in body["running"]}
    assert "foo" in running_slugs

    totals = body["totals"]
    foo_total = next((t for t in totals if t["slug"] == "foo"), None)
    assert foo_total is not None
    assert foo_total["is_running"] is True


def test_dashboard_timers_api_stopped_flag(tmp_path: Path, monkeypatch):
    """GET /dashboard/timers after stop shows is_running=False for stopped project."""
    with _client(tmp_path, monkeypatch) as client:
        client.post("/timer/start", json=_start_payload("foo", offset_seconds=0))
        client.post("/timer/stop", json=_stop_payload("foo", offset_seconds=1800))
        r = client.get("/dashboard/timers")
    body = r.json()
    assert body["running"] == []
    foo_total = next((t for t in body["totals"] if t["slug"] == "foo"), None)
    assert foo_total is not None
    assert foo_total["is_running"] is False


# ---------------------------------------------------------------------------
# T6: No server-side guard for delete confirm (browser confirm() only)
# ---------------------------------------------------------------------------


def test_timer_delete_no_confirm_required_server_side(tmp_path: Path, monkeypatch):
    """POST /timer/delete succeeds without any confirm token — client-side only."""
    with _client(tmp_path, monkeypatch) as client:
        client.post("/timer/start", json=_start_payload("foo"))
        # No special 'confirm' field needed — should delete immediately
        r = client.post("/timer/delete", json={"project": "foo"})
    assert r.status_code == 200, r.text
    assert r.json().get("deleted") is True


# ---------------------------------------------------------------------------
# T7: Dashboard version bumped to v0.6
# ---------------------------------------------------------------------------


def test_dashboard_version_is_v06(tmp_path: Path, monkeypatch):
    """Dashboard DASHBOARD_VERSION must be v0.6 after this feature ships."""
    from homunculus_brain.dashboard import DASHBOARD_VERSION, DASHBOARD_HTML
    assert DASHBOARD_VERSION == "v0.6", (
        f"Expected DASHBOARD_VERSION='v0.6', got {DASHBOARD_VERSION!r}. "
        "Bump it in dashboard.py as part of this feature."
    )
    assert "v0.6" in DASHBOARD_HTML, "v0.6 must be baked into DASHBOARD_HTML"


# ---------------------------------------------------------------------------
# T8: Herman VERSION bumped to 2.4.0
# ---------------------------------------------------------------------------


def test_herman_version_is_240():
    """Herman VERSION must be 2.4.0 after this feature ships."""
    from homunculus_brain import VERSION
    assert VERSION == "2.4.0", (
        f"Expected VERSION='2.4.0', got {VERSION!r}. "
        "Bump it in homunculus_brain/__init__.py."
    )
