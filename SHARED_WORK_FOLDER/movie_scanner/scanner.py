"""scanner.py — core Scanner class for the movie_scanner library.

This module is the primary public entrypoint. It is deliberately free of
Flask, Jinja2, or any HTTP-server dependency — it can be imported cleanly
inside Homunculus or any other Python context.

Typical usage
-------------
::

    from movie_scanner import Scanner, ScanConfig

    sc = Scanner(
        db_path="/path/to/scanner.db",
        data_dir="/path/to/data",
        config=ScanConfig(min_rating=7.5, include_genres=["Sci-Fi", "Drama"]),
    )

    summary = sc.scan(on_progress=print)
    # -> {'run_id': 42, 'scanned': 1_200_000, 'new_titles': 314, 'matches': 17}

    new_this_week = sc.new_matches_since("2026-07-10")
    last_run_meta = sc.latest_run()
"""

import datetime
from datetime import date
import gzip
import json
import os
import sqlite3
import time
from typing import Callable, Iterable

from .config import ScanConfig
from .downloader import fetch_dumps
from .omdb import OMDbClient
from .schema import apply_schema

# How often (in basics rows) to emit a progress message during ingest.
_PROGRESS_EVERY = 100_000

# Filename of the append-only human-readable scan log. Lives inside data_dir
# so it sits next to the cached IMDB dumps and the DB.
_SCAN_LOG_NAME = "scans.log"


def _utc_now_iso() -> str:
    """Return current UTC time as an ISO 8601 string with a ``Z`` suffix."""
    return datetime.datetime.utcnow().strftime("%Y-%m-%dT%H:%M:%SZ")


def _format_scan_log_entry(
    run_id: int,
    started_at: str,
    finished_at: str,
    status: str,
    scanned: int,
    new_titles: int,
    matches: int,
    cfg: "ScanConfig",
    error: str | None = None,
) -> str:
    """Return a human-readable, easy-to-skim block for scans.log.

    One block per run — success or error. Numbers use ``{:,}`` grouping so
    the log matches the on_progress messages elsewhere in this module.
    """
    lines = [
        "=" * 40,
        f"Scan run_id={run_id} — {started_at} → {finished_at}",
        f"Status: {status}" + (f" — {error}" if error else ""),
        (
            f"Scanned: {scanned:,} rows | "
            f"New titles: {new_titles:,} | "
            f"Matches: {matches:,}"
        ),
        "Config:",
        f"  min_rating: {cfg.min_rating}",
        f"  min_votes: {cfg.min_votes}",
        f"  min_year: {cfg.min_year}",
        f"  title_types: {', '.join(cfg.title_types)}",
        f"  include_genres: {', '.join(cfg.include_genres) if cfg.include_genres else '(any)'}",
        f"  exclude_genres: {', '.join(cfg.exclude_genres) if cfg.exclude_genres else '(none)'}",
        "=" * 40,
        "",
    ]
    return "\n".join(lines)


def _append_scan_log(data_dir: str, entry: str) -> None:
    """Append *entry* to ``<data_dir>/scans.log``. Creates data_dir if missing."""
    os.makedirs(data_dir, exist_ok=True)
    path = os.path.join(data_dir, _SCAN_LOG_NAME)
    with open(path, "a", encoding="utf-8") as f:
        f.write(entry)


# ── Internal parsers ───────────────────────────────────────────────────────

def _iter_basics(path: str, keep_types: set[str]) -> Iterable[tuple]:
    """Yield ``(tconst, titleType, primaryTitle, startYear, runtimeMin, genres)``
    tuples for rows whose titleType is in *keep_types*. Skips the header row."""
    with gzip.open(path, "rt", encoding="utf-8", errors="replace") as f:
        f.readline()  # skip header
        for line in f:
            parts = line.rstrip("\n").split("\t")
            if len(parts) < 9:
                continue
            tconst, title_type = parts[0], parts[1]
            if title_type not in keep_types:
                continue
            primary_title = parts[2]
            start_year    = parts[5]
            runtime_min   = parts[7]
            genres        = parts[8]
            yield (
                tconst,
                title_type,
                primary_title,
                None if start_year  == "\\N" else int(start_year),
                None if runtime_min == "\\N" else int(runtime_min),
                None if genres      == "\\N" else genres,
            )


def _load_ratings(path: str) -> dict[str, tuple[float, int]]:
    """Load ratings.tsv into a dict: ``tconst -> (rating, num_votes)``."""
    out: dict[str, tuple[float, int]] = {}
    with gzip.open(path, "rt", encoding="utf-8", errors="replace") as f:
        f.readline()  # skip header
        for line in f:
            parts = line.rstrip("\n").split("\t")
            if len(parts) != 3:
                continue
            try:
                out[parts[0]] = (float(parts[1]), int(parts[2]))
            except ValueError:
                pass
    return out


# ── Scanner class ──────────────────────────────────────────────────────────

class Scanner:
    """IMDB delta scanner — downloads, diffs, filters, and persists results.

    Parameters
    ----------
    db_path : str
        Absolute path to the SQLite database file. Created (with schema
        applied) on first use if it does not exist.
    data_dir : str, optional
        Directory where the downloaded .gz dump files are cached. Defaults
        to a ``data/`` subfolder next to *db_path*.
    config : ScanConfig, optional
        Filter parameters. If omitted, the scanner reads ``min_rating``,
        ``min_votes``, ``tags``, ``exclude_tags``, and ``title_types`` from
        the ``config`` table in the database (the same values the Flask UI
        writes). Pass an explicit ScanConfig to override the DB values
        programmatically (e.g. from Homunculus).

    Notes
    -----
    - Zero Flask / Jinja2 / HTTP-server dependencies. Only stdlib + urllib.
    - The database schema is applied idempotently on every instantiation, so
      pointing at an empty file just works.
    - Thread-safety: each public method opens and closes its own connection.
      Do not share a Scanner instance across threads without your own lock.
    """

    def __init__(
        self,
        db_path: str,
        data_dir: str | None = None,
        config: ScanConfig | None = None,
    ) -> None:
        self._db_path  = db_path
        self._data_dir = data_dir or os.path.join(os.path.dirname(db_path), "data")
        self._config   = config   # None → read from DB at scan time

        # Ensure DB and schema exist
        os.makedirs(os.path.dirname(db_path), exist_ok=True)
        with sqlite3.connect(db_path) as conn:
            apply_schema(conn)

    # ── Private helpers ────────────────────────────────────────────────────

    def _connect(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self._db_path)
        conn.execute("PRAGMA foreign_keys = ON")
        conn.row_factory = sqlite3.Row
        return conn

    def _resolve_config(self, conn: sqlite3.Connection) -> tuple["ScanConfig", str | None]:
        """Return (ScanConfig, omdb_api_key): explicit override, or read from DB.

        omdb_api_key is returned alongside the config so the scanner can
        instantiate an OMDbClient for country filtering without a second DB query.
        """
        rows = conn.execute("SELECT key, value FROM config").fetchall()
        raw: dict = {}
        for r in rows:
            k, v = r["key"], r["value"]
            if k in ("tags", "exclude_tags", "title_types", "exclude_countries"):
                try:
                    raw[k] = json.loads(v)
                except json.JSONDecodeError:
                    raw[k] = []
            elif k == "min_rating":
                raw[k] = float(v)
            elif k == "min_votes":
                raw[k] = int(v)
            elif k == "min_year":
                raw[k] = int(v)
            elif k == "omdb_api_key":
                raw[k] = v

        omdb_api_key: str | None = raw.get("omdb_api_key")

        if self._config is not None:
            return self._config, omdb_api_key

        return ScanConfig(
            min_rating        = raw.get("min_rating", 7.0),
            min_votes         = raw.get("min_votes",  100),
            min_year          = raw.get("min_year",   date.today().year),
            include_genres    = raw.get("tags",              []),
            exclude_genres    = raw.get("exclude_tags",      []),
            title_types       = raw.get("title_types",       ["movie", "tvMovie", "tvSeries"]),
            exclude_countries = raw.get("exclude_countries", []),
        ), omdb_api_key

    # ── Public API ─────────────────────────────────────────────────────────

    def scan(
        self,
        on_progress: Callable[[str], None] = lambda _: None,
    ) -> dict:
        """Execute one full scan cycle and return a summary dict.

        Steps
        -----
        1. Download today's basics + ratings dumps (resumable, atomic).
        2. Stream basics; skip already-seen tconsts (delta only).
        3. For each new tconst: apply exclude_genres → rating/vote filter →
           include_genres filter. Titles that survive all three are matches.
        4. Bulk-insert new titles and matches; update the run row.

        Parameters
        ----------
        on_progress : Callable[[str], None]
            Optional callback called with a human-readable status string as
            work progresses. Defaults to a no-op. Hook up ``print`` for CLI
            use, or a TTS/voice queue for Homunculus.

        Returns
        -------
        dict
            ``{'run_id': int, 'scanned': int, 'new_titles': int, 'matches': int}``
        """
        started_at = _utc_now_iso()

        # Counts + status carried out of the try-block so the finally-clause
        # can write an accurate scans.log entry on both success and error paths.
        run_id: int = -1
        scanned = 0
        new_title_rows: list[tuple] = []
        match_rows:     list[tuple] = []
        log_status = "error"
        log_error: str | None = None

        conn = self._connect()
        conn.row_factory = sqlite3.Row  # already set, but be explicit
        cfg, omdb_api_key = self._resolve_config(conn)

        keep_types        = set(cfg.title_types)
        min_rating        = cfg.min_rating
        min_votes         = cfg.min_votes
        min_year          = cfg.min_year
        tags              = [t.strip().lower() for t in cfg.include_genres if t.strip()]
        exclude           = set(t.strip().lower() for t in cfg.exclude_genres if t.strip())
        exclude_countries = [c.strip().lower() for c in cfg.exclude_countries if c.strip()]

        # OMDb client for country filtering — only instantiated when needed.
        omdb_client: OMDbClient | None = (
            OMDbClient(api_key=omdb_api_key, db_path=self._db_path)
            if exclude_countries and omdb_api_key
            else None
        )

        # Capture a DB-compatible config snapshot (mirrors the Flask app format)
        config_snapshot = json.dumps({
            "min_rating":        min_rating,
            "min_votes":         min_votes,
            "min_year":          min_year,
            "tags":              cfg.include_genres,
            "exclude_tags":      cfg.exclude_genres,
            "title_types":       cfg.title_types,
            "exclude_countries": cfg.exclude_countries,
        })

        run_id = conn.execute(
            "INSERT INTO runs (status, phase, config_snapshot) "
            "VALUES ('running', 'downloading', ?)",
            (config_snapshot,),
        ).lastrowid
        conn.commit()

        def phase(name: str, msg: str = "") -> None:
            conn.execute("UPDATE runs SET phase=? WHERE id=?", (name, run_id))
            conn.commit()
            on_progress(msg or name)

        try:
            # 1. Download
            phase("downloading", "downloading dumps from datasets.imdbws.com…")
            basics_path, ratings_path = fetch_dumps(self._data_dir, on_progress)

            # 2. Ratings — small enough to load fully into RAM (~50 MB)
            phase("loading ratings")
            ratings = _load_ratings(ratings_path)
            on_progress(f"loaded {len(ratings):,} rating rows")

            # 3. Basics — stream + diff
            phase("diffing basics")
            seen: set[str] = set(
                r[0] for r in conn.execute("SELECT tconst FROM titles")
            )
            on_progress(f"{len(seen):,} titles already in DB")

            for row in _iter_basics(basics_path, keep_types):
                scanned += 1
                if scanned % _PROGRESS_EVERY == 0:
                    on_progress(
                        f"scanned {scanned:,} basics rows, "
                        f"{len(new_title_rows):,} new so far"
                    )
                tconst = row[0]
                if tconst in seen:
                    continue
                seen.add(tconst)
                new_title_rows.append(row)

                title_type, primary_title, start_year, _, genres_str = row[1:]
                title_genres_lower = [
                    g.lower() for g in (genres_str or "").split(",") if g
                ]

                # Exclusion first — one excluded genre kills the title
                if exclude and any(g in exclude for g in title_genres_lower):
                    continue

                # Year filter
                if min_year > 0:
                    if start_year is None or int(start_year) < min_year:
                        continue

                # Rating + vote filter
                rating_row = ratings.get(tconst)
                if not rating_row:
                    continue
                rating, votes = rating_row
                if rating < min_rating or votes < min_votes:
                    continue

                # Include-genre filter
                if tags:
                    matched_tags = [g for g in title_genres_lower if g in tags]
                    if not matched_tags:
                        continue
                else:
                    matched_tags = title_genres_lower   # all genres auto-pass

                # Country filter — only when exclude_countries is configured.
                # Fail OPEN: if OMDb is unavailable or returns an error, include the title.
                if omdb_client and exclude_countries:
                    meta = omdb_client.fetch(tconst)
                    if meta.get("error"):
                        on_progress(f"OMDb error for {tconst}: {meta['error']} — including title")
                    elif meta.get("country"):
                        title_countries = [
                            c.strip().lower()
                            for c in meta["country"].split(",")
                            if c.strip()
                        ]
                        if any(ec in tc for ec in exclude_countries for tc in title_countries):
                            continue

                match_rows.append((
                    tconst, primary_title, start_year, title_type,
                    rating, votes, genres_str, ",".join(matched_tags), run_id,
                ))

            # 4. Persist
            phase("saving new titles")
            conn.executemany(
                "INSERT OR IGNORE INTO titles "
                "(tconst, title_type, primary_title, start_year, runtime_min, genres) "
                "VALUES (?, ?, ?, ?, ?, ?)",
                new_title_rows,
            )
            phase("saving matches")
            conn.executemany(
                "INSERT OR IGNORE INTO matches "
                "(tconst, primary_title, start_year, title_type, rating, num_votes, "
                "genres, matched_tags, run_id) "
                "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
                match_rows,
            )
            conn.execute(
                "UPDATE runs SET status='done', phase='done', "
                "completed_at=strftime('%Y-%m-%dT%H:%M:%SZ','now'), "
                "total_downloaded=?, new_titles=?, matched_titles=? WHERE id=?",
                (scanned, len(new_title_rows), len(match_rows), run_id),
            )
            conn.commit()

            log_status = "done"
            return {
                "run_id":     run_id,
                "scanned":    scanned,
                "new_titles": len(new_title_rows),
                "matches":    len(match_rows),
            }

        except BaseException as exc:
            # Catches Exception (network errors, assertion failures, etc.) AND
            # BaseException subclasses (KeyboardInterrupt, SystemExit) so the
            # run row always reaches a terminal state on any exit path that
            # try/finally can observe. (SIGKILL still requires the startup
            # reconciliation in app.py — there is no user-space safety net for
            # that case.)
            log_status = "error"
            log_error = str(exc) or type(exc).__name__
            try:
                conn.execute(
                    "UPDATE runs SET status='error', phase='error', "
                    "completed_at=strftime('%Y-%m-%dT%H:%M:%SZ','now'), "
                    "error=? WHERE id=?",
                    (log_error, run_id),
                )
                conn.commit()
            except Exception:
                pass  # best-effort; don't mask the original exception
            raise
        finally:
            # Append a human-readable entry to <data_dir>/scans.log on every
            # exit path (done or error) so Thomas can tail -f the file.
            finished_at = _utc_now_iso()
            try:
                entry = _format_scan_log_entry(
                    run_id      = run_id,
                    started_at  = started_at,
                    finished_at = finished_at,
                    status      = log_status,
                    scanned     = scanned,
                    new_titles  = len(new_title_rows),
                    matches     = len(match_rows),
                    cfg         = cfg,
                    error       = log_error,
                )
                _append_scan_log(self._data_dir, entry)
            except Exception:
                # Never let logging failures mask a real scan error.
                pass
            conn.close()

    def new_matches_since(
        self,
        iso_date: str,
        include_dismissed: bool = False,
    ) -> list[dict]:
        """Return matches first seen on or after *iso_date* (``YYYY-MM-DD``).

        This is the primary Homunculus query: "any good new movies this week?"

        Parameters
        ----------
        iso_date : str
            ISO 8601 date string, e.g. ``"2026-07-10"``. Matches whose
            ``matched_at`` column is >= this value are returned.
        include_dismissed : bool, optional
            When ``False`` (the default), rows the user has dismissed via the
            web UI (``dismissed_at IS NOT NULL``) are excluded from results.
            Set to ``True`` to include them (e.g. for admin/debug purposes).
            Herman should always use the default so dismissed titles are not
            voiced out.

        Returns
        -------
        list[dict]
            Each dict has keys: ``tconst``, ``primary_title``, ``start_year``,
            ``title_type``, ``rating``, ``num_votes``, ``genres``,
            ``matched_tags``, ``matched_at``, ``dismissed_at``.
            Ordered by rating DESC, num_votes DESC.
        """
        conn = self._connect()
        try:
            # Read dismissal state from the persistent dismissed_tconsts table
            # so that "rescan all" and "clear runs" don't resurrect dismissed titles.
            if include_dismissed:
                where = "m.matched_at >= ?"
                rows = conn.execute(
                    "SELECT m.tconst, m.primary_title, m.start_year, m.title_type, "
                    "m.rating, m.num_votes, m.genres, m.matched_tags, m.matched_at, "
                    "d.dismissed_at "
                    "FROM matches m LEFT JOIN dismissed_tconsts d ON d.tconst = m.tconst "
                    f"WHERE {where} "
                    "ORDER BY m.rating DESC, m.num_votes DESC",
                    (iso_date,),
                ).fetchall()
            else:
                rows = conn.execute(
                    "SELECT m.tconst, m.primary_title, m.start_year, m.title_type, "
                    "m.rating, m.num_votes, m.genres, m.matched_tags, m.matched_at, "
                    "d.dismissed_at "
                    "FROM matches m LEFT JOIN dismissed_tconsts d ON d.tconst = m.tconst "
                    "WHERE m.matched_at >= ? AND d.tconst IS NULL "
                    "ORDER BY m.rating DESC, m.num_votes DESC",
                    (iso_date,),
                ).fetchall()
            return [dict(r) for r in rows]
        finally:
            conn.close()

    def latest_run(self) -> dict | None:
        """Return metadata for the most recent scan run, or ``None`` if no runs exist.

        Returns
        -------
        dict | None
            Keys: ``id``, ``started_at``, ``completed_at``, ``status``,
            ``phase``, ``total_downloaded``, ``new_titles``,
            ``matched_titles``, ``error``, ``config_snapshot``.
        """
        conn = self._connect()
        try:
            row = conn.execute(
                "SELECT id, started_at, completed_at, status, phase, "
                "total_downloaded, new_titles, matched_titles, error, config_snapshot "
                "FROM runs ORDER BY id DESC LIMIT 1"
            ).fetchone()
            return dict(row) if row else None
        finally:
            conn.close()

    def rescan_upside(
        self,
        sample_size: int = 500,
        on_progress: Callable[[str], None] | None = None,
    ) -> dict:
        """Sample rejected titles and re-test them against the current config.

        Queries the ``titles`` table for tconsts NOT in ``matches``,
        pre-filters in SQL using the current config's title_type / genre
        settings, random-samples *sample_size* rows, downloads (or reuses
        today's cached copy of) ``title.ratings.tsv.gz``, tests each
        candidate against ``min_rating`` / ``min_votes``, and persists the
        passing rows to ``upside_matches`` (replacing prior contents).

        A marker row with ``phase='upside_rescan'`` is also inserted into
        ``runs`` so the audit trail on the landing page shows activity.

        Parameters
        ----------
        sample_size : int
            Number of pre-filtered candidates to random-sample. Default 500.
        on_progress : Callable[[str], None] | None
            Optional progress callback. No-op if omitted.

        Returns
        -------
        dict
            ``{'sampled': int, 'matched': int, 'run_marker_id': int}``
        """
        _prog = on_progress or (lambda _: None)

        conn = self._connect()
        try:
            cfg, omdb_api_key = self._resolve_config(conn)
            min_rating        = cfg.min_rating
            min_votes         = cfg.min_votes
            min_year          = cfg.min_year
            tags              = [t.strip().lower() for t in cfg.include_genres if t.strip()]
            exclude           = set(t.strip().lower() for t in cfg.exclude_genres if t.strip())
            keep_types        = list(cfg.title_types)
            exclude_countries = [c.strip().lower() for c in cfg.exclude_countries if c.strip()]

            omdb_client: OMDbClient | None = (
                OMDbClient(api_key=omdb_api_key, db_path=self._db_path)
                if exclude_countries and omdb_api_key
                else None
            )

            # ── Build the pre-filter SQL ───────────────────────────────────
            # Always filter: title_type in keep_types, genres IS NOT NULL,
            # tconst NOT IN matches.
            placeholders = ",".join("?" * len(keep_types))
            params: list = list(keep_types)

            genre_clauses: list[str] = []

            # exclude_genres: skip any title whose genres contain one of these
            for excl in exclude:
                genre_clauses.append("LOWER(genres) NOT LIKE ?")
                params.append(f"%{excl}%")

            # include_genres: keep only titles that have at least one — build
            # an OR group. If no include_genres are set, this clause is omitted
            # (any genre auto-passes, matching scan behaviour).
            if tags:
                include_or = " OR ".join(
                    ["LOWER(genres) LIKE ?"] * len(tags)
                )
                genre_clauses.append(f"({include_or})")
                for tag in tags:
                    params.append(f"%{tag}%")

            where_extra = ""
            if genre_clauses:
                where_extra = " AND " + " AND ".join(genre_clauses)

            sql = f"""
                SELECT tconst, title_type, primary_title, start_year, genres
                FROM titles
                WHERE title_type IN ({placeholders})
                  AND genres IS NOT NULL
                  AND tconst NOT IN (SELECT tconst FROM matches)
                  {where_extra}
                ORDER BY RANDOM()
                LIMIT ?
            """
            params.append(sample_size)

            _prog(f"sampling up to {sample_size} pre-filtered rejected titles…")
            rows = conn.execute(sql, params).fetchall()
            pre_filtered_count = len(rows)
            _prog(f"pre-filter yielded {pre_filtered_count} candidates; downloading ratings…")

            # ── Download (or reuse today's cached) ratings file ────────────
            ratings_path = os.path.join(self._data_dir, "title.ratings.tsv.gz")
            today_epoch  = time.mktime(time.strptime(
                time.strftime("%Y-%m-%d"), "%Y-%m-%d"
            ))
            cache_hit = (
                os.path.exists(ratings_path)
                and os.path.getmtime(ratings_path) >= today_epoch
            )
            if cache_hit:
                _prog("ratings file is from today — using cache (no re-download)")
            else:
                _prog("ratings file is stale or missing — downloading…")
                from .downloader import RATINGS_URL, _download
                os.makedirs(self._data_dir, exist_ok=True)
                _download(RATINGS_URL, ratings_path, _prog)

            _prog("loading ratings into memory…")
            ratings = _load_ratings(ratings_path)

            # ── Test each candidate against current rating/vote thresholds ─
            upside: list[tuple] = []
            for row in rows:
                tconst        = row["tconst"]
                title_type    = row["title_type"]
                primary_title = row["primary_title"]
                start_year    = row["start_year"]
                genres_str    = row["genres"]

                rating_row = ratings.get(tconst)
                if not rating_row:
                    continue
                rating, votes = rating_row
                if rating < min_rating or votes < min_votes:
                    continue

                # Year filter
                if min_year > 0:
                    if start_year is None or int(start_year) < min_year:
                        continue

                title_genres_lower = [
                    g.lower() for g in (genres_str or "").split(",") if g
                ]

                # include_genres filter (re-run full logic for correctness)
                if tags:
                    matched_tags = [g for g in title_genres_lower if g in tags]
                    if not matched_tags:
                        continue
                else:
                    matched_tags = title_genres_lower

                # Country filter — fail OPEN on OMDb errors.
                if omdb_client and exclude_countries:
                    meta = omdb_client.fetch(tconst)
                    if meta.get("error"):
                        _prog(f"OMDb error for {tconst}: {meta['error']} — including title")
                    elif meta.get("country"):
                        title_countries = [
                            c.strip().lower()
                            for c in meta["country"].split(",")
                            if c.strip()
                        ]
                        if any(ec in tc for ec in exclude_countries for tc in title_countries):
                            continue

                upside.append((
                    tconst, primary_title, start_year, title_type,
                    rating, votes, genres_str, ",".join(matched_tags),
                ))

            _prog(f"{len(upside)} upside candidates found; persisting…")

            # ── Persist — replace prior contents wholesale ─────────────────
            conn.execute("DELETE FROM upside_matches")
            conn.executemany(
                "INSERT INTO upside_matches "
                "(tconst, primary_title, start_year, title_type, rating, "
                " num_votes, genres, matched_tags) "
                "VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
                upside,
            )

            # ── Audit-trail row in runs ────────────────────────────────────
            run_marker_id = conn.execute(
                "INSERT INTO runs (status, phase, completed_at, matched_titles) "
                "VALUES ('done', 'upside_rescan', "
                "        strftime('%Y-%m-%dT%H:%M:%SZ','now'), ?)",
                (len(upside),),
            ).lastrowid
            conn.commit()

            _prog(f"upside rescan complete — {len(upside)} candidates saved")
            return {
                "sampled":        pre_filtered_count,
                "matched":        len(upside),
                "run_marker_id":  run_marker_id,
            }

        finally:
            conn.close()
