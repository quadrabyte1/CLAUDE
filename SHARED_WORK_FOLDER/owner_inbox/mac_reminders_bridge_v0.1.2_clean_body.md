# mac_reminders_bridge v0.1.2 — Clean Reminder Body

**v0.1.2** · Rune · 2026-09-22

---

## Problem Statement

Thomas opened a Reminder in Reminders.app and saw this in the note field:

```
# renew car registration

*Captured 2026-09-22 13:43 UTC via Sprite.*

Remind me to renew the car registration on October 30th at 10 a.m.

[herman-id:2026-10-30-renew-car-registration]
```

Thomas's words:

> "Each reminder item in its text field is getting a note in square brackets that is not useful. Let's drop that. And there are superfluous carriage returns between the lines, so it takes up a lot of vertical space in my report. So no blank lines between lines."

Two problems:

1. **`[herman-id:...]` sentinel** — v0.1.1 embedded this in the body as the idempotency key for the slow-path dedup check. Implementation detail leaking into the user-visible field.
2. **Body is the full vault markdown** — the `# heading`, the `*Captured ... via Sprite.*` italic caption, and the blank lines are all chrome that duplicates information already in Reminders.app's own fields or is metadata not useful to the user.

---

## New Body-Composition Rules

`ReminderRecord.reminders_body` (the value written to Reminders.app's note field) now strips all chrome and returns only the raw utterance.

**Strips:**
- `# heading` lines (any level)
- `*Captured ... via Sprite.*` italic captions
- `[herman-id:...]` legacy sentinels (backward-compat cleanup)
- All blank lines — leading, trailing, and interior

**Falls back to:** `frontmatter.title` if the body is empty after stripping.

**Target body for the car registration reminder:**
```
Remind me to renew the car registration on October 30th at 10 a.m.
```

One line. Nothing else.

---

## New Idempotency Scheme

**Removed:** `query_pushed_reminder_ids()` — queried reminder bodies and extracted `[herman-id:...]` sentinels.

**Added:** `query_pushed_reminder_names()` — queries `name of every reminder` in the list and returns reminder names.

Belt-and-suspenders (same 3-step ladder as mac_calendar_bridge v0.1.5):

1. **Fast path** — `pushed.jsonl` in-memory set (O(1), no Reminders.app round-trip)
2. **Slow path** — `query_pushed_reminder_names()` compares `record.display_title` against all existing reminder names. Self-heals `pushed.jsonl` on hit.
3. **Push** — only if both say "not present"

Worst case (state file wiped + title collision from a different capture): duplicate. Rare; cleanable manually. The trade-off is correct — UX over dedup robustness in the one-in-a-hundred edge case.

---

## Retroactive Cleanup Script

**File:** `Homunculus/mac_reminders_bridge/scripts/cleanup_existing_reminders.py`

Rewrites existing Reminders.app entries (pushed under v0.1.1) to strip sentinel, heading, and caption from the body. Does NOT delete reminders.

```bash
# Dry run (safe — shows what would change):
python Homunculus/mac_reminders_bridge/scripts/cleanup_existing_reminders.py

# Apply:
python Homunculus/mac_reminders_bridge/scripts/cleanup_existing_reminders.py --apply

# Custom list:
python Homunculus/mac_reminders_bridge/scripts/cleanup_existing_reminders.py --list "Homunculus" --apply
```

Idempotent — safe to run multiple times. `clean_body()` returns `None` for already-clean bodies; second run does nothing.

---

## Red → Green Table

| # | Test | File | Before | After |
|---|------|------|--------|-------|
| 1 | `test_live_regression_exact_body` | test_vault_reader.py | RED | GREEN |
| 2 | `test_live_regression_no_leading_trailing_whitespace` | test_vault_reader.py | RED | GREEN |
| 3 | `test_live_regression_no_newlines` | test_vault_reader.py | RED | GREEN |
| 4 | `test_strips_h1_heading_line` | test_vault_reader.py | RED | GREEN |
| 5 | `test_strips_h2_heading_line` | test_vault_reader.py | RED | GREEN |
| 6 | `test_heading_strip_preserves_utterance` | test_vault_reader.py | RED | GREEN |
| 7 | `test_strips_italic_captured_caption` | test_vault_reader.py | RED | GREEN |
| 8 | `test_strips_italic_caption_various_dates` | test_vault_reader.py | RED | GREEN |
| 9 | `test_strips_legacy_herman_id_sentinel` | test_vault_reader.py | RED | GREEN |
| 10 | `test_strips_sentinel_from_any_position` | test_vault_reader.py | RED | GREEN |
| 11 | `test_collapses_consecutive_blank_lines` | test_vault_reader.py | RED | GREEN |
| 12 | `test_no_leading_blank_lines` | test_vault_reader.py | RED | GREEN |
| 13 | `test_no_trailing_blank_lines` | test_vault_reader.py | RED | GREEN |
| 14 | `test_fallback_empty_body_returns_title` | test_vault_reader.py | RED | GREEN |
| 15 | `test_fallback_only_heading_body_returns_title` | test_vault_reader.py | RED | GREEN |
| 16 | `test_fallback_only_caption_body_returns_title` | test_vault_reader.py | RED | GREEN |
| 17 | `test_reminders_body_contains_no_sentinel` | test_vault_reader.py | RED | GREEN |
| 18 | `test_reminders_body_is_single_line_for_typical_vault` | test_vault_reader.py | RED | GREEN |
| 19 | `test_push_reminder_body_has_no_herman_id_sentinel` | test_applescript.py | RED | GREEN |
| 20 | `test_push_reminder_body_has_no_heading_line` | test_applescript.py | RED | GREEN |
| 21 | `test_push_reminder_body_has_no_captured_caption` | test_applescript.py | RED | GREEN |
| 22 | `test_no_herman_id_anywhere_in_applescript_module_source` | test_applescript.py | RED | GREEN |
| 23 | `TestQueryPushedReminderNames` (7 tests) | test_applescript.py | RED | GREEN |
| 24 | `test_state_file_fast_path_still_works` | test_watcher.py | RED | GREEN |
| 25 | `test_slow_path_name_match_skips_push` | test_watcher.py | RED | GREEN |
| 26 | `test_slow_path_name_miss_proceeds_to_push` | test_watcher.py | RED | GREEN |
| 27 | `test_slow_path_self_heals_state_on_name_hit` | test_watcher.py | RED | GREEN |
| 28–44 | `TestCleanBody` (8), `TestCleanupDryRun` (2), `TestCleanupApply` (2), `TestCleanupIdempotent` (1) | test_cleanup_script.py | RED | GREEN |

**Total: 116 → 160 passing (44 new tests, all green). 0 failures.**

---

## Migration Steps

1. Unload the daemon:
   ```bash
   launchctl unload ~/Library/LaunchAgents/com.homunculus.mac_reminders_bridge.plist
   ```

2. Install v0.1.2:
   ```bash
   bash Homunculus/mac_reminders_bridge/deploy/install.sh
   ```

3. Reload the daemon:
   ```bash
   launchctl load ~/Library/LaunchAgents/com.homunculus.mac_reminders_bridge.plist
   ```

4. Clean existing Reminders.app entries (one-shot):
   ```bash
   python Homunculus/mac_reminders_bridge/scripts/cleanup_existing_reminders.py --apply
   ```

5. Verify: open a reminder on iPhone or Mac. Body should be one clean line — no `[herman-id:...]`, no `# heading`, no `*Captured ...*`, no extra blank lines.

---

## Follow-up Question: Does mac_notes_bridge Have the Same Problem?

Check your Notes.app entries that Herman/Sprite pushed. If the note body contains `# heading`, `*Captured ...* ` captions, or `[herman-id:...]` markers, the same pattern applies.

If confirmed: we do a parallel v0.1.1 cleanup for mac_notes_bridge as a separate ticket. Rune will handle it the same way — TDD, body-cleaning helper, cleanup script, handoff doc.

Verdict call is yours — open a reminder and a note on your phone and compare.

---

*mac_reminders_bridge v0.1.2 — Rune, 2026-09-22*
