-- =============================================================================
-- iwi_enterprise_v1.1_schema.sql
-- Source:      UML class diagram "Hole In One (v1.1)"
--              (file: ItWentIn/IWI Enterprise Database Schema.drawio)
-- Task:        Assigned to Reed by Larry (workspace task id 492)
-- Date:        2026-09-07
-- Author:      Reed — Database Engineer
--
-- Delta from v1.0:
--   * REMOVED relationship Hole ↔ HoleInOne.  v1.0 had a direct FK
--     `hole_in_one.hole_id`; v1.1 diagram no longer draws that edge.  Thomas
--     has confirmed the R9 gap in numbering is intentional, and the pathway
--     from HoleInOne to a specific Hole now goes only via the Hole record's
--     own course + number (or through R10 HoleInOne → GolfCourse for the
--     course-level tie).  Column `hole_id` DROPPED from `hole_in_one`.
--   * All other tables, columns, and relationships carried forward from v1.0
--     unchanged (see v1.0 header for the v0.5 → v1.0 delta).
--
-- INHERITANCE STRATEGY: Table-per-subtype (unchanged from v1.0)
-- ----------------------------------------
-- PrintedItem has 7 simple subtypes (Frame, Fringe, Green, Bunker, Water, Rake,
-- Flag) plus one richer subtype (Plaque) with 5 extra columns.  Rationale for
-- table-per-subtype vs single-table discriminator: Plaque columns would be NULL
-- for every other row in a single-table layout, and per-subtype ALTER TABLE
-- stays local to the affected child.
--
-- DATE COLUMNS: SQLite has no native DATE type.  Dates → TEXT ISO 8601
-- (YYYY-MM-DD).  Timestamps → YYYY-MM-DDTHH:MM:SSZ.
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

-- GolfCourse: carries `state` from v1.0.
CREATE TABLE IF NOT EXISTS golf_course (
    id          INTEGER PRIMARY KEY,
    name        TEXT    NOT NULL,
    state       TEXT,
    created_at  TEXT    NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%SZ','now')),
    updated_at  TEXT    NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%SZ','now'))
);

CREATE INDEX IF NOT EXISTS idx_golf_course_name  ON golf_course(name);
CREATE INDEX IF NOT EXISTS idx_golf_course_state ON golf_course(state);

CREATE TABLE IF NOT EXISTS image_file (
    id          INTEGER PRIMARY KEY,
    name        TEXT    NOT NULL,   -- FullyQualifiedFilename in the UML
    created_at  TEXT    NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%SZ','now')),
    updated_at  TEXT    NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%SZ','now'))
);

CREATE INDEX IF NOT EXISTS idx_image_file_name ON image_file(name);

CREATE TABLE IF NOT EXISTS ordering_person (
    id                   INTEGER PRIMARY KEY,
    name                 TEXT    NOT NULL,
    email_address        TEXT    NOT NULL,
    text_message_number  INTEGER,
    created_at           TEXT    NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%SZ','now')),
    updated_at           TEXT    NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%SZ','now'))
);

CREATE INDEX IF NOT EXISTS idx_ordering_person_email ON ordering_person(email_address);

-- =============================================================================
-- EGM_FILE (diagram label: EMGFile — treated as a diagram-side typo of EGM.
-- Every ".egm" file in the pipeline is spelled EGM; renamed for consistency.)
-- Declared before hole_in_one because hole_in_one references it (R2).
-- =============================================================================

CREATE TABLE IF NOT EXISTS egm_file (
    id          INTEGER PRIMARY KEY,
    name        TEXT    NOT NULL,   -- FullyQualifiedFilename in the UML
    created_at  TEXT    NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%SZ','now')),
    updated_at  TEXT    NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%SZ','now'))
);

CREATE INDEX IF NOT EXISTS idx_egm_file_name ON egm_file(name);

-- =============================================================================
-- TABLES DEPENDENT ON ROOT TABLES
-- =============================================================================

-- ShippingAddress: R1 OrderingPerson ↔ ShippingAddress.  v1.1 diagram now
-- labels this edge with cardinalities "1 / 1" ("is home to" / "lives at").
-- Taken at face value that would mean each person has exactly one address and
-- each address belongs to exactly one person.  Interpretation held from v1.0:
-- modeled as one-to-many (one person can have many addresses) — matches real
-- ordering workflows better than strict 1:1.  If Thomas truly wants strict
-- 1:1, add UNIQUE(ordering_person_id).  FLAGGED — see note 2.
CREATE TABLE IF NOT EXISTS shipping_address (
    id                  INTEGER PRIMARY KEY,
    ordering_person_id  INTEGER NOT NULL REFERENCES ordering_person(id) ON DELETE CASCADE,
    street              TEXT    NOT NULL,
    city                TEXT    NOT NULL,
    state               TEXT    NOT NULL,
    zip                 TEXT    NOT NULL,   -- TEXT: preserves leading zeros (UML says int)
    created_at          TEXT    NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%SZ','now')),
    updated_at          TEXT    NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%SZ','now'))
);

CREATE INDEX IF NOT EXISTS idx_shipping_address_ordering_person_id
    ON shipping_address(ordering_person_id);

-- Hole:
--   R7 GolfCourse 1 → Hole 1..*   (NOT NULL FK, RESTRICT — a Hole must have a course)
--   R6 Hole 1 ↔ ImageFile 1       (NOT NULL FK, RESTRICT — every hole has an image)
CREATE TABLE IF NOT EXISTS hole (
    id              INTEGER PRIMARY KEY,
    number          INTEGER NOT NULL,
    golf_course_id  INTEGER NOT NULL REFERENCES golf_course(id) ON DELETE RESTRICT,
    image_file_id   INTEGER NOT NULL REFERENCES image_file(id)  ON DELETE RESTRICT,
    created_at      TEXT    NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%SZ','now')),
    updated_at      TEXT    NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%SZ','now'))
);

CREATE INDEX IF NOT EXISTS idx_hole_golf_course_id ON hole(golf_course_id);
CREATE INDEX IF NOT EXISTS idx_hole_image_file_id  ON hole(image_file_id);
CREATE INDEX IF NOT EXISTS idx_hole_number         ON hole(number);

-- HoleInOne: the order/root record.
--   R5  OrderingPerson → HoleInOne          (1..*: NOT NULL FK)
--   R4  HoleInOne → PrintedItem             (junction — see hole_in_one_printed_item)
--   R2  HoleInOne ↔ EGM_File                (1:1 in diagram; nullable — see note 11)
--   R10 HoleInOne ↔ GolfCourse              (1..* : 1; nullable — see note 12)
--
--   v1.1 CHANGE: `hole_id` DROPPED.  v1.0 modeled a direct HoleInOne → Hole
--   FK, but v1.1 removes that edge entirely.  The tie to a specific hole now
--   lives in the domain, not in HoleInOne.  See note 17.
CREATE TABLE IF NOT EXISTS hole_in_one (
    id                          INTEGER PRIMARY KEY,
    ordering_person_id          INTEGER NOT NULL REFERENCES ordering_person(id) ON DELETE RESTRICT,
    golf_course_id              INTEGER          REFERENCES golf_course(id)     ON DELETE SET NULL,
    egm_file_id                 INTEGER          REFERENCES egm_file(id)        ON DELETE SET NULL,
    name                        TEXT,
    golfers_name                TEXT,
    flag_clicks_from_center_x   INTEGER,
    flag_clicks_from_center_y   INTEGER,
    order_received              TEXT,                                            -- ISO 8601 date
    order_confirmed             TEXT,                                            -- ISO 8601 date
    order_shipped               TEXT,                                            -- ISO 8601 date
    purchase_price              INTEGER,                                         -- cents (see note 13)
    payment_received            INTEGER CHECK (payment_received IN (0,1)),       -- boolean
    created_at                  TEXT    NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%SZ','now')),
    updated_at                  TEXT    NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%SZ','now'))
);

CREATE INDEX IF NOT EXISTS idx_hole_in_one_ordering_person_id ON hole_in_one(ordering_person_id);
CREATE INDEX IF NOT EXISTS idx_hole_in_one_golf_course_id     ON hole_in_one(golf_course_id);
CREATE INDEX IF NOT EXISTS idx_hole_in_one_egm_file_id        ON hole_in_one(egm_file_id);
CREATE INDEX IF NOT EXISTS idx_hole_in_one_order_received     ON hole_in_one(order_received);

-- =============================================================================
-- THREE_MF  (diagram label: 3MF — leading digit is illegal as a SQL identifier)
--   R8 3MF ↔ EGM_File: 3MF 1 → EGM_File 0..1  (nullable FK on three_mf)
-- =============================================================================

CREATE TABLE IF NOT EXISTS three_mf (
    id              INTEGER PRIMARY KEY,
    name            TEXT    NOT NULL,   -- FullyQualifiedFilename in the UML
    egm_file_id     INTEGER          REFERENCES egm_file(id) ON DELETE SET NULL,
    created_at      TEXT    NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%SZ','now')),
    updated_at      TEXT    NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%SZ','now'))
);

CREATE INDEX IF NOT EXISTS idx_three_mf_egm_file_id ON three_mf(egm_file_id);
CREATE INDEX IF NOT EXISTS idx_three_mf_name        ON three_mf(name);

-- =============================================================================
-- PRINTED_ITEM (parent) + subtypes  (table-per-subtype — see header rationale)
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

CREATE INDEX IF NOT EXISTS idx_printed_item_kind          ON printed_item(kind);
CREATE INDEX IF NOT EXISTS idx_printed_item_serial_number ON printed_item(serial_number);

-- Simple subtypes: diagram shows a placeholder "+ attribute: type" column on
-- most subtype boxes, which is a UML placeholder — not a real column.  Frame
-- has no column listed at all.  Modeled as thin pass-throughs so per-subtype
-- columns can be added later without touching the parent.

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

-- Plaque — richer subtype.
--   club_used remains TEXT (v1.0 established this).
CREATE TABLE IF NOT EXISTS plaque (
    id               INTEGER PRIMARY KEY,
    printed_item_id  INTEGER NOT NULL UNIQUE REFERENCES printed_item(id) ON DELETE CASCADE,
    hole_number      INTEGER NOT NULL,
    golfers_name     TEXT    NOT NULL,
    date             TEXT    NOT NULL,   -- ISO 8601: YYYY-MM-DD
    yards            INTEGER NOT NULL,
    club_used        TEXT    NOT NULL,
    created_at       TEXT    NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%SZ','now')),
    updated_at       TEXT    NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%SZ','now'))
);

-- =============================================================================
-- LINKING TABLES
-- =============================================================================

-- R4: HoleInOne ↔ PrintedItem
--   Diagram labels: HoleInOne "is comprised of" 1 / PrintedItem "is a component of" 1..*
--   Modeled as a junction table (rather than an FK on printed_item) so a
--   printed_item row can potentially be reused across HoleInOne records if the
--   pipeline evolves that way.  If a strict 1:N is required, add
--   UNIQUE(printed_item_id) to this junction — no data migration needed.
CREATE TABLE IF NOT EXISTS hole_in_one_printed_item (
    id               INTEGER PRIMARY KEY,
    hole_in_one_id   INTEGER NOT NULL REFERENCES hole_in_one(id)  ON DELETE CASCADE,
    printed_item_id  INTEGER NOT NULL REFERENCES printed_item(id) ON DELETE CASCADE,
    UNIQUE (hole_in_one_id, printed_item_id)
);

CREATE INDEX IF NOT EXISTS idx_hio_pi_hole_in_one_id  ON hole_in_one_printed_item(hole_in_one_id);
CREATE INDEX IF NOT EXISTS idx_hio_pi_printed_item_id ON hole_in_one_printed_item(printed_item_id);

-- R3: PrintedItem ↔ 3MF  (0..* / 1..*  — many-to-many)
CREATE TABLE IF NOT EXISTS three_mf_printed_item (
    id               INTEGER PRIMARY KEY,
    three_mf_id      INTEGER NOT NULL REFERENCES three_mf(id)     ON DELETE CASCADE,
    printed_item_id  INTEGER NOT NULL REFERENCES printed_item(id) ON DELETE CASCADE,
    UNIQUE (three_mf_id, printed_item_id)
);

CREATE INDEX IF NOT EXISTS idx_tmf_pi_three_mf_id     ON three_mf_printed_item(three_mf_id);
CREATE INDEX IF NOT EXISTS idx_tmf_pi_printed_item_id ON three_mf_printed_item(printed_item_id);

-- =============================================================================
-- INTERPRETATION NOTES
-- =============================================================================
--
-- 1. EMGFile → egm_file: Diagram-side typo carried from v0.5/v1.0.  Every
--    actual pipeline file uses ".egm"; renamed for consistency.
--
-- 2. R1 OrderingPerson ↔ ShippingAddress: v1.1 diagram now shows cardinalities
--    "1 / 1" ("is home to" / "lives at").  Held the v1.0 interpretation of 1:N
--    (one person, many addresses) — matches how orders actually work (billing
--    vs. shipping address).  If strict 1:1 is intended, add
--    UNIQUE(ordering_person_id).  FLAGGED for Thomas — this is a NEW ambiguity
--    in v1.1.
--
-- 3. R5 OrderingPerson ↔ HoleInOne: Labeled 1 / 1..*.  Standard parent-child.
--    NOT NULL FK on hole_in_one, ON DELETE RESTRICT.
--
-- 4. R6 Hole ↔ ImageFile (1 / 1): Diagram shows an FK on the Hole side.
--    Modeled as NOT NULL image_file_id on hole with ON DELETE RESTRICT.
--    Strict 1:1 (UNIQUE image_file_id on hole) is NOT enforced at the schema
--    level — the diagram's "1 ↔ 1" is more accurately "each hole has one
--    image; images may be reused across holes."
--
-- 5. R7 GolfCourse ↔ Hole (1 ↔ 1..*): Standard parent-child.  NOT NULL FK on
--    hole, ON DELETE RESTRICT.
--
-- 6. R8 3MF ↔ EGM_File (1 ↔ 0..1): FK on three_mf, nullable.  A 3MF may exist
--    before its EGM has been created.  ON DELETE SET NULL preserves the 3MF
--    row if the EGM is removed.
--
-- 7. R4 HoleInOne ↔ PrintedItem: Modeled as a junction table rather than a
--    direct FK on printed_item.  See table comment above for rationale.
--
-- 8. 3MF entity name: "3MF" starts with a digit; renamed to `three_mf` (SQL
--    identifiers cannot begin with a digit).
--
-- 9. PrintedItem inheritance: Table-per-subtype.  Simple subtype boxes show a
--    placeholder "+ attribute: type" column — treated as UML boilerplate, not
--    a real column.  Frame has no column listed and no attributes were added.
--
-- 10. Date columns: SQLite has no native DATE type.  All date fields are TEXT
--     in ISO 8601 (YYYY-MM-DD).  Timestamps are YYYY-MM-DDTHH:MM:SSZ.
--
-- 11. R2 HoleInOne ↔ EGM_File: v1.1 labels this "1 / 1" ("gives instructions
--     to build" / "is the construction file for slicer").  Kept the practical
--     v1.0 interpretation of many-to-one, nullable: an order may exist before
--     the EGM has been generated.  If strict 1:1 is intended, add
--     UNIQUE(egm_file_id) and change to NOT NULL after backfill.  Not yet
--     flagged as newly-blocking since v1.0 already treated it this way.
--
-- 12. R10 HoleInOne ↔ GolfCourse: v1.1 labels this 1..* / 1 ("is host to" /
--     "is hosted on").  Modeled as NULLABLE many-to-one on hole_in_one so
--     early-stage orders (before course pick) still validate.  Consistency
--     risk unchanged from v1.0 (see note 15).
--
-- 13. purchase_price: UML type is "currency".  Stored as INTEGER cents.
--
-- 14. payment_received: UML type is "bool".  Stored as INTEGER with
--     CHECK (col IN (0,1)).
--
-- 15. hole_in_one.name vs hole_in_one.golfers_name: Kept split as v1.0.
--     `name` is the ordering party's label; `golfers_name` is the person who
--     hit the shot.  Plaque also carries `golfers_name` (redundant on purpose
--     — the plaque is physical media that freezes its own copy).
--
-- 16. ON DELETE strategies:
--     - CASCADE : child rows logically owned by parent (addresses, subtype
--                 rows, junction rows).
--     - RESTRICT: would orphan significant related data (course with holes,
--                 person with orders).
--     - SET NULL: nullable FK; child survives parent deletion (golf_course →
--                 hole_in_one, egm_file → hole_in_one, egm_file → three_mf).
--
-- 17. v1.1 CHANGE — Hole ↔ HoleInOne edge removed.  v1.0 had
--     `hole_in_one.hole_id` (nullable FK, SET NULL on delete).  v1.1 diagram
--     drops that edge entirely.  Thomas has confirmed the R9 numbering gap is
--     intentional, so the drop is authoritative.  Column `hole_id` DROPPED,
--     along with `idx_hole_in_one_hole_id`.  The hole-level tie now flows
--     through the domain layer (or via the GolfCourse — Hole join through the
--     R10 course tie) rather than via a HoleInOne FK.
--
-- 18. R9 gap: R1, R2, R3, R4, R5, R6, R7, R8, R10 present.  R9 intentionally
--     unused per Thomas.  Not flagged.
--
-- =============================================================================
