# Herman Deploy — v1.4.0

> **Herman (Homunculus brain) v1.4.0 — 2026-09-13**
> Process supervision assets: launchd (macOS) + systemd (Linux).

## Files

| File | Purpose |
|------|---------|
| `com.homunculus.brain.plist` | macOS launchd LaunchAgent |
| `homunculus-brain.service` | Linux systemd user unit |
| `install.sh` | Cross-platform install helper |

## Quick start (macOS)

```bash
# 1. Run the installer (does not load the plist)
bash deploy/install.sh

# 2. Confirm Ollama is running and qwen2.5:7b is resident
curl http://localhost:11434/api/tags | grep qwen2.5

# 3. Stop the current nohup Herman if one is running
pkill -f homunculus-brain   # or: kill <PID from nohup>

# 4. Load the LaunchAgent
launchctl load ~/Library/LaunchAgents/com.homunculus.brain.plist

# 5. Verify
launchctl list | grep homunculus
curl http://localhost:8765/health
```

The `/health` response should show `package_version: "1.4.0"` and the correct `vault_path`.

## Migrating from nohup

If Herman is currently running as a nohup process:

1. Find the PID: `ps aux | grep homunculus-brain`
2. Kill it: `kill <PID>` (or `pkill -f homunculus-brain`)
3. Run `bash deploy/install.sh`
4. `launchctl load ~/Library/LaunchAgents/com.homunculus.brain.plist`

From this point launchd owns the process — it will restart Herman on crash and bring it up at login.

## Linux / NVIDIA migration

See `docs/RUNBOOK.md` section "Linux migration" for the full checklist including the Ollama-to-vLLM swap path.

## Dry-run mode

```bash
bash deploy/install.sh --dry-run
```

Prints every step that would be taken without writing any files or installing anything.

## Configuration

All configuration is via environment variables declared in the plist (macOS) or the service unit (Linux). See `README.md` in the brain root for the full env-var table.

The one env var you must always set explicitly:

```
HOMUNCULUS_VAULT=/Volumes/GIT/CLAUDE/SHARED_WORK_FOLDER/Homunculus/vault
```

Without it, the pip-installed Herman defaults to a path inside the Python prefix (miniconda site-packages) — which is wrong and silent. This is the vault-path bug that bit us on 2026-09-13; the plist and service unit both set it explicitly to prevent recurrence.
