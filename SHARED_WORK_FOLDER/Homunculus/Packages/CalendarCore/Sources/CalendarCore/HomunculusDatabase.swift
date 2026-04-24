//  HomunculusDatabase.swift
//  CalendarCore
//
//  The one entry point into the data layer. Holds a `DatabasePool` for reads and an
//  actor-isolated `Writer` for writes.
//
//  Concurrency model (§3 of the plan):
//    - Every write goes through the `writer` actor. Serial. No exceptions.
//    - Reads go through `reader`, which wraps a GRDB `DatabasePool` (concurrent reads,
//      never blocked by a write except at commit boundaries).
//    - No one outside this module holds the raw `DatabasePool`.
//
//  Lifecycle:
//    - `AppShell` calls `HomunculusDatabase.open(...)` once during `didFinishLaunching`.
//    - The migrator runs before any code can read or write, so callers never see a
//      partially-migrated schema.

import Foundation
import GRDB

public final class HomunculusDatabase: @unchecked Sendable {

    public let reader: Reader
    public let writer: Writer

    private let dbPool: DatabasePool

    /// Open (or create) the Homunculus database at the given path. The directory must
    /// already exist — AppShell creates `Application Support/Homunculus/` with
    /// `NSFileProtectionComplete` before calling in here.
    ///
    /// The migrator runs synchronously on open. Returns only after the schema is at
    /// the latest version.
    public static func open(at url: URL) throws -> HomunculusDatabase {
        var config = Configuration()
        // WAL is set by GRDB's DatabasePool by default, but pin the other pragmas we
        // care about explicitly so they're obvious in a review.
        config.prepareDatabase { db in
            try db.execute(sql: "PRAGMA foreign_keys = ON;")
        }

        let pool = try DatabasePool(path: url.path, configuration: config)
        let migrator = Migrations.makeMigrator()
        try migrator.migrate(pool)
        return HomunculusDatabase(dbPool: pool)
    }

    /// In-memory variant used by tests. Identical migration path; no disk I/O.
    public static func inMemory() throws -> HomunculusDatabase {
        var config = Configuration()
        config.prepareDatabase { db in
            try db.execute(sql: "PRAGMA foreign_keys = ON;")
        }
        // GRDB treats an empty path as in-memory for DatabaseQueue; for DatabasePool we
        // use a unique shared-cache URI so pool reads/writes see the same DB.
        let path = "file:homunculus-\(UUID().uuidString)?mode=memory&cache=shared"
        let pool = try DatabasePool(path: path, configuration: config)
        let migrator = Migrations.makeMigrator()
        try migrator.migrate(pool)
        return HomunculusDatabase(dbPool: pool)
    }

    private init(dbPool: DatabasePool) {
        self.dbPool = dbPool
        self.reader = Reader(dbPool: dbPool)
        self.writer = Writer(dbPool: dbPool)
    }

    /// Inspect `schema_meta` to confirm the migrator landed us at the expected version.
    /// Helpful for tests and for a defensive assertion at launch.
    public func schemaVersion() throws -> Int {
        try dbPool.read { db in
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
