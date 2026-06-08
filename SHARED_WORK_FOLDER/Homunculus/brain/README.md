# Homunculus brain

The Mac-side engine for Homunculus — a voice-first capture and reminder
assistant. v1.0 design (see `~/.claude/projects/-Volumes-GIT-CLAUDE/memory/project_homunculus.md`).

The brain holds the calendar truth (as plain markdown), parses voice
utterances via a local LLM, routes captures to the right markdown file,
and generates the escalating-strike reminder schedule that the phone
client will register with `UNUserNotificationCenter` over Tailscale.

## Status

- Skeleton + core logic implemented. All 44 unit tests pass.
- Ollama integration written; not wired to a real model yet (heuristic
  fallback used in tests).
- Reminder push to phone is a logging stub; the phone client doesn't exist yet.
- No persona-driven team work yet — this skeleton was built directly by Larry
  while the user was out so the work could continue.

## Layout

```
brain/
├── pyproject.toml
├── README.md                  — this file
├── homunculus_brain/
│   ├── __init__.py            — VERSION + DESIGN_VERSION
│   ├── config.py              — env-driven runtime config
│   ├── schemas.py             — pydantic models (the contracts)
│   ├── date_resolver.py       — deterministic day/time math
│   ├── vault.py               — markdown read/write + slug + frontmatter
│   ├── calendar.py            — events + conflict detection
│   ├── notes.py               — tool/prompt/inbox writers
│   ├── reminders.py           — schedule generator + push stub
│   ├── llm.py                 — Ollama client + heuristic fallback
│   ├── intent_router.py       — dispatch ParsedIntent to a handler
│   └── server.py              — FastAPI HTTP surface
└── tests/                     — pytest, hermetic (no Ollama required)
```

The markdown vault lives alongside the brain at `../vault/` by default.
Override with `HOMUNCULUS_VAULT`.

## Install

```bash
cd Homunculus/brain
pip install .              # runtime
pip install .[dev]         # runtime + pytest for the test suite
```

Optional: install Ollama and pull a model.

```bash
brew install ollama
ollama serve &
ollama pull qwen2.5:7b     # ~5 GB; fits comfortably on a 16 GB Mac mini M4
# (or qwen2.5:14b on 32 GB+, llama3.1:8b as an alternative, etc.)
```

## Run

```bash
homunculus-brain          # binds 0.0.0.0:8765 by default
```

Environment variables (all optional, sensible defaults):

| Variable                       | Default                  | Purpose                                  |
| ------------------------------ | ------------------------ | ---------------------------------------- |
| `HOMUNCULUS_VAULT`             | `../vault`               | Where markdown files live                |
| `HOMUNCULUS_TZ`                | `America/New_York`       | Default time zone                        |
| `HOMUNCULUS_MORNING_SUMMARY`   | `07:00`                  | Morning summary fire time                |
| `HOMUNCULUS_MORNING_ANCHOR`    | `9`                      | Hour meant by "morning" / "tomorrow am"  |
| `HOMUNCULUS_FUZZ_MIN`          | `30`                     | Fuzzy-conflict window in minutes         |
| `HOMUNCULUS_DEFAULT_DURATION`  | `30`                     | Default event duration (min)             |
| `HOMUNCULUS_HOST`              | `0.0.0.0`                | Server bind host                         |
| `HOMUNCULUS_PORT`              | `8765`                   | Server port                              |
| `OLLAMA_BASE_URL`              | `http://localhost:11434` | Ollama API root                          |
| `OLLAMA_MODEL`                 | `qwen2.5:7b`             | Model to use for intent parsing          |

## Test

```bash
PYTHONPATH=. pytest tests/
```

Tests are hermetic — no Ollama, no network, no filesystem state outside
`tmp_path`. The heuristic fallback parser carries the test suite.

## API

### `GET /health`

```json
{
  "status": "ok",
  "design_version": "1.0",
  "package_version": "1.0.0",
  "vault_path": "/path/to/vault"
}
```

### `POST /capture/text`

```json
{ "text": "can we meet for coffee Thursday at 10?", "captured_at": null, "speaker_tz": null }
```

Returns a `CaptureResponse`:

```json
{
  "kind": "calendar_query",
  "confidence": "medium",
  "action": "wrote",
  "spoken_reply": "You're clear Thursday June 11 at 10:00 AM.",
  "written_path": null,
  "conflicts": { "has_direct_conflict": false, "has_fuzzy_conflict": false },
  "raw_text": "can we meet for coffee Thursday at 10?"
}
```

`action` is one of:
- `wrote` — the file was written (note) or the query was answered.
- `needs_confirmation` — calendar event proposed; user must say yes.
- `needs_clarification` — ambiguous field; ask the question in `spoken_reply`.
- `inbox` — low-confidence; dropped to `vault/inbox.md`.

### `POST /capture/confirm`

```json
{ "intent": <ParsedIntent>, "captured_at": null }
```

Writes the calendar event and generates the reminder schedule. Returns
`CaptureResponse` with `action: "wrote"` on success.

### `GET /events?day=YYYY-MM-DD`

Lists events on that day (or all events if `day` is omitted).

## Architectural notes

- **Files are truth.** Hand-editing a markdown file changes the brain's
  view immediately. There is no cache, no DB.
- **Portability over Mac-specific speed.** No MLX, no FSEvents, no Keychain.
  Python + Ollama + httpx + pydantic — same code runs on a Linux box or
  the new MS–NVIDIA silicon with zero changes.
- **Tailscale handles transport and trust.** No auth tokens at the
  endpoint level for v1; only your tailnet can reach this port.
- **LLM discipline.** The system prompt forbids prose, the request uses
  structured output (`format: <schema>`) so the model must emit valid
  JSON, and all date math is done in Python — not in the prompt.

## Keeping the Mac awake

The brain is a foreground process; if the Mac sleeps, requests queue.
See `../docs/mac_sleep_disable.md` for the recommended setup
(`sudo pmset -c sleep 0`, plus a LaunchAgent so the brain itself
auto-starts and survives crashes).

## What's not built yet

- iOS / watchOS client (Kit's job; phone is the press-to-talk surface,
  Watch mirrors notifications).
- Real push of the reminder schedule to the phone (HTTPS POST over
  Tailscale; today it's a logging stub).
- "Undo that" voice-driven correction within the 5-minute window.
- Activity log / dev viewer.
- LLM prompt tuning against a real model (the system prompt is a first
  pass and will need iteration with whatever model the user lands on).
