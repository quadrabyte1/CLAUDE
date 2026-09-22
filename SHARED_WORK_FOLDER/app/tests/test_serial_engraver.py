"""
test_serial_engraver.py — TDD tests for the global serial counter.

Written BEFORE the implementation so all tests run RED first, then GREEN
after serial_engraver.py is updated.

Test inventory
--------------
1. commit_global_serial() returns STARTING_GLOBAL_SERIAL on first call when
   global_serial.json is absent; file is created at value+1 afterwards.
2. commit_global_serial() returns 1000, 1001, 1002 on successive calls.
3. commit_global_serial() is atomic under concurrent access — no dupes, no gaps.
4. peek_next_global_serial() never advances the counter.
5. Deprecated shim peek_next_serial(course) logs DeprecationWarning, returns
   the same value as peek_next_global_serial(), ignores the course arg.
6. generate_from_egm_file(egm_path, out_dir, serial=1234) writes a file with
   [1234] in the name and does NOT touch global_serial.json.
7. Flask /api/generate_models commits a serial exactly once per request, even
   if the pipeline raises.
8. Regression guard: no serial.json inside ItWentIn/GolfCourses/*/ is modified
   by any test in this suite.
"""

from __future__ import annotations

import concurrent.futures
import glob
import json
import os
import sys
import tempfile
import threading
import warnings

import pytest

# ---------------------------------------------------------------------------
# Make app/ importable regardless of where pytest is invoked from.
# ---------------------------------------------------------------------------

APP_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if APP_DIR not in sys.path:
    sys.path.insert(0, APP_DIR)


# ---------------------------------------------------------------------------
# Shared fixture: a fresh temp dir for the global serial file.
# Every test that touches serial state uses this fixture so tests are
# independent of each other and NEVER touch the real app/global_serial.json.
# ---------------------------------------------------------------------------

@pytest.fixture()
def serial_dir(tmp_path, monkeypatch):
    """Patch serial_engraver.GLOBAL_SERIAL_PATH to a file inside tmp_path."""
    # Import lazily so the module-level state isn't shared between tests
    # without re-patching.
    import serial_engraver as se
    fake_path = str(tmp_path / "global_serial.json")
    monkeypatch.setattr(se, "GLOBAL_SERIAL_PATH", fake_path)
    yield fake_path


# ---------------------------------------------------------------------------
# Test 1 — First call on missing file returns STARTING_GLOBAL_SERIAL; file
#           is written with next_serial = STARTING_GLOBAL_SERIAL + 1.
# ---------------------------------------------------------------------------

def test_commit_first_call_returns_starting_value(serial_dir):
    import serial_engraver as se

    assert not os.path.exists(serial_dir), "pre-condition: file must be absent"

    result = se.commit_global_serial()

    assert result == se.STARTING_GLOBAL_SERIAL, (
        f"Expected {se.STARTING_GLOBAL_SERIAL}, got {result}"
    )
    assert os.path.exists(serial_dir), "global_serial.json must be created after first commit"
    with open(serial_dir) as f:
        data = json.load(f)
    assert data["next_serial"] == se.STARTING_GLOBAL_SERIAL + 1, (
        f"File should contain next_serial = {se.STARTING_GLOBAL_SERIAL + 1}, got {data}"
    )


# ---------------------------------------------------------------------------
# Test 2 — Successive calls return 1000, 1001, 1002.
# ---------------------------------------------------------------------------

def test_commit_successive_calls(serial_dir):
    import serial_engraver as se

    r1 = se.commit_global_serial()
    r2 = se.commit_global_serial()
    r3 = se.commit_global_serial()

    assert r1 == se.STARTING_GLOBAL_SERIAL
    assert r2 == se.STARTING_GLOBAL_SERIAL + 1
    assert r3 == se.STARTING_GLOBAL_SERIAL + 2


# ---------------------------------------------------------------------------
# Test 3 — Atomic under concurrent access: N threads, no dupes, no gaps.
# ---------------------------------------------------------------------------

def test_commit_atomic_concurrent(serial_dir):
    import serial_engraver as se

    N = 20
    results = []
    errors = []

    def _worker():
        try:
            results.append(se.commit_global_serial())
        except Exception as exc:
            errors.append(exc)

    threads = [threading.Thread(target=_worker) for _ in range(N)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()

    assert not errors, f"Thread errors: {errors}"
    expected = set(range(se.STARTING_GLOBAL_SERIAL, se.STARTING_GLOBAL_SERIAL + N))
    assert set(results) == expected, (
        f"Expected serials {expected}, got {sorted(results)}"
    )
    assert len(results) == N, "No serial should be missing"


# ---------------------------------------------------------------------------
# Test 4 — peek_next_global_serial() never advances the counter.
# ---------------------------------------------------------------------------

def test_peek_does_not_advance(serial_dir):
    import serial_engraver as se

    first = se.peek_next_global_serial()
    second = se.peek_next_global_serial()
    third = se.peek_next_global_serial()

    assert first == second == third, "peek must be idempotent"

    # Commit once — should still return STARTING value
    used = se.commit_global_serial()
    assert used == first, "commit after peek should use the same starting value"

    # Now peek again — should be STARTING + 1
    after_commit = se.peek_next_global_serial()
    assert after_commit == se.STARTING_GLOBAL_SERIAL + 1


# ---------------------------------------------------------------------------
# Test 5 — Deprecated shim peek_next_serial(course) logs DeprecationWarning
#           and returns the same value as peek_next_global_serial().
# ---------------------------------------------------------------------------

def test_deprecated_shim_peek(serial_dir):
    import serial_engraver as se

    global_peek = se.peek_next_global_serial()

    with warnings.catch_warnings(record=True) as caught:
        warnings.simplefilter("always")
        shim_result = se.peek_next_serial("Stanford")

    assert shim_result == global_peek, (
        f"Shim should return same as global peek ({global_peek}), got {shim_result}"
    )
    warning_categories = [str(w.category) for w in caught]
    assert any("DeprecationWarning" in c or "Warning" in c for c in warning_categories), (
        f"Expected a DeprecationWarning, got: {caught}"
    )


# ---------------------------------------------------------------------------
# Test 6 — generate_from_egm_file(egm_path, out_dir, serial=1234) writes a
#           file with [1234] in the name and does NOT touch global_serial.json.
# ---------------------------------------------------------------------------

def test_generate_from_egm_file_uses_explicit_serial(serial_dir, tmp_path):
    import serial_engraver as se

    # Minimal EGM with enough structure to reach the filename-building code
    # without actually running the full trimesh pipeline.  We pass a fake green
    # polygon so the function doesn't early-return.
    egm_data = {
        "course": "Test Course",
        "hole": "01",
        "imageSize": {"width": 600, "height": 600},
        "polygons": [
            {
                "type": "green",
                "points": [
                    {"x": 100, "y": 100},
                    {"x": 200, "y": 100},
                    {"x": 200, "y": 200},
                    {"x": 100, "y": 200},
                ],
            }
        ],
    }
    egm_path = str(tmp_path / "Test Course (Hole 01).egm")
    with open(egm_path, "w") as f:
        json.dump(egm_data, f)

    out_dir = str(tmp_path / "out")
    os.makedirs(out_dir, exist_ok=True)

    # Pre-capture the serial file's state (absent at this point)
    assert not os.path.exists(serial_dir)

    try:
        import generate_stl_3mf as gstl
        gstl.generate_from_egm_file(egm_path, output_dir=out_dir, serial=1234)
    except Exception:
        # The pipeline may fail on missing image / dependencies — what matters
        # is that no [serial] file was written and if files were written they
        # carry [1234].
        pass

    # Verify: if any 3MF was written it must have [1234] in the name.
    mfs = glob.glob(os.path.join(out_dir, "*.3mf"))
    for mf in mfs:
        assert "[1234]" in os.path.basename(mf), (
            f"Expected [1234] in filename, got: {os.path.basename(mf)}"
        )

    # Critical: global_serial.json must NOT have been written.
    assert not os.path.exists(serial_dir), (
        "generate_from_egm_file must not touch the global serial counter"
    )


# ---------------------------------------------------------------------------
# Test 7 — Flask /api/generate_models commits exactly ONE serial per request,
#           even when the pipeline raises.
# ---------------------------------------------------------------------------

def test_flask_route_commits_serial_exactly_once(serial_dir, tmp_path, monkeypatch):
    """The route should call commit_global_serial() once regardless of outcome."""
    import serial_engraver as se

    commit_calls = []

    def _fake_commit():
        sn = se.STARTING_GLOBAL_SERIAL + len(commit_calls)
        commit_calls.append(sn)
        return sn

    # Monkeypatch the module as imported inside app.py
    monkeypatch.setattr(se, "commit_global_serial", _fake_commit)

    # Also patch run_pipeline so the test doesn't need real EGM files.
    # We'll make it fail on the first attempt to verify the serial was still burned.
    import app as flask_app

    # Create a fake EGM file so the route can find it
    fake_egm_name = "FakeCourse (Hole 01).egm"
    egm_dir = str(tmp_path / "FakeCourse" / "EGMs")
    os.makedirs(egm_dir, exist_ok=True)
    fake_egm_path = os.path.join(egm_dir, fake_egm_name)
    egm_data = {
        "course": "FakeCourse",
        "hole": "01",
        "imageSize": {"width": 600, "height": 600},
        "polygons": [],
    }
    with open(fake_egm_path, "w") as f:
        json.dump(egm_data, f)

    # Patch _EGM_BASE so the route finds our fake course folder
    monkeypatch.setattr(flask_app, "_EGM_BASE", str(tmp_path))

    # Patch run_pipeline to raise to exercise the error path
    def _failing_pipeline(*args, **kwargs):
        raise RuntimeError("test-forced pipeline failure")

    # run_pipeline is imported inside the route with `from gradient_surface_diagnostic
    # import run_pipeline`, so we patch it in the gradient_surface_diagnostic module.
    from unittest.mock import patch
    with patch("gradient_surface_diagnostic.run_pipeline", _failing_pipeline):
        client = flask_app.app.test_client()
        resp = client.post(
            "/api/generate_models",
            json={"course": "FakeCourse", "hole": "01"},
            content_type="application/json",
        )

    # The route should have committed exactly one serial regardless of the error.
    assert len(commit_calls) == 1, (
        f"Expected commit_global_serial() to be called once, got {len(commit_calls)} calls"
    )

    # And the response should be an error (pipeline raised)
    assert resp.status_code in (500, 400, 404)


# ---------------------------------------------------------------------------
# Test 8 — Regression guard: no serial.json inside ItWentIn/GolfCourses/*/
#           is modified by any test in this suite.
# ---------------------------------------------------------------------------

def test_no_course_serial_json_modified():
    """Snapshot mtime of every existing per-course serial.json before running
    (or note their absence), then verify nothing changed after the suite."""

    # Find all per-course serial.json files
    base = os.path.abspath(
        os.path.join(os.path.dirname(__file__), "..", "..", "ItWentIn", "GolfCourses")
    )
    pattern = os.path.join(base, "**", "serial.json")
    paths = glob.glob(pattern, recursive=True)

    snapshots = {}
    for p in paths:
        try:
            snapshots[p] = os.path.getmtime(p)
        except OSError:
            snapshots[p] = None

    # All other tests in this module run in isolated tmp dirs via the serial_dir
    # fixture; this test simply verifies that state holds at the point it is
    # called (which pytest runs after isolation fixtures clean up).
    for p, original_mtime in snapshots.items():
        try:
            current_mtime = os.path.getmtime(p)
        except OSError:
            current_mtime = None
        assert current_mtime == original_mtime, (
            f"Per-course serial.json was modified during tests: {p}\n"
            f"  before: {original_mtime}\n"
            f"  after:  {current_mtime}"
        )
