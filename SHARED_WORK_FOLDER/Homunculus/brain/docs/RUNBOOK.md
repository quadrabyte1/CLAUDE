# Herman Runbook — v1.5.0

> **Herman (Homunculus brain) — Operations Reference**
> Updated: 2026-09-15 | Rune

This runbook covers day-to-day operations of Herman running as a supervised
launchd agent (macOS) or systemd user unit (Linux).

---

## Process management (macOS / launchd)

### Load (start at login + now)

```bash
launchctl load ~/Library/LaunchAgents/com.homunculus.brain.plist
```

### Unload (stop + remove from login)

```bash
launchctl unload ~/Library/LaunchAgents/com.homunculus.brain.plist
```

### Reload after plist or config change

```bash
launchctl unload ~/Library/LaunchAgents/com.homunculus.brain.plist
launchctl load   ~/Library/LaunchAgents/com.homunculus.brain.plist
```

### Check status

```bash
launchctl list | grep homunculus
```

Expected output (PID in first column means running):
```
<PID>   0   com.homunculus.brain
```

If the first column is `-`, Herman has exited. Check `/tmp/homunculus_brain_err.log`.

### Restart (crash-safe)

launchd will restart Herman automatically (ThrottleInterval=10s). To force
a manual restart:

```bash
launchctl unload ~/Library/LaunchAgents/com.homunculus.brain.plist
launchctl load   ~/Library/LaunchAgents/com.homunculus.brain.plist
```

---

## Process management (Linux / systemd)

```bash
# Start
systemctl --user start homunculus-brain

# Stop
systemctl --user stop homunculus-brain

# Restart
systemctl --user restart homunculus-brain

# Enable at login (linger must be enabled: loginctl enable-linger $USER)
systemctl --user enable homunculus-brain

# Check status
systemctl --user status homunculus-brain
```

---

## Log locations

| Platform | stdout | stderr |
|----------|--------|--------|
| macOS (launchd) | `/tmp/homunculus_brain.log` | `/tmp/homunculus_brain_err.log` |
| Linux (systemd) | `journalctl --user -u homunculus-brain` | same journal |

```bash
# macOS — tail both
tail -f /tmp/homunculus_brain.log
tail -f /tmp/homunculus_brain_err.log

# Linux
journalctl --user -u homunculus-brain -f
```

---

## Health check

```bash
curl http://localhost:8765/health
```

Expected response (v1.5.0):

```json
{
  "status": "ok",
  "design_version": "1.5",
  "package_version": "1.5.0",
  "vault_path": "/Volumes/GIT/CLAUDE/SHARED_WORK_FOLDER/Homunculus/vault"
}
```

Two things to verify here:
1. `package_version` should match the installed release.
2. `vault_path` should point at the real vault on the external volume, NOT a
   path inside miniconda's site-packages. If you see a miniconda path here,
   `HOMUNCULUS_VAULT` is not set — see the vault-path bug note below.

## Diagnostic (Ollama check)

```bash
curl http://localhost:8765/diagnostic
```

This endpoint pings Ollama with a 1-token request and reports model-resident
status. Slower than `/health` — don't poll it; use it for one-off checks.

---

## Changing the vault path

The vault path is set via `HOMUNCULUS_VAULT` in the plist (macOS) or service
unit (Linux). To move the vault:

1. Stop Herman.
2. Move the vault directory: `mv /old/vault /new/vault`
3. Edit the plist: `nano ~/Library/LaunchAgents/com.homunculus.brain.plist`
   Change the `HOMUNCULUS_VAULT` string to the new path.
4. Reload: `launchctl load ~/Library/LaunchAgents/com.homunculus.brain.plist`
5. Verify: `curl http://localhost:8765/health` — confirm `vault_path` is the new path.

### The vault-path bug (2026-09-13)

When `homunculus-brain` is installed via pip into miniconda, the package's
`config.py` computes the default vault as:

```python
_DEFAULT_VAULT = Path(__file__).resolve().parents[2] / "vault"
```

`__file__` resolves to somewhere inside miniconda's site-packages. `parents[2]`
walks up two levels — also inside miniconda. The resulting path is wrong and
silently creates a `vault/` inside the Python prefix.

**The fix:** always set `HOMUNCULUS_VAULT` explicitly in the process environment.
The deploy plist and service unit both set it. If you ever launch Herman manually
(e.g., for testing), set it in your shell first:

```bash
export HOMUNCULUS_VAULT=/Volumes/GIT/CLAUDE/SHARED_WORK_FOLDER/Homunculus/vault
homunculus-brain
```

---

## Swapping the Ollama model

Herman loads the model name from `OLLAMA_MODEL` at startup. To change it:

1. Pull the new model: `ollama pull qwen2.5:14b` (or whichever model)
2. Edit the plist `OLLAMA_MODEL` value.
3. Reload Herman (the old model is evicted from Ollama automatically when the
   new one loads — Ollama keeps one model resident).
4. Verify intent parsing still works: `curl -X POST http://localhost:8765/capture/text -H 'Content-Type: application/json' -d '{"text":"test note","captured_at":null,"speaker_tz":null}'`

Model options tested against the boss's utterance corpus:
- `qwen2.5:7b` — primary, fits 16 GB Mac mini M4, strong JSON schema compliance
- `qwen2.5:14b` — for 32 GB+ machines; better on edge cases
- `llama3.1:8b` — alternative, weaker schema compliance but good recall
- `mistral:7b` — baseline comparison only; not recommended for production

---

## Linux migration checklist

When the brain moves to a Linux box (expected: NVIDIA GPU, vLLM serving):

1. **Python environment**: install miniconda or use a virtualenv at
   `/opt/miniconda3` (or adjust `ExecStart` in the service unit).

2. **Install the package**:
   ```bash
   pip install -e /path/to/Homunculus/brain
   ```

3. **Install the service unit**:
   ```bash
   cp deploy/homunculus-brain.service ~/.config/systemd/user/
   systemctl --user daemon-reload
   systemctl --user enable homunculus-brain
   ```

4. **Set HOMUNCULUS_VAULT** in the service unit (or drop-in) to point at
   wherever the vault lives on Linux.

5. **Ollama on Linux**: install from `https://ollama.com/download/linux`.
   Pull the model: `ollama pull qwen2.5:7b`.

6. **vLLM swap (NVIDIA)**: when you switch from Ollama to vLLM:
   - Update `OLLAMA_BASE_URL=http://localhost:8000/v1` in the service unit.
   - Note: the brain's LLM client currently uses the Ollama-native `/api/generate`
     path. A config toggle (`HOMUNCULUS_LLM_BACKEND=openai`) to switch to
     `/v1/chat/completions` is tracked in the Herman backlog (BRAIN-LLM-BACKEND).
     Until that ships, run Ollama as a vLLM shim or patch `llm.py`.

7. **Linger** (so systemd user units survive logout):
   ```bash
   loginctl enable-linger $USER
   ```

8. **iCloud / TCC**: not applicable on Linux. The vault is a plain directory.

9. **Ollama port**: default `11434` matches the plist. No change needed unless
   you move Ollama to a different host.

---

## Common failure modes

| Symptom | Likely cause | Fix |
|---------|-------------|-----|
| `launchctl list` shows `-` for PID | Herman crashed at startup | Check `/tmp/homunculus_brain_err.log` |
| `/health` returns wrong `vault_path` (miniconda path) | `HOMUNCULUS_VAULT` not set | Set it in plist, reload |
| `/capture/text` falls back to heuristic every time | Ollama unreachable | `curl http://localhost:11434/api/tags` to confirm; `ollama serve` if not running |
| Port 8765 already in use on load | Old nohup Herman still running | `pkill -f homunculus-brain`, then reload |
| Sprite 404s on `/capture/parsed` | Herman not running | Reload plist, check health |
| Reminder schedule empty | Vault path wrong (vault-path bug) | Verify `vault_path` in `/health` output |

---

## Version history (deploy assets)

| Version | Date | Notes |
|---------|------|-------|
| v1.4.0 | 2026-09-13 | Initial launchd agent + systemd unit. Fixes vault-path bug by setting HOMUNCULUS_VAULT explicitly. |
| v1.5.0 | 2026-09-15 | Activity dashboard at /dashboard/. Read-only JSONL feed, auto-refresh every 5 s, ?since= incremental poll. No new dependencies. |
