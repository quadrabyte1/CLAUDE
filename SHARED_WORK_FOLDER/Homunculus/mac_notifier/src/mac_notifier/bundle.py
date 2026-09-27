"""
bundle.py — macOS .app bundle integration for mac_notifier v0.3.

Provides the two-path notification strategy:

  Path A — terminal-notifier (preferred when installed):
      terminal-notifier -title "Homunculus" -subtitle "..." -message "..."
          -sender com.homunculus.notifier -sound default

  Path B — Swift stub inside the bundle (fallback):
      ~/Applications/Homunculus Notifier.app/Contents/MacOS/notifier
          "Body text" "Subtitle text"

  Fallback (neither installed) → NotImplementedError; caller falls back to
  osascript (Script Editor branding, but still functional).

Bundle ID: com.homunculus.notifier
Bundle name: Homunculus Notifier.app

The bundle skeleton is created by deploy/install_bundle.sh.
On macOS 14+, the first notification from a new bundle will prompt the user
to allow notifications in System Settings → Notifications.

Platform guard: all public functions raise NotImplementedError on non-Darwin
platforms so the caller can degrade gracefully.

No real subprocess calls in tests — all shelling is mocked.
"""

from __future__ import annotations

import logging
import shutil
import subprocess
import sys
from pathlib import Path

log = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

BUNDLE_ID = "com.homunculus.notifier"
BUNDLE_NAME = "Homunculus Notifier.app"

# Default search locations for the installed .app, first match wins.
_DEFAULT_SEARCH_DIRS: list[Path] = [
    Path.home() / "Applications",
    Path("/Applications"),
]


# ---------------------------------------------------------------------------
# Errors
# ---------------------------------------------------------------------------


class BundleError(Exception):
    """Raised when the bundle notification subprocess fails or times out."""


# ---------------------------------------------------------------------------
# Bundle discovery
# ---------------------------------------------------------------------------


def find_bundle_app(
    search_dirs: list[Path] | None = None,
) -> Path | None:
    """
    Return the path to *Homunculus Notifier.app* or None if not found.

    Args:
        search_dirs: Ordered list of directories to search. Defaults to
                     [~/Applications, /Applications].

    Returns:
        Path to the .app directory (a directory, not an executable), or None.
    """
    dirs = search_dirs if search_dirs is not None else _DEFAULT_SEARCH_DIRS
    for d in dirs:
        candidate = d / BUNDLE_NAME
        if candidate.exists():
            return candidate
    return None


# ---------------------------------------------------------------------------
# Core notification via bundle
# ---------------------------------------------------------------------------


def fire_via_bundle(
    body: str,
    subtitle: str,
    title: str = "Homunculus",
    sound: str = "default",
    timeout: int = 10,
    search_dirs: list[Path] | None = None,
) -> None:
    """
    Fire a macOS notification via the Homunculus bundle.

    Strategy (in order):
      1. terminal-notifier with ``-sender com.homunculus.notifier`` (if installed)
      2. Bundle's own ``Contents/MacOS/notifier`` Swift stub (if bundle installed)
      3. NotImplementedError (caller should fall back to osascript)

    Also raises NotImplementedError on non-Darwin platforms.

    Args:
        body:        Notification body (main text).
        subtitle:    Short subtitle (e.g. "Morning summary", "Strike 1").
        title:       Notification title (default: "Homunculus").
        sound:       Sound name (default: "default").
        timeout:     Seconds before TimeoutExpired raises BundleError.
        search_dirs: Override search dirs for find_bundle_app().

    Raises:
        NotImplementedError: Non-Darwin platform, or no bundle + no terminal-notifier.
        BundleError:         Subprocess exited non-zero or timed out.
    """
    if sys.platform != "darwin":
        raise NotImplementedError(
            "mac_notifier.bundle.fire_via_bundle requires macOS"
        )

    tn_path = shutil.which("terminal-notifier")
    bundle_path = find_bundle_app(search_dirs=search_dirs)

    # ------------------------------------------------------------------
    # Path A: terminal-notifier
    # ------------------------------------------------------------------
    if tn_path is not None:
        log.debug(
            "bundle: using terminal-notifier at %s (sender=%s)", tn_path, BUNDLE_ID
        )
        cmd = [
            tn_path,
            "-title", title,
            "-subtitle", subtitle,
            "-message", body,
            "-sound", sound,
            "-sender", BUNDLE_ID,
        ]
        _run_notification_cmd(cmd, timeout, label="terminal-notifier")
        return

    # ------------------------------------------------------------------
    # Path B: bundle's Swift stub
    # ------------------------------------------------------------------
    if bundle_path is not None:
        stub_exe = bundle_path / "Contents" / "MacOS" / "notifier"
        log.debug("bundle: using Swift stub at %s", stub_exe)
        # The Swift stub accepts positional args: body subtitle [title [sound]]
        cmd = [str(stub_exe), body, subtitle, title, sound]
        _run_notification_cmd(cmd, timeout, label="swift-stub")
        return

    # ------------------------------------------------------------------
    # Neither available
    # ------------------------------------------------------------------
    raise NotImplementedError(
        "Homunculus Notifier.app not installed and terminal-notifier not found. "
        "Run deploy/install_bundle.sh, or install terminal-notifier via Homebrew. "
        "Caller should fall back to osascript (Script Editor branding)."
    )


def _run_notification_cmd(cmd: list[str], timeout: int, label: str) -> None:
    """Run *cmd* via subprocess.run; raise BundleError on failure."""
    try:
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=timeout,
        )
    except subprocess.TimeoutExpired as exc:
        raise BundleError(
            f"{label} timed out after {timeout}s"
        ) from exc

    if result.returncode != 0:
        stderr = result.stderr.strip()
        raise BundleError(
            f"{label} exited {result.returncode}: {stderr}"
        )

    log.debug("%s notification sent", label)
