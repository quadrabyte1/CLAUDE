# mac_calendar_bridge v0.1.2 — Remove invalid `tell account`

**v0.1.2 — 2026-09-14 — Rune**

---

## Root cause

`tell account "iCloud"` is a **parse error** in Calendar.app's AppleScript
dictionary (`-2741: Expected end of line but found ""`). This construct exists
in Mail.app and Contacts.app, which model IMAP/CardDAV accounts explicitly.
Calendar.app treats all calendars — iCloud, local, subscriptions — as a single
flat namespace. There is no AppleScript way to scope to an account.

The v0.1.1 code wrapped every AppleScript call in `tell account "iCloud" ... end tell`.
Calendar.app rejected the wrapper immediately, exit 1, before any calendar operation
could run. launchd restarted every 10 seconds. Crash-loop.

---

## Red → Green story

**19 tests written RED against v0.1.1 code (in `tests/test_v012_no_account.py`),
then all 19 turned GREEN by the v0.1.2 patch.**

Key failing assertions before the fix:
- `ensure_calendar` still existed in `applescript.py` — AssertionError
- `verify_calendar_exists` not importable — ImportError
- `push_event` and `query_pushed_event_ids` scripts contained `tell account` — assertion fail
- Regression guard: `tell account` found in f-strings in source — fail
- `watcher.main()` with `verify_calendar_exists=False` did not exit — AttributeError
- `Config` still had `calendar_account` field — assertion fail

After the patch: **130 passed, 2 skipped** (the 2 skips are Linux-only platform
guards that skip on macOS by design — unchanged from v0.1.1).

---

## What changed

### `src/mac_calendar_bridge/applescript.py`
- Deleted `ensure_calendar()` entirely.
- Added `verify_calendar_exists(calendar_name: str) -> bool` — runs
  `tell application "Calendar" → return exists calendar "Homunculus"` and
  returns a `bool`. No `account_name` parameter. No `tell account` anywhere.
- Stripped `tell account "{account_name}"` wrapper from `push_event()` and
  `query_pushed_event_ids()`. Both now use `tell calendar "..."` directly.
- Removed `account_name` parameter from both functions.
- Updated module docstring to document the AppleScript limitation.

### `src/mac_calendar_bridge/config.py`
- Removed `calendar_account` field from `Config` dataclass.
- Removed `BRIDGE_CALENDAR_ACCOUNT` env var reading from `Config.from_env()`.

### `src/mac_calendar_bridge/watcher.py`
- Removed `ensure_calendar` import and call.
- Imported `verify_calendar_exists` instead.
- Startup sequence: calls `verify_calendar_exists(cfg.calendar_name)`; if
  `False`, logs the actionable error message and `sys.exit(1)`. launchd's
  `ThrottleInterval=10` handles backoff — no crash-loop.
- Removed `account_name` parameter from `push_if_new`, `VaultCalendarHandler`,
  `cold_boot_sweep`, and all call sites.
- Updated startup log line: `Calendar: Homunculus` (no "account: iCloud").

### `src/mac_calendar_bridge/__init__.py`
- `VERSION = "0.1.2"`

### `pyproject.toml`
- `version = "0.1.2"`

### `deploy/com.homunculus.mac_calendar_bridge.plist`
- Removed `BRIDGE_CALENDAR_ACCOUNT` entry and its comment block.
- `plutil -lint` passes.
- Updated IMPORTANT comment to reference the manual calendar creation step.

### `docs/FIRST_RUN.md`
- Rewritten: **Step 1 is now "Create the Homunculus calendar in iCloud via
  Calendar.app UI"** with exact clicks (File → New Calendar → iCloud → Homunculus).
- Added architecture note explaining why auto-create is impossible via AppleScript.
- Updated expected log output to v0.1.2 format.
- Updated troubleshooting table with the new "Calendar does not exist" entry.

### `README.md`
- Version bump to 0.1.2.
- Added "Key architecture decision (v0.1.2)" section explaining the flat-namespace
  constraint and why auto-create is gone.
- Removed `BRIDGE_CALENDAR_ACCOUNT` from the configuration table.
- Added v0.2 roadmap item for Swift/EventKit calendar creation.

### `tests/test_applescript.py`
- Removed import of deleted `ensure_calendar`.
- Removed all `TestEnsureCalendar*` and `TestConfigCalendarAccount` and
  `TestWatcherPlumbsCalendarAccount` classes (they tested the wrong behavior).
- Added `TestVerifyCalendarExists` and `TestConfigV012` replacing them.
- Retained all date-formatting, run_applescript, push_event, query tests.

### `tests/test_v012_no_account.py` (new)
- The TDD test file. 21 tests, all written RED first. Documents the exact contract.

---

## Migration steps for Thomas

**[You already did #1 and #2 in parallel — skip to #3]**

1. **[Done]** In Calendar.app, delete the stale local "Homunculus" calendar if
   it was created under "On My Mac" by an earlier bridge run.
2. **[Done]** Create a NEW "Homunculus" calendar: File → New Calendar → **iCloud**
   → type `Homunculus` → Return. Verify it appears under the "iCloud" heading
   in the Calendar sidebar (not "On My Mac").

3. Unload the bridge:
   ```bash
   launchctl unload ~/Library/LaunchAgents/com.homunculus.mac_calendar_bridge.plist
   ```

4. Clear the pushed state file (so the cold-boot sweep re-pushes everything
   into the correct iCloud calendar):
   ```bash
   rm -f ~/.local/share/mac_calendar_bridge/pushed.jsonl
   ```

5. Re-install (picks up new plist without `BRIDGE_CALENDAR_ACCOUNT`):
   ```bash
   bash /Volumes/GIT/CLAUDE/SHARED_WORK_FOLDER/Homunculus/mac_calendar_bridge/deploy/install.sh
   ```

6. Load the agent:
   ```bash
   launchctl load ~/Library/LaunchAgents/com.homunculus.mac_calendar_bridge.plist
   ```

7. Watch the log:
   ```bash
   tail -f /tmp/mac_calendar_bridge.log
   ```
   Expect: clean cold-boot, `Sweep found 2 event(s) in vault`, two "pushed event …" lines
   for Sept 15 and Sept 18. No `ERROR`. No crash-loop.

8. Confirm in Calendar.app that both events appear in the **iCloud → Homunculus** calendar.
   iCloud should sync them to iPhone within ~1 minute.

---

## v0.2 recommendation

The only way to programmatically create an iCloud calendar is via Swift +
EventKit (`EKCalendar.source` targeting the iCloud `EKSource`). This requires
`pyobjc-framework-EventKit` and is macOS-only. If Thomas wants to restore
auto-create behavior, that's the v0.2 implementation path. The current "user
creates once" model is simpler and gives Thomas explicit control over which
account the calendar lives in.
