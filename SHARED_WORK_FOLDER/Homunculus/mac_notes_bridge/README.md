# mac_notes_bridge

**v0.1.0** — Herman vault/notes → macOS Notes.app bridge.

Watches `vault/notes/*.md` for new notes written by Herman/Sprite and pushes
them to Notes.app via AppleScript. Notes appear in a "Homunculus" folder under
the iCloud account, syncing to iPhone within ~60 seconds of capture.

---

## What it does

- **Cold-boot sweep**: on startup, scans all existing vault notes and pushes
  any that haven't been pushed yet (backfill).
- **Watchdog**: monitors `vault/notes/` for new `.md` files in real time,
  including atomic renames from the Sprite/Herman write path.
- **60-second periodic sweep**: safety net — catches any note missed by the
  watchdog within one minute.
- **Idempotent**: belt-and-suspenders deduplication via `pushed.jsonl` (fast
  path) + Notes.app title query (slow path). If `pushed.jsonl` is wiped, the
  slow path self-heals without creating duplicates.

---

## Architecture

```
vault/notes/YYYY-MM-DD-<slug>.md
         ↓ (watchdog / periodic sweep)
mac_notes_bridge
         ↓ (osascript)
Notes.app → Homunculus (folder, iCloud account)
         ↓ (iCloud sync, ~60s)
iPhone Notes.app
```

**Key design decisions vs Calendar bridge:**

| Aspect | mac_calendar_bridge | mac_notes_bridge |
|--------|--------------------|--------------------|
| AppleScript target | `tell calendar "Homunculus"` (flat namespace) | `tell folder "Homunculus" of account "iCloud"` (accounts exist in Notes.app) |
| Idempotency marker | `url` field (homunculus://event/...) | Title match (note title = Herman note_id slug, globally unique) |
| Body format | N/A (event fields) | Raw markdown prose — plain text in Notes.app (no HTML conversion) |
| Duplicate prevention | URL query on target date | Title-in-folder query |

**Why title-based idempotency:**
Notes.app has no URL field (unlike Calendar events). We match on note `name`
(title), which equals the Herman `title` field from frontmatter. Herman note
IDs and titles are globally unique (date + Ollama-derived slug). No two
Herman notes in the Homunculus folder will have the same title.

**Why plain text body:**
Notes.app renders plain text readably. Converting markdown to HTML adds a
dependency and formatting complexity not warranted by v0.1. The user sees
clean prose.

---

## Installation

See `docs/FIRST_RUN.md` for the full walkthrough.

Quick start:
```bash
# 1. Create "Homunculus" folder in Notes.app under iCloud (manual, one-time)
# 2. Install
bash deploy/install.sh
# 3. Load
launchctl load ~/Library/LaunchAgents/com.homunculus.mac_notes_bridge.plist
# 4. Grant Automation permission when macOS prompts
```

---

## Configuration

| Env var | Default | Description |
|---------|---------|-------------|
| `HERMAN_VAULT_PATH` | `/Volumes/GIT/CLAUDE/SHARED_WORK_FOLDER/Homunculus/vault` | Path to Herman vault root |
| `BRIDGE_FOLDER_NAME` | `Homunculus` | Notes.app folder name |
| `BRIDGE_NOTES_ACCOUNT` | `iCloud` | Notes.app account name |
| `BRIDGE_STATE_FILE` | `~/.local/share/mac_notes_bridge/pushed.jsonl` | Idempotency state |
| `BRIDGE_LOG_LEVEL` | `INFO` | Logging level |
| `BRIDGE_LOG_FILE` | `/tmp/mac_notes_bridge.log` | Log file path |

---

## Running tests

```bash
cd Homunculus/mac_notes_bridge
pip install -e ".[dev]"
pytest
```

Tests never invoke real osascript or touch the live vault.

---

## v0.2 roadmap

- Rich HTML body rendering (markdown → HTML, preserving headers + bullets)
- Non-iCloud account support without env var
- Two-way sync (edits in Notes.app reflected back to vault) — substantial scope
- Swift/EventKit approach for programmatic folder creation in correct account
