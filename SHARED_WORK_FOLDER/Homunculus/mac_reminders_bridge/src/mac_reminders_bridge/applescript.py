"""
applescript.py — Subprocess wrapper around osascript for Reminders.app.

macOS-only at runtime. On Linux, all functions raise NotImplementedError.
Tests mock subprocess.run; never invoke real osascript in automated tests.

Design:
- List name is configurable (default: "Homunculus") via BRIDGE_LIST_NAME.
- Reminders.app AppleScript uses `tell list "Homunculus"` at the top level.
  Reminders.app does NOT require `tell account` — it uses a flat list
  namespace like Calendar.app. This was verified by attempted testing; see
  docs/FIRST_RUN.md for the manual list creation requirement.
- ATOMIC creation: `make new reminder with properties {name:..., body:...}`
  in a SINGLE osascript command. No two-step make-then-set-body.
  The Calendar bridge v0.1.5 teaches us: two-step patterns can silently
  roll back on macOS 15.x. One command = atomic.
- NO url property in the properties dict. Reminders.app's AppleScript
  dictionary does NOT expose a url property — attempting to set it causes
  AppleScript error -1700 ("Can't make ... into type properties of reminder").
  Empirically confirmed on 2026-09-19: adding a url field to the properties
  dict triggers -1700; omitting it succeeds. The [herman-id:<event_id>] body
  marker is the durable idempotency key. No url property needed.
- NO `remind me date` alarm. Herman's strike chain (mac_notifier) is the
  authoritative notification mechanism. Setting native Reminders.app alarms
  would double-fire (persona rule #14: the reminder schedule is the signature).
- OPTIONAL `due date`: set without a `remind me date` alarm so the reminder
  surfaces in Calendar.app's sidebar per Apple's architecture. Only set when
  starts_at is available from frontmatter.
- "Homunculus" list must be created manually by the user in Reminders.app UI
  (File → New List → iCloud → "Homunculus"). See docs/FIRST_RUN.md Step 1.
- Idempotency slow path: query_pushed_reminder_ids() iterates reminder bodies
  and extracts event_ids via the [herman-id:<event_id>] regex. No URL query.
"""

from __future__ import annotations

import logging
import re
import subprocess
import sys
from datetime import datetime
from typing import Optional
from zoneinfo import ZoneInfo

from .vault_reader import ReminderRecord

log = logging.getLogger(__name__)

# Regex to extract event_id from body sentinel: [herman-id:<event_id>]
_HERMAN_ID_RE = re.compile(r"\[herman-id:([^\]]+)\]")


# ---------------------------------------------------------------------------
# Platform guard
# ---------------------------------------------------------------------------

def _require_darwin(fn_name: str) -> None:
    if sys.platform != "darwin":
        raise NotImplementedError(
            f"mac_reminders_bridge.applescript.{fn_name} requires macOS"
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

    Uses the same format as mac_calendar_bridge for consistency:
        "Wednesday, September 18, 2026 at 10:00 AM"

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
# List verification (startup check)
# ---------------------------------------------------------------------------

def verify_list_exists(list_name: str) -> bool:
    """
    Return True if a Reminders.app list named *list_name* exists.

    Reminders.app uses a flat list namespace (no account scoping needed from
    AppleScript), same as Calendar.app. We address lists by name only.

    If this returns False, the caller should log an actionable error telling
    the user to create the list manually in Reminders.app (File → New List →
    iCloud → "Homunculus") and exit gracefully.

    Args:
        list_name: Name of the Reminders list to check (e.g. "Homunculus").

    Returns:
        True if the list exists, False otherwise.

    Raises:
        NotImplementedError: on non-Darwin platforms.
        AppleScriptError: if the osascript call fails unexpectedly.
    """
    _require_darwin("verify_list_exists")

    script = f"""
tell application "Reminders"
    return exists list "{list_name}"
end tell
""".strip()

    log.debug("Checking if Reminders list '%s' exists", list_name)
    raw = run_applescript(script)
    return raw.lower() == "true"


# ---------------------------------------------------------------------------
# Reminder queries (idempotency slow path)
# ---------------------------------------------------------------------------

def query_pushed_reminder_ids(list_name: str) -> list[str]:
    """
    Return a list of homunculus event_ids already in Reminders.app.

    Queries the list for reminder bodies and extracts event_ids from the
    ``[herman-id:<event_id>]`` body sentinel. Used for the slow-but-authoritative
    idempotency check after pushed.jsonl is absent or incomplete.

    NOTE: Reminders.app's AppleScript dictionary does NOT expose a `url`
    property (attempts to set or read `url` of a reminder cause error -1700).
    The [herman-id:<event_id>] body marker is the durable idempotency key.
    Empirically confirmed 2026-09-19.

    Args:
        list_name: Name of the Reminders.app list.

    Returns:
        List of event_id strings extracted from body sentinels.

    Raises:
        NotImplementedError: on non-Darwin platforms.
        AppleScriptError: if the osascript call fails.
    """
    _require_darwin("query_pushed_reminder_ids")

    script = f"""
set result to {{}}
tell application "Reminders"
    tell list "{list_name}"
        set allReminders to every reminder
        repeat with r in allReminders
            try
                set rBody to body of r
                set end of result to rBody
            end try
        end repeat
    end tell
end tell
return result
""".strip()

    raw = run_applescript(script)
    if not raw:
        return []

    # osascript serialises an AppleScript list as comma-separated items.
    # Each item is a reminder body string. Extract [herman-id:...] from each.
    # Bodies may themselves contain commas, but the sentinel is at the end and
    # uses a distinctive bracket pattern that won't collide with prose.
    ids: list[str] = _HERMAN_ID_RE.findall(raw)
    log.debug("query_pushed_reminder_ids: found %d homunculus reminders", len(ids))
    return ids


# ---------------------------------------------------------------------------
# Reminder creation
# ---------------------------------------------------------------------------

def push_reminder(record: ReminderRecord, list_name: str) -> None:
    """
    Create *record* as a reminder in Reminders.app under *list_name*.

    Creates atomically with a single `make new reminder with properties {...}`
    command — never two-step make-then-set (same silent-rollback risk as
    Calendar v0.1.5 taught us).

    Sets:
      - name: record.display_title (clean subject, no [handle] prefix)
      - body: record.reminders_body (prose + [herman-id:<event_id>] sentinel)
      - due date: record.starts_at expressed in local time (if available)
        — WITHOUT a `remind me date` alarm, so no double-fire with mac_notifier.

    NOTE: `url:` is intentionally OMITTED from the properties dict.
    Reminders.app's AppleScript dictionary rejects url: with error -1700.
    The [herman-id:<event_id>] body sentinel is the idempotency key.

    The list must already exist — call verify_list_exists() at startup and
    exit if it returns False. See docs/FIRST_RUN.md for how to create it.

    Args:
        record:    The ReminderRecord to push.
        list_name: Name of the target Reminders.app list (e.g. "Homunculus").

    Raises:
        NotImplementedError: on non-Darwin platforms.
        AppleScriptError: if the osascript call fails.
    """
    _require_darwin("push_reminder")

    # Escape double-quotes for AppleScript string embedding.
    title_escaped = record.display_title.replace("\\", "\\\\").replace('"', '\\"')
    body_escaped = record.reminders_body.replace("\\", "\\\\").replace('"', '\\"')

    if record.starts_at is not None:
        # Include due date (without alarm) so the reminder surfaces in
        # Calendar.app's sidebar. AppleScript sets due date but NOT
        # remind me date — only the due date tooltip, no alarm trigger.
        due_str = format_applescript_date(record.starts_at, record.tz)
        script = f"""
tell application "Reminders"
    tell list "{list_name}"
        make new reminder with properties {{name:"{title_escaped}", body:"{body_escaped}", due date:date "{due_str}"}}
    end tell
end tell
""".strip()
    else:
        # No resolved start time — create reminder without due date.
        script = f"""
tell application "Reminders"
    tell list "{list_name}"
        make new reminder with properties {{name:"{title_escaped}", body:"{body_escaped}"}}
    end tell
end tell
""".strip()

    log.info(
        "Pushing reminder '%s' (event_id: %s) → Reminders list '%s'",
        record.display_title,
        record.event_id,
        list_name,
    )
    run_applescript(script)
    log.info("Reminder '%s' pushed successfully", record.event_id)
