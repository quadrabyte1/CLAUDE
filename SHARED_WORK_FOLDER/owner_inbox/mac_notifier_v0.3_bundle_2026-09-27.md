# mac_notifier v0.3 — Homunculus Notifier.app Bundle

**v0.3 · 2026-09-27 · Rune**

---

## What changed

Notifications now appear as **"Homunculus Notifier"** in the macOS Notification Center tray instead of "Script Editor". This was the v0.3 goal: correct notification branding via a proper `.app` bundle with bundle ID `com.homunculus.notifier`.

---

## Install (one-time)

```bash
# 1. Build and install the .app bundle (Swift compiler required — already present)
cd /Volumes/GIT/CLAUDE/SHARED_WORK_FOLDER/Homunculus/mac_notifier
bash deploy/install_bundle.sh

# 2. Re-install the launchd agent to pick up the updated plist comment
#    (no behavior change — bundle is auto-detected at runtime)
bash deploy/install.sh

# 3. Reload the launchd agent
launchctl unload ~/Library/LaunchAgents/com.homunculus.mac_notifier.plist
launchctl load  ~/Library/LaunchAgents/com.homunculus.mac_notifier.plist
```

On first notification after install, macOS will prompt:
> **"Homunculus Notifier" Would Like to Send You Notifications**

Go to **System Settings → Notifications → Homunculus Notifier** and click **Allow**.

---

## Manual verify (send yourself a test notification)

```bash
~/Applications/Homunculus\ Notifier.app/Contents/MacOS/notifier \
    "Herman is running. v0.3 bundle test." \
    "Homunculus v0.3 test" \
    "Homunculus" \
    "default"
```

**Expected:** notification banner appears labelled **"Homunculus Notifier"** — not "Script Editor".

---

## How the dispatch works

```
fire_notification_with_fallback()   ← new call site in applescript.py
  │
  ├─ terminal-notifier installed?   → terminal-notifier -sender com.homunculus.notifier
  │  (brew install terminal-notifier)
  │
  ├─ bundle installed?              → ~/Applications/Homunculus Notifier.app/
  │  (deploy/install_bundle.sh)        Contents/MacOS/notifier <body> <subtitle>
  │
  └─ neither                        → osascript fallback (Script Editor branding,
                                       but functional — was v0.1/v0.2 behavior)
```

Since `terminal-notifier` is **not installed**, the active path on Thomas's machine is the Swift stub inside the bundle.

---

## Files added / changed

| File | Status | Notes |
|------|--------|-------|
| `src/mac_notifier/bundle.py` | **New** | `find_bundle_app()`, `fire_via_bundle()`, `BundleError` |
| `src/mac_notifier/applescript.py` | Updated | Added `fire_notification_with_fallback()` |
| `src/mac_notifier/poller.py` | Updated | Uses `fire_notification_with_fallback` + catches `BundleError` |
| `src/mac_notifier/__init__.py` | Updated | VERSION = "0.3.0" |
| `pyproject.toml` | Updated | version = "0.3.0" |
| `deploy/install_bundle.sh` | **New** | Compiles Swift stub, assembles .app, validates plist |
| `deploy/notifier_stub/notifier.swift` | **New** | Swift CLI stub (UserNotifications framework) |
| `deploy/notifier_stub/Info.plist` | **New** | Bundle metadata (bundle ID: com.homunculus.notifier) |
| `deploy/com.homunculus.mac_notifier.plist` | Updated | v0.3.0 comment; removed v0.1 caveat note |
| `tests/test_bundle.py` | **New** (pre-staged) | 16 tests for bundle.py |
| `tests/test_applescript_v03.py` | **New** | 7 tests for fire_notification_with_fallback() |
| `tests/test_poller.py` | Updated | Mock updated: fire_notification → fire_notification_with_fallback |

---

## Test results

```
151 passed in 0.08s  (was 128 before v0.3 — +23 new tests)
```

All 151 pass. No real subprocess calls in tests — all shelling mocked per house rule.

---

## Bundle structure on disk (after install)

```
~/Applications/Homunculus Notifier.app/
└── Contents/
    ├── Info.plist          bundle ID: com.homunculus.notifier
    ├── MacOS/
    │   └── notifier        Swift binary (compiled from deploy/notifier_stub/notifier.swift)
    └── Resources/          reserved for future icon + localization
```

---

## Fallback behavior (no bundle installed)

If `install_bundle.sh` has not been run yet, `fire_notification_with_fallback()` logs:

```
INFO  Bundle not available — falling back to osascript (notifications will show as 'Script Editor'). Run deploy/install_bundle.sh to fix.
```

and falls back to the v0.1/v0.2 osascript path. Notifications still fire and sound; only the app name is wrong. No crashes, no missing notifications.

---

## What was NOT changed

- Herman brain (`Homunculus/brain/`) — untouched
- Sprite — untouched
- Herman `VERSION` — untouched (owned by parallel Rune agent on task 636)
- mac_calendar_bridge, mac_notes_bridge — untouched
- No commits/pushes made
