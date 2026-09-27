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
import random
import sqlite3
import threading
import time
from typing import Callable, Iterable

from .config import ScanConfig
from .downloader import fetch_dumps
from .omdb import OMDbClient
# COMPLIANCE EXCEPTION — parental_guide scrapes imdb.com. Isolated import;
# only used in the explicit filter step below. See parental_guide.py header.
from .parental_guide import (
    BASE_DELAY_SEC as _PG_BASE_DELAY,
    CATEGORIES     as _PG_CATEGORIES,
    JITTER_FRAC    as _PG_JITTER,
    fetch_parental_guide,
    severity_le,
)
from .schema import apply_schema

# How often (in basics rows) to emit a progress message during ingest.
_PROGRESS_EVERY = 100_000

# ── V3.25: Theatrical-window constants and helpers ─────────────────────────

# Days after theatrical release with no DVD date before we assume streaming
# exists somewhere. After this window, a title with no DVD info is no longer
# treated as "only in theaters" — too much time has passed for us to be sure.
# 180 days ≈ 6 months, covering the typical ~90-day theatrical window plus
# a comfortable buffer for delayed home-video announcements.
THEATRICAL_WINDOW_DAYS: int = 180

# OMDb date formats we accept. OMDb returns dates like "01 Jan 2026".
_OMDB_DATE_FMTS = ("%d %b %Y",)


def parse_omdb_date(date_str: str) -> date:
    """Parse an OMDb date string (e.g. "01 Jan 2026") into a :class:`date`.

    Raises :class:`ValueError` if the string cannot be parsed in any of the
    known OMDb date formats.
    """
    for fmt in _OMDB_DATE_FMTS:
        try:
            return datetime.datetime.strptime(date_str.strip(), fmt).date()
        except ValueError:
            continue
    raise ValueError(f"Cannot parse OMDb date: {date_str!r}")


def is_only_in_theaters(omdb_response: dict, today: date) -> bool:
    """Return True when the best available evidence suggests a title is still
    only in theaters (i.e. has not yet reached home video / streaming).

    Decision tree
    -------------
    1. Series (``Type == "series"``) are never in theaters → False.
    2. If ``DVD`` is a valid date string:
       - Past or today → already on home video → False.
       - Future date   → not yet on home video → True.
    3. ``DVD`` absent or "N/A", fall back to theatrical-release heuristic:
       - ``Released`` is a valid date within THEATRICAL_WINDOW_DAYS → True.
       - ``Released`` is a valid date older than THEATRICAL_WINDOW_DAYS → False.
    4. No usable date signal at all → False (don't over-filter unknowns).

    Parameters
    ----------
    omdb_response:
        The dict returned by :meth:`OMDbClient.fetch` (or any dict with
        ``DVD``, ``Released``, and ``Type`` keys matching OMDb field names).
        Uses raw OMDb field names (capital D/R/T) so it can be called with
        both the raw API response and the ``fetch()`` cache dict (which stores
        ``dvd``/``released`` in lowercase; callers should normalise first).
    today:
        Reference date — injectable for deterministic unit tests.
    """
    # Series are never in theaters.
    title_type = (omdb_response.get("Type") or omdb_response.get("type") or "").lower()
    if title_type == "series":
        return False

    # --- DVD signal ---
    dvd_str = omdb_response.get("DVD") or omdb_response.get("dvd") or "N/A"
    if dvd_str and dvd_str != "N/A":
        try:
            dvd_date = parse_omdb_date(dvd_str)
            return dvd_date > today   # future DVD → still in theaters
        except ValueError:
            pass   # malformed → fall through to Released heuristic

    # --- Released heuristic (no usable DVD date) ---
    released_str = (
        omdb_response.get("Released") or omdb_response.get("released") or "N/A"
    )
    if released_str and released_str != "N/A":
        try:
            released_date = parse_omdb_date(released_str)
            days_since = (today - released_date).days
            if 0 <= days_since <= THEATRICAL_WINDOW_DAYS:
                return True
        except ValueError:
            pass   # malformed → fall through to default

    # Unknown / old title → assume streaming exists, don't over-filter.
    return False


class ScanCancelled(Exception):
    """Raised inside :meth:`Scanner.scan` when the cancel event fires.

    Recognised by the scan()'s try/except: the current run row is marked
    ``status='error'`` with ``phase='cancelled'`` and a short error string.
    We deliberately reuse ``status='error'`` rather than introducing a new
    terminal status value — that avoids a schema migration on the runs
    CHECK constraint. The distinguishing signal is ``phase='cancelled'``.
    """
    pass

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


def _load_episode_years(
    path: str,
    on_progress: Callable[[str], None] | None = None,
) -> dict[str, int]:
    """Return a dict of ``{tconst -> startYear}`` for every ``tvEpisode`` row
    in the basics dump. Used by the V3.13 season-year aggregation.

    A separate streaming pass over title.basics is unavoidable because the
    main scan loop's ``_iter_basics`` filters to ``keep_types`` (movie /
    tvMovie / tvSeries / tvMiniSeries) and drops episodes early. Episodes
    have their own titleType (``tvEpisode``), so they're never yielded by
    the main iterator. We take a second, tighter pass here that only reads
    tconst + titleType + startYear (columns 0, 1, 5) to keep the cost down.

    If ``on_progress`` is supplied, emits a heartbeat every 2 M scanned rows
    so the seasons phase doesn't look hung during its ~8-15 s of silent
    streaming (see V3.19 seasons perf fix).
    """
    out: dict[str, int] = {}
    scanned = 0
    with gzip.open(path, "rt", encoding="utf-8", errors="replace") as f:
        f.readline()  # skip header
        for line in f:
            scanned += 1
            if on_progress and scanned % 2_000_000 == 0:
                on_progress(
                    f"  …scanned {scanned:,} basics rows for episode years "
                    f"({len(out):,} tvEpisode rows so far)"
                )
            parts = line.rstrip("\n").split("\t")
            if len(parts) < 6:
                continue
            if parts[1] != "tvEpisode":
                continue
            sy = parts[5]
            if sy == "\\N":
                continue
            try:
                out[parts[0]] = int(sy)
            except ValueError:
                continue
    return out


def _iter_episodes(path: str) -> Iterable[tuple[str, str, int | None]]:
    """Yield ``(tconst, parentTconst, seasonNumber)`` for every episode row.

    Rows whose ``seasonNumber`` is ``\\N`` are skipped — an episode that has
    no assigned season can't be aggregated by season. Rows whose
    ``parentTconst`` is ``\\N`` are also skipped (orphan episodes).
    """
    with gzip.open(path, "rt", encoding="utf-8", errors="replace") as f:
        f.readline()  # skip header
        for line in f:
            parts = line.rstrip("\n").split("\t")
            if len(parts) < 4:
                continue
            tconst, parent_tconst, season_s, _ep_s = parts[0], parts[1], parts[2], parts[3]
            if parent_tconst == "\\N" or season_s == "\\N":
                continue
            try:
                season_num = int(season_s)
            except ValueError:
                continue
            yield (tconst, parent_tconst, season_num)


def _seasons_cache_key(basics_path: str, episodes_path: str) -> str:
    """Build a cache-key string from the downloader's ``.last_modified``
    sidecar files. Used by the seasons phase (V3.19 perf fix) to skip a
    ~15 s rebuild when neither dump has changed since the last successful
    scan. Falls back to file mtime when the sidecar is missing (older DBs
    that predated the sidecar writer).

    Returns e.g. ``"basics:<lm>|episodes:<lm>"`` — opaque; equality-checked
    only. We deliberately avoid hashing file *contents* (a 215 MB read on
    every scan would defeat the whole optimization).
    """
    def _sig(p: str) -> str:
        lm_path = p + ".last_modified"
        try:
            with open(lm_path, "r", encoding="utf-8") as f:
                return f.read().strip()
        except OSError:
            # No sidecar (unit tests, hand-copied dumps, older DBs): fall
            # back to (size, mtime_ns). Slightly weaker but still stable.
            try:
                st = os.stat(p)
                return f"size={st.st_size},mtime={st.st_mtime_ns}"
            except OSError:
                return "unknown"
    return f"basics:{_sig(basics_path)}|episodes:{_sig(episodes_path)}"


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

    # Title types treated as "series-like" for the V3.13 per-season year
    # filter. Anything else (movie, tvMovie, short) uses the classic
    # startYear >= min_year check.
    _SERIES_TYPES = frozenset({"tvSeries", "tvMiniSeries"})

    def __init__(
        self,
        db_path: str,
        data_dir: str | None = None,
        config: ScanConfig | None = None,
    ) -> None:
        self._db_path  = db_path
        self._data_dir = data_dir or os.path.join(os.path.dirname(db_path), "data")
        self._config   = config   # None → read from DB at scan time

        # V3.13 cooperative cancel — set by Scanner.cancel(), polled between
        # phases and inside the download progress callback. Cannot force-kill
        # a Python thread, so cancellation is best-effort: the flag is
        # observed at safe checkpoints and raises ScanCancelled.
        self._cancel_event = threading.Event()

        # Ensure DB and schema exist
        os.makedirs(os.path.dirname(db_path), exist_ok=True)
        with sqlite3.connect(db_path) as conn:
            apply_schema(conn)

    # ── Cancellation (V3.13) ───────────────────────────────────────────────

    def cancel(self) -> None:
        """Signal the running :meth:`scan` to abort at the next checkpoint.

        Safe to call from any thread. The scan observes this flag between
        phases and inside the download progress callback; on observation it
        raises :class:`ScanCancelled`, which the scan's except-clause
        translates to a terminal run row with ``phase='cancelled'``.

        Calling ``cancel()`` on a Scanner whose scan has already finished
        is a no-op — the flag stays set but nothing consumes it. The next
        ``scan()`` call on the same instance would immediately abort, so
        the /run route creates a fresh Scanner instance for each run.
        """
        self._cancel_event.set()

    def _check_cancel(self, msg: str = "cancelled") -> None:
        """Raise :class:`ScanCancelled` if the cancel flag has been set."""
        if self._cancel_event.is_set():
            raise ScanCancelled(msg)

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
            elif k in (
                "max_sex_nudity", "max_violence_gore", "max_profanity",
                "max_alcohol_drugs", "max_frightening",
            ):
                raw[k] = (v or "severe").strip().lower()
            elif k == "exclude_unknown_parental":
                raw[k] = str(v).strip() in ("1", "true", "yes", "on")
            elif k == "parental_apply":
                # V3.14 — master switch for the parental-guide phase.
                raw[k] = str(v).strip() in ("1", "true", "yes", "on")

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
            # COMPLIANCE EXCEPTION — parental-guide ceilings (V3.12).
            max_sex_nudity    = raw.get("max_sex_nudity",    "severe"),
            max_violence_gore = raw.get("max_violence_gore", "severe"),
            max_profanity     = raw.get("max_profanity",     "severe"),
            max_alcohol_drugs = raw.get("max_alcohol_drugs", "severe"),
            max_frightening   = raw.get("max_frightening",   "severe"),
            exclude_unknown_parental = raw.get("exclude_unknown_parental", False),
            # V3.14 — Apply-filters master switch. Off by default so a
            # fresh scan never pays the ~2s/title parental-guide tax.
            apply_parental    = raw.get("parental_apply", False),
        ), omdb_api_key

    # ── Parental-guide filter (COMPLIANCE EXCEPTION — V3.12) ──────────────
    #
    # Isolated in its own helper so the entire feature can be excised with a
    # single method deletion + one call-site removal in scan(). If you find
    # yourself entangling this into the main loop or omdb.py, stop — the
    # compliance boundary depends on grep-ability.

    def _apply_parental_guide_filter(
        self,
        conn:        sqlite3.Connection,
        match_rows:  list[tuple],
        cfg:         "ScanConfig",
        phase:       Callable[[str, str], None],
        on_progress: Callable[[str], None],
    ) -> tuple[list[tuple], int, int]:
        """Filter ``match_rows`` against the parental-guide ceilings in ``cfg``.

        Returns
        -------
        (kept_rows, scraped_count, dropped_count)

        - ``kept_rows`` is a new list containing only titles that pass every
          ceiling (respecting the ``exclude_unknown_parental`` toggle).
        - ``scraped_count`` is the number of live imdb.com fetches performed
          (excludes cache hits).
        - ``dropped_count`` is the number of titles removed by the filter.

        Notes
        -----
        - If every ceiling is ``severe`` AND ``exclude_unknown_parental`` is
          False, the filter is a no-op and NO scraping is performed. This
          keeps the "no filter set" scan fast.
        - Rate limit: sleeps :data:`_PG_BASE_DELAY` ± :data:`_PG_JITTER`
          between live fetches (not between cache hits). Sleep happens
          BEFORE the request so the first fetch is also throttled from any
          prior activity by the caller.
        """
        # V3.14 — Master switch. The "Apply filters" checkbox next to the
        # Content-severity heading is authoritative: when it is off, we
        # never touch imdb.com/parentalguide, never read the cache, and
        # never apply any ceiling. The 5 severity dropdowns are ignored.
        # This is the fast default; opt-in only.
        if not getattr(cfg, "apply_parental", False):
            phase("saving matches", "parental_guide filter disabled (Apply filters off) — skipping")
            return match_rows, 0, 0

        ceilings = {
            "sex_nudity":    cfg.max_sex_nudity,
            "violence_gore": cfg.max_violence_gore,
            "profanity":     cfg.max_profanity,
            "alcohol_drugs": cfg.max_alcohol_drugs,
            "frightening":   cfg.max_frightening,
        }
        # Secondary short-circuit: even with the master switch ON, if every
        # ceiling is 'severe' AND unknown-passes, nothing can be filtered,
        # so skip the phase (and the scrape). Keeps a mis-configured "on
        # but no ceilings set" state from wasting time.
        filter_is_active = (
            any(c != "severe" for c in ceilings.values())
            or bool(cfg.exclude_unknown_parental)
        )
        if not filter_is_active:
            phase("saving matches", "parental_guide filter inactive — skipping")
            return match_rows, 0, 0

        phase("parental_guide", "checking parental-guide severities…")

        # Import requests lazily so tests / minimal installs that don't hit
        # the network never pay the import cost.
        import requests  # type: ignore
        session = requests.Session()

        kept:    list[tuple] = []
        scraped = 0
        dropped = 0

        stale_cutoff = "date('now', '-90 days')"  # used in the SQL below

        for i, row in enumerate(match_rows, start=1):
            tconst = row[0]

            cached = conn.execute(
                "SELECT sex_nudity, violence_gore, profanity, "
                "alcohol_drugs, frightening, "
                f"CASE WHEN date(fetched_at) >= {stale_cutoff} THEN 1 ELSE 0 END AS fresh "
                "FROM parental_guide WHERE tconst=?",
                (tconst,),
            ).fetchone()

            if cached is not None and cached["fresh"]:
                pg = {k: cached[k] for k in _PG_CATEGORIES}
            else:
                # Rate limit BEFORE the request (not after) so a KeyboardInterrupt
                # during the sleep doesn't leave us mid-request.
                jitter = 1.0 + random.uniform(-_PG_JITTER, _PG_JITTER)
                time.sleep(_PG_BASE_DELAY * jitter)
                pg = fetch_parental_guide(tconst, session)
                scraped += 1
                # Upsert every fetch — even all-unknown results — so we don't
                # retry a broken tconst on every scan.
                conn.execute(
                    """
                    INSERT INTO parental_guide
                        (tconst, sex_nudity, violence_gore, profanity,
                         alcohol_drugs, frightening, fetched_at)
                    VALUES (?, ?, ?, ?, ?, ?, strftime('%Y-%m-%dT%H:%M:%SZ','now'))
                    ON CONFLICT(tconst) DO UPDATE SET
                        sex_nudity    = excluded.sex_nudity,
                        violence_gore = excluded.violence_gore,
                        profanity     = excluded.profanity,
                        alcohol_drugs = excluded.alcohol_drugs,
                        frightening   = excluded.frightening,
                        fetched_at    = excluded.fetched_at
                    """,
                    (
                        tconst,
                        pg["sex_nudity"], pg["violence_gore"],
                        pg["profanity"], pg["alcohol_drugs"], pg["frightening"],
                    ),
                )
                conn.commit()

                if scraped % 10 == 0:
                    on_progress(
                        f"parental_guide: scraped {scraped} title(s) so far "
                        f"({i}/{len(match_rows)} checked)"
                    )

            # Apply ceilings. `unknown` handling is the caller's rule, not
            # severity_le's — see parental_guide.severity_le docstring.
            title_passes = True
            for cat, ceiling in ceilings.items():
                value = pg.get(cat, "unknown")
                if value == "unknown":
                    if cfg.exclude_unknown_parental:
                        title_passes = False
                        break
                    continue  # unknown passes any ceiling by default
                if not severity_le(value, ceiling):
                    title_passes = False
                    break

            if title_passes:
                kept.append(row)
            else:
                dropped += 1

        return kept, scraped, dropped

    # ── Plot filter (V3.24) ────────────────────────────────────────────────
    #
    # Isolated in its own helper (mirrors _apply_parental_guide_filter) so
    # the feature can be removed or toggled cleanly.  Every "can't be
    # fetched" case is already handled by OMDbClient._fetch_from_api():
    #
    #   • HTTP error / timeout        → error set, plot=None
    #   • OMDb Response=False         → error set, plot=None
    #   • OMDb Plot field is "N/A"    → _clean() normalises it to None
    #   • Missing Plot key            → dict.get() returns None
    #   • Network exception           → error set, plot=None
    #
    # So the filter rule is simply: if plot is None → drop the title.

    def _apply_plot_filter(
        self,
        db_path: str,
        match_rows: list[tuple],
        on_progress: "Callable[[str], None]",
    ) -> "tuple[list[tuple], int]":
        """Filter *match_rows* by whether an OMDb plot can be fetched.

        For each candidate match, calls ``OMDbClient.fetch()`` (which uses
        the ``title_metadata`` SQLite cache so prior hits are free).  Any
        title whose ``plot`` field is ``None`` — regardless of reason — is
        excluded.

        Parameters
        ----------
        db_path:
            Path to the scanner.db — used to read the OMDb API key and to
            pass to OMDbClient so its cache writes land in the right place.
        match_rows:
            The list of (tconst, ...) tuples produced by the match phase.
        on_progress:
            Progress callback.

        Returns
        -------
        (kept_rows, dropped_count)

        Fail-open behaviour
        -------------------
        If the OMDb API key is not configured, the filter is skipped and all
        rows are returned unchanged.  This preserves the pre-V3.24 experience
        for users who haven't set an API key, and matches the existing
        country-filter precedent (also fails open on missing key).
        """
        # Read the API key from the DB directly (the Scanner may have been
        # constructed before the key was added, or with an explicit ScanConfig
        # that doesn't carry the key).
        import sqlite3 as _sqlite3
        conn = _sqlite3.connect(db_path)
        conn.row_factory = _sqlite3.Row
        row = conn.execute(
            "SELECT value FROM config WHERE key='omdb_api_key'"
        ).fetchone()
        conn.close()

        if not row or not row["value"]:
            on_progress("plot_filter: no OMDb API key configured — skipping (all titles kept)")
            return match_rows, 0

        omdb_client = OMDbClient(api_key=row["value"], db_path=db_path)
        kept: list[tuple] = []
        dropped = 0

        for i, match_row in enumerate(match_rows, start=1):
            tconst = match_row[0]
            meta = omdb_client.fetch(tconst)
            if meta.get("plot"):
                kept.append(match_row)
            else:
                dropped += 1
                if dropped % 10 == 0 or dropped == 1:
                    on_progress(
                        f"plot_filter: {dropped} title(s) dropped so far "
                        f"(no OMDb plot) — {i}/{len(match_rows)} checked"
                    )

        on_progress(
            f"plot_filter: {len(kept)} titles kept, {dropped} excluded (no OMDb plot)"
        )
        return kept, dropped

    # ── V3.25: Theatrical-window filter ────────────────────────────────────

    def _apply_theaters_filter(
        self,
        db_path: str,
        match_rows: list,
        only_in_theaters_allowed: bool,
        on_progress: "Callable[[str], None]",
    ) -> "tuple[list, int]":
        """Filter *match_rows* based on the "Only In Theaters" user preference.

        Parameters
        ----------
        db_path:
            Path to scanner.db — used to read the OMDb API key and to pass to
            OMDbClient so its cache writes land in the right place.
        match_rows:
            The list of (tconst, ...) tuples coming out of _apply_plot_filter.
        only_in_theaters_allowed:
            True  → pass everything through (checkbox is checked).
            False → exclude titles whose OMDb data indicates they are still
                    only in theaters (checkbox is unchecked).
        on_progress:
            Progress callback.

        Returns
        -------
        (kept_rows, dropped_count)

        Fail-open behaviour
        -------------------
        * If ``only_in_theaters_allowed`` is True → all rows are kept (no API calls).
        * If the OMDb API key is not configured → all rows are kept (no filtering).
        * If a title's OMDb fetch fails or returns no DVD/Released data →
          the title is kept (unknown status → don't over-filter).
        """
        if only_in_theaters_allowed:
            on_progress("theaters_filter: checkbox checked — all titles permitted")
            return match_rows, 0

        import sqlite3 as _sqlite3
        conn = _sqlite3.connect(db_path)
        conn.row_factory = _sqlite3.Row
        row = conn.execute(
            "SELECT value FROM config WHERE key='omdb_api_key'"
        ).fetchone()
        conn.close()

        if not row or not row["value"]:
            on_progress(
                "theaters_filter: no OMDb API key configured — skipping (all titles kept)"
            )
            return match_rows, 0

        omdb_client = OMDbClient(api_key=row["value"], db_path=db_path)
        kept: list = []
        dropped = 0
        today = date.today()

        for match_row in match_rows:
            tconst = match_row[0]
            meta = omdb_client.fetch(tconst)

            if meta.get("error"):
                # OMDb fetch failed — fail open, include the title.
                kept.append(match_row)
                continue

            # Build the lookup dict for is_only_in_theaters using lowercase keys
            # from the cached fetch() result, normalised to the expected field names.
            omdb_lookup = {
                "DVD":      meta.get("dvd") or "N/A",
                "Released": meta.get("released") or "N/A",
                "Type":     meta.get("type") or "movie",
            }

            if is_only_in_theaters(omdb_lookup, today):
                dropped += 1
            else:
                kept.append(match_row)

        on_progress(
            f"theaters_filter: {len(kept)} titles kept, "
            f"{dropped} excluded (only in theaters)"
        )
        return kept, dropped

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
        # Parallel to match_rows: qualifying seasons per series (V3.13). Aligned
        # by index; movies/tvMovies have an empty list. Persisted to
        # match_seasons after the matches rows are inserted (so the FK match_id
        # resolves). A None slot means "series, but no season lookup ran" —
        # shouldn't happen in normal flow, defensive.
        match_seasons_by_idx: list[list[tuple[int, int | None, int]]] = []
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
            # 1. Download.
            #
            # The download progress callback is the ONE hook that can bail
            # mid-fetch (fetch_dumps is a single blocking call otherwise),
            # so we wrap the caller's on_progress to poll the cancel flag
            # on every message. When cancel is set, raising from inside the
            # callback tears down the urllib request cleanly.
            phase("downloading", "downloading dumps from datasets.imdbws.com…")

            def _cancellable_progress(msg: str) -> None:
                if self._cancel_event.is_set():
                    raise ScanCancelled("cancelled during download")
                on_progress(msg)

            basics_path, ratings_path, episodes_path = fetch_dumps(
                self._data_dir, _cancellable_progress
            )
            self._check_cancel("cancelled after download")

            # 2. Ratings — small enough to load fully into RAM (~50 MB)
            phase("loading ratings")
            ratings = _load_ratings(ratings_path)
            on_progress(f"loaded {len(ratings):,} rating rows")
            self._check_cancel("cancelled after loading ratings")

            # 2b. Seasons (V3.13, cache-optimized in V3.19) — build the
            # per-series season air-year cache so the per-series filter can
            # consult it during matching.
            #
            # PERF (V3.19): this phase costs ~15 s on M-series / ~30-60 s on
            # older hardware: it streams the 215 MB basics dump to build an
            # 8.5M-key ``{tvEpisode → startYear}`` map, then streams the
            # 52 MB episode dump to aggregate. Result is deterministic from
            # the two source files alone — so if neither has changed since
            # last successful scan, the on-disk ``series_seasons`` rows are
            # still valid. We short-circuit via a config cache key
            # (``seasons_cache_key``) built from the downloader's
            # ``.last_modified`` sidecars. Thomas re-runs frequently and
            # IMDb dumps refresh ~daily, so most scans hit the fast path.
            phase("seasons", "aggregating per-season air years…")
            cache_key = _seasons_cache_key(basics_path, episodes_path)
            cache_row = conn.execute(
                "SELECT value FROM config WHERE key='seasons_cache_key'"
            ).fetchone()
            existing_rows = conn.execute(
                "SELECT COUNT(*) FROM series_seasons"
            ).fetchone()[0]
            if (
                cache_row is not None
                and cache_row["value"] == cache_key
                and existing_rows > 0
            ):
                on_progress(
                    f"seasons cache hit — reusing {existing_rows:,} rows "
                    f"(episode/basics dumps unchanged); skipping rebuild"
                )
            else:
                # Cache miss — rebuild from scratch. Emit heartbeats during
                # the two silent ~7-10 s stream passes so the phase doesn't
                # look hung (this was the visible symptom Thomas hit).
                episode_years = _load_episode_years(
                    basics_path, on_progress=on_progress
                )
                on_progress(f"loaded {len(episode_years):,} episode air years")
                self._check_cancel("cancelled during season aggregation")

                # Aggregate: for each (parent_tconst, season_number), take
                # the MIN of its episodes' startYear as season_air_year,
                # and count episodes. Streamed — the ep-file iterator never
                # holds the full episode file in RAM.
                season_agg: dict[tuple[str, int], list[int | None]] = {}
                # value: [min_year_or_None, episode_count]
                ep_scanned = 0
                for _ep_tconst, parent_tconst, season_num in _iter_episodes(
                    episodes_path
                ):
                    ep_scanned += 1
                    if ep_scanned % 2_000_000 == 0:
                        on_progress(
                            f"  …aggregated {ep_scanned:,} episode rows "
                            f"({len(season_agg):,} seasons so far)"
                        )
                    key = (parent_tconst, season_num)
                    slot = season_agg.get(key)
                    ep_year = episode_years.get(_ep_tconst)
                    if slot is None:
                        season_agg[key] = [ep_year, 1]
                    else:
                        slot[1] += 1
                        if ep_year is not None:
                            cur = slot[0]
                            if cur is None or ep_year < cur:
                                slot[0] = ep_year

                # Bulk INSERT OR REPLACE inside an explicit transaction so
                # the write hits disk as one fsync instead of ~375K.
                # series_seasons has no FKs (see schema.py), so the
                # PRAGMA foreign_keys=ON default doesn't add work here.
                conn.execute("BEGIN IMMEDIATE")
                conn.execute("DELETE FROM series_seasons")  # full replace
                conn.executemany(
                    "INSERT INTO series_seasons "
                    "(parent_tconst, season_number, air_year, episode_count) "
                    "VALUES (?, ?, ?, ?)",
                    (
                        (parent, season, slot[0], slot[1])
                        for (parent, season), slot in season_agg.items()
                    ),
                )
                # Record the cache key so the NEXT scan can short-circuit.
                conn.execute(
                    "INSERT OR REPLACE INTO config (key, value) "
                    "VALUES ('seasons_cache_key', ?)",
                    (cache_key,),
                )
                conn.commit()
                on_progress(f"cached {len(season_agg):,} (series, season) rows")
                # Free the episode year dict + agg map — we won't need them
                # again in this scan and title.basics streaming below
                # allocates a lot.
                episode_years.clear()
                season_agg.clear()
            self._check_cancel("cancelled after season aggregation")

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
                    # Cancel check inside the main streaming loop — cheap,
                    # once per 100k rows, keeps latency to abort < ~1 s.
                    self._check_cancel("cancelled during basics diff")
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

                # Year filter — V3.17 STRICT (reverts V3.13 per-season branch).
                #
                # Every title type — movies AND series — must have
                # ``startYear >= min_year``. V3.13's "series passes if ANY
                # season has air_year >= min_year" leaked long-running shows
                # (Formula 1 1950, Great Performances 1971, Law & Order 1990)
                # into min_year=2026 scans; Thomas rejected the results and
                # picked Option A "strict" on 2026-08-10.
                #
                # We still capture qualifying seasons for series that PASS
                # the gate so the UI can show ``▼ N season matches (…)``
                # inline. That's display data only — it never affects the
                # match decision.
                qualifying_seasons: list[tuple[int, int | None, int]] = []
                is_series = title_type in self._SERIES_TYPES
                if min_year > 0:
                    if start_year is None or int(start_year) < min_year:
                        continue
                if is_series and min_year > 0:
                    # Display-only: show which seasons meet the min_year gate
                    # so the UI can render ``▼ N season matches (…)`` inline.
                    # No longer affects the match decision (V3.17 strict).
                    rows_s = conn.execute(
                        "SELECT season_number, air_year, episode_count "
                        "FROM series_seasons "
                        "WHERE parent_tconst=? AND air_year IS NOT NULL "
                        "AND air_year >= ? "
                        "ORDER BY season_number ASC",
                        (tconst, min_year),
                    ).fetchall()
                    qualifying_seasons = [
                        (r["season_number"], r["air_year"], r["episode_count"])
                        for r in rows_s
                    ]

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
                # Parallel list — same index as the just-appended match row.
                # Empty for movies / tvMovies; populated for series.
                match_seasons_by_idx.append(qualifying_seasons)

            self._check_cancel("cancelled after diff/match phase")

            # 3b. Parental-guide filter (COMPLIANCE EXCEPTION — V3.12).
            #
            # Runs only on rows that survived rating/vote/year/genre/country
            # filters, so the scrape volume is bounded (Thomas's typical set
            # hits ~150 titles → ~5 min at 2s/req). Anything blocked here is
            # dropped from ``match_rows`` before persistence so the runs row
            # and Herman-visible match list both reflect the ceilings.
            #
            # V3.13: capture the pre-PG {tconst -> qualifying_seasons} map
            # BEFORE the filter runs so we can realign the parallel season
            # list to the post-filter match_rows without depending on the
            # filter preserving row order.
            seasons_by_tconst: dict[str, list[tuple[int, int | None, int]]] = {
                row[0]: seasons
                for row, seasons in zip(match_rows, match_seasons_by_idx)
            }
            match_rows, pg_scraped, pg_dropped = self._apply_parental_guide_filter(
                conn         = conn,
                match_rows   = match_rows,
                cfg          = cfg,
                phase        = phase,
                on_progress  = on_progress,
            )
            on_progress(
                f"parental_guide: scraped {pg_scraped} title(s), "
                f"dropped {pg_dropped} for exceeding ceilings"
            )
            match_seasons_by_idx = [seasons_by_tconst[r[0]] for r in match_rows]
            assert len(match_seasons_by_idx) == len(match_rows), (
                f"season index desync: {len(match_seasons_by_idx)} vs {len(match_rows)}"
            )

            self._check_cancel("cancelled after parental_guide filter")

            # 3c. Plot filter (V3.24) — exclude titles whose OMDb plot can't
            # be fetched.  Runs after parental-guide so only titles that
            # survived all prior filters pay the OMDb cost.  The
            # ``title_metadata`` cache means repeat scans are essentially free
            # for previously-checked titles.
            #
            # Realign the seasons index after the filter (same pattern as PG
            # above) so the parallel list stays in sync.
            phase("plot_filter", "checking OMDb plots…")
            seasons_by_tconst_pre_plot: dict[str, list] = {
                row[0]: seasons
                for row, seasons in zip(match_rows, match_seasons_by_idx)
            }
            match_rows, plot_dropped = self._apply_plot_filter(
                db_path     = self._db_path,
                match_rows  = match_rows,
                on_progress = on_progress,
            )
            match_seasons_by_idx = [seasons_by_tconst_pre_plot[r[0]] for r in match_rows]
            assert len(match_seasons_by_idx) == len(match_rows), (
                f"season index desync after plot_filter: "
                f"{len(match_seasons_by_idx)} vs {len(match_rows)}"
            )

            self._check_cancel("cancelled after plot_filter")

            # 3d. Theaters filter (V3.25) — exclude titles that are still only
            # in theaters when the "Only In Theaters" checkbox is unchecked.
            # Runs after plot_filter so only titles that survived all prior
            # filters pay the OMDb cost. The title_metadata cache means
            # previously-checked titles are free on rescan.
            #
            # Reads only_in_theaters from the config table at scan time so the
            # UI checkbox always takes effect on the current run, even when
            # ScanConfig was constructed before the setting changed.
            #
            # Realign the seasons index after the filter (same pattern as PG +
            # plot_filter above) so the parallel list stays in sync.
            phase("theaters_filter", "checking theatrical release status…")
            _ot_row = conn.execute(
                "SELECT value FROM config WHERE key='only_in_theaters'"
            ).fetchone()
            _only_in_theaters_allowed: bool = (
                str(_ot_row["value"]).strip() in ("1", "true", "yes", "on")
                if _ot_row else False
            )
            seasons_by_tconst_pre_theaters: dict[str, list] = {
                row[0]: seasons
                for row, seasons in zip(match_rows, match_seasons_by_idx)
            }
            match_rows, theaters_dropped = self._apply_theaters_filter(
                db_path                  = self._db_path,
                match_rows               = match_rows,
                only_in_theaters_allowed = _only_in_theaters_allowed,
                on_progress              = on_progress,
            )
            match_seasons_by_idx = [
                seasons_by_tconst_pre_theaters[r[0]] for r in match_rows
            ]
            assert len(match_seasons_by_idx) == len(match_rows), (
                f"season index desync after theaters_filter: "
                f"{len(match_seasons_by_idx)} vs {len(match_rows)}"
            )

            self._check_cancel("cancelled after theaters_filter")

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

            # 4b. Persist match_seasons (V3.13). Look up each match row's
            # freshly-assigned id, then bulk-insert its qualifying seasons.
            # Only series with a non-empty seasons list get rows; movies
            # skip this branch entirely.
            season_insert_rows: list[tuple] = []
            for match_row, seasons in zip(match_rows, match_seasons_by_idx):
                if not seasons:
                    continue
                match_tconst = match_row[0]
                mid_row = conn.execute(
                    "SELECT id FROM matches WHERE tconst=?",
                    (match_tconst,),
                ).fetchone()
                if not mid_row:
                    continue  # shouldn't happen — INSERT OR IGNORE succeeded
                match_id = mid_row["id"]
                for season_num, air_year, ep_count in seasons:
                    season_insert_rows.append(
                        (match_id, season_num, air_year, ep_count)
                    )
            if season_insert_rows:
                conn.executemany(
                    "INSERT OR IGNORE INTO match_seasons "
                    "(match_id, season_number, air_year, episode_count) "
                    "VALUES (?, ?, ?, ?)",
                    season_insert_rows,
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

        except ScanCancelled as exc:
            # V3.13 — cooperative cancel. Reuse status='error' (see
            # ScanCancelled docstring) but set phase='cancelled' so the
            # UI can distinguish this from a real failure. The error
            # column carries Thomas's requested "superseded" wording so
            # the recent-runs table shows a clear reason.
            log_status = "error"
            log_error = str(exc) or "cancelled"
            error_msg = "cancelled — superseded by new scan request"
            try:
                conn.execute(
                    "UPDATE runs SET status='error', phase='cancelled', "
                    "completed_at=strftime('%Y-%m-%dT%H:%M:%SZ','now'), "
                    "error=? WHERE id=?",
                    (error_msg, run_id),
                )
                conn.commit()
            except Exception:
                pass
            # Overwrite log_error with the friendlier message for scans.log.
            log_error = error_msg
            # Do NOT re-raise: cancellation is a normal, user-initiated
            # exit path, and the worker thread is about to be replaced.
            # Returning a summary dict lets callers see counts-so-far.
            return {
                "run_id":     run_id,
                "scanned":    scanned,
                "new_titles": len(new_title_rows),
                "matches":    len(match_rows),
                "cancelled":  True,
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

    # NOTE (V3.8): rescan_upside() and the upside_matches table were removed
    # entirely. Thomas found the feature wasn't worth using; the button, DB
    # table, and route are all gone. See schema.py for the DROP TABLE
    # migration that cleans up existing databases.
