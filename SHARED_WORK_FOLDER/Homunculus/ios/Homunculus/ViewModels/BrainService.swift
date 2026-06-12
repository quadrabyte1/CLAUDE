/// BrainService.swift
/// Observable service layer that owns:
///   - BrainClient (networking)
///   - ScheduleRegistrar (notification reconciliation)
///   - Reminder polling loop (60-second background timer)
///   - Health checking
///
/// Views observe this object's published properties via @Observable.
/// BrainClient is stateless; BrainService holds session state.
///
/// OPEN QUESTION (OQ-1): CaptureResponse does not echo ParsedIntent back.
/// This service stores pendingIntent locally after a /capture/text call
/// and includes it in the subsequent /capture/confirm.
/// See OPEN_QUESTIONS.md §OQ-1.

import Foundation
import Observation
import UserNotifications

@MainActor
@Observable
final class BrainService {

    // MARK: - Observed state

    /// True when the brain is reachable and has returned a successful /health check.
    var isOnline: Bool = false

    /// Non-nil when a capture has returned needs_confirmation.
    /// The client carries this intent to POST /capture/confirm.
    var pendingIntent: ParsedIntent? = nil

    /// The last CaptureResponse received (for the UI to display action + reply).
    var lastCaptureResponse: CaptureResponse? = nil

    /// The upcoming reminder rows returned by the last /reminders/upcoming pull.
    var upcomingReminders: [ReminderRow] = []

    /// Today's calendar events (from /events?day=YYYY-MM-DD).
    var todayEvents: [CalendarEvent] = []

    /// Non-nil when an error should be shown to the user.
    var errorMessage: String? = nil

    /// True while a capture request is in-flight.
    var isCapturing: Bool = false

    /// True while the app is doing a health check (startup).
    var isCheckingHealth: Bool = false

    // MARK: - Configuration

    var brainHost: String {
        didSet { rebuildBaseURL() }
    }
    var brainPort: Int {
        didSet { rebuildBaseURL() }
    }

    private(set) var baseURL: URL?

    // MARK: - Dependencies

    let client: BrainClient
    private var pollTask: Task<Void, Never>?

    // MARK: - Init

    init(client: BrainClient = BrainClient(),
         host: String = AppSettings.defaultBrainHost,
         port: Int = AppSettings.defaultBrainPort) {
        self.client    = client
        self.brainHost = host
        self.brainPort = port
        rebuildBaseURL()
    }

    // MARK: - URL management

    private func rebuildBaseURL() {
        baseURL = URL.brainBaseURL(host: brainHost, port: brainPort)
    }

    // MARK: - Startup

    /// Called on app launch and when foregrounding.
    /// Checks health, then refreshes reminders and today's events.
    func startup() async {
        await checkHealth()
        if isOnline {
            await refreshReminders()
            await refreshTodayEvents()
        }
        startPolling()
    }

    // MARK: - Health check

    func checkHealth() async {
        guard let url = baseURL else {
            isOnline = false
            errorMessage = "No brain URL configured. Open Settings and set the brain host."
            return
        }
        isCheckingHealth = true
        defer { isCheckingHealth = false }
        do {
            _ = try await client.health(baseURL: url)
            isOnline = true
            errorMessage = nil
        } catch {
            isOnline = false
            errorMessage = "Homunculus is offline — \(error.localizedDescription)"
        }
    }

    // MARK: - Capture

    /// Submit text to the brain.  Updates lastCaptureResponse and
    /// sets pendingIntent if confirmation is required.
    func capture(text: String) async {
        guard let url = baseURL else {
            errorMessage = "No brain URL configured."
            return
        }
        isCapturing = true
        defer { isCapturing = false }

        let speakerTz = TimeZone.current.identifier
        let request   = CaptureRequest(text: text, capturedAt: Date(), speakerTz: speakerTz)

        do {
            let response = try await client.captureText(request, baseURL: url)
            lastCaptureResponse = response

            // Use the echoed intent from brain v1.2.1 when available.
            // Fall back to the synthetic workaround if the brain is older (nil intent).
            // See OPEN_QUESTIONS.md §OQ-1 — this is now largely resolved.
            if response.action == .needsConfirmation {
                pendingIntent = response.intent ?? ParsedIntent.synthetic(from: response)
            } else {
                pendingIntent = nil
            }

            errorMessage = nil

            // After every capture, refresh reminders (brain may have added new ones).
            await refreshReminders()
            await refreshTodayEvents()

        } catch {
            errorMessage = "Capture failed: \(error.localizedDescription)"
        }
    }

    /// Confirm a pending calendar write.  Requires pendingIntent to be set.
    func confirmCapture() async {
        guard let url = baseURL, let intent = pendingIntent else {
            errorMessage = pendingIntent == nil ? "Nothing to confirm." : "No brain URL configured."
            return
        }
        isCapturing = true
        defer { isCapturing = false }

        let speakerTz = TimeZone.current.identifier
        let request   = ConfirmRequest(intent: intent, capturedAt: Date(), speakerTz: speakerTz)

        do {
            let response = try await client.captureConfirm(request, baseURL: url)
            lastCaptureResponse = response
            pendingIntent = nil
            errorMessage = nil

            await refreshReminders()
            await refreshTodayEvents()

        } catch {
            errorMessage = "Confirm failed: \(error.localizedDescription)"
        }
    }

    /// Cancel a pending confirmation.
    func cancelCapture() {
        pendingIntent = nil
        lastCaptureResponse = nil
    }

    // MARK: - Reminders

    /// Pull /reminders/upcoming and reconcile with UNUserNotificationCenter.
    func refreshReminders() async {
        guard let url = baseURL else { return }
        do {
            let rows = try await client.remindersUpcoming(baseURL: url)
            upcomingReminders = rows
            await ScheduleRegistrar.shared.reconcile(with: rows)
        } catch {
            // Non-fatal: reminders are local, just log.
            // Don't overwrite errorMessage here as a capture error is more important.
        }
    }

    // MARK: - Events

    func refreshTodayEvents() async {
        guard let url = baseURL else { return }
        let formatter = DateFormatter()
        formatter.dateFormat = "yyyy-MM-dd"
        let today = formatter.string(from: Date())
        do {
            todayEvents = try await client.events(baseURL: url, day: today)
        } catch {
            // Non-fatal
        }
    }

    // MARK: - Ack

    /// POST /ack for a reminder.  Called from the NotificationDelegate on "OK" tap.
    func ack(_ request: AckRequest) async throws -> AckResponse {
        guard let url = baseURL else {
            throw BrainError.invalidURL("no base URL")
        }
        return try await client.ack(request, baseURL: url)
    }

    // MARK: - Background polling

    /// Start a 60-second background polling loop for /reminders/upcoming.
    /// Cancels any existing loop first.
    ///
    /// The Task is created on the MainActor and inherits the actor context,
    /// so `self` does not cross actor boundaries inside the loop body.
    /// Using unowned(unsafe) is avoided: we cancel the task in deinit-adjacent
    /// situations (stopPolling) so the reference lifecycle is safe.
    func startPolling() {
        pollTask?.cancel()
        pollTask = Task { @MainActor [weak self] in
            while !Task.isCancelled {
                try? await Task.sleep(nanoseconds: 60_000_000_000) // 60 seconds
                guard !Task.isCancelled, let self else { break }
                await self.refreshReminders()
            }
        }
    }

    func stopPolling() {
        pollTask?.cancel()
        pollTask = nil
    }
}

// MARK: - ParsedIntent synthetic construction

extension ParsedIntent {
    /// Build a minimal ParsedIntent from a CaptureResponse for use in /capture/confirm.
    ///
    /// OQ-1 WORKAROUND: The brain's CaptureResponse does not echo back the ParsedIntent
    /// it derived from the text.  We construct a synthetic ParsedIntent with the fields
    /// we CAN recover from CaptureResponse (kind, confidence, raw_text).
    ///
    /// The brain's /capture/confirm runs commit_calendar_event(intent, ...) which uses
    /// intent.raw_text to re-resolve date/time, so the round-trip is mostly safe as long
    /// as the LLM gives the same parse on the second call (which is likely but not guaranteed
    /// because the model is non-deterministic).
    ///
    /// RISK: Non-deterministic LLM may produce a different parse on confirm, causing
    /// a different event time than the readback announced.
    /// MITIGATION: When Rune adds intent echo in v1.3, remove this workaround entirely.
    ///
    /// See OPEN_QUESTIONS.md §OQ-1.
    static func synthetic(from response: CaptureResponse) -> ParsedIntent {
        // Use JSONDecoder with a synthetic JSON payload built from what we know.
        // This avoids duplicating init logic and is robust to future field additions.
        let json: [String: Any] = [
            "kind":             response.kind.rawValue,
            "confidence":       response.confidence.rawValue,
            "raw_text":         response.rawText,
            "people":           [String](),
            "tags":             [String](),
            "ambiguous_fields": [String]()
        ]
        // swiftlint:disable force_try force_cast
        let data   = try! JSONSerialization.data(withJSONObject: json)
        let intent = try! BrainClient.decoder.decode(ParsedIntent.self, from: data)
        // swiftlint:enable force_try force_cast
        return intent
    }
}
