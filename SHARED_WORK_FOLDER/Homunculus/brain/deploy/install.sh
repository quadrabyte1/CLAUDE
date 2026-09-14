#!/bin/bash
# Homunculus brain v1.4.0 install script
#
# Installs Herman (homunculus-brain) as a supervised process via launchd
# (macOS) or prints instructions for systemd (Linux).
#
# Usage:
#   bash deploy/install.sh             # full install
#   bash deploy/install.sh --dry-run   # print what would happen, do nothing
#
# What this does:
#   1. Installs the homunculus-brain package into miniconda (pip install -e)
#   2. On macOS: copies the plist to ~/Library/LaunchAgents/ but does NOT load
#      it — you load it manually after confirming Ollama is up.
#   3. On Linux: prints the systemd commands.
#   4. Checks that Ollama is reachable and prints a warning if not.
#
# Portability: pure bash, no Mac-only tools except the Darwin-gated launchd
# section. On Linux only the systemd section runs.

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
BRAIN_REPO="$(dirname "$SCRIPT_DIR")"

# ---------------------------------------------------------------------------
# Flags
# ---------------------------------------------------------------------------

DRY_RUN=false
for arg in "$@"; do
    if [[ "$arg" == "--dry-run" ]]; then
        DRY_RUN=true
    fi
done

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------

# Herman lives under miniconda — different from Sprite, which uses its own
# venv. The two are deliberately kept independent so they can drift Python
# versions and model dependencies without breaking each other.
MINICONDA_BIN="${MINICONDA_BIN:-/opt/miniconda3/bin}"
PIP="${MINICONDA_BIN}/pip"
HOMUNCULUS_BRAIN_BIN="${MINICONDA_BIN}/homunculus-brain"

PLIST_SRC="${SCRIPT_DIR}/com.homunculus.brain.plist"
SERVICE_SRC="${SCRIPT_DIR}/homunculus-brain.service"

PLIST_DST="${HOME}/Library/LaunchAgents/com.homunculus.brain.plist"

OLLAMA_URL="${OLLAMA_BASE_URL:-http://localhost:11434}"

# ---------------------------------------------------------------------------
# Helper: print + optionally execute
# ---------------------------------------------------------------------------

run() {
    echo "[install] $*"
    if [[ "$DRY_RUN" == false ]]; then
        "$@"
    fi
}

info() {
    echo "[install] $*"
}

# ---------------------------------------------------------------------------
# Dry-run banner
# ---------------------------------------------------------------------------

if [[ "$DRY_RUN" == true ]]; then
    echo "======================================================================"
    echo "  DRY RUN — no changes will be made"
    echo "======================================================================"
    echo ""
fi

# ---------------------------------------------------------------------------
# 1. Verify miniconda pip is present
# ---------------------------------------------------------------------------

info "Checking for miniconda pip at ${PIP} ..."
if [[ "$DRY_RUN" == false ]] && [[ ! -x "$PIP" ]]; then
    echo ""
    echo "[install] ERROR: pip not found at ${PIP}"
    echo "  If miniconda is installed elsewhere, set:"
    echo "    MINICONDA_BIN=/path/to/miniconda/bin bash deploy/install.sh"
    exit 1
fi
if [[ "$DRY_RUN" == true ]]; then
    info "Would verify: ${PIP} exists and is executable"
fi

# ---------------------------------------------------------------------------
# 2. Install the package editable into miniconda
# ---------------------------------------------------------------------------

info "Installing homunculus-brain (editable) into miniconda ..."
run "${PIP}" install --quiet -e "${BRAIN_REPO}"
info "Package installed. Entry point: ${HOMUNCULUS_BRAIN_BIN}"

# ---------------------------------------------------------------------------
# 3. Platform-specific process supervisor setup
# ---------------------------------------------------------------------------

if [[ "$(uname)" == "Darwin" ]]; then

    # ── macOS: launchd LaunchAgent ──────────────────────────────────────────

    if [[ "$DRY_RUN" == false ]]; then
        mkdir -p "${HOME}/Library/LaunchAgents"
        cp "$PLIST_SRC" "$PLIST_DST"
        info "Plist copied to ${PLIST_DST}"

        # Verify the plist is well-formed. plutil exits non-zero on a bad plist,
        # which will abort the script (set -e) before the user tries to load a
        # broken file.
        plutil -lint "$PLIST_DST" && info "Plist passes plutil -lint."
    else
        info "[dry-run] Would copy: ${PLIST_SRC} → ${PLIST_DST}"
        info "[dry-run] Would run: plutil -lint ${PLIST_DST}"
    fi

    echo ""
    echo "======================================================================"
    echo "  IMPORTANT: Do NOT load the plist yet!"
    echo ""
    echo "  Before loading, confirm Ollama is running:"
    echo "    curl ${OLLAMA_URL}/api/tags"
    echo "  It should list your models (qwen2.5:7b expected)."
    echo "  If not: ollama serve &  then  ollama pull qwen2.5:7b"
    echo ""
    echo "  If a Herman nohup process is already running, stop it first:"
    echo "    pkill -f homunculus-brain   # or kill <PID>"
    echo ""
    echo "  Then load and verify:"
    echo "    launchctl load ${PLIST_DST}"
    echo "    launchctl list | grep homunculus"
    echo "    curl http://localhost:8765/health"
    echo ""
    echo "  Tail logs:"
    echo "    tail -f /tmp/homunculus_brain.log"
    echo "    tail -f /tmp/homunculus_brain_err.log"
    echo "======================================================================"

else

    # ── Linux: systemd user unit ────────────────────────────────────────────

    echo ""
    echo "======================================================================"
    echo "  Linux detected — systemd unit available at:"
    echo "  ${SERVICE_SRC}"
    echo ""
    echo "  To install:"
    echo "    mkdir -p ~/.config/systemd/user/"
    echo "    cp ${SERVICE_SRC} ~/.config/systemd/user/"
    echo "    systemctl --user daemon-reload"
    echo "    systemctl --user enable homunculus-brain"
    echo "    systemctl --user start homunculus-brain"
    echo ""
    echo "  Tail logs:"
    echo "    journalctl --user -u homunculus-brain -f"
    echo "======================================================================"

fi

# ---------------------------------------------------------------------------
# 4. Ollama health check
# ---------------------------------------------------------------------------

echo ""
info "Checking Ollama at ${OLLAMA_URL} ..."

if [[ "$DRY_RUN" == true ]]; then
    info "[dry-run] Would run: curl -sf ${OLLAMA_URL}/api/tags"
else
    if curl -sf --max-time 5 "${OLLAMA_URL}/api/tags" > /dev/null 2>&1; then
        info "Ollama is reachable — good."
        # Check whether qwen2.5:7b is present (non-fatal warning if not)
        if curl -sf --max-time 5 "${OLLAMA_URL}/api/tags" | grep -q "qwen2.5:7b" 2>/dev/null; then
            info "Model qwen2.5:7b is resident in Ollama — good."
        else
            echo ""
            echo "[install] WARNING: qwen2.5:7b not found in Ollama model list."
            echo "  Herman will fall back to the heuristic parser until the model is loaded."
            echo "  To pull it:"
            echo "    ollama pull qwen2.5:7b"
        fi
    else
        echo ""
        echo "[install] WARNING: Ollama is not reachable at ${OLLAMA_URL}"
        echo "  Herman will boot but LLM-based intent parsing won't work."
        echo "  To start Ollama:"
        echo "    ollama serve"
        echo "  Then pull the model:"
        echo "    ollama pull qwen2.5:7b"
    fi
fi

# ---------------------------------------------------------------------------
# Done
# ---------------------------------------------------------------------------

echo ""
info "Done. See deploy/README.md and docs/RUNBOOK.md for next steps."
