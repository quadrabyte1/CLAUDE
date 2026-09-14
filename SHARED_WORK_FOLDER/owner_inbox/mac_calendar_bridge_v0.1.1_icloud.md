# mac_calendar_bridge v0.1.1 — iCloud sync fix

**v0.1.1 — 2026-09-14 — Rune**

---

## Root cause

AppleScript's `make new calendar with properties` and `tell calendar` both default to the **"On My Mac"** local store when no account is specified. v0.1.0 had no account scoping in any of its three AppleScript functions (`ensure_calendar`, `push_event`, `query_pushed_event_ids`), so the Homunculus calendar and all events landed in local storage — visible on the Mac only, invisible to iPhone / Watch / Siri.

The fix is one layer of nesting: wrap every Calendar.app AppleScript block in `tell account "iCloud"` (or whatever account name is configured via `BRIDGE_CALENDAR_ACCOUNT`).

---

## Red → Green

**13 new tests written RED first, then implementation, then GREEN.**

New tests in `tests/test_applescript.py`:

| Test class | What it asserts |
|---|---|
| `TestEnsureCalendarAccountScoping` | Script contains `tell account "iCloud"` and `make new calendar` appears after it |
| `TestPushEventAccountScoping` | Script contains `tell account "iCloud"` and `tell calendar` is nested inside it |
| `TestQueryPushedEventIdsAccountScoping` | Same nesting pattern for the query function |
| `TestRegressionGuardNoUnscoped` | Hard-asserts `make new calendar with properties` is always preceded by `tell account` — smoking-gun regression guard |
| `TestConfigCalendarAccount` | `Config.from_env()` defaults `calendar_account` to `"iCloud"`, reads `BRIDGE_CALENDAR_ACCOUNT`, treats empty string as `"iCloud"` |
| `TestWatcherPlumbsCalendarAccount` | `push_if_new()` accepts and forwards `account_name` to `push_event` |

Final run: **115 passed, 2 skipped** (the 2 skips are the Linux-platform guards that correctly skip on macOS). Zero regressions from the 102 pre-existing tests.

---

## What changed

| File | Change |
|---|---|
| `src/mac_calendar_bridge/applescript.py` | Added `account_name: str = "iCloud"` param to `ensure_calendar`, `push_event`, `query_pushed_event_ids`; all three scripts now wrap in `tell account "<name>"` |
| `src/mac_calendar_bridge/config.py` | Added `Config` frozen dataclass with `from_env()` class method; `calendar_account` field reads `BRIDGE_CALENDAR_ACCOUNT` env var with `"iCloud"` fallback |
| `src/mac_calendar_bridge/watcher.py` | `push_if_new`, `cold_boot_sweep`, `VaultCalendarHandler`, and `main()` all accept and forward `account_name`; `main()` now uses `Config.from_env()` |
| `src/mac_calendar_bridge/__init__.py` | `VERSION = "0.1.1"` |
| `pyproject.toml` | `version = "0.1.1"` |
| `README.md` | Version badge updated |
| `docs/FIRST_RUN.md` | Log sample updated to show account name in output |
| `deploy/com.homunculus.mac_calendar_bridge.plist` | Added explicit `BRIDGE_CALENDAR_ACCOUNT = iCloud` env var |
| `tests/test_applescript.py` | 13 new TDD tests |
| `tests/test_watcher.py` | Updated one side-effect lambda signature to accept `**kwargs` |

---

## Migration steps (do these in order)

### Step 1 — Delete the stale "On My Mac" Homunculus calendar

In Calendar.app sidebar, under **"On My Mac"**, find **Homunculus**.  
Right-click → **Delete** (or Ctrl+click → Delete).

This removes the 2 backfilled events that landed in local storage. The bridge will re-create them in iCloud after reinstall. Do this before step 3 to avoid name-collision ambiguity.

### Step 2 — Clear the bridge state file

The state file tracks which events have been pushed. Clearing it makes the bridge re-push all vault events from scratch on next start.

```bash
rm ~/.local/share/mac_calendar_bridge/pushed.jsonl
```

### Step 3 — Reinstall the bridge and bounce launchd

```bash
# Unload the current agent
launchctl unload ~/Library/LaunchAgents/com.homunculus.mac_calendar_bridge.plist

# Reinstall from the repo (re-installs the updated code into the boot-volume venv)
bash /Volumes/GIT/CLAUDE/SHARED_WORK_FOLDER/Homunculus/mac_calendar_bridge/deploy/install.sh

# Load the updated agent
launchctl load ~/Library/LaunchAgents/com.homunculus.mac_calendar_bridge.plist
```

### Step 4 — Confirm Automation permission (may not re-prompt)

macOS Automation grants are per-binary-signature. If `mac_calendar_bridge.sh` at `~/.local/bin/` hasn't changed on disk, the system won't re-prompt and the existing grant carries over.

If you see an "not permitted to send Apple events" error in `/tmp/mac_calendar_bridge.log`, go to **System Settings → Privacy & Security → Automation** and grant Terminal (or the relevant app) permission to control Calendar.

### Expected result (within ~30 seconds)

Watch the log:
```bash
tail -f /tmp/mac_calendar_bridge.log
```

You should see:
```
INFO  mac_calendar_bridge v0.1.1 starting
INFO  Calendar: Homunculus (account: iCloud)
INFO  Ensuring Calendar 'Homunculus' (account: iCloud) exists
INFO  Calendar 'Homunculus' ready
INFO  Pushing event 'meeting with myself' ...
INFO  Pushing event 'code review with myself' ...
INFO  Sweep complete: pushed 2 new event(s)
```

In Calendar.app sidebar, a **Homunculus** calendar appears under **iCloud** (not "On My Mac"). Both Sept 15 and Sept 18 events populate it. Within ~1 minute iCloud pushes them to iPhone / Watch / Siri.

---

## Configuration

To override the account name (e.g. if your iCloud account shows up as something other than "iCloud" in Calendar.app):

1. Edit `~/Library/LaunchAgents/com.homunculus.mac_calendar_bridge.plist`
2. Change the `BRIDGE_CALENDAR_ACCOUNT` value to your account name
3. Bounce the agent: `launchctl unload ... && launchctl load ...`

Or set it in the environment for testing:
```bash
BRIDGE_CALENDAR_ACCOUNT="My iCloud" mac-calendar-bridge
```

---

## What v0.2 should be

- **Two-way sync awareness:** detect when an event is deleted from Calendar.app and reflect that in the vault (or at minimum stop re-pushing it). Currently a delete in Calendar.app results in the bridge silently skipping the re-push (state file says "already pushed"), which leaves a vault event with no corresponding calendar entry.
- **Edit propagation:** when a vault `.md` file is modified (start time changed), update the existing Calendar.app event rather than silently ignoring it (state says "already pushed").
- **Account validation on startup:** query Calendar.app to verify the named account actually exists and emit a clear error (not a confusing AppleScript failure) if it doesn't.
- **systemd unit file:** Linux/NVIDIA migration readiness. The AppleScript layer is Mac-only, but having the service file ready means zero work on the supervision layer when the vault moves.
