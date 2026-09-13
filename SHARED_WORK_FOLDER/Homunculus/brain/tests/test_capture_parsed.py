"""POST /capture/parsed — the Sprite → Herman ingest surface (v1.3).

Positive-path tests for all four verbs, negative-path tests for schema
violations, low confidence, and idempotency, and integration tests for
the morning-summary "Standing warnings" section.

Rules of the road honored here:
* Every test uses ``tmp_path`` for the vault AND for the sprite warnings
  file — no test touches ``~/sprite/warnings.md`` for real. (The autouse
  fixture in ``conftest.py`` defaults the warnings path away from ``~/``
  even without an override, but these tests set both explicitly so the
  assertions can inspect the resulting file.)
* No live LLM — the endpoint doesn't call one; Sprite parses upstream.
"""

from __future__ import annotations

import hashlib
import json
from datetime import datetime, timedelta
from pathlib import Path
from zoneinfo import ZoneInfo

import pytest
from fastapi.testclient import TestClient

from homunculus_brain import calendar as cal
from homunculus_brain import capture_parsed
from homunculus_brain import reminders as rem
from homunculus_brain.schemas import (
    CaptureCriticality,
    CaptureVerb,
    ParsedCaptureRequest,
)
from homunculus_brain.server import create_app


TZ = ZoneInfo("America/New_York")
NOW = datetime(2026, 9, 15, 9, 0, tzinfo=TZ)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _client_with_vault(tmp_path: Path, monkeypatch) -> TestClient:
    warnings_path = tmp_path / "sprite" / "warnings.md"
    monkeypatch.setenv("HOMUNCULUS_VAULT", str(tmp_path))
    monkeypatch.setenv("HOMUNCULUS_TZ", "America/New_York")
    monkeypatch.setenv("OLLAMA_BASE_URL", "http://127.0.0.1:1")
    monkeypatch.setenv("SPRITE_WARNINGS_PATH", str(warnings_path))
    monkeypatch.setenv("HOMUNCULUS_MIN_CONFIDENCE", "0.6")
    app = create_app()
    return TestClient(app)


def _base_payload(**overrides) -> dict:
    payload = {
        "verb": "schedule",
        "subject": "coffee with Jane",
        "when": (NOW + timedelta(days=1, hours=1)).isoformat(),
        "criticality": "normal",
        "confidence": 0.9,
        "raw_transcript": "coffee with Jane tomorrow at 10am",
        "audio_path": "/Users/thomas/sprite/inbox/2026-09-15T09-00-00.m4a",
        "captured_at": NOW.isoformat(),
    }
    payload.update(overrides)
    return payload


# ---------------------------------------------------------------------------
# Positive path — one test per verb
# ---------------------------------------------------------------------------


def test_verb_schedule_creates_calendar_event_and_strike_chain(tmp_path, monkeypatch):
    client = _client_with_vault(tmp_path, monkeypatch)
    when = (NOW + timedelta(days=1, hours=1))
    r = client.post("/capture/parsed", json=_base_payload(when=when.isoformat()))
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["stored"] is True
    assert body["verb"] == "schedule"
    assert body["record_id"]
    assert body["event_id"]

    events = cal.list_events(tmp_path)
    assert len(events) == 1
    assert events[0].title == "coffee with Jane"

    # Strike chain persisted.
    sidecar_dir = tmp_path / "_reminders"
    files = list(sidecar_dir.glob("*.json"))
    assert len(files) == 1
    schedule = json.loads(files[0].read_text())
    kinds = {row["kind"] for row in schedule["schedule"]}
    assert {"heads_up_30", "pre_5", "strike_0", "strike_15"} <= kinds


def test_verb_note_writes_timestamped_markdown_with_provenance(tmp_path, monkeypatch):
    client = _client_with_vault(tmp_path, monkeypatch)
    r = client.post(
        "/capture/parsed",
        json=_base_payload(
            verb="note",
            subject="Kelvin Hall lighting insight",
            when=None,
            raw_transcript="Adam Kilmartin from Kelvin Hall said the LED reflection off the terrazzo is the tell.",
        ),
    )
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["stored"] is True
    assert body["verb"] == "note"
    assert body["written_path"]
    assert body["event_id"] is None

    written = tmp_path / body["written_path"]
    assert written.exists()
    contents = written.read_text(encoding="utf-8")
    # Provenance is in the frontmatter.
    assert "audio_path:" in contents
    assert "/Users/thomas/sprite/inbox/2026-09-15T09-00-00.m4a" in contents
    # Full transcript preserved verbatim in the body.
    assert "Adam Kilmartin" in contents
    assert "terrazzo" in contents


def test_verb_handle_creates_reminder_chain(tmp_path, monkeypatch):
    client = _client_with_vault(tmp_path, monkeypatch)
    when = (NOW + timedelta(hours=3)).isoformat()
    r = client.post(
        "/capture/parsed",
        json=_base_payload(
            verb="handle",
            subject="call the plumber back",
            when=when,
            criticality="normal",
        ),
    )
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["stored"] is True
    assert body["event_id"]

    # Verify the strike chain exists.
    rows = rem.read_event_rows(tmp_path, body["event_id"])
    kinds = {r.kind.value for r in rows}
    assert "strike_0" in kinds
    assert "strike_15" in kinds


def test_verb_handle_critical_bumps_chain_earlier(tmp_path, monkeypatch):
    """A critical handle fires its head-of-chain earlier than the given when."""
    client = _client_with_vault(tmp_path, monkeypatch)
    when = (NOW + timedelta(hours=3))
    r = client.post(
        "/capture/parsed",
        json=_base_payload(
            verb="handle",
            subject="drop off passport application",
            when=when.isoformat(),
            criticality="critical",
        ),
    )
    assert r.status_code == 200, r.text
    body = r.json()
    rows = rem.read_event_rows(tmp_path, body["event_id"])
    # Critical shifts the underlying event 30 min earlier so the whole
    # chain fires sooner. STRIKE_0 fire_at should equal `when - 30min`.
    strike_0 = next(r for r in rows if r.kind.value == "strike_0")
    assert strike_0.fire_at == when - timedelta(minutes=30)

    # And the title carries the critical marker so the vault shows it.
    events = cal.list_events(tmp_path)
    assert any("[handle!]" in e.title for e in events)


def test_verb_handle_null_when_defaults_to_next_business_morning_minus_hour(tmp_path, monkeypatch):
    """`when: null` → first alert defaults to 1h before start of next business day."""
    client = _client_with_vault(tmp_path, monkeypatch)
    # Monday 2026-09-14 at 22:00 EDT — next business day is Tuesday 9am.
    monday_night = datetime(2026, 9, 14, 22, 0, tzinfo=TZ)
    r = client.post(
        "/capture/parsed",
        json=_base_payload(
            verb="handle",
            subject="deposit check",
            when=None,
            captured_at=monday_night.isoformat(),
        ),
    )
    assert r.status_code == 200, r.text
    body = r.json()
    rows = rem.read_event_rows(tmp_path, body["event_id"])
    strike_0 = next(r for r in rows if r.kind.value == "strike_0")
    # Expected first alert: Tuesday 2026-09-15 at 8:00 AM local (9am anchor − 1h).
    expected = datetime(2026, 9, 15, 8, 0, tzinfo=TZ)
    assert strike_0.fire_at == expected


def test_verb_avoid_creates_warnings_file_on_first_write(tmp_path, monkeypatch):
    warnings_path = tmp_path / "sprite" / "warnings.md"
    assert not warnings_path.exists()

    client = _client_with_vault(tmp_path, monkeypatch)
    r = client.post(
        "/capture/parsed",
        json=_base_payload(
            verb="avoid",
            subject="Sam's dairy allergy",
            raw_transcript="Sam has a new dairy allergy — no cheese, no butter, no milk in coffee.",
            when=None,
        ),
    )
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["stored"] is True
    assert body["verb"] == "avoid"

    # File got created with the header + a single warning line.
    assert warnings_path.exists()
    text = warnings_path.read_text(encoding="utf-8")
    assert "# Sprite standing warnings" in text
    assert "- 2026-09-15 09:00 · Sam's dairy allergy · Sam has a new dairy allergy" in text


def test_verb_avoid_appends_without_repeating_header(tmp_path, monkeypatch):
    client = _client_with_vault(tmp_path, monkeypatch)
    client.post("/capture/parsed", json=_base_payload(verb="avoid", subject="allergy A"))
    # Second warning — same captured_at differs by subject so no idempotency collision.
    client.post(
        "/capture/parsed",
        json=_base_payload(
            verb="avoid",
            subject="allergy B",
            captured_at=(NOW + timedelta(minutes=1)).isoformat(),
        ),
    )
    warnings_path = tmp_path / "sprite" / "warnings.md"
    text = warnings_path.read_text(encoding="utf-8")
    # Header appears exactly once.
    assert text.count("# Sprite standing warnings") == 1
    # Both warnings landed.
    assert "allergy A" in text
    assert "allergy B" in text


# ---------------------------------------------------------------------------
# Negative path — schema violations return 400
# ---------------------------------------------------------------------------


def test_missing_required_field_returns_400(tmp_path, monkeypatch):
    client = _client_with_vault(tmp_path, monkeypatch)
    bad = _base_payload()
    del bad["subject"]
    r = client.post("/capture/parsed", json=bad)
    assert r.status_code == 400, r.text
    body = r.json()
    assert body["stored"] is False
    assert body["reason"] == "schema_violation"


def test_bad_verb_enum_returns_400(tmp_path, monkeypatch):
    client = _client_with_vault(tmp_path, monkeypatch)
    r = client.post("/capture/parsed", json=_base_payload(verb="obliterate"))
    assert r.status_code == 400, r.text
    body = r.json()
    assert body["stored"] is False
    assert body["reason"] == "schema_violation"


def test_bad_confidence_range_returns_400(tmp_path, monkeypatch):
    """Confidence outside [0.0, 1.0] is a schema violation, not a low-conf reject."""
    client = _client_with_vault(tmp_path, monkeypatch)
    r = client.post("/capture/parsed", json=_base_payload(confidence=1.5))
    assert r.status_code == 400, r.text


# ---------------------------------------------------------------------------
# Negative path — low confidence returns 422
# ---------------------------------------------------------------------------


def test_low_confidence_returns_422_and_writes_nothing(tmp_path, monkeypatch):
    client = _client_with_vault(tmp_path, monkeypatch)
    r = client.post("/capture/parsed", json=_base_payload(confidence=0.3))
    assert r.status_code == 422, r.text
    body = r.json()
    assert body == {"stored": False, "reason": "low_confidence"}

    # Vault untouched: no events, no notes, no warnings file, no idempotency log.
    assert cal.list_events(tmp_path) == []
    assert not (tmp_path / "notes").exists()
    assert not (tmp_path / "sprite" / "warnings.md").exists()
    assert not (tmp_path / "_capture_idempotency.jsonl").exists()


def test_confidence_exactly_at_floor_is_accepted(tmp_path, monkeypatch):
    client = _client_with_vault(tmp_path, monkeypatch)
    r = client.post("/capture/parsed", json=_base_payload(confidence=0.6, verb="note"))
    assert r.status_code == 200, r.text


# ---------------------------------------------------------------------------
# Idempotency — same request twice does NOT double-schedule
# ---------------------------------------------------------------------------


def test_same_request_twice_is_idempotent(tmp_path, monkeypatch):
    """POSTing the identical payload twice returns the same record_id and does
    not create two calendar events / two sidecars."""
    client = _client_with_vault(tmp_path, monkeypatch)
    payload = _base_payload()
    first = client.post("/capture/parsed", json=payload).json()
    second = client.post("/capture/parsed", json=payload).json()

    assert first["record_id"] == second["record_id"]
    assert first["event_id"] == second["event_id"]

    events = cal.list_events(tmp_path)
    assert len(events) == 1
    sidecar_files = list((tmp_path / "_reminders").glob("*.json"))
    assert len(sidecar_files) == 1


def test_idempotency_key_stable_across_transcript_variation(tmp_path, monkeypatch):
    """Two identical intents that differ only in raw_transcript or audio_path
    (e.g. re-parsed from a re-transcribed .m4a) collapse to the same record."""
    client = _client_with_vault(tmp_path, monkeypatch)
    p1 = _base_payload(raw_transcript="coffee with Jane tomorrow at 10am")
    p2 = _base_payload(
        raw_transcript="coffee with Jane, tomorrow, ten in the morning",
        audio_path="/Users/thomas/sprite/inbox/rework.m4a",
    )
    first = client.post("/capture/parsed", json=p1).json()
    second = client.post("/capture/parsed", json=p2).json()
    assert first["record_id"] == second["record_id"]
    assert len(cal.list_events(tmp_path)) == 1


def test_different_captured_at_produces_different_records(tmp_path, monkeypatch):
    """Two takes with the same subject/when but different captured_at ARE
    different records — the user recorded two memos."""
    client = _client_with_vault(tmp_path, monkeypatch)
    p1 = _base_payload()
    p2 = _base_payload(captured_at=(NOW + timedelta(hours=1)).isoformat())
    first = client.post("/capture/parsed", json=p1).json()
    second = client.post("/capture/parsed", json=p2).json()
    assert first["record_id"] != second["record_id"]


# ---------------------------------------------------------------------------
# Provenance — audio_path is preserved
# ---------------------------------------------------------------------------


def test_audio_path_is_logged_to_activity(tmp_path, monkeypatch):
    client = _client_with_vault(tmp_path, monkeypatch)
    audio = "/Users/thomas/sprite/inbox/2026-09-15T09-42-00.m4a"
    r = client.post("/capture/parsed", json=_base_payload(audio_path=audio, verb="note"))
    assert r.status_code == 200
    activity_file = tmp_path / "_activity.jsonl"
    assert activity_file.exists()
    entries = [json.loads(ln) for ln in activity_file.read_text().splitlines() if ln.strip()]
    capture_entries = [e for e in entries if e["kind"] == "capture_parsed"]
    assert capture_entries
    assert capture_entries[-1]["details"]["audio_path"] == audio


# ---------------------------------------------------------------------------
# Morning summary integration — Standing warnings section
# ---------------------------------------------------------------------------


def test_morning_summary_includes_standing_warnings_after_avoid(tmp_path, monkeypatch):
    """After Sprite pushes an `avoid`, /reminders/upcoming's summary rows
    surface the warning under a 'Standing warnings' section."""
    client = _client_with_vault(tmp_path, monkeypatch)
    r = client.post(
        "/capture/parsed",
        json=_base_payload(
            verb="avoid",
            subject="Sam's dairy allergy",
            raw_transcript="no cheese, no butter, no milk in coffee",
        ),
    )
    assert r.status_code == 200

    r = client.get("/reminders/upcoming?window_hours=72")
    assert r.status_code == 200, r.text
    rows = r.json()
    summary_rows = [row for row in rows if row["kind"] == "morning_summary"]
    assert summary_rows, "expected at least one morning_summary row"
    for row in summary_rows:
        assert "Standing warnings:" in row["body"], row["body"]
        assert "Sam's dairy allergy" in row["body"]


def test_morning_summary_omits_warnings_section_when_file_missing(tmp_path, monkeypatch):
    """No warnings file → no 'Standing warnings' section in the body."""
    warnings_path = tmp_path / "sprite" / "warnings.md"
    assert not warnings_path.exists()

    client = _client_with_vault(tmp_path, monkeypatch)
    r = client.get("/reminders/upcoming?window_hours=72")
    assert r.status_code == 200
    rows = r.json()
    summary_rows = [row for row in rows if row["kind"] == "morning_summary"]
    assert summary_rows
    for row in summary_rows:
        assert "Standing warnings" not in row["body"]


def test_morning_summary_shows_at_most_20_most_recent_warnings(tmp_path, monkeypatch):
    """`read_recent_warnings` caps at 20 and orders most-recent first."""
    client = _client_with_vault(tmp_path, monkeypatch)
    for i in range(25):
        client.post(
            "/capture/parsed",
            json=_base_payload(
                verb="avoid",
                subject=f"warning number {i:02d}",
                captured_at=(NOW + timedelta(minutes=i)).isoformat(),
            ),
        )

    r = client.get("/reminders/upcoming?window_hours=72")
    rows = r.json()
    summary_rows = [row for row in rows if row["kind"] == "morning_summary"]
    assert summary_rows
    body = summary_rows[0]["body"]
    # 20 warning lines expected.
    warning_lines = [ln for ln in body.split("\n") if ln.startswith("- ")]
    assert len(warning_lines) == 20
    # Most-recent first: the latest-indexed warning appears at the top.
    assert "warning number 24" in warning_lines[0]
    assert "warning number 05" in warning_lines[-1]
    # Older ones are not in the section (only newest 20 kept).
    assert "warning number 00" not in body


# ---------------------------------------------------------------------------
# Unit-level tests for the compute_record_id helper
# ---------------------------------------------------------------------------


def test_compute_record_id_is_deterministic():
    req_kwargs = dict(
        verb=CaptureVerb.SCHEDULE,
        subject="coffee with Jane",
        when=datetime(2026, 9, 16, 10, 0, tzinfo=TZ),
        criticality=CaptureCriticality.NORMAL,
        confidence=0.9,
        raw_transcript="…",
        audio_path="/tmp/x.m4a",
        captured_at=datetime(2026, 9, 15, 9, 0, tzinfo=TZ),
    )
    id1 = capture_parsed.compute_record_id(ParsedCaptureRequest(**req_kwargs))
    id2 = capture_parsed.compute_record_id(ParsedCaptureRequest(**req_kwargs))
    assert id1 == id2
    # 32 hex chars (truncated sha256).
    assert len(id1) == 32
    int(id1, 16)  # parses as hex


def test_compute_record_id_ignores_transcript_and_audio():
    a = ParsedCaptureRequest(
        verb=CaptureVerb.NOTE,
        subject="X",
        when=None,
        criticality=CaptureCriticality.NORMAL,
        confidence=0.9,
        raw_transcript="one",
        audio_path="/a.m4a",
        captured_at=datetime(2026, 9, 15, 9, 0, tzinfo=TZ),
    )
    b = a.model_copy(update={"raw_transcript": "TWO", "audio_path": "/b.m4a"})
    assert capture_parsed.compute_record_id(a) == capture_parsed.compute_record_id(b)


def test_compute_record_id_subject_is_case_insensitive_and_trimmed():
    a = ParsedCaptureRequest(
        verb=CaptureVerb.AVOID,
        subject="  Sam's Dairy Allergy  ",
        when=None,
        criticality=CaptureCriticality.NORMAL,
        confidence=0.9,
        raw_transcript="…",
        audio_path="/a.m4a",
        captured_at=datetime(2026, 9, 15, 9, 0, tzinfo=TZ),
    )
    b = a.model_copy(update={"subject": "sam's dairy allergy"})
    assert capture_parsed.compute_record_id(a) == capture_parsed.compute_record_id(b)
