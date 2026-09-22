"""
mac_reminders_bridge — Push Herman vault reminders to macOS Reminders.app.

Version 0.1.2 — clean reminder body; remove [herman-id:...] sentinel from UX.

Changes from v0.1.1:
- reminders_body now contains only the raw utterance — no # heading, no
  *Captured ... via Sprite.* caption, no [herman-id:...] sentinel, no blank lines.
- Idempotency slow path changed from body-sentinel extraction (query_pushed_
  reminder_ids) to name-based Reminders.app query (query_pushed_reminder_names).
  Belt-and-suspenders: pushed.jsonl fast-path + name match slow-path.
- cleanup_existing_reminders.py script rewrites existing Reminders.app entries
  to strip sentinel/heading/caption from bodies already pushed under v0.1.1.

Design:
- Watches vault/reminders/*.md for new files (watchdog + 60s periodic sweep).
- Parses YAML frontmatter (id, title, starts_at, tz) from each file.
- Pushes reminder to Reminders.app via AppleScript (make new reminder atomically).
- Idempotency: pushed.jsonl fast-path + name-match slow-path (no body sentinel).
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

VERSION = "0.1.2"
