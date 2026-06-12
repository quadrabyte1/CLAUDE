/// BrainClient.swift
/// URLSession-based HTTP client for the Homunculus brain.
///
/// All requests go to the brain at the Tailscale tailnet address configured
/// in Settings.  HTTP (not HTTPS) — Tailscale is the trust boundary.
/// App Transport Security exception for the tailnet host must be declared
/// in Info.plist (NSAppTransportSecurity → NSExceptionDomains).
///
/// Thread-safety: All async methods can be called from any actor context.
/// URLSession is already concurrency-safe.

import Foundation

// MARK: - Error Type

enum BrainError: LocalizedError, Equatable {
    case unreachable(String)
    case badStatus(Int, String)
    case decodingFailure(String)
    case encodingFailure(String)
    case invalidURL(String)

    var errorDescription: String? {
        switch self {
        case .unreachable(let msg):
            return "Brain unreachable: \(msg)"
        case .badStatus(let code, let msg):
            return "Brain returned HTTP \(code): \(msg)"
        case .decodingFailure(let msg):
            return "Couldn't parse brain response: \(msg)"
        case .encodingFailure(let msg):
            return "Couldn't encode request: \(msg)"
        case .invalidURL(let url):
            return "Invalid brain URL: \(url)"
        }
    }
}

// MARK: - Client

/// Low-level brain API client.  Contains no state except the shared JSONDecoder/Encoder.
/// Callers provide the base URL so it can be tested without a real brain.
final class BrainClient: Sendable {

    // MARK: Shared JSON plumbing

    static let decoder: JSONDecoder = {
        let d = JSONDecoder()
        d.dateDecodingStrategy = .custom { decoder in
            let container = try decoder.singleValueContainer()
            let string = try container.decode(String.self)
            // Brain sends ISO 8601 with timezone offset, e.g. "2026-06-12T10:00:00-04:00"
            if let date = ISO8601DateFormatter.brainFormatter.date(from: string) {
                return date
            }
            // Fallback: try fractional seconds
            if let date = ISO8601DateFormatter.brainFormatterFractional.date(from: string) {
                return date
            }
            throw DecodingError.dataCorruptedError(
                in: container,
                debugDescription: "Cannot parse date: \(string)"
            )
        }
        return d
    }()

    static let encoder: JSONEncoder = {
        let e = JSONEncoder()
        e.dateEncodingStrategy = .custom { date, encoder in
            var container = encoder.singleValueContainer()
            try container.encode(ISO8601DateFormatter.brainFormatter.string(from: date))
        }
        return e
    }()

    // MARK: Init

    private let session: URLSession

    init(session: URLSession = .shared) {
        self.session = session
    }

    // MARK: - API Methods

    /// GET /health — confirms the brain is reachable and returns version info.
    func health(baseURL: URL) async throws -> HealthResponse {
        let url = baseURL.appendingPathComponent("health")
        return try await get(url: url)
    }

    /// POST /capture/text — send a text capture to the brain.
    /// Returns the action the UI must perform.
    func captureText(_ request: CaptureRequest, baseURL: URL) async throws -> CaptureResponse {
        let url = baseURL.appendingPathComponent("capture/text")
        return try await post(url: url, body: request)
    }

    /// POST /capture/confirm — confirm a calendar write after readback.
    func captureConfirm(_ request: ConfirmRequest, baseURL: URL) async throws -> CaptureResponse {
        let url = baseURL.appendingPathComponent("capture/confirm")
        return try await post(url: url, body: request)
    }

    /// GET /reminders/upcoming — pull the next window_hours of reminder schedule.
    /// Default window: 72 hours.
    func remindersUpcoming(baseURL: URL, windowHours: Int = 72) async throws -> [ReminderRow] {
        var components = URLComponents(url: baseURL.appendingPathComponent("reminders/upcoming"),
                                       resolvingAgainstBaseURL: false)!
        components.queryItems = [URLQueryItem(name: "window_hours", value: String(windowHours))]
        guard let url = components.url else {
            throw BrainError.invalidURL("reminders/upcoming with window_hours=\(windowHours)")
        }
        return try await get(url: url)
    }

    /// POST /ack — acknowledge a reminder; brain cancels remaining strike chain.
    func ack(_ request: AckRequest, baseURL: URL) async throws -> AckResponse {
        let url = baseURL.appendingPathComponent("ack")
        return try await post(url: url, body: request)
    }

    /// GET /events?day=YYYY-MM-DD — list events for a specific day.
    func events(baseURL: URL, day: String? = nil) async throws -> [CalendarEvent] {
        var components = URLComponents(url: baseURL.appendingPathComponent("events"),
                                       resolvingAgainstBaseURL: false)!
        if let day {
            components.queryItems = [URLQueryItem(name: "day", value: day)]
        }
        guard let url = components.url else {
            throw BrainError.invalidURL("events")
        }
        return try await get(url: url)
    }

    // MARK: - Private HTTP Primitives

    private func get<T: Decodable>(url: URL) async throws -> T {
        let request = URLRequest(url: url, cachePolicy: .reloadIgnoringLocalCacheData, timeoutInterval: 15)
        return try await perform(request)
    }

    private func post<B: Encodable, T: Decodable>(url: URL, body: B) async throws -> T {
        var request = URLRequest(url: url, cachePolicy: .reloadIgnoringLocalCacheData, timeoutInterval: 30)
        request.httpMethod = "POST"
        request.setValue("application/json", forHTTPHeaderField: "Content-Type")
        do {
            request.httpBody = try Self.encoder.encode(body)
        } catch {
            throw BrainError.encodingFailure(error.localizedDescription)
        }
        return try await perform(request)
    }

    private func perform<T: Decodable>(_ request: URLRequest) async throws -> T {
        let data: Data
        let response: URLResponse
        do {
            (data, response) = try await session.data(for: request)
        } catch let urlError as URLError {
            throw BrainError.unreachable(urlError.localizedDescription)
        } catch {
            throw BrainError.unreachable(error.localizedDescription)
        }

        if let http = response as? HTTPURLResponse {
            guard (200..<300).contains(http.statusCode) else {
                let body = String(data: data, encoding: .utf8) ?? "<binary>"
                throw BrainError.badStatus(http.statusCode, body)
            }
        }

        do {
            return try Self.decoder.decode(T.self, from: data)
        } catch {
            let raw = String(data: data, encoding: .utf8) ?? "<binary>"
            throw BrainError.decodingFailure("\(error.localizedDescription) — raw: \(raw.prefix(200))")
        }
    }
}

// MARK: - ISO8601 Helpers

extension ISO8601DateFormatter {
    /// Formatter that handles timezone-offset ISO 8601 dates the brain emits.
    static let brainFormatter: ISO8601DateFormatter = {
        let f = ISO8601DateFormatter()
        f.formatOptions = [.withInternetDateTime, .withColonSeparatorInTimeZone]
        return f
    }()

    /// Formatter that also handles fractional seconds (some Python datetimes include them).
    static let brainFormatterFractional: ISO8601DateFormatter = {
        let f = ISO8601DateFormatter()
        f.formatOptions = [.withInternetDateTime, .withFractionalSeconds, .withColonSeparatorInTimeZone]
        return f
    }()
}

// MARK: - URL Convenience

extension URL {
    /// Build a base URL from host + port.
    static func brainBaseURL(host: String, port: Int = 8765) -> URL? {
        var components = URLComponents()
        components.scheme = "http"
        components.host   = host
        components.port   = port
        components.path   = "/"
        return components.url
    }
}
