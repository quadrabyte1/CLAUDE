// swift-tools-version: 6.0
import PackageDescription

// NotificationsKit — M3.
// Owner: Mori.
// Boundary: the UNUserNotificationCenter wrapper. Category + action registration,
// delegate lifecycle, request construction from DateComponents with explicit TimeZone,
// identifier scheme, add/remove/pending queries, ack routing.
// Depends on: CalendarCore (reminder IDs, event titles, TZ identifiers for triggers).
// Does NOT depend on: VoiceCapture, NLU, Scheduling, AppShell.
//
// Skeleton manifest. Implementation lands in M3.

let package = Package(
    name: "NotificationsKit",
    platforms: [.iOS(.v26)],
    products: [
        .library(name: "NotificationsKit", targets: ["NotificationsKit"])
    ],
    dependencies: [
        .package(path: "../CalendarCore")
    ],
    targets: [
        .target(
            name: "NotificationsKit",
            dependencies: [
                .product(name: "CalendarCore", package: "CalendarCore")
            ],
            swiftSettings: [
                .enableExperimentalFeature("StrictConcurrency")
            ]
        ),
        .testTarget(
            name: "NotificationsKitTests",
            dependencies: ["NotificationsKit"]
        )
    ]
)
