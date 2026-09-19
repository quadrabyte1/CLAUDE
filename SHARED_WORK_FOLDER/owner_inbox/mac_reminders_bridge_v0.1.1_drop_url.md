# v0.1.1 — 2026-09-19 — Rune
## mac_reminders_bridge — Remove url: property (AppleScript -1700 fix)

---

## Root Cause

Reminders.app's AppleScript dictionary does **not** expose a `url` property. Attempting to include `url:` in a `make new reminder with properties {…}` dict causes AppleScript error **-1700** ("Can't make … into type properties of reminder") and silently discards the entire `make` call — no reminder is created, no explicit error is surfaced to the caller's log until the subprocess stdout is inspected.

This was empirically confirmed on 2026-09-19 with four osascript probes inside `list "Homunculus"`:

| Properties dict | Result |
|---|---|
| `{name:"test-minimal"}` | success |
| `{name:"test-body", body:"..."}` | success |
| `{name:"test-due", body:"...", due date:...}` | success |
| `{name:"test-url", body:"...", URL:"homunculus://reminder/test"}` | **-1700 error** |

v0.1.0 included `url:"homunculus://reminder/<event_id>"` in the properties dict of every `push_reminder` call. All 9 cold-boot-sweep reminders failed silently.

---

## What Changed

### `src/mac_reminders_bridge/applescript.py`

1. **`push_reminder`** — `url:` field removed from both AppleScript templates (with-due-date and without-due-date branches). Properties dict now contains only `name:`, `body:`, and optionally `due date:`.

2. **`query_pushed_reminder_ids`** — Rewritten. The old implementation queried `url of r` on each reminder and parsed `homunculus://reminder/<event_id>` from the result. The new implementation queries `body of r` and extracts event_ids via the regex `\[herman-id:([^\]]+)\]`. The body sentinel `[herman-id:<event_id>]` is already written by `ReminderRecord.reminders_body` and is the durable idempotency key.

3. `import re` added; `_HERMAN_ID_RE` regex compiled at module level.

### `src/mac_reminders_bridge/vault_reader.py`

- `homunculus_url` property removed from `ReminderRecord` — it was only ever used by the now-fixed `push_reminder` to populate `url:`. The `[herman-id:…]` sentinel in `reminders_body` is the sole idempotency key going forward.
- Module docstring updated to reflect body-marker dedup strategy.

### `src/mac_reminders_bridge/state.py`

- Docstring comment updated: URL-based dedup language replaced with body-sentinel language.

### `src/mac_reminders_bridge/watcher.py`

- `push_if_new` docstring updated to reflect body-sentinel slow path.

### Version bump

- `pyproject.toml`: `0.1.0` → `0.1.1`
- `src/mac_reminders_bridge/__init__.py`: `VERSION = "0.1.1"`

---

## Red → Green (Bug→TDD)

Five regression tests added to `tests/test_applescript.py` under `class TestV011RegressionNoUrlProperty`:

| # | Test | Before fix | After fix |
|---|---|---|---|
| 1 | `test_push_reminder_script_does_not_contain_url_property` | RED — `url:` was in properties block | GREEN |
| 2 | `test_push_reminder_script_contains_body_sentinel` | GREEN (already passing) | GREEN |
| 3 | `test_query_pushed_reminder_ids_extracts_from_body` | RED — old impl looked for URL prefix, returned `[]` | GREEN |
| 4 | `test_push_if_new_skips_when_event_id_in_body` | GREEN (already passing — correct gating) | GREEN |
| 5 | `test_no_url_scheme_in_applescript_module` | RED — `homunculus://reminder/` present in module source | GREEN |

Full suite after fix: **116 passed, 0 failed** (up from 38 pre-regression-test; 78 pre-existing tests in state/vault_reader/watcher unchanged).

Two existing tests updated to reflect the removed `homunculus_url` property:
- `TestQueryPushedReminderIds::test_parses_single_url` → `test_parses_single_body_sentinel`
- `TestQueryPushedReminderIds::test_parses_multiple_urls` → `test_parses_multiple_body_sentinels`
- `TestQueryPushedReminderIds::test_ignores_non_homunculus_urls` → `test_ignores_bodies_without_sentinel`
- `TestPushReminder::test_script_contains_homunculus_url` → `test_script_does_not_contain_url_property`
- `TestReminderRecordProperties::test_homunculus_url_format` + `test_homunculus_url_prefix` → `test_reminders_body_sentinel_is_idempotency_key`

---

## pushed.jsonl state check

**v0.1.0 correctly gated `mark_pushed()` behind success only.** In all three push sites (`cold_boot_sweep`, `periodic_sweep`, `push_if_new`), `state.mark_pushed(record.event_id)` is called only after `push_reminder()` returns without raising. The `AppleScriptError` catch block logs the error and does not call `mark_pushed`. Therefore the 9 failed attempts did NOT write entries to `pushed.jsonl`. The state file is either absent or empty.

**Thomas does NOT need to run `rm ~/.local/share/mac_reminders_bridge/pushed.jsonl` before reinstalling.**

---

## Migration Steps

1. `launchctl unload ~/Library/LaunchAgents/com.homunculus.mac_reminders_bridge.plist`
2. `bash /Volumes/GIT/CLAUDE/SHARED_WORK_FOLDER/Homunculus/mac_reminders_bridge/deploy/install.sh`
3. `launchctl load ~/Library/LaunchAgents/com.homunculus.mac_reminders_bridge.plist`
4. `tail -f /tmp/mac_reminders_bridge.log` — expect cold-boot sweep to push all 9 successfully; verify count in Reminders.app is 9.

Note: no need to clear `pushed.jsonl` — v0.1.0 never wrote to it on failure.

---

*Rune — mac_reminders_bridge v0.1.1*
