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
