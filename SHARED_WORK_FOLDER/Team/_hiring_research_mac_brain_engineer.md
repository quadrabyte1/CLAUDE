# Research Report: Mac-Side Voice-Assistant Backend Engineer (Homunculus brain owner)

**Prepared by:** Pax (Senior Researcher)
**Date:** 2026-06-08
**Purpose:** Persona creation by Nolan (HR Director) for the Homunculus project's Mac-side brain owner.

---

## TL;DR for Nolan

- **Recommended title:** **Local-LLM Voice Assistant Backend Engineer** (industry-aligned working title: "Voice AI Backend Engineer, local-first"). This title is more accurate than "AI infrastructure engineer" (too platformy) or "Python backend engineer" (loses the LLM and voice context).
- **Most important differentiator:** They are a **prompt + schema + deterministic-math triad designer**, not a generic Python backend engineer. They design the Swift/Pydantic type *first*, the constrained-decoding prompt *second*, and do all time/date math in Python because **the LLM is for words, not for arithmetic.** They calibrate against an on-device 7B/14B-class model — far below frontier — and design every component to fail gracefully when the model is wrong.
- **Recommended model tier:** **opus**. The role's hardest work is judgment, not throughput: prompt/schema design, calibrating a small local model to an older user's speech patterns, holding portability discipline against Mac-only temptations, and owning the reminder-reliability contract end-to-end. The day-to-day Python implementation is routine; the design calls that bound the system to its locked v1.0 spec are not.

---

## 1. The Real-World Role

This person sits in a niche that has crystallized over 2024–2026: **the local/private voice assistant backend engineer.** It is *not* the same as either of these adjacent roles:

| Role | Differs from this one by |
|------|-----|
| Generic Python backend engineer | Has never had to design a JSON schema that an on-device 7B model can actually fill correctly, has never debugged timezone bugs that surface only on DST weekends, has never written a heuristic fallback for when their LLM is unreachable. |
| Voice AI Engineer (Feather, LiveKit, Cartesia roles) | Lives in the **cloud-first** voice stack — Whisper/Deepgram STT, OpenAI/Anthropic LLMs, ElevenLabs/Cartesia TTS, LiveKit transport. Optimizes for low-latency streaming at scale. They have *not* solved for offline operation, model-size-limited intent extraction, or "the entire stack must run on one Mac mini." |
| MLOps / AI Infrastructure | Owns model training, fine-tuning, deployment pipelines, GPU fleets. Our role does *zero* training and exactly one inference deployment (Ollama on a Mac). |

**Real-world titles you'll see used interchangeably for this niche:**
- "Voice AI Backend Engineer (local-first)" — used by privacy-focused startups (Mycroft alumni network, MaiAI, OllamaShack-style consultancies).
- "Local LLM Systems Engineer" — used by self-hosted enterprise voice projects.
- "Edge AI Application Engineer" — used by hardware-adjacent shops (Rabbit, Humane post-mortem hires, Frame glasses, etc.).
- "AI Application Engineer (Privacy / On-Device)" — common at health-tech and elder-care shops.

For Homunculus, "Local-LLM Voice Assistant Backend Engineer" is the most accurate and most legible.

---

## 2. What This Person Actually Does, Day to Day

The work splits into seven concrete activity buckets.

### 2.1. Prompt + Schema Co-Design (the highest-leverage work)

The Homunculus brain already exemplifies the canonical pattern:

```python
PARSED_INTENT_JSON_SCHEMA = { ... }  # Pydantic-derived JSON schema
payload = {
    "model": "qwen2.5:14b",
    "messages": [system_prompt, user_utterance],
    "format": PARSED_INTENT_JSON_SCHEMA,  # constrained decoding
    "options": {"temperature": 0.1},
}
```

The schema is *the contract* — the model is forced into valid JSON via grammar-constrained decoding (GBNF in llama.cpp, which Ollama exposes via the `format` field since v0.5). The engineer's daily work is:

- **Schema design:** What fields does the model need to emit? Where do you split "title" from "people"? Where do you add `ambiguous_fields` so the system can ask clarifying questions instead of guessing? **Designing `ambiguous_fields` as a first-class output is the single most important schema decision in a memory-support product** — it's what lets the brain say "did you mean Tuesday or Thursday?" rather than silently picking one.
- **Prompt iteration:** Even with grammar-constrained decoding, the *content* of the JSON is hallucinatable. The prompt has to push the model toward the right values. Best practice (well-documented across Ollama, Qwen, llama.cpp communities in 2026): include a JSON example in the system prompt, instruct it to emit JSON explicitly, keep temperature ≤ 0.2, and never let the model do math.
- **Calibration cycle:** Run a corpus of real utterances ("can we meet Thursday at 10?", "remember this prompt about deck framing", "what do I have tomorrow?") through the model, log failure modes, adjust schema or prompt, repeat. This is iterative empirical work — not theoretical.

### 2.2. Local LLM Operations

- **Model selection:** Which Ollama model fits? On a 16 GB M4 Mac mini, `qwen2.5:7b` is the sweet spot; on 32 GB+, `qwen2.5:14b`; `llama3.1:8b` and `mistral:7b` are common alternates. The engineer benchmarks intent-extraction accuracy on each, not generic benchmarks.
- **Ollama serving discipline:** Set timeouts (the current code uses 30s — appropriate). Handle `LLMUnreachable` cleanly. Keep one model loaded resident — switching models on each call is fatal to latency.
- **Heuristic fallback:** Already implemented in `llm.py`. Critical for offline / tests / dev. The engineer maintains it as the model rotates, because regex catches what the LLM misses on edge cases.
- **Portability watch:** **Do not adopt MLX directly.** Ollama uses MLX under the hood on Apple Silicon since v0.19 — that's fine, because the abstraction is at the Ollama API boundary. The engineer's code talks HTTP to `localhost:11434` and that's identical on a Linux box with `vllm serve` swapped in (vLLM supports an OpenAI-compatible endpoint that can be reverse-proxied to look like Ollama, or the brain can grow a thin backend-selector). This is the right design and it must be defended against MLX-direct shortcuts.

### 2.3. FastAPI Server Reliability

The brain is a long-running daemon on a Mac mini that the user expects to be up. Engineer responsibilities:

- **Async discipline:** Every endpoint is `async def`; every blocking I/O call (httpx, filesystem) uses the async variant or runs in a threadpool. Pydantic v2 is fast but a hot path can blow up if you `response_model`-validate twice — engineer knows this footgun.
- **Process supervision:** `launchd` (Mac) or `systemd` (Linux future) so the brain restarts on crash and boots with the machine. Single binary entrypoint (`homunculus-brain` defined in pyproject.toml).
- **Logging:** Structured-enough for the activity-log feature that's not built yet. JSON lines preferred — easy to render in a dev viewer.
- **Health endpoint:** `/health` already exists. Engineer extends it with model-reachable check (a 1-token Ollama ping with cache).

### 2.4. Markdown-as-Database Design

The user has chosen markdown over SQLite. This is unusual and deliberate: hand-editing a file changes the brain's view immediately, no schema migrations, the whole vault is greppable, the whole vault is git-versionable. The engineer's job here is:

- **File layout discipline:** `vault/calendar/<event-id>.md`, `vault/notes/`, `vault/inbox.md`, `vault/_reminders/<event-id>.json`. Underscored directories for system-managed content; clean directories for the user's prose.
- **Frontmatter as the index:** Each event file has YAML frontmatter (`starts_at`, `tz`, `id`, etc.). Engineer treats frontmatter parsing as the hot path — caching keyed by mtime would be a v1.1 optimization.
- **Concurrency:** Two captures landing in the same millisecond cannot corrupt `inbox.md`. The engineer either serializes writes through an `asyncio.Lock` or uses atomic write-rename. Already implemented; engineer keeps it that way.
- **No DB.** When tempted by SQLite for "just the activity log", the engineer writes JSONL.

### 2.5. Time and Timezone Correctness

**This is the #1 bug source in calendar systems and the engineer owns every related bug.** The brain already has `date_resolver.py` with the right primitives:

- Store UTC + IANA zone identifier, never offsets.
- Resolve relative expressions ("Tuesday", "tomorrow morning") deterministically in Python from a configurable morning anchor — not in the prompt.
- Use `zoneinfo` (Python 3.9+) rather than `pytz`.
- Treat DST weekend tests as RC blockers.
- Phone tells server its timezone with each capture (the schema has `speaker_tz`) — server respects it.

The engineer is the person who knows that `datetime.now()` is a footgun, that "next Tuesday" means different things in different cultures, and that the morning summary at 7:00 AM has to fire at 7:00 *local* even after a Caribbean trip.

### 2.6. Tailscale Transport + iOS Push Protocol

The brain pushes a reminder schedule to the phone over the tailnet. Engineer responsibilities:

- **Protocol design (their work):** Define the HTTPS POST contract that Kit implements. Today it's `push_to_phone()` as a logging stub. Engineer designs the real shape: an idempotent POST to the phone's tailnet IP carrying the next 72h of reminder rows; phone registers each as a `UNCalendarNotificationTrigger`. Idempotency keys are `ev.<uuid>.strike.<n>` — already defined in Mori's spec.
- **No APNs in v1.** Local notifications fire from a terminated app via the iOS scheduler. The brain doesn't need an APNs JWT, push certificates, or a third-party push service. That's a v1.0 design choice the engineer must protect against scope creep.
- **Tailscale ops discipline:** The brain binds `0.0.0.0:8765` and trusts the tailnet for auth. Engineer is alert to the day the user wants to expose this on a coffee-shop network — that day, the bearer-token middleware lands.
- **Engineer does not write Swift.** But they review Kit's notification handler PRs for protocol fidelity (the OK-tap must DELETE all remaining strikes on the brain side, etc.).

### 2.7. Escalating-Strike Reminder Logic

The schedule generator in `reminders.py` is the engineer's signature work. It is calmly stated but operationally critical:

- T-30 heads-up, T-5 pre, then strikes at T+0, T+5, T+10, T+15. Stop at four.
- Morning summary once per day, fires at user-configured time, includes today's events + yesterday's missed.
- Schedules are persisted as JSON sidecars in `vault/_reminders/` — the engineer can hand-edit one if they need to.
- "Undo within 5 minutes" (post-v1) hooks into this loop by cancelling the unfired tail before the phone fires it.

The engineer carries the entire reliability contract: morning summary → T-30 → T-5 → four strikes → missed log → next-morning reschedule offer. **A break in this chain breaks the product's trust contract** for an older user whose memory is failing.

---

## 3. Required Expertise (specific, not generic)

### Local LLM Serving (Ollama / llama.cpp / vLLM / MLX)
- **Ollama** as the day-one runtime — its `format` field accepts a JSON schema and uses GBNF under the hood to constrain decoding. Knows the v0.5+ structured output story cold.
- **llama.cpp** awareness — Ollama is a wrapper. When debugging weird repetition loops in constrained generation, the engineer knows to check the underlying llama.cpp issue tracker.
- **vLLM** as the Linux-future serving path. Knows vLLM's OpenAI-compatible endpoint, PagedAttention, continuous batching. Hits ~16-20x Ollama's concurrent throughput on NVIDIA — relevant when the user does migrate.
- **MLX** as the abstraction underneath Ollama on Apple Silicon since v0.19. Does *not* import MLX directly — that would defeat portability.
- **Model selection literacy:** Qwen2.5 family for general intent (good schema-following), Llama 3.1 8B as alternate, knows when a 7B model isn't going to cut it and gracefully escalates to clarifying question rather than silently failing.
- **Grammar-constrained decoding (GBNF)** at the conceptual level — knows that constraining structure doesn't guarantee accuracy, only validity. That's why the heuristic fallback and `ambiguous_fields` matter.

### Python Async Ecosystem
- **FastAPI** + **uvicorn** with `uvloop` and `httptools`. Knows to avoid `response_model` on hot paths to skip double-validation.
- **httpx** async client, with proper timeout, connection pooling, retry-with-backoff for the Ollama call.
- **pydantic v2** — Rust core, fast, but pathological on heavy nesting. Engineer keeps schemas flat where possible. `model_validate`, `model_dump(mode="json")`, `Field(default_factory=...)` are routine.
- **asyncio** primitives — `Lock`, `Semaphore`, `gather`, `TaskGroup` (Python 3.11+). Knows when to use a threadpool (sync filesystem calls in hot loops).
- **`zoneinfo`** (stdlib), not `pytz`.
- **pytest** with `tmp_path` for hermetic tests — already the pattern in the brain.

### Voice Pipeline Design (Server Side)
- STT happens **on the phone** (Kit's job, via iOS 26 `SpeechAnalyzer` / `SpeechTranscriber`). The server receives **text**, not audio. This is a major design simplification.
- TTS in v1 is **a string** the phone speaks via `AVSpeechSynthesizer`. The brain returns `spoken_reply: str` in the `CaptureResponse`. No audio streaming, no WebRTC, no LiveKit.
- The engineer thinks about TTS *content* — the phrasing of the spoken reply, the readback before write, the clarifying question form. "You're clear Thursday June 11 at 10:00 AM" is better than "no conflict found" for an older user.
- **Older-user ergonomics in protocol design:** the brain may need to send simple chunked replies the phone can speak with natural pauses; the brain should never emit dates as raw ISO 8601 in `spoken_reply`. These are engineer choices.

### Time / Timezone Correctness (their #1 bug source)
- UTC + IANA zone always. Never offsets.
- `zoneinfo.ZoneInfo("America/New_York")`, not `timezone(timedelta(hours=-5))`.
- DST transitions tested every release.
- Server's default TZ is configurable (`HOMUNCULUS_TZ`); the phone's TZ overrides per request (`speaker_tz`).
- "Tomorrow morning" resolves through the morning-anchor hour, configurable, defaults to 9.

### Cross-Platform Discipline
- **Hard rules they enforce:**
  - No `MLX` direct imports.
  - No `Keychain` (`security` framework). Secrets are env vars; if encryption is needed, use stdlib `cryptography` or `age` files.
  - No `FSEvents` direct. Use `watchdog` (cross-platform) if filesystem watching becomes necessary.
  - No `SwiftNIO`, no `Network.framework`. FastAPI/uvicorn for transport.
  - No `launchd`-only assumptions. Provide a `systemd` unit file alongside the launchd plist.
- **What they do allow:** anything pip-installable that runs on macOS *and* Linux. `httpx`, `pydantic`, `fastapi`, `uvicorn`, `pyyaml`, `python-frontmatter`, `tzdata` (for Windows future).

### iOS Push Protocol Design (without writing Swift)
- They design the HTTPS contract Kit implements.
- They know `UNUserNotificationCenter`'s constraints: 64-pending ceiling, `UNCalendarNotificationTrigger` always (never `TimeInterval`), `.timeSensitive` on strikes 0–3, single "OK" action, deterministic IDs.
- They understand that local notifications fire from a terminated app — no APNs needed for the core loop. That's why the brain pushes a schedule, not individual notifications.
- They know enough about iOS reconciliation (phone-off-at-fire-time, OS-update notification clears, TZ changes) to design the brain side that supports it: on every phone re-check-in, the brain hands over the current schedule and the phone reconciles.

---

## 4. What Separates This Person From A Generic Backend Engineer

Five differentiators, in order of importance.

1. **They design Swift/Pydantic types first, prompts second.** A generic backend engineer writes a prompt and parses whatever comes back. This engineer designs the type that captures the *intent shape* — including the meta-field (`ambiguous_fields`) that drives the clarifying-question UX — and only then writes the prompt that fills it. Schema is contract.

2. **They calibrate against a small local model, not a frontier model.** Cloud-LLM engineers can lean on GPT-4o / Claude Opus to mask bad prompts. This engineer's model is a 7B/14B with limited reasoning. They have to make the schema unambiguous enough that even a small model can fill it correctly. This is a *different skill* than prompt engineering for frontier models — it's closer to compiler design than to creative writing.

3. **Deterministic math lives outside the prompt.** They never ask the LLM "what date is next Tuesday" — that's a Python function. They never ask the LLM "is 2:30 PM in the morning or afternoon" — that's a regex. The LLM is for extracting *words*; arithmetic lives in code that can be unit-tested. This discipline separates working systems from demo-grade ones.

4. **They hold portability against expedient shortcuts.** When a Mac-only API would save two days of work, they say no — because the boss's stated goal is "migrate to Linux/NVIDIA later with zero code changes." They write a `systemd` unit file alongside the `launchd` plist on day one, and they make sure no env var name implies "mac". This is a Larry-aligned discipline.

5. **Ergonomics for an older user is a product principle, not a polish step.** The brain's spoken replies, clarifying questions, and confirmation prompts are designed to be heard by someone whose memory is failing. "You're clear Thursday June 11 at 10:00 AM" beats "No conflict." "Did you mean this Tuesday or next Tuesday?" beats silent guessing. This sensibility shapes the schema (`spoken_reply`, `clarifying_question`, `ambiguous_fields`) and the prompt.

---

## 5. Daily Workflow With Kit

| Activity | Mac-brain engineer (this hire) | Kit (iOS, existing) |
|---|---|---|
| Voice capture (mic, STT) | Reviews protocol, doesn't implement | Owns — iOS 26 `SpeechAnalyzer` |
| Network call to brain | Defines `/capture/text` contract | Implements URLSession async call over Tailscale |
| Intent parse + schema | **Owns** — designs schema, prompt, calibrates model | Consumes `CaptureResponse` |
| Date/time resolution | **Owns** — `date_resolver.py` | Trusts brain's resolved datetime |
| Vault writes (events, notes) | **Owns** — markdown files, atomic writes | Doesn't touch — phone is stateless |
| Reminder schedule generation | **Owns** — strike plan, morning summary | Trusts the schedule the brain hands him |
| Reminder fire on device | Designs the push protocol | Owns — `UNCalendarNotificationTrigger`, ack handler |
| Spoken reply / TTS | Owns the *content* (string in response) | Owns the playback — `AVSpeechSynthesizer` |
| "OK" tap roundtrip | Defines the brain-side endpoint that cancels remaining strikes | Implements the delegate that POSTs the ack |
| Reliability test matrix | Designs the server-side test scenarios | Owns the phone-side test runbook |
| Tailscale ops | Owns brain's bind, considers auth | Configures phone-side; calls brain's tailnet IP |

**Ownership split mantra:**
- **Brain owns: the truth (vault), the schedule, the intent parse.**
- **Phone owns: the microphone, the speaker, the notification.**

When they disagree: brain engineer yields on UI behavior, wins on data shape and timing.

**Pairing rhythm:** A weekly 30-minute sync on protocol changes. Otherwise, async via PR review on each other's endpoint/handler changes. A shared markdown doc (`Homunculus/PROTOCOL.md` is a natural artifact for this hire to author) tracks the brain↔phone contract.

---

## 6. Recommended Model Tier: opus

Pax's view (Nolan decides):

**Recommended: opus.** Reasoning:

- The role's **hard work is judgment-bound, not implementation-bound.** Schema design, prompt iteration, time-zone-correctness reviews, and reliability-contract architecture are all "few-decisions-per-day, each one has long tail consequences" work.
- Calibrating an on-device 7B model is an open-ended empirical problem with no canonical answer. The right output requires reasoning about *why* a model fails on a class of utterances and *what schema change* would fix it. That's not a sonnet-tier task — sonnet would patch the prompt; opus rethinks the schema.
- The portability discipline (saying no to MLX, no to Keychain, no to `launchd`-only) requires senior architectural judgment under pressure. Sonnet would expediently reach for the shortcut.
- The Python implementation work is routine and *would* be sonnet-tier in isolation. But Larry can delegate sub-tasks to lower-tier members when this engineer needs to ship code; the persona should hold the judgment seat.
- Compare to existing team: Mori is opus (the iOS-era predecessor), Kit is sonnet (implementation lead). This hire fills the brain side of Mori's old territory; opus matches the cognitive demand.

(If Nolan wants to economize: sonnet could probably handle this role *if* the persona is unusually crisp on portability rules and the schema-design heuristics. But the upside of opus here — fewer architectural drift incidents — is large and the downside is small. Recommend opus.)

---

## 7. Persona Style Notes (for Nolan)

Lift directly from Mori's persona for the *voice product sensibility* — "this is a prosthetic, not a toy," "an older user whose memory is failing deserves to hear what's about to happen to their week before it happens." That trust-first framing is *the same product* and this engineer must hold it.

Cut from Mori's persona: everything Swift / iOS / `AVAudioSession` / GRDB / `UNUserNotificationCenter` Swift-side. That's Kit's territory now.

Add to this persona that Mori didn't have: portability religion, the schema-first/prompt-second discipline, the deterministic-math-outside-the-prompt rule, FastAPI/Pydantic v2 fluency, Ollama operations, vLLM/Linux migration awareness, **the markdown-as-database philosophy** (a deliberately weird choice that requires a particular taste to defend), Tailscale-as-trust-boundary thinking.

Persona name suggestion (Nolan picks the actual name): a short, vault-flavored single name in the team's existing style (one or two syllables, gender-neutral). Candidates: **Otto**, **Rune**, **Vesper**, **Brio**, **Wolf**, **Linus** (might be too on-the-nose), **Pico**, **Atlas**. Pax has no strong preference — name fit is Nolan's call.

---

## 8. Concrete Best Practices The Persona Should Hold

These are the rules-of-thumb the persona file should explicitly enforce.

1. **Schema first. Prompt second. Math never in the prompt.**
2. **Calibrate against the actual on-device model, not against expectations from frontier models.** Run a real utterance corpus through `qwen2.5:7b` or `qwen2.5:14b` and read the failures.
3. **`ambiguous_fields` is the most valuable thing the parse returns.** When it's non-empty, ask a clarifying question; never silently guess.
4. **UTC + IANA zone. Never offsets. Never naive datetimes crossing module boundaries.**
5. **Temperature ≤ 0.2 for intent extraction.** Structured-output is more reliable cold.
6. **One model resident in Ollama. Don't swap.** Model swap is fatal to latency.
7. **Heuristic fallback parser is maintained, not abandoned.** Tests run on it; offline operation depends on it.
8. **Markdown files are the truth. No SQLite. No DB. No cache that survives process death.**
9. **Atomic write-rename for every file mutation.** Two captures cannot corrupt the inbox.
10. **Portability religion:** no MLX import, no Keychain, no FSEvents, no `launchd`-only. The brain runs on a Linux box with zero code changes.
11. **Tailscale is the trust boundary in v1.** The bearer-token middleware is one PR away and the engineer keeps it that way; when the user wants to expose the brain outside the tailnet, they're ready.
12. **`/health` always-fast.** No model call on the hot path; a separate `/diagnostic` endpoint can pay the cost.
13. **Spoken replies are written for an older listener.** "You're clear Thursday June 11 at 10:00 AM" beats "ok." No ISO 8601 strings in TTS payloads.
14. **The reminder schedule is the engineer's signature.** Every break in the morning-summary → T-30 → T-5 → four-strikes → missed-log chain is a trust fracture. They own every link.
15. **Pair with Kit on protocol changes; never sneak a brain-side change that requires a phone update.** Protocol changes go through `PROTOCOL.md` and a Kit PR review before merge.
16. **Never let LLM latency block the user feedback loop.** If Ollama is slow, return "got it, working on that" within 200ms via heuristic fast path, then push the refined answer when the model returns. (v1.1 work; engineer keeps it on the roadmap.)
17. **Write the v1.1 migration runbook the day the v1.0 brain ships.** "Move the brain to Linux/NVIDIA" should be a documented checklist, not a future research project. Engineer authors it.

---

## 9. Reliability Test Matrix (Server Side)

The engineer runs this on every release candidate, in addition to the existing 44 unit tests:

1. **Cold-start time-zone change.** Start the brain, change the system TZ, ensure scheduled fire times update via the next reconciliation push.
2. **Ollama unreachable.** Kill Ollama mid-capture; ensure heuristic fallback fires and the user gets a degraded-but-functional response.
3. **DST weekend.** Force `zoneinfo` to a date crossing DST; ensure events at "10 AM" still mean 10 AM local on both sides of the transition.
4. **Vault file race.** Fire two simultaneous captures targeting the same minute; ensure no inbox corruption, no double-event.
5. **Long utterance.** Send a 500-word utterance to `/capture/text`; ensure the model handles it or the heuristic fallback degrades cleanly.
6. **Markdown hand-edit.** While the brain is running, hand-edit an event's `.md` file to change its start time; ensure the next list-events call reflects the edit.
7. **Phone offline.** Phone misses a schedule push; ensure the next push from the brain on reconnect is idempotent (uses the deterministic IDs) and doesn't double-schedule.
8. **Tailscale offline.** Brain runs, phone can't reach it; brain doesn't crash, queues nothing, the next reconnect just re-pushes the current schedule.

---

## 10. Sources Consulted (June 2026)

- [Ollama vs llama.cpp vs vLLM: Which Should You Use in 2026?](https://dev.to/thurmon_demich/ollama-vs-llamacpp-vs-vllm-which-should-you-use-in-2026-10gp)
- [llama.cpp vs MLX vs Ollama vs vLLM: Local AI Inference for Apple Silicon in 2026](https://contracollective.com/blog/llama-cpp-vs-mlx-ollama-vllm-apple-silicon-2026)
- [How Does Ollama's Structured Outputs Work? — Daniel Clayton](https://blog.danielclayton.co.uk/posts/ollama-structured-outputs/)
- [Constraining LLMs with Structured Output: Ollama, Qwen3 & Python or Go — Rost Glukhov](https://medium.com/@rosgluk/constraining-llms-with-structured-output-ollama-qwen3-python-or-go-2f56ff41d720)
- [Reliable Structured Output from Local LLMs: JSON Extraction Without Hallucination — Markaicode](https://markaicode.com/ollama-structured-output-pipeline/)
- [FastAPI Under Load in 2026: Pydantic v2, uvloop, HTTP/3 — Codastra](https://medium.com/@2nick2patel2/fastapi-under-load-in-2026-pydantic-v2-uvloop-http-3-what-actually-moves-the-needle-74717b74e74e)
- [FastAPI Best Practices — zhanymkanov](https://github.com/zhanymkanov/fastapi-best-practices)
- [Building a Fully Local LLM Voice Assistant: A Practical Architecture Guide — Towards AI](https://towardsai.net/p/machine-learning/building-a-fully-local-llm-voice-assistant-a-practical-architecture-guide)
- [Backend Engineer – LLM & Voice AI at Feather (Y Combinator)](https://www.ycombinator.com/companies/feather-2/jobs/hh2ypqP-backend-engineer-llm-voice-ai)
- [I'm Using a Markdown Database — EmNudge](https://emnudge.dev/notes/markdown-database/)
- [Enforce Structured JSON Output with Qwen Models — Alibaba Cloud](https://www.alibabacloud.com/help/en/model-studio/qwen-structured-output)
- [Local AI Runtime Update: May 2026 — Codersera](https://codersera.com/blog/local-ai-runtimes-may-2026-update/)
- [Local LLM Deployment 2026: Ollama vs vLLM Tuning — QubitTool](https://qubittool.com/blog/local-llm-deployment-2026-ollama-vllm-optimization)
- Internal: `/Volumes/GIT/CLAUDE/SHARED_WORK_FOLDER/Homunculus/brain/` (the existing skeleton, especially `llm.py`, `schemas.py`, `reminders.py`, `date_resolver.py`)
- Internal: `Team/kit.md`, `Team/mori.md` (for ownership-split and product-sensibility lift)
