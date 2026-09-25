# MovieScanner V3.23 — Config Export/Import + Auto-Snapshot

**V3.23 — 2026-09-25 — Sienna**

---

## The Incident

> *"the movie scanner version 3.22 … all my genre settings have disappeared … on the last scan it found 823 matches, which of course is wrong … let's change things so that those genre settings get stored to a file that I can restore because this is a royal pain in the ass. I spent a lot of time setting up genres and then excluding particular movies, etc., and it looks like all of that information has now disappeared."*
> — Thomas, 2026-09-24

We restored from a 20-day-old Desktop backup. Config recovered: tags, exclude_tags, exclude_countries, omdb_api_key, parental levels, and 301 dismissed_tconsts. Anything configured after Sep 5 is gone. **V3.23 makes this impossible to happen again without a safety net.**

---

## Three Layers of Protection

### Layer 1 — Auto-snapshot on every config save

Every time you hit Save (or Run, which also saves config), MovieScanner copies the live `scanner.db` to `MovieScanner/db/backups/scanner_YYYYMMDD_HHMMSS.db`. Rolling window of 20 snapshots — the oldest is deleted when the 21st is added. Snapshots are taken AFTER the DB commit succeeds, never on partial state.

- Snapshot directory: `MovieScanner/db/backups/`
- Added to `.gitignore` — snapshots are local-machine artifacts, not source code
- 20 snapshots at ~175 MB each = ~3.5 GB max on disk

### Layer 2 — Config export and import (user-visible backup)

**Export:** `GET /config/export` downloads a JSON file containing every config key/value and every dismissed_tconst. File is named `moviescanner_config_YYYYMMDD_HHMMSS.json`.

**Import:** `GET /config/import_form` shows an upload form. `POST /config/import` validates the file, takes a pre-import snapshot (so you can roll back the import if needed), then replaces config and dismissed_tconsts in full.

Export JSON shape:
```json
{
  "version": "v1",
  "exported_at": "2026-09-25T12:49:00Z",
  "config": { "min_rating": "7.5", "tags": "[\"Action\",\"Drama\"]", "omdb_api_key": "...", ... },
  "dismissed_tconsts": ["tt1234567", "tt7654321", ...]
}
```

Import validation: rejects malformed JSON (400), unknown version field (400), missing required keys (400).

### Layer 3 — Startup integrity check + banner

On every page load of `/`, MovieScanner checks whether the four essential config keys (`tags`, `exclude_tags`, `min_rating`, `omdb_api_key`) are present. If any are missing:

- A red warning banner appears: *"Config appears reset."*
- If snapshots exist: a **Restore from most-recent snapshot** button appears inline
- If no snapshots exist: a link to the Import page is shown instead

`POST /config/restore_latest` copies the most-recent snapshot over the live DB. A safety snapshot of the broken state is taken first (so you can always undo the restore if needed).

---

## Files Changed

| File | Change |
|------|--------|
| `MovieScanner/app.py` | APP_VERSION V3.22 → **V3.23**; new imports (glob, io, shutil, datetime/timezone); `_backup_dir()`, `_snapshot_db()` helpers; `_check_config_integrity()` + module-level `_config_integrity_ok` flag; snapshot call added to `_save_config_from_form()`; `index()` passes integrity context vars; new routes: `GET /config/export`, `GET /config/import_form`, `POST /config/import`, `POST /config/restore_latest` |
| `MovieScanner/templates/index.html` | Header reworked to flex-row with Export/Import links (right-aligned, subtle); integrity warning banner added between header and flash messages |
| `MovieScanner/templates/config_import.html` | New template — file upload form for `/config/import_form` |
| `MovieScanner/tests/test_config_backup.py` | New — 30 tests covering all three layers + regression |
| `MovieScanner/tests/__init__.py` | New — makes tests/ a package |
| `.gitignore` | Added `MovieScanner/db/backups/` and `MovieScanner/db/scanner.db.pre_restore_*` |

---

## Red → Green Table

| # | Test | Before | After |
|---|------|--------|-------|
| T01 | `test_config_save_creates_snapshot` | FAIL | PASS |
| T02 | `test_snapshot_filename_pattern` | FAIL | PASS |
| T03 | `test_snapshot_rotation_keeps_20` | PASS* | PASS |
| T04 | `test_snapshot_dir_created_lazily` | FAIL | PASS |
| T05 | `test_snapshot_is_valid_sqlite` | FAIL | PASS |
| T06 | `test_snapshot_not_taken_on_failed_transaction` | PASS* | PASS |
| T07 | `test_export_returns_200_with_attachment` | FAIL | PASS |
| T08 | `test_export_has_required_top_level_keys` | FAIL | PASS |
| T09 | `test_export_version_is_v1` | FAIL | PASS |
| T10 | `test_export_config_contains_seeded_values` | FAIL | PASS |
| T11 | `test_export_dismissed_tconsts_list` | FAIL | PASS |
| T12 | `test_export_round_trip_config_matches_db` | FAIL | PASS |
| T13 | `test_import_replaces_config` | FAIL | PASS |
| T14 | `test_import_replaces_dismissed_tconsts` | FAIL | PASS |
| T15 | `test_import_takes_snapshot_before_replacing` | FAIL | PASS |
| T16 | `test_import_malformed_json_returns_400` | FAIL | PASS |
| T17 | `test_import_wrong_version_returns_400` | FAIL | PASS |
| T18 | `test_import_missing_top_level_keys_returns_400` | FAIL | PASS |
| T19 | `test_import_no_file_returns_400` | FAIL | PASS |
| T20 | `test_import_form_page_returns_200` | FAIL | PASS |
| T21 | `test_missing_essential_keys_sets_banner_flag` | FAIL | PASS |
| T22 | `test_all_essential_keys_present_no_banner` | PASS* | PASS |
| T23 | `test_restore_from_snapshot_route_exists` | FAIL | PASS |
| T24 | `test_restore_from_snapshot_replaces_config` | FAIL | PASS |
| T25 | `test_app_version_is_v3_23` | FAIL | PASS |
| T26 | `test_index_renders` | PASS* | PASS |
| T27 | `test_config_save_still_works` | PASS* | PASS |
| T28 | `test_dismiss_still_works` | PASS* | PASS |
| T29 | `test_header_contains_export_link` | FAIL | PASS |
| T30 | `test_header_contains_import_link` | FAIL | PASS |

*Already passing on V3.22 (rotation, smoke tests) — no regression.

**Final: 30/30 PASS**

---

## Migration for Thomas — Do This Now

**Immediately after deploying V3.23, hit Export and save the file off-repo:**

1. Open MovieScanner at http://localhost:5053
2. Click **Export config** in the top-right of the header
3. Save the downloaded `moviescanner_config_YYYYMMDD_HHMMSS.json` file somewhere outside the repo — Desktop, Downloads, or iCloud Drive
4. That's your manual off-machine backup until the next export

From this point forward, every time you hit Save, an automatic snapshot lands in `MovieScanner/db/backups/`. You will never again need to restore from a 20-day-old Desktop backup.

---

## Snapshot De-duplication Fix (implementation note)

During development, a subtle bug was found and fixed: if two saves happen within the same UTC second (e.g. the restore route taking a safety snapshot in the same second as a prior config save), `shutil.copy2` would have silently overwritten the first snapshot with the second, corrupting the backup the restore was about to use. Fixed by appending `_1`, `_2`, etc. when a filename collision is detected.

---

## Follow-up Considerations (deferred, not MVP)

- **Periodic auto-export to ~/Downloads/** — export a JSON backup on a schedule (e.g. once a week on first save) so there's always an off-machine copy without any manual action. Requires a cron/launchd hook or a "last exported at" config key.
- **Cloud sync of export file** — POST to a private GitHub Gist or Dropbox on each export. Useful but adds an outbound dependency; defer until Thomas asks for it.
- **Snapshot compression** — 20 × 175 MB = 3.5 GB. If disk becomes a concern, gzip the snapshots (trivial to add, just changes the copy to `shutil.copy` + `gzip.open` chain).
- **Config-only snapshots** — snapshot just the `config` + `dismissed_tconsts` tables rather than the whole DB (~175 MB → ~50 KB). Lower overhead but adds restore complexity (must merge tables rather than swap files). Defer.
- **Import history** — log each import/restore to a `_backup_events` config key so Thomas can see "last restored from X at Y".
