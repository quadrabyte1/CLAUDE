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
    """The Recent runs table must render a cancel affordance for rows with
    status='running'. V3.20 — the button is now vanilla-JS (data-cancel-run
    attribute + onclick calling window.cancelRun); we assert the presence
    of both markers so a future regression that drops the click wiring is
    caught even if the button element itself is still rendered."""
    app_module, client, db_path = app_client
    run_id = _insert_running_run(db_path)

    resp = client.get("/")
    html = resp.data.decode("utf-8")

    assert f'data-cancel-run="{run_id}"' in html, (
        f"Expected the running row to render a button with "
        f"data-cancel-run=\"{run_id}\" — the cancel button was not rendered."
    )
    assert f"cancelRun({run_id}" in html, (
        f"Expected the running row's cancel button to wire up cancelRun({run_id}, "
        f"this) in its onclick — the click handler is missing, which is the "
        f"exact V3.18 regression this test guards against."
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

    assert f'data-cancel-run="{done_id}"' not in html, "Done rows must not have a cancel button"
    assert f'data-cancel-run="{err_id}"' not in html, "Error rows must not have a cancel button"


# ── V3.20 — the fix Thomas actually asked for ────────────────────────────
#
# Root cause of V3.18 regression: the cancel button was htmx-driven
# (hx-post + hx-confirm), and htmx was loaded from unpkg.com. When the
# CDN failed to load (Thomas offline, firewall, unpkg blip, browser
# extension blocking third-party scripts), the button rendered with all
# its hx-* attributes but had NO click handler attached — clicking it
# did nothing, silently. Matched Thomas's exact report: "visible and
# clickable, but doesn't do anything." Local-first app; critical UX
# cannot depend on a remote script that may not load.
#
# The following two tests lock in the fix.


def test_cancel_button_has_no_external_script_dependency(app_client):
    """Regression guard: the cancel button MUST NOT depend on any script
    loaded from a third-party CDN. Its click handler is inline in the
    template's <script> block (window.cancelRun). If a future edit
    reintroduces an htmx / Alpine / other-CDN dependency for the cancel
    button, this test fails — because the exact V3.18 breakage was
    'unpkg didn't load, so the button did nothing.'"""
    app_module, client, db_path = app_client
    _insert_running_run(db_path)

    resp = client.get("/")
    html = resp.data.decode("utf-8")

    # No hx-post attribute anywhere — htmx was the failure mode.
    assert "hx-post" not in html, (
        "Found hx-post in the page — the cancel button (or something else) "
        "depends on htmx again. htmx loaded from a CDN was the exact V3.18 "
        "failure mode. Wire click handlers with vanilla JS instead."
    )
    # cancelRun function must be defined inline (not from a remote script).
    assert "window.cancelRun" in html, (
        "cancelRun handler is not defined inline in the page. If it's moved "
        "to an external file that fails to load, the button will silently "
        "do nothing — exactly the V3.18 bug this test guards against."
    )


def test_cancel_button_click_fires_post_in_real_browser(app_client, tmp_path):
    """The full browser round-trip test that would have caught V3.18.

    Uses Playwright to load the page in a real Chromium, block ALL
    third-party CDN scripts (simulating Thomas offline / firewall /
    unpkg outage), then click the cancel-X button and assert that a
    POST /cancel/<run_id> actually hits the server AND that the
    installed FakeScanner's cancel() method was called.

    This test is what the V3.18 unit tests failed to be: they used
    client.post() directly, which bypasses every browser-side thing
    that can go wrong (script loads, click handlers, confirm dialogs).
    """
    playwright = pytest.importorskip("playwright.sync_api")
    from playwright.sync_api import sync_playwright

    import socket, threading, time as _time

    app_module, _flask_test_client, db_path = app_client

    # Install a fake scanner so /cancel/<id> returns 200 and .cancel()
    # is observable.
    class FakeScanner:
        def __init__(self): self.cancelled = False
        def cancel(self): self.cancelled = True
    fake = FakeScanner()
    app_module._active_scanner = fake

    run_id = _insert_running_run(db_path)

    # Pick a free port Chromium won't block. 5061 is on Chromium's
    # ERR_UNSAFE_PORT list; 55000+ is fine.
    sock = socket.socket()
    sock.bind(("127.0.0.1", 0))
    port = sock.getsockname()[1]
    sock.close()

    # Serve the real app in a background thread. Werkzeug is happy
    # with a raw socket-bound port and threaded=True for this.
    server_thread = threading.Thread(
        target=lambda: app_module.app.run(
            host="127.0.0.1", port=port, debug=False,
            use_reloader=False, threaded=True,
        ),
        daemon=True,
    )
    server_thread.start()

    # Wait for server to be ready.
    import urllib.request
    deadline = _time.monotonic() + 5.0
    while _time.monotonic() < deadline:
        try:
            urllib.request.urlopen(f"http://127.0.0.1:{port}/").read()
            break
        except Exception:
            _time.sleep(0.05)
    else:
        pytest.fail("Flask test server didn't come up in 5s")

    try:
        with sync_playwright() as p:
            browser = p.chromium.launch(headless=True)
            page = browser.new_context().new_page()

            requests_seen = []
            page.on("request", lambda req: requests_seen.append(req.url))
            page.on("dialog", lambda d: d.accept())

            # Simulate offline / firewall: block any third-party CDN.
            def block_cdns(route):
                if any(host in route.request.url for host in
                       ("unpkg.com", "jsdelivr.net", "cdn.tailwindcss.com")):
                    route.abort()
                else:
                    route.continue_()
            page.route("**/*", block_cdns)

            page.goto(f"http://127.0.0.1:{port}/", wait_until="domcontentloaded")
            page.wait_for_timeout(300)

            btn = page.query_selector(f'button[data-cancel-run="{run_id}"]')
            assert btn is not None, "Cancel button not found in DOM"

            btn.click()
            page.wait_for_timeout(1500)

            cancel_posts = [u for u in requests_seen if f"/cancel/{run_id}" in u]
            assert cancel_posts, (
                f"Clicking the cancel-X button did NOT trigger a POST to "
                f"/cancel/{run_id}. This is the exact V3.18 bug: button "
                f"visible and clickable, but doesn't do anything."
            )
            assert fake.cancelled is True, (
                "POST reached the server but FakeScanner.cancel() was not "
                "called — the /cancel route contract is broken."
            )

            browser.close()
    finally:
        app_module._active_scanner = None
        # daemon thread dies with pytest process; werkzeug dev server has
        # no clean shutdown from the outside, so we let it die on exit.


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
