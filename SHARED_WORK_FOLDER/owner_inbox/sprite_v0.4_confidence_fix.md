# Sprite v0.4.0 — 2026-09-13 — Rune

## Root Cause

```
whisper-cli --output-json     →  segments have no 'tokens' key
_compute_confidence saw:      →  seg.get("avg_logprob", -1.0)  ← SILENT DEFAULT
result:                       →  exp(-1.0) = 0.36787944117144233  ← every memo, always
gating:                       →  0.368 < 0.6 min_confidence → inbox, never Herman
```

The flag `--output-json` does not emit per-token probabilities. The field `avg_logprob` is absent from every segment in the actual output. The code's fallback `seg.get("avg_logprob", -1.0)` silently returned `-1.0` for every segment, which `math.exp(-1.0)` maps to exactly `1/e ≈ 0.3679`. Every memo ever processed was gated to inbox.

## Fix

Three changes in `Sprite/src/sprite/transcribe.py`:

1. **Flag:** `--output-json` → `--output-json-full`  
   `--output-json-full` adds a `tokens` array to each segment. Each token has field `p` (float, probability in [0, 1]).

2. **New `_is_special_token(text)`:** filters `[_BEG_]`, `[_TT_576]`, `<|endoftext|>` etc.  
   Detection rule: token text (stripped) starts+ends with `[`/`]` or `<`/`>`.

3. **New `_compute_confidence(segments)`:**  
   `confidence = sum(tok.p for real_tokens) / len(real_tokens)`  
   Returns `0.0` (not `exp(-1.0)`) when zero real tokens survive.  
   No math in the prompt. Python does the arithmetic.

## Red → Green

| Test | Status before | Status after | What it proves |
|---|---|---|---|
| `test_v04_compute_confidence_filters_special_tokens` | RED: got 1/e=0.3679, want 0.700 | GREEN | Special tokens `[_BEG_]`, `<\|endoftext\|>`, `[_TT_576]` excluded from mean |
| `test_v04_compute_confidence_no_tokens_degenerate` | RED: got 1/e | GREEN | Empty transcription, empty tokens list, all-special → 0.0 (not 1/e) |
| `test_v04_regression_guard_no_one_over_e` | RED: avg_logprob=-1.0 still triggered | GREEN | 1/e never appears under any input |
| `test_v04_schema_guard_no_segments_key_lookup` | PASS (tests dict key lookup, already correct) | PASS | `raw_json.get("transcription")` is the correct key, not `"segments"` |
| `test_v04_full_json_transcribe_integration` | RED: got 1/e=0.3679, want 0.700 | GREEN | End-to-end transcribe() with --output-json-full JSON feeds correct confidence |

All 104 tests green (was 99 before this PR — 5 new tests added, 1 test updated to match new token-based API).

## Live Memo Verification

Memo: `~/sprite/audio/2026/09/e4ddd82879e2a311df69dfa83a6b178a.m4a`  
Transcript: `"Sprite test one. Schedule a meeting with myself on September 15th at 9 a.m."`  
**Confidence: 0.816489** (was 0.367879 — exactly 1/e)  
21 tokens total, 19 real (2 special: `[_BEG_]` and `[_TT_576]`).  
0.816 > 0.6 min_confidence → memo will now flow to Herman.

## Files Changed

| File | Change |
|---|---|
| `Sprite/src/sprite/transcribe.py` | `--output-json` → `--output-json-full`; rewrote `_compute_confidence` to use `token.p`; added `_is_special_token`; removed `import math`; updated docstring/comments |
| `Sprite/tests/test_transcribe.py` | Added 5 new TDD tests (9–13); updated test 8 to use token-p format; added `_compute_confidence` to imports |
| `Sprite/src/sprite/config.py` | `ollama_model` default: `"qwen2.5:7b-instruct"` → `"qwen2.5:7b"` |
| `Sprite/pyproject.toml` | `0.3.0` → `0.4.0` |
| `Sprite/src/sprite/watcher.py` | `"Sprite watcher v0.3.0 starting"` → `"Sprite watcher v0.4.0 starting"` |
| `Sprite/README.md` | v0.3 → v0.4; `qwen2.5:7b-instruct` → `qwen2.5:7b` throughout |
| `Sprite/docs/FIRST_RUN.md` | `qwen2.5:7b-instruct` → `qwen2.5:7b`; v0.3.0 → v0.4.0 in sample log |
| `Sprite/tests/test_parse.py` | `qwen2.5:7b-instruct` → `qwen2.5:7b` (4 occurrences) |
| `Sprite/tests/test_end_to_end.py` | `qwen2.5:7b-instruct` → `qwen2.5:7b` |
| `Sprite/tests/test_watcher.py` | `qwen2.5:7b-instruct` → `qwen2.5:7b` |

## Stale Default Flag (scoping doc)

`owner_inbox/sprite_mac_backend_scoping.md` §3 still mentions `qwen2.5:7b-instruct`. That is a historical design doc — not updated here per non-goals. Flag for awareness: if you share that doc externally, the model name is stale.

## What Thomas Does Now

1. Reinstall the venv to pick up the new module:
   ```bash
   cd /Volumes/GIT/CLAUDE/SHARED_WORK_FOLDER/Sprite
   pip install -e .
   ```

2. Clear the inbox disposition entry so the memo re-processes:
   ```bash
   # Remove the line whose key matches e4ddd82879e2a311df69dfa83a6b178a
   python3 -c "
   import json
   from pathlib import Path
   sf = Path.home() / 'sprite/state/processed.jsonl'
   lines = sf.read_text().splitlines()
   kept = [l for l in lines if 'e4ddd82879e2a311df69dfa83a6b178a' not in l]
   sf.write_text('\n'.join(kept) + ('\n' if kept else ''))
   print(f'Removed {len(lines)-len(kept)} line(s)')
   "
   ```

3. Bounce the launchd agent:
   ```bash
   launchctl unload ~/Library/LaunchAgents/com.sprite.watcher.plist
   launchctl load  ~/Library/LaunchAgents/com.sprite.watcher.plist
   ```

4. Watch the pipeline post to Herman:
   ```bash
   tail -f /tmp/sprite_watcher.log
   # Expected: conf=0.816 (or close) → verb=schedule → Herman accept → vault event written
   # Then check: ls ~/homunculus/vault/calendar/ | sort -r | head -3
   ```

## What M5 Should Be

The memo text parsed as `"Schedule a meeting with myself on September 15th at 9 a.m."` — a clear `schedule` verb with an explicit date and time. M5 verification target: Herman writes a calendar event at `2026-09-15T09:00:00` in Thomas's vault, the morning summary at 7 AM mentions it, and a T-30 / T-5 / strike chain fires on September 15th.

If the vault event appears but the reminder strikes don't fire, the next investigation is `vault/_reminders/` — confirm the strike sidecar JSON was written by Herman's reminder schedule generator.
