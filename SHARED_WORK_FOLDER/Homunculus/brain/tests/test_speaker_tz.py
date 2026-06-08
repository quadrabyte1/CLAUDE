"""speaker_tz is honored end-to-end (v1.2 item 1).

The phone reports its zone on every capture. The brain must resolve dates
in that zone and persist `tz` on the event in that zone (not the server
default). An invalid TZ name falls back to the default — never a 500.
"""

from __future__ import annotations

from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

from fastapi.testclient import TestClient

from homunculus_brain.config import Config
from homunculus_brain.intent_router import commit_calendar_event, route
from homunculus_brain.llm import heuristic_parse
from homunculus_brain.schemas import IntentKind
from homunculus_brain.server import create_app, _resolve_tz


EASTERN = ZoneInfo("America/New_York")
PACIFIC = ZoneInfo("America/Los_Angeles")
# Monday June 8 2026, 9:00 AM Pacific. Same instant is noon Eastern.
NOW_PACIFIC = datetime(2026, 6, 8, 9, 0, tzinfo=PACIFIC)


def _config(tmp_path: Path) -> Config:
    return Config(
        vault_path=tmp_path,
        default_tz_name="America/New_York",
        morning_summary_time="07:00",
        morning_anchor_hour=9,
        conflict_fuzz_minutes=30,
        default_event_duration_minutes=30,
        reminder_undo_window_seconds=300,
        ollama_base_url="http://127.0.0.1:1",  # connection refused → heuristic
        ollama_model="qwen2.5:7b",
        server_host="0.0.0.0",
        server_port=8765,
    )


def test_resolve_tz_falls_back_on_invalid():
    assert _resolve_tz(None, "America/New_York") == ZoneInfo("America/New_York")
    assert _resolve_tz("", "America/New_York") == ZoneInfo("America/New_York")
    # Invalid TZ name → default; not an exception.
    assert _resolve_tz("Mars/Olympus_Mons", "America/New_York") == ZoneInfo("America/New_York")


def test_resolve_tz_honors_valid_speaker_tz():
    assert _resolve_tz("America/Los_Angeles", "America/New_York") == PACIFIC


def test_commit_with_pacific_speaker_persists_pacific(tmp_path: Path):
    """Pacific speaker says 'Thursday at 10am' → event lands at 10 AM Pacific.

    Round-trips through commit_calendar_event with tz=PACIFIC and verifies
    the persisted event's starts_at is in Pacific (offset -07:00 on June 11,
    which is during PDT) and the frontmatter records that zone.
    """
    intent = heuristic_parse("add a meeting with Jane on Thursday at 10am")
    intent.kind = IntentKind.CALENDAR_EVENT
    intent.title = "meeting with Jane"

    cfg = _config(tmp_path)
    resp = commit_calendar_event(intent, config=cfg, now=NOW_PACIFIC, tz=PACIFIC)

    assert resp.action == "wrote"
    # Locate the persisted markdown.
    from homunculus_brain import calendar as cal

    events = cal.list_events(tmp_path)
    assert len(events) == 1
    ev = events[0]
    # Thursday June 11 2026 at 10:00 AM in Pacific.
    expected = datetime(2026, 6, 11, 10, 0, tzinfo=PACIFIC)
    assert ev.starts_at == expected
    # The persisted tz string is the speaker's zone, not the server default.
    assert ev.tz == "America/Los_Angeles"


def test_capture_text_endpoint_uses_speaker_tz(tmp_path: Path, monkeypatch):
    """End-to-end via TestClient: POST /capture/text with speaker_tz Pacific.

    Heuristic fallback fires (Ollama unreachable). The response should
    return needs_confirmation for a calendar_event; we then confirm and
    verify the written event is in Pacific.
    """
    monkeypatch.setenv("HOMUNCULUS_VAULT", str(tmp_path))
    monkeypatch.setenv("OLLAMA_BASE_URL", "http://127.0.0.1:1")
    monkeypatch.setenv("HOMUNCULUS_TZ", "America/New_York")

    app = create_app()
    with TestClient(app) as client:
        r = client.post(
            "/capture/text",
            json={
                "text": "add a meeting with Jane on Thursday at 10am",
                "captured_at": NOW_PACIFIC.isoformat(),
                "speaker_tz": "America/Los_Angeles",
            },
        )
        assert r.status_code == 200, r.text
        body = r.json()
        assert body["action"] in ("needs_confirmation", "wrote")


def test_invalid_speaker_tz_does_not_500(tmp_path: Path, monkeypatch):
    monkeypatch.setenv("HOMUNCULUS_VAULT", str(tmp_path))
    monkeypatch.setenv("OLLAMA_BASE_URL", "http://127.0.0.1:1")

    app = create_app()
    with TestClient(app) as client:
        r = client.post(
            "/capture/text",
            json={
                "text": "save that prompt about Claude",
                "speaker_tz": "Not/A_Real_Zone",
            },
        )
        assert r.status_code == 200, r.text
