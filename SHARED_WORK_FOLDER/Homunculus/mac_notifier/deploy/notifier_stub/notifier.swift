// notifier.swift — Homunculus Notifier stub
//
// A minimal Swift command-line tool that posts a macOS UserNotification.
// When run from inside a properly-signed .app bundle with bundle ID
// com.homunculus.notifier, the notification appears as "Homunculus" in
// the macOS Notification Center tray.
//
// Usage:
//   notifier <body> <subtitle> [<title>] [<sound>]
//
// Args:
//   body     — Notification body text (required)
//   subtitle — Short subtitle (required)
//   title    — Title override (default: "Homunculus")
//   sound    — NSUserNotificationCenter sound name (default: "default")
//
// Build (called by install_bundle.sh):
//   swiftc notifier.swift -o notifier
//
// Compiled binary is placed at:
//   ~/Applications/Homunculus Notifier.app/Contents/MacOS/notifier
//
// macOS will prompt the user to Allow Notifications on first use.
// After granting permission, all future notifications appear as "Homunculus".
//
// Compatibility: macOS 12+ (UserNotifications framework; Swift 5.5+)

import Foundation
import UserNotifications

// ---------------------------------------------------------------------------
// Parse CLI args
// ---------------------------------------------------------------------------

let args = CommandLine.arguments
guard args.count >= 3 else {
    fputs("Usage: notifier <body> <subtitle> [<title>] [<sound>]\n", stderr)
    exit(1)
}

let body     = args[1]
let subtitle = args[2]
let title    = args.count >= 4 ? args[3] : "Homunculus"
let sound    = args.count >= 5 ? args[4] : "default"

// ---------------------------------------------------------------------------
// Request notification authorization (non-interactive — first-run only)
// ---------------------------------------------------------------------------

let center = UNUserNotificationCenter.current()

// Semaphore so we can block until the authorization check resolves.
let authSem = DispatchSemaphore(value: 0)

center.requestAuthorization(options: [.alert, .sound]) { granted, error in
    if let err = error {
        fputs("Notification auth error: \(err)\n", stderr)
    }
    if !granted {
        fputs("Notification permission not granted — check System Settings → Notifications → Homunculus Notifier\n", stderr)
    }
    authSem.signal()
}

authSem.wait()

// ---------------------------------------------------------------------------
// Build and post the notification
// ---------------------------------------------------------------------------

let content = UNMutableNotificationContent()
content.title    = title
content.subtitle = subtitle
content.body     = body
if sound == "default" {
    content.sound = .default
} else {
    content.sound = UNNotificationSound(named: UNNotificationSoundName(sound))
}

// Unique identifier prevents duplicate delivery if called twice rapidly.
let identifier = "homunculus-\(UUID().uuidString)"
let request = UNNotificationRequest(
    identifier: identifier,
    content: content,
    trigger: nil   // nil = deliver immediately
)

let postSem = DispatchSemaphore(value: 0)
var postError: Error? = nil

center.add(request) { error in
    postError = error
    postSem.signal()
}

postSem.wait()

if let err = postError {
    fputs("Failed to post notification: \(err)\n", stderr)
    exit(1)
}

// Give the system a brief moment to deliver before the process exits.
// Without this sleep the notification can be lost when the process exits
// immediately after add().
Thread.sleep(forTimeInterval: 0.5)

exit(0)
