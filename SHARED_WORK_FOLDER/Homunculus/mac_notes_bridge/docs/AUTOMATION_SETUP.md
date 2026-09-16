# Automation Permission Setup — mac_notes_bridge

**v0.1.0** — 2026-09-15

This document describes how to grant the mac_notes_bridge process Automation
permission to control Notes.app on macOS.

---

## Why this is required

macOS's TCC (Transparency, Consent, and Control) framework requires explicit
user permission for any app or daemon to control Notes.app via AppleScript.
The bridge uses `osascript` to create notes via AppleScript, so it needs
Automation permission for Notes.app.

---

## Option A: Let macOS prompt you (recommended)

1. Load the launchd plist (see FIRST_RUN.md Step 3).
2. On first run, macOS shows a dialog:
   > "[process] wants access to control 'Notes'. Allowing control will provide
   > access to documents and data in 'Notes'."
3. Click **OK**.

That's it. The bridge will start working immediately.

---

## Option B: Pre-grant in System Settings

1. Open **System Settings → Privacy & Security → Automation**
2. Scroll to find the process running the bridge (Terminal, or the
   `mac_notes_bridge.sh` process itself if it appears)
3. Under that process, toggle **Notes** to **on**

---

## If you accidentally denied the prompt

1. Open **System Settings → Privacy & Security → Automation**
2. Find the `mac_notes_bridge` process (or Terminal)
3. Enable **Notes** access
4. Restart the bridge:
   ```bash
   launchctl unload ~/Library/LaunchAgents/com.homunculus.mac_notes_bridge.plist
   launchctl load   ~/Library/LaunchAgents/com.homunculus.mac_notes_bridge.plist
   ```

---

## Checking the log for permission errors

```bash
tail -f /tmp/mac_notes_bridge.log
```

Look for:
- `osascript exited 1: not allowed` — Automation permission denied
- `Failed to verify Notes folder` — Notes.app cannot be reached at all

Both indicate a permission issue — grant Automation access and restart.
