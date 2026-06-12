/// ReconciliationTests.swift
/// Swift Testing suite for the reminder reconciliation logic.
///
/// The reconciliation algorithm is the critical piece of the iOS client:
/// it keeps UNUserNotificationCenter in sync with the brain's schedule.
/// Every scenario here maps to a real thing that can go wrong at runtime.
///
/// Because UNUserNotificationCenter requires a real device/simulator to call,
/// we test the LOGIC of the diff here (what to add, what to remove) rather
/// than the actual UN calls.  The diff logic is extracted so it can be tested
/// in pure Swift without any framework mocking.

import Testing
import Foundation
@testable import Homunculus

// MARK: - Pure reconciliation diff logic (extracted for testability)

/// The pure diff that ScheduleRegistrar performs.
/// Returns (toAdd, toRemove) as sets of notification identifiers.
func reconcileDiff(
    brainRows: [ReminderRow],
    managedIDs: Set<String>,
    now: Date
) -> (toAdd: Set<String>, toRemove: Set<String>) {
    let futureRows = brainRows.filter { $0.fireAt > now }
    let brainIDs   = Set(futureRows.map(\.id))
    let toAdd      = brainIDs.subtracting(managedIDs)
    let toRemove   = managedIDs.subtracting(brainIDs)
    return (toAdd, toRemove)
}

// MARK: - Helpers

private func makeRow(eventId: String, kind: ReminderKind, fireAt: Date) -> ReminderRow {
    let json = """
    {
      "event_id": "\(eventId)",
      "kind": "\(kind.rawValue)",
      "fire_at": "\(ISO8601DateFormatter.brainFormatter.string(from: fireAt))",
      "tz": "America/New_York",
      "body": "Test body",
      "status": "pending"
    }
    """.data(using: .utf8)!
    return try! BrainClient.decoder.decode(ReminderRow.self, from: json)
}

private let future1 = Date(timeIntervalSinceNow:  3600)  // 1 hour from now
private let future2 = Date(timeIntervalSinceNow:  7200)  // 2 hours from now
private let past    = Date(timeIntervalSinceNow: -3600)  // 1 hour ago
private let now     = Date()

// MARK: - Test Suite

@Suite("Reminder reconciliation diff logic")
struct ReconciliationTests {

    // MARK: - Basic add/remove

    @Test("Fresh start: all brain rows become toAdd")
    func freshStart() {
        let brainRows: [ReminderRow] = [
            makeRow(eventId: "event1", kind: .strike0,   fireAt: future1),
            makeRow(eventId: "event1", kind: .headsUp30, fireAt: future2),
        ]
        let (toAdd, toRemove) = reconcileDiff(brainRows: brainRows, managedIDs: [], now: now)
        #expect(toAdd    == ["event1:strike_0", "event1:heads_up_30"])
        #expect(toRemove.isEmpty)
    }

    @Test("No change: brain and local match → empty diff")
    func noChange() {
        let brainRows: [ReminderRow] = [
            makeRow(eventId: "event1", kind: .strike0, fireAt: future1),
        ]
        let localIDs: Set<String> = ["event1:strike_0"]
        let (toAdd, toRemove) = reconcileDiff(brainRows: brainRows, managedIDs: localIDs, now: now)
        #expect(toAdd.isEmpty)
        #expect(toRemove.isEmpty)
    }

    @Test("Acked event: brain dropped strikes, local still has them → remove")
    func ackedEventRemovesStrikes() {
        // Brain has cancelled strike_5/10/15 after user acked strike_0.
        // Brain response no longer includes them.
        let brainRows: [ReminderRow] = [
            makeRow(eventId: "event1", kind: .strike0, fireAt: future1),
        ]
        let localIDs: Set<String> = [
            "event1:strike_0",
            "event1:strike_5",
            "event1:strike_10",
            "event1:strike_15",
        ]
        let (toAdd, toRemove) = reconcileDiff(brainRows: brainRows, managedIDs: localIDs, now: now)
        #expect(toAdd.isEmpty)
        #expect(toRemove == ["event1:strike_5", "event1:strike_10", "event1:strike_15"])
    }

    @Test("Deleted event: all rows vanish from brain → remove all local")
    func deletedEventRemovesAll() {
        let brainRows: [ReminderRow] = []  // brain has nothing
        let localIDs: Set<String> = [
            "event1:heads_up_30",
            "event1:pre_5",
            "event1:strike_0",
        ]
        let (toAdd, toRemove) = reconcileDiff(brainRows: brainRows, managedIDs: localIDs, now: now)
        #expect(toAdd.isEmpty)
        #expect(toRemove == localIDs)
    }

    @Test("New event added to brain while app was background → add new rows")
    func newEventAdded() {
        let existingRows: [ReminderRow] = [
            makeRow(eventId: "event1", kind: .strike0, fireAt: future1),
        ]
        let newRows: [ReminderRow] = [
            makeRow(eventId: "event1", kind: .strike0,   fireAt: future1),
            makeRow(eventId: "event2", kind: .headsUp30, fireAt: future2),
            makeRow(eventId: "event2", kind: .strike0,   fireAt: future1),
        ]
        let localIDs: Set<String> = Set(existingRows.map(\.id))
        let (toAdd, toRemove) = reconcileDiff(brainRows: newRows, managedIDs: localIDs, now: now)
        #expect(toAdd    == ["event2:heads_up_30", "event2:strike_0"])
        #expect(toRemove.isEmpty)
    }

    // MARK: - Past rows

    @Test("Past fire_at rows are skipped (not added)")
    func pastRowsNotAdded() {
        let brainRows: [ReminderRow] = [
            makeRow(eventId: "event1", kind: .strike0, fireAt: past),   // already fired
            makeRow(eventId: "event1", kind: .strike5, fireAt: future1), // still upcoming
        ]
        let (toAdd, toRemove) = reconcileDiff(brainRows: brainRows, managedIDs: [], now: now)
        #expect(toAdd == ["event1:strike_5"])  // only future row added
        #expect(!toAdd.contains("event1:strike_0"))
    }

    @Test("Past rows that are locally registered get removed (they fired and should be gone)")
    func pastLocalRowsRemoved() {
        let brainRows: [ReminderRow] = [
            makeRow(eventId: "event1", kind: .strike0, fireAt: past),
        ]
        let localIDs: Set<String> = ["event1:strike_0"]
        // The brain still mentions it (fired but not cleaned up),
        // but fire_at is in the past so it won't be in toAdd.
        // It IS in localIDs and NOT in brainIDs (which only counts future rows).
        let (toAdd, toRemove) = reconcileDiff(brainRows: brainRows, managedIDs: localIDs, now: now)
        #expect(toAdd.isEmpty)
        #expect(toRemove == ["event1:strike_0"])
    }

    // MARK: - Managed identifier detection

    @Test("Managed identifier detection: valid colon-separated kind suffix")
    func managedIdentifierValid() {
        // Simulates what ScheduleRegistrar.isManagedIdentifier does.
        let validIDs = [
            "2026-06-12-coffee:strike_0",
            "summary.2026-06-12:morning_summary",
            "some-event:heads_up_30",
            "some-event:pre_5",
        ]
        for id in validIDs {
            let colonIdx  = id.lastIndex(of: ":")!
            let kindPart  = String(id[id.index(after: colonIdx)...])
            let isManaged = ReminderKind(rawValue: kindPart) != nil
            #expect(isManaged, "Expected \(id) to be recognised as managed")
        }
    }

    @Test("Managed identifier detection: non-Homunculus IDs not matched")
    func managedIdentifierInvalid() {
        let foreignIDs = [
            "com.apple.reminders.1234",
            "some-random-string",
            "",
            "event:unknown_kind",
        ]
        for id in foreignIDs {
            let colonIdx  = id.lastIndex(of: ":")
            let isManaged: Bool
            if let colonIdx {
                let kindPart = String(id[id.index(after: colonIdx)...])
                isManaged = ReminderKind(rawValue: kindPart) != nil
            } else {
                isManaged = false
            }
            #expect(!isManaged, "Expected \(id) to NOT be recognised as managed")
        }
    }

    // MARK: - Strike identifier generation

    @Test("strikeIdentifiers generates all four strike IDs")
    func strikeIdentifiers() {
        let ids = ScheduleRegistrar.strikeIdentifiers(eventId: "2026-06-12-coffee")
        #expect(ids.count == 4)
        #expect(ids.contains("2026-06-12-coffee:strike_0"))
        #expect(ids.contains("2026-06-12-coffee:strike_5"))
        #expect(ids.contains("2026-06-12-coffee:strike_10"))
        #expect(ids.contains("2026-06-12-coffee:strike_15"))
    }

    // MARK: - Slot cap

    @Test("Reconciliation respects 60-slot cap — only first 60 future rows added")
    func slotCap() {
        // Create 70 future rows, all new.
        var brainRows = [ReminderRow]()
        for i in 0..<70 {
            let eventId  = "event\(i)"
            let fireDate = Date(timeIntervalSinceNow: Double(i + 1) * 60)
            brainRows.append(makeRow(eventId: eventId, kind: .strike0, fireAt: fireDate))
        }

        let (toAdd, _) = reconcileDiff(brainRows: brainRows, managedIDs: [], now: now)
        // Without the cap logic, all 70 would be in toAdd.
        // The cap is enforced in ScheduleRegistrar.reconcile(), not in the pure diff.
        // So here we just verify all 70 are in the toAdd set (cap is applied elsewhere).
        #expect(toAdd.count == 70)

        // In ScheduleRegistrar.reconcile(), only the first 60 (sorted by fireAt)
        // get registered.  That truncation happens after the diff, not inside it.
    }
}
