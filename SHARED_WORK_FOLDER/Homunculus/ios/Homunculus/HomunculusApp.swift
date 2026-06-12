/// HomunculusApp.swift
/// App entry point.  Sets up:
///   - NotificationDelegate (MUST be set before any notification fires)
///   - UNUserNotificationCenter category registration
///   - Notification permission request
///   - BrainService injection into the environment
///   - App lifecycle → startup / refresh / polling management

import SwiftUI
import UserNotifications

@main
struct HomunculusApp: App {

    // MARK: - Shared objects

    @State private var brainService = BrainService(
        host: UserDefaults.standard.string(forKey: AppSettings.brainHostKey) ?? AppSettings.defaultBrainHost,
        port: UserDefaults.standard.integer(forKey: AppSettings.brainPortKey).nonZeroOrDefault(AppSettings.defaultBrainPort)
    )

    /// NotificationDelegate must be strongly held here — UNUserNotificationCenter
    /// holds a weak reference.  Letting it live in App ensures it persists for the
    /// full lifecycle.
    @State private var notificationDelegate = NotificationDelegate()

    /// scenePhase drives foreground/background detection.
    /// Using scenePhase is the SwiftUI-native alternative to UIApplication notifications;
    /// it avoids importing UIKit and is Swift 6 safe.
    @Environment(\.scenePhase) private var scenePhase

    // MARK: - Scene

    var body: some Scene {
        WindowGroup {
            ContentView()
                .environment(brainService)
                .onAppear {
                    setupNotifications()
                }
        }
        .onChange(of: scenePhase) { _, newPhase in
            if newPhase == .active {
                // Called on first launch AND every time the app comes to foreground.
                Task { @MainActor in
                    await brainService.startup()
                }
            } else if newPhase == .background {
                brainService.stopPolling()
            }
        }
    }

    // MARK: - Notification bootstrap

    /// Called once on first appear.
    ///
    /// Order matters:
    ///   1. Assign the delegate synchronously before requesting permission.
    ///      (Apple docs: set delegate before app finishes launching.)
    ///   2. Register the HOMUNCULUS_EVENT category.
    ///   3. Request permission asynchronously.
    private func setupNotifications() {
        let center = UNUserNotificationCenter.current()

        // Step 1: Set delegate.  NotificationDelegate is held strongly by @State.
        notificationDelegate.brainService = brainService
        center.delegate = notificationDelegate

        // Step 2: Register category + action.
        center.registerHomunculusCategory()

        // Step 3: Request permission.
        Task { @MainActor in
            await requestNotificationPermission()
        }
    }

    private func requestNotificationPermission() async {
        let center = UNUserNotificationCenter.current()
        do {
            let granted = try await center.requestAuthorization(options: [.alert, .sound, .badge])
            if !granted {
                // User denied — reminders won't fire.
                // We'll surface this in the UI as a warning banner if needed.
                _ = granted  // suppress "unused" warning
            }
        } catch {
            // Ignore errors on permission request.
        }
    }
}

// MARK: - Helpers

private extension Int {
    func nonZeroOrDefault(_ fallback: Int) -> Int {
        self == 0 ? fallback : self
    }
}
