# Homunculus iOS client — v1.0 spec for Kit

**Audience:** Kit (iOS engineer). The new Mac-brain engineer (created
alongside this spec) owns the brain-side protocol; you own everything
on the phone.

**Scope:** the phone client for the Mac-as-brain Homunculus design (see
the project memory at
`~/.claude/projects/-Volumes-GIT-CLAUDE/memory/project_homunculus.md`
for the locked v1.0 decisions). The phone is a thin client: capture
voice, hand off to the brain, speak the reply, register the reminder
schedule the brain returns.

## What ships in v1

- **Press-to-talk Talk button** on a single main screen.
- **On-device STT** (Apple's `SpeechAnalyzer` / `SpeechTranscriber`, iOS 26).
- **HTTPS to the brain** at `mac-mini.<tailnet>.ts.net:8765`.
- **TTS readback** of the brain's `spoken_reply` field (`AVSpeechSynthesizer`,
  premium Siri voice).
- **Confirmation flow** for calendar writes (read back, accept "yes" / "no"
  / a one-shot correction utterance).
- **Clarifying-question loop** when the brain says `needs_clarification`.
- **Reminder registration**: pull the next-72h schedule from the brain,
  register each row with `UNUserNotificationCenter` using deterministic
  identifiers, ack on tap.
- **Watch reminder mirroring** for free (no native watchOS target).
- **Tailscale** configured once by the boss; the app does no network setup.

## What is NOT in v1

- No Watch app, no Watch voice input, no complications.
- No background listening (no ambient "just hears me" mode).
- No on-device LLM — that's the brain's job.
- No calendar interop with iOS's Calendar.app (events live only in the
  Homunculus vault for v1).
- No CarPlay, no Siri Shortcuts (later).
- No multi-user / multi-vault selection.

## Architecture (single-target iOS app)

```
HomunculusApp/
├── HomunculusApp.swift          — @main, app lifecycle, delegate registration
├── AppCoordinator.swift         — @Observable root; owns the active session
├── BrainClient.swift            — httpx-equivalent: URLSession + JSON; hits brain at tailnet host
├── VoiceCapture/
│   ├── AudioSession.swift       — AVAudioSession state machine
│   ├── Recorder.swift           — start/stop capture; SpeechAnalyzer pipeline
│   └── Speaker.swift            — AVSpeechSynthesizer + barge-in
├── Notifications/
│   ├── NotificationCenter.swift — UNUserNotificationCenter wrapper
│   ├── ScheduleRegistrar.swift  — diff/register from brain's schedule
│   └── DelegateHandler.swift    — willPresent / didReceive (the OK action)
├── Views/
│   ├── TodayView.swift          — Talk button + today's events list (pulled from brain)
│   ├── TranscriptView.swift     — live transcription while holding Talk
│   ├── ConfirmationSheet.swift  — appears when the brain returns needs_confirmation
│   └── ActivityView.swift       — recent captures (last N rows from brain's /activity)
└── Models/
    ├── ParsedIntent.swift       — mirrors the brain's pydantic schema
    ├── CaptureResponse.swift    — mirrors the brain's CaptureResponse
    └── ReminderRow.swift        — mirrors the brain's ReminderRow
```

Keep it simple SwiftUI / `@Observable`. No TCA in v1.

## Brain endpoints (the contract)

All endpoints live under `http://mac-mini.<tailnet>.ts.net:8765`. JSON
content type. No auth at the application level — Tailscale is the trust
boundary. If you ever need a token, add it to a single `X-Homunculus-Auth`
header so it's easy to add server-side.

### `GET /health`

```json
{ "status": "ok", "design_version": "1.0", "package_version": "1.0.0", "vault_path": "/.../vault" }
```

Use this on app launch to confirm the brain is reachable. If it isn't,
show a friendly "Homunculus is offline — check the Mac" screen and let
the user retry.

### `POST /capture/text`

Send the transcribed utterance plus the timestamp at which the user
finished speaking. `speaker_tz` is optional; the brain defaults to the
boss's configured zone.

```json
{
  "text": "can we meet for coffee Thursday at 10",
  "captured_at": "2026-06-08T15:23:45-04:00",
  "speaker_tz": "America/New_York"
}
```

Response (a `CaptureResponse`):

```json
{
  "kind": "calendar_query",
  "confidence": "medium",
  "action": "wrote",
  "spoken_reply": "You're clear Thursday June 11 at 10:00 AM.",
  "written_path": null,
  "conflicts": { "has_direct_conflict": false, "has_fuzzy_conflict": false, "direct": [], "fuzzy": [] },
  "clarifying_question": null,
  "raw_text": "can we meet for coffee Thursday at 10"
}
```

`action` is one of:

| value                  | client behavior                                                                                  |
| ---------------------- | ------------------------------------------------------------------------------------------------ |
| `wrote`                | Speak `spoken_reply` via TTS. Done.                                                              |
| `needs_confirmation`   | Speak `spoken_reply` (which is the readback). Show ConfirmationSheet. On "yes" → POST `/capture/confirm`. On "no" → discard. |
| `needs_clarification`  | Speak `clarifying_question`. Re-arm Talk for one more turn. Resend with the combined utterance. |
| `inbox`                | Speak `spoken_reply` (which announces the inbox drop). Done.                                     |

### `POST /capture/confirm`

Sent after the user says yes to a calendar readback. The body echoes the
parsed intent back (the brain doesn't keep server-side session state for
v1; the client carries it).

```json
{
  "intent": { ...the ParsedIntent the brain returned... },
  "captured_at": "2026-06-08T15:23:48-04:00"
}
```

Response is a `CaptureResponse` with `action: "wrote"`.

### `GET /events?day=YYYY-MM-DD`

Returns a list of events for the day in ISO-8601. Powers the Today view.

### `GET /activity?n=50` *(brain feature in progress — confirm with the brain engineer before wiring the UI)*

Returns the last N activity-log entries. Powers the ActivityView for
debugging.

### `GET /reminders/upcoming?window_hours=72`

Returns the next-window reminder schedule. Brain composes it fresh on
every call from the vault (per-event strike rows + daily morning-summary
rows). Sorted ascending by `fire_at`; capped at 60 rows so the client
stays under iOS's 64-pending limit.

Mechanism: client polls `/reminders/upcoming` on app launch, on
app-foreground, and after every capture, diffs against its local
`UNUserNotificationCenter` queue, and registers/cancels as needed.

```json
[
  {
    "event_id": "summary.2026-06-12",
    "kind": "morning_summary",
    "fire_at": "2026-06-12T07:00:00-04:00",
    "tz": "America/New_York",
    "body": "Good morning. Today: 10:00 AM Coffee with Jane.",
    "status": "pending"
  },
  {
    "event_id": "2026-06-12-coffee-with-jane",
    "kind": "heads_up_30",
    "fire_at": "2026-06-12T09:30:00-04:00",
    "tz": "America/New_York",
    "body": "In 30 minutes: Coffee with Jane at 10:00 AM.",
    "status": "pending"
  }
]
```

### `POST /ack`

The brain owns the strike chain. When the user taps `OK` on a strike,
POST the ack and the brain cancels every later strike in the same chain.

Request:

```json
{
  "event_id": "2026-06-12-coffee-with-jane",
  "kind": "strike_0",
  "acked_at": "2026-06-12T10:00:32-04:00"
}
```

Response:

```json
{
  "event_id": "2026-06-12-coffee-with-jane",
  "acked_kind": "strike_0",
  "cancelled_kinds": ["strike_5", "strike_10", "strike_15"],
  "rows": [ ... updated rows for the event chain ... ]
}
```

Idempotent: double-ack returns the same shape with an empty
`cancelled_kinds`. Unknown event ids return 200 with empty results —
never 404. The phone should still remove the cancelled strikes from
`UNUserNotificationCenter` even if it had a stale local view.

## Voice capture pipeline

1. **Touch-down on Talk:**
   - Haptic `.light`.
   - Stop any TTS in progress (`synthesizer.stopSpeaking(at: .immediate)`).
   - Activate `AVAudioSession` (`.playAndRecord`, `.duckOthers`, `.allowBluetooth`).
   - Start `SpeechAnalyzer` with `SpeechTranscriber`. Seed
     `contextualStrings` with recent event titles + names that have
     appeared in the last 90 days of activity.
   - Wire `SpeechDetector` for end-of-utterance (default 1.2s trailing silence).
   - Show live transcription on screen.
2. **Touch-up (or end-of-utterance):**
   - Stop capture. Haptic `.light`.
   - Final transcription string. POST to `/capture/text`.
3. **On response:**
   - Speak `spoken_reply`. Apply the action-driven UI per the table above.
4. **Permission timing:** request `NSMicrophoneUsageDescription` and
   `NSSpeechRecognitionUsageDescription` at the first Talk tap, not at
   launch. In-context prompts grant at higher rates with older users.

**Audio session teardown** when leaving capture:
`AVAudioSession.setActive(false, options: .notifyOthersOnDeactivation)`.
Skipping this causes silent activation failures after the screen locks.

## Confirmation UX

When the brain returns `needs_confirmation`:

- Speak the `spoken_reply` (it already ends with "Sound right?" or
  "Save anyway?").
- Show ConfirmationSheet with big buttons: **OK, save it** (primary)
  and **Cancel** (secondary).
- Also accept "yes" / "no" via a one-shot voice tap. (Press Talk →
  "yes" → POST `/capture/confirm` with the intent the brain echoed back.)
- Tap targets large; Dynamic Type supported from day one.

## Reminder registration

`UNUserNotificationCenter` is the fire engine. The brain owns the
schedule. Identifiers are deterministic:

- `ev.<event-id>.headsup30`
- `ev.<event-id>.pre5`
- `ev.<event-id>.strike.0` ... `ev.<event-id>.strike.15`
- `summary.<yyyy-mm-dd>`

Steps:

1. On launch + foreground + after each capture, fetch the next-72h
   reminder schedule from the brain.
2. Diff against `UNUserNotificationCenter.current().pendingNotificationRequests()`:
   - In schedule, not in UN, and `fire_at > now` → register with
     `UNCalendarNotificationTrigger` built from `DateComponents` carrying
     an explicit `TimeZone` (preserves wall-clock during TZ changes).
   - In UN, not in schedule (event was cancelled or rescheduled) → remove.
3. Cap pending count at 60 (Apple's hard limit is 64; leave 4 slots for
   summaries and one-offs).

**Interruption level:**
- `.timeSensitive` on `strike_*` and `pre_5` (pierces Focus modes; free
  entitlement, no review drama).
- `.active` on `morning_summary` and `heads_up_30`.
- **Never** request Critical Alerts — that's a life-safety entitlement
  and a review rejection vector.

**Single action** registered in a `UNNotificationCategory("HOMUNCULUS_EVENT")`:

```swift
UNNotificationAction(identifier: "ACK", title: "OK", options: .foreground)
```

On `didReceive` with `actionIdentifier == "ACK"`:

1. Cancel remaining strikes for that event:
   `removePendingNotificationRequests(withIdentifiers: ["ev.<id>.strike.5", ".10", ".15"])`.
2. POST `/ack { event_id: ..., kind: ..., acked_at: <iso> }` to the brain.
   The brain cancels the remaining strikes; honor the `cancelled_kinds`
   array it returns by also removing those identifiers from the local
   `UNUserNotificationCenter` queue.
3. Call the completion handler promptly.

Set the delegate in `application(_:didFinishLaunchingWithOptions:)` —
not in a view model, not later. Cold-launches from notification tap
deliver the response immediately.

## Watch mirroring

iOS auto-mirrors notifications to a paired Watch including the OK
action. No watchOS target, no `WatchConnectivity`, no second app.
You get buzz-on-wrist and tap-to-ack for free by shipping the phone
correctly. Verify on real hardware before RC.

## Tailscale

The boss already has Tailscale installed on Mac and phone. The app
treats the brain host as a configuration value:

```
defaults:
  brain_host = "mac-mini.<tailnet>.ts.net"
  brain_port = 8765
```

Surface it in Settings so the boss can change it if he renames the Mac.
No app-level Tailscale logic — the OS handles routing.

## Permissions

| Permission                      | When asked          | Plist key                                 |
| ------------------------------- | ------------------- | ----------------------------------------- |
| Microphone                      | First Talk tap      | `NSMicrophoneUsageDescription`            |
| Speech recognition              | First Talk tap      | `NSSpeechRecognitionUsageDescription`     |
| Notifications                   | First app launch    | (requested via UNUserNotificationCenter)  |

Time-Sensitive entitlement: free, declare in `Signing & Capabilities`.

## Accessibility (older user)

- Dynamic Type from the first pass.
- Large Talk button (≥ 88pt minimum tap target).
- VoiceOver labels on every interactive element.
- Haptics on capture start / end / ack.
- Press-and-hold AND press-to-start / press-to-cancel both supported
  (Settings toggle). Older users vary on which gesture is reliable.

## Testing on real hardware

Before any RC, run the boss's iPhone through:

1. Strike fires on locked phone; Watch mirrors; OK from the Watch
   cancels remaining strikes.
2. App killed (swipe up) between heads-up-30 and pre-5 — pre-5 still fires.
3. Phone rebooted mid-day — reconciliation pass on cold launch
   re-registers anything UN dropped.
4. Low Power Mode — strikes still fire (user-visible locals are not throttled).
5. Do Not Disturb / Focus — `.timeSensitive` strikes pierce.
6. Time-zone change (Settings → General → Date & Time) — remaining
   reminders fire at the event's original wall-clock.
7. 40 events over 3 days — rolling registrar stays under 60 pending.
8. Bluetooth headset connected during Talk — STT works, TTS plays
   through headset, disconnect mid-capture degrades gracefully.

Simulator doesn't reproduce most of these. Use the real iPhone 16.

## Open coordination items with the brain engineer

As of brain v1.2 (2026-06-08):

- `GET /reminders/upcoming` — **live.** Window-driven; combines strikes
  + daily summary rows. Documented above.
- `POST /ack` — **live.** Cancels remaining strikes; idempotent. See
  above.
- `POST /undo` — **still deferred to v1.3.** The 5-min undo window (see
  project memory) is on the next round.
- `GET /activity` — **still deferred to v1.3.** The JSONL log exists on
  the brain side; the HTTP surface isn't wired yet.

## Versioning

This spec tracks the project's `x.y` version. v1.0 is the contract above.
Significant changes (new transport, new audio model, ambient listening)
bump to v2.0. Smaller iterations (extra endpoint, polish) bump to 1.1.

Bump the version in the project memory entry at
`~/.claude/projects/-Volumes-GIT-CLAUDE/memory/project_homunculus.md`
and add a line to its version history when this spec changes.
