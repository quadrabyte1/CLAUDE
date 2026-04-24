#!/usr/bin/env python3
"""
init_db.py — Initialize the workspace SQLite database.

Creates db/workspace.db, applies schema.sql, seeds the team_members table
from the persona files in Team/, and sets PRAGMA user_version = 1.

Safe to re-run: uses IF NOT EXISTS for all tables and checks user_version
before re-applying.
"""

import os
import sqlite3
import sys

# ---------------------------------------------------------------------------
# Paths (relative to this script's directory)
# ---------------------------------------------------------------------------
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
DB_PATH = os.path.join(SCRIPT_DIR, "workspace.db")
SCHEMA_PATH = os.path.join(SCRIPT_DIR, "schema.sql")
TEAM_DIR = os.path.join(SCRIPT_DIR, os.pardir, "team")

SCHEMA_VERSION = 1  # must match the version noted in schema.sql


def connect(db_path: str) -> sqlite3.Connection:
    """Open a connection with Reed's standard PRAGMAs."""
    conn = sqlite3.connect(db_path)
    conn.execute("PRAGMA foreign_keys = ON;")
    conn.execute("PRAGMA journal_mode = WAL;")
    conn.execute("PRAGMA busy_timeout = 5000;")
    conn.execute("PRAGMA temp_store = MEMORY;")
    conn.execute("PRAGMA cache_size = -64000;")
    conn.execute("PRAGMA mmap_size = 268435456;")
    conn.execute("PRAGMA quick_check;")
    return conn


def apply_schema(conn: sqlite3.Connection) -> None:
    """Read schema.sql and execute it inside a transaction."""
    with open(SCHEMA_PATH, "r") as f:
        schema_sql = f.read()
    conn.executescript(schema_sql)
    conn.execute(f"PRAGMA user_version = {SCHEMA_VERSION};")
    print(f"  Schema applied (user_version = {SCHEMA_VERSION}).")


def seed_team_members(conn: sqlite3.Connection) -> None:
    """
    Parse each .md file in Team/ (except README.md) and insert a row
    into team_members if one doesn't already exist for that name.
    """
    if not os.path.isdir(TEAM_DIR):
        print(f"  Warning: Team directory not found at {TEAM_DIR}, skipping seed.")
        return

    seeded = 0
    for fname in sorted(os.listdir(TEAM_DIR)):
        if not fname.endswith(".md") or fname.lower() == "readme.md":
            continue

        filepath = os.path.join(TEAM_DIR, fname)
        name, role = None, None

        with open(filepath, "r") as f:
            for line in f:
                line = line.strip()
                if line.startswith("- **Name:**"):
                    name = line.split("**Name:**")[1].strip()
                elif line.startswith("- **Role:**"):
                    role = line.split("**Role:**")[1].strip()
                if name and role:
                    break

        if not name or not role:
            print(f"  Skipping {fname}: could not parse name/role.")
            continue

        relative_path = f"team/{fname}"
        try:
            conn.execute(
                """INSERT OR IGNORE INTO team_members (name, role, persona_file)
                   VALUES (?, ?, ?)""",
                (name, role, relative_path),
            )
            if conn.execute(
                "SELECT changes()"
            ).fetchone()[0]:
                seeded += 1
                print(f"  Seeded team member: {name} ({role})")
        except sqlite3.IntegrityError:
            pass  # already exists

    conn.commit()
    print(f"  Team seed complete ({seeded} new member(s)).")


def main() -> None:
    print(f"Database path: {DB_PATH}")

    already_exists = os.path.exists(DB_PATH)
    conn = connect(DB_PATH)

    # Check current version
    current_version = conn.execute("PRAGMA user_version;").fetchone()[0]

    if already_exists and current_version >= SCHEMA_VERSION:
        print(f"  Database already at version {current_version}, nothing to apply.")
    else:
        apply_schema(conn)

    seed_team_members(conn)

    # Quick verification
    tables = [
        r[0]
        for r in conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table' ORDER BY name;"
        ).fetchall()
    ]
    print(f"  Tables: {', '.join(tables)}")

    member_count = conn.execute("SELECT count(*) FROM team_members;").fetchone()[0]
    print(f"  Team members: {member_count}")

    conn.close()
    print("Done.")


if __name__ == "__main__":
    main()
