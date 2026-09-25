# o'clock AM/PM Qualifier Fix

<!-- v Sprite 0.12.0 | Herman 2.3.0 -->
**Sprite v0.12.0 · Herman v2.3.0** — 2026-09-25

---

## Live Incident

> *"You put the barrier up in the car at 9 o'clock a.m. today."*
> — whisper, 2026-09-25 07:49, confidence 0.887

Ollama parsed: `verb=handle, subject='put the barrier up in the car', ambiguous=[]`

Herman returned: `stored=False, clarifying_question="Did you mean AM or PM?", ambiguous=['time']`

The memo unambiguously said "a.m." Herman should have accepted it and created the reminder at 09:00.

---

## Root Cause Analysis

Two independent bugs, both required to reproduce the incident:

### Cause 1 — Sprite: LLM dropped the AM/PM qualifier (primary)

The LLM extracted the time as `time_hint="9 o'clock"` — verbatim digit + o'clock but without "a.m.". The AM/PM qualifier that followed ("a.m. today") was dropped.

Herman's resolver received bare `"9 o'clock"` for `verb=handle`. The resolver could not parse "o'clock" and flagged time as ambiguous, correctly asking "AM or PM?" — but the transcript had already provided the answer.

### Cause 2 — Herman: `_TIME_REGEX` can't parse "o'clock" forms (secondary)

Even if Sprite had preserved the qualifier (`"9 o'clock a.m."`), Herman's `_TIME_REGEX` would have failed to match because the word "o'clock" sits between the digit and the AM/PM group, which the regex expects to be immediately adjacent:

```
^\s* (\d{1,2}) (?:[:.](\d{2}))? \s* (am|pm|a\.m\.|p\.m\.)? \s*$
```

`"9 o'clock a.m."` does not match this pattern. Resolution: `could not parse time` → ambiguous → clarifying question.

### Why both matter

If only Cause 1 is fixed: Sprite sends `"9 o'clock a.m."` and Herman still can't parse it.
If only Cause 2 is fixed: Herman can parse `"9 o'clock a.m."` but Sprite sends `"9 o'clock"` (dropped qualifier) → bare 9 → ambiguous.

Both must be fixed. Belt-and-suspenders.

---

## Fixes

### Sprite v0.12.0 — post-LLM AM/PM injection + prompt reinforcement

**File:** `Sprite/src/sprite/parse.py`

**Code override** (post-LLM, same discipline as v0.8.1 bare-1-5 schedule override):

After the LLM returns, scan the original transcript for an AM/PM qualifier using a regex that handles all whisper transcription variants:

```python
_AMPM_IN_TEXT_RE = re.compile(
    r"(?:(?<=\d)|(?<=\s)|(?<=^))"
    r"(a\.m\.|p\.m\.|a\s+m(?=\s|$)|p\s+m(?=\s|$)|am(?=\s|$|\.|,)|pm(?=\s|$|\.|,))",
    re.IGNORECASE,
)
```

Recognized forms: `"a.m."`, `"p.m."`, `"A.M."`, `"AM"`, `"am"`, `"9am"` (no space), `"a m"` (no periods, whisper drops them sometimes).

If the transcript contains a qualifier AND `time_hint` does not already contain one → append the verbatim qualifier from the transcript to `time_hint`.

**Prompt reinforcement:** Added two new few-shot examples to `_SYSTEM_PROMPT`:
- `"9 o'clock a.m."` → `time_hint="9 o'clock a.m."` (keep verbatim, don't strip)
- `"3 o'clock p.m."` → `time_hint="3 o'clock p.m."`

### Herman v2.3.0 — normalize "o'clock" in date_resolver

**File:** `Homunculus/brain/homunculus_brain/date_resolver.py`

Before running `_TIME_REGEX`, strip the word "o'clock" (and variants: `oclock`, `o clock`, all case-insensitive) from `time_hint`:

```python
_OCLOCK_RE = re.compile(r"\bo'?clock\b", re.IGNORECASE)

def _resolve_time(...):
    if time_hint:
        time_hint = _OCLOCK_RE.sub("", time_hint).strip()
    ...
```

Result:
- `"9 o'clock a.m."` → `"9 a.m."` → resolves to 09:00, unambiguous
- `"3 o'clock p.m."` → `"3 p.m."` → resolves to 15:00, unambiguous
- `"9 o'clock"` → `"9"` → still ambiguous (bare hour, no qualifier — correct)

The strip is safe: "o'clock" carries no time information beyond marking a digit as an hour value.

---

## Red → Green Table

| # | Test | File | Before | After |
|---|------|------|--------|-------|
| 1 | `test_v0120_live_regression_oclock_am_transcript_qualifier_injected` | Sprite/tests/test_parse.py | RED | GREEN |
| 2 | `test_v0120_llm_already_has_qualifier_not_doubled` | Sprite/tests/test_parse.py | GREEN (already) | GREEN |
| 3 | `test_v0120_no_ampm_in_transcript_no_injection` | Sprite/tests/test_parse.py | GREEN (already) | GREEN |
| 4a | `test_v0120_various_ampm_formats_recognized[call at 9 AM today-am]` | Sprite/tests/test_parse.py | RED | GREEN |
| 4b | `test_v0120_various_ampm_formats_recognized[call at 9am today-am]` | Sprite/tests/test_parse.py | RED | GREEN |
| 4c | `test_v0120_various_ampm_formats_recognized[call at 9 A.M. today-a.m.]` | Sprite/tests/test_parse.py | RED | GREEN |
| 4d | `test_v0120_various_ampm_formats_recognized[call at 9 a m today-a m]` | Sprite/tests/test_parse.py | GREEN (already) | GREEN |
| 5 | `test_v0120_pm_variant_injected` | Sprite/tests/test_parse.py | RED | GREEN |
| 6 | `test_v0120_system_prompt_has_oclock_am_example` | Sprite/tests/test_parse.py | RED | GREEN |
| 7 | `test_v230_oclock_am_resolves_09_00` | brain/tests/test_date_resolver.py | RED | GREEN |
| 8 | `test_v230_oclock_no_punct_resolves_09_00` | brain/tests/test_date_resolver.py | RED | GREEN |
| 9 | `test_v230_oclock_pm_resolves_15_00` | brain/tests/test_date_resolver.py | RED | GREEN |
| 10 | `test_v230_oclock_no_ampm_still_ambiguous` | brain/tests/test_date_resolver.py | GREEN (already) | GREEN |
| R1 | `test_v230_regression_plain_9am_still_works` | brain/tests/test_date_resolver.py | GREEN | GREEN |
| R2 | `test_v230_regression_bare_9_still_ambiguous` | brain/tests/test_date_resolver.py | GREEN | GREEN |
| R3 | `test_v230_regression_17_35_unambiguous` | brain/tests/test_date_resolver.py | GREEN | GREEN |
| 12 | `test_v230_e2e_oclock_am_stores_at_0900` | brain/tests/test_capture_parsed.py | RED | GREEN |
| 13 | `test_v230_e2e_oclock_no_qualifier_still_asks` | brain/tests/test_capture_parsed.py | GREEN (already) | GREEN |

**Total new tests added:** 9 Sprite + 9 Herman = 18

**Prior suite counts:**
- Sprite: 184 → 193 (all pass)
- Herman (target files): 82 → 91 (all pass)
- Herman (full suite): 3 pre-existing failures in `test_timers_routes.py` unchanged

---

## Migration Steps for Thomas

1. **Bounce Sprite:**
   ```
   launchctl unload ~/Library/LaunchAgents/com.sprite.watcher.plist
   launchctl load  ~/Library/LaunchAgents/com.sprite.watcher.plist
   ```

2. **Bounce Herman:**
   ```
   launchctl unload ~/Library/LaunchAgents/com.homunculus.brain.plist
   launchctl load  ~/Library/LaunchAgents/com.homunculus.brain.plist
   ```

3. **Clear the stuck memo from Sprite's processed log** so it gets re-processed:
   ```bash
   # Remove the line with audio hash 55cdbe8de3b115cbbc64fa747a354da8
   # from ~/sprite/state/processed.jsonl
   grep -v '55cdbe8de3b115cbbc64fa747a354da8' ~/sprite/state/processed.jsonl \
     > ~/sprite/state/processed.jsonl.tmp \
     && mv ~/sprite/state/processed.jsonl.tmp ~/sprite/state/processed.jsonl
   ```
   On cold-boot restart, Sprite will re-process the file. Herman v2.3.0 will accept it and create the barrier reminder at 09:00 today.

4. **Verify Herman is v2.3.0:**
   ```
   curl http://localhost:8765/health
   ```
   Should show `"version": "2.3.0"` in the response.

---

## Follow-up Question

**Does the same "qualifier survival" logic apply to other time qualifiers beyond "o'clock"?**

The current fix is specifically about "o'clock" as the obstruction word. Two other cases are worth checking:

- **"at 9 sharp"** — "sharp" carries no AM/PM info, so "9 sharp a.m." → strip "sharp" → "9 a.m." would work. But does whisper transcribe this? Probably rare in Thomas's utterances.
- **"at 9 in the morning"** — "in the morning" IS an AM/PM indicator (but a whole phrase, not a single token). The Sprite injection regex won't match "in the morning". Herman's resolver also won't handle it. This would need a separate fix if it comes up in practice.

Recommended: leave both for v2.4 unless a live incident surfaces them. The "o'clock" form is the confirmed real-world case.
