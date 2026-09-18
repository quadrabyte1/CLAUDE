"""
herman_client.py — HTTP client for Herman's /reminders/upcoming endpoint.

Uses httpx (already in the Homunculus family dependency set). Single
synchronous GET per poll cycle; no async needed for a 60-second poller.

Herman's /reminders/upcoming response shape (verified 2026-09-15):
    [
      {
        "event_id":  "summary.2026-09-16",          # unique identifier for this reminder row
        "kind":      "morning_summary",              # morning_summary | heads_up_30 | pre_5 | strike_0..15
        "fire_at":   "2026-09-16T07:00:00-04:00",   # ISO 8601 with tz offset
        "tz":        "America/New_York",             # IANA zone
        "body":      "Good morning. Today: ...",     # human-readable notification body
        "status":    "pending"                       # pending | fired | acked
      },
      ...
    ]

The identifier for dedup purposes is built as "<event_id>:<kind>" because
the same event_id appears with multiple kinds (heads_up_30, pre_5, strike_0…).
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from datetime import datetime
from typing import Any

import httpx

log = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Data model for a single reminder row
# ---------------------------------------------------------------------------

_KIND_LABELS: dict[str, str] = {
    "morning_summary": "Morning summary",
    "heads_up_30": "30-min heads-up",
    "pre_5": "5-min heads-up",
    "strike_0": "Strike 1",
    "strike_5": "Strike 2",
    "strike_10": "Strike 3",
    "strike_15": "Strike 4",
}


@dataclass
class ReminderRow:
    """A single row from Herman's /reminders/upcoming response."""

    event_id: str
    kind: str
    fire_at: datetime        # always timezone-aware
    body: str
    tz: str

    @property
    def identifier(self) -> str:
        """
        Unique identifier for dedup: "<event_id>:<kind>".

        The same event_id appears with different kinds (heads_up_30, pre_5,
        strike_0, …), so we must scope the dedup key to kind as well.
        """
        return f"{self.event_id}:{self.kind}"

    @property
    def subtitle(self) -> str:
        """Human-readable subtitle derived from kind."""
        return _KIND_LABELS.get(self.kind, self.kind.replace("_", " ").title())


# ---------------------------------------------------------------------------
# Parse helpers
# ---------------------------------------------------------------------------


def _parse_row(raw: Any, row_index: int) -> ReminderRow | None:
    """
    Parse a single raw dict from the JSON response into a ReminderRow.

    Returns None (and logs at DEBUG) if the row is malformed.
    """
    if not isinstance(raw, dict):
        log.debug("Row %d: not a dict (%r); skipping", row_index, type(raw).__name__)
        return None

    event_id = raw.get("event_id")
    kind = raw.get("kind")
    fire_at_str = raw.get("fire_at")
    body = raw.get("body", "")
    tz = raw.get("tz", "UTC")

    if not event_id:
        log.debug("Row %d: missing 'event_id'; skipping (raw=%r)", row_index, raw)
        return None
    if not kind:
        log.debug("Row %d (%s): missing 'kind'; skipping", row_index, event_id)
        return None
    if not fire_at_str:
        log.debug("Row %d (%s): missing 'fire_at'; skipping", row_index, event_id)
        return None

    try:
        fire_at = datetime.fromisoformat(fire_at_str)
    except (ValueError, TypeError) as exc:
        log.debug(
            "Row %d (%s): cannot parse fire_at=%r (%s); skipping",
            row_index,
            event_id,
            fire_at_str,
            exc,
        )
        return None

    if fire_at.tzinfo is None:
        log.debug(
            "Row %d (%s): fire_at is naive (no tzinfo); skipping — "
            "all fire_at values must be timezone-aware",
            row_index,
            event_id,
        )
        return None

    return ReminderRow(
        event_id=event_id,
        kind=kind,
        fire_at=fire_at,
        body=body or "",
        tz=tz,
    )


# ---------------------------------------------------------------------------
# Client
# ---------------------------------------------------------------------------


class HermanClient:
    """
    Thin HTTP client for Herman's /reminders/upcoming endpoint.

    Args:
        base_url: Herman's base URL (e.g. "http://localhost:8765").
        timeout:  httpx request timeout in seconds (default 10).
    """

    def __init__(self, base_url: str, timeout: float = 10.0) -> None:
        self._base_url = base_url.rstrip("/")
        self._timeout = timeout

    def fetch_upcoming(self) -> list[ReminderRow]:
        """
        GET /reminders/upcoming?include_fired=false and return parsed rows.

        On any network or HTTP error: logs at ERROR and returns an empty list
        (caller keeps polling; no crash-loop).

        On JSON parse error: logs at ERROR and returns an empty list.

        On individual malformed rows: logs at DEBUG and skips them.
        Remaining valid rows are still returned.
        """
        url = f"{self._base_url}/reminders/upcoming"
        params = {"include_fired": "false"}

        try:
            response = httpx.get(url, params=params, timeout=self._timeout)
            response.raise_for_status()
        except httpx.TimeoutException as exc:
            log.error("Herman unreachable: request timed out (%s)", exc)
            return []
        except httpx.HTTPStatusError as exc:
            log.error(
                "Herman returned HTTP %d for %s",
                exc.response.status_code,
                url,
            )
            return []
        except httpx.RequestError as exc:
            log.error("Herman unreachable: %s", exc)
            return []

        try:
            raw_list = response.json()
        except Exception as exc:
            log.error("Herman response is not valid JSON: %s", exc)
            return []

        if not isinstance(raw_list, list):
            log.error(
                "Herman /reminders/upcoming returned unexpected type %s (expected list)",
                type(raw_list).__name__,
            )
            return []

        rows: list[ReminderRow] = []
        for i, raw in enumerate(raw_list):
            row = _parse_row(raw, i)
            if row is not None:
                rows.append(row)

        log.debug("Fetched %d valid reminder rows from Herman", len(rows))
        return rows
