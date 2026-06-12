# Homunculus iOS Client — v1.0

**Design version:** 1.2  
**iOS target:** 18.0+  
**Swift:** 6.0  
**Built against brain:** v1.2 (70 tests passing)

---

## What this is

A first-draft iOS companion app for the Homunculus Mac brain. Text-only capture
(voice is deferred to v1.3 — see `OPEN_QUESTIONS.md §OQ-2`). Connects to your
Mac mini over Tailscale. Registers reminder notifications locally and acks them
back to the brain.

### What works in v1.0

- Text capture → brain → spoken reply displayed on screen
- Confirmation flow (brain says "sounds right?" → tap OK → event written)
- Clarifying question loop (brain asks "what time?" → you answer → re-captured)
- Inbox filing display
- Reminder pull: GET /reminders/upcoming every 60s + on launch + on foreground
- Reminder reconciliation: adds new reminders, removes cancelled/acked ones
- Ack from notification "OK" button → POST /ack → brain cancels strike chain
- Time-Sensitive notifications for strikes/pre_5; .active for morning_summary/heads_up_30
- Today's events list (GET /events)
- Settings screen with editable brain URL

### What doesn't work yet (deferred)

- Voice input (text field only — see `OPEN_QUESTIONS.md §OQ-2`)
- TTS readback (no AVSpeechSynthesizer yet)
- Activity/capture history viewer (blocked on brain endpoint — `OPEN_QUESTIONS.md §OQ-3`)
- Undo (brain endpoint doesn't exist yet — `OPEN_QUESTIONS.md §OQ-4`)

---

## Setup

### 1. Prerequisites

- Xcode 16+ (Swift 6)
- iPhone running iOS 18+
- Mac mini brain running: `cd Homunculus/brain && python -m homunculus_brain.server` on port 8765
- Tailscale installed on both Mac and iPhone, connected to the same tailnet

### 2. Find your Tailscale hostname

On the Mac, run:
```
tailscale status
```

Look for your Mac mini's address. It will look like:
```
mac-mini   100.x.x.x   <your-tailnet>.ts.net   ...
```

The full hostname is something like `mac-mini.frosty-llama.ts.net`.
You can also find it in the Tailscale iOS app under "My devices".

### 3. Open in Xcode

```
open Homunculus/ios/Homunculus.xcodeproj
```

### 4. Configure signing

- Select the **Homunculus** target
- Signing & Capabilities → Team → select your Apple ID
- Bundle identifier: `com.homunculus.ios` (change if needed)

### 5. Add Time-Sensitive Notifications entitlement

- Signing & Capabilities → tap "+" → search "Time Sensitive Notifications" → add it
- This is a free entitlement, no App Review approval needed

### 6. Fix the critical-sound bug (OQ-8)

In `Homunculus/Notifications/ScheduleRegistrar.swift`, find:
```swift
content.sound = row.kind.isUrgent ? .defaultCritical : .default
```
Change to:
```swift
content.sound = .default
```
(The Time-Sensitive interruption level handles piercing Focus/DND; `.defaultCritical`
requires a separate entitlement we don't want.)

### 7. Build and run on your iPhone

Select your iPhone as the destination and hit Run (⌘R).

### 8. Set the brain URL

On first launch, go to **Settings** tab → tap **Edit connection** → enter:
- Host: `mac-mini.your-tailnet-name.ts.net` (your real tailnet hostname)
- Port: `8765`

Tap **Save** → tap **Test connection** → should show "Connected ✓".

### 9. Grant notification permission

The app will request notification permission on first launch. Tap **Allow**.

---

## Testing the full capture → reminder → ack flow

This is the recommended first test on return from Portugal.

### Step 1: Create an event

In the **Capture** tab, type:
```
coffee with Jane tomorrow at 10am
```
Tap send. The brain should respond with a readback like:
> "Thursday June 25 at 10:00 AM for 60 minutes. Sound right?"

Tap **OK, save it**.

### Step 2: Verify the reminder registered

Go to **Today** tab → "Upcoming Reminders" section. You should see reminder rows for
the coffee event (heads_up_30, pre_5, strike chain) listed.

### Step 3: Wait for a notification (or fast-forward by capturing a past-time event)

The brain will fire reminders at their scheduled times. On the phone (even locked),
you'll see the Homunculus banner.

To test immediately without waiting: capture an event 2 minutes in the future:
```
standup meeting today at [current time + 2 minutes]
```
Wait 2 minutes. A notification should fire.

### Step 4: Ack the notification

When the notification fires, pull it down and tap **OK**. This posts `/ack` to the brain.
The brain cancels the remaining strikes. On the next reconciliation pull (within 60s),
the strike notifications should disappear from **Today → Upcoming Reminders**.

### Step 5: Verify Watch mirroring (if you have an Apple Watch)

The notification automatically mirrors to the Watch. You should see it on your wrist.
Tapping **OK** on the Watch acks just like the phone.

---

## Running unit tests

```
xcodebuild test \
  -project Homunculus/ios/Homunculus.xcodeproj \
  -scheme Homunculus \
  -destination 'platform=iOS Simulator,name=iPhone 16,OS=18.0' \
  -testPlan HomunculusTests
```

Or in Xcode: select HomunculusTests scheme → ⌘U.

**What the tests cover:**
- `BrainModelTests.swift` — JSON encode/decode for all wire types (CaptureResponse,
  ReminderRow, AckResponse, ParsedIntent, HealthResponse, date parsing, URL building)
- `ReconciliationTests.swift` — the reminder diff algorithm (fresh start, no-change,
  acked-event cleanup, deleted-event cleanup, new-event addition, past-row skipping,
  managed-identifier detection, strike-ID generation)

---

## Architecture overview

```
Homunculus/
├── HomunculusApp.swift       — @main; sets up notification delegate, calls startup()
├── AppSettings.swift         — @AppStorage keys and defaults
├── Models/
│   └── BrainModels.swift     — Codable mirrors of Python Pydantic schemas
├── Networking/
│   └── BrainClient.swift     — URLSession + async/await; stateless HTTP client
├── Notifications/
│   ├── ScheduleRegistrar.swift — reconcile brain schedule with UNUserNotificationCenter
│   └── NotificationDelegate.swift — willPresent + didReceive("ACK") → POST /ack
├── ViewModels/
│   └── BrainService.swift    — @Observable coordinator; owns polling loop
└── Views/
    ├── ContentView.swift      — TabView root
    ├── CaptureView.swift      — Text input + response display
    ├── ConfirmationSheet.swift — Calendar confirm/cancel sheet
    ├── TodayView.swift        — Today's events + upcoming reminders
    └── SettingsView.swift     — Brain URL config + notification status
```

**Key design decisions:**

1. `BrainClient` is stateless — all session state lives in `BrainService`.
2. `ScheduleRegistrar` is a `@MainActor` singleton — all UNUserNotificationCenter
   interactions happen on the main actor to avoid races.
3. `NotificationDelegate` is held strongly by `@State` in `HomunculusApp` — the delegate
   must outlive every notification response, including cold-launch acks.
4. The 60-second polling loop lives in `BrainService`. It is cancelled and restarted
   on each call to `startup()`. No background fetch, no push — purely local polling.
5. Reminder identifiers are `"<event_id>:<kind>"`. The colon separator + known ReminderKind
   values are used to detect "managed" notifications and avoid clobbering other apps.

---

## Brain API quick reference

All endpoints at `http://<brain-host>:8765/`.

| Endpoint | Method | Purpose |
|---|---|---|
| `/health` | GET | Confirm brain is alive |
| `/capture/text` | POST | Send text; get action + spoken_reply |
| `/capture/confirm` | POST | Confirm a calendar write |
| `/events` | GET | Today's events (`?day=YYYY-MM-DD`) |
| `/reminders/upcoming` | GET | Next 72h schedule (`?window_hours=72`) |
| `/ack` | POST | Ack a reminder; brain cancels remaining strikes |

---

## Troubleshooting

**"Brain unreachable" on launch:**
1. Is the brain running? `curl http://localhost:8765/health` on the Mac.
2. Is Tailscale connected on both devices? Check the iOS Tailscale app.
3. Is the hostname in Settings correct? Try `curl http://<your-hostname>:8765/health`
   from an iOS device browser (or the Tailscale "Test connection" in Settings).

**Notifications not firing:**
1. Is notification permission granted? Settings app → Notifications → Homunculus.
2. Is Time-Sensitive Notifications entitlement added? (Xcode → Signing & Capabilities)
3. Is Focus/DND blocking them? Time-Sensitive should pierce DND, but check if the
   entitlement is actually in the `.entitlements` file.

**Confirmation tap does nothing:**
If the confirm POST fails, check the brain is reachable. The brain URL in Settings must
be correct and Tailscale must be connected.
OQ-1 (ParsedIntent echo) was resolved in brain v1.2.1 before this client shipped —
the brain echoes back the parsed intent so confirm uses the exact same parse.

---

## What to try first on June 23

1. Open the project, fix OQ-8 (`.defaultCritical` → `.default`), and set your Developer Team.
2. Run the app on your phone. Set the brain URL. Tap "Test connection."
3. Type a capture. See the response. Confirm if it's a calendar event.
4. Check Today → Upcoming Reminders.
5. Run the unit tests (⌘U). They should all pass without a device.
6. Then try the full end-to-end flow described in the "Testing" section above.
7. Come back and tell Kit / Rune what felt wrong — that becomes the v1.1 list.
