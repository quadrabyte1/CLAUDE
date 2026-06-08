# Keeping the Mac mini awake for Homunculus

The brain is a foreground process on the Mac mini. If the Mac goes to sleep,
requests from the phone (over Tailscale) queue or time out until it wakes.
The boss has elected to disable sleep on AC power.

## One-time setup (recommended)

Run these in Terminal. They require an admin password.

```bash
# Never sleep the system on AC power.
sudo pmset -c sleep 0

# Allow the display to sleep on its own — that's fine, the brain still runs.
sudo pmset -c displaysleep 30

# Wake when the network sends a magic packet (helps if the Mac ever does sleep).
sudo pmset -c womp 1
```

Verify with:

```bash
pmset -g custom
```

Look for `sleep 0` and `displaysleep 30` under the AC profile.

## Reversing the change later

```bash
sudo pmset -c sleep 30        # or whatever the default was
sudo pmset -c displaysleep 10
```

## Immediate session alternative (no admin needed)

If you ever want the Mac to *not sleep right now* without changing the
defaults — say you're running a long task and the change is temporary:

```bash
caffeinate -dimsu &
```

That keeps display, idle, and system sleep all suppressed until you kill
the process (`kill %1` or close the Terminal). It's the per-session hammer.

## Keeping the brain process itself alive

Disabling sleep keeps the *Mac* awake, but the `homunculus-brain` process
also has to stay running. Three options, easiest to most-correct:

### Option A — a Terminal window with `nohup` (quick + dirty)

```bash
cd ~/path/to/Homunculus/brain
nohup homunculus-brain > ~/Library/Logs/homunculus-brain.log 2>&1 &
disown
```

Survives the Terminal closing. Doesn't survive reboot.

### Option B — a LaunchAgent (recommended)

Create `~/Library/LaunchAgents/com.homunculus.brain.plist`:

```xml
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN"
  "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
  <key>Label</key>                <string>com.homunculus.brain</string>
  <key>ProgramArguments</key>     <array>
    <string>/opt/miniconda3/bin/homunculus-brain</string>
  </array>
  <key>RunAtLoad</key>            <true/>
  <key>KeepAlive</key>            <true/>
  <key>StandardOutPath</key>      <string>/tmp/homunculus-brain.log</string>
  <key>StandardErrorPath</key>    <string>/tmp/homunculus-brain.err</string>
  <key>EnvironmentVariables</key> <dict>
    <key>HOMUNCULUS_VAULT</key>   <string>/Volumes/GIT/CLAUDE/SHARED_WORK_FOLDER/Homunculus/vault</string>
    <key>OLLAMA_MODEL</key>       <string>qwen2.5:7b</string>
  </dict>
</dict>
</plist>
```

Load it:

```bash
launchctl load ~/Library/LaunchAgents/com.homunculus.brain.plist
```

Now the brain starts at login and is auto-restarted if it crashes.
Unload it with `launchctl unload <path>`.

(Substitute the actual `homunculus-brain` script path you get from
`which homunculus-brain` after `pip install` finishes.)

### Option C — tmux or screen

Run `homunculus-brain` inside a `tmux` session so it lives independently
of the Terminal. Good for development, less good for unattended uptime.
