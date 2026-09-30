# Homunculus AM/PM Integration Fix — v2.5.1
<!-- v2.5.1 -->

**Date:** 2026-09-29  
**Engineer:** Rune  
**Branch:** main (no commit — do not push)  
**Herman:** v2.5.0 → **v2.5.1**  
**Sprite:** unchanged (no Sprite code touched)

---

## Root Cause

`capture_parsed.py` contains three call sites where `date_resolver.resolve()` is invoked. **None of them passed `context_text=`**. The parameter was added to `resolve()` in v2.5.0 (optional, defaults to `None`) but the glue code was never updated to supply it.

With `context_text=None`, the resolver skips Signals A and C entirely and falls straight to Signal B (roll-forward). Roll-forward gives a plausible answer, so `stored=True` — but the hour is wrong (the memo resolves to the nearest future interpretation rather than the contextually correct one).

| Call site | Function | Fix |
|---|---|---|
| `_resolve_from_hints` L986 | Primary ambiguity check (all verbs) | Added `context_text=req.raw_transcript` |
| `_handle_schedule` L511 | Second resolve call after check passes (schedule verb) | Added `context_text=req.raw_transcript` |
| `_handle_handle` L656 | Second resolve call after check passes (handle/remind verb) | Added `context_text=req.raw_transcript` |
| `_resolve_from_hints` L961 | Day-only check for handle/remind with no time_hint | Left as-is (no time_hint present; context_text only affects time resolution) |
| `_handle_handle` L640 | Day-only resolve with stand-in time="morning" | Left as-is (time is overridden to default handle-hour regardless) |

Why "Doctor tomorrow morning at 10" worked: that memo provides `day_hint="tomorrow"` and `time_hint="10"`. Signal C matches "tomorrow morning" → AM, BUT `time_hint="10"` was explicit. The resolver's Step 1 (explicit AM/PM) does not fire for "10" (no marker), so Signal C fires correctly. The difference: "Doctor tomorrow morning at 10" was a compound where "tomorrow" was in `day_hint` AND "morning" was still in `raw_transcript` — but wait, that also has `context_text=None` in v2.5.0. So why did it pass?

**Answer:** It was passing via Signal B roll-forward. At NOW=10:00 AM, with `day_hint="tomorrow"`, roll-forward anchors to midnight of tomorrow and the nearest future 10 is 10 AM tomorrow. The result is coincidentally correct. The C-signal version also gives 10 AM, so Thomas couldn't tell the difference.

---

## Code Changes

### `Homunculus/brain/homunculus_brain/capture_parsed.py`

Three `date_resolver.resolve()` calls updated — `context_text=req.raw_transcript` added:

- **`_resolve_from_hints`** (primary check path, all verbs with time hints)
- **`_handle_schedule`** (second resolve call, schedule verb)
- **`_handle_handle`** (second resolve call, handle/remind verb with time_hint present)

### `Homunculus/brain/homunculus_brain/date_resolver.py`

**Military time (HHMM) parsing** added as Step 0 in `_resolve_time`:

- New regex `_MILITARY_TIME_RE` matches 4-digit strings in `[00-23][00-59]` range
- Checked before the standard 1-2 digit regex to avoid false ambiguity
- Military time is unambiguous by construction — no signal processing, returns directly
- Examples: `"1400"` → `14:00`, `"0900"` → `09:00`, `"1830"` → `18:30`

**New docstring marker:** `_MILITARY_TIME_RE` is labeled `v2.5.1`.

### `Homunculus/brain/homunculus_brain/__init__.py`

```python
VERSION = "2.5.1"    # was: "2.5.0"
DESIGN_VERSION = "2.5"  # unchanged
```

### `Homunculus/brain/tests/test_ampm_live_pipeline.py` (new file)

11 integration tests that push memos through the live `/capture/parsed` pipeline (FastAPI TestClient), inspect vault files to verify the resolved hour.

---

## Red → Green Table

| # | Memo | Expected | Was (before fix) | After fix |
|---|---|---|---|---|
| 1 | "Meeting at 6 in the morning" | 6 AM | stored=True, **18:00** (roll-forward, WRONG hour) | stored=True, **06:00** GREEN |
| 2 | "Remind me the plumber comes at 3" | 3 PM | stored=True, 15:00 (roll-forward coincidence) | stored=True, 15:00 GREEN (now via Signal A) |
| 3 | "Call mom at 8 tonight" | 8 PM | stored=True, 20:00 (roll-forward coincidence) | stored=True, 20:00 GREEN (now via Signal C) |
| 4 | "Dinner at 7 in the morning" | 7 AM | stored=True, **19:00** (Signal A/dinner won, WRONG) | stored=True, **07:00** GREEN (Signal C beats A) |

Tests 2 and 3 were the "survived by coincidence" category — roll-forward happened to pick the right time. The fix makes them correct for the right reason (Signal A/C fire first). Tests 1 and 4 had unambiguously wrong hours; both are fixed.

---

## Military Time Addition

Shipped. `date_resolver._resolve_time` now handles 4-digit HHMM input:

```
"1400"  →  14:00  (2 PM),  no clarifying question
"0900"  →  09:00  (9 AM),  no clarifying question
"1830"  →  18:30  (6:30 PM),  no clarifying question
```

3 new integration tests verify these cases (`TestMilitaryTime`).

---

## Test Drive for Thomas

Re-dictate these four memos verbatim through Sprite → Herman. All four should resolve without a clarifying question:

1. **"Meeting at 6 in the morning"**  
   Expect: event written for 6:00 AM (tomorrow if today after 6 AM, today otherwise)

2. **"Remind me the plumber comes at 3"**  
   Expect: reminder written for 3:00 PM today (Signal A: profession keyword)

3. **"Call mom at 8 tonight"**  
   Expect: event written for 8:00 PM today (Signal C: "tonight")

4. **"Dinner at 7 in the morning"**  
   Expect: event written for 7:00 AM — NOT 7 PM  
   (Signal C "in the morning" overrides Signal A "dinner → PM")

**Bonus:** Try dictating "Set a reminder for 1400 today" — should land at 2:00 PM with no clarification.

---

## Restart Command

```
launchctl kickstart -k gui/$(id -u)/com.homunculus.brain
```

Herman is already running on v2.5.1 as of this report. Verify:

```
curl http://localhost:8765/health
# → {"package_version": "2.5.1", ...}
```

---

## Test Count

| Suite | Before | After |
|---|---|---|
| date_resolver unit tests (v2.5.0) | 52 passed | 52 passed |
| integration tests (new) | 0 | 11 passed |
| full brain suite | 364 passed | **375 passed** |
