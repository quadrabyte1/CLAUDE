# MovieScanner V3.24 — Skip Matches With No OMDb Plot

**v3.24** · Sienna · 2026-09-27

---

## What "can't be fetched" means (5 cases)

All 5 cases already flow through `OMDbClient._fetch_from_api()`, which normalises every failure to `plot=None`:

| # | Condition | What OMDbClient returns |
|---|-----------|------------------------|
| 1 | HTTP error or non-200 status | `plot=None, error="Network error: …"` |
| 2 | OMDb responds `{"Response":"False"}` (title not in OMDb) | `plot=None, error="Movie not found!"` |
| 3 | OMDb returns `Plot:"N/A"` (obscure title, no plot data) | `plot=None` (the existing `_clean()` function normalises "N/A" to None) |
| 4 | Network timeout / connection exception | `plot=None, error="Network error: timed out"` |
| 5 | Missing `Plot` key in the JSON response | `plot=None` (dict.get() returns None) |

The filter rule is simply: **if `plot` is `None` → drop the title.**

---

## Fetch timing choice: eager at match-time

**Decision: eager** — OMDb is called for every surviving candidate during the scan's new `plot_filter` phase.

**Why not lazy (on hover)?**
Thomas's words: "just skip it as if it was not a match." That requires knowing about the plot *before* the title lands in the matches list. Lazy fetch (on hover) would show the title in the table and only hide it when the user moves the mouse over it — not what he asked for.

**Why eager is fine here:**
- The `title_metadata` SQLite cache makes re-scans essentially free. A tconst that was checked in any prior scan is served from the DB with zero network calls.
- Titles that reach the plot-filter phase have already survived rating, vote, year, genre, country, and (optionally) parental-guide filters — so the set is bounded. Thomas's typical scans produce ~50–200 surviving candidates, not thousands.
- The existing country filter (`exclude_countries`) does exactly the same eager OMDb pattern and has been running in production since V3.x.

**Fail-open behaviour:**
If no OMDb API key is configured, the plot-filter phase is skipped and all titles pass through unchanged. This preserves the pre-V3.24 experience for key-less installs and matches the country-filter precedent.

---

## Cache strategy

No schema changes needed. The existing `title_metadata` table already stores:
- `plot TEXT` — set to the plot string on success, or `NULL` on failure.
- `error TEXT` — set to a descriptive message on failure, or `NULL` on success.
- `fetched_at TEXT` — timestamp of the most-recent fetch.

The `OMDbClient` already caches every fetch result (success or failure) in this table, so:
- **Cache hit on success** → plot served from SQLite, no API call, title passes filter.
- **Cache hit on failure** → `plot=NULL` served from SQLite, no API call, title excluded.
- **Cache miss** → network call made, result written to cache, filter applied.

On re-scans, titles that previously had their plot fetched (pass or fail) do not re-hit the OMDb API. Only genuinely new tconsts (never seen before) pay the network cost.

**No TTL or stale-retry policy was added** in this version. The assignment scope said "fresh policy from this scan forward is fine." A future V3.x can add a `fetched_at < 90 days` re-fetch if OMDb's data catches up for previously-missing titles.

---

## API budget impact estimate

OMDb free tier: 1,000 requests/day.

- Re-scans are free for any tconst already in `title_metadata` (cache hit).
- Only *new* titles since the last scan pay the API cost.
- Thomas's typical daily delta is small (IMDb adds ~dozens of high-rating titles per day that match his filters). Budget impact: negligible for normal use.
- Worst case: first scan after `Clear all` with many new titles. Even then the plot-filter runs after rating/vote/year/genre/country filters, so only the survivors are checked — not the full millions of IMDb titles.

---

## Red → Green table

| # | Test | Description | Before | After |
|---|------|-------------|--------|-------|
| 1 | `test_case1_http_error_excluded` | HTTP error for B → [A, C] returned | RED | GREEN |
| 2 | `test_case2_response_false_excluded` | OMDb Response=False → excluded | RED | GREEN |
| 3 | `test_case3_plot_na_excluded` | Plot:"N/A" → excluded | RED | GREEN |
| 4 | `test_case4_timeout_excluded` | Timeout → excluded | RED | GREEN |
| 5 | `test_case5_valid_plot_included` | Valid plot → included (regression guard) | RED | GREEN |
| 6 | `test_case6_cached_failure_no_new_call` | Cached failure → excluded, no API call | RED | GREEN |
| 7 | `test_case7_all_fail_returns_empty` | All fail → empty list, no exception | RED | GREEN |
| 8 | `test_case8_no_api_key_fail_open` | No API key → all pass, no OMDb call | RED | GREEN |
| 9 | `test_app_version_is_v3_24` | APP_VERSION = V3.24 | RED | GREEN |
| — | `test_valid_plot_returned` | OMDb unit: valid plot → plot field set | already GREEN | GREEN |
| — | `test_plot_na_normalised_to_none` | OMDb unit: N/A → None | already GREEN | GREEN |
| — | `test_response_false_sets_error` | OMDb unit: Response=False → error | already GREEN | GREEN |
| — | `test_network_error_sets_error` | OMDb unit: URLError → error | already GREEN | GREEN |
| — | `test_cached_failure_no_new_call` | OMDb unit: cached miss → no HTTP call | already GREEN | GREEN |

Full suite: **46 tests, 46 passed** (30 existing V3.23 tests + 16 new V3.24 tests).

---

## Test-drive instructions

1. Make sure port 5053 is running (or start it: `python MovieScanner/app.py`).
2. Open http://localhost:5053 and confirm the footer shows **V3.24**.
3. Run a scan (`▶ Run scan now`). The Recent runs table will show a new `plot_filter` phase in the status column while the scan is in progress.
4. When the scan completes, the matches list will only show titles for which OMDb returned a real plot. Hover any title — the tooltip should always show a plot (never blank).
5. To see the filter in action explicitly: run this in a Python shell to count how many cached failures exist in `title_metadata`:

   ```python
   import sqlite3
   conn = sqlite3.connect("MovieScanner/db/scanner.db")
   row = conn.execute(
       "SELECT COUNT(*) FROM title_metadata WHERE plot IS NULL"
   ).fetchone()
   print(f"{row[0]} titles cached as no-plot")
   ```

   After a scan, any tconst with a cached failure that previously appeared in matches will be absent from the new matches list.

---

## Files changed

- `/Volumes/GIT/CLAUDE/SHARED_WORK_FOLDER/movie_scanner/scanner.py` — added `_apply_plot_filter()` method; added call site in `scan()` after parental-guide filter (phase `plot_filter`).
- `/Volumes/GIT/CLAUDE/SHARED_WORK_FOLDER/MovieScanner/app.py` — `APP_VERSION` bumped V3.23 → V3.24.
- `/Volumes/GIT/CLAUDE/SHARED_WORK_FOLDER/MovieScanner/tests/test_plot_filter.py` — new test file (16 tests).
- `/Volumes/GIT/CLAUDE/SHARED_WORK_FOLDER/MovieScanner/tests/test_config_backup.py` — updated `test_app_version_is_v3_23` → `test_app_version_is_v3_24` (version assertion kept current).

No schema changes. No template changes. No new dependencies.
