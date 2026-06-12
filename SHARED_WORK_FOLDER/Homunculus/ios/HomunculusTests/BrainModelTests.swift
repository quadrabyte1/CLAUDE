/// BrainModelTests.swift
/// Swift Testing suite for JSON encoding/decoding of brain wire types.
///
/// These tests are the first line of defence against schema drift between
/// the Python brain (schemas.py) and the Swift client (BrainModels.swift).
/// Run them whenever schemas.py changes.

import Testing
import Foundation
@testable import Homunculus

@Suite("BrainModel JSON round-trips")
struct BrainModelTests {

    // MARK: - ReminderRow

    @Test("ReminderRow decodes from brain JSON")
    func reminderRowDecodes() throws {
        let json = """
        {
          "event_id": "2026-06-12-coffee-with-jane",
          "kind": "strike_0",
          "fire_at": "2026-06-12T10:00:00-04:00",
          "tz": "America/New_York",
          "body": "Coffee with Jane is now.",
          "status": "pending"
        }
        """.data(using: .utf8)!

        let row = try BrainClient.decoder.decode(ReminderRow.self, from: json)
        #expect(row.eventId == "2026-06-12-coffee-with-jane")
        #expect(row.kind    == .strike0)
        #expect(row.tz      == "America/New_York")
        #expect(row.id      == "2026-06-12-coffee-with-jane:strike_0")
        #expect(row.kind.isUrgent == true)
    }

    @Test("ReminderRow.id is eventId:kind")
    func reminderRowID() throws {
        let json = """
        {
          "event_id": "summary.2026-06-12",
          "kind": "morning_summary",
          "fire_at": "2026-06-12T07:00:00-04:00",
          "tz": "America/New_York",
          "body": "Good morning.",
          "status": "pending"
        }
        """.data(using: .utf8)!

        let row = try BrainClient.decoder.decode(ReminderRow.self, from: json)
        #expect(row.id == "summary.2026-06-12:morning_summary")
        #expect(row.kind.isUrgent == false)
    }

    @Test("ReminderKind isUrgent classification")
    func reminderKindUrgency() {
        #expect(ReminderKind.strike0.isUrgent  == true)
        #expect(ReminderKind.strike5.isUrgent  == true)
        #expect(ReminderKind.strike10.isUrgent == true)
        #expect(ReminderKind.strike15.isUrgent == true)
        #expect(ReminderKind.pre5.isUrgent     == true)
        #expect(ReminderKind.headsUp30.isUrgent    == false)
        #expect(ReminderKind.morningSummary.isUrgent == false)
    }

    // MARK: - CaptureResponse

    @Test("CaptureResponse decodes wrote action")
    func captureResponseWrote() throws {
        let json = """
        {
          "kind": "calendar_event",
          "confidence": "high",
          "action": "wrote",
          "spoken_reply": "Got it, coffee Thursday at 10.",
          "written_path": null,
          "conflicts": {"has_direct_conflict": false, "has_fuzzy_conflict": false, "direct": [], "fuzzy": []},
          "clarifying_question": null,
          "raw_text": "coffee Thursday at 10"
        }
        """.data(using: .utf8)!

        let resp = try BrainClient.decoder.decode(CaptureResponse.self, from: json)
        #expect(resp.action      == .wrote)
        #expect(resp.kind        == .calendarEvent)
        #expect(resp.confidence  == .high)
        #expect(resp.spokenReply == "Got it, coffee Thursday at 10.")
    }

    @Test("CaptureResponse decodes needs_confirmation with echoed intent (brain v1.2.1+)")
    func captureResponseNeedsConfirmationWithIntent() throws {
        let json = """
        {
          "kind": "calendar_event",
          "confidence": "high",
          "action": "needs_confirmation",
          "spoken_reply": "Thursday June 12 at 10 AM for 60 minutes. Sound right?",
          "written_path": null,
          "conflicts": {"has_direct_conflict": false, "has_fuzzy_conflict": false, "direct": [], "fuzzy": []},
          "clarifying_question": null,
          "raw_text": "coffee Thursday at 10",
          "intent": {
            "kind": "calendar_event",
            "confidence": "high",
            "raw_text": "coffee Thursday at 10",
            "title": "Coffee",
            "day_hint": "Thursday",
            "time_hint": "10am",
            "people": [],
            "tags": [],
            "ambiguous_fields": []
          }
        }
        """.data(using: .utf8)!

        let resp = try BrainClient.decoder.decode(CaptureResponse.self, from: json)
        #expect(resp.action == .needsConfirmation)
        #expect(resp.intent != nil)
        #expect(resp.intent?.title == "Coffee")
        #expect(resp.intent?.dayHint == "Thursday")
    }

    @Test("CaptureResponse decodes needs_confirmation without intent (brain v1.2 compat)")
    func captureResponseNeedsConfirmationNoIntent() throws {
        let json = """
        {
          "kind": "calendar_event",
          "confidence": "high",
          "action": "needs_confirmation",
          "spoken_reply": "Thursday June 12 at 10 AM for 60 minutes. Sound right?",
          "written_path": null,
          "conflicts": {"has_direct_conflict": false, "has_fuzzy_conflict": false, "direct": [], "fuzzy": []},
          "clarifying_question": null,
          "raw_text": "coffee Thursday at 10"
        }
        """.data(using: .utf8)!

        let resp = try BrainClient.decoder.decode(CaptureResponse.self, from: json)
        #expect(resp.action == .needsConfirmation)
        #expect(resp.intent == nil)
    }

    @Test("CaptureResponse decodes needs_clarification with question")
    func captureResponseNeedsClarification() throws {
        let json = """
        {
          "kind": "calendar_event",
          "confidence": "medium",
          "action": "needs_clarification",
          "spoken_reply": "What time?",
          "written_path": null,
          "conflicts": null,
          "clarifying_question": "What time did you want to meet?",
          "raw_text": "coffee Thursday"
        }
        """.data(using: .utf8)!

        let resp = try BrainClient.decoder.decode(CaptureResponse.self, from: json)
        #expect(resp.action             == .needsClarification)
        #expect(resp.clarifyingQuestion == "What time did you want to meet?")
    }

    @Test("CaptureResponse decodes inbox action")
    func captureResponseInbox() throws {
        let json = """
        {
          "kind": "unknown",
          "confidence": "low",
          "action": "inbox",
          "spoken_reply": "Filed to inbox.",
          "written_path": null,
          "conflicts": null,
          "clarifying_question": null,
          "raw_text": "blah blah"
        }
        """.data(using: .utf8)!

        let resp = try BrainClient.decoder.decode(CaptureResponse.self, from: json)
        #expect(resp.action == .inbox)
        #expect(resp.kind   == .unknown)
    }

    // MARK: - AckResponse

    @Test("AckResponse decodes with cancelled_kinds")
    func ackResponseDecodes() throws {
        let json = """
        {
          "event_id": "2026-06-12-coffee-with-jane",
          "acked_kind": "strike_0",
          "cancelled_kinds": ["strike_5", "strike_10", "strike_15"],
          "rows": []
        }
        """.data(using: .utf8)!

        let resp = try BrainClient.decoder.decode(AckResponse.self, from: json)
        #expect(resp.eventId         == "2026-06-12-coffee-with-jane")
        #expect(resp.ackedKind       == .strike0)
        #expect(resp.cancelledKinds  == [.strike5, .strike10, .strike15])
    }

    @Test("AckResponse handles empty cancelled_kinds (idempotent double-ack)")
    func ackResponseEmpty() throws {
        let json = """
        {
          "event_id": "2026-06-12-coffee-with-jane",
          "acked_kind": "strike_0",
          "cancelled_kinds": [],
          "rows": []
        }
        """.data(using: .utf8)!

        let resp = try BrainClient.decoder.decode(AckResponse.self, from: json)
        #expect(resp.cancelledKinds.isEmpty)
    }

    // MARK: - ParsedIntent

    @Test("ParsedIntent decodes with optional fields absent")
    func parsedIntentDecodes() throws {
        let json = """
        {
          "kind": "calendar_event",
          "confidence": "high",
          "raw_text": "coffee Thursday at 10",
          "people": [],
          "tags": [],
          "ambiguous_fields": []
        }
        """.data(using: .utf8)!

        let intent = try BrainClient.decoder.decode(ParsedIntent.self, from: json)
        #expect(intent.kind       == .calendarEvent)
        #expect(intent.confidence == .high)
        #expect(intent.people.isEmpty)
        #expect(intent.title      == nil)
    }

    @Test("CaptureRequest encodes with snake_case keys")
    func captureRequestEncodes() throws {
        let req  = CaptureRequest(text: "hello", speakerTz: "America/New_York")
        let data = try BrainClient.encoder.encode(req)
        let dict = try JSONSerialization.jsonObject(with: data) as! [String: Any]

        #expect(dict["text"]       as? String == "hello")
        #expect(dict["speaker_tz"] as? String == "America/New_York")
    }

    // MARK: - HealthResponse

    @Test("HealthResponse decodes design_version")
    func healthResponseDecodes() throws {
        let json = """
        {
          "status": "ok",
          "design_version": "1.2",
          "package_version": "1.0.0",
          "vault_path": "/Users/boss/vault"
        }
        """.data(using: .utf8)!

        let resp = try BrainClient.decoder.decode(HealthResponse.self, from: json)
        #expect(resp.status        == "ok")
        #expect(resp.designVersion == "1.2")
    }

    // MARK: - Date decoding

    @Test("ISO 8601 with timezone offset decodes correctly")
    func dateDecoding() throws {
        // The brain emits dates like "2026-06-12T10:00:00-04:00"
        let json = """
        {
          "event_id": "test",
          "kind": "strike_0",
          "fire_at": "2026-06-12T10:00:00-04:00",
          "tz": "America/New_York",
          "body": "Test",
          "status": "pending"
        }
        """.data(using: .utf8)!

        let row = try BrainClient.decoder.decode(ReminderRow.self, from: json)
        // 10:00 AM EDT = 14:00 UTC
        let utcCalendar = Calendar.current
        var components  = DateComponents(timeZone: TimeZone(identifier: "UTC"),
                                         year: 2026, month: 6, day: 12,
                                         hour: 14, minute: 0, second: 0)
        let expectedUTC = utcCalendar.date(from: components)!
        #expect(abs(row.fireAt.timeIntervalSince(expectedUTC)) < 1.0)
    }

    // MARK: - URL builder

    @Test("brainBaseURL builds correct URL")
    func brainBaseURL() {
        let url = URL.brainBaseURL(host: "mac-mini.frosty-llama.ts.net", port: 8765)
        #expect(url != nil)
        #expect(url?.scheme == "http")
        #expect(url?.host   == "mac-mini.frosty-llama.ts.net")
        #expect(url?.port   == 8765)
    }

    @Test("reminders/upcoming URL includes window_hours query param")
    func remindersUpcomingURL() throws {
        let base   = URL.brainBaseURL(host: "mac-mini.test.ts.net", port: 8765)!
        var comps  = URLComponents(url: base.appendingPathComponent("reminders/upcoming"),
                                    resolvingAgainstBaseURL: false)!
        comps.queryItems = [URLQueryItem(name: "window_hours", value: "72")]
        let url    = try #require(comps.url)
        #expect(url.absoluteString.contains("window_hours=72"))
    }
}
