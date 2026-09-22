# v1.9.0 — Untimed handle/remind resolves to default hour on specified day

**Version: v1.9.0** | 2026-09-22 | Rune

---

## Root Cause

`_resolve_from_hints()` in `capture_parsed.py` called `date_resolver.resolve()` unconditionally for any request that had `day_hint` or `time_hint` set. When `time_hint` was `None`, `_resolve_time()` returned `(None, True, "no time given")` — the `True` flag meaning "ambiguous." That propagated up as `ambiguous=["time"]` which triggered the clarifying question "Did you mean AM or PM?"

The two cases were conflated:

| Situation | Correct behavior | What happened |
|---|---|---|
| `time_hint=None` (user said "on Friday") | Apply default hour, no question | Asked "AM or PM?" — nonsense |
| `time_hint="3"` (bare hour, no AM/PM) | Ask "AM or PM?" | Correctly asked (unchanged) |

The fix is scoped to `verb in (handle, remind)` only. Schedule with no time is still genuinely ambiguous (all-day? 9 AM? TBD?) and continues to ask.

---

## Design Rule (locked as of v1.9.0)

When `verb in ("handle", "remind")` AND `time_hint is None or empty`:

1. Validate that `day_hint` resolves cleanly (if not, ask about the day).
2. Apply **default handle-hour = `morning_anchor_hour - 1`** (with `morning_anchor_hour=9` this is **8 AM local**) on the user-specified day.
3. Do NOT add `time` to `ambiguous_fields`. The user meant "sometime that day."
4. Full strike chain hangs off the 8 AM anchor: T-30 at 7:30, T-5 at 7:55, strikes at 8:00 / 8:05 / 8:10 / 8:15.

This matches the existing `_handle_handle` "no when at all" fallback (`_next_business_morning(captured_at) - 1h`) except here the day comes from the user's utterance, not from next-business-day logic.

---

## Red → Green Table

| # | Test | Before fix | After fix |
|---|---|---|---|
| 1 | `test_v190_handle_day_hint_null_time_stores_at_8am` | FAIL — stored=False, "Did you mean AM or PM?" | PASS — stored=True, strike_0 at 2026-09-25 08:00 |
| 2 | `test_v190_remind_day_hint_null_time_stores_at_8am` | FAIL — stored=False, "Did you mean AM or PM?" | PASS — stored=True, strike_0 at 2026-09-25 08:00 |
| 3 | `test_v190_schedule_day_hint_null_time_still_asks` | PASS (schedule behavior unchanged) | PASS |
| 4 | `test_v190_strike_chain_complete_for_null_time_handle` | FAIL — stored=False | PASS — all 6 kinds present, anchored correctly |
| 5 | `test_v190_configurable_morning_anchor_shifts_default_hour` | FAIL — stored=False | PASS — anchor=10 → hour=9 |
| 6 | `test_v190_handle_with_explicit_time_hint_uses_that_time` | PASS (explicit time unchanged) | PASS |
| 7 | `test_v190_handle_bare_hour_time_hint_still_asks` | PASS (bare-hour ambiguity unchanged) | PASS |
| 8 | `test_v190_regression_null_time_handle_writes_reminder_markdown` | FAIL — stored=False | PASS — vault/reminders/<id>.md has starts_at on Friday 08:00 |

**Prior suite:** 161 tests all passed before; 169 tests all pass after (161 + 8 new).

---

## Files Changed

- `Homunculus/brain/homunculus_brain/capture_parsed.py` — `_resolve_from_hints()` and `_handle_handle()` (v1.9.0 null-time path)
- `Homunculus/brain/homunculus_brain/__init__.py` — VERSION = "1.9.0", DESIGN_VERSION = "1.9"
- `Homunculus/brain/pyproject.toml` — version = "1.9.0"
- `Homunculus/brain/tests/test_capture_parsed.py` — 8 new tests

---

## Migration for Thomas

**1. Bounce Herman:**

```
launchctl unload ~/Library/LaunchAgents/com.homunculus.brain.plist
launchctl load  ~/Library/LaunchAgents/com.homunculus.brain.plist
```

**2. Clear the stuck dry-cleaning inbox entry:**

The original Sprite capture has `record_id=722f5593b5363ce41a35b97dc11f87bf`. Because Herman rejected it (stored=False), it was never written to the idempotency log — so Sprite's client-side inbox still holds it. Find the line in:

```
~/sprite/state/processed.jsonl
```

Look for the line containing `"pick up dry cleaning"` (or `record_id=722f5593b5363ce41a35b97dc11f87bf`). Remove that line so cold-boot or the next Sprite reconciliation re-POSTs it.

**3. Watch the tail:**

```
tail -f ~/Library/Logs/homunculus-brain.log
```

Expect to see:

```
verb=handle subject='pick up dry cleaning' → event on Friday at 8 AM local
written to vault/reminders/<event_id>.md
```

And in `vault/reminders/` you should have a new `.md` file with `starts_at: 2026-09-25T08:00:00-04:00`.

---

## Follow-up Considerations

- **User-configurable default handle-hour?** Currently `morning_anchor_hour - 1` is the convention, controlled indirectly by `HOMUNCULUS_MORNING_ANCHOR`. This is tested (test 5). If Thomas ever wants "remind me at noon by default" that's a new env var (`HOMUNCULUS_HANDLE_ANCHOR`). For now `morning_anchor_hour - 1` is good.
- **All-day reminders:** Reminders.app supports all-day reminders. A future design could interpret "Friday" (no time) as all-day rather than 8 AM. Deferred — this would require iOS protocol changes and a Kit PR.
- **Same rule for `verb=avoid` and `verb=note`?** Not applicable — avoid and note have no strike chain and are not time-sensitive. They are unaffected.
