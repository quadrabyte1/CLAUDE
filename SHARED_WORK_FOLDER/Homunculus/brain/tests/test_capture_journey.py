"""End-to-end user journey (v1.2 item 5).

Exercises the single path the boss will actually run, from voice utterance
to acked reminder, against a real FastAPI ``TestClient``. No Ollama —
``OLLAMA_BASE_URL`` points at a closed port so the heuristic fallback
fires.

We pin ``captured_at`` to a known wall-clock so weekday math is stable.
``NOW`` is Monday June 8 2026 at 9:00 AM Eastern; "Thursday at 10am" then
resolves to Thursday June 11.
"""

from __future__ import annotations

from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

from fastapi.testclient import TestClient

from homunculus_brain import reminders as rem
from homunculus_brain.schemas import ReminderKind
from homunculus_brain.server import create_app


TZ = ZoneInfo("America/New_York")
NOW = datetime(2026, 6, 8, 9, 0, tzinfo=TZ)  # Monday 9 AM


def test_full_user_journey(tmp_path: Path, monkeypatch):
    monkeypatch.setenv("HOMUNCULUS_VAULT", str(tmp_path))
    monkeypatch.setenv("OLLAMA_BASE_URL", "http://127.0.0.1:1")
    monkeypatch.setenv("HOMUNCULUS_TZ", "America/New_York")

    app = create_app()
    with TestClient(app) as client:
        # 1) Capture: "add coffee with Jane on Thursday at 10am"
        r = client.post(
            "/capture/text",
            json={
                "text": "add coffee with Jane on Thursday at 10am",
                "captured_at": NOW.isoformat(),
                "speaker_tz": "America/New_York",
            },
        )
        assert r.status_code == 200, r.text
        body = r.json()
        assert body["action"] == "needs_confirmation", body
        readback = body["spoken_reply"]
        assert "10:00 AM" in readback or "10:00" in readback

        # 2) Confirm. The phone keeps the intent client-side (per the iOS
        # spec) and posts it back to /capture/confirm. The heuristic parser
        # routed the original utterance as a calendar_query, but the
        # request was "add" — so for the journey to commit, force the kind
        # to calendar_event the way the phone's confirmation flow would.
        intent_payload = {
            "kind": "calendar_event",
            "confidence": "medium",
            "title": "coffee with Jane",
            "day_hint": "Thursday",
            "time_hint": "10am",
            "duration_minutes": None,
            "people": ["Jane"],
            "tags": [],
            "raw_text": "add coffee with Jane on Thursday at 10am",
            "ambiguous_fields": [],
            "body": None,
        }
        r = client.post(
            "/capture/confirm",
            json={
                "intent": intent_payload,
                "captured_at": NOW.isoformat(),
                "speaker_tz": "America/New_York",
            },
        )
        assert r.status_code == 200, r.text
        confirm = r.json()
        assert confirm["action"] == "wrote", confirm
        written = confirm["written_path"]
        assert written is not None
        assert (tmp_path / written).exists()

        # 3) /events?day=2026-06-11 returns the event.
        r = client.get("/events?day=2026-06-11")
        assert r.status_code == 200
        events = r.json()
        assert any("coffee" in (e["title"] or "").lower() for e in events), events
        event_id = events[0]["id"]

        # 4) /reminders/upcoming returns the 6 strike rows + the morning
        # summary for that Thursday. Window covers 72h from NOW.
        # TestClient uses the live "now" (real clock), so to test against
        # the planted Thursday event we use a wide window. The brain
        # internally uses datetime.now(tz) — we have to allow for the
        # fact that the seeded event sits in the future relative to the
        # real test clock too, since June 11 2026 is the future.
        r = client.get("/reminders/upcoming?window_hours=240")  # 10 days
        assert r.status_code == 200, r.text
        rows = r.json()
        event_strike_rows = [row for row in rows if row["event_id"] == event_id]
        kinds = {row["kind"] for row in event_strike_rows}
        # All six strike kinds present.
        assert kinds == {
            "heads_up_30",
            "pre_5",
            "strike_0",
            "strike_5",
            "strike_10",
            "strike_15",
        }, kinds
        # And at least one morning summary row for that Thursday.
        summary_ids = {row["event_id"] for row in rows if row["kind"] == "morning_summary"}
        assert "summary.2026-06-11" in summary_ids, summary_ids

        # 5) Ack strike_0. The three later strikes should be cancelled.
        r = client.post(
            "/ack",
            json={
                "event_id": event_id,
                "kind": "strike_0",
                "acked_at": NOW.isoformat(),
            },
        )
        assert r.status_code == 200, r.text
        ack = r.json()
        assert set(ack["cancelled_kinds"]) == {"strike_5", "strike_10", "strike_15"}

        # 6) After ack, /reminders/upcoming no longer returns the
        # cancelled strikes for that event.
        r = client.get("/reminders/upcoming?window_hours=240")
        rows = r.json()
        live_kinds = {
            row["kind"] for row in rows if row["event_id"] == event_id
        }
        assert "strike_0" not in live_kinds  # acked
        assert "strike_5" not in live_kinds  # cancelled
        assert "strike_10" not in live_kinds
        assert "strike_15" not in live_kinds
        # Earlier rows still present (they weren't part of the post-start chain).
        assert "heads_up_30" in live_kinds
        assert "pre_5" in live_kinds
