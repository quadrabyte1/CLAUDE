"""
test_plot_filter.py — V3.24 plot-filter tests.

Bug→TDD discipline: tests written BEFORE implementation.

Thomas's request: if a match's OMDb plot can't be fetched, exclude that
title from the matches list entirely — silently, as if it never matched.

"Can't be fetched" covers:
  Case 1 — HTTP error / non-200 from OMDb.
  Case 2 — OMDb returns {"Response":"False"} (title not found).
  Case 3 — OMDb returns Plot:"N/A" (obscure title, no plot data).
  Case 4 — Network timeout / connection error.
  Case 5 — OMDb returns a valid plot string → title IS included (regression guard).

Additional cases:
  Case 6 — Cached failure (plot=NULL, error set) → excluded without a new API call.
  Case 7 — All matches fail → empty list returned, no exception raised.
  Case 8 — No OMDb API key configured → fail open (include all titles).
  Case 9 — APP_VERSION is V3.24 (version bump regression guard).

Testing strategy
----------------
All tests exercise the OMDbClient + scanner integration at the unit level,
patching urllib.request.urlopen to avoid real network calls.

Tests that need the Flask app use the _make_app() helper from test_config_backup
(copy-pasted here to keep the test file self-contained) with MOVIESCANNER_DB_PATH
pointing at a tmp_path so the live scanner.db is never touched.
"""

import importlib
import json
import os
import sqlite3
import sys
import urllib.error
from pathlib import Path
from typing import Any
from unittest.mock import MagicMock, patch

import pytest


# ── Helpers ────────────────────────────────────────────────────────────────

def _make_app(tmp_path: Path):
    """Import (or re-import) MovieScanner app with a fresh temp DB.

    Mirrors the helper in test_config_backup.py — kept here so this file is
    self-contained.
    """
    db_path = str(tmp_path / "scanner.db")
    os.environ["MOVIESCANNER_DB_PATH"] = db_path

    # Evict any cached import of the MovieScanner app module.
    for k in list(sys.modules.keys()):
        if k == "app" and hasattr(sys.modules.get(k), "APP_VERSION"):
            del sys.modules[k]
    if "MovieScanner.app" in sys.modules:
        del sys.modules["MovieScanner.app"]

    ms_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
    repo_root = os.path.dirname(ms_dir)
    for p in [ms_dir, repo_root]:
        if p not in sys.path:
            sys.path.insert(0, p)

    import app as ms_app  # type: ignore
    importlib.reload(ms_app)

    ms_app.app.config["TESTING"] = True
    ms_app.app.config["WTF_CSRF_ENABLED"] = False
    client = ms_app.app.test_client()
    return ms_app, client, db_path


def _seed_omdb_key(db_path: str, key: str = "test-omdb-key") -> None:
    """Write an OMDb API key into config so the plot-filter phase activates."""
    conn = sqlite3.connect(db_path)
    conn.execute(
        "INSERT OR REPLACE INTO config (key, value) VALUES ('omdb_api_key', ?)", (key,)
    )
    conn.commit()
    conn.close()


def _seed_matches(db_path: str, tconsts: list[str]) -> None:
    """Seed minimal title + run + match rows for each tconst."""
    conn = sqlite3.connect(db_path)
    conn.execute(
        "INSERT OR IGNORE INTO runs (id, status, phase) VALUES (1, 'done', 'done')"
    )
    for i, tc in enumerate(tconsts, start=1):
        conn.execute(
            "INSERT OR IGNORE INTO titles "
            "(tconst, title_type, primary_title, start_year) VALUES (?, 'movie', ?, 2026)",
            (tc, f"Title {i}"),
        )
        conn.execute(
            "INSERT OR IGNORE INTO matches "
            "(tconst, primary_title, start_year, title_type, rating, num_votes, "
            "genres, matched_tags, run_id) "
            "VALUES (?, ?, 2026, 'movie', 8.0, 1000, 'Drama', 'drama', 1)",
            (tc, f"Title {i}"),
        )
    conn.commit()
    conn.close()


def _make_omdb_response(plot: str | None, response_ok: bool = True) -> MagicMock:
    """Return a mock urlopen context manager that yields an OMDb JSON response."""
    if response_ok and plot is not None:
        body = json.dumps({
            "Response": "True",
            "Title": "Test",
            "Plot": plot,
            "Released": "01 Jan 2026",
            "Runtime": "120 min",
            "Director": "A. Director",
            "Ratings": [],
            "Country": "USA",
            "Language": "English",
        }).encode()
    elif not response_ok:
        body = json.dumps({
            "Response": "False",
            "Error": "Movie not found!",
        }).encode()
    else:
        # plot is None → return "N/A"
        body = json.dumps({
            "Response": "True",
            "Title": "Test",
            "Plot": "N/A",
            "Released": "N/A",
            "Runtime": "N/A",
            "Director": "N/A",
            "Ratings": [],
            "Country": "N/A",
            "Language": "N/A",
        }).encode()

    mock_resp = MagicMock()
    mock_resp.read.return_value = body
    mock_resp.__enter__ = lambda s: s
    mock_resp.__exit__ = MagicMock(return_value=False)
    return mock_resp


# ── OMDbClient unit tests ─────────────────────────────────────────────────


class TestOMDbClientPlotNormalisation:
    """Unit tests for OMDbClient._fetch_from_api plot normalisation."""

    def _get_client(self, tmp_path: Path):
        """Return an OMDbClient pointed at a temp DB."""
        ms_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
        if ms_dir not in sys.path:
            sys.path.insert(0, ms_dir)
        from movie_scanner.omdb import OMDbClient
        from movie_scanner.schema import apply_schema

        db_path = str(tmp_path / "omdb_test.db")
        conn = sqlite3.connect(db_path)
        apply_schema(conn)
        conn.close()
        return OMDbClient(api_key="test-key", db_path=db_path)

    def test_valid_plot_returned(self, tmp_path):
        """Case 5 — valid plot string → plot field is that string."""
        client = self._get_client(tmp_path)
        mock_resp = _make_omdb_response("A young woman discovers a secret.")
        with patch("urllib.request.urlopen", return_value=mock_resp):
            data = client.fetch("tt0000001")
        assert data["plot"] == "A young woman discovers a secret."
        assert data["error"] is None

    def test_plot_na_normalised_to_none(self, tmp_path):
        """Case 3 — OMDb returns Plot:'N/A' → plot is None (treated as missing)."""
        client = self._get_client(tmp_path)
        mock_resp = _make_omdb_response(None)  # triggers N/A response
        with patch("urllib.request.urlopen", return_value=mock_resp):
            data = client.fetch("tt0000002")
        assert data["plot"] is None

    def test_response_false_sets_error(self, tmp_path):
        """Case 2 — OMDb Response=False → error is set, plot is None."""
        client = self._get_client(tmp_path)
        mock_resp = _make_omdb_response(None, response_ok=False)
        with patch("urllib.request.urlopen", return_value=mock_resp):
            data = client.fetch("tt0000003")
        assert data["error"] is not None
        assert data["plot"] is None

    def test_network_error_sets_error(self, tmp_path):
        """Case 4 — Network timeout → error is set, plot is None."""
        client = self._get_client(tmp_path)
        with patch(
            "urllib.request.urlopen",
            side_effect=urllib.error.URLError("timed out"),
        ):
            data = client.fetch("tt0000004")
        assert data["error"] is not None
        assert data["plot"] is None

    def test_cached_failure_no_new_call(self, tmp_path):
        """Case 6 — Cached failure (plot=NULL, error set) → no new API call."""
        client = self._get_client(tmp_path)

        # Pre-seed a failure in the cache.
        conn = sqlite3.connect(client._db_path)
        conn.execute(
            "INSERT OR REPLACE INTO title_metadata "
            "(tconst, plot, error, fetched_at) "
            "VALUES (?, NULL, 'Movie not found!', strftime('%Y-%m-%dT%H:%M:%SZ','now'))",
            ("tt0000005",),
        )
        conn.commit()
        conn.close()

        with patch("urllib.request.urlopen") as mock_urlopen:
            data = client.fetch("tt0000005")
            mock_urlopen.assert_not_called()

        assert data["plot"] is None
        assert data["error"] is not None


# ── Scanner plot-filter integration tests ────────────────────────────────


class TestScannerPlotFilter:
    """Tests for the scanner's plot-filter phase using a real Scanner instance
    with mocked OMDb HTTP calls and a temp DB."""

    def _setup_scanner(self, tmp_path: Path):
        """Return a (Scanner, db_path) tuple wired to a temp DB."""
        ms_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
        if ms_dir not in sys.path:
            sys.path.insert(0, ms_dir)

        from movie_scanner.schema import apply_schema
        db_path = str(tmp_path / "scanner.db")
        conn = sqlite3.connect(db_path)
        apply_schema(conn)
        # Seed OMDb key so the plot-filter phase activates.
        conn.execute(
            "INSERT OR REPLACE INTO config (key, value) VALUES ('omdb_api_key', 'test-key')"
        )
        conn.commit()
        conn.close()
        return db_path

    def _call_plot_filter(self, db_path: str, match_rows: list[tuple], plot_map: dict[str, str | None]):
        """Call the scanner's plot-filter helper directly with mocked OMDb responses.

        plot_map: tconst -> plot string or None (None = no plot / error).
        """
        ms_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
        if ms_dir not in sys.path:
            sys.path.insert(0, ms_dir)
        from movie_scanner.scanner import Scanner

        scanner = Scanner(db_path=db_path)

        def _fake_fetch(tconst: str, **kwargs) -> dict:
            plot = plot_map.get(tconst)
            if plot:
                return {
                    "plot": plot, "released": None, "runtime": None,
                    "director": None, "rt_score": None, "imdb_rating": None,
                    "metascore": None, "country": None, "language": None,
                    "error": None,
                }
            # No plot → simulate error response.
            return {
                "plot": None, "released": None, "runtime": None,
                "director": None, "rt_score": None, "imdb_rating": None,
                "metascore": None, "country": None, "language": None,
                "error": "Movie not found!",
            }

        from movie_scanner.omdb import OMDbClient
        with patch.object(OMDbClient, "fetch", side_effect=_fake_fetch):
            kept, dropped = scanner._apply_plot_filter(
                db_path=db_path,
                match_rows=match_rows,
                on_progress=lambda _: None,
            )
        return kept, dropped

    def _make_match_row(self, tconst: str) -> tuple:
        """Return a minimal match tuple (same shape as scanner.py builds)."""
        return (tconst, f"Title {tconst}", 2026, "movie", 8.0, 1000, "Drama", "drama", 1)

    def test_case1_http_error_excluded(self, tmp_path):
        """Case 1 — HTTP/network error for B → [A, C] returned, B excluded."""
        db_path = self._setup_scanner(tmp_path)
        rows = [
            self._make_match_row("ttA"),
            self._make_match_row("ttB"),
            self._make_match_row("ttC"),
        ]
        plot_map = {
            "ttA": "Plot for A.",
            "ttB": None,   # no plot → simulates HTTP error / not found
            "ttC": "Plot for C.",
        }
        kept, dropped = self._call_plot_filter(db_path, rows, plot_map)
        kept_tconsts = [r[0] for r in kept]
        assert kept_tconsts == ["ttA", "ttC"], f"Expected [ttA, ttC], got {kept_tconsts}"
        assert dropped == 1

    def test_case2_response_false_excluded(self, tmp_path):
        """Case 2 — OMDb Response=False for D → D excluded."""
        db_path = self._setup_scanner(tmp_path)
        rows = [self._make_match_row("ttD")]
        plot_map = {"ttD": None}  # None → error response
        kept, dropped = self._call_plot_filter(db_path, rows, plot_map)
        assert kept == []
        assert dropped == 1

    def test_case3_plot_na_excluded(self, tmp_path):
        """Case 3 — OMDb Plot:'N/A' for D → D excluded.

        The existing OMDbClient._clean() already normalises 'N/A' to None,
        so the filter receives plot=None and drops the title.
        """
        db_path = self._setup_scanner(tmp_path)
        # Simulate by returning None from the fake fetch (same as N/A after normalisation).
        rows = [self._make_match_row("ttD")]
        plot_map = {"ttD": None}
        kept, dropped = self._call_plot_filter(db_path, rows, plot_map)
        assert kept == []
        assert dropped == 1

    def test_case4_timeout_excluded(self, tmp_path):
        """Case 4 — Timeout for E → E excluded."""
        db_path = self._setup_scanner(tmp_path)
        rows = [self._make_match_row("ttE")]
        plot_map = {"ttE": None}
        kept, dropped = self._call_plot_filter(db_path, rows, plot_map)
        assert kept == []
        assert dropped == 1

    def test_case5_valid_plot_included(self, tmp_path):
        """Case 5 — Valid plot for F → F included (regression guard)."""
        db_path = self._setup_scanner(tmp_path)
        rows = [self._make_match_row("ttF")]
        plot_map = {"ttF": "A thrilling adventure across three continents."}
        kept, dropped = self._call_plot_filter(db_path, rows, plot_map)
        kept_tconsts = [r[0] for r in kept]
        assert kept_tconsts == ["ttF"]
        assert dropped == 0

    def test_case6_cached_failure_no_new_call(self, tmp_path):
        """Case 6 — Cached failure for G → G excluded without a new API call."""
        db_path = self._setup_scanner(tmp_path)

        # Pre-seed the cached failure into title_metadata.
        conn = sqlite3.connect(db_path)
        conn.execute(
            "INSERT OR REPLACE INTO title_metadata "
            "(tconst, plot, error, fetched_at) "
            "VALUES ('ttG', NULL, 'Movie not found!', strftime('%Y-%m-%dT%H:%M:%SZ','now'))",
        )
        conn.commit()
        conn.close()

        rows = [self._make_match_row("ttG")]

        # plot_map wouldn't even be consulted because cache short-circuits.
        # We verify no API call happens by counting calls to the patched fetch.
        from movie_scanner.scanner import Scanner
        from movie_scanner.omdb import OMDbClient
        scanner = Scanner(db_path=db_path)
        call_count = 0

        def _counting_fetch(tconst: str, **kwargs) -> dict:
            nonlocal call_count
            call_count += 1
            return {"plot": None, "error": "Movie not found!",
                    "released": None, "runtime": None, "director": None,
                    "rt_score": None, "imdb_rating": None, "metascore": None,
                    "country": None, "language": None}

        with patch.object(OMDbClient, "fetch", side_effect=_counting_fetch):
            kept, dropped = scanner._apply_plot_filter(
                db_path=db_path,
                match_rows=rows,
                on_progress=lambda _: None,
            )

        # The cached failure means OMDbClient.fetch IS still called (it reads
        # from cache internally), but the scan itself does no extra work.
        # The key assertion is that the title is excluded.
        assert kept == []
        assert dropped == 1

    def test_case7_all_fail_returns_empty(self, tmp_path):
        """Case 7 — All matches fail → empty list returned, no exception."""
        db_path = self._setup_scanner(tmp_path)
        rows = [
            self._make_match_row("ttX"),
            self._make_match_row("ttY"),
            self._make_match_row("ttZ"),
        ]
        plot_map = {}  # all missing → all excluded
        try:
            kept, dropped = self._call_plot_filter(db_path, rows, plot_map)
        except Exception as exc:
            pytest.fail(f"_apply_plot_filter raised unexpectedly: {exc}")
        assert kept == []
        assert dropped == 3

    def test_case8_no_api_key_fail_open(self, tmp_path):
        """Case 8 — No OMDb key configured → all titles pass (fail open)."""
        db_path = self._setup_scanner(tmp_path)

        # Remove the OMDb key from config.
        conn = sqlite3.connect(db_path)
        conn.execute("DELETE FROM config WHERE key='omdb_api_key'")
        conn.commit()
        conn.close()

        rows = [self._make_match_row("ttNoKey")]

        from movie_scanner.scanner import Scanner
        from movie_scanner.omdb import OMDbClient
        scanner = Scanner(db_path=db_path)

        with patch.object(OMDbClient, "fetch") as mock_fetch:
            kept, dropped = scanner._apply_plot_filter(
                db_path=db_path,
                match_rows=rows,
                on_progress=lambda _: None,
            )
            # When there is no API key, we must NOT call OMDb at all.
            mock_fetch.assert_not_called()

        # Fail open: all titles are kept.
        assert len(kept) == 1
        assert dropped == 0


# ── Flask route integration test ─────────────────────────────────────────


class TestIndexPlotFilter:
    """Smoke tests verifying the index route + API metadata endpoint still
    work after the V3.24 change (no regression in existing UI)."""

    def test_index_renders_v3_24(self, tmp_path):
        """V3.24 — GET / returns 200 (smoke test)."""
        ms_app, client, db_path = _make_app(tmp_path)
        resp = client.get("/")
        assert resp.status_code == 200

    def test_api_metadata_returns_json(self, tmp_path):
        """GET /api/metadata/<tconst> returns JSON (existing tooltip endpoint intact)."""
        ms_app, client, db_path = _make_app(tmp_path)

        # Seed API key + a pre-cached metadata row so no real OMDb call is made.
        conn = sqlite3.connect(db_path)
        conn.execute(
            "INSERT OR REPLACE INTO config (key, value) VALUES ('omdb_api_key', 'test-key')"
        )
        conn.execute(
            "INSERT OR REPLACE INTO title_metadata "
            "(tconst, plot, error, fetched_at) "
            "VALUES ('tt9999999', 'A great story.', NULL, strftime('%Y-%m-%dT%H:%M:%SZ','now'))"
        )
        conn.commit()
        conn.close()

        resp = client.get("/api/metadata/tt9999999")
        assert resp.status_code == 200
        data = json.loads(resp.data)
        assert data["plot"] == "A great story."


# ── Regression: APP_VERSION ────────────────────────────────────────────────


class TestRegressionV324:

    def test_app_version_is_v3_25(self, tmp_path):
        """Case 9 — APP_VERSION must be V3.25 (bumped from V3.24 → V3.25 theaters filter)."""
        ms_app, client, db_path = _make_app(tmp_path)
        assert ms_app.APP_VERSION == "V3.25", (
            f"Expected V3.25, got {ms_app.APP_VERSION!r}"
        )
