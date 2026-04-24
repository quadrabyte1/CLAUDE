//  Reader.swift
//  CalendarCore
//
//  Read-side of the database. Wraps a GRDB `DatabasePool` with a small, deliberately
//  narrow API. New read methods get added here as the product needs them — but only
//  when the product needs them. No speculative queries.
//
//  Every method here respects soft-delete: if an event's `deleted_at IS NOT NULL`,
//  default queries behave as if it doesn't exist. If you need to see deleted rows
//  (audit, debug, reschedule offers that reference the old ID), use the explicit
//  `*IncludingDeleted` variant.

import Foundation
import GRDB

extension HomunculusDatabase {

    public struct Reader: Sendable {

        let dbPool: DatabasePool

        // MARK: - Events

        /// Fetch a single live (non-soft-deleted) event by id.
        public func event(id: String) async throws -> Event? {
            try await dbPool.read { db in
                try Event
                    .filter(Column("id") == id && Column("deleted_at") == nil)
                    .fetchOne(db)
            }
        }

        /// Fetch an event by id, returning it even if it's been soft-deleted.
        public func eventIncludingDeleted(id: String) async throws -> Event? {
            try await dbPool.read { db in
                try Event.filter(Column("id") == id).fetchOne(db)
            }
        }

        /// Live events whose start is in the half-open UTC range `[startUTC, endUTC)`,
        /// ordered ascending by start. Soft-deleted events are excluded.
        public func events(
            fromUTC startUTC: Int64,
            toUTC endUTC: Int64
        ) async throws -> [Event] {
            try await dbPool.read { db in
                try Event
                    .filter(
                        Column("starts_at_utc") >= startUTC
                        && Column("starts_at_utc") < endUTC
                        && Column("deleted_at") == nil
                    )
                    .order(Column("starts_at_utc").asc)
                    .fetchAll(db)
            }
        }

        // MARK: - Reminders

        /// All reminder rows attached to a given event, any status, ordered by fire time.
        public func reminders(forEventID eventID: String) async throws -> [Reminder] {
            try await dbPool.read { db in
                try Reminder
                    .filter(Column("event_id") == eventID)
                    .order(Column("fire_at_utc").asc)
                    .fetchAll(db)
            }
        }

        /// Reminders whose fire time falls in `[nowUTC, nowUTC + horizonSeconds)` and
        /// whose status is one of the supplied set. The Scheduling layer's top-up pass
        /// calls this with `{pending, scheduled}`.
        public func reminders(
            fireAtUTCFrom nowUTC: Int64,
            within horizonSeconds: Int64,
            statuses: Set<ReminderStatus>
        ) async throws -> [Reminder] {
            let rawStatuses = statuses.map(\.rawValue)
            return try await dbPool.read { db in
                try Reminder
                    .filter(
                        Column("fire_at_utc") >= nowUTC
                        && Column("fire_at_utc") < (nowUTC + horizonSeconds)
                        && rawStatuses.contains(Column("status"))
                    )
                    .order(Column("fire_at_utc").asc)
                    .fetchAll(db)
            }
        }

        // MARK: - Settings

        /// Fetch a setting's raw JSON string. Returns nil if the row is missing — callers
        /// should treat that as "use the hard-coded default".
        public func settingJSON(_ key: SettingsKey) async throws -> String? {
            try await dbPool.read { db in
                try Setting
                    .filter(Column("key") == key.rawValue)
                    .fetchOne(db)?
                    .value
            }
        }

        // MARK: - Schema meta

        public func schemaVersion() async throws -> Int {
            try await dbPool.read { db in
                let row = try Row.fetchOne(
                    db,
                    sql: "SELECT value FROM schema_meta WHERE key = 'schema_version'"
                )
                guard let value = row?["value"] as String?, let v = Int(value) else {
                    return 0
                }
                return v
            }
        }
    }
}
