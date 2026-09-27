# Timer Row Buttons — Herman v2.4.0

**v2.4.0** · Rune · 2026-09-27

---

## Endpoint List

### `POST /timer/start`
Already existed. Dashboard buttons call it with `{"project": "<name>", "captured_at": "<iso>"}`.
- 200 `{"stored": true, "project": ..., "slug": ..., "started_at": ..., "record_id": ...}`
- Idempotent: double-start returns original `started_at`, no error.

### `POST /timer/stop`
Already existed. Dashboard buttons call it with `{"project": "<name>", "captured_at": "<iso>"}`.
- 200 `{"stored": true, "duration_seconds": ..., "total_seconds": ..., ...}`
- 400 `{"stored": false, "error": "No running timer for..."}` when not running.
- Dashboard button is disabled when timer is not running.

### `POST /timer/delete`  ← new in v2.4.0
- Request body: `{"project": "<name>"}`
- 200 `{"deleted": true}` — file was removed.
- 200 `{"deleted": false}` — no file existed (idempotent no-op).
- If the timer was running, it is silently stopped first (audit log preserved, no notification sidecar).
- No confirmation token required server-side. Browser `confirm()` dialog handles "are you sure."

---

## Template Diff

**`homunculus_brain/dashboard.py`** — two change areas:

1. **CSS additions** (after `.timer-running-badge`): `.timer-actions`, `.tbtn`, `.tbtn-start`, `.tbtn-stop`, `.tbtn-delete` — flex row of three small colored buttons per row.

2. **JS additions / replacements**:
   - New helper `timerAction(endpoint, project)` — POSTs to the endpoint (includes `captured_at` for start/stop), then calls `fetchTimers()` to refresh both panels.
   - New helper `timerBtns(project, isRunning)` — returns the three-button HTML fragment with correct `disabled` state.
   - `renderRunning`: each row now appends `${timerBtns(r.project, true)}` — Stop enabled, Start disabled.
   - `renderTotals`: each row now appends `${timerBtns(t.project, t.is_running)}` — state derived from `is_running`.

**`homunculus_brain/schemas.py`** — added `TimerDeleteRequest` and `TimerDeleteResponse` Pydantic models.

**`homunculus_brain/server.py`** — added `POST /timer/delete` endpoint (after `/timer/reset`); imported the two new schema classes.

**`homunculus_brain/__init__.py`** — `VERSION` 2.3.0 → 2.4.0, `DESIGN_VERSION` 2.3 → 2.4.

**`homunculus_brain/dashboard.py`** — `DASHBOARD_VERSION` v0.5 → v0.6.

---

## Button Visibility State Matrix

| Timer state | Start button | Stop button | Delete button |
|---|---|---|---|
| Running | `disabled` | enabled | enabled (confirm dialog) |
| Stopped / idle | enabled | `disabled` | enabled (confirm dialog) |

State is derived from `is_running` in the `/dashboard/timers` API response at render time. The dashboard auto-refreshes every 5 s, so a timer started via voice will reflect its state in the UI within the next poll cycle.

---

## Red → Green Table

| # | Test | RED reason | GREEN after |
|---|---|---|---|
| T1a | `test_dashboard_timer_start_endpoint_via_form_post` | (passed already — endpoint existed) | — |
| T1b | `test_dashboard_timer_start_idempotent_double_post` | (passed already) | — |
| T2a | `test_dashboard_timer_stop_endpoint_via_form_post` | (passed already) | — |
| T2b | `test_dashboard_timer_stop_idempotent_not_running` | (passed already) | — |
| T2c | `test_dashboard_timer_stop_nonexistent_project_does_not_500` | (passed already) | — |
| T3a | `test_timer_delete_removes_file` | 404 — endpoint missing | Added `POST /timer/delete` |
| T3b | `test_timer_delete_nonexistent_project_is_noop` | 404 | Added endpoint |
| T3c | `test_timer_delete_running_timer_stops_first` | 404 | Added endpoint |
| T3d | `test_timer_delete_writes_activity_log` | endpoint missing, no log row | Added endpoint |
| T3e | `test_timer_delete_removed_project_not_in_totals` | file not deleted | Added endpoint |
| T4a | `test_dashboard_html_contains_timer_button_names` | HTML had no "Stop"/"Delete" | Added buttons to `renderRunning` / `renderTotals` |
| T4b | `test_dashboard_html_uses_post_forms_for_timer_actions` | no `/timer/start` in HTML | Added `timerAction` helper referencing all three endpoints |
| T5a | `test_dashboard_timers_api_running_flag` | (passed already) | — |
| T5b | `test_dashboard_timers_api_stopped_flag` | (passed already) | — |
| T6 | `test_timer_delete_no_confirm_required_server_side` | 404 | Added endpoint (no confirm token needed) |
| T7 | `test_dashboard_version_is_v06` | version was v0.5 | Bumped `DASHBOARD_VERSION` to v0.6 |
| T8 | `test_herman_version_is_240` | version was 2.3.0 | Bumped `VERSION` to 2.4.0 |

**Full suite result: 303 passed, 3 pre-existing failures (timer stop notification tests — unrelated to this feature).**

---

## Manual Verify for Thomas

1. Open `http://localhost:8765/dashboard/` in a browser.
2. In the **Project Totals** section you should see the Golf Timer row with three buttons: **Start** (green), **Stop** (amber, disabled because golf is currently running), **Delete** (red).
3. In the **Running Timers** section the Golf Timer row shows **Start** (disabled), **Stop** (enabled), **Delete**.
4. Click **Stop** on the Golf Timer row → the timer stops, the row moves from Running to Totals, Stop becomes disabled, Start becomes enabled. Both panels refresh within 5 s automatically.
5. Click **Start** on the (now stopped) Golf Timer row → it moves back to Running.
6. Click **Delete** on any non-Golf timer row → browser shows: "Delete timer '<project>'? This cannot be undone." → OK → row disappears from both panels on next refresh.
7. If Herman is running as launchd, the changes are on disk — restart to pick up the new code: `launchctl stop com.homunculus.brain && launchctl start com.homunculus.brain` (or `sudo launchctl kickstart -k gui/$(id -u)/com.homunculus.brain`).

---

## Files Changed

- `/Volumes/GIT/CLAUDE/SHARED_WORK_FOLDER/Homunculus/brain/homunculus_brain/__init__.py`
- `/Volumes/GIT/CLAUDE/SHARED_WORK_FOLDER/Homunculus/brain/homunculus_brain/schemas.py`
- `/Volumes/GIT/CLAUDE/SHARED_WORK_FOLDER/Homunculus/brain/homunculus_brain/server.py`
- `/Volumes/GIT/CLAUDE/SHARED_WORK_FOLDER/Homunculus/brain/homunculus_brain/dashboard.py`
- `/Volumes/GIT/CLAUDE/SHARED_WORK_FOLDER/Homunculus/brain/tests/test_timer_row_buttons.py` (new)
- `/Volumes/GIT/CLAUDE/SHARED_WORK_FOLDER/Homunculus/brain/tests/test_dashboard.py` (version badge assertions updated)
- `/Volumes/GIT/CLAUDE/SHARED_WORK_FOLDER/Homunculus/brain/tests/test_timers_routes.py` (version badge assertion updated)
