"""
test_enable_fringe_grass.py — Bug→TDD: Enable Fringe Grass checkbox (task 714)

Thomas wants a UI checkbox that gates the fringe grass texture.  When checked
(default), the grass application proceeds as before.  When unchecked, the
fringe is smooth — grass functions are not called.

RED-first tests.  All should fail before implementation.

Tests
-----
T1  Checkbox renders — editor.html has input[type=checkbox] with label text
    "Enable Fringe Grass".
T2  Alpine default state — x-data block initialises enableFringeGrass: true.
T3  autoSave writes the field — data object in autoSave() includes
    enableFringeGrass.
T4  loadProject reads the field — loadProject() assigns this.enableFringeGrass
    from the loaded data.
T5  Load backward compat — loading EGM without the field defaults to true
    (missing = data.enableFringeGrass !== false pattern).
T6  clearEditorState resets to true — clearEditorState() sets
    this.enableFringeGrass = true.
T7  startNewProject resets to true — startNewProject() sets
    this.enableFringeGrass = true.
T8  EGM round-trip false — save EGM with enableFringeGrass: false, reload
    → HTTP 200 body carries enableFringeGrass === false.
T9  EGM round-trip true — save EGM with enableFringeGrass: true, reload
    → HTTP 200 body carries enableFringeGrass === true.
T10 Geometry skip when false — call run_pipeline with an EGM that has
    enableFringeGrass: false; apply_grass_texture_v2 and apply_grass_texture
    are NOT called.
T11 Geometry runs grass when true — call run_pipeline with enableFringeGrass:
    true; at least one of the grass functions IS called.
T12 Regression — generate_models route passes enableFringeGrass from the EGM
    to run_pipeline (field present in app.py route body).
"""
from __future__ import annotations

import json
import os
import re
import sys
import tempfile

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

EDITOR_HTML = os.path.join(os.path.dirname(__file__), "..", "templates", "editor.html")
APP_PY = os.path.join(os.path.dirname(__file__), "..", "app.py")


def _read_editor_js() -> str:
    with open(EDITOR_HTML, "r") as f:
        return f.read()


# ─────────────────────────────────────────────────────────────────────────────
# T1: Checkbox renders in HTML
# ─────────────────────────────────────────────────────────────────────────────

class TestCheckboxRendersInHTML:

    def test_checkbox_input_with_model(self):
        """T1a: editor.html must have an input[type=checkbox] x-modelled to enableFringeGrass."""
        src = _read_editor_js()
        assert 'x-model="enableFringeGrass"' in src or "x-model='enableFringeGrass'" in src, (
            "No checkbox x-model='enableFringeGrass' found in editor.html. "
            "Add the checkbox to the config panel."
        )

    def test_checkbox_label_text(self):
        """T1b: A <label> or <span> with text 'Enable Fringe Grass' must exist."""
        src = _read_editor_js()
        assert "Enable Fringe Grass" in src, (
            "The text 'Enable Fringe Grass' not found in editor.html. "
            "The checkbox must have a visible label with that exact text."
        )

    def test_checkbox_autosave_wired(self):
        """T1c: The checkbox must fire autoSave() on change."""
        src = _read_editor_js()
        # Find the block containing enableFringeGrass input
        # Locate the x-model line and check nearby @change
        # We look for a region that has both x-model="enableFringeGrass" and @change="autoSave()"
        # within a reasonable proximity (< 200 chars)
        idx = src.find('x-model="enableFringeGrass"')
        if idx == -1:
            idx = src.find("x-model='enableFringeGrass'")
        assert idx != -1, "enableFringeGrass x-model not found"
        surrounding = src[max(0, idx - 100) : idx + 200]
        assert '@change="autoSave()"' in surrounding or "@change='autoSave()'" in surrounding, (
            "The enableFringeGrass checkbox must have @change=\"autoSave()\" wired to it."
        )


# ─────────────────────────────────────────────────────────────────────────────
# T2: Alpine default state
# ─────────────────────────────────────────────────────────────────────────────

class TestAlpineDefaultState:

    def test_enable_fringe_grass_defaults_true(self):
        """T2: x-data block must initialise enableFringeGrass to true."""
        src = _read_editor_js()
        # Look for the initialisation line in the x-data object
        assert "enableFringeGrass: true" in src, (
            "enableFringeGrass: true not found in editor.html x-data initialisation. "
            "The field must default to true so existing behaviour is unchanged."
        )


# ─────────────────────────────────────────────────────────────────────────────
# T3: autoSave writes the field
# ─────────────────────────────────────────────────────────────────────────────

class TestAutoSaveWritesField:

    def test_autosave_includes_enable_fringe_grass(self):
        """T3: autoSave() must include enableFringeGrass in the data object it posts."""
        src = _read_editor_js()
        # Find the autoSave function body
        m = re.search(r'async autoSave\s*\(\s*\)\s*\{(.+?)^\s*\},', src,
                      re.DOTALL | re.MULTILINE)
        assert m, "autoSave() function body not found in editor.html"
        body = m.group(1)
        assert "enableFringeGrass" in body, (
            "autoSave() does not include enableFringeGrass in the data object. "
            "Add 'enableFringeGrass: this.enableFringeGrass,' to the data dict."
        )


# ─────────────────────────────────────────────────────────────────────────────
# T4: loadProject reads the field
# ─────────────────────────────────────────────────────────────────────────────

class TestLoadProjectReadsField:

    def test_load_project_assigns_enable_fringe_grass(self):
        """T4: loadProject() must assign this.enableFringeGrass from the response data."""
        src = _read_editor_js()
        m = re.search(r'async loadProject\s*\(proj\)\s*\{(.+?)^\s*\},', src,
                      re.DOTALL | re.MULTILINE)
        assert m, "loadProject() not found in editor.html"
        body = m.group(1)
        assert "enableFringeGrass" in body, (
            "loadProject() does not assign this.enableFringeGrass from response data. "
            "Add the assignment following the applyFringeFrameCap pattern."
        )


# ─────────────────────────────────────────────────────────────────────────────
# T5: Load backward compat — missing field defaults to true
# ─────────────────────────────────────────────────────────────────────────────

class TestLoadBackwardCompat:

    def test_missing_field_defaults_to_true_in_loadproject(self):
        """T5: loadProject() must default enableFringeGrass to true when field is absent.

        The correct pattern is: data.enableFringeGrass !== false
        (same as applyFringeFrameCap — truthy default on missing key).
        """
        src = _read_editor_js()
        m = re.search(r'async loadProject\s*\(proj\)\s*\{(.+?)^\s*\},', src,
                      re.DOTALL | re.MULTILINE)
        assert m, "loadProject() not found"
        body = m.group(1)
        # Check for the backward-compat pattern: !== false
        assert "enableFringeGrass" in body and "!== false" in body, (
            "loadProject() must use the '!== false' pattern for enableFringeGrass "
            "so that old EGMs without the field default to true (checked = grass on)."
        )


# ─────────────────────────────────────────────────────────────────────────────
# T6: clearEditorState resets to true
# ─────────────────────────────────────────────────────────────────────────────

class TestClearEditorStateResetsField:

    def test_clear_resets_enable_fringe_grass_to_true(self):
        """T6: clearEditorState() must reset enableFringeGrass to true."""
        src = _read_editor_js()
        m = re.search(r'clearEditorState\s*\(\s*\)\s*\{(.+?)^\s*\},', src,
                      re.DOTALL | re.MULTILINE)
        assert m, "clearEditorState() body not found"
        body = m.group(1)
        assert "enableFringeGrass" in body, (
            "clearEditorState() does not reset enableFringeGrass. "
            "Add: this.enableFringeGrass = true;"
        )
        # Check that it's reset to true (not false)
        # Look for the assignment in the body
        idx = body.find("enableFringeGrass")
        region = body[idx : idx + 50]
        assert "true" in region, (
            "clearEditorState() resets enableFringeGrass but not to true. "
            "Use: this.enableFringeGrass = true;"
        )


# ─────────────────────────────────────────────────────────────────────────────
# T7: startNewProject resets to true
# ─────────────────────────────────────────────────────────────────────────────

class TestStartNewProjectResetsField:

    def test_start_new_project_resets_enable_fringe_grass(self):
        """T7: startNewProject() must reset enableFringeGrass to true."""
        src = _read_editor_js()
        m = re.search(r'async startNewProject\s*\(\s*\)\s*\{(.+?)^\s*\},', src,
                      re.DOTALL | re.MULTILINE)
        assert m, "startNewProject() not found in editor.html"
        body = m.group(1)
        assert "enableFringeGrass" in body, (
            "startNewProject() does not reset enableFringeGrass. "
            "Add: this.enableFringeGrass = true; near the other defaults."
        )


# ─────────────────────────────────────────────────────────────────────────────
# T8 & T9: EGM round-trip via Flask routes
# ─────────────────────────────────────────────────────────────────────────────

@pytest.fixture()
def egm_client(tmp_path, monkeypatch):
    """Flask test client + temp EGM tree.  Never touches live DB."""
    import app as _app_module
    tmp_db = str(tmp_path / "workspace.db")
    monkeypatch.setattr(_app_module, "DB_PATH", tmp_db)

    egm_dir = tmp_path / "GolfCourses" / "Test Course" / "EGMs"
    egm_dir.mkdir(parents=True)
    monkeypatch.setattr(_app_module, "_EGM_BASE", str(tmp_path / "GolfCourses"))

    _app_module.app.config["TESTING"] = True
    with _app_module.app.test_client() as client:
        yield client, egm_dir


def _write_egm(egm_dir, fname: str, extra: dict) -> None:
    base = {
        "course": "Test Course",
        "hole": "5",
        "image": "test.jpg",
        "imageCourse": "Test Course",
        "polygons": [
            {"type": "green",  "points": [{"x": 10, "y": 10}, {"x": 20, "y": 10}, {"x": 15, "y": 20}]},
            {"type": "fringe", "points": [{"x":  5, "y":  5}, {"x": 25, "y":  5}, {"x": 15, "y": 25}]},
        ],
        "contourStep": 0.5,
        "grassAmplitude": 0.5,
        "grassSpacing": 0.05,
        "greenStyle": "terraced",
        "elevationRange": 14.5,
        "greenScale": 1.0065,
        "fringeEdgeHeight": 10.0,
        "baseThicknessMm": 1.5,
        "gpsBackend": {
            "enabled": True,
            "gpsFile": "/some/course.gps",
            "bbox": {"lat_min": 36.0, "lng_min": -122.0, "lat_max": 36.01, "lng_max": -121.99},
            "approachM": 10.0,
            "vertExag": 2.5,
            "gridSize": [150, 150],
        },
    }
    base.update(extra)
    (egm_dir / fname).write_text(json.dumps(base))


class TestEGMRoundTrip:

    def test_round_trip_false(self, egm_client):
        """T8: Load EGM with enableFringeGrass=false → API returns false."""
        client, egm_dir = egm_client
        fname = "Test Course (Hole 05).egm"
        _write_egm(egm_dir, fname, {"enableFringeGrass": False})
        resp = client.get(f"/api/boundaries/load?filename={fname}")
        assert resp.status_code == 200, f"Unexpected status: {resp.status_code}"
        data = resp.get_json()
        assert data["status"] == "ok"
        assert data.get("enableFringeGrass") is False, (
            f"Expected enableFringeGrass=false but got: {data.get('enableFringeGrass')}"
        )

    def test_round_trip_true(self, egm_client):
        """T9: Load EGM with enableFringeGrass=true → API returns true."""
        client, egm_dir = egm_client
        fname = "Test Course (Hole 05).egm"
        _write_egm(egm_dir, fname, {"enableFringeGrass": True})
        resp = client.get(f"/api/boundaries/load?filename={fname}")
        assert resp.status_code == 200
        data = resp.get_json()
        assert data["status"] == "ok"
        assert data.get("enableFringeGrass") is True, (
            f"Expected enableFringeGrass=true but got: {data.get('enableFringeGrass')}"
        )

    def test_backward_compat_missing_field_defaults_true(self, egm_client):
        """T8b: Load EGM without enableFringeGrass → API returns true (backward compat)."""
        client, egm_dir = egm_client
        fname = "Test Course (Hole 05).egm"
        _write_egm(egm_dir, fname, {})  # no enableFringeGrass key
        resp = client.get(f"/api/boundaries/load?filename={fname}")
        assert resp.status_code == 200
        data = resp.get_json()
        assert data["status"] == "ok"
        assert data.get("enableFringeGrass") is not False, (
            "enableFringeGrass missing from old EGM must default to true (or absent → JS defaults to true). "
            f"Got: {data.get('enableFringeGrass')}"
        )


# ─────────────────────────────────────────────────────────────────────────────
# T10 & T11: Geometry skip / run via run_pipeline
# ─────────────────────────────────────────────────────────────────────────────

@pytest.fixture()
def egm_file_false(tmp_path):
    """Write a minimal EGM with enableFringeGrass=False for pipeline testing."""
    import importlib.util
    from pathlib import Path
    APP_DIR = Path(__file__).parent.parent
    # We need a real image; use the first .jpg found in GolfCourses
    EGM_BASE = APP_DIR.parent / "ItWentIn" / "GolfCourses"
    # Find any existing EGM to borrow its structure
    egm_files = list(EGM_BASE.rglob("*.egm")) if EGM_BASE.exists() else []
    if not egm_files:
        pytest.skip("No real EGM files found for pipeline test")
    real_egm_path = egm_files[0]
    with open(real_egm_path) as f:
        egm_data = json.load(f)
    egm_data["enableFringeGrass"] = False
    out = tmp_path / "test_hole.egm"
    out.write_text(json.dumps(egm_data))
    return str(out)


@pytest.fixture()
def egm_file_true(tmp_path):
    """Write a minimal EGM with enableFringeGrass=True for pipeline testing."""
    from pathlib import Path
    APP_DIR = Path(__file__).parent.parent
    EGM_BASE = APP_DIR.parent / "ItWentIn" / "GolfCourses"
    egm_files = list(EGM_BASE.rglob("*.egm")) if EGM_BASE.exists() else []
    if not egm_files:
        pytest.skip("No real EGM files found for pipeline test")
    real_egm_path = egm_files[0]
    with open(real_egm_path) as f:
        egm_data = json.load(f)
    egm_data["enableFringeGrass"] = True
    out = tmp_path / "test_hole.egm"
    out.write_text(json.dumps(egm_data))
    return str(out)


class TestGeometryGrassGating:

    def test_grass_not_called_when_disabled(self, egm_file_false, monkeypatch):
        """T10: When enableFringeGrass=False, grass is NOT applied to the plate-1 fringe.

        Task 718 update: a plate-2 fringe grass sample is ALWAYS built with
        grass=True regardless of the checkbox — so the grass function IS called
        once (for plate 2). The assertion is updated to:
          - Exactly 1 call (plate-2 sample only) when enableFringeGrass=False.
          - NOT 0 calls (plate 2 unconditionally fires grass).
          - NOT 2+ calls (plate 1 was correctly skipped).

        The spirit of T10 — that unchecking the box suppresses grass on the main
        plaque fringe — is preserved; only the plate-2 sample always has grass.
        """
        import gradient_surface_diagnostic as gsd
        call_log: list[str] = []

        def _mock_v2(*args, **kwargs):
            call_log.append("v2")

        def _mock_v1(*args, **kwargs):
            call_log.append("v1")

        monkeypatch.setattr(gsd, "apply_grass_texture_v2", _mock_v2)
        monkeypatch.setattr(gsd, "apply_grass_texture", _mock_v1)

        try:
            gsd.run_pipeline(egm_file_false)
        except Exception:
            pass  # pipeline may fail on mock data; we only care about call counts

        # Task 718: plate-2 fringe sample always has grass → exactly 1 call.
        # If 0 calls: plate-2 sample was not built (regression).
        # If 2+ calls: plate-1 fringe was also grassed (enableFringeGrass=False ignored).
        assert len(call_log) == 1, (
            f"Expected exactly 1 grass call when enableFringeGrass=False "
            f"(plate-2 sample only); got {len(call_log)}: {call_log}. "
            "0 calls = plate-2 sample not built (regression). "
            "2+ calls = plate-1 fringe was also grassed (checkbox ignored)."
        )

    def test_grass_called_when_enabled(self, egm_file_true, monkeypatch):
        """T11: When enableFringeGrass=True, at least one grass function is called."""
        import gradient_surface_diagnostic as gsd
        call_log: list[str] = []

        def _mock_v2(*args, **kwargs):
            call_log.append("v2")

        def _mock_v1(*args, **kwargs):
            call_log.append("v1")

        monkeypatch.setattr(gsd, "apply_grass_texture_v2", _mock_v2)
        monkeypatch.setattr(gsd, "apply_grass_texture", _mock_v1)

        try:
            gsd.run_pipeline(egm_file_true)
        except Exception:
            pass  # pipeline may fail on mock data; we only care about call counts

        assert len(call_log) > 0, (
            "Grass functions were never called but enableFringeGrass=True — "
            "expected at least one call."
        )


# ─────────────────────────────────────────────────────────────────────────────
# T12: Regression — generate_models route passes enableFringeGrass
# ─────────────────────────────────────────────────────────────────────────────

class TestGenerateModelsRouteWiring:

    def test_route_reads_enable_fringe_grass(self):
        """T12: app.py generate_models route must extract enableFringeGrass from request."""
        with open(APP_PY) as f:
            src = f.read()
        assert "enableFringeGrass" in src, (
            "app.py generate_models does not handle enableFringeGrass. "
            "Add: enable_fringe_grass = bool(data.get('enableFringeGrass', True))"
        )

    def test_route_passes_to_run_pipeline(self):
        """T12b: app.py must pass enable_fringe_grass to run_pipeline()."""
        with open(APP_PY) as f:
            src = f.read()
        # After the change, run_pipeline call must include enable_fringe_grass
        assert "enable_fringe_grass" in src, (
            "app.py does not pass enable_fringe_grass to run_pipeline(). "
            "Add the kwarg to the run_pipeline() call in generate_models."
        )
