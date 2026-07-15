-- schema.sql
-- Canonical schema for workspace.db (SQLite) — full current schema, idempotent.
-- Sourced by app.py's init_db() on every startup, and by db/init_db.py for
-- one-shot fresh-clone bootstrap.
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
    persona_file  TEXT,                          -- relative path, e.g. 'team/reed.md'
    model         TEXT    NOT NULL DEFAULT 'opus',
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
    started_at      TEXT,
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

------------------------------------------------------------------------
-- 7. token_usage
--    Monthly Claude token accounting.
------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS token_usage (
    id               INTEGER PRIMARY KEY,
    month            TEXT    NOT NULL UNIQUE,
    tokens_purchased INTEGER NOT NULL DEFAULT 0,
    tokens_used      INTEGER NOT NULL DEFAULT 0,
    start_date       TEXT,
    updated_at       TEXT    NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%SZ', 'now'))
);

------------------------------------------------------------------------
-- 8. life_areas + life_items
--    Personal life-tracking board.
------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS life_areas (
    id          INTEGER PRIMARY KEY,
    name        TEXT    NOT NULL UNIQUE,
    icon        TEXT,
    color       TEXT,
    sort_order  INTEGER NOT NULL DEFAULT 0,
    created_at  TEXT    NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%SZ', 'now')),
    updated_at  TEXT    NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%SZ', 'now'))
);

CREATE TABLE IF NOT EXISTS life_items (
    id              INTEGER PRIMARY KEY,
    title           TEXT    NOT NULL,
    notes           TEXT,
    area_id         INTEGER REFERENCES life_areas(id) ON DELETE SET NULL,
    priority        TEXT    NOT NULL DEFAULT 'normal'
                           CHECK (priority IN ('urgent', 'high', 'normal', 'low')),
    status          TEXT    NOT NULL DEFAULT 'open'
                           CHECK (status IN ('open', 'done', 'snoozed', 'cancelled')),
    due_date        TEXT,
    recur_rule      TEXT,
    recur_interval  INTEGER,
    recur_anchor    TEXT,
    snoozed_until   TEXT,
    escalation_days INTEGER DEFAULT 3,
    completed_at    TEXT,
    created_at      TEXT    NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%SZ', 'now')),
    updated_at      TEXT    NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%SZ', 'now'))
);

CREATE INDEX IF NOT EXISTS idx_life_items_area_id  ON life_items(area_id);
CREATE INDEX IF NOT EXISTS idx_life_items_status   ON life_items(status);
CREATE INDEX IF NOT EXISTS idx_life_items_due_date ON life_items(due_date);

------------------------------------------------------------------------
-- Seed rows (idempotent — INSERT OR IGNORE)
------------------------------------------------------------------------

-- Larry is the orchestrator (CLAUDE.md pins him to id=1 for assigned_to lookups).
INSERT OR IGNORE INTO team_members (id, name, role, status, persona_file, model)
VALUES (1, 'Larry', 'Orchestrator / Team Lead', 'active', 'team/larry.md', 'fable');

-- Default life areas (matches app.py's original bootstrap set).
INSERT OR IGNORE INTO life_areas (name, icon, color, sort_order) VALUES
    ('Home',            '🏠', '#8B5CF6', 1),
    ('Health',          '💪', '#10B981', 2),
    ('Finance',         '💰', '#F59E0B', 3),
    ('Relationships',   '👥', '#EC4899', 4),
    ('Career',          '💼', '#3B82F6', 5),
    ('Personal Growth', '📚', '#6366F1', 6),
    ('Admin & Errands', '📋', '#6B7280', 7);
