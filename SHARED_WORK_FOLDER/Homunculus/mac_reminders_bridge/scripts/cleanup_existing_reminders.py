"""
cleanup_existing_reminders.py

One-shot retroactive cleanup: rewrites existing Reminders.app reminder bodies
in the "Homunculus" list to strip v0.1.1-era chrome:
  - ``# <heading>`` lines
  - ``*Captured ... via Sprite.*`` italic captions
  - ``[herman-id:...]`` body sentinels
  - Leading/trailing blank lines
  - All interior blank lines

Usage::

    # Dry run (default — safe, shows what would change, writes nothing):
    python scripts/cleanup_existing_reminders.py

    # Apply the cleanup (rewrites reminder bodies in Reminders.app):
    python scripts/cleanup_existing_reminders.py --apply

    # Target a custom Reminders list:
    python scripts/cleanup_existing_reminders.py --list "My List" --apply

Idempotent: running twice on already-clean reminders is a no-op
(clean_body() returns None when no changes are needed).

Safe: never deletes reminders. Only edits the body field.
Atomic per-reminder: each set-body call is independent; a failure on one
reminder does not affect the others.

macOS only at runtime (requires osascript). The dry-run mode works on any
platform since it only calls the read-side AppleScript.
"""

from __future__ import annotations

import argparse
import logging
import re
import sys

log = logging.getLogger("cleanup_existing_reminders")

# ---------------------------------------------------------------------------
# Import AppleScript runner — require it at import time so tests can mock it.
# ---------------------------------------------------------------------------

try:
    from mac_reminders_bridge.applescript import AppleScriptError, run_applescript
except ImportError:
    # Allow the script to be imported from tests without the full package
    # installed (e.g. via importlib.util.spec_from_file_location). Tests will
    # patch run_applescript via the cleanup module namespace.
    import subprocess as _subprocess

    class AppleScriptError(Exception):
        pass

    def run_applescript(script: str, timeout: int = 30) -> str:
        """Thin wrapper — duplicated here for standalone import. Tests mock this."""
        try:
            result = _subprocess.run(
                ["osascript", "-e", script],
                capture_output=True,
                text=True,
                timeout=timeout,
            )
        except _subprocess.TimeoutExpired as exc:
            raise AppleScriptError(f"osascript timed out after {timeout}s") from exc
        if result.returncode != 0:
            raise AppleScriptError(
                f"osascript exited {result.returncode}: {result.stderr.strip()}"
            )
        return result.stdout.strip()


# ---------------------------------------------------------------------------
# Body-cleaning logic (mirrors vault_reader._clean_body)
# ---------------------------------------------------------------------------

_HEADING_RE = re.compile(r"^#{1,6}\s+.*$", re.MULTILINE)
_CAPTION_RE = re.compile(r"^\*Captured [^*]+via [^*]+\.\*\s*$", re.MULTILINE)
_HERMAN_ID_RE = re.compile(r"\[herman-id:[^\]]*\]")


def clean_body(raw: str) -> str | None:
    """
    Strip all chrome from *raw* and return the cleaned body.

    Returns ``None`` if the body is already clean (no changes needed).
    Returns the cleaned string if any changes were made.

    Removes:
      - Markdown heading lines (``# heading``, ``## heading``, etc.)
      - Sprite italic captions (``*Captured ... via Sprite.*``)
      - Legacy body sentinels (``[herman-id:...]``)
      - All blank lines (leading, trailing, interior)
    """
    text = raw

    text = _HEADING_RE.sub("", text)
    text = _CAPTION_RE.sub("", text)
    text = _HERMAN_ID_RE.sub("", text)

    # Normalise line endings
    text = text.replace("\r\n", "\n").replace("\r", "\n")

    # Keep only non-empty lines — strip all blank lines
    result_lines = [line.rstrip() for line in text.splitlines() if line.strip()]
    cleaned = "\n".join(result_lines).strip()

    if cleaned == raw.strip():
        # No change needed
        return None

    return cleaned if cleaned else raw.strip()


# ---------------------------------------------------------------------------
# Reminders.app interaction
# ---------------------------------------------------------------------------

def _get_reminder_names(list_name: str) -> list[str]:
    """Return names of all reminders in *list_name*."""
    script = f"""
tell application "Reminders"
    tell list "{list_name}"
        return name of every reminder
    end tell
end tell
""".strip()
    raw = run_applescript(script)
    if not raw:
        return []
    return [n.strip() for n in raw.split(",") if n.strip()]


def _get_reminder_body(list_name: str, reminder_name: str) -> str:
    """Return the body of a reminder by name."""
    name_escaped = reminder_name.replace("\\", "\\\\").replace('"', '\\"')
    script = f"""
tell application "Reminders"
    tell list "{list_name}"
        set r to first reminder whose name is "{name_escaped}"
        return body of r
    end tell
end tell
""".strip()
    return run_applescript(script)


def _set_reminder_body(list_name: str, reminder_name: str, new_body: str) -> None:
    """Set the body of a reminder by name."""
    name_escaped = reminder_name.replace("\\", "\\\\").replace('"', '\\"')
    body_escaped = new_body.replace("\\", "\\\\").replace('"', '\\"')
    script = f"""
tell application "Reminders"
    tell list "{list_name}"
        set r to first reminder whose name is "{name_escaped}"
        set body of r to "{body_escaped}"
    end tell
end tell
""".strip()
    run_applescript(script)


# ---------------------------------------------------------------------------
# Main cleanup logic
# ---------------------------------------------------------------------------

def run_cleanup(list_name: str, apply: bool) -> tuple[int, int]:
    """
    Enumerate reminders in *list_name* and clean each dirty body.

    Args:
        list_name: Name of the Reminders.app list.
        apply:     If True, write cleaned bodies back. If False, dry run.

    Returns:
        (changed, total) — number of reminders changed and total enumerated.
    """
    names = _get_reminder_names(list_name)
    total = len(names)
    changed = 0

    for name in names:
        try:
            body = _get_reminder_body(list_name, name)
        except AppleScriptError as exc:
            log.warning("Cannot read body of '%s': %s — skipping", name, exc)
            continue

        cleaned = clean_body(body)
        if cleaned is None:
            log.debug("'%s': already clean — no change", name)
            continue

        mode = "APPLY" if apply else "DRY"
        log.info("[%s] '%s': body will be cleaned", mode, name)
        log.debug("  Before: %r", body[:120])
        log.debug("  After:  %r", cleaned[:120])

        if apply:
            try:
                _set_reminder_body(list_name, name, cleaned)
                log.info("       '%s': body updated", name)
            except AppleScriptError as exc:
                log.error("       '%s': failed to update body: %s", name, exc)
                continue

        changed += 1

    return changed, total


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

def main() -> None:
    parser = argparse.ArgumentParser(
        description=(
            "Retroactively strip v0.1.1 chrome (heading, caption, sentinel) "
            "from Reminders.app reminder bodies in the Homunculus list."
        )
    )
    parser.add_argument(
        "--apply",
        action="store_true",
        default=False,
        help="Execute the cleanup. Without this flag, performs a dry run (safe).",
    )
    parser.add_argument(
        "--list",
        dest="list_name",
        default="Homunculus",
        help="Name of the Reminders.app list to clean (default: Homunculus).",
    )
    parser.add_argument(
        "--verbose",
        action="store_true",
        default=False,
        help="Show DEBUG log lines.",
    )
    args = parser.parse_args()

    logging.basicConfig(
        level=logging.DEBUG if args.verbose else logging.INFO,
        format="%(levelname)-7s %(message)s",
    )

    if sys.platform != "darwin":
        log.error("This script requires macOS (osascript). Exiting.")
        sys.exit(1)

    if not args.apply:
        log.info("DRY RUN — pass --apply to execute. No reminders will be modified.")

    changed, total = run_cleanup(args.list_name, apply=args.apply)

    print()
    print("=" * 60)
    print(f"  Reminders enumerated:  {total}")
    if args.apply:
        print(f"  Bodies cleaned:        {changed}")
    else:
        print(f"  Would clean (dry run): {changed}")
    print("=" * 60)

    if not args.apply and changed > 0:
        print()
        print("  Re-run with --apply to execute the cleanup.")


if __name__ == "__main__":
    main()
