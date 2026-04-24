# Scheduling

**Owner:** Mori. **Milestone:** M3 (the hard one).

## Responsibility

The rolling scheduler and reconciler that sit between `CalendarCore`'s `reminders` table
and `NotificationsKit`'s UN wrapper. Owns the reliability contract.

- Target pending depth: 60 (headroom of 4 on Apple's 64 ceiling).
- Horizon: next 72 hours. Anything further out stays `status='pending'` in DB.
- Runs on: cold launch, foreground, after any event mutation, after any fire, after any
  ack, on `NSSystemTimeZoneDidChangeNotification`, on significant time change.
- Per-event fan-out: 7 reminder rows (morning_summary, heads_up_30, pre_5, strike_0/5/10/15).
- Deterministic UN identifiers: `ev.<uuid>.strike.<n>`, `ev.<uuid>.headsup30`, etc.
- Missed-event detection: strike_15 unacked + grace → `missed_events` insert.

## Boundary

- **Consumes:** `CalendarCore` (reminders table, events state), `NotificationsKit`
  (the UN interface).
- **Does not consume:** VoiceCapture, NLU, AppShell.
- **Is consumed by:** AppShell (on mutations), `NotificationsKit` delegate (on ack).

## Non-goals

- Does not touch the UN center directly — that's `NotificationsKit`.
- Does not know about voice, NLP, or views.
- Does not compose notification body copy — that's `NotificationsKit` (static) or the
  morning-summary composer (live DB query at reconcile time).
