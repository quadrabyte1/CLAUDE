"""
applescript.py — Subprocess wrapper for `osascript display notification`.

macOS-only at runtime. On Linux, fire_notification raises NotImplementedError.
Tests mock subprocess.run; never invoke real osascript in automated tests.

Notification design:
    Title:    "Homunculus"
    Subtitle: derived from row.kind (e.g. "Morning summary", "Strike 1")
    Body:     row.body (human-facing summary Herman built)
    Sound:    "default" (system default notification sound)

Known caveat (v0.1):
    `display notification` sends notifications branded as "Script Editor"
    (or the calling process name) on macOS. This is a documented macOS
    limitation for osascript-based notifications run outside a bundled app.
    The mechanism works — the notification appears and sounds — but the
    branding shows "Script Editor" rather than "Homunculus".
    See docs/FIRST_RUN.md for the v0.2 workaround (terminal-notifier or
    a bundled .app with its own bundle ID).
"""

from __future__ import annotations

import logging
import subprocess
import sys

log = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Platform guard
# ---------------------------------------------------------------------------


def _require_darwin(fn_name: str) -> None:
    if sys.platform != "darwin":
        raise NotImplementedError(
            f"mac_notifier.applescript.{fn_name} requires macOS"
        )


# ---------------------------------------------------------------------------
# Core notification function
# ---------------------------------------------------------------------------


class AppleScriptError(Exception):
    """Raised when osascript exits non-zero."""


def fire_notification(
    body: str,
    subtitle: str,
    title: str = "Homunculus",
    sound: str = "default",
    timeout: int = 10,
) -> None:
    """
    Fire a macOS notification via ``osascript display notification``.

    Args:
        body:     The notification message body (main text).
        subtitle: Short subtitle (e.g. "Morning summary", "Strike 1").
        title:    Notification title (default: "Homunculus").
        sound:    Sound name (default: "default" = system default).
        timeout:  Seconds before subprocess.TimeoutExpired (default 10).

    Raises:
        NotImplementedError: on non-Darwin platforms.
        AppleScriptError:    if osascript exits non-zero.
    """
    _require_darwin("fire_notification")

    # Escape double quotes in user-supplied strings so AppleScript doesn't break.
    def _esc(s: str) -> str:
        return s.replace("\\", "\\\\").replace('"', '\\"')

    script = (
        f'display notification "{_esc(body)}" '
        f'with title "{_esc(title)}" '
        f'subtitle "{_esc(subtitle)}" '
        f'sound name "{_esc(sound)}"'
    )

    log.debug("osascript: %s", script)
    try:
        result = subprocess.run(
            ["osascript", "-e", script],
            capture_output=True,
            text=True,
            timeout=timeout,
        )
    except subprocess.TimeoutExpired as exc:
        raise AppleScriptError(f"osascript timed out after {timeout}s") from exc

    if result.returncode != 0:
        stderr = result.stderr.strip()
        raise AppleScriptError(
            f"osascript exited {result.returncode}: {stderr}"
        )

    log.debug("osascript notification sent (subtitle=%r)", subtitle)
