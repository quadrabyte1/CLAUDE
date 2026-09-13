`v0.1 — 2026-09-12`

# Sprite iOS Scoping — Mori

## 1. iCloud Voice Memos sync — verified

**Confirmed path on macOS 26.5:** `~/Library/Group Containers/group.com.apple.VoiceMemos.shared/Recordings/` (group container present, entitlement `com.apple.security.application-groups` on `/System/Applications/VoiceMemos.app` confirms this is the shared storage bucket for the app + widget + daemon).

**Critical finding — TCC blocks direct access.** The container is user-owned but `Operation not permitted` for any process without Full Disk Access. `sudo` alone is insufficient (macOS TCC gates the group container regardless of uid). **Any Sprite watcher must run as a process with FDA granted in System Settings → Privacy & Security → Full Disk Access.** For a launchd `LaunchAgent`, that means either (a) the agent binary itself gets FDA, or (b) a helper CLI it invokes does.

**Sync mechanism.** Voice Memos uses **CloudKit** (private container `com.apple.voicememos.datastore.Cloud`), *not* CloudDocs / iCloud Drive. Files aren't dribbled as flat `.m4a` blobs into an iCloud Drive folder — the CoreData store `CloudRecordings.db` in the group container references `.m4a` audio files that `voicememod` materializes into `Recordings/`. Implication: `.icloud` placeholder stubs are unlikely (CloudKit isn't file-shim-based), but we should still test with real memos before committing.

**Sync latency (documented ballpark).** Phone → Mac on Wi-Fi: 5–30 seconds after the memo finishes recording. Cellular: 15–90 seconds. Push arrives via APNs; the daemon materializes on receipt. Real-world verification requires Thomas recording a test memo — deferred to first integration test.

**Is sync currently ON?** Cannot verify from this session (TCC blocks folder listing). Empirical test: Thomas records one memo on the phone and Rune's watcher tails the folder for a new `.m4a` within 60 seconds. If it lands, sync is on.

## 2. Phone-side UX — recommendation

**Recommend option (a): built-in Voice Memos app.**

Zero install, zero code, works today if iCloud sync is on. Thomas already knows the UI. Route memos to Sprite on the *Mac side* by whisper-transcribing every new memo and letting Rune's intent parser decide `schedule | note | handle | avoid` — the phone doesn't need to know Sprite exists.

Reject (b) for v1 because a custom Shortcut/SwiftUI recorder means new install friction, permission prompts, another thing for Thomas to remember to open, and it wouldn't survive iOS updates as cleanly as the first-party app. A tiny Shortcut to prepend a title marker ("sprite: ...") is tempting but the LLM parser already discriminates intent well enough that a title marker is redundant.

Revisit (b) only if we see confusion in the parse pipeline about non-Sprite memos (dictation drafts, song ideas). For those, a Shortcut that writes to a dedicated sub-folder in iCloud Drive is a cleaner escape hatch than a Voice Memos title marker.

## 3. Kit handoff — Herman phone client

Sprite unblocks Kit. Coordination notes for Kit (do not ask him to touch anything today — just get on the same page):

- **Sprite-generated reminders should be indistinguishable from Herman-native ones in the phone client UI.** Same shape, same ack path. Reduces cognitive load — Thomas shouldn't need to know where a reminder came from.
- **Ack API is unchanged.** Sprite emits Herman-shaped records via Herman's existing FastAPI (`POST /reminders`), so ack lands on Herman's existing `/ack` endpoint regardless of origin. Kit's client needs no branch.
- **Optional origin tag.** Add an internal `source: "sprite" | "herman"` field on the record for morning-summary attribution ("Sprite captured 3 new items yesterday") and debugging. Not user-facing.
- **What Kit needs from Sprite:** nothing new. Herman's API surface is the contract; Sprite is just another producer.

## 4. Top-3 risks

1. **TCC / Full Disk Access requirement for the watcher.** launchd agents don't inherit FDA automatically; the granting binary must be the one that reads. If Rune's watcher runs from `/Volumes/GIT/...` (nosuid external volume), FDA gets fussy — likely need a boot-volume copy at `~/.local/bin/` per project memory.
2. **CloudKit sync is opaque.** No API to poll "is sync healthy right now?" — we get files or we don't. If sync silently regresses (iCloud outage, storage full, account signed out), Sprite goes deaf without warning. Need a heartbeat: if no memos in 72 h *and* the phone reports recordings exist, flag it in morning summary.
3. **iCloud storage tier / quota.** Voice Memos count against iCloud storage. Thomas's tier unknown. If he's on the 5 GB free plan and it fills, sync stops silently. Confirm tier at kickoff; recommend 200 GB minimum for headroom.
