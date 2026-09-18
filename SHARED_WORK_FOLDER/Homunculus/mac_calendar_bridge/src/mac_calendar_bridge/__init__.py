"""
mac_calendar_bridge — Push Herman vault calendar events to macOS Calendar.app.

Version 0.2.0 — semantic scope clarified: calendar events (verb=schedule) only.
  Reminder-type captures (verb=handle, verb=remind) write to vault/reminders/
  and are handled by mac_reminders_bridge. vault/calendar/ is now schedule-only.

  The display_title transform that strips [handle]/[handle!] prefixes is
  retained as a belt-and-suspenders safety net in case any legacy handle event
  slips through the watcher (e.g. files created before the v1.6 migration).

Version history:
  0.1.5 — belt-and-suspenders dup-prevention: query_pushed_event_ids()
           wired into push_if_new(); url-in-make-properties fix
  0.2.0 — semantic scope narrowed to schedule events only
"""

VERSION = "0.2.0"
