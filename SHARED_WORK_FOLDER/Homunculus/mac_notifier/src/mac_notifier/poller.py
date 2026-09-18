"""
poller.py — Main poll loop for mac_notifier.

Every NOTIFIER_POLL_INTERVAL seconds (default 60):
  1. GET /reminders/upcoming from Herman.
  2. For each row, check if fire_at is within the grace window of now.
  3. If due and not already fired: fire notification + mark fired.
  4. Log every skip decision at DEBUG or INFO (no silent drops).

Grace-window logic (generous by design — reliability over speed):
    A row is "due" if:
        now - grace_window <= fire_at <= now + grace_window
    Default grace_window = 90 seconds.

    "Missed" case (fire_at < now - grace_window): logged at INFO.
    "Future" case (fire_at > now + grace_window): logged at DEBUG (normal).
    "Already fired": logged at DEBUG.

Fail-loudly contract:
    - Herman unreachable → log ERROR, keep polling. No crash-loop.
    - Malformed row → log DEBUG, skip. No crash.
    - osascript failure → log ERROR, do NOT mark fired (will retry next cycle).
    - State-file write failure → log ERROR, still mark in-memory (best effort).
"""

from __future__ import annotations

import logging
import time
from datetime import datetime, timedelta, timezone

from .applescript import AppleScriptError, fire_notification
from .config import Config
from .herman_client import HermanClient, ReminderRow
from .state import FiredState

log = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Due-row evaluation
# ---------------------------------------------------------------------------


def is_due(row: ReminderRow, now: datetime, grace_window: int) -> bool:
    """
    Return True if *row* is within the grace window of *now*.

    Args:
        row:          The reminder row to evaluate.
        now:          Current time (timezone-aware, UTC recommended).
        grace_window: Seconds on each side of fire_at to consider "due".

    Returns:
        True if now - grace_window <= fire_at <= now + grace_window.
    """
    delta = timedelta(seconds=grace_window)
    return (now - delta) <= row.fire_at <= (now + delta)


def classify_row(row: ReminderRow, now: datetime, grace_window: int) -> str:
    """
    Classify a row relative to now.

    Returns one of: "due", "future", "missed".
    """
    delta = timedelta(seconds=grace_window)
    if row.fire_at > now + delta:
        return "future"
    if row.fire_at < now - delta:
        return "missed"
    return "due"


# ---------------------------------------------------------------------------
# Single poll cycle
# ---------------------------------------------------------------------------


def run_poll_cycle(
    client: HermanClient,
    state: FiredState,
    grace_window: int,
    now: datetime | None = None,
) -> dict[str, int]:
    """
    Execute one poll cycle: fetch rows, evaluate, fire due notifications.

    Args:
        client:       HermanClient instance for fetching rows.
        state:        FiredState instance for dedup.
        grace_window: Grace window in seconds.
        now:          Override "now" for testing. Defaults to datetime.now(utc).

    Returns:
        A dict of counts: {"fetched", "fired", "skipped_fired", "skipped_future",
        "skipped_missed", "skipped_malformed", "errors"}.
    """
    if now is None:
        now = datetime.now(timezone.utc)

    counts: dict[str, int] = {
        "fetched": 0,
        "fired": 0,
        "skipped_fired": 0,
        "skipped_future": 0,
        "skipped_missed": 0,
        "skipped_malformed": 0,
        "errors": 0,
    }

    rows = client.fetch_upcoming()
    counts["fetched"] = len(rows)

    for row in rows:
        classification = classify_row(row, now, grace_window)

        if classification == "future":
            log.debug(
                "SKIP future: %s (fire_at=%s, now=%s)",
                row.identifier,
                row.fire_at.isoformat(),
                now.isoformat(),
            )
            counts["skipped_future"] += 1
            continue

        if classification == "missed":
            log.info(
                "SKIP missed: %s fired_at=%s is %.0fs in the past (grace=%ds) — "
                "notification window expired",
                row.identifier,
                row.fire_at.isoformat(),
                (now - row.fire_at).total_seconds(),
                grace_window,
            )
            counts["skipped_missed"] += 1
            continue

        # classification == "due"
        if state.is_fired(row.identifier):
            log.debug("SKIP already-fired: %s", row.identifier)
            counts["skipped_fired"] += 1
            continue

        # Fire it.
        log.info(
            "FIRE: %s (kind=%s, fire_at=%s)",
            row.identifier,
            row.kind,
            row.fire_at.isoformat(),
        )
        try:
            fire_notification(
                body=row.body,
                subtitle=row.subtitle,
            )
        except NotImplementedError:
            # Linux / non-Darwin platform — log and mark fired to avoid
            # infinite retry on a platform that can't fire notifications.
            log.warning(
                "Platform does not support osascript notifications; "
                "marking %s as fired to prevent retry",
                row.identifier,
            )
            state.mark_fired(row.identifier)
            counts["fired"] += 1
            continue
        except AppleScriptError as exc:
            log.error(
                "osascript failed for %s: %s — will retry next cycle",
                row.identifier,
                exc,
            )
            counts["errors"] += 1
            continue

        # Mark fired only after successful notification.
        state.mark_fired(row.identifier)
        counts["fired"] += 1
        log.info("FIRED: %s → notification delivered", row.identifier)

    return counts


# ---------------------------------------------------------------------------
# Main loop
# ---------------------------------------------------------------------------


def main() -> None:
    """
    Entry point for mac_notifier.

    Reads config from environment, sets up logging, and runs the poll loop
    indefinitely. Designed to be run under launchd (KeepAlive=true) or
    systemd (Restart=always).
    """
    from .config import configure_logging, Config

    cfg = Config.from_env()
    configure_logging(log_level=cfg.log_level, log_file=cfg.log_file)

    log.info(
        "mac_notifier starting — herman=%s poll=%ds grace=%ds state=%s",
        cfg.herman_url,
        cfg.poll_interval,
        cfg.grace_window,
        cfg.state_file,
    )

    client = HermanClient(base_url=cfg.herman_url)
    state = FiredState(state_file=cfg.state_file)

    log.info("State loaded: %d previously fired identifiers", state.count())

    while True:
        try:
            counts = run_poll_cycle(
                client=client,
                state=state,
                grace_window=cfg.grace_window,
            )
            log.info(
                "Poll cycle: fetched=%d fired=%d skipped(fired=%d future=%d missed=%d) errors=%d",
                counts["fetched"],
                counts["fired"],
                counts["skipped_fired"],
                counts["skipped_future"],
                counts["skipped_missed"],
                counts["errors"],
            )
        except Exception as exc:  # noqa: BLE001
            # Belt-and-suspenders: the poll cycle should never raise, but if
            # it does (e.g. a bug we haven't caught), keep the loop alive.
            log.error("Unexpected error in poll cycle: %s", exc, exc_info=True)

        log.debug("Sleeping %ds until next poll", cfg.poll_interval)
        time.sleep(cfg.poll_interval)


if __name__ == "__main__":
    main()
