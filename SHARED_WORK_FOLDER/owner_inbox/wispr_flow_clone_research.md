# Wispr Flow: How It Works & Building a Local Ollama-Powered Clone on macOS

Author: Pax (Senior Researcher)
Date: 2026-07-06
Task: workspace #493
Target machine: Apple Silicon Mac, macOS 26 (Darwin 25.5), Ollama already installed

---

## Executive Summary

Wispr Flow is a **cloud-only** AI dictation app. It works by (1) capturing audio while you hold a hotkey (Fn on Mac by default), (2) shipping the audio to Wispr's proprietary cloud ASR ensemble (not just Whisper — hosted on Baseten on AWS us-east-1, with reported p99 <700 ms model-side latency, ~1–2 s felt latency), (3) running a fine-tuned "Smart Formatting" LLM stage that strips fillers, adds punctuation, does context-aware auto-formatting per focused app, and applies **Backtrack** (voice edits like "scratch that"), then (4) inserting the polished text into whatever app is focused via the Accessibility API. It has a "Flow Bar" lozenge at the bottom of the screen, a "Command Mode" for voice-driven text transforms (Fn+Ctrl), a synced personal dictionary, 100+ languages with automatic language dispatch, and requires Microphone + Accessibility + (macOS 15+) Keyboard Monitoring permissions. The Mac app is native (Swift); the Windows build is Electron and buggier. Wispr Flow does not work offline at all.

**Recommended local clone architecture** (all on-device, Apple Silicon):

| Stage | Recommendation | Why |
|---|---|---|
| Hotkey | `KeyboardShortcuts` Swift package + CGEventTap fallback; Right-Option as default (avoid Fn — it's problematic to intercept cleanly) | Native, low-latency, works with Input Monitoring perm |
| Audio capture | AVAudioEngine tap on input node, 16 kHz mono Float32 | Standard native path, minimal deps |
| VAD / endpointing | Silero VAD via ONNX (`silero-vad-rs` in Rust, or `soniqo/speech-swift` bundle in Swift) | <1 ms per 30 ms chunk, gold-standard accuracy |
| ASR | **Apple SpeechTranscriber (macOS 26+) as primary**, with WhisperKit (Whisper large-v3-turbo) or `parakeet-mlx` as fallback for languages Apple doesn't cover | SpeechTranscriber is ~2× faster than Whisper large-v3-turbo, runs on ANE, ships with the OS on macOS 26, supports 42 locales including en_US, and streams |
| LLM cleanup | Ollama running `qwen3:4b` (or `gemma3:4b`) with a short strict-JSON system prompt, streaming disabled (batch is faster for one paragraph) | ~50–150 tok/s on M-series, <500 ms for typical dictation output |
| Text injection | Pasteboard save-set-paste-restore via NSPasteboard + CGEvent Cmd-V synthesis | Fastest, works everywhere; direct CGEvent-per-character is slow & drops chars in some apps |
| UI | SwiftUI menu-bar app (`MenuBarExtra`) + overlay window for a "Flow bar" | Native, ~40 MB RAM instead of Wispr's 800 MB Electron footprint on Windows |

**Top open-source project to study/fork**: [**VoiceInk**](https://github.com/beingpax/VoiceInk) (Swift, GPL-3.0, 5.4k stars, active). It already implements exactly this architecture — native Swift menu-bar app, whisper.cpp + Parakeet (via FluidAudio) engines, KeyboardShortcuts global hotkeys, optional cloud "AI Enhancement" — and would only need the AI Enhancement pointed at local Ollama instead of a cloud API to become the clone the owner wants. If GPL is a blocker, [**Handy**](https://github.com/cjpais/Handy) (Rust + Tauri, MIT, 25.9k stars) is the fallback but it's cross-platform Rust/Tauri, not Mac-native.

**Biggest technical risks**:
1. **AI cleanup quality parity with Wispr Flow.** Wispr's "Smart Formatting" is a fine-tuned model trained on *real user edits*. A stock Ollama model with a prompt will get you 80% there but will occasionally over-rewrite (paraphrase user speech) or under-rewrite (leave fillers). Expect meaningful prompt-engineering iteration, and consider making the LLM stage optional/toggleable (users like VoiceInk keep it off).
2. **Fn-key hotkey feasibility.** macOS treats Fn specially; CGEventTap can see Fn events but reliable "hold Fn only" (as Wispr does) is fragile — it has known debounce/release issues. Right-Option, Cmd-Right, or a chorded shortcut is far safer to ship first.

**All three deliverables**: (1) this document, (2) executive summary above, (3) journal entry inserted into workspace.db for 2026-07-06 — all complete.

---

## PART 1 — How Wispr Flow Actually Works

### 1.1 Core UX

**Activation modes** ([docs.wisprflow.ai — hotkeys](https://docs.wisprflow.ai/articles/2612050838-supported-unsupported-keyboard-hotkey-shortcuts), [hands-free](https://docs.wisprflow.ai/articles/6391241694-use-flow-hands-free)):

- **Push-to-talk (default)**: hold `Fn` on Mac. Alternatives you can rebind to: `Option+Space`, `Cmd+Right`, and other modifier-only or chorded shortcuts. Release = text is inserted at the cursor.
- **Hands-free**: `Fn+Space` starts continuous listening, `Fn` again stops. No key held during speech.
- **Command Mode**: `Fn+Ctrl` (or `Cmd+Ctrl+Option` on keyboards without an Apple Fn). Press-and-hold, speak a *command* rather than dictation ("make this more concise", "translate to Polish", "turn this outline into an essay"), release, and Flow rewrites the currently selected text (up to 1000 words) or generates fresh text at the cursor.

**The "Flow Bar"** ([docs — Flow Bar troubleshooting](https://docs.wisprflow.ai/articles/5002934560-why-is-the-wispr-bar-is-not-appearing-or-disappearing)):
Small lozenge always shown at the bottom-center of the screen. Expands on hover, shows the hotkey hint ("hold Fn to dictate"). During dictation it pulses/animates. Users can disable it via Settings → General → "Show Flow Bar at all times". Toggleable per-app.

**Insertion**: text is *pasted*, not typed. This is how "700 ms cloud latency then whole polished paragraph appears" works. Confirmed by the fact that Wispr Flow requires the **Accessibility** permission on macOS specifically to "type into any application on your behalf" ([Wispr setup docs](https://docs.wisprflow.ai/articles/3152211871-setup-guide), [permissions re-verify](https://docs.wisprflow.ai/articles/5510622673-re-verify-wispr-flow-permissions-after-updating)). Users report the polished text arrives all at once, not word-by-word — consistent with a paste operation gated on the cloud response.

### 1.2 The AI Layer

Wispr's "Smart Formatting" pipeline does three distinguishable things ([docs — Smart Formatting & Backtrack](https://docs.wisprflow.ai/articles/5373093536-how-do-i-use-smart-formatting-and-backtrack)):

1. **Cleanup**: punctuation, capitalization, filler removal ("um", "uh", "like", "you know"), disfluency and false-start removal.
2. **Context-aware formatting**: detects the *focused app*, then adjusts style — casual/no-trailing-period in Slack/iMessage, formal paragraph in Gmail, monospaced/no-punctuation-in-strings in a terminal/IDE, code-comment style in Cursor and VS Code ([Wispr — Cursor/VS Code use](https://docs.wisprflow.ai/articles/6434410694-use-flow-with-cursor-vs-code-and-other-ides)). Focused-app detection reads screen context (accessibility tree / app bundle id).
3. **Backtrack (voice edits)**: trigger words like "actually" and "scratch that" delete the previous phrase; you can also just restate — the LLM uses the full utterance as context and decides what you changed. Explicitly *does not* correct misheard words at this stage.

**Punctuation dictation** works verbatim: say "comma", "period", "em dash", "ellipsis" and it inserts the mark rather than the word.

**Custom Dictionary** ([Wispr — dictionary](https://docs.wisprflow.ai/articles/4052411709-teach-flow-your-words-with-the-dictionary)):
Two types of entries: (a) *word additions* (names, technical terms, product names — steer the ASR toward these) and (b) *replacement rules* ("if you hear X, write Y" — for persistent misspellings). Auto-populated when users correct output. Syncs across devices via the user's account (implication: cloud storage of the dictionary).

**Command Mode** ([docs — Command Mode](https://docs.wisprflow.ai/articles/4816967992-how-to-use-command-mode)):
Uses a *separate* hotkey (not a voice trigger like "Hey Flow"). Under the hood clearly a general-purpose LLM prompt with the selected text as input and the utterance as the instruction. Can access personal calendar/reminders.

**Whisper Mode**: quiet dictation (very soft voice / lip-microphone); marketing feature — implementation is presumably a low-noise-tuned ASR path or a gain-boosted preprocessor.

**Auto Cleanup toggle** in Settings can turn the LLM stage off entirely, returning raw ASR — useful when the LLM is over-rewriting.

### 1.3 Architecture (as publicly known)

**Where processing happens**: **entirely in the cloud.** Multiple independent reviews confirm no on-device mode, no self-hosting, no offline capability ([Voibe: Whisper vs Wispr Flow](https://www.getvoibe.com/resources/openai-whisper-vs-wispr-flow/), [Weesper: does Wispr work offline](https://weesperneonflow.ai/en/blog/2026-02-09-wispr-flow-review-cloud-dictation-2026/)). No internet = no dictation.

**What models Wispr Flow actually runs**: Not Whisper as the primary engine, despite the name confusion. Wispr's own research post ([wisprflow.ai/research/supporting-languages](https://wisprflow.ai/research/supporting-languages)) states they use "an ensemble of speech recognition models" and dynamically dispatch to the best per language — namechecking Scribe (ElevenLabs) and Gemini as outperforming Whisper for Asian languages. They then run a **fine-tuned formatting model** trained on real user edits (punctuation/spacing/grammar corrections captured from users). Reports elsewhere identify OpenAI and Meta cloud infrastructure in their stack ([Voibe review](https://www.getvoibe.com/resources/wispr-flow-review/)). Baseten hosts the models on AWS us-east-1 with p99 <700 ms ([reviewed on spokenly & willowvoice](https://willowvoice.com/blog/super-whisper-vs-wispr-flow-comparison-and-alternatives)).

**Client architecture**:
- **macOS**: native Swift app. Menu-bar presence with optional Dock icon. Ships arm64 + x86_64 builds.
- **Windows**: Electron. Users report it freezes target apps and has performance issues.
- **Idle footprint** (Mac, 2021 MBP, Reddit benchmarks): ~800 MB RAM, ~8% CPU idle ([Voibe review](https://www.getvoibe.com/resources/wispr-flow-review/)) — unusually high for a menu-bar dictation app; likely persistent WebSocket + audio pre-buffering + local ML for VAD/wake.

**macOS permissions used**:
- **Microphone** (mandatory)
- **Accessibility** (to inject text via keystroke/paste)
- **Keyboard Monitoring / Input Monitoring** (mandatory since macOS Sequoia 15 — needed for the global hotkey)
- **Screen recording** likely used for focused-app context detection (implied by "reads screen context to do its magic" in reviews)

### 1.4 Languages, latency, praise, complaints

- **Languages**: 100+, with 7 languages achieving English-parity model quality. Auto-detects language mid-session without switching settings.
- **Real-world felt latency**: 1–2 s from release-key to text-appearing for typical utterances. Not word-by-word streaming — batch replace at the end.
- **Accuracy**: independent testing ~97.2% on standard English audio (comparable to any good cloud STT).
- **Users praise**: end-to-end "just works" polish, cross-app formatting, natural filler removal, sub-second-ish latency, 100+ languages.
- **Users complain**: cloud-only (privacy), $15/mo Pro, no Linux, no self-hosting, Electron on Windows is janky, occasional over-rewriting when the LLM decides your natural sentence needs "polish", no way to point it at a local Whisper.

---

## PART 2 — Building a Local Clone on Apple Silicon with Ollama

### 2.1 Local ASR options

| Option | Runtime | Strengths | Weaknesses | On M-series |
|---|---|---|---|---|
| **Apple SpeechTranscriber (macOS 26+)** | Apple Speech framework | Fastest local option, ~2× Whisper large-v3-turbo, streams natively, ships with OS, ANE-accelerated, low RAM, real-time partials | Requires macOS 26; only 42 locales (missing e.g. hi_IN, id_ID, pl_PL); asset must be downloaded via `AssetInventory`; API is new (2025 WWDC) | Ideal primary path |
| **WhisperKit (large-v3 / large-v3-turbo)** | Swift, CoreML/ANE | Best-in-class Whisper on Apple Silicon; Argmax now bundles Whisper + speaker diarization + TTS under MIT ([argmax-oss-swift](https://github.com/argmaxinc/WhisperKit)); streaming supported | Chunked-streaming with stitching complexity; large-v3 ~3 GB | Excellent fallback / for languages Apple doesn't cover |
| **whisper.cpp (Metal)** | C++ | Fastest CPU/GPU inference of any Whisper runtime on Apple Silicon; large-v3 at ~10× real-time on M5 Pro; huge ecosystem; GGUF quantized models | Chunked, not naturally streaming; C++ bridging | Solid, battle-tested (what VoiceInk and OpenSuperWhisper use) |
| **MLX Whisper** | Python/Swift MLX | Native Apple MLX, ~2× whisper.cpp turbo in one benchmark ([llimllib notes](https://notes.billmill.org/dev_blog/2026/01/updated_my_mlx_whisper_vs._whisper.cpp_benchmark.html)) | Newer, smaller ecosystem, Python-centric | Worth considering if going all-in on MLX |
| **Parakeet V3 (via `parakeet-mlx` or FluidAudio)** | MLX / Swift | 600M params, 10× faster than Whisper large-v3-turbo on English, tops HF Open ASR leaderboard, low RAM/battery, streaming with partials + EOU detection ([soniqo/speech-swift DictateDemo](https://github.com/soniqo/speech-swift)) | English + 25 languages only (V3); newer & less familiar than Whisper | Excellent for English-dominant use |
| **faster-whisper (CTranslate2)** | Python | Best on NVIDIA GPUs | **No Metal support on Mac — CPU-only.** Slow on M-series. | Skip on Mac |

**Recommendation**: **Primary = Apple SpeechTranscriber** (macOS 26 is already the owner's OS; it's fastest and free; supported locales include `en_US`, `en_GB`, `en_AU`, `en_CA`, `en_IN`, and 30+ more per [Anton's SpeechAnalyzer guide](https://antongubarenko.substack.com/p/ios-26-speechanalyzer-guide)). **Fallback = WhisperKit** with `whisper-large-v3-turbo` for locales SpeechTranscriber doesn't support. Optional **Parakeet V3** as an English-fast path if latency is tight.

Sources: [WWDC25 session 277](https://developer.apple.com/videos/play/wwdc2025/277/), [Apple SpeechAnalyzer docs](https://developer.apple.com/documentation/speech/speechanalyzer), [MacRumors on Apple transcription speed](https://www.macrumors.com/2025/06/18/apple-transcription-api-faster-than-whisper/), [Arun Baby — Whisper vs Parakeet](https://www.arunbaby.com/speech-tech/0073-whisper-vs-parakeet-asr-decision/), [Parakeet V3 vs Whisper benchmark](https://whispernotes.app/blog/parakeet-v3-default-mac-model), [Parakeet MLX](https://github.com/senstella/parakeet-mlx).

### 2.2 The LLM cleanup / formatting stage on Ollama

**Model recommendation (best to worst for text cleanup on M-series)**:

- `qwen3:4b` or `qwen3:8b` — Qwen3 family is currently the sweet spot for instruction-following at small size; predictable JSON output; well-supported on Ollama.
- `gemma3:4b` — Notably clean prose output; strong at formatting/readability tasks per multiple 2026 comparisons. 140+ language multimodal-capable variant available. Slightly heavier than Qwen at same size.
- `llama3.2:3b` — Fastest option for cleanup-only tasks. 3 B params, ~80 tok/s on M4 Pro. Very well documented for 8 GB machines.
- `qwen3-coder:30b-a3b` (MoE) — If the owner needs the highest quality *and* has 24+ GB RAM: only 3 B active params so runs at ~130 tok/s on M4 Pro via Ollama MLX backend ([Ollama MLX blog](https://ollama.com/blog/mlx)). But overkill for cleanup.

**Prompt pattern** (well-tested for this exact use case; keep it strict):

```
System: You clean up dictated speech into polished written text.
Rules:
1. Remove fillers: um, uh, like (when filler), you know, sort of, kind of.
2. Add correct punctuation and capitalization.
3. Fix disfluencies and false starts. Honor "scratch that" / "actually" as edit signals.
4. DO NOT paraphrase. DO NOT add content. DO NOT change meaning.
5. Preserve technical terms and proper nouns exactly.
6. Output ONLY the cleaned text. No explanation.
Context: The user is writing in <APP_BUNDLE_ID>. Style: <casual|formal|code>.

User: <raw ASR transcript>
```

**Streaming**: For a 30-word cleaned paragraph, batch (non-streaming) Ollama call on Qwen3 4B is ~300–500 ms on M-series. Streaming the LLM output doesn't help perceived UX because you can't paste incrementally without visible cursor jitter and undo issues — better to wait for full response and paste once. **Do not stream the LLM stage.**

**Latency budget for the full pipeline** (M-series):

| Stage | Budget | Notes |
|---|---|---|
| Hotkey → audio start | <10 ms | AVAudioEngine tap |
| Speaking duration | user-controlled | — |
| VAD end-of-utterance | 500–800 ms | Silero waits for silence tail |
| ASR (SpeechTranscriber, 10-sec utterance) | 100–300 ms | Streaming; partial already available |
| LLM cleanup (Qwen3 4B, 30 words) | 300–500 ms | Batch, not streaming |
| Text injection (paste) | ~50 ms | NSPasteboard + Cmd-V |
| **Total from release-key to text-visible** | **~500–900 ms** | Faster than Wispr Flow's 1–2 s felt latency |

Sources: [Ollama MLX blog](https://ollama.com/blog/mlx), [Kotrotsos Apple Silicon LLM stack](https://kotrotsos.medium.com/the-local-ai-stack-for-apple-silicon-now-with-superpowers-c6038147eb1a), [LLMCheck benchmarks](https://llmcheck.net/benchmarks), [Ollama streaming docs](https://docs.ollama.com/api/streaming).

### 2.3 System integration on macOS

**Global hotkey capture**:
- Cleanest: the Swift package **[KeyboardShortcuts](https://github.com/sindresorhus/KeyboardShortcuts)** (used by VoiceInk). Wraps Carbon hotkey API and NSEvent monitors, gives users a settings-UI recorder. Needs no permission for standard shortcuts.
- For **modifier-only** hold (like Wispr's Fn or Right-Option-hold): use **CGEventTap** at HID or session level. Requires **Input Monitoring** TCC permission (mandatory since macOS 15 Sequoia).
- **Fn key specifically**: technically capturable as a modifier flag change event, but has known debounce/release-timing quirks ([elaineyxu/macos-global-hotkey-troubleshooting](https://github.com/elaineyxu/macos-global-hotkey-troubleshooting/blob/main/SKILL.md)). Some MacBook models don't expose it as a proper flag. **Recommendation: default to Right-Option-hold, offer Fn as an experimental setting.**
- Reference implementation for CGEventTap in Swift: [usagimaru/EventTapper](https://github.com/usagimaru/EventTapper).

**Audio capture**:
- **AVAudioEngine** with a tap on the `inputNode`, converted to 16 kHz mono Float32 (both SpeechTranscriber and Whisper want that format). Bare minimum code, well-documented. No CoreAudio HAL needed for a dictation use case.

**VAD**:
- **Silero VAD** is the gold standard: ONNX model, <1 ms per 30 ms chunk on one CPU thread, trained on 6000+ languages. Swift path: [soniqo/speech-swift](https://github.com/soniqo/speech-swift) bundles it (their DictateDemo uses Silero + Parakeet EOU-120M for end-of-utterance detection). Rust path: [silero-vad-rs](https://docs.rs/silero-vad-rs).
- For a push-to-talk-only clone you can arguably skip VAD (record while key held, stop on release). For hands-free mode, VAD-driven endpointing is mandatory.

**Text injection** — three options, pick paste:

1. **NSPasteboard + synthesized Cmd-V** ("save-set-paste-restore"): save current clipboard, put text on clipboard, synthesize Cmd-V via CGEvent, restore clipboard 200 ms later. **This is the default in ~every dictation app.** Fast, reliable, works in every app that supports paste. Downside: momentarily overwrites clipboard (mitigated with the `org.nspasteboard.TransientType` marker so history managers ignore it; see [nspasteboard.org](https://nspasteboard.org/)).
2. **CGEvent per-character keyboard synthesis**: slower (10–50 ms/char), can drop characters in some apps (browsers/Electron under load), doesn't handle non-ASCII unicode cleanly without `CGEventKeyboardSetUnicodeString`. Better for very short inserts.
3. **Accessibility API (AXUIElement)**: read the focused text field and directly set its `AXValue`. Cleanest technically, but many apps (browsers especially) don't expose the value attribute writably — falls through inconsistently.

Wispr Flow's use of paste is inferred from its behavior (single polished paragraph appears at once) and its need for the Accessibility permission.

**Required TCC permissions for the clone**:
- Microphone (`kTCCServiceMicrophone`) — always.
- Accessibility (`kTCCServiceAccessibility`) — to synthesize Cmd-V into the focused app.
- Input Monitoring (`kTCCServiceListenEvent`) — for the global hotkey (mandatory since macOS 15).
- Optional: Screen Recording — only if you want app-context reading like Wispr's per-app formatting.

Sources: [Kulman — implementing Auto-Type on macOS](https://blog.kulman.sk/implementing-auto-type-on-macos/), [Wispr Flow permissions](https://docs.wisprflow.ai/articles/5510622673-re-verify-wispr-flow-permissions-after-updating), [nspasteboard.org transient types](https://nspasteboard.org/).

### 2.4 Existing open-source alternatives to study or fork

| Project | Language / stack | License | Stars | Coverage | Verdict for our use |
|---|---|---|---|---|---|
| **[VoiceInk](https://github.com/beingpax/VoiceInk)** | Swift + whisper.cpp + FluidAudio (Parakeet) | **GPL-3.0** | 5.4 k | Native macOS 14+ menu-bar, KeyboardShortcuts, dual engine, cloud "AI Enhancement" already pluggable | **Best fork candidate.** Repoint AI Enhancement at local Ollama. |
| **[Handy](https://github.com/cjpais/Handy)** | Rust + Tauri (React UI) + transcribe-rs + Silero VAD | MIT | 25.9 k | Cross-platform (Mac/Win/Linux), Whisper + Parakeet V3, VAD included, active | Second choice. MIT-clean. Less Mac-idiomatic. |
| **[sebsto/wispr](https://github.com/sebsto/wispr)** | Swift + Whisper + Parakeet, `CompositeTranscriptionEngine` | Apache-2.0 | 127 | Native menu-bar, dual engine, small & readable | Great **reference codebase** — smaller than VoiceInk, easier to read, Apache-2.0 friendly. |
| **[OpenSuperWhisper](https://github.com/Starmel/OpenSuperWhisper)** | Swift + whisper.cpp | MIT | 1.9 k | Menu-bar dictation, Whisper+Parakeet, model downloader | Solid reference; text-injection layer is thinner than VoiceInk. |
| **[OpenWhispr](https://github.com/OpenWhispr/openwhispr)** | ? cross-platform | ? | ? | Whisper + Parakeet + cloud BYOK | Reasonable Wispr-Flow-alike; less Mac-native. |
| **[whisper-writer / verbumeng fork](https://github.com/verbumeng/whisper-writer)** | Python + faster-whisper | GPL/similar | small | Cross-platform, tray app, faster-whisper | Skip on Mac — faster-whisper is CPU-only on M-series. |
| **[whisper-local (drajb)](https://github.com/drajb/whisper-local)** | ? Whisper + voice commands | ? | small | Push-to-talk, voice commands, sub-second latency claim | Worth a glance for command-mode inspiration. |
| **VocalFlow, Weesper Neon Flow, Willow, Spokenly, MacWhisper** | Various | Commercial or freemium | — | Wispr-Flow-style commercial alternatives | Reference only; not open-source clone material. |
| **Superwhisper** | Native Mac | **Commercial** | — | Closest UX clone of Wispr Flow, fully local, Whisper + Parakeet | Not fork-able but a great UX reference. |

**Fork VoiceInk if GPL-3.0 is acceptable.** Otherwise study VoiceInk + sebsto/wispr and reimplement — the code volume is not large.

### 2.5 Minimal Viable Clone — component breakdown

```
                                                 [ Ollama daemon ]
                                                    (local)
                                                        ▲
                                                        │ HTTP POST
                                                        │ /api/generate
                                                        │
[ Hotkey listener ]──► [ Audio capture ]──► [ VAD ]──► [ ASR ]──► [ LLM cleanup ]──► [ Text injector ]
  KeyboardShortcuts    AVAudioEngine        Silero    Speech-      Qwen3 4B /         NSPasteboard
  + CGEventTap         inputNode tap        ONNX      Transcriber  Gemma3 4B          + Cmd-V
                       (16 kHz mono)                  (fallback:                       CGEvent
                                                     WhisperKit)
                                                        │
                                                        ▼
                                              [ Menu bar UI + Flow bar overlay ]
                                                 SwiftUI MenuBarExtra + NSPanel
```

**Component-by-component**:

1. **Hotkey listener** — Right-Option hold (default), user-rebindable via `KeyboardShortcuts` package. CGEventTap for modifier-only-hold detection. Emits `.startRecording` / `.stopRecording` events.
2. **Audio capture** — AVAudioEngine tap. Buffer to a ring of 16 kHz PCM. Only start writing to the ring on `.startRecording`.
3. **VAD / endpointing** — Silero VAD on 30 ms frames. In push-to-talk, just used to trim leading/trailing silence. In hands-free, used to detect end-of-utterance (300–500 ms of silence tail).
4. **ASR** — First choice: SpeechTranscriber (streaming, partials, macOS 26+). Emit final transcript to the LLM stage on utterance end. Fallback: WhisperKit large-v3-turbo.
5. **LLM cleanup** — Ollama `/api/generate` batch call with the strict system prompt above, `stream: false`, low temperature (0.2), 200 ms typical latency. Include focused-app bundle id in the context field.
6. **Text injector** — Save `NSPasteboard.general.string`, set text with `TransientType` marker, synthesize Cmd-V via CGEvent, restore original clipboard after 200 ms.
7. **UI** — `MenuBarExtra` for menu-bar; a borderless always-on-top `NSPanel` for the Flow-bar-style lozenge; hotkey recorder + dictionary editor in a Settings scene.

**Hardware requirements** (Apple Silicon, unified memory):
- **Minimum**: 8 GB (Llama3.2 3B or Qwen3 4B Q4 + SpeechTranscriber ~= <5 GB active).
- **Comfortable**: 16 GB (Whisper large-v3-turbo + Qwen3 8B ~= <10 GB active, room for other apps).
- **Sweet spot**: 24 GB (Qwen3-Coder-30B-A3B MoE for cleanup + WhisperKit large-v3 loaded; 130 tok/s).

**Expected end-to-end latency**: **500–900 ms** from key-release to text-visible on M-series with SpeechTranscriber + Qwen3 4B + paste. Beats Wispr Flow's ~1–2 s felt latency.

### 2.6 Notes and caveats specific to this environment

- **External volume mounted `nosuid`** (from user memory): repo lives on `/Volumes/GIT`. Any component the user wants launched by launchd at login must live on the boot volume (`~/.local/bin/` etc.) — but a menu-bar app is normally launched via `LSUIElement`/`Launch Services`, not launchd, so **for this project the constraint is moot** for the app itself. It only matters if we add a launchd LaunchAgent for e.g. background dictionary sync.
- **Ollama already running** for Homunculus — the clone can share the same Ollama instance on `localhost:11434`. Load a lightweight dictation-cleanup model alongside whatever Homunculus uses; Ollama will keep both hot within its `OLLAMA_KEEP_ALIVE` window.
- **macOS 26 (Darwin 25.5)** unlocks SpeechTranscriber. Don't design around it as *required* if the owner might downgrade — provide the WhisperKit fallback path.

---

## Sources

**Wispr Flow official**
- [wisprflow.ai — Features](https://wisprflow.ai/features)
- [wisprflow.ai/research — Supporting 100 languages](https://wisprflow.ai/research/supporting-languages)
- [docs.wisprflow.ai — Setup guide](https://docs.wisprflow.ai/articles/3152211871-setup-guide)
- [docs.wisprflow.ai — Hotkey shortcuts](https://docs.wisprflow.ai/articles/2612050838-supported-unsupported-keyboard-hotkey-shortcuts)
- [docs.wisprflow.ai — Hands-free mode](https://docs.wisprflow.ai/articles/6391241694-use-flow-hands-free)
- [docs.wisprflow.ai — Command Mode](https://docs.wisprflow.ai/articles/4816967992-how-to-use-command-mode)
- [docs.wisprflow.ai — Smart Formatting & Backtrack](https://docs.wisprflow.ai/articles/5373093536-how-do-i-use-smart-formatting-and-backtrack)
- [docs.wisprflow.ai — Dictionary](https://docs.wisprflow.ai/articles/4052411709-teach-flow-your-words-with-the-dictionary)
- [docs.wisprflow.ai — Multiple languages](https://docs.wisprflow.ai/articles/3191899797-use-flow-with-multiple-languages)
- [docs.wisprflow.ai — Re-verify permissions](https://docs.wisprflow.ai/articles/5510622673-re-verify-wispr-flow-permissions-after-updating)
- [docs.wisprflow.ai — Flow Bar troubleshooting](https://docs.wisprflow.ai/articles/5002934560-why-is-the-wispr-bar-is-not-appearing-or-disappearing)
- [docs.wisprflow.ai — MDM deployment](https://docs.wisprflow.ai/articles/9363440133-deploy-wispr-flow-via-mdm)

**Wispr Flow independent reviews / analysis**
- [Voibe — Wispr Flow review](https://www.getvoibe.com/resources/wispr-flow-review/)
- [Voibe — Whisper vs Wispr Flow](https://www.getvoibe.com/resources/openai-whisper-vs-wispr-flow/)
- [Voibe — Wispr Flow vs Superwhisper](https://www.getvoibe.com/resources/wispr-flow-vs-superwhisper/)
- [Weesper — Does Wispr work offline](https://weesperneonflow.ai/en/blog/2026-02-09-wispr-flow-review-cloud-dictation-2026/)
- [Spokenly — Wispr Flow review](https://spokenly.app/blog/wispr-flow-review)
- [Willow Voice — Super Whisper vs Wispr Flow](https://willowvoice.com/blog/super-whisper-vs-wispr-flow-comparison-and-alternatives)
- [Zack Proser — WisprFlow Review](https://zackproser.com/blog/wisprflow-review)

**Apple SpeechAnalyzer / SpeechTranscriber (macOS 26)**
- [Apple Developer — SpeechAnalyzer](https://developer.apple.com/documentation/speech/speechanalyzer)
- [WWDC25 Session 277 — Speech-to-text with SpeechAnalyzer](https://developer.apple.com/videos/play/wwdc2025/277/)
- [Anton Gubarenko — SpeechAnalyzer guide](https://antongubarenko.substack.com/p/ios-26-speechanalyzer-guide)
- [MacRumors — Apple transcription API faster than Whisper](https://www.macrumors.com/2025/06/18/apple-transcription-api-faster-than-whisper/)
- [MacStories — Apple speech APIs vs Whisper](https://www.macstories.net/stories/hands-on-how-apples-new-speech-apis-outpace-whisper-for-lightning-fast-transcription/)
- [Callstack — On-Device Speech Transcription with SpeechAnalyzer](https://www.callstack.com/blog/on-device-speech-transcription-with-apple-speechanalyzer)

**Local ASR benchmarks**
- [PromptQuorum — whisper.cpp vs faster-whisper 2026](https://www.promptquorum.com/power-local-llm/local-whisper-stt-comparison-2026)
- [JustVoice — Whisper benchmark Apple Silicon M1-M4](https://justvoice.ai/blog/whisper-benchmark-apple-silicon-m3-m4)
- [llimllib — mlx_whisper vs whisper.cpp benchmark](https://notes.billmill.org/dev_blog/2026/01/updated_my_mlx_whisper_vs._whisper.cpp_benchmark.html)
- [Arun Baby — Whisper vs Parakeet decision](https://www.arunbaby.com/speech-tech/0073-whisper-vs-parakeet-asr-decision/)
- [WhisperNotes — Parakeet V3 vs Whisper benchmark](https://whispernotes.app/blog/parakeet-v3-default-mac-model)
- [WhisperKit paper (arXiv)](https://arxiv.org/html/2507.10860v1)

**Ollama / local LLM on Apple Silicon**
- [Ollama — MLX preview blog](https://ollama.com/blog/mlx)
- [Ollama — Streaming docs](https://docs.ollama.com/api/streaming)
- [Ollama — Model library](https://ollama.com/library)
- [Ante Kapetanovic — Qwen3.5 on Apple Silicon benchmark](https://antekapetanovic.com/blog/qwen3.5-apple-silicon-benchmark/)
- [Marco Kotrotsos — Local AI stack for Apple Silicon](https://kotrotsos.medium.com/the-local-ai-stack-for-apple-silicon-now-with-superpowers-c6038147eb1a)
- [LLMCheck — Apple Silicon LLM benchmarks](https://llmcheck.net/benchmarks)
- [Local AI Master — Best small language models 2026](https://localaimaster.com/blog/small-language-models-guide-2026)

**Open-source dictation projects**
- [VoiceInk (Beingpax)](https://github.com/beingpax/VoiceInk)
- [Handy (cjpais)](https://github.com/cjpais/Handy)
- [sebsto/wispr](https://github.com/sebsto/wispr)
- [OpenSuperWhisper (Starmel)](https://github.com/Starmel/OpenSuperWhisper)
- [OpenWhispr](https://github.com/OpenWhispr/openwhispr)
- [whisper-writer (savbell)](https://github.com/savbell/whisper-writer)
- [WhisperKit / argmax-oss-swift](https://github.com/argmaxinc/WhisperKit)
- [parakeet-mlx (senstella)](https://github.com/senstella/parakeet-mlx)
- [speech-swift (soniqo)](https://github.com/soniqo/speech-swift)
- [silero-vad](https://github.com/snakers4/silero-vad)
- [silero-vad-rs](https://docs.rs/silero-vad-rs)
- [Awesome Whisper Apps (danielrosehill)](https://github.com/danielrosehill/Awesome-Whisper-Apps)
- [Awesome Voice Typing (primaprashant)](https://github.com/primaprashant/awesome-voice-typing)

**macOS integration**
- [Igor Kulman — Implementing Auto-Type on macOS](https://blog.kulman.sk/implementing-auto-type-on-macos/)
- [Adonis Gaitatzis — Capture key bindings in Swift](https://gaitatzis.medium.com/capture-key-bindings-in-swift-3050b0ccbf42)
- [usagimaru/EventTapper — CGEventTap module](https://github.com/usagimaru/EventTapper)
- [elaineyxu — macOS global hotkey troubleshooting](https://github.com/elaineyxu/macos-global-hotkey-troubleshooting/blob/main/SKILL.md)
- [sindresorhus/KeyboardShortcuts](https://github.com/sindresorhus/KeyboardShortcuts)
- [nspasteboard.org — transient pasteboard types](https://nspasteboard.org/)
- [Apple — NSPasteboard docs](https://developer.apple.com/documentation/appkit/nspasteboard/)
