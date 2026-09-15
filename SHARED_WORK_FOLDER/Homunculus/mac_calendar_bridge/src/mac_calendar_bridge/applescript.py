"""
applescript.py — Subprocess wrapper around osascript for Calendar.app.

macOS-only at runtime. On Linux, all functions raise NotImplementedError.
Tests mock subprocess.run; never invoke real osascript in automated tests.

Design:
- Calendar name is configurable (default: "Homunculus").
- Every event gets url = "homunculus://event/<event_id>" for deduplication.
- Date format: AppleScript expects full weekday name + "at" separator,
  e.g. 'date "Monday, September 15, 2026 at 9:00 AM"'.
- Calendar "Homunculus" must be created manually in Calendar.app (iCloud
  account) before starting the bridge. See docs/FIRST_RUN.md, Step 1.
- Calendar.app's AppleScript dictionary has NO "account" term — `tell account`
  is invalid syntax (Calendar.app is not Mail or Contacts). All calendars are
  a single flat namespace; we address them by name only.
"""

from __future__ import annotations

import logging
import subprocess
import sys
from datetime import datetime
from zoneinfo import ZoneInfo

from .vault_reader import EventRecord

log = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Platform guard
# ---------------------------------------------------------------------------

def _require_darwin(fn_name: str) -> None:
    if sys.platform != "darwin":
        raise NotImplementedError(
            f"mac_calendar_bridge.applescript.{fn_name} requires macOS"
        )


# ---------------------------------------------------------------------------
# Date formatting
# ---------------------------------------------------------------------------

# Full weekday names in the order Python's datetime returns them (0=Monday)
_WEEKDAY_NAMES = [
    "Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"
]

_MONTH_NAMES = [
    "", "January", "February", "March", "April", "May", "June",
    "July", "August", "September", "October", "November", "December",
]


def format_applescript_date(dt: datetime, tz: str) -> str:
    """
    Format a datetime for AppleScript's ``date`` coercion.

    AppleScript is locale-sensitive about date strings. The format that works
    reliably on US English macOS (System Preferences → Language & Region →
    English) is::

        "Wednesday, September 18, 2026 at 10:00 AM"

    We explicitly request 12-hour AM/PM rather than 24h because AppleScript's
    ``date`` coercion in many locale configs requires the AM/PM form.

    Args:
        dt:  An aware datetime (any timezone).
        tz:  IANA zone name to express the time in (e.g. "America/New_York").

    Returns:
        A string suitable for embedding in ``date "..."`` in AppleScript.
    """
    local = dt.astimezone(ZoneInfo(tz))
    weekday = _WEEKDAY_NAMES[local.weekday()]
    month = _MONTH_NAMES[local.month]
    hour24 = local.hour
    minute = local.minute
    am_pm = "AM" if hour24 < 12 else "PM"
    hour12 = hour24 % 12 or 12
    return f"{weekday}, {month} {local.day}, {local.year} at {hour12}:{minute:02d} {am_pm}"


# ---------------------------------------------------------------------------
# Low-level osascript runner
# ---------------------------------------------------------------------------

class AppleScriptError(Exception):
    """Raised when osascript exits non-zero."""


def run_applescript(script: str, timeout: int = 30) -> str:
    """
    Run *script* via ``osascript -e`` and return stdout stripped.

    Args:
        script:  Multi-line AppleScript source.
        timeout: Seconds before subprocess.TimeoutExpired (default 30).

    Raises:
        AppleScriptError: if osascript exits with a non-zero code.
        NotImplementedError: on non-Darwin platforms.
    """
    _require_darwin("run_applescript")

    log.debug("osascript:\n%s", script)
    try:
        result = subprocess.run(
            ["osascript", "-e", script],
            capture_output=True,
            text=True,
            timeout=timeout,
        )
    except subprocess.TimeoutExpired as exc:
        raise AppleScriptError(f"osascript timed out after {timeout}s") from exc

    if result.returncode != 0:
        stderr = result.stderr.strip()
        raise AppleScriptError(
            f"osascript exited {result.returncode}: {stderr}"
        )

    stdout = result.stdout.strip()
    log.debug("osascript result: %r", stdout)
    return stdout


# ---------------------------------------------------------------------------
# Calendar verification (replaces ensure_calendar — v0.1.2)
# ---------------------------------------------------------------------------

def verify_calendar_exists(calendar_name: str) -> bool:
    """
    Return True if a calendar named *calendar_name* exists in Calendar.app.

    Calendar.app's AppleScript dictionary has no "account" concept — all
    calendars (iCloud, local, subscriptions) share one flat namespace.
    This function simply tests existence by name.

    If it returns False, the caller should log an actionable error telling
    the user to create the calendar manually and exit gracefully — NOT
    try to create it programmatically (Calendar.app cannot be told which
    account to use from AppleScript; `make new calendar` always creates
    in the local "On My Mac" store, not iCloud).

    Args:
        calendar_name: Name of the calendar to check (e.g. "Homunculus").

    Returns:
        True if the calendar exists, False otherwise.

    Raises:
        NotImplementedError: on non-Darwin platforms.
        AppleScriptError: if the osascript call fails unexpectedly.
    """
    _require_darwin("verify_calendar_exists")

    script = f"""
tell application "Calendar"
    return exists calendar "{calendar_name}"
end tell
""".strip()

    log.debug("Checking if calendar '%s' exists", calendar_name)
    raw = run_applescript(script)
    return raw.lower() == "true"


# ---------------------------------------------------------------------------
# Event queries
# ---------------------------------------------------------------------------

def query_pushed_event_ids(
    calendar_name: str,
    date_str: str,
) -> list[str]:
    """
    Return a list of homunculus event_ids already in Calendar.app on *date_str*.

    Queries the calendar for events whose URL starts with ``homunculus://event/``.
    Used for the slow-but-authoritative idempotency check.

    Calendar.app resolves calendars by name across all accounts — no account
    scoping is needed or supported in AppleScript.

    Args:
        calendar_name: Name of the Homunculus calendar.
        date_str:      AppleScript-formatted date string for the target day,
                       e.g. ``"Monday, September 15, 2026 at 12:00 AM"``.

    Returns:
        List of event_id strings (extracted from the URL suffix).

    Raises:
        NotImplementedError: on non-Darwin platforms.
        AppleScriptError: if the osascript call fails.
    """
    _require_darwin("query_pushed_event_ids")

    script = f"""
set result to {{}}
tell application "Calendar"
    tell calendar "{calendar_name}"
        set dayStart to date "{date_str}"
        set dayEnd to dayStart + (24 * 60 * 60)
        set evts to (every event whose start date >= dayStart and start date < dayEnd)
        repeat with evt in evts
            try
                set evtUrl to url of evt
                if evtUrl starts with "homunculus://event/" then
                    set end of result to evtUrl
                end if
            end try
        end repeat
    end tell
end tell
return result
""".strip()

    raw = run_applescript(script)
    # osascript returns a comma-separated list for AppleScript lists
    urls = [u.strip() for u in raw.split(",") if u.strip().startswith("homunculus://event/")]
    ids = [u.removeprefix("homunculus://event/") for u in urls]
    log.debug("query_pushed_event_ids on %s: found %d homunculus events", date_str, len(ids))
    return ids


# ---------------------------------------------------------------------------
# Event creation
# ---------------------------------------------------------------------------

def push_event(event: EventRecord, calendar_name: str) -> None:
    """
    Create *event* in Calendar.app under *calendar_name*.

    Sets the event's URL to ``homunculus://event/<event_id>`` for deduplication.
    The calendar must already exist — call verify_calendar_exists() at startup
    and exit if it returns False. See docs/FIRST_RUN.md for how to create it.

    Calendar.app resolves *calendar_name* across all accounts — AppleScript
    cannot scope to a specific account (Calendar.app has no "account" term in
    its dictionary). The user controls which account the calendar lives in by
    creating it manually; once created, any `tell calendar "<name>"` call reaches
    it regardless of which account hosts it.

    Args:
        event:         The EventRecord to push.
        calendar_name: Name of the target calendar (e.g. "Homunculus").

    Raises:
        NotImplementedError: on non-Darwin platforms.
        AppleScriptError: if the osascript call fails.
    """
    _require_darwin("push_event")

    starts_str = format_applescript_date(event.starts_at, event.tz)
    ends_str = format_applescript_date(event.ends_at, event.tz)
    # Use display_title (strips [handle]/[handle!] vault markers) so the
    # Calendar surface shows "✓ ..." or "🔥 ..." instead of raw brackets.
    title_escaped = event.display_title.replace('"', '\\"')
    url = event.homunculus_url

    script = f"""
tell application "Calendar"
    tell calendar "{calendar_name}"
        make new event with properties {{summary:"{title_escaped}", start date:date "{starts_str}", end date:date "{ends_str}", url:"{url}"}}
    end tell
end tell
""".strip()

    log.info(
        "Pushing event '%s' (vault title: %r) (%s) → Calendar '%s'",
        event.display_title,
        event.title,
        event.event_id,
        calendar_name,
    )
    run_applescript(script)
    log.info("Event '%s' pushed successfully", event.event_id)
