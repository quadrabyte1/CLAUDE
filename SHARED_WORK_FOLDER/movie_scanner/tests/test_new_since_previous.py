"""test_new_since_previous.py — V3.21 regression tests.

Locks in the "NEW since last scan" affordance in the Matches table.

Behaviour under test:

    1. First-ever scan (no previous_match_tconsts snapshot): NO row is
       flagged as new. The pill must not appear.

    2. After a scan produces matches and a fresh /run wipes them, the
       outgoing tconst set is snapshotted into previous_match_tconsts.
       The next scan's rows are diffed against that snapshot:

         - tconst present in snapshot AND in current matches → not new.
         - tconst absent from snapshot but present in current → NEW pill.
         - tconst present in snapshot but absent from current → just
           doesn't appear (nothing to flag).

    3. /clear wipes the snapshot too, so the very next scan starts clean
       (no rows flagged as new).

SAFETY: Every test sets MOVIESCANNER_DB_PATH to a per-test tempfile
BEFORE importing app, so the live scanner.db is never touched.
"""

import os
import sqlite3
import sys
import tempfile

import pytest


# ── Test harness (mirrors test_app_cancel_and_status.py) ──────────────────

@pytest.fixture
def app_client(monkeypatch):
    """Fresh Flask test_client backed by a per-test temp DB."""
    fd, db_path = tempfile.mkstemp(suffix=".db", prefix="movscan_test_")
    os.close(fd)
    monkeypatch.setenv("MOVIESCANNER_DB_PATH", db_path)

    _REPO_ROOT = os.path.dirname(
        os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    )
    ms_dir = os.path.join(_REPO_ROOT, "MovieScanner")
    if ms_dir not in sys.path:
        sys.path.insert(0, ms_dir)
    if "app" in sys.modules:
        del sys.modules["app"]
    import app as app_module  # noqa: E402

    app_module.app.config["TESTING"] = True
    client = app_module.app.test_client()

    yield app_module, client, db_path

    if "app" in sys.modules:
        del sys.modules["app"]
    try:
        os.unlink(db_path)
    except FileNotFoundError:
        pass


def _insert_run(db_path: str, status: str = "done") -> int:
    conn = sqlite3.connect(db_path)
    cur = conn.execute(
        "INSERT INTO runs (status, phase) VALUES (?, 'test')",
        (status,),
    )
    conn.commit()
    run_id = cur.lastrowid
    conn.close()
    return run_id


def _insert_match(
    db_path: str, run_id: int, tconst: str, title: str = "Test Title"
) -> None:
    conn = sqlite3.connect(db_path)
    # titles row is required by matches.tconst → titles.tconst FK.
    conn.execute(
        "INSERT OR IGNORE INTO titles (tconst, title_type, primary_title, start_year) "
        "VALUES (?, 'movie', ?, 2026)",
        (tconst, title),
    )
    conn.execute(
        "INSERT INTO matches (tconst, primary_title, start_year, title_type, "
        "rating, num_votes, genres, matched_tags, run_id) "
        "VALUES (?, ?, 2026, 'movie', 8.0, 500, 'Drama', 'drama', ?)",
        (tconst, title, run_id),
    )
    conn.commit()
    conn.close()


def _snapshot_previous(db_path: str, tconsts: list[str]) -> None:
    """Populate previous_match_tconsts directly (simulates the state left
    behind by a prior /run's snapshot step)."""
    conn = sqlite3.connect(db_path)
    conn.execute("DELETE FROM previous_match_tconsts")
    conn.executemany(
        "INSERT INTO previous_match_tconsts (tconst) VALUES (?)",
        [(t,) for t in tconsts],
    )
    conn.commit()
    conn.close()


# ── Case 1: first-ever scan — nothing flagged ─────────────────────────────

def test_first_scan_flags_nothing_as_new(app_client):
    """When previous_match_tconsts is empty (first scan / post-clear),
    the NEW pill must not appear on any row, even if there are matches."""
    app_module, client, db_path = app_client

    run_id = _insert_run(db_path)
    _insert_match(db_path, run_id, "tt0000001", "First Movie")
    _insert_match(db_path, run_id, "tt0000002", "Second Movie")
    # previous_match_tconsts left empty on purpose

    resp = client.get("/")
    assert resp.status_code == 200
    html = resp.data.decode("utf-8")
    assert "First Movie" in html
    assert "Second Movie" in html
    # No NEW pill anywhere — no baseline to compare against.
    assert 'class="new-pill"' not in html


# ── Case 2: repeat scan, no changes — nothing flagged ─────────────────────

def test_repeat_scan_no_changes_flags_nothing(app_client):
    """If every current-run tconst was in the previous run's snapshot,
    no rows are flagged as new."""
    app_module, client, db_path = app_client

    run_id = _insert_run(db_path)
    _insert_match(db_path, run_id, "tt1000001", "Stable One")
    _insert_match(db_path, run_id, "tt1000002", "Stable Two")
    _snapshot_previous(db_path, ["tt1000001", "tt1000002"])

    resp = client.get("/")
    html = resp.data.decode("utf-8")
    assert "Stable One" in html
    assert "Stable Two" in html
    assert 'class="new-pill"' not in html


# ── Case 3: repeat scan with 1 new match — only that row flagged ──────────

def test_repeat_scan_with_one_new_match_flags_only_that_row(app_client):
    """The tconst that wasn't in the snapshot gets the NEW pill; the
    tconst that WAS in the snapshot does not."""
    app_module, client, db_path = app_client

    run_id = _insert_run(db_path)
    _insert_match(db_path, run_id, "tt2000001", "Returning Title")
    _insert_match(db_path, run_id, "tt2000002", "Brand New Title")
    _snapshot_previous(db_path, ["tt2000001"])  # only the first was here before

    resp = client.get("/")
    html = resp.data.decode("utf-8")
    # Exactly one pill in the DOM.
    assert html.count('class="new-pill"') == 1
    # The pill sits on the row for the new title, not the returning one.
    # Row layout: <tr ... data-tconst="tt..."> ... title link ... {% if is_new %}<span class="new-pill">
    # So we can look for the new-pill occurring after the new tconst but
    # before the next <tr.
    new_row_start = html.index('data-tconst="tt2000002"')
    next_tr = html.find("<tr", new_row_start + 1)
    if next_tr == -1:
        next_tr = len(html)
    new_row_slice = html[new_row_start:next_tr]
    assert 'class="new-pill"' in new_row_slice

    old_row_start = html.index('data-tconst="tt2000001"')
    old_next_tr = html.find("<tr", old_row_start + 1)
    if old_next_tr == -1:
        old_next_tr = len(html)
    old_row_slice = html[old_row_start:old_next_tr]
    assert 'class="new-pill"' not in old_row_slice


# ── Case 4: dropped + added — only the added one is flagged ───────────────

def test_repeat_scan_dropped_and_added_flags_only_the_added(app_client):
    """A match that was in the snapshot but is missing from current
    matches simply doesn't appear (there's nothing to render). A match
    that's new gets the pill."""
    app_module, client, db_path = app_client

    run_id = _insert_run(db_path)
    _insert_match(db_path, run_id, "tt3000001", "Still Here")
    _insert_match(db_path, run_id, "tt3000003", "Just Arrived")
    # Snapshot had "Still Here" AND "Dropped From Results" but not
    # "Just Arrived". Only "Just Arrived" should get the pill.
    _snapshot_previous(db_path, ["tt3000001", "tt3000002"])

    resp = client.get("/")
    html = resp.data.decode("utf-8")

    assert "Still Here" in html
    assert "Just Arrived" in html
    # The dropped tconst isn't rendered at all — nothing to see.
    assert "tt3000002" not in html
    # Exactly one NEW pill.
    assert html.count('class="new-pill"') == 1


# ── Case 5: /clear wipes the snapshot ─────────────────────────────────────

def test_clear_all_wipes_previous_snapshot(app_client):
    """POST /clear must wipe previous_match_tconsts so the next scan
    starts with a clean baseline (nothing flagged as new)."""
    app_module, client, db_path = app_client

    _snapshot_previous(db_path, ["tt4000001", "tt4000002"])

    # Sanity: rows exist before /clear.
    conn = sqlite3.connect(db_path)
    before = conn.execute(
        "SELECT COUNT(*) FROM previous_match_tconsts"
    ).fetchone()[0]
    conn.close()
    assert before == 2

    resp = client.post("/clear")
    assert resp.status_code in (200, 302)

    conn = sqlite3.connect(db_path)
    after = conn.execute(
        "SELECT COUNT(*) FROM previous_match_tconsts"
    ).fetchone()[0]
    conn.close()
    assert after == 0, "Clear all should wipe the previous-match snapshot"
