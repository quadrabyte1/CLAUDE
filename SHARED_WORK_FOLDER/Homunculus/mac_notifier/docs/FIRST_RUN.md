# mac_notifier — First Run Guide

**v0.1.0 — 2026-09-15 — Rune**

---

## Prerequisites

- Herman (Homunculus brain) is running on `http://localhost:8765`
- `curl http://localhost:8765/reminders/upcoming` returns a JSON list
- Python 3.11+ available at `python3`

---

## Install

```bash
cd /Volumes/GIT/CLAUDE/SHARED_WORK_FOLDER/Homunculus/mac_notifier
bash deploy/install.sh
```

This:
1. Creates `~/.local/lib/mac_notifier/venv` (boot-volume venv — required because `/Volumes/GIT` is `nosuid`)
2. Installs `mac-notifier` (editable) from the repo
3. Writes `~/.local/bin/mac_notifier.sh` entry point
4. Copies the launchd plist to `~/Library/LaunchAgents/com.homunculus.mac_notifier.plist`

---

## Step 1 — Load the launchd agent

```bash
launchctl load ~/Library/LaunchAgents/com.homunculus.mac_notifier.plist
```

**No Automation permission is required.** Unlike the Calendar and Notes bridges,
`display notification` does not need to control another app — it goes directly
to Notification Center. macOS will not prompt for Automation access.

---

## Step 2 — Verify it started

```bash
launchctl list | grep mac_notifier
```

Expected output: a line with `com.homunculus.mac_notifier` and a PID (not `-`).

---

## Step 3 — Watch the logs

```bash
tail -f /tmp/mac_notifier.log
```

On the first poll cycle you'll see something like:

```
2026-09-15T12:00:00 INFO     [mac_notifier] mac_notifier starting — herman=http://localhost:8765 poll=60s grace=90s state=/Users/fourierflight/.local/share/mac_notifier/fired.jsonl
2026-09-15T12:00:00 INFO     [mac_notifier] State loaded: 0 previously fired identifiers
2026-09-15T12:00:01 INFO     [mac_notifier] Poll cycle: fetched=14 fired=0 skipped(fired=0 future=14 missed=0) errors=0
```

"future=14" means Herman has 14 upcoming reminders, all scheduled for tomorrow — none are due yet. That's correct.

---

## What to expect at 7 AM tomorrow

When Herman's morning summary fires (`fire_at = 2026-09-16T07:00:00-04:00`):

1. The poller sees the row is within the 90-second grace window of `now`
2. Fires a macOS notification:
   - **Title:** Homunculus
   - **Subtitle:** Morning summary
   - **Body:** "Good morning. Today: ..."
   - **Sound:** system default
3. Marks `summary.2026-09-16:morning_summary` as fired in `~/.local/share/mac_notifier/fired.jsonl`
4. Logs `FIRED: summary.2026-09-16:morning_summary → notification delivered`

---

## Known caveat: "Script Editor" branding

Notifications sent via `osascript display notification` appear branded as
**"Script Editor"** (or the name of the calling process) rather than "Homunculus".

This is a **documented macOS limitation** — `display notification` is an
AppleScript command; macOS attributes it to the AppleScript runner process,
not to the invoking script. There is no way to change this branding from
within `osascript` itself.

The mechanism works correctly — the notification appears, sounds, and
disappears. Only the app name in the notification header is wrong.

**v0.2 fix options:**
- Install `terminal-notifier` via Homebrew (`brew install terminal-notifier`)
  and switch the notifier to call `terminal-notifier -title "Homunculus" ...`
- Ship mac_notifier as a proper `.app` bundle with its own bundle ID —
  the most correct fix, allows action buttons too

The v0.1 approach is the right call for tonight. We can brand it properly in v0.2.

---

## If 7 AM has already passed when you wake up

The morning summary's `fire_at` will be outside the 90-second grace window.
The poller will log it as:

```
SKIP missed: summary.2026-09-16:morning_summary fired_at=... is Xs in the past (grace=90s) — notification window expired
```

No notification fires for missed rows. The next natural trigger will be the
T-30 heads-up for one of your Wednesday events (e.g., 3 PM handle → heads-up
fires at 2:30 PM).

**To force a test notification right now:**
Run `curl http://localhost:8765/reminders/upcoming` and check which `fire_at`
value is closest to the current time. The poller will pick it up on the next
60-second cycle.

---

## To unload / stop

```bash
launchctl unload ~/Library/LaunchAgents/com.homunculus.mac_notifier.plist
```

---

## Troubleshooting

| Symptom | Likely cause | Fix |
|---------|-------------|-----|
| `launchctl list` shows no PID | plist not loaded or crashed at start | Check `/tmp/mac_notifier_err.log` |
| Log shows `Herman unreachable` | Herman not running | Start Herman: `launchctl list \| grep homunculus_brain` |
| Notifications firing but "Script Editor" branding | Expected v0.1 behavior | See caveat above; v0.2 fixes this |
| Notification fired but no sound | System notification settings | Check System Settings → Notifications |
| `fetched=0` on every cycle | Herman returning empty list | `curl http://localhost:8765/reminders/upcoming` to verify |
