---
title: "Obsidian Phase 1 Bootstrap Report"
date: 2026-05-07
author: Cairn (PKM Specialist)
batch: obsidian-phase1
status: complete
---

# Obsidian Phase 1 Bootstrap Report

**Date:** 2026-05-07
**Performed by:** Cairn (PKM Specialist)
**Vault:** `/Volumes/GIT/CLAUDE/SHARED_WORK_FOLDER/`
**Obsidian version installed:** 1.12.7

---

## What Was Changed

### 1. Obsidian installed
- **Method:** `brew install --cask obsidian`
- **Version:** 1.12.7 (verified in `obsidian.log` and `/Applications/Obsidian.app`)
- **Additional binary:** `obsidian-cli` linked to `/opt/homebrew/bin/obsidian`

### 2. Vault bootstrapped
The following files were created in `.obsidian/`:

| File | Purpose |
|---|---|
| `.obsidian/app.json` | Vault-level settings; `userIgnoreFilters` set (see §3) |
| `.obsidian/core-plugins.json` | 15 core plugins enabled |
| `.obsidian/community-plugins.json` | 3 community plugins registered |
| `.obsidian/daily-notes.json` | Daily notes → `journal/`, format `YYYY-MM-DD`, template `_templates/daily.md` |
| `.obsidian/templates.json` | Templates folder set to `_templates/` |
| `.obsidian/workspace.json` | Minimal workspace state (pre-created; Obsidian will overwrite on first interactive open) |

### 3. Excluded paths (userIgnoreFilters)
Each folder was verified by `ls` before exclusion:

| Excluded Pattern | Reason | Verified Contents |
|---|---|---|
| `^\.claude/` | Internal Claude config, not knowledge content | Confirmed: project config |
| `^\.git/` | Git internals | Confirmed: git repo data |
| `^app/` | Python Flask application code + `__pycache__` | Confirmed: `.py` files, `__pycache__/` |
| `^db/` | SQLite database files + migrations | Confirmed: `.db`, `.db-shm`, `.db-wal`, `.py`, `.sql` |
| `^test-results/` | Test output (empty at inspection time) | Confirmed: empty |
| `^EliteGolfMoments/.*/STLs/` | Binary STL 3D print files | Confirmed: `.stl` files |
| `^EliteGolfMoments/.*/3MFs/` | Binary 3MF 3D print files | Confirmed: `.3mf` files |
| `^EliteGolfMoments/.*/EGMs/` | Binary EGM files | Confirmed: `.egm` files |
| `^EliteGolfMoments/Frames/` | Binary `.3mf` and `.step` frame files | Confirmed: `.3mf`, `.step` |
| `^owner_inbox/deck_blueprint/` | Binary/CAD deck drawings | Confirmed: `.drawio`, `.bkp`, `.dtmp` |
| `^owner_inbox/GoButton/` | iOS Xcode project source code | Confirmed: Swift/Xcode project |
| `^Images/` | PNG image files only | Confirmed: 4 `.png`/`.jpg` image files |
| `^Homunculus/Packages/` | Swift packages / source code | Confirmed: `AppShell`, `NLU`, etc. (code) |
| `^Team/` | **Legacy** team folder (capital T) — hiring research `.md` files + persona files | ⚠️ **SEE FLAG #1 BELOW** |
| `.*/__pycache__/` | Python bytecode | Confirmed: present in `app/` |
| `.*/node_modules/` | JS dependencies (none found, but defensive) | Precautionary |
| `.*\.pyc$` | Compiled Python | Confirmed: present |
| `.*\.3mf$` | Binary 3MF files (belt-and-suspenders) | Belt-and-suspenders for any 3MF outside named folders |
| `.*\.stl$` | Binary STL files | Belt-and-suspenders |
| `.*\.step$` | STEP CAD files | Belt-and-suspenders |
| `.*\.egm$` | EGM proprietary files | Belt-and-suspenders |
| `.*\.db$`, `.*\.db-shm$`, `.*\.db-wal$` | SQLite database files | Belt-and-suspenders |

**Not excluded (intentionally visible in Obsidian):**
- `team/` (lowercase — the active team persona files; these are knowledge content)
- `journal/` (daily notes target)
- `owner_inbox/` (deliverables — most are `.md` files Thomas wants to see)
- `team_inbox/` (shared files for team review)
- `Evernotes/` (Evernote exports — future migration source)
- `Homunculus/docs/` and `Homunculus/README.md` (Markdown docs within Homunculus)
- `EliteGolfMoments/GolfCourses/*/Images/` (PNG reference images — small count, low noise)
- `EliteGolfMoments/GolfCourses/*/serial.json` (small JSON metadata — Obsidian will index; low noise, not excluded by instruction)

### 4. Community plugins installed

| Plugin | Version | Source | Files |
|---|---|---|---|
| Templater | 2.20.3 | github.com/SilentVoid13/Templater | `main.js`, `manifest.json`, `styles.css` |
| Dataview | 0.5.70 release (manifest: 0.5.68) | github.com/blacksmithgu/obsidian-dataview | `main.js`, `manifest.json`, `styles.css` |
| Obsidian Git | 2.38.2 | github.com/Vinzent03/obsidian-git | `main.js`, `manifest.json`, `styles.css` |

> Note: Dataview's release tag was `0.5.70` on GitHub but the `manifest.json` self-reports `0.5.68`. This is a version skew in the upstream repo (common for Dataview). The files are current as of the latest release. No action needed.

### 5. Daily note template created
- Path: `_templates/daily.md`
- Contains: YAML frontmatter stub (`title`, `created`, `tags`), sections for Today's tasks, Notes, Activity log, Journal entry
- DB-facing sections are clearly marked as Phase 2 stubs with comment blocks explaining what Reed will wire up

### 6. Obsidian launched and verified
- Launched via `open -a Obsidian /Volumes/GIT/CLAUDE/SHARED_WORK_FOLDER`
- Obsidian 1.12.7 process confirmed running (`pgrep` positive)
- `workspace.json` pre-created (Obsidian did not auto-create it because first-launch vault-selection is a GUI interaction; pre-created minimal file serves the same purpose)
- Obsidian quit cleanly via `osascript -e 'quit app "Obsidian"'`

---

## Items Flagged for Boss Review

### ⚠️ FLAG #1 — `Team/` (capital T) is excluded; verify this is intentional

The capital-`T` `Team/` folder contains **the same content as `team/` (lowercase)** — persona files and hiring research `.md` files. It appears to be a legacy duplicate of `team/`. It was excluded from Obsidian because the instructions specified `^Team/` as an exclude target, and it has the same content as the already-indexed `team/` folder (which is visible in Obsidian).

**Action needed:** Thomas should confirm whether `Team/` (capital T) can be deleted or is serving a purpose. If it's a true duplicate, deleting it will reduce confusion. If it needs to stay, consider adding a `README.md` note inside it explaining its relationship to `team/`.

### ⚠️ FLAG #2 — Community plugins require "Trust" click on first Obsidian open

When Thomas opens the vault for the first time, Obsidian will show a security prompt for each manually-installed community plugin (Templater, Dataview, Obsidian Git). He must click **"Trust author and enable plugin"** for each. This is Obsidian's sandboxing behavior — cannot be bypassed programmatically. First open will take ~60 extra seconds for this step.

### ⚠️ FLAG #3 — `workspace.json` was pre-created, not Obsidian-generated

The `workspace.json` was manually authored because Obsidian did not auto-create it during the headless launch (vault selection requires GUI interaction on first run). The pre-created file is a valid minimal workspace. Obsidian will rewrite it on first interactive open, which is the correct behavior. No data loss risk — just noting that the file is synthetic, not Obsidian-native, until Thomas opens the vault interactively.

### ⚠️ FLAG #4 — `EliteGolfMoments/GolfCourses/*/Images/` not excluded

Per the instructions, the top-level `Images/` folder was excluded, but `Images/` subfolders inside each GolfCourse were left visible (they contain reference PNGs like `Moffett Field (7).png`). Obsidian will index these images. If the image files create noise in search results, add `^EliteGolfMoments/.*/Images/` to `userIgnoreFilters`. Currently left visible per the instruction scope ("the goal is Obsidian shows knowledge files, not code or 3MFs" — PNG images arguably qualify as knowledge/reference content for the golf project).

### ⚠️ FLAG #5 — `Evernotes/` folder not excluded; large HTML exports will be indexed

The `Evernotes/` folder (My Notes1–5, Running Journal exports) is visible to Obsidian. These are large HTML files (potentially 4–160 MB each). Obsidian will attempt to index them. This may cause slowness on initial vault index and will pollute search results with raw HTML. Recommend adding `^Evernotes/` to `userIgnoreFilters` until Cairn completes the formal Evernote migration. **No change made** — flagging for Thomas to decide.

---

## Unverified / Skipped

- **Obsidian interactive vault registration:** Not verified headlessly. Thomas must open Obsidian interactively once to complete vault registration and plugin trust flow.
- **`obsidian-git` auto-commit schedule:** Plugin is installed but not configured (schedule, commit message template, remote). Reed or Thomas should configure via Obsidian settings UI on first open.
- **Templater auto-trigger on new note:** Not configured. Default behavior is manual invoke (`Alt+E`). Thomas can configure in Settings → Templater if he wants the daily template to auto-populate on new file creation.

---

## Phase 2 Handoff Summary

Reed's work is defined in:
`owner_inbox/Notes/obsidian_db_bridge_architecture.md`

Core deliverables for Reed:
1. `scripts/sync_journal.py` — file watcher syncing vault → DB (journal) and DB → vault (dashboard notes)
2. `scripts/init_bridge.sh` + `launchd` plist for persistence
3. Generated dashboard notes in `journal/_dashboard/`

Database tables in scope: `journal_entries` (two-way), `tasks` (DB → vault), `activity_log` (DB → vault).
