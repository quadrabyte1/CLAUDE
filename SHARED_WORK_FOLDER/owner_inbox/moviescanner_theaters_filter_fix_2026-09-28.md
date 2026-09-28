# MovieScanner Theaters Filter Fix — V3.26

**v3.26** · 2026-09-28 · Sienna

---

## Part B — Durable Fix (shipped first)

### Root Cause

`_apply_theaters_filter` (V3.25) called `is_only_in_theaters(omdb_response, today)` which checked `omdb_response["Type"]` to short-circuit series detection. But 366 of 370 `title_metadata` rows pre-dated the V3.25 schema addition of `dvd`/`type` columns — those rows had `type=NULL`. So `Neagley` (`tt33539520`, tvSeries, released 12 days ago) fell through to the theatrical-window heuristic: released within 180 days → `is_only_in_theaters()` returned `True` → dropped when checkbox unchecked.

The fix was not in `is_only_in_theaters()` (which was correct for movies). The fix was in `_apply_theaters_filter`: use `title_type` from the **IMDb match row** (column index 3, always populated from `titles.title_type`) as the authoritative kind-of-title signal. OMDb `type` is a cache field that may be stale; `titles.title_type` comes from the official IMDb basics dump.

### Code Change

**`/Volumes/GIT/CLAUDE/SHARED_WORK_FOLDER/movie_scanner/scanner.py`**

Added class-level constant:
```python
_NON_THEATRICAL_TYPES = frozenset({
    "tvSeries", "tvMovie", "tvEpisode", "tvMiniSeries", "tvSpecial",
})
```

Inside `_apply_theaters_filter`, before any OMDb call:
```python
title_type: str = match_row[3] if len(match_row) > 3 else "movie"

# V3.26 short-circuit: non-theatrical title types are never in cinemas
if title_type in self._NON_THEATRICAL_TYPES:
    kept.append(match_row)
    continue

# Only run OMDb check for movies; safe default for other types
if title_type != "movie":
    kept.append(match_row)
    continue

# ... existing OMDb DVD/Released heuristic for movies unchanged
```

`is_only_in_theaters()` is untouched — its signature and behavior are preserved.

### File Paths

- **Core fix:** `/Volumes/GIT/CLAUDE/SHARED_WORK_FOLDER/movie_scanner/scanner.py` (method `_apply_theaters_filter`, new class var `_NON_THEATRICAL_TYPES`)
- **Version bump:** `/Volumes/GIT/CLAUDE/SHARED_WORK_FOLDER/MovieScanner/app.py` (`APP_VERSION = "V3.26"`)
- **New tests:** `/Volumes/GIT/CLAUDE/SHARED_WORK_FOLDER/MovieScanner/tests/test_theaters_filter.py`

### RED → GREEN Table

| # | Test | Before | After |
|---|------|--------|-------|
| B1 | tvSeries + empty OMDb type + released 12 days ago → passes when unchecked | FAIL (dropped=1) | PASS |
| B2 | movie + no DVD + released 30 days ago → dropped when unchecked | PASS | PASS |
| B3 | movie + past DVD → passes when unchecked | PASS | PASS |
| B4 | only_in_theaters=True bypasses all filtering | PASS | PASS |
| B5 | tvMovie + empty OMDb type → never filtered | FAIL (dropped=1) | PASS |
| — | APP_VERSION == V3.26 | FAIL (got V3.25) | PASS |
| — | All 16 prior V3.25 theaters tests | PASS | PASS |

**Total: 22/22 GREEN. Full suite: 117/117 GREEN.**

---

## Part A — OMDb type/dvd Backfill

### Script Location

`/Volumes/GIT/CLAUDE/SHARED_WORK_FOLDER/MovieScanner/scripts/backfill_omdb_type_dvd.py`

Tests: `/Volumes/GIT/CLAUDE/SHARED_WORK_FOLDER/MovieScanner/tests/test_backfill_omdb_type_dvd.py` (9/9 GREEN, temp DB only — never touched live DB)

### Live Backfill Run Stats

- **Rows needing refresh:** 367
- **Backup created:** `MovieScanner/db/scanner.db.pre_backfill_2026-09-28`
- **refreshed=307, errored=60, elapsed=128s**

### Error Analysis

60 errors, two categories:

1. **3 errors — "Error getting data."** (OMDb server-side issue for these specific tconsts):
   - `tt33095205`, `tt38126135`, `tt42273710`

2. **57 errors — "Incorrect IMDb ID."** All are high-numbered tconsts (tt43xxx–tt45xxx range). These appear to be very new or pre-release titles that OMDb doesn't yet have indexed. These rows remain with `type=NULL`/`dvd=NULL`. This is the expected error state — the next time a scan fetches them, if OMDb has them by then, they'll be updated. The V3.26 short-circuit handles them correctly anyway: `tvSeries` rows short-circuit on `title_type` before touching OMDb.

All 60 errored tconsts are listed in the backfill output log.

---

## Neagley Verification

**Will Neagley appear on the next scan?**

Yes. Two independent reasons:

1. **V3.26 fix (durable):** `tt33539520` has `titles.title_type='tvSeries'`. The filter now short-circuits on `title_type in _NON_THEATRICAL_TYPES` before any OMDb call. Even if OMDb's cache row had an empty `type`, Neagley passes.

2. **Backfill (belt-and-suspenders):** `tt33539520` was successfully refreshed. OMDb now returns `type='series'` for this tconst. Verified:
   ```
   sqlite> SELECT tconst, type, dvd, released FROM title_metadata WHERE tconst='tt33539520';
   tt33539520|series||16 Sep 2026
   ```
   (`dvd` is still empty — OMDb has no DVD date for it yet, which is correct for a current streaming series.)

### Population Size

`SELECT COUNT(*) FROM titles WHERE title_type IN ('tvSeries','tvMiniSeries','tvMovie','tvSpecial','tvEpisode')` → **462,272 rows**

This is the population that was potentially being misclassified by the V3.25 bug when their OMDb cache had empty `type` and they had a recent `released` date.

---

## Follow-Up: Part C Still Open

**Part C** (auto-invalidate cache inside `fetch()` when critical fields like `type`/`dvd` are NULL) was **explicitly deferred by Thomas**. Not implemented here. The backfill script is the one-shot remedy; Part C would make this self-healing on the next fetch cycle for any future stale rows.

Tracked as a future task.

---

*Handoff by Sienna — task 644 closed.*
