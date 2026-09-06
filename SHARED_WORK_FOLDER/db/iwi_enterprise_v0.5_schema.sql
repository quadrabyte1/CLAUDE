-- =============================================================================
-- iwi_enterprise_v0.5_schema.sql
-- Source:      UML class diagram "Hole In One (v0.5)"
--              (file: ItWentIn/IWI Enterprise Database Schema.drawio)
-- Task:        Assigned to Reed (team_members.id = 4) by Larry
-- Date:        2026-09-05
-- Author:      Reed — Database Engineer
--
-- Delta from v0.3:
--   * NEW relationship R2: HoleInOne ↔ EMG_File.  Diagram shows the edge but
--     provides no cardinality or verb labels.  Interpreted as many-HoleInOne
--     → one-EMG_File (0..1); modeled with a nullable `egm_file_id` FK on
--     `hole_in_one`.  See interpretation note 12 at the bottom of this file.
--   * All other tables, columns, and relationships are unchanged from v0.3.
--
-- INHERITANCE STRATEGY: Table-per-subtype
-- ----------------------------------------
-- PrintedItem has 7 simple subtypes (Frame, Fringe, Green, Bunker, Water, Rake,
-- Flag) plus one richer subtype (Plaque) with 5 extra columns.  Table-per-
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
-- EGM_FILE (diagram label: EMG_File — treated as typo; corrected to EGM_File)
-- Declared before hole_in_one because hole_in_one now references it (R2, v0.5).
-- =============================================================================

CREATE TABLE IF NOT EXISTS egm_file (
    id          INTEGER PRIMARY KEY,
    name        TEXT    NOT NULL,
    created_at  TEXT    NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%SZ','now')),
    updated_at  TEXT    NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%SZ','now'))
);

CREATE INDEX IF NOT EXISTS idx_egm_file_name ON egm_file(name);

-- =============================================================================
-- TABLES DEPENDENT ON ROOT TABLES
-- =============================================================================

-- ShippingAddress: one OrderingPerson → many ShippingAddresses (R1)
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

CREATE INDEX IF NOT EXISTS idx_shipping_address_ordering_person_id
    ON shipping_address(ordering_person_id);

-- Hole: many Holes belong to one GolfCourse (R7: 1..* ↔ 1)
--       one Hole references one ImageFile (R6: 1 ↔ 1 — FK on Hole side)
CREATE TABLE IF NOT EXISTS hole (
    id              INTEGER PRIMARY KEY,
    number          INTEGER NOT NULL,
    golf_course_id  INTEGER NOT NULL REFERENCES golf_course(id)  ON DELETE RESTRICT,
    image_file_id   INTEGER NOT NULL REFERENCES image_file(id)   ON DELETE RESTRICT,
    created_at      TEXT    NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%SZ','now')),
    updated_at      TEXT    NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%SZ','now'))
);

CREATE INDEX IF NOT EXISTS idx_hole_golf_course_id ON hole(golf_course_id);
CREATE INDEX IF NOT EXISTS idx_hole_image_file_id  ON hole(image_file_id);

-- HoleInOne: many HoleInOnes belong to one OrderingPerson  (R5)
--            optionally references one Hole   (0..1 ↔ 1: hole_id nullable)
--            optionally references one EGM    (NEW R2: v0.5 — cardinality
--                                              unlabeled in diagram; see note 12)
-- v0.3 additions retained: order_received / order_confirmed / order_shipped
CREATE TABLE IF NOT EXISTS hole_in_one (
    id                          INTEGER PRIMARY KEY,
    ordering_person_id          INTEGER NOT NULL REFERENCES ordering_person(id) ON DELETE RESTRICT,
    hole_id                     INTEGER          REFERENCES hole(id)            ON DELETE SET NULL,
    egm_file_id                 INTEGER          REFERENCES egm_file(id)        ON DELETE SET NULL,
    flag_clicks_from_center_x   INTEGER,
    flag_clicks_from_center_y   INTEGER,
    order_received              TEXT,   -- ISO 8601: YYYY-MM-DD (nullable)
    order_confirmed             TEXT,   -- ISO 8601: YYYY-MM-DD (nullable)
    order_shipped               TEXT,   -- ISO 8601: YYYY-MM-DD (nullable)
    created_at                  TEXT    NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%SZ','now')),
    updated_at                  TEXT    NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%SZ','now'))
);

CREATE INDEX IF NOT EXISTS idx_hole_in_one_ordering_person_id
    ON hole_in_one(ordering_person_id);
CREATE INDEX IF NOT EXISTS idx_hole_in_one_hole_id      ON hole_in_one(hole_id);
CREATE INDEX IF NOT EXISTS idx_hole_in_one_egm_file_id  ON hole_in_one(egm_file_id);

-- =============================================================================
-- THREE_MF  (diagram label: 3MF — leading digit invalid as SQL identifier)
--            one HoleInOne → one or more three_mf rows (1 ↔ 1..*)
--            optionally derived from one egm_file  (R8: 0..1 ↔ 1)
-- =============================================================================

CREATE TABLE IF NOT EXISTS three_mf (
    id              INTEGER PRIMARY KEY,
    name            TEXT    NOT NULL,
    hole_in_one_id  INTEGER NOT NULL REFERENCES hole_in_one(id) ON DELETE RESTRICT,
    egm_file_id     INTEGER          REFERENCES egm_file(id)    ON DELETE SET NULL,
    created_at      TEXT    NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%SZ','now')),
    updated_at      TEXT    NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%SZ','now'))
);

CREATE INDEX IF NOT EXISTS idx_three_mf_hole_in_one_id ON three_mf(hole_in_one_id);
CREATE INDEX IF NOT EXISTS idx_three_mf_egm_file_id    ON three_mf(egm_file_id);

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

CREATE INDEX IF NOT EXISTS idx_printed_item_kind ON printed_item(kind);
CREATE INDEX IF NOT EXISTS idx_printed_item_serial_number ON printed_item(serial_number);

-- Simple subtypes — no extra UML-specified columns; exist as distinct rows for
-- type safety and future per-subtype extensibility.

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
-- LINKING TABLES
-- =============================================================================

-- R4: HoleInOne ↔ PrintedItem
--   "is comprised of" 1 (HoleInOne)  /  "is a component of" 1..* (PrintedItem)
-- Diagram shows one HoleInOne composed of many PrintedItem instances and each
-- PrintedItem belonging to exactly one HoleInOne.  However, because
-- PrintedItem is also referenced from three_mf (R3, many-to-many), we
-- pragmatically model this as a many-to-many junction so a printed_item row
-- can be reused across HoleInOne records if the pipeline ever produces
-- shared components.  Application layer enforces "1 HoleInOne per
-- printed_item" if that invariant holds.
CREATE TABLE IF NOT EXISTS hole_in_one_printed_item (
    id               INTEGER PRIMARY KEY,
    hole_in_one_id   INTEGER NOT NULL REFERENCES hole_in_one(id)  ON DELETE CASCADE,
    printed_item_id  INTEGER NOT NULL REFERENCES printed_item(id) ON DELETE CASCADE,
    UNIQUE (hole_in_one_id, printed_item_id)
);

CREATE INDEX IF NOT EXISTS idx_hio_pi_hole_in_one_id
    ON hole_in_one_printed_item(hole_in_one_id);
CREATE INDEX IF NOT EXISTS idx_hio_pi_printed_item_id
    ON hole_in_one_printed_item(printed_item_id);

-- R3: three_mf ↔ printed_item  (many-to-many: 0..* ↔ 1..*)
CREATE TABLE IF NOT EXISTS three_mf_printed_item (
    id               INTEGER PRIMARY KEY,
    three_mf_id      INTEGER NOT NULL REFERENCES three_mf(id)     ON DELETE CASCADE,
    printed_item_id  INTEGER NOT NULL REFERENCES printed_item(id)  ON DELETE CASCADE,
    UNIQUE (three_mf_id, printed_item_id)
);

CREATE INDEX IF NOT EXISTS idx_tmf_pi_three_mf_id
    ON three_mf_printed_item(three_mf_id);
CREATE INDEX IF NOT EXISTS idx_tmf_pi_printed_item_id
    ON three_mf_printed_item(printed_item_id);

-- =============================================================================
-- INTERPRETATION NOTES
-- =============================================================================
--
-- 1. EMG_File → EGM_File: The UML diagram labels this entity "EMG_File".
--    Every other reference in the golf pipeline uses ".egm" files; this is
--    treated as a diagram typo and corrected to `egm_file` here.
--
-- 2. OrderingPerson ↔ ShippingAddress cardinality (R1): Not labeled in the UML.
--    Assumed one-to-many (one person, many addresses).  FK `ordering_person_id`
--    placed on `shipping_address`.
--
-- 3. OrderingPerson ↔ HoleInOne cardinality (R5): Not labeled in the UML.
--    Assumed one-to-many (one person can have multiple HoleInOne records).
--    FK `ordering_person_id` placed on `hole_in_one`.
--
-- 4. HoleInOne ↔ Hole multiplicity (0..1 ↔ 1): A HoleInOne may optionally
--    reference a Hole.  FK `hole_id` on `hole_in_one` is nullable; ON DELETE
--    SET NULL preserves the order record if the Hole row is ever removed.
--
-- 5. 3MF entity name: "3MF" starts with a digit, which is illegal as a SQL
--    identifier.  Renamed to `three_mf`.
--
-- 6. PrintedItem inheritance: Table-per-subtype chosen over single-table
--    discriminator.  Rationale in the header comment block above.
--
-- 7. Subtype child tables: Each simple subtype (frame, fringe, green, bunker,
--    water, rake, flag) has no extra UML-specified columns beyond the
--    PrintedItem fields.  The child tables exist as thin pass-throughs with
--    their own surrogate PKs, enabling future column additions per subtype
--    without schema-wide ALTER TABLE changes.
--
-- 8. plaque.club_used: UML specifies type `int`.  Stored as INTEGER.
--    Application layer is responsible for mapping integer codes to club names.
--
-- 9. Date columns: SQLite has no native DATE type.  All date fields are TEXT
--    in ISO 8601 format (YYYY-MM-DD).  Timestamps use YYYY-MM-DDTHH:MM:SSZ.
--
-- 10. ON DELETE strategies:
--     - CASCADE: child rows logically owned by the parent (addresses, subtype
--       rows, junction rows).
--     - RESTRICT: would orphan significant related data (e.g. removing a Hole
--       that has HoleInOne records attached, or removing an OrderingPerson).
--     - SET NULL: nullable FK; safer than RESTRICT when the parent record
--       might be removed but the child record should survive (e.g. egm_file
--       → three_mf, egm_file → hole_in_one, hole → hole_in_one).
--
-- 11. v0.3 delta retained — hole_in_one order lifecycle dates: Three nullable
--     TEXT columns (order_received, order_confirmed, order_shipped) track the
--     order-fulfillment lifecycle.  No CHECK constraints; the application
--     layer validates ISO 8601 date parsing.
--
-- 12. v0.5 delta — NEW R2 relationship: HoleInOne ↔ EMG_File.
--     The diagram draws an edge between HoleInOne and EMG_File labeled only
--     "R2" — no verb phrases and no multiplicity markers on either end.
--     Two plausible interpretations:
--       (a) each HoleInOne originates from at most one authoritative EMG
--           source file (many-to-one, nullable);
--       (b) many-to-many, if a HoleInOne can pull from multiple EMG files.
--     Interpretation (a) chosen: it matches the R8 pattern (three_mf →
--     egm_file, 0..1) and matches the actual golf pipeline (one EMG per hole
--     order).  Modeled as nullable `egm_file_id` on `hole_in_one` with
--     ON DELETE SET NULL.  If interpretation (b) turns out to be correct,
--     migrate by dropping this column and adding a `hole_in_one_egm_file`
--     junction table.  FLAGGED for Thomas's confirmation.
--
-- 13. v0.5 delta — R4 (HoleInOne ↔ PrintedItem) modeled as junction:
--     Diagram labels this 1 (HoleInOne) ↔ 1..* (PrintedItem), which is a
--     classic one-to-many and could live as an FK on `printed_item`.
--     However, PrintedItem participates in R3 as a many-to-many with
--     three_mf, and the pipeline may reasonably share printed_item rows
--     across HoleInOne records.  Chose a junction table
--     (`hole_in_one_printed_item`) to keep the composition flexible.  If a
--     strict 1:N is required later, add a UNIQUE(printed_item_id) constraint
--     on the junction table — no data migration needed.
--
-- =============================================================================
