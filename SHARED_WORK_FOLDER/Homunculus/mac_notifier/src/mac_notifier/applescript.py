"""
applescript.py — Subprocess wrapper for `osascript display notification`.

macOS-only at runtime. On Linux, fire_notification raises NotImplementedError.
Tests mock subprocess.run; never invoke real osascript in automated tests.

Notification design:
    Title:    "Homunculus"
    Subtitle: derived from row.kind (e.g. "Morning summary", "Strike 1")
    Body:     row.body (human-facing summary Herman built)
    Sound:    "default" (system default notification sound)

v0.3 — Bundle-first notification path:
    fire_notification_with_fallback() is the preferred call site.
    It tries the bundle path (terminal-notifier or Swift stub) first,
    and falls back to this osascript path only if the bundle is absent.
    See mac_notifier.bundle for the bundle strategy.

Legacy caveat (v0.1 / raw osascript path):
    `display notification` sends notifications branded as "Script Editor"
    (or the calling process name) on macOS. This is a documented macOS
    limitation for osascript-based notifications run outside a bundled app.
    The mechanism works — the notification appears and sounds — but the
    branding shows "Script Editor" rather than "Homunculus".
    v0.3 fix: run deploy/install_bundle.sh, then use fire_notification_with_fallback().
"""

from __future__ import annotations

import logging
import subprocess
import sys
from pathlib import Path

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


# ---------------------------------------------------------------------------
# Bundle-first notification (v0.3 preferred call site)
# ---------------------------------------------------------------------------


def fire_notification_with_fallback(
    body: str,
    subtitle: str,
    title: str = "Homunculus",
    sound: str = "default",
    timeout: int = 10,
    search_dirs: list[Path] | None = None,
) -> str:
    """
    Fire a macOS notification using the best available method.

    Strategy:
      1. Try mac_notifier.bundle.fire_via_bundle() — shows "Homunculus" branding.
      2. On NotImplementedError (bundle absent + terminal-notifier absent):
         fall back to fire_notification() (osascript; shows "Script Editor").

    Returns:
        "bundle" — notification was delivered via the .app bundle or terminal-notifier.
        "osascript" — notification was delivered via osascript (legacy branding).

    Raises:
        NotImplementedError: Non-Darwin platform (both paths raised it).
        AppleScriptError / BundleError: Delivery failed on the active path.
    """
    # Import here to avoid circular import at module load time.
    from .bundle import BundleError, fire_via_bundle

    try:
        fire_via_bundle(
            body=body,
            subtitle=subtitle,
            title=title,
            sound=sound,
            timeout=timeout,
            search_dirs=search_dirs,
        )
        return "bundle"
    except NotImplementedError:
        # Bundle not installed; fall back to osascript.
        log.info(
            "Bundle not available — falling back to osascript "
            "(notifications will show as 'Script Editor'). "
            "Run deploy/install_bundle.sh to fix."
        )

    fire_notification(body=body, subtitle=subtitle, title=title, sound=sound, timeout=timeout)
    return "osascript"
