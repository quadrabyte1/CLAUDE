/// BrainModels.swift
/// Swift mirror of the brain's Pydantic schemas (schemas.py).
///
/// Source of truth: Homunculus/brain/homunculus_brain/schemas.py
/// Keep these in sync when the brain schema changes.
///
/// NOTE (open question for v1.3): CaptureResponse does not echo the ParsedIntent
/// the brain derived from the text.  The client must hold the ParsedIntent locally
/// between /capture/text and /capture/confirm.  See OPEN_QUESTIONS.md §OQ-1.

import Foundation

// MARK: - Enumerations

/// Maps to Python IntentKind enum.
enum IntentKind: String, Codable, CaseIterable {
    case calendarEvent    = "calendar_event"
    case toolNote         = "tool_note"
    case promptNote       = "prompt_note"
    case calendarQuery    = "calendar_query"
    case unknown          = "unknown"
}

/// Maps to Python Confidence enum.
enum Confidence: String, Codable {
    case high   = "high"
    case medium = "medium"
    case low    = "low"
}

/// Maps to Python ReminderKind enum.
/// Order matches escalation chain: summary → heads_up_30 → pre_5 → strikes.
enum ReminderKind: String, Codable, CaseIterable {
    case morningSummary = "morning_summary"
    case headsUp30      = "heads_up_30"
    case pre5           = "pre_5"
    case strike0        = "strike_0"
    case strike5        = "strike_5"
    case strike10       = "strike_10"
    case strike15       = "strike_15"

    /// Returns true for strike kinds and pre_5 — these get .timeSensitive
    /// interruption level so they pierce Focus modes (per design v1.2 UX).
    var isUrgent: Bool {
        switch self {
        case .pre5, .strike0, .strike5, .strike10, .strike15:
            return true
        case .morningSummary, .headsUp30:
            return false
        }
    }
}

// MARK: - Core Models

/// Maps to Python ParsedIntent.
/// This is carried client-side between /capture/text and /capture/confirm
/// because CaptureResponse does not echo it back (see OPEN_QUESTIONS.md §OQ-1).
struct ParsedIntent: Codable, Equatable {
    let kind: IntentKind
    let confidence: Confidence
    var title: String?
    var dayHint: String?
    var timeHint: String?
    var durationMinutes: Int?
    var people: [String]
    var tags: [String]
    let rawText: String
    var ambiguousFields: [String]
    var body: String?

    enum CodingKeys: String, CodingKey {
        case kind
        case confidence
        case title
        case dayHint          = "day_hint"
        case timeHint         = "time_hint"
        case durationMinutes  = "duration_minutes"
        case people
        case tags
        case rawText          = "raw_text"
        case ambiguousFields  = "ambiguous_fields"
        case body
    }

    // Provide defaults for array fields that are empty by default.
    init(from decoder: Decoder) throws {
        let c = try decoder.container(keyedBy: CodingKeys.self)
        kind             = try c.decode(IntentKind.self, forKey: .kind)
        confidence       = try c.decode(Confidence.self, forKey: .confidence)
        title            = try c.decodeIfPresent(String.self, forKey: .title)
        dayHint          = try c.decodeIfPresent(String.self, forKey: .dayHint)
        timeHint         = try c.decodeIfPresent(String.self, forKey: .timeHint)
        durationMinutes  = try c.decodeIfPresent(Int.self, forKey: .durationMinutes)
        people           = (try? c.decode([String].self, forKey: .people)) ?? []
        tags             = (try? c.decode([String].self, forKey: .tags)) ?? []
        rawText          = try c.decode(String.self, forKey: .rawText)
        ambiguousFields  = (try? c.decode([String].self, forKey: .ambiguousFields)) ?? []
        body             = try c.decodeIfPresent(String.self, forKey: .body)
    }
}

/// Maps to Python ConflictReport.
struct ConflictReport: Codable, Equatable {
    let hasDirectConflict: Bool
    let hasFuzzyConflict: Bool
    let direct: [CalendarEvent]
    let fuzzy: [CalendarEvent]

    enum CodingKeys: String, CodingKey {
        case hasDirectConflict = "has_direct_conflict"
        case hasFuzzyConflict  = "has_fuzzy_conflict"
        case direct
        case fuzzy
    }

    init(from decoder: Decoder) throws {
        let c = try decoder.container(keyedBy: CodingKeys.self)
        hasDirectConflict = try c.decode(Bool.self, forKey: .hasDirectConflict)
        hasFuzzyConflict  = try c.decode(Bool.self, forKey: .hasFuzzyConflict)
        direct            = (try? c.decode([CalendarEvent].self, forKey: .direct)) ?? []
        fuzzy             = (try? c.decode([CalendarEvent].self, forKey: .fuzzy)) ?? []
    }
}

/// Maps to Python CalendarEvent (used inside ConflictReport).
struct CalendarEvent: Codable, Identifiable, Equatable {
    let id: String
    let title: String
    let startsAt: Date
    let endsAt: Date
    let tz: String
    let durationMinutes: Int
    let people: [String]
    let tags: [String]
    let source: String
    let sourceUtterance: String?
    let createdAt: Date
    let updatedAt: Date

    enum CodingKeys: String, CodingKey {
        case id
        case title
        case startsAt         = "starts_at"
        case endsAt           = "ends_at"
        case tz
        case durationMinutes  = "duration_minutes"
        case people
        case tags
        case source
        case sourceUtterance  = "source_utterance"
        case createdAt        = "created_at"
        case updatedAt        = "updated_at"
    }

    init(from decoder: Decoder) throws {
        let c = try decoder.container(keyedBy: CodingKeys.self)
        id               = try c.decode(String.self, forKey: .id)
        title            = try c.decode(String.self, forKey: .title)
        startsAt         = try c.decode(Date.self, forKey: .startsAt)
        endsAt           = try c.decode(Date.self, forKey: .endsAt)
        tz               = try c.decode(String.self, forKey: .tz)
        durationMinutes  = try c.decode(Int.self, forKey: .durationMinutes)
        people           = (try? c.decode([String].self, forKey: .people)) ?? []
        tags             = (try? c.decode([String].self, forKey: .tags)) ?? []
        source           = try c.decode(String.self, forKey: .source)
        sourceUtterance  = try c.decodeIfPresent(String.self, forKey: .sourceUtterance)
        createdAt        = try c.decode(Date.self, forKey: .createdAt)
        updatedAt        = try c.decode(Date.self, forKey: .updatedAt)
    }
}

// MARK: - API Request/Response Types

/// Maps to Python CaptureRequest.
struct CaptureRequest: Codable {
    let text: String
    let capturedAt: Date?
    let speakerTz: String?

    enum CodingKeys: String, CodingKey {
        case text
        case capturedAt  = "captured_at"
        case speakerTz   = "speaker_tz"
    }

    init(text: String, capturedAt: Date? = nil, speakerTz: String? = nil) {
        self.text       = text
        self.capturedAt = capturedAt
        self.speakerTz  = speakerTz
    }
}

/// The action the client must take after receiving a CaptureResponse.
enum CaptureAction: String, Codable {
    case wrote              = "wrote"
    case needsConfirmation  = "needs_confirmation"
    case needsClarification = "needs_clarification"
    case inbox              = "inbox"
}

/// Maps to Python CaptureResponse.
///
/// Brain v1.2.1 added `intent: Optional[ParsedIntent]` — the structured parse
/// the brain derived from the utterance.  When present, this should be used
/// verbatim in the /capture/confirm body (eliminating the need for the
/// synthetic-intent workaround in BrainService).  See OPEN_QUESTIONS.md §OQ-1.
struct CaptureResponse: Codable {
    let kind: IntentKind
    let confidence: Confidence
    let action: CaptureAction
    let spokenReply: String
    let writtenPath: String?
    let conflicts: ConflictReport?
    let clarifyingQuestion: String?
    let rawText: String
    /// Echoed-back ParsedIntent (added in brain v1.2.1).  When non-nil, use
    /// this directly in /capture/confirm instead of the synthetic workaround.
    let intent: ParsedIntent?

    enum CodingKeys: String, CodingKey {
        case kind
        case confidence
        case action
        case spokenReply        = "spoken_reply"
        case writtenPath        = "written_path"
        case conflicts
        case clarifyingQuestion = "clarifying_question"
        case rawText            = "raw_text"
        case intent
    }

    init(from decoder: Decoder) throws {
        let c               = try decoder.container(keyedBy: CodingKeys.self)
        kind                = try c.decode(IntentKind.self, forKey: .kind)
        confidence          = try c.decode(Confidence.self, forKey: .confidence)
        action              = try c.decode(CaptureAction.self, forKey: .action)
        spokenReply         = try c.decode(String.self, forKey: .spokenReply)
        writtenPath         = try c.decodeIfPresent(String.self, forKey: .writtenPath)
        conflicts           = try c.decodeIfPresent(ConflictReport.self, forKey: .conflicts)
        clarifyingQuestion  = try c.decodeIfPresent(String.self, forKey: .clarifyingQuestion)
        rawText             = try c.decode(String.self, forKey: .rawText)
        intent              = try c.decodeIfPresent(ParsedIntent.self, forKey: .intent)
    }
}

/// Maps to Python ConfirmRequest (defined in server.py, not schemas.py).
struct ConfirmRequest: Codable {
    let intent: ParsedIntent
    let capturedAt: Date?
    let speakerTz: String?

    enum CodingKeys: String, CodingKey {
        case intent
        case capturedAt  = "captured_at"
        case speakerTz   = "speaker_tz"
    }

    init(intent: ParsedIntent, capturedAt: Date? = nil, speakerTz: String? = nil) {
        self.intent     = intent
        self.capturedAt = capturedAt
        self.speakerTz  = speakerTz
    }
}

/// Maps to Python ReminderRow.
struct ReminderRow: Codable, Identifiable, Equatable {
    /// Computed identifier — the local UNNotificationRequest identifier.
    /// Format: "<event_id>:<kind>" (e.g. "2026-06-12-coffee:strike_0")
    var id: String { "\(eventId):\(kind.rawValue)" }

    let eventId: String
    let kind: ReminderKind
    let fireAt: Date
    let tz: String
    let body: String
    let status: String

    enum CodingKeys: String, CodingKey {
        case eventId = "event_id"
        case kind
        case fireAt  = "fire_at"
        case tz
        case body
        case status
    }

    init(from decoder: Decoder) throws {
        let c   = try decoder.container(keyedBy: CodingKeys.self)
        eventId = try c.decode(String.self, forKey: .eventId)
        kind    = try c.decode(ReminderKind.self, forKey: .kind)
        fireAt  = try c.decode(Date.self, forKey: .fireAt)
        tz      = try c.decode(String.self, forKey: .tz)
        body    = try c.decode(String.self, forKey: .body)
        status  = try c.decode(String.self, forKey: .status)
    }
}

/// Maps to Python AckRequest.
struct AckRequest: Codable {
    let eventId: String
    let kind: ReminderKind
    let ackedAt: Date?

    enum CodingKeys: String, CodingKey {
        case eventId  = "event_id"
        case kind
        case ackedAt  = "acked_at"
    }

    init(eventId: String, kind: ReminderKind, ackedAt: Date? = nil) {
        self.eventId = eventId
        self.kind    = kind
        self.ackedAt = ackedAt
    }
}

/// Maps to Python AckResponse.
struct AckResponse: Codable {
    let eventId: String
    let ackedKind: ReminderKind
    let cancelledKinds: [ReminderKind]
    let rows: [ReminderRow]

    enum CodingKeys: String, CodingKey {
        case eventId        = "event_id"
        case ackedKind      = "acked_kind"
        case cancelledKinds = "cancelled_kinds"
        case rows
    }

    init(from decoder: Decoder) throws {
        let c            = try decoder.container(keyedBy: CodingKeys.self)
        eventId          = try c.decode(String.self, forKey: .eventId)
        ackedKind        = try c.decode(ReminderKind.self, forKey: .ackedKind)
        cancelledKinds   = (try? c.decode([ReminderKind].self, forKey: .cancelledKinds)) ?? []
        rows             = (try? c.decode([ReminderRow].self, forKey: .rows)) ?? []
    }
}

/// Maps to Python HealthResponse.
struct HealthResponse: Codable {
    let status: String
    let designVersion: String
    let packageVersion: String
    let vaultPath: String

    enum CodingKeys: String, CodingKey {
        case status
        case designVersion  = "design_version"
        case packageVersion = "package_version"
        case vaultPath      = "vault_path"
    }
}
