/// ScheduleRegistrar.swift
/// Reconciles the brain's reminder schedule with iOS's UNUserNotificationCenter.
///
/// THIS IS THE CRITICAL PIECE (per task brief).
///
/// The brain is the source of truth for what reminders should exist.
/// The phone's UNUserNotificationCenter is a local cache.
/// This registrar keeps them in sync on every pull.
///
/// Reconciliation algorithm:
///
///   brainIDs = set of "<event_id>:<kind>" from /reminders/upcoming
///   localIDs = set of pending UNNotificationRequest identifiers
///   (filtered to only those managed by this app using the known prefixes)
///
///   TO ADD:   brainIDs - localIDs   (brain has it, local doesn't → register)
///   TO REMOVE: localIDs - brainIDs  (local has it, brain dropped it → cancel)
///
/// This means:
///   - If the user acks a reminder and the brain cancels later strikes,
///     the next reconciliation will see those IDs missing from the brain
///     response and remove them from UNUserNotificationCenter.
///   - If an event is deleted on the Mac, all its reminder IDs vanish from
///     the brain response and they get cleaned up on the next pull.
///   - If the phone was offline and missed registrations, the next foreground
///     pull catches up.
///
/// IMPORTANT: We never touch UNNotificationRequests whose identifiers we
/// don't recognise (they might belong to other apps or system features).
/// We only manage requests in the "HOMUNCULUS" namespace.

import Foundation
import UserNotifications

// MARK: - Category / Action setup

/// The notification category identifier shared between ScheduleRegistrar and
/// the app delegate notification handler.
let homunculusNotificationCategoryID = "HOMUNCULUS_EVENT"

/// The action identifier for the "OK" ack button.
let homunculusAckActionID = "ACK"

extension UNUserNotificationCenter {
    /// Register the HOMUNCULUS_EVENT category with its single "OK" action.
    /// Call this once from the AppDelegate (or App scene delegate) so it is
    /// set before the first notification fires.
    func registerHomunculusCategory() {
        let ackAction = UNNotificationAction(
            identifier: homunculusAckActionID,
            title: "OK",
            options: [.foreground]   // brings app to foreground so ack POST can run
        )
        let category = UNNotificationCategory(
            identifier: homunculusNotificationCategoryID,
            actions: [ackAction],
            intentIdentifiers: [],
            options: []
        )
        setNotificationCategories([category])
    }
}

// MARK: - Registrar

/// Stateless helper — all state is held by UNUserNotificationCenter.
/// Marked @MainActor because UNUserNotificationCenter callbacks can
/// dispatch on arbitrary queues; centralising on MainActor avoids races.
@MainActor
final class ScheduleRegistrar {

    static let shared = ScheduleRegistrar()
    private init() {}

    private let center = UNUserNotificationCenter.current()

    // MARK: - Primary entry point

    /// Reconcile the brain's upcoming schedule against the local notification queue.
    ///
    /// - Parameter rows: The rows returned by GET /reminders/upcoming.
    ///
    /// Steps:
    ///   1. Get all currently pending UNNotificationRequests managed by this app.
    ///   2. Compute what to add (brain has it, local doesn't, fire_at is in the future).
    ///   3. Compute what to remove (local has it, brain dropped it).
    ///   4. Register additions; remove cancellations.
    ///   5. Enforce the 60-slot cap (remove oldest local entries if over limit).
    func reconcile(with rows: [ReminderRow]) async {
        let now = Date()

        // --- Step 1: get currently pending managed requests ---
        let pending   = await center.pendingNotificationRequests()
        let managedIDs = Set(pending.map(\.identifier).filter(isManagedIdentifier))

        // --- Step 2: determine what the brain says should be registered ---
        // Only register rows that fire in the future (no point scheduling past ones).
        let brainRows  = rows.filter { $0.fireAt > now }
        let brainIDs   = Set(brainRows.map(\.id))

        // --- Step 3: compute diffs ---
        let toAdd    = brainIDs.subtracting(managedIDs)
        let toRemove = managedIDs.subtracting(brainIDs)

        // --- Step 4: remove cancelled/dropped IDs ---
        if !toRemove.isEmpty {
            center.removePendingNotificationRequests(withIdentifiers: Array(toRemove))
        }

        // --- Step 5: register new rows (capped at 60 total) ---
        // Count how many managed slots remain after removals.
        let slotsUsed    = managedIDs.count - toRemove.count
        let slotsAvail   = max(0, 60 - slotsUsed)

        // Sort additions by fire_at (soonest first) so we register the most urgent.
        let rowsToAdd = brainRows
            .filter { toAdd.contains($0.id) }
            .sorted { $0.fireAt < $1.fireAt }
            .prefix(slotsAvail)

        for row in rowsToAdd {
            if let request = makeRequest(for: row) {
                try? await center.add(request)
            }
        }
    }

    // MARK: - Remove specific identifiers (used after ack)

    /// Remove UNNotificationRequests for the given reminder IDs.
    /// Called immediately after a successful /ack response so the phone
    /// doesn't wait for the next reconciliation cycle.
    func removePending(identifiers: [String]) {
        center.removePendingNotificationRequests(withIdentifiers: identifiers)
        center.removeDeliveredNotifications(withIdentifiers: identifiers)
    }

    /// Build the set of local notification identifiers for all strike kinds
    /// in a given event's chain (used when pre-emptively clearing after ack).
    static func strikeIdentifiers(eventId: String) -> [String] {
        [ReminderKind.strike0, .strike5, .strike10, .strike15].map { kind in
            "\(eventId):\(kind.rawValue)"
        }
    }

    // MARK: - Private helpers

    /// Returns true if the identifier looks like it was created by this registrar.
    /// We namespace with "<eventId>:<kind>" — the colon is our sentinel.
    /// This prevents us from clobbering system or other-app notifications.
    private func isManagedIdentifier(_ id: String) -> Bool {
        // A managed identifier must contain a colon (our separator)
        // and the kind portion must be a valid ReminderKind raw value.
        guard let colonIdx = id.lastIndex(of: ":") else { return false }
        let kindPart = String(id[id.index(after: colonIdx)...])
        return ReminderKind(rawValue: kindPart) != nil
    }

    /// Build a UNNotificationRequest from a ReminderRow.
    ///
    /// Trigger: UNCalendarNotificationTrigger with explicit TimeZone from the row's `tz`.
    /// This is important: using calendar-based triggers with an explicit timezone
    /// means the notification fires at the correct wall-clock time even if the
    /// user travels across time zones before it fires.
    ///
    /// Interruption level:
    ///   - .timeSensitive for strikes and pre_5 (pierces Focus modes)
    ///   - .active for morning_summary and heads_up_30
    private func makeRequest(for row: ReminderRow) -> UNNotificationRequest? {
        // Build DateComponents from the fire_at date in the event's timezone.
        let timeZone = TimeZone(identifier: row.tz) ?? TimeZone.current
        var calendar = Calendar(identifier: .gregorian)
        calendar.timeZone = timeZone

        let components = calendar.dateComponents(
            [.year, .month, .day, .hour, .minute, .second, .timeZone],
            from: row.fireAt
        )

        let trigger = UNCalendarNotificationTrigger(dateMatching: components, repeats: false)

        // Build notification content.
        let content = UNMutableNotificationContent()
        content.title          = "Homunculus"
        content.body           = row.body
        content.sound          = .default
        content.categoryIdentifier = homunculusNotificationCategoryID

        // Store event_id and kind in userInfo so the ack handler can read them
        // without parsing the notification identifier string.
        content.userInfo = [
            "event_id": row.eventId,
            "kind": row.kind.rawValue
        ]

        // Set interruption level per design v1.2 UX rules.
        if row.kind.isUrgent {
            content.interruptionLevel = .timeSensitive
        } else {
            content.interruptionLevel = .active
        }

        return UNNotificationRequest(
            identifier: row.id,   // "<event_id>:<kind>"
            content: content,
            trigger: trigger
        )
    }
}
