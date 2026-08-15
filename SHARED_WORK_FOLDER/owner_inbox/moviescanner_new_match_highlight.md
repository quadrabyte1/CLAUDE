# MovieScanner V3.21 — "NEW since last scan" highlight

**Task 655** · Sienna · 2026-08-15

## Visual treatment chosen

A small amber **NEW** pill inline in the Title cell, right after the title
link (before the season-count hint). Warm palette:

- text: `amber-800` (`#92400e`)
- background: `amber-100` (`#fef3c7`)
- border: `amber-200` (`#fde68a`)
- shape: fully rounded, `9px` uppercase with `letter-spacing: 0.06em`
- transition: `180ms ease` on color/background/border-color

**Why a pill, not a column:**

- Uses zero horizontal space in an already dense 9-column table.
- Reads correctly at any sort order — the flag travels with the row.
- Palette matches the existing flash-message chrome (`bg-amber-50 border-amber-200 text-amber-800`),
  so it feels part of the family instead of introduced.
- Sits next to the thing it's describing (the title) — no eye-scan across
  columns to figure out what's new.
- Fades slightly further on dismissed rows so it doesn't fight the
  strikethrough.

A `data-new="0|1"` attribute is also set on the `<tr>` so a future
"sort by new" affordance can be added without another backend pass.

## Files changed

| File | Line range | Change |
|---|---|---|
| `MovieScanner/app.py` | 33-40 | Bump `APP_VERSION` to `V3.21` + changelog comment |
| `MovieScanner/app.py` | 200-216 | Load `previous_match_tconsts` set + attach `is_new` to each match dict |
| `MovieScanner/app.py` | 379-388 | `/clear` also wipes `previous_match_tconsts` (no baseline after clear) |
| `MovieScanner/app.py` | 428-441 | `/run` snapshots outgoing matches' tconsts into `previous_match_tconsts` BEFORE `DELETE FROM matches` |
| `movie_scanner/schema.py` | 125-135 | New `previous_match_tconsts` table in `SCHEMA_SQL` |
| `movie_scanner/schema.py` | 260-269 | Idempotent CREATE-IF-NOT-EXISTS migration for existing DBs |
| `MovieScanner/templates/index.html` | 95-124 | `.new-pill` CSS (amber, 180ms transition, dismissed-row variant) |
| `MovieScanner/templates/index.html` | 638-644 | Pill rendered in title cell when `m.is_new` |
| `MovieScanner/templates/index.html` | 632 | `data-new` attribute on match `<tr>` |
| `movie_scanner/tests/test_new_since_previous.py` | new file, 205 lines | 5 regression tests covering all four cases + `/clear` wipe |

## New APP_VERSION

`V3.21` (bumped from V3.20). The version badge in the sticky footer picks
this up via the existing `app_version` context processor — nothing to
change in the template for the badge itself.

## How the diff is computed

**Which prior run:** The immediately-previous scan (there is only one
"source" — the config — so there is exactly one prior run to consider).

**Keyed on:** `tconst` (the IMDb stable identifier — also the natural
primary key for both `titles` and `matches.tconst UNIQUE`).

**Storage primitive:** New `previous_match_tconsts` table — one column,
`tconst TEXT PRIMARY KEY`. This exists because `/run` does
`DELETE FROM matches` before every scan (CASCADE from `runs` too), so the
prior run's matches are gone from the `matches` table by the time the
fresh scan starts. The snapshot is the only surviving record.

**Lifecycle:**

1. `/run` → `DELETE FROM previous_match_tconsts; INSERT ... SELECT tconst FROM matches;`
   then the existing `DELETE FROM matches` / `DELETE FROM titles` / spawn.
2. Scanner populates fresh `matches` rows for the new run.
3. `index()` loads `previous_match_tconsts` into a Python set; for each
   match row, `is_new = (has_previous_run) and (tconst not in previous_set)`.
4. Template renders the pill when `is_new` is truthy.
5. `/clear` → also wipes `previous_match_tconsts` (a full clear means
   no baseline exists, so the next scan starts clean).

## Edge cases handled

| Case | Behaviour |
|---|---|
| First-ever scan (empty snapshot) | `has_previous_run = False` → NO row flagged. Verified by `test_first_scan_flags_nothing_as_new`. |
| Repeat scan, no changes | Every current tconst is in snapshot → no pills. Verified. |
| Repeat scan, 1 new match | Only the new tconst is flagged. Verified. |
| Repeat scan, one dropped + one added | Dropped tconst just doesn't appear (no row to flag); added one gets the pill. Verified. |
| After `/clear` | Snapshot is wiped → next scan flags nothing. Verified. |
| Existing DBs (pre-V3.21) | `apply_schema()` runs on every startup and creates the table idempotently. First scan post-upgrade sees an empty snapshot, so nothing is flagged as "new" — correct, because we cannot retroactively know what the pre-upgrade run produced. |

## Verification

- **Unit tests:** 5 new tests in `movie_scanner/tests/test_new_since_previous.py`
  (all pass), plus the full 40-test suite still green.
- **Safety:** Every test sets `MOVIESCANNER_DB_PATH` to a per-test tempfile
  BEFORE importing `app`, following the existing fixture pattern in
  `test_app_cancel_and_status.py`. The live `scanner.db` was never
  touched during verification.

## Follow-ups (none required, noted for context)

- If Thomas later wants a **"NEW-only" filter** in the Matches header
  bar, the `data-new` attribute on each `<tr>` is already there — a
  client-side toggle could hide `[data-new="0"]` rows without a
  round-trip.
- If we ever move to **multi-source scanning** (currently there's only
  one config), the `previous_match_tconsts` table would need a
  `source_id` column and a compound PK.
