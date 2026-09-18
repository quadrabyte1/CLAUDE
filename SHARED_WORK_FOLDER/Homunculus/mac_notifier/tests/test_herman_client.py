"""
test_herman_client.py — Tests for mac_notifier.herman_client

House rule: NEVER hit real Herman in tests. All httpx calls are mocked.

Covers:
- Happy path: valid JSON list → parsed ReminderRow list
- Herman unreachable (RequestError) → empty list, no crash
- Herman timeout → empty list, no crash
- Herman returns HTTP 500 → empty list, no crash
- Herman returns non-JSON → empty list, no crash
- Herman returns a JSON dict (not list) → empty list, no crash
- Malformed row: missing event_id → skipped
- Malformed row: missing kind → skipped
- Malformed row: missing fire_at → skipped
- Malformed row: unparseable fire_at → skipped
- Malformed row: naive fire_at (no tzinfo) → skipped
- Valid rows alongside malformed → valid ones returned
- ReminderRow.identifier = "<event_id>:<kind>"
- ReminderRow.subtitle maps kind to human label
- Unknown kind → title-cased fallback subtitle
"""

from __future__ import annotations

from datetime import datetime, timezone, timedelta
from unittest import mock

import pytest
import httpx

from mac_notifier.herman_client import HermanClient, ReminderRow, _parse_row


# ---------------------------------------------------------------------------
# Fixtures / helpers
# ---------------------------------------------------------------------------


def _make_client() -> HermanClient:
    return HermanClient(base_url="http://localhost:8765", timeout=5.0)


def _valid_row_dict(**overrides) -> dict:
    base = {
        "event_id": "summary.2026-09-16",
        "kind": "morning_summary",
        "fire_at": "2026-09-16T07:00:00-04:00",
        "tz": "America/New_York",
        "body": "Good morning. Today: test.",
        "status": "pending",
    }
    base.update(overrides)
    return base


def _mock_response(json_data, status_code: int = 200) -> mock.MagicMock:
    resp = mock.MagicMock(spec=httpx.Response)
    resp.status_code = status_code
    resp.json.return_value = json_data
    resp.raise_for_status.return_value = None
    if status_code >= 400:
        resp.raise_for_status.side_effect = httpx.HTTPStatusError(
            f"HTTP {status_code}",
            request=mock.MagicMock(),
            response=resp,
        )
    return resp


# ---------------------------------------------------------------------------
# Tests: ReminderRow properties
# ---------------------------------------------------------------------------


class TestReminderRowProperties:
    def _make_row(self, event_id="ev.abc", kind="morning_summary") -> ReminderRow:
        return ReminderRow(
            event_id=event_id,
            kind=kind,
            fire_at=datetime(2026, 9, 16, 7, 0, 0, tzinfo=timezone.utc),
            body="Test body",
            tz="America/New_York",
        )

    def test_identifier_format(self):
        row = self._make_row(event_id="summary.2026-09-16", kind="morning_summary")
        assert row.identifier == "summary.2026-09-16:morning_summary"

    def test_identifier_includes_kind(self):
        row = self._make_row(event_id="ev.abc", kind="strike_0")
        assert row.identifier == "ev.abc:strike_0"

    def test_subtitle_morning_summary(self):
        row = self._make_row(kind="morning_summary")
        assert row.subtitle == "Morning summary"

    def test_subtitle_heads_up_30(self):
        row = self._make_row(kind="heads_up_30")
        assert row.subtitle == "30-min heads-up"

    def test_subtitle_pre_5(self):
        row = self._make_row(kind="pre_5")
        assert row.subtitle == "5-min heads-up"

    def test_subtitle_strike_0(self):
        row = self._make_row(kind="strike_0")
        assert row.subtitle == "Strike 1"

    def test_subtitle_strike_5(self):
        row = self._make_row(kind="strike_5")
        assert row.subtitle == "Strike 2"

    def test_subtitle_strike_10(self):
        row = self._make_row(kind="strike_10")
        assert row.subtitle == "Strike 3"

    def test_subtitle_strike_15(self):
        row = self._make_row(kind="strike_15")
        assert row.subtitle == "Strike 4"

    def test_subtitle_unknown_kind_fallback(self):
        row = self._make_row(kind="some_custom_kind")
        # Falls back to title-cased version of kind
        assert row.subtitle == "Some Custom Kind"


# ---------------------------------------------------------------------------
# Tests: _parse_row helper
# ---------------------------------------------------------------------------


class TestParseRow:
    def test_valid_row_parsed(self):
        raw = _valid_row_dict()
        row = _parse_row(raw, 0)
        assert row is not None
        assert row.event_id == "summary.2026-09-16"
        assert row.kind == "morning_summary"
        assert row.fire_at.tzinfo is not None
        assert row.body == "Good morning. Today: test."
        assert row.tz == "America/New_York"

    def test_missing_event_id_returns_none(self):
        raw = _valid_row_dict()
        del raw["event_id"]
        assert _parse_row(raw, 0) is None

    def test_empty_event_id_returns_none(self):
        raw = _valid_row_dict(event_id="")
        assert _parse_row(raw, 0) is None

    def test_missing_kind_returns_none(self):
        raw = _valid_row_dict()
        del raw["kind"]
        assert _parse_row(raw, 0) is None

    def test_missing_fire_at_returns_none(self):
        raw = _valid_row_dict()
        del raw["fire_at"]
        assert _parse_row(raw, 0) is None

    def test_none_fire_at_returns_none(self):
        raw = _valid_row_dict(fire_at=None)
        assert _parse_row(raw, 0) is None

    def test_unparseable_fire_at_returns_none(self):
        raw = _valid_row_dict(fire_at="not-a-date")
        assert _parse_row(raw, 0) is None

    def test_naive_fire_at_returns_none(self):
        # ISO 8601 without tz info → naive datetime → should be rejected
        raw = _valid_row_dict(fire_at="2026-09-16T07:00:00")
        assert _parse_row(raw, 0) is None

    def test_not_a_dict_returns_none(self):
        assert _parse_row("string", 0) is None
        assert _parse_row(42, 0) is None
        assert _parse_row(None, 0) is None
        assert _parse_row([], 0) is None

    def test_missing_body_defaults_empty_string(self):
        raw = _valid_row_dict()
        del raw["body"]
        row = _parse_row(raw, 0)
        assert row is not None
        assert row.body == ""

    def test_missing_tz_defaults_utc(self):
        raw = _valid_row_dict()
        del raw["tz"]
        row = _parse_row(raw, 0)
        assert row is not None
        assert row.tz == "UTC"


# ---------------------------------------------------------------------------
# Tests: HermanClient.fetch_upcoming — happy path
# ---------------------------------------------------------------------------


class TestFetchUpcomingHappyPath:
    @mock.patch("httpx.get")
    def test_returns_parsed_rows(self, mock_get):
        mock_get.return_value = _mock_response([_valid_row_dict()])
        client = _make_client()
        rows = client.fetch_upcoming()
        assert len(rows) == 1
        assert rows[0].event_id == "summary.2026-09-16"

    @mock.patch("httpx.get")
    def test_multiple_rows(self, mock_get):
        mock_get.return_value = _mock_response([
            _valid_row_dict(event_id="ev.a", kind="morning_summary"),
            _valid_row_dict(event_id="ev.a", kind="strike_0"),
            _valid_row_dict(event_id="ev.b", kind="heads_up_30"),
        ])
        client = _make_client()
        rows = client.fetch_upcoming()
        assert len(rows) == 3

    @mock.patch("httpx.get")
    def test_empty_list(self, mock_get):
        mock_get.return_value = _mock_response([])
        client = _make_client()
        rows = client.fetch_upcoming()
        assert rows == []


# ---------------------------------------------------------------------------
# Tests: HermanClient.fetch_upcoming — network errors
# ---------------------------------------------------------------------------


class TestFetchUpcomingNetworkErrors:
    @mock.patch("httpx.get", side_effect=httpx.TimeoutException("timed out"))
    def test_timeout_returns_empty_list(self, mock_get):
        client = _make_client()
        rows = client.fetch_upcoming()
        assert rows == []

    @mock.patch("httpx.get", side_effect=httpx.ConnectError("connection refused"))
    def test_connection_refused_returns_empty_list(self, mock_get):
        client = _make_client()
        rows = client.fetch_upcoming()
        assert rows == []

    @mock.patch("httpx.get")
    def test_http_500_returns_empty_list(self, mock_get):
        mock_get.return_value = _mock_response({}, status_code=500)
        client = _make_client()
        rows = client.fetch_upcoming()
        assert rows == []

    @mock.patch("httpx.get")
    def test_http_404_returns_empty_list(self, mock_get):
        mock_get.return_value = _mock_response({}, status_code=404)
        client = _make_client()
        rows = client.fetch_upcoming()
        assert rows == []

    @mock.patch("httpx.get")
    def test_json_parse_error_returns_empty_list(self, mock_get):
        resp = mock.MagicMock(spec=httpx.Response)
        resp.status_code = 200
        resp.raise_for_status.return_value = None
        resp.json.side_effect = ValueError("not json")
        mock_get.return_value = resp
        client = _make_client()
        rows = client.fetch_upcoming()
        assert rows == []

    @mock.patch("httpx.get")
    def test_json_dict_not_list_returns_empty_list(self, mock_get):
        mock_get.return_value = _mock_response({"error": "unexpected"})
        client = _make_client()
        rows = client.fetch_upcoming()
        assert rows == []


# ---------------------------------------------------------------------------
# Tests: HermanClient.fetch_upcoming — partial malformed rows
# ---------------------------------------------------------------------------


class TestFetchUpcomingPartialMalformed:
    @mock.patch("httpx.get")
    def test_valid_rows_returned_despite_malformed(self, mock_get):
        mock_get.return_value = _mock_response([
            _valid_row_dict(event_id="ev.good", kind="morning_summary"),
            {"event_id": "ev.bad"},  # missing fire_at
            _valid_row_dict(event_id="ev.also_good", kind="strike_0"),
        ])
        client = _make_client()
        rows = client.fetch_upcoming()
        assert len(rows) == 2
        ids = {r.event_id for r in rows}
        assert "ev.good" in ids
        assert "ev.also_good" in ids

    @mock.patch("httpx.get")
    def test_all_malformed_returns_empty(self, mock_get):
        mock_get.return_value = _mock_response([
            {"event_id": "ev.a"},  # missing fire_at
            {"kind": "strike_0"},  # missing event_id
        ])
        client = _make_client()
        rows = client.fetch_upcoming()
        assert rows == []
