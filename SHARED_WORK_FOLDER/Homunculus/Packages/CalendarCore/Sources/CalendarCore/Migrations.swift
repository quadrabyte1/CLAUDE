//  Migrations.swift
//  CalendarCore
//
//  The full schema lives here. Every change is a new migration; the v1 migration below
//  is frozen the moment we ship. Changes after that land as v2, v3... — no edits to v1.
//  This is the contract that makes the reconciliation story sane when v1.x users open
//  a v1.0 database after an app update.
//
//  GRDB's DatabaseMigrator tracks applied migrations in `grdb_migrations` and treats the
//  migration identifier as the key, so the identifier strings here are load-bearing.
//  Do not rename them.

import Foundation
import GRDB

enum Migrations {

    /// Register every migration on the shared migrator.
    static func makeMigrator() -> DatabaseMigrator {
        var migrator = DatabaseMigrator()
        // In DEBUG, erase the DB on an incompatible migration change so tests don't
        // inherit a half-migrated state from a sibling dev branch. This has no effect
        // on release builds (Scheduling's reconciliation pass is the production
        // recovery story).
        #if DEBUG
        migrator.eraseDatabaseOnSchemaChange = true
        #endif

        registerV1(&migrator)
        return migrator
    }

    // MARK: - v1

    private static func registerV1(_ migrator: inout DatabaseMigrator) {
        migrator.registerMigration("v1_initial_schema") { db in

            // MARK: events
            try db.create(table: "events") { t in
                t.column("id",               .text).primaryKey().notNull()
                t.column("title",            .text).notNull()
                t.column("starts_at_utc",    .integer).notNull()
                t.column("ends_at_utc",      .integer).notNull()
                t.column("tz_identifier",    .text).notNull()
                t.column("notes",            .text)
                t.column("source",           .text).notNull()
                t.column("source_utterance", .text)
                t.column("created_at",       .integer).notNull()
                t.column("updated_at",       .integer).notNull()
                t.column("deleted_at",       .integer)
            }
            // Partial indices so "live" queries skip soft-deleted rows without a WHERE.
            try db.execute(sql: """
                CREATE INDEX idx_events_starts
                  ON events(starts_at_utc)
                  WHERE deleted_at IS NULL;
                """)
            try db.execute(sql: """
                CREATE INDEX idx_events_day
                  ON events(starts_at_utc, tz_identifier)
                  WHERE deleted_at IS NULL;
                """)

            // MARK: reminders
            try db.create(table: "reminders") { t in
                t.column("id",              .text).primaryKey().notNull()
                t.column("event_id",        .text).notNull()
                    .references("events", column: "id", onDelete: .cascade)
                t.column("kind",            .text).notNull()
                t.column("fire_at_utc",     .integer).notNull()
                t.column("notification_id", .text)
                t.column("status",          .text).notNull()
                t.column("scheduled_at",    .integer)
                t.column("fired_at",        .integer)
                t.column("acked_at",        .integer)
                t.column("created_at",      .integer).notNull()
                t.column("updated_at",      .integer).notNull()
            }
            try db.execute(sql: """
                CREATE INDEX idx_reminders_event
                  ON reminders(event_id);
                """)
            try db.execute(sql: """
                CREATE INDEX idx_reminders_fire
                  ON reminders(fire_at_utc, status);
                """)
            // One row per (event, kind) — the defense against duplicate strike_0s from
            // a buggy rescheduler.
            try db.execute(sql: """
                CREATE UNIQUE INDEX uq_reminders_ek
                  ON reminders(event_id, kind);
                """)

            // MARK: missed_events
            try db.create(table: "missed_events") { t in
                t.column("event_id",              .text).primaryKey().notNull()
                    .references("events", column: "id")
                t.column("missed_at",             .integer).notNull()
                t.column("surfaced_in_summary",   .integer).notNull().defaults(to: 0)
                t.column("rescheduled_event_id",  .text)
                    .references("events", column: "id")
            }

            // MARK: settings
            try db.create(table: "settings") { t in
                t.column("key",   .text).primaryKey().notNull()
                t.column("value", .text).notNull()
            }
            // Seed defaults.
            for key in SettingsKey.allCases {
                try db.execute(
                    sql: "INSERT INTO settings(key, value) VALUES (?, ?)",
                    arguments: [key.rawValue, key.defaultValueJSON]
                )
            }

            // MARK: activity_log
            try db.create(table: "activity_log") { t in
                t.autoIncrementedPrimaryKey("id")
                t.column("at_utc",   .integer).notNull()
                t.column("kind",     .text).notNull()
                t.column("event_id", .text)
                t.column("payload",  .text)
            }
            try db.execute(sql: """
                CREATE INDEX idx_activity_at
                  ON activity_log(at_utc);
                """)

            // MARK: schema_meta
            try db.create(table: "schema_meta") { t in
                t.column("key",   .text).primaryKey().notNull()
                t.column("value", .text).notNull()
            }
            try db.execute(
                sql: "INSERT INTO schema_meta(key, value) VALUES (?, ?)",
                arguments: ["schema_version", "1"]
            )
            // Placeholder — updated by the reconciler as reconcile passes complete.
            try db.execute(
                sql: "INSERT INTO schema_meta(key, value) VALUES (?, ?)",
                arguments: ["last_reconcile_at_utc", "0"]
            )
        }
    }
}
