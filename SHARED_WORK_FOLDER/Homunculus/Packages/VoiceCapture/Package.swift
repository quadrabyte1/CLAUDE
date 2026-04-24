// swift-tools-version: 6.0
import PackageDescription

// VoiceCapture — M2.
// Owner: Mori.
// Boundary: AVAudioSession lifecycle, SpeechAnalyzer/SpeechTranscriber push-to-talk capture,
// AVSpeechSynthesizer playback with barge-in, permission prompting at first-Talk moment.
// Depends on: CalendarCore (for contextualStrings biasing from recent titles/people).
// Does NOT depend on: NLU, Scheduling, NotificationsKit, AppShell.
//
// This manifest is an intentional skeleton — implementation lands in M2. Do not add
// targets or dependencies here until M2 begins.

let package = Package(
    name: "VoiceCapture",
    platforms: [.iOS(.v26)],
    products: [
        .library(name: "VoiceCapture", targets: ["VoiceCapture"])
    ],
    dependencies: [
        .package(path: "../CalendarCore")
    ],
    targets: [
        .target(
            name: "VoiceCapture",
            dependencies: [
                .product(name: "CalendarCore", package: "CalendarCore")
            ],
            swiftSettings: [
                .enableExperimentalFeature("StrictConcurrency")
            ]
        ),
        .testTarget(
            name: "VoiceCaptureTests",
            dependencies: ["VoiceCapture"]
        )
    ]
)
