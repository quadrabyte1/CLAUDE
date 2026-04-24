//  Writer.swift
//  CalendarCore
//
//  The actor-isolated writer. Every mutation in the system lands here, serialized.
//  There is one writer instance per `HomunculusDatabase`, so the actor's mailbox IS
//  the serialization point. If the calling layer respects the "writes go through
//  `writer`" rule, we cannot have a write-write race.
//
//  Soft-delete is the default: `deleteEvent(...)` sets `deleted_at` and cascades to the
//  reminders via status='cancelled'. A true DELETE is never exposed in v1.

import Foundation
import GRDB

extension HomunculusDatabase {

    public actor Writer {

        let dbPool: DatabasePool

        // The actor owns a clock so tests can inject deterministic time. In production
        // this defaults to wall-clock via `Date()`.
        private let clock: @Sendable () -> Int64

        init(
            dbPool: DatabasePool,
            clock: @Sendable @escaping () -> Int64 = { Int64(Date().timeIntervalSince1970) }
        ) {
            self.dbPool = dbPool
            self.clock = clock
        }

        // MARK: - Events

        /// Insert a new event. Caller supplies the UUID so the scheduler can use it to
        /// build UN identifiers immediately.
        ///
        /// Reminder rows are NOT inserted here — that's a separate call, typically made
        /// from the same caller on the same actor hop.
        public func insertEvent(_ event: Event) async throws {
            try await dbPool.write { db in
                try event.insert(db)
            }
        }

        /// Convenience: insert an event and the seven per-event reminder rows, each with
        /// `status='pending'` and `fire_at_utc` computed from the event's start plus the
        /// kind's `secondsFromEventStart`. Called on the create-event happy path.
        ///
        /// The morning-summary row is NOT inserted here — per §7 of the plan, the daily
        /// summary is a per-day trigger (`summary.<yyyy-mm-dd>`), not a per-event row.
        public func insertEventWithReminders(_ event: Event) async throws {
            let now = clock()
            try await dbPool.write { db in
                try event.insert(db)
                for kind in ReminderKind.allCases where kind != .morningSummary {
                    guard let offset = kind.secondsFromEventStart else { continue }
                    let reminder = Reminder(
                        id: "ev.\(event.id).\(kind.notificationSuffix)",
                        eventID: event.id,
                        kind: kind,
                        fireAtUTC: event.startsAtUTC + Int64(offset),
                        notificationID: nil,
                        status: .pending,
                        scheduledAt: nil,
                        firedAt: nil,
                        ackedAt: nil,
                        createdAt: now,
                        updatedAt: now
                    )
                    try reminder.insert(db)
                }
            }
        }

        /// Update an event. `updated_at` is bumped here; callers don't have to.
        public func updateEvent(_ event: Event) async throws {
            let now = clock()
            var updated = event
            updated.updatedAt = now
            try await dbPool.write { db in
                try updated.update(db)
            }
        }

        /// Soft-delete an event. The row stays in `events`; `deleted_at` is set. All
        /// attached reminders flip to `status='cancelled'` so the reconciler will drop
        /// them from the UN center on its next pass.
        public func softDeleteEvent(id: String) async throws {
            let now = clock()
            try await dbPool.write { db in
                try db.execute(
                    sql: """
                        UPDATE events
                           SET deleted_at = ?, updated_at = ?
                         WHERE id = ?
                        """,
                    arguments: [now, now, id]
                )
                try db.execute(
                    sql: """
                        UPDATE reminders
                           SET status = ?, updated_at = ?
                         WHERE event_id = ?
                        """,
                    arguments: [ReminderStatus.cancelled.rawValue, now, id]
                )
            }
        }

        // MARK: - Reminders

        /// Upsert one reminder row. Insert if the (event_id, kind) pair is new, update
        /// otherwise. Used by the scheduler to promote `pending` → `scheduled` or to
        /// flip status on ack.
        public func upsertReminder(_ reminder: Reminder) async throws {
            let now = clock()
            var updated = reminder
            updated.updatedAt = now
            try await dbPool.write { db in
                try updated.save(db)
            }
        }

        /// Batch status update — one transaction.
        public func updateReminderStatus(
            ids: [String],
            to status: ReminderStatus
        ) async throws {
            guard !ids.isEmpty else { return }
            let now = clock()
            try await dbPool.write { db in
                let placeholders = ids.map { _ in "?" }.joined(separator: ",")
                var args: [DatabaseValueConvertible] = [status.rawValue, now]
                args.append(contentsOf: ids as [DatabaseValueConvertible])
                try db.execute(
                    sql: """
                        UPDATE reminders
                           SET status = ?, updated_at = ?
                         WHERE id IN (\(placeholders))
                        """,
                    arguments: StatementArguments(args)
                )
            }
        }

        // MARK: - Missed events

        public func markMissed(eventID: String) async throws {
            let now = clock()
            try await dbPool.write { db in
                try db.execute(
                    sql: """
                        INSERT OR IGNORE INTO missed_events
                          (event_id, missed_at, surfaced_in_summary, rescheduled_event_id)
                        VALUES (?, ?, 0, NULL)
                        """,
                    arguments: [eventID, now]
                )
            }
        }

        // MARK: - Settings

        public func setSettingJSON(_ key: SettingsKey, value: String) async throws {
            try await dbPool.write { db in
                try db.execute(
                    sql: """
                        INSERT INTO settings(key, value) VALUES(?, ?)
                        ON CONFLICT(key) DO UPDATE SET value = excluded.value
                        """,
                    arguments: [key.rawValue, value]
                )
            }
        }

        // MARK: - Activity log

        public func log(
            kind: ActivityKind,
            eventID: String? = nil,
            payload: String? = nil
        ) async throws {
            let now = clock()
            try await dbPool.write { db in
                var entry = ActivityLogEntry(
                    atUTC: now,
                    kind: kind,
                    eventID: eventID,
                    payload: payload
                )
                try entry.insert(db)
            }
        }

        // MARK: - Schema meta

        public func setSchemaMeta(key: String, value: String) async throws {
            try await dbPool.write { db in
                try db.execute(
                    sql: """
                        INSERT INTO schema_meta(key, value) VALUES(?, ?)
                        ON CONFLICT(key) DO UPDATE SET value = excluded.value
                        """,
                    arguments: [key, value]
                )
            }
        }
    }
}
