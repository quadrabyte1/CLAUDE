// swift-tools-version: 6.0
import PackageDescription

// NLU — M2.
// Owner: Mori.
// Boundary: Apple Foundation Models client, @Generable scheduling-intent types,
// prompt authoring, deterministic Swift-side date/time resolution, ambiguity handling.
// Depends on: CalendarCore (for settings: morning_anchor_hour, user TZ).
// Does NOT depend on: VoiceCapture, Scheduling, NotificationsKit, AppShell.
//
// Skeleton manifest. Implementation lands in M2.

let package = Package(
    name: "NLU",
    platforms: [.iOS(.v26)],
    products: [
        .library(name: "NLU", targets: ["NLU"])
    ],
    dependencies: [
        .package(path: "../CalendarCore")
    ],
    targets: [
        .target(
            name: "NLU",
            dependencies: [
                .product(name: "CalendarCore", package: "CalendarCore")
            ],
            swiftSettings: [
                .enableExperimentalFeature("StrictConcurrency")
            ]
        ),
        .testTarget(
            name: "NLUTests",
            dependencies: ["NLU"]
        )
    ]
)
