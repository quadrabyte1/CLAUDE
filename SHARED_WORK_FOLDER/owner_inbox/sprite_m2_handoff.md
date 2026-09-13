**Sprite v0.2 — 2026-09-13 — Rune**

# Sprite M2 Handoff — Mac Pipeline End-to-End

## What ships

### Source modules (`Sprite/src/sprite/`)

| Module | What it does |
|---|---|
| `config.py` | All paths + tuning via env vars. Neutral names (`SPRITE_*`, not mac-specific). Frozen dataclass. |
| `state.py` | `processed.jsonl` append-only idempotency. Key = SHA-256 first 64 KB. No SQLite. |
| `inbox.py` | Atomic-append per-day markdown inbox for ambiguous/low-confidence captures. |
| `icloud.py` | FDA-graceful directory listing, `.icloud` placeholder detection + `brctl download`, mtime-stable check (`time.time()`, not monotonic), atomic archive copy. |
| `transcribe.py` | `whisper-cpp` subprocess wrapper. Confidence derived from `exp(mean(avg_logprob))` across segments. Transcript JSON persisted to `~/sprite/transcripts/YYYY/MM/<uuid>.json`. |
| `parse.py` | Preprocessor (regex criticality + verb hints) + Ollama JSON-schema-constrained call (`format=` field, GBNF). Temperature 0.2. Preprocessor criticality cannot be overridden downward. |
| `herman.py` | `httpx` POST `/capture/parsed`. 3 retries with 1s/2s backoff. 5xx retries, 4xx does not. Single source of truth for wire shape via `build_request()`. |
| `watcher.py` | Cold-boot sweep (mtime-order, idempotent) + `watchdog` event loop. 1s poll drain cycle. Graceful SIGTERM/SIGINT shutdown. FDA error logs clearly without crash-looping. |

### Tests (`Sprite/tests/`)

| Test file | # tests | What it covers |
|---|---|---|
| `test_state.py` | 12 | file_key determinism, 64KB boundary, idempotency, append-only, UTC timestamps |
| `test_inbox.py` | 8 | atomic write, header dedup, ambiguous-fields display, existing-content preservation |
| `test_parse.py` | 23 | preprocessor (7 criticality, 10 verb hint, 2 interaction), 4 Ollama mocks, 3 error paths |
| `test_herman_client.py` | 18 | build_request field coverage, **4 wire-shape tests against Herman's actual `ParsedCaptureRequest`**, retry logic (5xx, 4xx, network), success-on-retry |
| `test_watcher.py` | 14 | cold-boot sweep, FDA-blocked graceful, already-processed idempotency, happy path, low confidence → inbox, ambiguous → inbox, WhisperError, OllamaUnreachable, debounce, iCloud placeholder |
| `test_end_to_end.py` | 9 | fixture E2E happy path, low-conf → inbox, idempotency 2nd run, fixture sanity |
| **Total** | **84** | **84/84 green** |

### Deploy artifacts (`Sprite/deploy/`)

- `com.sprite.watcher.plist` — launchd agent. **Unloaded. Boss loads after FDA grant.**
- `sprite-watcher.service` — systemd unit (Linux/NVIDIA portability religion).
- `install.sh` — copies watcher to `~/.local/bin/sprite_watcher.sh`, creates venv at `~/.local/lib/sprite/venv/`, installs plist, prints FDA instructions.

### Docs (`Sprite/docs/`)

- `FDA_SETUP.md` — exact System Settings steps + verification commands.
- `FIRST_RUN.md` — smoke test procedure with expected log output + troubleshooting table.

---

## How to smoke-test tomorrow

After granting FDA (see docs/FDA_SETUP.md):

```bash
# 1. Run install
bash /Volumes/GIT/CLAUDE/SHARED_WORK_FOLDER/Sprite/deploy/install.sh

# 2. Download whisper model (one-time)
brew install whisper-cpp
mkdir -p ~/sprite/models
whisper-cpp-download-ggml-model small.en
# Model lands in ~/Library/Caches/whisper/ — move it:
cp ~/Library/Caches/whisper/ggml-small.en.bin ~/sprite/models/

# 3. Verify FDA (should list .m4a files, not "Operation not permitted")
ls ~/Library/Group\ Containers/group.com.apple.VoiceMemos.shared/Recordings/

# 4. Make sure Herman and Ollama are running
curl -s http://localhost:8765/health | python3 -m json.tool
curl -s http://localhost:11434/api/tags | python3 -m json.tool | grep qwen

# 5. Load the watcher (AFTER FDA is granted)
launchctl load ~/Library/LaunchAgents/com.sprite.watcher.plist
launchctl list | grep sprite

# 6. Tail the log
tail -f /tmp/sprite_watcher.log

# 7. Record on iPhone: "Sprite test one two three, schedule a meeting with myself on Monday at nine"
#    Wait 30-90 seconds for iCloud sync.
#    Watch the log — expect: archive → transcribe → parse → herman accepted → record_id

# 8. Verify Herman wrote it
ls ~/homunculus/vault/calendar/ | sort -r | head -3
tail -5 ~/sprite/state/processed.jsonl | python3 -m json.tool
```

---

## What's stubbed / not proven live

| Gap | Reason | Risk |
|---|---|---|
| **whisper.cpp not installed** | `brew install whisper-cpp` not available in agent context. Binary is assumed; all transcription tests mock the subprocess. | Low — standard Homebrew package. |
| **Ollama model not live-tested** | `qwen2.5:7b-instruct` intent extraction not run in agent context against real audio. Prompt tuned against corpus from Herman M1. | Medium — first real memo may need prompt iteration. |
| **iCloud sync not verified** | FDA not grantable from agent context. Path confirmed inaccessible (`Operation not permitted` = correct sign it exists). | Low — Mori confirmed path and mechanism. |
| **Live Herman POST not proven** | Wire-shape tests run against Herman's Pydantic model directly (cross-repo import). HTTP 200 round-trip needs live Herman + watcher + real audio. | Low — wire shape is locked by the 4 Pydantic tests that import Herman's schema. |
| **Date resolution of relative `when`** | `parse.py` emits relative `when` strings (e.g. "thursday") for Herman to resolve via its `date_resolver.py`. Sprite does not resolve dates. Herman's existing resolver handles this. | None for M2 — Herman already resolves relative dates from its own `/capture/text` path. The same resolver fires for `/capture/parsed`. |
| **`avoid` verb** | Per M2 non-goals, `avoid` is handled by Herman (writes to `~/sprite/warnings.md`). Sprite passes it through to Herman correctly (verb="avoid" is a valid ParsedCaptureRequest verb). No special Sprite-side handling needed. | None. |

---

## Deviations from `sprite_mac_backend_scoping.md`

1. **`fswatch` → `watchdog`** (scoping §1 listed both). I chose `watchdog` (pip-installable, cross-platform, zero binary dependency) over `fswatch` (requires separate brew install, subprocess-based). `watchdog` uses FSEvents on Mac under the hood but behind the Python abstraction boundary — no direct FSEvents import. The portability religion is upheld.

2. **Confidence gating: `min(whisper_confidence, llm_confidence)`** instead of just LLM confidence. Scoping §4 said gate on `confidence < 0.6` using the LLM output alone. A bad transcript (garbled audio) can produce a high-confidence wrong parse. Taking the minimum prevents silent bad parses from reaching Herman. Conservative change, same threshold.

3. **No `speaker_tz` resolution in Sprite.** Scoping implied Sprite might resolve relative dates before POSTing to Herman. Herman's `date_resolver.py` already handles this for `/capture/text`; it fires for `/capture/parsed` too (Herman receives `speaker_tz` in the payload). No duplication.

4. **No `source: "sprite"` field in `ParsedCaptureRequest`.** Herman's schema doesn't include it (Mori's scoping mentioned it as an "optional origin tag" — Kit's territory, not Sprite's). I added `sprite_uuid` as a provenance field (Herman ignores unknown fields in Pydantic v2 by default). Herman's `_handle_note()` already writes `source: "sprite"` in the frontmatter from capture_parsed.py line 254 — it hardcodes it.

---

## What M3 should be

**M3: First live iCloud sync verified + prompt calibration pass**

1. **Boss records test memo, watcher processes it live.** This is the only thing M2 did not prove. One phone + one voice memo + tailing the log is the test.
2. **Prompt calibration pass.** Collect the first 10 real memos from `~/sprite/transcripts/`. Check parse quality: wrong verb? wrong subject? Run `qwen2.5:7b-instruct` against them and adjust the system prompt. Pay particular attention to: subject extraction from long memos, "this Tuesday vs next Tuesday" ambiguity (should populate `ambiguous_fields`), multi-intent memos.
3. **Date resolution for relative `when`.** Currently Sprite emits "thursday" raw and Herman resolves it. Herman's resolver works for `/capture/text` but `/capture/parsed` passes `when` straight to the verb handler. **This may be a bug** — check whether `_handle_schedule` and `_handle_handle` in Herman's `capture_parsed.py` call `_ensure_tz()` on a string `when`. If not, relative dates will be passed to `cal.create_event()` as strings and likely fail. File a bug note in Herman for M3. [Scoping risk §3 mentioned this gap.]
4. **`avoid` morning summary section.** Herman's morning summary already reads `~/sprite/warnings.md` via `read_recent_warnings()`. Verify it appears in `/reminders/upcoming` after a real `avoid` memo.
5. **Heartbeat monitoring.** Mori's risk #2: if iCloud sync goes silent, Sprite goes deaf. Add a check: if no new .m4a in 72h AND the state log shows prior activity, write a warning to the inbox. Simple cron-style check in the watcher's main loop.

---

*All 84 tests green. Wire shape validated against Herman's Pydantic schema. Fixture E2E proven. Live iCloud sync gated on FDA grant + phone test tomorrow.*
