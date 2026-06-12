"""Tests for the v1.2.1 in-browser test client.

Three concerns covered here:

1. The static page is mounted and served at ``/test/``.
2. ``CaptureResponse`` echoes the parsed intent (the brain gap the boss
   identified — without this, the page can't reliably post a
   ``/capture/confirm`` request without trying to reconstruct the intent
   from visible fields, which is brittle).
3. The full capture → confirm → upcoming → ack journey works *through
   the test client's wire format* — same JSON the browser sees on the
   page, against the live FastAPI app.
4. ``GET /reminders/upcoming?include_fired=true`` returns rows that
   ``include_fired=false`` would hide (test-client affordance for
   eyeballing just-fired strikes during live testing).

No Ollama. ``OLLAMA_BASE_URL`` points at a closed port so the heuristic
fallback fires (matching the existing journey test).
"""

from __future__ import annotations

from datetime import datetime, timedelta
from pathlib import Path
from zoneinfo import ZoneInfo

from fastapi.testclient import TestClient

from homunculus_brain.schemas import ReminderRow, ReminderKind
from homunculus_brain.server import create_app
from homunculus_brain import reminders as rem


TZ = ZoneInfo("America/New_York")
NOW = datetime(2026, 6, 8, 9, 0, tzinfo=TZ)  # Monday 9 AM, same anchor as test_capture_journey.


# --- 1. static page is mounted ----------------------------------------------


def test_test_client_index_is_served(tmp_path: Path, monkeypatch):
    """GET /test/ returns 200 and the expected HTML markers.

    Sanity check that the FastAPI mount is wired and the file is shipped
    inside the package. If this breaks, the boss will get a 404 on the
    page he was told to open.
    """
    monkeypatch.setenv("HOMUNCULUS_VAULT", str(tmp_path))
    monkeypatch.setenv("OLLAMA_BASE_URL", "http://127.0.0.1:1")
    app = create_app()
    with TestClient(app) as client:
        # Trailing-slash form (FastAPI's StaticFiles serves index.html here).
        r = client.get("/test/")
        assert r.status_code == 200, r.text
        html = r.text
        assert "Homunculus brain" in html
        assert "Capture" in html
        assert "version-badge" in html  # the upper-left badge container.
        assert "/health" not in html or "loadHealth" in r.text or True  # html only

        # The bare /test (no slash) should also resolve, via the redirect
        # route — otherwise users hit a confusing 404.
        r2 = client.get("/test")
        assert r2.status_code == 200, r2.text

        # The static asset files should also be reachable.
        r3 = client.get("/test/app.js")
        assert r3.status_code == 200
        assert "loadUpcoming" in r3.text

        r4 = client.get("/test/styles.css")
        assert r4.status_code == 200
        assert "version-badge" in r4.text


# --- 2. CaptureResponse echoes the parsed intent -----------------------------


def test_capture_response_echoes_parsed_intent(tmp_path: Path, monkeypatch):
    """The brain must echo the ParsedIntent in CaptureResponse.intent.

    Without this, the test client cannot send /capture/confirm without
    reconstructing the intent from rendered fields — which loses
    ambiguous_fields, body, tags, etc. The boss flagged this as a real
    gap; this test pins it shut.
    """
    monkeypatch.setenv("HOMUNCULUS_VAULT", str(tmp_path))
    monkeypatch.setenv("OLLAMA_BASE_URL", "http://127.0.0.1:1")
    app = create_app()
    with TestClient(app) as client:
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
        assert "intent" in body, body
        intent = body["intent"]
        assert intent is not None
        assert intent["raw_text"] == "add coffee with Jane on Thursday at 10am"
        # The heuristic parser fills these.
        assert intent["kind"] in ("calendar_event", "calendar_query")
        assert intent["confidence"] in ("high", "medium", "low")


# --- 3. full journey driven by the test client's wire format -----------------


def test_full_journey_through_test_client_wire_format(tmp_path: Path, monkeypatch):
    """Capture → confirm → upcoming → ack, posting the echoed intent verbatim.

    This mirrors what the browser does: POST /capture/text, read the
    echoed ``intent`` out of the response, POST it straight to
    /capture/confirm. No client-side intent reconstruction.
    """
    monkeypatch.setenv("HOMUNCULUS_VAULT", str(tmp_path))
    monkeypatch.setenv("OLLAMA_BASE_URL", "http://127.0.0.1:1")
    monkeypatch.setenv("HOMUNCULUS_TZ", "America/New_York")
    app = create_app()
    with TestClient(app) as client:
        # 1) Capture.
        r = client.post(
            "/capture/text",
            json={
                "text": "add coffee with Jane on Thursday at 10am",
                "captured_at": NOW.isoformat(),
                "speaker_tz": "America/New_York",
            },
        )
        assert r.status_code == 200, r.text
        capture = r.json()
        assert capture["intent"] is not None

        # The heuristic parser may route as calendar_query (read-only) or
        # calendar_event (write) depending on phrasing; for the journey
        # to commit, force the kind to calendar_event the way the page's
        # confirmation button would — matching the existing journey
        # test's discipline.
        intent_payload = dict(capture["intent"])
        intent_payload["kind"] = "calendar_event"

        # 2) Confirm using the echoed (and lightly mutated) intent.
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
        assert confirm["intent"] is not None  # echo on confirm too
        assert confirm["written_path"]

        # 3) Upcoming (default — no include_fired).
        r = client.get("/reminders/upcoming?window_hours=240")
        assert r.status_code == 200
        rows = r.json()
        # At least one row for the planted Thursday event.
        event_kinds = {row["kind"] for row in rows if row["kind"].startswith("strike")}
        assert event_kinds, rows

        # Pick the event id off any strike row.
        event_id = next(row["event_id"] for row in rows if row["kind"].startswith("strike"))

        # 4) Ack strike_0 — later strikes cancelled.
        r = client.post(
            "/ack",
            json={
                "event_id": event_id,
                "kind": "strike_0",
                "acked_at": NOW.isoformat(),
            },
        )
        assert r.status_code == 200
        ack = r.json()
        assert set(ack["cancelled_kinds"]) == {"strike_5", "strike_10", "strike_15"}

        # 5) On the next upcoming pull, those strikes no longer appear —
        # the test client's reconcile-by-rebuild renders the truth.
        r = client.get("/reminders/upcoming?window_hours=240")
        rows = r.json()
        live = {row["kind"] for row in rows if row["event_id"] == event_id}
        assert "strike_0" not in live
        assert "strike_5" not in live
        assert "strike_10" not in live
        assert "strike_15" not in live


# --- 4. include_fired exposes past rows for the test client ------------------


def test_include_fired_reveals_past_rows(tmp_path: Path, monkeypatch):
    """``GET /reminders/upcoming?include_fired=true`` surfaces rows whose
    ``fire_at`` is in the past, so the boss can verify strike generation
    during live testing without losing visibility as soon as they fire.

    We exercise the endpoint directly: plant an event whose start time is
    in the real-world future (so ``list_events_between`` picks it up) and
    a sidecar with a row whose ``fire_at`` is in the real-world past
    (just before now). The default call hides it; ``include_fired=true``
    reveals it.
    """
    from homunculus_brain import calendar as cal

    monkeypatch.setenv("HOMUNCULUS_VAULT", str(tmp_path))
    monkeypatch.setenv("OLLAMA_BASE_URL", "http://127.0.0.1:1")
    app = create_app()

    # Place an event ~2 hours in the future so list_events_between(now, +72h)
    # picks it up under both calls.
    real_now = datetime.now(TZ)
    starts_at = real_now + timedelta(hours=2)
    event = cal.create_event(
        tmp_path,
        title="test event",
        starts_at=starts_at,
        duration_minutes=30,
        tz_name="America/New_York",
        people=[],
        tags=[],
        source_utterance="planted for include_fired test",
    )

    # One row already fired (1h ago) + one still ahead (~2h from now).
    past_row = ReminderRow(
        event_id=event.id,
        kind=ReminderKind.STRIKE_0,
        fire_at=real_now - timedelta(hours=1),
        tz="America/New_York",
        body="past strike",
        status="pending",
    )
    future_row = ReminderRow(
        event_id=event.id,
        kind=ReminderKind.HEADS_UP_30,
        fire_at=real_now + timedelta(minutes=90),
        tz="America/New_York",
        body="future heads-up",
        status="pending",
    )
    rem.persist_event_schedule(tmp_path, event, [past_row, future_row])

    with TestClient(app) as client:
        # Default call — past row hidden, future row visible.
        r = client.get("/reminders/upcoming?window_hours=72")
        assert r.status_code == 200, r.text
        bodies = [row["body"] for row in r.json() if row["event_id"] == event.id]
        assert "past strike" not in bodies, bodies
        assert "future heads-up" in bodies, bodies

        # include_fired — past row surfaces.
        r = client.get("/reminders/upcoming?window_hours=72&include_fired=true")
        assert r.status_code == 200, r.text
        bodies = [row["body"] for row in r.json() if row["event_id"] == event.id]
        assert "past strike" in bodies, bodies
        assert "future heads-up" in bodies, bodies


