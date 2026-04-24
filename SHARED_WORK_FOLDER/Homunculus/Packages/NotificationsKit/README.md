# NotificationsKit

**Owner:** Mori. **Milestone:** M3.

## Responsibility

Thin wrapper around `UNUserNotificationCenter` with all of v1's policy baked in.

- Registers the `HOMUNCULUS_EVENT` category with a single `ACK` action on startup.
- Sets the `UNUserNotificationCenterDelegate` inside `didFinishLaunchingWithOptions`
  (cold-launch-from-tap responses drop silently otherwise).
- Builds `UNCalendarNotificationTrigger`s from `DateComponents` with an explicit
  `TimeZone` set to the event's zone — never a time-interval trigger.
- Uses deterministic identifiers: `ev.<uuid>.strike.<n>`, `ev.<uuid>.headsup30`,
  `ev.<uuid>.pre5`, `summary.<yyyy-mm-dd>`.
- Interruption levels: `.timeSensitive` on strikes + pre_5; `.active` on morning summary
  and heads_up_30. No Critical Alerts.
- Routes ACK taps to `Scheduling` so remaining strikes can be cancelled and the reconciler
  can top up.

## Boundary

- **Consumes:** `CalendarCore` (reminder IDs, event titles for body copy, TZ identifiers).
- **Does not consume:** VoiceCapture, NLU, Scheduling (one-way — Scheduling calls in).
- **Is consumed by:** AppShell (delegate setup), Scheduling (scheduler fan-out).

## Non-goals

- Does not decide what to schedule — `Scheduling` owns that.
- Does not compose morning-summary body text (that's a DB query at reconcile time,
  delivered in via the caller).
- Does not know about voice or NLP.
