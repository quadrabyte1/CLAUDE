"""schema.py — SQLite DDL for the movie_scanner library.

The canonical schema lives here. Both the standalone library and the Flask
app reference this module so the two can never drift apart.

Call ``apply_schema(conn)`` on any fresh sqlite3.Connection to initialise
(or upgrade-idempotently) a scanner database.
"""

import sqlite3

SCHEMA_SQL = """
-- Every tconst we've ever seen in a downloaded basics dump. Used to identify
-- the "new since last run" delta.
CREATE TABLE IF NOT EXISTS titles (
    tconst         TEXT PRIMARY KEY,
    title_type     TEXT NOT NULL,
    primary_title  TEXT NOT NULL,
    start_year     INTEGER,
    runtime_min    INTEGER,
    genres         TEXT,
    first_seen_at  TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%SZ','now'))
);
CREATE INDEX IF NOT EXISTS idx_titles_type_year ON titles(title_type, start_year);

-- Titles that survived the rating + tag filter on the run they first appeared.
CREATE TABLE IF NOT EXISTS matches (
    id             INTEGER PRIMARY KEY,
    tconst         TEXT NOT NULL UNIQUE REFERENCES titles(tconst) ON DELETE CASCADE,
    primary_title  TEXT NOT NULL,
    start_year     INTEGER,
    title_type     TEXT NOT NULL,
    rating         REAL NOT NULL,
    num_votes      INTEGER NOT NULL,
    genres         TEXT,
    matched_tags   TEXT,
    run_id         INTEGER NOT NULL REFERENCES runs(id) ON DELETE CASCADE,
    matched_at     TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%SZ','now')),
    dismissed_at   TEXT
);
CREATE INDEX IF NOT EXISTS idx_matches_run_id ON matches(run_id);
CREATE INDEX IF NOT EXISTS idx_matches_rating  ON matches(rating);

-- One row per scan run.
CREATE TABLE IF NOT EXISTS runs (
    id                INTEGER PRIMARY KEY,
    started_at        TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%SZ','now')),
    completed_at      TEXT,
    status            TEXT NOT NULL DEFAULT 'running'
                           CHECK (status IN ('running', 'done', 'error')),
    phase             TEXT,
    total_downloaded  INTEGER DEFAULT 0,
    new_titles        INTEGER DEFAULT 0,
    matched_titles    INTEGER DEFAULT 0,
    error             TEXT,
    config_snapshot   TEXT
);

-- Simple key/value store for user config.
CREATE TABLE IF NOT EXISTS config (
    key    TEXT PRIMARY KEY,
    value  TEXT NOT NULL
);

-- Default config rows — INSERT OR IGNORE so user edits persist across restarts.
INSERT OR IGNORE INTO config (key, value) VALUES
    ('min_rating',   '7.0'),
    ('min_votes',    '100'),
    ('tags',         '[]'),
    ('exclude_tags', '[]'),
    ('title_types',  '["movie","tvMovie","tvSeries"]');

-- Cached OMDb metadata for individual titles. One row per tconst; shared
-- across all matches/runs. Populated on-demand when the user hovers a title.
CREATE TABLE IF NOT EXISTS title_metadata (
    tconst      TEXT PRIMARY KEY,
    plot        TEXT,
    released    TEXT,     -- OMDb format: "01 Apr 1965"
    runtime     TEXT,     -- OMDb format: "172 min"
    director    TEXT,
    rt_score    TEXT,     -- e.g. "83%" or NULL if not on RT
    imdb_rating TEXT,     -- e.g. "8.1/10"
    metascore   TEXT,     -- e.g. "63/100"
    raw_json    TEXT,     -- full response for future extraction
    fetched_at  TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%SZ','now')),
    error       TEXT      -- if the fetch failed, why (e.g. "Movie not found!")
);

-- Stage C: upside-chance candidates — titles that were rejected at scan time
-- but would now pass the current config. Replaced wholesale on each rescan.
CREATE TABLE IF NOT EXISTS upside_matches (
    id             INTEGER PRIMARY KEY,
    tconst         TEXT NOT NULL UNIQUE,
    primary_title  TEXT NOT NULL,
    start_year     INTEGER,
    title_type     TEXT NOT NULL,
    rating         REAL NOT NULL,
    num_votes      INTEGER NOT NULL,
    genres         TEXT,
    matched_tags   TEXT,
    checked_at     TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%SZ','now'))
);
"""


def apply_schema(conn: sqlite3.Connection) -> None:
    """Execute the schema DDL against *conn* (idempotent — safe to call on
    an existing database; CREATE TABLE IF NOT EXISTS guards every statement).

    Also handles live migration: adds any columns introduced after the initial
    release (e.g. ``dismissed_at``) to databases created by earlier versions.
    """
    conn.executescript(SCHEMA_SQL)

    # Live migration: add dismissed_at to existing matches tables that pre-date V1.2.
    cur = conn.execute("PRAGMA table_info(matches)")
    cols = [r[1] for r in cur.fetchall()]
    if "dismissed_at" not in cols:
        conn.execute("ALTER TABLE matches ADD COLUMN dismissed_at TEXT")

    # Live migration: create title_metadata for databases created before V1.3.
    # The CREATE TABLE IF NOT EXISTS in SCHEMA_SQL handles new databases;
    # this ALTER block ensures existing DBs gain any columns added later.
    conn.execute("""
        CREATE TABLE IF NOT EXISTS title_metadata (
            tconst      TEXT PRIMARY KEY,
            plot        TEXT,
            released    TEXT,
            runtime     TEXT,
            director    TEXT,
            rt_score    TEXT,
            imdb_rating TEXT,
            metascore   TEXT,
            raw_json    TEXT,
            fetched_at  TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%SZ','now')),
            error       TEXT
        )
    """)

    # Live migration: create upside_matches for databases created before V1.4.
    conn.execute("""
        CREATE TABLE IF NOT EXISTS upside_matches (
            id             INTEGER PRIMARY KEY,
            tconst         TEXT NOT NULL UNIQUE,
            primary_title  TEXT NOT NULL,
            start_year     INTEGER,
            title_type     TEXT NOT NULL,
            rating         REAL NOT NULL,
            num_votes      INTEGER NOT NULL,
            genres         TEXT,
            matched_tags   TEXT,
            checked_at     TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%SZ','now'))
        )
    """)

    conn.commit()
