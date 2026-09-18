# mac_calendar_bridge

**Version:** 0.2.0 | **Status:** Active | **Platform:** macOS only

Herman writes **calendar events** (verb=`schedule`) to `vault/calendar/`.
`mac_calendar_bridge` watches that directory and pushes new events into macOS
Calendar.app via AppleScript, so they appear in Calendar.app and sync to iPhone
via iCloud.

**Scope clarification (v0.2.0):** This bridge handles `verb=schedule` events
**only**. Reminder-type captures (`verb=handle`, `verb=remind`) now write to
`vault/reminders/` and are handled by `mac_reminders_bridge`. The
`[handle]`/`[handle!]` display-title transform is retained as a safety net for
any legacy events that pre-date the v1.6 migration.

---

## Architecture

Herman's brain stays Linux-portable — no AppleScript, no EventKit inside
`Homunculus/brain/`. The bridge is a **separate, Mac-only sibling process**
that only runs on macOS. On Linux it simply doesn't exist; Herman still works.

```
vault/calendar/
    2026-09/
        2026-09-15-meeting-with-myself.md   ← Herman writes this
        2026-09-18-code-review-with-myself.md

mac_calendar_bridge (this project)
    watches vault/calendar/ via watchdog
    parses frontmatter (python-frontmatter)
    checks ~/.local/share/mac_calendar_bridge/pushed.jsonl  (idempotency)
    calls osascript → Calendar.app
    appends to pushed.jsonl
```

Events land in a dedicated **"Homunculus"** calendar in Calendar.app, which
syncs to iPhone via iCloud automatically.

### Key architecture decision (v0.1.2)

Calendar.app's AppleScript dictionary has **no account concept**. The `tell account`
construct that works in Mail.app and Contacts.app is a parse error in Calendar.app
(`-2741: Expected end of line but found ""`). All calendars — iCloud, local,
subscriptions — share one flat namespace and are addressed by name only.

This means the bridge cannot programmatically create a calendar in the iCloud
account. **You create the "Homunculus" calendar manually once in Calendar.app
(File → New Calendar → iCloud → Homunculus).** The bridge then uses it by name.
See [docs/FIRST_RUN.md](docs/FIRST_RUN.md) for exact steps.

---

## What v0.1 does

- **Push-only, one-way, additive.** Events flow vault → Calendar.app only.
- **Cold-boot sweep:** on startup, any vault events not yet pushed are backfilled.
- **Watchdog:** new `.md` files under `vault/calendar/` are pushed as they arrive.
- **Idempotency:** `pushed.jsonl` + URL-field check (`homunculus://event/<id>`)
  prevents duplicate Calendar entries across restarts.
- **Dedicated calendar:** all events go into a "Homunculus" calendar (created
  manually by the user once in the iCloud account). Toggle it on/off in
  Calendar.app without affecting other calendars.
- **Graceful startup check:** verifies the "Homunculus" calendar exists before
  starting the watch loop. If missing, logs an actionable error and exits cleanly
  — launchd's `ThrottleInterval` handles backoff. No crash-loop.

## What v0.1 does NOT do

- **No auto-create calendar.** Calendar.app AppleScript cannot target a specific
  iCloud account. You create the calendar once manually.
- **No delete propagation.** Deleting a vault `.md` file will NOT delete the Calendar entry.
- **No edit propagation.** Editing a vault `.md` file will NOT update the Calendar entry.
- **No two-way sync.** Calendar.app edits are not reflected back to the vault.
- **No native EventKit** (no `pyobjc`). AppleScript is the abstraction boundary.

These are intentional scope limits. See [v0.2 roadmap](#v02-roadmap) below.

---

## Install

```bash
cd Homunculus/mac_calendar_bridge
bash deploy/install.sh
```

See **[docs/FIRST_RUN.md](docs/FIRST_RUN.md)** for the full walkthrough — including
the required manual calendar creation (Step 1) and Automation permission grant.

---

## Configuration

All config via environment variables (set in the plist or your shell):

| Variable | Default | Description |
|---|---|---|
| `HERMAN_VAULT_PATH` | `/Volumes/GIT/CLAUDE/SHARED_WORK_FOLDER/Homunculus/vault` | Root of the Herman vault |
| `BRIDGE_CALENDAR_NAME` | `Homunculus` | Name of the Calendar.app calendar to push events into |
| `BRIDGE_STATE_FILE` | `~/.local/share/mac_calendar_bridge/pushed.jsonl` | Idempotency state file |
| `BRIDGE_LOG_LEVEL` | `INFO` | Logging level (DEBUG / INFO / WARNING / ERROR) |
| `BRIDGE_LOG_FILE` | `/tmp/mac_calendar_bridge.log` | Log file path |

Note: `BRIDGE_CALENDAR_ACCOUNT` (present in v0.1.1) has been removed. Calendar.app
has no account concept in AppleScript; the variable was dead and its use caused
syntax errors (`-2741`).

---

## Development

```bash
cd Homunculus/mac_calendar_bridge
python3 -m venv .venv
source .venv/bin/activate
pip install -e ".[dev]"
pytest
```

Tests never invoke real AppleScript or touch the live vault (`tmp_path` fixtures only).

---

## v0.2 roadmap

Candidates for the next version (in rough priority order):

1. **Swift/EventKit calendar creation** — use `pyobjc` + `EventKit` to create the
   "Homunculus" calendar programmatically in the iCloud account (`EKCalendar.source`).
   This is the only way to auto-create in iCloud; AppleScript cannot do it.
   Requires macOS-only `pyobjc-framework-EventKit`.
2. **Edit propagation** — when a vault `.md` file is modified after push, update
   the corresponding Calendar.app event. Requires querying Calendar by the
   `homunculus://event/<id>` URL and calling `set` on the event properties.
3. **Delete propagation** — when a `.md` file disappears, remove the Calendar
   entry. Requires a tombstone mechanism (can't read frontmatter from a deleted file).
4. **Rebuild state from Calendar** — on startup, query Calendar.app for all
   events whose URL starts with `homunculus://event/` and rebuild `pushed.jsonl`
   from scratch. Makes the bridge fully self-healing after a state file loss.
5. **Two-way sync** — Calendar.app edits (time changes, title edits) propagate
   back to the vault. Complex; requires polling Calendar.app or an EventKit
   native layer.
