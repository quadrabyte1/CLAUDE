-- Migration 002: Add journal_entries table
-- Brings database from user_version 1 -> 2
-- Date: 2026-03-30
-- Author: Reed (Database Engineer)

-- UP
CREATE TABLE IF NOT EXISTS journal_entries (
    id          INTEGER PRIMARY KEY,
    date        TEXT    NOT NULL UNIQUE,           -- ISO 8601 date, e.g. '2026-03-30'
    title       TEXT,                              -- optional title
    content     TEXT    NOT NULL DEFAULT '',       -- rich text / markdown content
    created_at  TEXT    NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%SZ', 'now')),
    updated_at  TEXT    NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%SZ', 'now'))
);

CREATE INDEX IF NOT EXISTS idx_journal_entries_date ON journal_entries(date);

PRAGMA user_version = 2;

-- DOWN
-- WARNING: Rolling back this migration will destroy all journal entry data.
DROP INDEX IF EXISTS idx_journal_entries_date;
DROP TABLE IF EXISTS journal_entries;
PRAGMA user_version = 1;
