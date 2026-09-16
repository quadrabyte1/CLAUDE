# mac_notes_bridge v0.1.0 — Handoff

**v0.1.0 — 2026-09-15 — Rune**

---

## What shipped

`/Volumes/GIT/CLAUDE/SHARED_WORK_FOLDER/Homunculus/mac_notes_bridge/` — a new
bridge package that watches `vault/notes/*.md` and pushes notes to Notes.app
via AppleScript. Sibling to `mac_calendar_bridge`. Same family, same patterns.

---

## Architecture — side-by-side with Calendar bridge

| Aspect | mac_calendar_bridge (v0.1.5) | mac_notes_bridge (v0.1.0) |
|--------|------------------------------|---------------------------|
| Source watched | `vault/calendar/*.md` | `vault/notes/*.md` |
| AppleScript target | `tell calendar "Homunculus"` (flat namespace — no account concept) | `tell folder "Homunculus" of account "iCloud"` (Notes.app has account model) |
| Idempotency marker | `url` field = `homunculus://event/<id>` | Note title match (title = Herman `title` field, globally unique per note) |
| Deduplication slow path | Date-window URL query | Folder title query |
| Body | Event fields (summary/start/end) | Raw markdown prose, plain text in Notes.app |
| State file | `~/.local/share/mac_calendar_bridge/pushed.jsonl` | `~/.local/share/mac_notes_bridge/pushed.jsonl` |
| Startup guard | `verify_calendar_exists()` | `verify_folder_exists()` |
| Boot-volume install | `~/.local/lib/mac_calendar_bridge/` | `~/.local/lib/mac_notes_bridge/` |

**Key lessons carried forward from Calendar bridge:**

1. Atomic `make new note with properties {name:..., body:...}` — no two-step
   make-then-set-body. The Calendar v0.1.5 incident taught us that two-step
   patterns silently roll back on macOS 15.x.
2. Belt-and-suspenders idempotency: pushed.jsonl fast path + Notes.app query
   slow path. If the state file is wiped, the slow path self-heals.
3. `verify_folder_exists()` at startup — log actionable error, exit non-zero,
   don't crash-loop.
4. `on_moved` handler for atomic renames from Sprite/Herman write path.
5. Explicit `.tmp` skip logging at DEBUG.
6. 60-second generous sweep interval (reliability over speed).

---

## Idempotency design rationale

Notes.app has no `url` field accessible from AppleScript (unlike Calendar
events). Three options considered:

- **Body sentinel** (e.g. `[hmnid:2026-09-15-test-notes-mechanism]` at end
  of body) — rejected: pollutes the note content the user sees.
- **Title match** — chosen: Herman note titles are globally unique (date +
  Ollama-derived slug). `title` in frontmatter becomes the Note `name`.
  The Homunculus folder will only ever contain Herman-generated notes.
  Title = unique key. No pollution.
- **State file only, no slow path** — rejected: the Calendar bridge v0.1.4
  incident proved that a wiped state file creates duplicates on cold boot.

---

## Body format

Plain text (raw markdown prose, frontmatter stripped). Notes.app renders it
readably. No HTML conversion — adding a dep for formatting not asked for in
v0.1 is scope creep. The user sees clean prose.

---

## What the vault notes look like (real files as of 2026-09-15)

Four notes in `vault/notes/`:
- `2026-09-15-test-notes-mechanism.md` — "test notes mechanism"
- `2026-09-15-a-way.md` — "a way"
- `2026-09-15-mechanism-to-close-the-loop-between-phone-and-mac.md`
- `2026-09-15-voice-message-deletion-and-cancellation.md`

All from Sprite (voice capture). All have `id`, `title`, `captured_at` in
frontmatter. The bridge's cold-boot sweep will push all four on first run.

---

## Test coverage

**130 tests passing, 4 skipped** (Linux-only guard tests, correct on macOS).

Coverage includes:
- `test_vault_reader.py`: 37 tests — parse real note format, error handling,
  timezone conversion, scan_vault_notes
- `test_state.py`: 26 tests — JSONL persistence, `note_id` key (not
  `event_id`), reload, deduplication, thread safety
- `test_applescript.py`: 43 tests — verify_folder_exists, query_pushed_note_ids,
  push_note (atomic, no two-step), quote escaping, config fields
- `test_watcher.py`: 28 tests — push_if_new (fast path, slow path,
  self-heal), cold_boot_sweep, VaultNotesHandler (on_created, on_moved,
  on_modified, tmp-skip), periodic_sweep

All tests use `tmp_path` — never touch live vault. All osascript calls mocked.

---

## Migration steps (for Thomas)

1. **Create "Homunculus" folder in Notes.app under iCloud**
   - Open Notes.app
   - Sidebar: click **+** next to iCloud (or File → New Folder)
   - Select iCloud account, name it exactly **`Homunculus`**
   - Verify it appears under the iCloud heading (not "On My Mac")

2. **Run the installer**
   ```bash
   cd /Volumes/GIT/CLAUDE/SHARED_WORK_FOLDER/Homunculus/mac_notes_bridge
   bash deploy/install.sh
   ```

3. **Load the launchd agent**
   ```bash
   launchctl load ~/Library/LaunchAgents/com.homunculus.mac_notes_bridge.plist
   ```

4. **Grant Automation permission when macOS prompts** → click Allow

5. **Cold-boot sweep backfills the 4 existing vault notes** into the
   Homunculus folder in Notes.app

6. **Within ~60 seconds, iCloud syncs to your iPhone**

Watch logs: `tail -f /tmp/mac_notes_bridge.log`

---

## Known limitations

- Notes.app only — no Reminders, no other note services
- Plain text body — no rich HTML rendering of markdown
- One-way sync only — edits in Notes.app are not reflected back to vault
- No delete propagation — deleting a vault note leaves it in Notes.app
- iCloud account only by default (`BRIDGE_NOTES_ACCOUNT=iCloud`); other
  accounts configurable via env var but untested
- No attachment support (notes are text-only)
- Title-based idempotency assumes no two Herman notes in the Homunculus folder
  have identical titles (guaranteed by Herman's Ollama-derived unique ID scheme)

---

## v0.2 roadmap

- Rich HTML body rendering (markdown → HTML for proper formatting in Notes.app)
- Non-iCloud account support with verification
- Programmatic folder creation via Swift/EventKit (avoids the manual step)
- Delete propagation (remove from Notes.app when vault note is deleted)
- Two-way sync investigation (substantial scope — v0.3 at earliest)
- Attachment handling (images captured with voice memos)

---

## Files delivered

```
Homunculus/mac_notes_bridge/
├── README.md
├── pyproject.toml
├── src/mac_notes_bridge/
│   ├── __init__.py          VERSION = "0.1.0"
│   ├── config.py            env-driven config (BRIDGE_FOLDER_NAME, BRIDGE_NOTES_ACCOUNT, etc.)
│   ├── vault_reader.py      parse vault/notes/*.md → NoteRecord
│   ├── applescript.py       osascript wrappers (verify_folder_exists, push_note, query_pushed_note_ids)
│   ├── state.py             pushed.jsonl idempotency
│   └── watcher.py           cold-boot + watchdog + 60s periodic sweep + main()
├── tests/
│   ├── __init__.py
│   ├── test_vault_reader.py  37 tests
│   ├── test_applescript.py   43 tests
│   ├── test_state.py         26 tests
│   └── test_watcher.py       28 tests
├── deploy/
│   ├── com.homunculus.mac_notes_bridge.plist
│   ├── mac-notes-bridge.service   (systemd sibling, portability)
│   └── install.sh
└── docs/
    ├── FIRST_RUN.md
    └── AUTOMATION_SETUP.md
```
