"""
test_backfill_omdb_type_dvd.py — Tests for the Part A backfill script.

Uses a temp DB fixture — NEVER touches the live scanner.db.

Test plan
---------
1. Unit: _rows_needing_refresh returns only rows missing type or dvd.
2. Unit: _read_omdb_key returns key or None.
3. Integration: run_backfill updates missing-field rows via mocked OMDbClient.
4. Integration: run_backfill correctly counts errors when OMDb returns error.
5. Integration: --dry-run prints plan but does no fetches.
6. Integration: rows that already have both type and dvd are skipped.
"""

import os
import sqlite3
import sys
from pathlib import Path
from unittest.mock import patch, call

import pytest

# ── Path setup (mirrors the script) ──────────────────────────────────────────
_TESTS_DIR  = os.path.dirname(os.path.abspath(__file__))
_MS_DIR     = os.path.dirname(_TESTS_DIR)
_REPO_ROOT  = os.path.dirname(_MS_DIR)
for _p in (_MS_DIR, _REPO_ROOT):
    if _p not in sys.path:
        sys.path.insert(0, _p)

from movie_scanner.schema import apply_schema
from movie_scanner.omdb import OMDbClient


# ── Import the script under test ──────────────────────────────────────────────
import importlib.util

_SCRIPT_PATH = os.path.join(_MS_DIR, "scripts", "backfill_omdb_type_dvd.py")


def _load_backfill_module():
    spec = importlib.util.spec_from_file_location("backfill_omdb_type_dvd", _SCRIPT_PATH)
    mod  = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


# ── Fixtures ──────────────────────────────────────────────────────────────────


def _make_db(tmp_path: Path, omdb_key: str = "test-key") -> str:
    """Return path to a fresh temp scanner.db with schema and test rows."""
    db_path = str(tmp_path / "scanner.db")
    conn = sqlite3.connect(db_path)
    apply_schema(conn)
    conn.execute(
        "INSERT OR REPLACE INTO config (key, value) VALUES ('omdb_api_key', ?)",
        (omdb_key,),
    )
    conn.commit()
    conn.close()
    return db_path


def _insert_metadata_row(
    db_path: str,
    tconst: str,
    type_val: str | None = None,
    dvd_val:  str | None = None,
    plot:     str | None = "A plot.",
) -> None:
    """Insert a title_metadata row with optional type/dvd."""
    conn = sqlite3.connect(db_path)
    conn.execute(
        """
        INSERT INTO title_metadata (tconst, plot, type, dvd)
        VALUES (?, ?, ?, ?)
        ON CONFLICT(tconst) DO UPDATE SET
            plot = excluded.plot,
            type = excluded.type,
            dvd  = excluded.dvd
        """,
        (tconst, plot, type_val, dvd_val),
    )
    conn.commit()
    conn.close()


def _read_metadata(db_path: str, tconst: str) -> dict | None:
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    row = conn.execute(
        "SELECT type, dvd, error FROM title_metadata WHERE tconst=?", (tconst,)
    ).fetchone()
    conn.close()
    return dict(row) if row else None


def _good_omdb_response(tconst: str, **kwargs) -> dict:
    return {
        "plot": "A great show.",
        "released": "01 Sep 2026",
        "runtime": None,
        "director": None,
        "rt_score": None,
        "imdb_rating": None,
        "metascore": None,
        "country": "USA",
        "language": "English",
        "dvd": "N/A",
        "type": "series",
        "error": None,
    }


# ══════════════════════════════════════════════════════════════════════════════
# Unit tests
# ══════════════════════════════════════════════════════════════════════════════


class TestRowsNeedingRefresh:

    def test_returns_only_rows_missing_type_or_dvd(self, tmp_path):
        mod     = _load_backfill_module()
        db_path = _make_db(tmp_path)

        _insert_metadata_row(db_path, "ttMissing1", type_val=None, dvd_val=None)
        _insert_metadata_row(db_path, "ttMissingType", type_val=None, dvd_val="N/A")
        _insert_metadata_row(db_path, "ttMissingDvd", type_val="movie", dvd_val=None)
        _insert_metadata_row(db_path, "ttComplete", type_val="movie", dvd_val="N/A")

        rows = mod._rows_needing_refresh(db_path)
        assert "ttMissing1"    in rows, "Row missing both should be included"
        assert "ttMissingType" in rows, "Row missing type should be included"
        assert "ttMissingDvd"  in rows, "Row missing dvd should be included"
        assert "ttComplete"  not in rows, "Row with both fields should be excluded"

    def test_empty_table_returns_empty_list(self, tmp_path):
        mod     = _load_backfill_module()
        db_path = _make_db(tmp_path)
        rows = mod._rows_needing_refresh(db_path)
        assert rows == []


class TestReadOmdbKey:

    def test_returns_key_when_present(self, tmp_path):
        mod     = _load_backfill_module()
        db_path = _make_db(tmp_path, omdb_key="abc123")
        assert mod._read_omdb_key(db_path) == "abc123"

    def test_returns_none_when_absent(self, tmp_path):
        mod     = _load_backfill_module()
        db_path = _make_db(tmp_path)
        # Delete the key
        conn = sqlite3.connect(db_path)
        conn.execute("DELETE FROM config WHERE key='omdb_api_key'")
        conn.commit()
        conn.close()
        assert mod._read_omdb_key(db_path) is None


# ══════════════════════════════════════════════════════════════════════════════
# Integration tests
# ══════════════════════════════════════════════════════════════════════════════


class TestRunBackfill:

    def test_refreshes_missing_rows(self, tmp_path):
        """run_backfill updates rows that are missing type/dvd.

        We patch OMDbClient._fetch_from_api (the network layer) rather than
        the entire fetch() method so that the cache-write path (_save_cache)
        still executes and the DB rows actually get updated.
        """
        mod     = _load_backfill_module()
        db_path = _make_db(tmp_path)

        # Insert 3 rows missing fields
        for tc in ("ttA", "ttB", "ttC"):
            _insert_metadata_row(db_path, tc, type_val=None, dvd_val=None)

        # Patch the network layer only — cache write still runs.
        with patch.object(
            OMDbClient, "_fetch_from_api", side_effect=_good_omdb_response
        ):
            result = mod.run_backfill(db_path=db_path, dry_run=False)

        assert result["refreshed"] == 3
        assert result["errored"]   == 0

        # Verify the DB rows were updated by the cache-write path.
        for tc in ("ttA", "ttB", "ttC"):
            row = _read_metadata(db_path, tc)
            assert row is not None
            assert row["type"] == "series", f"{tc} type not updated"
            assert row["dvd"]  == "N/A",    f"{tc} dvd not updated"

    def test_counts_errors_correctly(self, tmp_path):
        """run_backfill counts and records tconsts that OMDb errors on."""
        mod     = _load_backfill_module()
        db_path = _make_db(tmp_path)

        _insert_metadata_row(db_path, "ttOk",  type_val=None, dvd_val=None)
        _insert_metadata_row(db_path, "ttBad", type_val=None, dvd_val=None)

        def _mixed_response(tconst: str, **kwargs):
            if tconst == "ttBad":
                return {
                    "plot": None, "released": None, "runtime": None,
                    "director": None, "rt_score": None, "imdb_rating": None,
                    "metascore": None, "country": None, "language": None,
                    "dvd": None, "type": None,
                    "error": "Movie not found!",
                }
            return _good_omdb_response(tconst)

        with patch.object(OMDbClient, "fetch", side_effect=_mixed_response):
            result = mod.run_backfill(db_path=db_path, dry_run=False)

        assert result["refreshed"] == 1
        assert result["errored"]   == 1
        assert "ttBad" in result["errored_tconsts"]

    def test_dry_run_does_no_fetches(self, tmp_path):
        """dry_run=True prints plan without calling OMDb."""
        mod     = _load_backfill_module()
        db_path = _make_db(tmp_path)

        _insert_metadata_row(db_path, "ttDry", type_val=None, dvd_val=None)

        with patch.object(OMDbClient, "fetch") as mock_fetch:
            result = mod.run_backfill(db_path=db_path, dry_run=True)

        mock_fetch.assert_not_called()
        assert result["refreshed"] == 0
        assert result["errored"]   == 0

    def test_already_complete_rows_not_fetched(self, tmp_path):
        """Rows that already have both type and dvd are not refreshed."""
        mod     = _load_backfill_module()
        db_path = _make_db(tmp_path)

        # One complete row, one missing
        _insert_metadata_row(db_path, "ttComplete", type_val="movie", dvd_val="N/A")
        _insert_metadata_row(db_path, "ttMissing",  type_val=None,    dvd_val=None)

        fetched_tconsts = []

        def _tracking_fetch(tconst: str, **kwargs):
            fetched_tconsts.append(tconst)
            return _good_omdb_response(tconst)

        with patch.object(OMDbClient, "fetch", side_effect=_tracking_fetch):
            result = mod.run_backfill(db_path=db_path, dry_run=False)

        assert "ttComplete" not in fetched_tconsts, "Complete row should not be fetched"
        assert "ttMissing"  in     fetched_tconsts, "Missing row should be fetched"
        assert result["refreshed"] == 1

    def test_no_rows_exits_cleanly(self, tmp_path):
        """When no rows need refresh, backfill returns zeros without errors."""
        mod     = _load_backfill_module()
        db_path = _make_db(tmp_path)
        # No rows inserted
        with patch.object(OMDbClient, "fetch") as mock_fetch:
            result = mod.run_backfill(db_path=db_path, dry_run=False)
        mock_fetch.assert_not_called()
        assert result["refreshed"] == 0
        assert result["errored"]   == 0
