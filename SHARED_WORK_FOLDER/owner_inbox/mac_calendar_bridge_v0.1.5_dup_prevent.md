# mac_calendar_bridge v0.1.5 — Dup-Prevention Hardened

**v0.1.5** | 2026-09-14 | Rune

---

## Root Cause: Bug 1 — Belt-and-Suspenders Not Wired

`push_if_new()` in `watcher.py` only checked `pushed.jsonl` (the fast lane).
`query_pushed_event_ids()` in `applescript.py` existed since v0.1.0 but was
**never called** — it was designed as the authoritative second check but never
wired in.

**What went wrong during v0.1.4 migration:**
Thomas ran `rm ~/.local/share/mac_calendar_bridge/pushed.jsonl` to force
clean re-render of `[handle]` titles. Bridge cold-booted, `pushed.jsonl` was
empty, so `state.is_pushed()` returned False for every event. All 5 events
were re-pushed → 5 duplicates in Calendar.app.

---

## Root Cause: Bug 2 — Two-Step URL Set Causes Silent Calendar.app Rollback

The AppleScript in `push_event()` used a two-step pattern:
```applescript
set newEvent to make new event with properties {summary:"...", start date:..., end date:...}
set url of newEvent to "homunculus://event/..."
```

On macOS 15.x Calendar.app builds, `set url of newEvent` can silently fail or
trigger an internal rollback that discards the event without giving osascript
a non-zero exit code. The result: `run_applescript()` returns 0, the bridge
logs "Event pushed successfully", but no event materialises in Calendar.app.

This is why `2026-09-18-code-review-with-myself` disappeared — the bridge
believed it pushed it (pushed.jsonl has the entry), but Calendar.app rolled
it back. Verified: the `format_applescript_date()` output for Friday Sep 18 is
correct ("Friday, September 18, 2026 at 10:00 AM") — the date format was never
the issue.

---

## Fixes Shipped

### Bug 1 fix — `watcher.py: push_if_new()`

Added `_midnight_date_str()` helper and a three-step idempotency ladder:

1. **Fast path** — `state.is_pushed()` (in-memory / pushed.jsonl). If hit → skip immediately, no Calendar.app round-trip.
2. **Slow path** (new) — `query_pushed_event_ids(calendar_name, midnight_date_str)`. If event_id found in Calendar → self-heal pushed.jsonl, log `"Self-heal: <id> already in Calendar.app but missing from pushed.jsonl"`, skip.
3. **Push** — only if both checks say "not present" → `push_event()` then `mark_pushed()`.

The slow path is guarded: if `query_pushed_event_ids` raises `AppleScriptError` or `NotImplementedError` (Linux), it logs DEBUG and falls through to push (safe degradation).

### Bug 2 fix — `applescript.py: push_event()`

Changed from two-step to single atomic make-with-properties:

```applescript
-- BEFORE (broken — two-step, url can roll back):
set newEvent to make new event with properties {summary:"...", start date:..., end date:...}
set url of newEvent to "homunculus://event/..."

-- AFTER (fixed — atomic, url in properties dict):
make new event with properties {summary:"...", start date:..., end date:..., url:"homunculus://event/..."}
```

---

## Red → Green Tables

### Bug 1 tests (test_watcher.py::TestPushIfNewBeltAndSuspenders)

| # | Test | Before | After |
|---|------|--------|-------|
| 1 | `test_bug1_calendar_already_has_event_no_push_when_jsonl_wiped` | FAIL | PASS |
| 2 | `test_bug1_self_heal_writes_to_jsonl_when_found_in_calendar` | FAIL | PASS |
| 3 | `test_bug1_self_heal_message_logged` | FAIL | PASS |
| 4 | `test_bug1_normal_push_path_still_works` | FAIL | PASS |
| 5 | `test_bug1_query_not_called_when_fast_path_hits` | FAIL | PASS |
| 6 | `test_bug1_query_date_str_is_midnight_on_event_date` | FAIL | PASS |

### Bug 2 tests (test_applescript.py::TestPushEventUrlInProperties)

| # | Test | Before | After |
|---|------|--------|-------|
| 1 | `test_url_in_make_properties_not_separate_set` | FAIL | PASS |
| 2 | `test_no_separate_set_url_statement_for_any_event` | FAIL | PASS |
| 3 | `test_applescript_error_propagates_loudly` | PASS | PASS |
| 4 | `test_friday_event_url_included_in_make_properties` | FAIL | PASS |

### Full suite

| Suite | Pre-fix | Post-fix |
|-------|---------|----------|
| Pre-existing tests | 155 pass, 2 skip | 155 pass, 2 skip |
| New Bug 1 tests | — | 6 pass |
| New Bug 2 tests | — | 4 pass |
| **Total** | **155 pass** | **165 pass, 2 skip** |

---

## Files Changed

- `src/mac_calendar_bridge/__init__.py` — VERSION 0.1.4 → 0.1.5
- `pyproject.toml` — version 0.1.4 → 0.1.5
- `src/mac_calendar_bridge/watcher.py` — import `query_pushed_event_ids` + `format_applescript_date`; add `_midnight_date_str()`; rewrite `push_if_new()` with 3-step ladder + self-heal
- `src/mac_calendar_bridge/applescript.py` — `push_event()` script: url included in `make new event with properties` dict (atomic), `set url of newEvent` removed
- `tests/test_watcher.py` — `TestPushIfNewBeltAndSuspenders` class (6 tests)
- `tests/test_applescript.py` — `TestPushEventUrlInProperties` class (4 tests)

---

## Migration Commands (DO NOT rm pushed.jsonl this time)

```bash
# 1. Unload the bridge
launchctl unload ~/Library/LaunchAgents/com.homunculus.mac_calendar_bridge.plist

# 2. Leave pushed.jsonl alone — the self-heal will reconcile it from Calendar.app

# 3. Install v0.1.5
bash /Volumes/GIT/CLAUDE/SHARED_WORK_FOLDER/Homunculus/mac_calendar_bridge/deploy/install.sh

# 4. Load the bridge
launchctl load ~/Library/LaunchAgents/com.homunculus.mac_calendar_bridge.plist

# 5. Watch the log
tail -f /tmp/mac_calendar_bridge.log
```

### What to look for in the log

- `Self-heal: <event_id> already in Calendar.app but missing from pushed.jsonl; healing pushed.jsonl and skipping push` — for each event that was already in Calendar (self-heal working)
- `Event '2026-09-18-code-review-with-myself' pushed successfully` — for the Sep 18 event that was missing (Bug 2 fix working)
- **No** `Pushing event ...` followed by the same event again → confirms no duplicates

### After the log looks clean

Open Calendar.app and verify:
- Sep 18 "code review with myself" appears at 10:00 AM
- It syncs to your phone within a few minutes
- No duplicate events for Sep 15 or any other date
