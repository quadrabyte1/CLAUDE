# Schedule Bare-Hour PM Inference — Sprite v0.8.0 + Herman v1.8.0

**v0.8 / v1.8** · 2026-09-21 · Rune

---

## Root Cause + User-Granted Design Rule

**Live incident (13:36 EDT, 2026-09-21):** Thomas said "Let's set Jake's VCA annual check-up on September 20th at three." Whisper confidence 0.844 — clean transcript. Ollama correctly parsed `verb=schedule, time_hint="three"` but, per the existing AM/PM rule, emitted `ambiguous_fields=["time_hint"]`. Sprite's gate fired and routed the record to `~/sprite/inbox/2026-09-21.md`. The record never reached Herman.

**Thomas's direction:** "A whole chunk of the day that they can't possibly be scheduled. And if I put something at 3 and I meant it to be at 3 AM, that's on me to correct it."

**Locked design rule:** For `verb=schedule` AND `time_hint` is a bare hour in {1, 2, 3, 4, 5} (no AM/PM, no minutes qualifier, no "in the morning"):
- Resolve to PM. Do NOT flag `ambiguous_fields=["time_hint"]`.
- User can override by saying "3 AM" explicitly.
- Hours 6-12: still ambiguous for all verbs (6 AM breakfast call vs 6 PM dinner are both common).
- `handle` / `remind` bare hours: still ambiguous (reminders can legitimately fire at 3 AM — medication, alarms).

---

## Files Changed

### Sprite v0.8.0

| File | Change |
|---|---|
| `Sprite/src/sprite/parse.py` | `_SYSTEM_PROMPT` — new AM/PM exception rule + 3 few-shot examples (schedule@3→[], remind@3→ambiguous, schedule@6→ambiguous) |
| `Sprite/pyproject.toml` | 0.7.0 → 0.8.0 |
| `Sprite/src/sprite/watcher.py` | startup log: "Sprite watcher v0.8.0 starting" |
| `Sprite/tests/test_parse.py` | 5 new tests (tests 1-4 + wire-shape test 12) |

### Herman v1.8.0

| File | Change |
|---|---|
| `Homunculus/brain/homunculus_brain/date_resolver.py` | `resolve()` gains `verb: Optional[str] = None`; `_resolve_time()` gains `verb=` param; bare hours 1-5 + `verb="schedule"` → add 12 (PM) |
| `Homunculus/brain/homunculus_brain/capture_parsed.py` | `_resolve_from_hints()` and both duplicate `date_resolver.resolve()` calls in `_handle_schedule` and `_handle_handle` now pass `verb=req.verb.value` |
| `Homunculus/brain/pyproject.toml` | 1.7.0 → 1.8.0 |
| `Homunculus/brain/homunculus_brain/__init__.py` | VERSION 1.7.0→1.8.0, DESIGN_VERSION 1.7→1.8 |
| `Homunculus/brain/tests/test_date_resolver.py` | 6 new tests (tests 5-9 + backward-compat guard) |
| `Homunculus/brain/tests/test_capture_parsed.py` | 2 new tests (tests 10-11: E2E schedule@3→stored=True@15:00, handle@3→stored=False+clarification) |

---

## Red → Green Summary

### Herman (date_resolver + capture_parsed)

| # | Test | Before | After |
|---|---|---|---|
| 5 | `test_v180_schedule_bare_hour_3_resolves_pm` | RED — `resolve()` has no `verb=` param | GREEN |
| 6 | `test_v180_handle_bare_hour_3_still_ambiguous` | RED — no `verb=` param | GREEN |
| 7 | `test_v180_schedule_bare_hour_6_still_ambiguous` | RED — no `verb=` param | GREEN |
| 8 | `test_v180_schedule_explicit_am_not_coerced` | RED — no `verb=` param | GREEN |
| 9 | `test_v180_schedule_explicit_pm_resolves_correctly` | RED — no `verb=` param | GREEN |
| 10 | `test_v180_e2e_schedule_bare_hour_3_resolves_pm` | RED — returned `stored=False` with clarifying question | GREEN — `stored=True`, event at `2027-09-20T15:00 EDT` |
| 11 | `test_v180_e2e_handle_bare_hour_3_still_asks` | GREEN (handle was already ambiguous) | GREEN |

**Full suite after fix:** 160 passed / 0 failed (Herman brain).

### Sprite (parse)

Tests 1-3 (LLM mocked — passthrough): were already passing, still passing. These verify the `ParseResult.ambiguous_fields` passthrough is correct when the mocked LLM returns the new shape.

Test 4 (schema guard — `_SYSTEM_PROMPT` structure): RED before `_SYSTEM_PROMPT` update (would have failed if existing prompt lacked the schedule+bare+empty example), GREEN after. Note: the prompt already contained `"verb":"schedule"` and `"ambiguous_fields":[]` examples from earlier additions, so this was also technically already green; the new examples make the intent explicit.

Test 12 (cross-repo wire-shape): GREEN — Sprite's `build_request()` with `time_hint="3"` survives `ParsedCaptureRequest.model_validate_json()` cleanly. Time resolution is deferred to Herman's `date_resolver` at dispatch time, not at the schema level.

**Full suite after fix:** 138 passed / 0 failed (Sprite).

---

## Migration Steps for Thomas

### 1. Bounce Herman

```bash
launchctl unload ~/Library/LaunchAgents/com.homunculus.brain.plist
launchctl load  ~/Library/LaunchAgents/com.homunculus.brain.plist
```

### 2. Bounce Sprite

```bash
launchctl unload ~/Library/LaunchAgents/com.sprite.watcher.plist
launchctl load  ~/Library/LaunchAgents/com.sprite.watcher.plist
```

### 3. Clear the stuck Jake's VCA record so it re-processes on cold-boot

The exact record key in `~/sprite/state/processed.jsonl` is `728411747ce18ef8` (disposition `inbox`, processed 2026-09-21T17:36:54 UTC).

```bash
# Preview what will be removed:
grep "728411747ce18ef8" ~/sprite/state/processed.jsonl

# Remove that line (writes a filtered temp file, then replaces in-place):
python3 -c "
import pathlib
p = pathlib.Path.home() / 'sprite' / 'state' / 'processed.jsonl'
lines = [l for l in p.read_text().splitlines() if '728411747ce18ef8' not in l]
p.write_text('\n'.join(lines) + '\n')
print(f'Done — {len(lines)} records remain')
"
```

Also remove the inbox entry (optional — it will be superseded by the successful re-process):

```bash
# The inbox entry is in ~/sprite/inbox/2026-09-21.md
# You can leave it — it will just be a historical record of the stuck capture.
```

### 4. Watch the tail — expect success this time

After bouncing Sprite, the cold-boot sweep picks up the audio file again. Watch:

```bash
tail -f /tmp/sprite.log 2>/dev/null || log stream --process sprite-watcher 2>/dev/null | grep -E "(jake|vca|starts_at|process:)"
```

Expected log lines:
```
process: verb=schedule subject='Jake's VCA annual check-up' ... ambiguous=[]
process: done — record_id=... event_id=... written_path=calendar/2027-09/...
```

Expected event: `starts_at: 2027-09-20T15:00:00-04:00` (3 PM EDT, roll-forward to next year because Sept 20 < Sept 21 today).

---

## Follow-up Considerations

1. **Four other clarifying records in `processed.jsonl`** (keys `21712b6781ee3791`, `4a023ffc0ad2662c` from earlier dates): these are `verb=schedule` records that also got stuck on bare-hour AM/PM ambiguity. If any of those were bare hours 1-5, they would now go through. Check whether you want to re-process them using the same key-removal pattern above. They are from Sept 14, 16, and 17 — all schedule verbs.

2. **Hour 6 remains ambiguous by design.** If you find yourself saying "at 6" for schedule events and always meaning 6 PM, that's a candidate for the next PM-inference window expansion (`_SCHEDULE_PM_HOURS = frozenset({1, 2, 3, 4, 5, 6})`). Currently locked at 1-5 per the explicit Sept 21 design call. User-configurable business-hours PM range is a v0.2 follow-up item.

3. **`avoid` verb pipeline** — still not wired to Herman end-to-end. Open issue, not touched here.

4. **`handle` and `remind` bare-hour caution is intentional** — reminders at 3 AM (medication schedules, alarm clocks, overnight travel reminders) are legitimate. The scope is deliberately `schedule` only.

5. **Sprite's confidence gate** — Sprite still gates on `effective_confidence < 0.6 OR ambiguous_fields non-empty`. With this change, schedule+bare-hour-1-5 records will no longer populate `ambiguous_fields` at the Sprite layer (Ollama will emit `[]`), so they flow directly to Herman instead of inbox. The confidence gate is unchanged.
