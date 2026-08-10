"""test_min_year_filter.py — regression tests for the V3.13 min_year filter.

Bug report (Thomas, 2026-08-10, MovieScanner V3.16):
    "Movie scanner is not paying attention to the minimum year value. So a
    bunch of things are making it into the match list that are older than
    the minimum year."

Live DB config at time of bug:  min_year=2026, min_rating=7.5,
                                min_votes=100, tags=["Drama"].

V3.13 semantics we expect to hold:
    * movie / tvMovie / short → classic gate: startYear >= min_year.
    * tvSeries / tvMiniSeries → passes if ANY season has air_year >= min_year.
      When the series has NO episodes at all (nothing in title.episode.tsv.gz
      for that parent_tconst), the per-season lookup returns nothing and we
      MUST fall back to a strict startYear check — otherwise brand-new series
      whose episodes haven't been indexed yet would silently drop, AND old
      series with no episode file coverage would silently drop too.

Four cases covered here:
    A. movie, startYear=1995     → must NOT match (old)
    B. movie, startYear=2026     → MUST match
    C. tvSeries, startYear=1998, all seasons air_year < 2026 → must NOT match
    D. tvSeries, startYear=1998, one season air_year=2026    → MUST match
    E. tvSeries, startYear=1998, NO episodes in episode file → must NOT match
       (fall back to startYear >= min_year; series is 1998, gate is 2026)
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

# Case A: old movie — must NOT match
# Case B: current-year movie — MUST match
# Case C: old series with all-old seasons — must NOT match
# Case D: old series with one new season — MUST match
# Case E: old series with NO episodes — must NOT match (fallback to startYear)
BASICS_ROWS = [
    "tt1000001\tmovie\tOld Movie\tOld Movie\t0\t1995\t\\N\t120\tDrama\n",
    "tt1000002\tmovie\tNew Movie\tNew Movie\t0\t2026\t\\N\t120\tDrama\n",
    "tt2000001\ttvSeries\tOld Series\tOld Series\t0\t1998\t\\N\t45\tDrama\n",
    "tt2000002\ttvSeries\tOld Series w New Season\tOld Series w New Season\t0\t1998\t\\N\t45\tDrama\n",
    "tt2000003\ttvSeries\tGhost Series\tGhost Series\t0\t1998\t\\N\t45\tDrama\n",
    # Case F: series with startYear = \N and NO episodes — must NOT match
    "tt2000004\ttvSeries\tYearless Ghost\tYearless Ghost\t0\t\\N\t\\N\t45\tDrama\n",
    # Case G: series with startYear = \N but a season with air_year=2026 — MUST match
    "tt2000005\ttvSeries\tYearless Recent\tYearless Recent\t0\t\\N\t\\N\t45\tDrama\n",
    # Case H: series with startYear=1998, seasons exist but all air_year is \N
    # (episodes present but every episode's startYear is \N). Must NOT match.
    "tt2000006\ttvSeries\tSilent Seasons\tSilent Seasons\t0\t1998\t\\N\t45\tDrama\n",
    # Episode rows — needed so _load_episode_years can attach startYear per
    # episode; _iter_basics filters these out for the main match loop.
    "tt9000001\ttvEpisode\tOld Ep\tOld Ep\t0\t1999\t\\N\t45\tDrama\n",
    "tt9000002\ttvEpisode\tOld Ep 2\tOld Ep 2\t0\t2000\t\\N\t45\tDrama\n",
    "tt9000010\ttvEpisode\tRevival Ep\tRevival Ep\t0\t2026\t\\N\t45\tDrama\n",
    # Yearless-recent series (tt2000005): one episode with year=2026
    "tt9000020\ttvEpisode\tYearless Recent Ep\tYearless Recent Ep\t0\t2026\t\\N\t45\tDrama\n",
    # Silent-seasons series (tt2000006): two episodes but startYear = \N on both
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
]

EPISODES_HEADER = "tconst\tparentTconst\tseasonNumber\tepisodeNumber\n"
# tt2000001 (Old Series): one season, all episodes 1999/2000 (old)
# tt2000002 (Old Series w New Season): one old season + one 2026 season
# tt2000003 (Ghost Series): NO episode rows at all
EPISODES_ROWS = [
    "tt9000001\ttt2000001\t1\t1\n",
    "tt9000002\ttt2000001\t1\t2\n",
    "tt9000001\ttt2000002\t1\t1\n",   # season 1 (1999) — old
    "tt9000010\ttt2000002\t2\t1\n",   # season 2 (2026) — qualifies
    # Yearless-recent series (startYear=\N) with a 2026 season → qualifies
    "tt9000020\ttt2000005\t1\t1\n",
    # Silent-seasons series (startYear=1998) with two \N episodes → seasons
    # exist in series_seasons but with air_year=NULL; must NOT match.
    "tt9000030\ttt2000006\t1\t1\n",
    "tt9000031\ttt2000006\t1\t2\n",
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


def test_min_year_filter_all_cases(tmp_paths, fake_fetch_dumps):
    """The V3.13 min_year filter must reject old movies AND old series that
    have no qualifying season, while allowing current-year movies and series
    with a season that airs at or after min_year."""
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

    # MUST match — current-year movie, series with a 2026 season,
    # yearless series with a 2026 episode
    assert "tt1000002" in matched, "New Movie (2026) should match"
    assert "tt2000002" in matched, "Old Series with 2026 season should match"
    assert "tt2000005" in matched, (
        "Yearless-startYear series with a 2026 season should still match "
        "on the per-season branch"
    )

    # Must NOT match — old titles + ghost series that fell back to startYear
    assert "tt1000001" not in matched, "Old Movie (1995) leaked past min_year filter"
    assert "tt2000001" not in matched, "Old Series (all seasons 1999/2000) leaked"
    assert "tt2000003" not in matched, (
        "Ghost Series (no episode rows) should fall back to startYear=1998 "
        "and be rejected by min_year=2026, but it leaked into matches"
    )
    assert "tt2000004" not in matched, (
        "Yearless Ghost Series (no episodes, startYear=\\N) has no evidence "
        "of a recent air year and must NOT leak past min_year"
    )
    assert "tt2000006" not in matched, (
        "Silent-Seasons Series (episodes present but every episode's "
        "startYear=\\N) has NO qualifying season air_year and must NOT match"
    )

    # Sanity — exactly the three intended matches, no more, no less
    expected = {"tt1000002", "tt2000002", "tt2000005"}
    assert matched == expected, f"expected exactly {expected} matches, got {matched}"
    assert summary["matches"] == 3
