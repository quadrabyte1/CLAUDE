"""
test_strip_exterior_ocr.py — Bug→TDD for T2: removal of exterior OCR / fringe
anchor pipeline (task 691, Sienna 2026-10-02).

Semantic pivot: exterior ring numbers (10,15,20,25,30) are distance-from-pin
markers, NOT altitude values.  The fringeBoundaryHeights → F-badge → fringe
anchor pipeline is semantically wrong and is being torn out.

These tests are RED first.  They describe the *reduced* API contract.
Run:
    cd /Volumes/GIT/CLAUDE/SHARED_WORK_FOLDER
    python -m pytest app/tests/test_strip_exterior_ocr.py -v
"""
from __future__ import annotations

import json
import re
import sys
from pathlib import Path

import pytest

# T5 (2026-10-03): Full OCR pipeline stripped — golf_intel_ocr.py deleted, G-badge removed.
# T2's regression assertions (extract_numeric_markers still importable, G-badge present) are
# now superseded by T5's full strip. Tombstone this entire file.
pytestmark = pytest.mark.skip(reason="T5 supersedes T2: full OCR strip completed, exterior+interior pipeline gone")

# ---------------------------------------------------------------------------
# Path setup
# ---------------------------------------------------------------------------
APP_DIR = Path(__file__).parent.parent
REPO_ROOT = APP_DIR.parent
sys.path.insert(0, str(APP_DIR))

EDITOR_HTML_PATH = APP_DIR / "templates" / "editor.html"
APP_PY_PATH = APP_DIR / "app.py"
OCR_PY_PATH = APP_DIR / "golf_intel_ocr.py"

_DL_H5 = REPO_ROOT / "ItWentIn/GolfCourses/Delaveaga/Images/Delaveaga (Hole 5, 55169).png"


# ---------------------------------------------------------------------------
# Flask test-client fixture (temp DB — never touches live workspace.db)
# ---------------------------------------------------------------------------

@pytest.fixture()
def app_client(tmp_path, monkeypatch):
    """Flask test client with a temp DB."""
    import app as _app_module
    tmp_db = str(tmp_path / "workspace.db")
    tmp_egm_base = str(tmp_path / "GolfCourses")
    monkeypatch.setattr(_app_module, "DB_PATH", tmp_db)
    monkeypatch.setattr(_app_module, "_EGM_BASE", tmp_egm_base)
    _app_module.app.config["TESTING"] = True
    with _app_module.app.test_client() as client:
        yield client


# ---------------------------------------------------------------------------
# C1 — /api/detect_boundaries returns no fringeBoundaryHeights (absent or [])
# ---------------------------------------------------------------------------

class TestDetectBoundariesNoFringeBoundaryHeights:
    """
    C1 — After removal, detect_boundaries response must NOT return
    fringeBoundaryHeights with content.  The field may be absent or empty.
    """

    @pytest.mark.skipif(not _DL_H5.exists(), reason="DeLaveaga Hole 5 image not present")
    def test_no_fringe_boundary_heights_in_response(self, app_client, monkeypatch):
        """C1a — fringeBoundaryHeights absent or empty in detect_boundaries response."""
        import app as _app_module
        monkeypatch.setattr(
            _app_module, "_find_image_path",
            lambda name, preferred_course="": str(_DL_H5),
        )
        resp = app_client.post(
            "/api/detect_boundaries",
            data=json.dumps({
                "image": "Delaveaga (Hole 5, 55169).png",
                "course": "Delaveaga",
                "imageCourse": "Delaveaga",
            }),
            content_type="application/json",
        )
        assert resp.status_code == 200
        data = resp.get_json()
        assert data.get("status") == "ok", f"detect_boundaries error: {data}"
        fbh = data.get("fringeBoundaryHeights", [])
        assert fbh == [], (
            f"fringeBoundaryHeights should be absent or empty after exterior OCR removal, "
            f"got {len(fbh)} entries: {fbh}"
        )

    def test_mock_detect_boundaries_no_fringe_boundary_heights(self, app_client, monkeypatch):
        """C1b — Mock OCR response also has no fringeBoundaryHeights."""
        import app as _app_module
        # Mock out the OCR so test runs without real image
        monkeypatch.setattr(
            _app_module, "_find_image_path",
            lambda name, preferred_course="": str(APP_DIR / "tests" / "__init__.py"),  # dummy
        )
        import io
        import numpy as np
        import cv2

        # Build a tiny mock image (green square)
        mock_img = np.zeros((100, 100, 3), dtype=np.uint8)
        mock_img[:, :] = [100, 150, 80]
        _, buf = cv2.imencode(".png", mock_img)
        tmp_img = Path(APP_DIR) / "tests" / "_mock_detect_img.png"
        tmp_img.write_bytes(buf.tobytes())

        try:
            monkeypatch.setattr(
                _app_module, "_find_image_path",
                lambda name, preferred_course="": str(tmp_img),
            )
            resp = app_client.post(
                "/api/detect_boundaries",
                data=json.dumps({"image": "_mock_detect_img.png", "course": "TestCourse"}),
                content_type="application/json",
            )
            assert resp.status_code == 200
            data = resp.get_json()
            fbh = data.get("fringeBoundaryHeights", [])
            assert fbh == [], (
                f"detect_boundaries returned non-empty fringeBoundaryHeights "
                f"on mock call: {fbh}"
            )
        finally:
            tmp_img.unlink(missing_ok=True)


# ---------------------------------------------------------------------------
# C2 — OCR module has no exterior pass / no _EXT_ constants
# ---------------------------------------------------------------------------

class TestOCRModuleNoExteriorPass:
    """
    C2 — golf_intel_ocr.py must not expose _EXT_* constants or
    extract_numeric_markers_with_exterior after the removal.
    """

    @pytest.fixture(scope="class")
    def ocr_src(self):
        return OCR_PY_PATH.read_text(encoding="utf-8")

    def test_no_ext_constants(self, ocr_src):
        """C2a — No _EXT_ prefixed constants in golf_intel_ocr.py."""
        ext_matches = re.findall(r'\b_EXT_\w+', ocr_src)
        assert ext_matches == [], (
            f"golf_intel_ocr.py still has _EXT_ constants: {ext_matches}"
        )

    def test_no_extract_numeric_markers_with_exterior(self, ocr_src):
        """C2b — extract_numeric_markers_with_exterior removed from golf_intel_ocr.py."""
        assert "extract_numeric_markers_with_exterior" not in ocr_src, (
            "golf_intel_ocr.py still exports extract_numeric_markers_with_exterior — "
            "the exterior pass was not removed."
        )

    def test_no_pass_b_exterior_function(self, ocr_src):
        """C2c — _pass_b_exterior function removed from golf_intel_ocr.py."""
        assert "_pass_b_exterior" not in ocr_src, (
            "golf_intel_ocr.py still contains _pass_b_exterior — exterior pass not removed."
        )

    def test_no_exterior_valid_ints(self, ocr_src):
        """C2d — _EXTERIOR_VALID_INTS removed from golf_intel_ocr.py."""
        assert "_EXTERIOR_VALID_INTS" not in ocr_src, (
            "golf_intel_ocr.py still contains _EXTERIOR_VALID_INTS."
        )


# ---------------------------------------------------------------------------
# C3 — Editor HTML contains NO F-badge markup
# ---------------------------------------------------------------------------

class TestEditorHtmlNoFBadge:
    """
    C3 — editor.html must have no F-badge template markup after removal.
    """

    @pytest.fixture(scope="class")
    def editor_html(self):
        return EDITOR_HTML_PATH.read_text(encoding="utf-8")

    def test_no_data_fringe_anchor(self, editor_html):
        """C3a — No data-fringe-anchor attribute in editor.html."""
        assert "data-fringe-anchor" not in editor_html, (
            "editor.html still contains data-fringe-anchor — F-badge not removed."
        )

    def test_no_fringe_xfor_loop(self, editor_html):
        """C3b — No x-for loop over fringeBoundaryHeights for badge rendering."""
        # The loop pattern: x-for="... in fringeBoundaryHeights"
        has_xfor = bool(re.search(r'x-for[^>]+fringeBoundaryHeights', editor_html))
        assert not has_xfor, (
            "editor.html still has an x-for loop over fringeBoundaryHeights — "
            "F-badge template not removed."
        )

    def test_no_anchor_edit_methods(self, editor_html):
        """C3c — anchorEditStart/Commit/Cancel methods removed."""
        for fn_name in ("anchorEditStart", "anchorEditCommit", "anchorEditCancel"):
            assert fn_name not in editor_html, (
                f"editor.html still contains {fn_name}() — orphaned anchor edit method not removed."
            )


# ---------------------------------------------------------------------------
# C4 — OCR status strip shows only G count (no F count)
# ---------------------------------------------------------------------------

class TestStatusStripGOnly:
    """
    C4 — After removal, status strip shows G-badge count only.
    No reference to F count or fringeBoundaryHeights.length in strip.
    """

    @pytest.fixture(scope="class")
    def editor_html(self):
        return EDITOR_HTML_PATH.read_text(encoding="utf-8")

    def test_status_strip_no_fringeboundaryheights_length(self, editor_html):
        """C4a — Status strip x-text no longer references fringeBoundaryHeights.length."""
        # The strip area is between "OCR detection status strip" and
        # "── Elevation-spike overlays"
        strip_area = _extract_section(
            editor_html,
            "OCR detection status strip",
            "── Elevation-spike overlays",
        )
        assert strip_area, "Could not find OCR status strip section in editor.html"
        assert "fringeBoundaryHeights.length" not in strip_area, (
            "Status strip still references fringeBoundaryHeights.length — "
            "F count not removed from strip."
        )

    def test_status_strip_still_shows_g_count(self, editor_html):
        """C4b — Status strip still references elevationSpikes.length (G count)."""
        strip_area = _extract_section(
            editor_html,
            "OCR detection status strip",
            "── Elevation-spike overlays",
        )
        assert "elevationSpikes.length" in strip_area, (
            "Status strip no longer references elevationSpikes.length — "
            "G count was accidentally removed."
        )


# ---------------------------------------------------------------------------
# C5 — EGM round-trip: save path drops fringeBoundaryHeights
# ---------------------------------------------------------------------------

class TestEgmRoundTripNoFringeBoundaryHeights:
    """
    C5 — EGM save path must not write fringeBoundaryHeights.
    Load path must gracefully ignore fringeBoundaryHeights if present in old EGM.
    """

    @pytest.fixture(scope="class")
    def editor_html(self):
        return EDITOR_HTML_PATH.read_text(encoding="utf-8")

    def test_egm_save_path_no_fringeboundaryheights(self, editor_html):
        """C5a — autoSave data object no longer includes fringeBoundaryHeights."""
        # Look for the buildEgmData / save payload block; it should not include
        # fringeBoundaryHeights: this.fringeBoundaryHeights...
        # We check the JS save payload patterns
        save_pattern = re.compile(
            r'fringeBoundaryHeights\s*:\s*this\.fringeBoundaryHeights',
            re.DOTALL,
        )
        assert not save_pattern.search(editor_html), (
            "editor.html autoSave payload still includes fringeBoundaryHeights — "
            "EGM save path not cleaned."
        )

    def test_egm_load_path_no_fringe_state_population(self, editor_html):
        """C5b — EGM load path (loadProject) no longer populates fringeBoundaryHeights state."""
        # The load path had:
        #   this.fringeBoundaryHeights = Array.isArray(data.fringeBoundaryHeights) ? ...
        # This should be removed (or the state field itself should be gone).
        load_pattern = re.compile(
            r'this\.fringeBoundaryHeights\s*=\s*Array\.isArray\s*\(\s*data\.fringeBoundaryHeights',
            re.DOTALL,
        )
        assert not load_pattern.search(editor_html), (
            "editor.html loadProject still populates this.fringeBoundaryHeights from EGM — "
            "load path not cleaned."
        )


# ---------------------------------------------------------------------------
# C6 — Regression: interior OCR + G-badges still work
# ---------------------------------------------------------------------------

class TestInteriorOCRRegression:
    """
    C6 — Interior OCR (elevationSpikes / G-badges) must remain fully intact.
    """

    @pytest.fixture(scope="class")
    def editor_html(self):
        return EDITOR_HTML_PATH.read_text(encoding="utf-8")

    def test_extract_numeric_markers_still_importable(self):
        """C6a — extract_numeric_markers is still importable from golf_intel_ocr."""
        from golf_intel_ocr import extract_numeric_markers  # noqa: F401

    def test_g_badge_xfor_loop_still_present(self, editor_html):
        """C6b — x-for loop over elevationSpikes (G-badges) still present."""
        has_xfor = bool(re.search(r'x-for[^>]+elevationSpikes', editor_html))
        assert has_xfor, (
            "editor.html x-for loop over elevationSpikes was accidentally removed."
        )

    def test_elevation_spikes_state_still_present(self, editor_html):
        """C6c — elevationSpikes state field still present in Alpine data."""
        assert "elevationSpikes" in editor_html, (
            "editor.html no longer references elevationSpikes — state removed accidentally."
        )

    def test_detect_boundaries_returns_elevation_markers(self, app_client, monkeypatch):
        """C6d — detect_boundaries response still includes elevationMarkers field."""
        import app as _app_module
        import numpy as np
        import cv2

        # Build a tiny mock image
        mock_img = np.zeros((100, 100, 3), dtype=np.uint8)
        mock_img[:, :] = [100, 150, 80]
        _, buf = cv2.imencode(".png", mock_img)
        tmp_img = APP_DIR / "tests" / "_mock_c6_img.png"
        tmp_img.write_bytes(buf.tobytes())

        try:
            monkeypatch.setattr(
                _app_module, "_find_image_path",
                lambda name, preferred_course="": str(tmp_img),
            )
            resp = app_client.post(
                "/api/detect_boundaries",
                data=json.dumps({"image": "_mock_c6_img.png", "course": "TestCourse"}),
                content_type="application/json",
            )
            assert resp.status_code == 200
            data = resp.get_json()
            assert "elevationMarkers" in data, (
                "detect_boundaries response missing elevationMarkers — interior OCR path broken."
            )
        finally:
            tmp_img.unlink(missing_ok=True)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _extract_section(html: str, start_marker: str, end_marker: str) -> str:
    """Extract HTML between two markers."""
    start = html.find(start_marker)
    if start == -1:
        return ""
    end = html.find(end_marker, start + len(start_marker))
    if end == -1:
        return html[start:]
    return html[start:end]
