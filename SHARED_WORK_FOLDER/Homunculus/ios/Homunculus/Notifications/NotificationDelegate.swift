/// NotificationDelegate.swift
/// UNUserNotificationCenterDelegate implementation.
///
/// Handles two cases:
///   1. willPresentNotification — show notification even when app is foregrounded.
///   2. didReceive response — user tapped "OK" on a reminder; POST /ack to brain.
///
/// The delegate MUST be set in the app entry point (HomunculusApp), not in a view
/// model.  Cold-launch from a notification tap delivers the response immediately
/// via didReceive — if the delegate isn't set, the ack is lost.
///
/// Ack flow on "OK" tap:
///   1. Parse event_id + kind from notification's userInfo.
///   2. Immediately remove all local strike identifiers for that event_id.
///      (Pre-emptive — don't wait for the brain response.)
///   3. POST /ack to the brain.
///   4. On success, remove any additional IDs listed in cancelled_kinds
///      (the brain may have cancelled ones our local pre-emption missed).
///   5. Trigger a reconciliation pull so the UI updates.
///
/// Swift 6 note: UNUserNotificationCenterDelegate callbacks are delivered on an
/// arbitrary queue.  The delegate methods are `nonisolated` to satisfy the protocol;
/// they immediately hop to `@MainActor` via `Task { @MainActor in ... }`.
/// `brainService` is accessed only after that hop.

import Foundation
import UserNotifications

/// @unchecked Sendable is acceptable here because:
///  - `brainService` is only written once, on the MainActor, before notifications fire.
///  - All reads of `brainService` happen inside `Task { @MainActor in ... }` blocks.
///  - NSObject itself is not Sendable in Swift 6; @unchecked suppresses the diagnostic
///    while keeping the pattern safe by convention.
final class NotificationDelegate: NSObject, UNUserNotificationCenterDelegate, @unchecked Sendable {

    /// Injected at setup time from the app.  Written on MainActor before any notification
    /// fires.  Read only inside MainActor Task blocks.
    @MainActor var brainService: BrainService?

    // MARK: - willPresent (foreground)

    /// Show banner + sound even when app is in foreground (useful for testing).
    func userNotificationCenter(
        _ center: UNUserNotificationCenter,
        willPresent notification: UNNotification,
        withCompletionHandler completionHandler: @escaping (UNNotificationPresentationOptions) -> Void
    ) {
        completionHandler([.banner, .sound, .badge])
    }

    // MARK: - didReceive (action tap)

    func userNotificationCenter(
        _ center: UNUserNotificationCenter,
        didReceive response: UNNotificationResponse,
        withCompletionHandler completionHandler: @escaping () -> Void
    ) {
        guard response.actionIdentifier == homunculusAckActionID else {
            completionHandler()
            return
        }

        let userInfo = response.notification.request.content.userInfo
        guard
            let eventId = userInfo["event_id"] as? String,
            let kindRaw = userInfo["kind"] as? String,
            let kind = ReminderKind(rawValue: kindRaw)
        else {
            completionHandler()
            return
        }

        // Hop to MainActor to safely access brainService and ScheduleRegistrar.
        Task { @MainActor in
            await self.handleAck(eventId: eventId, kind: kind)
            completionHandler()
        }
    }

    // MARK: - Private ack logic (MainActor)

    @MainActor
    private func handleAck(eventId: String, kind: ReminderKind) async {
        // Step 1: Pre-emptively remove all strike identifiers for this event.
        // This gives immediate feedback even if the brain is momentarily unreachable.
        let strikeIDs = ScheduleRegistrar.strikeIdentifiers(eventId: eventId)
        ScheduleRegistrar.shared.removePending(identifiers: strikeIDs)

        // Step 2: POST /ack to the brain.
        guard let service = brainService else { return }

        do {
            let ackReq  = AckRequest(eventId: eventId, kind: kind, ackedAt: Date())
            let ackResp = try await service.ack(ackReq)

            // Step 3: Remove any additional IDs the brain cancelled that our
            // pre-emption might not have covered.
            let additionalIDs = ackResp.cancelledKinds.map { cancelledKind in
                "\(ackResp.eventId):\(cancelledKind.rawValue)"
            }
            if !additionalIDs.isEmpty {
                ScheduleRegistrar.shared.removePending(identifiers: additionalIDs)
            }

            // Step 4: Trigger a reconciliation so the app UI refreshes.
            await service.refreshReminders()

        } catch {
            // Ack failed — brain unreachable.
            // Pre-emptive local removal already happened.  Next reconciliation will sync.
        }
    }
}
