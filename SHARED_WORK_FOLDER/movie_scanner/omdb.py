"""omdb.py — Thin OMDb API client with SQLite cache.

Provides :class:`OMDbClient`, which fetches and caches title metadata from
the OMDb API (http://www.omdbapi.com/).  Cached rows live in the
``title_metadata`` table; a successful fetch is never repeated.  Failed
fetches (network errors, OMDb "not found", quota exceeded) are also cached
so repeated hovers on the same missing title never hit the network again.

Compliance boundary
-------------------
Enrichment MUST go through OMDb (or another licensed API). Never fetch
imdb.com/* pages — prohibited by IMDb site TOS. Dataset dumps come from
``datasets.imdbws.com`` (personal/non-commercial license) via
``downloader.py``. If a future feature needs a data point OMDb doesn't
expose, add another licensed provider — do NOT scrape imdb.com HTML.

See also: ``movie_scanner/parental_guide.py``. That module is the ONE
sanctioned exception to this rule — it scrapes the parental-guide page
for personal-use severity data. It is deliberately isolated (no imports
from here, and vice-versa) so that a future removal is a single
``git rm``. Do not import it from this file or ``scanner.py``'s main
flow-of-control except at the explicit parental-guide filter step.

Usage::

    from movie_scanner import OMDbClient

    client = OMDbClient(api_key="208c6d0e", db_path="/path/to/scanner.db")
    data = client.fetch("tt0059742")
    print(data["rt_score"])    # "83%"
    print(data["plot"])        # "A young novice is sent…"
"""

import json
import sqlite3
import urllib.error
import urllib.request
from typing import Optional

_OMDB_BASE = "http://www.omdbapi.com/"

# Dict keys returned by fetch() — all values are str | None.
_FIELDS = ("plot", "released", "runtime", "director",
           "rt_score", "imdb_rating", "metascore", "country", "language", "error")


class OMDbClient:
    """Fetch and cache OMDb title metadata.

    Parameters
    ----------
    api_key:
        OMDb API key.  Retrieved from the ``config`` table in the caller;
        never hard-coded here.
    db_path:
        Absolute path to ``scanner.db``.  The ``title_metadata`` table is
        assumed to already exist (created by :func:`movie_scanner.schema.apply_schema`).
    timeout:
        HTTP request timeout in seconds (default 5.0).
    """

    def __init__(self, api_key: str, db_path: str, timeout: float = 5.0) -> None:
        self._api_key = api_key
        self._db_path = db_path
        self._timeout = timeout

    # ── public ────────────────────────────────────────────────────────────────

    def fetch(self, tconst: str, force_refresh: bool = False) -> dict:
        """Return cached metadata for *tconst*, or fetch + cache on miss.

        Returns a dict with keys: ``plot``, ``released``, ``runtime``,
        ``director``, ``rt_score``, ``imdb_rating``, ``metascore``, ``error``.
        Any field that is absent or unknown is ``None``.

        If ``force_refresh=True``, the cache row is deleted before fetching so
        the OMDb API is always contacted regardless of what is stored.
        """
        conn = self._conn()
        try:
            if force_refresh:
                conn.execute("DELETE FROM title_metadata WHERE tconst=?", (tconst,))
                conn.commit()
            else:
                cached = self._load_cache(conn, tconst)
                if cached is not None:
                    return cached

            # Cache miss — go to the network.
            result = self._fetch_from_api(tconst)
            self._save_cache(conn, tconst, result)
            return result
        finally:
            conn.close()

    # ── private ───────────────────────────────────────────────────────────────

    def _conn(self) -> sqlite3.Connection:
        c = sqlite3.connect(self._db_path)
        c.row_factory = sqlite3.Row
        c.execute("PRAGMA foreign_keys = ON")
        return c

    @staticmethod
    def _load_cache(conn: sqlite3.Connection, tconst: str) -> Optional[dict]:
        """Return the cached row as a plain dict, or None if not found."""
        row = conn.execute(
            "SELECT plot, released, runtime, director, "
            "rt_score, imdb_rating, metascore, country, language, error "
            "FROM title_metadata WHERE tconst=?",
            (tconst,),
        ).fetchone()
        if row is None:
            return None
        return {k: row[k] for k in _FIELDS}

    def _fetch_from_api(self, tconst: str) -> dict:
        """Hit the OMDb API and return a normalised dict.

        On any failure (network, quota, not found) the returned dict has all
        data fields as None and ``error`` set to a descriptive string.
        """
        # COMPLIANCE: Only the OMDb licensed endpoint is called here.
        # If OMDb doesn't return the field you need, add another licensed
        # provider — do NOT reach for imdb.com/title/<id>/ HTML. That is a
        # TOS violation and would poison our right to redistribute anything.
        url = f"{_OMDB_BASE}?i={tconst}&apikey={self._api_key}&plot=short"
        try:
            req = urllib.request.Request(url, headers={"Accept": "application/json"})
            with urllib.request.urlopen(req, timeout=self._timeout) as resp:
                raw = resp.read().decode("utf-8")
        except urllib.error.URLError as exc:
            return self._error_dict(f"Network error: {exc.reason}")
        except Exception as exc:  # pragma: no cover — catch-all for unexpected IO errors
            return self._error_dict(f"Unexpected fetch error: {exc}")

        try:
            data = json.loads(raw)
        except json.JSONDecodeError as exc:
            return self._error_dict(f"JSON parse error: {exc}")

        if data.get("Response") == "False":
            return self._error_dict(data.get("Error", "OMDb returned Response=False"))

        # Parse Ratings array into individual fields.
        ratings = data.get("Ratings", [])
        rt_score = None
        imdb_rating = None
        metascore = None
        for entry in ratings:
            src = entry.get("Source", "")
            val = entry.get("Value")
            if src == "Rotten Tomatoes":
                rt_score = val
            elif src == "Internet Movie Database":
                imdb_rating = val
            elif src == "Metacritic":
                metascore = val

        # Normalise sentinel values OMDb returns for missing data.
        def _clean(v: Optional[str]) -> Optional[str]:
            if v in (None, "N/A", ""):
                return None
            return v

        return {
            "plot":        _clean(data.get("Plot")),
            "released":    _clean(data.get("Released")),
            "runtime":     _clean(data.get("Runtime")),
            "director":    _clean(data.get("Director")),
            "rt_score":    _clean(rt_score),
            "imdb_rating": _clean(imdb_rating),
            "metascore":   _clean(metascore),
            "country":     _clean(data.get("Country")),
            "language":    _clean(data.get("Language")),
            "error":       None,
        }

    @staticmethod
    def _error_dict(reason: str) -> dict:
        return {
            "plot": None, "released": None, "runtime": None,
            "director": None, "rt_score": None, "imdb_rating": None,
            "metascore": None, "country": None, "language": None, "error": reason,
        }

    @staticmethod
    def _save_cache(conn: sqlite3.Connection, tconst: str, data: dict) -> None:
        """Upsert a metadata row into ``title_metadata``."""
        # Serialize full raw_json isn't available here (we don't keep it
        # through the parse path), so raw_json is stored as NULL on the
        # error path and as a JSON dump of the extracted fields on success.
        conn.execute(
            """
            INSERT INTO title_metadata
                (tconst, plot, released, runtime, director,
                 rt_score, imdb_rating, metascore, country, language, error)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(tconst) DO UPDATE SET
                plot        = excluded.plot,
                released    = excluded.released,
                runtime     = excluded.runtime,
                director    = excluded.director,
                rt_score    = excluded.rt_score,
                imdb_rating = excluded.imdb_rating,
                metascore   = excluded.metascore,
                country     = excluded.country,
                language    = excluded.language,
                error       = excluded.error,
                fetched_at  = strftime('%Y-%m-%dT%H:%M:%SZ','now')
            """,
            (
                tconst,
                data.get("plot"),
                data.get("released"),
                data.get("runtime"),
                data.get("director"),
                data.get("rt_score"),
                data.get("imdb_rating"),
                data.get("metascore"),
                data.get("country"),
                data.get("language"),
                data.get("error"),
            ),
        )
        conn.commit()
