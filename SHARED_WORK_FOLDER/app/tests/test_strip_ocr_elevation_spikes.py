"""
test_strip_ocr_elevation_spikes.py — Bug→TDD for T5: strip numeric-marker
pipeline + G-badges + Add Spike + delete + elevationSpikes field (2026-10-02).

Thomas pivot: dropping the entire OCR → elevationSpikes → topology pipeline.
Fringe altitudes will come from a different mechanism later.

Tests describe the REDUCED API contract (RED first, then GREEN after strip).

Groups:
  A — /api/detect_boundaries has no elevationMarkers field
  B — editor.html has no G-badge markup, no Add Spike button, no × delete
  C — editor.html Alpine state has no elevationSpikes, no spikeMode
  D — EGM round-trip: save path does not write elevationSpikes; load
      tolerates (ignores) elevationSpikes in old EGMs without crashing
  E — golf_intel_ocr.py: extract_numeric_markers no longer importable
      (module deleted), OR module exists but has no markers entrypoint
  F — Regression: polygon detection still works end-to-end; autosave path
      still has polygons; APP_VERSION bumped to v4.98

Run:
    cd /Volumes/GIT/CLAUDE/SHARED_WORK_FOLDER
    python -m pytest app/tests/test_strip_ocr_elevation_spikes.py -v
"""
from __future__ import annotations

import importlib
import json
import re
import sys
from pathlib import Path

import pytest

# ---------------------------------------------------------------------------
# Path setup
# ---------------------------------------------------------------------------
APP_DIR = Path(__file__).parent.parent
REPO_ROOT = APP_DIR.parent
sys.path.insert(0, str(APP_DIR))

EDITOR_HTML_PATH = APP_DIR / "templates" / "editor.html"
APP_PY_PATH = APP_DIR / "app.py"
OCR_PY_PATH = APP_DIR / "golf_intel_ocr.py"


# ---------------------------------------------------------------------------
# Flask test-client fixture (temp DB — never touches live workspace.db)
# ---------------------------------------------------------------------------

@pytest.fixture()
def app_client(tmp_path, monkeypatch):
    """Flask test client with a temp DB and temp GolfCourses tree."""
    import app as _app_module
    tmp_db = str(tmp_path / "workspace.db")
    tmp_egm_base = str(tmp_path / "GolfCourses")
    monkeypatch.setattr(_app_module, "DB_PATH", tmp_db)
    monkeypatch.setattr(_app_module, "_EGM_BASE", tmp_egm_base)
    _app_module.app.config["TESTING"] = True
    with _app_module.app.test_client() as client:
        yield client


def _make_mock_image(tmp_path: Path) -> Path:
    """Write a small green-ish PNG to tmp_path and return its path."""
    import cv2
    import numpy as np
    img = np.zeros((100, 100, 3), dtype=np.uint8)
    img[:, :] = [100, 150, 80]
    p = tmp_path / "_strip_mock.png"
    cv2.imwrite(str(p), img)
    return p


# ===========================================================================
# A — /api/detect_boundaries has no elevationMarkers field
# ===========================================================================

class TestDetectBoundariesNoElevationMarkers:
    """
    A1 — After removal, /api/detect_boundaries must NOT return an
    'elevationMarkers' field.  The field should be absent (or absent).
    """

    def test_no_elevation_markers_in_response(self, app_client, tmp_path, monkeypatch):
        """A1 — elevationMarkers field absent from detect_boundaries response."""
        import app as _app_module
        img_path = _make_mock_image(tmp_path)
        monkeypatch.setattr(
            _app_module, "_find_image_path",
            lambda name, preferred_course="": str(img_path),
        )
        resp = app_client.post(
            "/api/detect_boundaries",
            data=json.dumps({"image": "_strip_mock.png", "course": "TestCourse"}),
            content_type="application/json",
        )
        assert resp.status_code == 200
        data = resp.get_json()
        assert data.get("status") == "ok", f"detect_boundaries error: {data}"
        assert "elevationMarkers" not in data, (
            f"detect_boundaries still returns elevationMarkers after OCR strip: "
            f"{data.get('elevationMarkers')}"
        )

    def test_no_elevation_spikes_in_response(self, app_client, tmp_path, monkeypatch):
        """A2 — elevationSpikes field also absent from detect_boundaries response."""
        import app as _app_module
        img_path = _make_mock_image(tmp_path)
        monkeypatch.setattr(
            _app_module, "_find_image_path",
            lambda name, preferred_course="": str(img_path),
        )
        resp = app_client.post(
            "/api/detect_boundaries",
            data=json.dumps({"image": "_strip_mock.png", "course": "TestCourse"}),
            content_type="application/json",
        )
        assert resp.status_code == 200
        data = resp.get_json()
        assert "elevationSpikes" not in data, (
            f"detect_boundaries still returns elevationSpikes in response."
        )

    def test_polygons_still_present_in_response(self, app_client, tmp_path, monkeypatch):
        """A3 — Regression: polygons field still present (core detection not broken)."""
        import app as _app_module
        img_path = _make_mock_image(tmp_path)
        monkeypatch.setattr(
            _app_module, "_find_image_path",
            lambda name, preferred_course="": str(img_path),
        )
        resp = app_client.post(
            "/api/detect_boundaries",
            data=json.dumps({"image": "_strip_mock.png", "course": "TestCourse"}),
            content_type="application/json",
        )
        assert resp.status_code == 200
        data = resp.get_json()
        assert "polygons" in data, (
            "detect_boundaries response is missing 'polygons' — core detection broken."
        )


# ===========================================================================
# B — editor.html has no G-badge markup, no Add Spike, no × delete
# ===========================================================================

class TestEditorHtmlNoGBadge:
    """
    B — After removal, editor.html must have no G-badge template, no
    'Add Spike' button, no × delete affordance.
    """

    @pytest.fixture(scope="class")
    def html(self):
        return EDITOR_HTML_PATH.read_text(encoding="utf-8")

    def test_no_gbadge_xfor_loop(self, html):
        """B1 — No x-for loop over elevationSpikes in editor.html."""
        has_xfor = bool(re.search(r'x-for[^>]+elevationSpikes', html))
        assert not has_xfor, (
            "editor.html still has x-for loop over elevationSpikes — G-badge template not removed."
        )

    def test_no_add_spike_button(self, html):
        """B2 — No 'Add Spike' button text in editor.html."""
        assert "Add Spike" not in html, (
            "editor.html still contains 'Add Spike' button — not removed."
        )

    def test_no_start_spike_placement(self, html):
        """B3 — startSpikePlacement() method removed from editor.html."""
        assert "startSpikePlacement" not in html, (
            "editor.html still references startSpikePlacement() — Add Spike not fully removed."
        )

    def test_no_remove_elevation_spike(self, html):
        """B4 — removeElevationSpike() removed (× delete affordance from T4)."""
        assert "removeElevationSpike" not in html, (
            "editor.html still contains removeElevationSpike() — × delete not removed."
        )

    def test_no_spike_edit_start(self, html):
        """B5 — spikeEditStart() removed."""
        assert "spikeEditStart" not in html, (
            "editor.html still contains spikeEditStart() — G-badge inline edit not removed."
        )

    def test_no_spike_edit_commit(self, html):
        """B6 — spikeEditCommit() removed."""
        assert "spikeEditCommit" not in html, (
            "editor.html still contains spikeEditCommit() — G-badge inline edit not removed."
        )

    def test_no_spike_edit_cancel(self, html):
        """B7 — spikeEditCancel() removed."""
        assert "spikeEditCancel" not in html, (
            "editor.html still contains spikeEditCancel() — G-badge inline edit not removed."
        )

    def test_no_ocr_status_strip(self, html):
        """B8 — OCR detection status strip removed (G detected count)."""
        assert "G detected" not in html, (
            "editor.html still shows 'G detected' OCR status strip — not removed."
        )

    def test_no_spike_placement_hint_banner(self, html):
        """B9 — Spike placement mode hint banner removed."""
        assert "Click to place a spike" not in html, (
            "editor.html still shows spike placement hint banner — not removed."
        )

    def test_no_crosshair_spike_cursor(self, html):
        """B10 — spikeMode cursor:crosshair style binding removed."""
        # The old binding was: :style="spikeMode ? 'cursor: crosshair;' : ..."
        has_spike_crosshair = bool(re.search(r"spikeMode.*crosshair", html))
        assert not has_spike_crosshair, (
            "editor.html still has spikeMode-driven crosshair cursor binding — not removed."
        )

    def test_no_g_letter_badge_div(self, html):
        """B11 — The 'G' letter badge div (inner label) removed."""
        # The badge had: <div ... >G</div> immediately preceding the spike input
        # Check for the specific G-badge interior letter div pattern
        has_g_badge_letter = bool(re.search(r'>\s*G\s*</div>\s*<input[^>]+data-spike-input', html, re.DOTALL))
        assert not has_g_badge_letter, (
            "editor.html still contains the G-badge letter div before spike input."
        )

    def test_elev_spike_legend_entry_removed(self, html):
        """B12 — 'Elev spike' legend entry removed from region legend."""
        assert "Elev spike" not in html, (
            "editor.html still has 'Elev spike' entry in the region legend — not removed."
        )


# ===========================================================================
# C — Alpine state: no elevationSpikes, no spikeMode
# ===========================================================================

class TestAlpineStateNoSpikes:
    """
    C — editor.html Alpine state must not declare elevationSpikes or spikeMode.
    """

    @pytest.fixture(scope="class")
    def html(self):
        return EDITOR_HTML_PATH.read_text(encoding="utf-8")

    def test_no_elevation_spikes_state(self, html):
        """C1 — elevationSpikes state field removed from Alpine x-data."""
        # Should not appear as a state declaration (e.g.  "elevationSpikes: []")
        has_state = bool(re.search(r'elevationSpikes\s*:', html))
        assert not has_state, (
            "editor.html still declares elevationSpikes: in Alpine state — not removed."
        )

    def test_no_spike_mode_state(self, html):
        """C2 — spikeMode state field removed from Alpine x-data."""
        has_state = bool(re.search(r'spikeMode\s*:', html))
        assert not has_state, (
            "editor.html still declares spikeMode: in Alpine state — not removed."
        )

    def test_no_spike_drag_state(self, html):
        """C3 — _spikeDrag internal state removed."""
        has_state = bool(re.search(r'_spikeDrag\s*:', html))
        assert not has_state, (
            "editor.html still declares _spikeDrag: in Alpine state — not removed."
        )

    def test_no_spike_edit_prev_state(self, html):
        """C4 — _spikeEditPrev internal state removed."""
        has_state = bool(re.search(r'_spikeEditPrev\s*:', html))
        assert not has_state, (
            "editor.html still declares _spikeEditPrev: in Alpine state — not removed."
        )


# ===========================================================================
# D — EGM round-trip: save doesn't write elevationSpikes; load tolerates it
# ===========================================================================

class TestEgmRoundTrip:
    """
    D — After removal, save path must NOT write elevationSpikes to EGM.
    Load path must silently ignore elevationSpikes if present in old EGM (no crash).
    """

    @pytest.fixture(scope="class")
    def html(self):
        return EDITOR_HTML_PATH.read_text(encoding="utf-8")

    def test_save_path_no_elevation_spikes(self, html):
        """D1 — autoSave payload no longer includes elevationSpikes field."""
        # Old code: elevationSpikes: this.elevationSpikes.map(...)
        save_pattern = re.compile(
            r'elevationSpikes\s*:\s*this\.elevationSpikes',
            re.DOTALL,
        )
        assert not save_pattern.search(html), (
            "editor.html autoSave payload still serializes this.elevationSpikes — save path not cleaned."
        )

    def test_load_path_no_elevation_spikes_population(self, html):
        """D2 — loadProject() no longer populates this.elevationSpikes from EGM data."""
        # Old code: this.elevationSpikes = Array.isArray(data.elevationSpikes) ? ...
        load_pattern = re.compile(
            r'this\.elevationSpikes\s*=\s*Array\.isArray\s*\(\s*data\.elevationSpikes',
            re.DOTALL,
        )
        assert not load_pattern.search(html), (
            "editor.html loadProject still populates this.elevationSpikes from EGM — load path not cleaned."
        )

    def test_load_old_egm_with_elevation_spikes_via_api(self, app_client, tmp_path, monkeypatch):
        """D3 — Loading an old EGM with elevationSpikes field does not crash the app."""
        import app as _app_module

        # Create a minimal EGM with elevationSpikes field (old format).
        # The load route searches <course>/EGMs/<filename>, so we must create the EGMs subdir.
        egms_dir = tmp_path / "GolfCourses" / "TestCourse" / "EGMs"
        egms_dir.mkdir(parents=True)
        egm_path = egms_dir / "TestCourse (Hole 1, 99999).egm"
        old_egm = {
            "course": "TestCourse",
            "hole": "1",
            "image": "dummy.png",
            "imageSize": {"width": 400, "height": 400},
            "polygons": [],
            "elevationSpikes": [{"x": 100, "y": 100, "mm": 5.0, "source": "ocr"}],
        }
        egm_path.write_text(json.dumps(old_egm))
        monkeypatch.setattr(_app_module, "_EGM_BASE", str(tmp_path / "GolfCourses"))

        resp = app_client.get(
            "/api/boundaries/load",
            query_string={"filename": "TestCourse (Hole 1, 99999).egm"},
        )
        # Should succeed — old elevationSpikes field tolerated silently
        assert resp.status_code == 200, (
            f"Loading old EGM with elevationSpikes crashed the app: {resp.get_json()}"
        )
        data = resp.get_json()
        assert data.get("status") == "ok", (
            f"Load returned error: {data}"
        )


# ===========================================================================
# E — golf_intel_ocr.py: extract_numeric_markers no longer accessible
# ===========================================================================

class TestOCRModuleDeleted:
    """
    E — After removal, extract_numeric_markers must not be importable
    (module deleted), OR the module exists but exposes no numeric-marker
    extraction entrypoint.
    """

    def test_extract_numeric_markers_not_importable(self):
        """E1 — extract_numeric_markers is no longer importable."""
        try:
            from golf_intel_ocr import extract_numeric_markers  # noqa: F401
            pytest.fail(
                "golf_intel_ocr.extract_numeric_markers is still importable — "
                "OCR module not deleted / entrypoint not removed."
            )
        except (ImportError, ModuleNotFoundError):
            pass  # expected: module deleted

    def test_markers_to_elevation_spikes_removed_from_app(self):
        """E2 — markers_to_elevation_spikes() removed from app.py source."""
        src = APP_PY_PATH.read_text(encoding="utf-8")
        assert "markers_to_elevation_spikes" not in src, (
            "app.py still contains markers_to_elevation_spikes() — OCR wiring not removed."
        )

    def test_clamp_ocr_value_removed_from_app(self):
        """E3 — clamp_ocr_value() removed from app.py source."""
        src = APP_PY_PATH.read_text(encoding="utf-8")
        assert "clamp_ocr_value" not in src, (
            "app.py still contains clamp_ocr_value() — OCR helper not removed."
        )

    def test_classify_ocr_markers_removed_from_app(self):
        """E4 — classify_ocr_markers() removed from app.py source (became dead code)."""
        src = APP_PY_PATH.read_text(encoding="utf-8")
        assert "classify_ocr_markers" not in src, (
            "app.py still contains classify_ocr_markers() — OCR wiring not removed."
        )

    def test_no_extract_ocr_import_in_detect_boundaries(self):
        """E5 — app.py detect_boundaries no longer imports extract_numeric_markers."""
        src = APP_PY_PATH.read_text(encoding="utf-8")
        assert "from golf_intel_ocr import extract_numeric_markers" not in src, (
            "app.py still imports extract_numeric_markers inside detect_boundaries."
        )

    def test_ocr_module_file_deleted(self):
        """E6 — golf_intel_ocr.py file has been deleted from app/."""
        assert not OCR_PY_PATH.exists(), (
            f"golf_intel_ocr.py still exists at {OCR_PY_PATH} — module not deleted."
        )


# ===========================================================================
# F — Regression: polygon detection + autosave path still intact
# ===========================================================================

class TestRegressionPolygonDetection:
    """
    F — Core polygon detection and save path must remain intact after OCR strip.
    """

    @pytest.fixture(scope="class")
    def html(self):
        return EDITOR_HTML_PATH.read_text(encoding="utf-8")

    def test_detect_boundaries_still_returns_polygons(self, app_client, tmp_path, monkeypatch):
        """F1 — /api/detect_boundaries still returns a polygons array."""
        import app as _app_module
        img_path = _make_mock_image(tmp_path)
        monkeypatch.setattr(
            _app_module, "_find_image_path",
            lambda name, preferred_course="": str(img_path),
        )
        resp = app_client.post(
            "/api/detect_boundaries",
            data=json.dumps({"image": "_strip_mock.png", "course": "TestCourse"}),
            content_type="application/json",
        )
        assert resp.status_code == 200
        data = resp.get_json()
        assert "polygons" in data and isinstance(data["polygons"], list), (
            "detect_boundaries no longer returns a polygons list — core detection broken."
        )

    def test_app_version_bumped(self):
        """F2 — APP_VERSION bumped at or beyond v4.99 in app.py (task 700+).
        Updated: task 702 bumped to v5.00; accept any version ≥ v4.99."""
        src = APP_PY_PATH.read_text(encoding="utf-8")
        m = re.search(r'APP_VERSION\s*=\s*["\']v(\d+)\.(\d+)["\']', src)
        assert m is not None, "APP_VERSION not found in app.py"
        major, minor = int(m.group(1)), int(m.group(2))
        version_ok = (major > 4) or (major == 4 and minor >= 99)
        assert version_ok, (
            f"APP_VERSION v{major}.{minor} not at or beyond v4.99"
        )

    def test_editor_version_string_bumped(self, html):
        """F3 — On-page version string in editor.html ≥ v4.98.
        Updated: task 702 set v5.00; accept any version beyond v4.97."""
        m = re.search(r'Boundary Editor v(\d+)\.(\d+)', html)
        assert m is not None, "No 'Boundary Editor vX.XX' version string in editor.html"
        major, minor = int(m.group(1)), int(m.group(2))
        version_ok = (major > 4) or (major == 4 and minor >= 98)
        assert version_ok, (
            f"editor.html version v{major}.{minor} not at or beyond v4.98"
        )

    def test_autosave_still_has_polygons(self, html):
        """F4 — autoSave payload still serializes polygons."""
        assert "polygons" in html, (
            "editor.html no longer references 'polygons' in save path — autosave broken."
        )

    def test_tee_hole_still_present(self, html):
        """F5 — teeHole state and marker still present (not accidentally removed)."""
        assert "teeHole" in html, (
            "editor.html no longer references teeHole — accidentally removed with spike code."
        )
