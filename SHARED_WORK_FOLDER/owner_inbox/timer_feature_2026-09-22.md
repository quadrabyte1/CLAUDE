# Timer Feature Handoff
## Sprite v0.9.0 · Herman v2.0.0 · Dashboard v0.2
### 2026-09-22 — Rune

---

## Feature Summary

Thomas can now say "start gym" to begin a stopwatch and "stop gym" to end it. On stop, a macOS notification fires (via the existing mac_notifier 90-second polling grace window) announcing the elapsed time and all-time cumulative total. Running timers and project totals appear in a dedicated **Timers panel** above the activity feed on the dashboard, with elapsed times updating every second client-side.

**Design decisions Thomas locked in:**
- Feed placement: timer events appear in BOTH the main activity feed AND the new Timers panel above it
- Total scope: all-time cumulative (per-period rollups deferred to v1.1)

---

## Storage Schema

One file per project: `vault/timers/<slug>.json`

```json
{
  "project": "gym",
  "slug": "gym",
  "running": {
    "started_at": "2026-09-22T10:30:00-04:00",
    "record_id": "uuid-here"
  },
  "sessions": [
    {
      "started_at": "2026-09-22T10:30:00-04:00",
      "ended_at": "2026-09-22T11:17:32-04:00",
      "duration_seconds": 2832,
      "record_id": "uuid-here"
    }
  ],
  "total_seconds": 2832,
  "last_touched_at": "2026-09-22T11:17:32-04:00"
}
```

---

## Files Changed

### Sprite v0.9.0
| File | Change |
|---|---|
| `Sprite/pyproject.toml` | Version 0.8.1 → 0.9.0 |
| `Sprite/src/sprite/parse.py` | Added `start_timer`/`stop_timer` to verb enum; added `project` field to schema; added 7 new few-shot examples; `ParseResult.project` field; `ParsedIntent` alias |
| `Sprite/src/sprite/herman.py` | `build_request()` accepts and forwards `project` parameter |
| `Sprite/src/sprite/watcher.py` | Passes `parse_result.project` to `build_request()`; version log bump |

### Herman v2.0.0
| File | Change |
|---|---|
| `Homunculus/brain/pyproject.toml` | Version 1.9.0 → 2.0.0 |
| `Homunculus/brain/homunculus_brain/__init__.py` | VERSION/DESIGN_VERSION → 2.0.0/2.0 |
| `Homunculus/brain/homunculus_brain/timers.py` | **New module** — `TimerManager`, `NoRunningTimer`, `format_duration`, `_normalize_project`, all timer state logic |
| `Homunculus/brain/homunculus_brain/schemas.py` | Added `CaptureVerb.START_TIMER`/`STOP_TIMER`; `ReminderKind.TIMER_STOP`; `TimerStartRequest/Response`; `TimerStopRequest/Response`; `RunningTimer`; `ProjectTotal`; `project` + `speaker_tz` fields on `ParsedCaptureRequest` |
| `Homunculus/brain/homunculus_brain/capture_parsed.py` | Routes timer verbs; `_handle_start_timer`; `_handle_stop_timer`; timer verbs bypass the idempotency log |
| `Homunculus/brain/homunculus_brain/reminders.py` | Added `import json`; `_collect_timer_notifications()`; calls it in `collect_upcoming_rows()` |
| `Homunculus/brain/homunculus_brain/server.py` | New routes: `POST /timer/start`, `POST /timer/stop`, `GET /timers/running`, `GET /timers/totals`, `GET /dashboard/timers` |
| `Homunculus/brain/homunculus_brain/dashboard.py` | v0.1 → v0.2; `timer_start`/`timer_stop` icons; `_summary_for` handles timer kinds; `_short_duration` helper; Timers panel HTML; JavaScript for polling + 1-sec tick |

### New Test Files
| File | Tests |
|---|---|
| `Sprite/tests/test_timers.py` | 15 tests covering parse, schema, prompt, `build_request`, disambiguation, wire shape |
| `Homunculus/brain/tests/test_timers.py` | 27 tests covering `TimerManager`, slugification, `format_duration`, activity log |
| `Homunculus/brain/tests/test_timers_routes.py` | 20 tests covering HTTP routes, capture_parsed dispatch, notifications, dashboard |

---

## Red → Green Table

| Component | Baseline | After | New Tests | Regressions |
|---|---|---|---|---|
| Sprite | 155 passed | 170 passed | +15 | 0 |
| Herman | 169 passed | 216 passed | +47 | 0 |
| **Total** | **324** | **386** | **+62** | **0** |

All 62 new tests were written RED before implementation and turned GREEN after.

---

## Migration Steps

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
3. **Open dashboard:** http://localhost:8765/dashboard/ — Timers panel visible at top (version badge shows v0.2)
4. **Test:** Record "Start gym" → watch running timer appear on dashboard. Record "Stop gym" → see notification fire within ~60 seconds, total updated, feed shows timer_start and timer_stop rows.

No vault migration needed. The `vault/timers/` directory is created on first use.

---

## Non-Obvious Behaviors

**Article-strip normalization:** "the gym" and "gym" resolve to the same file `vault/timers/gym.json`. Specifically, leading articles "the", "a", "an" are stripped before slugification. So all of these target the same timer:
- "Start gym"
- "Start the gym"
- "Start Gym"
- "Start The Gym"

**Idempotent start:** Saying "start gym" twice (e.g. duplicate voice memo) does NOT reset the stopwatch. The original `started_at` is preserved and a warning is logged. The second call returns the same `started_at` as the first.

**Immediate notification via 90-second grace window:** On stop, Herman writes a `_reminders/timer.<slug>.<uuid>.json` sidecar with `fire_at = now`. The mac_notifier polls `/reminders/upcoming?include_fired=true` on its 90-second cycle and delivers it within that window. This is reliable delivery with up to 90 seconds of latency — deliberate, per your memory: "Reliability > speed."

**Stop with no running timer:** Returns a 400 error (or `stored=False` via `/capture/parsed`) with a human-readable message: "No running timer for 'gym'. Say 'start gym' first."

**Timer verbs bypass the capture_parsed idempotency log:** Normal verbs (schedule, note, handle, etc.) have a short-circuit: POSTing the identical payload twice returns the same record without touching the vault. Timer verbs are excluded from this — every call routes to `TimerManager` which has its own idempotency semantics (idempotent start, stateful stop).

**Dashboard 1-second tick:** The JavaScript timer panel updates running elapsed times every second using a `setInterval` without making any server requests. The server is polled every 5 seconds (same cadence as the activity feed) to update started_at times and catch new/stopped timers.

---

## New Endpoints

| Method | Path | Description |
|---|---|---|
| `POST` | `/timer/start` | Start a named stopwatch |
| `POST` | `/timer/stop` | Stop a running stopwatch, get duration + total |
| `GET` | `/timers/running` | List all running timers with elapsed_seconds |
| `GET` | `/timers/totals` | List all project totals sorted by last-touched |
| `GET` | `/dashboard/timers` | Combined running+totals for the dashboard panel |

Sprite also routes `verb=start_timer` and `verb=stop_timer` through `POST /capture/parsed` (the existing Sprite entry point) — so no Sprite-side changes are needed after the initial version bump.

---

## Follow-up Considerations for v1.1

- **Per-week / per-month rollups:** total_seconds is always all-time; v1.1 can add `weekly_seconds`, `monthly_seconds` computed from session timestamps.
- **Pause / resume:** `verb=pause_timer` would add a "paused" state between running and stopped.
- **Manual duration entry:** "I worked on the deck for 2 hours" — parse a duration from utterance and add it directly to total_seconds without a start/stop pair.
- **Export / report:** "How much time did I spend on the deck this week?" — summarize sessions from the JSON files.
- **Cross-project totals:** Tag-based aggregation (e.g., all "billable" projects).
