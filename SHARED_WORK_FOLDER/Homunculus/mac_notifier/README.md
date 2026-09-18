# mac_notifier

**v0.1.0 — 2026-09-15 — Rune**

Mac notification poller for Herman/Homunculus. Polls Herman's `/reminders/upcoming`
endpoint every 60 seconds and fires macOS notifications when scheduled reminder
rows come due.

This is the Mac-side stopgap until Kit's iOS client is running on Thomas's phone.
It surfaces Herman's full escalating-strike schedule (morning summary at 7 AM,
T-30, T-5, strikes at T+0/+5/+10/+15) as native macOS notifications.

---

## Architecture

```
mac_notifier/
├── src/mac_notifier/
│   ├── __init__.py         VERSION = "0.1.0"
│   ├── poller.py           Main loop + run_poll_cycle()
│   ├── herman_client.py    httpx GET /reminders/upcoming
│   ├── applescript.py      subprocess wrapper for osascript display notification
│   ├── state.py            fired.jsonl append + in-memory dedup set
│   └── config.py           env-loaded config dataclass
├── tests/                  ~55 unit tests — all external calls mocked
├── deploy/
│   ├── com.homunculus.mac_notifier.plist   launchd agent
│   ├── mac-notifier.service                systemd companion (Linux portability)
│   └── install.sh                          boot-volume install script
└── docs/FIRST_RUN.md
```

**Sibling packages** (not touched by this package):
- `Homunculus/brain/` — Herman FastAPI server (the data source)
- `Homunculus/mac_calendar_bridge/` — vault → Calendar.app sync
- `Homunculus/mac_notes_bridge/` — vault → Notes.app sync

---

## How it works

1. **Poll loop** — every 60 seconds (configurable via `NOTIFIER_POLL_INTERVAL`):
   - `GET http://localhost:8765/reminders/upcoming?include_fired=false`
   - Parse JSON list of reminder rows

2. **Grace window** — a row is "due" if `now - 90s ≤ fire_at ≤ now + 90s`.
   90 seconds is intentionally generous: if the process was down for a minute,
   it still catches the row. Under-fire is acceptable; over-fire is not.

3. **Dedup** — `~/.local/share/mac_notifier/fired.jsonl` tracks every fired
   notification by `<event_id>:<kind>`. Loaded into memory at boot. Append-only.

4. **Fire** — `osascript display notification "<body>" with title "Homunculus" subtitle "<kind-label>" sound name "default"`

5. **Mark fired** — append to state file, update in-memory set. Log at INFO.

6. **Fail loudly** — every skip decision logged (DEBUG or INFO). Herman unreachable → log ERROR, keep polling. osascript failure → log ERROR, do NOT mark fired (retry next cycle).

---

## Herman response shape

Fields used from `/reminders/upcoming`:

| Field | Type | Example |
|-------|------|---------|
| `event_id` | str | `"summary.2026-09-16"` |
| `kind` | str | `"morning_summary"` |
| `fire_at` | ISO 8601 with tz | `"2026-09-16T07:00:00-04:00"` |
| `body` | str | `"Good morning. Today: ..."` |
| `tz` | IANA zone | `"America/New_York"` |

Identifier for dedup: `"<event_id>:<kind>"` (same event_id, different kinds fire independently).

---

## Kind → Subtitle mapping

| `kind` | Notification subtitle |
|--------|----------------------|
| `morning_summary` | Morning summary |
| `heads_up_30` | 30-min heads-up |
| `pre_5` | 5-min heads-up |
| `strike_0` | Strike 1 |
| `strike_5` | Strike 2 |
| `strike_10` | Strike 3 |
| `strike_15` | Strike 4 |

---

## Configuration (environment variables)

| Variable | Default | Description |
|----------|---------|-------------|
| `NOTIFIER_HERMAN_URL` | `http://localhost:8765` | Herman base URL |
| `NOTIFIER_POLL_INTERVAL` | `60` | Seconds between polls |
| `NOTIFIER_GRACE_WINDOW` | `90` | Seconds grace on each side of fire_at |
| `NOTIFIER_STATE_FILE` | `~/.local/share/mac_notifier/fired.jsonl` | Dedup state |
| `NOTIFIER_LOG_LEVEL` | `INFO` | Python log level |
| `NOTIFIER_LOG_FILE` | `/tmp/mac_notifier.log` | Log file path |

---

## Install

```bash
cd Homunculus/mac_notifier
bash deploy/install.sh
launchctl load ~/Library/LaunchAgents/com.homunculus.mac_notifier.plist
```

See `docs/FIRST_RUN.md` for the full walkthrough.

---

## Tests

```bash
cd Homunculus/mac_notifier
pip install -e ".[dev]"
pytest -v
```

~55 tests. All external calls (osascript, httpx, Herman) are mocked.
No real notifications. No real network calls.

---

## Known caveat: notification branding (v0.1)

Notifications appear branded as **"Script Editor"** rather than "Homunculus".
This is a documented macOS limitation: `display notification` is attributed
to the osascript runner process, not the calling script.

**The mechanism works** — notifications appear, sound, and can be interacted
with normally. Only the app-name attribution is wrong.

### v0.2 roadmap

- **terminal-notifier** (Homebrew): `brew install terminal-notifier` → call
  `terminal-notifier -title "Homunculus" -subtitle "..." -message "..." -sound default`
  — easiest fix, correct branding, no code-signing needed.
- **Bundled .app**: proper macOS app bundle with its own bundle ID. Enables
  notification action buttons (Snooze / Ack) via the macOS Notification API.
  Required for ack roundtrip to Herman (`/ack/{event_id}`).
- **Sound customization by kind**: different sounds for morning_summary vs strikes.
- **User-configurable message templates**: v0.2 nice-to-have.

---

## Non-goals (v0.1)

- Ack roundtrip to Herman (Kit's territory — Herman's `/ack` endpoint untouched)
- Phone-side surfacing (Kit)
- Sound customization by kind (v0.2)
- Notification action buttons (v0.2 — requires bundled .app)
- Any change to Herman, Sprite, mac_calendar_bridge, or mac_notes_bridge
