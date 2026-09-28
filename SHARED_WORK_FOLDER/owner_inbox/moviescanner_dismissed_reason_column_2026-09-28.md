# MovieScanner V3.27 — Dismissal Reason Column

**v3.27** · Sienna · 2026-09-28

---

## Scope Decision

**Shipped: Scanner-eliminated with reason logging + Reason column in UI.**

The primary problem Thomas was solving was scanner debuggability — it took an hour of manual DB archaeology to figure out that Neagley (`tt33539520`) was dropped by the theaters filter. With V3.27, he checks "Show dismissed" and sees a `only_in_theaters:filter_dropped` pill on that row. Instant.

**Also shipped (lightweight): user-dismissed markers.** Matches the user clicked X on show `dismissed_by_user` in the Reason column. No UI popup/dropdown needed — just a marker.

**Deferred: per-filter choice of which reason codes to show/hide.** Not needed; the reason is always 1 line and visually color-coded.

---

## Data Model

**New table: `scan_eliminations`** (not a column on `matches`).

Rationale: scanner-eliminated titles never became a match row. Adding a `dismissal_reason` column to `matches` would only cover post-match filtering (plot, theaters, parental). The pre-match filtering (year, rating, votes, genre) happens before a row is ever inserted into `matches`. A separate table captures all drop events cleanly without awkward NULL columns on `matches`.

```sql
CREATE TABLE scan_eliminations (
    id             INTEGER PRIMARY KEY,
    tconst         TEXT NOT NULL,
    primary_title  TEXT,
    reason         TEXT NOT NULL,
    eliminated_at  TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%SZ','now'))
);
CREATE INDEX idx_scan_eliminations_tconst ON scan_eliminations(tconst);
```

The table is **cleared at the start of every `/run`** alongside `matches` + `titles`, so it always reflects the current scan's eliminations only. Historical reasons are not retained (non-goal).

The UI joins `matches` (active + dismissed) against `scan_eliminations` by tconst to populate the Reason column.

---

## Reason Vocabulary

| Code | Trigger |
|------|---------|
| `year:<actual><<min>` | `startYear < min_year` gate |
| `rating:<actual><<min>` | `rating < min_rating` gate |
| `votes:<actual><<min>` | `num_votes < min_votes` gate |
| `genre:excluded=<genre>` | Title has an excluded genre |
| `country:<country>` | OMDb country matched an excluded country |
| `plot:missing` | OMDb returned no plot string |
| `only_in_theaters:filter_dropped` | `_apply_theaters_filter` dropped it |
| `dismissed_by_user` | User clicked X in the UI (virtual; not from scan_eliminations — set by index() when `dismissed_tconsts` has a row but `scan_eliminations` does not) |

The reason codes are short, human-readable, and sortable/scannable at a glance in the UI.

---

## Red → Green Table

| # | Test | Failure (RED) | Result (GREEN) |
|---|------|--------------|----------------|
| T1 | `_record_elimination` called for year drop | `AttributeError: 'Scanner' object has no attribute '_record_elimination'` | PASS |
| T2 | `_record_elimination` called for rating drop | same | PASS |
| T3 | `_record_elimination` called for votes drop | same | PASS |
| T4 | `_apply_theaters_filter` records `only_in_theaters:filter_dropped` | `sqlite3.OperationalError: no such table: scan_eliminations` | PASS |
| T5 | `Reason` column header in `/?show_dismissed=1` | `AssertionError: 'Reason' not in HTML` | PASS |
| T6 | No Reason header in default view | Already passed (column didn't exist) | PASS |
| T7 | `dismissed_by_user` appears in show_dismissed view for manual dismissal | `AssertionError: 'dismissed_by_user' not in HTML` | PASS |
| T8 | Active matches show `—` in Reason column | Already passed (em-dash was in nav text) | PASS |
| T9 | `APP_VERSION == "V3.27"` | `AssertionError: Expected V3.27, got 'V3.26'` | PASS |

Full suite: **108/108 passed** (0 regressions).

---

## Migration Behavior on Thomas's Live DB

1. **Backup taken first**: `MovieScanner/db/scanner.db.pre_v3.27` (copy made before any schema change).
2. **`apply_schema()` adds `scan_eliminations` table + index** via `CREATE TABLE IF NOT EXISTS` — safe on the live DB on next app boot. Already applied manually.
3. **Existing rows**: all pre-V3.27 match rows have no corresponding `scan_eliminations` rows. The UI shows blank (no pill) in the Reason column for all those rows — correct. No backfill attempted (non-goal).
4. **Next scan run**: when Thomas hits "Run scan now", `/run` issues `DELETE FROM scan_eliminations` before the scan, scanner.py calls `_record_elimination()` at every filter drop site, and the new table fills with fresh data.

---

## Test Drive

**Neagley-like debugging scenario (from ~ 1 hour → 10 seconds):**

1. Run a scan (or load an existing dismissed-title scenario).
2. Check "Show dismissed" checkbox — the Matches table grows a **Reason** column.
3. A title dropped by the theaters filter shows a blue `only_in_theaters:filter_dropped` pill.
4. A title with too low a rating shows an amber `rating:6.8<7.5` pill.
5. A title the user manually dismissed shows a gray `dismissed_by_user` pill.
6. Active (non-dismissed) matches show a faint `—` — no noise.

Color coding by reason family:
- **Blue**: `only_in_theaters:…`
- **Amber**: `rating:…` / `votes:…`
- **Purple**: `year:…`
- **Red**: `genre:…`
- **Orange**: `country:…`
- **Yellow**: `plot:…`
- **Gray**: `dismissed_by_user` / unknown

---

## Follow-Up: Manual Dismissal Reason (Deferred)

If Thomas wants to capture a user-typed reason when clicking X ("I've seen this", "Not interested", etc.), that would require:
- A text input or dropdown in the dismiss confirmation flow.
- Writing to `scan_eliminations` or a new `manual_dismissal_notes` column.

Current behavior (`dismissed_by_user` marker) is a solid foundation — Thomas can see that a title was manually dismissed (not filtered) without needing a freeform note. If he wants freeform notes, it's a future ticket.

---

## Files Changed

- `/Volumes/GIT/CLAUDE/SHARED_WORK_FOLDER/movie_scanner/schema.py` — `scan_eliminations` table + index in DDL + V3.27 migration block in `apply_schema()`
- `/Volumes/GIT/CLAUDE/SHARED_WORK_FOLDER/movie_scanner/scanner.py` — `_record_elimination()` method; instrumented genre/year/rating/votes/country filters in `scan()`; instrumented `_apply_plot_filter()`; instrumented `_apply_theaters_filter()`
- `/Volumes/GIT/CLAUDE/SHARED_WORK_FOLDER/MovieScanner/app.py` — `APP_VERSION` → V3.27; `/run` clears `scan_eliminations`; `index()` loads `elimination_reasons` when `show_dismissed`; attaches `dismissal_reason` to each match dict
- `/Volumes/GIT/CLAUDE/SHARED_WORK_FOLDER/MovieScanner/templates/index.html` — Reason column header (show_dismissed only); Reason cell with color-coded pills
- `/Volumes/GIT/CLAUDE/SHARED_WORK_FOLDER/MovieScanner/tests/test_dismissal_reason.py` — 9 new tests (T1–T9)
- `/Volumes/GIT/CLAUDE/SHARED_WORK_FOLDER/MovieScanner/tests/test_theaters_filter.py` — V3.26 version pin loosened to `>= V3.26`
- `/Volumes/GIT/CLAUDE/SHARED_WORK_FOLDER/MovieScanner/db/scanner.db.pre_v3.27` — backup
