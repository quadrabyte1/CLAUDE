# Wispr Flow Clone — Ollama Transcript-Cleanup Stage (Design Spec v1)

Author: Rune (Local-LLM Voice Assistant Backend Engineer)
Task: workspace #495 (spec) / #498 (calibration revision)
Date: 2026-07-06 · **Revised 2026-07-06** — see §11 for measurement-driven changes.
Pipeline position: raw ASR (whisper.cpp / Parakeet / SpeechTranscriber inside VoiceInk fork) → **this stage** → paste into focused app
Companion: Wren's fork/implementation plan at `owner_inbox/wispr_flow_clone_plan.md`

> **Revision notice (2026-07-06):** Wren measured actual latency on the owner's M4 Mac mini (16 GB) and found the v1-draft numbers below (150–350 ms typical / 800 ms timeout) do not hold — see §11 for the full decomposition. The **skimmable summary below reflects the revised recommendation**; the estimates struck through in §2.1 are the original v1-draft numbers, preserved for honesty.

---

## Skimmable summary (revised 2026-07-06)

| Item | Decision |
|---|---|
| Recommended primary model | **`qwen2.5:3b`** (Q4_K_M) — dual-resident alongside Homunculus's `qwen2.5:7b`. See §2.4 (revised) and §11. |
| Original v1-draft primary (superseded) | ~~`qwen2.5:7b`~~ — measured too slow on the owner's M4 (typical warm cleanup 900–1500 ms vs 500 ms budget). Retained as the *fallback* when RAM cannot hold two residents. |
| Rejected alternate | `qwen3:4b` — this is a *thinking* model in current Ollama builds; it emits `<think>…</think>` chains and blows every budget even with `think:false`. See §11.3. |
| Expected added latency, 1–3 sentence dictation, M-series, model warm | **300–600 ms typical** (`qwen2.5:3b` + full prompt, prefix-cached), **~1000 ms worst-case run-on**. Cold start on the first call: +1–2 s (one-time). |
| Streaming | **No.** Batch. Paste-once UX wins over token drip. |
| Ollama call | `POST /api/chat`, `stream:false`, `keep_alive:"30m"`, `temperature:0.1`, `top_p:0.9`, `num_predict` ≤ 2× input tokens |
| Timeout / fallback | **1500 ms hard cap** (revised up from 800 ms) → **pass raw ASR through unchanged**. Never block the paste. Never lose the user's words. |
| Output format | **Plain text.** No JSON, no wrapper. Structured decoding does not help prose fidelity. |
| Toggleability | Global on/off (Settings) + per-invocation bypass (hold Shift while releasing hotkey → skip LLM stage) + auto-skip when Ollama unreachable |
| Resident-model collision with Homunculus | **Revised: accept dual-resident.** Homunculus keeps `qwen2.5:7b` (4.7 GB VRAM); cleanup uses `qwen2.5:3b` (2.2 GB VRAM). Total 6.9 GB — comfortable on the 16 GB M4. Requires `OLLAMA_MAX_LOADED_MODELS=2`. See §2.4 revised and §11.4. |
| Calibration deliverable owner must produce | A corpus of **≥ 30 real dictations** (raw ASR + hand-corrected target) covering all seven hard-case categories in §6.2. Without it, this stage cannot be tuned. |

---

## 1. Task definition — the contract

The cleanup stage transforms a raw ASR transcript into text a human would have typed themselves. The contract is precise, and the *forbidden* list is as important as the *allowed* list. This section is the product.

### 1.1 What the stage MUST do

1. **Remove disfluencies and fillers** — "um", "uh", "er", "ah", "hmm", "you know", "like" (when used as filler, not as a verb/simile), "sort of", "kind of", "I mean", "so" (leading), "well" (leading), "basically", "literally" (when used as a filler intensifier), "right?" (trailing verbal check).
2. **Remove false starts / self-restarts** — "I was going to — I mean I wanted to" → "I wanted to".
3. **Honor explicit self-correction commands** — treat these as edits, not as text:
   - "scratch that" → delete the immediately preceding phrase/clause and continue.
   - "no wait" / "no, wait" / "actually, make that X" / "correction, X" → replace the last phrase with X.
   - "delete that" → delete the last phrase.
   - "new paragraph" / "new line" → paragraph break.
4. **Convert dictated punctuation to marks** — literal spoken words become marks: "comma" → `,`, "period" / "full stop" → `.`, "question mark" → `?`, "exclamation point" → `!`, "colon" → `:`, "semicolon" → `;`, "open quote" / "close quote" → `"`, "open paren" / "close paren" → `(` `)`, "dash" / "em dash" → `—`, "hyphen" → `-`, "ellipsis" → `…`, "new paragraph" → paragraph break, "new line" → line break.
5. **Add capitalization and terminal punctuation** where the speaker did not dictate any — sentence starts capitalized, sentence-final period unless the speaker ended with an obvious question intonation cue (leave a period; do not invent question marks).
6. **Normalize spacing** — collapse repeated whitespace, put one space after each terminal mark, no space before commas/periods.
7. **Format numbers, dates, and times conservatively when unambiguous**:
   - "three thirty PM" → "3:30 PM"
   - "January fifteenth" → "January 15"
   - "two thousand twenty six" → "2026"
   - "five million" → "5 million" (NOT "5,000,000" — the speaker chose the words)
   - Phone numbers, addresses: leave the digits the speaker dictated; add hyphens only if the speaker paused in a phone-number cadence (this is unreliable — err on leaving as spoken).
8. **Preserve technical vocabulary and proper nouns exactly** — code identifiers, product names, personal names, acronyms. When personal dictionary hints are supplied (§5), match those spellings.

### 1.2 What the stage MUST NOT do (the forbidden list)

Violations here destroy user trust. These are hard errors in the eval harness (§6).

1. **No paraphrasing.** Do not rewrite the speaker's word choice for style, brevity, or "polish".
2. **No summarization.** If the speaker rambled, the output rambles at the same length. The stage cleans; it does not edit.
3. **No tone-shifting.** Casual stays casual. Formal stays formal. Profanity stays. Slang stays.
4. **No content addition.** Do not invent a greeting, a closing, a subject line, a topic sentence, a transitional phrase, or a clarification the speaker did not say.
5. **No content removal beyond fillers and false starts.** If the speaker said something factual, it stays — even if it seems redundant, off-topic, or unclear.
6. **No fact correction.** If the speaker said "the meeting is Wednesday" but Wednesday is a Saturday, output "Wednesday". The model is not a knowledge base.
7. **No translation.** Language stays as spoken.
8. **No punctuation invention beyond §1.1 rules.** Do not add semicolons, em-dashes, or parentheticals the speaker did not dictate.
9. **No metadata, framing, or explanation.** Output is only the cleaned text — no "Here is the cleaned version:", no quotes around the output, no trailing newline commentary.

### 1.3 The Wispr Flow quality bar in one sentence

Wispr Flow's Smart Formatting was fine-tuned on real user edits — meaning its bias is toward what users *keep* rather than what a stock instruct model wants to *improve*. Our stock model has the opposite bias by default (LLM RLHF pushes toward "helpful" rewriting). The prompt in §3 and the calibration corpus in §6 exist to counteract that bias. **Under-cleaning is a recoverable failure. Over-rewriting is a trust-fracturing failure.** When in doubt, the model must leave the speaker's words alone.

---

## 2. Model selection

> **Revised 2026-07-06** — v1-draft estimates in this section were validated on the owner's M4 Mac mini (16 GB) and did not hold. Original numbers are marked ~~struck through~~; measured replacements sit next to them. See §11 for the raw-data revision.

### 2.1 Candidate comparison — v1 estimates vs measured

Rows below reflect *v1-draft estimates* alongside the *measured warm latency on the owner's M4 Mac mini* with the exact §3 prompt (system prompt = 855 tokens including six few-shots) and §3.3 sampling parameters. Full data tables in §11.2.

| Model | Size (Q4) | v1 tok/s estimate | **Measured tok/s** | v1 latency estimate (60 out tok) | **Measured warm latency** (short 18-tok / medium 25-tok / run-on 46-tok) | Contract adherence |
|---|---|---|---|---|---|---|
| ~~`qwen2.5:7b` (v1 primary)~~ | 4.7 GB | ~~55–75~~ | **~19** | ~~~1000 ms~~ | **1010 / 1500 / 2560 ms** | Strong. Strips leading "So", preserves rambling. |
| `qwen3:4b` | 3.2 GB | ~~90–120~~ | **~36 (raw)** but emits chain-of-thought → useless | ~~~600 ms~~ | **11–13 s** (saturates `num_predict=400` with reasoning) | **Rejected** — see §11.3. Emits `<think>…</think>` even with `think:false`; can't return prompt output within budget. |
| **`qwen2.5:3b`** (revised primary) | 2.2 GB | ~~100–140~~ | **~46** | ~~~450 ms~~ | **490 / 733 / 1044 ms** | Strong with the full §3.1+§3.2 prompt. Trimmed prompt breaks contract (leaks "new paragraph" tokens). Few-shots are load-bearing. |
| `gemma3:4b` | 3.1 GB | — | not tested (v2) | — | — | Deferred — "helpful rewriter" bias per community reports; would need re-calibration. |
| `llama3.2:3b` | 2.0 GB | — | not tested (v2) | — | — | Deferred — weak on negative-constraint instructions. |

**Where the time actually goes on `qwen2.5:7b`** (from `total_duration` = `load_duration` + `prompt_eval_duration` + `eval_duration`, warm resident, prefix cache hot from second call onward):

| Phase | First-ever call | Subsequent calls (prefix cache hit) |
|---|---|---|
| `load_duration` | ~85 ms | ~85 ms |
| `prompt_eval_duration` (855-tok system prompt) | **~3700 ms** (cold prefill) | **~55 ms** (Ollama's prompt-prefix cache reuses the KV state — this is the confirmed observed behavior on Ollama 0.x with `keep_alive:"30m"` and identical system messages) |
| `eval_duration` (~19 tok/s @ 7B, ~46 tok/s @ 3B) | ~50 ms/tok × N | ~50 ms/tok × N |

So on a warm-with-cache 7B, **generation dominates** — the 855-tok system prompt is essentially free on the second call. Trimming it to 178 tokens (see §11.2) saves ~250 ms *only on the first call after a cache miss* and 0 ms thereafter. Cache misses happen when: system prompt changes, per-call context (§5.2 style hint) changes, or Ollama evicts. That last one is the one that costs on 3B too — see §11.5.

**The 500 ms budget** in the brief holds for `qwen2.5:3b` on typical short dictations (18–25 output tokens); it does *not* hold on `qwen2.5:7b` at any output length beyond ~10 tokens. That is the empirical fact that forces the revision.

### 2.2 Recommendation (revised)

**Primary: `qwen2.5:3b`** — full §3 prompt including few-shots, dual-resident with Homunculus's `qwen2.5:7b`. Reasons:
1. **Measured 490 ms warm on the short case, 730 ms on the medium filler-heavy case, 1050 ms on a 60-tok run-on.** The typical (short/medium) band lands inside a 500–800 ms budget; run-ons are handled by the 1500 ms timeout in §4.
2. **Same instruction tuning family as the 7B** — Rune knows the failure modes; the prompt tested here has already been validated on the exact leading-"So" failure case Wren hit.
3. **Few-shots are load-bearing on the small model** — the trimmed prompt (rules only, no examples) broke the contract entirely on qwen2.5:3b, hallucinating "new paragraph" tokens into the output. The full prompt is safe *and* costs nothing extra after prefix-cache warmup (§11.2).
4. **RAM fits on the 16 GB M4** — `qwen2.5:7b` (4.7 GB) + `qwen2.5:3b` (2.2 GB) = 6.9 GB VRAM total, leaving ~9 GB for user working set. See §2.4 revised.

**Fallback (if user prefers single-resident to save RAM): `qwen2.5:7b` alone** — shared with Homunculus as originally planned. Accept 900–1500 ms typical, ~2.5 s run-on. Requires timeout ≥ 2500 ms and an on-screen "polishing…" indicator so the user isn't confused by the delay. Ships as a Settings-page option: *LLM cleanup speed: Fast (2 models resident, +2.2 GB RAM) / Balanced (share with Homunculus, slower)*.

**Not recommended: `qwen3:4b`.** In current Ollama, this is a *thinking* model — it emits chain-of-thought inside `<think>…</think>` before the visible answer. Setting `"think": false` in the request payload does not stop it from monologuing (the model was RLHF-trained to reason first, format second), and setting `num_predict=400` doesn't help — 400 is *not enough headroom* for reasoning + answer, so calls truncate with empty visible output. Every test call in §11.3 finished at 11–13 s with `done_reason: "length"`. This model is disqualified from any latency-bounded stage. Log for revisit only if Alibaba ships a `qwen3:4b-instruct` (non-reasoning) variant.

**Not tested in this revision: `gemma3:4b`, `llama3.2:3b`.** Deferred — the qwen2.5:3b result is strong enough that changing families would demand a full recalibration against the corpus in §6, which does not yet exist. Log as candidates for the v2 calibration pass once the owner has ≥ 30 corpus entries.

### 2.3 Not evaluated (deferred)

- **Fine-tuning our own cleanup model** — this is the *right* long-term answer (it's what Wispr did) but is out of v1 scope. Log as v2 roadmap: assemble the calibration corpus in §6, then LoRA-fine-tune `qwen2.5:7b` on it. Deliverable: a `qwen2.5:7b-cleanup` variant that ships with the app.
- **Cloud API fallback** — explicitly out. The clone is local-first; Ollama-unreachable falls back to raw ASR pass-through, not to a cloud call.

### 2.4 Resolving the resident-model collision with Homunculus — REVISED 2026-07-06

This is the single most important architectural decision in the spec, and the v1-draft resolution (share `qwen2.5:7b`) turned out to be wrong. Measured 7B cleanup latency (900–1500 ms typical, 2.5 s worst case) exceeds the product budget by 2–3×. A different model is required, which reopens the collision.

**The problem, restated.** Homunculus keeps `qwen2.5:7b` resident (per `Homunculus/brain/README.md` line 78). Cleanup needs `qwen2.5:3b` for latency. If Ollama swaps between the two on each context switch, every dictation between Homunculus calls pays a 1–2 s cold reload — product-killing.

**Three ways to resolve it — measured against the M4 Mac mini (16 GB) target machine:**

| Option | How | Latency cost | RAM cost | Trade-off |
|---|---|---|---|---|
| ~~A. Share `qwen2.5:7b`~~ (v1 recommendation, now superseded) | Both stages use the same model. | Zero swap. **But cleanup itself is 900–1500 ms.** | 4.7 GB (single resident) | Cleanup does not meet its own latency budget. |
| **B. Dual-resident: `qwen2.5:7b` (Homunculus) + `qwen2.5:3b` (cleanup)** — **NEW RECOMMENDATION** | Two models pinned, both hit by their respective stages, `OLLAMA_MAX_LOADED_MODELS=2`. | Zero swap. Cleanup 490–1050 ms (§11.2). | **6.9 GB VRAM** (4.7 + 2.2). Fits comfortably on 16 GB; leaves ~9 GB for user working set. | Cleanup and Homunculus are now weakly coupled: user has to commit 2.2 extra GB. |
| C. Two Ollama instances on different ports | Second Ollama process, different port. | Zero swap. | Same 6.9 GB, plus a second process footprint. | Doubles operational surface (two launchd units, two log paths). Rejected — Option B does it more cleanly. |

**Decision: Option B — dual-resident.** The extra 2.2 GB of resident VRAM on the owner's 16 GB machine is the price to buy back the latency budget the v1 draft assumed was free. Verified live: with both models resident I measured 4.7 GB + 2.2 GB = 6.9 GB VRAM per `ollama ps`, and every cleanup call in §11 hit the warm `qwen2.5:3b` with no eviction.

**Ollama config the user should set** (in `~/Library/LaunchAgents/homebrew.mxcl.ollama.plist` or via `launchctl setenv`):

```
OLLAMA_KEEP_ALIVE=30m
OLLAMA_MAX_LOADED_MODELS=2      # was 1 in v1 draft — REVISED
OLLAMA_NUM_PARALLEL=2
```

`OLLAMA_MAX_LOADED_MODELS=2` pins both `qwen2.5:7b` (Homunculus) and `qwen2.5:3b` (cleanup) simultaneously. `OLLAMA_NUM_PARALLEL=2` still allows concurrent slot handling within each model. If the user later upgrades Homunculus to a larger model, or wants to dedicate one model to cleanup fine-tuning (v2), this ceiling can rise on a 32 GB machine.

**RAM-constrained fallback (single-resident config for users on 8 GB Macs or heavy concurrent workloads):** share `qwen2.5:7b` with Homunculus as originally planned, accept 900–1500 ms cleanup, and raise the cleanup timeout to 2500 ms. This is the ~~Option A~~ path retained as an escape hatch. Ship as the *Balanced* preset in the Settings UI (§7).

**If the user later changes the Homunculus model** (e.g. upgrades to `qwen2.5:14b` on a 32 GB machine): the coupling loosens — cleanup can stay on `qwen2.5:3b` regardless. Noted in the app's Settings UI copy.

---

## 3. Prompt design

### 3.1 Full system prompt (v1 draft — to be calibrated against §6 corpus)

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
```

### 3.2 Few-shot examples (embedded in the prompt after the rules)

Six examples covering the hard cases. Order matters — put the paraphrase-resistance examples first so the model's attention is anchored to the forbidden behaviors.

```
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

Note on Example 5: the model may want to write "milk, bread, eggs, and dark-roast coffee from Ethiopia". That is exactly the forbidden behavior. The example is there to counteract it.

### 3.3 Sampling parameters

| Param | Value | Rationale |
|---|---|---|
| `temperature` | **0.1** | Deterministic. Cleanup has one right answer; randomness introduces paraphrase drift. |
| `top_p` | 0.9 | Standard. |
| `top_k` | 20 | Narrow. Cleanup vocabulary is not creative. |
| `repeat_penalty` | 1.05 | Just above neutral — the speaker may naturally repeat words ("very, very good") and we do not want the model to unrepeat them. |
| `num_predict` | `min(2 * input_tokens + 20, 400)` | Cleanup output length ≈ input length. Cap prevents runaway. |
| `stop` | `["\n\n\n"]` | Optional guard against multi-paragraph runaway. |

### 3.4 Plain text vs structured output

**Decision: plain text, no wrapper.**

Reasoning:
- Ollama's `format: json` / GBNF constrained decoding guarantees valid JSON. It does **not** guarantee correct content. Rune's persona rule: constrained decoding is validity, not correctness.
- The output *is* prose. Wrapping prose in `{"cleaned_text": "..."}` adds no verification value — the wrapper cannot detect paraphrase, tone shift, or content addition.
- JSON adds ~10–15 output tokens (open brace, key, quotes, close brace, escape handling) — a 10–20% latency tax for zero validation benefit.
- Escaping is a footgun: a dictation containing a double-quote or a newline will trip the model into producing malformed JSON, forcing a re-parse or fallback anyway.
- We can post-validate plain text cheaply on the Swift side: `output.trimmingCharacters(in: .whitespacesAndNewlines)`, reject if length > 3× input length (runaway), reject if empty. Fall back to raw ASR on rejection.

The one case for JSON would be if we wanted the model to *also* emit confidence or a "did-I-change-anything" flag. Neither is a reliable signal from a small model — reject as false structure.

---

## 4. API contract — Swift ⇄ Ollama

### 4.1 Endpoint choice: `/api/chat`

`/api/chat` over `/api/generate` because:
- Native support for system + user roles (our prompt has a strict system message).
- Cleaner for future few-shot expansion (assistant messages inline).
- Homunculus uses `/api/chat` already — one HTTP shape for the codebase to reason about.

### 4.2 Request shape

```json
POST http://localhost:11434/api/chat
Content-Type: application/json

{
  "model": "qwen2.5:3b",
  "stream": false,
  "keep_alive": "30m",
  "messages": [
    { "role": "system", "content": "<the §3.1 prompt + §3.2 few-shots>" },
    { "role": "user",   "content": "<raw ASR transcript>" }
  ],
  "options": {
    "temperature": 0.1,
    "top_p": 0.9,
    "top_k": 20,
    "repeat_penalty": 1.05,
    "num_predict": 400,
    "stop": ["\n\n\n"]
  }
}
```

Notes:
- `"model": "qwen2.5:3b"` — **REVISED 2026-07-06** (was `qwen2.5:7b`). See §2.2 revised and §11.2.
- `stream: false` — see §3.4 and §4.4.
- `keep_alive: "30m"` — matches Homunculus's `keep_alive`. Cleanup's `qwen2.5:3b` and Homunculus's `qwen2.5:7b` are both pinned via `OLLAMA_MAX_LOADED_MODELS=2` (§2.4 revised).
- No `format` field. Plain text out.

### 4.3 Response shape

```json
{
  "model": "qwen2.5:7b",
  "created_at": "2026-07-06T14:22:11.123Z",
  "message": { "role": "assistant", "content": "<cleaned text>" },
  "done": true,
  "total_duration": 342000000,
  "load_duration": 1200000,
  "prompt_eval_count": 512,
  "eval_count": 34,
  "eval_duration": 320000000
}
```

Swift side reads `message.content`, applies §4.5 validation, and pastes.

### 4.4 Non-streaming rationale

Pax's research: paste UX beats token drip. Reinforcing that:

1. **Pasting incrementally is not possible.** NSPasteboard + Cmd-V is atomic — you would have to type character-by-character via CGEvent, which is 10–50 ms per char and unreliable in Electron apps.
2. **Streaming's perceived-latency win is a text-showing-in-a-chat-UI win.** Our UI shows nothing until paste — there is no benefit to the user from earlier tokens.
3. **Streaming adds overhead** — HTTP chunked encoding, per-token JSON parsing on the Swift side, more error paths.
4. **Batch call reports final `total_duration` cleanly** — critical for the calibration harness in §6.

### 4.5 Timeout, error handling, and the sacred fallback rule

**The sacred rule: the stage MUST NEVER block the paste and MUST NEVER lose the user's words.**

If anything goes wrong, the raw ASR transcript is pasted as-is. This is the single most important behavior in the spec. A dictation app that eats a user's utterance because Ollama hiccupped is worse than useless — it destroys the user's trust in the fundamental act of dictating.

**Timeout budget (REVISED 2026-07-06):**

| Condition | Timeout | Action |
|---|---|---|
| Total wall-clock from request send to response received (`qwen2.5:3b` primary config) | **1500 ms** (was ~~800 ms~~ in v1) | Cancel request; paste raw ASR. |
| Total wall-clock — RAM-constrained fallback config (`qwen2.5:7b` shared with Homunculus) | **2500 ms** | Same behavior; timeout raised because the model is inherently slower. |
| Connection to `localhost:11434` refused / no route | Immediate | Paste raw ASR. Log `LLM_UNREACHABLE`. |
| HTTP 4xx (model not found, bad request) | Immediate | Paste raw ASR. Log details. Surface non-blocking notification to user *once per session* ("Cleanup model not available — check Ollama"). |
| HTTP 5xx (Ollama internal error) | Immediate | Paste raw ASR. Log. |
| Response received, `message.content` empty | Immediate | Paste raw ASR. Log `LLM_EMPTY_OUTPUT`. |
| Response received, `message.content.count > 3 * rawTranscript.count` | Immediate | Paste raw ASR. Log `LLM_RUNAWAY`. This is the over-rewrite guard. |
| Response received, `message.content` is empty string or only whitespace | Immediate | Paste raw ASR. |

**Why 1500 ms and not 800 ms (revised rationale):** measurement on the owner's M4 (§11) shows `qwen2.5:3b` warm typical latencies of 490–730 ms for short/medium utterances, but the 60-token run-on measured at 1044 ms warm. Setting the timeout at 800 ms would cut off legitimate run-on cleanups. 1500 ms gives ~40% headroom above the observed run-on worst case, and still exits well below the 2 s "user considers this stuck" threshold. The 500 ms *budget* remains the design target for typical cases — 1500 ms is the *bailout*, not the norm.

~~Why 800 ms and not 500 ms (v1 rationale, superseded):~~ *v1 assumed 150–350 ms typical on qwen2.5:7b. Measurement shows actual typical is 900–1500 ms on 7B and 490–730 ms on 3B. The 800 ms figure was calibrated to a fictitious latency floor.*

**Concurrency:** the Swift side must serialize cleanup calls — one in flight at a time. If a second dictation completes while the first is in flight, cancel the first, paste its raw ASR, and start the second. This preserves the "never lose words" guarantee.

### 4.6 Error taxonomy (log lines, JSONL, one per event)

```
{"ts": "...", "event": "cleanup_ok",              "raw_len": 42, "out_len": 39, "ms": 187}
{"ts": "...", "event": "cleanup_timeout",         "raw_len": 42, "ms": 800}
{"ts": "...", "event": "cleanup_unreachable",     "raw_len": 42}
{"ts": "...", "event": "cleanup_runaway_reject",  "raw_len": 42, "out_len": 200}
{"ts": "...", "event": "cleanup_empty_reject",    "raw_len": 42}
{"ts": "...", "event": "cleanup_bypass_shift",    "raw_len": 42}
{"ts": "...", "event": "cleanup_disabled_setting","raw_len": 42}
```

These lines are the basis of the calibration eval harness (§6). Log to `~/Library/Application Support/<AppName>/logs/cleanup.jsonl`.

---

## 5. Context features (design now; ship progressively)

### 5.1 Personal dictionary / vocabulary hints

**Data model:** a plain JSON file at `~/Library/Application Support/<AppName>/dictionary.json`.

```json
{
  "additions":   ["Kotlin", "Homunculus", "quadrabyte", "Tailscale"],
  "replacements": { "roon": "Rune", "wren wren": "Wren" }
}
```

**Injection into the prompt.** Additions go into a *dictionary-hint block* at the end of the system prompt, only when non-empty:

```
Additional vocabulary the speaker uses (preserve exact spelling if the transcript contains a phonetic match):
Kotlin, Homunculus, quadrabyte, Tailscale
```

Replacements are applied **on the Swift side, deterministically, after the LLM output** — never trust the model to do a string replace reliably. Regex with word boundaries, case-insensitive match, case-preserving replace.

**Population:** initially manual (Settings UI). v2 roadmap: auto-populate when the user manually edits pasted output — capture the edit, propose an addition.

### 5.2 Per-app formatting hints

The Swift side passes the focused app's bundle ID and a style enum. The style enum has four values:

| Style | When applied | Prompt injection |
|---|---|---|
| `prose` (default) | Mail, Notes, Word, Notion, Slack in a "channel description" field | (none — the default prompt is prose-oriented) |
| `casual` | Slack, iMessage, Discord, Messages, WhatsApp desktop | Add: "Style hint: casual chat — trailing period optional, contractions preferred." |
| `code` | Terminal, iTerm2, VS Code, Cursor, Xcode | Add: "Style hint: code context — do not add trailing period, preserve exact spacing and case, do not capitalize identifiers." |
| `email` | Mail.app compose window, Gmail in browser | Add: "Style hint: email body — full sentences, standard capitalization and punctuation." |

**Bundle-ID → style map** ships as a JSON file, user-editable, with sensible defaults. Unknown bundle → `prose`.

**How the Swift side signals it:** it inspects `NSWorkspace.shared.frontmostApplication?.bundleIdentifier` at the moment the hotkey is *released* (not pressed — the user may switch apps mid-dictation), looks up the style, and passes it in the API call as an *additional line prepended to the user message*, not as a separate parameter:

```
[style: code]
<raw ASR transcript>
```

This keeps the request shape uniform and lets the model see the style hint as part of the immediate context.

### 5.3 What we do NOT do in v1

- **Screen scraping / accessibility tree read** — Wispr does this to grok "what field am I in?". Out of scope for v1. Bundle-ID + style enum is enough.
- **Prior-utterance context** — no session memory. Every cleanup call is independent. (v2 candidate: pass the last 100 chars of prior text as context for pronoun resolution — but only if calibration shows it helps.)
- **Language dispatch** — v1 is English. Multi-language is a v2 concern; will require per-language prompt variants.

---

## 6. Calibration plan

This is Rune's calibration-loop discipline applied to cleanup. **This section is not optional.** A stock instruct model with a well-written prompt gets you 80% there. The last 20% comes from reading your own failures against your own dictations and adjusting the prompt.

### 6.1 The corpus

**Owner deliverable (the one thing on the owner's calibration to-do list):** assemble **at least 30 real dictations**. For each:

1. A recording of the owner speaking (or the raw ASR transcript, if audio recording is inconvenient).
2. The hand-corrected target output — what the owner would have typed.

**Corpus coverage** — the 30 must include at least three examples of each category:

| Category | Description | Why hard |
|---|---|---|
| **Simple** | Clean single sentence, minimal fillers | Baseline — should be near-perfect |
| **Filler-heavy** | Many "um/uh/like/you know" tokens | Model may leave some; may remove non-fillers |
| **Self-correction** | "scratch that", "no wait", "actually" | Model may transcribe the command instead of executing it |
| **Dictated punctuation** | "comma", "period", "open quote" | Model may write the word "comma" instead of `,` |
| **Technical vocabulary** | Code, file paths, product names, acronyms | Model may capitalize, add punctuation inside identifiers |
| **Run-on / rambling** | Multi-clause, no natural breaks | Model may summarize or reorganize |
| **Numbers / dates / times** | Various formats | Model may over- or under-format |

Store the corpus at `~/Library/Application Support/<AppName>/calibration/corpus.jsonl`:

```jsonl
{"id": "c001", "category": "filler_heavy", "raw": "um so I was thinking...", "target": "I was thinking..."}
{"id": "c002", "category": "self_correction", "raw": "meet Tuesday no wait Wednesday", "target": "Meet Wednesday."}
```

### 6.2 Red / green eval harness (sketch)

A Swift or Python script that:
1. Reads `corpus.jsonl`.
2. For each entry: sends `raw` to the cleanup stage via the real API contract (§4).
3. Compares the model output to `target` using:
   - **Green (exact)** — normalized-whitespace equality.
   - **Green (near)** — Levenshtein ratio ≥ 0.95.
   - **Yellow (drift)** — Levenshtein ratio 0.80–0.95. Human review.
   - **Red (over-rewrite)** — Levenshtein ratio < 0.80 **OR** output length < 60% of target length (summarization) **OR** output length > 140% of target length (invention).
4. Emits an HTML report grouping failures by category, with the diff between `model_output` and `target` inline.

### 6.3 The "over-rewrite" failure mode — the one to watch

Rune's persona view: over-rewriting is the trust-fracturing failure. The eval harness explicitly flags it as **Red** whenever any of:

- Output tokens include a word not present in the input token stream *and* not in the "allowed insertions" list (punctuation marks, "the/a/an" only when merging clauses, capitalization variants).
- Output token count is < 60% of target token count for non-filler-only inputs (summarization).
- A proper noun in the input is misspelled, missing, or replaced in the output.
- A dictated profanity is absent from the output.

Every Red must be fixed before shipping. Fixes cascade in priority:
1. **Prompt adjustment** — add a firmer negative example.
2. **Few-shot addition** — a new §3.2 example matching the failure category.
3. **Prompt restructure** — reorder rules, elevate the violated rule.
4. **Model swap** — if the primary model keeps failing a category the fallback handles, escalate to v2 fine-tune conversation.

### 6.4 Calibration cadence

- **Pre-v1-ship:** all 30 corpus entries must be **Green** or **Green (near)**. No Reds, no Yellows.
- **Post-ship:** the app logs every cleanup call to `cleanup.jsonl` (§4.6). Owner reviews weekly (or when a paste looks wrong, right-click the Flow bar → "Report this cleanup" — appends to corpus with a `needs_target` flag).
- **Corpus growth:** target 100 entries by month 2. Re-run harness on every model or prompt change. Corpus + harness are the release gate.

---

## 7. Toggleability

### 7.1 Global on/off

Settings UI toggle: **"Clean up dictation with Ollama"**. Default: **on**. When off, raw ASR pastes directly. State persists in `NSUserDefaults`.

Rationale for the default: the target user (this owner) is building this because they want the Wispr-Flow-style polish. But Pax noted VoiceInk users often keep AI enhancement off — so the toggle must be prominent and one-click, not buried three settings deep.

### 7.2 Per-invocation bypass

**Modifier during hotkey release: hold Shift.** If the user releases the hotkey while Shift is held, the cleanup stage is skipped and raw ASR is pasted. Logged as `cleanup_bypass_shift`.

Rationale: the user is dictating a code snippet, a password, an acronym-heavy passage — anything where the cleanup stage is likely to over-format. One-key escape valve, no menu, no dialog.

### 7.3 Auto-skip on Ollama unavailable

If the last 3 calls to `/api/chat` failed with connection refused, skip the LLM stage for the next **60 seconds** and paste raw ASR directly (do not even attempt the call — saves the 800 ms wait). Retry after 60 s. This prevents a stuck Ollama daemon from making every dictation feel 800 ms slow.

Surfaced in the Flow bar with a subtle indicator dot (amber → cleanup unavailable) so the user knows why polish stopped happening.

### 7.4 Per-app disable (v1.1)

Log for v1.1: some apps (Xcode, Terminal) may benefit from a hard "cleanup off" rule instead of the "code style" hint. Ship the bundle-ID list mechanism in v1 but expose the disable-per-app UI in v1.1.

---

## 8. Deferred / v2 roadmap

| Item | Rationale to defer |
|---|---|
| Fine-tune `qwen2.5:7b` on the calibration corpus | v2 — needs 300+ corpus entries and a training pipeline. Right long-term answer. |
| Two Ollama instances (cleanup + Homunculus on different ports) | v2 — only if user upgrades to 32+ GB and wants a smaller cleanup model. |
| Prior-utterance context for pronoun resolution | v2 — only if calibration shows it helps. |
| Multi-language cleanup | v2 — requires per-language prompt variants and per-language corpora. |
| Auto-populate personal dictionary from user edits | v2 — needs edit-tracking infrastructure. |
| Screen-context reading for finer-grained per-app style | v2 — accessibility tree read; complex. |
| Streaming with in-place text update | Rejected. Batch + paste is architecturally correct for this UX. |
| JSON structured output | Rejected. Structure adds no correctness for prose. |
| Cloud fallback | Rejected. Local-first is the product. |

---

## 9. Contract with Wren's implementation plan

This spec is authoritative for:
- The Ollama request/response shape (§4).
- The system prompt content (§3.1) and sampling parameters (§3.3).
- The fallback / timeout / error behavior (§4.5).
- The toggleability behaviors (§7).

Wren's plan owns:
- Where in the VoiceInk fork the cleanup call is invoked (post-ASR, pre-paste).
- The Swift `httpx`-equivalent (URLSession) code that makes the call.
- The Settings UI wiring.
- The bundle-ID → style map file location and format enforcement.
- The `NSPasteboard` transient-type marker and clipboard restore timing.
- The Shift-key detection on hotkey release.
- The dictionary editor UI.

**Coordination point:** Wren and Rune sync on the `cleanup_result` type crossing the ASR → paste boundary. Draft signature:

```swift
struct CleanupResult {
  let text: String            // what to paste
  let source: Source          // .llm | .rawFallback | .userBypass
  let latencyMs: Int
  let logEvent: String        // one of §4.6 event names
}
```

Any change to that shape requires a Rune review (same protocol discipline as Homunculus's `PROTOCOL.md`).

---

## 10. Open questions for the owner

1. **Do you want the Shift-to-bypass modifier, or a different key?** Some users chord Shift naturally when releasing keys.
2. **What's the ceiling on RAM you're comfortable dedicating to Ollama on the dictation machine?** Post-revision (§2.4) the primary config uses 6.9 GB VRAM. If you want to reserve more RAM for other work, we ship the *Balanced* preset (single-resident 7B, slower cleanup) — confirm which you prefer.
3. **Are you willing to keep a corpus growing?** The whole quality story rests on the answer being yes. If no, we downgrade expectations and ship with the v1 draft prompt only.

---

## 11. Measured performance (2026-07-06)

Rune measured actual cleanup latency on the owner's target machine to reconcile the v1-draft estimates with reality. Wren surfaced the mismatch when her M4 validation showed 904 ms on an 18-token utterance and 1570 ms on a 31-token filler-heavy input against a spec that predicted 150–350 ms and set an 800 ms timeout. This section documents what the numbers actually are, where the time goes, and what changed in the recommendation.

### 11.1 Test environment

| Property | Value |
|---|---|
| Machine | Apple Mac mini (Mac16,10) — M4, 16 GB unified memory |
| Ollama version | server responding on `localhost:11434` (concurrent Homunculus resident) |
| Models tested | `qwen2.5:7b` (Q4_K_M, 4.7 GB), `qwen3:4b` (Q4_K_M, 3.2 GB), `qwen2.5:3b` (Q4_K_M, 2.2 GB) |
| Sampling parameters | Exactly §3.3: `temperature 0.1, top_p 0.9, top_k 20, repeat_penalty 1.05, num_predict 400, stop ["\n\n\n"]` |
| Request shape | `POST /api/chat, stream:false, keep_alive:"30m"` (§4.2) |
| Prompt variants | **full** (§3.1 rules + §3.2 six few-shots, ~855 tokens), **trimmed** (rules only, ~180 tokens), **minimal** (~75 tokens, one-sentence contract) |
| Test utterances | 18-tok short (Wren's short case), 31-tok medium filler-heavy (Wren's failure case), 60-tok run-on, 35-tok technical with dictated punctuation, 20-tok self-correction |
| Warmup discipline | One throwaway call per model before measurement; then 2–3 repeats per (model × prompt × utterance) to observe prefix-cache behavior |

### 11.2 The core latency table (warm resident, prefix cache hot)

All values are the median of 2–3 warm repeats. `total_ms` = `load_ms` + `prompt_ms` + `eval_ms`; the small residual is Ollama internals.

**`qwen2.5:7b` — full §3 prompt (855 system tokens)**

| Utterance | Output tok | `prompt_ms` (warm/cached) | `eval_ms` | **Wall total** |
|---|---|---|---|---|
| short_18tok | 18 | 55 | 900 | **~1010 ms** |
| medium_filler_31tok | 25 | 55 | 1340 | **~1500 ms** |
| run_on_60tok | 46 | 55 | 2420 | **~2560 ms** |
| technical_35tok | 21 | 55 | 1015 | **~1155 ms** |
| self_correct_20tok | 14 | 55 | 660 | **~790 ms** |

Reproduces Wren's 904 ms / 1570 ms directly (short + medium filler cases). **Where the 904 ms goes on 7B: ~85 ms overhead + ~55 ms prompt-eval-cached + ~760 ms generation @ ~19 tok/s.** Generation dominates — the long system prompt is essentially free on repeat calls.

**`qwen2.5:3b` — full §3 prompt (855 system tokens)** — new primary

| Utterance | Output tok | `prompt_ms` (warm/cached) | `eval_ms` | **Wall total** |
|---|---|---|---|---|
| short_18tok | 18 | 24 | 385 | **~490 ms** |
| medium_filler_31tok | 29 | 23 | 636 | **~730 ms** |
| run_on_60tok | 43 | 23 | 943 | **~1050 ms** |
| technical_35tok | 21 | 23 | 470 | **~560 ms** |
| self_correct_20tok | 14 | 23 | 287 | **~395 ms** |

**Where the time goes on 3B:** ~85 ms overhead + ~23 ms prompt-eval-cached + generation @ ~46 tok/s. Roughly 2× faster generation than 7B for the same quality on our task.

**Prompt-size sweep on `qwen2.5:7b`** (does trimming the prompt save latency? — the surprise finding)

| System-prompt size | short_18tok wall | medium_filler wall | Notes |
|---|---|---|---|
| **full** (855 tok) | 1010 ms | 1500 ms | Baseline. |
| trimmed (178 tok) | 1120 ms | 1590 ms | Same-order, sometimes slower. |
| minimal (73 tok) | 1150 ms | 2400 ms | Slower — model rambles without few-shots. |

**Conclusion: trimming the prompt does not save meaningful time**, because (a) Ollama's prompt-prefix cache reduces the system-prompt evaluation to ~55 ms after the first call regardless of size, and (b) removing the few-shots *increases* the model's output length as it invents its own filler removals, spending more time in generation than the prompt cost saved. This is the "calibration over intuition" lesson applied to the spec itself: shortening the system prompt sounds like an obvious win and empirically is not.

### 11.3 Why `qwen3:4b` is disqualified

`qwen3:4b` in current Ollama is a *reasoning* model. It emits a `<think>…</think>` chain-of-thought block before the visible answer. Even with the Ollama `think:false` request flag set:

- Every test call finished at 11–13 s with `done_reason: "length"`, saturating `num_predict=400` with reasoning tokens.
- On a small `num_predict=100` sanity check the model returned an internal monologue as the visible answer (`"Hmm, the user just said..."`), never producing the cleaned text.
- Raw eval rate is impressive (~36 tok/s vs 7B's 19), but this doesn't matter when the model can't be persuaded to output the answer directly.

**Disqualified for any latency-bounded stage.** Revisit only if Alibaba ships an `instruct` (non-reasoning) variant. `qwen2.5:3b` is the correct small-model choice here — it uses the older instruct-tuned recipe that outputs answers directly.

### 11.4 Prompt/model quality check on Wren's failure case

Wren reported the leading-"So" filler surviving the cleanup on `qwen2.5:7b` (i.e. `"so I was thinking..."` → `"So I was thinking..."`). Reproduction and cross-check:

| Model | Prompt | Runs stripping leading "So" | Median wall | Sample output |
|---|---|---|---|---|
| `qwen2.5:7b` | full | **3/3** | 1015 ms | `"I was thinking maybe we could get together on Thursday."` |
| `qwen2.5:7b` | trimmed | 3/3 | 914 ms | `"I was thinking maybe we could get together on Thursday."` |
| `qwen2.5:3b` | full | **3/3** | 451 ms | `"I was thinking maybe we could get together on Thursday."` |
| `qwen2.5:3b` | trimmed | 3/3 (but corrupted output) | 263 ms | `"new paragraphThursday new paragraph"` — trimmed prompt breaks the contract on 3B. |

Two takeaways:
1. **`qwen2.5:3b` with the full prompt strips the leading "So" reliably** on this input across three runs. The contract holds. Wren's original 7B-with-full-prompt run stripping it too, on my rerun — her one observed miss may have been a stochastic slip. Either way the 3B on this test set is at least as good on the leading-So contract as the 7B.
2. **The trimmed prompt is unusable on 3B.** Few-shots are load-bearing. Any future prompt-shrinking must be validated against the full corpus (§6), not eyeballed.

### 11.5 Homunculus dual-resident RAM verification

Verified live via `curl http://localhost:11434/api/ps`:

| Model | VRAM in use |
|---|---|
| `qwen2.5:7b` | 4.74 GB |
| `qwen2.5:3b` | 2.16 GB |
| **Sum (dual-resident target)** | **6.90 GB** |

On the 16 GB M4, this leaves ~9 GB for the user's working set (browser tabs, VoiceInk, IDE, Homunculus's Python process, etc.). Comfortable — no swap pressure observed while running the measurements above with all three models resident. The v1-draft §2.4 assumption that "one resident = fatal to swap, share the model" was correct in principle but wrong in practice — the M4 has enough headroom to hold two.

### 11.6 Reasoning for the revision, in one paragraph

The v1-draft numbers overestimated qwen2.5:7b's tok/s by ~3× (55–75 tok/s cited vs 19 tok/s measured) — the Ollama MLX blog and llmcheck.net numbers I cited were for shorter or differently-benchmarked runs, and I did not calibrate against the owner's actual machine before committing to the estimate. Wren's calibration surfaced the miss. Empirically, `qwen2.5:3b` runs cleanup ~2× faster with equal-or-better contract adherence *when the full few-shot prompt is retained* (which costs nothing at inference because prefix cache reuses it). The only real cost of the switch is 2.2 GB of resident VRAM, which the 16 GB M4 can absorb. `qwen3:4b` cannot be used at all in current Ollama for latency-bounded work because it's a reasoning model. The timeout rises from 800 ms to 1500 ms to accommodate the observed 60-tok run-on worst case (~1050 ms) plus ~40% headroom.

### 11.7 What Wren must change in her VoiceInk fork configuration

1. **Model string:** change from `qwen2.5:7b` → **`qwen2.5:3b`** in the Ollama request body.
2. **Timeout:** change from 800 ms → **1500 ms**.
3. **Ollama env:** ensure `OLLAMA_MAX_LOADED_MODELS=2` (was `1` in the v1 draft) so both her cleanup 3B and Homunculus's 7B stay resident.
4. **Keep the full §3 prompt.** Do not trim it in an effort to save time — measurement shows trimming does not save time and can break the contract on the 3B.
5. **Settings-page presets:** ship both *Fast* (dual-resident 3B, 1500 ms timeout — default) and *Balanced* (single-resident 7B, 2500 ms timeout — for RAM-constrained users). See §2.4 revised and §4.5 revised.

---

*End of spec v1 (revised 2026-07-06). Next revision after §6.1 corpus lands and calibration pass runs.*
