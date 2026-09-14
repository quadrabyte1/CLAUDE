# Herman v1.4.0 — launchd Agent Deployment

> **v1.4.0 — 2026-09-13 — Rune**

---

## What ships

| File | Purpose |
|------|---------|
| `Homunculus/brain/deploy/com.homunculus.brain.plist` | macOS launchd LaunchAgent — `KeepAlive=true`, `RunAtLoad=true`, `ThrottleInterval=10`, env vars incl. explicit `HOMUNCULUS_VAULT` |
| `Homunculus/brain/deploy/homunculus-brain.service` | systemd user unit — Linux migration / portability religion |
| `Homunculus/brain/deploy/install.sh` | Cross-platform install script; `--dry-run` mode; runs `plutil -lint` on the plist before printing load instructions |
| `Homunculus/brain/deploy/README.md` | Deploy quick-start (version badge upper-left) |
| `Homunculus/brain/docs/RUNBOOK.md` | Operations reference: load/unload, logs, health check, vault-path bug note, model swap, Linux migration checklist |
| `Homunculus/brain/pyproject.toml` | Version bumped 1.3.1 → 1.4.0 |
| `Homunculus/brain/homunculus_brain/__init__.py` | `VERSION = "1.4.0"`, `DESIGN_VERSION = "1.4"` |
| `Homunculus/brain/README.md` | v1.4.0 status entry added; Install section updated with supervised-service path |

---

## Thomas's exact cutover steps

You currently have Herman running as:
```
nohup /opt/miniconda3/bin/homunculus-brain > /tmp/homunculus_brain.log 2>&1 &
```

Here's the migration — five commands:

```bash
# 1. Stop the nohup Herman
pkill -f homunculus-brain

# 2. Confirm Ollama is running and qwen2.5:7b is resident
curl http://localhost:11434/api/tags | grep qwen2.5

# 3. Run the installer (does not load yet — just installs + copies plist)
bash /Volumes/GIT/CLAUDE/SHARED_WORK_FOLDER/Homunculus/brain/deploy/install.sh

# 4. Load the LaunchAgent (launchd owns Herman from this point forward)
launchctl load ~/Library/LaunchAgents/com.homunculus.brain.plist

# 5. Verify
launchctl list | grep homunculus
curl http://localhost:8765/health
```

Step 3 will print the plist destination and confirm `plutil -lint` passes before giving you the load command. You can also run step 3 with `--dry-run` first to see what it would do without changing anything:

```bash
bash /Volumes/GIT/CLAUDE/SHARED_WORK_FOLDER/Homunculus/brain/deploy/install.sh --dry-run
```

---

## Sanity check after cutover

```bash
curl http://localhost:8765/health
```

Should return:
```json
{
  "status": "ok",
  "design_version": "1.4",
  "package_version": "1.4.0",
  "vault_path": "/Volumes/GIT/CLAUDE/SHARED_WORK_FOLDER/Homunculus/vault"
}
```

Two things to confirm:
- `package_version` is `1.4.0`
- `vault_path` is the real vault on the external volume, NOT a path inside miniconda

If `vault_path` shows a miniconda path, the plist is not the one that was copied by `install.sh`. Check `~/Library/LaunchAgents/com.homunculus.brain.plist` directly.

---

## The vault-path bug (why this matters)

When `homunculus-brain` is pip-installed into miniconda, `config.py` computes:

```python
_DEFAULT_VAULT = Path(__file__).resolve().parents[2] / "vault"
```

`__file__` is inside miniconda's site-packages. Walking up two parents puts you inside the miniconda prefix. The resulting path is wrong, silent, and hard to notice until you realize no events are being written where you expect.

This hit us on 2026-09-13 and was fixed manually before the first Sprite→Herman live capture. The plist sets `HOMUNCULUS_VAULT` explicitly to prevent recurrence. The RUNBOOK documents it so future readers don't fall into the same pit.

---

## Log locations (post-cutover)

```bash
tail -f /tmp/homunculus_brain.log       # stdout
tail -f /tmp/homunculus_brain_err.log   # stderr
```

Same paths as the nohup command was using. No log location change.

---

## Unload / reload if needed

```bash
# Unload (stops Herman)
launchctl unload ~/Library/LaunchAgents/com.homunculus.brain.plist

# Reload after a config change (edit the plist, then:)
launchctl unload ~/Library/LaunchAgents/com.homunculus.brain.plist
launchctl load   ~/Library/LaunchAgents/com.homunculus.brain.plist
```

---

## What M5 should be — Rune's recommendation

**M5: Tailnet exposure + auth middleware**

The brain is now properly supervised. The next architectural risk is exposure.
Today, Tailscale is the only trust boundary — no endpoint-level auth. That's
fine for a single-user, single-tailnet setup, but one step toward sharing the
brain (e.g., Kit running tests against it from their own machine) requires a
bearer-token middleware.

M5 should deliver:
1. A `HOMUNCULUS_BEARER_TOKEN` env var (set in the plist, not hardcoded).
2. A FastAPI middleware that checks `Authorization: Bearer <token>` on all
   `/capture/*`, `/events`, `/reminders/*`, and `/ack` routes.
3. `/health` stays unauthenticated (so launchd can health-check cheaply).
4. Updated `docs/RUNBOOK.md` with the token setup step.
5. Kit-side: add the token to `BrainClient.swift`'s request headers.

This is one PR's worth of work. The middleware skeleton is already implicit in
the comment at the top of `server.py` ("if Homunculus is ever exposed to a
larger network, add a bearer token here first"). M5 makes that comment
unnecessary by making it true.

Secondary candidate for M5: the `BRAIN-LLM-BACKEND` config toggle
(`HOMUNCULUS_LLM_BACKEND=openai`) to switch the LLM client from Ollama's
`/api/generate` to `/v1/chat/completions`. This is the last remaining code
change needed for the Linux/vLLM migration path to be config-only.

---

## Memory update block (copy-paste for `project_homunculus.md`)

```
[Herman v1.4.0 — 2026-09-13]
Deployment infrastructure milestone. Herman now runs as a launchd LaunchAgent
(com.homunculus.brain) — survives reboots, restarts on crash (ThrottleInterval=10s).
Matching systemd unit ships day-of (portability religion).
Cross-platform install.sh with --dry-run mode.
Fixes vault-path bug: HOMUNCULUS_VAULT set explicitly in plist.
Docs: deploy/README.md, docs/RUNBOOK.md (load/unload, logs, health, model swap, Linux migration).
No wire-protocol changes. 87 tests pass.
M5 candidate: bearer-token middleware + BRAIN-LLM-BACKEND toggle.
```

---

## Task closure

Task 528 (Herman v1.4.0 launchd) — closed in `db/workspace.db`. See activity_log entry dated 2026-09-13.
