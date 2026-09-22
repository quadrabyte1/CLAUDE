# Homunculus Test Plan

**v0.1 — 2026-09-22 — Larry**

System state at plan creation: Herman v1.8.0, Sprite v0.8.1, mac_calendar_bridge v0.2.0, mac_reminders_bridge v0.1.1, mac_notes_bridge v0.1.0, mac_notifier v0.1.0, dashboard v0.1.

Tick each checkbox as you go. Row `#` maps to a specific voice memo utterance + verification. "Say" is verbatim — dictate exactly. "Expect" is the pass condition.

Dashboard: `http://localhost:8765/dashboard/` — leave it open in a browser tab; every capture appears within ~15 sec.

---

## 1. Core verbs — the four intents

- [x] **1a — schedule / calendar event**
  Say: *"Schedule a haircut on October 15th at 3 PM."*
  Expect: Calendar.app "Homunculus" list gets `haircut` on Oct 15 2026, 3:00–3:30 PM.

- [x] **1b — remind / to-do with due date**
  Say: *"Remind me to renew the car registration on October 30th at 10 AM."*
  Expect: Reminders.app "Homunculus" list, `renew the car registration`, due Oct 30 2026 10:00 AM.

- [ ] **1c — handle / to-do no time**
  Say: *"Handle picking up the dry cleaning on Friday."*
  Expect: Reminders.app entry `picking up the dry cleaning` (default 8 AM next business morning).

- [ ] **1d — note / free-form**
  Say: *"Take a note that the porch light bulb is 60 watt."*
  Expect: Notes.app "Homunculus" folder, note titled `porch light bulb is 60 watt` (or similar), body preserved.

---

## 2. Date resolution — Herman v1.7 roll-forward + v1.8 PM inference

- [ ] **2a — roll bare past date forward**
  Say: *"Schedule dinner on September 20th at 6 PM."*
  Expect: Event resolves to **Sept 20 2027** (Sept 20 2026 has passed → rolls forward).

- [ ] **2b — future date stays this year**
  Say: *"Schedule dinner on December 15th at 7 PM."*
  Expect: Event on **Dec 15 2026** (still future — no roll).

- [ ] **2c — relative "tomorrow"**
  Say: *"Schedule dentist tomorrow at 9 AM."*
  Expect: Event on Sept 23 2026 (day after today).

- [ ] **2d — bare hour 1-5 with schedule → PM (v0.8.1)**
  Say: *"Schedule appointment at 3."*
  Expect: Time resolves to **3:00 PM**, `ambiguous=[]`, event created.

- [ ] **2e — bare hour 6 stays ambiguous**
  Say: *"Schedule dinner at 6."*
  Expect: **Inbox** entry — 6 could be 6 AM or 6 PM.

- [ ] **2f — named time "noon"**
  Say: *"Schedule lunch at noon on Wednesday."*
  Expect: 12:00 PM event on the coming Wednesday.

---

## 3. Ambiguity + clarifying flow

- [ ] **3a — remind at bare 3 stays ambiguous**
  Say: *"Remind me to take medication at 3."*
  Expect: **Inbox** with Herman's clarifying question about AM/PM. Reminders app gets NOTHING for this one.

- [ ] **3b — colon disqualifies the PM override**
  Say: *"Schedule meeting at 5:30."*
  Expect: **Inbox** with clarifying question (5:30 could be AM or PM; the 1-5 rule only fires for bare hours without minutes).

- [ ] **3c — low-confidence memo**
  Say: any mumbled or noisy memo where whisper conf will land below 0.6.
  Expect: **Inbox** with low-confidence flag.

- [ ] **3d — inbox exists and is readable**
  Open: `~/sprite/inbox/2026-09-22.md`
  Expect: Entries from 3a, 3b, 3c with `**Herman asks:**` blocks in bold.

---

## 4. Delivery to Apple apps + iCloud

After 1a-d, check on Mac AND phone:

- [ ] **4a — Calendar.app** contains 1a's haircut event.
- [ ] **4b — Reminders.app** contains 1b + 1c.
- [ ] **4c — Notes.app** contains 1d.
- [ ] **4d — iPhone** — wait 60-90 sec after Mac appears, verify all three synced to phone.

---

## 5. Notifications — mac_notifier

- [ ] **5a — future event → T-30 fires**
  Set up: record a schedule memo for exactly 2 hours from now.
  Expect: Mac notification at ~90 minutes from now (T-30 for the event). Branded "Script Editor" (documented cosmetic issue).

- [ ] **5b — 7 AM morning summary**
  Setup: any event on tomorrow's date.
  Expect: Mac notification at 7 AM tomorrow summarizing the day.

- [ ] **5c — handle strike chain**
  Setup: record a handle for tomorrow's default time (8 AM auto-set).
  Expect: Mac notifications at 7:30 (T-30), 7:55 (T-5), 8:00 (T+0), 8:05, 8:10, 8:15.

---

## 6. Dashboard

- [ ] **6a — dashboard loads**
  Open: `http://localhost:8765/dashboard/`
  Expect: Reverse-chronological feed, latest capture at top.

- [ ] **6b — new memo shows within 5 sec**
  Setup: record any memo → wait 15 sec → dashboard should auto-refresh with new row.

- [ ] **6c — row expand shows details**
  Click any row → panel expands with `raw_text`, `event_id`, `written_path`, confidence.

---

## 7. Reliability

- [ ] **7a — sleep + wake**
  Force sleep (Apple menu → Sleep) for ~1 minute, wake.
  Expect: All services still running (`launchctl list | grep -iE "sprite|homunculus"` shows 6 entries with PIDs). Dashboard still loads.

- [ ] **7b — capture during sleep**
  Sleep Mac → record memo on phone → wake Mac.
  Expect: Memo processes within ~30 sec of wake (iCloud syncs then Sprite cold-boot sweep picks it up).

- [ ] **7c — reboot survivability**
  Reboot Mac. After login:
  - [ ] All 6 launchd services running
  - [ ] Dashboard loads
  - [ ] Any previously-captured memo still in vault

---

## 8. Edge cases + regressions

- [ ] **8a — explicit year preserved**
  Say: *"Schedule board meeting on March 15th 2028 at 2 PM."*
  Expect: Event on March 15 **2028**, not 2026 or 2027.

- [ ] **8b — verb classification robustness**
  Say: *"Take a note that Homer's my dog."*
  Expect: verb=note (the word "note" isn't miscoded as schedule).

- [ ] **8c — compound sentence**
  Say: *"Remind me to feed the cats at noon and again at 6 PM."*
  Expect: LLM picks one intent — likely just the first. Documented limitation, not a bug.

- [ ] **8d — idempotency**
  Record the SAME memo twice back to back (word-for-word if you can).
  Expect: Second dedupes at the audio-fingerprint level; no duplicate event.

- [ ] **8e — Ollama unavailable**
  Setup: `ollama stop qwen2.5:7b`, then record.
  Expect: Sprite marks record as `error` disposition, logs cleanly, doesn't crash-loop. Bring Ollama back: `ollama run qwen2.5:7b`, delete the error entry, memo re-flows.

---

## 9. Known gaps — DO NOT TEST (won't work by design)

- **`avoid` verb** — never wired to a delivery surface.
- **`paste` verb** — Kit's iOS client not built yet.
- **Phone-side notifications** — mac_notifier fires locally on the Mac only; iCloud doesn't propagate Mac notifications to phone. Would need Kit's iOS client.
- **Compound sentences** — LLM picks one intent, others silently dropped.
- **Two-way sync** — Calendar / Reminders / Notes edits on the phone don't propagate back to Herman's vault.

---

## Test log — record pass/fail with date

| # | Ran | Passed? | Notes |
|---|-----|---------|-------|
| 1a | | | |
| 1b | | | |
| ... | | | |
