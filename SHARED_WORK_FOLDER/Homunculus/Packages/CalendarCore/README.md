# CalendarCore

**Owner:** Mori. **Milestone:** M1.

## Responsibility

The local data layer. Everything that lands in or comes out of SQLite goes through here.

- SQLite via GRDB.swift, WAL mode, file at
  `Application Support/Homunculus/homunculus.sqlite`.
- Data Protection class `NSFileProtectionComplete` is set by `AppShell` at the directory
  level on first launch (outside this module's control — we just consume the path).
- Schema v1 via `DatabaseMigrator`, versioned from day one.
- Actor-isolated `Writer` — every mutation goes through one serialized queue.
- `DatabasePool`-backed `Reader` — concurrent reads during writes.
- Time-zone helpers for the UTC-seconds ↔ IANA-zone conversion pattern that the notification
  trigger construction relies on.

## Public surface

- `HomunculusDatabase` — entry point. Holds the writer and reader.
- `HomunculusDatabase.Writer` — `actor`, every write function is async.
- `HomunculusDatabase.Reader` — `DatabasePool` wrapped for safe concurrent reads.
- Record types: `Event`, `Reminder`, `MissedEvent`, `Setting`, `ActivityLogEntry`,
  `SchemaMetaEntry`.
- Enums: `ReminderKind`, `ReminderStatus`, `EventSource`, `ActivityKind`.
- `TimeZoneHelpers` — UTC-seconds ↔ zoned `DateComponents` conversions.

## Boundary

- **Consumes:** GRDB.swift only.
- **Is consumed by:** every other package (this is the floor of the stack).

## Non-goals

- Not a view-model. No `@Observable`, no Combine, no SwiftUI types.
- Not a notification scheduler. Stores reminder rows; does not talk to UN center.
- Not a voice/NLP layer. Stores `source_utterance` for audit, does not parse it.
- No cloud sync. No CloudKit. No iCloud Drive. Device-local only.
