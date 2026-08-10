"""test_app_cancel_and_status.py — V3.18 regression tests.

Two bugs (Thomas, 2026-08-10, MovieScanner V3.17):

    Bug 1 — Status column in Recent runs shows the phase name ("seasons",
    "matches", "download") instead of "Running". The column is LABELED
    Status but currently displays the phase.

    Bug 2 — There is no way to cancel a stuck scan from the UI. Run #4
    in Thomas's live DB was running for hours with no cancel affordance.

V3.18 behaviour we lock in here:

    1. For a run with status='running' and phase='seasons', the STATUS cell
       in the Recent runs table shows the string "Running" (primary) AND
       "seasons" (secondary, muted). "Running" is the load-bearing token.

    2. POST /cancel/<run_id> returns 200 when the given run_id matches the
       currently-running scan AND ``_active_scanner`` is set; it calls
       ``.cancel()`` on that scanner. Returns 404 otherwise.

SAFETY: Every test sets MOVIESCANNER_DB_PATH to a per-test tempfile BEFORE
importing app, so the live scanner.db is never touched.
"""

import importlib
import os
import sqlite3
import sys
import tempfile

import pytest


# ── Test harness ──────────────────────────────────────────────────────────

@pytest.fixture
def app_client(monkeypatch):
    """Fresh Flask test_client backed by a per-test temp DB.

    Re-imports MovieScanner.app under a MOVIESCANNER_DB_PATH override so
    the module-level DB_PATH picks up the tempfile. Cleans up cleanly.
    """
    fd, db_path = tempfile.mkstemp(suffix=".db", prefix="movscan_test_")
    os.close(fd)
    monkeypatch.setenv("MOVIESCANNER_DB_PATH", db_path)

    # Force a fresh import of MovieScanner.app so the module-level DB_PATH
    # honours our tempfile. Reset the module if it was already imported.
    _REPO_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    ms_dir = os.path.join(_REPO_ROOT, "MovieScanner")
    if ms_dir not in sys.path:
        sys.path.insert(0, ms_dir)
    if "app" in sys.modules:
        del sys.modules["app"]
    import app as app_module  # noqa: E402

    app_module.app.config["TESTING"] = True
    client = app_module.app.test_client()

    yield app_module, client, db_path

    # Cleanup — remove the tempfile and the imported module so the next
    # test picks up a fresh one.
    if "app" in sys.modules:
        del sys.modules["app"]
    try:
        os.unlink(db_path)
    except FileNotFoundError:
        pass


def _insert_running_run(db_path: str, phase: str = "seasons") -> int:
    """Insert a fixture row with status='running' and the given phase."""
    conn = sqlite3.connect(db_path)
    cur = conn.execute(
        "INSERT INTO runs (status, phase) VALUES ('running', ?)",
        (phase,),
    )
    conn.commit()
    run_id = cur.lastrowid
    conn.close()
    return run_id


# ── Bug 1: Status column shows "Running" not the phase ────────────────────

def test_running_row_shows_running_as_primary_label(app_client):
    """A row with status='running', phase='seasons' must render the string
    "Running" in the STATUS cell (the primary token), NOT just "seasons".
    """
    app_module, client, db_path = app_client
    _insert_running_run(db_path, phase="seasons")

    resp = client.get("/")
    assert resp.status_code == 200
    html = resp.data.decode("utf-8")

    # The primary label must be "Running" (title-cased, load-bearing).
    assert "Running" in html, (
        "Expected 'Running' as the primary STATUS label for an in-flight "
        "run, but did not find it in the rendered page. The column is "
        "labeled STATUS — it must show the status, not the phase."
    )


def test_running_row_shows_phase_as_secondary_context(app_client):
    """The phase (e.g. 'seasons') should still be visible as secondary
    context under / next to the Running label, so the user knows how far
    the scan has gotten.
    """
    app_module, client, db_path = app_client
    _insert_running_run(db_path, phase="seasons")

    resp = client.get("/")
    html = resp.data.decode("utf-8")

    assert "seasons" in html, (
        "Expected 'seasons' to appear as secondary phase context alongside "
        "the Running label."
    )


def test_running_row_status_column_order(app_client):
    """"Running" must appear BEFORE "seasons" in the rendered STATUS cell
    (primary label first, phase second). This asserts the layout order,
    not just the presence of both strings.
    """
    app_module, client, db_path = app_client
    _insert_running_run(db_path, phase="seasons")

    resp = client.get("/")
    html = resp.data.decode("utf-8")

    running_idx = html.find("Running")
    seasons_idx = html.find("seasons")
    assert running_idx != -1, "Running not found"
    assert seasons_idx != -1, "seasons not found"
    assert running_idx < seasons_idx, (
        f"Expected 'Running' (idx {running_idx}) to render BEFORE 'seasons' "
        f"(idx {seasons_idx}). Status is the primary token; phase is context."
    )


# ── Bug 2: /cancel/<run_id> route ─────────────────────────────────────────

def test_cancel_route_returns_404_when_no_active_scanner(app_client):
    """POST /cancel/<run_id> with no active scan returns 404."""
    app_module, client, db_path = app_client
    # No scan running, no rows.
    resp = client.post("/cancel/999")
    assert resp.status_code == 404


def test_cancel_route_returns_404_when_run_id_does_not_match(app_client):
    """POST /cancel/<run_id> with a run_id that doesn't match the active
    scan returns 404 (defensive — protect against stale UI state)."""
    app_module, client, db_path = app_client

    # Install a fake scanner that just records cancel() calls.
    class FakeScanner:
        def __init__(self):
            self.cancelled = False
        def cancel(self):
            self.cancelled = True

    fake = FakeScanner()
    app_module._active_scanner = fake

    # Insert a running row with id=1
    real_id = _insert_running_run(db_path)

    # POST with the WRONG id → 404, no cancel called
    resp = client.post(f"/cancel/{real_id + 100}")
    assert resp.status_code == 404
    assert fake.cancelled is False

    app_module._active_scanner = None


def test_cancel_route_calls_scanner_cancel_on_match(app_client):
    """POST /cancel/<run_id> when run_id matches the currently-running row
    AND _active_scanner is set → returns 200 and calls .cancel()."""
    app_module, client, db_path = app_client

    class FakeScanner:
        def __init__(self):
            self.cancelled = False
        def cancel(self):
            self.cancelled = True

    fake = FakeScanner()
    app_module._active_scanner = fake

    run_id = _insert_running_run(db_path)

    resp = client.post(f"/cancel/{run_id}")
    assert resp.status_code == 200
    assert fake.cancelled is True, (
        "Expected /cancel/<run_id> to call .cancel() on the active scanner "
        "when the run_id matches the currently-running row."
    )

    app_module._active_scanner = None


def test_cancel_button_renders_in_running_row(app_client):
    """The Recent runs table must render a cancel affordance (htmx POST to
    /cancel/<run_id>) ONLY for rows with status='running'."""
    app_module, client, db_path = app_client
    run_id = _insert_running_run(db_path)

    resp = client.get("/")
    html = resp.data.decode("utf-8")

    assert f"/cancel/{run_id}" in html, (
        "Expected the running row to contain an htmx POST target of "
        f"/cancel/{run_id} — the cancel button was not rendered."
    )


def test_cancel_button_absent_from_non_running_rows(app_client):
    """Done and error rows must NOT have a cancel button."""
    app_module, client, db_path = app_client

    conn = sqlite3.connect(db_path)
    conn.execute(
        "INSERT INTO runs (status, phase, completed_at) "
        "VALUES ('done', 'done', strftime('%Y-%m-%dT%H:%M:%SZ','now'))"
    )
    done_id = conn.execute("SELECT last_insert_rowid()").fetchone()[0]
    conn.execute(
        "INSERT INTO runs (status, phase, error, completed_at) "
        "VALUES ('error', 'download', 'boom', strftime('%Y-%m-%dT%H:%M:%SZ','now'))"
    )
    err_id = conn.execute("SELECT last_insert_rowid()").fetchone()[0]
    conn.commit()
    conn.close()

    resp = client.get("/")
    html = resp.data.decode("utf-8")

    assert f"/cancel/{done_id}" not in html, "Done rows must not have a cancel button"
    assert f"/cancel/{err_id}" not in html, "Error rows must not have a cancel button"


# ── Bonus: cancelled run reads well (neutral, not red) ────────────────────

def test_cancelled_run_row_reads_neutrally_not_as_hard_error(app_client):
    """A run with status='error', phase='cancelled' should render with
    language that reads as a user-initiated cancel, not a system error.

    We assert the word 'cancelled' appears near the row. We do NOT require
    a specific colour — Sienna's judgment on the neutral treatment — but
    the token must be visible so the user knows what happened.
    """
    app_module, client, db_path = app_client
    conn = sqlite3.connect(db_path)
    conn.execute(
        "INSERT INTO runs (status, phase, error, completed_at) "
        "VALUES ('error', 'cancelled', 'cancelled during seasons', "
        "strftime('%Y-%m-%dT%H:%M:%SZ','now'))"
    )
    conn.commit()
    conn.close()

    resp = client.get("/")
    html = resp.data.decode("utf-8")
    assert "cancelled" in html.lower(), (
        "Expected 'cancelled' to appear in the rendered page so the user "
        "can see that the run was cancelled rather than crashed."
    )
