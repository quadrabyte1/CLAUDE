# mac_calendar_bridge v0.1.0 — Handoff

**v0.1.0 — 2026-09-14 — Rune**

---

## What was built

Herman vault events can now appear in macOS Calendar.app. The `mac_calendar_bridge` is a new sibling package under `Homunculus/mac_calendar_bridge/` that watches the vault and pushes events to a dedicated "Homunculus" calendar via AppleScript. Herman's brain is untouched; it stays Linux-portable.

---

## Root cause / architecture

Herman writes calendar events to `vault/calendar/<YYYY-MM>/<event-id>.md`. Two events already existed:
- `2026-09/2026-09-15-meeting-with-myself.md`
- `2026-09/2026-09-18-code-review-with-myself.md`

They were invisible to Calendar.app because Herman has no macOS-specific code (by design — portability rule). The bridge is the adapter layer.

**Architecture:**

```
vault/calendar/  ←  Herman writes here
      ↓
mac_calendar_bridge (watchdog, Python)
      ↓  (osascript subprocess)
Calendar.app  →  iCloud  →  iPhone Calendar
```

Key design choices:
- **Dedicated "Homunculus" calendar** — never touches "Home", "Work", or any existing calendar. You can toggle it on/off or nuke it without consequences.
- **URL field as event identity** — each Calendar.app event gets `url = "homunculus://event/<id>"`. This is how the bridge detects duplicates on restart without a database.
- **Idempotency via JSONL** — `~/.local/share/mac_calendar_bridge/pushed.jsonl` tracks what's been pushed. Fast path on every file-system event; state survives restarts.
- **AppleScript (not EventKit/pyobjc)** — same abstraction-boundary discipline as the Ollama HTTP API. No native macOS SDK in the Python code.

---

## Your install steps

1. Run the installer:
   ```bash
   cd /Volumes/GIT/CLAUDE/SHARED_WORK_FOLDER/Homunculus/mac_calendar_bridge
   bash deploy/install.sh
   ```
   This installs to `~/.local/lib/mac_calendar_bridge/` and `~/.local/bin/` (boot volume, not the nosuid external drive), and copies the launchd plist to `~/Library/LaunchAgents/`.

2. Load the plist:
   ```bash
   launchctl load ~/Library/LaunchAgents/com.homunculus.mac_calendar_bridge.plist
   ```

3. **Automation permission dialog will appear.** macOS asks: "mac_calendar_bridge wants access to control Calendar." Click **OK**. (If you miss it: System Settings → Privacy & Security → Automation → enable Calendar for the bridge.)

4. Verify:
   ```bash
   launchctl list | grep mac_calendar_bridge
   tail -f /tmp/mac_calendar_bridge.log
   ```

5. Open Calendar.app — you should see a new **Homunculus** calendar with both Sep 15 and Sep 18 events.

See `docs/FIRST_RUN.md` for full troubleshooting.

---

## Expected first-run log output

```
INFO  mac_calendar_bridge v0.1.0 starting
INFO  Vault: /Volumes/GIT/CLAUDE/.../Homunculus/vault
INFO  Calendar: Homunculus
INFO  Ensuring Calendar 'Homunculus' exists
INFO  Calendar 'Homunculus' ready
INFO  Cold-boot sweep of .../vault/calendar
INFO  Sweep found 2 event(s) in vault
INFO  Pushing event 'meeting with myself' (2026-09-15-meeting-with-myself) → Calendar 'Homunculus'
INFO  Event '2026-09-15-meeting-with-myself' pushed successfully
INFO  Pushing event 'code review with myself' (2026-09-18-code-review-with-myself) → Calendar 'Homunculus'
INFO  Event '2026-09-18-code-review-with-myself' pushed successfully
INFO  Sweep complete: pushed 2 new event(s)
INFO  Watching .../vault/calendar (recursive) …
```

After first run, any new event Herman/Sprite writes to the vault will be pushed to Calendar.app within seconds.

---

## Test results

```
102 passed, 2 skipped in 0.09s
```

The 2 skips are Linux-platform guards (test that `push_event` / `ensure_calendar` raise `NotImplementedError` on Linux — not applicable on macOS). All 102 macOS-side tests pass. `plutil -lint` on the plist: OK.

---

## Known limitations (v0.1)

- **Push-only.** Editing a vault `.md` file does NOT update the Calendar entry.
- **No delete propagation.** Deleting a vault `.md` file does NOT delete the Calendar entry.
- **No two-way sync.** Changes made directly in Calendar.app are not reflected back to the vault.
- **AppleScript date format is locale-sensitive.** The date format `"Tuesday, September 15, 2026 at 9:00 AM"` works on US English macOS. If you change System Settings → Language & Region to a non-English locale, the AppleScript `date` coercion may fail. Documented in `README.md`.
- **One-time Automation permission prompt.** The first `launchctl load` triggers a macOS permission dialog. If clicked "Don't Allow", you have to re-enable it in System Settings.

---

## v0.2 recommendations

In rough priority order:

1. **Edit propagation** — when a vault `.md` is modified after initial push, query Calendar.app by `homunculus://event/<id>` URL and `set` the event properties. Medium complexity.
2. **Delete propagation** — when `.md` disappears, remove the Calendar entry. Needs a tombstone mechanism (can't read frontmatter from a deleted file); watchdog `on_deleted` event gives the path, so a pre-deletion cache or ID-from-filename heuristic would work.
3. **Rebuild state from Calendar.app** — on startup, query Calendar for all events whose URL starts with `homunculus://event/` and rebuild `pushed.jsonl` from that. Makes the bridge fully self-healing after a state file loss.
4. **Two-way sync** — Calendar.app edits propagate back to the vault. Most complex; requires polling Calendar or an EventKit native integration.

---

## Files delivered

```
Homunculus/mac_calendar_bridge/
├── README.md
├── pyproject.toml
├── src/mac_calendar_bridge/
│   ├── __init__.py          (VERSION = "0.1.0")
│   ├── config.py            (env vars, logging setup)
│   ├── vault_reader.py      (frontmatter parser → EventRecord)
│   ├── applescript.py       (osascript wrapper, date formatter)
│   ├── state.py             (pushed.jsonl idempotency)
│   └── watcher.py           (entry point, cold-boot sweep, watchdog)
├── tests/
│   ├── test_vault_reader.py (37 tests — parses Sep 15 + Sep 18 real events)
│   ├── test_state.py        (22 tests — persistence, thread safety)
│   ├── test_applescript.py  (29 tests — mocked osascript, date formatting)
│   └── test_watcher.py      (16 tests — push_if_new, sweep, handler)
├── deploy/
│   ├── com.homunculus.mac_calendar_bridge.plist  (plutil-linted OK)
│   └── install.sh
└── docs/
    └── FIRST_RUN.md
```
