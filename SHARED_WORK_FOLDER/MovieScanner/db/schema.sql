-- MovieScanner schema — idempotent, sourced by app.py on startup.

-- Every tconst we've ever seen in a downloaded basics dump. Used to identify
-- the "new since last run" delta.
CREATE TABLE IF NOT EXISTS titles (
    tconst         TEXT PRIMARY KEY,
    title_type     TEXT NOT NULL,       -- movie | tvMovie | tvSeries
    primary_title  TEXT NOT NULL,
    start_year     INTEGER,
    runtime_min    INTEGER,
    genres         TEXT,                -- comma-separated as in the dump
    first_seen_at  TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%SZ','now'))
);
CREATE INDEX IF NOT EXISTS idx_titles_type_year ON titles(title_type, start_year);

-- Titles that survived the rating + tag filter on the run in which they were
-- first seen. One row per matched title (never re-matched — spec: only test
-- newly-appeared titles).
CREATE TABLE IF NOT EXISTS matches (
    id             INTEGER PRIMARY KEY,
    tconst         TEXT NOT NULL UNIQUE REFERENCES titles(tconst) ON DELETE CASCADE,
    primary_title  TEXT NOT NULL,
    start_year     INTEGER,
    title_type     TEXT NOT NULL,
    rating         REAL NOT NULL,
    num_votes      INTEGER NOT NULL,
    genres         TEXT,
    matched_tags   TEXT,                -- comma-separated subset that satisfied config.tags
    run_id         INTEGER NOT NULL REFERENCES runs(id) ON DELETE CASCADE,
    matched_at     TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%SZ','now'))
);
CREATE INDEX IF NOT EXISTS idx_matches_run_id ON matches(run_id);
CREATE INDEX IF NOT EXISTS idx_matches_rating ON matches(rating);

-- One row per scan run.
CREATE TABLE IF NOT EXISTS runs (
    id                INTEGER PRIMARY KEY,
    started_at        TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%SZ','now')),
    completed_at      TEXT,
    status            TEXT NOT NULL DEFAULT 'running'
                           CHECK (status IN ('running', 'done', 'error')),
    phase             TEXT,             -- downloading | loading | diffing | matching | done
    total_downloaded  INTEGER DEFAULT 0,
    new_titles        INTEGER DEFAULT 0,
    matched_titles    INTEGER DEFAULT 0,
    error             TEXT,
    config_snapshot   TEXT               -- JSON of the config at run time
);

-- Simple key/value store for user config (min_rating, min_votes, tags list).
CREATE TABLE IF NOT EXISTS config (
    key    TEXT PRIMARY KEY,
    value  TEXT NOT NULL
);

-- Default config — INSERT OR IGNORE so user edits persist.
INSERT OR IGNORE INTO config (key, value) VALUES
    ('min_rating',    '7.0'),
    ('min_votes',     '100'),
    ('tags',          '[]'),
    ('exclude_tags',  '[]'),
    ('title_types',   '["movie","tvMovie","tvSeries"]');
