"""
watcher.py — Entry point for mac_reminders_bridge.

Lifecycle:
1. Configure logging.
2. Verify the "Homunculus" list exists in Reminders.app.
   If it does NOT exist, log a clear actionable message and exit non-zero.
   Do NOT crash-loop — launchd's ThrottleInterval handles backoff.
3. Cold-boot sweep: scan the whole vault/reminders/ directory and push any
   un-pushed reminders (backfills existing handle/remind captures on first run).
4. Start a watchdog observer on vault/reminders/ and dispatch new .md files
   as they appear (including atomic renames from Herman's write path).
5. A periodic sweep thread fires every SWEEP_INTERVAL_SECONDS (default 60).
   Safety net: if watchdog misses an event for any reason, the sweep finds
   and pushes within 60 s.

macOS-only at runtime (AppleScript calls). On Linux the watcher will start
and sweep the vault but will raise NotImplementedError on the push step.
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
from .applescript import (
    AppleScriptError,
    push_reminder,
    query_pushed_reminder_names,
    verify_list_exists,
)
from .config import (
    BRIDGE_LIST_NAME,
    BRIDGE_STATE_FILE,
    REMINDERS_ROOT,
    Config,
    configure_logging,
)
from .state import PushedState
from .vault_reader import VaultReaderError, parse_reminder_file, scan_vault_reminders

log = logging.getLogger(__name__)

# Generous 60-second periodic sweep interval per Thomas's reliability preference.
SWEEP_INTERVAL_SECONDS = 60


# ---------------------------------------------------------------------------
# Push helper — shared by cold-boot sweep and watchdog handler
# ---------------------------------------------------------------------------

def push_if_new(
    path: Path,
    state: PushedState,
    list_name: str,
) -> None:
    """
    Parse *path* and push the reminder if it hasn't been pushed yet.

    Idempotency is belt-and-suspenders (same 3-step pattern as mac_calendar_bridge):

    1. **Fast path** — check state.is_pushed() (in-memory + pushed.jsonl).
       If found → skip. Returns immediately, no Reminders.app round-trip.

    2. **Slow path** (authoritative second check, v0.1.2) — call
       query_pushed_reminder_names() to ask Reminders.app for the names of all
       reminders in the list. Compare against record.display_title.
       If found → self-heal pushed.jsonl and skip.

       v0.1.2 change from v0.1.1: the slow path no longer uses the
       [herman-id:<event_id>] body sentinel. That sentinel leaked an
       implementation detail into the user-visible body field. Name matching
       is sufficient and produces no visible side-effects.

    3. **Push** — only if both checks say "not present" → call push_reminder()
       then mark_pushed().

    The slow path exists because pushed.jsonl can be wiped (e.g. migration).
    Without it, every reminder would be re-pushed on cold boot.

    Does nothing if the file extension isn't .md.
    Explicitly logs and skips .tmp files at DEBUG level.

    Args:
        path:      Path to the vault/reminders/ .md file.
        state:     Idempotency state tracker.
        list_name: Name of the Reminders.app list.
    """
    if path.suffix != ".md":
        log.debug("Ignoring non-.md file: %s", path)
        return

    try:
        record = parse_reminder_file(path)
    except (VaultReaderError, FileNotFoundError) as exc:
        log.warning("Cannot parse %s: %s", path, exc)
        return

    # --- Fast path: pushed.jsonl ---
    if state.is_pushed(record.event_id):
        log.debug("Already pushed %s; skipping", record.event_id)
        return

    # --- Slow path: authoritative Reminders.app name query ---
    try:
        existing_names = query_pushed_reminder_names(list_name)
    except (AppleScriptError, NotImplementedError) as exc:
        # On Linux or if Reminders is unreachable, skip the slow check.
        log.debug(
            "query_pushed_reminder_names unavailable for %s (%s); proceeding to push",
            record.event_id,
            exc,
        )
        existing_names = []

    if record.display_title in existing_names:
        log.info(
            "Self-heal: '%s' already in Reminders.app (name match) but missing "
            "from pushed.jsonl; healing pushed.jsonl and skipping push",
            record.display_title,
        )
        state.mark_pushed(record.event_id)
        return

    try:
        push_reminder(record, list_name)
        state.mark_pushed(record.event_id)
    except (AppleScriptError, NotImplementedError) as exc:
        log.error("Failed to push %s: %s", record.event_id, exc)


# ---------------------------------------------------------------------------
# Watchdog event handler
# ---------------------------------------------------------------------------

class VaultRemindersHandler(FileSystemEventHandler):
    """Watchdog handler: fires on new, modified, or moved .md files under vault/reminders/."""

    def __init__(self, state: PushedState, list_name: str) -> None:
        super().__init__()
        self._state = state
        self._list_name = list_name

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
        push_if_new(path, self._state, self._list_name)

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
        push_if_new(dest_path, self._state, self._list_name)

    def on_modified(self, event: FileModifiedEvent) -> None:
        # Modified events fire for existing files; only push if we haven't
        # seen this event_id yet.
        if not event.is_directory:
            path = Path(event.src_path)
            if path.suffix == ".md":
                try:
                    record = parse_reminder_file(path)
                    if not self._state.is_pushed(record.event_id):
                        log.info("Modified file (not yet pushed): %s", event.src_path)
                        push_if_new(path, self._state, self._list_name)
                except (VaultReaderError, FileNotFoundError):
                    pass  # already logged inside push_if_new


# ---------------------------------------------------------------------------
# Periodic sweep — belt-and-suspenders safety net
# ---------------------------------------------------------------------------

def periodic_sweep(
    reminders_root: Path,
    state: PushedState,
    list_name: str,
) -> int:
    """
    Scan *reminders_root* for any .md that isn't in pushed.jsonl and push it.

    Safety net for reminders missed by watchdog (dropped inotify, .tmp-file
    timing edge cases, or any future bug). Runs on a background thread every
    SWEEP_INTERVAL_SECONDS (60s by default — generous per Thomas's principle).

    Returns:
        The number of reminders pushed during this sweep.
    """
    if not reminders_root.exists():
        log.debug("Periodic sweep: reminders root does not exist: %s", reminders_root)
        return 0

    records = scan_vault_reminders(reminders_root)
    pushed_count = 0

    for record in records:
        if state.is_pushed(record.event_id):
            continue
        log.info(
            "Periodic sweep: found unpushed reminder %s — pushing now",
            record.event_id,
        )
        try:
            push_reminder(record, list_name)
            state.mark_pushed(record.event_id)
            pushed_count += 1
        except (AppleScriptError, NotImplementedError) as exc:
            log.error(
                "Periodic sweep: failed to push %s: %s", record.event_id, exc
            )

    if pushed_count == 0:
        log.debug(
            "Periodic sweep: nothing new to push (%d reminder(s) in vault)",
            len(records),
        )
    else:
        log.info("Periodic sweep: pushed %d new reminder(s)", pushed_count)

    return pushed_count


def _sweep_loop(
    reminders_root: Path,
    state: PushedState,
    list_name: str,
    interval: float,
    stop_event: threading.Event,
) -> None:
    """Background thread body: run periodic_sweep every *interval* seconds."""
    while not stop_event.wait(interval):
        try:
            periodic_sweep(reminders_root, state, list_name)
        except Exception:
            log.exception("Periodic sweep thread: unexpected error (continuing)")


# ---------------------------------------------------------------------------
# Cold-boot sweep
# ---------------------------------------------------------------------------

def cold_boot_sweep(
    reminders_root: Path,
    state: PushedState,
    list_name: str,
) -> int:
    """
    Scan *reminders_root* recursively and push any reminders not yet in state.

    Args:
        reminders_root: Root directory of the vault/reminders/ tree.
        state:          Idempotency state tracker.
        list_name:      Name of the Reminders.app list.

    Returns:
        The number of reminders pushed during this sweep.
    """
    log.info("Cold-boot sweep of %s", reminders_root)
    if not reminders_root.exists():
        log.warning("Reminders root does not exist: %s", reminders_root)
        return 0

    records = scan_vault_reminders(reminders_root)
    log.info("Sweep found %d reminder(s) in vault", len(records))

    pushed_count = 0
    for record in records:
        if state.is_pushed(record.event_id):
            log.debug("Sweep: already pushed %s; skipping", record.event_id)
            continue
        try:
            push_reminder(record, list_name)
            state.mark_pushed(record.event_id)
            pushed_count += 1
        except (AppleScriptError, NotImplementedError) as exc:
            log.error("Sweep: failed to push %s: %s", record.event_id, exc)

    log.info("Sweep complete: pushed %d new reminder(s)", pushed_count)
    return pushed_count


# ---------------------------------------------------------------------------
# Main entry point
# ---------------------------------------------------------------------------

def main() -> None:
    configure_logging()
    cfg = Config.from_env()

    log.info("mac_reminders_bridge v%s starting", VERSION)
    log.info("Vault reminders: %s", cfg.reminders_root)
    log.info("Reminders list: %s", cfg.list_name)
    log.info("State file: %s", cfg.state_file)

    # Verify the Homunculus list exists in Reminders.app.
    # The user must create it manually: File → New List → iCloud → "Homunculus".
    # See docs/FIRST_RUN.md Step 1.
    try:
        exists = verify_list_exists(cfg.list_name)
    except NotImplementedError:
        log.warning(
            "Not running on macOS — verify_list_exists() skipped. "
            "Reminders.app integration will not function."
        )
        exists = True  # allow the watcher loop to start on Linux for testing
    except AppleScriptError as exc:
        log.error(
            "Failed to verify Reminders list '%s': %s",
            cfg.list_name,
            exc,
        )
        sys.exit(1)

    if not exists:
        log.error(
            "Reminders list '%s' does not exist in Reminders.app. "
            "Create it manually: open Reminders.app, choose File → New List, "
            "select the iCloud account, name it '%s'. "
            "Then reload the bridge. See docs/FIRST_RUN.md Step 1.",
            cfg.list_name,
            cfg.list_name,
        )
        sys.exit(1)

    # Initialise idempotency state
    state = PushedState(cfg.state_file)

    # Cold-boot sweep — backfill any existing vault reminders
    cold_boot_sweep(cfg.reminders_root, state, cfg.list_name)

    # Watchdog observer
    handler = VaultRemindersHandler(state, cfg.list_name)
    observer = Observer()
    if cfg.reminders_root.exists():
        observer.schedule(handler, str(cfg.reminders_root), recursive=False)
        log.info("Watching %s …", cfg.reminders_root)
    else:
        log.warning(
            "Reminders root %s does not exist yet; watchdog not started. "
            "The periodic sweep will catch reminders once the directory is created.",
            cfg.reminders_root,
        )
    observer.start()

    # Periodic sweep — safety net for reminders watchdog might miss.
    stop_sweep = threading.Event()
    sweep_thread = threading.Thread(
        target=_sweep_loop,
        args=(cfg.reminders_root, state, cfg.list_name, SWEEP_INTERVAL_SECONDS, stop_sweep),
        name="mac-reminders-bridge-sweep",
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
        log.info("mac_reminders_bridge stopped")


if __name__ == "__main__":
    main()
