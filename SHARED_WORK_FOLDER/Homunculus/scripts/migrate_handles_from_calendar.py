"""
migrate_handles_from_calendar.py

One-shot migration script: finds [handle] and [handle!] events in vault/calendar/
and migrates them to vault/reminders/ with v1.6.0 frontmatter conventions.

Usage:
    # Dry run (default — safe, shows what would happen, writes nothing):
    python scripts/migrate_handles_from_calendar.py

    # Apply the migration (moves files and rewrites frontmatter):
    python scripts/migrate_handles_from_calendar.py --apply

What it does per file:
    1. Reads the YAML frontmatter.
    2. Checks whether the title starts with "[handle]" or "[handle!]".
    3. Strips the prefix from title.
    4. Adds/updates: verb=handle, criticality=critical (for [handle!]) or removes
       criticality (for [handle]).
    5. Removes: ends_at, duration_minutes (not used in reminders vault).
    6. Writes the new file to vault/reminders/<event-id>.md (atomically).
    7. Deletes the original calendar file.

The script does NOT touch:
    - Events without [handle] or [handle!] in the title (schedule events).
    - vault/_reminders/ (strike-chain sidecars — unrelated directory).
    - Any file in vault/reminders/ (already migrated or new-format).

Idempotent: running twice is safe — the second run finds nothing to migrate.

Safety:
    - Dry run by default. Writes nothing without --apply.
    - Atomic write: tmp file → os.replace.
    - Logs every action at INFO level.
    - Prints a summary at the end.
"""

from __future__ import annotations

import argparse
import logging
import os
import sys
import tempfile
from pathlib import Path

try:
    import yaml
except ImportError:
    print("ERROR: PyYAML is required. Run: pip install pyyaml", file=sys.stderr)
    sys.exit(1)

try:
    import frontmatter as fm
except ImportError:
    print("ERROR: python-frontmatter is required. Run: pip install python-frontmatter", file=sys.stderr)
    sys.exit(1)

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------

_DEFAULT_VAULT = Path(
    os.environ.get(
        "HERMAN_VAULT_PATH",
        str(Path(__file__).parent.parent / "vault"),
    )
)

log = logging.getLogger("migrate_handles")


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _is_handle_title(title: str) -> bool:
    """Return True if title begins with [handle] or [handle!]."""
    t = title.strip()
    return t.startswith("[handle]") or t.startswith("[handle!]")


def _strip_handle_prefix(title: str) -> tuple[str, bool]:
    """
    Strip [handle] or [handle!] prefix from title.

    Returns:
        (clean_title, is_critical)
    """
    t = title.strip()
    if t.startswith("[handle!]"):
        return t[len("[handle!]"):].strip(), True
    if t.startswith("[handle]"):
        return t[len("[handle]"):].strip(), False
    return t, False


def _build_reminders_frontmatter(old_fm: dict, clean_title: str, is_critical: bool) -> dict:
    """Build a new frontmatter dict for vault/reminders/."""
    new_fm: dict = {}

    # Required fields
    new_fm["id"] = old_fm["id"]
    new_fm["title"] = clean_title
    new_fm["tz"] = old_fm.get("tz", "America/New_York")
    new_fm["verb"] = "handle"

    # Optional: starts_at (hint for due date in Reminders.app)
    if "starts_at" in old_fm:
        new_fm["starts_at"] = old_fm["starts_at"]

    # criticality — only set when critical; absent = normal
    if is_critical:
        new_fm["criticality"] = "critical"

    # Passthrough fields that are still meaningful
    for key in ("source", "source_utterance", "people", "tags", "created_at", "updated_at"):
        if key in old_fm:
            new_fm[key] = old_fm[key]

    # Explicitly drop: ends_at, duration_minutes (calendar-specific)
    return new_fm


def _write_reminders_file(dest: Path, new_fm: dict, body: str, apply: bool) -> None:
    """Write a new reminders vault file (atomically). Respects dry-run mode."""
    if not apply:
        return  # dry run

    dest.parent.mkdir(parents=True, exist_ok=True)

    # Build content: YAML frontmatter + body
    lines = ["---"]
    lines.append(yaml.safe_dump(new_fm, sort_keys=False).rstrip())
    lines.append("---")
    lines.append("")
    if body.strip():
        lines.append(body.strip())

    content = "\n".join(lines) + "\n"

    # Atomic write: tmp → os.replace
    tmp_fd, tmp_path_str = tempfile.mkstemp(
        dir=dest.parent, prefix=dest.name + ".tmp.", suffix=""
    )
    try:
        with os.fdopen(tmp_fd, "w", encoding="utf-8") as fh:
            fh.write(content)
            fh.flush()
            os.fsync(fh.fileno())
        os.replace(tmp_path_str, dest)
    except Exception:
        try:
            os.unlink(tmp_path_str)
        except OSError:
            pass
        raise


# ---------------------------------------------------------------------------
# Main migration logic
# ---------------------------------------------------------------------------

def migrate(vault_path: Path, apply: bool) -> tuple[int, int, int]:
    """
    Scan vault/calendar/ for [handle] / [handle!] files and migrate them.

    Returns:
        (found, migrated, skipped_already_done)
    """
    calendar_dir = vault_path / "calendar"
    reminders_dir = vault_path / "reminders"

    if not calendar_dir.exists():
        log.info("vault/calendar/ does not exist at %s — nothing to migrate", calendar_dir)
        return 0, 0, 0

    found = 0
    migrated = 0
    skipped = 0

    # Walk all .md files in vault/calendar/ (subdirectories included)
    md_files = sorted(calendar_dir.rglob("*.md"))
    log.info("Scanning %d .md files in %s", len(md_files), calendar_dir)

    for cal_path in md_files:
        try:
            post = fm.load(str(cal_path))
        except Exception as exc:
            log.warning("Cannot parse %s: %s — skipping", cal_path, exc)
            continue

        title = post.metadata.get("title", "")
        if not _is_handle_title(str(title)):
            log.debug("Not a handle event: %s (title=%r)", cal_path.name, title)
            continue

        found += 1
        event_id = post.metadata.get("id", cal_path.stem)
        dest = reminders_dir / f"{event_id}.md"

        if dest.exists():
            log.info(
                "SKIP  %s → already exists in vault/reminders/ (idempotent)",
                cal_path.name,
            )
            skipped += 1
            continue

        clean_title, is_critical = _strip_handle_prefix(str(title))
        new_fm = _build_reminders_frontmatter(dict(post.metadata), clean_title, is_critical)
        body = post.content or ""

        mode = "APPLY" if apply else "DRY"
        log.info(
            "[%s]  %s  →  vault/reminders/%s  (title=%r, critical=%s)",
            mode,
            cal_path.name,
            dest.name,
            clean_title,
            is_critical,
        )

        if apply:
            _write_reminders_file(dest, new_fm, body, apply=True)
            cal_path.unlink()
            log.info("       Deleted %s", cal_path)

        migrated += 1

    return found, migrated, skipped


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

def main() -> None:
    parser = argparse.ArgumentParser(
        description=(
            "Migrate [handle]/[handle!] events from vault/calendar/ to "
            "vault/reminders/ with v1.6.0 frontmatter conventions."
        )
    )
    parser.add_argument(
        "--apply",
        action="store_true",
        default=False,
        help="Execute the migration. Without this flag, performs a dry run (safe).",
    )
    parser.add_argument(
        "--vault",
        type=Path,
        default=_DEFAULT_VAULT,
        help=f"Path to the Herman vault (default: {_DEFAULT_VAULT})",
    )
    parser.add_argument(
        "--verbose",
        action="store_true",
        default=False,
        help="Show DEBUG log lines (includes skipped non-handle events).",
    )
    args = parser.parse_args()

    logging.basicConfig(
        level=logging.DEBUG if args.verbose else logging.INFO,
        format="%(levelname)-7s %(message)s",
    )

    if not args.apply:
        log.info("DRY RUN — pass --apply to execute. No files will be written or deleted.")

    found, migrated, skipped = migrate(args.vault, apply=args.apply)

    print()
    print("=" * 60)
    print(f"  Handle events found in vault/calendar/:  {found}")
    print(f"  Already in vault/reminders/ (skipped):   {skipped}")
    if args.apply:
        print(f"  Migrated (moved + rewritten):            {migrated}")
    else:
        print(f"  Would migrate (dry run):                 {migrated}")
    print("=" * 60)
    if not args.apply and migrated > 0:
        print()
        print("  Re-run with --apply to execute the migration.")


if __name__ == "__main__":
    main()
