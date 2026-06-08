"""HTTP endpoints for /reminders/upcoming and /ack (v1.2 item 4)."""

from __future__ import annotations

from datetime import datetime, timedelta
from pathlib import Path
from zoneinfo import ZoneInfo

from fastapi.testclient import TestClient

from homunculus_brain import calendar as cal
from homunculus_brain import reminders as rem
from homunculus_brain.schemas import ReminderKind
from homunculus_brain.server import create_app


TZ = ZoneInfo("America/New_York")


def _seed_event_tomorrow(tmp_path: Path) -> str:
    """Create an event tomorrow at 10am and persist its strike schedule."""
    now = datetime.now(TZ)
    when = (now + timedelta(days=1)).replace(hour=10, minute=0, second=0, microsecond=0)
    event = cal.create_event(
        tmp_path,
        title="Coffee with Jane",
        starts_at=when,
        duration_minutes=30,
        tz_name="America/New_York",
    )
    rows = rem.build_event_schedule(event)
    rem.persist_event_schedule(tmp_path, event, rows)
    return event.id


def test_reminders_upcoming_returns_strike_rows_and_summary(tmp_path: Path, monkeypatch):
    monkeypatch.setenv("HOMUNCULUS_VAULT", str(tmp_path))
    event_id = _seed_event_tomorrow(tmp_path)

    app = create_app()
    with TestClient(app) as client:
        r = client.get("/reminders/upcoming?window_hours=72")
        assert r.status_code == 200, r.text
        rows = r.json()

    # 6 strike rows + at least 1 morning summary in the window.
    kinds = [row["kind"] for row in rows]
    assert kinds.count("strike_0") == 1
    assert kinds.count("strike_15") == 1
    assert "morning_summary" in kinds
    # Strike rows reference the right event.
    strike_event_ids = {row["event_id"] for row in rows if row["kind"].startswith("strike_")}
    assert event_id in strike_event_ids
    # Sorted ascending by fire_at.
    fire_ats = [row["fire_at"] for row in rows]
    assert fire_ats == sorted(fire_ats)


def test_reminders_upcoming_respects_status_filter(tmp_path: Path, monkeypatch):
    """Rows marked acked or cancelled are excluded from /reminders/upcoming."""
    monkeypatch.setenv("HOMUNCULUS_VAULT", str(tmp_path))
    event_id = _seed_event_tomorrow(tmp_path)

    # Manually flip strike_0 to acked + strike_5 to cancelled.
    rows = rem.read_event_rows(tmp_path, event_id)
    updated = []
    for r in rows:
        if r.kind == ReminderKind.STRIKE_0:
            updated.append(r.model_copy(update={"status": "acked"}))
        elif r.kind == ReminderKind.STRIKE_5:
            updated.append(r.model_copy(update={"status": "cancelled"}))
        else:
            updated.append(r)
    rem._persist_rows(tmp_path, event_id, updated)

    app = create_app()
    with TestClient(app) as client:
        r = client.get("/reminders/upcoming")
        live = r.json()
    kinds_for_event = [row["kind"] for row in live if row["event_id"] == event_id]
    assert "strike_0" not in kinds_for_event
    assert "strike_5" not in kinds_for_event
    # The later strikes still pending should remain.
    assert "strike_10" in kinds_for_event


def test_ack_cancels_remaining_strikes(tmp_path: Path, monkeypatch):
    monkeypatch.setenv("HOMUNCULUS_VAULT", str(tmp_path))
    event_id = _seed_event_tomorrow(tmp_path)

    app = create_app()
    with TestClient(app) as client:
        r = client.post(
            "/ack",
            json={
                "event_id": event_id,
                "kind": "strike_0",
                "acked_at": datetime.now(TZ).isoformat(),
            },
        )
        assert r.status_code == 200, r.text
        body = r.json()
        assert body["acked_kind"] == "strike_0"
        cancelled = set(body["cancelled_kinds"])
        assert cancelled == {"strike_5", "strike_10", "strike_15"}

    # Sidecar reflects the new statuses.
    persisted = rem.read_event_rows(tmp_path, event_id)
    statuses = {row.kind: row.status for row in persisted}
    assert statuses[ReminderKind.STRIKE_0] == "acked"
    assert statuses[ReminderKind.STRIKE_5] == "cancelled"
    assert statuses[ReminderKind.STRIKE_10] == "cancelled"
    assert statuses[ReminderKind.STRIKE_15] == "cancelled"
    # Earlier rows untouched.
    assert statuses[ReminderKind.HEADS_UP_30] == "pending"


def test_ack_idempotent(tmp_path: Path, monkeypatch):
    """Double-acking the same row is a no-op the second time around."""
    monkeypatch.setenv("HOMUNCULUS_VAULT", str(tmp_path))
    event_id = _seed_event_tomorrow(tmp_path)

    app = create_app()
    with TestClient(app) as client:
        first = client.post(
            "/ack",
            json={"event_id": event_id, "kind": "strike_0",
                  "acked_at": datetime.now(TZ).isoformat()},
        ).json()
        second = client.post(
            "/ack",
            json={"event_id": event_id, "kind": "strike_0",
                  "acked_at": datetime.now(TZ).isoformat()},
        ).json()

    assert first["cancelled_kinds"] == ["strike_5", "strike_10", "strike_15"]
    # Second time: nothing left to cancel.
    assert second["cancelled_kinds"] == []
    assert second["acked_kind"] == "strike_0"


def test_ack_unknown_event_does_not_404(tmp_path: Path, monkeypatch):
    monkeypatch.setenv("HOMUNCULUS_VAULT", str(tmp_path))
    app = create_app()
    with TestClient(app) as client:
        r = client.post(
            "/ack",
            json={"event_id": "nonexistent-event", "kind": "strike_0",
                  "acked_at": datetime.now(TZ).isoformat()},
        )
        assert r.status_code == 200
        body = r.json()
        assert body["cancelled_kinds"] == []
        assert body["rows"] == []
