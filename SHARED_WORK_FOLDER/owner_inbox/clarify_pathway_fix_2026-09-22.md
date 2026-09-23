# Clarifying-Question Pathway Fix

**v Sprite 0.11.0 · v mac_notifier 0.2.0** — 2026-09-22 · Rune

---

## Apology

I owe you a straight answer on why the vet reminder disappeared silently.

When I shipped v2.2's clarifying-question surfacing, I tested Herman's side — the `stored=False + clarifying_question` response, the `_clarifying_pending.jsonl` write, the inbox entry, the notification. What I did not test was whether Sprite would even forward this class of capture to Herman. It would not. The integration gap was mine to catch and I missed it. I'm sorry. The fixes below close the hole and the tests enforce it so it can't re-open.

---

## Two Root Causes

### Root Cause 1 — Sprite pre-empted Herman for ambiguous captures

`Sprite/src/sprite/watcher.py`, line ~200 (pre-fix):

```python
is_ambiguous = (
    effective_confidence < config.min_confidence
    or bool(parse_result.ambiguous_fields)   # ← this clause was wrong
)
if is_ambiguous:
    write_to_inbox()
    return
```

`ambiguous_fields=['time_hint']` with confidence 0.850 triggered `bool(['time_hint']) = True`, routing the capture to inbox without ever calling `post_to_herman`. Herman v2.2's clarifying-question logic never ran.

The design assumption was wrong: Sprite was treating ambiguity as a signal that the capture is not ready for processing. The correct framing is the opposite. Ambiguity is exactly the class of capture that needs Herman's full context — the `date_resolver`, the v1.8 bare-hour PM inference, the v2.2 clarifying-question surfacing. Sprite's job is to be a thin pipe from voice memo → parsed structure → Herman. The confidence gate (garbled audio) is Sprite's responsibility. Everything else is Herman's.

### Root Cause 2 — mac_notifier grace window was borderline-tight

`Homunculus/mac_notifier/src/mac_notifier/config.py`:

```python
NOTIFIER_GRACE_WINDOW = 90   # ← too tight for 60s poll cycle
```

Poll interval is 60s. A notification queued at second 59 of a cycle can arrive at second 1 of the next cycle — a 118s gap between the last poll and when the row was first seen. The 90s grace was only 30s of headroom above one poll interval. The timer_stop notification fired at +99s from `fire_at`, which is 9 seconds past the 90s window. 9 seconds. The window was not wrong in direction, only in magnitude.

---

## Design Rationale

### Fix 1: Sprite v0.11.0 — gate simplified to confidence only

The Sprite gate now reads:

```python
is_low_confidence = effective_confidence < config.min_confidence
if is_low_confidence:
    write_to_inbox()
    return
# otherwise: forward to Herman regardless of ambiguous_fields
```

The v0.8.1 code override (strip `time_hint` from `ambiguous_fields` for `verb=schedule` + bare 1–5 PM hours) is preserved. It's belt-and-suspenders: if the LLM follows the prompt rule, `ambiguous_fields` is already clean before it reaches the gate. If the LLM ignores the rule, the code catches it. If both slip and `time_hint` remains in `ambiguous_fields`, we now forward to Herman anyway — Herman's `date_resolver` v1.8 applies the same rule one more time.

The whisper-confidence gate stays unchanged. Genuinely garbled audio below 0.6 is not worth Herman's time. LLM-parsed ambiguity is always worth forwarding.

### Fix 2: mac_notifier v0.2.0 — grace window 90 → 300

300 seconds (5 minutes) gives comfortable headroom above the 60s poll interval. A notification that arrives 4 minutes late still fires. A notification older than 5 minutes is genuinely stale and should be skipped. This aligns with the `feedback_reliability_over_speed` principle: a 4-minute-late notification beats a silently missed one.

Environment variable override (`NOTIFIER_GRACE_WINDOW=<seconds>`) is fully preserved.

---

## Red → Green Table

| # | Test | File | Before | After |
|---|------|------|--------|-------|
| 1 | `test_v011_vet_remind_incident_posts_to_herman` | `Sprite/tests/test_watcher.py` | FAIL | PASS |
| 2 | `test_process_file_ambiguous_fields_no_longer_gates_to_inbox` | `Sprite/tests/test_watcher.py` | FAIL | PASS |
| 3 | `test_v011_confidence_gate_still_routes_to_inbox_when_below_threshold` | `Sprite/tests/test_watcher.py` | PASS | PASS |
| 4 | `test_v011_confidence_below_threshold_with_ambiguous_goes_to_inbox` | `Sprite/tests/test_watcher.py` | PASS | PASS |
| 5 | `test_v011_schedule_override_preserved_forwards_to_herman` | `Sprite/tests/test_watcher.py` | PASS | PASS |
| 6 | `TestGraceWindowV020::test_default_grace_window_is_300` | `mac_notifier/tests/test_config.py` | FAIL | PASS |
| 7 | `TestGraceWindowV020::test_module_level_constant_is_300` | `mac_notifier/tests/test_config.py` | FAIL | PASS |
| 8 | `TestGraceWindowV020::test_plist_has_300` | `mac_notifier/tests/test_config.py` | FAIL | PASS |
| 9 | `TestGraceWindowExtended::test_99s_past_fires_with_300s_grace` | `mac_notifier/tests/test_poller.py` | PASS† | PASS |
| 10 | `TestGraceWindowExtended::test_200s_past_fires_with_300s_grace` | `mac_notifier/tests/test_poller.py` | PASS† | PASS |
| 11 | `TestGraceWindowExtended::test_400s_past_skips_with_300s_grace` | `mac_notifier/tests/test_poller.py` | PASS† | PASS |
| 12 | `TestGraceWindowExtended::test_90s_past_would_have_been_skipped_with_old_grace` | `mac_notifier/tests/test_poller.py` | FAIL | PASS |
| 13 | Herman `test_ambiguous_time_hint_returns_stored_false_with_clarifying_question` | `brain/tests/test_capture_parsed.py` | PASS‡ | PASS |
| 14 | Herman `test_v180_e2e_handle_bare_hour_3_still_asks` | `brain/tests/test_capture_parsed.py` | PASS‡ | PASS |

† Tests 9–11 passed in the red phase because they use explicit `GRACE_300=300` bypassing the default; the default constant tests (6–8) are what failed red.

‡ Herman-side tests were already green — Herman's clarifying-question logic existed. The gap was Sprite never forwarding the call.

**Final counts:** Sprite 184 passed. mac_notifier 128 passed. Herman 42 passed.

---

## Files Changed

| Package | File | Change |
|---------|------|--------|
| Sprite v0.11.0 | `src/sprite/watcher.py` | Remove `or bool(ambiguous_fields)` from gate; rename var to `is_low_confidence`; bump startup log |
| Sprite v0.11.0 | `src/sprite/__init__.py` | `__version__` 0.7.0 → 0.11.0 |
| Sprite v0.11.0 | `pyproject.toml` | `version` 0.10.0 → 0.11.0 |
| Sprite v0.11.0 | `tests/test_watcher.py` | Replace old ambiguous-gate test; add 5 new v0.11.0 tests |
| mac_notifier v0.2.0 | `src/mac_notifier/config.py` | Default grace window 90 → 300 (both constant and `Config.from_env`) |
| mac_notifier v0.2.0 | `src/mac_notifier/__init__.py` | VERSION 0.1.0 → 0.2.0; changelog entry |
| mac_notifier v0.2.0 | `pyproject.toml` | `version` 0.1.0 → 0.2.0 |
| mac_notifier v0.2.0 | `deploy/com.homunculus.mac_notifier.plist` | NOTIFIER_GRACE_WINDOW 90 → 300; comment updated; version bump in comment |
| mac_notifier v0.2.0 | `tests/test_config.py` | Update existing default test (90→300); add `TestGraceWindowV020` suite (4 tests) |
| mac_notifier v0.2.0 | `tests/test_poller.py` | Add `TestGraceWindowExtended` suite (4 tests) |

---

## Migration Steps (for Thomas)

### Step 1: Bounce Sprite

```bash
launchctl unload ~/Library/LaunchAgents/com.sprite.watcher.plist
launchctl load  ~/Library/LaunchAgents/com.sprite.watcher.plist
```

Verify startup log shows `Sprite watcher v0.11.0 starting`.

### Step 2: Reinstall and bounce mac_notifier

```bash
launchctl unload ~/Library/LaunchAgents/com.homunculus.mac_notifier.plist
bash /Volumes/GIT/CLAUDE/SHARED_WORK_FOLDER/Homunculus/mac_notifier/deploy/install.sh
launchctl load  ~/Library/LaunchAgents/com.homunculus.mac_notifier.plist
```

Verify the plist was copied from `deploy/` (not the old one in `~/Library/LaunchAgents/`). Check:

```bash
grep NOTIFIER_GRACE_WINDOW ~/Library/LaunchAgents/com.homunculus.mac_notifier.plist
# should show: <string>300</string>
```

### Step 3: Re-process the vet reminder

The "call the vet at 3" recording was processed by the old Sprite and written to the inbox state with `disposition=inbox`. To re-process it, remove the state entry so Sprite's cold-boot sweep picks it up again on restart.

Find and remove the line containing audio hash `042c44a7e251d33b720dc7d616a12d37`:

```bash
grep -n "042c44a7e251d33b720dc7d616a12d37" ~/sprite/state/processed.jsonl
# note the line number, then remove it (or just remove the whole file to re-process everything)
```

Easiest approach — remove the specific entry:

```bash
python3 -c "
lines = open('$HOME/sprite/state/processed.jsonl').readlines()
lines = [l for l in lines if '042c44a7e251d33b720dc7d616a12d37' not in l]
open('$HOME/sprite/state/processed.jsonl', 'w').writelines(lines)
print(f'Kept {len(lines)} lines')
"
```

Or find by subject if you prefer:

```bash
python3 -c "
import json, os
f = os.path.expanduser('~/sprite/state/processed.jsonl')
lines = open(f).readlines()
filtered = []
for l in lines:
    try:
        d = json.loads(l)
        if 'vet' in str(d.get('details', '')).lower():
            print('Removing:', l.strip())
        else:
            filtered.append(l)
    except:
        filtered.append(l)
open(f, 'w').writelines(filtered)
"
```

Then bounce Sprite again (cold-boot sweep will re-process the .m4a automatically):

```bash
launchctl unload ~/Library/LaunchAgents/com.sprite.watcher.plist
launchctl load  ~/Library/LaunchAgents/com.sprite.watcher.plist
```

### Step 4: Verify

Within ~90 seconds of Sprite restart you should see:

- mac_notifier fires a Mac notification with a question like "3 — AM or PM?" (or Herman's exact phrasing)
- Dashboard shows an amber row for the clarifying record
- `~/sprite/state/processed.jsonl` has a new line with `"disposition": "clarifying"`

### Step 5: Verify timer_stop notifications

Start any project timer via voice, then stop it. Wait ~2 minutes. The stop notification should fire. With the old 90s grace and an unlucky poll-cycle slot it would have been swallowed. With 300s it fires even if it misses by a full cycle.

---

## Follow-Up Candidate: v0.12 (not in scope here)

The Sprite gate currently uses `effective_confidence = min(whisper_conf, llm_conf)` as a single number for both transcript quality and parse quality. A garbled transcript (`whisper_conf = 0.4`) and a clean transcript with a genuinely uncertain parse (`llm_conf = 0.45`) are treated identically. They shouldn't be: the former is worth skipping (garbled audio), the latter might be worth forwarding to Herman with a low-confidence flag.

Splitting the two confidence signals into separate gates (whisper below threshold → inbox; LLM confidence passed through to Herman for its own gate) would give more resolution. Queued as a v0.12 candidate — not urgent, but worth a conversation before the next parse-quality incident.
