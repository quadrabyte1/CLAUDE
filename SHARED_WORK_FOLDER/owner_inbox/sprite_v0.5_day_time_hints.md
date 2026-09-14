# Sprite v0.5.0 — 2026-09-14 — Rune

## Root cause

Two things failed in the live incident (voice memo "Let's set a second meeting with myself tomorrow at 10am", 2026-09-14 16:42:33):

**1. LLM date math.** The system prompt told Ollama to put a "relative expression" in the `when` field if it couldn't resolve a date. Ollama silently decided "tomorrow" from Sunday 2026-09-14 was "Thursday" — arbitrary, wrong, and exactly the failure mode that a 7B model without a real-time clock will always produce. The model has no idea what day it is. Asking it to translate "tomorrow" into a day name is asking it to do calendar math with fabricated context. It will guess, and the guess will be wrong.

**2. Incomplete M3 alignment.** Herman's M3 schema already accepted `day_hint`/`time_hint` (added in Herman v1.3.1). Sprite never propagated those fields out of the LLM output. The `_PARSE_SCHEMA` still had `when` as a required string. The emitted payload sent `when="thursday at 10am"` which Herman's `ParsedCaptureRequest` rejected with HTTP 400: `datetime_from_date_parsing, invalid character in year`.

## What was fixed (v0.5.0)

### `Sprite/src/sprite/parse.py`

- Renamed `_PARSE_SCHEMA` → `_INTENT_JSON_SCHEMA` (exported for test introspection).
- Removed `when` from `required`. Added `day_hint` and `time_hint` to `required`.
- `day_hint` — verbatim day expression the user spoke: "tomorrow", "Thursday", "September 18th", "next Monday". Copy exactly; do not resolve.
- `time_hint` — verbatim time expression the user spoke: "10am", "9:00 AM", "5:35". Copy exactly; do not add AM/PM if the user did not say it.
- `when` remains in `properties` as optional — the LLM may emit it only when the user provided an explicit, unambiguous ISO-8601 string (rare in speech). It is never in `required`.
- Rewrote `_SYSTEM_PROMPT` with the explicit "do not compute" rule, AM/PM no-guess rule, and six few-shot examples covering relative day, absolute date, day-only, time-only, bare-hour, and no-time utterances.
- `ParseResult` dataclass: dropped `when` field, added `day_hint: Optional[str]` and `time_hint: Optional[str]`. The old `when` string path is gone; constructing `ParseResult(when=...)` now raises `TypeError`.
- The rare explicit-ISO case is preserved via `raw_llm_json["when"]` (provenance dict already stored) — the watcher extracts and validates it before use.

### `Sprite/src/sprite/watcher.py`

- Updated `process_file()` to read `parse_result.day_hint` / `parse_result.time_hint`.
- Added ISO-validation guard for the rare `raw_llm_json["when"]` path.
- Passes `day_hint`/`time_hint` to `build_request()` (or clears them when an explicit ISO datetime is in `raw_llm_json["when"]`).
- Version string: `"Sprite watcher v0.4.0 starting"` → `"Sprite watcher v0.5.0 starting"`.

### `Sprite/pyproject.toml`

- `version = "0.4.0"` → `"0.5.0"`.

### `Sprite/docs/FIRST_RUN.md`

- Updated expected log output to show v0.5.0.

### `herman.py` — no changes

`build_request()` already accepted `day_hint`/`time_hint` from M3. No changes needed.

### Deploy files — no changes

`com.sprite.watcher.plist` and `sprite-watcher.service` reference the watcher binary via the shell wrapper, not the prompt or schema. No changes needed.

## Red → green story

Tests written FIRST against v0.4.0 code (all failed at import — `_INTENT_JSON_SCHEMA` did not exist):

| # | Test | v0.4.0 | v0.5.0 |
|---|------|---------|---------|
| 1 | `test_regression_tomorrow_at_10am_yields_hints_not_when_string` | FAIL | PASS |
| 2 | `test_schema_does_not_require_when_and_requires_hints` | FAIL | PASS |
| 3 | `test_system_prompt_teaches_no_date_math` | FAIL | PASS |
| 4 | `test_build_request_with_hints_only_sends_none_when` | FAIL | PASS |
| 5 | `test_build_request_iso_when_takes_precedence_over_hints` | FAIL | PASS |
| 6 | `test_parse_result_has_no_when_field` | FAIL | PASS |
| 7 | `test_wire_shape_hints_round_trip_through_herman_schema` | FAIL | PASS |
| 8 | `test_end_to_end_tomorrow_at_10am_clean_dispatch` | FAIL | PASS |

Final suite: **115 passed** (up from 55 before this milestone).

## Steps to deploy

### 1. Reinstall Sprite

The editable install picks up Python changes automatically, but the Ollama prompt is loaded at process start. A bounce is required to get the new `_SYSTEM_PROMPT` and `_INTENT_JSON_SCHEMA` into the running process.

```bash
cd /Volumes/GIT/CLAUDE/SHARED_WORK_FOLDER/Sprite
~/.local/lib/sprite/venv/bin/pip install -e . --quiet
```

### 2. Clear the stuck error entry

The "Let's set a second meeting with myself tomorrow at 10am" memo landed in `processed.jsonl` with `disposition=error`. Clear it so the watcher re-processes it on restart.

```bash
~/.local/lib/sprite/venv/bin/python -c "
from pathlib import Path
import json
p = Path.home() / 'sprite/state/processed.jsonl'
kept = [l for l in p.read_text().splitlines() if l.strip() and json.loads(l).get('disposition') not in ('error', 'inbox')]
p.write_text('\n'.join(kept) + '\n')
print(f'kept {len(kept)}, cleared error+inbox entries')
"
```

### 3. Bounce the Sprite launchd agent

```bash
launchctl unload ~/Library/LaunchAgents/com.sprite.watcher.plist
launchctl load   ~/Library/LaunchAgents/com.sprite.watcher.plist
```

### 4. Watch the cascade

```bash
tail -f /tmp/sprite_watcher.log
```

Expected sequence:
1. Sprite cold-boot finds the stuck memo.
2. Ollama parse emits `day_hint="tomorrow"`, `time_hint="10am"`.
3. Sprite POSTs to Herman with `when=null`, `day_hint="tomorrow"`, `time_hint="10am"`.
4. Herman's `date_resolver` resolves "tomorrow" relative to 2026-09-14 → 2026-09-15 (Monday).
5. Event written to vault. Reminder chain scheduled. mac_calendar_bridge pushes to iCloud → phone.

## Design contract going forward

The LLM is a parser, not a clock. It extracts what the user said. Python resolves it. This split is now enforced by the type system (no `when` field on `ParseResult`) and by the schema guard test (`test_schema_does_not_require_when_and_requires_hints`). Any future attempt to add `when` back to `required` will fail CI.
