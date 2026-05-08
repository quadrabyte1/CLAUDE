# Obsidian ↔ SQLite Bridge — Operator's Guide

Maintained by **Reed** (Database Engineer). This sidecar bridge keeps your Obsidian vault and `db/workspace.db` in sync without touching the Flask app or any production schema.

---

## Architecture at a glance

| Direction | Mechanism |
|-----------|-----------|
| Vault → DB | `sync_journal.py` watches `journal/*.md`; extracts the **"Journal entry (syncs to DB)"** H2 section; upserts into `journal_entries` |
| DB → vault | `sync_journal.py` also watches `db/workspace.db`; on change, calls `generate_dashboard.py` to regenerate three read-only notes under `journal/_dashboard/` |

The watcher runs as a persistent macOS launchd agent (`com.sharedworkfolder.journal-watcher`).

---

## One-time setup

```bash
bash scripts/init_bridge.sh
```

This:
1. Creates a Python venv at `scripts/.venv/`
2. Installs `watchdog`, `python-frontmatter`, `python-dateutil`
3. Generates the initial dashboard notes
4. Registers the launchd agent (starts immediately + on every login)

**Safe to run multiple times.** Running it again updates the plist and restarts the agent.

---

## Starting and stopping the watcher

| Action | Command |
|--------|---------|
| Check status | `launchctl print gui/$UID/com.sharedworkfolder.journal-watcher` |
| Stop | `launchctl bootout gui/$UID/com.sharedworkfolder.journal-watcher` |
| Start (after stop) | `launchctl bootstrap gui/$UID ~/Library/LaunchAgents/com.sharedworkfolder.journal-watcher.plist` |
| Restart | Stop, then Start (as above) |
| Run in foreground (debug) | `scripts/.venv/bin/python3 scripts/sync_journal.py` |

---

## Log files

| Log | Path |
|-----|------|
| stdout (info/debug) | `/tmp/journal-watcher.log` |
| stderr (errors) | `/tmp/journal-watcher.err` |

Tail them live:
```bash
tail -f /tmp/journal-watcher.log
tail -f /tmp/journal-watcher.err
```

---

## Regenerating the dashboard manually

```bash
scripts/.venv/bin/python3 scripts/generate_dashboard.py
```

Or if you want to use any Python 3 with the deps installed:
```bash
python3 scripts/generate_dashboard.py
```

Dashboard files are written to:
- `journal/_dashboard/tasks-today.md`
- `journal/_dashboard/recent-activity.md`
- `journal/_dashboard/task-index.md`

These files have `read_only: true` in their YAML frontmatter. **Do not edit them by hand** — changes will be overwritten on next DB change.

---

## Conflict resolution

If both your vault file and the DB row are modified within 60 seconds of each other (e.g., the watcher was down and a script also updated the DB), the bridge:

1. Writes **both versions** to `journal/_conflicts/YYYY-MM-DD-conflict.md`
2. Logs a `conflict_detected` event to `activity_log`
3. **Does NOT silently overwrite** either side

To resolve: open the conflict file, pick the correct version, paste it into your daily note's "Journal entry (syncs to DB)" section, and save. The watcher will sync the resolved version.

---

## What if the watcher dies?

launchd will restart it automatically (the plist has `KeepAlive = true`). If it keeps crashing, check `/tmp/journal-watcher.err` for the error.

Common causes:
- The venv was deleted → re-run `bash scripts/init_bridge.sh`
- The DB file moved → update `DB_PATH` in `sync_journal.py` and re-register the plist
- The Volumes mount is offline → watcher will error; restart after the volume is back

---

## Manual launchd install (if init_bridge.sh was run without launchctl)

```bash
mkdir -p ~/Library/LaunchAgents
cp scripts/com.sharedworkfolder.journal-watcher.plist ~/Library/LaunchAgents/
launchctl bootstrap gui/$UID ~/Library/LaunchAgents/com.sharedworkfolder.journal-watcher.plist
```

---

## File inventory

| File | Purpose |
|------|---------|
| `scripts/sync_journal.py` | Core watcher — vault→DB and DB→vault |
| `scripts/generate_dashboard.py` | Standalone dashboard regenerator |
| `scripts/requirements.txt` | Python dependencies |
| `scripts/init_bridge.sh` | One-time setup + launchd registration |
| `scripts/com.sharedworkfolder.journal-watcher.plist` | launchd plist (source; init_bridge.sh copies to ~/Library/LaunchAgents/) |
| `journal/_dashboard/` | Generated read-only dashboard notes |
| `journal/_conflicts/` | Conflict files (only created when needed) |
