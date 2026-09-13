`v0.1` — 2026-09-12 — Rune

# Sprite Mac Backend — Scoping Document

Sprite = voice-memo → transcript → intent JSON → Herman. Mac side only. No code yet; this is the pipeline plan, model picks, and Herman handoff contract.

## Pipeline

```
+----------------+     +-----------+     +-------------+     +-----------------+     +---------+
| iCloud Voice   | --> | fswatch   | --> | whisper.cpp | --> | preproc + Ollama| --> | Herman  |
| Memos folder   |     | (launchd) |     |  small.en   |     | intent parser   |     | FastAPI |
+----------------+     +-----------+     +-------------+     +-----------------+     +---------+
        |                    |                  |                    |                    ^
        v                    v                  v                    v                    |
   .icloud stub       debounce 3s        ~/sprite/audio/       confidence>=0.6 ------------+
   materialize        (mtime stable)     YYYY/MM/uuid.m4a      confidence<0.6 -> inbox.md
```

## 1. Watcher

- **Tool:** `fswatch` (Homebrew, cross-platform-ish; watchdog is the Linux-future fallback). launchd `KeepAlive=true`, `RunAtLoad=true`.
- **Path (assumed, Mori verifying):** `~/Library/Group Containers/group.com.apple.VoiceMemos.shared/Recordings/`.
- **iCloud placeholders:** files land as `foo.m4a.icloud` (Data-less). Detect suffix, call `brctl download` (or `NSFileCoordinator` via a helper), wait for the real `.m4a`. Poll mtime; only process when mtime is stable for 3 s AND size > 10 KB.
- **Cold boot:** on watcher start, sweep the folder for any `.m4a` not present in `~/sprite/state/processed.jsonl`. Idempotent by SHA-256 of first 64 KB + duration.
- **Repo lives on `/Volumes/GIT` (nosuid).** launchd cannot exec from there — ship the watcher script to `~/.local/bin/sprite_watcher.sh`; plist at `~/Library/LaunchAgents/com.sprite.watcher.plist`.

## 2. Transcription — whisper.cpp

- **Model pick: `small.en` (466 MB, Q5_0).** M4 16 GB with Metal/ANE runs 30 s of speech in ~2-3 s warm. `medium.en` (1.5 GB) is ~3x slower and the accuracy delta on Thomas's short casual memos does not justify the RAM eviction of the resident Ollama model (see §3). Escalate to `medium.en` only if the calibration corpus shows >5% WER on proper nouns.
- **Install:** `brew install whisper-cpp` (binary + Metal support baked in). Model files at `~/sprite/models/ggml-small.en.bin`.
- **Warm-start:** whisper.cpp is stateless CLI per invocation — cold-load is 300 ms, acceptable. No daemon needed. If latency matters later, `whisper-server` (v1.6+) exposes an HTTP endpoint.
- **Output:** JSON with segments + confidence per segment. Persist full JSON to `~/sprite/transcripts/YYYY/MM/<uuid>.json`.

## 3. Intent Parser — Ollama

- **Model pick: `qwen2.5:7b-instruct` (Q4_K_M, ~4.4 GB resident).** Strong schema-following, same family Herman already uses — one model in RAM serves both if we standardize. Llama 3.1 8B Instruct is the fallback; Qwen 2.5 Coder is rejected (code-tuned; wastes capacity on non-code intent).
- **Prompt discipline:** temp 0.2, `format` = JSON schema constrained decoding, one-shot example in system prompt, "emit JSON only."
- **Preprocessor (Python, runs BEFORE the LLM):**
  - Regex on transcript for `\b(mark critical|important|urgent|don't let me forget|critical)\b` → set `criticality="high"` in the record. LLM cannot override downward; can override upward.
  - Verb hint regexes for `schedule|avoid|note|remind|handle` bias the prompt.
- **LLM output JSON:**
```json
{
  "verb": "schedule|note|handle|avoid",
  "subject": "string",
  "when": "ISO-8601 local or null",
  "criticality": "normal|high",
  "confidence": 0.0,
  "raw_transcript": "string",
  "ambiguous_fields": []
}
```
- **Ambiguity gate:** `confidence < 0.6` OR non-empty `ambiguous_fields` → write to `~/sprite/inbox/YYYY-MM-DD.md` (append, atomic rename). Do NOT call Herman.

## 4. Herman Handoff (proposal — needs Herman-side PR)

Herman does not currently expose `POST /capture`. Proposal: **add `POST /capture/parsed`** to Herman, accepting Sprite's pre-parsed record. Distinct from `/capture/text` (which triggers Herman's own parse) so Sprite doesn't double-parse.

**Sprite → Herman request:**
```json
{
  "source": "sprite",
  "audio_path": "/Users/thomas/sprite/audio/2026/09/8f3a....m4a",
  "transcript": "remember I need to call the deck contractor Thursday, mark critical",
  "verb": "handle",
  "subject": "call deck contractor",
  "when": "2026-09-17T09:00:00-04:00",
  "speaker_tz": "America/New_York",
  "criticality": "high",
  "confidence": 0.82,
  "captured_at": "2026-09-12T14:03:11Z",
  "sprite_uuid": "8f3a...",
  "raw_transcript": "..."
}
```

**Herman response:** `CaptureResponse` (existing shape) with `written_event_id`, `spoken_reply`, `clarifying_question`. Sprite logs the response into `~/sprite/state/processed.jsonl`; only then is the memo marked complete.

## 5. `avoid` Verb — Recommendation

**Pick (a): `~/sprite/warnings.md` surfaced in Herman's morning summary.** Reasoning: `avoid` is a passive standing note ("avoid scheduling anything after 3pm Fridays"), not a context-triggered guard. Building a context-guard system needs a signal for "context," which Herman doesn't have. The morning summary is Herman's existing surface; extending it to include a `## Watch out for` section from `warnings.md` is a 20-line Herman patch. Revisit context-guards in v1.x when there's a real trigger channel.

## 6. Audio Retention

- `.m4a` original → `~/sprite/audio/YYYY/MM/<uuid>.m4a` (uuid = SHA-256 truncated of file bytes at capture time).
- Never deleted. Transcript JSON references path. Parse record references path.

## 7. Top Risks

1. **iCloud sync latency variance.** Voice Memos can take 5-60 s to sync depending on network. Watcher debouncing must not fire on partial downloads. Mori is verifying real-world latency; scoping assumes worst-case 90 s.
2. **whisper + Ollama RAM contention.** 4.4 GB Qwen + 500 MB whisper + macOS + Herman FastAPI on 16 GB is tight. If Herman also holds Qwen resident (it does), we share the same Ollama instance — one model, two clients. Mandatory: no model swap in Ollama.
3. **Herman endpoint doesn't exist yet.** `POST /capture/parsed` is a proposal. Until Herman ships it, Sprite has nowhere to hand off. Sequencing: Herman patch first, Sprite integration second.

## Open Questions for Thomas

- Confirm `qwen2.5:7b-instruct` as the shared model (vs Herman potentially wanting 14b).
- Confirm the `avoid` → `warnings.md` design over context-guards.
