"""
watcher.py — Entry point for mac_notes_bridge.

Lifecycle:
1. Configure logging.
2. Verify the "Homunculus" folder exists in Notes.app under the "iCloud" account.
   If it does NOT exist, log a clear actionable message and exit non-zero.
   Do NOT crash-loop — launchd's ThrottleInterval handles backoff.
3. Cold-boot sweep: scan the whole vault/notes/ tree and push any
   un-pushed notes (backfills existing notes on first run).
4. Start a watchdog observer on vault/notes/ and dispatch new .md files
   as they appear (including atomic renames from Herman/Sprite write path).
5. A periodic sweep thread fires every SWEEP_INTERVAL_SECONDS (default 60).
   Safety net: if watchdog misses an event for any reason (dropped inotify,
   .tmp-file timing), the sweep finds and pushes within 60 s.

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
    push_note,
    query_pushed_note_ids,
    verify_folder_exists,
)
from .config import (
    BRIDGE_FOLDER_NAME,
    BRIDGE_NOTES_ACCOUNT,
    BRIDGE_STATE_FILE,
    NOTES_ROOT,
    Config,
    configure_logging,
)
from .state import PushedState
from .vault_reader import VaultReaderError, parse_note_file, scan_vault_notes

log = logging.getLogger(__name__)

# Periodic sweep interval in seconds. Generous (60s) per Thomas's reliability preference.
SWEEP_INTERVAL_SECONDS = 60


# ---------------------------------------------------------------------------
# Push helper — shared by cold-boot sweep and watchdog handler
# ---------------------------------------------------------------------------

def push_if_new(
    path: Path,
    state: PushedState,
    folder_name: str,
    account_name: str,
) -> None:
    """
    Parse *path* and push the note if it hasn't been pushed yet.

    Idempotency is belt-and-suspenders:

    1. **Fast path** — check state.is_pushed() (in-memory + pushed.jsonl).
       If found → skip.  Returns immediately, no Notes.app round-trip.

    2. **Slow path** (authoritative second check) — call
       query_pushed_note_ids() to ask Notes.app directly whether a note
       with this title is already present in the folder.  If found →
       self-heal pushed.jsonl (so future lookups hit the fast path) and skip.
       Notes.app does not expose a URL field, so we match on note title
       (= note_id slug, which is globally unique for Herman-generated notes).

    3. **Push** — only if both checks say "not present" → call push_note()
       then mark_pushed().

    The slow path exists because pushed.jsonl can be wiped.  Without it,
    every note would be re-pushed on cold boot, producing duplicates.

    Does nothing if the file extension isn't .md.
    Explicitly logs and skips .tmp files at DEBUG level.

    Args:
        path:         Path to the vault note .md file.
        state:        Idempotency state tracker.
        folder_name:  Name of the Notes.app folder.
        account_name: Name of the Notes.app account.
    """
    if path.suffix != ".md":
        log.debug("Ignoring non-.md file: %s", path)
        return

    try:
        record = parse_note_file(path)
    except (VaultReaderError, FileNotFoundError) as exc:
        log.warning("Cannot parse %s: %s", path, exc)
        return

    # --- Fast path: pushed.jsonl ---
    if state.is_pushed(record.note_id):
        log.debug("Already pushed %s; skipping", record.note_id)
        return

    # --- Slow path: authoritative Notes.app query ---
    try:
        existing_titles = query_pushed_note_ids(folder_name, account_name)
    except (AppleScriptError, NotImplementedError) as exc:
        # On Linux or if Notes is unreachable, skip the slow check.
        log.debug(
            "query_pushed_note_ids unavailable for %s (%s); proceeding to push",
            record.note_id,
            exc,
        )
        existing_titles = []

    if record.display_title in existing_titles:
        log.info(
            "Self-heal: '%s' already in Notes.app but missing from pushed.jsonl; "
            "healing pushed.jsonl and skipping push",
            record.note_id,
        )
        state.mark_pushed(record.note_id)
        return

    try:
        push_note(record, folder_name, account_name)
        state.mark_pushed(record.note_id)
    except (AppleScriptError, NotImplementedError) as exc:
        log.error("Failed to push %s: %s", record.note_id, exc)


# ---------------------------------------------------------------------------
# Watchdog event handler
# ---------------------------------------------------------------------------

class VaultNotesHandler(FileSystemEventHandler):
    """Watchdog handler: fires on new, modified, or moved .md files under vault/notes/."""

    def __init__(
        self,
        state: PushedState,
        folder_name: str,
        account_name: str,
    ) -> None:
        super().__init__()
        self._state = state
        self._folder_name = folder_name
        self._account_name = account_name

    def on_created(self, event: FileCreatedEvent) -> None:
        if event.is_directory:
            return
        path = Path(event.src_path)
        # Herman/Sprite writes atomically: <file>.md.tmp.<PID>.<N> → os.replace → <file>.md.
        # Explicitly log and skip temp files — do NOT fall through silently.
        if ".tmp" in path.suffixes or path.suffix == ".tmp" or ".tmp." in path.name:
            log.debug("Skipping temp file: %s", path.name)
            return
        log.info("New file detected: %s", event.src_path)
        push_if_new(
            path,
            self._state,
            self._folder_name,
            self._account_name,
        )

    def on_moved(self, event: FileMovedEvent) -> None:
        """Handle atomic rename: Sprite/Herman writes .tmp → os.replace → .md.

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
        push_if_new(dest_path, self._state, self._folder_name, self._account_name)

    def on_modified(self, event: FileModifiedEvent) -> None:
        # Modified events fire for existing files; only push if we haven't
        # seen this note_id yet (handles the case where Sprite rewrites a file
        # in place shortly after creation — still push-only in v0.1).
        if not event.is_directory:
            path = Path(event.src_path)
            if path.suffix == ".md":
                try:
                    record = parse_note_file(path)
                    if not self._state.is_pushed(record.note_id):
                        log.info("Modified file (not yet pushed): %s", event.src_path)
                        push_if_new(
                            path,
                            self._state,
                            self._folder_name,
                            self._account_name,
                        )
                except (VaultReaderError, FileNotFoundError):
                    pass  # already logged inside push_if_new


# ---------------------------------------------------------------------------
# Periodic sweep — belt-and-suspenders safety net
# ---------------------------------------------------------------------------

def periodic_sweep(
    notes_root: Path,
    state: PushedState,
    folder_name: str,
    account_name: str,
) -> int:
    """
    Scan *notes_root* for any .md that isn't in pushed.jsonl and push it.

    Safety net for notes missed by watchdog (dropped inotify, .tmp-file timing
    edge cases, or any future bug). Runs on a background thread every
    SWEEP_INTERVAL_SECONDS.

    Returns:
        The number of notes pushed during this sweep.
    """
    if not notes_root.exists():
        log.debug("Periodic sweep: notes root does not exist: %s", notes_root)
        return 0

    records = scan_vault_notes(notes_root)
    pushed_count = 0

    for record in records:
        if state.is_pushed(record.note_id):
            continue
        log.info(
            "Periodic sweep: found unpushed note %s — pushing now",
            record.note_id,
        )
        try:
            push_note(record, folder_name, account_name)
            state.mark_pushed(record.note_id)
            pushed_count += 1
        except (AppleScriptError, NotImplementedError) as exc:
            log.error(
                "Periodic sweep: failed to push %s: %s", record.note_id, exc
            )

    if pushed_count == 0:
        log.debug("Periodic sweep: nothing new to push (%d note(s) in vault)", len(records))
    else:
        log.info("Periodic sweep: pushed %d new note(s)", pushed_count)

    return pushed_count


def _sweep_loop(
    notes_root: Path,
    state: PushedState,
    folder_name: str,
    account_name: str,
    interval: float,
    stop_event: threading.Event,
) -> None:
    """Background thread body: run periodic_sweep every *interval* seconds."""
    while not stop_event.wait(interval):
        try:
            periodic_sweep(notes_root, state, folder_name, account_name)
        except Exception:
            log.exception("Periodic sweep thread: unexpected error (continuing)")


# ---------------------------------------------------------------------------
# Cold-boot sweep
# ---------------------------------------------------------------------------

def cold_boot_sweep(
    notes_root: Path,
    state: PushedState,
    folder_name: str,
    account_name: str,
) -> int:
    """
    Scan *notes_root* recursively and push any notes not yet in state.

    Args:
        notes_root:   Root directory of the vault/notes/ tree.
        state:        Idempotency state tracker.
        folder_name:  Name of the Notes.app folder.
        account_name: Name of the Notes.app account.

    Returns:
        The number of notes pushed during this sweep.
    """
    log.info("Cold-boot sweep of %s", notes_root)
    if not notes_root.exists():
        log.warning("Notes root does not exist: %s", notes_root)
        return 0

    records = scan_vault_notes(notes_root)
    log.info("Sweep found %d note(s) in vault", len(records))

    pushed_count = 0
    for record in records:
        if state.is_pushed(record.note_id):
            log.debug("Sweep: already pushed %s; skipping", record.note_id)
            continue
        try:
            push_note(record, folder_name, account_name)
            state.mark_pushed(record.note_id)
            pushed_count += 1
        except (AppleScriptError, NotImplementedError) as exc:
            log.error("Sweep: failed to push %s: %s", record.note_id, exc)

    log.info("Sweep complete: pushed %d new note(s)", pushed_count)
    return pushed_count


# ---------------------------------------------------------------------------
# Main entry point
# ---------------------------------------------------------------------------

def main() -> None:
    configure_logging()
    cfg = Config.from_env()

    log.info("mac_notes_bridge v%s starting", VERSION)
    log.info("Vault: %s", cfg.notes_root)
    log.info("Notes folder: %s", cfg.folder_name)
    log.info("Notes account: %s", cfg.notes_account)
    log.info("State file: %s", cfg.state_file)

    # Verify the Homunculus folder exists in Notes.app under the iCloud account.
    # Notes.app's AppleScript dictionary DOES support the account concept,
    # unlike Calendar.app. The user must create the "Homunculus" folder manually
    # in the iCloud account via Notes.app UI. See docs/FIRST_RUN.md Step 1.
    try:
        exists = verify_folder_exists(cfg.folder_name, cfg.notes_account)
    except NotImplementedError:
        log.warning(
            "Not running on macOS — verify_folder_exists() skipped. "
            "Notes.app integration will not function."
        )
        exists = True  # allow the watcher loop to start on Linux for testing
    except AppleScriptError as exc:
        log.error(
            "Failed to verify Notes folder '%s' in account '%s': %s",
            cfg.folder_name,
            cfg.notes_account,
            exc,
        )
        sys.exit(1)

    if not exists:
        log.error(
            "Notes folder '%s' does not exist in account '%s' in Notes.app. "
            "Create it manually: open Notes.app, click the folder icon or "
            "choose File → New Folder, select the iCloud account, name it '%s'. "
            "Then reload the bridge. See docs/FIRST_RUN.md Step 1.",
            cfg.folder_name,
            cfg.notes_account,
            cfg.folder_name,
        )
        sys.exit(1)

    # Initialise idempotency state
    state = PushedState(cfg.state_file)

    # Cold-boot sweep — backfill any existing vault notes
    cold_boot_sweep(cfg.notes_root, state, cfg.folder_name, cfg.notes_account)

    # Watchdog observer
    handler = VaultNotesHandler(state, cfg.folder_name, cfg.notes_account)
    observer = Observer()
    observer.schedule(handler, str(cfg.notes_root), recursive=True)
    observer.start()
    log.info("Watching %s (recursive) …", cfg.notes_root)

    # Periodic sweep — safety net for notes watchdog might miss.
    stop_sweep = threading.Event()
    sweep_thread = threading.Thread(
        target=_sweep_loop,
        args=(
            cfg.notes_root,
            state,
            cfg.folder_name,
            cfg.notes_account,
            SWEEP_INTERVAL_SECONDS,
            stop_sweep,
        ),
        name="mac-notes-bridge-sweep",
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
        log.info("mac_notes_bridge stopped")


if __name__ == "__main__":
    main()
