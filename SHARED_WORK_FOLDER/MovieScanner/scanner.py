"""
scanner.py — IMDB dataset downloader + delta scanner.

Runs entirely from the two free daily-refreshed dumps at
https://datasets.imdbws.com — no scraping, no rate limiting, no ToS concerns.

Public entrypoint: `run_scan(db_path, on_progress)` — called by app.py from a
background thread.
"""

import gzip
import json
import os
import sqlite3
import time
import urllib.request
from typing import Callable, Iterable

DATASET_BASE = "https://datasets.imdbws.com"
BASICS_URL   = f"{DATASET_BASE}/title.basics.tsv.gz"
RATINGS_URL  = f"{DATASET_BASE}/title.ratings.tsv.gz"

_DATA_DIR    = os.path.join(os.path.dirname(__file__), "data")

# Chunk size for progress reporting during dump ingest.
_PROGRESS_EVERY = 100_000


# ── Downloader ─────────────────────────────────────────────────────────────

def _download(url: str, dest: str, on_progress: Callable[[str], None]) -> None:
    """Atomically stream a URL to a local file with HTTP Range-based resume.

    Writes to `dest.part` first and renames to `dest` only on successful
    completion — so an interrupted download (Werkzeug reload mid-scan,
    SIGKILL, network drop, disk full) never leaves a truncated file at
    the final path. Also verifies the byte count against the server's
    Content-Length header when available; a size mismatch triggers a
    resume attempt using the Range header before giving up.

    Resume logic:
      - If `.part` already exists from a prior run, start from that offset.
      - On a short read, re-issue with `Range: bytes=<got>-` and append.
      - If the server responds 200 (no Range support) instead of 206,
        fall back to a full restart from byte 0.
      - Up to 5 consecutive attempts that make no forward progress before
        raising. Backoff: 2 s, 4 s, 8 s, 16 s between attempts.

    User-Agent header keeps IMDB's CDN from 403-ing the plain urllib UA.
    """
    import gzip as _gzip

    os.makedirs(os.path.dirname(dest), exist_ok=True)
    part = dest + ".part"
    name = os.path.basename(dest)

    _MAX_STALL   = 5       # consecutive no-progress attempts before giving up
    _BACKOFF_BASE = 2      # seconds; doubles each stall

    total = 0              # authoritative size from first response (0 = unknown)
    stall_count = 0
    prev_got    = -1

    while True:
        # ── Figure out where we are ──────────────────────────────────────────
        got = os.path.getsize(part) if os.path.exists(part) else 0

        if got == prev_got:
            stall_count += 1
        else:
            stall_count = 0
        prev_got = got

        if stall_count >= _MAX_STALL:
            if os.path.exists(part):
                os.remove(part)
            raise IOError(
                f"download stalled for {name}: no forward progress after "
                f"{_MAX_STALL} consecutive attempts (last position {got} bytes)"
            )

        # ── Backoff between retry/resume attempts (skip on first pass) ───────
        if got > 0 or stall_count > 0:
            backoff = _BACKOFF_BASE * (2 ** max(stall_count - 1, 0))
            on_progress(
                f"resuming {name} from "
                f"{got // (1 << 20)}/{total // (1 << 20) if total else '?'} MiB"
                f" (attempt {stall_count + 1}/{_MAX_STALL}) — waiting {backoff}s…"
            )
            time.sleep(backoff)

        # ── Build request (with Range header if we have partial data) ─────────
        headers: dict = {"User-Agent": "MovieScanner/1.0"}
        if got > 0:
            headers["Range"] = f"bytes={got}-"

        req = urllib.request.Request(url, headers=headers)

        try:
            with urllib.request.urlopen(req, timeout=120) as r:
                status = r.status

                # If server ignores our Range request and sends 200, we must
                # restart from byte 0 — appending would corrupt the file.
                if got > 0 and status == 200:
                    on_progress(
                        f"{name}: server returned 200 (no Range support) — "
                        "restarting from byte 0"
                    )
                    if os.path.exists(part):
                        os.remove(part)
                    got = 0
                    prev_got = -1  # reset stall detection for the fresh start

                # First response: capture the authoritative content length.
                if total == 0:
                    cl = r.headers.get("content-length")
                    if cl:
                        total = got + int(cl)   # for 206, CL is remaining bytes

                open_mode = "ab" if (status == 206) else "wb"
                with open(part, open_mode) as f:
                    while True:
                        chunk = r.read(1 << 16)   # 64 KiB
                        if not chunk:
                            break
                        f.write(chunk)
                        got += len(chunk)
                        if total:
                            on_progress(
                                f"downloading {name}: "
                                f"{got // (1 << 20)}/{total // (1 << 20)} MiB"
                            )

        except OSError:
            # Network error mid-stream — loop will resume from current .part size
            on_progress(f"{name}: connection dropped at {got // (1 << 20)} MiB — will retry")
            continue

        # ── Check if we're done ───────────────────────────────────────────────
        got = os.path.getsize(part) if os.path.exists(part) else 0
        if total and got < total:
            # Short read — loop back and resume
            continue

        # Either total is unknown (no Content-Length) or got == total
        break

    # ── gzip integrity spot-check ─────────────────────────────────────────────
    # Cheap way to detect corruption that a byte count wouldn't catch
    # (e.g. bad byte mid-stream, CDN mangling).
    if dest.endswith(".gz"):
        try:
            with _gzip.open(part, "rb") as gz:
                while gz.read(1 << 20):
                    pass
        except (EOFError, _gzip.BadGzipFile, OSError) as exc:
            os.remove(part)
            raise IOError(f"downloaded {name} failed gzip check: {exc}")

    os.replace(part, dest)   # atomic on POSIX


def _fetch_dumps(on_progress: Callable[[str], None]) -> tuple[str, str]:
    """Download today's basics + ratings dumps to data/. Returns local paths."""
    basics_path  = os.path.join(_DATA_DIR, "title.basics.tsv.gz")
    ratings_path = os.path.join(_DATA_DIR, "title.ratings.tsv.gz")
    _download(BASICS_URL,  basics_path,  on_progress)
    _download(RATINGS_URL, ratings_path, on_progress)
    return basics_path, ratings_path


# ── Parsers ────────────────────────────────────────────────────────────────

def _iter_basics(path: str, keep_types: set[str]) -> Iterable[tuple]:
    """Yield (tconst, titleType, primaryTitle, startYear, runtime, genres) tuples
    for rows whose titleType is in keep_types. Skips the header row."""
    with gzip.open(path, "rt", encoding="utf-8", errors="replace") as f:
        header = f.readline()  # noqa: skip header
        for line in f:
            parts = line.rstrip("\n").split("\t")
            if len(parts) < 9:
                continue
            tconst, title_type = parts[0], parts[1]
            if title_type not in keep_types:
                continue
            primary_title = parts[2]
            start_year   = parts[5]  # "\N" or a year string
            runtime_min  = parts[7]  # "\N" or minutes string
            genres       = parts[8]  # "\N" or comma-separated
            yield (
                tconst,
                title_type,
                primary_title,
                None if start_year  == "\\N" else int(start_year),
                None if runtime_min == "\\N" else int(runtime_min),
                None if genres      == "\\N" else genres,
            )


def _load_ratings(path: str) -> dict[str, tuple[float, int]]:
    """Load ratings.tsv into a dict: tconst -> (rating, votes)."""
    out: dict[str, tuple[float, int]] = {}
    with gzip.open(path, "rt", encoding="utf-8", errors="replace") as f:
        f.readline()  # header
        for line in f:
            parts = line.rstrip("\n").split("\t")
            if len(parts) != 3:
                continue
            try:
                out[parts[0]] = (float(parts[1]), int(parts[2]))
            except ValueError:
                pass
    return out


# ── Config helpers ─────────────────────────────────────────────────────────

def _load_config(db: sqlite3.Connection) -> dict:
    """Read the config key/value table into a Python dict, JSON-decoding lists."""
    cfg: dict = {}
    for k, v in db.execute("SELECT key, value FROM config").fetchall():
        if k in ("tags", "exclude_tags", "title_types"):
            try: cfg[k] = json.loads(v)
            except json.JSONDecodeError: cfg[k] = []
        elif k == "min_rating":
            cfg[k] = float(v)
        elif k == "min_votes":
            cfg[k] = int(v)
        else:
            cfg[k] = v
    return cfg


# ── Main scan ──────────────────────────────────────────────────────────────

def run_scan(db_path: str, on_progress: Callable[[str], None]) -> dict:
    """Execute one full scan cycle. Returns a summary dict.

    Steps:
      1. Download today's basics + ratings dumps.
      2. Iterate basics, skip already-seen tconsts (delta only).
      3. For each new tconst, apply rating >= min_rating AND
         num_votes >= min_votes AND (no tags configured OR tag intersects genres).
      4. Insert new titles into `titles`, matches into `matches`, and
         update the current run row.
    """
    db = sqlite3.connect(db_path)
    db.execute("PRAGMA foreign_keys = ON")
    cfg = _load_config(db)
    keep_types  = set(cfg.get("title_types", ["movie", "tvMovie", "tvSeries"]))
    min_rating  = cfg.get("min_rating", 7.0)
    min_votes   = cfg.get("min_votes",  100)
    tags        = [t.strip().lower() for t in cfg.get("tags",         []) if t.strip()]
    exclude     = set(t.strip().lower() for t in cfg.get("exclude_tags", []) if t.strip())

    # Open a run row so the UI can show live progress
    run_id = db.execute(
        "INSERT INTO runs (status, phase, config_snapshot) VALUES ('running', 'downloading', ?)",
        (json.dumps(cfg),),
    ).lastrowid
    db.commit()

    def phase(name: str, msg: str = ""):
        db.execute("UPDATE runs SET phase=? WHERE id=?", (name, run_id))
        db.commit()
        on_progress(msg or name)

    try:
        # 1. Download
        phase("downloading", "downloading dumps from datasets.imdbws.com…")
        basics_path, ratings_path = _fetch_dumps(on_progress)

        # 2. Ratings — load fully into RAM (~50 MB, fine)
        phase("loading ratings")
        ratings = _load_ratings(ratings_path)
        on_progress(f"loaded {len(ratings):,} rating rows")

        # 3. Basics — stream and diff against already-seen
        phase("diffing basics")
        seen: set[str] = set(row[0] for row in db.execute("SELECT tconst FROM titles"))
        on_progress(f"{len(seen):,} titles already in DB")

        new_title_rows: list[tuple] = []
        match_rows:     list[tuple] = []
        scanned = 0
        for row in _iter_basics(basics_path, keep_types):
            scanned += 1
            if scanned % _PROGRESS_EVERY == 0:
                on_progress(f"scanned {scanned:,} basics rows, "
                            f"{len(new_title_rows):,} new so far")
            tconst = row[0]
            if tconst in seen:
                continue
            seen.add(tconst)
            new_title_rows.append(row)

            title_type, primary_title, start_year, _, genres = row[1:]
            title_genres_lower = [g.lower() for g in (genres or "").split(",") if g]

            # Exclusion first — a single excluded genre kills the title
            # regardless of rating or desirable tags. E.g. "Horror" in exclude
            # means everything tagged Horror is off the table, even a 9.0
            # Sci-Fi/Horror crossover.
            if exclude and any(g in exclude for g in title_genres_lower):
                continue

            # Apply the rating / vote filters
            rating_row = ratings.get(tconst)
            if not rating_row:
                continue
            rating, votes = rating_row
            if rating < min_rating or votes < min_votes:
                continue

            if tags:
                matched_tags = [g for g in title_genres_lower if g in tags]
                if not matched_tags:
                    continue
            else:
                # No tag filter configured → auto-pass, record all genres as matched
                matched_tags = title_genres_lower

            match_rows.append((
                tconst, primary_title, start_year, title_type,
                rating, votes, genres, ",".join(matched_tags), run_id,
            ))

        # 4. Persist — chunked inserts so a 100K-row batch doesn't blow the log
        phase("saving new titles")
        db.executemany(
            "INSERT OR IGNORE INTO titles "
            "(tconst, title_type, primary_title, start_year, runtime_min, genres) "
            "VALUES (?, ?, ?, ?, ?, ?)",
            new_title_rows,
        )
        phase("saving matches")
        db.executemany(
            "INSERT OR IGNORE INTO matches "
            "(tconst, primary_title, start_year, title_type, rating, num_votes, "
            "genres, matched_tags, run_id) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
            match_rows,
        )

        db.execute(
            "UPDATE runs SET status='done', phase='done', completed_at=strftime('%Y-%m-%dT%H:%M:%SZ','now'), "
            "total_downloaded=?, new_titles=?, matched_titles=? WHERE id=?",
            (scanned, len(new_title_rows), len(match_rows), run_id),
        )
        db.commit()

        return {
            "run_id": run_id,
            "scanned": scanned,
            "new_titles": len(new_title_rows),
            "matches": len(match_rows),
        }

    except Exception as exc:
        db.execute(
            "UPDATE runs SET status='error', phase='error', completed_at=strftime('%Y-%m-%dT%H:%M:%SZ','now'), "
            "error=? WHERE id=?",
            (str(exc), run_id),
        )
        db.commit()
        raise
    finally:
        db.close()


# ── CLI entry point ────────────────────────────────────────────────────────
# Invoked by launchd/cron to run a scan without needing the Flask process.
# Reads config from and writes results to the same scanner.db the web app
# uses, so any browser hit against the web UI sees the cron's output.
#
#   python3 scanner.py            → run against the default db/scanner.db
#   python3 scanner.py <db_path>  → run against a specific DB file
#
# Progress messages go to stdout so launchd's log capture is useful.

if __name__ == "__main__":
    import sys
    default_db = os.path.join(os.path.dirname(__file__), "db", "scanner.db")
    db_path = sys.argv[1] if len(sys.argv) > 1 else default_db

    # Bootstrap the DB if it doesn't exist yet (fresh clone / first cron run)
    if not os.path.exists(db_path):
        schema_path = os.path.join(os.path.dirname(__file__), "db", "schema.sql")
        os.makedirs(os.path.dirname(db_path), exist_ok=True)
        _boot = sqlite3.connect(db_path)
        with open(schema_path) as _f:
            _boot.executescript(_f.read())
        _boot.commit()
        _boot.close()
        print(f"[{time.strftime('%Y-%m-%d %H:%M:%S')}] bootstrapped fresh DB at {db_path}")

    def _print_progress(msg: str) -> None:
        print(f"[{time.strftime('%Y-%m-%d %H:%M:%S')}] {msg}", flush=True)

    _print_progress(f"scan starting against {db_path}")
    try:
        summary = run_scan(db_path, _print_progress)
        _print_progress(
            f"scan complete — run {summary['run_id']}: "
            f"scanned {summary['scanned']:,}, "
            f"new {summary['new_titles']:,}, "
            f"matched {summary['matches']:,}"
        )
    except Exception as exc:
        _print_progress(f"scan failed: {exc}")
        sys.exit(1)
