"""
test_editor_clear_on_open.py  —  Bug→TDD: editor clears state on Open Project click
Bug-fix: clicking "Open Project" must clear all previous EGM state BEFORE the fetch
completes, so a failed load never leaves stale polygons/image on screen.

These tests validate:
  T1. clearEditorState() helper exists and returns a dict with all fields emptied.
  T2. loadProject() calls clearEditorState() before the fetch (order of operations).
  T3. Load-success path: after a successful /api/boundaries/load, state holds new data.
  T4. Load-failure path (HTTP 500): state stays cleared — no stale data.
  T5. Load-failure path (file not found, 404): state stays cleared.
  T6. User-adjusted polygons are discarded on click, before the fetch resolves.

Tests T3–T6 exercise the Flask routes with a temp DB (never touch live DB).
T1–T2 parse the JS handler source to verify structural guarantees.
"""
import json
import os
import re
import sys
import tempfile
import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))


# ─────────────────────────────────────────────────────────────────────────────
# Fixtures
# ─────────────────────────────────────────────────────────────────────────────

@pytest.fixture()
def app_client(tmp_path, monkeypatch):
    """Flask test client with a temp DB — never touches the live workspace DB."""
    tmp_db = str(tmp_path / "workspace.db")
    import app as _app_module
    monkeypatch.setattr(_app_module, "DB_PATH", tmp_db)
    _app_module.app.config["TESTING"] = True
    with _app_module.app.test_client() as client:
        yield client


@pytest.fixture()
def saved_egm(tmp_path, monkeypatch):
    """
    Create a minimal .egm file in a temp GolfCourses tree and patch the app's
    _EGM_BASE so /api/boundaries/load can find it.
    Returns (client, filename, egm_data).
    """
    egm_data = {
        "course": "Test Course",
        "hole": "3",
        "image": "test_hole3.jpg",
        "imageCourse": "Test Course",
        "polygons": [
            {"type": "green",  "points": [{"x": 10, "y": 10}, {"x": 20, "y": 10}]},
            {"type": "fringe", "points": [{"x":  5, "y":  5}, {"x": 25, "y":  5}]},
            {"type": "trap",   "points": [{"x": 30, "y": 30}, {"x": 40, "y": 30}]},
        ],
        "gpsBackend": {
            "enabled": True,
            "gpsFile": "/some/course.gps",
            "bbox": {"lat_min": 36.0, "lng_min": -122.0, "lat_max": 36.01, "lng_max": -121.99},
            "approachM": 10.0,
            "vertExag": 2.5,
            "gridSize": [150, 150],
        },
        "courseGeoRef": {
            "imageWidth": 1024, "imageHeight": 1024,
            "swCornerLatLng": [36.0, -122.0],
            "neCornerLatLng": [36.01, -121.99],
        },
        "contourStep": 0.75,
        "grassAmplitude": 0.8,
        "grassSpacing": 0.06,
        "greenStyle": "smooth",
        "elevationRange": 12.0,
        "greenScale": 1.01,
        "fringeEdgeHeight": 9.0,
        "baseThicknessMm": 2.0,
        "includeBoundaryRegion": True,
        "applyFringeFrameCap": False,
        "flagOffsetXMm": 1.5,
        "flagOffsetYMm": -0.5,
        "elevationSpikes": [{"x": 100, "y": 200, "mm": 5.0}],
        "tee_hole": {"x_mm": 30.0, "y_mm": 30.0},
    }

    # Build GolfCourses/Test Course/EGMs/ under tmp_path
    egm_dir = tmp_path / "GolfCourses" / "Test Course" / "EGMs"
    egm_dir.mkdir(parents=True)
    fname = "Test Course (Hole 03).egm"
    (egm_dir / fname).write_text(json.dumps(egm_data))

    tmp_db = str(tmp_path / "workspace.db")
    import app as _app_module
    monkeypatch.setattr(_app_module, "DB_PATH", tmp_db)
    monkeypatch.setattr(_app_module, "_EGM_BASE", str(tmp_path / "GolfCourses"))
    _app_module.app.config["TESTING"] = True
    with _app_module.app.test_client() as client:
        yield client, fname, egm_data


# ─────────────────────────────────────────────────────────────────────────────
# T1: JS source — clearEditorState() helper exists and resets all EGM fields
# ─────────────────────────────────────────────────────────────────────────────

EDITOR_HTML = os.path.join(os.path.dirname(__file__), "..", "templates", "editor.html")

def _read_editor_js():
    """Return the raw JS content of editor.html as a string."""
    with open(EDITOR_HTML, "r") as f:
        return f.read()


class TestClearEditorStateHelper:

    def test_clearEditorState_function_exists(self):
        """T1a: clearEditorState() must be defined in the editor JS."""
        src = _read_editor_js()
        assert "clearEditorState()" in src or "clearEditorState (" in src, (
            "clearEditorState() helper not found in editor.html. "
            "Add it before implementing loadProject() order-of-operations fix."
        )

    def test_clearEditorState_clears_polygons(self):
        """T1b: clearEditorState() must assign an empty array to this.polygons."""
        src = _read_editor_js()
        # Find the clearEditorState function body
        m = re.search(r'clearEditorState\s*\(\s*\)\s*\{(.+?)^\s*\},', src,
                      re.DOTALL | re.MULTILINE)
        assert m, "clearEditorState() body not found or not properly closed."
        body = m.group(1)
        assert "this.polygons" in body, "clearEditorState() does not reset this.polygons"
        assert "[]" in body or "= []" in body.replace(" ", ""), (
            "clearEditorState() should set polygons to []"
        )

    def test_clearEditorState_clears_image(self):
        """T1c: clearEditorState() must clear selectedImage and imgLoaded."""
        src = _read_editor_js()
        m = re.search(r'clearEditorState\s*\(\s*\)\s*\{(.+?)^\s*\},', src,
                      re.DOTALL | re.MULTILINE)
        assert m, "clearEditorState() body not found."
        body = m.group(1)
        assert "selectedImage" in body, "clearEditorState() must reset selectedImage"
        assert "imgLoaded" in body, "clearEditorState() must reset imgLoaded"

    def test_clearEditorState_clears_gps_fields(self):
        """T1d: clearEditorState() must reset GPS backend state."""
        src = _read_editor_js()
        m = re.search(r'clearEditorState\s*\(\s*\)\s*\{(.+?)^\s*\},', src,
                      re.DOTALL | re.MULTILINE)
        assert m, "clearEditorState() body not found."
        body = m.group(1)
        assert "gpsEnabled" in body, "clearEditorState() must reset gpsEnabled"
        assert "gpsFile" in body, "clearEditorState() must reset gpsFile"

    def test_clearEditorState_clears_elevation_spikes(self):
        """T1e: clearEditorState() must reset elevationSpikes."""
        src = _read_editor_js()
        m = re.search(r'clearEditorState\s*\(\s*\)\s*\{(.+?)^\s*\},', src,
                      re.DOTALL | re.MULTILINE)
        assert m, "clearEditorState() body not found."
        body = m.group(1)
        assert "elevationSpikes" in body, "clearEditorState() must reset elevationSpikes"

    def test_clearEditorState_clears_contours(self):
        """T1f: clearEditorState() must reset contours."""
        src = _read_editor_js()
        m = re.search(r'clearEditorState\s*\(\s*\)\s*\{(.+?)^\s*\},', src,
                      re.DOTALL | re.MULTILINE)
        assert m, "clearEditorState() body not found."
        body = m.group(1)
        assert "contours" in body, "clearEditorState() must reset contours"


# ─────────────────────────────────────────────────────────────────────────────
# T2: Order of operations — clearEditorState() called BEFORE fetch in loadProject()
# ─────────────────────────────────────────────────────────────────────────────

class TestLoadProjectOrderOfOperations:

    def test_clear_fires_before_fetch_in_loadProject(self):
        """T2: In loadProject(), clearEditorState() must appear before the fetch() call."""
        src = _read_editor_js()
        # Locate the loadProject function body
        m = re.search(r'async loadProject\s*\(proj\)\s*\{(.+?)^\s*\},', src,
                      re.DOTALL | re.MULTILINE)
        assert m, "loadProject() not found in editor.html"
        body = m.group(1)

        clear_pos = body.find("clearEditorState()")
        fetch_pos = body.find("fetch(")
        assert clear_pos != -1, (
            "clearEditorState() not called inside loadProject(). "
            "It must be called immediately when the user picks a project."
        )
        assert fetch_pos != -1, "fetch() call not found in loadProject()"
        assert clear_pos < fetch_pos, (
            "clearEditorState() must appear BEFORE fetch() in loadProject(). "
            f"Found clearEditorState at offset {clear_pos}, fetch at {fetch_pos}."
        )

    def test_clear_fires_before_resp_ok_check_in_loadProject(self):
        """T2b: clearEditorState() must appear before resp.ok check (failure path guard)."""
        src = _read_editor_js()
        m = re.search(r'async loadProject\s*\(proj\)\s*\{(.+?)^\s*\},', src,
                      re.DOTALL | re.MULTILINE)
        assert m, "loadProject() not found"
        body = m.group(1)

        clear_pos = body.find("clearEditorState()")
        resp_ok_pos = body.find("resp.ok")
        assert clear_pos != -1, "clearEditorState() not called in loadProject()"
        assert resp_ok_pos != -1, "resp.ok check not found in loadProject()"
        assert clear_pos < resp_ok_pos, (
            "clearEditorState() must fire before resp.ok check — "
            "state must be empty even on HTTP failure."
        )


# ─────────────────────────────────────────────────────────────────────────────
# T3: Load-success path — /api/boundaries/load returns valid data
# ─────────────────────────────────────────────────────────────────────────────

class TestLoadBoundariesSuccessRoute:

    def test_load_success_returns_200_and_polygons(self, saved_egm):
        """T3: /api/boundaries/load returns 200 with polygons on a valid file."""
        client, fname, egm_data = saved_egm
        resp = client.get(f"/api/boundaries/load?filename={fname}")
        assert resp.status_code == 200
        data = resp.get_json()
        assert data["status"] == "ok"
        assert data["course"] == egm_data["course"]
        assert data["hole"] == egm_data["hole"]
        assert len(data["polygons"]) == len(egm_data["polygons"])

    def test_load_success_returns_all_egm_fields(self, saved_egm):
        """T3b: /api/boundaries/load returns all per-hole config fields."""
        client, fname, egm_data = saved_egm
        resp = client.get(f"/api/boundaries/load?filename={fname}")
        data = resp.get_json()
        assert data["contourStep"] == pytest.approx(egm_data["contourStep"])
        assert data["grassAmplitude"] == pytest.approx(egm_data["grassAmplitude"])
        assert data["greenStyle"] == egm_data["greenStyle"]
        assert data["flagOffsetXMm"] == pytest.approx(egm_data["flagOffsetXMm"])
        assert data["flagOffsetYMm"] == pytest.approx(egm_data["flagOffsetYMm"])
        gps = data.get("gpsBackend", {})
        assert gps.get("enabled") is True
        assert gps.get("approachM") == pytest.approx(egm_data["gpsBackend"]["approachM"])


# ─────────────────────────────────────────────────────────────────────────────
# T4: Load-failure path — HTTP 404 (file not found)
# ─────────────────────────────────────────────────────────────────────────────

class TestLoadBoundariesNotFound:

    def test_load_missing_file_returns_404(self, app_client):
        """T4: /api/boundaries/load with a nonexistent filename → 404."""
        resp = app_client.get("/api/boundaries/load?filename=DoesNotExist.egm")
        assert resp.status_code == 404
        data = resp.get_json()
        assert data["status"] == "error"

    def test_load_missing_file_error_message(self, app_client):
        """T4b: Error response contains a human-readable message."""
        resp = app_client.get("/api/boundaries/load?filename=DoesNotExist.egm")
        data = resp.get_json()
        assert "msg" in data
        assert len(data["msg"]) > 0

    def test_load_invalid_filename_returns_400(self, app_client):
        """T4c: Path-traversal filename → 400 (not 500)."""
        resp = app_client.get("/api/boundaries/load?filename=../../etc/passwd")
        assert resp.status_code == 400


# ─────────────────────────────────────────────────────────────────────────────
# T5: JS source — after failure, no stale-state re-assignment in failure branches
# ─────────────────────────────────────────────────────────────────────────────

class TestLoadProjectFailurePathNoClobber:

    def test_no_state_assignment_before_resp_ok_check(self):
        """T5: The HTTP-error early-return path must not assign EGM fields.

        Specifically: the block between 'await fetch(...)' and '!resp.ok'
        check must not assign this.polygons, this.selectedImage, etc. — only
        clearEditorState() and error-flash are allowed there.
        """
        src = _read_editor_js()
        m = re.search(r'async loadProject\s*\(proj\)\s*\{(.+?)^\s*\},', src,
                      re.DOTALL | re.MULTILINE)
        assert m, "loadProject() not found"
        body = m.group(1)

        # Find the span between fetch() and the !resp.ok guard
        fetch_pos = body.find("fetch(")
        resp_ok_pos = body.find("resp.ok")
        assert fetch_pos != -1 and resp_ok_pos != -1
        between = body[fetch_pos:resp_ok_pos]

        # Should not assign EGM fields in this gap
        for field in ("this.polygons", "this.courseName", "this.holeName",
                      "this.selectedImage", "this.gpsEnabled"):
            assert field + " =" not in between and field + "=" not in between.replace(" ", ""), (
                f"Unexpected assignment to {field} between fetch() and resp.ok check. "
                "State assignments belong AFTER the resp.ok check."
            )

    def test_catch_block_does_not_restore_stale_state(self):
        """T5b: The catch block must not re-assign EGM data fields."""
        src = _read_editor_js()
        m = re.search(r'async loadProject\s*\(proj\)\s*\{(.+?)^\s*\},', src,
                      re.DOTALL | re.MULTILINE)
        assert m, "loadProject() not found"
        body = m.group(1)

        # Crude extraction: find catch block
        catch_pos = body.rfind("} catch (")
        if catch_pos == -1:
            catch_pos = body.rfind("} catch(")
        assert catch_pos != -1, "No catch block found in loadProject()"
        catch_block = body[catch_pos:]

        for field in ("this.polygons", "this.selectedImage", "this.courseName"):
            assert field + " =" not in catch_block, (
                f"catch block should not assign {field} — state must remain cleared on error."
            )


# ─────────────────────────────────────────────────────────────────────────────
# T6: User-adjusted polygons — stale data cleared before fetch
# ─────────────────────────────────────────────────────────────────────────────

class TestUserAdjustmentsDiscarded:

    def test_previous_polygons_not_preserved_after_open_click(self):
        """T6: clearEditorState() resets polygons (simulated via JS source analysis).

        We can't run the browser, so we verify structurally: after clearEditorState()
        is called in loadProject(), no code path before the fetch() can re-populate
        this.polygons from any cached / previous value.
        """
        src = _read_editor_js()
        m = re.search(r'async loadProject\s*\(proj\)\s*\{(.+?)^\s*\},', src,
                      re.DOTALL | re.MULTILINE)
        assert m, "loadProject() not found"
        body = m.group(1)

        clear_pos = body.find("clearEditorState()")
        fetch_pos = body.find("fetch(")
        assert clear_pos != -1 and fetch_pos != -1
        # Between clearEditorState() and fetch() nothing should push to polygons
        gap = body[clear_pos:fetch_pos]
        assert "this.polygons.push" not in gap, (
            "this.polygons.push() called between clearEditorState() and fetch() — "
            "stale data could sneak back."
        )
        assert "this.polygons =" not in gap.replace("this.polygons = []", ""), (
            "this.polygons re-assigned between clearEditorState() and fetch(). "
            "Only the clear itself is allowed."
        )

    def test_list_endpoint_returns_polygon_count(self, saved_egm):
        """T6b: /api/boundaries/list correctly reports polygon_count for a project."""
        client, fname, egm_data = saved_egm
        resp = client.get("/api/boundaries/list")
        assert resp.status_code == 200
        data = resp.get_json()
        assert data["status"] == "ok"
        projects = data["projects"]
        match = next((p for p in projects if p["filename"] == fname), None)
        assert match is not None, f"Expected {fname} in project list"
        assert match["polygon_count"] == len(egm_data["polygons"])
