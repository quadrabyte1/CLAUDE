# mac_calendar_bridge — First Run Guide

**v0.1.2** — 2026-09-14

This document covers the steps required to go from a fresh install to seeing
Herman vault events appear in Calendar.app.

---

## Prerequisites

- macOS (the bridge is Mac-only; Calendar.app is required)
- Python 3.11 or later (check with `python3 --version`)
- The repo checked out at `/Volumes/GIT/CLAUDE/SHARED_WORK_FOLDER/Homunculus/`

---

## Step 1: Create the "Homunculus" calendar in iCloud (REQUIRED — do this first)

The bridge does **not** create the calendar automatically. Calendar.app's
AppleScript dictionary has no account concept — `make new calendar` always
creates in the local "On My Mac" store, not iCloud, so automation cannot
put it in the right place. You must create it manually, once.

1. Open **Calendar.app**
2. Choose **File → New Calendar**
3. In the submenu, choose **iCloud** (not "On My Mac")
4. Name the calendar exactly: **`Homunculus`**
5. Press **Return**

Verify: in the Calendar sidebar you should see "Homunculus" listed under the
**iCloud** heading (not under "On My Mac").

> If you see "Homunculus" under "On My Mac" instead, delete it and repeat
> Step 1, making sure to choose **iCloud** in the submenu.

---

## Step 2: Run the installer

```bash
cd /Volumes/GIT/CLAUDE/SHARED_WORK_FOLDER/Homunculus/mac_calendar_bridge
bash deploy/install.sh
```

This installs the bridge into a venv at `~/.local/lib/mac_calendar_bridge/venv/`
and writes an entry-point script at `~/.local/bin/mac_calendar_bridge.sh`.
It also copies the launchd plist to `~/Library/LaunchAgents/` but does **not**
load it yet.

---

## Step 3: Grant Automation permission (Calendar.app)

macOS requires explicit user permission for any process to control Calendar.app
via AppleScript. You grant this through System Settings.

**Recommended approach — let macOS prompt you automatically:**

1. Load the plist (see Step 4).
2. macOS will show a permission dialog:
   > "mac_calendar_bridge" wants access to control "Calendar". Allowing
   > control will provide access to documents and data in "Calendar", and
   > to perform actions within that app.
3. Click **OK**.

**Alternative — pre-grant in System Settings:**

1. Open **System Settings → Privacy & Security → Automation**
2. Locate **Terminal** (or whatever shell loaded the plist) in the list.
3. Ensure **Calendar** is checked.

If you deny the prompt by accident:
- Open **System Settings → Privacy & Security → Automation**
- Find `mac_calendar_bridge` or `Terminal` and enable Calendar access
- Then restart the bridge:
  ```bash
  launchctl unload ~/Library/LaunchAgents/com.homunculus.mac_calendar_bridge.plist
  launchctl load   ~/Library/LaunchAgents/com.homunculus.mac_calendar_bridge.plist
  ```

---

## Step 4: Load the launchd agent

```bash
launchctl load ~/Library/LaunchAgents/com.homunculus.mac_calendar_bridge.plist
```

On first load, macOS may show the Automation permission dialog — click **OK**.

---

## Step 5: Verify it started

```bash
launchctl list | grep mac_calendar_bridge
```

You should see a line like:
```
-    0    com.homunculus.mac_calendar_bridge
```
(The `0` means the process exited with code 0; it restarts automatically via
KeepAlive. A positive PID means it's still running.)

Watch the log:
```bash
tail -f /tmp/mac_calendar_bridge.log
```

Expected first-run output:
```
2026-09-14T... INFO     [mac_calendar_bridge] mac_calendar_bridge v0.1.2 starting
2026-09-14T... INFO     [mac_calendar_bridge] Vault: /Volumes/GIT/CLAUDE/.../vault/calendar
2026-09-14T... INFO     [mac_calendar_bridge] Calendar: Homunculus
2026-09-14T... INFO     [mac_calendar_bridge] Cold-boot sweep of .../vault/calendar
2026-09-14T... INFO     [mac_calendar_bridge] Sweep found 2 event(s) in vault
2026-09-14T... INFO     [mac_calendar_bridge] Pushing event 'meeting with myself' (2026-09-15-meeting-with-myself) → Calendar 'Homunculus'
2026-09-14T... INFO     [mac_calendar_bridge] Event '2026-09-15-meeting-with-myself' pushed successfully
2026-09-14T... INFO     [mac_calendar_bridge] Pushing event 'code review with myself' (2026-09-18-code-review-with-myself) → Calendar 'Homunculus'
2026-09-14T... INFO     [mac_calendar_bridge] Event '2026-09-18-code-review-with-myself' pushed successfully
2026-09-14T... INFO     [mac_calendar_bridge] Sweep complete: pushed 2 new event(s)
2026-09-14T... INFO     [mac_calendar_bridge] Watching .../vault/calendar (recursive) …
```

---

## Step 6: Open Calendar.app

You should now see a **Homunculus** calendar under the **iCloud** heading in
the sidebar, with two events:

| Date | Event |
|------|-------|
| Tuesday, September 15, 2026 | meeting with myself (9:00 – 9:30 AM) |
| Friday, September 18, 2026 | code review with myself (10:00 – 10:30 AM) |

---

## Troubleshooting

| Symptom | Likely cause | Fix |
|---------|-------------|-----|
| Log says "Calendar 'Homunculus' does not exist" and bridge exits | Calendar not created yet | Complete Step 1 — create "Homunculus" under iCloud in Calendar.app UI, then reload the bridge |
| Events appear under "On My Mac" instead of iCloud | Calendar was created under the wrong account | Delete the "On My Mac" Homunculus calendar, redo Step 1 choosing iCloud |
| Events not appearing in Calendar | Automation permission denied | System Settings → Privacy → Automation → enable Calendar |
| `osascript exited 1: not allowed` in log | Same as above | Same fix |
| Bridge exits immediately | Python version < 3.11, or venv not built | Re-run `install.sh` with the correct Python |
| Log file empty | Bridge not started or wrong plist path | Check `launchctl list \| grep mac_calendar_bridge` |
| Events don't sync to iPhone | "Homunculus" calendar is not in iCloud | Check Calendar.app sidebar — must be under "iCloud" heading |

---

## Architecture note (why not auto-create?)

Calendar.app's AppleScript dictionary has no "account" term. `tell account "iCloud"`
is a parse error — it works in Mail.app and Contacts.app (which model IMAP/CardDAV
accounts explicitly) but Calendar.app treats all calendars as a single flat namespace.
The only way to programmatically create a calendar and control which account it lands
in would be via Swift + EventKit (the `EKCalendar.source` property). That is a v0.2
candidate; see the [v0.2 roadmap in README.md](../README.md#v02-roadmap).

---

## Backfilling older events

If events were written to the vault before the bridge was installed, the
cold-boot sweep (Step 4) handles backfill automatically. Every event `.md` file
under `vault/calendar/` that has not yet been pushed will be pushed on startup.

---

## Unloading the bridge

```bash
launchctl unload ~/Library/LaunchAgents/com.homunculus.mac_calendar_bridge.plist
```
