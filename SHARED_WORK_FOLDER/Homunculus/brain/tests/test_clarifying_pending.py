"""TDD suite — Herman v2.2.0: clarifying-question surfacing.

Tests are written RED first. They document what must be true AFTER the
implementation lands in capture_parsed.py.  Running this file before
the implementation shows failures; after, all pass.

Coverage:
  1. clarify_immediate notification sidecar written to _reminders/clarify.<id>.json
  2. Notification body contains question + transcript excerpt
  3. Notification identifier is clarify.<record_id>
  4. _clarifying_pending.jsonl gets a new row (resolved_at=null)
  5. Daily summary via /reminders/upcoming includes unresolved clarify rows
     when mocked "now" crosses morning_anchor_hour
  6. Idempotency — two identical clarifying calls don't create two entries
  7. No-clarify path (stored=True) does NOT touch clarifying pending or emit
     clarify notification
  8. Wire contract unchanged — stored=False response body is identical to pre-v2.2
  9. Resolution heuristic — subsequent successful capture writes resolved_at
 10. _collect_clarify_notifications() read path (unit test)
"""

from __future__ import annotations

import json
from datetime import datetime, timedelta, timezone
from pathlib import Path
from zoneinfo import ZoneInfo

import pytest
from fastapi.testclient import TestClient

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
NOW = datetime(2026, 9, 22, 14, 0, tzinfo=TZ)  # Mon 2pm EDT

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _client(tmp_path: Path, monkeypatch, *, morning_anchor: int = 9) -> TestClient:
    monkeypatch.setenv("HOMUNCULUS_VAULT", str(tmp_path))
    monkeypatch.setenv("HOMUNCULUS_TZ", "America/New_York")
    monkeypatch.setenv("OLLAMA_BASE_URL", "http://127.0.0.1:1")
    monkeypatch.setenv("SPRITE_WARNINGS_PATH", str(tmp_path / "sprite" / "warnings.md"))
    monkeypatch.setenv("HOMUNCULUS_MIN_CONFIDENCE", "0.6")
    monkeypatch.setenv("HOMUNCULUS_MORNING_ANCHOR", str(morning_anchor))
    return TestClient(create_app())


def _ambiguous_payload(**overrides) -> dict:
    """Returns a payload that will trigger stored=False + clarifying_question.

    Uses time_hint="nine" with verb=schedule — the word "nine" is a bare
    text hour that date_resolver cannot resolve to AM or PM, so it returns
    ambiguous=['time'] regardless of the PM-inference rule (which only fires
    on numeric bare hours 1–5 for the schedule verb).
    """
    payload = {
        "verb": "schedule",
        "subject": "call the vet",
        "when": None,
        "day_hint": "friday",
        "time_hint": "nine",       # text bare-hour → genuinely ambiguous
        "criticality": "normal",
        "confidence": 0.85,
        "raw_transcript": "call the vet at nine",
        "audio_path": "/Users/thomas/sprite/inbox/vet.m4a",
        "captured_at": NOW.isoformat(),
    }
    payload.update(overrides)
    return payload


def _stored_payload(**overrides) -> dict:
    """Returns a payload that will be stored successfully."""
    payload = {
        "verb": "note",
        "subject": "pick up milk",
        "when": None,
        "day_hint": None,
        "time_hint": None,
        "criticality": "normal",
        "confidence": 0.9,
        "raw_transcript": "pick up milk on the way home",
        "audio_path": "/Users/thomas/sprite/inbox/milk.m4a",
        "captured_at": NOW.isoformat(),
    }
    payload.update(overrides)
    return payload


def _clarify_sidecars(vault: Path) -> list[Path]:
    """Return all clarify.*.json sidecars in _reminders/."""
    rem_dir = vault / "_reminders"
    if not rem_dir.exists():
        return []
    return sorted(rem_dir.glob("clarify.*.json"))


def _pending_path(vault: Path) -> Path:
    return vault / "_reminders" / "_clarifying_pending.jsonl"


def _pending_rows(vault: Path) -> list[dict]:
    p = _pending_path(vault)
    if not p.exists():
        return []
    out = []
    for line in p.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if line:
            try:
                out.append(json.loads(line))
            except json.JSONDecodeError:
                pass
    return out


# ---------------------------------------------------------------------------
# 1. Clarify immediate notification sidecar is written
# ---------------------------------------------------------------------------


def test_clarify_sidecar_written_on_stored_false(tmp_path, monkeypatch):
    """POST /capture/parsed with ambiguous time_hint → _reminders/clarify.<id>.json
    sidecar is created with fire_at ≈ now and correct kind."""
    client = _client(tmp_path, monkeypatch)
    r = client.post("/capture/parsed", json=_ambiguous_payload())
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["stored"] is False, "Pre-condition: must be ambiguous"

    sidecars = _clarify_sidecars(tmp_path)
    assert len(sidecars) == 1, f"Expected 1 clarify sidecar, found: {sidecars}"

    data = json.loads(sidecars[0].read_text(encoding="utf-8"))
    rows = data.get("schedule", [])
    assert len(rows) == 1
    row = rows[0]
    assert row["kind"] == "clarify_immediate"
    # fire_at must be parseable and close to now (within ±120 sec)
    fire_at = datetime.fromisoformat(row["fire_at"])
    if fire_at.tzinfo is None:
        fire_at = fire_at.replace(tzinfo=timezone.utc)
    delta = abs((fire_at - datetime.now(timezone.utc)).total_seconds())
    assert delta < 120, f"fire_at={row['fire_at']} is more than 120s from now"


# ---------------------------------------------------------------------------
# 2. Notification body contains question + transcript excerpt
# ---------------------------------------------------------------------------


def test_clarify_sidecar_body_contains_question_and_excerpt(tmp_path, monkeypatch):
    """Notification body includes the clarifying question and first ~40 chars of transcript."""
    client = _client(tmp_path, monkeypatch)
    transcript = "call the vet at 3"
    r = client.post("/capture/parsed", json=_ambiguous_payload(raw_transcript=transcript))
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["stored"] is False

    sidecars = _clarify_sidecars(tmp_path)
    assert sidecars
    row = json.loads(sidecars[0].read_text())["schedule"][0]

    # Body must mention the clarifying question (AM/PM present)
    assert "AM" in row["body"] or "am" in row["body"].lower(), (
        f"Expected AM/PM question in notification body. Got: {row['body']!r}"
    )
    # Body must include an excerpt of the transcript
    excerpt = transcript[:40]
    assert excerpt[:10] in row["body"], (
        f"Expected transcript excerpt in body. Got: {row['body']!r}"
    )


# ---------------------------------------------------------------------------
# 3. Notification identifier is clarify.<record_id>
# ---------------------------------------------------------------------------


def test_clarify_sidecar_identifier_matches_record_id(tmp_path, monkeypatch):
    """Notification event_id == 'clarify.<record_id>' from the response."""
    client = _client(tmp_path, monkeypatch)
    r = client.post("/capture/parsed", json=_ambiguous_payload())
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["stored"] is False
    record_id = body["record_id"]

    sidecars = _clarify_sidecars(tmp_path)
    assert sidecars
    data = json.loads(sidecars[0].read_text())
    row = data["schedule"][0]

    expected_id = f"clarify.{record_id}"
    assert row["event_id"] == expected_id, (
        f"Expected event_id='clarify.{record_id}', got {row['event_id']!r}"
    )
    assert data["event_id"] == expected_id


# ---------------------------------------------------------------------------
# 4. _clarifying_pending.jsonl row is appended (resolved_at=null)
# ---------------------------------------------------------------------------


def test_clarifying_pending_row_appended(tmp_path, monkeypatch):
    """A new row with resolved_at=null is written to _clarifying_pending.jsonl."""
    client = _client(tmp_path, monkeypatch)
    r = client.post("/capture/parsed", json=_ambiguous_payload())
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["stored"] is False

    rows = _pending_rows(tmp_path)
    assert len(rows) == 1, f"Expected 1 pending row, got {rows}"
    row = rows[0]
    assert row["resolved_at"] is None
    assert row["record_id"] == body["record_id"]
    assert row["question"]
    assert row["transcript_excerpt"]
    assert row["created_at"]


# ---------------------------------------------------------------------------
# 5. Daily summary includes unresolved clarify count when crossing anchor hour
# ---------------------------------------------------------------------------


def test_reminders_upcoming_includes_clarify_daily_summary_past_anchor(tmp_path, monkeypatch):
    """POST an ambiguous capture, then call /reminders/upcoming with a window
    that spans tomorrow's morning_anchor_hour → the response contains a
    morning_summary row whose body mentions pending clarifications.

    We rely on the real /reminders/upcoming endpoint and a 72h window from NOW.
    Since NOW is 2pm EDT and morning_anchor is 9am, tomorrow morning is within
    the 72h window → the morning_summary body must include the clarify count.
    """
    client = _client(tmp_path, monkeypatch)

    # Post an ambiguous record first
    r = client.post("/capture/parsed", json=_ambiguous_payload())
    assert r.status_code == 200
    assert r.json()["stored"] is False

    # Get upcoming reminders for next 72h
    r = client.get("/reminders/upcoming?window_hours=72")
    assert r.status_code == 200, r.text
    rows = r.json()

    # Find morning_summary rows
    summary_rows = [row for row in rows if row["kind"] == "morning_summary"]
    assert summary_rows, "Expected at least one morning_summary row in 72h window"

    # At least one summary body must mention pending clarifications
    any_with_clarify = any(
        "clarif" in row["body"].lower() or "pending" in row["body"].lower()
        for row in summary_rows
    )
    assert any_with_clarify, (
        f"Expected 'clarif' or 'pending' in a morning_summary body. "
        f"Bodies: {[r['body'][:100] for r in summary_rows]}"
    )


# ---------------------------------------------------------------------------
# 6. Idempotency — two identical clarifying calls don't create two entries
# ---------------------------------------------------------------------------


def test_clarify_idempotent_on_repeated_post(tmp_path, monkeypatch):
    """Posting the same ambiguous payload twice creates only ONE sidecar
    and ONE pending entry (matched on record_id)."""
    client = _client(tmp_path, monkeypatch)
    payload = _ambiguous_payload()

    r1 = client.post("/capture/parsed", json=payload)
    r2 = client.post("/capture/parsed", json=payload)
    assert r1.status_code == 200
    assert r2.status_code == 200
    # Both must be stored=False (clarification)
    assert r1.json()["stored"] is False
    assert r2.json()["stored"] is False
    # Same record_id
    assert r1.json()["record_id"] == r2.json()["record_id"]

    # Only ONE sidecar
    sidecars = _clarify_sidecars(tmp_path)
    assert len(sidecars) == 1, f"Expected idempotent: only 1 sidecar, got {len(sidecars)}"

    # Only ONE pending row
    rows = _pending_rows(tmp_path)
    assert len(rows) == 1, f"Expected 1 pending row, got {len(rows)}"


# ---------------------------------------------------------------------------
# 7. No-clarify path (stored=True) does NOT touch clarifying infrastructure
# ---------------------------------------------------------------------------


def test_stored_true_does_not_touch_clarifying_infrastructure(tmp_path, monkeypatch):
    """A successful capture (stored=True) must not write any clarify sidecar
    or pending row."""
    client = _client(tmp_path, monkeypatch)
    r = client.post("/capture/parsed", json=_stored_payload())
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["stored"] is True, f"Pre-condition: must be stored. Got: {body}"

    sidecars = _clarify_sidecars(tmp_path)
    assert len(sidecars) == 0, (
        f"stored=True capture must not emit clarify sidecar. Found: {sidecars}"
    )

    rows = _pending_rows(tmp_path)
    assert len(rows) == 0, (
        f"stored=True capture must not write to _clarifying_pending.jsonl. Got: {rows}"
    )


# ---------------------------------------------------------------------------
# 8. Wire contract unchanged — stored=False response body identical to pre-v2.2
# ---------------------------------------------------------------------------


def test_stored_false_response_wire_shape_unchanged(tmp_path, monkeypatch):
    """The HTTP response body for a clarifying question must retain all
    pre-v2.2 fields. New side effects (sidecar, pending log) are additive.
    """
    client = _client(tmp_path, monkeypatch)
    r = client.post("/capture/parsed", json=_ambiguous_payload())
    assert r.status_code == 200, r.text
    body = r.json()

    # Original wire contract fields
    assert "stored" in body and body["stored"] is False
    assert "record_id" in body and body["record_id"]
    assert "verb" in body
    assert "clarifying_question" in body and body["clarifying_question"]
    assert "ambiguous_fields" in body and isinstance(body["ambiguous_fields"], list)
    # event_id may be None for a clarification — allowed
    assert "event_id" in body


# ---------------------------------------------------------------------------
# 9. Resolution heuristic — successful follow-up with same event_id (if set)
#    or same subject within a configurable window marks resolved_at
# ---------------------------------------------------------------------------


def test_resolution_marks_resolved_at_on_subsequent_store(tmp_path, monkeypatch):
    """Best-effort resolution heuristic: when a successful capture (stored=True)
    arrives with the same verb+subject+captured_at as a pending clarifying entry,
    the pending entry gets its resolved_at populated.

    The heuristic: on every stored=True dispatch, scan _clarifying_pending.jsonl
    for entries that share (verb, subject.strip().lower(), captured_at.isoformat())
    with the new successful capture and mark them resolved.

    This covers the common user path: Thomas re-records the memo with "at 9 AM"
    instead of "at nine" — same verb, same subject, same captured_at (Sprite
    preserves the original mtime) → pending entry gets resolved.
    """
    client = _client(tmp_path, monkeypatch)

    # 1. Post the ambiguous version → stored=False, record appears in pending.
    # captured_at is NOW (base of _ambiguous_payload).
    r_ambig = client.post("/capture/parsed", json=_ambiguous_payload())
    assert r_ambig.json()["stored"] is False
    pending = _pending_rows(tmp_path)
    assert len(pending) == 1
    assert pending[0]["resolved_at"] is None

    # 2. Post the resolved version:
    # SAME verb, SAME subject, SAME captured_at → but with explicit when= (unambiguous).
    # This is what Sprite does when the user re-records with "at 9 AM".
    resolved_when = (NOW + timedelta(days=1, hours=9)).isoformat()  # explicit Friday 9am
    r_stored = client.post(
        "/capture/parsed",
        json=_ambiguous_payload(
            time_hint="9 AM",   # unambiguous → stored=True (explicit AM)
            when=None,          # let hints resolve
        ),
    )
    assert r_stored.status_code == 200, r_stored.text
    body_stored = r_stored.json()
    assert body_stored["stored"] is True, (
        f"Follow-up with explicit AM/PM must store. Got: {body_stored}"
    )

    # 3. After resolution, the pending entry must have a resolved_at timestamp.
    rows = _pending_rows(tmp_path)
    resolved_rows = [row for row in rows if row.get("resolved_at") is not None]
    assert resolved_rows, (
        f"Expected at least one resolved_at after successful follow-up with "
        f"same verb+subject+captured_at. Rows: {rows}"
    )


# ---------------------------------------------------------------------------
# 10. Unit test: _collect_clarify_notifications read path
# ---------------------------------------------------------------------------


def test_collect_clarify_notifications_reads_sidecar(tmp_path, monkeypatch):
    """Unit test: _collect_clarify_notifications() picks up a sidecar that
    was written by dispatch() and returns a ReminderRow with kind=clarify_immediate.
    """
    client = _client(tmp_path, monkeypatch)
    r = client.post("/capture/parsed", json=_ambiguous_payload())
    assert r.json()["stored"] is False

    # Confirm sidecar exists
    sidecars = _clarify_sidecars(tmp_path)
    assert sidecars

    # Use /reminders/upcoming with include_fired=True to see the just-written row
    r_up = client.get("/reminders/upcoming?window_hours=72&include_fired=true")
    assert r_up.status_code == 200
    rows = r_up.json()

    clarify_rows = [row for row in rows if row.get("kind") == "clarify_immediate"]
    assert clarify_rows, (
        f"Expected clarify_immediate row in /reminders/upcoming. Kinds seen: "
        f"{sorted(set(r['kind'] for r in rows))}"
    )
    cr = clarify_rows[0]
    assert "AM" in cr["body"] or "am" in cr["body"].lower() or "clarif" in cr["body"].lower()


# ---------------------------------------------------------------------------
# 11. Multiple pending entries accumulate in the daily summary count
# ---------------------------------------------------------------------------


def test_multiple_pending_entries_reflected_in_summary(tmp_path, monkeypatch):
    """Two different ambiguous captures → daily summary body mentions 2 pending."""
    client = _client(tmp_path, monkeypatch)

    # First ambiguous capture
    r1 = client.post("/capture/parsed", json=_ambiguous_payload(
        subject="vet call",
        raw_transcript="call the vet at 3",
        captured_at=NOW.isoformat(),
    ))
    assert r1.json()["stored"] is False

    # Second ambiguous capture (different subject, different captured_at to get different record_id)
    r2 = client.post("/capture/parsed", json=_ambiguous_payload(
        subject="doctor appointment at 3",
        raw_transcript="doctor appointment at 3",
        captured_at=(NOW + timedelta(minutes=30)).isoformat(),
    ))
    assert r2.json()["stored"] is False

    rows = _pending_rows(tmp_path)
    assert len(rows) == 2, f"Expected 2 pending rows, got {rows}"

    # Morning summary should mention both
    r_up = client.get("/reminders/upcoming?window_hours=72")
    assert r_up.status_code == 200
    summary_rows = [row for row in r_up.json() if row["kind"] == "morning_summary"]
    assert summary_rows
    # The body should either mention 2 or just mention "pending clarifications"
    body_text = " ".join(r["body"] for r in summary_rows)
    assert "clarif" in body_text.lower() or "pending" in body_text.lower(), (
        f"Expected clarify mention in summary. Bodies: {[r['body'][:120] for r in summary_rows]}"
    )


# ---------------------------------------------------------------------------
# 12. Clarify sidecar has correct structure for mac_notifier consumption
# ---------------------------------------------------------------------------


def test_clarify_sidecar_structure_for_mac_notifier(tmp_path, monkeypatch):
    """The sidecar written to _reminders/ must have the same outer shape as
    a timer_stop sidecar: {'event_id': str, 'schedule': [row_dict]}.
    The row must have fire_at, body, status, and kind fields.
    """
    client = _client(tmp_path, monkeypatch)
    r = client.post("/capture/parsed", json=_ambiguous_payload())
    assert r.json()["stored"] is False

    sidecars = _clarify_sidecars(tmp_path)
    assert sidecars
    data = json.loads(sidecars[0].read_text())

    # Outer shape
    assert "event_id" in data
    assert "schedule" in data
    assert isinstance(data["schedule"], list)
    assert len(data["schedule"]) == 1

    row = data["schedule"][0]
    for field in ("event_id", "kind", "fire_at", "body", "status"):
        assert field in row, f"Missing field '{field}' in sidecar row"
    assert row["status"] == "pending"
    assert row["kind"] == "clarify_immediate"


# ---------------------------------------------------------------------------
# 13. Regression — stored=True captures still use activity log (no regression)
# ---------------------------------------------------------------------------


def test_stored_true_still_writes_activity_log(tmp_path, monkeypatch):
    """stored=True path: activity log entry written as before (no regression)."""
    client = _client(tmp_path, monkeypatch)
    r = client.post("/capture/parsed", json=_stored_payload())
    assert r.json()["stored"] is True

    activity_file = tmp_path / "_activity.jsonl"
    assert activity_file.exists()
    entries = [json.loads(ln) for ln in activity_file.read_text().splitlines() if ln.strip()]
    assert any(e["kind"] == "capture_parsed" for e in entries), (
        "Expected capture_parsed activity log entry for stored=True capture"
    )
