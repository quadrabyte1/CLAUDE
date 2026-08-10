"""test_scan_log.py — regression tests for the scans.log append-only log file.

Covers both the success and error paths of Scanner.scan(): the log file must
exist under data_dir, contain a "Scan run_id=" line, the started/finished
timestamps, the effective genre/rating/vote/title_type config, the counts,
and — on the error path — a "Status: error" block with the exception message.
"""

import gzip
import os
import tempfile

import pytest

from movie_scanner import Scanner, ScanConfig
from movie_scanner import scanner as scanner_module


# ── Fixtures ───────────────────────────────────────────────────────────────

BASICS_HEADER = (
    "tconst\ttitleType\tprimaryTitle\toriginalTitle\tisAdult\t"
    "startYear\tendYear\truntimeMinutes\tgenres\n"
)

# Use a year that is comfortably in the future relative to today so the
# min_year filter (which defaults to the current calendar year) never
# rejects the fixture row simply because the calendar rolled forward.
# The test explicitly overrides min_year in ScanConfig below, but keeping
# the fixture year "future-proof" makes the data self-consistent and
# reduces surprise if the test config ever changes.
_FIXTURE_YEAR = "2099"

# One row that should match (Sci-Fi, high rating/votes), one that should not
# (Horror, excluded), plus a short film that fails the title_type filter.
BASICS_ROWS = [
    # matches: movie, Sci-Fi, in ratings dump with 8.5 / 5000
    f"tt0000001\tmovie\tGood Sci-Fi\tGood Sci-Fi\t0\t{_FIXTURE_YEAR}\t\\N\t120\tSci-Fi,Drama\n",
    # skipped: Horror is in exclude_genres
    f"tt0000002\tmovie\tBad Horror\tBad Horror\t0\t{_FIXTURE_YEAR}\t\\N\t95\tHorror\n",
    # skipped: title_type not in keep list
    f"tt0000003\tshort\tShort Film\tShort Film\t0\t{_FIXTURE_YEAR}\t\\N\t10\tDrama\n",
]

RATINGS_HEADER = "tconst\taverageRating\tnumVotes\n"
RATINGS_ROWS = [
    "tt0000001\t8.5\t5000\n",
    "tt0000002\t7.9\t2000\n",
    "tt0000003\t8.0\t500\n",
]

# V3.13 — title.episode.tsv.gz shape. Empty for these tests (no series in
# the basics fixture), but the file must exist so fetch_dumps can return
# the tuple the scanner destructures.
EPISODES_HEADER = "tconst\tparentTconst\tseasonNumber\tepisodeNumber\n"
EPISODES_ROWS: list[str] = []


def _write_gz(path: str, header: str, rows: list[str]) -> None:
    with gzip.open(path, "wt", encoding="utf-8") as f:
        f.write(header)
        for r in rows:
            f.write(r)


@pytest.fixture
def tmp_paths():
    """Provide (db_path, data_dir) rooted in a fresh TemporaryDirectory."""
    with tempfile.TemporaryDirectory() as td:
        db_path  = os.path.join(td, "scanner.db")
        data_dir = os.path.join(td, "data")
        os.makedirs(data_dir, exist_ok=True)
        yield db_path, data_dir


@pytest.fixture
def fake_fetch_dumps(tmp_paths, monkeypatch):
    """Monkeypatch fetch_dumps to return three tiny gzip TSVs in data_dir.

    V3.13 — fetch_dumps returns a 3-tuple (basics, ratings, episodes) so
    the scanner can build the per-season air-year cache. The episodes
    file is empty for the log-format tests (no series in the fixture),
    but must exist so the scanner's second-pass streamer opens cleanly.
    """
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

def test_scan_log_written_on_success(tmp_paths, fake_fetch_dumps):
    """Success path: scans.log exists in data_dir and contains all expected fields."""
    db_path, data_dir = tmp_paths
    cfg = ScanConfig(
        min_rating=7.5,
        min_votes=500,
        min_year=0,   # disable year filter so the fixture year is irrelevant
        include_genres=["Sci-Fi", "Drama"],
        exclude_genres=["Horror"],
        title_types=["movie", "tvMovie", "tvSeries"],
    )
    sc = Scanner(db_path=db_path, data_dir=data_dir, config=cfg)
    summary = sc.scan()

    log_path = os.path.join(data_dir, "scans.log")
    assert os.path.exists(log_path), "scans.log was not created in data_dir"

    with open(log_path, "r", encoding="utf-8") as f:
        contents = f.read()

    # Structural markers
    assert "Scan run_id=" in contents
    assert f"run_id={summary['run_id']}" in contents
    assert "Status: done" in contents

    # Timestamps — ISO 8601 UTC "Z" suffix
    assert contents.count("Z") >= 2, "expected started/finished ISO timestamps ending in Z"

    # Config lines
    assert "min_rating" in contents and "7.5" in contents
    assert "min_votes"  in contents and "500" in contents
    assert "title_types" in contents
    assert "movie" in contents and "tvSeries" in contents
    assert "include_genres" in contents
    assert "Sci-Fi" in contents and "Drama" in contents
    assert "exclude_genres" in contents
    assert "Horror" in contents

    # Counts — should have Scanned / New titles / Matches
    assert "Scanned:" in contents
    assert "New titles:" in contents
    assert "Matches:" in contents
    # Our synthetic dataset yields exactly 1 match (tt0000001)
    assert summary["matches"] == 1


def test_scan_log_written_on_error(tmp_paths, fake_fetch_dumps, monkeypatch):
    """Error path: an exception in scan() still writes a log entry with Status: error."""
    db_path, data_dir = tmp_paths
    cfg = ScanConfig(
        min_rating=7.5,
        min_votes=500,
        include_genres=["Sci-Fi"],
        exclude_genres=["Horror"],
    )

    # Force _load_ratings to explode — mirrors a real-world dump-parse failure.
    boom = "kaboom: ratings dump is corrupt"

    def _explode(_path):
        raise RuntimeError(boom)

    monkeypatch.setattr(scanner_module, "_load_ratings", _explode)

    sc = Scanner(db_path=db_path, data_dir=data_dir, config=cfg)
    with pytest.raises(RuntimeError):
        sc.scan()

    log_path = os.path.join(data_dir, "scans.log")
    assert os.path.exists(log_path), "scans.log was not created on error path"

    with open(log_path, "r", encoding="utf-8") as f:
        contents = f.read()

    assert "Scan run_id=" in contents
    assert "Status: error" in contents
    assert boom in contents, "exception message should be recorded in the log"
    # Config still recorded even on failure
    assert "Sci-Fi" in contents
    assert "Horror" in contents


def test_scan_log_appends_across_runs(tmp_paths, fake_fetch_dumps):
    """Two successive scans should produce two log blocks, not overwrite."""
    db_path, data_dir = tmp_paths
    cfg = ScanConfig(
        min_rating=7.5, min_votes=500, min_year=0,
        include_genres=["Sci-Fi"], exclude_genres=["Horror"],
    )
    sc = Scanner(db_path=db_path, data_dir=data_dir, config=cfg)
    sc.scan()
    sc.scan()

    log_path = os.path.join(data_dir, "scans.log")
    with open(log_path, "r", encoding="utf-8") as f:
        contents = f.read()

    # Two "Scan run_id=" headers means we appended, not overwrote.
    assert contents.count("Scan run_id=") == 2
