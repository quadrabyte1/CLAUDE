//  SoftDeleteTests.swift
//  CalendarCoreTests
//
//  Soft-delete is a product decision — the boss needs to be able to ask "what happened
//  to my 2pm" and get an answer. These tests lock the behavior in.

import Testing
import Foundation
@testable import CalendarCore

@Suite("Soft delete semantics")
struct SoftDeleteTests {

    @Test("Soft-deleted events are excluded from default event queries")
    func excludedFromDefaultQueries() async throws {
        let db = try HomunculusDatabase.inMemory()
        let start: Int64 = 1_714_100_000

        let e = Event(
            id: "E1",
            title: "Coffee with Jane",
            startsAtUTC: start,
            endsAtUTC: start + 1800,
            tzIdentifier: "America/Los_Angeles",
            notes: nil,
            source: .manual,
            sourceUtterance: nil,
            createdAt: start - 3600,
            updatedAt: start - 3600,
            deletedAt: nil
        )
        try await db.writer.insertEvent(e)

        // Alive: findable.
        let alive = try await db.reader.event(id: "E1")
        #expect(alive != nil)

        try await db.writer.softDeleteEvent(id: "E1")

        // Default query hides it.
        let afterDelete = try await db.reader.event(id: "E1")
        #expect(afterDelete == nil)

        // Explicit variant still returns it — deleted_at set.
        let audit = try await db.reader.eventIncludingDeleted(id: "E1")
        #expect(audit != nil)
        #expect(audit?.deletedAt != nil)
    }

    @Test("Soft-deleted events are excluded from range queries")
    func excludedFromRangeQueries() async throws {
        let db = try HomunculusDatabase.inMemory()
        let start: Int64 = 1_714_100_000

        let alive = Event(
            id: "ALIVE",
            title: "Alive",
            startsAtUTC: start,
            endsAtUTC: start + 1800,
            tzIdentifier: "America/Los_Angeles",
            source: .manual,
            createdAt: start - 3600,
            updatedAt: start - 3600
        )
        let dead = Event(
            id: "DEAD",
            title: "Dead",
            startsAtUTC: start + 60,
            endsAtUTC: start + 60 + 1800,
            tzIdentifier: "America/Los_Angeles",
            source: .manual,
            createdAt: start - 3600,
            updatedAt: start - 3600
        )
        try await db.writer.insertEvent(alive)
        try await db.writer.insertEvent(dead)
        try await db.writer.softDeleteEvent(id: "DEAD")

        let results = try await db.reader.events(fromUTC: start - 10, toUTC: start + 3600)
        let ids = Set(results.map(\.id))
        #expect(ids == ["ALIVE"])
    }

    @Test("Soft-deleting an event flips all its reminders to cancelled")
    func softDeleteCancelsReminders() async throws {
        let db = try HomunculusDatabase.inMemory()
        let start: Int64 = 1_714_200_000

        let e = Event(
            id: "E2",
            title: "Dentist",
            startsAtUTC: start,
            endsAtUTC: start + 1800,
            tzIdentifier: "America/Los_Angeles",
            source: .manual,
            createdAt: start - 3600,
            updatedAt: start - 3600
        )
        try await db.writer.insertEventWithReminders(e)

        let before = try await db.reader.reminders(forEventID: "E2")
        #expect(before.allSatisfy { $0.status == .pending })

        try await db.writer.softDeleteEvent(id: "E2")

        let after = try await db.reader.reminders(forEventID: "E2")
        #expect(!after.isEmpty)
        #expect(after.allSatisfy { $0.status == .cancelled })
    }
}
