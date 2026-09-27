# v2.4.1 — Timer Stop Notification Fix

**v2.4.1** · Rune · 2026-09-27

## What was broken

Three tests were failing with `Expected >=2 timer_stop notification rows, got 0`:

- `test_timer_stop_enqueues_notification`
- `test_timer_stop_notification_body_format`
- `test_stop_all_enqueues_individual_notifications`

## Root cause

`_collect_timer_notifications()` in `reminders.py` applied a time-window filter
when `include_fired=True`:

```python
in_window = (events_from <= fire_at <= window_end) if include_fired else True
```

The `events_from` anchor is `datetime.now() - 24h` (real wall-clock time).
Tests use a fixed past date (`NOW = 2026-09-22`) for all timer operations.
The resulting `fire_at` (Sept 22 ~11:00 AM) sat 5 days before the 24 h lookback
window (anchored to Sept 27), so the sidecars were written correctly but
never returned by `/reminders/upcoming`.

The delete path (`delete_timer` / `_silent_stop`) was unaffected — it correctly
never calls `_enqueue_stop_notification`.

## Fix

`Homunculus/brain/homunculus_brain/reminders.py` — `_collect_timer_notifications()`:

When `include_fired=True`, skip the window filter entirely. The flag's intent is
"return everything regardless of timing and status" (test-client affordance).
For the normal phone path (`include_fired=False`), keep the window filter so
only recent timer-stop notifications are returned.

## Verified

```
306 passed in 1.42s
```

All 3 previously-failing tests now green. No regressions. Delete path still does
not enqueue notifications (`test_reset_does_not_enqueue_notification` passes).

## Files changed

- `Homunculus/brain/homunculus_brain/reminders.py` — fixed window filter logic
- `Homunculus/brain/homunculus_brain/__init__.py` — VERSION 2.4.0 → 2.4.1
