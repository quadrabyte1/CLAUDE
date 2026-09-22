# Timer v1.1 — stop_all_timers + reset_timer

**Sprite v0.10.0 · Herman v2.1.0 · Dashboard v0.3**
Delivered 2026-09-22 by Rune

---

## Root cause / user need

Thomas built up multiple running timers during the day (Amunculus, golf) and surfaced two gaps in real use:

1. **End-of-day sweep** — saying "stop X" five times is friction. One utterance should shut everything down.
2. **Clear accumulator** — after a billing period or a mistake, the user needs to zero a project's running total without losing the project entry itself (so the next `start gym` just works).

---

## Design: two new verbs

### `stop_all_timers` — no project field

Utterances that map to it:
- "Stop all timers"
- "Stop everything"
- "Stop all"

Herman behavior:
- Calls `TimerManager.stop_all()` — iterates all running timers, stops each one.
- Returns `stored=True, stopped=[...]` where each entry is a `TimerStopResult`-shaped dict.
- Returns `stopped=[]` (empty list) when nothing is running — still `stored=True`, silent success. No error. This differs from `stop_timer` which errors on a missing project because `stop_all` has no scope.
- Each individual stop fires its own notification sidecar (polled by mac_notifier within ~90 sec). No batching.
- Each stop writes its own `timer_stop` row to `_activity.jsonl` so the audit trail shows all stopped projects.

### `reset_timer` — requires `project`

Utterances that map to it:
- "Reset gym"
- "Clear gym timer"
- "Start gym over"
- "Zero out gym"

Herman behavior:
1. If the target timer is currently running: **silent stop** (no notification sidecar, audit trail `timer_stop` row with `silent: true` in details).
2. Record `cleared_seconds` (the pre-reset total) and `cleared_session_count`.
3. Set `total_seconds = 0`, `sessions = []`. File is NOT deleted — the project stays visible.
4. Update `last_touched_at = now`.
5. Write a `timer_reset` activity log row with `cleared_seconds` so the dashboard feed shows what was wiped.
6. Returns `stored=True, cleared_seconds=<old_total>, cleared_session_count=<n>`.
7. If the project does not exist: `stored=False, clarifying_question="No timer for '<project>'. Say 'start <project>' first to begin tracking."`

---

## Files changed

### Herman v2.1.0

| File | Change |
|---|---|
| `homunculus_brain/__init__.py` | VERSION 2.0.0 → 2.1.0, DESIGN_VERSION 2.0 → 2.1 |
| `homunculus_brain/schemas.py` | Added `STOP_ALL_TIMERS` and `RESET_TIMER` to `CaptureVerb` enum; added `TimerStopAllRequest`, `TimerStopAllResponse`, `TimerResetRequest`, `TimerResetResponse` |
| `homunculus_brain/timers.py` | Added `NoSuchTimer` exception, `TimerResetResult` dataclass, `TimerManager.stop_all()`, `TimerManager.reset()`, `TimerManager._silent_stop()` |
| `homunculus_brain/capture_parsed.py` | Extended `is_timer_verb` set; added `_handle_stop_all_timers()`, `_handle_reset_timer()` handlers; routed them in `dispatch()` |
| `homunculus_brain/server.py` | Added `POST /timer/stop_all` and `POST /timer/reset` routes; imported new schemas |
| `homunculus_brain/dashboard.py` | Added `timer_reset` to `_VERB_ICONS`; added `timer_reset` branch in `_summary_for()` → "Reset: gym — cleared 4h 12m" format; bumped DASHBOARD_VERSION v0.2 → v0.3 |
| `pyproject.toml` | version 2.0.0 → 2.1.0 |

### Sprite v0.10.0

| File | Change |
|---|---|
| `sprite/parse.py` | Added `stop_all_timers` and `reset_timer` to `_INTENT_JSON_SCHEMA` verb enum; expanded verb description with disambiguation rules; added 8 new few-shot examples in `_SYSTEM_PROMPT`; bumped `ParseResult.verb` docstring |
| `sprite/watcher.py` | Startup log string 0.9.0 → 0.10.0 |
| `pyproject.toml` | version 0.9.0 → 0.10.0 |

---

## Red → Green table

| # | Test | Status |
|---|---|---|
| 1 | `test_stop_all_timers_verb_parsed_from_mock` | RED → GREEN |
| 2 | `test_stop_all_timers_stop_everything_variant` | RED → GREEN |
| 3 | `test_stop_all_timers_stop_all_variant` | RED → GREEN |
| 4 | `test_reset_timer_verb_parsed_from_mock` | RED → GREEN |
| 5 | `test_reset_timer_clear_variant` | RED → GREEN |
| 6 | `test_schema_enum_contains_stop_all_timers` | RED → GREEN |
| 7 | `test_schema_enum_contains_reset_timer` | RED → GREEN |
| 8 | `test_system_prompt_has_stop_all_timers_example` | RED → GREEN |
| 9 | `test_system_prompt_has_reset_timer_example` | RED → GREEN |
| 10 | `test_stop_gym_stays_stop_timer_not_stop_all` | GREEN (mock already passes) |
| 11 | `test_stop_all_empty_returns_empty_list` | RED → GREEN |
| 12 | `test_stop_all_empty_no_files_created` | RED → GREEN |
| 13 | `test_stop_all_stops_all_running_timers` | RED → GREEN |
| 14 | `test_stop_all_files_show_running_none` | RED → GREEN |
| 15 | `test_stop_all_each_result_is_timer_stop_result` | RED → GREEN |
| 16 | `test_reset_nonrunning_clears_sessions_and_total` | RED → GREEN |
| 17 | `test_reset_nonrunning_clears_seconds_matches_old_total` | RED → GREEN |
| 18 | `test_reset_running_stops_first_then_resets` | RED → GREEN |
| 19 | `test_reset_nonexistent_project_returns_stored_false` | RED → GREEN |
| 20 | `test_reset_idempotent_second_call` | RED → GREEN |
| 21 | `test_reset_preserves_project_file` | RED → GREEN |
| 22 | `test_reset_silent_stop_no_notification_sidecar` | RED → GREEN |
| 23 | `test_stop_all_writes_timer_stop_activity_per_project` | RED → GREEN |
| 24 | `test_reset_writes_timer_reset_activity_row` | RED → GREEN |
| 25 | `test_reset_running_writes_timer_stop_activity_row` | RED → GREEN |
| 26 | `test_stop_all_fires_individual_notifications` | RED → GREEN |
| 27 | `test_timer_stop_all_returns_200_empty` | RED → GREEN |
| 28 | `test_timer_stop_all_returns_stopped_list` | RED → GREEN |
| 29 | `test_timer_reset_valid_project_returns_200` | RED → GREEN |
| 30 | `test_timer_reset_zeros_totals` | RED → GREEN |
| 31 | `test_timer_reset_unknown_project_returns_stored_false` | RED → GREEN |
| 32 | `test_capture_parsed_stop_all_timers_dispatches` | RED → GREEN |
| 33 | `test_capture_parsed_reset_timer_dispatches` | RED → GREEN |
| 34 | `test_stop_all_activity_log_has_stop_per_project` | RED → GREEN |
| 35 | `test_reset_activity_log_has_timer_reset_row` | RED → GREEN |
| 36 | `test_stop_all_enqueues_individual_notifications` | RED → GREEN |
| 37 | `test_reset_does_not_enqueue_notification` | RED → GREEN |
| 38 | `test_dashboard_data_after_reset_shows_timer_reset_row` | RED → GREEN |
| 39 | `test_dashboard_reset_row_summary_format` | RED → GREEN |
| 40 | `test_dashboard_data_after_stop_all_shows_stop_rows` | RED → GREEN |
| 41 | `test_dashboard_version_badge_v03` | RED → GREEN |
| — | **Regression: all 216 prior Herman tests** | STILL GREEN |
| — | **Regression: all 170 prior Sprite tests** | STILL GREEN |

**Final count:** 247 Herman tests (216 + 31), 180 Sprite tests (170 + 10). All passing.

---

## Migration steps

1. **Bounce Herman:**
   ```
   launchctl unload ~/Library/LaunchAgents/com.homunculus.brain.plist
   launchctl load  ~/Library/LaunchAgents/com.homunculus.brain.plist
   ```
2. **Bounce Sprite:**
   ```
   launchctl unload ~/Library/LaunchAgents/com.sprite.watcher.plist
   launchctl load  ~/Library/LaunchAgents/com.sprite.watcher.plist
   ```
3. **Hard-refresh the dashboard tab** (⌘⇧R) — pick up v0.3 badge.
4. **Test:**
   - Start a few timers, then say "Stop all timers" — all should stop, individual notifications fire ~60–90 sec later.
   - Say "Reset gym" — gym total zeros out, dashboard feed shows "Reset: gym — cleared Xh Ym".

---

## Dashboard feed format

| kind | Feed summary |
|---|---|
| `timer_reset` | `⏱ Reset: gym — cleared 4h 12m` |
| `timer_stop` (from stop_all) | `⏱ Stopped: gym — 30m 0s (total 1h 45m)` — one row per project |

stop_all does not produce a combined "Stopped 3 timers" batch row. Each project appears as its own `timer_stop` feed entry. This is intentional — cleaner, and each row carries the project's elapsed session time.

---

## Deliberate non-goal: `reset_all_timers`

Skipped for MVP. Resetting every project at once is irreversible and has no undo mechanism. If Thomas wants this in v1.2, an undo-window or archive path should be designed first.

---

## Follow-up considerations (v1.2 candidates)

- **Undo window for reset** — write pre-reset data to `vault/timers/_archive/<slug>_<date>.json` before zeroing; surface via `undo reset gym` verb.
- **Batch stop notification** — a single "Stopped 3 timers: gym (45m), deck (1h 12m), amunculus (22m)" in place of 3 individual pings.
- **Session-history archival** — reset currently clears `sessions` entirely; archiving them enables per-week / per-month rollups.
- **`reset_all_timers`** — global reset, only safe once an undo/archive path exists.
