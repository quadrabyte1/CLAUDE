# AppShell

**Owner:** Kit. **Milestone:** M1 onward.

## Responsibility

The SwiftUI app target itself — the `@main App` struct, `UIApplicationDelegate`, root
coordinator, navigation, and all views. Also the place where every other package is
wired together (the UN delegate is set here, the audio session is activated on Talk
here, the confirmation readback lives here).

### M1 scope for this module (what Kit builds first)

- `@main App` struct with a `UIApplicationDelegate` adapter that:
  - Opens the `CalendarCore` database before any UI renders.
  - Registers the `HOMUNCULUS_EVENT` notification category (placeholder in M1; real in M3).
  - Sets the `UNUserNotificationCenterDelegate` (placeholder in M1; real in M3).
- `Today` view: lists events from `CalendarCore` for today, grouped by time.
- `Add Event` manual form: title + start date/time + duration + notes, written through
  `CalendarCore.Writer`.
- `Info.plist` with `NSMicrophoneUsageDescription` and `NSSpeechRecognitionUsageDescription`
  (copy is ready to use but doesn't fire until M2).
- Data Protection Complete on the DB file, set on first open.

## Boundary

- **Consumes:** every package. This is the glue layer.
- **Is consumed by:** nothing. This is the app.
