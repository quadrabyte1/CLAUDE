# Sprite v0.8.1 — Code-Enforce Bare 1-5 PM Rule

**v0.8.1** · Rune · 2026-09-21

---

## Root Cause

The 7B model ignored the v0.8.0 prompt's exception clause ("schedule verb + bare 1-5 → do NOT flag time_hint ambiguous") and returned `ambiguous_fields=['time_hint']` anyway. Prompting a multi-condition rule into a small model is unreliable — this is my own persona rule #1, which I violated by shipping v0.8.0 as a prompt-only fix. I apologize for the shortcut. It cost you a round trip and an inbox'd memo that should have gone straight to the calendar.

The exact log line from the live incident:

```
confidence 0.844 < 0.6 or ambiguous=['time_hint'] → inbox
```

The model obeyed the schema shape (valid JSON) but not the content rule (clear the flag). GBNF guarantees structural validity, not semantic correctness. Code has authority; the prompt is advisory.

---

## Fix

**`Sprite/src/sprite/parse.py`** — post-LLM merge step (same location as the existing preprocessor-criticality override):

```python
# Post-LLM time_hint override: for verb=schedule + bare hours 1-5
# (digits "1"–"5" or words "one"–"five", no AM/PM marker, no colon),
# strip "time_hint" from ambiguous_fields regardless of what the LLM said.
_BARE_1_5 = frozenset({"1","2","3","4","5","one","two","three","four","five"})
if (
    verb == "schedule"
    and time_hint_stripped in _BARE_1_5
    and ":" not in time_hint_stripped
):
    ambiguous_fields = [f for f in ambiguous_fields if f != "time_hint"]
```

The v0.8.0 prompt teaching stays intact — it's still useful for making the LLM produce cleaner output on the happy path. But it is no longer load-bearing for correctness.

Herman's `date_resolver.py` v1.8.0 already applies `verb="schedule" + bare 1-5 → PM` inference and builds its own fresh `ambiguous` list from resolution outcomes. It cannot be tainted by caller-side state. No Herman code change needed.

---

## Red → Green Table

| # | Test | Before fix | After fix |
|---|------|-----------|-----------|
| 1 | `test_v081_live_incident_schedule_bare_3_llm_returns_ambiguous_post_strips` | FAIL | PASS |
| 2a | `test_v081_schedule_all_bare_1_5_llm_ambiguous_stripped[1]` | FAIL | PASS |
| 2b | `test_v081_schedule_all_bare_1_5_llm_ambiguous_stripped[2]` | FAIL | PASS |
| 2c | `test_v081_schedule_all_bare_1_5_llm_ambiguous_stripped[3]` | FAIL | PASS |
| 2d | `test_v081_schedule_all_bare_1_5_llm_ambiguous_stripped[4]` | FAIL | PASS |
| 2e | `test_v081_schedule_all_bare_1_5_llm_ambiguous_stripped[5]` | FAIL | PASS |
| 2f | `test_v081_schedule_all_bare_1_5_llm_ambiguous_stripped[one]` | FAIL | PASS |
| 2g | `test_v081_schedule_all_bare_1_5_llm_ambiguous_stripped[two]` | FAIL | PASS |
| 2h | `test_v081_schedule_all_bare_1_5_llm_ambiguous_stripped[three]` | FAIL | PASS |
| 2i | `test_v081_schedule_all_bare_1_5_llm_ambiguous_stripped[four]` | FAIL | PASS |
| 2j | `test_v081_schedule_all_bare_1_5_llm_ambiguous_stripped[five]` | FAIL | PASS |
| 3 | `test_v081_remind_bare_3_llm_ambiguous_not_stripped` (scope) | PASS | PASS |
| 4 | `test_v081_handle_bare_3_llm_ambiguous_not_stripped` (scope) | PASS | PASS |
| 5 | `test_v081_schedule_bare_6_llm_ambiguous_not_stripped` (hour-6) | PASS | PASS |
| 6 | `test_v081_schedule_explicit_pm_llm_sends_clean_no_change` (explicit AM/PM) | PASS | PASS |
| 7 | `test_v081_schedule_colon_time_ambiguous_not_stripped` (colon/minutes) | PASS | PASS |
| 8 | `test_v081_schedule_strips_only_time_hint_preserves_others` (only time_hint stripped) | FAIL | PASS |
| Herman | `test_v180_defensive_resolve_output_not_tainted_by_legacy_ambiguous` (new) | PASS | PASS |

**Sprite full suite:** 155 passed (was 138 before v0.8.1 tests added)  
**Herman date_resolver suite:** 40 passed (was 39 before defensive test added)

---

## Migration — Bounce and Reprocess

1. **Bounce Sprite:**
   ```bash
   launchctl unload ~/Library/LaunchAgents/com.sprite.watcher.plist
   launchctl load  ~/Library/LaunchAgents/com.sprite.watcher.plist
   ```
   Watch for `Sprite watcher v0.8.1 starting` in the log.

2. **Clear the stuck Jake's VCA record** from `~/sprite/state/processed.jsonl`:  
   Find the line with `disposition=inbox` and today's date (2026-09-21) that matches the Jake's VCA audio filename, and remove that single line. Example (substitute your actual filename):
   ```bash
   grep -n "jakes" ~/sprite/state/processed.jsonl   # find the line number
   # Remove that line in your editor, or:
   # sed -i '' '<line_number>d' ~/sprite/state/processed.jsonl
   ```
   If uncertain, filter for `"disposition":"inbox"` lines from today and remove the one matching the VCA audio path.

3. **Watch the tail:** the cold-boot sweep will pick the file up on next start.  
   Expect:
   ```
   process: verb=schedule subject='Jake's VCA annual check-up' conf=0.844 ... ambiguous=[]
   ```
   Herman v1.8 will receive `time_hint="3"` with `ambiguous_fields=[]`, resolve to `2027-09-20T15:00:00-04:00`, and write the event to `calendar/2027-09/2027-09-20-jakes-vca-*.md`.

---

## Files Changed

- `Sprite/src/sprite/parse.py` — post-LLM override block (lines after criticality merge)
- `Sprite/tests/test_parse.py` — v0.8.1 TDD block (17 new tests)
- `Sprite/pyproject.toml` — version 0.8.0 → 0.8.1
- `Sprite/src/sprite/watcher.py` — startup log string v0.8.0 → v0.8.1
- `Homunculus/brain/tests/test_date_resolver.py` — 1 new defensive contract test
