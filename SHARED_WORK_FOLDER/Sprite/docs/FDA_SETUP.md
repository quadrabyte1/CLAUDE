# Full Disk Access Setup for Sprite

Sprite's watcher must read files from:

```
~/Library/Group Containers/group.com.apple.VoiceMemos.shared/Recordings/
```

This path is TCC-gated by macOS regardless of file ownership or sudo.
**Full Disk Access must be granted to the process that reads it.**

## Steps

1. **Open System Settings**
   → Privacy & Security → Full Disk Access

2. **Click the `+` button** (you may need to authenticate with Touch ID or password)

3. **Navigate to and add the watcher binary.** There are two candidates:
   - The shell script wrapper: `~/.local/bin/sprite_watcher.sh`
   - The Python interpreter it invokes: `~/.local/lib/sprite/venv/bin/python`

   **Add both to be safe.** macOS grants FDA to the process that makes the
   filesystem call — which is the Python interpreter, not the shell wrapper.
   If in doubt: add the Python binary first.

4. **Verify the path exists and is blocked** (before granting FDA):
   ```bash
   ls ~/Library/Group\ Containers/group.com.apple.VoiceMemos.shared/Recordings/
   # Expected: Operation not permitted
   ```

5. **After granting FDA**, verify it works:
   ```bash
   ls ~/Library/Group\ Containers/group.com.apple.VoiceMemos.shared/Recordings/
   # Expected: list of .m4a files (or empty if no memos synced yet)
   ```

6. **Load the launchd agent:**
   ```bash
   launchctl load ~/Library/LaunchAgents/com.sprite.watcher.plist
   ```

7. **Check it started:**
   ```bash
   launchctl list | grep sprite
   # Should show a PID next to com.sprite.watcher
   tail -50 /tmp/sprite_watcher.log
   ```

## Notes

- FDA is not inherited from the parent shell. The launchd agent runs as its own
  process and must have FDA granted directly.
- If you revoke FDA (System Settings → uncheck), the watcher will log a clear
  error and continue running (no crash loop), but will not process any memos.
- FDA is per-binary-path. If you reinstall the Python venv or move the binary,
  you must re-grant FDA.
- macOS stores FDA grants in the TCC database (`~/Library/Application Support/com.apple.TCC/TCC.db`).
  Do not modify this database manually.
