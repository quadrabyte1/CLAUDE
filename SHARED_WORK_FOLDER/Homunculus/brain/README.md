# Homunculus brain

The Mac-side engine for Homunculus — a voice-first capture and reminder
assistant. v1.0 design (see `~/.claude/projects/-Volumes-GIT-CLAUDE/memory/project_homunculus.md`).

The brain holds the calendar truth (as plain markdown), parses voice
utterances via a local LLM, routes captures to the right markdown file,
and generates the escalating-strike reminder schedule that the phone
client will register with `UNUserNotificationCenter` over Tailscale.

## Status

- v1.2.2 shipped 2026-06-10. **87 unit tests pass** (77 baseline + 10
  new). Bug fix: an ambiguous bare hour:minute (e.g. "Feed Jake at
  5:35") no longer silently defaults to AM. The date resolver flags
  hours 1-12 with no AM/PM and no 24-hour context as ambiguous; the
  router asks "AM or PM?" instead of guessing. Matches the locked UX
  rule "Missing info: one specific clarifying question." Heuristic +
  LLM paths agree (system prompt also updated; prompt-contract test
  guards against regression).
- v1.2.1 shipped 2026-06-10. **77 unit tests pass** (73 baseline + 4 new
  for the in-browser test client). Additive over v1.2:
  `CaptureResponse.intent` is now populated, `/reminders/upcoming`
  accepts `include_fired`, and a single-page test client lives at
  `/test/`.
- v1.2 shipped 2026-06-08. **70 unit tests pass** (51 baseline + 19 new
  for the v1.2 must-fix items).
- `speaker_tz` is honored end-to-end (phone zone wins over server default).
- Vault writes are atomic (tmp + `os.replace`); inbox appends are
  serialized by a POSIX file lock — two simultaneous captures cannot
  corrupt the vault.
- Morning summary rows are generated lazily inside `/reminders/upcoming`.
- `/reminders/upcoming` and `/ack` are live — Kit can wire the iOS client
  against the real contract instead of the client-side shim.
- Ollama wired in production against `qwen2.5:7b` (local, on the Mac mini
  M4); live captures hit the model. The heuristic parser remains as the
  offline-fallback path and as the carrier for the hermetic test suite.
- Reminder push to phone is still a logging stub; the phone client
  doesn't exist yet (v1.3 gating).

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

## In-browser test client

A single-page harness for hand-exercising the brain end-to-end without
curl. Vanilla HTML/CSS/JS — no build step, no framework, ships inside the
package.

Open it at:

```
http://localhost:8765/test/
```

The page is mounted by the brain itself (same port), so there is no
second process to start. Files live at
`homunculus_brain/test_client/{index.html, styles.css, app.js}`.

Features:

- **Text capture** — textarea + Send hits `POST /capture/text` and
  renders the response with one of four color-coded action states
  (`wrote` green, `needs_confirmation` yellow, `needs_clarification`
  orange, `inbox` gray).
- **Confirm flow** — when the brain returns `needs_confirmation`, the
  page reads `CaptureResponse.intent` (echoed by the brain — see the
  schema change below) and posts it back to `/capture/confirm` on
  click. No client-side intent reconstruction.
- **Live `/reminders/upcoming`** — auto-refreshes every 5 seconds.
  Groups rows by `event_id`, shows fire times in the row's own `tz`,
  exposes a per-row OK button → `POST /ack`. After ack, the next
  refresh reconciles by full rebuild — cancelled strikes disappear
  immediately.
- **Version badge** — upper-left, populated from `/health`.
- **"Include fired" toggle** — sets `?include_fired=true` so just-fired
  rows stay visible during live testing (the default endpoint behavior
  filters them out so the phone client gets a clean iOS schedule).

The test client uses no auth — Tailscale is the trust boundary, same as
the phone client will be. Don't expose port 8765 outside the tailnet
without adding bearer-token middleware first.

### Related schema change (additive, wire-compatible)

`CaptureResponse` now carries an optional `intent: ParsedIntent` field,
populated for every router branch. The test client uses it for the
confirm round-trip; the iOS client may use it (or ignore it). Older
clients that don't know about the field will silently drop it.

## API

### `GET /health`

```json
{
  "status": "ok",
  "design_version": "1.2",
  "package_version": "1.2.0",
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

### `GET /reminders/upcoming?window_hours=72&include_fired=false`

Returns the next window of reminder rows the phone should register with
`UNUserNotificationCenter`. Combines:

- Per-event strike rows (T-30, T-5, T+0, T+5, T+10, T+15) for every
  event whose fire times fall in the window.
- Daily morning-summary rows (one per day in the window, identifier
  `summary.<yyyy-mm-dd>`).

Rows already `acked`, `cancelled`, or `fired` are excluded. Output is
sorted ascending by `fire_at` and capped at 60 rows so the phone stays
under iOS's 64-pending limit. The brain composes this list fresh on
every call — the vault is the truth.

`include_fired=true` is a test-client affordance (v1.2.1): the time
window opens to `now - 24h` and rows of any status are returned, so the
boss can verify schedule generation during live testing without losing
visibility as soon as a strike fires. The phone client should never set
this — `UNUserNotificationCenter` would silently drop past triggers
anyway.

```json
[
  {
    "event_id": "summary.2026-06-12",
    "kind": "morning_summary",
    "fire_at": "2026-06-12T07:00:00-04:00",
    "tz": "America/New_York",
    "body": "Good morning. Today: 10:00 AM Coffee with Jane.",
    "status": "pending"
  },
  {
    "event_id": "2026-06-12-coffee-with-jane",
    "kind": "heads_up_30",
    "fire_at": "2026-06-12T09:30:00-04:00",
    "tz": "America/New_York",
    "body": "In 30 minutes: Coffee with Jane at 10:00 AM.",
    "status": "pending"
  }
]
```

### `POST /ack`

```json
{
  "event_id": "2026-06-12-coffee-with-jane",
  "kind": "strike_0",
  "acked_at": "2026-06-12T10:00:32-04:00"
}
```

Marks the named row `acked` and cancels every later strike in the same
event chain (`strike_5`, `strike_10`, `strike_15` when `strike_0` is
acked). Idempotent: a double-ack returns the same shape with an empty
`cancelled_kinds`. Unknown event ids return 200 with empty results — the
brain is the source of truth; the phone reconciles on the next
`/reminders/upcoming` pull.

Response:

```json
{
  "event_id": "2026-06-12-coffee-with-jane",
  "acked_kind": "strike_0",
  "cancelled_kinds": ["strike_5", "strike_10", "strike_15"],
  "rows": [ ... updated ReminderRow list for the chain ... ]
}
```

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
  Tailscale; today it's still a logging stub — gated on the phone
  client existing).
- "Undo that" voice-driven correction within the 5-minute window
  (`POST /undo`, deferred to v1.3 — not blocked, just not in the v1.2
  must-fix set).
- `GET /activity` HTTP surface for the dev viewer (the JSONL log is
  there; the endpoint isn't surfaced yet).
- Richer `ambiguous_fields` shape (still a list of names; v1.3 promotes
  to per-field reason + candidate values, requires Kit review).
- Missed-event tracking — `build_daily_summary_rows` accepts the slot
  but stubs `missed_yesterday` as `[]` so the API shape is stable while
  the v1.3 tracking work is open.
- LLM prompt tuning against a real model (the system prompt is a first
  pass and will need iteration with whatever model the user lands on).
