-- schema.sql
-- Canonical schema for workspace.db (SQLite)
-- Corresponds to PRAGMA user_version = 2
--
-- Conventions:
--   - snake_case for all identifiers
--   - Timestamps stored as ISO 8601 TEXT (e.g. '2026-03-30T18:00:00Z')
--   - Foreign keys enforced (PRAGMA foreign_keys = ON at connection open)
--   - Every table gets created_at / updated_at

------------------------------------------------------------------------
-- 1. team_members
--    One row per AI team member. Sourced from the persona files in team/.
------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS team_members (
    id            INTEGER PRIMARY KEY,
    name          TEXT    NOT NULL UNIQUE,
    role          TEXT    NOT NULL,
    status        TEXT    NOT NULL DEFAULT 'active'
                         CHECK (status IN ('active', 'inactive')),
    persona_file  TEXT,                          -- relative path, e.g. 'Team/reed.md'
    created_at    TEXT    NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%SZ', 'now')),
    updated_at    TEXT    NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%SZ', 'now'))
);

------------------------------------------------------------------------
-- 2. tasks
--    Tracks assignments and their lifecycle.
------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS tasks (
    id              INTEGER PRIMARY KEY,
    title           TEXT    NOT NULL,
    description     TEXT,
    status          TEXT    NOT NULL DEFAULT 'pending'
                           CHECK (status IN ('pending', 'in_progress', 'blocked', 'done', 'cancelled')),
    priority        TEXT    NOT NULL DEFAULT 'normal'
                           CHECK (priority IN ('low', 'normal', 'high', 'urgent')),
    assigned_to     INTEGER REFERENCES team_members(id) ON DELETE SET NULL,
    created_by      TEXT,                        -- owner name or team member name
    due_date        TEXT,                        -- ISO 8601 date or datetime
    completed_at    TEXT,
    created_at      TEXT    NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%SZ', 'now')),
    updated_at      TEXT    NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%SZ', 'now'))
);

CREATE INDEX IF NOT EXISTS idx_tasks_status      ON tasks(status);
CREATE INDEX IF NOT EXISTS idx_tasks_assigned_to  ON tasks(assigned_to);

------------------------------------------------------------------------
-- 3. documents
--    Files and images that pass through the inboxes.
------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS documents (
    id            INTEGER PRIMARY KEY,
    filename      TEXT    NOT NULL,
    file_path     TEXT    NOT NULL,               -- relative path inside the workspace
    source_inbox  TEXT    NOT NULL
                         CHECK (source_inbox IN ('owner_inbox', 'team_inbox')),
    mime_type     TEXT,
    size_bytes    INTEGER,
    description   TEXT,
    uploaded_by   TEXT,                            -- 'Thomas' or a team member name
    task_id       INTEGER REFERENCES tasks(id) ON DELETE SET NULL,
    created_at    TEXT    NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%SZ', 'now')),
    updated_at    TEXT    NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%SZ', 'now'))
);

CREATE INDEX IF NOT EXISTS idx_documents_source_inbox ON documents(source_inbox);
CREATE INDEX IF NOT EXISTS idx_documents_task_id      ON documents(task_id);

------------------------------------------------------------------------
-- 4. activity_log
--    Append-only log of notable events in the workspace.
------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS activity_log (
    id          INTEGER PRIMARY KEY,
    actor       TEXT    NOT NULL,                  -- who did it (team member name or 'Thomas')
    action      TEXT    NOT NULL,                  -- verb, e.g. 'created_task', 'uploaded_document'
    entity_type TEXT,                              -- 'task', 'document', 'team_member', etc.
    entity_id   INTEGER,                           -- PK of the affected row
    details     TEXT,                              -- free-form JSON or plain text
    created_at  TEXT    NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%SZ', 'now'))
);

CREATE INDEX IF NOT EXISTS idx_activity_log_actor      ON activity_log(actor);
CREATE INDEX IF NOT EXISTS idx_activity_log_entity     ON activity_log(entity_type, entity_id);
CREATE INDEX IF NOT EXISTS idx_activity_log_created_at ON activity_log(created_at);

------------------------------------------------------------------------
-- 5. notes
--    General-purpose notes attached to tasks or standing alone.
------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS notes (
    id          INTEGER PRIMARY KEY,
    task_id     INTEGER REFERENCES tasks(id) ON DELETE CASCADE,
    author      TEXT    NOT NULL,
    body        TEXT    NOT NULL,
    created_at  TEXT    NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%SZ', 'now')),
    updated_at  TEXT    NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%SZ', 'now'))
);

CREATE INDEX IF NOT EXISTS idx_notes_task_id ON notes(task_id);

------------------------------------------------------------------------
-- 6. journal_entries
--    Daily journal for the workspace owner. One entry per date.
------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS journal_entries (
    id          INTEGER PRIMARY KEY,
    date        TEXT    NOT NULL UNIQUE,           -- ISO 8601 date, e.g. '2026-03-30'
    title       TEXT,                              -- optional title
    content     TEXT    NOT NULL DEFAULT '',       -- rich text / markdown content
    created_at  TEXT    NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%SZ', 'now')),
    updated_at  TEXT    NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%SZ', 'now'))
);

CREATE INDEX IF NOT EXISTS idx_journal_entries_date ON journal_entries(date);
