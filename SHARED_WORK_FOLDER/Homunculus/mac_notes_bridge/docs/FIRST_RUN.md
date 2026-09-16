# mac_notes_bridge — First Run Guide

**v0.1.0** — 2026-09-15

This document covers the steps required to go from a fresh install to seeing
Herman vault notes appear in Notes.app.

---

## Prerequisites

- macOS (the bridge is Mac-only; Notes.app is required)
- Python 3.11 or later (check with `python3 --version`)
- The repo checked out at `/Volumes/GIT/CLAUDE/SHARED_WORK_FOLDER/Homunculus/`

---

## Step 1: Create the "Homunculus" folder in Notes.app under iCloud (REQUIRED — do this first)

The bridge does **not** create the folder automatically. You must create it
manually, once, under the iCloud account.

1. Open **Notes.app**
2. In the sidebar, look for the **iCloud** account heading
3. Either click the **+** folder icon next to "iCloud", or choose
   **File → New Folder**
4. When prompted for the account, select **iCloud** (not "On My Mac")
5. Name the folder exactly: **`Homunculus`**
6. Press **Return**

Verify: in the Notes sidebar you should see "Homunculus" listed under the
**iCloud** heading (not under "On My Mac").

> If you see "Homunculus" under "On My Mac" instead, delete it and repeat
> Step 1, making sure to put it under iCloud.

---

## Step 2: Run the installer

```bash
cd /Volumes/GIT/CLAUDE/SHARED_WORK_FOLDER/Homunculus/mac_notes_bridge
bash deploy/install.sh
```

This installs the bridge into a venv at `~/.local/lib/mac_notes_bridge/venv/`
and writes an entry-point script at `~/.local/bin/mac_notes_bridge.sh`.
It also copies the launchd plist to `~/Library/LaunchAgents/` but does **not**
load it yet.

---

## Step 3: Load the launchd agent

```bash
launchctl load ~/Library/LaunchAgents/com.homunculus.mac_notes_bridge.plist
```

On first load, macOS may show an Automation permission dialog:

> "mac_notes_bridge" wants access to control "Notes". Allowing control will
> provide access to documents and data in "Notes", and to perform actions
> within that app.

Click **OK**.

If you missed the prompt or accidentally denied it:
- Open **System Settings → Privacy & Security → Automation**
- Find `mac_notes_bridge` or `Terminal` and enable Notes access
- Then restart the bridge:
  ```bash
  launchctl unload ~/Library/LaunchAgents/com.homunculus.mac_notes_bridge.plist
  launchctl load   ~/Library/LaunchAgents/com.homunculus.mac_notes_bridge.plist
  ```

---

## Step 4: Verify it started

```bash
launchctl list | grep mac_notes_bridge
```

Watch the log:
```bash
tail -f /tmp/mac_notes_bridge.log
```

Expected first-run output:
```
2026-09-15T... INFO     [mac_notes_bridge] mac_notes_bridge v0.1.0 starting
2026-09-15T... INFO     [mac_notes_bridge] Vault: .../vault/notes
2026-09-15T... INFO     [mac_notes_bridge] Notes folder: Homunculus
2026-09-15T... INFO     [mac_notes_bridge] Notes account: iCloud
2026-09-15T... INFO     [mac_notes_bridge] Cold-boot sweep of .../vault/notes
2026-09-15T... INFO     [mac_notes_bridge] Sweep found 4 note(s) in vault
2026-09-15T... INFO     [mac_notes_bridge] Pushing note 'test notes mechanism' (vault filename: '2026-09-15-test-notes-mechanism.md') → Notes folder 'Homunculus'
2026-09-15T... INFO     [mac_notes_bridge] Note '2026-09-15-test-notes-mechanism' pushed successfully
... (3 more notes)
2026-09-15T... INFO     [mac_notes_bridge] Sweep complete: pushed 4 new note(s)
2026-09-15T... INFO     [mac_notes_bridge] Watching .../vault/notes (recursive) …
```

---

## Step 5: Open Notes.app

You should now see a **Homunculus** folder under the **iCloud** heading in
the sidebar, with your vault notes inside. Within a minute, iCloud syncs
to your iPhone.

---

## Troubleshooting

| Symptom | Likely cause | Fix |
|---------|-------------|-----|
| Log says "Notes folder 'Homunculus' does not exist" and bridge exits | Folder not created yet | Complete Step 1 — create "Homunculus" under iCloud in Notes.app UI, then reload |
| Notes appear under "On My Mac" instead of iCloud | Folder was created under wrong account | Delete the "On My Mac" Homunculus folder, redo Step 1 choosing iCloud |
| Notes not appearing in Notes.app | Automation permission denied | System Settings → Privacy → Automation → enable Notes |
| `osascript exited 1: not allowed` in log | Same as above | Same fix |
| Bridge exits immediately | Python version < 3.11, or venv not built | Re-run `install.sh` with the correct Python |
| Log file empty | Bridge not started or wrong plist path | Check `launchctl list | grep mac_notes_bridge` |
| Notes don't sync to iPhone | "Homunculus" folder is not in iCloud | Check Notes.app sidebar — must be under "iCloud" heading |
| Duplicate notes appearing | pushed.jsonl was wiped | The slow-path query (title matching) should prevent this; check the log for self-heal messages |

---

## Backfilling existing notes

If notes were written to the vault before the bridge was installed, the
cold-boot sweep (Step 3) handles backfill automatically. Every note `.md` file
under `vault/notes/` that has not yet been pushed will be pushed on startup.

---

## Unloading the bridge

```bash
launchctl unload ~/Library/LaunchAgents/com.homunculus.mac_notes_bridge.plist
```

---

## Architecture note (why manual folder creation?)

Notes.app's AppleScript dictionary has an `account` concept (unlike Calendar.app),
so `tell account "iCloud"` is valid and works. However, programmatically creating
a folder in a specific account from AppleScript is unreliable across Notes.app
versions — the user-creation path is simpler and guaranteed to put the folder
in the right place. This is the same pattern established for the Calendar bridge.
