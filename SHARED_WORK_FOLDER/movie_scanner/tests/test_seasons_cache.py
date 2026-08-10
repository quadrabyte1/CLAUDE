"""test_seasons_cache.py — regression tests for the V3.19 seasons cache.

Bug context (Thomas, 2026-08-10):
    A scan (run #4) appeared to hang on ``phase='seasons'`` — long enough
    that Thomas asked for a cancel button. Diagnosis (Sienna, same day):
    the phase isn't hung; it's ~15 s of silent local file+SQLite work
    (loading 8.5 M tvEpisode air years, streaming 7.8 M episode rows,
    writing 375 K series_seasons rows). No IMDB HTTP calls — Thomas's
    "repeated fetches from IMDB" hypothesis was refuted by the code path
    (there are literally zero requests.get() / urllib calls in the seasons
    phase; it's all local .tsv.gz + SQLite).

V3.19 fix:
    1. Cache-key short-circuit — on scan #2+ with unchanged .last_modified
       sidecars, skip the entire rebuild. Series_seasons stays valid
       because the aggregation is a pure function of basics + episodes.
    2. Heartbeat progress every 2 M scanned rows so the (rare) rebuild
       path doesn't look hung.

Tests below lock in the correctness + perf gains:
    A. Fresh DB rebuilds and populates series_seasons + writes cache_key.
    B. Second scan with unchanged dumps hits the cache and DOES NOT
       re-scan basics/episodes (verified via a monkeypatch counter).
    C. Second scan after a dump CHANGES rebuilds correctly.
    D. Aggregation math is right (MIN(startYear) per season, correct
       episode_count).
"""

import gzip
import os
import sqlite3
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
    # One series that will pass min_year=2026 so we exercise the season
    # sub-list branch too.
    "tt2000010\ttvSeries\tExample Series\tExample Series\t0\t2026\t\\N\t45\tDrama\n",
    # Old series with a mix of season air years — used for aggregation math
    "tt2000011\ttvSeries\tOld Show\tOld Show\t0\t1998\t\\N\t45\tDrama\n",
    # Episodes for aggregation math (MIN startYear per season)
    "tt9100001\ttvEpisode\tS1E1\tS1E1\t0\t2020\t\\N\t45\tDrama\n",
    "tt9100002\ttvEpisode\tS1E2\tS1E2\t0\t2019\t\\N\t45\tDrama\n",  # earlier
    "tt9100003\ttvEpisode\tS1E3\tS1E3\t0\t2021\t\\N\t45\tDrama\n",
    "tt9100004\ttvEpisode\tS2E1\tS2E1\t0\t2022\t\\N\t45\tDrama\n",
    "tt9100005\ttvEpisode\tS2E2\tS2E2\t0\t\\N\t\\N\t45\tDrama\n",  # unknown
    "tt9100010\ttvEpisode\tNewShowEp\tNewShowEp\t0\t2026\t\\N\t45\tDrama\n",
]

RATINGS_HEADER = "tconst\taverageRating\tnumVotes\n"
RATINGS_ROWS = [
    "tt2000010\t9.0\t10000\n",
    "tt2000011\t9.0\t10000\n",
]

EPISODES_HEADER = "tconst\tparentTconst\tseasonNumber\tepisodeNumber\n"
EPISODES_ROWS = [
    # tt2000011 (Old Show): 2 seasons, mixed years
    "tt9100001\ttt2000011\t1\t1\n",  # 2020
    "tt9100002\ttt2000011\t1\t2\n",  # 2019 (MIN of season 1)
    "tt9100003\ttt2000011\t1\t3\n",  # 2021
    "tt9100004\ttt2000011\t2\t1\n",  # 2022 (MIN of season 2 — only known)
    "tt9100005\ttt2000011\t2\t2\n",  # \N (ignored for MIN)
    # tt2000010 (Example Series): 1 season, 1 episode 2026
    "tt9100010\ttt2000010\t1\t1\n",
]


def _write_gz(path: str, header: str, rows: list[str]) -> None:
    with gzip.open(path, "wt", encoding="utf-8") as f:
        f.write(header)
        for r in rows:
            f.write(r)


@pytest.fixture
def tmp_paths():
    with tempfile.TemporaryDirectory() as td:
        db_path = os.path.join(td, "scanner.db")
        data_dir = os.path.join(td, "data")
        os.makedirs(data_dir, exist_ok=True)
        yield db_path, data_dir


def _write_dumps(data_dir: str) -> tuple[str, str, str]:
    basics_path = os.path.join(data_dir, "title.basics.tsv.gz")
    ratings_path = os.path.join(data_dir, "title.ratings.tsv.gz")
    episodes_path = os.path.join(data_dir, "title.episode.tsv.gz")
    _write_gz(basics_path, BASICS_HEADER, BASICS_ROWS)
    _write_gz(ratings_path, RATINGS_HEADER, RATINGS_ROWS)
    _write_gz(episodes_path, EPISODES_HEADER, EPISODES_ROWS)
    # Simulate the downloader's .last_modified sidecars — these are the
    # cache key inputs. Fresh dumps → identical sidecar strings on the
    # second scan → cache hit.
    for p in (basics_path, ratings_path, episodes_path):
        with open(p + ".last_modified", "w", encoding="utf-8") as f:
            f.write("Mon, 10 Aug 2026 00:00:00 GMT")
    return basics_path, ratings_path, episodes_path


@pytest.fixture
def fake_fetch_dumps(tmp_paths, monkeypatch):
    _, data_dir = tmp_paths
    paths = _write_dumps(data_dir)

    def _fake(_data_dir, _on_progress):
        return paths

    monkeypatch.setattr(scanner_module, "fetch_dumps", _fake)
    return paths


def _run(db_path: str, data_dir: str) -> list[str]:
    """Run one scan with permissive filters. Returns collected progress msgs."""
    cfg = ScanConfig(
        min_rating=0.0, min_votes=0, min_year=2026,
        include_genres=[], exclude_genres=[],
        title_types=["movie", "tvMovie", "tvSeries", "tvMiniSeries"],
    )
    msgs: list[str] = []
    Scanner(db_path=db_path, data_dir=data_dir, config=cfg).scan(
        on_progress=msgs.append
    )
    return msgs


def _series_seasons(db_path: str) -> list[tuple]:
    with sqlite3.connect(db_path) as conn:
        return sorted(conn.execute(
            "SELECT parent_tconst, season_number, air_year, episode_count "
            "FROM series_seasons"
        ).fetchall())


# ── Tests ──────────────────────────────────────────────────────────────────

def test_seasons_cache_populated_and_correct_on_first_scan(
    tmp_paths, fake_fetch_dumps,
):
    """First scan must populate series_seasons + record the cache key."""
    db_path, data_dir = tmp_paths
    _run(db_path, data_dir)

    rows = _series_seasons(db_path)
    # Old Show: S1 min=2019 (3 eps), S2 min=2022 (2 eps, 1 unknown ignored)
    # Example Series: S1 min=2026 (1 ep)
    assert rows == [
        ("tt2000010", 1, 2026, 1),
        ("tt2000011", 1, 2019, 3),
        ("tt2000011", 2, 2022, 2),
    ], f"aggregation math wrong: {rows}"

    with sqlite3.connect(db_path) as conn:
        cached = conn.execute(
            "SELECT value FROM config WHERE key='seasons_cache_key'"
        ).fetchone()
    assert cached is not None, "cache key not persisted after first scan"
    assert "basics:" in cached[0] and "episodes:" in cached[0]


def test_second_scan_hits_cache_and_skips_rebuild(
    tmp_paths, fake_fetch_dumps, monkeypatch,
):
    """The whole point of V3.19: when dumps are unchanged, scan #2 must
    NOT re-run ``_load_episode_years`` — the 8.5 M-row streaming pass
    was the visible symptom Thomas hit as "hangs on seasons phase"."""
    db_path, data_dir = tmp_paths
    _run(db_path, data_dir)  # populate

    # Now instrument: count calls to _load_episode_years on scan #2.
    call_count = {"n": 0}
    real = scanner_module._load_episode_years

    def counting(path, on_progress=None):
        call_count["n"] += 1
        return real(path, on_progress=on_progress)

    monkeypatch.setattr(scanner_module, "_load_episode_years", counting)

    msgs = _run(db_path, data_dir)

    assert call_count["n"] == 0, (
        "seasons cache MISS — _load_episode_years was called on scan #2 "
        "despite unchanged .last_modified sidecars. This is the V3.19 "
        "regression: repeat scans must short-circuit the 15 s rebuild."
    )
    assert any("cache hit" in m for m in msgs), (
        f"expected 'cache hit' progress message, got: {msgs}"
    )

    # Series_seasons rows must still be intact (cache reuse is correct).
    assert _series_seasons(db_path) == [
        ("tt2000010", 1, 2026, 1),
        ("tt2000011", 1, 2019, 3),
        ("tt2000011", 2, 2022, 2),
    ]


def test_cache_miss_when_episode_dump_changes(
    tmp_paths, fake_fetch_dumps, monkeypatch,
):
    """If the episode dump's .last_modified changes, we MUST rebuild —
    otherwise stale season data would silently leak into filter decisions."""
    db_path, data_dir = tmp_paths
    _run(db_path, data_dir)  # populate cache

    # Mutate the episode sidecar as if a fresh dump landed.
    ep_lm = os.path.join(data_dir, "title.episode.tsv.gz.last_modified")
    with open(ep_lm, "w", encoding="utf-8") as f:
        f.write("Tue, 11 Aug 2026 00:00:00 GMT")

    call_count = {"n": 0}
    real = scanner_module._load_episode_years

    def counting(path, on_progress=None):
        call_count["n"] += 1
        return real(path, on_progress=on_progress)

    monkeypatch.setattr(scanner_module, "_load_episode_years", counting)

    _run(db_path, data_dir)

    assert call_count["n"] == 1, (
        "cache should have MISSED (episode sidecar changed) but the "
        "rebuild was skipped — this would let stale season data leak."
    )


def test_cache_miss_when_no_prior_key(tmp_paths, fake_fetch_dumps, monkeypatch):
    """First scan on a DB that was populated by an older version (no
    ``seasons_cache_key`` row) must trigger a rebuild — not a false hit."""
    db_path, data_dir = tmp_paths
    _run(db_path, data_dir)  # populate

    # Simulate an old DB by DELETING the cache key row (leaving the
    # series_seasons rows in place).
    with sqlite3.connect(db_path) as conn:
        conn.execute("DELETE FROM config WHERE key='seasons_cache_key'")
        conn.commit()

    call_count = {"n": 0}
    real = scanner_module._load_episode_years

    def counting(path, on_progress=None):
        call_count["n"] += 1
        return real(path, on_progress=on_progress)

    monkeypatch.setattr(scanner_module, "_load_episode_years", counting)

    _run(db_path, data_dir)

    assert call_count["n"] == 1, (
        "no prior cache key = must rebuild (fail-safe: never trust "
        "existing series_seasons rows without a matching key)"
    )
