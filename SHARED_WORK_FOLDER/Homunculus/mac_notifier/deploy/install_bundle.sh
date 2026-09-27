#!/bin/bash
# install_bundle.sh — Build and install Homunculus Notifier.app
#
# mac_notifier v0.3.0 — Rune — 2026-09-27
#
# What this does:
#   1. Compiles deploy/notifier_stub/notifier.swift → a macOS binary
#   2. Assembles the .app bundle skeleton under ~/Applications/
#      (boot volume — repo lives on /Volumes/GIT which is nosuid)
#   3. Validates the bundle with plutil
#   4. Runs a self-test notification so Thomas can confirm "Homunculus" branding
#
# Prerequisites:
#   - macOS (Darwin)
#   - Xcode Command Line Tools: xcode-select --install
#     (provides /usr/bin/swift + /usr/bin/swiftc)
#
# Usage:
#   bash deploy/install_bundle.sh [--dry-run]
#
#   --dry-run: print what would happen without executing; still validates plist.
#
# After install, re-run deploy/install.sh to reload the launchd plist (no other
# step is needed — the poller auto-detects the bundle via find_bundle_app()).
#
# Manual verify:
#   ~/Applications/Homunculus\ Notifier.app/Contents/MacOS/notifier \
#       "Test body" "Manual verify" "Homunculus" "default"
#   → You should see a notification labelled "Homunculus Notifier" (not "Script Editor")
#
# To uninstall:
#   rm -rf ~/Applications/Homunculus\ Notifier.app

set -euo pipefail

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
STUB_SRC="${SCRIPT_DIR}/notifier_stub/notifier.swift"
INFO_PLIST_SRC="${SCRIPT_DIR}/notifier_stub/Info.plist"
BUNDLE_DEST="${HOME}/Applications/Homunculus Notifier.app"
CONTENTS="${BUNDLE_DEST}/Contents"
MACOS_DIR="${CONTENTS}/MacOS"
RESOURCES_DIR="${CONTENTS}/Resources"
BINARY="${MACOS_DIR}/notifier"

DRY_RUN=false
if [[ "${1:-}" == "--dry-run" ]]; then
    DRY_RUN=true
    echo "[install_bundle] DRY RUN — no files will be written."
fi

# ---------------------------------------------------------------------------
# Platform guard
# ---------------------------------------------------------------------------

if [[ "$(uname)" != "Darwin" ]]; then
    echo "[install_bundle] ERROR: This script requires macOS."
    echo "  On Linux, notifications are not supported. Exiting."
    exit 1
fi

# ---------------------------------------------------------------------------
# Swift compiler check
# ---------------------------------------------------------------------------

if ! command -v swiftc &>/dev/null; then
    echo "[install_bundle] ERROR: swiftc not found."
    echo "  Install Xcode Command Line Tools:"
    echo "    xcode-select --install"
    exit 1
fi

SWIFTC_VERSION="$(swiftc --version 2>&1 | head -1)"
echo "[install_bundle] Compiler: ${SWIFTC_VERSION}"

# ---------------------------------------------------------------------------
# Validate Info.plist source
# ---------------------------------------------------------------------------

echo "[install_bundle] Validating Info.plist source..."
if plutil -lint "${INFO_PLIST_SRC}" >/dev/null 2>&1; then
    echo "[install_bundle] Info.plist source: OK"
else
    echo "[install_bundle] ERROR: Info.plist source failed plutil lint."
    plutil -lint "${INFO_PLIST_SRC}"
    exit 1
fi

if $DRY_RUN; then
    echo "[install_bundle] Would compile: ${STUB_SRC}"
    echo "[install_bundle] Would create bundle at: ${BUNDLE_DEST}"
    echo "[install_bundle] Dry run complete."
    exit 0
fi

# ---------------------------------------------------------------------------
# Create bundle skeleton
# ---------------------------------------------------------------------------

echo "[install_bundle] Creating bundle at: ${BUNDLE_DEST}"
mkdir -p "${MACOS_DIR}" "${RESOURCES_DIR}"

# ---------------------------------------------------------------------------
# Compile the Swift stub
# ---------------------------------------------------------------------------

echo "[install_bundle] Compiling ${STUB_SRC} ..."
swiftc "${STUB_SRC}" -o "${BINARY}"
chmod +x "${BINARY}"
echo "[install_bundle] Binary written to: ${BINARY}"

# ---------------------------------------------------------------------------
# Copy Info.plist
# ---------------------------------------------------------------------------

cp "${INFO_PLIST_SRC}" "${CONTENTS}/Info.plist"
echo "[install_bundle] Info.plist installed at: ${CONTENTS}/Info.plist"

# ---------------------------------------------------------------------------
# Validate installed bundle
# ---------------------------------------------------------------------------

echo "[install_bundle] Validating installed Info.plist ..."
if plutil -lint "${CONTENTS}/Info.plist" >/dev/null 2>&1; then
    echo "[install_bundle] Installed Info.plist: OK"
else
    echo "[install_bundle] WARNING: installed Info.plist failed plutil lint."
    plutil -lint "${CONTENTS}/Info.plist"
fi

# ---------------------------------------------------------------------------
# Summary
# ---------------------------------------------------------------------------

echo ""
echo "======================================================================"
echo "  Homunculus Notifier.app installed at:"
echo "  ${BUNDLE_DEST}"
echo ""
echo "  Bundle structure:"
echo "  ${BUNDLE_DEST}/"
echo "  └── Contents/"
echo "      ├── Info.plist  (bundle ID: com.homunculus.notifier)"
echo "      ├── MacOS/"
echo "      │   └── notifier  (Swift notification stub)"
echo "      └── Resources/  (reserved for future icon + localization)"
echo ""
echo "  Manual verify — send yourself a test notification:"
echo "    \"${BINARY}\" \\"
echo "        \"Herman is running.\" \\"
echo "        \"Homunculus v0.3 test\" \\"
echo "        \"Homunculus\" \\"
echo "        \"default\""
echo ""
echo "  Expected: notification appears labelled 'Homunculus Notifier'"
echo "  (not 'Script Editor')"
echo ""
echo "  NOTE: macOS will prompt you to Allow Notifications the first time."
echo "  Go to System Settings → Notifications → Homunculus Notifier → Allow."
echo ""
echo "  The mac_notifier poller (com.homunculus.mac_notifier launchd agent)"
echo "  will auto-detect this bundle on next startup. No plist reload needed."
echo "======================================================================"
echo ""
echo "[install_bundle] Done."
