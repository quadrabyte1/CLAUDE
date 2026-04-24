//  Records.swift
//  CalendarCore
//
//  GRDB record types. Each struct here corresponds 1:1 to a row in a table defined by
//  Migrations.swift. We keep them small, `Sendable`, and deliberately plain — no
//  convenience initializers that hide the schema shape. When schema v2 eventually lands,
//  it will be obvious which column just changed.

import Foundation
import GRDB

// MARK: - Event

/// An event on the homunculus's calendar. Times are stored as UTC unix seconds + an
/// IANA zone identifier. DST and travel break offset-based storage, so we don't store
/// offsets. Ever.
public struct Event: Codable, Sendable, FetchableRecord, PersistableRecord, Equatable {

    public static let databaseTableName = "events"

    public var id: String
    public var title: String
    public var startsAtUTC: Int64
    public var endsAtUTC: Int64
    public var tzIdentifier: String
    public var notes: String?
    public var source: EventSource
    public var sourceUtterance: String?
    public var createdAt: Int64
    public var updatedAt: Int64
    public var deletedAt: Int64?

    public init(
        id: String,
        title: String,
        startsAtUTC: Int64,
        endsAtUTC: Int64,
        tzIdentifier: String,
        notes: String? = nil,
        source: EventSource,
        sourceUtterance: String? = nil,
        createdAt: Int64,
        updatedAt: Int64,
        deletedAt: Int64? = nil
    ) {
        self.id = id
        self.title = title
        self.startsAtUTC = startsAtUTC
        self.endsAtUTC = endsAtUTC
        self.tzIdentifier = tzIdentifier
        self.notes = notes
        self.source = source
        self.sourceUtterance = sourceUtterance
        self.createdAt = createdAt
        self.updatedAt = updatedAt
        self.deletedAt = deletedAt
    }

    public enum CodingKeys: String, CodingKey {
        case id
        case title
        case startsAtUTC      = "starts_at_utc"
        case endsAtUTC        = "ends_at_utc"
        case tzIdentifier     = "tz_identifier"
        case notes
        case source
        case sourceUtterance  = "source_utterance"
        case createdAt        = "created_at"
        case updatedAt        = "updated_at"
        case deletedAt        = "deleted_at"
    }
}

// MARK: - Reminder

/// One step of the escalation contract for a specific event.
public struct Reminder: Codable, Sendable, FetchableRecord, PersistableRecord, Equatable {

    public static let databaseTableName = "reminders"

    public var id: String
    public var eventID: String
    public var kind: ReminderKind
    public var fireAtUTC: Int64
    public var notificationID: String?
    public var status: ReminderStatus
    public var scheduledAt: Int64?
    public var firedAt: Int64?
    public var ackedAt: Int64?
    public var createdAt: Int64
    public var updatedAt: Int64

    public init(
        id: String,
        eventID: String,
        kind: ReminderKind,
        fireAtUTC: Int64,
        notificationID: String? = nil,
        status: ReminderStatus,
        scheduledAt: Int64? = nil,
        firedAt: Int64? = nil,
        ackedAt: Int64? = nil,
        createdAt: Int64,
        updatedAt: Int64
    ) {
        self.id = id
        self.eventID = eventID
        self.kind = kind
        self.fireAtUTC = fireAtUTC
        self.notificationID = notificationID
        self.status = status
        self.scheduledAt = scheduledAt
        self.firedAt = firedAt
        self.ackedAt = ackedAt
        self.createdAt = createdAt
        self.updatedAt = updatedAt
    }

    public enum CodingKeys: String, CodingKey {
        case id
        case eventID        = "event_id"
        case kind
        case fireAtUTC      = "fire_at_utc"
        case notificationID = "notification_id"
        case status
        case scheduledAt    = "scheduled_at"
        case firedAt        = "fired_at"
        case ackedAt        = "acked_at"
        case createdAt      = "created_at"
        case updatedAt      = "updated_at"
    }
}

// MARK: - MissedEvent

public struct MissedEvent: Codable, Sendable, FetchableRecord, PersistableRecord, Equatable {

    public static let databaseTableName = "missed_events"

    public var eventID: String
    public var missedAt: Int64
    public var surfacedInSummary: Bool
    public var rescheduledEventID: String?

    public init(
        eventID: String,
        missedAt: Int64,
        surfacedInSummary: Bool = false,
        rescheduledEventID: String? = nil
    ) {
        self.eventID = eventID
        self.missedAt = missedAt
        self.surfacedInSummary = surfacedInSummary
        self.rescheduledEventID = rescheduledEventID
    }

    public enum CodingKeys: String, CodingKey {
        case eventID             = "event_id"
        case missedAt            = "missed_at"
        case surfacedInSummary   = "surfaced_in_summary"
        case rescheduledEventID  = "rescheduled_event_id"
    }
}

// MARK: - Setting

/// Generic settings row. The key space is closed (see `SettingsKey`); any row with an
/// unknown key is ignored by the reader.
public struct Setting: Codable, Sendable, FetchableRecord, PersistableRecord, Equatable {

    public static let databaseTableName = "settings"

    public var key: String
    /// JSON-encoded value. Strings in v1 but we JSON-encode them so the column can hold
    /// structured values in future migrations without a schema change.
    public var value: String

    public init(key: String, value: String) {
        self.key = key
        self.value = value
    }
}

// MARK: - ActivityLogEntry

public struct ActivityLogEntry: Codable, Sendable, FetchableRecord, PersistableRecord, Equatable {

    public static let databaseTableName = "activity_log"

    public var id: Int64?
    public var atUTC: Int64
    public var kind: ActivityKind
    public var eventID: String?
    /// JSON string. Optional per kind.
    public var payload: String?

    public init(
        id: Int64? = nil,
        atUTC: Int64,
        kind: ActivityKind,
        eventID: String? = nil,
        payload: String? = nil
    ) {
        self.id = id
        self.atUTC = atUTC
        self.kind = kind
        self.eventID = eventID
        self.payload = payload
    }

    public enum CodingKeys: String, CodingKey {
        case id
        case atUTC    = "at_utc"
        case kind
        case eventID  = "event_id"
        case payload
    }

    public mutating func didInsert(_ inserted: InsertionSuccess) {
        id = inserted.rowID
    }
}

// MARK: - SchemaMetaEntry

public struct SchemaMetaEntry: Codable, Sendable, FetchableRecord, PersistableRecord, Equatable {

    public static let databaseTableName = "schema_meta"

    public var key: String
    public var value: String

    public init(key: String, value: String) {
        self.key = key
        self.value = value
    }
}
