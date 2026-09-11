#!/usr/bin/env python3
"""populate_v1_2.py — Populate iwi_enterprise_v1.2.db from ItWentIn/GolfCourses/.

Reed — Database Engineer.  Re-runnable: wipes the five content tables in
reverse-FK order before inserting.  Wraps all work in a single transaction.

Tables populated:
    golf_course, hole, egm_file, three_mf, image_file

Tables left empty (order-side, not folder-derived):
    ordering_person, shipping_address, hole_in_one, printed_item,
    frame, fringe, green, bunker, water, rake, flag, plaque,
    three_mf_printed_item, hole_in_one_printed_item

Design notes:
  * hole.number is INTEGER NOT NULL.  Filenames like "Hole 11a" or
    "Hole quadrabyte@protonmail.com" cannot be represented in an integer
    column, so we DO NOT create a hole row for those.  The EGM / 3MF /
    Image file rows are still created (they don't require a hole FK).
  * hole.image_file_id is NOT NULL.  For each parseable (course, hole-int)
    we prefer an on-disk image whose filename contains the hole number in
    parentheses (e.g. "Firefly Golf Links (14).png").  If nothing matches,
    we fall back to the "image" field inside the EGM JSON — creating an
    image_file row if the file is not already in Images/.
  * three_mf.egm_file_id is nullable.  We link a 3MF to the matching EGM
    (same course, same hole-int) when one exists; otherwise NULL.
  * image_file has no direct hole FK in this schema — the hole → image
    tie flows through hole.image_file_id.
"""

from __future__ import annotations

import json
import os
import re
import sqlite3
import sys
from pathlib import Path

ROOT       = Path("/Volumes/GIT/CLAUDE/SHARED_WORK_FOLDER")
COURSE_DIR = ROOT / "ItWentIn" / "GolfCourses"
DB_PATH    = ROOT / "db" / "iwi_enterprise_v1.2.db"

# Filename patterns
EGM_HOLE_RE = re.compile(r"\(Hole ([^)]+)\)\.egm$", re.IGNORECASE)
TMF_HOLE_RE = re.compile(r"\(Hole ([^)]+)\)\s*\[(\d+)\]\.3mf$", re.IGNORECASE)
# Image: capture a token inside the LAST parenthetical group before the extension
IMG_HOLE_RE = re.compile(r"\(([^)]+)\)[^()]*\.(?:png|jpe?g)$", re.IGNORECASE)
INT_HOLE_RE = re.compile(r"^(\d+)")   # leading integer, e.g. "14a" → 14


def parse_hole_int(raw: str) -> int | None:
    """Extract a leading integer from a raw hole string.  Return None if none.

    Examples:
        "14"    -> 14
        "11a"   -> 11        (schema is INTEGER — best-effort truncation)
        "888"   -> 888
        "x"     -> None
        "zzzz"  -> None
        "06105" -> 6105
    """
    m = INT_HOLE_RE.match(raw.strip())
    return int(m.group(1)) if m else None


def scan_course(course_dir: Path):
    """Return a dict of file lists for one course folder."""
    egms   = sorted((course_dir / "EGMs").glob("*.egm"))   if (course_dir / "EGMs").is_dir()   else []
    tmfs   = sorted((course_dir / "3MFs").glob("*.3mf"))   if (course_dir / "3MFs").is_dir()   else []
    images = []
    if (course_dir / "Images").is_dir():
        for ext in ("*.png", "*.jpg", "*.jpeg", "*.PNG", "*.JPG", "*.JPEG"):
            images.extend((course_dir / "Images").glob(ext))
    images.sort()
    return egms, tmfs, images


def load_egm_json(path: Path) -> dict | None:
    try:
        with open(path, "r", encoding="utf-8") as fh:
            return json.load(fh)
    except (json.JSONDecodeError, OSError):
        return None


def main() -> int:
    if not DB_PATH.exists():
        print(f"ERROR: {DB_PATH} does not exist.", file=sys.stderr)
        return 1

    conn = sqlite3.connect(DB_PATH)
    # Standard PRAGMAs (Reed's convention)
    conn.execute("PRAGMA foreign_keys = ON")
    conn.execute("PRAGMA journal_mode = WAL")
    conn.execute("PRAGMA busy_timeout = 5000")
    cur = conn.cursor()

    # Reports
    unparseable_holes: list[tuple[str, str, str]] = []   # (course, raw_hole, egm_name)
    holes_missing_image: list[tuple[str, int]]  = []     # (course, hole_int)
    unusual_courses: list[str] = []
    synthetic_images: list[tuple[str, str]] = []         # (course, image_filename_from_json)

    try:
        cur.execute("BEGIN")

        # --- wipe existing content-table rows in reverse-FK order ---
        for tbl in (
            "three_mf",
            "hole",
            "egm_file",
            "image_file",
            "golf_course",
        ):
            cur.execute(f"DELETE FROM {tbl}")

        # ------------------------------------------------------------------
        # Walk each course folder
        # ------------------------------------------------------------------
        course_folders = sorted(
            p for p in COURSE_DIR.iterdir() if p.is_dir()
        )

        for course_dir in course_folders:
            course_name = course_dir.name

            # Flag unusual layouts
            required = ["EGMs", "3MFs", "Images"]
            missing = [s for s in required if not (course_dir / s).is_dir()]
            if missing:
                unusual_courses.append(f"{course_name} (missing: {', '.join(missing)})")

            # 1) golf_course
            cur.execute(
                "INSERT INTO golf_course (name) VALUES (?)",
                (course_name,),
            )
            course_id = cur.lastrowid

            egms, tmfs, images = scan_course(course_dir)

            # ---------- 4) image_file (up front so holes can reference) --------
            # Map: image basename (case-insensitive) -> image_file.id
            image_id_by_name: dict[str, int] = {}
            for img in images:
                cur.execute("INSERT INTO image_file (name) VALUES (?)", (img.name,))
                image_id_by_name[img.name.lower()] = cur.lastrowid

            # ---------- 3) egm_file + 2) hole (needs egm/image linkage) --------
            # We store: for each parseable (course, hole_int), which egm_file_id
            # and which image_file_id to use for the hole row.
            hole_int_to_egm_id: dict[int, int] = {}

            for egm_path in egms:
                m = EGM_HOLE_RE.search(egm_path.name)
                if not m:
                    unparseable_holes.append((course_name, "<no match>", egm_path.name))
                    # still insert the egm_file row so orphan files are captured
                    cur.execute("INSERT INTO egm_file (name) VALUES (?)", (egm_path.name,))
                    continue

                raw_hole = m.group(1).strip()
                hole_int = parse_hole_int(raw_hole)

                # Always insert the egm_file row
                cur.execute("INSERT INTO egm_file (name) VALUES (?)", (egm_path.name,))
                egm_file_id = cur.lastrowid

                if hole_int is None:
                    unparseable_holes.append((course_name, raw_hole, egm_path.name))
                    continue

                # Pick an image for this hole:
                # 1) any Images/*.png|jpg whose parenthetical contains the hole int
                image_file_id: int | None = None
                for img in images:
                    im = IMG_HOLE_RE.search(img.name)
                    if not im:
                        continue
                    inside = im.group(1).strip()
                    ih = parse_hole_int(inside)
                    if ih == hole_int:
                        image_file_id = image_id_by_name[img.name.lower()]
                        break

                # 2) fall back to the EGM's JSON "image" field.
                if image_file_id is None:
                    egm_json = load_egm_json(egm_path)
                    json_image = (egm_json or {}).get("image")
                    if json_image:
                        json_image_lc = json_image.lower()
                        if json_image_lc in image_id_by_name:
                            image_file_id = image_id_by_name[json_image_lc]
                        else:
                            # Not on disk — insert a synthetic image_file row
                            # (record-only, per the spec).
                            cur.execute(
                                "INSERT INTO image_file (name) VALUES (?)",
                                (json_image,),
                            )
                            image_file_id = cur.lastrowid
                            image_id_by_name[json_image_lc] = image_file_id
                            synthetic_images.append((course_name, json_image))

                if image_file_id is None:
                    # Cannot satisfy NOT NULL image_file_id — skip this hole row
                    holes_missing_image.append((course_name, hole_int))
                    continue

                # Insert hole
                cur.execute(
                    "INSERT INTO hole (number, golf_course_id, image_file_id) "
                    "VALUES (?, ?, ?)",
                    (hole_int, course_id, image_file_id),
                )
                hole_int_to_egm_id[hole_int] = egm_file_id

            # ---------- 5) three_mf -----------------------------------------
            for tmf_path in tmfs:
                m = TMF_HOLE_RE.search(tmf_path.name)
                egm_link: int | None = None
                if m:
                    raw_hole = m.group(1).strip()
                    hole_int = parse_hole_int(raw_hole)
                    if hole_int is not None and hole_int in hole_int_to_egm_id:
                        egm_link = hole_int_to_egm_id[hole_int]
                cur.execute(
                    "INSERT INTO three_mf (name, egm_file_id) VALUES (?, ?)",
                    (tmf_path.name, egm_link),
                )

        # ------------------------------------------------------------------
        # Integrity check
        # ------------------------------------------------------------------
        fk_violations = cur.execute("PRAGMA foreign_key_check").fetchall()
        if fk_violations:
            print("FK violations found:", fk_violations, file=sys.stderr)
            conn.rollback()
            return 2

        conn.commit()

    except Exception:
        conn.rollback()
        raise

    # -------------------- Report ------------------------------------------
    print("=== Row counts ===")
    for tbl in ("golf_course", "hole", "egm_file", "three_mf", "image_file"):
        n = cur.execute(f"SELECT COUNT(*) FROM {tbl}").fetchone()[0]
        print(f"  {tbl:15s} {n}")

    if unusual_courses:
        print("\n=== Courses with unusual layout ===")
        for u in unusual_courses:
            print(f"  {u}")

    if unparseable_holes:
        print("\n=== Unparseable hole numbers (EGM row inserted, hole row skipped) ===")
        for c, raw, fn in unparseable_holes:
            print(f"  [{c}] raw={raw!r}  file={fn}")

    if holes_missing_image:
        print("\n=== Holes skipped: no image found (on-disk or in EGM JSON) ===")
        for c, h in holes_missing_image:
            print(f"  [{c}] hole {h}")

    if synthetic_images:
        print("\n=== Synthetic image_file rows (image referenced in EGM JSON but not in Images/) ===")
        for c, name in synthetic_images:
            print(f"  [{c}] {name}")

    conn.close()
    return 0


if __name__ == "__main__":
    sys.exit(main())
