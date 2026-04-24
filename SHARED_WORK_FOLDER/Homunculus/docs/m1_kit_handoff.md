# M1 Handoff: CalendarCore → Kit

**From:** Mori
**To:** Kit
**Date:** 2026-04-22
**Milestone:** M1 (project skeleton + local data layer)

Boss said "let's go" on the v1 plan. I've laid down the SPM skeleton and the full
`CalendarCore` package. You're up next for the Xcode project and the M1 view surface.
Below is everything you need to pick this up cleanly.

---

## 1. What I built

### Project layout
```
Homunculus/
├── README.md
├── docs/
│   └── m1_kit_handoff.md       ← this file
└── Packages/
    ├── CalendarCore/            ← done (M1)
    ├── VoiceCapture/            ← skeleton; real in M2
    ├── NLU/                     ← skeleton; real in M2
    ├── Scheduling/              ← skeleton; real in M3
    ├── NotificationsKit/        ← skeleton; real in M3
    └── AppShell/                ← skeleton; yours to build out
```

Each skeleton package has a valid `Package.swift`, a `README.md` describing the
ownership boundary, and empty source/test folders. Build graph is pre-wired:

- `CalendarCore` → GRDB only.
- `VoiceCapture`, `NLU`, `NotificationsKit` → `CalendarCore`.
- `Scheduling` → `CalendarCore`, `NotificationsKit`.
- `AppShell` → everybody.

### `CalendarCore` contents
- `Enums.swift` — `ReminderKind`, `ReminderStatus`, `EventSource`, `ActivityKind`.
  Each kind carries its own `notificationSuffix` and `secondsFromEventStart` so
  Scheduling can build UN identifiers without case-analysis spaghetti.
- `SettingsKey.swift` — closed enum of setting keys with default JSON values.
  Seeded on first migration.
- `Records.swift` — GRDB record types for every table.
- `Migrations.swift` — v1 schema. **Do not edit this migration after we ship.**
  Any change post-ship is a new migration.
- `TimeZoneHelpers.swift` — UTC-seconds ↔ zoned `DateComponents`. The
  `zonedComponents` helper is what Scheduling (M3) will feed into
  `UNCalendarNotificationTrigger`. The returned components carry an explicit
  `TimeZone`; do not drop that field.
- `HomunculusDatabase.swift` — entry point. `.open(at:)` for production,
  `.inMemory()` for tests.
- `Reader.swift` — `DatabasePool`-backed reads. Respects soft-delete by default.
- `Writer.swift` — `actor`. Every mutation goes through here, serialized.

### GRDB version pin
`6.29.3` exact. Pinned in `Packages/CalendarCore/Package.swift`. Don't let SPM
re-resolve this without a migration review — schema migrator behavior is part of
the contract.

---

## 2. What you (Kit) do next in M1

### 2.1 Xcode project
Create the `Homunculus.xcodeproj` (or `.xcworkspace` if you prefer) at
`Homunculus/`. App target name: `Homunculus`. Bundle id: pick — I have no opinion.
Add all six local packages as package dependencies. `AppShell` is the one that
actually gets linked into the app target; the others transit through.

### 2.2 Deployment + language
- iOS 26.0 deployment target.
- Swift 6.
- Strict concurrency ON at the target level (we have it on per-package too).

### 2.3 Entitlements + Info.plist
Required Info.plist keys (copy is up to you, keep it calm and factual):
- `NSMicrophoneUsageDescription` — "Homunculus listens when you tap Talk."
- `NSSpeechRecognitionUsageDescription` — "Homunculus turns your voice into events on
  your phone. No audio leaves your device."

Entitlements:
- **No** Critical Alerts. Don't apply, don't add.
- **No** push. Local notifications only.
- **No** background modes needed for the core notification loop. Local notifications
  fire from a terminated app; the system schedules them.
- Time-Sensitive interruption level is a free notification feature in v1 — does not
  require a separate entitlement request.

### 2.4 Data Protection on the DB file
Before calling `HomunculusDatabase.open(at:)`, create
`Application Support/Homunculus/` and apply file protection:

```swift
try FileManager.default.createDirectory(
    at: dir, withIntermediateDirectories: true,
    attributes: [.protectionKey: FileProtectionType.complete]
)
```

Then open:

```swift
let dbURL = dir.appendingPathComponent("homunculus.sqlite")
let db = try HomunculusDatabase.open(at: dbURL)
```

Do this synchronously in the `UIApplicationDelegate`'s
`application(_:didFinishLaunchingWithOptions:)`, **before** any UI renders.
`CalendarCore` will run migrations as part of `.open(...)`. Surface any error here
with a real user-visible message; we don't silently continue with a dead DB.

### 2.5 Notification category registration (placeholder in M1)
In `didFinishLaunching...`, register a placeholder category with a single OK action
so the identifier is stable from day one:

```swift
let ack = UNNotificationAction(identifier: "ACK", title: "OK", options: .foreground)
let category = UNNotificationCategory(
    identifier: "HOMUNCULUS_EVENT",
    actions: [ack],
    intentIdentifiers: [],
    options: [.customDismissAction]
)
UNUserNotificationCenter.current().setNotificationCategories([category])
UNUserNotificationCenter.current().delegate = appDelegateDelegateShim
```

Delegate will be a no-op in M1; real routing lands in M3 via `NotificationsKit`. The
point is: set the delegate **in `didFinishLaunching`**, not in a view model. Cold
launches from a notification tap will silently drop the ack otherwise.

### 2.6 SwiftUI views for M1
- **Root `ContentView`** with a `NavigationStack` and a single tab equivalent
  (`Today`). No tab bar in v1.
- **`Today` view**:
  - Title: "Today".
  - Body: calls `db.reader.events(fromUTC:, toUTC:)` with today's local
    start-of-day and end-of-day (use `Calendar.current`).
  - Each row: start time (hh:mm a), title, faint duration line.
  - Empty state (Q4-approved warm-minimal): "No events today. Tap Talk to add
    one." plus the big Talk button (Talk button is styled in M1 but does nothing —
    the wiring is M2).
  - Missed-events banner at top if `missed_events.surfaced_in_summary = 0` rows
    exist (not strictly required for M1, but trivial to stub now so M4 slots in).
- **Manual Add Event form** — this is the only write surface in M1:
  - Fields: title, start date/time (date picker), duration (30 min default),
    optional notes.
  - TZ: use `TimeZone.current.identifier` — M1 does not ask the user to pick
    zones. Zone-at-creation (Q1) is the rule.
  - On save: generate UUID (lowercased); call
    `db.writer.insertEventWithReminders(event)` with `source: .manual`. This lays
    down the event row AND the six non-summary reminder rows in one transaction.
    (The reminder rows stay `status='pending'` until Scheduling lands in M3 —
    that's correct behavior.)
  - Dismiss back to `Today`.

Typography + tap targets: Dynamic Type from the first pass. Big buttons. The boss
is older; design for him, not for you.

### 2.7 Run the CalendarCore test suite
Once the project is wired, please run `swift test` (or the Xcode test runner
against the `CalendarCoreTests` target) and confirm all five suites pass:
- `SchemaTests`
- `ReminderUniquenessTests`
- `SoftDeleteTests`
- `TimeZoneHelpersTests`

I couldn't run them from my environment — no Xcode on that path. If anything
fails, ping me before proceeding.

---

## 3. Interface contracts you must honor

These are the promises the rest of the app depends on. Don't route around them.

### 3.1 Every write goes through `HomunculusDatabase.Writer`
Do not open the database pool directly. Do not add a second writer. The actor is
the serialization point; two writers means we have a write-write race.

### 3.2 Never store offsets. Always UTC seconds + IANA identifier.
When you build an `Event`, `tzIdentifier` is the IANA string
(`TimeZone.current.identifier` for now — from M2 onward NLU resolves it). Never
store `-0800` or a manual offset integer. DST and travel break offset storage.

### 3.3 Reminder IDs are deterministic
`"ev.\(eventID).\(kind.notificationSuffix)"`. Do not mint your own. The
`insertEventWithReminders` helper already does this; if you insert reminders
manually for some reason, follow the same scheme.

### 3.4 `deletedAt` is the only way to delete an event in v1
No `DELETE FROM events`. Soft-delete via `writer.softDeleteEvent(id:)`, which
also flips attached reminders to cancelled. Audit trail matters for a memory
product.

### 3.5 `source_utterance` is sensitive
When M2 lands and voice writes start flowing, `Event.sourceUtterance` holds the
raw STT string. Treat it as user content: don't render it in debug UI outside the
dev-only activity log reader.

### 3.6 Activity log is a table, not a file
Write via `writer.log(kind:eventID:payload:)`. Don't add an OSLog-file bridge.
One reconciliation story is enough.

### 3.7 Settings are JSON-encoded
Even the string-valued ones. Read with `reader.settingJSON(.morningSummaryTime)`
and decode; write with `writer.setSettingJSON(.morningSummaryTime, value: "\"07:30\"")`.
Future migrations may add structured values here.

---

## 4. Things I deliberately did NOT build in this session

(So you're not surprised they're missing.)

- Voice capture (M2).
- Foundation Models / NLP (M2).
- Notification wrapper + rolling scheduler + reconciler (M3).
- Morning summary composer (M4).
- Settings screen (M5).
- Any view code. That's yours.
- Any Xcode project file. Also yours.
- Privacy Manifest (`PrivacyInfo.xcprivacy`). M5 — I'll give you the
  data-collection summary ("none beyond local") when we get there.

---

## 5. Style / code-review ground rules

Per §9 of the plan, I yield to you on Swift style and SwiftUI craft. If anything in
`CalendarCore` reads awkwardly on its way into your views, open an issue or a PR
and we'll resolve it. What I do care about:

- Do not change the schema without a migration.
- Do not add a dependency to `CalendarCore` beyond GRDB.
- Do not expose the `DatabasePool` publicly.

Everything else — naming, file organization inside `AppShell`, how you compose
views — is your call.

---

## 6. Open questions for you

1. **Xcode project file shape.** App target + package references, or workspace
   with the packages as local repos alongside the `.xcodeproj`? Your call. I
   don't have a preference; pick whichever keeps your CI story cleanest.
2. **Bundle id.** You own the signing. Ping me only if the boss asks what it is.

---

Ping me when the project is up and the `CalendarCoreTests` suite passes. After
that we'll plan the M2 kickoff together — voice capture and NLU will need a
coordination pass so the Talk button gesture (yours) and the capture engine
(mine) marry cleanly.

— Mori
