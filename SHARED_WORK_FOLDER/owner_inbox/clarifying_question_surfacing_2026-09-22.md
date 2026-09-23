# Herman v2.2.0 + Dashboard v0.5: Clarifying-Question Surfacing

**v2.2.0 / v0.5** · Rune · 2026-09-22

---

## Root Problem

Thomas's exact words:

> *"We need to find a better way to handle ambiguities that hang up processing of memos. When Herman decided that the 10 o'clock was ambiguous and gave me a question 'did you mean AM or PM', I had no idea that that question had come up. So we have to figure out how we're gonna manage that."*

**Previous behavior:** When `dispatch()` returned `stored=False` + `clarifying_question`, it logged nothing, wrote nothing, and returned the response silently. Sprite wrote the question to its inbox `.md` file — which Thomas never saw. Herman logged nothing. The Volvo call reminder Friday morning was the most recent casualty.

---

## Design (locked in)

**One-shot immediate + daily reminder if still unresolved.**

- On every `stored=False` clarifying response: fire an immediate Mac notification within the ~90 s grace window that mac_notifier already polls.
- If still unresolved 24h later: the daily morning summary (at `morning_anchor_hour`) includes "You have N pending clarifications. Check the Herman dashboard."
- Phase 1: Mac only. Phone-side notification waits for Kit's iOS client.

---

## Files Changed

| File | Change |
|---|---|
| `homunculus_brain/__init__.py` | VERSION `2.1.1 → 2.2.0`, DESIGN_VERSION `2.1 → 2.2` |
| `homunculus_brain/pyproject.toml` | version `2.1.1 → 2.2.0` |
| `homunculus_brain/schemas.py` | `ReminderKind.CLARIFY_IMMEDIATE = "clarify_immediate"` added |
| `homunculus_brain/capture_parsed.py` | New helpers: `_enqueue_clarify_notification`, `_append_clarifying_pending`, `_resolve_clarifying_pending`, `read_unresolved_clarifying`. Wired into `dispatch()` on the `stored=False` branch and the `stored=True` resolution path. Activity log entry written for clarifying responses so dashboard can show them. |
| `homunculus_brain/reminders.py` | `build_morning_summary` + `_compose_summary_body` accept `pending_clarifications`. `build_daily_summary_rows` reads unresolved entries once per call. New `_collect_clarify_notifications()` reads `clarify.*.json` sidecars. Wired into `collect_upcoming_rows`. |
| `homunculus_brain/dashboard.py` | `DASHBOARD_VERSION "v0.4" → "v0.5"`. `_is_clarifying_row()` helper. `_shape_row()` detects clarifying rows, sets `icon="⚠️❓"`, `summary="Awaiting clarification — <question>"`, `is_clarifying=True`, `clarifying_question=<full question>`. Warning-amber CSS (`.row.clarify`). `buildRow` JS applies `clarify` class and shows full question in expand panel. |
| `tests/test_clarifying_pending.py` | **New** — 13 tests, all written RED-first |
| `tests/test_dashboard.py` | 10 new v0.5 tests appended; existing `test_v04_version_badge` updated to track current version |
| `tests/test_timers_routes.py` | `test_dashboard_version_badge_v03` updated to track current version (no logic change) |

---

## Red → Green Table

| # | Test | Before | After |
|---|---|---|---|
| 1 | `test_clarify_sidecar_written_on_stored_false` | FAIL | PASS |
| 2 | `test_clarify_sidecar_body_contains_question_and_excerpt` | FAIL | PASS |
| 3 | `test_clarify_sidecar_identifier_matches_record_id` | FAIL | PASS |
| 4 | `test_clarifying_pending_row_appended` | FAIL | PASS |
| 5 | `test_reminders_upcoming_includes_clarify_daily_summary_past_anchor` | FAIL | PASS |
| 6 | `test_clarify_idempotent_on_repeated_post` | FAIL | PASS |
| 7 | `test_stored_false_response_wire_shape_unchanged` | PASS | PASS (pre-existing) |
| 8 | `test_resolution_marks_resolved_at_on_subsequent_store` | FAIL | PASS |
| 9 | `test_collect_clarify_notifications_reads_sidecar` | FAIL | PASS |
| 10 | `test_multiple_pending_entries_reflected_in_summary` | FAIL | PASS |
| 11 | `test_clarify_sidecar_structure_for_mac_notifier` | FAIL | PASS |
| 12 | `test_stored_true_does_not_touch_clarifying_infrastructure` | PASS | PASS (pre-existing) |
| 13 | `test_stored_true_still_writes_activity_log` | PASS | PASS (pre-existing) |
| D1 | `test_v05_version_badge` | FAIL | PASS |
| D2 | `test_v05_shape_row_clarifying_question` | FAIL | PASS |
| D3 | `test_v05_shape_row_clarifying_question_truncates_long_question` | FAIL | PASS |
| D4 | `test_v05_dashboard_data_clarify_row_shape` | FAIL | PASS |
| D5 | `test_v05_non_clarifying_rows_are_unaffected` | FAIL | PASS |
| D6 | `test_v05_shape_row_clarifying_expand_fields` | FAIL | PASS |
| D7 | `test_v05_regression_existing_rows_still_pass` | FAIL | PASS |
| D8 | `test_v05_full_pipeline_clarify_row_in_dashboard` | FAIL | PASS |

**Total: 274 tests passing, 0 failures.**

---

## How It Works

### Immediate notification (Herman → mac_notifier, no new code in mac_notifier)

When `dispatch()` detects `stored=False` + `clarifying_question`:

1. Writes `vault/_reminders/clarify.<record_id>.json` — a sidecar with `kind="clarify_immediate"`, `fire_at=now`, `body="Homunculus needs input: <question> (memo about '<excerpt>')"`.
2. Appends a row to `vault/_reminders/_clarifying_pending.jsonl` with `resolved_at=null`.
3. Writes an activity log entry to `_activity.jsonl` so the dashboard shows the row.
4. Returns the response unchanged (wire contract preserved).

mac_notifier polls `/reminders/upcoming` every ~90 s. `collect_upcoming_rows()` now calls `_collect_clarify_notifications()` which reads `clarify.*.json` sidecars and returns `ReminderRow(kind=CLARIFY_IMMEDIATE)`. mac_notifier fires it within one polling cycle.

### Daily morning summary

`build_daily_summary_rows()` reads `read_unresolved_clarifying()` once per call. When the count is non-zero, `_compose_summary_body()` appends: `"You have N pending clarifications. Check the Herman dashboard."` — included in every day's morning summary body until entries are resolved.

### Resolution heuristic

On every `stored=True` dispatch, `_resolve_clarifying_pending()` scans the JSONL for entries with matching `(verb, subject.strip().lower(), captured_at.isoformat())`. This covers the common user path: re-record the same memo with `"at 9 AM"` instead of `"at nine"` — same verb, same subject, same mtime → pending entry gets `resolved_at` stamped.

A `# TODO(v2.3)` comment marks where precise match replaces the heuristic once the reply verb carries the original clarifying `record_id`.

### Dashboard v0.5

`_shape_row()` calls `_is_clarifying_row()`: checks `details.stored is False` and `details.clarifying_question` non-empty. Clarifying rows get:
- `icon = "⚠️❓"`
- `summary = "Awaiting clarification — <question truncated to 60 chars>"`
- `is_clarifying = True`
- `clarifying_question = <full question>` (for expand panel)
- CSS class `.row.clarify`: warning-amber background (`#fffbeb`), amber left border, amber text on summary.

---

## Migration Steps

```
# 1. Bounce Herman
launchctl unload ~/Library/LaunchAgents/com.homunculus.brain.plist
launchctl load  ~/Library/LaunchAgents/com.homunculus.brain.plist

# 2. Hard-refresh the dashboard tab
# ⌘⇧R in the browser tab showing http://100.x.x.x:8765/dashboard/
# Confirm version badge shows "v0.5" in the upper-left corner.

# 3. Test with a deliberately ambiguous memo
# Say or POST: "Remind me to call the vet at nine on Friday"
# (verb=schedule or handle, time_hint="nine" → genuinely ambiguous)
# Expected within ~60 s: Mac notification:
#   "Homunculus needs input: Did you mean AM or PM? (memo about 'call the vet at nine')"

# 4. Check the dashboard
# The row appears in warning amber at the top of the feed.
# Click to expand → see full question + transcript.

# 5. To test the daily summary path immediately (without waiting 24h):
# Temporarily set HOMUNCULUS_MORNING_ANCHOR to the current hour + 1
# in the launchd plist, reload, and call /reminders/upcoming?window_hours=72.
# The next morning_summary body will include "You have 1 pending clarification."
```

---

## Deliberate Deferrals

**Phone-side notification** — waiting on Kit's iOS client. The `/reminders/upcoming` row is already correctly shaped (`kind=clarify_immediate`); when Kit implements the client, it will just fire. No Herman changes needed at that point.

**Reply-to-clarify verb** (v2.3+) — a future `verb=reply` that carries the original `clarifying_record_id` in the payload. When it ships, `_resolve_clarifying_pending()` switches to precise record_id matching instead of the current `(verb, subject, captured_at)` heuristic.

**Per-user snooze** — single-user assumption for now. If Thomas wants to snooze a specific question, that's a v2.3 UI element.

**Dashboard filter by clarifying vs normal** — v0.6 candidate. Currently clarifying rows are visually distinct in the feed but not filterable.

**Sound customization** — deferred. Mac notification uses system default sound.

---

## Follow-up Considerations

- **What constitutes "resolved"** — today: same `(verb, subject, captured_at)` triple on a successful store. Precise when the reply verb ships. Edge cases: if Thomas manually edits the subject text between recordings, the heuristic will miss. Acceptable for v2.2.
- **Accumulation without resolution** — the daily summary will keep mentioning pending clarifications indefinitely if Thomas ignores them. Consider adding a "stale after N days" mark in a future version.
- **Per-notification escalation** — the spec says one-shot + daily summary. No middle-ground buzzing. If Thomas wants escalation after 48h, that's a v2.3 config knob.
- **`_clarifying_pending.jsonl` growth** — purely append-only today (resolved rows stay in file with `resolved_at` stamped). At ~1 clarification per day the file stays tiny forever. Rotation is a future concern.
