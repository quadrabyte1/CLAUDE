# v1.7 — Herman date_resolver: roll-forward for past bare month+day

**v1.7** · Rune · 2026-09-21

---

## Root cause

**Two compounding bugs in `_try_absolute_date`:**

1. **Ordinal suffix not stripped.** The regex `^([a-z]+)\s+(\d{1,2})$` requires a bare digit after the month name. "September 20th" normalizes to `"september 20th"` — the `"th"` suffix caused no match, so `_try_absolute_date` returned `None`, `_resolve_day` returned `(None, True, "could not parse day …")`, and Herman responded `stored=False, ambiguous=['day']` with a confusing clarifying question.

2. **30-day heuristic too coarse.** Even for plain "September 20" (no ordinal), the old code used `> 30 days in the past → next year`. On Sept 21, Sept 20 is only 1 day in the past — well inside the 30-day window — so it returned 2026-09-20 (yesterday), not 2027-09-20.

---

## Design rule (v1.7)

When a hint gives **specific month+day but no year**:

| month+day vs today | result |
|---|---|
| `>` today | current year (still upcoming) |
| `==` today | current year (today itself) |
| `<` today | current year + 1 (already passed — roll forward) |

**Ordinal suffixes** (`st`, `nd`, `rd`, `th`) are stripped before parsing.

**Explicit year** (`"September 20th 2027"`) bypasses the roll entirely — the stated year is used as-is.

**Feb 29 in a non-leap year** (see decision below) scans forward to the next actual leap-day.

**Relative expressions** ("tomorrow", "next Tuesday") are untouched — they go through the weekday/relative path, not `_try_absolute_date`.

---

## Red → green

Tests written failing before implementation, then turned green by the fix.

| # | Test | Before | After |
|---|---|---|---|
| 1 | `test_v17_live_regression_sept20_rolls_to_next_year` | FAIL — `ambiguous=['day']` | PASS — `2027-09-20 10:00 EDT`, `ambiguous=[]` |
| 2 | `test_v17_not_yet_past_same_year` (Sept 22nd on Sept 21) | FAIL — `ambiguous=['day']` | PASS — `2026-09-22` |
| 3 | `test_v17_same_day_no_roll` (Sept 21st on Sept 21) | FAIL — `ambiguous=['day']` | PASS — `2026-09-21` |
| 4 | `test_v17_year_boundary_near_future` (Jan 1st on Dec 31) | FAIL — `ambiguous=['day']` | PASS — `2027-01-01` |
| 5 | `test_v17_year_boundary_mid_year` (Dec 31st on Jan 1) | FAIL — `ambiguous=['day']` | PASS — `2026-12-31` |
| 6 | `test_v17_explicit_year_preserved` (Sept 20th 2027 on Sept 21 2026) | FAIL — `ambiguous=['day']` | PASS — `2027-09-20` |
| 7 | `test_v17_feb29_edge_case` (Feb 29th on Mar 1 2026) | FAIL — `ambiguous=['day']` | PASS — `2028-02-29` |
| 8 | `test_v17_relative_day_untouched` ("tomorrow" on Sept 21) | PASS (unchanged path) | PASS |
| 9 | All 21 pre-v1.7 `test_date_resolver.py` tests | 21 PASS | 21 PASS |
| 10 | `test_v17_e2e_sept20_hint_rolls_to_2027_and_written_path_correct` | FAIL — `stored=False` | PASS — `stored=True`, `written_path` in `calendar/2027-09/` |

**Final run: 152/152 passed.**

---

## Feb 29 decision

**Chosen: scan forward to the next real leap-day.**

When the user says "February 29th" on a non-leap year, there is no Feb 29 this calendar year. Three options were considered:

- **Degrade to Feb 28** — silently wrong; the user said "the 29th."
- **Return `ambiguous=['day']`** — honest but adds friction for a well-understood calendar artifact.
- **Scan forward to next leap year** — `_next_feb29(today)` iterates up to 8 years (worst case: just missed 2024, next is 2028). Returns the actual next Feb 29 on or after today.

The scan-forward choice is locked in by `test_v17_feb29_edge_case`: `February 29th` on 2026-03-01 → `2028-02-29`, `ambiguous=[]`.

The user almost certainly means the next leap-day appointment, and getting that date right is worth more than being evasive about the calendar. Silent degradation to Feb 28 would be a date error; the scan makes the intent explicit.

---

## Migration steps for Thomas

1. **Bounce Herman:**
   ```
   launchctl unload ~/Library/LaunchAgents/com.homunculus.brain.plist
   launchctl load  ~/Library/LaunchAgents/com.homunculus.brain.plist
   ```

2. **Verify `/health` shows 1.7.0:**
   ```
   curl -s http://localhost:8765/health | python3 -m json.tool
   ```
   Look for `"package_version": "1.7.0"`.

3. **Your Sept 20 memo.** The voice memo at `~/sprite/inbox/2026-09-21.md` was truncated ("I'm going to tea…") and was already logged with `stored=False`. The cleanest path forward is to record a fresh memo now that the fix is live — voice memos are cheap and a fresh transcript will be clean. Herman will resolve "September 20th at 10am" correctly and write the event to `calendar/2027-09/`.

---

## Files changed

| File | Change |
|---|---|
| `homunculus_brain/date_resolver.py` | Strip ordinal suffixes; add month+day+year parser; replace 30-day heuristic with crisp roll-forward; add `_next_feb29` for leap-day edge case |
| `homunculus_brain/__init__.py` | VERSION `1.6.0` → `1.7.0`, DESIGN_VERSION `1.6` → `1.7` |
| `pyproject.toml` | version `1.6.0` → `1.7.0` |
| `tests/test_date_resolver.py` | 12 new v1.7 tests (ordinals, roll-forward, Feb 29, regression guards) |
| `tests/test_capture_parsed.py` | 1 new e2e test (`test_v17_e2e_sept20_hint_rolls_to_2027_and_written_path_correct`) |

---

## Follow-up recommendations

1. **Re-process Thomas's memo.** See "Migration steps" above.
2. **Consider "Month the Nth" phrasing.** Some people say "September the 20th" — the ordinal is after "the". Current code won't strip "the" before the day number. Low frequency; log for v1.8 if it surfaces.
3. **Explicit-year parse supports one pattern.** `"Month Day Year"` (e.g. "September 20th 2027") is now handled. `"Month Year Day"` and `"Year Month Day"` are not — ISO-8601 already covers the latter. No action needed unless a real utterance hits a different order.
4. **`_SYSTEM_PROMPT` (LLM prompt).** The prompt does not ask a clarifying question about year — that was Herman's `ambiguous=['day']` triggering the router's generic clarifying-question path. With `ambiguous=[]` after this fix, the prompt path is unaffected. No LLM prompt changes required.
