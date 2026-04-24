# Hiring Research: macOS Productivity & Voice-Input Specialist

**Prepared by:** Pax (Senior Researcher)
**Date:** 2026-04-22
**Trigger:** Thomas needs an in-house expert on AI-powered Mac dictation tools (Wispr Flow, SuperWhisper, MacWhisper, Aiko, Apple Dictation, Apple Voice Control). No current team member owns this domain. Immediate first question concerns Wispr Flow's **Command Mode / Fn+Ctrl hotkey not auto-pressing Return on release**.

---

## 1. Role & Common Titles

Real-world practitioners with this skill set typically hold one of these titles:

- **macOS Power User / Productivity Consultant** — independent consultants, YouTubers, and MacStories/Six Colors-adjacent writers who live inside the Mac automation stack and advise individuals and small teams.
- **Accessibility Technology Specialist** — consultants (often tied to AT firms or universities) who configure voice input for people with RSI, motor impairments, or voice-first workflow preferences. Familiar with both assistive workflows and mainstream productivity tooling.
- **Voice-First Workflow Designer** — an emerging role at tools like Wispr, Descript, Willow, and Otter; designs the interaction model for hold-to-talk, push-to-talk, and command-mode flows and debugs how they interact with host apps.
- **Mac Automation Engineer** — Karabiner, Hammerspoon, Keyboard Maestro, BetterTouchTool, Shortcuts.app fluency. Often overlaps with productivity consultant.
- **Support Engineer at a dictation vendor** (Wispr Flow, SuperWhisper, Willow, MacWhisper) — front-line diagnostician for exactly the kind of hotkey / paste / permission issues Thomas is asking about.

For our team, the right archetype is a **Voice-First Mac Productivity Specialist** — fluent in the full dictation-tool landscape, sharp on macOS Accessibility/Input-Monitoring/CGEvent internals, and comfortable debugging hotkey + paste + send-on-release failures.

---

## 2. Core Expertise

### 2.1 Modern AI Dictation Tools (2025-2026 landscape)

**Wispr Flow** (cloud-backed, subscription)
- The dominant "AI dictation with polish" tool as of 2026. Works on macOS, Windows, and iOS.
- Two distinct modes:
  - **Dictation Mode (default, push-to-talk):** Hold `Fn` on Mac, speak, release. Transcribes via Whisper-class model, optionally runs an AI polish pass, then pastes into the focused text field via the pasteboard.
  - **Hands-Free Mode:** `Fn+Space` toggles continuous dictation.
  - **Command Mode (experimental, paid):** Default Mac shortcut `Fn+Ctrl`. **Hold-to-talk**: press and hold, speak a command ("rewrite this professionally", "translate to Spanish", "answer via Perplexity"), release. Operates on selected text (1–1,000 words) or issues an LLM/Perplexity query. Configured in **Settings → Experimental → Command Mode** toggle, plus **Settings → Shortcuts → Command Mode**.
- Default hotkey model on Mac: **hold-to-talk, release-to-send** for both dictation and command mode. The Fn key is only usable *as a modifier* on macOS, which is why Apple Silicon's globe/Fn key works cleanly here.
- Backup shortcut for keyboards without Fn: `Cmd+Ctrl+Option`.
- Shortcut rules: at least one modifier, max 3 keys, max 4 shortcut bindings, can't mix left/right variants of the same modifier, can't reuse reserved macOS combos (Cmd+C/V/Z, Cmd+arrows, Ctrl+A/E/K, Fn+F11/F12, Caps Lock).
- "Press enter" voice command: saying "press enter" at the end of a dictation triggers an extra simulated Return after paste. **Toggle lives in Settings → Experimental.** (Critical for Thomas's question — see §7.)
- Permissions required on macOS: **Microphone** (mandatory), **Accessibility** (mandatory for keystroke simulation and hotkey capture), **Input Monitoring** (strongly recommended for modifier-only shortcuts like bare `Fn`), Screen Capture (optional).

**SuperWhisper** (mostly local, one-time license or subscription tiers)
- Real-time system-wide dictation, local Whisper models (tiny/base/small/medium/large) plus optional cloud models.
- Strong **custom mode** system (define prompts, target apps, output styles). Great for "dictate then auto-format as bullet list in Obsidian" flows.
- Push-to-talk or toggle hotkey; highly customizable.
- Privacy pitch: on-device transcription by default.

**MacWhisper** (Jordi Bruin)
- Primary use case: **file transcription** (audio/video to text), not system-wide dictation, although it has added a real-time mode.
- Pro tier ~$29 on Gumroad; broad Whisper model support including distil-whisper and turbo.
- Preferred when you need to transcribe meetings, podcasts, or voice memos rather than live dictate.

**Aiko** (Sindre Sorhus)
- Free, open-source, on-device Whisper. Minimal UI.
- Good entry point for Whisper testing; not a full dictation replacement.

**Willow Voice** (cloud, subscription)
- Focused on polished dictation with strong technical-term accuracy. Growing niche in developer circles.

**WhisperClip** (emerging, local-first)
- Lightweight clipboard-oriented dictation.

**Whisper.cpp-based DIY pipelines**
- `whisper.cpp` (ggerganov) + Hammerspoon or a shell script + `pbcopy`/`osascript` to glue together a push-to-talk dictation workflow. Common in r/LocalLLaMA and r/MacApps DIY threads.
- `voxt` and `Typer` are open-source macOS Whisper frontends (GitHub) used as starting points.

### 2.2 Built-in macOS Options

**macOS Dictation** (Edit → Start Dictation, or shortcut in System Settings → Keyboard → Dictation)
- On-device since macOS Ventura for most languages. No fixed duration cap.
- Default hotkey: press fn/globe twice (configurable to a single key). Very different interaction model from Wispr Flow — it uses the OS-level TextInput protocol, not clipboard paste.
- Frequently conflicts with third-party dictation tools that also bind Fn; turn it off in **System Settings → Keyboard → Dictation** when running Wispr Flow on Fn.

**Apple Voice Control** (System Settings → Accessibility → Voice Control)
- A full hands-free *control* framework — not just dictation but mouse/keyboard/menu control via voice. "Click OK", "Number the grid", "Scroll down", custom vocabularies.
- Critical for accessibility workflows. Ships with built-in command set plus user-defined commands.
- Known to **conflict with Dictation and third-party dictation tools**; when Thomas hears "dictation doesn't work", the #1 cause (per Voibe/MacKeeper/Willow guides) is Voice Control being silently enabled.

**Customizing built-in shortcuts:** System Settings → Keyboard → Keyboard Shortcuts → Dictation (and → Accessibility for Voice Control). Third-party tools usually warn if their hotkey overlaps Apple's.

### 2.3 macOS Internals a Specialist Must Understand

**Permissions (System Settings → Privacy & Security):**
- **Microphone** — gate for capture. Trivial but frequently reset by macOS updates.
- **Accessibility** — gate for simulated keystrokes, global hotkey capture, reading focused-app text. Without this, a tool literally cannot paste or press Return into another app.
- **Input Monitoring** — gate for reading raw keyboard events globally. Required for modifier-only shortcuts (bare Fn, bare Ctrl) because the OS otherwise won't hand them over. Wispr Flow's docs specifically call this out.
- **Automation** (App-to-app AppleScript permissions) — relevant for tools that drive other apps via scripting.
- **Screen Capture** — needed for context-aware features ("summarize what's on screen").

**Event pipelines & injection strategies:**
- **CGEventTap / CGEventPost** — the macOS Core Graphics event API. Wispr Flow and most dictation tools use this to synthesize key-up/key-down events (including Return). These events pass through the normal event dispatch pipeline.
- **NSEvent global monitors** — used for *observing* global key events (e.g., hotkey detection) without consuming them. Needs Input Monitoring / Accessibility permission.
- **Accessibility API (AX)** — used for reading focused element, inserting text directly into a text field (bypassing the keyboard), and identifying the focused app. Some tools prefer AX text insertion over paste for fidelity (no pasteboard clobbering).
- **Pasteboard paste** (NSPasteboard + synthesized Cmd+V) — the simplest approach; what Wispr Flow uses by default. Fails when the focused app blocks clipboard or uses a nonstandard paste shortcut.
- **Simulated typing** — each character posted as a key event. Slowest, most compatible, worst for special characters and Unicode.

**Why one strategy fails where another works:**
- Terminal apps (Terminal.app, iTerm2, Ghostty) in **raw mode** (used by TUI apps like Vim, tmux, htop, and **Claude Code**) read stdin directly. Synthesized Return via CGEvent *does* reach the terminal window on-screen but some raw-mode input handlers don't pick up the synthesized event correctly — this is exactly the Claude Code issue filed March 27 2026 (anthropics/claude-code#39983).
- Sandboxed web apps (1Password, some banking apps) intentionally block pasteboard reads.
- Remote desktop sessions (Jump, Parsec, Citrix, Splashtop) don't bridge the synthesized Return across the session boundary.

**Hotkey mechanics:**
- **Fn / globe key on Apple Silicon:** only functions as a modifier. You can't tap-and-release Fn alone as a hotkey trigger in macOS without special handling — tools like Wispr Flow capture its *hold* state specifically.
- **Tap vs hold vs double-tap semantics:** OS-level distinction is subtle. Apple Dictation uses double-tap; Wispr Flow uses hold-and-release. BetterTouchTool and Karabiner can remap tap/hold/double-tap onto different actions.
- **Release-triggered actions:** the tool listens for key-up events and, on release, fires `stop-recording → transcribe → paste → (optional) send Return`. If any step in that chain is blocked, the apparent symptom is "Return didn't fire."
- **Secure Input mode:** when active (triggered by password fields, 1Password, Terminal's "Secure Keyboard Entry", some banking/EMR apps, KeePassXC bugs), macOS blocks all keystroke monitoring and often synthesized keystrokes too. Detect via `ioreg -l -w 0 | grep kIOHIDSecureInputIsActive` or the AppleScript that reads the secure-input bit. Menu bar apps like Keyboard Maestro and Karabiner-EventViewer show the current state.

---

## 3. Tools & Techniques a Specialist Uses

### 3.1 Keyboard / Automation Layer
- **Karabiner-Elements** — the canonical macOS keyboard remapper. Defines complex modifications in JSON; frequently used to turn Caps Lock into a Hyper key, build chords, and reroute Fn behavior. **Karabiner-EventViewer** is the go-to for inspecting what the OS actually sees when you press a key.
- **Hammerspoon** — Lua scripting for macOS automation. Can bind hotkeys, run shell commands, call AX APIs, and build full push-to-talk pipelines around `whisper.cpp`.
- **BetterTouchTool** (BTT) — GUI-first alternative; strong for tap-vs-hold distinctions and gesture bindings. Known to occasionally conflict with Karabiner.
- **Keyboard Maestro** — macro-heavy automation; excellent for composing "dictate → polish via LLM → paste → press Return" chains without writing Lua.
- **Shortcuts.app** — Apple's native automation; limited for low-level key events but useful for the "dictate into Notes then run a Shortcut" archetype.
- **Raycast** — launcher + command palette; has its own global hotkey system that routinely **collides with dictation tools**. Alfred has the same class of issue.
- **skhd** — tiling-WM crowd's simple hotkey daemon; niche for dictation but appears in r/unixporn-style configs.

### 3.2 Debugging & Observability
- **Accessibility Inspector** (comes with Xcode) — inspect the AX hierarchy of any app to understand why text injection lands or doesn't.
- **Karabiner-EventViewer** — see raw key events, modifier states, and simulated events as macOS sees them.
- **Console.app** — OS log stream. Filter on `com.wisprflow`, `com.apple.speech`, `corespeechd`, `AccessibilityUIServer`. Secure Input events show up here too.
- **`ioreg -l`** — HID device tree; verify microphone and keyboard devices are enumerated; check `kIOHIDSecureInputIsActive`.
- **`log stream --predicate 'subsystem == "com.apple.accessibility"'`** — live tail accessibility events while reproducing a failure.
- **`tccutil reset Accessibility` / `tccutil reset Microphone`** — nuclear option to reset the permission database for a given capability when an app is stuck "granted but not working."
- **`killall corespeechd`** — forces Apple's speech daemon to restart; fixes a surprising number of "Dictation stopped working" reports.
- **`pbpaste` / `pbcopy`** — sanity-check the pasteboard state when auto-paste misfires.
- **Activity Monitor** — watch CPU and RAM for runaway Whisper processes; SuperWhisper with large model + live mode can be heavy.

### 3.3 Scripting & Integration
- **AppleScript / `osascript`** — `tell application "System Events" to keystroke return` is the canonical fallback when a tool's own Return injection fails.
- **Shell glue** — `say`, `sox`, `ffmpeg` for audio pipeline testing.
- **Python** with `pyobjc-framework-Quartz` for custom CGEvent work when debugging.

---

## 4. Trusted Sources & Communities

**Tier 1 — primary reads:**
- **Wispr Flow docs** (docs.wisprflow.ai) — authoritative on Command Mode, hotkey rules, permissions, and troubleshooting. Updated frequently.
- **Wispr Flow Discord / roadmap.wisprflow.ai** — where bugs and new features are actually discussed.
- **SuperWhisper Discord and docs** (superwhisper.com/docs) — mode configuration, custom prompts.
- **The Eclectic Light Company** (eclecticlight.co, Howard Oakley) — deepest Mac internals writing, including periodic posts on Accessibility/TCC permission changes across OS versions.
- **Six Colors** (Jason Snell, Dan Moren) — strong on Mac productivity coverage.
- **MacStories** (Federico Viticci, John Voorhees) — Shortcuts.app and automation deep dives; Viticci specifically covers dictation/accessibility workflows.

**Tier 2 — community and corroboration:**
- **r/MacApps, r/macOS** — broad user experience reports.
- **r/Whisper, r/LocalLLaMA** — local-Whisper setups and benchmarks.
- **r/wisprflow** — small but active; real user pain points.
- **Karabiner-Elements GitHub + pqrs.org docs** — Takayama Fumihiko's documentation.
- **Hammerspoon docs + Learn Hammerspoon** — canonical scripting reference.
- **Keyboard Maestro forum** (forum.keyboardmaestro.com) — exceptional Secure Input troubleshooting threads.
- **Apple Developer Forums** — threads on Accessibility/Input Monitoring, CGEventTap behavior across macOS versions.
- **Mac Power Users podcast** (David Sparks & Stephen Hackett) — regular coverage of dictation and automation.
- **Automators podcast** (Rosemary Orchard & David Sparks) — Shortcuts/Keyboard Maestro workflows.
- **MacSparky blog** — David Sparks' field notes on productivity tooling.

**Tier 3 — product comparison / review sites:**
- **Voibe Resources** (getvoibe.com), **Max Productive** (max-productive.ai), **OnResonant** — useful for landscape overviews, less for deep troubleshooting. Treat with light skepticism.

**Key individuals to follow:**
- **Tanya Rai / Wispr Flow team** — Wispr product updates.
- **Jordi Bruin** — MacWhisper, Supermaven, TouchRetouch; independent Mac dev perspective.
- **Sindre Sorhus** — Aiko and a large catalog of Mac utilities.
- **Federico Viticci** — MacStories; accessibility-informed Mac workflow writing.
- **Howard Oakley** — eclecticlight.co; the reference for Mac privacy/security internals.

---

## 5. Common Troubleshooting Patterns

A specialist has a mental decision tree for "dictation/hotkey misbehaving":

### 5.1 Nothing happens when I hold the hotkey
1. **Accessibility permission missing or stale.** Fix: System Settings → Privacy & Security → Accessibility, toggle Wispr Flow off and back on. After OS updates, permissions sometimes silently invalidate; the Wispr docs explicitly call out re-verification.
2. **Input Monitoring missing.** Needed for modifier-only hotkeys (bare Fn). Add the app manually.
3. **Another app has captured the hotkey first.** Usual suspects: **Raycast**, **Alfred**, **Karabiner-Elements**, **BetterTouchTool**, **Keyboard Maestro**, **Rectangle**, **Apple Dictation** (System Settings → Keyboard → Dictation → Shortcut), **Apple Voice Control**. Disable one at a time.
4. **Microphone in use by another app** (Zoom, Meet, QuickTime recording). Some tools fail silently instead of queuing.
5. **App updated, binary moved, TCC confused.** `tccutil reset Accessibility com.wisprflow.flow` and re-grant.

### 5.2 Transcription works but text doesn't paste
1. **Pasteboard paste blocked by target app.** Citrix, banking apps, password managers, some EMR systems explicitly block synthesized Cmd+V. Fix: paste into Notes and copy across, or use the app's own paste-fallback shortcut (Wispr: Ctrl+Cmd+V pastes last transcript).
2. **Auto-Polish delay.** Wispr's polish pass adds seconds; user thinks it failed. Disable in settings or wait.
3. **Focused element is read-only** (e.g., some Google Docs modes, a blurred text field). Click back into the field.
4. **Wrong clipboard mode** (Windows: "Run as Administrator" mismatch — not relevant on Mac but worth knowing).

### 5.3 Text pastes but Return/Enter doesn't fire on release — **Thomas's issue**
This is the diagnostic tree that matters most for the first task. Top causes, in order of frequency:

1. **The "Press Enter" feature isn't actually enabled.** Wispr Flow does **not** auto-send Return on release by default. The behavior is opt-in and lives at **Settings → Experimental → "press enter"** (and as a voice command spoken at end of dictation). Many users expect release-to-send and don't realize it's a separate setting. *Most likely root cause.*
2. **Accessibility permission revoked or partially granted.** Paste can work via pasteboard paste while simulated Return (a separate CGEvent keystroke) fails — they go through different subsystems. Fix: full Accessibility toggle off/on.
3. **Conflicting global hotkey on Return release.** Rare but possible if Karabiner/BetterTouchTool/Keyboard Maestro intercepts key-up events.
4. **Focused app eats synthesized Return.** Claude Code's raw terminal mode is the canonical 2026 example (GitHub anthropics/claude-code#39983, filed March 27 2026) — CGEvent-synthesized Return passes through macOS but the raw-mode stdin handler doesn't register it. Also affects some Electron apps, some custom game-launcher text fields. Workaround: dictate into Notes, copy, paste manually; or use an alternative tool that posts HID-level events rather than CGEvents.
5. **Secure Input mode is active.** 1Password open, Terminal's "Secure Keyboard Entry" toggled, a password field somewhere has focus, or a rogue app left it stuck on. Check: Keyboard Maestro status menu, or `ioreg | grep Secure`, or Apple menu → look for the padlock in Console. Fix: dismiss password-entry context, quit the offender, or `killall` the sticky process.

Secondary causes worth mentioning: the Wispr version hasn't been updated (earlier versions had a bug inserting stray punctuation after "press enter"); the command mode hotkey was rebound and the new binding collides with something; the user is on a non-paid tier and experimental features are silently disabled.

### 5.4 Hotkey fires but transcription is empty or garbled
1. Wrong input device selected (Bluetooth headset dropped; AirPods switched to another Mac).
2. Model language mismatch.
3. Network down on cloud-backed tools.
4. Whisper model corrupted or not downloaded for local tools.

---

## 6. Workflow Archetypes

A specialist recognizes which archetype a user is in and tunes the tool choice:

- **Replace-all-typing dictation** — user wants to dictate everywhere. Wispr Flow or SuperWhisper with a global hotkey bound to Fn; polish pass on; Hands-Free mode for long-form writing.
- **Command-and-dictate hybrid** — user dictates prose by default and occasionally issues commands ("make this formal", "translate to French"). Wispr Flow with both Dictation Mode on Fn and Command Mode on Fn+Ctrl.
- **Dictate-then-polish** — dictate rough text, then pipe to an LLM (Claude, GPT, local) for cleanup before insertion. Native in Wispr Flow's "Auto-Polish"; buildable in Keyboard Maestro + API call for SuperWhisper.
- **Local/private dictation** — SuperWhisper with local Whisper, or a whisper.cpp + Hammerspoon DIY rig. Chosen for privacy-regulated work (legal, healthcare) or offline reliability.
- **Accessibility-first / hands-free** — Apple Voice Control as the primary interface, with third-party dictation layered for fluency and polish. Custom vocabularies for user's jargon.
- **Coding/TUI** — trickiest. Raw-mode terminals (Claude Code, Vim, tmux) break synthesized Return. Current workaround is dictation-for-prose-only; for terminal submission, either use the host terminal's paste-and-enter ability or accept a manual Return press.
- **Meeting-to-notes** — MacWhisper for file transcription of a recorded meeting, then separate dictation tool for live notes.

---

## 7. First-Task Preparation: "Wispr Flow's Command Mode / Fn+Ctrl combo isn't auto-pressing Return on release"

The new hire needs to walk into this question informed and precise.

### 7.1 What Command Mode actually is
Command Mode is **not** Wispr Flow's default dictation. It is an experimental, paid-tier feature that sends your spoken words to an LLM as a *command* — "rewrite this professionally", "translate to Spanish", "answer this from the web via Perplexity" — optionally operating on selected text (1–1000 words) or a standalone query.

- **Activation:** hold the Command Mode shortcut, speak, release.
- **Default Mac shortcut:** `Fn+Ctrl` (backup: `Cmd+Ctrl+Option`).
- **Configuration path:** Settings → Experimental → toggle "Command Mode" on, then Settings → Shortcuts → Command Mode to customize the binding.
- **Requires:** active paid subscription or free trial; Accessibility + Microphone + ideally Input Monitoring permissions.

### 7.2 What "auto-press Return on release" means in Wispr terms
Wispr Flow has **no built-in "always send Return on release"** behavior. The closest features:

1. **"Press enter" voice command.** At the end of a dictation, say "press enter" and Flow will, after pasting the transcribed text, synthesize a Return keypress. The phrase itself is stripped from the pasted text. **Toggle lives in Settings → Experimental.** Works in both Dictation Mode and (per current docs) can affect Command Mode flows.
2. **Nothing automatic in Command Mode.** Command Mode's release handler pastes the LLM's response into the focused text field. It does not, by default, fire Return — because the user may want to review the LLM output before submitting.

So if Thomas expects holding Fn+Ctrl, speaking, and releasing to automatically submit (e.g., to Claude Code, a Slack message, a ChatGPT textarea), he almost certainly either (a) wants the "press enter" feature toggled on and to say "press enter" at the end of each command, or (b) is hitting the Claude-Code-style raw-terminal problem where even an enabled Return synthesis doesn't reach the app.

### 7.3 Top 5 likely causes, ranked
1. **"Press enter" feature is off, or the user isn't saying "press enter" at the end of the utterance.** Default state. First thing to verify: Settings → Experimental → "press enter" is enabled. Then confirm the user's mental model — Wispr does not auto-send just because they released the key.
2. **Target app is Claude Code or another raw-mode TUI.** Synthesized Return via CGEvent doesn't register. Filed as anthropics/claude-code#39983 on 2026-03-27. No fix yet. Workaround: alternate input method or manual Return.
3. **Accessibility permission degraded.** Paste via clipboard still works (different pathway), but simulated Return (CGEvent keystroke) silently fails. Fix: toggle Wispr off and on in System Settings → Privacy & Security → Accessibility; re-verify Input Monitoring.
4. **Conflicting hotkey consumer.** Raycast, Alfred, Karabiner, BetterTouchTool, or Keyboard Maestro is catching Fn+Ctrl on key-up, suppressing Wispr's release handler. Disable suspects one at a time. Karabiner-EventViewer will show whether the release event reaches userland.
5. **Secure Input mode active.** 1Password, a password field, Terminal's Secure Keyboard Entry, or a stuck process is blocking synthesized keystrokes globally. Check with the AppleScript secure-input probe or `ioreg | grep SecureInput`. Dismiss the offending context.

Runners-up worth checking if the top 5 don't explain it: Wispr Flow version is out of date (earlier versions had a "press enter" bug that inserted stray punctuation or failed silently); free-tier/trial lapsed so Experimental features were silently disabled; hotkey was re-bound to a combination that Mac reserves; microphone was captured by another app so recording never started (release fired but there was nothing to paste and nothing to Return).

---

## 8. Decision-Making Patterns

### 8.1 Picking the right tool for a given user
- **Privacy concern is primary?** → SuperWhisper local model, or whisper.cpp + Hammerspoon.
- **Polish and speed matter more than local?** → Wispr Flow.
- **Only needs to transcribe files, not dictate live?** → MacWhisper.
- **Just wants to test Whisper free?** → Aiko.
- **Accessibility-first (motor impairment)?** → Apple Voice Control as the foundation, Wispr or SuperWhisper layered for fluency.
- **Heavy technical vocabulary (code, medical, legal)?** → tools with **custom dictionaries / custom vocabulary**: Wispr Flow supports vocabulary training; SuperWhisper via prompt engineering in custom modes; Willow Voice targets technical terms specifically.
- **Must work offline?** → SuperWhisper local or DIY whisper.cpp. Avoid Wispr Flow.
- **Budget-sensitive?** → Aiko (free) or MacWhisper one-time (~$29). Wispr Flow and SuperWhisper are subscription-heavy.

### 8.2 Cloud vs local trade-offs
- **Latency:** Cloud ~500-900 ms end-to-end in good conditions; local Whisper on Apple Silicon with small/base model is sub-500ms; large local models can exceed cloud.
- **Accuracy on technical terms:** Cloud models plus an LLM polish pass typically win; local medium+ Whisper closes the gap.
- **Privacy:** Local wins unconditionally.
- **Cost:** Local has no marginal cost after setup; cloud is $12-25/month subscription territory.
- **Reliability:** Local doesn't care about network; cloud breaks on flaky Wi-Fi, VPN, corporate firewalls.

### 8.3 When to recommend the built-in instead
If a user dictates casually and already has macOS Ventura+, **Apple Dictation** is free, on-device, and surprisingly good. The specialist should not reflexively push a paid tool — if the user doesn't need polish, custom modes, or command mode, Apple Dictation is the right answer.

---

## 9. Recommended Persona Archetype for New Hire

**Who Nolan should create:**

A calm, practical voice-first Mac power user who:

- Knows the **2025-2026 dictation landscape cold** — Wispr Flow (including the Command Mode / Fn+Ctrl / "press enter" quirks), SuperWhisper, MacWhisper, Aiko, Willow, Apple Dictation, Apple Voice Control.
- Speaks fluently about **macOS Accessibility, Input Monitoring, CGEvent injection, pasteboard vs AX text insertion, and Secure Input mode**.
- Can open Karabiner-EventViewer, Accessibility Inspector, and Console.app on instinct when debugging a hotkey or paste failure.
- Matches tool to use case: asks "what are you actually doing?" before recommending.
- Treats **Apple Dictation as a legitimate answer** when it fits, not a second-class option.
- Clear on the distinction between **dictation mode (hold-to-talk → paste) and command mode (hold-to-talk → LLM → paste)**, and on what does and does not auto-send.
- Aware of the **Claude Code raw-mode Return bug** and similar focused-app interception cases.
- Personality: patient, diagnostic, unafraid to say "the feature you want isn't on by default — go to Settings → Experimental and toggle it."

**Suggested name cues for Nolan:** something short, calm, voice-evocative (e.g., Vox, Sable, Mira, Wren, Echo). Final naming is Nolan's call.

**Suggested title:** "Voice-First Productivity Specialist" or "macOS Dictation & Voice-Input Specialist."

**Immediate first task:** Answer Thomas's question about Wispr Flow's Command Mode / Fn+Ctrl not auto-pressing Return on release — walk through the top 5 causes in §7.3, starting with the Settings → Experimental → "press enter" toggle as the first thing to check.

---

## Sources Consulted

- [Wispr Flow Docs — How to use Command Mode](https://docs.wisprflow.ai/articles/4816967992-how-to-use-command-mode)
- [Wispr Flow Docs — Command Mode overview](https://docs.wisprflow.ai/articles/8476991260-command-mode)
- [Wispr Flow Docs — Supported & Unsupported Keyboard Hotkey Shortcuts](https://docs.wisprflow.ai/articles/2612050838-supported-unsupported-keyboard-hotkey-shortcuts)
- [Wispr Flow Docs — Starting your first dictation](https://docs.wisprflow.ai/articles/6409258247-starting-your-first-dictation)
- [Wispr Flow Docs — Use Flow hands-free](https://docs.wisprflow.ai/articles/6391241694-use-flow-hands-free)
- [Wispr Flow Docs — Fix text not pasting after dictation](https://docs.wisprflow.ai/articles/7971211038-fix-text-not-pasting-after-dictation)
- [Wispr Flow Docs — Re-verify Wispr Flow permissions after updating](https://docs.wisprflow.ai/articles/5510622673-re-verify-wispr-flow-permissions-after-updating)
- [Wispr Flow Docs — Setup Guide](https://docs.wisprflow.ai/articles/3152211871-setup-guide)
- [Wispr Flow Docs — Keyboard and Screen Reader Accessibility](https://docs.wisprflow.ai/articles/3941699399-keyboard-and-screen-reader-accessibility-in-wispr-flow)
- [Wispr Flow Docs — Reset and restart the Wispr Flow app](https://docs.wisprflow.ai/articles/2999006910-reset-and-restart-the-wispr-flow-app)
- [Wispr Flow roadmap — Command mode and smarter text insertion (beta)](https://roadmap.wisprflow.ai/changelog/pray-command-mode-and-smarter-text-insertion-in-beta)
- [Wispr Flow roadmap — Select your own keyboard shortcut](https://roadmap.wisprflow.ai/changelog/keyboard-select-your-own-keyboard-shortcut)
- [anthropics/claude-code#39983 — Simulated Enter keypress from Wispr Flow not registered in raw mode](https://github.com/anthropics/claude-code/issues/39983)
- [Wispr Flow Review 2026 — Max Productive](https://max-productive.ai/ai-tools/wispr-flow/)
- [Wispr Flow 101 — Sid Saladi Substack](https://sidsaladi.substack.com/p/wispr-flow-101-the-complete-guide)
- [Podfeet — Dictate with Wispr Flow (Scott Willsey)](https://www.podfeet.com/blog/2026/03/wispr-flow-scott-willsey/)
- [MacWhisper vs Superwhisper — Voibe](https://www.getvoibe.com/resources/macwhisper-vs-superwhisper/)
- [Wispr Flow vs Superwhisper — Voibe](https://www.getvoibe.com/resources/wispr-flow-vs-superwhisper/)
- [Speech to Text on Mac 2026 — Voibe](https://www.getvoibe.com/resources/speech-to-text-mac/)
- [WhisperClip vs Superwhisper vs Wispr Flow vs MacWhisper](https://whisperclip.com/blog/posts/whisperclip-vs-superwhisper-wisprflow-macwhisper-which-ai-dictation-fits-your-workflow)
- [Best Dictation Apps for Mac 2026 — OnResonant](https://www.onresonant.com/resources/best-dictation-apps-mac)
- [Dictation Not Working on Mac: 7 Proven Fixes — Voibe](https://www.getvoibe.com/resources/dictation-not-working-mac/)
- [Fix Dictation Not Working — Willow Voice](https://willowvoice.com/blog/fix-mac-dictation-not-working)
- [Dictation Not Working on Mac — MacKeeper](https://mackeeper.com/blog/dictation-not-working-on-mac/)
- [How to fix macOS Accessibility permission — Macworld](https://www.macworld.com/article/347452/how-to-fix-macos-accessibility-permission-when-an-app-cant-be-enabled.html)
- [macOS secure input mode — Nick Turner](https://nickjvturner.com/posts/macos-secure-input-mode)
- [Finding the app/process using Secure Input — alexwlchan](https://alexwlchan.net/2021/secure-input/)
- [Keyboard Maestro Secure Input Problem wiki](https://wiki.keyboardmaestro.com/assistance/Secure_Input_Problem)
- [Karabiner-Elements alternatives — TextExpander](https://textexpander.com/blog/karabiner-elements-alternatives)
- [Better shortcuts with Karabiner Elements and Hammerspoon — dev.to](https://dev.to/ccedacero/better-shortcuts-with-karabiner-elements-and-hammerspoon-1plf)
- [halftone-dev/Typer — open-source voice dictation utility for macOS](https://github.com/halftone-dev/Typer)
- [hehehai/voxt — macOS press-to-talk, release-to-paste voice app](https://github.com/hehehai/voxt)
- [KeyVox — Free AI Voice Dictation for macOS](https://keyvox.app/)
- [Dictation on Mac: Complete 2025 Guide — VideoSDK](https://www.videosdk.live/developer-hub/stt/dictation-on-mac)
