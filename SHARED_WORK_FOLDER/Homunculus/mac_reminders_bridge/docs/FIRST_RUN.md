# mac_reminders_bridge — First Run Guide

**v0.1.0** — 2026-09-17

This document covers the steps required to go from a fresh install to seeing
Herman `handle` and `remind` captures appear in Reminders.app.

---

## Prerequisites

- macOS (the bridge is Mac-only; Reminders.app / AppleScript required)
- Python 3.11 or later (check with `python3 --version`)
- The repo checked out at `/Volumes/GIT/CLAUDE/SHARED_WORK_FOLDER/Homunculus/`
- Herman brain running and writing to `vault/reminders/`

---

## Step 1: Create the "Homunculus" list in Reminders.app (REQUIRED — do this first)

The bridge does **not** create the list automatically. You must create it manually,
once. Reminders.app uses a flat list namespace — no account scoping is needed
in AppleScript, but the list must exist before the bridge can push to it.

1. Open **Reminders.app**
2. Choose **File → New List**
3. In the sheet that appears, select the **iCloud** account (not "On My Mac")
4. Name the list exactly: **`Homunculus`**
5. Click **OK**

Verify: in the Reminders sidebar you should see "Homunculus" listed under the
**iCloud** section.

> If you see "Homunculus" under "On My Mac" instead, delete it and repeat
> Step 1, making sure to select **iCloud** in the account sheet.

---

## Step 2: Run the installer

```bash
cd /Volumes/GIT/CLAUDE/SHARED_WORK_FOLDER/Homunculus/mac_reminders_bridge
bash deploy/install.sh
```

This installs the bridge into a venv at `~/.local/lib/mac_reminders_bridge/venv/`
and writes an entry-point script at `~/.local/bin/mac_reminders_bridge.sh`.
It also copies the launchd plist to `~/Library/LaunchAgents/` but does **not**
load it yet.

---

## Step 3: Load the launchd agent

```bash
launchctl load ~/Library/LaunchAgents/com.homunculus.mac_reminders_bridge.plist
```

On first load, macOS will show an Automation permission dialog:

> "mac_reminders_bridge" wants access to control "Reminders". Allowing
> control will provide access to documents and data in "Reminders", and
> to perform actions within that app.

Click **OK**.

---

## Step 4: Verify it started

```bash
launchctl list | grep mac_reminders_bridge
```

You should see a line like:
```
12345    0    com.homunculus.mac_reminders_bridge
```
(A positive PID in the first column means the process is running.)

Watch the log:
```bash
tail -f /tmp/mac_reminders_bridge.log
```

Expected first-run output (with existing vault/reminders/ entries):
```
2026-09-17T... INFO  mac_reminders_bridge v0.1.0 starting
2026-09-17T... INFO  Vault reminders: .../vault/reminders
2026-09-17T... INFO  Reminders list: Homunculus
2026-09-17T... INFO  Cold-boot sweep of .../vault/reminders
2026-09-17T... INFO  Sweep found 3 reminder(s) in vault
2026-09-17T... INFO  Pushing reminder 'call the vet' (event_id: 2026-09-16-call-the-vet) → Reminders list 'Homunculus'
2026-09-17T... INFO  Reminder '2026-09-16-call-the-vet' pushed successfully
...
2026-09-17T... INFO  Sweep complete: pushed 3 new reminder(s)
2026-09-17T... INFO  Watching .../vault/reminders …
2026-09-17T... INFO  Periodic sweep started (interval=60s)
```

---

## Step 5: Open Reminders.app

You should now see the **Homunculus** list in the sidebar with your captures listed
as reminders. Each reminder will:

- **Name**: the plain subject (e.g. "call the vet") — no `[handle]` prefix
- **Notes**: the capture body + `[herman-id:<event-id>]` sentinel for deduplication
- **URL**: `homunculus://reminder/<event-id>` (internal, used for idempotency)
- **Due date**: shown if the capture included a `starts_at` time, otherwise absent
- **No alarm**: Herman's mac_notifier is the authoritative notification mechanism;
  no native Reminders alarm fires (avoids double-fire)

---

## Troubleshooting

| Symptom | Likely cause | Fix |
|---------|-------------|-----|
| Log says "Reminders list 'Homunculus' does not exist" and bridge exits | List not created yet | Complete Step 1 — create "Homunculus" under iCloud in Reminders.app UI, then reload |
| Reminders appear in a different list or account | List is under "On My Mac" instead of iCloud | Delete the wrong list, redo Step 1 choosing iCloud |
| `osascript exited 1: not allowed` in log | Automation permission denied | System Settings → Privacy & Security → Automation → enable Reminders |
| `-1712 AppleEvent timed out` in log | Reminders.app not running or permission dialog waiting | Open Reminders.app, check for permission prompts |
| Bridge exits immediately with exit code 1 | List doesn't exist | Follow Step 1 |
| Reminders pushed twice | pushed.jsonl was deleted; slow path healed it | Normal — self-heal is working correctly |
| Bridge exits: Python not found | venv not built or Python version mismatch | Re-run `install.sh --venv-python /path/to/python3.11` |
| `nosuid` error in log | Trying to run script from /Volumes/GIT | Use the boot-volume entry point (install.sh handles this) |

---

## Idempotency design

The bridge uses a 3-step belt-and-suspenders approach to avoid duplicate reminders:

1. **Fast path** — in-memory set backed by `pushed.jsonl`. O(1) lookup; no Reminders.app round-trip.
2. **Slow path** — on each new file, queries Reminders.app for a reminder whose URL is `homunculus://reminder/<event-id>`. If found, self-heals `pushed.jsonl` and skips the push. This handles the case where `pushed.jsonl` is deleted or reset.
3. **Push** — only if both fast and slow paths say "not present".

Unlike Notes.app (which has no `url` property), Reminders.app exposes a `url` property in its AppleScript dictionary, enabling reliable URL-based deduplication.

---

## Migrating existing handle captures

If handle/remind captures were written to `vault/calendar/` before v1.6.0 of Herman,
use the migration script to move them to `vault/reminders/`:

```bash
# Dry run (safe — shows what would happen)
python scripts/migrate_handles_from_calendar.py

# Apply the migration
python scripts/migrate_handles_from_calendar.py --apply
```

See [`scripts/migrate_handles_from_calendar.py`](../scripts/migrate_handles_from_calendar.py)
for details.

---

## Unloading the bridge

```bash
launchctl unload ~/Library/LaunchAgents/com.homunculus.mac_reminders_bridge.plist
```
