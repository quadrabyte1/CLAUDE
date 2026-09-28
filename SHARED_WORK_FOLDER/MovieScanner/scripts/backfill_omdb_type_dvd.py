#!/usr/bin/env python3
"""backfill_omdb_type_dvd.py — One-shot backfill for title_metadata rows
that are missing the V3.25 ``type`` or ``dvd`` columns.

Background
----------
V3.25 added ``dvd`` and ``type`` columns to ``title_metadata``.  The
theatrical-window filter reads these fields. Any title whose cached row
pre-dates V3.25 has ``type=NULL`` and ``dvd=NULL``, causing the filter to
fall through to a heuristic that may misclassify tvSeries as "only in
theaters."

This script re-fetches those rows from OMDb using ``force_refresh=True``
(which deletes the stale cache row and re-inserts with the new fields).

Usage
-----
    python3 MovieScanner/scripts/backfill_omdb_type_dvd.py [--db PATH] [--dry-run]

Options
-------
--db PATH       Path to scanner.db (default: auto-detects sibling db/scanner.db).
--dry-run       Print counts without fetching anything.

Safety
------
- Back up scanner.db before running. This script prints the backup path.
- Rate limit: 250 ms between calls (~4 req/s, well under OMDb's cap).
- Ctrl-C finishes the current fetch then exits gracefully.
- All automated tests use a temp DB -- the live DB is never touched by tests.
"""

import argparse
import os
import shutil
import signal
import sqlite3
import sys
import time

# ── Path setup ────────────────────────────────────────────────────────────────
# The script lives in MovieScanner/scripts/; the movie_scanner package is at
# the repo root (one level above MovieScanner/).  Both need to be on sys.path.
_SCRIPT_DIR   = os.path.dirname(os.path.abspath(__file__))
_MS_DIR       = os.path.dirname(_SCRIPT_DIR)          # MovieScanner/
_REPO_ROOT    = os.path.dirname(_MS_DIR)               # repo root
for _p in (_MS_DIR, _REPO_ROOT):
    if _p not in sys.path:
        sys.path.insert(0, _p)

from movie_scanner.omdb import OMDbClient             # noqa: E402

# ── Constants ─────────────────────────────────────────────────────────────────
RATE_LIMIT_SEC  = 0.25   # 250 ms between API calls
PROGRESS_EVERY  = 50     # print a progress line every N rows

# ── Graceful Ctrl-C handling ──────────────────────────────────────────────────
_STOP_REQUESTED = False


def _on_sigint(sig, frame):                            # noqa: ARG001
    global _STOP_REQUESTED
    _STOP_REQUESTED = True
    print("\n[backfill] Ctrl-C received — finishing current fetch, then stopping.")


signal.signal(signal.SIGINT, _on_sigint)


# ── Helpers ───────────────────────────────────────────────────────────────────

def _default_db_path() -> str:
    """Return the default scanner.db path relative to this script."""
    return os.path.join(_MS_DIR, "db", "scanner.db")


def _read_omdb_key(db_path: str) -> str | None:
    """Return the OMDb API key from the config table, or None if absent."""
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    try:
        row = conn.execute(
            "SELECT value FROM config WHERE key='omdb_api_key'"
        ).fetchone()
        return row["value"] if row and row["value"] else None
    finally:
        conn.close()


def _rows_needing_refresh(db_path: str) -> list[str]:
    """Return tconsts whose title_metadata row is missing type or dvd."""
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    try:
        rows = conn.execute(
            """
            SELECT tconst
            FROM title_metadata
            WHERE (type IS NULL OR type = '')
               OR (dvd  IS NULL OR dvd  = '')
            ORDER BY tconst
            """
        ).fetchall()
        return [r["tconst"] for r in rows]
    finally:
        conn.close()


def _backup_db(db_path: str) -> str:
    """Copy scanner.db to scanner.db.pre_backfill_<date> and return the path."""
    from datetime import date
    backup_path = f"{db_path}.pre_backfill_{date.today().strftime('%Y-%m-%d')}"
    shutil.copy2(db_path, backup_path)
    return backup_path


# ── Main ──────────────────────────────────────────────────────────────────────

def run_backfill(db_path: str, dry_run: bool = False) -> dict:
    """Execute the backfill and return a summary dict.

    Parameters
    ----------
    db_path:
        Absolute path to scanner.db.
    dry_run:
        If True, count rows and print the plan without fetching.

    Returns
    -------
    dict with keys: refreshed, errored, skipped (Ctrl-C), elapsed_sec,
                    errored_tconsts (list of tconst strings).
    """
    if not os.path.exists(db_path):
        print(f"[backfill] ERROR: database not found at {db_path}", file=sys.stderr)
        sys.exit(1)

    api_key = _read_omdb_key(db_path)
    if not api_key:
        print(
            "[backfill] ERROR: no omdb_api_key in config table. "
            "Configure it in the MovieScanner web UI first.",
            file=sys.stderr,
        )
        sys.exit(1)

    tconsts = _rows_needing_refresh(db_path)
    total   = len(tconsts)

    print(f"[backfill] Rows needing refresh: {total}")
    if total == 0:
        print("[backfill] Nothing to do — all rows already have type+dvd populated.")
        return {"refreshed": 0, "errored": 0, "skipped": 0, "elapsed_sec": 0.0,
                "errored_tconsts": []}

    estimated_sec = total * RATE_LIMIT_SEC
    estimated_min = estimated_sec / 60
    print(
        f"[backfill] Estimated {total} OMDb calls "
        f"at {RATE_LIMIT_SEC*1000:.0f} ms/call "
        f"≈ {estimated_sec:.0f}s ({estimated_min:.1f} min)"
    )

    if dry_run:
        print("[backfill] --dry-run: no fetches performed.")
        return {"refreshed": 0, "errored": 0, "skipped": 0, "elapsed_sec": 0.0,
                "errored_tconsts": []}

    # Back up before touching anything.
    backup_path = _backup_db(db_path)
    print(f"[backfill] Backup written to: {backup_path}")
    print("[backfill] Starting fetch loop…")

    client         = OMDbClient(api_key=api_key, db_path=db_path)
    refreshed      = 0
    errored        = 0
    errored_tconsts: list[str] = []
    start_time     = time.monotonic()

    for i, tconst in enumerate(tconsts, start=1):
        if _STOP_REQUESTED:
            print(f"[backfill] Stopped by user after {i-1} fetches.")
            break

        try:
            meta = client.fetch(tconst, force_refresh=True)
            if meta.get("error"):
                errored += 1
                errored_tconsts.append(tconst)
                print(f"[backfill] ERROR {tconst}: {meta['error']}")
            else:
                refreshed += 1
        except Exception as exc:
            errored += 1
            errored_tconsts.append(tconst)
            print(f"[backfill] EXCEPTION {tconst}: {exc}")

        if i % PROGRESS_EVERY == 0:
            elapsed = time.monotonic() - start_time
            print(
                f"[backfill] {i}/{total} fetched "
                f"({refreshed} refreshed, {errored} errors) "
                f"— {elapsed:.0f}s elapsed"
            )

        # Rate limit (skip after the last item).
        if i < total and not _STOP_REQUESTED:
            time.sleep(RATE_LIMIT_SEC)

    elapsed_sec = time.monotonic() - start_time
    skipped = total - (refreshed + errored) if _STOP_REQUESTED else 0

    print(
        f"\n[backfill] Done. "
        f"refreshed={refreshed}, errored={errored}, "
        f"skipped={skipped}, elapsed={elapsed_sec:.1f}s"
    )
    if errored_tconsts:
        print(f"[backfill] Errored tconsts: {', '.join(errored_tconsts)}")

    return {
        "refreshed":       refreshed,
        "errored":         errored,
        "skipped":         skipped,
        "elapsed_sec":     elapsed_sec,
        "errored_tconsts": errored_tconsts,
    }


# ── CLI entrypoint ────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(
        description="Backfill title_metadata rows missing OMDb type/dvd fields."
    )
    parser.add_argument(
        "--db",
        default=_default_db_path(),
        help="Path to scanner.db (default: auto-detect sibling db/scanner.db)",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Print counts without fetching anything.",
    )
    args = parser.parse_args()

    run_backfill(db_path=args.db, dry_run=args.dry_run)


if __name__ == "__main__":
    main()
