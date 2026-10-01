# v0.2.1 — mac_calendar_bridge slug-collision fix

<!-- v0.2.1 — 2026-09-30 -->

---

## Empirical trace evidence

Bridge log at the moment the "Schedule dinner at 7" memo landed (11:31:35 local):

```
2026-09-30T11:31:35 INFO  Atomic rename detected: 2026-09-30-dinner.md.tmp.867.0 → 2026-09-30-dinner.md
```

No "Pushing event..." line followed. No error. Silent skip.

`pushed.jsonl` had this entry from a **prior session** (8:25 AM EDT same day):

```json
{"event_id": "2026-09-30-dinner", "pushed_at": "2026-09-30T12:25:17.937990+00:00"}
```

The bridge loaded this at startup, loaded 21 event_ids into its in-memory set, and when the new memo landed the fast-path check (`state.is_pushed("2026-09-30-dinner")`) returned `True` — so it logged at `DEBUG` and returned. At `BRIDGE_LOG_LEVEL=INFO` that log line never appears. Thomas sees nothing.

The same thing happened at 11:38:27 and 11:41:03 (two more re-schedules of "dinner" after utterance corrections).

---

## Root cause (concrete)

**Two separate bugs, compounding:**

### Bug A — Slug collision in `vault.event_id()`

`vault.event_id()` generated:

```python
f"{starts_at.date().isoformat()}-{slugify(title)}"
# → "2026-09-30-dinner" for EVERY dinner on Sept 30, regardless of time
```

"Schedule dinner at 7" → `2026-09-30-dinner`  
"Scheduled dinner at 8" → `2026-09-30-dinner`  ← same ID

Once the first is pushed, the second is silently treated as a duplicate forever.

### Bug B — Silent fast-path skip

When `push_if_new` hit the fast-path (`is_pushed()` returned True), it logged:

```python
log.debug("Already pushed %s; skipping", record.event_id)
```

At `INFO` (the default log level), this produced **no output**. Thomas had no way to know the bridge was actively skipping his memo — it looked like the file was never seen.

---

## Files changed

| File | Change |
|------|--------|
| `brain/homunculus_brain/vault.py` | `event_id()` now includes `HHMM` (local): `2026-09-30-1900-dinner` |
| `brain/homunculus_brain/__init__.py` | `VERSION` 2.5.2 → 2.5.3 |
| `mac_calendar_bridge/src/mac_calendar_bridge/watcher.py` | Fast-path skip promoted from `log.debug` to `log.info` with `starts_at` |
| `mac_calendar_bridge/src/mac_calendar_bridge/__init__.py` | `VERSION` 0.2.0 → 0.2.1 |
| `brain/tests/test_vault.py` | Updated hardcoded `event_id` expectation; added regression test |
| `mac_calendar_bridge/tests/test_slug_collision_fix.py` | 11 new RED → GREEN tests (3 bug classes) |

---

## Red → Green table

| # | Test | Before fix | After fix |
|---|------|-----------|----------|
| 1 | `TestVaultEventIdIncludesTime::test_same_day_same_title_different_hour_produces_different_ids` | RED — both dinner IDs = `2026-09-30-dinner` | GREEN |
| 2 | `TestVaultEventIdIncludesTime::test_event_id_contains_time_component` | RED — bare date-only slug | GREEN |
| 3 | `TestDistinctEventIdsBothPushed::test_two_dinners_at_different_times_both_pushed` | RED — second dinner silently skipped | GREEN |
| 4 | `TestDistinctEventIdsBothPushed::test_second_dinner_not_skipped_when_first_already_pushed` | RED — same | GREEN |
| 5 | `TestSkipVisibility::test_already_pushed_skip_logged_at_info` | RED — only DEBUG, invisible at INFO | GREEN |
| 6 | `TestSkipVisibility::test_skip_log_includes_event_id` | RED — no INFO record at all | GREEN |
| 7–11 | `TestPermissionDeniedVisibility` (3 subtests) + `TestVaultEventIdIncludesTime` regression guards | All GREEN (existing behaviour confirmed) | GREEN |

Full suites: **176 bridge tests + 394 brain tests = 570 total, all passing** (+ 2 skipped macOS-only on Linux).

---

## Test drive

After restarting the bridge (`mac_calendar_bridge v0.2.1 starting` confirmed in `/tmp/mac_calendar_bridge.log`):

Dictate **"Schedule dinner at 7"** → Herman resolves to 7:00 PM EDT → writes:

```
vault/calendar/2026-09/2026-09-30-1900-dinner.md   (id: 2026-09-30-1900-dinner)
```

Bridge log will show:

```
INFO  Atomic rename detected: 2026-09-30-1900-dinner.md.tmp.XXX.N → 2026-09-30-1900-dinner.md
INFO  Pushing event 'dinner' (vault title: 'dinner') (2026-09-30-1900-dinner) → Calendar 'Homunculus'
INFO  Event '2026-09-30-1900-dinner' pushed successfully
```

Event appears in Calendar.app "Homunculus" within 2–3 seconds.

If you then dictate **"Scheduled dinner at 8"** (a correction), Herman writes:

```
vault/calendar/2026-09/2026-09-30-2000-dinner.md   (id: 2026-09-30-2000-dinner)
```

Bridge pushes that too (distinct ID). Both dinner events appear on the calendar — one at 7:00 PM, one at 8:00 PM.

**If you only want the 8 PM one**, delete the 7 PM event from Calendar.app manually (or use Herman's delete verb when it exists). The vault file remains; the bridge will not re-push an event that's already in pushed.jsonl.

---

## What happened to the old `2026-09-30-dinner`?

The event written by the earlier test session (at 8:25 AM EDT) is still in `pushed.jsonl` as `2026-09-30-dinner` and still in the vault as `vault/calendar/2026-09/2026-09-30-dinner.md`. If it was successfully pushed to Calendar.app at 8:25 AM, it's in your calendar. If not, the slow-path query check will handle it on the next cold-boot. Either way, new memos will not conflict with it because they get the new `HHMM`-stamped slugs.

---

## Re-auth reminder (not needed here)

No Calendar.app permission issues were found. The bridge had valid Calendar.app access throughout — the failure was purely a slug collision + silent logging issue.

---

## Notes on the "Meeting at 9 in the morning" test

The log shows `"Meeting at ten in the morning"` and `"Meeting at eight in the morning"` both parsed and wrote successfully post-v2.5.2. The `2026-09-30-meeting` entry in pushed.jsonl was pushed at `2026-09-30T12:46:21Z` (= 8:46 AM EDT) — before the second bridge start. Any new "meeting" capture at a **different time** will now get a unique ID (e.g. `2026-09-30-0900-meeting`) and will be pushed without conflict.

---

*Brain v2.5.3 / Bridge v0.2.1 — Rune — 2026-09-30*
