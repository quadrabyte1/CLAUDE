#!/usr/bin/env python3
"""Post-migration DB cleanup pass.

Run from inside the NEW vault after `migrate_to_vault.sh` carried over `workspace.db`.

What it does (dry-run by default):
  1. Lists `tasks` rows still in 'in_progress' or 'pending' — these are leftovers from
     the old workspace; the new Larry isn't actually running them.
  2. Lists `documents` rows whose `file_path` no longer resolves under the vault root.
  3. With --apply, marks those tasks 'cancelled' (with a cleanup note) and deletes
     the orphaned `documents` rows. Backs the DB up first.

Usage:
  python3 scripts/cleanup_after_migration.py                  # preview
  python3 scripts/cleanup_after_migration.py --apply          # do it
  python3 scripts/cleanup_after_migration.py --apply --keep-docs   # tasks only
"""
from __future__ import annotations

import argparse
import shutil
import sqlite3
import sys
from datetime import datetime, timezone
from pathlib import Path

VAULT = Path(__file__).resolve().parent.parent
DB_PATH = VAULT / "db" / "workspace.db"


def now_iso() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def stale_tasks(conn: sqlite3.Connection) -> list[sqlite3.Row]:
    return conn.execute(
        """
        SELECT t.id, t.title, t.status, t.created_at, tm.name AS assignee
        FROM tasks t
        LEFT JOIN team_members tm ON tm.id = t.assigned_to
        WHERE t.status IN ('in_progress', 'pending', 'blocked')
        ORDER BY t.created_at
        """
    ).fetchall()


def orphan_documents(conn: sqlite3.Connection) -> list[sqlite3.Row]:
    rows = conn.execute(
        "SELECT id, filename, file_path, source_inbox FROM documents"
    ).fetchall()
    orphans = []
    for r in rows:
        p = (VAULT / r["file_path"]).resolve()
        if not p.exists():
            orphans.append(r)
    return orphans


def print_table(title: str, rows: list[sqlite3.Row], cols: list[str]) -> None:
    print(f"\n=== {title} ({len(rows)}) ===")
    if not rows:
        print("  (none)")
        return
    widths = [max(len(c), *(len(str(r[c] or "")) for r in rows)) for c in cols]
    header = "  " + "  ".join(c.ljust(w) for c, w in zip(cols, widths))
    print(header)
    print("  " + "  ".join("-" * w for w in widths))
    for r in rows:
        print("  " + "  ".join(str(r[c] or "").ljust(w) for c, w in zip(cols, widths)))


def backup_db() -> Path:
    stamp = datetime.now().strftime("%Y%m%dT%H%M%S")
    dest = DB_PATH.with_name(f"workspace.db.bak-{stamp}")
    shutil.copy2(DB_PATH, dest)
    return dest


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--apply", action="store_true", help="Perform the cleanup (default: dry-run)")
    ap.add_argument("--keep-docs", action="store_true", help="Don't touch the documents table")
    ap.add_argument("--note", default="Cancelled during post-migration cleanup.",
                    help="Note recorded in activity_log for each cancelled task")
    args = ap.parse_args()

    if not DB_PATH.exists():
        print(f"DB not found: {DB_PATH}", file=sys.stderr)
        return 1

    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")

    tasks = stale_tasks(conn)
    orphans = [] if args.keep_docs else orphan_documents(conn)

    print(f"Vault: {VAULT}")
    print(f"DB:    {DB_PATH}")
    print_table("Stale tasks (would be cancelled)", tasks,
                ["id", "status", "assignee", "title", "created_at"])
    if not args.keep_docs:
        print_table("Orphaned documents (would be deleted)", orphans,
                    ["id", "source_inbox", "filename", "file_path"])

    if not args.apply:
        print("\nDry-run only. Re-run with --apply to make changes.")
        return 0

    if not tasks and not orphans:
        print("\nNothing to do.")
        return 0

    backup = backup_db()
    print(f"\nDB backed up to: {backup}")

    ts = now_iso()
    with conn:  # transaction
        for t in tasks:
            conn.execute(
                "UPDATE tasks SET status='cancelled', updated_at=? WHERE id=?",
                (ts, t["id"]),
            )
            conn.execute(
                """
                INSERT INTO activity_log (actor, action, entity_type, entity_id, details, created_at)
                VALUES ('migration', 'cancelled_task', 'task', ?, ?, ?)
                """,
                (t["id"], args.note, ts),
            )
        for d in orphans:
            conn.execute("DELETE FROM documents WHERE id=?", (d["id"],))
            conn.execute(
                """
                INSERT INTO activity_log (actor, action, entity_type, entity_id, details, created_at)
                VALUES ('migration', 'deleted_orphan_document', 'document', ?, ?, ?)
                """,
                (d["id"], f"file_path={d['file_path']} not present in new vault", ts),
            )

    print(f"\nCancelled {len(tasks)} task(s); deleted {len(orphans)} orphan document row(s).")
    print("Done.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
