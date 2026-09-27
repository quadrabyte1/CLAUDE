"""
test_theaters_filter.py — V3.25 "Only In Theaters" filter tests.

Bug→TDD discipline: tests written BEFORE implementation.

Thomas's request: add a checkbox "Only In Theaters".
  - Checked  → permission granted; all titles (including in-theaters-only) appear.
  - Unchecked → suppress; titles still only in theaters are excluded.
  - Default  → unchecked (safer).

Heuristic (is_only_in_theaters):
  DVD past date       → False  (already on home video)
  DVD future date     → True   (still in theaters)
  DVD N/A, release 30 days ago → True (within theatrical window)
  DVD N/A, release 200 days ago → False (past THEATRICAL_WINDOW_DAYS)
  DVD N/A, release N/A → False (unknown → don't over-filter)
  Type=series          → always False
  Malformed DVD, release 30 days ago → True (falls back to Released)
  Malformed both       → False

_apply_theaters_filter integration:
  Unchecked + 1 in-theaters + 1 streaming → matches contains only streaming
  Checked   + same input   → matches contains both
  Unchecked + no OMDb data for a title    → title passes (don't over-filter unknowns)

UI/config:
  Checkbox state persists across scans (config table)
  Config export includes only_in_theaters
  Config import restores only_in_theaters
"""

import importlib
import json
import os
import sqlite3
import sys
from datetime import date, timedelta
from pathlib import Path
from unittest.mock import patch

import pytest


# ── Helpers ────────────────────────────────────────────────────────────────


def _make_app(tmp_path: Path):
    """Re-import MovieScanner app with a fresh temp DB (no live DB touch)."""
    db_path = str(tmp_path / "scanner.db")
    os.environ["MOVIESCANNER_DB_PATH"] = db_path

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
    conn = sqlite3.connect(db_path)
    conn.execute(
        "INSERT OR REPLACE INTO config (key, value) VALUES ('omdb_api_key', ?)", (key,)
    )
    conn.commit()
    conn.close()


def _make_match_row(tconst: str, title_type: str = "movie") -> tuple:
    """Return a minimal match tuple (same shape as scanner.py builds)."""
    return (tconst, f"Title {tconst}", 2026, title_type, 8.0, 1000, "Drama", "drama", 1)


def _setup_scanner_db(tmp_path: Path) -> str:
    """Create a temp scanner DB with schema applied."""
    ms_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
    if ms_dir not in sys.path:
        sys.path.insert(0, ms_dir)
    from movie_scanner.schema import apply_schema

    db_path = str(tmp_path / "scanner.db")
    conn = sqlite3.connect(db_path)
    apply_schema(conn)
    conn.execute(
        "INSERT OR REPLACE INTO config (key, value) VALUES ('omdb_api_key', 'test-key')"
    )
    conn.commit()
    conn.close()
    return db_path


def _import_helpers():
    """Import the helper functions from scanner.py."""
    ms_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
    if ms_dir not in sys.path:
        sys.path.insert(0, ms_dir)
    from movie_scanner.scanner import is_only_in_theaters, parse_omdb_date, Scanner, THEATRICAL_WINDOW_DAYS
    return is_only_in_theaters, parse_omdb_date, Scanner, THEATRICAL_WINDOW_DAYS


# ══════════════════════════════════════════════════════════════════════════════
# Unit tests: is_only_in_theaters — 8 cases
# ══════════════════════════════════════════════════════════════════════════════


class TestIsOnlyInTheaters:
    """Unit tests for the is_only_in_theaters() module-level helper."""

    def test_case1_dvd_past_date_returns_false(self):
        """Case 1 — DVD date is in the past → title is on home video → False."""
        is_only_in_theaters, _, _, _ = _import_helpers()
        today = date(2026, 9, 27)
        omdb = {"DVD": "01 Jan 2026", "Released": "01 Oct 2025", "Type": "movie"}
        assert is_only_in_theaters(omdb, today) is False

    def test_case2_dvd_future_date_returns_true(self):
        """Case 2 — DVD date is in the future → still in theatrical window → True."""
        is_only_in_theaters, _, _, _ = _import_helpers()
        today = date(2026, 9, 27)
        # DVD release one month from now
        future_dvd = (today + timedelta(days=30)).strftime("%d %b %Y")
        omdb = {"DVD": future_dvd, "Released": "01 Sep 2026", "Type": "movie"}
        assert is_only_in_theaters(omdb, today) is True

    def test_case3_no_dvd_recent_release_returns_true(self):
        """Case 3 — DVD 'N/A', Released 30 days ago → within window → True."""
        is_only_in_theaters, _, _, _ = _import_helpers()
        today = date(2026, 9, 27)
        released = (today - timedelta(days=30)).strftime("%d %b %Y")
        omdb = {"DVD": "N/A", "Released": released, "Type": "movie"}
        assert is_only_in_theaters(omdb, today) is True

    def test_case4_no_dvd_old_release_returns_false(self):
        """Case 4 — DVD 'N/A', Released 200 days ago → past THEATRICAL_WINDOW_DAYS → False."""
        is_only_in_theaters, _, _, THEATRICAL_WINDOW_DAYS = _import_helpers()
        today = date(2026, 9, 27)
        # 200 days > THEATRICAL_WINDOW_DAYS (180)
        released = (today - timedelta(days=200)).strftime("%d %b %Y")
        omdb = {"DVD": "N/A", "Released": released, "Type": "movie"}
        assert THEATRICAL_WINDOW_DAYS < 200, (
            f"THEATRICAL_WINDOW_DAYS ({THEATRICAL_WINDOW_DAYS}) should be < 200 "
            f"for this test to make sense"
        )
        assert is_only_in_theaters(omdb, today) is False

    def test_case5_no_dvd_no_released_returns_false(self):
        """Case 5 — DVD 'N/A', Released 'N/A' → unknown → False (don't over-filter)."""
        is_only_in_theaters, _, _, _ = _import_helpers()
        today = date(2026, 9, 27)
        omdb = {"DVD": "N/A", "Released": "N/A", "Type": "movie"}
        assert is_only_in_theaters(omdb, today) is False

    def test_case6_series_always_false(self):
        """Case 6 — Type='series' → series never in theaters → False."""
        is_only_in_theaters, _, _, _ = _import_helpers()
        today = date(2026, 9, 27)
        # Even with a very recent release and no DVD
        released = (today - timedelta(days=5)).strftime("%d %b %Y")
        omdb = {"DVD": "N/A", "Released": released, "Type": "series"}
        assert is_only_in_theaters(omdb, today) is False

    def test_case7_malformed_dvd_falls_back_to_released(self):
        """Case 7 — Malformed DVD string, Released 30 days ago → falls back → True."""
        is_only_in_theaters, _, _, _ = _import_helpers()
        today = date(2026, 9, 27)
        released = (today - timedelta(days=30)).strftime("%d %b %Y")
        omdb = {"DVD": "not-a-date", "Released": released, "Type": "movie"}
        assert is_only_in_theaters(omdb, today) is True

    def test_case8_malformed_both_returns_false(self):
        """Case 8 — Malformed DVD and malformed Released → False (don't over-filter)."""
        is_only_in_theaters, _, _, _ = _import_helpers()
        today = date(2026, 9, 27)
        omdb = {"DVD": "not-a-date", "Released": "also-not-a-date", "Type": "movie"}
        assert is_only_in_theaters(omdb, today) is False


# ══════════════════════════════════════════════════════════════════════════════
# Integration tests: _apply_theaters_filter
# ══════════════════════════════════════════════════════════════════════════════


class TestApplyTheatersFilter:
    """Integration tests for Scanner._apply_theaters_filter."""

    def _call_theaters_filter(
        self,
        db_path: str,
        match_rows: list,
        omdb_map: dict,
        only_in_theaters_allowed: bool,
    ):
        """Call _apply_theaters_filter with mocked OMDb responses.

        omdb_map: tconst → dict with DVD/Released/Type fields (raw OMDb shape).
        If a tconst is not in omdb_map, the fetch returns an error dict.
        """
        ms_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
        if ms_dir not in sys.path:
            sys.path.insert(0, ms_dir)
        from movie_scanner.scanner import Scanner
        from movie_scanner.omdb import OMDbClient

        scanner = Scanner(db_path=db_path)

        def _fake_fetch(tconst: str, **kwargs) -> dict:
            if tconst in omdb_map:
                raw = omdb_map[tconst]
                return {
                    "plot": "Some plot.",
                    "released": raw.get("Released"),
                    "runtime": None,
                    "director": None,
                    "rt_score": None,
                    "imdb_rating": None,
                    "metascore": None,
                    "country": "USA",
                    "language": "English",
                    "dvd": raw.get("DVD"),
                    "type": raw.get("Type", "movie"),
                    "error": None,
                }
            # No OMDb data → error response
            return {
                "plot": None, "released": None, "runtime": None,
                "director": None, "rt_score": None, "imdb_rating": None,
                "metascore": None, "country": None, "language": None,
                "dvd": None, "type": None,
                "error": "Movie not found!",
            }

        with patch.object(OMDbClient, "fetch", side_effect=_fake_fetch):
            kept, dropped = scanner._apply_theaters_filter(
                db_path=db_path,
                match_rows=match_rows,
                only_in_theaters_allowed=only_in_theaters_allowed,
                on_progress=lambda _: None,
            )
        return kept, dropped

    def test_unchecked_filters_out_theaters_only_title(self, tmp_path):
        """Checkbox unchecked + 1 in-theaters + 1 streaming → only streaming kept."""
        db_path = _setup_scanner_db(tmp_path)
        today = date.today()

        # in_theaters: released recently, no DVD
        in_theaters_released = (today - timedelta(days=20)).strftime("%d %b %Y")
        # streaming: has a past DVD date
        streaming_dvd = (today - timedelta(days=60)).strftime("%d %b %Y")

        rows = [
            _make_match_row("ttInTheaters"),
            _make_match_row("ttStreaming"),
        ]
        omdb_map = {
            "ttInTheaters": {"DVD": "N/A", "Released": in_theaters_released, "Type": "movie"},
            "ttStreaming":   {"DVD": streaming_dvd,    "Released": in_theaters_released, "Type": "movie"},
        }
        kept, dropped = self._call_theaters_filter(
            db_path, rows, omdb_map, only_in_theaters_allowed=False
        )
        kept_tconsts = [r[0] for r in kept]
        assert "ttStreaming" in kept_tconsts, f"Streaming title missing from kept: {kept_tconsts}"
        assert "ttInTheaters" not in kept_tconsts, f"In-theaters title should be filtered: {kept_tconsts}"
        assert dropped == 1

    def test_checked_passes_everything_through(self, tmp_path):
        """Checkbox checked → all titles pass regardless of in-theaters status."""
        db_path = _setup_scanner_db(tmp_path)
        today = date.today()

        in_theaters_released = (today - timedelta(days=20)).strftime("%d %b %Y")
        streaming_dvd = (today - timedelta(days=60)).strftime("%d %b %Y")

        rows = [
            _make_match_row("ttInTheaters"),
            _make_match_row("ttStreaming"),
        ]
        omdb_map = {
            "ttInTheaters": {"DVD": "N/A", "Released": in_theaters_released, "Type": "movie"},
            "ttStreaming":   {"DVD": streaming_dvd,    "Released": in_theaters_released, "Type": "movie"},
        }
        kept, dropped = self._call_theaters_filter(
            db_path, rows, omdb_map, only_in_theaters_allowed=True
        )
        assert len(kept) == 2, f"Expected both titles kept, got {len(kept)}"
        assert dropped == 0

    def test_unchecked_no_omdb_data_passes_through(self, tmp_path):
        """Checkbox unchecked + no OMDb DVD/Released data → title passes (don't over-filter)."""
        db_path = _setup_scanner_db(tmp_path)
        rows = [_make_match_row("ttNoData")]
        # omdb_map is empty → fetch returns error dict
        kept, dropped = self._call_theaters_filter(
            db_path, rows, {}, only_in_theaters_allowed=False
        )
        assert len(kept) == 1, f"Title with no OMDb data should pass through; got kept={kept}"
        assert dropped == 0


# ══════════════════════════════════════════════════════════════════════════════
# Config persistence tests
# ══════════════════════════════════════════════════════════════════════════════


class TestTheatersFilterConfig:
    """Config table, export/import, and Flask route tests."""

    def _post_config(self, client, extra: dict = None):
        """POST a minimal valid config form to /config."""
        form = {
            "min_rating": "7.0",
            "min_votes": "100",
            "min_year": "2026",
            "exclude_countries": "",
            "title_types": "movie",
            "max_sex_nudity": "severe",
            "max_violence_gore": "severe",
            "max_profanity": "severe",
            "max_alcohol_drugs": "severe",
            "max_frightening": "severe",
        }
        if extra:
            form.update(extra)
        return client.post("/config", data=form, follow_redirects=True)

    def test_checkbox_state_persists_unchecked(self, tmp_path):
        """Checkbox unchecked → config table stores only_in_theaters='0'."""
        ms_app, client, db_path = _make_app(tmp_path)
        # Post without only_in_theaters → unchecked
        resp = self._post_config(client)
        assert resp.status_code == 200

        conn = sqlite3.connect(db_path)
        row = conn.execute(
            "SELECT value FROM config WHERE key='only_in_theaters'"
        ).fetchone()
        conn.close()
        assert row is not None, "only_in_theaters config key should exist after save"
        assert row[0] == "0", f"Expected '0', got {row[0]!r}"

    def test_checkbox_state_persists_checked(self, tmp_path):
        """Checkbox checked → config table stores only_in_theaters='1'."""
        ms_app, client, db_path = _make_app(tmp_path)
        resp = self._post_config(client, extra={"only_in_theaters": "1"})
        assert resp.status_code == 200

        conn = sqlite3.connect(db_path)
        row = conn.execute(
            "SELECT value FROM config WHERE key='only_in_theaters'"
        ).fetchone()
        conn.close()
        assert row is not None, "only_in_theaters config key should exist after save"
        assert row[0] == "1", f"Expected '1', got {row[0]!r}"

    def test_config_export_includes_only_in_theaters(self, tmp_path):
        """GET /config/export → JSON includes only_in_theaters key."""
        ms_app, client, db_path = _make_app(tmp_path)
        self._post_config(client, extra={"only_in_theaters": "1"})

        resp = client.get("/config/export")
        assert resp.status_code == 200
        payload = json.loads(resp.data)
        assert "only_in_theaters" in payload["config"], (
            f"only_in_theaters missing from export config keys: {list(payload['config'].keys())}"
        )
        assert payload["config"]["only_in_theaters"] == "1"

    def test_config_import_restores_only_in_theaters(self, tmp_path):
        """POST /config/import → restores only_in_theaters from the JSON file."""
        ms_app, client, db_path = _make_app(tmp_path)

        # Build a minimal valid export payload with only_in_theaters='1'
        payload = {
            "version": "v1",
            "exported_at": "2026-09-27T12:00:00Z",
            "config": {
                "tags":           "[]",
                "exclude_tags":   "[]",
                "min_rating":     "7.0",
                "omdb_api_key":   "test-key",
                "min_votes":      "100",
                "min_year":       "2026",
                "only_in_theaters": "1",
            },
            "dismissed_tconsts": [],
        }
        import io
        file_data = json.dumps(payload).encode()
        resp = client.post(
            "/config/import",
            data={"file": (io.BytesIO(file_data), "test_import.json")},
            content_type="multipart/form-data",
            follow_redirects=True,
        )
        assert resp.status_code == 200

        conn = sqlite3.connect(db_path)
        row = conn.execute(
            "SELECT value FROM config WHERE key='only_in_theaters'"
        ).fetchone()
        conn.close()
        assert row is not None, "only_in_theaters should be in config after import"
        assert row[0] == "1", f"Expected '1', got {row[0]!r}"


# ══════════════════════════════════════════════════════════════════════════════
# Regression: APP_VERSION
# ══════════════════════════════════════════════════════════════════════════════


class TestRegressionV325:

    def test_app_version_is_v3_25(self, tmp_path):
        """APP_VERSION must be V3.25 (version bump from V3.24)."""
        ms_app, client, db_path = _make_app(tmp_path)
        assert ms_app.APP_VERSION == "V3.25", (
            f"Expected V3.25, got {ms_app.APP_VERSION!r}"
        )
