//  ReminderUniquenessTests.swift
//  CalendarCoreTests
//
//  Proves `uq_reminders_ek` actually rejects duplicates. If this test ever fails, a
//  buggy rescheduler could stack up strike_0 rows for one event and fire the same
//  reminder twice — which is exactly the noise-then-distrust failure mode we're
//  protecting against.

import Testing
import Foundation
import GRDB
@testable import CalendarCore

@Suite("Reminder (event_id, kind) uniqueness")
struct ReminderUniquenessTests {

    @Test("Two reminders with the same event_id + kind cannot both exist")
    func duplicateRejected() async throws {
        let db = try HomunculusDatabase.inMemory()
        let now: Int64 = 1_714_000_000 // arbitrary fixed 2024 timestamp, fine for this

        let event = makeEvent(id: "E1", startsAt: now + 3600)
        try await db.writer.insertEvent(event)

        let r1 = Reminder(
            id: "ev.E1.strike.0",
            eventID: "E1",
            kind: .strike0,
            fireAtUTC: event.startsAtUTC,
            notificationID: nil,
            status: .pending,
            createdAt: now,
            updatedAt: now
        )
        try await db.writer.upsertReminder(r1)

        // Second row, same (event_id, kind), different primary key. Must be rejected.
        let r2 = Reminder(
            id: "ev.E1.strike.0.dupe",
            eventID: "E1",
            kind: .strike0,
            fireAtUTC: event.startsAtUTC,
            notificationID: nil,
            status: .pending,
            createdAt: now,
            updatedAt: now
        )
        await #expect(throws: (any Error).self) {
            try await db.writer.upsertReminder(r2)
        }
    }

    @Test("`insertEventWithReminders` creates exactly one row per non-summary kind")
    func helperInsertsOnePerKind() async throws {
        let db = try HomunculusDatabase.inMemory()
        let now: Int64 = 1_714_000_000
        let event = makeEvent(id: "E2", startsAt: now + 7200)
        try await db.writer.insertEventWithReminders(event)

        let reminders = try await db.reader.reminders(forEventID: "E2")
        let nonSummaryKinds = ReminderKind.allCases.filter { $0 != .morningSummary }
        #expect(reminders.count == nonSummaryKinds.count)
        #expect(Set(reminders.map(\.kind)) == Set(nonSummaryKinds))
    }

    private func makeEvent(id: String, startsAt: Int64) -> Event {
        Event(
            id: id,
            title: "Test",
            startsAtUTC: startsAt,
            endsAtUTC: startsAt + 1800,
            tzIdentifier: "America/Los_Angeles",
            notes: nil,
            source: .manual,
            sourceUtterance: nil,
            createdAt: startsAt - 3600,
            updatedAt: startsAt - 3600,
            deletedAt: nil
        )
    }
}
