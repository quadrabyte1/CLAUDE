# Homunculus — Role Research for Nolan

**Author:** Pax (Senior Researcher)
**Date:** 2026-04-22
**Audience:** Nolan (HR), writing the persona for the Homunculus specialist
**Project brief:** `project_homunculus.md` (v1 scope locked; v1.5 deferred)

---

## TL;DR for Nolan

- The **defining skills** of this role are: (a) voice-first iOS product design, (b) natural-language-to-structured-event extraction using LLMs with strict schemas, (c) iOS local-notification reliability under adversarial conditions (Low Power Mode, time-zone changes, DND, phone-off-at-fire-time), and (d) privacy-first local data architecture. This is **not** a generalist iOS role — Kit already covers that.
- The hire should **direct Kit**, not compete with him. They own product/voice/NLP/reminder-reliability decisions; Kit owns SwiftUI/build-system/App Store execution.
- **iOS 26 changed the math.** Apple's Foundation Models framework (on-device ~3B LLM with `@Generable` structured output) and SpeechAnalyzer (replacing SFSpeechRecognizer) now make a fully on-device version of Homunculus genuinely viable. That has real implications for whether we need the Anthropic API at all. The hire must be fluent in both Apple's on-device stack and server LLM tool-use, and must have an opinion on when to use which.
- **v1.5 (native watchOS) is non-trivial.** WatchConnectivity, independent mic/speaker on Watch, and a separate watchOS target mean the hire should have watchOS shipping experience, not just "iOS with Watch mirroring."

---

## 1. iOS app architecture for this shape of product

**Recommendation:** Swift 6 + SwiftUI, MVVM with `@Observable`, modularized as local Swift packages. This matches Kit's stack — intentional, so the hire can direct Kit without architectural friction.

Stack:

- **Language:** Swift 6 with strict concurrency checking on from day one.
- **UI:** SwiftUI (`NavigationStack`, `@Observable` view models, system Dynamic Type). The user is older; Dynamic Type and accessibility are first-class.
- **Module layout:** Feature packages (`CalendarCore`, `VoiceCapture`, `NLU`, `Scheduling`, `Notifications`, `WatchBridge`) as local SPM packages. Keeps NLP/reminder logic testable in isolation without dragging in UI.
- **State ownership:** One `@Observable` root coordinator holding the active user session; each feature module exposes an actor-isolated service it owns.
- **Concurrency:** `async`/`await` everywhere; `actor` for anything touching the SQLite writer or the notification center.

This is boring-on-purpose. A memory-support tool for an older user must fail rarely and predictably. No TCA unless the complexity grows — the product surface is small.

## 2. Voice I/O on iOS

**Biggest 2026 change:** `SFSpeechRecognizer` is effectively legacy. iOS 26 introduced **SpeechAnalyzer** (WWDC25 session 277) — a new modular speech-to-text API with a faster, more accurate on-device model designed for long-form, conversational, and distant audio. It supports `SpeechTranscriber` and `SpeechDetector` modules.

Recommended stack:

- **STT:** `SpeechAnalyzer` with `SpeechTranscriber` module; on-device only. Use `contextualStrings` to bias recognition toward user-specific vocabulary (contact names, recurring event titles).
- **TTS:** `AVSpeechSynthesizer` with a premium voice (`AVSpeechSynthesisVoice(identifier:)` targeting a Siri-quality voice). Offers `pauseSpeaking(at: .word)`, `continueSpeaking()`, `stopSpeaking(at: .immediate)` for barge-in.
- **Push-to-talk UX:** Large tap target ("Talk") that starts a capture session on touch-down, ends on touch-up (or after 1.2s of silence via `SpeechDetector`). Single-press-to-start / press-to-cancel also works for older users with tremor or short-press difficulty — offer both in Settings.
- **Audio session:** `AVAudioSession` category `.playAndRecord` with options `.duckOthers` and `.allowBluetooth`. Configure once at app launch; re-activate when entering capture.
- **Barge-in:** While TTS is speaking, if user taps Talk, call `synthesizer.stopSpeaking(at: .immediate)` before starting capture. This matters — conversational feel depends on it.
- **Permissions:** `NSSpeechRecognitionUsageDescription`, `NSMicrophoneUsageDescription`. Request at first Talk tap, not at launch — for older users, in-context permission prompts have meaningfully higher grant rates.
- **Watch handoff gotcha:** In v1 (phone-only), make sure `AVAudioSession` deactivates cleanly when the phone locks during TTS; otherwise the system will warn and future activations can fail silently. Use `AVAudioSession.setActive(false, options: .notifyOthersOnDeactivation)` on teardown.

## 3. Local calendar / event store

**Recommendation for v1: GRDB.swift** (Swift wrapper over SQLite) — not SwiftData.

Why not SwiftData: SwiftData (iOS 17+) is low-friction and SwiftUI-native, but in 2026 practitioners still hit walls with complex predicates, ordered relationships, dynamic queries, and migration sharpness. Calendar apps with recurring events, conflict windows, and missed-event logs do real querying — GRDB's predictable SQL + type-safe query DSL is the safer bet.

Why not Core Data: Viable, but SwiftData essentially replaces it for new code, and Core Data brings XCDataModel drama that a small app doesn't need.

**GRDB schema sketch:**

```sql
CREATE TABLE events (
  id TEXT PRIMARY KEY,             -- UUID
  title TEXT NOT NULL,
  starts_at INTEGER NOT NULL,      -- unix seconds, UTC
  ends_at INTEGER NOT NULL,
  tz_identifier TEXT NOT NULL,     -- "America/Los_Angeles" — store the zone, not the offset
  notes TEXT,
  created_at INTEGER NOT NULL,
  updated_at INTEGER NOT NULL
);
CREATE INDEX idx_events_starts ON events(starts_at);

CREATE TABLE reminders (
  id TEXT PRIMARY KEY,
  event_id TEXT NOT NULL REFERENCES events(id) ON DELETE CASCADE,
  kind TEXT NOT NULL,              -- 'morning_summary' | 'heads_up_30' | 'pre_5' | 'strike_0' | 'strike_5' | 'strike_10' | 'strike_15'
  fire_at INTEGER NOT NULL,
  notification_id TEXT,            -- UN identifier, for cancellation
  status TEXT NOT NULL             -- 'scheduled' | 'fired' | 'acked' | 'cancelled' | 'missed'
);

CREATE TABLE missed_events (
  event_id TEXT PRIMARY KEY REFERENCES events(id),
  missed_at INTEGER NOT NULL,
  rescheduled_event_id TEXT REFERENCES events(id)
);

CREATE TABLE activity_log (          -- debugging + user trust
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  at INTEGER NOT NULL,
  kind TEXT NOT NULL,
  payload TEXT                        -- JSON
);
```

Key patterns:

- **Store UTC + IANA zone identifier**, never a raw offset. DST and travel break offset-based storage.
- Run SQLite in **WAL mode** (`PRAGMA journal_mode = WAL`) — better crash durability and concurrent reads during writes.
- All writes go through a single `DatabaseQueue`-backed actor. Reads use `DatabasePool` for concurrency.
- On app launch, run a **reconciliation pass**: compare pending UN notifications to scheduled reminders in the DB and re-schedule any missing ones (covers phone reboot, app reinstall).

Persistence is durable across relaunches and reboots natively with SQLite. The durability story is solved; the hire mainly needs to own schema and reconciliation logic.

## 4. Natural-language scheduling

This is the hardest product problem in v1.

**Three paths, with 2026 tradeoffs:**

### Path A — Apple Foundation Models framework (iOS 26+), on-device

Apple's ~3B on-device LLM is now directly available to developers via the Foundation Models framework with `@Generable` guided generation — constrained decoding forces output into a Swift type at the token level. Free, zero network, no API key, zero privacy exposure. Great fit for Homunculus's "paranoid privacy" constraint.

```swift
@Generable struct ParsedSchedulingIntent {
  enum Kind: String, Generable { case query, create, cancel, reschedule }
  let kind: Kind
  let title: String?
  let participants: [String]
  let startLocal: String?            // ISO8601 local time, model returns, we reconcile with user TZ
  let durationMinutes: Int?
  let ambiguousFields: [String]      // e.g. ["startDate"] if "Tuesday" was ambiguous
}
```

**Caveats:** The on-device model is small (~3B). Complex multi-step scheduling ("move everything on Thursday to Friday except my dentist appointment") may underperform. Also: ignores older iPhones without Apple Intelligence.

### Path B — Anthropic Claude API from the phone

Strong accuracy, robust tool-use, works on all iPhones iOS 15+. Cost and latency are modest for this volume (a few calls/day per user). User controls their own API key.

**Privacy note for the paranoid user:** Calendar content would leave the device on each parse. Two mitigations:
1. Send only the current utterance + minimal context (recent event titles within the conflict window), never the full DB.
2. Make it explicit in the UI that parsing runs in the cloud; user can disable it and fall back to Path A.

### Path C — Hybrid (recommended)

- Try Path A first (on-device). If the parse is confident and unambiguous, use it.
- Fall back to Path B (Claude) when on-device confidence is low, the request is multi-step, or ambiguous fields are present.
- Always present the parsed structured event to the user in confirmation text + TTS before writing to DB: *"I'll add 'Coffee with Jane' Tuesday April 28 at 2pm for 30 minutes. Okay?"* — one-tap confirm / cancel. This is non-negotiable for a memory-support app; silent writes are dangerous.

### Ambiguous-date resolution

- "Tuesday" → compute the next Tuesday from `Date()` in user's TZ; if today is Tuesday before noon, prefer today, else next week. Encode the rule; don't leave it to the LLM alone.
- "Tomorrow morning" → 9:00 local TZ unless the user has configured a different morning anchor.
- If both "this X" and "next X" are plausible (e.g. said Monday evening about "Thursday"), ask for confirmation rather than guessing.

### Conflict detection (the "maybe-close" case)

Use a simple temporal-overlap query with a fuzz window:

```swift
// Direct conflict: any event whose [start, end] intersects proposed [start, end]
// Fuzzy "close" conflict: any event whose start is within ±30 min of proposed start/end,
//   or whose end is within ±30 min of proposed start.
```

30 minutes is a reasonable default for the fuzz band; expose it in Settings.

## 5. iOS local notifications for escalating nag

The 64-pending limit is the operative constraint. Apple stores the soonest-fire 64 and drops the rest.

**The pattern:** maintain a rolling horizon. Schedule notifications for roughly the next 48–72 hours of events at a time. After each app launch and after each reminder fires, run a "top-up" pass that fills the queue back up to the nearest 60 upcoming strikes (leave ~4 headroom for morning summaries and one-off nags).

**Per-event strike plan, for a single event at T:**

```
strike 0 (event start):    T + 0 min    "Your coffee with Jane is starting now."
strike 1:                  T + 5 min    "Still on? Your coffee with Jane started 5 minutes ago."
strike 2:                  T + 10 min   "Reminder — coffee with Jane, 10 minutes ago."
strike 3:                  T + 15 min   "Final reminder. Coffee with Jane. Tap OK or it'll be logged as missed."
```

Plus two pre-strikes:

```
morning summary:           user's configured morning time (e.g. 7:00)
heads-up:                  T - 30 min
pre-event:                 T - 5 min
```

So up to **7 notifications per event** including morning summary share. At 60-headroom, ~8 upcoming events fit the queue — comfortable for a personal calendar.

**Mechanics:**

- Use `UNCalendarNotificationTrigger`, not `UNTimeIntervalNotificationTrigger`. Time-interval triggers drift; calendar triggers are anchored to wall-clock and handle TZ changes correctly.
- **Time-Sensitive interruption level** (`UNNotificationInterruptionLevel.timeSensitive`): bypasses most Focus modes; requires the Time Sensitive Notifications entitlement (free, no review). Set this on strikes 0–3 and pre-5; use `.active` for morning summary and heads-up-30.
- **Critical alerts**: require a separate Apple-granted entitlement and are intended for life-safety (severe weather, medical). **Do not apply for this.** A memory-support app will not get approval, and misuse is an App Review rejection. If the user wants guaranteed pierce-DND, document that they should add the app to the DND allow list and enable Time Sensitive.
- **Category + OK action:** register a `UNNotificationCategory` with a single `UNNotificationAction(identifier: "ACK", title: "OK", options: .foreground)`. The tap invokes `userNotificationCenter(_:didReceive:withCompletionHandler:)` with `actionIdentifier == "ACK"`.
- **On ACK tap:** in the delegate, immediately call `UNUserNotificationCenter.current().removePendingNotificationRequests(withIdentifiers:)` with the remaining strike IDs for that event, update reminder status in GRDB to `acked`, and log activity. Call the completion handler promptly.
- **Notification identifiers:** use a deterministic scheme, e.g. `ev.<eventUUID>.strike.<n>` — makes cancellation and deduping trivial.

## 6. Watch mirroring and ack propagation

Good news: for v1, this is nearly free.

- **Default behavior:** when you do *not* have a watchOS target, the Apple Watch automatically mirrors iPhone notifications, including notification actions. The "OK" action appears on the Watch; tapping it wakes the iPhone app and delivers the same `UNNotificationResponse` to the iOS delegate.
- **Haptic:** Watch adds haptic automatically; no code needed.
- **What's free:** display, haptic, OK tap, ack propagation.
- **What you lose without a watchOS target:** custom Watch UI, Watch-only voice input, Watch complications, Watch-specific sounds.

**Implementation note:** make sure the iOS delegate is set at `UIApplication.didFinishLaunchingWithOptions` (not later), because notification-tap launches of a suspended app deliver the response immediately and a missed delegate drops it.

**For v1.5**, this changes — see §10.

## 7. Privacy architecture

**Calendar data: device-local only.** SQLite file in App Support directory (not Documents — Documents is user-visible in Files app; App Support is not). Enable Data Protection class `NSFileProtectionComplete` on the DB file so it's encrypted at rest with the device passcode.

**LLM API calls (if using Path B or C):**

- **Direct phone → Anthropic API** is the honest approach for a self-install app with a privacy-paranoid user. No middleman server means no middleman logs.
- Store the API key in **Keychain** with `kSecAttrAccessible = kSecAttrAccessibleWhenPasscodeSetThisDeviceOnly` — requires a passcode to exist, doesn't sync via iCloud Keychain, doesn't migrate on device restore. For a memory-support user this tradeoff is worth discussing with the boss: iCloud Keychain sync would make device migration smoother at the cost of key exposure to iCloud.
- Optionally gate the key with `LAContext` (Face ID/Touch ID) on first retrieval per session.
- **Never log the key, never include it in crash reports.** Set `CFNetworkDiagnosticLogging` off and scrub NSURLSession logs.
- **What leaves the device on a Claude call:** only the current utterance text + minimal conflict-check context (titles of events within ±1 day of proposed time). Never the full DB, never notes, never participant names unless they're in the utterance.
- **Consider:** expose a "local-only mode" toggle in Settings that hard-disables the network path and forces Path A (Foundation Models) only. This is a trust-building feature that costs little.

**A user-owned middleman server** (option the boss mentioned) is worse than direct Anthropic-from-device for privacy, not better — it adds a logging surface the user has to trust and doesn't hide content from Anthropic regardless. Recommend against, unless the boss has a specific auditing reason.

## 8. Reliability patterns

Real-practitioner reality check:

- **Local notifications do fire from a terminated app.** `UNUserNotificationCenter` is scheduled by the system, not by your process, so they fire even if the app isn't running. This is the main reliability win and the reason you don't need Background App Refresh for Homunculus's core loop.
- **Low Power Mode** disables Background App Refresh and throttles *silent* push. It does **not** disable local user-visible notifications. Don't rely on silent push or background-fetch work for reminder delivery — use scheduled local notifications.
- **Phone off / dead battery at fire time:** the notification is delivered when the phone next powers on, shown in Notification Center. Apple does **not** retroactively fire missed local notifications as alerts. Implication: your reconciliation pass on launch must detect "fire time passed, no ack recorded, reminder status still scheduled" and decide whether to roll forward to the next strike or mark missed.
- **Time zone changes:** `UNCalendarNotificationTrigger` uses wall-clock. If the user flies LAX→JFK, a 2pm trigger will fire at 2pm Eastern. This is usually desired for events *at the destination*, wrong for events *back home*. Solution: when scheduling, if the event's TZ differs from the device TZ, use a `DateComponents` with explicit `TimeZone`. Log time-zone shifts via `NSSystemTimeZoneDidChangeNotification` and run a reconciliation pass on the reminder queue.
- **iOS/OS updates:** can clear some pending notifications. Not common, not guaranteed. Reconciliation pass on launch handles it.
- **Rate-limit / budget:** Apple will quietly throttle an app that schedules excessive notifications. Stay well under 64 pending and avoid rescheduling on every app launch unless state changed.

**Test matrix the hire should own:**
1. Fire a strike while phone is locked; confirm Watch mirror + OK tap cancels remaining.
2. Kill the app between heads-up-30 and pre-5; confirm pre-5 still fires.
3. Reboot phone mid-day; confirm next scheduled strike still fires correctly.
4. Enable Low Power Mode; confirm strikes still fire.
5. Enable Do Not Disturb; confirm Time-Sensitive strikes pierce.
6. Change time zone (Settings → General → Date & Time); confirm reconciliation fires and strike times are correct.
7. Fill the DB with 40 events over 3 days; confirm rolling scheduler maintains the 60-strike window.

This is what separates "works in dev" from "works for a 72-year-old on month three."

## 9. Skills/role the job requires

Synthesizing the above, the Homunculus specialist needs:

### Primary expertise (must-have)

- **Voice-first iOS product design** — has shipped an app where voice is the primary interaction, knows the UX pitfalls (mic permission moment, barge-in, error recovery, older-user ergonomics).
- **On-device speech I/O** — `SpeechAnalyzer`/`SpeechTranscriber`, `AVSpeechSynthesizer`, `AVAudioSession` state machine. Understands the legacy `SFSpeechRecognizer` path for fallback.
- **LLM-backed structured extraction** — Anthropic Claude tool-use with strict JSON schemas, Apple Foundation Models `@Generable` guided generation. Knows prompt-design for scheduling intents, confidence scoring, human-in-the-loop confirmation patterns.
- **iOS notification systems at the expert level** — `UNUserNotificationCenter`, categories/actions, interruption levels, calendar triggers, the 64-pending ceiling and rolling scheduler patterns, delegate lifecycle during cold launch.
- **Local data durability** — SQLite via GRDB, WAL mode, schema migrations, time-zone-correct event modeling, reconciliation patterns for "the phone was off" states.

### Secondary / supporting knowledge

- SwiftUI + Swift 6 concurrency (enough to direct Kit without friction).
- Keychain + Data Protection classes.
- WatchConnectivity fundamentals (for v1.5 readiness).
- Accessibility for older users — Dynamic Type, large-target UX, contrast, haptics.

### Daily workflow

- Owns the voice-input → parsed-intent → confirmation → DB-write → reminder-scheduling pipeline end-to-end.
- Writes the NLP prompts/schemas, tunes confidence thresholds, decides when on-device vs. Claude.
- Owns the reminder-reliability test matrix and runs it on every release candidate.
- Directs Kit on SwiftUI implementation, app structure, App Store submission, CI/CD. Pair-designs the feature modules; Kit writes most of the view code.
- Makes product calls on ambiguous cases (e.g., "is morning summary before or after the first reminder? how loud is strike 3?") informed by what the boss has said and what memory-support research recommends.

### What differentiates them from Kit

| Dimension | Kit (iOS generalist) | Homunculus specialist |
|---|---|---|
| Focus | SwiftUI craft, App Store, CI/CD, code quality | Product, voice, NLP, reminder reliability |
| Voice I/O | Familiar with AVFoundation | Expert; owns the audio session + barge-in design |
| LLM integration | Can wire it up | Owns the prompts, schemas, hybrid routing, confirmation UX |
| Notifications | Knows `UNUserNotificationCenter` | Owns the escalation contract, the 64-limit scheduler, the test matrix |
| Calendar domain | — | Owns schema, TZ handling, conflict logic |
| Decision authority | Implementation patterns | Product behavior |

Think of the shape as a **Voice-First Product Engineer** who can hold their own in product arguments, not a coder-who-also-does-voice.

## 10. v1.5 preview — native watchOS companion

Additional skills and tools the hire should already have:

- **Separate watchOS target** in Xcode: watchOS App + Watch Companion; the watchOS app is a real Swift target with its own Info.plist, entitlements, and binary.
- **WatchConnectivity (`WCSession`)** — the paired-phone/watch bridge. Key methods:
  - `updateApplicationContext(_:)` — lightweight state sync (preferred for "here's today's schedule").
  - `sendMessage(_:replyHandler:)` — real-time when both apps are reachable (e.g., user taps ack on Watch, tell phone immediately).
  - `transferUserInfo(_:)` — guaranteed eventual delivery when the counterpart is offline (e.g., new event created on phone propagates next time Watch app wakes).
  - Set up session early (app delegate, not view code) so it's initialized even during background launch.
- **Watch audio stack** — independent mic and speaker, using `AVAudioSession` + `AVAudioEngine` on Watch. `SpeechTranscriber` works on watchOS 11+; voice-only push-to-talk is viable without the phone.
- **Watch UI idioms** — SwiftUI on Watch, digital crown, corner complications, Smart Stack integration.
- **Power/battery discipline** — Watch is more power-constrained; no long-running background tasks, keep STT sessions short, use `WKApplication` lifecycle callbacks correctly.

**Implication for hiring:** prefer a candidate who has shipped at least one watchOS app. If they've only done "iOS with Watch mirroring," v1.5 is a significant ramp — still doable under Kit's iOS support, but slower.

---

## Sources

- [Apple: UNUserNotificationCenter](https://developer.apple.com/documentation/usernotifications/unusernotificationcenter)
- [Apple: removePendingNotificationRequests(withIdentifiers:)](https://developer.apple.com/documentation/usernotifications/unusernotificationcenter/removependingnotificationrequests(withidentifiers:))
- [Apple: UNNotificationAction](https://developer.apple.com/documentation/usernotifications/unnotificationaction)
- [Apple: UNNotificationInterruptionLevel.timeSensitive](https://developer.apple.com/documentation/usernotifications/unnotificationinterruptionlevel/timesensitive)
- [WWDC21: Send communication and Time Sensitive notifications](https://developer.apple.com/videos/play/wwdc2021/10091/)
- [WWDC25: Bring advanced speech-to-text to your app with SpeechAnalyzer](https://developer.apple.com/videos/play/wwdc2025/277/)
- [Callstack: On-Device Speech Transcription with Apple SpeechAnalyzer](https://www.callstack.com/blog/on-device-speech-transcription-with-apple-speechanalyzer)
- [Apple: SFSpeechRecognizer](https://developer.apple.com/documentation/speech/sfspeechrecognizer)
- [Apple: AVSpeechSynthesizer](https://developer.apple.com/documentation/avfaudio/avspeechsynthesizer)
- [Apple: Foundation Models framework](https://developer.apple.com/documentation/FoundationModels)
- [Apple Machine Learning Research: Introducing Apple's On-Device and Server Foundation Models](https://machinelearning.apple.com/research/introducing-apple-foundation-models)
- [Apple: Keychain services](https://developer.apple.com/documentation/security/keychain-services)
- [Apple: Storing Keys in the Keychain](https://developer.apple.com/documentation/security/storing-keys-in-the-keychain)
- [Apple: WCSession (WatchConnectivity)](https://developer.apple.com/documentation/watchconnectivity/wcsession)
- [Teabyte: Three ways to communicate via WatchConnectivity](https://alexanderweiss.dev/blog/2023-01-18-three-ways-to-communicate-via-watchconnectivity)
- [Fatbobman: Why I'm Still Thinking About Core Data in 2026](https://fatbobman.com/en/posts/why-i-am-still-thinking-about-core-data-in-2026/)
- [BrightDigit: Should You SwiftData?](https://brightdigit.com/articles/swiftdata-considerations/)
- [GRDB.swift (GitHub)](https://github.com/groue/GRDB.swift)
- [Medium/Mohsin Khan: Silent Push Notifications in iOS — Opportunities, Not Guarantees](https://mohsinkhan845.medium.com/silent-push-notifications-in-ios-opportunities-not-guarantees-2f18f645b5d5)
- [Apple HIG: Managing notifications](https://developer.apple.com/design/human-interface-guidelines/managing-notifications)
