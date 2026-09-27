# MovieScanner V3.25 — Only In Theaters Filter

**v3.25** · Sienna · 2026-09-27

---

## Semantic Table

| Checkbox state | Behavior |
|---|---|
| **Unchecked** (default) | Titles still only in theaters (no home-video/streaming date yet) are **excluded** from the matches list. Only titles that are actually streaming/on home video appear. |
| **Checked** | All titles are permitted, including ones still only in theaters. Previous V3.24 behavior is restored. |

Default is unchecked — doesn't waste your eyeballs on titles you can't watch tonight.

---

## `is_only_in_theaters` Heuristic

Module-level function in `movie_scanner/scanner.py`. Takes the OMDb response dict and a reference `date`.

**Constant:** `THEATRICAL_WINDOW_DAYS = 180` — 6 months covers the typical 90-day theatrical window plus a buffer for delayed home-video announcements. After this window, a title with no DVD info is assumed to be streaming somewhere.

**Decision tree:**

1. **Series** (`Type == "series"`) — never in theaters → `False`.
2. **DVD field is a parseable date:**
   - Past or today → already on home video → `False`.
   - Future date → not yet on home video → `True`.
3. **DVD is "N/A" or absent** — fall back to theatrical-release heuristic:
   - `Released` parses + is within `THEATRICAL_WINDOW_DAYS` of today → `True`.
   - `Released` parses + is older than `THEATRICAL_WINDOW_DAYS` → `False`.
4. **No usable date signal** → `False` (don't over-filter unknowns).

**The 8 cases:**

| # | Scenario | Result | Reason |
|---|---|---|---|
| 1 | DVD = past date | `False` | Already on home video |
| 2 | DVD = future date | `True` | Still in theaters (pre-home-video) |
| 3 | DVD = N/A, Released 30 days ago | `True` | Within 180-day theatrical window |
| 4 | DVD = N/A, Released 200 days ago | `False` | Past THEATRICAL_WINDOW_DAYS (180) |
| 5 | DVD = N/A, Released = N/A | `False` | Unknown → don't over-filter |
| 6 | Type = "series", any dates | `False` | Series never in theaters |
| 7 | Malformed DVD, Released 30 days ago | `True` | DVD parse fails → falls back to Released |
| 8 | Malformed DVD + malformed Released | `False` | No usable signal → don't over-filter |

---

## Where the Checkbox Sits in the UI

The **Only In Theaters** checkbox is placed in the Filter configuration section of `MovieScanner/templates/index.html`, between the Genres grid and the Content-severity filters `<details>` block.

It renders as a simple `label + checkbox` row, styled consistently with the other checkboxes in the form (e.g. "Exclude titles with missing parental-guide data").

---

## Red → Green Table

All tests written before implementation. All RED on the V3.24 codebase, all GREEN after.

| Test class | Test | Result |
|---|---|---|
| `TestIsOnlyInTheaters` | `test_case1_dvd_past_date_returns_false` | GREEN |
| `TestIsOnlyInTheaters` | `test_case2_dvd_future_date_returns_true` | GREEN |
| `TestIsOnlyInTheaters` | `test_case3_no_dvd_recent_release_returns_true` | GREEN |
| `TestIsOnlyInTheaters` | `test_case4_no_dvd_old_release_returns_false` | GREEN |
| `TestIsOnlyInTheaters` | `test_case5_no_dvd_no_released_returns_false` | GREEN |
| `TestIsOnlyInTheaters` | `test_case6_series_always_false` | GREEN |
| `TestIsOnlyInTheaters` | `test_case7_malformed_dvd_falls_back_to_released` | GREEN |
| `TestIsOnlyInTheaters` | `test_case8_malformed_both_returns_false` | GREEN |
| `TestApplyTheatersFilter` | `test_unchecked_filters_out_theaters_only_title` | GREEN |
| `TestApplyTheatersFilter` | `test_checked_passes_everything_through` | GREEN |
| `TestApplyTheatersFilter` | `test_unchecked_no_omdb_data_passes_through` | GREEN |
| `TestTheatersFilterConfig` | `test_checkbox_state_persists_unchecked` | GREEN |
| `TestTheatersFilterConfig` | `test_checkbox_state_persists_checked` | GREEN |
| `TestTheatersFilterConfig` | `test_config_export_includes_only_in_theaters` | GREEN |
| `TestTheatersFilterConfig` | `test_config_import_restores_only_in_theaters` | GREEN |
| `TestRegressionV325` | `test_app_version_is_v3_25` | GREEN |

**Full suite: 62/62 passed.**

---

## Test-Drive Instructions

1. **Scan with checkbox OFF (default):** After restarting the server, run a scan. Titles released within the last 6 months that have no DVD date on OMDb will be excluded. Expect fewer results than V3.24 for recent releases.

2. **Toggle ON:** Check "Only In Theaters" in the Filter configuration section, save (auto-saves on change), then run again. Those previously-excluded titles now appear — previous V3.24 behavior returns.

3. **Config export/import:** Export config, verify `"only_in_theaters"` key appears in the JSON. Import the file back; the checkbox should restore to whatever state you exported.

---

## Files Changed

- `MovieScanner/app.py` — `APP_VERSION` bumped V3.24 → V3.25; `only_in_theaters` added to `_save_config_from_form`.
- `MovieScanner/templates/index.html` — "Only In Theaters" checkbox added between genres and content-severity sections.
- `movie_scanner/scanner.py` — `THEATRICAL_WINDOW_DAYS`, `parse_omdb_date`, `is_only_in_theaters` module-level exports; `_apply_theaters_filter` method on `Scanner`; wired into `scan()` as step 3d after plot_filter.
- `movie_scanner/omdb.py` — `dvd` and `type` fields added to `_FIELDS`, `_load_cache`, `_fetch_from_api`, `_error_dict`, `_save_cache`.
- `movie_scanner/schema.py` — `dvd`/`type` columns added to `title_metadata` DDL + live migration; `only_in_theaters='0'` seeded into config defaults + migration block.
- `MovieScanner/tests/test_theaters_filter.py` — new test file (16 tests, all green).
- `MovieScanner/tests/test_config_backup.py` — version-pin guard updated V3.24 → V3.25.
- `MovieScanner/tests/test_plot_filter.py` — version-pin guard updated V3.24 → V3.25.
