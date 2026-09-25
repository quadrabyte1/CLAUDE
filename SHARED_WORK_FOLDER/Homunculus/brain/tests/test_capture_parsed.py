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
    ParsedCaptureResponse,
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

    # v1.6: title no longer carries [handle!] prefix — criticality is in frontmatter.
    # The vault/reminders/ markdown file should have criticality: critical.
    reminders_dir = tmp_path / "reminders"
    md_files = list(reminders_dir.rglob("*.md"))
    assert md_files, "Expected reminder markdown file"
    content = md_files[0].read_text()
    assert "criticality: critical" in content, (
        f"Expected 'criticality: critical' frontmatter tag. File:\n{content[:300]}"
    )


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


# ---------------------------------------------------------------------------
# M3 bug fix — day_hint / time_hint on /capture/parsed
# ---------------------------------------------------------------------------
# Tests are written RED first (failing against the pre-fix code), then the
# implementation below turns them GREEN. The red→green transition is shown in
# the handoff report.
#
# New behaviors under test:
#   1. schedule + day_hint/time_hint (no when) → real event at resolved time
#   2. handle  + day_hint/time_hint (no when) → real reminder at resolved time
#   3. ambiguous time (bare hour, no AM/PM) → stored=False + clarifying_question
#   4. precedence: explicit `when` wins over hints
#   5. wire-shape: raw string in `when` field → 400 (schema rejects it)
#   6. regression: existing when=<datetime> tests still pass unchanged
# ---------------------------------------------------------------------------


def _hint_payload(**overrides) -> dict:
    """Base payload with hints but no `when`."""
    payload = {
        "verb": "schedule",
        "subject": "dentist appointment",
        "when": None,
        "day_hint": "thursday",
        "time_hint": "9am",
        "criticality": "normal",
        "confidence": 0.88,
        "raw_transcript": "dentist appointment thursday at 9am",
        "audio_path": "/Users/thomas/sprite/inbox/test.m4a",
        "captured_at": NOW.isoformat(),
    }
    payload.update(overrides)
    return payload


# --- 1. schedule verb with hints -----------------------------------------


def test_schedule_with_day_and_time_hints_creates_event_at_correct_time(tmp_path, monkeypatch):
    """POST /capture/parsed with day_hint=thursday, time_hint=9am, when=None
    → stored=True, event at next Thursday 09:00 local, NOT a 400/422."""
    client = _client_with_vault(tmp_path, monkeypatch)
    r = client.post("/capture/parsed", json=_hint_payload(verb="schedule"))
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["stored"] is True
    assert body["event_id"] is not None

    events = cal.list_events(tmp_path)
    assert len(events) == 1
    event = events[0]
    # NOW is 2026-09-15 (Tuesday). Next Thursday = 2026-09-17.
    assert event.starts_at.date().isoformat() == "2026-09-17"
    assert event.starts_at.hour == 9
    assert event.starts_at.minute == 0


# --- 2. handle verb with hints -------------------------------------------


def test_handle_with_day_and_time_hints_creates_reminder_at_correct_time(tmp_path, monkeypatch):
    """POST /capture/parsed with verb=handle, day_hint=thursday, time_hint=9am
    → stored=True, reminder strike chain anchored to Thursday 09:00."""
    client = _client_with_vault(tmp_path, monkeypatch)
    r = client.post(
        "/capture/parsed",
        json=_hint_payload(
            verb="handle",
            subject="call back the plumber",
        ),
    )
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["stored"] is True
    assert body["event_id"] is not None

    rows = rem.read_event_rows(tmp_path, body["event_id"])
    strike_0 = next(row for row in rows if row.kind.value == "strike_0")
    # Thursday 2026-09-17 at 09:00 local.
    assert strike_0.fire_at.date().isoformat() == "2026-09-17"
    assert strike_0.fire_at.hour == 9


# --- 3. ambiguous time hint → needs clarification ------------------------


def test_ambiguous_time_hint_returns_stored_false_with_clarifying_question(tmp_path, monkeypatch):
    """day_hint=thursday, time_hint=nine (bare hour, no AM/PM)
    → stored=False, clarifying_question mentions AM/PM, ambiguous_fields=['time']."""
    client = _client_with_vault(tmp_path, monkeypatch)
    r = client.post(
        "/capture/parsed",
        json=_hint_payload(time_hint="nine"),
    )
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["stored"] is False
    assert "clarifying_question" in body
    assert body["clarifying_question"] is not None
    # The clarifying question must mention the ambiguity.
    assert "AM" in body["clarifying_question"] or "am" in body["clarifying_question"].lower()
    assert "ambiguous_fields" in body
    assert "time" in body["ambiguous_fields"]

    # Nothing should be written to the vault.
    assert cal.list_events(tmp_path) == []


def test_ambiguous_day_hint_returns_stored_false_with_clarifying_question(tmp_path, monkeypatch):
    """day_hint with an unparseable value → stored=False, ambiguous_fields includes 'day'."""
    client = _client_with_vault(tmp_path, monkeypatch)
    r = client.post(
        "/capture/parsed",
        json=_hint_payload(day_hint="xyzzy day"),
    )
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["stored"] is False
    assert "ambiguous_fields" in body
    assert "day" in body["ambiguous_fields"]
    assert cal.list_events(tmp_path) == []


# --- 4. precedence: explicit when wins over hints -------------------------


def test_explicit_when_takes_precedence_over_hints(tmp_path, monkeypatch):
    """when=<real datetime>, day_hint=tomorrow → the event is at `when`, not tomorrow."""
    client = _client_with_vault(tmp_path, monkeypatch)
    explicit_when = datetime(2026, 9, 20, 14, 30, tzinfo=TZ)  # Sunday at 14:30
    r = client.post(
        "/capture/parsed",
        json=_hint_payload(
            when=explicit_when.isoformat(),
            day_hint="tomorrow",
            time_hint="9am",
        ),
    )
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["stored"] is True

    events = cal.list_events(tmp_path)
    assert len(events) == 1
    # Must be at the explicit when (2026-09-20), NOT tomorrow (2026-09-16).
    assert events[0].starts_at.date().isoformat() == "2026-09-20"
    assert events[0].starts_at.hour == 14
    assert events[0].starts_at.minute == 30


# --- 5. wire-shape: raw string in `when` field → 400 --------------------


def test_raw_string_in_when_field_returns_400(tmp_path, monkeypatch):
    """Sending 'thursday' as the `when` value (not ISO-8601) must return 400
    (Pydantic rejects it before any handler runs). This test documents the
    wire contract: `when` is Optional[datetime], not Optional[str]."""
    client = _client_with_vault(tmp_path, monkeypatch)
    bad_payload = _base_payload()
    bad_payload["when"] = "thursday"  # raw string — not ISO-8601
    r = client.post("/capture/parsed", json=bad_payload)
    assert r.status_code == 400, r.text
    body = r.json()
    assert body["stored"] is False
    assert body["reason"] == "schema_violation"


# --- 6. regression: existing when=<datetime> path still works -------------


def test_regression_explicit_when_schedule_still_works(tmp_path, monkeypatch):
    """Existing callers that send a resolved ISO-8601 when are unaffected."""
    client = _client_with_vault(tmp_path, monkeypatch)
    explicit_when = NOW + timedelta(days=1, hours=1)
    r = client.post(
        "/capture/parsed",
        json=_base_payload(
            verb="schedule",
            when=explicit_when.isoformat(),
            # No hints sent — backward-compatible call site.
        ),
    )
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["stored"] is True
    assert body["event_id"] is not None

    events = cal.list_events(tmp_path)
    assert len(events) == 1
    assert events[0].starts_at.date() == explicit_when.date()


def test_regression_explicit_when_handle_still_works(tmp_path, monkeypatch):
    """Existing handle callers with explicit when are unaffected."""
    client = _client_with_vault(tmp_path, monkeypatch)
    explicit_when = NOW + timedelta(hours=4)
    r = client.post(
        "/capture/parsed",
        json=_base_payload(
            verb="handle",
            subject="call accountant",
            when=explicit_when.isoformat(),
        ),
    )
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["stored"] is True
    assert body["event_id"] is not None


# --- wire-shape cross-repo round-trip ------------------------------------


def test_hint_fields_round_trip_through_pydantic_model():
    """ParsedCaptureRequest with day_hint+time_hint serialises and re-parses
    correctly. This is the schema drift-detection guard for the Sprite side."""
    req = ParsedCaptureRequest(
        verb=CaptureVerb.SCHEDULE,
        subject="dentist appointment",
        when=None,
        day_hint="thursday",
        time_hint="9am",
        criticality=CaptureCriticality.NORMAL,
        confidence=0.88,
        raw_transcript="dentist thursday at 9am",
        audio_path="/tmp/test.m4a",
        captured_at=datetime(2026, 9, 15, 9, 0, tzinfo=TZ),
    )
    # Round-trip through JSON (as Sprite's build_request does over the wire).
    json_str = req.model_dump_json()
    req2 = ParsedCaptureRequest.model_validate_json(json_str)
    assert req2.day_hint == "thursday"
    assert req2.time_hint == "9am"
    assert req2.when is None


# ---------------------------------------------------------------------------
# v1.7 end-to-end regression — Thomas's live incident (2026-09-21)
#
# POST /capture/parsed with day_hint="September 20th", time_hint="10 AM",
# captured_at=2026-09-21 should:
#   - return stored=True
#   - resolve to 2027-09-20 10:00 EDT (roll-forward because Sept 20 < Sept 21)
#   - written_path must point at calendar/2027-09/...
# ---------------------------------------------------------------------------

NOW_INCIDENT = datetime(2026, 9, 21, 11, 2, tzinfo=TZ)  # Thomas's memo time


def _incident_payload(**overrides) -> dict:
    payload = {
        "verb": "schedule",
        "subject": "appointment",
        "when": None,
        "day_hint": "September 20th",
        "time_hint": "10 AM",
        "criticality": "normal",
        "confidence": 0.76,
        "raw_transcript": "That appointment at September 20th at 10am, I'm going to tea...",
        "audio_path": "/Users/thomas/sprite/inbox/2026-09-21.m4a",
        "captured_at": NOW_INCIDENT.isoformat(),
    }
    payload.update(overrides)
    return payload


def _client_incident(tmp_path: Path, monkeypatch) -> TestClient:
    monkeypatch.setenv("HOMUNCULUS_VAULT", str(tmp_path))
    monkeypatch.setenv("HOMUNCULUS_TZ", "America/New_York")
    monkeypatch.setenv("OLLAMA_BASE_URL", "http://127.0.0.1:1")
    monkeypatch.setenv("SPRITE_WARNINGS_PATH", str(tmp_path / "sprite" / "warnings.md"))
    monkeypatch.setenv("HOMUNCULUS_MIN_CONFIDENCE", "0.6")
    return TestClient(create_app())


def test_v17_e2e_sept20_hint_rolls_to_2027_and_written_path_correct(tmp_path, monkeypatch):
    """POST /capture/parsed with day_hint='September 20th', time_hint='10 AM',
    captured_at=2026-09-21 → stored=True, event on 2027-09-20, written_path
    under calendar/2027-09/.

    This is the router-level end-to-end test for the live incident that
    motivated v1.7.
    """
    client = _client_incident(tmp_path, monkeypatch)
    r = client.post("/capture/parsed", json=_incident_payload())
    assert r.status_code == 200, r.text
    body = r.json()

    assert body["stored"] is True, f"expected stored=True, got: {body}"
    assert body["event_id"] is not None

    # written_path must point into 2027-09
    written_path = body.get("written_path", "")
    assert "2027-09" in written_path, (
        f"expected written_path under calendar/2027-09/, got: {written_path!r}"
    )

    # The vault event itself must resolve to Sept 20 2027 at 10:00.
    events = cal.list_events(tmp_path)
    assert len(events) == 1
    ev = events[0]
    assert ev.starts_at.year == 2027
    assert ev.starts_at.month == 9
    assert ev.starts_at.day == 20
    assert ev.starts_at.hour == 10
    assert ev.starts_at.minute == 0


# ===========================================================================
# TDD REGRESSION SUITE — v1.8.0 (must fail before fix, pass after fix)
#
# Tests 10-12: end-to-end schedule bare-hour PM inference through Herman's
# /capture/parsed endpoint. The date_resolver now accepts verb= so the
# schedule handler can pass context through. handle/remind keep the old caution.
# ===========================================================================

NOW_V18 = datetime(2026, 9, 21, 13, 36, tzinfo=TZ)  # exact incident time


def _v18_client(tmp_path: Path, monkeypatch) -> TestClient:
    monkeypatch.setenv("HOMUNCULUS_VAULT", str(tmp_path))
    monkeypatch.setenv("HOMUNCULUS_TZ", "America/New_York")
    monkeypatch.setenv("OLLAMA_BASE_URL", "http://127.0.0.1:1")
    monkeypatch.setenv("SPRITE_WARNINGS_PATH", str(tmp_path / "sprite" / "warnings.md"))
    monkeypatch.setenv("HOMUNCULUS_MIN_CONFIDENCE", "0.6")
    return TestClient(create_app())


# --- Test 10: schedule + bare '3' → stored=True, event at 15:00 (3 PM)

def test_v180_e2e_schedule_bare_hour_3_resolves_pm(tmp_path, monkeypatch):
    """POST /capture/parsed with verb=schedule, time_hint='3', day_hint='September 20th',
    captured_at=2026-09-21 → stored=True, event on 2027-09-20 at 15:00 (3 PM, not ambiguous).

    This is the Jake's VCA fix end-to-end: a bare hour 1-5 in a schedule request
    must pass through Herman's date_resolver as PM without raising a clarifying question.
    """
    client = _v18_client(tmp_path, monkeypatch)
    payload = {
        "verb": "schedule",
        "subject": "Jake's VCA check",
        "when": None,
        "day_hint": "September 20th",
        "time_hint": "3",
        "criticality": "normal",
        "confidence": 0.87,
        "raw_transcript": "Let's set Jake's VCA annual check-up on September 20th at three.",
        "audio_path": "/Users/thomas/sprite/audio/2026-09-21.m4a",
        "captured_at": NOW_V18.isoformat(),
    }
    r = client.post("/capture/parsed", json=payload)
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["stored"] is True, (
        f"verb=schedule + bare hour 3 must resolve as PM and store. Got: {body}"
    )
    assert body["event_id"] is not None

    events = cal.list_events(tmp_path)
    assert len(events) == 1
    ev = events[0]
    assert ev.starts_at.year == 2027, f"roll-forward expected 2027, got {ev.starts_at.year}"
    assert ev.starts_at.month == 9
    assert ev.starts_at.day == 20
    assert ev.starts_at.hour == 15, (
        f"Bare hour 3 + verb=schedule must resolve to 15:00 (3 PM). "
        f"Got hour={ev.starts_at.hour}"
    )
    assert ev.starts_at.minute == 0


# --- Test 11: handle + bare '3' → stored=False, clarifying question (old behavior)

def test_v180_e2e_handle_bare_hour_3_still_asks(tmp_path, monkeypatch):
    """POST /capture/parsed with verb=handle, time_hint='3'
    → stored=False, clarifying_question about AM/PM.

    The PM-inference rule is scoped to verb=schedule only. Reminders can
    legitimately be at 3 AM (medication, alarms). Handle must still ask.
    """
    client = _v18_client(tmp_path, monkeypatch)
    payload = {
        "verb": "handle",
        "subject": "call the pharmacy",
        "when": None,
        "day_hint": "September 22nd",
        "time_hint": "3",
        "criticality": "normal",
        "confidence": 0.83,
        "raw_transcript": "call the pharmacy at 3",
        "audio_path": "/Users/thomas/sprite/audio/2026-09-21b.m4a",
        "captured_at": NOW_V18.isoformat(),
    }
    r = client.post("/capture/parsed", json=payload)
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["stored"] is False, (
        f"verb=handle + bare hour must still ask (stored=False). Got: {body}"
    )
    assert body.get("clarifying_question"), (
        f"Expected a clarifying_question for handle + bare hour. Got: {body}"
    )
    assert "time" in body.get("ambiguous_fields", []), (
        f"Expected 'time' in ambiguous_fields. Got: {body.get('ambiguous_fields')}"
    )
    # Nothing stored in vault.
    assert cal.list_events(tmp_path) == []


# ===========================================================================
# TDD REGRESSION SUITE — v1.9.0 (must FAIL before fix, pass after fix)
#
# Bug: "Pick up the dry cleaning on Friday" (verb=handle, day_hint="Friday",
# time_hint=null) was rejected with:
#   stored=False, clarifying_question="Did you mean AM or PM?"
# which is nonsense — there is no time to be ambiguous about.
#
# Root cause: _resolve_from_hints() treats time_hint=None the same as
# time_hint=bare-hour (both set ambiguous=['time']). Fix: when
# verb in (handle, remind) AND time_hint is None, apply the default
# handle-hour (morning_anchor_hour - 1) and do NOT ask.
#
# Tests 1-8 defined here; the green→red transition is shown in the handoff.
# ===========================================================================

NOW_V19 = datetime(2026, 9, 22, 9, 5, tzinfo=TZ)  # Monday morning after the incident


def _v19_client(tmp_path: Path, monkeypatch) -> TestClient:
    monkeypatch.setenv("HOMUNCULUS_VAULT", str(tmp_path))
    monkeypatch.setenv("HOMUNCULUS_TZ", "America/New_York")
    monkeypatch.setenv("OLLAMA_BASE_URL", "http://127.0.0.1:1")
    monkeypatch.setenv("SPRITE_WARNINGS_PATH", str(tmp_path / "sprite" / "warnings.md"))
    monkeypatch.setenv("HOMUNCULUS_MIN_CONFIDENCE", "0.6")
    return TestClient(create_app())


# --- Test 1: Live regression — handle + day_hint + null time_hint → 8 AM default


def test_v190_handle_day_hint_null_time_stores_at_8am(tmp_path, monkeypatch):
    """POST /capture/parsed with verb=handle, day_hint='Friday', time_hint=null,
    captured_at=Monday 9:05 AM → stored=True, strike_0 fires Friday at 8:00 AM local.

    This is the dry-cleaning incident. Herman must NOT ask "AM or PM?" when
    there was no time in the utterance at all.
    """
    client = _v19_client(tmp_path, monkeypatch)
    payload = {
        "verb": "handle",
        "subject": "pick up dry cleaning",
        "when": None,
        "day_hint": "Friday",
        "time_hint": None,
        "criticality": "normal",
        "confidence": 0.85,
        "raw_transcript": "Pick up the dry cleaning on Friday.",
        "audio_path": "/Users/thomas/sprite/audio/2026-09-22.m4a",
        "captured_at": NOW_V19.isoformat(),
    }
    r = client.post("/capture/parsed", json=payload)
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["stored"] is True, (
        f"verb=handle + day_hint only must store without asking. Got: {body}"
    )
    assert body["event_id"] is not None

    # Strike chain must anchor to Friday 8:00 AM (morning_anchor_hour=9, default − 1 = 8).
    rows = rem.read_event_rows(tmp_path, body["event_id"])
    strike_0 = next(r for r in rows if r.kind.value == "strike_0")
    assert strike_0.fire_at.weekday() == 4, (
        f"Expected Friday (weekday=4), got weekday={strike_0.fire_at.weekday()}"
    )
    assert strike_0.fire_at.hour == 8, (
        f"Expected 8 AM default (morning_anchor_hour-1), got hour={strike_0.fire_at.hour}"
    )
    assert strike_0.fire_at.minute == 0
    # Also confirm date is 2026-09-25 (next Friday from Monday 2026-09-22).
    assert strike_0.fire_at.date().isoformat() == "2026-09-25", (
        f"Expected 2026-09-25, got {strike_0.fire_at.date().isoformat()}"
    )


# --- Test 2: remind verb — same rule


def test_v190_remind_day_hint_null_time_stores_at_8am(tmp_path, monkeypatch):
    """verb=remind + day_hint='Friday' + time_hint=null → stored=True, 8 AM anchor.

    remind is a synonym for handle; both must get the null-time default.
    """
    client = _v19_client(tmp_path, monkeypatch)
    payload = {
        "verb": "remind",
        "subject": "call dentist office",
        "when": None,
        "day_hint": "Friday",
        "time_hint": None,
        "criticality": "normal",
        "confidence": 0.82,
        "raw_transcript": "Remind me to call the dentist office on Friday.",
        "audio_path": "/Users/thomas/sprite/audio/2026-09-22b.m4a",
        "captured_at": NOW_V19.isoformat(),
    }
    r = client.post("/capture/parsed", json=payload)
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["stored"] is True, (
        f"verb=remind + day_hint only must store without asking. Got: {body}"
    )
    rows = rem.read_event_rows(tmp_path, body["event_id"])
    strike_0 = next(r for r in rows if r.kind.value == "strike_0")
    assert strike_0.fire_at.weekday() == 4
    assert strike_0.fire_at.hour == 8
    assert strike_0.fire_at.date().isoformat() == "2026-09-25"


# --- Test 3: schedule verb unchanged — null time still asks


def test_v190_schedule_day_hint_null_time_still_asks(tmp_path, monkeypatch):
    """POST /capture/parsed with verb=schedule, day_hint='Friday', time_hint=null
    → stored=False with a clarifying question.

    Untimed calendar events remain ambiguous (all-day? 9 AM? TBD?).
    The null-time default is scoped to handle/remind only.
    """
    client = _v19_client(tmp_path, monkeypatch)
    payload = {
        "verb": "schedule",
        "subject": "board meeting",
        "when": None,
        "day_hint": "Friday",
        "time_hint": None,
        "criticality": "normal",
        "confidence": 0.88,
        "raw_transcript": "Schedule board meeting on Friday.",
        "audio_path": "/Users/thomas/sprite/audio/2026-09-22c.m4a",
        "captured_at": NOW_V19.isoformat(),
    }
    r = client.post("/capture/parsed", json=payload)
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["stored"] is False, (
        f"verb=schedule + null time must still ask for a time. Got: {body}"
    )
    assert body.get("clarifying_question") is not None
    # Nothing stored in vault.
    assert cal.list_events(tmp_path) == []


# --- Test 4: strike chain intact for the dry-cleaning case


def test_v190_strike_chain_complete_for_null_time_handle(tmp_path, monkeypatch):
    """Verify all 6 strike rows exist for a handle + day_hint + null time capture.

    The chain should be: heads_up_30, pre_5, strike_0, strike_5, strike_10,
    strike_15 — all hanging off the 8 AM anchor on Friday.
    """
    client = _v19_client(tmp_path, monkeypatch)
    payload = {
        "verb": "handle",
        "subject": "return library books",
        "when": None,
        "day_hint": "Friday",
        "time_hint": None,
        "criticality": "normal",
        "confidence": 0.87,
        "raw_transcript": "Return library books on Friday.",
        "audio_path": "/Users/thomas/sprite/audio/2026-09-22d.m4a",
        "captured_at": NOW_V19.isoformat(),
    }
    r = client.post("/capture/parsed", json=payload)
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["stored"] is True

    rows = rem.read_event_rows(tmp_path, body["event_id"])
    kinds = {row.kind.value for row in rows}
    expected_kinds = {"heads_up_30", "pre_5", "strike_0", "strike_5", "strike_10", "strike_15"}
    assert expected_kinds == kinds, (
        f"Expected all 6 strike kinds. Got: {kinds}"
    )

    # All rows must anchor off 8 AM on Friday 2026-09-25.
    anchor = datetime(2026, 9, 25, 8, 0, tzinfo=TZ)
    kind_to_offset = {
        "heads_up_30": -30,
        "pre_5": -5,
        "strike_0": 0,
        "strike_5": 5,
        "strike_10": 10,
        "strike_15": 15,
    }
    for row in rows:
        expected_fire = anchor + timedelta(minutes=kind_to_offset[row.kind.value])
        actual_fire = row.fire_at.astimezone(TZ)
        assert actual_fire == expected_fire, (
            f"Row {row.kind.value}: expected {expected_fire}, got {actual_fire}"
        )


# --- Test 5: configurable morning anchor — anchor=10 → default becomes 9 AM


def test_v190_configurable_morning_anchor_shifts_default_hour(tmp_path, monkeypatch):
    """When HOMUNCULUS_MORNING_ANCHOR=10, the null-time default for handle/remind
    should resolve to 10-1 = 9 AM (morning_anchor_hour - 1).
    """
    monkeypatch.setenv("HOMUNCULUS_VAULT", str(tmp_path))
    monkeypatch.setenv("HOMUNCULUS_TZ", "America/New_York")
    monkeypatch.setenv("OLLAMA_BASE_URL", "http://127.0.0.1:1")
    monkeypatch.setenv("SPRITE_WARNINGS_PATH", str(tmp_path / "sprite" / "warnings.md"))
    monkeypatch.setenv("HOMUNCULUS_MIN_CONFIDENCE", "0.6")
    monkeypatch.setenv("HOMUNCULUS_MORNING_ANCHOR", "10")  # anchor at 10 → default = 9 AM
    client = TestClient(create_app())

    payload = {
        "verb": "handle",
        "subject": "check mail",
        "when": None,
        "day_hint": "Friday",
        "time_hint": None,
        "criticality": "normal",
        "confidence": 0.85,
        "raw_transcript": "Check the mail on Friday.",
        "audio_path": "/Users/thomas/sprite/audio/2026-09-22e.m4a",
        "captured_at": NOW_V19.isoformat(),
    }
    r = client.post("/capture/parsed", json=payload)
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["stored"] is True

    rows = rem.read_event_rows(tmp_path, body["event_id"])
    strike_0 = next(row for row in rows if row.kind.value == "strike_0")
    assert strike_0.fire_at.hour == 9, (
        f"morning_anchor=10 → default hour should be 9. Got: {strike_0.fire_at.hour}"
    )
    assert strike_0.fire_at.date().isoformat() == "2026-09-25"


# --- Test 6: when time_hint IS given, existing logic applies (unchanged)


def test_v190_handle_with_explicit_time_hint_uses_that_time(tmp_path, monkeypatch):
    """verb=handle, day_hint='Friday', time_hint='3 PM' → still resolves to Friday 15:00.

    The null-time default must NOT override a real time_hint.
    """
    client = _v19_client(tmp_path, monkeypatch)
    payload = {
        "verb": "handle",
        "subject": "call the accountant",
        "when": None,
        "day_hint": "Friday",
        "time_hint": "3 PM",
        "criticality": "normal",
        "confidence": 0.88,
        "raw_transcript": "Call the accountant Friday at 3 PM.",
        "audio_path": "/Users/thomas/sprite/audio/2026-09-22f.m4a",
        "captured_at": NOW_V19.isoformat(),
    }
    r = client.post("/capture/parsed", json=payload)
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["stored"] is True

    rows = rem.read_event_rows(tmp_path, body["event_id"])
    strike_0 = next(row for row in rows if row.kind.value == "strike_0")
    assert strike_0.fire_at.hour == 15, (
        f"Expected 15:00 (3 PM), got hour={strike_0.fire_at.hour}"
    )
    assert strike_0.fire_at.date().isoformat() == "2026-09-25"


# --- Test 7: bare-hour ambiguous time_hint still asks (unchanged from v1.8)


def test_v190_handle_bare_hour_time_hint_still_asks(tmp_path, monkeypatch):
    """verb=handle, day_hint='Friday', time_hint='3' (bare hour, no AM/PM)
    → stored=False, clarifying_question, ambiguous_fields=['time'].

    This fix is ONLY about null time_hint. A bare-hour time_hint is genuinely
    ambiguous and must still ask.
    """
    client = _v19_client(tmp_path, monkeypatch)
    payload = {
        "verb": "handle",
        "subject": "pick up prescriptions",
        "when": None,
        "day_hint": "Friday",
        "time_hint": "3",
        "criticality": "normal",
        "confidence": 0.84,
        "raw_transcript": "Pick up prescriptions Friday at 3.",
        "audio_path": "/Users/thomas/sprite/audio/2026-09-22g.m4a",
        "captured_at": NOW_V19.isoformat(),
    }
    r = client.post("/capture/parsed", json=payload)
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["stored"] is False, (
        f"bare-hour time_hint must still ask. Got: {body}"
    )
    assert body.get("clarifying_question") is not None
    assert "time" in body.get("ambiguous_fields", [])
    assert cal.list_events(tmp_path) == []


# --- Test 8: full regression — all 161 existing tests still pass (enforced by
#     the overall pytest run; this test documents the contract explicitly)

def test_v190_regression_null_time_handle_writes_reminder_markdown(tmp_path, monkeypatch):
    """Regression: vault/reminders/<event_id>.md exists and has correct frontmatter
    for a null-time handle capture. Confirms the full write path fires, not just
    the response object.
    """
    client = _v19_client(tmp_path, monkeypatch)
    payload = {
        "verb": "handle",
        "subject": "water the garden",
        "when": None,
        "day_hint": "Friday",
        "time_hint": None,
        "criticality": "normal",
        "confidence": 0.86,
        "raw_transcript": "Water the garden on Friday.",
        "audio_path": "/Users/thomas/sprite/audio/2026-09-22h.m4a",
        "captured_at": NOW_V19.isoformat(),
    }
    r = client.post("/capture/parsed", json=payload)
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["stored"] is True
    assert body["written_path"] is not None

    # The reminder markdown must exist under vault/reminders/.
    written = tmp_path / body["written_path"]
    assert written.exists(), f"Expected reminder markdown at {written}"
    contents = written.read_text(encoding="utf-8")
    assert "starts_at:" in contents
    assert "verb: handle" in contents
    # starts_at must be on 2026-09-25 at 08:00.
    assert "2026-09-25T08:00:00" in contents or "2026-09-25 08:00:00" in contents, (
        f"starts_at should be on Friday 2026-09-25 at 08:00. Frontmatter:\n{contents[:400]}"
    )


# ===========================================================================
# TDD REGRESSION SUITE — v2.3.0 end-to-end (must FAIL before fix, pass after)
#
# Tests 12-13: /capture/parsed with time_hint="9 o'clock a.m." must store
# the event at 09:00.  Belt-and-suspenders: even if Sprite already injected
# the qualifier, Herman's resolver must also be able to handle "o'clock" forms.
# ===========================================================================

NOW_V23_E2E = datetime(2026, 9, 25, 7, 49, tzinfo=TZ)


def _v23_client(tmp_path: Path, monkeypatch) -> TestClient:
    monkeypatch.setenv("HOMUNCULUS_VAULT", str(tmp_path))
    monkeypatch.setenv("HOMUNCULUS_TZ", "America/New_York")
    monkeypatch.setenv("OLLAMA_BASE_URL", "http://127.0.0.1:1")
    monkeypatch.setenv("SPRITE_WARNINGS_PATH", str(tmp_path / "sprite" / "warnings.md"))
    monkeypatch.setenv("HOMUNCULUS_MIN_CONFIDENCE", "0.6")
    return TestClient(create_app())


# --- Test 12: POST with time_hint="9 o'clock a.m." → stored=True, event at 09:00

def test_v230_e2e_oclock_am_stores_at_0900(tmp_path, monkeypatch):
    """POST /capture/parsed with verb=handle, day_hint='today',
    time_hint="9 o'clock a.m.", captured_at=2026-09-25 07:49
    → stored=True, event/reminder at 09:00 today.

    This is the live-incident fix. Before v2.3.0 Herman couldn't parse
    'o\\'clock' and returned stored=False with a clarifying question.
    """
    client = _v23_client(tmp_path, monkeypatch)
    payload = {
        "verb": "handle",
        "subject": "put the barrier up in the car",
        "when": None,
        "day_hint": "today",
        "time_hint": "9 o'clock a.m.",
        "criticality": "normal",
        "confidence": 0.887,
        "raw_transcript": "You put the barrier up in the car at 9 o'clock a.m. today.",
        "audio_path": "/Users/thomas/sprite/audio/2026-09-25.m4a",
        "captured_at": NOW_V23_E2E.isoformat(),
    }
    r = client.post("/capture/parsed", json=payload)
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["stored"] is True, (
        f"time_hint='9 o\\'clock a.m.' must resolve and store. Got: {body}"
    )
    assert body["event_id"] is not None

    # The reminder/event must be at 09:00 today (2026-09-25).
    rows = rem.read_event_rows(tmp_path, body["event_id"])
    strike_0 = next(r for r in rows if r.kind.value == "strike_0")
    local_fire = strike_0.fire_at.astimezone(TZ)
    assert local_fire.hour == 9, (
        f"Event must be at 09:00. Got hour={local_fire.hour}"
    )
    assert local_fire.date().isoformat() == "2026-09-25", (
        f"Event must be today (2026-09-25). Got {local_fire.date().isoformat()}"
    )


# --- Test 13: Regression guard — bare "9 o'clock" (no qualifier) still asks

def test_v230_e2e_oclock_no_qualifier_still_asks(tmp_path, monkeypatch):
    """POST /capture/parsed with time_hint="9 o'clock" (no AM/PM qualifier)
    → stored=False, clarifying_question. The o\\'clock normalization reveals a
    bare '9' which is genuinely ambiguous for verb=handle.
    """
    client = _v23_client(tmp_path, monkeypatch)
    payload = {
        "verb": "handle",
        "subject": "put the barrier up in the car",
        "when": None,
        "day_hint": "today",
        "time_hint": "9 o'clock",
        "criticality": "normal",
        "confidence": 0.887,
        "raw_transcript": "You put the barrier up in the car at 9 o'clock today.",
        "audio_path": "/Users/thomas/sprite/audio/2026-09-25b.m4a",
        "captured_at": NOW_V23_E2E.isoformat(),
    }
    r = client.post("/capture/parsed", json=payload)
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["stored"] is False, (
        f"Bare '9 o\\'clock' (no AM/PM) must remain ambiguous. Got: {body}"
    )
    assert body.get("clarifying_question") is not None, (
        f"Expected a clarifying_question. Got: {body}"
    )
