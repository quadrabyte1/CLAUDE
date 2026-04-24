// swift-tools-version: 6.0
import PackageDescription

// AppShell — M1+.
// Owner: Kit.
// Boundary: SwiftUI entry point, root coordinator, navigation, Today view, manual Add
// Event form (M1), Talk button and confirmation readback UI (M2), settings (M5).
// Depends on: every other package.
//
// Skeleton manifest. Kit builds this out starting in M1.

let package = Package(
    name: "AppShell",
    platforms: [.iOS(.v26)],
    products: [
        .library(name: "AppShell", targets: ["AppShell"])
    ],
    dependencies: [
        .package(path: "../CalendarCore"),
        .package(path: "../VoiceCapture"),
        .package(path: "../NLU"),
        .package(path: "../Scheduling"),
        .package(path: "../NotificationsKit")
    ],
    targets: [
        .target(
            name: "AppShell",
            dependencies: [
                .product(name: "CalendarCore", package: "CalendarCore"),
                .product(name: "VoiceCapture", package: "VoiceCapture"),
                .product(name: "NLU", package: "NLU"),
                .product(name: "Scheduling", package: "Scheduling"),
                .product(name: "NotificationsKit", package: "NotificationsKit")
            ],
            swiftSettings: [
                .enableExperimentalFeature("StrictConcurrency")
            ]
        ),
        .testTarget(
            name: "AppShellTests",
            dependencies: ["AppShell"]
        )
    ]
)
