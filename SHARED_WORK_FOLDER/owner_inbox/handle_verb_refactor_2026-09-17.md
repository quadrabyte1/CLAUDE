# Handle Verb Refactor — Handoff

**Date:** 2026-09-17
**Author:** Rune (Senior Python Engineer)
**Task:** 552

---

## Summary

The `handle` and `remind` verbs now route correctly to **Reminders.app** instead
of Calendar.app. A `handle` is a to-do; Calendar is for time-blocked meetings.
Four packages were updated; a new bridge package was created; 8 vault files need
migration.

---

## What Changed

### Herman brain — v1.5.0 → v1.6.0

- New verb: `remind` added to `CaptureVerb` enum. Routes identically to `handle`
  through `_handle_handle()`. Original verb is preserved in the response.
- `_handle_handle()` now writes to `vault/reminders/<event-id>.md` (not `vault/calendar/`).
- No more `[handle]` / `[handle!]` title prefix. Vault location is the semantic signal.
- Criticality expressed as `criticality: critical` frontmatter tag.
- 11 new tests in `tests/test_v160_reminders_vault.py` (all green).

### Sprite — v0.6.0 → v0.7.0

- `remind` added to the verb enum in the Ollama JSON schema.
- System prompt teaches the `remind` / `handle` distinction:
  - `handle` = bare imperative ("call the vet")
  - `remind` = starts with "remind me" or "don't let me forget"
- 2 new few-shot examples for `remind` in the system prompt.
- 12 new tests in `tests/test_v070_remind_verb.py` (all green).

### mac_calendar_bridge — v0.1.5 → v0.2.0

- Version bump only. Scope clarification: this bridge handles `schedule` events
  only. Handle/remind events no longer land in Calendar. The `display_title`
  strip of `[handle]`/`[handle!]` prefixes is kept as a safety net for any
  stragglers pushed before migration.

### mac_reminders_bridge — NEW — v0.1.0

New sibling package. Mirrors `mac_calendar_bridge` structure.

Key design decisions:
- **Atomic creation**: single `make new reminder with properties {...}` command —
  never two-step (same silent-rollback risk Calendar v0.1.5 caught).
- **No native alarm**: `due date` is set (optional) but NOT `remind me date`.
  mac_notifier is the authoritative alarm; no double-fire.
- **URL-based deduplication**: `homunculus://reminder/<event_id>` in the `url`
  property. Reminders.app exposes `url` in its AppleScript dictionary (unlike
  Notes.app which has none).
- **3-step idempotency**: fast path (pushed.jsonl) → slow path (app query) →
  push. Self-heals pushed.jsonl if the Reminders.app query finds an existing
  reminder not in the state file.
- **112 tests** — vault_reader (26), applescript (38), state (19), watcher (29).
  All green. No live osascript calls in tests.

---

## Files Created / Modified

### New files

```
Homunculus/mac_reminders_bridge/
├── src/mac_reminders_bridge/
│   ├── __init__.py          (VERSION = "0.1.0")
│   ├── config.py
│   ├── vault_reader.py
│   ├── state.py
│   ├── applescript.py
│   └── watcher.py
├── tests/
│   ├── test_vault_reader.py   (26 tests)
│   ├── test_applescript.py    (38 tests)
│   ├── test_state.py          (19 tests)
│   └── test_watcher.py        (29 tests)
├── deploy/
│   ├── com.homunculus.mac_reminders_bridge.plist
│   ├── mac-reminders-bridge.service  (systemd sibling)
│   └── install.sh
├── docs/
│   └── FIRST_RUN.md
└── pyproject.toml

Homunculus/scripts/migrate_handles_from_calendar.py
```

### Modified files

```
Homunculus/brain/homunculus_brain/__init__.py    (VERSION 1.5.0 → 1.6.0)
Homunculus/brain/homunculus_brain/schemas.py     (REMIND added to CaptureVerb)
Homunculus/brain/homunculus_brain/vault.py       (vault_reminders_dir + vault_reminder_path)
Homunculus/brain/homunculus_brain/capture_parsed.py  (rewrote _handle_handle)
Homunculus/brain/pyproject.toml                  (1.5.0 → 1.6.0)
Homunculus/brain/tests/test_v160_reminders_vault.py  (NEW — 11 tests)
Homunculus/brain/tests/test_capture_parsed.py    (updated critical test)

Sprite/src/sprite/__init__.py    (0.6.0 → 0.7.0)
Sprite/src/sprite/parse.py       (remind verb + few-shot examples)
Sprite/src/sprite/watcher.py     (version string)
Sprite/pyproject.toml            (0.6.0 → 0.7.0)
Sprite/tests/test_v070_remind_verb.py  (NEW — 12 tests)

Homunculus/mac_calendar_bridge/src/mac_calendar_bridge/__init__.py  (0.1.5 → 0.2.0)
Homunculus/mac_calendar_bridge/pyproject.toml   (0.1.5 → 0.2.0)
Homunculus/mac_calendar_bridge/README.md        (scope clarification)
```

---

## Action Required: Migration

**8 existing handle events** in `vault/calendar/` need to move to `vault/reminders/`:

```bash
# Review what will happen (safe):
python Homunculus/scripts/migrate_handles_from_calendar.py

# Execute:
python Homunculus/scripts/migrate_handles_from_calendar.py --apply
```

The events are all from 2026-09-16 and 2026-09-17. They were written before v1.6.0
deployed. The migration strips the `[handle]` prefix from titles and rewrites
frontmatter to the v1.6.0 format.

After migration, reload mac_calendar_bridge (it may try to push the handle events
one more time if they're still in its pushed.jsonl — harmless, it won't duplicate
them since it deduplicates by event_id URL).

---

## Action Required: Install mac_reminders_bridge

```bash
cd Homunculus/mac_reminders_bridge
bash deploy/install.sh
```

Then follow `docs/FIRST_RUN.md`:

1. Create "Homunculus" list in Reminders.app (File → New List → iCloud → Homunculus)
2. Load the plist: `launchctl load ~/Library/LaunchAgents/com.homunculus.mac_reminders_bridge.plist`
3. Grant Automation permission for Reminders.app when prompted
4. Verify: `tail -f /tmp/mac_reminders_bridge.log`

---

## Test Counts

| Package | Tests | Status |
|---------|-------|--------|
| Herman brain | 11 new (v1.6.0) + 1 updated | All green |
| Sprite | 12 new (v0.7.0) | All green |
| mac_reminders_bridge | 112 (vault_reader + applescript + state + watcher) | All green |

---

## Non-Goals (Not Changed)

- vault/_reminders/ — strike-chain sidecars; unrelated to this refactor
- mac_notes_bridge — unchanged
- mac_notifier — unchanged
- Herman's morning summary, /ack, /reminders/upcoming — unchanged
- Sprite's audio pipeline — unchanged
