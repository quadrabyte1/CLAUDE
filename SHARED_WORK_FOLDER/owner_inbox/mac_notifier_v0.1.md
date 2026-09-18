# mac_notifier v0.1.0 — Handoff

**v0.1.0 — 2026-09-15 — Rune**

---

## What shipped

A new sibling package at `Homunculus/mac_notifier/` that polls Herman's
`/reminders/upcoming` endpoint every 60 seconds and fires macOS notifications
when scheduled rows come due. Zero changes to Herman, Sprite, mac_calendar_bridge,
or mac_notes_bridge. Purely additive.

**120 tests. 120 passed. 0 failed.**

---

## Install steps (run when you wake up)

```bash
cd /Volumes/GIT/CLAUDE/SHARED_WORK_FOLDER/Homunculus/mac_notifier
bash deploy/install.sh
launchctl load ~/Library/LaunchAgents/com.homunculus.mac_notifier.plist
```

Then verify:
```bash
launchctl list | grep mac_notifier
tail -f /tmp/mac_notifier.log
```

**No Automation permission needed.** `display notification` does not require
System Settings → Privacy & Security → Automation (unlike the Calendar/Notes bridges).

---

## What it does

1. Every 60 seconds: `GET http://localhost:8765/reminders/upcoming`
2. For each row: if `fire_at` is within ±90 seconds of now, and not already fired → notification
3. Notification:
   - **Title:** Homunculus
   - **Subtitle:** "Morning summary" / "30-min heads-up" / "Strike 1" / etc.
   - **Body:** Herman's human-readable text (e.g. "Good morning. Today: ...")
   - **Sound:** system default
4. Marks fired in `~/.local/share/mac_notifier/fired.jsonl` — append-only dedup
5. Logs to `/tmp/mac_notifier.log`

---

## Herman's /reminders/upcoming — verified shape

Queried live before writing. Fields used:

| Field | Example |
|-------|---------|
| `event_id` | `"summary.2026-09-16"` |
| `kind` | `"morning_summary"` |
| `fire_at` | `"2026-09-16T07:00:00-04:00"` |
| `body` | `"Good morning. Today: 8:00 AM [handle] Check on Frozen auditions..."` |
| `tz` | `"America/New_York"` |

14 pending rows confirmed in Herman for 2026-09-16 — morning summary at 7 AM,
T-30 heads-ups at 7:30 AM, T-5s at 7:55 AM, then strike sequences through 8:15 AM.

---

## If 7 AM passes before you run install

The morning summary row will be outside the 90-second grace window. The poller
logs it as "SKIP missed" — no notification fires for it. Next natural triggers:
- 7:30 AM — T-30 heads-up for 8 AM events
- 7:55 AM — T-5 heads-up

The missed-row log is at INFO level, so you'll see it in `tail -f /tmp/mac_notifier.log`.

---

## Known caveat: "Script Editor" branding

Notifications fire correctly — they appear, sound, and persist in Notification
Center — but macOS attributes them to **"Script Editor"** rather than "Homunculus".

This is a documented macOS limitation: `display notification` is run via
`osascript`, which macOS brands as Script Editor regardless of what invoked it.
Not a bug in mac_notifier — it's an OS-level constraint for scripted notifications
run outside a bundled app.

**The mechanism works.** Branding is cosmetic.

---

## v0.2 roadmap

1. **terminal-notifier** (easiest fix): `brew install terminal-notifier` →
   switch to `terminal-notifier -title "Homunculus" -subtitle "..." -message "..."`.
   Proper branding, no code-signing needed.

2. **Bundled .app**: proper macOS app bundle with its own bundle ID. Required
   for notification action buttons (Snooze / Dismiss). Enables ack roundtrip
   to Herman's `/ack/{event_id}` without Kit's client.

3. **Sound customization by kind**: different sounds for morning summary vs strikes.

4. **User-configurable body templates**: customize how each kind is worded.

5. **Snooze / Ack action buttons** (requires bundled .app from item 2).

---

## Package layout

```
Homunculus/mac_notifier/
├── README.md
├── pyproject.toml                  # mac-notifier 0.1.0, deps: httpx + tzdata
├── src/mac_notifier/
│   ├── __init__.py                 # VERSION = "0.1.0"
│   ├── poller.py                   # main loop + run_poll_cycle()
│   ├── herman_client.py            # httpx GET /reminders/upcoming
│   ├── applescript.py              # osascript display notification wrapper
│   ├── state.py                    # fired.jsonl append + in-memory dedup
│   └── config.py                   # env-loaded Config dataclass
├── tests/
│   ├── test_poller.py              # 37 tests — grace window, dedup, errors
│   ├── test_state.py               # 23 tests — JSONL load/write/dedup/thread-safety
│   ├── test_applescript.py         # 18 tests — osascript args, escaping, errors
│   └── test_config.py              # 16 tests — defaults, overrides, frozen
├── deploy/
│   ├── com.homunculus.mac_notifier.plist
│   ├── mac-notifier.service        # systemd companion (portability)
│   └── install.sh                  # boot-volume install (nosuid pattern)
└── docs/FIRST_RUN.md
```

---

## Test results

```
120 passed in 0.12s
```

All 8 mandatory test cases from the spec covered:

| # | Case | Result |
|---|------|--------|
| 1 | Row due + not in state → fire + mark | PASS |
| 2 | Row due + already in state → skip | PASS |
| 3 | Row too far in future → skip | PASS |
| 4 | Row too far in past (missed) → skip at INFO | PASS |
| 5 | Malformed row (missing fire_at) → skip, no crash | PASS |
| 6 | Herman unreachable → log error, keep polling | PASS |
| 7 | State file missing → empty state, no crash | PASS |
| 8 | Grace boundary: ±89s fires, ±91s skips | PASS |

— Rune
