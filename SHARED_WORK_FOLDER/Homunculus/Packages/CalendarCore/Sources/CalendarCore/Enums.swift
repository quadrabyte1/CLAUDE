//  Enums.swift
//  CalendarCore
//
//  The string-backed enums that travel in and out of SQLite. Every on-disk value uses
//  the `rawValue` of the Swift enum — never an Int — so the DB stays human-readable when
//  I'm reading it in sqlite3 at 2am trying to figure out why a strike didn't fire.

import Foundation

/// The seven reminder kinds that together form the escalation contract for a single event,
/// plus the one per-day morning summary. Each event gets one row of every kind in the
/// `reminders` table on creation; uniqueness is enforced by `uq_reminders_ek`.
public enum ReminderKind: String, Sendable, CaseIterable, Codable {
    /// 7:00 local (user-configurable) — one per day, not per event. Stored in `reminders`
    /// for a given event only when that event needs to be mentioned in the next-morning
    /// rescheduling offer; the nominal daily summary row uses identifier
    /// `summary.<yyyy-mm-dd>` and lives outside the per-event scheme.
    case morningSummary = "morning_summary"
    case headsUp30      = "heads_up_30"
    case pre5           = "pre_5"
    case strike0        = "strike_0"
    case strike5        = "strike_5"
    case strike10       = "strike_10"
    case strike15       = "strike_15"

    /// Offset (in seconds) from the event's `starts_at_utc` at which this reminder fires.
    /// Negative for pre-event kinds. Morning summary has no sensible per-event offset
    /// (it anchors to a wall-clock time of day), so we return nil there.
    public var secondsFromEventStart: Int? {
        switch self {
        case .morningSummary: return nil
        case .headsUp30:      return -30 * 60
        case .pre5:           return -5 * 60
        case .strike0:        return 0
        case .strike5:        return 5 * 60
        case .strike10:       return 10 * 60
        case .strike15:       return 15 * 60
        }
    }

    /// The deterministic UN identifier suffix, so the Scheduling layer can build
    /// `"ev.\(eventID).\(kind.notificationSuffix)"` without case analysis scattered
    /// across the codebase.
    public var notificationSuffix: String {
        switch self {
        case .morningSummary: return "morningSummary"
        case .headsUp30:      return "headsup30"
        case .pre5:           return "pre5"
        case .strike0:        return "strike.0"
        case .strike5:        return "strike.1"
        case .strike10:       return "strike.2"
        case .strike15:       return "strike.3"
        }
    }
}

/// The lifecycle a single reminder row walks through.
public enum ReminderStatus: String, Sendable, CaseIterable, Codable {
    /// In the DB but not yet handed to `UNUserNotificationCenter`. Typically because it
    /// sits beyond the 72h horizon.
    case pending   = "pending"
    /// Handed to UN via `UN.add()`. The `notification_id` column is set when this flips.
    case scheduled = "scheduled"
    /// Observed as fired (via delegate or reconciliation past-due detection), no ack yet.
    case fired     = "fired"
    /// User tapped OK. Terminal for this row; triggers cancel-the-rest in Scheduling.
    case acked     = "acked"
    /// Explicitly removed — event cancelled, event edited, or a later strike cancelled by
    /// an earlier ack.
    case cancelled = "cancelled"
    /// Strike_15 passed unacked and the grace window elapsed.
    case missed    = "missed"
}

/// How an event got into the database. Used by the activity log and future analytics
/// (for us, not for Apple — we never ship user-level analytics over the wire).
public enum EventSource: String, Sendable, CaseIterable, Codable {
    case voice       = "voice"
    case manual      = "manual"
    case rescheduled = "rescheduled"
}

/// Every kind of line item the activity log accepts. Keep the set closed — a surprise
/// value in production means something upstream has drifted.
public enum ActivityKind: String, Sendable, CaseIterable, Codable {
    case sttCapture         = "stt_capture"
    case nlpParse           = "nlp_parse"
    case nlpAmbiguous       = "nlp_ambiguous"
    case eventCreate        = "event_create"
    case eventUpdate        = "event_update"
    case eventDelete        = "event_delete"
    case reminderSchedule   = "reminder_schedule"
    case reminderFire       = "reminder_fire"
    case reminderAck        = "reminder_ack"
    case reminderMiss       = "reminder_miss"
    case reconcile          = "reconcile"
    case tzChange           = "tz_change"
    case settingsChange     = "settings_change"
    case error              = "error"
}
