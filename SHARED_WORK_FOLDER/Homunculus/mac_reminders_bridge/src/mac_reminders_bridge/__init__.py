"""
mac_reminders_bridge — Push Herman vault reminders to macOS Reminders.app.

Version 0.1.0 — first release.

Design:
- Watches vault/reminders/*.md for new files (watchdog + 60s periodic sweep).
- Parses YAML frontmatter (id, title, starts_at, tz) from each file.
- Pushes reminder to Reminders.app via AppleScript (make new reminder atomically).
- Idempotency: pushed.jsonl fast-path + event_id-in-body marker slow-path.
- "Homunculus" list must be created manually in Reminders.app under iCloud.
  See docs/FIRST_RUN.md Step 1.

AppleScript note: Reminders.app uses `tell list "Homunculus"` at the top
  level (no account scoping, same as Calendar.app). No `tell account` needed.

Alarm policy: NO `remind me date` alarm is set. Herman's strike chain via
  mac_notifier is the authoritative notification mechanism. Reminders.app is
  a passive display surface only. Setting native alarms would double-fire
  notifications (persona rule #14: the reminder schedule is the engineer's
  signature). Optionally sets `due date` (without alarm) so the reminder
  surfaces in Calendar.app's sidebar.
"""

VERSION = "0.1.0"
