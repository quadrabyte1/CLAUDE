# v2.5.2 — Word-form time hint fix
**v2.5.2** · Rune · 2026-09-30

---

## Curl trace evidence

All four memos tested against the live daemon at `http://localhost:8765`.

| Memo | time_hint sent | Before fix | After fix | Resolved time |
|---|---|---|---|---|
| `"Dinner at 7 in the morning"` (baseline) | `"7"` (digit) | ✅ stored=true | ✅ stored=true | 07:00 AM |
| `"Meeting at 9 in the morning"` | `"nine"` (word) | ❌ clarify | ✅ stored=true | 09:00 AM |
| `"Remind me the plumber comes at three"` | `"three"` (word) | ❌ clarify | ✅ stored=true | 15:00 (3 PM) |
| `"Call mom at 8 tonight"` | `"eight"` (word) | ❌ clarify | ✅ stored=true | 20:00 (8 PM) |

Pre-fix clarifying question: `"Did you mean AM or PM? (e.g. '9 AM' or '9 PM')"` — same on all three.

---

## Root cause

Sprite's on-device LLM (Qwen2.5 7B) sometimes emits the spoken word form rather than the digit when transcribing a time — `"three"` instead of `"3"`, `"eight"` instead of `"8"`. This is verbatim copying of the transcript.

`date_resolver._resolve_time()` uses `_TIME_REGEX` (`\d{1,2}`) to parse `time_hint`. Word-form strings like `"three"` fail the regex match and fall through immediately to:

```python
return None, True, f"could not parse time '{time_hint}'"
```

This happens **before** Signals A, B, and C are checked. So even when Signal C (`"in the morning"`, `"tonight"`) or Signal A (`"plumber"` profession keyword) would have unambiguously resolved the meridiem, they never ran.

The `context_text=req.raw_transcript` fix from v2.5.1 was correct — but it was irrelevant for word-form hints because the signals were never reached.

**The v2.5.1 fix worked for digit-form hints. This fix (v2.5.2) makes it work for word-form hints too.**

---

## Files changed

| File | Change |
|---|---|
| `Homunculus/brain/homunculus_brain/__init__.py` | VERSION: `2.5.1` → `2.5.2` |
| `Homunculus/brain/homunculus_brain/date_resolver.py` | Added `_WORD_HOUR_MAP` dict + normalisation step in `_resolve_time` before `_TIME_REGEX`; updated module docstring |
| `Homunculus/brain/tests/test_wordform_time_hints.py` | New — 18 tests (3 primary failing cases, 3 digit-form regressions, 12 parametrised word-form roll-forward) |
| `Homunculus/brain/tests/test_capture_parsed.py` | Updated 1 test: `time_hint="nine"` → `time_hint="5:35"` with neutral transcript |
| `Homunculus/brain/tests/test_clarifying_pending.py` | Updated 3 tests: replaced `"call the vet at nine"` / `"doctor appointment at 3"` with neutral `"team sync"` + `"7:45"` transcripts |
| `Homunculus/brain/tests/test_dashboard.py` | Updated 1 test: same `"nine"`/`"vet"` → `"5:35"`/`"team sync"` replacement |

The pre-existing test fixtures used `time_hint="nine"` as a proxy for "ambiguous time" because word-forms previously failed. With v2.5.2 that assumption is wrong. Updated those fixtures to use `"5:35"` (bare hour:minute — Signal B skips non-zero minutes, still genuinely ambiguous) with neutral transcripts that don't trigger Signal A.

---

## Red → green table

| Test | v2.5.1 | v2.5.2 |
|---|---|---|
| `TestWordFormTimeHints::test_meeting_at_nine_in_the_morning` | ❌ FAIL | ✅ PASS |
| `TestWordFormTimeHints::test_plumber_comes_at_three` | ❌ FAIL | ✅ PASS |
| `TestWordFormTimeHints::test_call_mom_at_eight_tonight` | ❌ FAIL | ✅ PASS |
| `TestWordFormNormalization` (12 parametrised: one–twelve) | ❌ FAIL (12) | ✅ PASS (12) |
| `TestDigitFormRegression` (3) | ✅ PASS | ✅ PASS |
| Full suite (393 tests) | 389 pass / 4 fail* | ✅ 393 pass |

*The 4 pre-existing failures were the fixture tests that assumed `"nine"` was ambiguous.

---

## Vocabulary check

Signal A `_PROFESSION_KEYWORDS` confirmed present:
- `plumber` ✓ (was listed in task 656 spec)
- `doctor` ✓, `appointment` ✓
- `meeting` is NOT a profession keyword — and doesn't need to be. `"Meeting at 9 in the morning"` is resolved by Signal C (`"in the morning"`) not Signal A. Signal C fires correctly for both digit and word-form hints.
- `call` verb + `mom` object — not in Signal A. `"Call mom at 8 tonight"` is resolved by Signal C (`"tonight"`) not Signal A. Correct.

No vocabulary additions were needed. The three failing cases were all signal routing issues, not vocabulary gaps.

---

## Test drive for Thomas

Dictate these three memos — all three should confirm cleanly with no clarifying question:

1. **"Meeting at nine in the morning"** → Herman should confirm: Meeting Wednesday September 30 at 9:00 AM (or similar next-occurrence wording). No "AM or PM?" bounce.

2. **"Remind me the plumber comes at three"** → Herman should confirm: Reminder scheduled for 3:00 PM (business hours). No "AM or PM?" bounce.

3. **"Call mom at eight tonight"** → Herman should confirm: Call mom at 8:00 PM. No "AM or PM?" bounce.

Herman restarted at end of this fix session: `launchctl kickstart -k gui/$(id -u)/com.homunculus.brain`. Version confirmed: `2.5.2`.
