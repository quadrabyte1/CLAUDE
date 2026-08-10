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
--
-- PERSISTENCE CONTRACT (V3.8): every row in this table MUST survive:
--   * App restarts (Werkzeug reloader fires apply_schema every reload)
--   * Code deploys / version bumps
--   * Schema migrations (adding columns/tables — but NEVER wipe config)
-- The seed INSERTs below use INSERT OR IGNORE — they only run when the key
-- is missing. NEVER use INSERT OR REPLACE for config rows: it would wipe
-- user-edited values on every restart.  Do NOT add DROP TABLE config
-- anywhere in this file or in apply_schema() — that is the one operation
-- that would silently destroy every genre/rating/vote/country selection.
CREATE TABLE IF NOT EXISTS config (
    key    TEXT PRIMARY KEY,
    value  TEXT NOT NULL
);

-- Default config rows — INSERT OR IGNORE so user edits persist across restarts.
-- Every config key the app writes to should be seeded here so a fresh DB
-- boots into a usable state without the UI having to fabricate defaults.
INSERT OR IGNORE INTO config (key, value) VALUES
    ('min_rating',        '7.0'),
    ('min_votes',         '100'),
    ('min_year',          '2026'),
    ('tags',              '[]'),
    ('exclude_tags',      '[]'),
    ('title_types',       '["movie","tvMovie","tvSeries"]'),
    ('exclude_countries', '[]'),
    -- parental-guide severity ceilings (V3.12). Default 'severe' means the
    -- filter is inactive (all severities <= severe → nothing filtered).
    -- COMPLIANCE EXCEPTION — see movie_scanner/parental_guide.py.
    ('max_sex_nudity',    'severe'),
    ('max_violence_gore', 'severe'),
    ('max_profanity',     'severe'),
    ('max_alcohol_drugs', 'severe'),
    ('max_frightening',   'severe'),
    ('exclude_unknown_parental', '0'),
    -- V3.14 — master switch for the parental-guide phase. Default '0' means
    -- the scanner SKIPS all parental-guide work (no scrape, no ceilings).
    -- Flip to '1' via the "Apply filters" checkbox to activate the ceilings.
    ('parental_apply',    '0');

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
    country     TEXT,     -- OMDb Country field, e.g. "India, USA"
    language    TEXT,     -- OMDb Language field, e.g. "Kannada, English"
    raw_json    TEXT,     -- full response for future extraction
    fetched_at  TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%SZ','now')),
    error       TEXT      -- if the fetch failed, why (e.g. "Movie not found!")
);

-- Persistent dismissal store — survives DELETE FROM matches and rescan-all.
-- Written by /matches/<tconst>/dismiss; read via LEFT JOIN in all match SELECTs.
CREATE TABLE IF NOT EXISTS dismissed_tconsts (
    tconst        TEXT PRIMARY KEY,
    dismissed_at  TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%SZ','now'))
);

-- Per-season air-year cache (V3.13). Populated during the scan's
-- 'seasons' phase from title.episode.tsv.gz + the startYear on each
-- episode's basics row. One row per (parent_tconst, season_number);
-- rebuilt in full on every scan via INSERT OR REPLACE so the table is
-- always consistent with the latest IMDb dumps. Supports the per-season
-- year filter: a series matches when ANY season has air_year >= min_year.
CREATE TABLE IF NOT EXISTS series_seasons (
    parent_tconst   TEXT NOT NULL,
    season_number   INTEGER NOT NULL,
    air_year        INTEGER,           -- NULL if unknown
    episode_count   INTEGER NOT NULL DEFAULT 0,
    PRIMARY KEY (parent_tconst, season_number)
);
CREATE INDEX IF NOT EXISTS idx_series_seasons_year
  ON series_seasons(parent_tconst, air_year);

-- Which seasons of a series qualified for a given match (V3.13). Populated
-- by the scanner immediately after inserting a series into `matches`.
-- The index (match_id) lets the UI fetch all qualifying seasons for a
-- match in one hop.
CREATE TABLE IF NOT EXISTS match_seasons (
    match_id       INTEGER NOT NULL REFERENCES matches(id) ON DELETE CASCADE,
    season_number  INTEGER NOT NULL,
    air_year       INTEGER,
    episode_count  INTEGER NOT NULL DEFAULT 0,
    PRIMARY KEY (match_id, season_number)
);
CREATE INDEX IF NOT EXISTS idx_match_seasons_match ON match_seasons(match_id);

-- Parental-guide severity cache (V3.12). Populated on-demand by the
-- scanner AFTER a title passes the existing rating/votes/year/genre
-- filters. Rows are refetched when ``fetched_at`` is older than 90 days.
-- COMPLIANCE EXCEPTION — this table exists to support the parental-guide
-- filter added in V3.12 by scraping imdb.com/title/<id>/parentalguide/.
-- Personal, non-commercial use only. See movie_scanner/parental_guide.py.
CREATE TABLE IF NOT EXISTS parental_guide (
    tconst           TEXT PRIMARY KEY,
    sex_nudity       TEXT NOT NULL DEFAULT 'unknown',
    violence_gore    TEXT NOT NULL DEFAULT 'unknown',
    profanity        TEXT NOT NULL DEFAULT 'unknown',
    alcohol_drugs    TEXT NOT NULL DEFAULT 'unknown',
    frightening      TEXT NOT NULL DEFAULT 'unknown',
    fetched_at       TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%SZ','now')),
    CHECK (sex_nudity IN ('none','mild','moderate','severe','unknown')),
    CHECK (violence_gore IN ('none','mild','moderate','severe','unknown')),
    CHECK (profanity IN ('none','mild','moderate','severe','unknown')),
    CHECK (alcohol_drugs IN ('none','mild','moderate','severe','unknown')),
    CHECK (frightening IN ('none','mild','moderate','severe','unknown'))
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
            country     TEXT,
            language    TEXT,
            raw_json    TEXT,
            fetched_at  TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%SZ','now')),
            error       TEXT
        )
    """)

    # Live migration: add country + language to existing title_metadata tables.
    try:
        cur = conn.execute("PRAGMA table_info(title_metadata)")
        tm_cols = [r[1] for r in cur.fetchall()]
        if "country" not in tm_cols:
            conn.execute("ALTER TABLE title_metadata ADD COLUMN country TEXT")
        if "language" not in tm_cols:
            conn.execute("ALTER TABLE title_metadata ADD COLUMN language TEXT")
    except sqlite3.OperationalError:
        pass  # table doesn't exist yet — CREATE TABLE IF NOT EXISTS above handles it

    # V3.8 migration: drop the deprecated upside_matches table. The feature
    # was removed entirely — Thomas found it wasn't worth using. Existing
    # databases silently drop the table on next boot; new databases never
    # create it (removed from SCHEMA_SQL above).
    try:
        conn.execute("DROP TABLE IF EXISTS upside_matches")
    except sqlite3.OperationalError:
        pass  # non-fatal — this is a cleanup migration, not a hard requirement

    # Live migration: create dismissed_tconsts for databases created before V1.5
    # and back-fill any existing dismissals from matches.dismissed_at.
    # INSERT OR IGNORE + idempotent CREATE TABLE make this safe to run on every
    # startup (Werkzeug reloader fires apply_schema repeatedly).
    conn.execute("""
        CREATE TABLE IF NOT EXISTS dismissed_tconsts (
            tconst        TEXT PRIMARY KEY,
            dismissed_at  TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%SZ','now'))
        )
    """)
    try:
        conn.execute("""
            INSERT OR IGNORE INTO dismissed_tconsts (tconst, dismissed_at)
            SELECT tconst, dismissed_at FROM matches WHERE dismissed_at IS NOT NULL
        """)
    except sqlite3.OperationalError:
        pass  # matches table may not exist on brand-new DB

    # V3.12 migration: ensure parental_guide table exists on DBs that
    # pre-date it. Idempotent — CREATE TABLE IF NOT EXISTS. See
    # movie_scanner/parental_guide.py for the compliance context.
    conn.execute("""
        CREATE TABLE IF NOT EXISTS parental_guide (
            tconst           TEXT PRIMARY KEY,
            sex_nudity       TEXT NOT NULL DEFAULT 'unknown',
            violence_gore    TEXT NOT NULL DEFAULT 'unknown',
            profanity        TEXT NOT NULL DEFAULT 'unknown',
            alcohol_drugs    TEXT NOT NULL DEFAULT 'unknown',
            frightening      TEXT NOT NULL DEFAULT 'unknown',
            fetched_at       TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%SZ','now')),
            CHECK (sex_nudity IN ('none','mild','moderate','severe','unknown')),
            CHECK (violence_gore IN ('none','mild','moderate','severe','unknown')),
            CHECK (profanity IN ('none','mild','moderate','severe','unknown')),
            CHECK (alcohol_drugs IN ('none','mild','moderate','severe','unknown')),
            CHECK (frightening IN ('none','mild','moderate','severe','unknown'))
        )
    """)

    # V3.13 migration: ensure series_seasons + match_seasons exist on DBs
    # that pre-date the per-season year filter. Idempotent — CREATE IF NOT
    # EXISTS. The series_seasons table is rebuilt on every scan (INSERT OR
    # REPLACE against every row from title.episode.tsv.gz), so no back-fill
    # is required — the next scan populates it in full.
    conn.execute("""
        CREATE TABLE IF NOT EXISTS series_seasons (
            parent_tconst   TEXT NOT NULL,
            season_number   INTEGER NOT NULL,
            air_year        INTEGER,
            episode_count   INTEGER NOT NULL DEFAULT 0,
            PRIMARY KEY (parent_tconst, season_number)
        )
    """)
    conn.execute("""
        CREATE INDEX IF NOT EXISTS idx_series_seasons_year
          ON series_seasons(parent_tconst, air_year)
    """)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS match_seasons (
            match_id       INTEGER NOT NULL REFERENCES matches(id) ON DELETE CASCADE,
            season_number  INTEGER NOT NULL,
            air_year       INTEGER,
            episode_count  INTEGER NOT NULL DEFAULT 0,
            PRIMARY KEY (match_id, season_number)
        )
    """)
    conn.execute("""
        CREATE INDEX IF NOT EXISTS idx_match_seasons_match ON match_seasons(match_id)
    """)

    # V3.12 migration: seed the new parental-guide config keys on DBs whose
    # config table pre-dates them. The top-of-file SCHEMA_SQL block only
    # runs on fresh DBs; existing DBs need this INSERT OR IGNORE pass so
    # the UI dropdowns render a sane default instead of an empty string.
    for key, value in (
        ("max_sex_nudity",         "severe"),
        ("max_violence_gore",      "severe"),
        ("max_profanity",          "severe"),
        ("max_alcohol_drugs",      "severe"),
        ("max_frightening",        "severe"),
        ("exclude_unknown_parental", "0"),
        # V3.14 — master switch, off by default on existing DBs so the
        # parental-guide phase remains opt-in.
        ("parental_apply",         "0"),
    ):
        conn.execute(
            "INSERT OR IGNORE INTO config (key, value) VALUES (?, ?)",
            (key, value),
        )

    conn.commit()
