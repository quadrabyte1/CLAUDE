# Herman Timer Deletion — v1.0
> 2026-09-27 · Rune

---

## Where timers are stored

**Storage layer:** One JSON file per project under `vault/timers/<slug>.json`.

Schema per file:
```json
{
  "project": "golf",
  "slug": "golf",
  "running": null,
  "sessions": [ { "started_at": "...", "ended_at": "...", "duration_seconds": N, "record_id": "..." } ],
  "total_seconds": N,
  "last_touched_at": "..."
}
```

The dashboard reads these files via `TimerManager.get_totals()` and `get_running()`. No SQLite — pure markdown-adjacent JSONL discipline.

---

## What was deleted

| Project name | Slug | File | Sessions | Total time |
|---|---|---|---|---|
| golf | `golf` | `vault/timers/golf.json` | 2 sessions | 1h 4m 21s (3861s) |
| Amunculus (= "homunculus", Wispr mishearing) | `amunculus` | `vault/timers/amunculus.json` | 1 session | 13m 5s (785s) |

Neither was running at time of deletion (both had `running: null`).

The third timer `Golf Timer` (slug `golf-timer`, currently running) was **not touched** — that is a distinct project.

---

## Archive

Before deletion, both files were copied to:

```
vault/timers/_deleted_2026-09-27/golf.json
vault/timers/_deleted_2026-09-27/amunculus.json
```

These are the full original JSON blobs including all session history.

---

## What changed in code

### New method: `TimerManager.delete_timer(project: str) -> bool`

Added to `/Volumes/GIT/CLAUDE/SHARED_WORK_FOLDER/Homunculus/brain/homunculus_brain/timers.py`.

Behavior:
- Resolves slug via the same article-strip + slugify pipeline as all other methods (case-insensitive).
- If the timer is currently running, silent-stops it first (audit row written, no mac_notifier sidecar).
- Unlinks the file. Idempotent: calling again is a no-op.
- Writes a `timer_delete` activity log row.
- Returns `True` if a file was removed, `False` if no file existed.

### VERSION bump

`homunculus_brain/__init__.py`: `2.2.0` → `2.3.0` / `DESIGN_VERSION` `2.2` → `2.3`.

---

## TDD — RED → GREEN

6 new tests added to `Homunculus/brain/tests/test_timers.py` under the `v2.3.0 TDD — delete_timer` block:

| Test | Covers |
|---|---|
| `test_delete_removes_timer_file` | File is unlinked from disk |
| `test_delete_after_deletion_not_in_totals` | Deleted project absent from `get_totals()`; others intact |
| `test_delete_nonexistent_is_noop` | Unknown project → no exception |
| `test_delete_case_insensitive` | `"Golf"` resolves to slug `golf` and deletes correctly |
| `test_delete_stops_running_timer_first` | Running timer gets silent-stopped then file removed |
| `test_delete_multiple_projects_leaves_others_intact` | Deleting golf + homunculus leaves "other" untouched |

Before implementation: **6 FAILED** (`AttributeError: 'TimerManager' has no attribute 'delete_timer'`).  
After implementation: **49 passed** (43 pre-existing + 6 new).

---

## Dashboard verification

**Before deletion** (`GET /dashboard/timers`):
```json
{
  "running": [{"project": "Golf Timer", ...}],
  "totals": [
    {"project": "Golf Timer", "slug": "golf-timer", ...},
    {"project": "golf",       "slug": "golf",       "total_seconds": 3861,  ...},
    {"project": "Amunculus",  "slug": "amunculus",  "total_seconds": 785,   ...}
  ]
}
```

**After deletion** (`GET /dashboard/timers`):
```json
{
  "running": [{"project": "Golf Timer", "slug": "golf-timer", ...}],
  "totals": [
    {"project": "Golf Timer", "slug": "golf-timer", "total_seconds": 2370, "is_running": true}
  ]
}
```

"golf" and "Amunculus" are gone. "Golf Timer" is untouched.

---

## Notes on residual _reminders sidecars

Four old timer-stop notification sidecars remain in `vault/_reminders/`:
- `timer.golf.d179674d-....json`
- `timer.golf.5e623e3a-....json`
- `timer.amunculus.d7025cfd-....json`
- `timer.golf-timer.697c3045-....json`

These are historical — their `fire_at` timestamps are days old and will never trigger a new notification. They do not appear on the dashboard. Per the task brief ("no need to rewrite history"), they are left in place as the audit trail.
