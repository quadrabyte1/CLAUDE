"""
watcher.py — Entry point for mac_calendar_bridge.

Lifecycle:
1. Configure logging.
2. Verify the "Homunculus" calendar exists in Calendar.app.
   If it does NOT exist, log a clear actionable message and exit non-zero.
   Do NOT crash-loop — launchd's ThrottleInterval handles backoff.
3. Cold-boot sweep: scan the whole vault/calendar/ tree and push any
   un-pushed events (backfills the two existing Sep 15 + Sep 18 events
   on first run).
4. Start a watchdog observer on vault/calendar/ and dispatch new .md files
   as they appear.
5. A periodic sweep thread fires every SWEEP_INTERVAL_SECONDS (default 60).
   Safety net: if watchdog misses an event for any reason (dropped inotify,
   .tmp-file timing, or a v0.1.2 bug), the sweep finds and pushes within 60 s.

macOS-only at runtime (AppleScript calls). On Linux the watcher will start
and sweep the vault but will raise NotImplementedError on the push step.

v0.1.3:
  - Handle on_moved events where dest is a *.md (Herman's atomic rename path).
  - Explicitly ignore .tmp file create events (log DEBUG instead of silent fall-through).
  - Add periodic_sweep() function + background thread as a belt-and-suspenders
    safety net — catches any event missed by watchdog within 60 s.
  - Version bump 0.1.2 → 0.1.3.
"""

from __future__ import annotations

import logging
import sys
import threading
import time
from pathlib import Path

from watchdog.events import (
    FileCreatedEvent,
    FileModifiedEvent,
    FileMovedEvent,
    FileSystemEventHandler,
)
from watchdog.observers import Observer

from . import VERSION
from .applescript import AppleScriptError, push_event, verify_calendar_exists
from .config import (
    BRIDGE_CALENDAR_NAME,
    BRIDGE_STATE_FILE,
    CALENDAR_ROOT,
    Config,
    configure_logging,
)
from .state import PushedState
from .vault_reader import VaultReaderError, parse_event_file, scan_vault_calendar

log = logging.getLogger(__name__)

# Periodic sweep interval in seconds.
SWEEP_INTERVAL_SECONDS = 60


# ---------------------------------------------------------------------------
# Push helper — shared by cold-boot sweep and watchdog handler
# ---------------------------------------------------------------------------

def push_if_new(
    path: Path,
    state: PushedState,
    calendar_name: str,
) -> None:
    """
    Parse *path* and push the event if it hasn't been pushed yet.

    Fast path: check state.is_pushed() first.
    Does nothing if the file extension isn't .md.

    Args:
        path:          Path to the vault event .md file.
        state:         Idempotency state tracker.
        calendar_name: Name of the Calendar.app calendar.
    """
    if path.suffix != ".md":
        log.debug("Ignoring non-.md file: %s", path)
        return

    try:
        record = parse_event_file(path)
    except (VaultReaderError, FileNotFoundError) as exc:
        log.warning("Cannot parse %s: %s", path, exc)
        return

    if state.is_pushed(record.event_id):
        log.debug("Already pushed %s; skipping", record.event_id)
        return

    try:
        push_event(record, calendar_name)
        state.mark_pushed(record.event_id)
    except (AppleScriptError, NotImplementedError) as exc:
        log.error("Failed to push %s: %s", record.event_id, exc)


# ---------------------------------------------------------------------------
# Watchdog event handler
# ---------------------------------------------------------------------------

class VaultCalendarHandler(FileSystemEventHandler):
    """Watchdog handler: fires on new, modified, or moved .md files under vault/calendar/."""

    def __init__(
        self,
        state: PushedState,
        calendar_name: str,
    ) -> None:
        super().__init__()
        self._state = state
        self._calendar_name = calendar_name

    def on_created(self, event: FileCreatedEvent) -> None:
        if event.is_directory:
            return
        path = Path(event.src_path)
        # Herman writes atomically: <file>.md.tmp.<PID>.<N> → os.replace → <file>.md.
        # Explicitly log and skip temp files — do NOT fall through silently.
        if ".tmp" in path.suffixes or path.suffix == ".tmp" or ".tmp." in path.name:
            log.debug("Skipping temp file: %s", path.name)
            return
        log.info("New file detected: %s", event.src_path)
        push_if_new(
            path,
            self._state,
            self._calendar_name,
        )

    def on_moved(self, event: FileMovedEvent) -> None:
        """Handle atomic rename: Herman writes .tmp → os.replace → .md.

        Watchdog fires a MOVE event (src=.tmp, dest=.md). The bridge must
        dispatch on the destination, not the source.
        """
        if event.is_directory:
            return
        dest_path = Path(event.dest_path)
        if dest_path.suffix != ".md":
            log.debug(
                "Ignoring move to non-.md destination: %s → %s",
                event.src_path,
                event.dest_path,
            )
            return
        log.info(
            "Atomic rename detected: %s → %s",
            Path(event.src_path).name,
            dest_path.name,
        )
        push_if_new(dest_path, self._state, self._calendar_name)

    def on_modified(self, event: FileModifiedEvent) -> None:
        # Modified events fire for existing files; only push if we haven't
        # seen this event_id yet (handles the case where Herman rewrites a file
        # in place shortly after creation — still push-only in v0.1).
        if not event.is_directory:
            path = Path(event.src_path)
            if path.suffix == ".md":
                try:
                    record = parse_event_file(path)
                    if not self._state.is_pushed(record.event_id):
                        log.info("Modified file (not yet pushed): %s", event.src_path)
                        push_if_new(
                            path,
                            self._state,
                            self._calendar_name,
                        )
                except (VaultReaderError, FileNotFoundError):
                    pass  # already logged inside push_if_new


# ---------------------------------------------------------------------------
# Periodic sweep — belt-and-suspenders safety net
# ---------------------------------------------------------------------------

def periodic_sweep(
    calendar_root: Path,
    state: PushedState,
    calendar_name: str,
) -> int:
    """
    Scan *calendar_root* for any .md that isn't in pushed.jsonl and push it.

    This is the safety net for events missed by watchdog (dropped inotify,
    .tmp-file timing edge cases, or any future bug). Runs on a background
    thread every SWEEP_INTERVAL_SECONDS.

    Logs at DEBUG when no new events are found (nothing to act on).
    Logs at INFO when it finds and pushes one or more events.

    Returns:
        The number of events pushed during this sweep.
    """
    if not calendar_root.exists():
        log.debug("Periodic sweep: calendar root does not exist: %s", calendar_root)
        return 0

    records = scan_vault_calendar(calendar_root)
    pushed_count = 0

    for record in records:
        if state.is_pushed(record.event_id):
            continue
        log.info(
            "Periodic sweep: found unpushed event %s — pushing now",
            record.event_id,
        )
        try:
            push_event(record, calendar_name)
            state.mark_pushed(record.event_id)
            pushed_count += 1
        except (AppleScriptError, NotImplementedError) as exc:
            log.error(
                "Periodic sweep: failed to push %s: %s", record.event_id, exc
            )

    if pushed_count == 0:
        log.debug("Periodic sweep: nothing new to push (%d event(s) in vault)", len(records))
    else:
        log.info("Periodic sweep: pushed %d new event(s)", pushed_count)

    return pushed_count


def _sweep_loop(
    calendar_root: Path,
    state: PushedState,
    calendar_name: str,
    interval: float,
    stop_event: threading.Event,
) -> None:
    """Background thread body: run periodic_sweep every *interval* seconds."""
    while not stop_event.wait(interval):
        try:
            periodic_sweep(calendar_root, state, calendar_name)
        except Exception:
            log.exception("Periodic sweep thread: unexpected error (continuing)")


# ---------------------------------------------------------------------------
# Cold-boot sweep
# ---------------------------------------------------------------------------

def cold_boot_sweep(
    calendar_root: Path,
    state: PushedState,
    calendar_name: str,
) -> int:
    """
    Scan *calendar_root* recursively and push any events not yet in state.

    Args:
        calendar_root: Root directory of the vault/calendar/ tree.
        state:         Idempotency state tracker.
        calendar_name: Name of the Calendar.app calendar.

    Returns:
        The number of events pushed during this sweep.
    """
    log.info("Cold-boot sweep of %s", calendar_root)
    if not calendar_root.exists():
        log.warning("Calendar root does not exist: %s", calendar_root)
        return 0

    records = scan_vault_calendar(calendar_root)
    log.info("Sweep found %d event(s) in vault", len(records))

    pushed_count = 0
    for record in records:
        if state.is_pushed(record.event_id):
            log.debug("Sweep: already pushed %s; skipping", record.event_id)
            continue
        try:
            push_event(record, calendar_name)
            state.mark_pushed(record.event_id)
            pushed_count += 1
        except (AppleScriptError, NotImplementedError) as exc:
            log.error("Sweep: failed to push %s: %s", record.event_id, exc)

    log.info("Sweep complete: pushed %d new event(s)", pushed_count)
    return pushed_count


# ---------------------------------------------------------------------------
# Main entry point
# ---------------------------------------------------------------------------

def main() -> None:
    configure_logging()
    cfg = Config.from_env()

    log.info("mac_calendar_bridge v%s starting", VERSION)
    log.info("Vault: %s", cfg.calendar_root)
    log.info("Calendar: %s", cfg.calendar_name)
    log.info("State file: %s", cfg.state_file)

    # Verify the Homunculus calendar exists in Calendar.app.
    # Calendar.app has no AppleScript "account" concept — all calendars are a
    # flat namespace. The user must create the "Homunculus" calendar manually
    # in the iCloud account via Calendar.app UI (see docs/FIRST_RUN.md Step 1).
    try:
        exists = verify_calendar_exists(cfg.calendar_name)
    except NotImplementedError:
        log.warning(
            "Not running on macOS — verify_calendar_exists() skipped. "
            "Calendar.app integration will not function."
        )
        exists = True  # allow the watcher loop to start on Linux for testing
    except AppleScriptError as exc:
        log.error(
            "Failed to verify calendar '%s' exists: %s",
            cfg.calendar_name,
            exc,
        )
        sys.exit(1)

    if not exists:
        log.error(
            "Calendar '%s' does not exist in Calendar.app. "
            "Create it manually in the iCloud account, then reload the bridge. "
            "In Calendar.app: File → New Calendar → iCloud → name it '%s'. "
            "See docs/FIRST_RUN.md Step 1 for the full walkthrough.",
            cfg.calendar_name,
            cfg.calendar_name,
        )
        sys.exit(1)

    # Initialise idempotency state
    state = PushedState(cfg.state_file)

    # Cold-boot sweep
    cold_boot_sweep(cfg.calendar_root, state, cfg.calendar_name)

    # Watchdog observer
    handler = VaultCalendarHandler(state, cfg.calendar_name)
    observer = Observer()
    observer.schedule(handler, str(cfg.calendar_root), recursive=True)
    observer.start()
    log.info("Watching %s (recursive) …", cfg.calendar_root)

    # Periodic sweep — safety net for events watchdog might miss.
    stop_sweep = threading.Event()
    sweep_thread = threading.Thread(
        target=_sweep_loop,
        args=(cfg.calendar_root, state, cfg.calendar_name, SWEEP_INTERVAL_SECONDS, stop_sweep),
        name="mac-calendar-bridge-sweep",
        daemon=True,
    )
    sweep_thread.start()
    log.info("Periodic sweep started (interval=%ds)", SWEEP_INTERVAL_SECONDS)

    try:
        while observer.is_alive():
            time.sleep(1)
    except KeyboardInterrupt:
        log.info("Interrupted; stopping observer")
    finally:
        stop_sweep.set()
        sweep_thread.join(timeout=5)
        observer.stop()
        observer.join()
        log.info("mac_calendar_bridge stopped")


if __name__ == "__main__":
    main()
