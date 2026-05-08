#!/usr/bin/env bash
# init_bridge.sh — One-time setup for the Obsidian ↔ SQLite journal bridge.
#
# Idempotent: safe to run multiple times.
#
# Steps:
#   1. Detect Python 3
#   2. Create venv at scripts/.venv/ (if absent)
#   3. pip install -r scripts/requirements.txt
#   4. Run generate_dashboard.py for initial dashboard
#   5. Copy plist to ~/Library/LaunchAgents/ and register with launchd (macOS only)
#
# Usage:
#   bash scripts/init_bridge.sh

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "${SCRIPT_DIR}/.." && pwd)"
VENV_DIR="${SCRIPT_DIR}/.venv"
PLIST_NAME="com.sharedworkfolder.journal-watcher.plist"
PLIST_SRC="${SCRIPT_DIR}/${PLIST_NAME}"
LAUNCHAGENTS_DIR="${HOME}/Library/LaunchAgents"
PLIST_DEST="${LAUNCHAGENTS_DIR}/${PLIST_NAME}"
LABEL="com.sharedworkfolder.journal-watcher"

echo ""
echo "=== Obsidian ↔ SQLite Bridge — init_bridge.sh ==="
echo ""

# ── Step 1: Detect Python 3 ──────────────────────────────────────────────
echo "[1/5] Detecting Python 3..."
if command -v python3 &>/dev/null; then
    PYTHON3="$(command -v python3)"
elif [ -x /usr/bin/python3 ]; then
    PYTHON3="/usr/bin/python3"
else
    echo "ERROR: Python 3 not found. Install Python 3 and retry."
    exit 1
fi
PY_VERSION="$("${PYTHON3}" --version 2>&1)"
echo "      Found: ${PYTHON3} (${PY_VERSION})"

# ── Step 2: Create venv ───────────────────────────────────────────────────
echo "[2/5] Setting up virtualenv at scripts/.venv/..."
if [ ! -d "${VENV_DIR}" ]; then
    "${PYTHON3}" -m venv "${VENV_DIR}"
    echo "      Created new venv."
else
    echo "      Venv already exists — skipping creation."
fi
VENV_PYTHON="${VENV_DIR}/bin/python3"
VENV_PIP="${VENV_DIR}/bin/pip"

# ── Step 3: Install dependencies ─────────────────────────────────────────
echo "[3/5] Installing dependencies from scripts/requirements.txt..."
"${VENV_PIP}" install --quiet --upgrade pip
"${VENV_PIP}" install --quiet -r "${SCRIPT_DIR}/requirements.txt"
echo "      Dependencies installed."

# ── Step 4: Generate initial dashboard ───────────────────────────────────
echo "[4/5] Generating initial dashboard notes..."
cd "${REPO_ROOT}"
"${VENV_PYTHON}" "${SCRIPT_DIR}/generate_dashboard.py"
echo "      Dashboard generated."

# ── Step 5: launchd registration (macOS only) ────────────────────────────
echo "[5/5] Registering launchd agent..."

if ! command -v launchctl &>/dev/null; then
    echo "      WARNING: launchctl not found (not macOS, or not in PATH)."
    echo "      Plist is at: ${PLIST_SRC}"
    echo "      To start manually:  python scripts/sync_journal.py"
    echo "      Skipping launchd registration."
else
    mkdir -p "${LAUNCHAGENTS_DIR}"

    # Copy plist (always overwrite to pick up any updates)
    cp "${PLIST_SRC}" "${PLIST_DEST}"
    echo "      Copied plist to ${PLIST_DEST}"

    # Bootout any existing agent first (idempotent — ignore failure if not loaded)
    launchctl bootout "gui/${UID}/${LABEL}" 2>/dev/null || true

    # Bootstrap (register + start)
    launchctl bootstrap "gui/${UID}" "${PLIST_DEST}"
    echo "      launchd agent registered: ${LABEL}"
    echo "      The watcher will start now and restart on login."
    echo ""
    echo "      Logs:"
    echo "        stdout → /tmp/journal-watcher.log"
    echo "        stderr → /tmp/journal-watcher.err"
    echo ""
    echo "      To check status:  launchctl print gui/${UID}/${LABEL}"
    echo "      To stop:          launchctl bootout gui/${UID}/${LABEL}"
    echo "      To restart:       launchctl bootout gui/${UID}/${LABEL} && launchctl bootstrap gui/${UID} ${PLIST_DEST}"
fi

echo ""
echo "=== Bridge setup complete. ==="
echo ""
