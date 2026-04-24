// swift-tools-version: 6.0
import PackageDescription

// Scheduling — M3.
// Owner: Mori.
// Boundary: the rolling 72h-horizon scheduler, reconciliation pass, missed-event
// detection, event-level operations (create/edit/cancel/ack fan-out).
// Depends on: CalendarCore (reminders + events state), NotificationsKit (UN interface).
// Does NOT depend on: VoiceCapture, NLU, AppShell.
//
// Skeleton manifest. Implementation lands in M3 — the hardest milestone.

let package = Package(
    name: "Scheduling",
    platforms: [.iOS(.v26)],
    products: [
        .library(name: "Scheduling", targets: ["Scheduling"])
    ],
    dependencies: [
        .package(path: "../CalendarCore"),
        .package(path: "../NotificationsKit")
    ],
    targets: [
        .target(
            name: "Scheduling",
            dependencies: [
                .product(name: "CalendarCore", package: "CalendarCore"),
                .product(name: "NotificationsKit", package: "NotificationsKit")
            ],
            swiftSettings: [
                .enableExperimentalFeature("StrictConcurrency")
            ]
        ),
        .testTarget(
            name: "SchedulingTests",
            dependencies: ["Scheduling"]
        )
    ]
)
