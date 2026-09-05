-- =============================================================================
-- hole_in_one_v0.3_schema.sql
-- Source:      UML class diagram "Hole In One (v0.3)"
-- Task:        DB task id 744 (assigned to Reed, team_members.id = 4)
-- Date:        2026-09-05
-- Author:      Reed — Database Engineer
--
-- Delta from v0.2 (task 736):
--   hole_in_one gains three nullable TEXT date columns:
--     order_received   (ISO 8601: YYYY-MM-DD)
--     order_confirmed  (ISO 8601: YYYY-MM-DD)
--     order_shipped    (ISO 8601: YYYY-MM-DD)
--   All other tables, relationships, and constraints are unchanged.
-- =============================================================================
--
-- INHERITANCE STRATEGY: Table-per-subtype
-- ----------------------------------------
-- PrintedItem has 8 simple subtypes (Frame, Fringe, Green, Bunker, Water, Rake,
-- Flag) plus one richer subtype (Plaque) with 4 extra columns.  Table-per-
-- subtype was chosen over the single-table discriminator approach for two
-- reasons:
--   1. Plaque's extra columns (hole_number, name, date, yards, club_used) would
--      be NULL for every other subtype in a single-table layout — a silent data-
--      quality risk.
--   2. Each subtype can gain its own columns in the future with a simple ALTER
--      TABLE on the child table instead of touching the shared parent.
-- The parent table `printed_item` carries serial_number, a `kind` discriminator
-- TEXT column (CHECK-constrained to the valid subtype names), and the standard
-- surrogate PK + timestamps.  Each child table has its own `id` surrogate PK
-- plus a `printed_item_id` FK pointing back to the parent row.
--
-- DATE COLUMNS: SQLite has no native DATE type.  Dates are stored as TEXT in
-- ISO 8601 format (YYYY-MM-DD).  Timestamps use YYYY-MM-DDTHH:MM:SSZ.
-- =============================================================================

PRAGMA foreign_keys  = ON;
PRAGMA journal_mode  = WAL;
PRAGMA busy_timeout  = 5000;
PRAGMA temp_store    = MEMORY;
PRAGMA cache_size    = -64000;
PRAGMA mmap_size     = 268435456;

-- =============================================================================
-- INDEPENDENT / ROOT TABLES
-- =============================================================================

CREATE TABLE IF NOT EXISTS golf_course (
    id          INTEGER PRIMARY KEY,
    name        TEXT    NOT NULL,
    created_at  TEXT    NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%SZ','now')),
    updated_at  TEXT    NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%SZ','now'))
);

CREATE TABLE IF NOT EXISTS image_file (
    id          INTEGER PRIMARY KEY,
    name        TEXT    NOT NULL,
    created_at  TEXT    NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%SZ','now')),
    updated_at  TEXT    NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%SZ','now'))
);

CREATE TABLE IF NOT EXISTS ordering_person (
    id                   INTEGER PRIMARY KEY,
    name                 TEXT    NOT NULL,
    email_address        TEXT    NOT NULL,
    text_message_number  INTEGER,
    created_at           TEXT    NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%SZ','now')),
    updated_at           TEXT    NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%SZ','now'))
);

-- =============================================================================
-- TABLES DEPENDENT ON ROOT TABLES
-- =============================================================================

-- ShippingAddress: one OrderingPerson → many ShippingAddresses
CREATE TABLE IF NOT EXISTS shipping_address (
    id                  INTEGER PRIMARY KEY,
    ordering_person_id  INTEGER NOT NULL REFERENCES ordering_person(id) ON DELETE CASCADE,
    street              TEXT    NOT NULL,
    city                TEXT    NOT NULL,
    state               TEXT    NOT NULL,
    zip                 TEXT    NOT NULL,
    created_at          TEXT    NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%SZ','now')),
    updated_at          TEXT    NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%SZ','now'))
);

-- Hole: many Holes belong to one GolfCourse (1..* ↔ 1)
--       one Hole references one ImageFile (1 ↔ 1 — FK on Hole side)
CREATE TABLE IF NOT EXISTS hole (
    id              INTEGER PRIMARY KEY,
    number          INTEGER NOT NULL,
    golf_course_id  INTEGER NOT NULL REFERENCES golf_course(id)  ON DELETE RESTRICT,
    image_file_id   INTEGER NOT NULL REFERENCES image_file(id)   ON DELETE RESTRICT,
    created_at      TEXT    NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%SZ','now')),
    updated_at      TEXT    NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%SZ','now'))
);

-- HoleInOne: many HoleInOnes belong to one OrderingPerson
--            optionally references one Hole (0..1 ↔ 1: hole_id nullable)
-- v0.3 addition: three nullable order-lifecycle date columns (TEXT ISO 8601).
--   order_received   — date the order was received; set immediately on creation.
--   order_confirmed  — date the order was confirmed; NULL until confirmed.
--   order_shipped    — date the order was shipped; NULL until shipped.
--   No CHECK constraints on values; application layer validates date parsing.
CREATE TABLE IF NOT EXISTS hole_in_one (
    id                          INTEGER PRIMARY KEY,
    ordering_person_id          INTEGER NOT NULL REFERENCES ordering_person(id) ON DELETE RESTRICT,
    hole_id                     INTEGER          REFERENCES hole(id)            ON DELETE SET NULL,
    flag_clicks_from_center_x   INTEGER,
    flag_clicks_from_center_y   INTEGER,
    order_received              TEXT,   -- ISO 8601: YYYY-MM-DD (nullable)
    order_confirmed             TEXT,   -- ISO 8601: YYYY-MM-DD (nullable)
    order_shipped               TEXT,   -- ISO 8601: YYYY-MM-DD (nullable)
    created_at                  TEXT    NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%SZ','now')),
    updated_at                  TEXT    NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%SZ','now'))
);

-- =============================================================================
-- EGM_FILE (diagram label: EMG_File — treated as typo; corrected to EGM_File)
-- =============================================================================

CREATE TABLE IF NOT EXISTS egm_file (
    id          INTEGER PRIMARY KEY,
    name        TEXT    NOT NULL,
    created_at  TEXT    NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%SZ','now')),
    updated_at  TEXT    NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%SZ','now'))
);

-- =============================================================================
-- THREE_MF  (diagram label: 3MF — leading digit invalid as table name)
--            one HoleInOne → one or more three_mf rows (1 ↔ 1..*)
--            optionally derived from one egm_file (0..1 ↔ 1: egm_file_id nullable)
-- =============================================================================

CREATE TABLE IF NOT EXISTS three_mf (
    id              INTEGER PRIMARY KEY,
    name            TEXT    NOT NULL,
    hole_in_one_id  INTEGER NOT NULL REFERENCES hole_in_one(id) ON DELETE RESTRICT,
    egm_file_id     INTEGER          REFERENCES egm_file(id)    ON DELETE SET NULL,
    created_at      TEXT    NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%SZ','now')),
    updated_at      TEXT    NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%SZ','now'))
);

-- =============================================================================
-- PRINTED_ITEM (parent) + subtypes
-- =============================================================================

CREATE TABLE IF NOT EXISTS printed_item (
    id             INTEGER PRIMARY KEY,
    serial_number  INTEGER NOT NULL,
    kind           TEXT    NOT NULL CHECK (kind IN (
                       'frame','fringe','green','bunker','water','rake','flag','plaque'
                   )),
    created_at     TEXT    NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%SZ','now')),
    updated_at     TEXT    NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%SZ','now'))
);

-- Simple subtypes — no extra columns; exist as distinct rows for type safety
-- and future extensibility.

CREATE TABLE IF NOT EXISTS frame (
    id               INTEGER PRIMARY KEY,
    printed_item_id  INTEGER NOT NULL UNIQUE REFERENCES printed_item(id) ON DELETE CASCADE,
    created_at       TEXT    NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%SZ','now')),
    updated_at       TEXT    NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%SZ','now'))
);

CREATE TABLE IF NOT EXISTS fringe (
    id               INTEGER PRIMARY KEY,
    printed_item_id  INTEGER NOT NULL UNIQUE REFERENCES printed_item(id) ON DELETE CASCADE,
    created_at       TEXT    NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%SZ','now')),
    updated_at       TEXT    NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%SZ','now'))
);

CREATE TABLE IF NOT EXISTS green (
    id               INTEGER PRIMARY KEY,
    printed_item_id  INTEGER NOT NULL UNIQUE REFERENCES printed_item(id) ON DELETE CASCADE,
    created_at       TEXT    NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%SZ','now')),
    updated_at       TEXT    NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%SZ','now'))
);

CREATE TABLE IF NOT EXISTS bunker (
    id               INTEGER PRIMARY KEY,
    printed_item_id  INTEGER NOT NULL UNIQUE REFERENCES printed_item(id) ON DELETE CASCADE,
    created_at       TEXT    NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%SZ','now')),
    updated_at       TEXT    NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%SZ','now'))
);

CREATE TABLE IF NOT EXISTS water (
    id               INTEGER PRIMARY KEY,
    printed_item_id  INTEGER NOT NULL UNIQUE REFERENCES printed_item(id) ON DELETE CASCADE,
    created_at       TEXT    NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%SZ','now')),
    updated_at       TEXT    NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%SZ','now'))
);

CREATE TABLE IF NOT EXISTS rake (
    id               INTEGER PRIMARY KEY,
    printed_item_id  INTEGER NOT NULL UNIQUE REFERENCES printed_item(id) ON DELETE CASCADE,
    created_at       TEXT    NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%SZ','now')),
    updated_at       TEXT    NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%SZ','now'))
);

CREATE TABLE IF NOT EXISTS flag (
    id               INTEGER PRIMARY KEY,
    printed_item_id  INTEGER NOT NULL UNIQUE REFERENCES printed_item(id) ON DELETE CASCADE,
    created_at       TEXT    NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%SZ','now')),
    updated_at       TEXT    NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%SZ','now'))
);

-- Plaque — richer subtype with UML-specified extra columns
-- date stored as TEXT ISO 8601 (see header note on DATE columns)
-- club_used stored as INTEGER (UML type); application layer maps to club name
CREATE TABLE IF NOT EXISTS plaque (
    id               INTEGER PRIMARY KEY,
    printed_item_id  INTEGER NOT NULL UNIQUE REFERENCES printed_item(id) ON DELETE CASCADE,
    hole_number      INTEGER NOT NULL,
    name             TEXT    NOT NULL,
    date             TEXT    NOT NULL,   -- ISO 8601: YYYY-MM-DD
    yards            INTEGER NOT NULL,
    club_used        INTEGER NOT NULL,
    created_at       TEXT    NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%SZ','now')),
    updated_at       TEXT    NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%SZ','now'))
);

-- =============================================================================
-- JUNCTION TABLE: three_mf ↔ printed_item  (many-to-many: 0..* ↔ 1..*)
-- =============================================================================

CREATE TABLE IF NOT EXISTS three_mf_printed_item (
    id               INTEGER PRIMARY KEY,
    three_mf_id      INTEGER NOT NULL REFERENCES three_mf(id)     ON DELETE CASCADE,
    printed_item_id  INTEGER NOT NULL REFERENCES printed_item(id)  ON DELETE CASCADE,
    UNIQUE (three_mf_id, printed_item_id)
);

-- =============================================================================
-- INTERPRETATION NOTES
-- =============================================================================
--
-- 1. EMG_File → EGM_File: The UML diagram labels this entity "EMG_File".
--    Every other reference in the golf pipeline uses ".egm" files; this is
--    treated as a diagram typo and corrected to `egm_file` here.
--
-- 2. OrderingPerson ↔ ShippingAddress cardinality: Not specified in the UML.
--    Assumed one-to-many (one person, many addresses). FK `ordering_person_id`
--    placed on `shipping_address`.
--
-- 3. OrderingPerson ↔ HoleInOne cardinality: Not specified in the UML.
--    Assumed one-to-many (one person can have multiple HoleInOne records).
--    FK `ordering_person_id` placed on `hole_in_one`.
--
-- 4. HoleInOne ↔ Hole multiplicity (0..1 ↔ 1): A HoleInOne may optionally
--    reference a Hole (the hole hasn't been set up in the system yet). FK
--    `hole_id` on `hole_in_one` is nullable; ON DELETE SET NULL to preserve
--    the order record if the Hole row is ever removed.
--
-- 5. 3MF entity name: "3MF" starts with a digit, which is illegal as a SQL
--    identifier. Renamed to `three_mf`.
--
-- 6. PrintedItem inheritance: Table-per-subtype chosen over single-table
--    discriminator. Rationale in the header comment block above.
--
-- 7. Subtype child tables: Each simple subtype (frame, fringe, green, bunker,
--    water, rake, flag) has no extra UML-specified columns beyond the
--    PrintedItem fields. The child tables exist as thin pass-throughs with
--    their own surrogate PKs, enabling future column additions per subtype
--    without schema-wide ALTER TABLE changes.
--
-- 8. plaque.club_used: UML specifies type `int`. Stored as INTEGER.
--    Application layer is responsible for mapping integer codes to club names.
--
-- 9. Date columns: SQLite has no native DATE type. All date fields are TEXT
--    in ISO 8601 format (YYYY-MM-DD). Timestamps use YYYY-MM-DDTHH:MM:SSZ.
--
-- 10. ON DELETE strategies:
--     - CASCADE: child rows logically owned by the parent (addresses, subtype rows).
--     - RESTRICT: would orphan significant related data (e.g., removing a Hole
--       that has HoleInOne records attached).
--     - SET NULL: nullable FK; safer than RESTRICT when the parent record might
--       be removed but the child record should survive (e.g., egm_file → three_mf).
--
-- 11. v0.3 delta — hole_in_one order lifecycle dates: Three new nullable TEXT
--     columns (order_received, order_confirmed, order_shipped) track the
--     order-fulfillment lifecycle. All nullable because an order progresses
--     through these states over time (a fresh order has order_received but not
--     order_confirmed or order_shipped yet). No CHECK constraints; the
--     application layer validates ISO 8601 date parsing.
--
-- =============================================================================
