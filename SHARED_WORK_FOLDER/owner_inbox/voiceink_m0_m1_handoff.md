# VoiceInk M0 / M1 Handoff Checklist

**Author:** Wren (Voice-First Mac Productivity Specialist)
**Date:** 2026-07-06
**Task:** Workspace #497
**From:** What Wren completed → **To:** What the owner must click through

---

## What Was Built and Where

| Item | Location | State |
|---|---|---|
| VoiceInk source clone | `~/VoiceInk-local/` | Cloned from `beingpax/VoiceInk` main branch, personal branch `personal/local-ollama` |
| Default Ollama model patched | `~/VoiceInk-local/VoiceInk/Services/OllamaService.swift` line 29 | Changed `"llama2"` → `"qwen2.5:3b"` (committed; was briefly 7b, revised per Rune's measured spec §11) |
| Upstream remote | `~/VoiceInk-local/` | Added as `upstream https://github.com/beingpax/VoiceInk.git` |
| Ollama validated | `localhost:11434` | `qwen2.5:7b` confirmed present and responding |
| Rune's system prompt | This document (below) | End-to-end tested, latency measured |
| **VoiceInk.app (M0 build)** | `~/Downloads/VoiceInk.app` | **Built and launched successfully — 2026-07-06** |

---

## M0 Build — COMPLETE (2026-07-06)

**`make local` succeeded.** Built with Xcode 26.6 (Build 17F113) using `DEVELOPER_DIR=/Applications/Xcode.app/Contents/Developer` override (note: `xcode-select` still points at CommandLineTools — the DEVELOPER_DIR override was sufficient, but you can permanently fix it with `sudo xcode-select -s /Applications/Xcode.app/Contents/Developer`).

**App location:** `~/Downloads/VoiceInk.app`  
**whisper.cpp dependencies:** `~/VoiceInk-Dependencies/whisper.cpp/` (built from source, ~25 min first-time compile)  
**Launch verified:** VoiceInk process confirmed running post-launch.

If Gatekeeper blocks future launches after a rebuild:
```bash
xattr -dr com.apple.quarantine ~/Downloads/VoiceInk.app
```

---

## Deviations from Stock VoiceInk

| # | File | Change | Reason |
|---|---|---|---|
| 1 | `VoiceInk/Services/OllamaService.swift` line 29 | Default model: `"llama2"` → `"qwen2.5:3b"` | Rune's measured revision: 3b is ~2× faster (~46 tok/s vs ~19) and holds the no-paraphrase contract; runs dual-resident with Homunculus's 7b |

---

## Owner Checklist — Get to Working Dictation in ~15 Minutes

Work through these steps in order after the app builds and launches.

---

### STEP 1 — Grant Permissions (do in this order)

**1a. Microphone**
System Settings → Privacy & Security → Microphone → find VoiceInk → toggle ON

**1b. Input Monitoring** (required for global hotkey)
System Settings → Privacy & Security → Input Monitoring → click + → select VoiceInk.app → toggle ON

**1c. Accessibility** (required for text injection via Cmd-V)
System Settings → Privacy & Security → Accessibility → click + → select VoiceInk.app → toggle ON

> If a permission appears granted but the feature is broken, reset it:
> `tccutil reset Accessibility com.prakashjoshipax.VoiceInk`
> (Speech Recognition will prompt automatically on first use — click Allow.)

---

### STEP 2 — Configure Ollama AI Enhancement (Settings UI)

Open VoiceInk → click the menu bar icon → Settings (⌘,) → navigate to **AI Enhancement** or **Modes**

**2a. Set AI Provider to Ollama**
- Provider dropdown → select **Ollama**
- Base URL: `http://localhost:11434` (should already be correct)
- Click **Refresh / Test Connection** — should show `qwen2.5:3b` and `qwen2.5:7b` in the model list
- Select **qwen2.5:3b** from the model dropdown (Rune's revised primary — ~490–730 ms typical; pick `qwen2.5:7b` only if you want single-resident to save 2.2 GB RAM and can accept ~1–1.5 s cleanup latency)
- If a timeout field is exposed, set it to **1500 ms** (Rune's revised hard cap; on timeout the raw transcript passes through unchanged)

**2b. Create the cleanup prompt**
In Settings → AI Enhancement → Prompts (or "Custom Prompts") → click **+** to add a new prompt

Title: `Cleanup (Ollama)`

Paste this exact text into the System Prompt field:

```
You transform a raw dictation transcript into the exact text the speaker would have typed themselves. You do not improve, polish, edit, or shorten. You only clean.

RULES (all must hold):
1. Remove filler words only: um, uh, er, ah, hmm, you know, sort of, kind of, I mean, leading "so", leading "well", basically, literally-as-filler, trailing "right?". Everything else stays.
2. Remove false starts and self-restarts. Keep the completed thought.
3. Self-correction commands are edits, not text. Apply them and remove them:
   - "scratch that" → delete the immediately preceding phrase.
   - "no wait" / "actually make that X" / "correction, X" → replace the last phrase with X.
   - "delete that" → delete the last phrase.
   - "new paragraph" → paragraph break.
4. Dictated punctuation becomes marks: "comma" → , / "period" → . / "question mark" → ? / "exclamation point" → ! / "colon" → : / "semicolon" → ; / "open quote" and "close quote" → " / "dash" or "em dash" → — / "hyphen" → - / "ellipsis" → …
5. Capitalize sentence starts. Add a terminal period if the speaker ended a thought without dictating one. Never invent question marks.
6. Format numbers, dates, times conservatively: "three thirty PM" → "3:30 PM", "January fifteenth" → "January 15", "two thousand twenty six" → "2026". Do NOT expand "five million" into digits.
7. Preserve every proper noun, technical term, brand name, and identifier the speaker used, exactly.

YOU MUST NOT:
- Paraphrase. Do not rewrite for style, brevity, or clarity.
- Summarize. Long ramblings stay long.
- Shift tone. Casual stays casual. Profanity stays. Slang stays.
- Add content the speaker did not say. No greetings, closings, subject lines, or transitions.
- Remove content beyond fillers and false starts. If it seems redundant, it stays.
- Correct facts. If the speaker said Wednesday, output Wednesday.
- Translate.
- Wrap the output in quotes or preface it with anything.

OUTPUT: only the cleaned text. No explanation. No metadata. No trailing commentary.

Example 1 — resist paraphrase, preserve rambling
Input: um so I was thinking maybe we could like get together on Thursday and you know just kind of go over the deck plans
Output: I was thinking maybe we could get together on Thursday and just go over the deck plans.

Example 2 — self-correction with "no wait"
Input: let's meet on Tuesday no wait make that Wednesday at three
Output: Let's meet on Wednesday at 3.

Example 3 — scratch that
Input: send Bob the invoice scratch that send Bob the receipt
Output: Send Bob the receipt.

Example 4 — dictated punctuation, technical vocabulary
Input: the config file lives at slash etc slash nginx slash sites dash available comma make sure permissions are six four four
Output: The config file lives at /etc/nginx/sites-available, make sure permissions are 644.

Example 5 — run-on, do not summarize
Input: I need to pick up milk and also bread and also I think we're out of eggs and I want to grab some coffee if they have that dark roast the one from Ethiopia
Output: I need to pick up milk and also bread, and also I think we're out of eggs, and I want to grab some coffee if they have that dark roast, the one from Ethiopia.

Example 6 — profanity and casual tone stay
Input: this fucking build is broken again um can you look at it
Output: This fucking build is broken again. Can you look at it?
```

Save the prompt.

**2c. Enable AI Enhancement in your Mode**
Settings → Modes → select your default mode (or "Standard") → toggle **AI Enhancement: ON** → select prompt: `Cleanup (Ollama)`

Set **Minimum word count** to `3` (skip Ollama for single-word commands).

---

### STEP 3 — Configure Hotkey (Settings UI)

Settings → Shortcuts → Primary Shortcut → click the shortcut recorder → press **Right-Option (⌥ right)** → set mode to **Push-to-Talk**

> If the recorder rejects a modifier-only binding (no keycode accepted), bind **Right-Option + Space** instead — still one-handed, still easy to hold.

Disable macOS built-in Dictation to prevent collision:
System Settings → Keyboard → Dictation → toggle **OFF**

---

### STEP 4 — Ollama Environment (Ollama.app Settings)

Rune's revised spec (§2.4, §11.4) requires `OLLAMA_KEEP_ALIVE=30m`, `OLLAMA_MAX_LOADED_MODELS=2` (dual-resident: Homunculus's `qwen2.5:7b` + cleanup's `qwen2.5:3b` = 6.9 GB VRAM, verified fits on the 16 GB M4), and `OLLAMA_NUM_PARALLEL=2`.

Ollama runs as a macOS app (no launchd plist on this machine). Set env vars:

**Option A — Ollama.app Settings UI** (if the app exposes these fields):
Ollama menu bar icon → Settings → Advanced → set Keep Alive to 30m, Max loaded models to 2, Parallel requests to 2.

**Option B — launchctl environment** (terminal, survives reboots):
```bash
launchctl setenv OLLAMA_KEEP_ALIVE 30m
launchctl setenv OLLAMA_MAX_LOADED_MODELS 2
launchctl setenv OLLAMA_NUM_PARALLEL 2
```
Then quit and relaunch Ollama.app from /Applications.

> Note: `OLLAMA_MODELS` is already set to `/Volumes/GIT/OLLAMA/ollama/models` — leave that alone.

---

## M0 Acceptance Tests

Build gate cleared — `~/Downloads/VoiceInk.app` is built and launched. Run these after granting permissions (Step 1):

- [ ] VoiceInk icon appears in menu bar
- [ ] Hold hotkey → MiniRecorder panel appears with audio waveform
- [ ] Speak a sentence into TextEdit, release hotkey → raw transcript appears
- [ ] No cloud requests in Console.app filter `com.prakashjoshipax.VoiceInk` during transcription

---

## M1 Acceptance Tests

Run these after Step 2 (AI Enhancement configured):

- [ ] Dictate into TextEdit: *"um so I was uh thinking we could like schedule this for Friday period"* → output: *"I was thinking we could schedule this for Friday."* (fillers gone, punctuation converted)
- [ ] Dictate: *"send the invoice scratch that send the receipt"* → output: *"Send the receipt."* (scratch-that honored)
- [ ] Dictate a 2–3 sentence ramble with no rewriting or summarization in output
- [ ] Check Console.app — only `localhost:11434` network traffic, no cloud calls
- [ ] Felt latency (key-release to text visible) under ~2 seconds for a 1–2 sentence dictation

---

## Ollama Validation Results (Wren, 2026-07-06)

Validated end-to-end from shell with Rune's exact parameters (`stream:false`, `temperature:0.1`, `keep_alive:"30m"`, `top_p:0.9`, `top_k:20`, `repeat_penalty:1.05`).

| Test | Result |
|---|---|
| Model present | `qwen2.5:7b` Q4_K_M, 4.7 GB confirmed |
| Connection | `localhost:11434` responding |
| Filler removal | Passed — um/uh/like/you know removed |
| Self-correction ("no wait make that Friday") | Passed — Thursday replaced with Friday |
| Dictated punctuation ("comma", "period") | Passed — converted to marks |
| No-paraphrase contract | Passed — speaker's phrasing preserved |
| Wall-clock latency (warm, short utterance ~18 tokens) | **904ms** |
| Wall-clock latency (warm, filler-heavy utterance ~31 tokens) | **1570ms** |
| Known minor issue | Leading "So" occasionally survives as filler (calibration item, not a blocker) |

Latency note (revised 2026-07-06 after Rune's measured reconciliation, spec §11): the 7b numbers above are what prompted the model switch — at ~19 tok/s, 7b cleanup lands 900–1570 ms and would have blown the original 800 ms timeout on nearly every dictation. The revised setup is **`qwen2.5:3b`** (~46 tok/s): measured 490 ms short / 730 ms filler-heavy / ~1050 ms long run-on, under a **1500 ms** hard timeout that falls back to the raw transcript. Cold-start on first call remains 1–2 s one-time.

---

## Known Risks and Notes

1. **xcode-select still points at CommandLineTools** — the build used a DEVELOPER_DIR env override. This is fine for `make local` (the Makefile doesn't call `xcode-select`). To permanently fix: `sudo xcode-select -s /Applications/Xcode.app/Contents/Developer`.
2. **SpeechAnalyzer fast path** (macOS 26 ANE) — optional optimization: Xcode → VoiceInk target → Build Settings → User-Defined → add `ENABLE_NATIVE_SPEECH_ANALYZER = 1` in both Debug and Release. Verify in Settings → Transcription that engine shows "Apple Speech" not "Whisper". This eliminates whisper.cpp memory use (~2.7 GB freed for other work). Requires a rebuild.
3. **Ollama cold-start** — check if `ModelPrewarmService.swift` covers Ollama (it may only pre-warm whisper.cpp). If dictation latency spikes after idle, this is why.
4. **Right-Option collision** — check Karabiner, BTT, or Raycast don't consume Right-Option first. Use Karabiner-EventViewer to confirm.
5. **Homunculus coexistence (revised)** — cleanup now uses its own `qwen2.5:3b` dual-resident alongside Homunculus's `qwen2.5:7b` (`OLLAMA_MAX_LOADED_MODELS=2`); no lockstep model coupling anymore. Just don't drop `OLLAMA_MAX_LOADED_MODELS` back to 1, or the two projects will evict each other's model and every dictation/capture pays a 2–4 s reload.

---

## Repo Quick Reference

```bash
# Update from upstream
cd ~/VoiceInk-local
git fetch upstream
git rebase upstream/main

# Rebuild after updates
make local

# Remove quarantine if Gatekeeper blocks
xattr -dr com.apple.quarantine ~/Downloads/VoiceInk.app
```

Bundle ID (for tccutil resets): `com.prakashjoshipax.VoiceInk`
