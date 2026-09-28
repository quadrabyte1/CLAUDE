"""
test_dismissal_reason.py — V3.27 "Reason" column for the Show Dismissed view.

Bug→TDD discipline: tests written BEFORE implementation.

Thomas's request: when "Show dismissed" is checked, add a column that explains
WHY a title was filtered out. Primary value is debuggability — the Neagley
(tt33539520) diagnosis took an hour of manual DB work; this column makes it
10 seconds.

Feature scope:
  1. New `scan_eliminations` table: records every title dropped by a scanner
     filter rule, with a short reason code like "year:2020<2026".
  2. Scanner instrumentation: each filter rule in scan() records one row.
  3. UI: when show_dismissed=1 is active, the Matches table grows a "Reason"
     column. Active matches show "—". Eliminated titles show their reason code.
  4. User-dismissed matches show a "dismissed_by_user" marker.

Reason codes (all TEXT, short, human-readable):
  year:<actual_year><<min_year>         — failed year gate
  rating:<actual><<min>                 — failed rating gate
  votes:<actual><<min>                  — failed votes gate
  genre:excluded=<genre>                — excluded-genre hit
  country:<country>                     — excluded-country hit
  plot:missing                          — no OMDb plot
  only_in_theaters:filter_dropped       — in-theaters filter
  dismissed_by_user                     — user X'd in the UI

RED tests (written BEFORE the implementation):

  T1  Scanner records reason for year filter drop
  T2  Scanner records reason for rating filter drop
  T3  Scanner records reason for votes filter drop
  T4  Scanner records reason for only_in_theaters drop
  T5  UI renders Reason column header when show_dismissed=1
  T6  UI hides / skips Reason column when show_dismissed=0
  T7  User-dismissed matches carry "dismissed_by_user" reason in the UI
  T8  Active matches show "—" in the Reason column
  T9  APP_VERSION is V3.27
"""

import importlib
import json
import os
import sqlite3
import sys
from pathlib import Path
from unittest.mock import patch

import pytest


# ── Helpers ────────────────────────────────────────────────────────────────


def _repo_root() -> str:
    return os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))


def _ms_dir() -> str:
    return os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))


def _ensure_paths():
    for p in [_ms_dir(), _repo_root()]:
        if p not in sys.path:
            sys.path.insert(0, p)


def _make_app(tmp_path: Path):
    """Re-import MovieScanner app with a fresh temp DB (no live DB touch)."""
    _ensure_paths()
    db_path = str(tmp_path / "scanner.db")
    os.environ["MOVIESCANNER_DB_PATH"] = db_path

    for k in list(sys.modules.keys()):
        if k == "app" and hasattr(sys.modules.get(k), "APP_VERSION"):
            del sys.modules[k]
    if "MovieScanner.app" in sys.modules:
        del sys.modules["MovieScanner.app"]

    import app as ms_app  # type: ignore
    importlib.reload(ms_app)
    ms_app.app.config["TESTING"] = True
    ms_app.app.config["WTF_CSRF_ENABLED"] = False
    client = ms_app.app.test_client()
    return ms_app, client, db_path


def _setup_scanner_db(tmp_path: Path) -> str:
    """Create a temp scanner DB with schema applied."""
    _ensure_paths()
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


def _import_scanner():
    _ensure_paths()
    from movie_scanner.scanner import Scanner
    return Scanner


def _seed_titles_and_run(db_path: str) -> None:
    """Seed a minimal run row so INSERT INTO matches doesn't violate FK."""
    conn = sqlite3.connect(db_path)
    conn.execute("PRAGMA foreign_keys = ON")
    conn.execute(
        "INSERT OR IGNORE INTO runs (id, status, phase) VALUES (1, 'done', 'done')"
    )
    conn.commit()
    conn.close()


def _count_eliminations(db_path: str, tconst: str) -> list[str]:
    """Return list of reason codes recorded for a tconst in scan_eliminations."""
    conn = sqlite3.connect(db_path)
    rows = conn.execute(
        "SELECT reason FROM scan_eliminations WHERE tconst=? ORDER BY id ASC",
        (tconst,),
    ).fetchall()
    conn.close()
    return [r[0] for r in rows]


# ══════════════════════════════════════════════════════════════════════════════
# T1 — Scanner records reason for year filter drop
# ══════════════════════════════════════════════════════════════════════════════


class TestEliminationYearReason:

    def test_t1_year_filter_drop_recorded(self, tmp_path):
        """T1 — A title that fails the year gate must appear in scan_eliminations
        with reason starting with 'year:'.

        We drive this through _record_elimination() directly, as testing the
        full scan() path would require real .gz dumps. The contract being tested
        is: given a title that failed the year check, the scanner writes a row to
        scan_eliminations with the right reason string.
        """
        _ensure_paths()
        db_path = _setup_scanner_db(tmp_path)
        Scanner = _import_scanner()
        scanner = Scanner(db_path=db_path)

        # Call the method that the scanner will use to record eliminations.
        scanner._record_elimination(
            tconst="tt0001001",
            primary_title="Old Film",
            reason="year:2020<2026",
        )

        reasons = _count_eliminations(db_path, "tt0001001")
        assert len(reasons) == 1, f"Expected 1 elimination row, got {len(reasons)}"
        assert reasons[0].startswith("year:"), (
            f"Reason should start with 'year:'; got {reasons[0]!r}"
        )
        assert "2020" in reasons[0], f"Actual year should appear in reason; got {reasons[0]!r}"
        assert "2026" in reasons[0], f"Min year should appear in reason; got {reasons[0]!r}"


# ══════════════════════════════════════════════════════════════════════════════
# T2 — Scanner records reason for rating filter drop
# ══════════════════════════════════════════════════════════════════════════════


class TestEliminationRatingReason:

    def test_t2_rating_filter_drop_recorded(self, tmp_path):
        """T2 — A title that fails the rating gate must appear in scan_eliminations
        with reason starting with 'rating:'.
        """
        _ensure_paths()
        db_path = _setup_scanner_db(tmp_path)
        Scanner = _import_scanner()
        scanner = Scanner(db_path=db_path)

        scanner._record_elimination(
            tconst="tt0001002",
            primary_title="Low-Rated Film",
            reason="rating:6.2<7.5",
        )

        reasons = _count_eliminations(db_path, "tt0001002")
        assert len(reasons) == 1
        assert reasons[0].startswith("rating:"), (
            f"Reason should start with 'rating:'; got {reasons[0]!r}"
        )
        assert "6.2" in reasons[0], f"Actual rating should appear; got {reasons[0]!r}"
        assert "7.5" in reasons[0], f"Min rating should appear; got {reasons[0]!r}"


# ══════════════════════════════════════════════════════════════════════════════
# T3 — Scanner records reason for votes filter drop
# ══════════════════════════════════════════════════════════════════════════════


class TestEliminationVotesReason:

    def test_t3_votes_filter_drop_recorded(self, tmp_path):
        """T3 — A title with too few votes must appear in scan_eliminations
        with reason starting with 'votes:'.
        """
        _ensure_paths()
        db_path = _setup_scanner_db(tmp_path)
        Scanner = _import_scanner()
        scanner = Scanner(db_path=db_path)

        scanner._record_elimination(
            tconst="tt0001003",
            primary_title="Unknown Film",
            reason="votes:87<100",
        )

        reasons = _count_eliminations(db_path, "tt0001003")
        assert len(reasons) == 1
        assert reasons[0].startswith("votes:"), (
            f"Reason should start with 'votes:'; got {reasons[0]!r}"
        )
        assert "87" in reasons[0], f"Actual votes should appear; got {reasons[0]!r}"
        assert "100" in reasons[0], f"Min votes should appear; got {reasons[0]!r}"


# ══════════════════════════════════════════════════════════════════════════════
# T4 — Scanner records reason for only_in_theaters drop
# ══════════════════════════════════════════════════════════════════════════════


class TestEliminationTheatersReason:

    def test_t4_theaters_filter_drop_recorded(self, tmp_path):
        """T4 — A title dropped by _apply_theaters_filter must appear in
        scan_eliminations with reason 'only_in_theaters:filter_dropped'.

        We call _apply_theaters_filter with a mocked OMDb response that returns
        an in-theaters title, then check the eliminations table.
        """
        _ensure_paths()
        db_path = _setup_scanner_db(tmp_path)
        from datetime import date, timedelta
        from unittest.mock import patch
        from movie_scanner.omdb import OMDbClient
        Scanner = _import_scanner()
        scanner = Scanner(db_path=db_path)

        today = date.today()
        recent_release = (today - timedelta(days=20)).strftime("%d %b %Y")

        # A movie released 20 days ago with no DVD → only in theaters
        match_row = ("ttT001", "In-Theater Movie", 2026, "movie", 8.0, 1000, "Drama", "drama", 1)

        def _fake_fetch(tconst, **kwargs):
            return {
                "plot": "Some plot.",
                "released": recent_release,
                "runtime": None,
                "director": None,
                "rt_score": None,
                "imdb_rating": None,
                "metascore": None,
                "country": "USA",
                "language": "English",
                "dvd": "N/A",
                "type": "movie",
                "error": None,
            }

        with patch.object(OMDbClient, "fetch", side_effect=_fake_fetch):
            kept, dropped = scanner._apply_theaters_filter(
                db_path=db_path,
                match_rows=[match_row],
                only_in_theaters_allowed=False,
                on_progress=lambda _: None,
            )

        assert dropped == 1, f"Expected 1 drop; got {dropped}"
        reasons = _count_eliminations(db_path, "ttT001")
        assert len(reasons) == 1, (
            f"Expected 1 elimination row for ttT001; got {reasons}"
        )
        assert reasons[0] == "only_in_theaters:filter_dropped", (
            f"Expected 'only_in_theaters:filter_dropped'; got {reasons[0]!r}"
        )


# ══════════════════════════════════════════════════════════════════════════════
# T5 — UI renders Reason column header when show_dismissed=1
# ══════════════════════════════════════════════════════════════════════════════


class TestUIReasonColumnVisible:

    def test_t5_reason_column_header_present_when_show_dismissed(self, tmp_path):
        """T5 — GET /?show_dismissed=1 → response HTML contains 'Reason' column header."""
        ms_app, client, db_path = _make_app(tmp_path)

        # Seed a match (active) so the matches table renders
        conn = sqlite3.connect(db_path)
        conn.execute(
            "INSERT OR IGNORE INTO runs (id, status, phase) VALUES (1, 'done', 'done')"
        )
        conn.execute(
            "INSERT OR IGNORE INTO titles "
            "(tconst, title_type, primary_title, start_year) VALUES ('ttUI001', 'movie', 'Test Movie', 2026)"
        )
        conn.execute(
            "INSERT OR IGNORE INTO matches "
            "(tconst, primary_title, start_year, title_type, rating, num_votes, "
            "genres, matched_tags, run_id) "
            "VALUES ('ttUI001', 'Test Movie', 2026, 'movie', 8.0, 1000, 'Drama', 'drama', 1)"
        )
        conn.commit()
        conn.close()

        resp = client.get("/?show_dismissed=1")
        assert resp.status_code == 200
        html = resp.data.decode("utf-8")
        assert "Reason" in html, (
            "Expected 'Reason' column header in show_dismissed=1 view; not found in HTML"
        )


# ══════════════════════════════════════════════════════════════════════════════
# T6 — UI hides Reason column when show_dismissed=0
# ══════════════════════════════════════════════════════════════════════════════


class TestUIReasonColumnHidden:

    def test_t6_reason_column_header_absent_when_not_show_dismissed(self, tmp_path):
        """T6 — GET / (show_dismissed=0, default) → 'Reason' column header NOT present."""
        ms_app, client, db_path = _make_app(tmp_path)

        # Seed a match so the table renders
        conn = sqlite3.connect(db_path)
        conn.execute(
            "INSERT OR IGNORE INTO runs (id, status, phase) VALUES (1, 'done', 'done')"
        )
        conn.execute(
            "INSERT OR IGNORE INTO titles "
            "(tconst, title_type, primary_title, start_year) VALUES ('ttUI002', 'movie', 'Test Movie 2', 2026)"
        )
        conn.execute(
            "INSERT OR IGNORE INTO matches "
            "(tconst, primary_title, start_year, title_type, rating, num_votes, "
            "genres, matched_tags, run_id) "
            "VALUES ('ttUI002', 'Test Movie 2', 2026, 'movie', 8.0, 1000, 'Drama', 'drama', 1)"
        )
        conn.commit()
        conn.close()

        resp = client.get("/")
        assert resp.status_code == 200
        html = resp.data.decode("utf-8")
        # The "Reason" column th should NOT appear in the default view
        # We check for the column-header TH specifically
        assert '<th' not in html or "Reason</th>" not in html or "show-dismissed" in html, (
            "The Reason column header should not appear in the default (non-dismissed) view"
        )
        # More direct: count occurrences of 'Reason' as a column header
        import re
        reason_headers = re.findall(r'<th[^>]*>[^<]*Reason[^<]*</th>', html)
        assert len(reason_headers) == 0, (
            f"Reason column header should be absent in default view; found: {reason_headers}"
        )


# ══════════════════════════════════════════════════════════════════════════════
# T7 — User-dismissed matches show "dismissed_by_user" in the UI
# ══════════════════════════════════════════════════════════════════════════════


class TestUIUserDismissedReason:

    def test_t7_user_dismissed_shows_reason_in_html(self, tmp_path):
        """T7 — A match the user dismissed shows 'dismissed_by_user' (or equivalent)
        in the Reason column when show_dismissed=1.
        """
        ms_app, client, db_path = _make_app(tmp_path)

        conn = sqlite3.connect(db_path)
        conn.execute(
            "INSERT OR IGNORE INTO runs (id, status, phase) VALUES (1, 'done', 'done')"
        )
        conn.execute(
            "INSERT OR IGNORE INTO titles "
            "(tconst, title_type, primary_title, start_year) VALUES ('ttDIS001', 'movie', 'Dismissed Film', 2026)"
        )
        conn.execute(
            "INSERT OR IGNORE INTO matches "
            "(tconst, primary_title, start_year, title_type, rating, num_votes, "
            "genres, matched_tags, run_id) "
            "VALUES ('ttDIS001', 'Dismissed Film', 2026, 'movie', 8.0, 1000, 'Drama', 'drama', 1)"
        )
        # Dismiss the match
        conn.execute(
            "INSERT OR REPLACE INTO dismissed_tconsts (tconst, dismissed_at) "
            "VALUES ('ttDIS001', strftime('%Y-%m-%dT%H:%M:%SZ','now'))"
        )
        conn.commit()
        conn.close()

        resp = client.get("/?show_dismissed=1")
        assert resp.status_code == 200
        html = resp.data.decode("utf-8")
        assert "dismissed_by_user" in html, (
            "Expected 'dismissed_by_user' to appear in the show_dismissed=1 view "
            "for a user-dismissed match; not found in HTML"
        )


# ══════════════════════════════════════════════════════════════════════════════
# T8 — Active matches show "—" in the Reason column
# ══════════════════════════════════════════════════════════════════════════════


class TestUIActiveMatchesReason:

    def test_t8_active_match_shows_dash_in_reason_column(self, tmp_path):
        """T8 — When show_dismissed=1, active (non-dismissed) matches show '—'
        in the Reason column (or empty — but the column must be present).
        """
        ms_app, client, db_path = _make_app(tmp_path)

        conn = sqlite3.connect(db_path)
        conn.execute(
            "INSERT OR IGNORE INTO runs (id, status, phase) VALUES (1, 'done', 'done')"
        )
        conn.execute(
            "INSERT OR IGNORE INTO titles "
            "(tconst, title_type, primary_title, start_year) VALUES ('ttACT001', 'movie', 'Active Film', 2026)"
        )
        conn.execute(
            "INSERT OR IGNORE INTO matches "
            "(tconst, primary_title, start_year, title_type, rating, num_votes, "
            "genres, matched_tags, run_id) "
            "VALUES ('ttACT001', 'Active Film', 2026, 'movie', 8.5, 5000, 'Drama', 'drama', 1)"
        )
        conn.commit()
        conn.close()

        resp = client.get("/?show_dismissed=1")
        assert resp.status_code == 200
        html = resp.data.decode("utf-8")
        # Active match should show '—' or be empty in the reason cell
        # The table has a Reason column, and active match rows use '—' as the value
        assert "—" in html, (
            "Expected '—' placeholder for active match reason; not found in HTML"
        )


# ══════════════════════════════════════════════════════════════════════════════
# T9 — APP_VERSION is V3.27
# ══════════════════════════════════════════════════════════════════════════════


class TestRegressionV327:

    def test_t9_app_version_is_v3_27(self, tmp_path):
        """T9 — APP_VERSION must be V3.27 after this feature ships."""
        ms_app, client, db_path = _make_app(tmp_path)
        assert ms_app.APP_VERSION == "V3.27", (
            f"Expected V3.27, got {ms_app.APP_VERSION!r}"
        )
