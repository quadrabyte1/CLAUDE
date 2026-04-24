//  TimeZoneHelpersTests.swift
//  CalendarCoreTests
//
//  The TZ-aware DateComponents builder is the single most load-bearing helper in this
//  package. If this is wrong, notifications fire at the wrong wall-clock when the boss
//  travels. DST is where offset-based storage visibly breaks — these tests exercise
//  that boundary directly.

import Testing
import Foundation
@testable import CalendarCore

@Suite("TimeZoneHelpers")
struct TimeZoneHelpersTests {

    /// America/Los_Angeles shifts UTC-8 → UTC-7 at 2:00 AM local on 2026-03-08.
    /// A wall-clock of 2026-03-09 10:00 (the day after DST start) is UTC-7 = 17:00 UTC.
    @Test("Builds components for a post-DST-start wall-clock in America/Los_Angeles")
    func postDSTStart() throws {
        // 2026-03-09 10:00 PDT = 2026-03-09 17:00 UTC = 1_773_072_000
        let utc: Int64 = 1_773_072_000
        let comps = try TimeZoneHelpers.zonedComponents(
            fromUTCSeconds: utc,
            tzIdentifier: "America/Los_Angeles"
        )
        #expect(comps.year   == 2026)
        #expect(comps.month  == 3)
        #expect(comps.day    == 9)
        #expect(comps.hour   == 10)
        #expect(comps.minute == 0)
        #expect(comps.second == 0)
        #expect(comps.timeZone?.identifier == "America/Los_Angeles")
    }

    /// Mirror side of the same date: a wall-clock of 2026-03-07 10:00 is still PST
    /// (UTC-8) = 18:00 UTC.
    @Test("Builds components for a pre-DST-start wall-clock in America/Los_Angeles")
    func preDSTStart() throws {
        // 2026-03-07 10:00 PST = 2026-03-07 18:00 UTC = 1_772_899_200
        let utc: Int64 = 1_772_899_200
        let comps = try TimeZoneHelpers.zonedComponents(
            fromUTCSeconds: utc,
            tzIdentifier: "America/Los_Angeles"
        )
        #expect(comps.year   == 2026)
        #expect(comps.month  == 3)
        #expect(comps.day    == 7)
        #expect(comps.hour   == 10)
        #expect(comps.minute == 0)
        #expect(comps.second == 0)
        #expect(comps.timeZone?.identifier == "America/Los_Angeles")
    }

    /// An event scheduled at 2026-03-09 10:00 LA wall-clock must yield the same UTC
    /// seconds no matter what the device's current TZ is. This is the round-trip test
    /// — break this and you break the "dentist at 10am back home" promise.
    @Test("Round trip: wall-clock → UTC → wall-clock preserves identity across DST")
    func roundTripAcrossDST() throws {
        let wallYear   = 2026
        let wallMonth  = 3
        let wallDay    = 9
        let wallHour   = 10
        let wallMinute = 0
        let wallSecond = 0
        let tz = "America/Los_Angeles"

        let utc = try TimeZoneHelpers.utcSeconds(
            fromZonedWallClock: wallYear,
            month: wallMonth,
            day: wallDay,
            hour: wallHour,
            minute: wallMinute,
            second: wallSecond,
            tzIdentifier: tz
        )
        let back = try TimeZoneHelpers.zonedComponents(
            fromUTCSeconds: utc,
            tzIdentifier: tz
        )
        #expect(back.year   == wallYear)
        #expect(back.month  == wallMonth)
        #expect(back.day    == wallDay)
        #expect(back.hour   == wallHour)
        #expect(back.minute == wallMinute)
        #expect(back.second == wallSecond)
    }

    @Test("Unknown TZ identifier throws rather than silently falling back")
    func unknownZoneThrows() {
        #expect(throws: TimeZoneHelpers.Error.self) {
            _ = try TimeZoneHelpers.zonedComponents(
                fromUTCSeconds: 0,
                tzIdentifier: "Not/A/Real/Zone"
            )
        }
    }

    /// The whole point of carrying `timeZone` on the returned components is that
    /// `UNCalendarNotificationTrigger` uses it to anchor the wall-clock. If someone
    /// later "simplifies" this helper by dropping that field, this test will scream.
    @Test("Returned components always carry an explicit TimeZone")
    func componentsCarryExplicitTimeZone() throws {
        let comps = try TimeZoneHelpers.zonedComponents(
            fromUTCSeconds: 1_773_072_000,
            tzIdentifier: "Europe/London"
        )
        #expect(comps.timeZone != nil)
        #expect(comps.timeZone?.identifier == "Europe/London")
    }
}
