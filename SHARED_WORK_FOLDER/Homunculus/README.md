# Homunculus

A single-user, device-local, voice-first scheduling assistant for iPhone.

**Status:** v1 — M1 in progress.
**Deployment target:** iOS 26.0.
**Language:** Swift 6 (strict concurrency).
**Device:** iPhone 16 (Apple Intelligence capable).
**Architecture spec:** `../owner_inbox/mori_homunculus_v1_plan.md`.

## Layout

```
Homunculus/
├── README.md                     — this file
├── docs/                         — handoff notes, ADRs, working docs
└── Packages/                     — local SPM packages (one per module)
    ├── CalendarCore/             — local data layer: GRDB + schema + TZ helpers   (Mori)
    ├── VoiceCapture/             — AVAudioSession + SpeechAnalyzer + TTS          (Mori)
    ├── NLU/                      — Foundation Models @Generable parse + resolver  (Mori)
    ├── Scheduling/               — rolling scheduler + reconciler                 (Mori)
    ├── NotificationsKit/         — UNUserNotificationCenter wrapper + delegate    (Mori)
    └── AppShell/                 — SwiftUI app entry + coordinator                (Kit)
```

The Xcode project itself (signing, entitlements, `Info.plist`, the `App` target) is Kit's
to create and lives alongside `Packages/` once Kit sets it up.

## Module ownership

Per §9 of the v1 plan:

| Package          | Primary author | Notes                                                           |
|------------------|----------------|-----------------------------------------------------------------|
| CalendarCore     | Mori           | GRDB, schema migrations, writer actor, reader pool, TZ helpers  |
| VoiceCapture     | Mori           | Audio session, STT, TTS, permissions, barge-in                  |
| NLU              | Mori           | `@Generable` types, prompt, deterministic date resolver         |
| Scheduling       | Mori           | Rolling 72h horizon, reconciliation, missed-event logic         |
| NotificationsKit | Mori           | UN center wrapper, category/action, delegate                    |
| AppShell         | Kit            | `@main App`, SwiftUI views, navigation, `Today`, Add Event form |

## Dependencies

Exactly one third-party dependency in v1: **GRDB.swift**. No analytics, no crash reporters,
no networking libraries. Every dependency is a privacy liability in a local-only app.

## Tests

Swift Testing. Each package owns its own `Tests/` folder. Device test matrix runs on real
iPhone 16 before any RC (see §11 of the plan).
