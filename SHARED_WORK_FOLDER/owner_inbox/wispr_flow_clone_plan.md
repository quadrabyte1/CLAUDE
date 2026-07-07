# Wispr Flow Local Clone — Implementation Plan

**Author:** Wren (Voice-First Mac Productivity Specialist)
**Date:** 2026-07-06
**Task:** Workspace #494
**Fork basis:** [VoiceInk](https://github.com/beingpax/VoiceInk) (GPL-3.0, ~5.4k stars, commits as of 2026-07-06)
**Target machine:** Apple Silicon Mac, macOS 26 (Darwin 25.5), Ollama already installed
**LLM-stage spec:** See `owner_inbox/wispr_flow_clone_ollama_stage.md` (Rune, in parallel)

---

## Skimmable Summary

| Phase | Name | Effort | Gate |
|---|---|---|---|
| M0 | Fork + first local build | 2–4 hrs | Stock VoiceInk runs, records, transcribes |
| M1 | Ollama-backed AI Enhancement ON | 1–2 hrs | Dictation → cleaned text via local Ollama |
| M2 | Hotkey + UX parity | 3–6 hrs | Right-Option hold-to-talk, flow-bar indicator |
| M3 | Tuning, dictionary, hardening | 4–8 hrs | Personal dictionary works; latency <1 s felt |

**Total effort estimate:** 10–20 hours over several sessions. Most of that is M3 prompt-engineering iteration, not code volume. The surprising finding (detailed below) substantially reduces M1 from "write an Ollama integration" to "configure the one that's already there."

> **KEY FINDING — Read this first:**
> VoiceInk already ships a first-class, production-quality Ollama integration. `Services/OllamaService.swift` provides connection management, model discovery, and text generation. `Services/AIEnhancement/AIService.swift` defines `AIProvider` as a 15-case enum that includes `.ollama` as an explicit named case. `Services/AIEnhancement/AIEnhancementService.swift` routes `.ollama` traffic to `OllamaService` with configurable timeout, temperature (0.3), and base URL (default `http://localhost:11434`). The Ollama base URL, model selection, and system prompt are all user-configurable through the existing Settings UI. **M1 is a configuration task, not a coding task** — point the UI at your local Ollama and select a model. Rune's spec will inform prompt-engineering choices but no new Swift code should be required for the basic integration.

---

## Section 1 — Fork + Build Setup

### 1.1 Prerequisites

| Requirement | Version / Notes |
|---|---|
| Xcode | Latest stable (26.x / Tahoe). `BUILDING.md` says "latest recommended." The macOS 26 SpeechAnalyzer API (`ENABLE_NATIVE_SPEECH_ANALYZER` build flag) requires the Tahoe SDK. |
| macOS | 26 (Darwin 25.5) — already met. NativeAppleTranscriptionService gates on `#available(macOS 26, *)`. |
| Swift | Ships with Xcode; no separate install needed. |
| Homebrew | For `make` toolchain; already likely present. |
| Disk space | ~3–5 GB for Xcode + whisper.cpp XCFramework + model weights. |
| Ollama | Already installed — shared with Homunculus on `localhost:11434`. |

### 1.2 Fork procedure

1. Fork `beingpax/VoiceInk` to your GitHub account (or create a private repo mirror if you want no public fork visible). Since this is personal use only, GPL-3.0 poses no distribution obligation.
2. Clone locally: `git clone git@github.com:<you>/VoiceInk.git ~/VoiceInk-local`
3. Add upstream remote for future upstream pulls: `git remote add upstream https://github.com/beingpax/VoiceInk.git`
4. Create a personal branch: `git checkout -b personal/local-ollama`

### 1.3 Build steps (from `BUILDING.md`)

The repo ships a `Makefile` that handles all dependency compilation.

```bash
cd ~/VoiceInk-local
make local          # builds whisper.xcframework, signs with ad-hoc cert via LocalBuild.xcconfig
```

`make local` uses `LocalBuild.xcconfig` + `VoiceInk.local.entitlements` — **no Apple Developer account required.** This is the correct path for personal use.

For active development, `make dev` builds and launches the app directly.

**Expected first-run time:** 15–30 minutes (whisper.cpp compilation). Subsequent builds are incremental.

### 1.4 Code signing for personal use

VoiceInk's `make local` path uses ad-hoc signing, which works for running on your own machine. You do not need a paid developer certificate. The entitlements file `VoiceInk.local.entitlements` is pre-configured for this. If macOS Gatekeeper complains: `xattr -dr com.apple.quarantine VoiceInk.app` after first build.

### 1.5 Enabling the SpeechAnalyzer engine (macOS 26 fast path)

The NativeAppleTranscriptionService (SpeechAnalyzer) is gated behind a build flag. To enable it:

In `VoiceInk.xcodeproj`, add `ENABLE_NATIVE_SPEECH_ANALYZER=1` to the Debug and Release configurations under Build Settings → User-Defined. This unlocks the macOS 26 ANE-accelerated transcription path (~2× faster than Whisper large-v3-turbo per Pax's research). The code falls back gracefully on older OS if the flag is ever removed.

### 1.6 External volume / nosuid note

The repo lives on `/Volumes/GIT` which is mounted `nosuid` — launchd cannot execute scripts from there directly. VoiceInk is a login-item macOS app launched via Launch Services (not launchd), so **this does not affect the app at all.** The constraint only matters if you later add a launchd LaunchAgent (e.g., for dictionary sync). If that day comes, put the agent script in `~/.local/bin/` on the boot volume.

---

## Section 2 — Codebase Orientation

### 2.1 Repository map (verified 2026-07-06)

```
VoiceInk/
├── Shortcuts/                  # CGEventTap-based global hotkey system (no KeyboardShortcuts pkg)
│   ├── ShortcutMonitor.swift   # CGEventTap; fires onKeyDown / onKeyUp callbacks
│   ├── RecordingShortcutManager.swift  # toggle / push-to-talk / hybrid modes
│   ├── Shortcut.swift          # Key+modifier struct; supports kVK_RightOption explicitly
│   └── ShortcutStore.swift     # UserDefaults persistence
├── Transcription/
│   ├── Engine/
│   │   ├── VoiceInkEngine.swift          # top-level coordinator
│   │   ├── TranscriptionPipeline.swift   # ASR → filter → AI Enhancement → delivery
│   │   ├── TranscriptionServiceRegistry.swift  # engine selection
│   │   └── TranscriptionDelivery.swift   # text injection
│   ├── Native/
│   │   ├── NativeAppleTranscriptionService.swift  # SpeechAnalyzer (macOS 26, behind build flag)
│   │   └── NativeAppleSpeechAssetManager.swift
│   ├── Whisper/                # whisper.cpp XCFramework bridge
│   ├── FluidAudio/             # Parakeet engine (via FluidAudio)
│   └── Cloud/                  # Cloud ASR (Deepgram, AssemblyAI, etc.)
├── Services/
│   ├── AIEnhancement/
│   │   ├── AIService.swift               # AIProvider enum (15 cases including .ollama)
│   │   ├── AIEnhancementService.swift    # orchestrator; routes .ollama to OllamaService
│   │   ├── AIChatCompletionService.swift # OpenAI-compatible + Anthropic path
│   │   ├── CustomAIProviderManager.swift # custom endpoint config (UUID, name, baseURL, model)
│   │   ├── LocalCLIService.swift         # shell-out path for local models
│   │   └── ReasoningConfig.swift
│   ├── OllamaService.swift               # Ollama connection, model discovery, generation
│   └── APIKeyManager.swift
├── Paste/
│   ├── CursorPaster.swift     # NSPasteboard save-set-Cmd-V-restore; AppleScript + CGEvent paths
│   ├── ClipboardManager.swift # transient pasteboard type support
│   └── PasteMethod.swift
└── Views/
    ├── Recorder/
    │   ├── MiniRecorderView.swift     # compact floating recorder panel
    │   ├── NotchRecorderView.swift    # notch-integrated recorder UI
    │   └── AudioVisualizerView.swift  # waveform feedback during recording
    └── Settings/
        └── SettingsView.swift         # includes AI provider/model picker
```

### 2.2 How the AI Enhancement stage is plugged in

`TranscriptionPipeline.run()` sequence:

1. ASR (SpeechAnalyzer or Whisper or Parakeet)
2. Filtering + word replacements (personal dictionary)
3. **AI Enhancement** — calls `AIEnhancementService.enhance(text:config:context:)` if `isConfigured() && isEnabled`
4. Delivery via `TranscriptionDelivery` (paste)

The enhancement stage is **entirely optional and skipable at runtime** — if unconfigured or if the `isEnabled` toggle is off, the pipeline delivers the raw (filtered) ASR transcript. Minimum word count for enhancement is configurable to avoid burning LLM time on single-word dictations.

### 2.3 How pluggable the enhancement stage is — bottom line

**Extremely pluggable.** The `AIProvider` enum has 15 cases. `.ollama` is a first-class named case with dedicated routing in `AIEnhancementService`, a dedicated `OllamaService` class that handles model discovery from `localhost:11434`, and UserDefaults-persisted base URL + model name. No code changes are needed to use Ollama. **This is a configuration task.**

Additionally, `CustomAIProviderManager` lets you define arbitrary OpenAI-compatible endpoints (UUID, display name, base URL, model list) — so if you ever want to point at a different local inference server, you can add it through the UI without touching Swift code.

### 2.4 Hotkey system

VoiceInk does **not** use the third-party `KeyboardShortcuts` Swift package (contrary to what Pax's research implied based on the README acknowledgments — Pax was reading an older readme). It ships its **own CGEventTap-based system** in `Shortcuts/ShortcutMonitor.swift`. The `Shortcut` struct explicitly supports `kVK_RightOption` (Right ⌥) as a side-specific modifier. Push-to-talk mode (key-down = start, key-up = stop) is a first-class mode in `RecordingShortcutModeHandler` alongside toggle and hybrid.

### 2.5 Text injection

`CursorPaster.swift` implements save-set-paste-restore with two backend options:
- **AppleScript** (`tell application "System Events" to keystroke "v" using command down`) — works without Accessibility permission in many cases; slower.
- **CGEvent** — synthesized Cmd-V via low-level keyboard simulation; requires Accessibility TCC grant; faster and more reliable.

`ClipboardManager` supports the `org.nspasteboard.TransientType` marker (from [nspasteboard.org](https://nspasteboard.org/)) so pasteboard history managers (Pasta, Pasty, Alfred clipboard, etc.) ignore the transient dictation content and don't pollute the history. The clipboard save/restore delay is configurable (minimum 0.25 s, which is safe for virtually all apps).

---

## Section 3 — Delta Work to Wispr Flow Parity

Most of this is configuration and UX tuning, not new code. Here is what must change from stock VoiceInk.

### 3.1 Ollama AI Enhancement — configuration (not code)

**Action:** In VoiceInk Settings → AI Enhancement → Provider → select "Ollama." Set:
- Base URL: `http://localhost:11434` (default, already correct)
- Model: whichever model Rune's spec recommends (likely `qwen3:4b` or similar)
- System prompt: the strict cleanup prompt from Rune's spec (owner_inbox/wispr_flow_clone_ollama_stage.md)
- Temperature: 0.3 (already the default in OllamaService)

**Integration point for Rune's spec:** The system prompt field in VoiceInk's Ollama settings IS the integration point. Rune's spec should deliver a tested system prompt string that goes directly into this field. No Swift code changes needed unless Rune's spec requires request-level parameters (e.g., `think: false` budget control — see open issue #589, which is a feature request for exactly this). If issue #589 is resolved by the time you build, the timeout control will be available from the UI.

**One possible code change:** `OllamaService` defaults to `"llama2"` as the initial model if none is saved. You may want to change that default to your preferred model to avoid a bad first-run experience. It's a one-line change in `OllamaService.swift`.

### 3.2 Hotkey default — Right-Option hold

VoiceInk ships some default shortcut (migration-managed). You want Right-Option hold-to-talk. 

**Action:** Settings → Shortcuts → Primary Shortcut → record Right-Option. Switch mode to "Push-to-Talk."

**If the UI shortcut recorder doesn't let you bind a modifier-only key** (some shortcut recorders require a non-modifier keycode): look at `ShortcutMigration.swift` to find the UserDefaults key and set it programmatically, or check `ShortcutValidator.swift` to see if modifier-only bindings are allowed. Given VoiceInk's own CGEventTap listens on `flagsChanged` events (Right-Option fires `flagsChanged` when pressed), this should work. If not, it is a small fix in `ShortcutValidator.swift` to allow modifier-only shortcuts.

**Fn key:** VoiceInk's `Shortcut.swift` lists Function (Fn) as a supported modifier, but Pax's research and your own experience confirm Fn-only hold is fragile across MacBook models. Leave Right-Option as default. Fn can be documented as an experimental option.

### 3.3 Flow-bar-style indicator

**Current state:** VoiceInk has `NotchRecorderView` (notch-integrated indicator) and `MiniRecorderPanel` (floating compact panel). Neither is a bottom-center lozenge exactly like Wispr Flow's Flow Bar, but the Mini panel is close.

**Action for M2:** Evaluate whether MiniRecorderPanel is sufficient UX. If so, configure it. If you want a dedicated bottom-center lozenge matching Wispr Flow exactly, add a new `NSPanel` with `level = .floating`, `styleMask = .borderless`, positioned at bottom-center of the key screen. This is ~50 lines of SwiftUI + AppKit. Given you're running macOS 26's Dynamic Island-style notch integration is already there, the Notch panel may actually be the better choice aesthetically.

### 3.4 Press-Enter-on-release option

**Wispr Flow behavior:** Optionally sends a Return keystroke after pasting the transcript, enabling "speak a chat message and have it send automatically."

**VoiceInk current state:** Not confirmed in the codebase from this audit. Check `TranscriptionDelivery.swift` for any `sendReturn` or post-paste keystroke option. If absent, this is a ~10-line addition: after the paste completes, if a user preference `sendReturnAfterPaste` is on, synthesize a Return via CGEvent.

**Claude Code / raw-mode TUI caveat (per my expertise):** Synthesized CGEvent Return does NOT register in raw-mode terminal apps — Claude Code, Vim, tmux, and similar TUIs intercept raw HID events and CGEvent-synthesized Return is invisible to them. This is a known macOS limitation (anthropics/claude-code#39983, filed 2026-03-27). No workaround exists at the CGEvent level. If you want Return to fire in these apps, use the AppleScript path: `tell application "System Events" to key code 36` — this routes through a different mechanism and works in some (but not all) raw-mode apps. Document this clearly in your personal settings: "press enter" will work in browsers, Slack, Mail, Notes, Terminal prompts — not in Claude Code or Vim.

### 3.5 Personal dictionary behavior

VoiceInk already has a personal dictionary system (see `Views/Dictionary/`). Two entry types:
- **Word additions** — steer ASR toward preferred spellings/names.
- **Replacement rules** — if heard X, write Y.

This maps directly to Wispr Flow's dictionary. The VoiceInk implementation stores dictionary entries locally and injects custom vocabulary into the `AIEnhancementService` context window (the orchestrator explicitly notes vocabulary injection in the system message construction).

**Action:** Populate your dictionary entries through the VoiceInk UI. No code changes needed. The vocabulary is passed to the Ollama prompt automatically.

### 3.6 Context-aware per-app formatting

**Wispr Flow behavior:** Detects focused app bundle ID and adjusts LLM style (casual for Slack, formal for Gmail, no-punctuation for terminal).

**VoiceInk current state:** `AIEnhancementService` captures a `RecordingContextSnapshot` that includes clipboard and screen content. Check whether it also captures focused app bundle ID — if yes, you can encode per-app style rules into your system prompt. If not, this is a modest addition: capture `NSWorkspace.shared.frontmostApplication?.bundleIdentifier` at recording start and pass it in the Ollama prompt context field.

This is an M3 enhancement; not needed for M1 parity.

---

## Section 4 — macOS Permissions Checklist and Pitfalls

### 4.1 Required permissions

| Permission | Why needed | Where to grant | Symptom if missing |
|---|---|---|---|
| **Microphone** (`kTCCServiceMicrophone`) | Audio capture | System Settings → Privacy → Microphone → toggle VoiceInk on | No audio captured; silent failure |
| **Accessibility** (`kTCCServiceAccessibility`) | Synthesize Cmd-V into focused app (CGEvent path) | System Settings → Privacy → Accessibility → toggle VoiceInk on | Text doesn't paste; fallback to AppleScript path which is slower |
| **Input Monitoring** (`kTCCServiceListenEvent`) | CGEventTap for global hotkey (mandatory since macOS 15 Sequoia) | System Settings → Privacy → Input Monitoring → toggle VoiceInk on | Hotkey doesn't fire; app may crash or log TCC error |
| **Speech Recognition** | Used by SpeechAnalyzer internally | Granted automatically on first use by macOS prompt | SpeechAnalyzer falls back to Whisper if denied |

Screen Recording is NOT required unless you enable the screen-context capture feature for per-app formatting awareness.

### 4.2 Permission grant order

Grant in this order to avoid confusing dialogs:
1. Microphone — usually prompted on first record attempt.
2. Input Monitoring — prompted when VoiceInk tries to register the hotkey CGEventTap.
3. Accessibility — prompted on first paste attempt.

If any permission appears granted in System Settings but the feature is still broken, the nuclear reset is: `tccutil reset Accessibility com.beingpax.voiceink` (or whatever the bundle ID is in your build). Check the bundle ID in `Info.plist`.

### 4.3 Secure Input mode

If the hotkey fires but nothing happens when a certain app is focused: check if Secure Input is active. Cmd-V injection via CGEvent is silently blocked in Secure Input mode (password fields, 1Password unlock screen, Terminal with Secure Keyboard Entry on).

Detect: `ioreg -l -w 0 | grep kIOHIDSecureInputIsActive`

In Secure Input mode, neither the AppleScript nor the CGEvent path for pasting will work. The app will silently do nothing. This is not a VoiceInk bug — it's an OS security boundary. Known triggering apps: 1Password (when unlocking), Terminal with "Secure Keyboard Entry" on, some banking/EMR apps. Your dictation will be transcribed; the text just won't be injected. VoiceInk should surface this gracefully (check whether it does; if not, add a notification).

### 4.4 Ad-hoc signed build caveats (macOS 26)

Ad-hoc signed apps on macOS 26 Tahoe may face additional Gatekeeper hardening compared to macOS 15. If the app won't launch after `make local`:
1. `xattr -dr com.apple.quarantine ~/VoiceInk-local/build/VoiceInk.app`
2. If still blocked: System Settings → Privacy & Security → scroll down → click "Open Anyway"
3. Verify the build is using `Debug` not `Release` configuration for development.

### 4.5 Claude Code / raw-mode TUI Return injection

As noted in §3.4: CGEvent-synthesized Return does not register in Claude Code, Vim, tmux, and other raw-mode TUIs (this is anthropics/claude-code#39983, still open as of 2026-07-06). This applies specifically to the "press enter after dictation" feature — the main transcript paste works fine everywhere. Do not spend time debugging this; it is a known macOS architectural limitation, not a bug in VoiceInk.

---

## Section 5 — Milestones and Acceptance Criteria

### M0 — Fork + first local build running stock VoiceInk

**Effort:** 2–4 hours (mostly whisper.cpp compile time)

**Steps:**
1. Fork repo, `make local`, app launches.
2. Grant Microphone + Input Monitoring + Accessibility.
3. Verify default hotkey fires (check VoiceInk docs for its current default).
4. Dictate a sentence into TextEdit → raw (unenhanced) transcript appears.

**Acceptance criteria (owner verifies by dictating):**
- [ ] App appears in menu bar.
- [ ] Hold hotkey → MiniRecorder panel appears with audio waveform.
- [ ] Release hotkey → transcript of spoken sentence appears in TextEdit.
- [ ] No cloud calls in Console.app during transcription (all local).

---

### M1 — Ollama-backed AI Enhancement working

**Effort:** 1–2 hours (configuration only)

**Steps:**
1. Ensure Ollama is running: `ollama serve` (already running for Homunculus — confirm with `curl http://localhost:11434/api/tags`).
2. Pull the target model per Rune's spec: `ollama pull <model>` (likely `qwen3:4b` or `gemma3:4b`).
3. VoiceInk Settings → AI Enhancement → Provider → Ollama → select model → paste system prompt from Rune's spec.
4. Toggle "AI Enhancement" on.
5. Set minimum word count to something reasonable (e.g., 3 words) so short commands aren't sent to Ollama.

**Acceptance criteria:**
- [ ] Dictate a sentence with fillers ("um", "uh"): enhanced output has fillers removed.
- [ ] Dictate "scratch that" mid-utterance: phrase before it is removed.
- [ ] Punctuation added correctly to multi-clause sentence.
- [ ] No cloud traffic in Console.app; only `localhost:11434` in network activity.
- [ ] Ollama model insights panel (VoiceInk dashboard) shows usage for the dictation model.
- [ ] Total time from release-key to text-visible is under 2 seconds (target: under 1 s).

---

### M2 — Hotkey + UX parity with Wispr Flow

**Effort:** 3–6 hours

**Steps:**
1. Change primary shortcut to Right-Option in VoiceInk Settings → Shortcuts.
2. Set recording mode to "Push-to-Talk."
3. Disable macOS built-in Dictation (System Settings → Keyboard → Dictation → OFF) to prevent hotkey collision.
4. Verify no collision with existing tools: Raycast, Alfred, BTT. Use Karabiner-EventViewer to confirm Right-Option key-down reaches VoiceInk.
5. Configure MiniRecorder or NotchRecorder panel position to taste.
6. If press-enter-on-release is desired: implement §3.4 addition if not already in VoiceInk.

**Acceptance criteria:**
- [ ] Hold Right-Option in any app → recording indicator appears.
- [ ] Release Right-Option → enhanced text injected at cursor.
- [ ] Works in: Safari, Mail, Notes, Slack, VS Code.
- [ ] Works in: Terminal (plain text fields, not raw-mode prompts).
- [ ] Hotkey fires correctly with no false positives when Right-Option is used in other keyboard shortcuts.
- [ ] If press-enter enabled: release Right-Option in Slack → text pasted AND message sent.
- [ ] In Claude Code terminal: text pastes but Return does NOT auto-fire (expected; not a bug).

---

### M3 — Tuning, personal dictionary, hardening

**Effort:** 4–8 hours (spread over real usage sessions)

**Steps:**
1. Add personal terms to VoiceInk dictionary: proper nouns, product names, technical vocabulary.
2. Add replacement rules for persistent ASR misheard words.
3. Prompt-engineer the Ollama system prompt with reference to Rune's spec: test edge cases (very short dictation, code-heavy content, proper nouns, non-English words, very long paragraphs).
4. Tune min-word-count threshold for enhancement skip.
5. (Optional) Add focused-app bundle ID capture for per-app style (§3.6).
6. Test latency budget: measure wall-clock time from key-release to text-visible using `date +%s%3N` before/after in a test script, or just count seconds aloud. Target: < 1 s for a 20-word sentence.
7. Verify Ollama model memory pressure: run Activity Monitor with 2–3 other LLM tasks active (Homunculus etc.) and confirm no OOM evictions.

**Acceptance criteria:**
- [ ] Your name, domain terms, project names transcribed correctly > 95% of the time.
- [ ] Replacement rules trigger correctly (say word X, get word Y in output).
- [ ] No over-rewriting: dictated sentences are cleaned, not paraphrased.
- [ ] Felt latency (key-release to text visible) < 1 s for typical 10–30 word utterance.
- [ ] No pasteboard history pollution (ClipboardManager transient type working).
- [ ] After 30 minutes of use: no memory leaks, no zombie Whisper processes (check Activity Monitor).

---

## Section 6 — Test Plan

### 6.1 Target apps for injection testing

Test in this order (easiest to hardest for text injection):

| App | Injection path | Expected result | Known gotcha |
|---|---|---|---|
| TextEdit | Cmd-V (CGEvent) | Works first try | None |
| Notes.app | Cmd-V (CGEvent) | Works | None |
| Mail.app (compose) | Cmd-V (CGEvent) | Works | None |
| Safari address bar | Cmd-V | Works | None |
| Safari webpage text field | Cmd-V | Works | None |
| Slack (browser) | Cmd-V | Works | None |
| Slack (native app) | Cmd-V | Works | Very occasionally needs Accessibility permission re-toggle |
| VS Code | Cmd-V | Works | Electron; confirm Accessibility is granted |
| Terminal.app (shell prompt) | Cmd-V | Works — pastes at prompt | Secure Keyboard Entry must be OFF |
| Terminal.app (Vim, insert mode) | Cmd-V | Works | Must be in insert mode |
| Claude Code TUI | Cmd-V pastes | Return does NOT auto-send | Expected; document as known behavior |
| 1Password (unlock dialog) | Cmd-V | FAILS (Secure Input) | Expected; document as known limitation |

### 6.2 Latency measurement approach

For informal measurement:
- Hold hotkey, speak a 15-word sentence at normal pace, release, and count "one-Mississippi" until text appears.
- Target: text appears before you finish saying "one."

For precise measurement:
```bash
# In a Terminal alongside the dictation target app, time the pipeline:
# - Note time at key release (you can see the shell cursor)
# - Note time when text appears
# Alternatively, add a debug log line in TranscriptionPipeline.run() 
# at the start and end of the AI Enhancement stage.
```

The pipeline stages to measure separately (add debug print statements in M0):
- ASR completion time (key-release → raw transcript in pipeline)
- Ollama call time (raw transcript → enhanced text)
- Paste time (trivial, ~50 ms)

### 6.3 Known failure modes to check at each milestone

| Failure mode | When | Diagnosis | Fix |
|---|---|---|---|
| Hotkey fires but no recording | M0 | Input Monitoring not granted | System Settings → Input Monitoring → grant |
| Text doesn't paste | M0 | Accessibility not granted | System Settings → Accessibility → grant |
| Enhancement never fires | M1 | Ollama not running, model not pulled, or AI Enhancement toggle off | `curl http://localhost:11434/api/tags` to verify; check Settings |
| Enhancement fires but returns raw text | M1 | System prompt missing or model doesn't follow it | Check Ollama model selection; try `qwen3:4b` specifically |
| Ollama timeout errors | M1 | Model cold-start (first call after idle) | Increase timeout in VoiceInk Ollama settings; open issue #713 was fixed but verify |
| Right-Option hotkey doesn't register | M2 | Karabiner, BTT, or another tool is consuming it | Open Karabiner-EventViewer; disable suspects one at a time |
| Clipboard history polluted | M3 | `org.nspasteboard.TransientType` not being set | Verify ClipboardManager transient flag is enabled in settings |
| OOM / Ollama eviction | M3 | Homunculus + dictation model both hot + large Whisper model | Switch to smaller model; ensure Ollama `OLLAMA_KEEP_ALIVE` is reasonable |

---

## Section 7 — Risks and Open Questions, Ranked

### Risk 1 (HIGH) — Ollama cold-start latency on first call after idle

**Description:** Ollama evicts models from memory after the `OLLAMA_KEEP_ALIVE` window. The first dictation after a period of inactivity will wait for the model to reload into GPU memory — 2–8 seconds for a 4B model. This makes the first post-idle dictation feel very slow.

**Mitigation:** Set `OLLAMA_KEEP_ALIVE=24h` in Ollama's launchctl config, or implement model pre-warming. VoiceInk already has a `ModelPrewarmService.swift` — check whether it pre-warms the Ollama model or only whisper.cpp models. If only whisper.cpp, extend it to send a no-op Ollama request on app launch.

**Note:** Since Homunculus also uses Ollama, coordinate the `OLLAMA_KEEP_ALIVE` setting so both tools get the memory behavior they need.

### Risk 2 (HIGH) — Ollama over-rewriting / paraphrasing

**Description:** A stock LLM with a cleanup prompt will occasionally rewrite your natural speech into "better" prose that isn't what you said. Wispr Flow's formatting model is fine-tuned to avoid this. Ollama models aren't.

**Mitigation:** The system prompt must include explicit, bold "DO NOT PARAPHRASE. DO NOT ADD CONTENT. OUTPUT ONLY THE CLEANED TEXT." instructions. Rune's spec should address this in detail. Also: set `isEnabled` to false initially and turn it on only after you've validated prompt behavior with test inputs.

**Fallback:** VoiceInk lets you toggle AI Enhancement off per-session or globally. Raw ASR quality with SpeechAnalyzer on macOS 26 is excellent on its own.

### Risk 3 (MEDIUM) — macOS 26 SpeechAnalyzer build flag

**Description:** `ENABLE_NATIVE_SPEECH_ANALYZER` is a non-standard build flag not in the default Xcode project settings. If it doesn't exist in the project as shipped, you need to add it. Easy to do, but easy to miss.

**Mitigation:** After `make local`, go to Settings → Transcription → check which engine is shown as active. If it shows Whisper instead of "Apple Speech" or "SpeechAnalyzer," the flag isn't set. Add the build flag as described in §1.5.

### Risk 4 (MEDIUM) — Right-Option modifier-only hotkey binding in VoiceInk UI

**Description:** Some shortcut recorder UI widgets reject modifier-only key bindings (they expect a non-modifier keycode). `Shortcut.swift` supports `kVK_RightOption` natively, but the recorder UI may block it.

**Mitigation:** If the Settings UI won't accept Right-Option alone, look at `ShortcutValidator.swift` — it's the gatekeeper. If modifier-only is blocked, either relax the validator (small code change) or bind to `Right-Option + Space` as a one-character chord, which avoids the modifier-only problem while still being easy to hold with one hand.

### Risk 5 (MEDIUM) — Memory pressure with whisper.cpp + Ollama model both hot

**Description:** On an 8 GB Mac: whisper.cpp large-v3-turbo (~2.7 GB) + Qwen3 4B (~2.4 GB Q4) + system + other apps = tight. Models may be evicted and re-loaded, adding latency.

**Mitigation:** With SpeechAnalyzer enabled (ANE-accelerated, very low RAM), you don't need the Whisper model loaded at all. Verify that VoiceInk is actually using SpeechAnalyzer and not whisper.cpp once the build flag is set. This risk is moot on 16+ GB machines.

### Risk 6 (LOW) — VoiceInk upstream divergence

**Description:** The repo is actively maintained (daily commits as of 2026-07-06). If upstream makes breaking changes to the AI Enhancement or Shortcuts architecture, rebasing your personal branch may require conflict resolution.

**Mitigation:** Keep your personal changes minimal and well-isolated to configuration/settings rather than architectural changes. Use a dedicated `personal/local-ollama` branch, and periodically `git fetch upstream && git rebase upstream/main`. If the Ollama configuration is purely in Settings (UserDefaults), you may not even have code conflicts — just UI settings that carry over.

### Risk 7 (LOW) — External volume nosuid for future launchd agents

**Description:** If you ever want a background launchd LaunchAgent (e.g., for dictionary sync or model pre-warming on login), scripts on `/Volumes/GIT` can't be executed by launchd due to `nosuid` mount flag.

**Mitigation:** For this project, not relevant (VoiceInk is a login-item app, not a launchd daemon). If it ever becomes relevant, put agent scripts in `~/.local/bin/` on the boot volume.

### Open questions

1. **Does Rune's system prompt for Ollama fit within the VoiceInk system prompt field as-is, or does it need a custom code integration?** Check the Settings UI for character limits on the system prompt field.
2. **Does VoiceInk capture the focused app bundle ID and pass it to the Ollama prompt already?** If yes, per-app style is essentially free. Check `AIEnhancementService.swift`'s context snapshot construction.
3. **Issue #589 (Ollama thinking budget control) — is it resolved?** The thinking budget for models that support it (Qwen3 thinking mode) should be set to zero for a cleanup task — you want fast, not deep reasoning. Check if the VoiceInk UI exposes this parameter or if you need to force `think: false` in a code change.
4. **Is `ModelPrewarmService.swift` wiring to Ollama or just whisper.cpp?** If just whisper.cpp, extend it for warm-start benefits.

---

## Sources

All VoiceInk claims verified by direct inspection of source files on 2026-07-06:

- [VoiceInk repo](https://github.com/beingpax/VoiceInk) — star count, license, description, commit history
- `VoiceInk/Services/OllamaService.swift` — Ollama base URL, model discovery, generate endpoint
- `VoiceInk/Services/AIEnhancement/AIService.swift` — `AIProvider` enum with explicit `.ollama` case
- `VoiceInk/Services/AIEnhancement/AIEnhancementService.swift` — routing logic, `.ollama` path, context snapshot
- `VoiceInk/Services/AIEnhancement/CustomAIProviderManager.swift` — custom provider schema
- `VoiceInk/Services/AIEnhancement/AIChatCompletionService.swift` — OpenAI-compatible endpoint support
- `VoiceInk/Shortcuts/ShortcutMonitor.swift` — CGEventTap implementation, keyDown/keyUp callbacks
- `VoiceInk/Shortcuts/RecordingShortcutManager.swift` — push-to-talk / toggle / hybrid modes
- `VoiceInk/Shortcuts/Shortcut.swift` — `kVK_RightOption` explicit support
- `VoiceInk/Transcription/Engine/TranscriptionServiceRegistry.swift` — four engine registrations
- `VoiceInk/Transcription/Engine/TranscriptionPipeline.swift` — ASR → filter → enhance → deliver sequence
- `VoiceInk/Transcription/Native/NativeAppleTranscriptionService.swift` — `SpeechAnalyzer` API, `#available(macOS 26, *)` gate, `ENABLE_NATIVE_SPEECH_ANALYZER` flag
- `VoiceInk/Paste/CursorPaster.swift` — NSPasteboard save-set-Cmd-V-restore, AppleScript + CGEvent paths, `org.nspasteboard.TransientType` support
- `BUILDING.md` — `make local` for ad-hoc signing, dependency path
- VoiceInk GitHub Issues — #589 (Ollama thinking budget, open), #717 (LM Studio, open), #713 (timeout fix, resolved)
- Pax's research: `owner_inbox/wispr_flow_clone_research.md` — architecture decisions, latency budget, model recommendations
- [anthropics/claude-code#39983](https://github.com/anthropics/claude-code/issues/39983) — CGEvent Return in raw-mode TUIs (filed 2026-03-27, still open)
- [nspasteboard.org](https://nspasteboard.org/) — `org.nspasteboard.TransientType` pasteboard marker spec
