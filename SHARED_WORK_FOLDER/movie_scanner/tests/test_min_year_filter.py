"""test_min_year_filter.py — regression tests for the min_year filter.

Bug report (Thomas, 2026-08-10, MovieScanner V3.16):
    A scan with min_year=2026 returned 355 matches; 191 were long-running
    tvSeries with startYear as far back as 1950 (Formula 1), 1971 (Great
    Performances), 1990 (Law & Order). Each leaker had at least one season
    with air_year=2026. V3.13's "series matches if ANY season has
    air_year >= min_year" rule worked as specified but produced results
    Thomas did not want.

Product decision (2026-08-10, Option A "strict"):
    A tvSeries must have ``start_year >= min_year`` — same rule as movies.
    V3.13's per-season year-filter branch is REVERTED.

Live DB config at time of bug:  min_year=2026, min_rating=7.5,
                                min_votes=100, tags=["Drama"].

V3.17 semantics we lock in here (STRICT, same rule for everything):
    * movie / tvMovie / short / tvSeries / tvMiniSeries → startYear >= min_year.
    * The season sub-list (``series_seasons`` + ``match_seasons``) is still
      populated for series that PASS the start_year check, so the UI can
      still show ``▼ N season matches (…)`` when relevant. Only the match
      DECISION changes here.

Cases covered:
    A. movie, startYear=1995     → must NOT match (old)
    B. movie, startYear=2026     → MUST match
    C. tvSeries, startYear=1998, all seasons air_year < 2026 → must NOT match
    D. tvSeries, startYear=1998, one season air_year=2026    → **must NOT match**
       (this is the case that flipped in V3.17 — the whole bug)
    E. tvSeries, startYear=1998, NO episodes in episode file → must NOT match
    F. tvSeries, startYear=\\N, no episodes                  → must NOT match
    G. tvSeries, startYear=\\N, one season air_year=2026     → must NOT match
       (no start_year = no evidence the *series* started at/after min_year)
    H. tvSeries, startYear=1998, episodes present but every
       episode's startYear=\\N                                → must NOT match
    I. tvSeries, startYear=2026, regardless of season data   → MUST match
"""

import gzip
import os
import tempfile

import pytest

from movie_scanner import Scanner, ScanConfig
from movie_scanner import scanner as scanner_module


# ── Fixture data ───────────────────────────────────────────────────────────

BASICS_HEADER = (
    "tconst\ttitleType\tprimaryTitle\toriginalTitle\tisAdult\t"
    "startYear\tendYear\truntimeMinutes\tgenres\n"
)

BASICS_ROWS = [
    # A: old movie — must NOT match
    "tt1000001\tmovie\tOld Movie\tOld Movie\t0\t1995\t\\N\t120\tDrama\n",
    # B: current-year movie — MUST match
    "tt1000002\tmovie\tNew Movie\tNew Movie\t0\t2026\t\\N\t120\tDrama\n",
    # C: old series, all-old seasons — must NOT match
    "tt2000001\ttvSeries\tOld Series\tOld Series\t0\t1998\t\\N\t45\tDrama\n",
    # D: old series with a 2026 revival season — must NOT match (V3.17 flip)
    "tt2000002\ttvSeries\tOld Series w New Season\tOld Series w New Season\t0\t1998\t\\N\t45\tDrama\n",
    # E: old series, ghost (no episodes) — must NOT match
    "tt2000003\ttvSeries\tGhost Series\tGhost Series\t0\t1998\t\\N\t45\tDrama\n",
    # F: yearless series, no episodes — must NOT match
    "tt2000004\ttvSeries\tYearless Ghost\tYearless Ghost\t0\t\\N\t\\N\t45\tDrama\n",
    # G: yearless series with 2026 season — must NOT match (no series startYear)
    "tt2000005\ttvSeries\tYearless Recent\tYearless Recent\t0\t\\N\t\\N\t45\tDrama\n",
    # H: old series w/ silent seasons (episode startYear=\N) — must NOT match
    "tt2000006\ttvSeries\tSilent Seasons\tSilent Seasons\t0\t1998\t\\N\t45\tDrama\n",
    # I: current-year series — MUST match regardless of season data
    "tt2000007\ttvSeries\tNew Series\tNew Series\t0\t2026\t\\N\t45\tDrama\n",
    # Episode rows for the series above
    "tt9000001\ttvEpisode\tOld Ep\tOld Ep\t0\t1999\t\\N\t45\tDrama\n",
    "tt9000002\ttvEpisode\tOld Ep 2\tOld Ep 2\t0\t2000\t\\N\t45\tDrama\n",
    "tt9000010\ttvEpisode\tRevival Ep\tRevival Ep\t0\t2026\t\\N\t45\tDrama\n",
    "tt9000020\ttvEpisode\tYearless Recent Ep\tYearless Recent Ep\t0\t2026\t\\N\t45\tDrama\n",
    "tt9000030\ttvEpisode\tSilent Ep A\tSilent Ep A\t0\t\\N\t\\N\t45\tDrama\n",
    "tt9000031\ttvEpisode\tSilent Ep B\tSilent Ep B\t0\t\\N\t\\N\t45\tDrama\n",
]

RATINGS_HEADER = "tconst\taverageRating\tnumVotes\n"
# All above rating/vote thresholds so ONLY the year filter decides matches.
RATINGS_ROWS = [
    "tt1000001\t9.0\t10000\n",
    "tt1000002\t9.0\t10000\n",
    "tt2000001\t9.0\t10000\n",
    "tt2000002\t9.0\t10000\n",
    "tt2000003\t9.0\t10000\n",
    "tt2000004\t9.0\t10000\n",
    "tt2000005\t9.0\t10000\n",
    "tt2000006\t9.0\t10000\n",
    "tt2000007\t9.0\t10000\n",
]

EPISODES_HEADER = "tconst\tparentTconst\tseasonNumber\tepisodeNumber\n"
EPISODES_ROWS = [
    # tt2000001 (Old Series): one season, all episodes 1999/2000 (old)
    "tt9000001\ttt2000001\t1\t1\n",
    "tt9000002\ttt2000001\t1\t2\n",
    # tt2000002 (Old Series w New Season): S1 old, S2 2026
    "tt9000001\ttt2000002\t1\t1\n",
    "tt9000010\ttt2000002\t2\t1\n",
    # tt2000005 (yearless w/ 2026 season)
    "tt9000020\ttt2000005\t1\t1\n",
    # tt2000006 (silent seasons)
    "tt9000030\ttt2000006\t1\t1\n",
    "tt9000031\ttt2000006\t1\t2\n",
    # tt2000007 (new series): a real 2026 season so we can also verify the
    # season sub-list still populates for series that pass the gate.
    "tt9000010\ttt2000007\t1\t1\n",
]


def _write_gz(path: str, header: str, rows: list[str]) -> None:
    with gzip.open(path, "wt", encoding="utf-8") as f:
        f.write(header)
        for r in rows:
            f.write(r)


@pytest.fixture
def tmp_paths():
    with tempfile.TemporaryDirectory() as td:
        db_path  = os.path.join(td, "scanner.db")
        data_dir = os.path.join(td, "data")
        os.makedirs(data_dir, exist_ok=True)
        yield db_path, data_dir


@pytest.fixture
def fake_fetch_dumps(tmp_paths, monkeypatch):
    _, data_dir = tmp_paths
    basics_path   = os.path.join(data_dir, "title.basics.tsv.gz")
    ratings_path  = os.path.join(data_dir, "title.ratings.tsv.gz")
    episodes_path = os.path.join(data_dir, "title.episode.tsv.gz")
    _write_gz(basics_path,   BASICS_HEADER,   BASICS_ROWS)
    _write_gz(ratings_path,  RATINGS_HEADER,  RATINGS_ROWS)
    _write_gz(episodes_path, EPISODES_HEADER, EPISODES_ROWS)

    def _fake(_data_dir, _on_progress):
        return basics_path, ratings_path, episodes_path

    monkeypatch.setattr(scanner_module, "fetch_dumps", _fake)
    return basics_path, ratings_path, episodes_path


# ── Tests ──────────────────────────────────────────────────────────────────

def _matched_tconsts(db_path: str) -> set[str]:
    import sqlite3
    with sqlite3.connect(db_path) as conn:
        return {r[0] for r in conn.execute("SELECT tconst FROM matches")}


def test_min_year_filter_strict_all_cases(tmp_paths, fake_fetch_dumps):
    """V3.17 strict semantics: series must have ``start_year >= min_year``,
    same rule as movies. A recent season alone is NOT enough — this was the
    bug that let Formula 1 (1950), Great Performances (1971), and Law &
    Order (1990) leak into a min_year=2026 scan."""
    db_path, data_dir = tmp_paths
    cfg = ScanConfig(
        min_rating=0.0,
        min_votes=0,
        min_year=2026,
        include_genres=[],          # permissive — no include filter
        exclude_genres=[],
        title_types=["movie", "tvMovie", "tvSeries", "tvMiniSeries"],
    )
    sc = Scanner(db_path=db_path, data_dir=data_dir, config=cfg)
    summary = sc.scan()

    matched = _matched_tconsts(db_path)

    # MUST match — current-year movie and current-year series only
    assert "tt1000002" in matched, "New Movie (2026) should match"
    assert "tt2000007" in matched, "New Series (startYear=2026) should match"

    # Must NOT match — every old title, regardless of season data
    assert "tt1000001" not in matched, "Old Movie (1995) leaked past min_year filter"
    assert "tt2000001" not in matched, "Old Series (all seasons 1999/2000) leaked"
    assert "tt2000002" not in matched, (
        "Old Series (startYear=1998) with a 2026 season MUST NOT match under "
        "V3.17 strict semantics — this is the exact bug (Law & Order pattern)"
    )
    assert "tt2000003" not in matched, "Ghost Series (startYear=1998, no episodes) leaked"
    assert "tt2000004" not in matched, "Yearless Ghost (no episodes, startYear=\\N) leaked"
    assert "tt2000005" not in matched, (
        "Yearless-startYear series with a 2026 season MUST NOT match — "
        "no start_year means no evidence the SERIES started at/after min_year"
    )
    assert "tt2000006" not in matched, "Silent-Seasons Series leaked"

    # Sanity — exactly the two intended matches, no more, no less
    expected = {"tt1000002", "tt2000007"}
    assert matched == expected, f"expected exactly {expected} matches, got {matched}"
    assert summary["matches"] == 2


def test_season_sublist_still_populated_for_passing_series(tmp_paths, fake_fetch_dumps):
    """V3.17 keeps the season sub-list display for series that DO pass the
    start_year gate. The UI shows ▼ N season matches (…) inline — the data
    behind that display must still be written to match_seasons."""
    import sqlite3
    db_path, data_dir = tmp_paths
    cfg = ScanConfig(
        min_rating=0.0,
        min_votes=0,
        min_year=2026,
        include_genres=[],
        exclude_genres=[],
        title_types=["movie", "tvMovie", "tvSeries", "tvMiniSeries"],
    )
    Scanner(db_path=db_path, data_dir=data_dir, config=cfg).scan()

    with sqlite3.connect(db_path) as conn:
        conn.row_factory = sqlite3.Row
        row = conn.execute(
            "SELECT ms.season_number, ms.air_year, ms.episode_count "
            "FROM match_seasons ms "
            "JOIN matches m ON m.id = ms.match_id "
            "WHERE m.tconst = 'tt2000007' "
            "ORDER BY ms.season_number"
        ).fetchall()

    assert len(row) >= 1, (
        "series tt2000007 passed the start_year gate and has a 2026 season "
        "in the episodes fixture — match_seasons should have at least one row"
    )
    assert row[0]["air_year"] == 2026, (
        f"expected season air_year=2026 for tt2000007, got {row[0]['air_year']}"
    )
