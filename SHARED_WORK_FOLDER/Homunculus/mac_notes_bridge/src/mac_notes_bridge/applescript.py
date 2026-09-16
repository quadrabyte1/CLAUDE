"""
applescript.py — Subprocess wrapper around osascript for Notes.app.

macOS-only at runtime. On Linux, all functions raise NotImplementedError.
Tests mock subprocess.run; never invoke real osascript in automated tests.

Design:
- Folder name is configurable (default: "Homunculus") via BRIDGE_FOLDER_NAME.
- Account name is configurable (default: "iCloud") via BRIDGE_NOTES_ACCOUNT.
- Notes.app AppleScript target: `tell folder "Homunculus" of account "iCloud"`.
  Unlike Calendar.app (which has no account concept), Notes.app DOES have an
  account model accessible from AppleScript. Using `tell account "iCloud"`
  is documented and works reliably in Notes.app.
- Idempotency: query_pushed_note_ids() searches by title. Because note titles
  in the Homunculus folder come from Herman's note_id slugs (unique), a title
  match is a reliable idempotency signal.
  Rationale for title-based check over body-marker approach:
    - Embedding a sentinel in the body would pollute the visible note content.
    - Title = note_id slug is inherently unique in the Homunculus folder.
    - No two Herman notes have the same slug (the id field in frontmatter is
      globally unique: date + slug derived from Ollama title parse).
- Atomic note creation: `make new note with properties {name:..., body:...}`
  in a SINGLE osascript command. No two-step make-then-set-body. The Calendar
  bridge learned this the hard way (v0.1.5): two-step patterns can silently
  roll back on macOS 15.x.

Notes.app AppleScript account/folder access:
  Notes.app models accounts differently from Calendar.app.
  The AppleScript dictionary DOES include `account` as a valid container.
  `tell folder "<name>" of account "<name>"` is the canonical pattern.
  See docs/AUTOMATION_SETUP.md for the permission requirements.
"""

from __future__ import annotations

import logging
import subprocess
import sys

from .vault_reader import NoteRecord

log = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Platform guard
# ---------------------------------------------------------------------------

def _require_darwin(fn_name: str) -> None:
    if sys.platform != "darwin":
        raise NotImplementedError(
            f"mac_notes_bridge.applescript.{fn_name} requires macOS"
        )


# ---------------------------------------------------------------------------
# Low-level osascript runner
# ---------------------------------------------------------------------------

class AppleScriptError(Exception):
    """Raised when osascript exits non-zero."""


def run_applescript(script: str, timeout: int = 30) -> str:
    """
    Run *script* via ``osascript -e`` and return stdout stripped.

    Args:
        script:  Multi-line AppleScript source.
        timeout: Seconds before subprocess.TimeoutExpired (default 30).

    Raises:
        AppleScriptError: if osascript exits with a non-zero code.
        NotImplementedError: on non-Darwin platforms.
    """
    _require_darwin("run_applescript")

    log.debug("osascript:\n%s", script)
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

    stdout = result.stdout.strip()
    log.debug("osascript result: %r", stdout)
    return stdout


# ---------------------------------------------------------------------------
# Folder verification (startup check)
# ---------------------------------------------------------------------------

def verify_folder_exists(folder_name: str, account_name: str) -> bool:
    """
    Return True if a Notes.app folder named *folder_name* exists under
    *account_name*.

    Notes.app's AppleScript dictionary DOES have an account concept, unlike
    Calendar.app. We use `tell account "iCloud"` to scope the folder lookup.

    If this returns False, the caller should log an actionable error telling
    the user to create the folder manually in Notes.app and exit gracefully —
    NOT try to create it programmatically. Creating a folder in the right
    iCloud account via AppleScript is finicky; manual creation is the same
    pattern we established for Calendar.

    Args:
        folder_name:  Name of the Notes folder to check (e.g. "Homunculus").
        account_name: Name of the Notes account (e.g. "iCloud").

    Returns:
        True if the folder exists, False otherwise.

    Raises:
        NotImplementedError: on non-Darwin platforms.
        AppleScriptError: if the osascript call fails unexpectedly.
    """
    _require_darwin("verify_folder_exists")

    # We try the account-scoped form first. If the account name is wrong
    # or Notes.app rejects the account syntax, the script will exit non-zero
    # and we raise AppleScriptError — letting the caller decide what to do.
    script = f"""
tell application "Notes"
    tell account "{account_name}"
        return exists folder "{folder_name}"
    end tell
end tell
""".strip()

    log.debug(
        "Checking if Notes folder '%s' exists in account '%s'",
        folder_name,
        account_name,
    )
    raw = run_applescript(script)
    return raw.lower() == "true"


# ---------------------------------------------------------------------------
# Note queries (idempotency slow path)
# ---------------------------------------------------------------------------

def query_pushed_note_ids(
    folder_name: str,
    account_name: str,
) -> list[str]:
    """
    Return a list of note names (titles) already in the Notes.app folder.

    Used as the authoritative idempotency check when pushed.jsonl is absent
    or incomplete. Notes.app has no URL field, so we use the note name (which
    equals the Herman note_id slug) as the deduplication key.

    Because Herman's note titles come from Ollama intent parse and are stored
    in frontmatter `title` (also used as NoteRecord.display_title → Notes.app
    `name`), a title match uniquely identifies a Herman note.

    Args:
        folder_name:  Name of the Notes folder.
        account_name: Name of the Notes account.

    Returns:
        List of note name strings (these are the note titles, equivalent to
        note_id slugs for Herman-generated notes).

    Raises:
        NotImplementedError: on non-Darwin platforms.
        AppleScriptError: if the osascript call fails.
    """
    _require_darwin("query_pushed_note_ids")

    script = f"""
set result to {{}}
tell application "Notes"
    tell account "{account_name}"
        tell folder "{folder_name}"
            set allNotes to every note
            repeat with aNote in allNotes
                set end of result to name of aNote
            end repeat
        end tell
    end tell
end tell
return result
""".strip()

    raw = run_applescript(script)
    if not raw:
        return []
    # osascript returns a comma-separated list for AppleScript lists
    names = [n.strip() for n in raw.split(",") if n.strip()]
    log.debug(
        "query_pushed_note_ids: found %d notes in folder '%s'",
        len(names),
        folder_name,
    )
    return names


# ---------------------------------------------------------------------------
# Note creation
# ---------------------------------------------------------------------------

def push_note(note: NoteRecord, folder_name: str, account_name: str) -> None:
    """
    Create *note* in Notes.app under *folder_name* within *account_name*.

    Uses atomic single-command `make new note with properties {name:..., body:...}`
    — no two-step make-then-set-body. The Calendar bridge v0.1.5 teaches us
    that two-step patterns can silently roll back on macOS 15.x.

    The folder must already exist — call verify_folder_exists() at startup
    and exit if it returns False. See docs/FIRST_RUN.md for how to create it.

    Body format: plain text (raw markdown prose, frontmatter already stripped
    by vault_reader.py). Notes.app renders plain text readably. No HTML
    conversion is attempted — it would add a dependency and formatting
    complexity not asked for in v0.1.

    Args:
        note:         The NoteRecord to push.
        folder_name:  Name of the target Notes folder (e.g. "Homunculus").
        account_name: Name of the Notes account (e.g. "iCloud").

    Raises:
        NotImplementedError: on non-Darwin platforms.
        AppleScriptError: if the osascript call fails.
    """
    _require_darwin("push_note")

    # Escape double-quotes for AppleScript string embedding.
    title_escaped = note.display_title.replace("\\", "\\\\").replace('"', '\\"')
    body_escaped = note.notes_body.replace("\\", "\\\\").replace('"', '\\"')

    script = f"""
tell application "Notes"
    tell account "{account_name}"
        tell folder "{folder_name}"
            make new note with properties {{name:"{title_escaped}", body:"{body_escaped}"}}
        end tell
    end tell
end tell
""".strip()

    log.info(
        "Pushing note '%s' (vault filename: '%s') → Notes folder '%s'",
        note.display_title,
        note.source_path.name,
        folder_name,
    )
    run_applescript(script)
    log.info("Note '%s' pushed successfully", note.note_id)
