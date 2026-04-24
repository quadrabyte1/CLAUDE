# Homunculus v1 — Architecture and Build Plan

**Author:** Mori (Voice-First iOS Product Engineer, Homunculus Lead)
**Date:** 2026-04-22
**Status:** Plan for boss review. No code until approved.
**Prior art:** `owner_inbox/pax_homunculus_research.md` (absorbed, extended where I disagree)

---

## 1. Summary

Homunculus v1 is a single-user, device-local, voice-first scheduling assistant for iPhone whose one job is to make sure the boss does not miss a commitment. The boss presses Talk, speaks a query or a new event, hears the homunculus read the parsed result back, taps confirm, and the event is written to a local SQLite calendar. From that moment until the event is acknowledged, an escalation contract runs on `UNUserNotificationCenter`: a morning summary at 7:00, a 30-minute heads-up, a 5-minute pre-event, then four strikes at 0/+5/+10/+15. One "OK" button on the notification cancels the rest of the chain. If all four strikes pass unacked, the event drops into a missed log and shows up in tomorrow's summary with an offer to reschedule. No cloud. No third-party calendar sync. No second button on the notification. v1 is a reliability product, not a capability product — the feature list is intentionally short because each item in it has to hold under phone-off, time-zone-change, OS-update, and Low-Power-Mode adversarial conditions. Everything else is v1.5 or later.

## 2. Tech stack

| Area | Choice | One-line justification |
|---|---|---|
| iOS deployment target | **iOS 26.0** | Foundation Models requires iOS 26. No point pretending otherwise. |
| Device target | iPhone 16 (Apple Intelligence capable) | The boss's hardware; the only device v1 needs to work on. |
| Language | Swift 6 with strict concurrency on | Compile-time data-race safety in the audio/notification/DB actor soup is worth its weight. |
| UI | SwiftUI + `@Observable` | Kit's stack; boring-on-purpose; Dynamic Type first-class. |
| Local storage | **GRDB.swift over SQLite, WAL mode** | Confirming Pax. SwiftData still hits walls on complex predicates and migration sharpness in 2026. Calendar querying is real querying. |
| NLP | Apple Foundation Models with `@Generable` | On-device ~3B LLM, schema-constrained decoding, zero network. The locked spec demands this. |
| Voice input | **`SpeechAnalyzer` + `SpeechTranscriber` + `SpeechDetector`** | WWDC25 modular STT — faster and more accurate than `SFSpeechRecognizer`, and the legacy API is effectively deprecated on iOS 26. |
| Voice output | `AVSpeechSynthesizer` with premium Siri voice via `AVSpeechSynthesisVoice(identifier:)` | Barge-in via `stopSpeaking(at: .immediate)` is the only thing that makes this feel like a conversation. |
| Audio session | `AVAudioSession` `.playAndRecord` + `.duckOthers` + `.allowBluetooth`, configured once at launch | Single activation pattern; teardown with `.notifyOthersOnDeactivation` to prevent silent-activation-failure after lock. |
| Notifications | `UNUserNotificationCenter` with `UNCalendarNotificationTrigger` | Calendar triggers are wall-clock anchored; time-interval triggers drift. Non-negotiable. |
| Interruption level | `.timeSensitive` on strikes and pre-5; `.active` on summary and T-30 | Free entitlement, pierces Focus, no App Review drama. No Critical Alerts — that's a rejection vector for a memory-support app. |
| App architecture | Modular SPM: `CalendarCore`, `VoiceCapture`, `NLU`, `Scheduling`, `NotificationsKit`, `AppShell` | Keeps NLP and reminder logic testable without dragging the view layer. |
| Third-party deps | **GRDB only.** No analytics, no crash reporter, no networking library. | Every dependency is a privacy liability in a local-only app. Zero beyond GRDB. |

## 3. Data model

SQLite via GRDB, WAL mode, file at `Application Support/Homunculus/homunculus.sqlite` with Data Protection class `NSFileProtectionComplete`. Schema versioned from 1 via GRDB's `DatabaseMigrator`.

```sql
-- Migration v1

CREATE TABLE events (
  id                 TEXT    PRIMARY KEY,          -- UUID v4, lowercased
  title              TEXT    NOT NULL,
  starts_at_utc      INTEGER NOT NULL,             -- unix seconds, UTC
  ends_at_utc        INTEGER NOT NULL,             -- unix seconds, UTC
  tz_identifier      TEXT    NOT NULL,             -- IANA zone, e.g. "America/Los_Angeles"
  notes              TEXT,
  source             TEXT    NOT NULL,             -- 'voice' | 'manual' | 'rescheduled'
  source_utterance   TEXT,                         -- raw STT for debugging / audit
  created_at         INTEGER NOT NULL,
  updated_at         INTEGER NOT NULL,
  deleted_at         INTEGER                       -- soft delete, NULL if live
);
CREATE INDEX idx_events_starts       ON events(starts_at_utc) WHERE deleted_at IS NULL;
CREATE INDEX idx_events_day          ON events(starts_at_utc, tz_identifier) WHERE deleted_at IS NULL;

CREATE TABLE reminders (
  id               TEXT    PRIMARY KEY,           -- matches UN identifier, e.g. "ev.<uuid>.strike.0"
  event_id         TEXT    NOT NULL REFERENCES events(id) ON DELETE CASCADE,
  kind             TEXT    NOT NULL,              -- 'morning_summary'|'heads_up_30'|'pre_5'|'strike_0'|'strike_5'|'strike_10'|'strike_15'
  fire_at_utc      INTEGER NOT NULL,
  notification_id  TEXT,                          -- UN identifier if scheduled; NULL if not yet
  status           TEXT    NOT NULL,              -- 'pending'|'scheduled'|'fired'|'acked'|'cancelled'|'missed'
  scheduled_at     INTEGER,                       -- when we last called UN.add()
  fired_at         INTEGER,
  acked_at         INTEGER,
  created_at       INTEGER NOT NULL,
  updated_at       INTEGER NOT NULL
);
CREATE INDEX idx_reminders_event     ON reminders(event_id);
CREATE INDEX idx_reminders_fire      ON reminders(fire_at_utc, status);
CREATE UNIQUE INDEX uq_reminders_ek  ON reminders(event_id, kind);

CREATE TABLE missed_events (
  event_id              TEXT    PRIMARY KEY REFERENCES events(id),
  missed_at             INTEGER NOT NULL,             -- when the 4th strike passed unacked
  surfaced_in_summary   INTEGER NOT NULL DEFAULT 0,   -- boolean: included in a morning summary yet?
  rescheduled_event_id  TEXT    REFERENCES events(id) -- set when user rescheduled via next-morning offer
);

CREATE TABLE settings (
  key    TEXT PRIMARY KEY,
  value  TEXT NOT NULL                                 -- JSON-encoded
);
-- Seeded on first run:
--   morning_summary_time = "07:00"
--   morning_anchor_hour  = 9           (for "tomorrow morning" resolution)
--   conflict_fuzz_min    = 30
--   talk_mode            = "press_hold" (only option in v1; stored for v1.x forward-compat)

CREATE TABLE activity_log (
  id         INTEGER PRIMARY KEY AUTOINCREMENT,
  at_utc     INTEGER NOT NULL,
  kind       TEXT    NOT NULL,  -- 'stt_capture'|'nlp_parse'|'nlp_ambiguous'|'event_create'|'event_update'|'event_delete'|'reminder_schedule'|'reminder_fire'|'reminder_ack'|'reminder_miss'|'reconcile'|'tz_change'|'settings_change'|'error'
  event_id   TEXT,
  payload    TEXT               -- JSON
);
CREATE INDEX idx_activity_at ON activity_log(at_utc);

CREATE TABLE schema_meta (
  key    TEXT PRIMARY KEY,
  value  TEXT NOT NULL
);
-- Seeded: ('schema_version','1'), ('app_version', '<bundle-version>'), ('last_reconcile_at_utc', ...)
```

**Design notes:**

- **Time-zone rule:** UTC seconds + IANA `tz_identifier`, never offset. DST and travel break offset storage. An event scheduled at the boss's home zone stays anchored to home-zone wall-clock even if he travels — that's what the boss wants (see open question Q4 if I'm wrong).
- **`activity_log` is a DB table, not a file.** Justification: we already have SQL and a writer actor; an OSLog-backed file log means two reconciliation stories instead of one. The boss doesn't see this table; it's for me when something goes wrong. Rotate at 30 days / 10MB, whichever hits first.
- **Soft delete on events (`deleted_at`).** If the boss says "cancel coffee with Jane," I want to be able to explain what happened and when. Hard deletes destroy that audit trail.
- **`uq_reminders_ek`** enforces one reminder of each kind per event. Prevents duplicate strike_0s from a buggy rescheduler.
- **`source_utterance`** stored per event for debugging "why did it think I said that" — can be purged on user request.
- **Concurrency:** one actor-isolated `DatabaseQueue` writer; reads go through a `DatabasePool`.

## 4. Voice interaction pipeline

### 4.1 Add-event flow (happy path)

```
Talk button touch-down
  → Haptic .light
  → synthesizer.stopSpeaking(at: .immediate)        // barge-in if TTS was playing
  → AVAudioSession.setActive(true)
  → SpeechAnalyzer + SpeechTranscriber start
     · contextualStrings seeded with recent event titles + known people
     · SpeechDetector end-of-utterance 1.2s silence
Talk button touch-up (or SpeechDetector end)
  → Stop capture, final transcription
  → Haptic .light
  → FoundationModel.generate(ParsedSchedulingIntent.self, prompt:)
  → Deterministic date/time resolution in Swift (not in the prompt)
  → If parsedIntent.ambiguousFields non-empty  → clarifying TTS question (branch A)
    Else if parsedIntent.kind == .create        → confirmation (branch B)
    Else if parsedIntent.kind == .query         → conflict check (branch C)
    Else if parse failed entirely               → "I didn't catch that, say it again" (branch D)
```

**Branch B — confirmation (the only write path):**

```
Compose confirmation copy, e.g.:
  "Adding 'coffee with Jane' Tuesday April 28 at 2:00 PM for 30 minutes. Tap OK to save, or Cancel."
Speak it via AVSpeechSynthesizer (non-blocking, can be barge-in'd).
Show same copy on screen with two large buttons: "OK, save it" (primary) and "Cancel".
On OK:
  Writer actor:
    INSERT INTO events (...)
    INSERT INTO reminders (7 rows: morning_summary, heads_up_30, pre_5, strike_0, strike_5, strike_10, strike_15) with status='pending'
  Scheduler.reconcile(eventID:)  →  pushes rows into UN if within horizon, marks status='scheduled'
  Speak "Saved."
On Cancel: log to activity_log, discard.
```

**Branch A — ambiguity clarification (the most important output):**

```
ambiguousFields == ["startDate"] (e.g. "Tuesday" when today is Monday evening)
  → Speak + show: "Did you mean this Tuesday, tomorrow, or next Tuesday the 5th?"
  → One tap resolves; re-run the date resolution deterministically with the boss's answer.
  → Then fall into Branch B confirmation.
```

I am not letting the LLM guess dates. The ambiguous-fields list is the single most important output of the NLP layer — it's what converts the failure mode from "silent wrong event on the calendar" to "one extra tap."

### 4.2 Query flow (branch C — "can I have coffee Tuesday at 2?")

```
Parse → kind == .query, startLocal = resolved Tuesday 2 PM.
Query:
  direct   = events whose [start, end] intersects proposed [start, start+30min]
  fuzzy    = events starting within ±30 min of proposed start (boss-confirmed default)
Compose answer:
  direct non-empty   → "You have 'X' at 2:00. That's a conflict."
  fuzzy non-empty    → "You have 'X' at 1:45 — close to 2, but no direct conflict."
  both empty         → "You're clear Tuesday at 2. Want me to add coffee?"
Speak + display. If "Want me to add" and user says "yes" (another Talk press) → Branch B with pre-filled intent.
```

Query flow does not write to the DB. It reads, answers, offers. The follow-up add is a new utterance. Keeps the write path single-purpose.

### 4.3 `@Generable` schema sketch

```swift
@Generable
struct ParsedSchedulingIntent {
    @Generable enum Kind: String { case query, create, cancel, reschedule }

    let kind: Kind
    let title: String?
    let participants: [String]                 // names pulled from the utterance
    let startLocal: String?                    // ISO8601 local wall time, e.g. "2026-04-28T14:00:00"
    let durationMinutes: Int?                  // default 30 if nil on create
    let endLocal: String?                      // only if user said "until 3:30"
    let relativeDayHint: String?               // "today"|"tomorrow"|"tuesday"|"next tuesday"|nil — drives Swift resolver
    let relativeTimeHint: String?              // "morning"|"afternoon"|"evening"|"night"|nil
    let ambiguousFields: [String]              // authoritative: if non-empty, we MUST ask
    let lowConfidence: Bool                    // model's own flag
}
```

Date math is a Swift function taking `(relativeDayHint, relativeTimeHint, startLocal, now, userTZ, morningAnchorHour) -> (resolvedStartUTC, ambiguous: Bool)`. Pure, unit-testable, no model involvement.

## 5. Rolling notification scheduler

This is the hardest part of v1, and the part the boss needs most to actually work. Pax was right to flag it.

### 5.1 The horizon

- Target pending queue depth: **60** (leave 4 of Apple's 64 as headroom for morning summaries and one-off user actions).
- Scheduling horizon: **next 72 hours of events**. Any event starting > 72h out sits in `reminders` with `status='pending'` and `notification_id IS NULL` — not yet handed to UN.
- With 7 reminder rows per event, 60 / 7 ≈ 8.5 events of full coverage per 72h window. That's plenty for the boss's calendar shape. If the boss ever has a 10+ event day, headroom survives because morning summary + older events have already fired and are no longer in pending.

### 5.2 When the scheduler runs

A single `SchedulerService` actor owns the UN interface. It runs `reconcile()` on:

1. App cold launch (first thing after DB open, before UI).
2. App foreground (`UIApplication.willEnterForegroundNotification`).
3. After any `INSERT` / `UPDATE` / soft-delete on `events`.
4. After a reminder fires (from `willPresent` and `didReceive` delegate callbacks).
5. After an ACK (removes remaining strikes, then tops up).
6. On `NSSystemTimeZoneDidChangeNotification`.
7. On significant time change (`UIApplication.significantTimeChangeNotification`).

### 5.3 `reconcile()` — the core loop

```
1. Query UN: getPendingNotificationRequests() -> Set<String> of current UN identifiers.
2. Query DB: SELECT ... FROM reminders WHERE fire_at_utc > now AND fire_at_utc < now + 72h AND status IN ('pending','scheduled') ORDER BY fire_at_utc ASC LIMIT 60.
3. Diff:
   a. In DB but not in UN and fire_at_utc in future → schedule (UN.add) with UNCalendarNotificationTrigger
      built from DateComponents in the event's tz_identifier.
   b. In UN but not in DB (shouldn't happen but defend against it) → remove.
   c. In both → leave alone.
4. Past-due unacked pass:
   For each reminder with status='scheduled' and fire_at_utc < now - grace(60s):
     mark status='fired' if unacked, write activity_log 'reminder_fire' (missed-as-alert case).
   For each event whose strike_15 is > 30 min in the past with no acked_at on any strike:
     mark status='missed' on strike rows, INSERT into missed_events if not present,
     write activity_log 'reminder_miss'.
5. Update schema_meta.last_reconcile_at_utc = now.
```

### 5.4 Event-level operations

- **Create event:** Writer inserts event + 7 reminder rows all `status='pending'`. Scheduler `reconcile()` promotes the ones in-horizon to `status='scheduled'` in UN.
- **Edit event (time change):** tear down: `UN.removePendingNotificationRequests` for all `ev.<id>.*`; set all reminders `status='cancelled'`. Re-insert fresh reminder rows. Reconcile. Rationale: mutating reminder rows in place invites subtle drift; a clean rebuild is boring and correct.
- **Cancel event:** soft-delete event, set all reminders `status='cancelled'`, remove from UN by identifier prefix.
- **On ACK:** delegate handler immediately calls `UN.removePendingNotificationRequests(withIdentifiers: [ev.<id>.strike.N+1 ... strike.3])`. Update strike rows to `status='cancelled'` (for the future ones) and the acked one to `status='acked'` with `acked_at`. Reconcile top-up.

### 5.5 Calendar trigger construction

For an event with `starts_at_utc=S` and `tz_identifier="America/Los_Angeles"`:

```swift
let zone = TimeZone(identifier: event.tzIdentifier)!
var cal = Calendar(identifier: .gregorian); cal.timeZone = zone
let fireDate = Date(timeIntervalSince1970: TimeInterval(reminder.fireAtUTC))
var comps = cal.dateComponents([.year,.month,.day,.hour,.minute,.second], from: fireDate)
comps.timeZone = zone  // CRITICAL — wall-clock anchors to event zone
let trigger = UNCalendarNotificationTrigger(dateMatching: comps, repeats: false)
```

This is the difference between "fires at 2pm back home even after you fly to NYC" and "fires at 2pm NYC because the device TZ changed."

## 6. Escalation contract

Testable, explicit, with draft copy. Reliability beats cleverness — the copy is calm, short, and escalates without scolding.

| # | Label | When | Interruption | Sound/Haptic | Draft copy |
|---|---|---|---|---|---|
| — | Morning summary | 7:00 local | `.active` | Default | "Good morning. Today: 9:30 dentist, 2:00 coffee with Jane, 4:00 call with Alex. Yesterday's missed: none." |
| — | Heads-up 30 | T − 30 min | `.active` | Default | "In 30 minutes: coffee with Jane at 2:00." |
| — | Pre-5 | T − 5 min | `.timeSensitive` | Default + haptic | "5 minutes: coffee with Jane at 2:00." |
| 0 | Strike 0 | T + 0 min | `.timeSensitive` | Default + haptic | "Coffee with Jane is starting now. Tap OK when you see this." |
| 1 | Strike 1 | T + 5 min | `.timeSensitive` | Louder sound + haptic | "Still on? Coffee with Jane started 5 minutes ago. Tap OK." |
| 2 | Strike 2 | T + 10 min | `.timeSensitive` | Louder sound + haptic | "Reminder: coffee with Jane — 10 minutes ago. Tap OK." |
| 3 | Strike 3 | T + 15 min | `.timeSensitive` | Loudest sound + haptic | "Final reminder. Coffee with Jane. Tap OK or I'll log it as missed." |
| — | (after strike 3 unacked) | T + 15 min, silent | — | — | Write to `missed_events`. No alert. |

**Category and action registration (done once in `didFinishLaunchingWithOptions`):**

```
UNNotificationCategory(
  identifier: "HOMUNCULUS_EVENT",
  actions: [UNNotificationAction(identifier: "ACK", title: "OK", options: .foreground)],
  intentIdentifiers: [],
  options: [.customDismissAction]
)
```

Single action. No snooze. No reschedule-from-notification. Every addition dilutes the one tap the boss needs to make. I will push back if this is ever relitigated — it's the whole product philosophy.

**Missed-event handling:** after strike 3 passes and `acked_at` is still NULL, the `reconcile()` pass marks the event missed and inserts into `missed_events` with `surfaced_in_summary=0`. Tomorrow morning's summary flips the flag to 1 and offers a reschedule.

## 7. Morning summary

- **Scheduling:** one `UNCalendarNotificationTrigger` per day for the next 3 days, identifier `summary.<yyyy-mm-dd>`, trigger at 07:00 in the user's current `TimeZone.current`. Rebuilt on reconcile.
- **Not** a repeating trigger — the content changes every day, and repeating triggers fire the same payload every day. Daily individual triggers give us content flexibility at trivial queue cost (3 slots).
- **Composition time:** the trigger fires at 07:00; the `willPresent` delegate callback composes the *current* body text from the DB at fire time. **Correction:** that's wrong for locked-screen delivery, where `willPresent` doesn't fire. Real answer: compose the body when *scheduling*, and re-compose on every reconcile pass so it's up-to-date if events changed after 05:00 bedtime. Risk: a 6:30 AM event edit won't show up in the 7:00 summary. Acceptable — the boss can open the app and see it.
- **Content:**
  - Line 1: "Today: \<event1 at time\>, \<event2 at time\>, ..." (up to 5; "and 2 more" if over)
  - Line 2 (if applicable): "Yesterday missed: \<missed1\>. Tap to reschedule."
  - Empty-day copy: "Good morning. No events today."
- **Format:** single notification, multi-line body. Tapping it deep-links into the app's "Today" view, where the boss can tap any missed event to get a voice-driven reschedule flow (new event with pre-filled title).

## 8. Watch mirroring

v1 ships with **no watchOS target**. Everything we need is automatic:

- **Mirror:** iPhone notifications mirror to the paired Watch by default when the phone is locked or the Watch is active on the wrist. Free.
- **OK action on Watch:** the `UNNotificationAction(identifier: "ACK", title: "OK", options: .foreground)` mirrors automatically — it appears on the Watch notification detail. Tapping it wakes the iPhone app to deliver the response. **Confirmed via Apple docs; must verify on real hardware in M3.**
- **Haptic:** Watch plays a haptic automatically on Time-Sensitive notifications. No code.
- **Caveat to test:** the `.foreground` option on the action brings the iPhone forward when tapped from Watch. For an older user that might be desirable (shows that the ack landed) or annoying (phone lights up when they were just using Watch). I'll ship `.foreground` in v1 and revisit if the boss objects — changing it is a one-line edit.

**Non-goals in v1:** native Watch app, Watch complications, Watch-specific voice capture, Watch-only UI. All v1.5.

## 9. Division of labor — Mori vs Kit

| Component | Mori owns | Kit owns |
|---|---|---|
| SPM module layout | Designs module boundaries | Creates packages, wires up builds, manages dependencies |
| App shell / `@main` | Spec: delegate registration order, notification category registration, root coordinator lifecycle | Implements `UIApplicationDelegate` + `App` struct, environment wiring |
| SwiftUI views (all of them) | Specs: copy, button sizes, Dynamic Type behavior, flow | Implements every view; accessibility audit; tap targets |
| Navigation | Specs screens and transitions | `NavigationStack`, deep links from notifications, sheet/cover |
| `VoiceCapture` package | **Writes it.** `AVAudioSession`, `SpeechAnalyzer`, `SpeechTranscriber`, `SpeechDetector`, barge-in, permission prompting | Reviews for concurrency style; pairs on the press-and-hold gesture integration |
| `NLU` package | **Writes it.** Foundation Models client, `@Generable` types, prompt, deterministic date resolver, ambiguity handling | Reviews; wires into view model |
| `CalendarCore` package (schema + DAO) | **Writes it.** GRDB setup, migrations, schema, writer actor, reader pool, TZ handling | Reviews; handles any DB bridging into views |
| `Scheduling` / `NotificationsKit` | **Writes it.** `UNUserNotificationCenter` wrapper, category registration, rolling scheduler, delegate callbacks, reconciliation | Reviews |
| Confirmation UI | Specs exact behavior (TTS + text readback, button labels) | Implements view |
| Morning summary composer | **Writes composition logic.** Kit does nothing here | — |
| Settings screen | Specs fields | Implements view + binding to `settings` table |
| Activity log reader (dev menu, debug builds only) | Designs what's shown | Implements |
| Swift 6 concurrency review | — | Owns project-wide; Mori defers |
| Xcode project + signing + entitlements | — | Owns. Time-Sensitive entitlement, Info.plist keys for mic + speech, Data Protection Complete on DB file |
| Privacy Manifest + Nutrition Labels | Provides data-collection summary ("none beyond local") | Authors `PrivacyInfo.xcprivacy` |
| CI/CD (Fastlane + GH Actions) | — | Owns end to end |
| TestFlight + App Store submission | Provides app description framing ("memory support") | Owns submission, responds to review |
| Swift Testing unit tests for NLU / Scheduler / DAO | **Writes them** — these are reliability-critical | Reviews |
| SwiftUI snapshot tests | — | Owns |
| Device test matrix runs (M5) | **Runs on real iPhone 16** every RC | Observes, fixes platform-adjacent bugs |
| Accessibility (VoiceOver, Dynamic Type, tap targets) | Specs large-target expectations | Implements and audits |
| Localization (v1: en-US only) | — | Sets up `.xcstrings` for future-proofing |

**Mori's rule with Kit:** win on product behavior, yield on code style. When a PR touches behavior — notification copy, the ack-cancels-rest flow, the confirmation readback — my word is final. When it's Swift formatting, view composition, or which property wrapper, Kit's word is final.

## 10. Milestones

Sizing is in working days. These are honest estimates by someone who has lost a week to notification weirdness before. Pad your mental model another 20% for the unexpected.

| M | Scope | Size (days) | T-shirt |
|---|---|---|---|
| **M1** | Project skeleton: SPM packages, GRDB + schema v1, DB writer actor, writer tests, `Today` SwiftUI view that lists events from DB, manual "Add Event" form (no voice), Info.plist, entitlements, Data Protection. | **7** | M |
| **M2** | Voice pipeline: `AVAudioSession`, `SpeechAnalyzer`, press-and-hold Talk button, `contextualStrings`, `AVSpeechSynthesizer` with barge-in, permission prompting. Foundation Models integration, `@Generable` types, deterministic date resolver, ambiguity clarification flow. Confirmation readback UI. NLP unit tests. | **11** | L |
| **M3** | **The hard one.** `UNUserNotificationCenter` setup, category + action, delegate, rolling scheduler, reconciliation, TZ-correct triggers, ack-cancels-rest, missed-event logging, 7-reminder-per-event scheduling, 72h horizon top-up. Scheduler unit tests on synthetic clock. | **12** | L |
| **M4** | Morning summary (daily triggers, composition on reconcile, missed-event inclusion). Next-morning reschedule offer flow (voice-driven, reuses M2 pipeline). Query flow (branch C). Dev activity-log reader behind debug flag. | **7** | M |
| **M5** | Settings screen (morning time, fuzz window). Accessibility audit. Full reliability test matrix on real iPhone 16 (§11). Fixes. Privacy Manifest. TestFlight build. | **8** | M |
| **Total** | | **45 working days** | — |

~9 calendar weeks at a disciplined pace. M3 is where things go wrong; that's why it has the most headroom and why I'd rather cut a feature than cut M3 time.

## 11. Reliability test matrix

Every scenario below runs on a **real iPhone 16 on iOS 26.3.1+** with a paired Apple Watch before any RC is cut. Simulator doesn't reproduce Low Power Mode, TZ changes, lock-screen, or Watch mirroring faithfully.

1. **Strike 0 fires on locked phone; Watch mirrors; Watch OK tap cancels strikes 1–3.** Verify `UN.pendingNotificationRequests` empty of that event, `reminders.status = 'acked' / 'cancelled'` in DB.
2. **App killed (swipe up) between heads-up-30 and pre-5.** Pre-5 still fires. Strike chain still fires on schedule. Ack still works when app cold-launches.
3. **Phone powered off at strike-0 time; powered back on 7 minutes later.** Strike 0 delivered in Notification Center (not as alert, per iOS). Strike 1 at +5 min from original T fires as an alert. Reconciliation on launch detects missed strike 0 as fired-but-unacked. Ack on strike 1 cancels strikes 2–3.
4. **Phone powered off through all four strikes, powered back on 30 min after T+15.** Reconciliation marks event missed, pushes to `missed_events`. Next morning summary surfaces it.
5. **Device time-zone change (Settings → General → Date & Time, set zone manually from LA to NYC).** `NSSystemTimeZoneDidChangeNotification` fires; reconciliation runs; remaining strikes for LA-zone events still fire at LA wall-clock (because `DateComponents.timeZone` was set explicitly).
6. **Low Power Mode enabled before strike time.** Strikes still fire (user-visible locals are not throttled).
7. **Do Not Disturb / Focus mode enabled.** Time-Sensitive strikes pierce. Morning summary (`.active`) respects DND. Document this behavior for the boss.
8. **OS minor-version update while app is installed, with pending notifications.** Relaunch; reconciliation re-schedules anything UN dropped.
9. **40 events over 3 days stress test.** Rolling scheduler maintains ≤60 pending, ~4 headroom. No "scheduled in DB but missing from UN" gaps.
10. **Event edited 2 hours before fire time (title + time change).** Old UN requests removed, new ones scheduled under updated IDs. No ghost fires from stale identifiers.
11. **Event cancelled (voice "cancel my 2pm").** All 7 reminders torn down. No fires.
12. **Airplane mode enabled.** Full voice add flow works: STT, Foundation Models parse, DB write, reminder schedule. Proves offline-correct.
13. **Bluetooth headset connected during Talk.** Audio session routes correctly; STT works; TTS plays through headset; disconnect mid-capture gracefully falls back.
14. **Permission denied for mic on first Talk tap.** Homunculus surfaces a clear "I need the microphone to listen. Open Settings?" path. Doesn't crash.
15. **Phone storage full / DB write fails.** Confirmation UI surfaces a real error rather than silently failing. Activity log captures it.
16. **Cold launch from notification tap.** Delegate fires, ack is recorded, remaining strikes cancelled. Proves `didFinishLaunchingWithOptions` delegate registration is correct.

16 scenarios. All pass on real hardware, or the RC doesn't ship.

## 12. Open questions / risks

### Questions for the boss (ranked by how much they block me)

**Q1. Event-attached time zone behavior — whose wall-clock wins when you travel?**
My default: each event carries its own `tz_identifier` set at creation time (= user's zone then). If the boss creates "dentist Friday 10am" in LA and then flies to NYC on Thursday, the alert fires at 10am *LA time* (1pm NYC). My read is that's what the boss wants — the dentist appointment didn't physically move. But if the boss expected "10am wherever I am when Friday arrives," I should know now. This is a one-line change but it's load-bearing. **Recommend: zone-at-creation wins.** Boss confirms or corrects.

**Q2. Morning summary update freshness.**
If the boss edits an event at 6:45am, the 7:00am summary body was composed during the last reconcile (likely overnight). I don't have a way to rewrite the scheduled notification body between reconciles without re-scheduling it (which may re-fire). My call: accept the minor staleness, and tapping the summary always shows fresh content. **Flag if this is wrong.**

**Q3. Ack-cancels-rest — confirm this is the right behavior even mid-event.**
If the boss taps OK on strike 0 at T+1min, strikes 1/2/3 are cancelled and the event is acked. If he taps OK on strike 2 at T+12min, strikes 3 is cancelled and the event is acked. I believe this is what "one tap ends the chain" means but want it on record. **My read: yes, any OK ends the chain.**

**Q4. What should the boss see when no events exist?**
Empty "Today" view — what's there? I'm going with a warm, minimal empty state ("No events today. Tap Talk to add one.") plus the big Talk button. Flag if this should be more.

### Risks the boss should know

**R1. Foundation Models (~3B) quality on complex utterances.** For "move my Thursday dentist to Friday morning except keep the 10am call on Thursday," the on-device model may produce a partial or garbled intent. My mitigation is to detect multi-step shape in the parsed intent and tell the boss "that's a two-step change — try one at a time." I will NOT silently fall back to the cloud. The locked spec forbids it and I agree with the spec.

**R2. The 7:00 summary content-freshness issue (Q2 above).** Real but low-impact. Accepted tradeoff.

**R3. Watch `.foreground` ack behavior on older-user ergonomics.** Tapping OK on the Watch wakes the phone. That's either a pleasant confirmation or an annoyance. I'll know after the boss lives with it a week. Easy to flip.

**R4. iOS 26 adoption + Foundation Models availability edge cases.** If the boss ever has AI disabled in Settings (Apple Intelligence toggle), Foundation Models calls fail. I'll detect this at launch, show a clear "Apple Intelligence must be on for Homunculus to understand voice. Open Settings?" flow, and block voice input. DB and manual add still work.

**R5. Notification reliability is a black box.** Apple does not publish hard SLAs on local notification delivery under all conditions. My only defense is the reconciliation pass and the test matrix. Neither is a proof; both are evidence. I'm confident in the M3 design, but if something goes wrong in production the first thing I'll instrument is activity_log fire/miss telemetry so we can see the pattern.

**R6. Disagreement with a (non-locked) Pax suggestion: hybrid Path C.** Pax recommended a hybrid on-device-plus-Claude-fallback. The locked spec overrode that to pure on-device. I agree with the spec and will not pre-build the Claude path. If the boss eventually wants it, it's v1.x work with explicit per-utterance consent — not silent fallback. This is on record so it's not relitigated.

**R7. Scope creep temptation at M3.** When notification reliability gets hard (it will), the temptation is to skip to M4 and come back. Don't let me do that — M3 is the product. If I start drifting, drag me back.

---

**End of plan. Awaiting boss approval before a line of Swift is written.**
