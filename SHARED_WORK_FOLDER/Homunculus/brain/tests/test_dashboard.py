"""Tests for the Herman v1.5.0 dashboard routes.

Coverage:
  1. GET /dashboard/ returns 200 with HTML content-type.
  2. GET /dashboard/data on an empty vault returns {"rows": [], "latest_at": null}.
  3. GET /dashboard/data after captures returns rows reverse-chronological
     with the expected shape (icon, time, summary derived per verb).
  4. ?since=<timestamp> filter returns only rows newer than the timestamp.
  5. Malformed rows in _activity.jsonl are skipped without crashing.
  6. Confidence field extraction — nested (details.confidence) and missing.

No real vault, no Ollama, no osascript.
"""

from __future__ import annotations

import json
from datetime import datetime, timezone, timedelta
from pathlib import Path
from zoneinfo import ZoneInfo

import pytest
from fastapi.testclient import TestClient

from homunculus_brain.server import create_app
from homunculus_brain import dashboard as dash


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _write_activity(vault: Path, rows: list[dict]) -> None:
    """Write rows to the vault's _activity.jsonl (creates the file)."""
    path = vault / "_activity.jsonl"
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as f:
        for row in rows:
            f.write(json.dumps(row) + "\n")


def _app(vault: Path, monkeypatch) -> TestClient:
    monkeypatch.setenv("HOMUNCULUS_VAULT", str(vault))
    monkeypatch.setenv("OLLAMA_BASE_URL", "http://127.0.0.1:1")
    return TestClient(create_app())


def _ts(offset_seconds: int = 0) -> str:
    """Return an ISO 8601 UTC timestamp offset from a fixed base.

    Uses 'Z' suffix rather than '+00:00' so the value is safe to embed
    directly in a URL query-string without percent-encoding the '+' sign.
    """
    base = datetime(2026, 9, 14, 12, 0, 0, tzinfo=timezone.utc)
    dt = base + timedelta(seconds=offset_seconds)
    # Produce e.g. "2026-09-14T12:00:00Z" — no '+' character.
    return dt.strftime("%Y-%m-%dT%H:%M:%SZ")


# ---------------------------------------------------------------------------
# 1. Dashboard HTML is served
# ---------------------------------------------------------------------------


def test_dashboard_page_returns_200_html(tmp_path: Path, monkeypatch):
    """/dashboard/ returns 200 and HTML content-type."""
    with _app(tmp_path, monkeypatch) as client:
        r = client.get("/dashboard/")
        assert r.status_code == 200, r.text
        ct = r.headers.get("content-type", "")
        assert "text/html" in ct, ct
        # Must contain the version badge
        assert "Homunculus Dashboard" in r.text
        assert dash.DASHBOARD_VERSION in r.text
        # Must contain the feed container
        assert 'id="feed"' in r.text


# ---------------------------------------------------------------------------
# 2. Empty vault → empty rows
# ---------------------------------------------------------------------------


def test_dashboard_data_empty_vault(tmp_path: Path, monkeypatch):
    """/dashboard/data with no _activity.jsonl returns empty result."""
    with _app(tmp_path, monkeypatch) as client:
        r = client.get("/dashboard/data")
        assert r.status_code == 200, r.text
        body = r.json()
        assert body["rows"] == []
        assert body["latest_at"] is None


# ---------------------------------------------------------------------------
# 3. Rows are reverse-chronological with correct shape
# ---------------------------------------------------------------------------


def test_dashboard_data_reverse_chron_and_shape(tmp_path: Path, monkeypatch):
    """Rows returned newest-first; icon/summary/confidence derived correctly."""
    rows = [
        {
            "at": _ts(0),
            "kind": "capture_parsed",
            "event_id": "evt-a",
            "raw_text": "Schedule a meeting on Monday",
            "details": {
                "verb": "schedule",
                "subject": "meeting on Monday",
                "confidence": 0.85,
            },
        },
        {
            "at": _ts(60),  # 1 minute later — should appear FIRST in response
            "kind": "capture_parsed",
            "event_id": "evt-b",
            "raw_text": "Take a note about the deck project",
            "details": {
                "verb": "note",
                "subject": "deck project",
                "confidence": 0.55,
            },
        },
        {
            "at": _ts(-60),  # 1 minute earlier — should appear LAST
            "kind": "event_ack",
            "event_id": "evt-x",
            "raw_text": None,
            "details": {"acked_kind": "strike_0"},
        },
    ]
    _write_activity(tmp_path, rows)

    with _app(tmp_path, monkeypatch) as client:
        r = client.get("/dashboard/data")
        assert r.status_code == 200, r.text
        body = r.json()
        data_rows = body["rows"]
        assert len(data_rows) == 3

        # Verify reverse-chronological order
        ats = [row["at"] for row in data_rows]
        assert ats == sorted(ats, reverse=True), "Rows must be newest-first"

        # First row (newest): note verb
        first = data_rows[0]
        assert first["event_id"] == "evt-b"
        assert first["icon"] == "📝", f"Expected note icon, got {first['icon']!r}"
        assert "deck project" in first["summary"]
        assert first["confidence"] == pytest.approx(0.55)

        # Second row: schedule verb
        second = data_rows[1]
        assert second["event_id"] == "evt-a"
        assert second["icon"] == "📅", f"Expected schedule icon, got {second['icon']!r}"
        assert "schedule" in second["summary"].lower() or "meeting" in second["summary"].lower()
        assert second["confidence"] == pytest.approx(0.85)

        # Third row: event_ack — no verb in details, fallback to kind
        third = data_rows[2]
        assert third["event_id"] == "evt-x"
        assert third["icon"] == "✔️", f"Expected event_ack icon, got {third['icon']!r}"

        # latest_at matches the newest timestamp (compare as parsed datetimes
        # since the server normalises 'Z' → '+00:00' in its isoformat output)
        from datetime import timezone as _tz
        assert datetime.fromisoformat(body["latest_at"]).astimezone(_tz.utc) == \
               datetime.fromisoformat(_ts(60)).astimezone(_tz.utc)


# ---------------------------------------------------------------------------
# 4. ?since= filter
# ---------------------------------------------------------------------------


def test_dashboard_data_since_filter(tmp_path: Path, monkeypatch):
    """?since= returns only rows with at > since."""
    rows = [
        {"at": _ts(0),   "kind": "parse", "event_id": None, "raw_text": "old",  "details": {}},
        {"at": _ts(120), "kind": "parse", "event_id": None, "raw_text": "new1", "details": {}},
        {"at": _ts(180), "kind": "parse", "event_id": None, "raw_text": "new2", "details": {}},
    ]
    _write_activity(tmp_path, rows)

    # since = _ts(60): only rows at _ts(120) and _ts(180) should appear
    since = _ts(60)
    with _app(tmp_path, monkeypatch) as client:
        r = client.get(f"/dashboard/data?since={since}")
        assert r.status_code == 200, r.text
        body = r.json()
        returned_texts = [row["raw_text"] for row in body["rows"]]
        assert "old" not in returned_texts, returned_texts
        assert "new1" in returned_texts, returned_texts
        assert "new2" in returned_texts, returned_texts
        assert len(body["rows"]) == 2


def test_dashboard_data_since_exclusive(tmp_path: Path, monkeypatch):
    """Rows exactly at the since timestamp are excluded (exclusive bound)."""
    pivot = _ts(100)
    rows = [
        {"at": pivot,    "kind": "parse", "event_id": None, "raw_text": "at-pivot", "details": {}},
        {"at": _ts(200), "kind": "parse", "event_id": None, "raw_text": "after",    "details": {}},
    ]
    _write_activity(tmp_path, rows)

    with _app(tmp_path, monkeypatch) as client:
        r = client.get(f"/dashboard/data?since={pivot}")
        body = r.json()
        texts = [row["raw_text"] for row in body["rows"]]
        assert "at-pivot" not in texts, texts
        assert "after" in texts, texts


# ---------------------------------------------------------------------------
# 5. Malformed rows are skipped gracefully
# ---------------------------------------------------------------------------


def test_dashboard_data_skips_malformed_rows(tmp_path: Path, monkeypatch):
    """Malformed JSONL lines don't crash /dashboard/data."""
    path = tmp_path / "_activity.jsonl"
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as f:
        f.write("this is not json at all\n")
        f.write("{incomplete json\n")
        # A valid row with no 'at' field (should be skipped gracefully)
        f.write(json.dumps({"kind": "parse", "event_id": None}) + "\n")
        # A valid row with an unparseable 'at' value
        f.write(json.dumps({"at": "not-a-date", "kind": "parse"}) + "\n")
        # One good row to confirm the endpoint still returns results
        f.write(json.dumps({
            "at": _ts(0),
            "kind": "parse",
            "event_id": None,
            "raw_text": "good row",
            "details": {},
        }) + "\n")

    with _app(tmp_path, monkeypatch) as client:
        r = client.get("/dashboard/data")
        assert r.status_code == 200, r.text
        body = r.json()
        assert len(body["rows"]) == 1
        assert body["rows"][0]["raw_text"] == "good row"


# ---------------------------------------------------------------------------
# 6. Confidence extraction — nested and missing
# ---------------------------------------------------------------------------


def test_confidence_nested_in_details(tmp_path: Path, monkeypatch):
    """Confidence comes from details.confidence (float)."""
    rows = [
        {
            "at": _ts(0),
            "kind": "capture_parsed",
            "event_id": None,
            "raw_text": "test",
            "details": {"verb": "handle", "confidence": 0.72},
        },
    ]
    _write_activity(tmp_path, rows)

    with _app(tmp_path, monkeypatch) as client:
        r = client.get("/dashboard/data")
        body = r.json()
        assert body["rows"][0]["confidence"] == pytest.approx(0.72)


def test_confidence_missing_is_null(tmp_path: Path, monkeypatch):
    """Rows without a confidence field return confidence=null."""
    rows = [
        {
            "at": _ts(0),
            "kind": "event_ack",
            "event_id": "evt-x",
            "raw_text": None,
            "details": {"acked_kind": "strike_0"},
        },
    ]
    _write_activity(tmp_path, rows)

    with _app(tmp_path, monkeypatch) as client:
        r = client.get("/dashboard/data")
        body = r.json()
        assert body["rows"][0]["confidence"] is None


def test_confidence_string_value_coerced(tmp_path: Path, monkeypatch):
    """Older rows may have confidence as a string ('high'); coerce gracefully."""
    rows = [
        {
            "at": _ts(0),
            "kind": "parse",
            "event_id": None,
            "raw_text": "old-era row",
            # v1.2-era rows used string confidence like "high"/"medium"
            "details": {"confidence": "high"},
        },
    ]
    _write_activity(tmp_path, rows)

    with _app(tmp_path, monkeypatch) as client:
        r = client.get("/dashboard/data")
        body = r.json()
        # "high" can't be float-coerced; should return null rather than crash
        assert body["rows"][0]["confidence"] is None
        assert r.status_code == 200


# ---------------------------------------------------------------------------
# 7. limit parameter is respected
# ---------------------------------------------------------------------------


def test_dashboard_data_limit(tmp_path: Path, monkeypatch):
    """?limit=N returns at most N rows."""
    rows = [
        {"at": _ts(i), "kind": "parse", "event_id": None, "raw_text": f"r{i}", "details": {}}
        for i in range(10)
    ]
    _write_activity(tmp_path, rows)

    with _app(tmp_path, monkeypatch) as client:
        r = client.get("/dashboard/data?limit=3")
        body = r.json()
        assert len(body["rows"]) == 3


# ---------------------------------------------------------------------------
# 8. Visual redesign v0.4 — structural contracts
# ---------------------------------------------------------------------------


def _get_html(tmp_path: Path, monkeypatch) -> str:
    """Convenience: return the dashboard HTML string."""
    with _app(tmp_path, monkeypatch) as client:
        r = client.get("/dashboard/")
        assert r.status_code == 200
        return r.text


def test_v04_version_badge(tmp_path: Path, monkeypatch):
    """DASHBOARD_VERSION == 'v0.5' and appears in the served HTML.

    Note: this test was originally named v04 but tracks the current version.
    We update the assertion to the current version (v0.5) as the badge bumps.
    """
    import re
    from homunculus_brain import dashboard as dash

    assert dash.DASHBOARD_VERSION == "v0.5", (
        f"Expected v0.5, got {dash.DASHBOARD_VERSION!r}"
    )
    html = _get_html(tmp_path, monkeypatch)
    assert "v0.5" in html, "v0.5 badge not found in HTML"


def test_v04_sticky_header(tmp_path: Path, monkeypatch):
    """Header element has position:sticky (or fixed) in the CSS."""
    import re

    html = _get_html(tmp_path, monkeypatch)
    # Look for 'header' block in the <style> section containing sticky/fixed
    # We look for a CSS rule that applies to the header element
    # Match: header { ... position: sticky ... } or header { ... position: fixed ... }
    match = re.search(
        r"header\s*\{[^}]*position\s*:\s*(sticky|fixed)[^}]*\}",
        html,
        re.DOTALL | re.IGNORECASE,
    )
    assert match, (
        "Expected header { position: sticky|fixed } in CSS — not found.\n"
        "Tip: the header must be positionally anchored so it stays visible when feed scrolls."
    )


def test_v04_sticky_timers_panel(tmp_path: Path, monkeypatch):
    """Timers panel has position:sticky (or fixed) in the CSS."""
    import re

    html = _get_html(tmp_path, monkeypatch)
    # The timers panel uses id="timers-panel" — look for its CSS block
    match = re.search(
        r"#timers-panel\s*\{[^}]*position\s*:\s*(sticky|fixed)[^}]*\}",
        html,
        re.DOTALL | re.IGNORECASE,
    )
    assert match, (
        "Expected #timers-panel { position: sticky|fixed } in CSS — not found.\n"
        "Tip: the timers panel must stay visible when the activity feed scrolls."
    )


def test_v04_light_theme_body_background(tmp_path: Path, monkeypatch):
    """Body background is NOT a dark value (#111 / #0x0x0x under threshold)."""
    import re

    html = _get_html(tmp_path, monkeypatch)
    # Extract the background value from the body { } CSS block
    body_block = re.search(
        r"body\s*\{([^}]*)\}",
        html,
        re.DOTALL,
    )
    assert body_block, "No body {} CSS block found in HTML"
    block_text = body_block.group(1)

    bg_match = re.search(
        r"background(?:-color)?\s*:\s*(#[0-9a-fA-F]{3,6}|[a-z]+)",
        block_text,
    )
    assert bg_match, f"No background color found in body block: {block_text!r}"
    bg_value = bg_match.group(1).lower()

    # Reject short hex darks like #111, #000, #0d0d0d
    def _is_dark_hex(val: str) -> bool:
        val = val.lstrip("#")
        if len(val) == 3:
            val = "".join(c * 2 for c in val)
        if len(val) != 6:
            return False
        r = int(val[0:2], 16)
        g = int(val[2:4], 16)
        b = int(val[4:6], 16)
        # "Dark" = average channel < 80 (out of 255)
        return (r + g + b) / 3 < 80

    assert not _is_dark_hex(bg_value), (
        f"Body background {bg_value!r} is too dark — expected light theme."
    )


def test_v04_feed_scrollable(tmp_path: Path, monkeypatch):
    """The feed container has overflow-y: auto or scroll."""
    import re

    html = _get_html(tmp_path, monkeypatch)
    # Look for #feed { ... overflow-y: auto|scroll ... }
    match = re.search(
        r"#feed\s*\{[^}]*overflow-y\s*:\s*(auto|scroll)[^}]*\}",
        html,
        re.DOTALL | re.IGNORECASE,
    )
    assert match, (
        "Expected #feed { overflow-y: auto|scroll } in CSS — not found.\n"
        "Tip: only the feed area should scroll; header and timers must stay pinned."
    )


def test_v04_version_badge_readable_contrast(tmp_path: Path, monkeypatch):
    """Version badge color is not the old dark-on-dark scheme (#aaa on dark)."""
    import re

    html = _get_html(tmp_path, monkeypatch)
    # The old scheme was color: #aaa (light grey) on a dark bg pill.
    # For the light theme the badge must use a dark text or a colored pill
    # visible on white/off-white — i.e. NOT color: #aaa on a light bg.
    # We simply assert the badge CSS does NOT contain "color: #aaa" as the
    # primary text colour (it was the old dark-theme compromise).
    badge_block = re.search(
        r"\.version-badge\s*\{([^}]*)\}",
        html,
        re.DOTALL,
    )
    assert badge_block, "No .version-badge CSS block found"
    block_text = badge_block.group(1).lower()
    # The old value was exactly "color: #aaa" — that's a low-contrast grey on
    # the new light background. Assert it's gone.
    assert "color: #aaa" not in block_text, (
        "Version badge still uses color: #aaa — low contrast on light theme. "
        "Use a dark readable colour instead."
    )


# ---------------------------------------------------------------------------
# v0.5 — Clarifying-question rows in the dashboard feed
# ---------------------------------------------------------------------------


def _write_clarify_activity(vault: Path, *, at: str, question: str, record_id: str,
                             transcript: str = "call the vet at 3") -> None:
    """Write an activity row for a clarifying question (stored=False path)."""
    row = {
        "at": at,
        "kind": "capture_parsed",
        "event_id": None,
        "raw_text": transcript,
        "details": {
            "verb": "schedule",
            "subject": transcript,
            "confidence": 0.85,
            "audio_path": "/tmp/vet.m4a",
            "record_id": record_id,
            "written_path": None,                  # stored=False → no written_path
            "ambiguous_fields": ["time"],
            "clarifying_question": question,
            "stored": False,
        },
    }
    path = vault / "_activity.jsonl"
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as f:
        f.write(json.dumps(row) + "\n")


def test_v05_version_badge(tmp_path: Path, monkeypatch):
    """DASHBOARD_VERSION == 'v0.5' and appears in the served HTML."""
    from homunculus_brain import dashboard as dash

    assert dash.DASHBOARD_VERSION == "v0.5", (
        f"Expected v0.5, got {dash.DASHBOARD_VERSION!r}"
    )
    html = _get_html(tmp_path, monkeypatch)
    assert "v0.5" in html, "v0.5 badge not found in HTML"


def test_v05_shape_row_clarifying_question(tmp_path: Path, monkeypatch):
    """_shape_row() on a clarifying-question activity row returns:
    - icon containing the clarify indicator
    - summary starting with 'Awaiting clarification'
    - is_clarifying: True
    """
    from homunculus_brain import dashboard as dash

    raw = {
        "at": _ts(0),
        "kind": "capture_parsed",
        "event_id": None,
        "raw_text": "call the vet at 3",
        "details": {
            "verb": "schedule",
            "subject": "call the vet at 3",
            "confidence": 0.85,
            "audio_path": "/tmp/vet.m4a",
            "record_id": "abc123",
            "written_path": None,
            "ambiguous_fields": ["time"],
            "clarifying_question": "Did you mean AM or PM?",
            "stored": False,
        },
    }
    shaped = dash._shape_row(raw)
    assert shaped is not None

    # icon must signal clarification
    icon = shaped.get("icon", "")
    assert "❓" in icon or "⚠" in icon, (
        f"Expected clarify icon (❓ or ⚠), got {icon!r}"
    )

    # summary must start with "Awaiting clarification"
    summary = shaped.get("summary", "")
    assert summary.startswith("Awaiting clarification"), (
        f"Expected summary to start with 'Awaiting clarification', got {summary!r}"
    )

    # is_clarifying flag
    assert shaped.get("is_clarifying") is True, (
        f"Expected is_clarifying=True, got {shaped.get('is_clarifying')!r}"
    )


def test_v05_shape_row_clarifying_question_truncates_long_question(tmp_path: Path, monkeypatch):
    """Long clarifying questions are truncated to ≤ 60 chars in the summary."""
    from homunculus_brain import dashboard as dash

    long_question = "Did you mean AM or PM for this appointment that you mentioned on Thursday morning?"
    raw = {
        "at": _ts(0),
        "kind": "capture_parsed",
        "event_id": None,
        "raw_text": "something",
        "details": {
            "verb": "schedule",
            "subject": "something",
            "confidence": 0.85,
            "audio_path": "/tmp/x.m4a",
            "record_id": "xyz",
            "written_path": None,
            "ambiguous_fields": ["time"],
            "clarifying_question": long_question,
            "stored": False,
        },
    }
    shaped = dash._shape_row(raw)
    assert shaped is not None
    summary = shaped["summary"]
    # The question portion should be truncated to ≤ 60 chars after the prefix
    question_part = summary.replace("Awaiting clarification — ", "")
    assert len(question_part) <= 60, (
        f"Question in summary too long ({len(question_part)} chars): {question_part!r}"
    )


def test_v05_dashboard_data_clarify_row_shape(tmp_path: Path, monkeypatch):
    """GET /dashboard/data after a clarifying activity row returns correct shape.

    This uses _write_clarify_activity to inject the row directly into the
    activity log, simulating what capture_parsed.dispatch() does when
    stored=False + clarifying_question.
    """
    _write_clarify_activity(
        tmp_path,
        at=_ts(0),
        question="Did you mean AM or PM?",
        record_id="testrecord001",
        transcript="call the vet at 3",
    )

    with _app(tmp_path, monkeypatch) as client:
        r = client.get("/dashboard/data")
        assert r.status_code == 200, r.text
        body = r.json()
        rows = body["rows"]
        assert len(rows) == 1

        row = rows[0]
        icon = row.get("icon", "")
        assert "❓" in icon or "⚠" in icon, f"Expected clarify icon, got {icon!r}"
        summary = row.get("summary", "")
        assert "Awaiting clarification" in summary, f"Expected 'Awaiting clarification', got {summary!r}"
        assert row.get("is_clarifying") is True, (
            f"Expected is_clarifying=True, got {row.get('is_clarifying')!r}"
        )


def test_v05_non_clarifying_rows_are_unaffected(tmp_path: Path, monkeypatch):
    """Normal stored=True rows must NOT get is_clarifying=True."""
    rows = [
        {
            "at": _ts(0),
            "kind": "capture_parsed",
            "event_id": "evt-a",
            "raw_text": "schedule a meeting",
            "details": {
                "verb": "schedule",
                "subject": "meeting",
                "confidence": 0.9,
                "written_path": "calendar/2026-09/something.md",
                "ambiguous_fields": [],
                # No stored=False, no clarifying_question
            },
        },
    ]
    _write_activity(tmp_path, rows)

    with _app(tmp_path, monkeypatch) as client:
        r = client.get("/dashboard/data")
        assert r.status_code == 200
        body_row = r.json()["rows"][0]
        is_clarifying = body_row.get("is_clarifying")
        assert is_clarifying is not True, (
            f"Normal stored=True row must not be marked is_clarifying. Got: {is_clarifying!r}"
        )
        assert body_row["icon"] != "❓", "Normal row must not use clarify icon"


def test_v05_shape_row_clarifying_expand_fields(tmp_path: Path, monkeypatch):
    """_shape_row() on a clarifying row must include the full question and
    ambiguous_fields for the expand panel."""
    from homunculus_brain import dashboard as dash

    question = "Did you mean AM or PM?"
    raw = {
        "at": _ts(0),
        "kind": "capture_parsed",
        "event_id": None,
        "raw_text": "call the vet at 3",
        "details": {
            "verb": "schedule",
            "subject": "call the vet at 3",
            "confidence": 0.85,
            "audio_path": "/tmp/vet.m4a",
            "record_id": "abc123",
            "written_path": None,
            "ambiguous_fields": ["time"],
            "clarifying_question": question,
            "stored": False,
        },
    }
    shaped = dash._shape_row(raw)
    assert shaped is not None

    # Full question available for expand panel
    assert shaped.get("clarifying_question") == question, (
        f"Expected full question in shaped row. Got: {shaped.get('clarifying_question')!r}"
    )
    # ambiguous_fields preserved
    assert shaped.get("ambiguous_fields") == ["time"], (
        f"Expected ambiguous_fields=['time']. Got: {shaped.get('ambiguous_fields')!r}"
    )


def test_v05_regression_existing_rows_still_pass(tmp_path: Path, monkeypatch):
    """Regression: existing non-clarifying row shapes are unaffected by v0.5."""
    from homunculus_brain import dashboard as dash

    # Timer stop row
    timer_raw = {
        "at": _ts(0),
        "kind": "timer_stop",
        "event_id": None,
        "raw_text": None,
        "details": {
            "project": "deck",
            "slug": "deck",
            "duration_seconds": 3600,
            "total_seconds": 7200,
        },
    }
    shaped = dash._shape_row(timer_raw)
    assert shaped is not None
    assert shaped["icon"] == "⏱"
    assert "Stopped" in shaped["summary"] or "stopped" in shaped["summary"].lower() or "deck" in shaped["summary"].lower()
    assert shaped.get("is_clarifying") is not True

    # Avoid/warning row
    avoid_raw = {
        "at": _ts(10),
        "kind": "capture_parsed",
        "event_id": None,
        "raw_text": "Sam's dairy allergy",
        "details": {
            "verb": "avoid",
            "subject": "Sam's dairy allergy",
            "confidence": 0.9,
            "written_path": "/home/sprite/warnings.md",
            "ambiguous_fields": [],
        },
    }
    shaped_avoid = dash._shape_row(avoid_raw)
    assert shaped_avoid is not None
    assert shaped_avoid["icon"] == "⚠️", f"Expected avoid icon, got {shaped_avoid['icon']!r}"
    assert shaped_avoid.get("is_clarifying") is not True


def test_v05_full_pipeline_clarify_row_in_dashboard(tmp_path: Path, monkeypatch):
    """End-to-end: POST /capture/parsed with ambiguous time →
    GET /dashboard/data returns a row with is_clarifying=True and
    'Awaiting clarification' in summary.

    This test uses the real FastAPI endpoint + real dispatch() so it exercises
    whether dispatch() writes the clarifying activity log entry.
    """
    monkeypatch.setenv("HOMUNCULUS_VAULT", str(tmp_path))
    monkeypatch.setenv("HOMUNCULUS_TZ", "America/New_York")
    monkeypatch.setenv("OLLAMA_BASE_URL", "http://127.0.0.1:1")
    monkeypatch.setenv("SPRITE_WARNINGS_PATH", str(tmp_path / "sprite" / "warnings.md"))
    monkeypatch.setenv("HOMUNCULUS_MIN_CONFIDENCE", "0.6")

    with TestClient(create_app()) as client:
        # Post an ambiguous capture
        r_cap = client.post("/capture/parsed", json={
            "verb": "schedule",
            "subject": "call the vet",
            "when": None,
            "day_hint": "friday",
            "time_hint": "nine",   # text bare-hour → genuinely ambiguous for any verb
            "criticality": "normal",
            "confidence": 0.85,
            "raw_transcript": "call the vet at nine",
            "audio_path": "/tmp/vet.m4a",
            "captured_at": datetime(2026, 9, 22, 14, 0,
                                    tzinfo=ZoneInfo("America/New_York")).isoformat(),
        })
        assert r_cap.status_code == 200, r_cap.text
        assert r_cap.json()["stored"] is False

        # Now check dashboard
        r_dash = client.get("/dashboard/data")
        assert r_dash.status_code == 200
        rows = r_dash.json()["rows"]
        # There should be at least one clarifying row
        clarify_rows = [row for row in rows if row.get("is_clarifying")]
        assert clarify_rows, (
            f"Expected is_clarifying row in dashboard. Rows: {[r['summary'] for r in rows]}"
        )
