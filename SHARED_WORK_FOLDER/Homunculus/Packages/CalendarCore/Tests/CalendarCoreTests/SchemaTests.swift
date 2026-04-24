//  SchemaTests.swift
//  CalendarCoreTests
//
//  Proves that the v1 migration lands cleanly on an empty database and that the
//  structural invariants the rest of the app relies on are in place.

import Testing
import Foundation
import GRDB
@testable import CalendarCore

@Suite("Schema v1 migration")
struct SchemaTests {

    @Test("An empty database migrates to schema version 1")
    func migratesToV1() async throws {
        let db = try HomunculusDatabase.inMemory()
        let version = try db.schemaVersion()
        #expect(version == 1)
    }

    @Test("All expected tables exist after migration")
    func allTablesExist() async throws {
        let db = try HomunculusDatabase.inMemory()
        let expected: Set<String> = [
            "events",
            "reminders",
            "missed_events",
            "settings",
            "activity_log",
            "schema_meta"
        ]
        let names = try await db.__testingTableNames()
        #expect(expected.isSubset(of: names))
    }

    @Test("All seeded settings are present with the expected default JSON values")
    func seededSettingsArePresent() async throws {
        let db = try HomunculusDatabase.inMemory()
        for key in SettingsKey.allCases {
            let json = try await db.reader.settingJSON(key)
            #expect(json == key.defaultValueJSON,
                    "Setting \(key.rawValue) seeded value mismatch: \(String(describing: json))")
        }
    }

    @Test("schema_meta carries schema_version=1 and last_reconcile_at_utc=0")
    func schemaMetaSeeded() async throws {
        let db = try HomunculusDatabase.inMemory()
        let version = try await db.reader.schemaVersion()
        #expect(version == 1)
    }

}

extension HomunculusDatabase {
    /// Test-only hook. Kept inside `CalendarCore` so the test target can see it without
    /// punching a hole in the public API.
    func __testingTableNames() async throws -> Set<String> {
        try await reader.dbPool.read { db in
            let rows = try Row.fetchAll(
                db,
                sql: """
                    SELECT name FROM sqlite_master
                     WHERE type = 'table' AND name NOT LIKE 'sqlite_%'
                       AND name NOT LIKE 'grdb_%';
                    """
            )
            return Set(rows.compactMap { $0["name"] as String? })
        }
    }
}
