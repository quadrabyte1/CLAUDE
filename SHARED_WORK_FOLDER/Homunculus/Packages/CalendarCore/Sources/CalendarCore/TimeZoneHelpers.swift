//  TimeZoneHelpers.swift
//  CalendarCore
//
//  The TZ-aware conversion helpers the Scheduling layer relies on. The whole point of
//  storing UTC seconds plus an IANA zone identifier is that we can reconstruct the
//  wall-clock DateComponents for the event's zone deterministically, no matter what the
//  device's current zone is.
//
//  §5.5 of the plan is the rule here: when building a `UNCalendarNotificationTrigger`,
//  the `DateComponents` we pass in MUST carry an explicit `TimeZone`. If we omit that,
//  the trigger fires at the device's current wall-clock — which is the "fires at 2pm NYC
//  because the device TZ changed" bug. Setting `comps.timeZone` is what keeps the
//  dentist appointment at 2pm LA time even after the boss flies east.

import Foundation

public enum TimeZoneHelpers {

    /// Error type surfaced when an IANA identifier cannot be resolved. This should be
    /// rare — the foundation zone database is comprehensive — but we don't silently
    /// fall back to `.current` or `.gmt` because that's exactly the class of bug this
    /// module exists to prevent.
    public enum Error: Swift.Error, Sendable, Equatable {
        case unknownTimeZone(identifier: String)
    }

    /// Given a UTC unix-seconds timestamp and an IANA zone identifier, return the
    /// `DateComponents` that a `UNCalendarNotificationTrigger` should fire on.
    ///
    /// The returned components carry an explicit `timeZone` — that field is load-bearing.
    /// Strip it and the trigger will re-interpret the wall-clock in `TimeZone.current`
    /// at fire time.
    public static func zonedComponents(
        fromUTCSeconds utcSeconds: Int64,
        tzIdentifier: String
    ) throws -> DateComponents {
        guard let zone = TimeZone(identifier: tzIdentifier) else {
            throw Error.unknownTimeZone(identifier: tzIdentifier)
        }
        var calendar = Calendar(identifier: .gregorian)
        calendar.timeZone = zone
        let date = Date(timeIntervalSince1970: TimeInterval(utcSeconds))
        var comps = calendar.dateComponents(
            [.year, .month, .day, .hour, .minute, .second],
            from: date
        )
        // This is the critical line. Do not remove.
        comps.timeZone = zone
        return comps
    }

    /// Inverse helper: given a zoned wall-clock (year/month/day/hour/minute/second +
    /// IANA identifier), return UTC unix seconds. Useful when the NLU layer hands us a
    /// "local" time it resolved from an utterance.
    public static func utcSeconds(
        fromZonedWallClock year: Int,
        month: Int,
        day: Int,
        hour: Int,
        minute: Int,
        second: Int,
        tzIdentifier: String
    ) throws -> Int64 {
        guard let zone = TimeZone(identifier: tzIdentifier) else {
            throw Error.unknownTimeZone(identifier: tzIdentifier)
        }
        var calendar = Calendar(identifier: .gregorian)
        calendar.timeZone = zone
        var comps = DateComponents()
        comps.year   = year
        comps.month  = month
        comps.day    = day
        comps.hour   = hour
        comps.minute = minute
        comps.second = second
        comps.timeZone = zone
        guard let date = calendar.date(from: comps) else {
            // The only way to land here with valid component values is an impossible
            // wall-clock (the missing hour during DST spring-forward, for example).
            // Surface it to the caller rather than papering over it.
            throw Error.unknownTimeZone(identifier: tzIdentifier)
        }
        return Int64(date.timeIntervalSince1970)
    }
}
