# Homunculus iOS — Open Questions & Known Issues

**Written for: Thomas (solo reading on 2026-06-23 return)**
**iOS client version: 1.0 (first draft)**
**Brain version this was built against: 1.2**

---

## OQ-1 — ParsedIntent echo in CaptureResponse — RESOLVED (brain v1.2.1)

**Status: RESOLVED.** Rune shipped `intent: Optional[ParsedIntent]` in `CaptureResponse`
as part of brain v1.2.1 (before this iOS client was built).

**What was the problem:** The original brain v1.2 `CaptureResponse` did not include the
`ParsedIntent` the brain derived from the text. The iOS client needed it to POST
`/capture/confirm`, so there was a risk of the brain re-parsing differently on confirm.

**How it's handled now:**
- `CaptureResponse` in `BrainModels.swift` decodes `intent: ParsedIntent?`.
- `BrainService.capture()` uses `response.intent` when non-nil (brain v1.2.1+).
- Falls back to `ParsedIntent.synthetic(from:)` if the brain returns nil (backward compat
  with any older brain you might be running). The synthetic workaround is kept but should
  never be needed against the current brain.

**Residual risk:** None under normal operation. The synthetic fallback is dead code
against brain v1.2.1+.

**Cleanup:** Remove `ParsedIntent.synthetic(from:)` in a future cleanup pass once you're
confident you won't downgrade the brain. It's in `BrainService.swift` extension.

---

## OQ-2 — Voice input is deferred (text only in v1)

**What:** The app is text-only. The task brief explicitly approved this.

**Why:** Apple's `SpeechAnalyzer` / `SpeechTranscriber` APIs require iOS 26 (not yet
shipping) and the STT pipeline needs real hardware testing with AVAudioSession.
The text path exercises the brain identically to voice — all the networking, confirmation,
reconciliation, and ack flows are the same.

**To add voice later:**
1. Add `VoiceCapture/` module (Recorder.swift, Speaker.swift per the ios_client_spec.md).
2. Add a "Hold to Talk" button to `CaptureView` that fills the same `inputText` field
   (or better: submits directly, bypassing the field).
3. Add `AVSpeechSynthesizer` TTS to `BrainService` to read back `spoken_reply`.
4. Permission prompt (`NSMicrophoneUsageDescription` + `NSSpeechRecognitionUsageDescription`)
   already declared in Info.plist — just needs to be *requested* in `VoiceCapture`.

---

## OQ-3 — Activity viewer blocked on brain endpoint

**What:** The Today view / capture history panel is not implemented.

**Why:** `GET /activity` doesn't exist on the brain yet (see brain v1.2 open coordination
items — it's in the `_activity.jsonl` file but no HTTP surface). Until Rune adds the
endpoint, the phone can't fetch it.

**When Rune ships `GET /activity`:**
1. Add `func activity(baseURL: URL, n: Int) async throws -> [ActivityRow]` to `BrainClient`.
2. Add `ActivityRow: Codable` to `BrainModels.swift` (mirror Rune's schema).
3. Add an "Activity" tab or section in `TodayView`.

---

## OQ-4 — Undo flow blocked on brain endpoint

**What:** "Undo that" (5-minute undo window) is not implemented.

**Why:** `POST /undo` doesn't exist on the brain yet (v1.3 planned).

**When Rune ships `POST /undo`:**
1. Add an "Undo" button to `ResponseCard` that appears for ~5 minutes after a `wrote` action.
2. Store the `written_path` from `CaptureResponse` (it's already decoded — just not surfaced).
3. POST `/undo` with the path.

---

## OQ-5 — ATS exception covers all *.ts.net subdomains

**What:** `Info.plist` allows plain HTTP to any `*.ts.net` hostname.

**Why:** Tailscale encrypts all traffic at the VPN layer; the HTTP between the app and the
brain is inside the encrypted tailnet. ATS doesn't know this, so we must add an exception.

**Security posture:** This is fine for personal use on a private tailnet. It would be
wrong for an app distributed to others.

**If submitting to the App Store:** Replace the `ts.net` domain exception with the boss's
specific tailnet hostname (e.g. `mac-mini.frosty-llama.ts.net`) to minimise the ATS
carve-out. The current blanket exception would likely get an App Review question.

---

## OQ-6 — DEVELOPMENT_TEAM must be set before building to device

**What:** The `project.pbxproj` has `DEVELOPMENT_TEAM = ""` (empty).

**Why:** I don't have the boss's Apple Developer team ID; it needs to be set in Xcode.

**Fix:** Open `Homunculus.xcodeproj` in Xcode → select the Homunculus target → Signing &
Capabilities → choose your Apple ID team. Xcode will fill in `DEVELOPMENT_TEAM`.

---

## OQ-7 — Time-Sensitive entitlement must be declared in Signing & Capabilities

**What:** The `ScheduleRegistrar` sets `.timeSensitive` interruption level on strike/pre_5
notifications. This requires the `com.apple.developer.usernotifications.time-sensitive`
entitlement.

**Fix:** In Xcode → Homunculus target → Signing & Capabilities → tap "+" → add
"Time Sensitive Notifications". This adds the entitlement to the `.entitlements` file
(Xcode creates this automatically). No App Review special approval needed — it's free.

---

## OQ-8 — `.defaultCritical` sound on urgent notifications may not fire correctly

**What:** `ScheduleRegistrar.makeRequest(for:)` uses `UNNotificationSound.defaultCritical`
for urgent (strike/pre_5) notifications.

**Issue:** `.defaultCritical` requires the Critical Alerts entitlement (which we explicitly
are NOT using — the spec says no Critical Alerts). Without the entitlement, iOS may
silently fall back to `.default`.

**Fix:** Change `row.kind.isUrgent ? .defaultCritical : .default` to simply `.default`
for both. The Time-Sensitive interruption level already ensures the notification
pierces Focus/DND; the critical sound entitlement is not needed and not wanted.

**This is a known bug in the v1.0 draft.** Fix it in the first Xcode session.

---

## OQ-9 — BrainService polling on background thread may accumulate tasks

**What:** `BrainService.startPolling()` creates a `Task` that loops with
`Task.sleep(for: .seconds(60))`. If `startup()` is called multiple times in quick
succession (fast app switches), `stopPolling()` might not cancel the old task before
a new one starts.

**Current mitigation:** `startPolling()` calls `pollTask?.cancel()` before creating a
new task. This is correct but relies on Swift structured concurrency cancellation
propagating through `Task.sleep`.

**To harden:** Consider using a `Timer` publisher from Combine instead, which is easier
to cancel atomically. But for v1 this is fine.

---

## OQ-10 — SwiftData not used in v1

**What:** The task brief suggested SwiftData for "last successful brain URL, recent
capture history". In v1, `@AppStorage` (UserDefaults) is used for the brain URL only.
Capture history is not persisted locally (the brain is truth).

**Why:** The task brief also said "don't over-engineer this". `@AppStorage` is sufficient
for a single URL string. SwiftData adds `@Model` migration overhead for no real benefit
at v1 data volumes.

**If you want local capture history:** Add a SwiftData `@Model CaptureHistoryEntry`
with `id`, `text`, `action`, `spokenReply`, `timestamp`. Store the last 50 captures.
Display in an "Activity" tab (also blocked on OQ-3 for brain-side history).

---

## Known Issues (bugs to fix in first Xcode session)

1. **OQ-8 (critical sound):** Change `.defaultCritical` to `.default` in
   `ScheduleRegistrar.makeRequest(for:)`.

2. **`ParsedIntent` does not conform to `Encodable`:** `ConfirmRequest` contains a
   `ParsedIntent` that must be serialized. `ParsedIntent` has a custom `init(from:)` but
   no custom `encode(to:)`. Swift's synthesized `Encodable` should work because all
   stored properties are `Encodable`. Verify this compiles without a custom encode.

3. **`HomunculusApp` `UIApplication.willEnterForegroundNotification`:** The `@main` struct
   uses `onReceive` to listen for foreground events. In a pure SwiftUI lifecycle, this
   should work. If you see double-startup calls, consider using `@Environment(\.scenePhase)`
   instead — it's the SwiftUI-native way:
   ```swift
   .onChange(of: scenePhase) { _, phase in
       if phase == .active { Task { await brain.startup() } }
   }
   ```

4. **`@Observable` and `@Environment` in tests:** `BrainService` uses `@Observable` macro.
   In unit tests that import `@testable import Homunculus`, you may get macro expansion
   errors if the test target doesn't build the app target first. This is resolved by
   running tests via the app's test target (which depends on the app target).
