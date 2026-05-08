#!/usr/bin/env python3
"""
sync_journal.py — Two-way Obsidian ↔ SQLite bridge watcher.

Vault → DB:
  Watches journal/*.md for close-write events. On change, parses YAML
  frontmatter + extracts the "Journal entry (syncs to DB)" H2 section,
  then upserts into journal_entries. Applies conflict resolution per the
  architecture doc (timestamp wins; ambiguous → write to _conflicts/).

DB → vault:
  Watches db/workspace.db (and -wal/-shm) for changes. On change,
  regenerates the three dashboard notes under journal/_dashboard/.

Ignored paths:
  journal/_dashboard/*.md  — never synced to DB (prevents loop)
  journal/_conflicts/*.md  — never synced to DB

Usage:
  python scripts/sync_journal.py [--once]

  --once   Run one pass of the DB→vault sync, then exit (used by init_bridge.sh
           for the initial dashboard generation without starting the watcher).

Run permanently via launchd (see scripts/com.sharedworkfolder.journal-watcher.plist).
"""

import argparse
import logging
import os
import re
import sqlite3
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

# ── Watchdog import ────────────────────────────────────────────────────────
try:
    from watchdog.events import (
        FileClosedEvent,
        FileCreatedEvent,
        FileDeletedEvent,
        FileModifiedEvent,
        FileMovedEvent,
        FileSystemEventHandler,
    )
    from watchdog.observers import Observer
except ImportError:
    print(
        "ERROR: watchdog not installed. Run: pip install -r scripts/requirements.txt",
        file=sys.stderr,
    )
    sys.exit(1)

try:
    import frontmatter
except ImportError:
    print(
        "ERROR: python-frontmatter not installed. Run: pip install -r scripts/requirements.txt",
        file=sys.stderr,
    )
    sys.exit(1)

# ── Paths ──────────────────────────────────────────────────────────────────
REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DB_PATH = os.path.join(REPO_ROOT, "db", "workspace.db")
JOURNAL_DIR = os.path.join(REPO_ROOT, "journal")
DASHBOARD_DIR = os.path.join(JOURNAL_DIR, "_dashboard")
CONFLICTS_DIR = os.path.join(JOURNAL_DIR, "_conflicts")

# Paths the watcher must never attempt to sync back to DB
IGNORED_JOURNAL_SUBDIRS = {
    os.path.realpath(DASHBOARD_DIR),
    os.path.realpath(CONFLICTS_DIR),
}

# How many seconds between two modifications counts as "ambiguous"
CONFLICT_WINDOW_SECONDS = 60

# ── Logging ────────────────────────────────────────────────────────────────
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%Y-%m-%dT%H:%M:%SZ",
)
log = logging.getLogger("journal-bridge")

# ── DB helpers ─────────────────────────────────────────────────────────────

def open_db() -> sqlite3.Connection:
    """Open DB with standard PRAGMAs. isolation_level=None = autocommit."""
    conn = sqlite3.connect(DB_PATH, isolation_level=None, timeout=10)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON;")
    conn.execute("PRAGMA journal_mode = WAL;")
    conn.execute("PRAGMA busy_timeout = 5000;")
    conn.execute("PRAGMA temp_store = MEMORY;")
    return conn


def now_utc() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")

# ── Journal parsing ────────────────────────────────────────────────────────

JOURNAL_SECTION_HEADING = "Journal entry (syncs to DB)"
# Matches any H2 heading (## ...) to split the note body into sections
H2_SPLIT_RE = re.compile(r"^## .+", re.MULTILINE)


def extract_journal_section(body: str) -> str:
    """
    Extract only the 'Journal entry (syncs to DB)' H2 section from the note body.

    The architecture doc specifies: "The vault→DB content is the last H2 block
    in the daily template — strip dashboard-derived sections before upserting."

    Returns the section text (without the heading line), stripped of leading/
    trailing whitespace. Returns empty string if the section is absent.
    """
    # Find all H2 positions
    matches = list(H2_SPLIT_RE.finditer(body))
    if not matches:
        return ""

    target_idx = None
    for i, m in enumerate(matches):
        heading_text = body[m.start():m.end()].lstrip("# ").strip()
        if heading_text == JOURNAL_SECTION_HEADING:
            target_idx = i
            break

    if target_idx is None:
        return ""

    section_start = matches[target_idx].end()
    if target_idx + 1 < len(matches):
        section_end = matches[target_idx + 1].start()
    else:
        section_end = len(body)

    section_body = body[section_start:section_end].strip()

    # Strip HTML comment stubs left by the template placeholder
    section_body = re.sub(r"<!--.*?-->", "", section_body, flags=re.DOTALL).strip()

    return section_body


def parse_date_from_path(path: str) -> str | None:
    """
    Infer the journal date from the filename: journal/YYYY-MM-DD.md.
    Returns the date string or None if not parseable.
    """
    name = os.path.basename(path)
    m = re.match(r"^(\d{4}-\d{2}-\d{2})\.md$", name)
    return m.group(1) if m else None


def is_ignored_path(path: str) -> bool:
    """Return True if this path is under a directory we never sync to DB."""
    real = os.path.realpath(path)
    for ignored in IGNORED_JOURNAL_SUBDIRS:
        if real.startswith(ignored + os.sep) or real == ignored:
            return True
    return False

# ── Conflict resolution ────────────────────────────────────────────────────

def write_conflict_file(date: str, vault_content: str, db_content: str) -> str:
    """Write both versions to journal/_conflicts/YYYY-MM-DD-conflict.md."""
    os.makedirs(CONFLICTS_DIR, exist_ok=True)
    conflict_path = os.path.join(CONFLICTS_DIR, f"{date}-conflict.md")
    ts = now_utc()
    text = (
        f"---\n"
        f"title: \"Conflict — {date}\"\n"
        f"conflict_detected_at: \"{ts}\"\n"
        f"read_only: true\n"
        f"---\n\n"
        f"> [!danger] CONFLICT DETECTED for {date}\n"
        f"> Both the vault file and the DB row were modified within {CONFLICT_WINDOW_SECONDS}s "
        f"of each other. Review both versions below and reconcile manually.\n\n"
        f"---\n\n"
        f"## Vault version\n\n"
        f"{vault_content}\n\n"
        f"---\n\n"
        f"## DB version (at time of conflict)\n\n"
        f"{db_content}\n"
    )
    with open(conflict_path, "w", encoding="utf-8") as f:
        f.write(text)
    log.warning("Conflict written to %s", conflict_path)
    return conflict_path

# ── Vault → DB sync ────────────────────────────────────────────────────────

def sync_vault_to_db(path: str) -> None:
    """
    Parse a journal note and upsert its 'Journal entry' section to journal_entries.

    Conflict resolution:
    - Compare vault file mtime vs journal_entries.updated_at.
    - Newer timestamp wins.
    - If both modified within CONFLICT_WINDOW_SECONDS → write conflict file, skip upsert.
    """
    if is_ignored_path(path):
        log.debug("Ignoring write to excluded path: %s", path)
        return

    date = parse_date_from_path(path)
    if not date:
        log.debug("Skipping non-date-named file: %s", path)
        return

    # Parse frontmatter + body
    try:
        post = frontmatter.load(path)
    except Exception as exc:
        log.error("Failed to parse frontmatter from %s: %s", path, exc)
        return

    journal_section = extract_journal_section(post.content)

    # Title: prefer frontmatter title, fall back to date
    title = str(post.get("title", date)).strip() or date

    # File modification time
    try:
        file_mtime = datetime.fromtimestamp(os.path.getmtime(path), tz=timezone.utc)
    except OSError:
        file_mtime = datetime.now(timezone.utc)

    conn = open_db()
    try:
        # Check existing DB row for conflict detection
        existing = conn.execute(
            "SELECT content, updated_at FROM journal_entries WHERE date = ?",
            (date,),
        ).fetchone()

        if existing:
            db_content = existing["content"] or ""
            db_updated_str = existing["updated_at"] or ""
            # Parse DB updated_at
            try:
                db_updated = datetime.strptime(db_updated_str, "%Y-%m-%dT%H:%M:%SZ").replace(
                    tzinfo=timezone.utc
                )
            except ValueError:
                db_updated = None

            if db_updated:
                delta = abs((file_mtime - db_updated).total_seconds())

                if delta <= CONFLICT_WINDOW_SECONDS and db_content != journal_section:
                    # Ambiguous — both modified recently
                    log.warning(
                        "Conflict detected for %s (file mtime=%s, db updated_at=%s, delta=%.1fs)",
                        date, file_mtime.isoformat(), db_updated_str, delta,
                    )
                    write_conflict_file(date, journal_section, db_content)
                    # Log to activity_log but do NOT upsert
                    conn.execute(
                        """
                        INSERT INTO activity_log (actor, action, entity_type, details)
                        VALUES ('obsidian-bridge', 'conflict_detected', 'journal_entry', ?)
                        """,
                        (f"Conflict for {date} — see journal/_conflicts/{date}-conflict.md",),
                    )
                    return
                elif db_updated and db_updated > file_mtime and db_content != journal_section:
                    # DB is newer — vault is stale; do NOT overwrite
                    log.info(
                        "DB row for %s is newer than vault file (db=%s, file=%s) — skipping upsert",
                        date, db_updated_str, file_mtime.isoformat(),
                    )
                    return
                # else: vault is newer (or same) → proceed with upsert

        # Upsert
        conn.execute(
            """
            INSERT INTO journal_entries (date, title, content, created_at, updated_at)
            VALUES (?, ?, ?, strftime('%Y-%m-%dT%H:%M:%SZ','now'), strftime('%Y-%m-%dT%H:%M:%SZ','now'))
            ON CONFLICT(date) DO UPDATE SET
                content  = excluded.content,
                title    = excluded.title,
                updated_at = strftime('%Y-%m-%dT%H:%M:%SZ','now')
            """,
            (date, title, journal_section),
        )

        conn.execute(
            """
            INSERT INTO activity_log (actor, action, entity_type, details)
            VALUES ('obsidian-bridge', 'synced_journal', 'journal_entry', ?)
            """,
            (os.path.basename(path),),
        )
        log.info("Synced %s → journal_entries (date=%s, content_len=%d)", path, date, len(journal_section))
    finally:
        conn.close()

# ── DB → vault: dashboard regeneration ────────────────────────────────────

# Import lazily so generate_dashboard.py works standalone too
def regenerate_dashboard() -> None:
    """Call generate_dashboard.generate_all() via import."""
    try:
        scripts_dir = os.path.dirname(os.path.abspath(__file__))
        if scripts_dir not in sys.path:
            sys.path.insert(0, scripts_dir)
        import generate_dashboard
        generate_dashboard.generate_all()
    except Exception as exc:
        log.error("Dashboard regeneration failed: %s", exc)

# ── File-system event handlers ─────────────────────────────────────────────

class JournalEventHandler(FileSystemEventHandler):
    """Handles events from journal/*.md files."""

    def on_closed(self, event) -> None:
        if not event.is_directory and event.src_path.endswith(".md"):
            sync_vault_to_db(event.src_path)

    def on_created(self, event) -> None:
        # Some editors write via CREATE rather than CLOSE
        if not event.is_directory and event.src_path.endswith(".md"):
            sync_vault_to_db(event.src_path)

    def on_modified(self, event) -> None:
        # Fallback: some platforms don't emit FileClosedEvent
        if not event.is_directory and event.src_path.endswith(".md"):
            sync_vault_to_db(event.src_path)

    def on_moved(self, event) -> None:
        """
        Handle rename: treat as DELETE old date + INSERT new date.
        The UNIQUE constraint on journal_entries.date means we can't just UPDATE.
        """
        if not event.is_directory:
            old_date = parse_date_from_path(event.src_path)
            new_date = parse_date_from_path(event.dest_path)
            if old_date and old_date != new_date:
                conn = open_db()
                try:
                    conn.execute(
                        "DELETE FROM journal_entries WHERE date = ?", (old_date,)
                    )
                    log.info("Deleted journal_entries row for renamed file (old date=%s)", old_date)
                    conn.execute(
                        """
                        INSERT INTO activity_log (actor, action, entity_type, details)
                        VALUES ('obsidian-bridge', 'deleted_journal', 'journal_entry', ?)
                        """,
                        (f"Deleted {old_date} due to file rename → {new_date}",),
                    )
                finally:
                    conn.close()
            # Now sync the new file
            if new_date and os.path.exists(event.dest_path):
                sync_vault_to_db(event.dest_path)

    def on_deleted(self, event) -> None:
        if not event.is_directory and event.src_path.endswith(".md"):
            date = parse_date_from_path(event.src_path)
            if date and not is_ignored_path(event.src_path):
                # We do NOT delete DB rows on file deletion — data is precious.
                log.warning(
                    "File deleted: %s — journal_entries row for %s PRESERVED in DB (delete manually if intended)",
                    event.src_path, date,
                )


class DBChangeHandler(FileSystemEventHandler):
    """Watches db/ for any change and triggers dashboard regeneration."""

    # Debounce: don't regenerate more than once per N seconds
    _last_regen: float = 0
    # 30s debounce: the Flask app touches workspace.db-shm constantly; we only
    # want to regenerate when actual data changes, not on every WAL heartbeat.
    DEBOUNCE_SECONDS: float = 30.0

    def _maybe_regen(self, path: str) -> None:
        # Only care about workspace.db and -wal (actual data changes).
        # Exclude -shm: it is a shared-memory coordination file that SQLite
        # updates on every connection open/close and WAL checkpoint — not a
        # reliable indicator of new data being written.
        basename = os.path.basename(path)
        if basename not in ("workspace.db", "workspace.db-wal"):
            return
        now = time.monotonic()
        if now - DBChangeHandler._last_regen < self.DEBOUNCE_SECONDS:
            return
        DBChangeHandler._last_regen = now
        log.info("DB change detected (%s) — regenerating dashboard", basename)
        regenerate_dashboard()

    def on_modified(self, event) -> None:
        if not event.is_directory:
            self._maybe_regen(event.src_path)

    def on_created(self, event) -> None:
        if not event.is_directory:
            self._maybe_regen(event.src_path)

    def on_closed(self, event) -> None:
        if not event.is_directory:
            self._maybe_regen(event.src_path)

# ── Main ───────────────────────────────────────────────────────────────────

def run_watcher() -> None:
    """Start the watchdog observer loop. Blocks until KeyboardInterrupt."""
    os.makedirs(DASHBOARD_DIR, exist_ok=True)
    os.makedirs(CONFLICTS_DIR, exist_ok=True)

    # Initial dashboard regeneration on startup
    log.info("Starting journal bridge watcher (repo root: %s)", REPO_ROOT)
    log.info("Initial dashboard regeneration...")
    regenerate_dashboard()

    observer = Observer()

    # Watch journal/ (non-recursive: we only care about YYYY-MM-DD.md at top level)
    # We set recursive=True but the handler filters by path.
    observer.schedule(JournalEventHandler(), JOURNAL_DIR, recursive=True)

    # Watch db/ for DB changes
    db_dir = os.path.join(REPO_ROOT, "db")
    observer.schedule(DBChangeHandler(), db_dir, recursive=False)

    observer.start()
    log.info("Watcher running. Ctrl-C to stop.")

    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        log.info("Stopping watcher...")
    finally:
        observer.stop()
        observer.join()
        log.info("Watcher stopped.")


def main() -> None:
    parser = argparse.ArgumentParser(description="Obsidian ↔ SQLite journal bridge")
    parser.add_argument(
        "--once",
        action="store_true",
        help="Regenerate dashboard once and exit (no watcher loop)",
    )
    args = parser.parse_args()

    if args.once:
        log.info("--once mode: regenerating dashboard and exiting")
        regenerate_dashboard()
        return

    run_watcher()


if __name__ == "__main__":
    main()
