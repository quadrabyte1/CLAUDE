# v2.5.0 — AM/PM Disambiguation

**v2.5.0** · Rune · 2026-09-29

---

## Precedence Stack

Six levels, highest wins:

| # | Signal | What fires it | Example |
|---|--------|---------------|---------|
| 1 | **Explicit AM/PM in time_hint** | User says "3 PM" or "9am" | `time_hint="3pm"` → 15:00, no question |
| 2 | **Signal C — natural qualifier phrase** | "in the morning", "tonight", "this afternoon" | "Meeting at 9 in the morning" → 9 AM |
| 3 | **Signal A — meal / profession / activity** | "breakfast", "plumber", "gym" | "Dinner at 7" → 7 PM |
| 4 | **v0.8.1 schedule + bare hour 1–5** | verb=schedule, hour in {1,2,3,4,5}, no minutes | "Schedule at 3" → 3 PM |
| 5 | **Signal B — speaker-time roll-forward** | Bare whole-hour, no other signal fired | "At 3" at 10 AM → 3 PM today |
| 6 | **Clarifying question** | No signal resolved it (bare hour:minute, no context, no `now`) | "5:35" → ask AM/PM |

After v2.5.0, **level 6 is reached only for bare hour:minute cases** (e.g. "5:35" with no qualifier). Bare whole-hour cases always resolve via Signal B because the normal capture path always supplies `now`.

---

## Signal A — Context Keyword Vocabulary

Data structure: three Python dicts/sets in `date_resolver.py`. Add one line to expand any category.

### Meals → meridiem

| Keyword | Meridiem | Notes |
|---------|----------|-------|
| `breakfast` | AM | window 5–11 AM |
| `brunch` | PM | leans late morning / early afternoon |
| `lunch` | PM | noon default |
| `dinner` | PM | window 5–9 PM |
| `supper` | PM | alias for dinner |
| `snack` | PM | afternoon default |

### Morning activity keywords → AM

`wake`, `wakeup`, `wake-up`, `exercise`, `gym`, `workout`, `run`, `jog`, `yoga`, `swim`

### Evening activity keywords → PM

`bedtime`, `sleep`, `wind down`, `winddown`, `wind-down`, `bed`

### Profession / appointment keywords → PM (business hours)

`plumber`, `electrician`, `doctor`, `dentist`, `mechanic`, `contractor`, `inspector`, `appointment`, `therapist`, `lawyer`, `attorney`, `accountant`, `vet`, `veterinarian`, `chiropractor`, `optometrist`, `pediatrician`, `dermatologist`, `physical therapy`, `physical therapist`

**To add a new keyword:** one line in the appropriate set/dict in `date_resolver.py`. Example:
```python
# In _PROFESSION_KEYWORDS:
"dermatologist",   # <- already there
"orthodontist",    # <- add here, done
```

---

## Signal B — Roll-Forward Algorithm

```
Given bare hour H and now:
  buffer = 15 min  (avoid "right now" confusion)
  cutoff = now + buffer
  candidates = [
    (today,     H am),
    (today,     H pm),
    (tomorrow,  H am),
    (tomorrow,  H pm),
    (day-after, H am),
    (day-after, H pm),
  ]
  filter:  candidate >= cutoff
           AND NOT in sleep window (hours 0–5)
           UNLESS late-night (now.hour >= 22)
  pick:    min(remaining candidates)
```

### Sleep Window Decision

Sleep window = hours 0 through 5 AM inclusive. This is skipped to avoid suggesting "3 AM tomorrow" when the user says "at 3" at 5 PM — that would be weird. The sleep-skip is lifted at 22:00+ (late night) because `"at 3"` from 11 PM is plausibly a morning alarm or medication.

### Day-Hint Interaction

- **No day_hint**: roll-forward scans today/tomorrow/day-after freely. `"at 3"` from 5 PM → 3 PM tomorrow.
- **day_hint given**: anchor is midnight of the resolved date (for future dates) or `now` (same-day). Result is constrained to that date. Sleep-window skip selects AM vs PM: `"Friday at 3"` → Friday 3 PM (3 AM skipped).

### Documented Choices

| Scenario | Decision | Rationale |
|----------|----------|-----------|
| Current time 5 PM, "at 3" | 3 PM tomorrow (skip sleep) | 3 AM at 5 PM is unusual; sleep window covers 0–5 AM |
| Current time 11 PM, "at 3" | 3 AM tomorrow (late-night, no sleep skip) | 11 PM is close to midnight; 3 AM alarm/medication is reasonable |
| Current time 8 AM, "at 6" | 6 PM today | 6 AM has passed; next future 6 = 6 PM today |
| Current time 10 AM, "at 3" | 3 PM today | 3 AM passed; 3 PM still in future |
| "Friday at 3" | Friday 3 PM | Specific date given; sleep skip applied on that date |

---

## Signal C — Natural Qualifier Vocabulary

Regex patterns (ordered most-specific first, applied to full `context_text`):

| Pattern | Meridiem |
|---------|----------|
| `tomorrow morning` | AM |
| `tomorrow afternoon` | PM |
| `tomorrow evening` | PM |
| `tomorrow night` | PM |
| `this morning` | AM |
| `this afternoon` | PM |
| `this evening` | PM |
| `this night` | PM |
| `late morning` | AM |
| `early afternoon` | PM |
| `late evening` | PM |
| `in the morning` | AM |
| `in the afternoon` | PM |
| `in the evening` | PM |
| `at night` | PM |
| `tonight` | PM |

All patterns are case-insensitive. Signal C fires before Signal A, so `"dinner at 7 in the morning"` → 7 AM (qualifier overrides meal word).

**To add a new qualifier phrase:** one tuple in `_QUALIFIER_PATTERNS` in `date_resolver.py`:
```python
(re.compile(r"\bearly\s+morning\b", re.IGNORECASE), "am"),  # -> add here
```

---

## Signal A + C — Interaction / Precedence Tests

| Utterance | Signal fired | Result |
|-----------|-------------|--------|
| "Schedule dinner at 7" | A (dinner→PM) | 7 PM |
| "Meeting at 9 in the morning" | C (in the morning→AM) | 9 AM |
| "Wake up call at 6" | A (wake→AM) | 6 AM |
| "Bedtime meds at 9" | A (bedtime→PM) | 9 PM |
| "Plumber at 3" | A (plumber→PM) | 3 PM |
| "Dinner at 7 in the morning" | C wins over A | 7 AM (C precedes A) |
| "Meeting at 3 PM in the morning" | explicit PM wins over C | 3 PM (level 1 beats all) |
| "Breakfast at 8 PM" | explicit PM wins over A | 8 PM (level 1 beats all) |
| "Schedule at 3" (no context) | v0.8.1 (schedule+1-5) | 3 PM |
| "Handle at 3" at 10 AM | B (roll-forward) | 3 PM today |
| "At 6" at 10 AM | B (roll-forward) | 6 PM today |
| "At 3" at 5 PM | B (sleep skip) | 3 PM tomorrow |

---

## Red → Green Table

All 52 new tests started RED, all pass GREEN after implementation. 9 previously-passing tests were updated (their old assertions described the pre-v2.5.0 "ask" behavior; the new assertions document the resolved behavior). All 557 tests green.

| Test group | Count | Status |
|------------|-------|--------|
| Signal A — Meals | 4 | RED → GREEN |
| Signal A — Professions | 4 | RED → GREEN |
| Signal A — Personal activity | 4 | RED → GREEN |
| Signal A — Neutral fallthrough | 2 | RED → GREEN |
| Signal B — Roll-forward | 6 | RED → GREEN |
| Signal C — Qualifiers | 13 | RED → GREEN |
| Precedence integration | 8 | RED → GREEN |
| Regression preservation | 11 | RED → GREEN |
| Thomas's test-drive scenarios | 3 | RED → GREEN |
| **v1.2.2 / v1.8.0 / v2.3.0 superseded** | **9 updated** | now describe v2.5.0 behavior |
| Existing suite (untouched) | 312 | stayed GREEN |
| Sprite suite (untouched) | 193 | stayed GREEN |
| **Total** | **557** | **all GREEN** |

---

## How to Expand Later

All three signal vocabularies are designed for 1-line additions:

**New meal:**
```python
# In _MEAL_MERIDIEM dict:
"brunch":    "pm",   # already there
"high tea":  "pm",   # <- add here
```

**New profession:**
```python
# In _PROFESSION_KEYWORDS frozenset:
"orthodontist",     # <- add here
"physical therapist",  # already there
```

**New morning activity:**
```python
# In _MORNING_ACTIVITY_KEYWORDS frozenset:
"pilates",   # <- add here
```

**New qualifier phrase:**
```python
# In _QUALIFIER_PATTERNS list (order matters — more specific first):
(re.compile(r"\bearly\s+morning\b", re.IGNORECASE), "am"),  # <- add here
```

All expansions take effect without any other code changes. The test in `test_ampm_disambiguation_v250.py` covers the precedence contract; adding a new keyword doesn't require a new test (the keyword dictionary is data, not logic).

---

## Expected Impact on Thomas's Clarifying Rate

Before v2.5.0: >50% of time-bearing captures triggered "Did you mean AM or PM?". The main failure patterns:

1. **Bare hours 6–12 with verb=schedule** — the v0.8.1 rule only covered 1–5. "Schedule at 9" always asked.
2. **All bare hours with verb=handle/remind** — no inference existed for these verbs.
3. **Meal/activity context ignored** — "dinner at 7" asked even though dinner is obviously PM.

After v2.5.0, the only remaining cases that ask:
- Bare hour:minute (e.g. "5:35") — still asks because the user was specific enough to include minutes; AM/PM is cheap to ask in that context.
- The `now` reference is missing — cannot happen in the normal capture path.

**Estimated post-v2.5.0 clarifying rate: <5%** of time-bearing captures.

---

## Thomas's Test Drive

Say these out loud to Sprite; expect no clarifying question:

- **"Schedule dinner at 7"** → 7 PM tonight (or tomorrow if after 7 PM now). Signal A fires (dinner → PM).
- **"Meeting at 3"** during afternoon → 3 PM tomorrow (roll-forward skips sleep window). Signal B fires.
- **"At 3"** with no verb, mid-morning (e.g. 10 AM) → 3 PM today. Signal B fires (next future 3 from 10 AM).
- **"Wake up call at 6"** → 6 AM tomorrow (if said after 6 AM). Signal A fires (wake → AM).
- **"Plumber at 2"** → 2 PM. Signal A fires (plumber → PM business hours).

---

## Code Changes

- `/Volumes/GIT/CLAUDE/SHARED_WORK_FOLDER/Homunculus/brain/homunculus_brain/date_resolver.py` — Signal A/B/C implementation; `resolve()` gains optional `context_text` param; `_resolve_time()` updated; `_signal_a_meridiem()`, `_signal_b_rollforward()`, `_signal_c_meridiem()` added.
- `/Volumes/GIT/CLAUDE/SHARED_WORK_FOLDER/Homunculus/brain/homunculus_brain/__init__.py` — VERSION `2.4.2` → `2.5.0`, DESIGN_VERSION `2.4` → `2.5`.
- `/Volumes/GIT/CLAUDE/SHARED_WORK_FOLDER/Homunculus/brain/tests/test_ampm_disambiguation_v250.py` — 52 new TDD tests.
- `/Volumes/GIT/CLAUDE/SHARED_WORK_FOLDER/Homunculus/brain/tests/test_date_resolver.py` — 7 tests updated to reflect v2.5.0 behavior.
- `/Volumes/GIT/CLAUDE/SHARED_WORK_FOLDER/Homunculus/brain/tests/test_capture_parsed.py` — 2 tests updated to reflect v2.5.0 behavior.

---

## Daemon Restart

Herman is supervised by launchd. After deploying these changes, reload the daemon:

```bash
launchctl kickstart -k gui/$(id -u)/com.homunculus.brain
```

Verify it came up cleanly:
```bash
curl -s http://localhost:8765/health
```

No Sprite changes required (the `context_text` parameter threads through to Herman's `resolve()` call via `capture_parsed.py`; Sprite sends the raw transcript as `raw_transcript` which Herman already passes through).
