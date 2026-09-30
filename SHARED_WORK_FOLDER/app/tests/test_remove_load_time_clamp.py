"""
test_remove_load_time_clamp.py — Bug→TDD: remove load-time off-frame clamp

Thomas's requirement: control points dragged outside the PNG frame must survive
a project round-trip (close + reopen) unchanged. The load-time clamp in
load_boundaries() and the JS belt-and-suspenders in loadProject() was silently
destroying those intentional placements.

What is REMOVED (load-time path):
  - Python: the block in load_boundaries() that calls _clamp_polygon_points on
    every polygon and returns off_frame_count in the response.
  - JS: the off_frame_count / clampPt belt-and-suspenders block in loadProject().
  - JS: the toast + _pendingAutoSave = true triggered by off-frame healing.

What is PRESERVED (generation-time path):
  - _clamp_point_to_image() helper — still used by detect_boundaries.
  - _clamp_polygon_points() helper — still used by detect_boundaries.
  - The clamp applied inside detect_boundaries to auto-analyzed output.

Tests
-----
NL1  Off-frame point survives round-trip — load_boundaries returns raw coords.
NL2  off_frame_count absent or 0 unconditionally.
NL3  Legacy EGM without imageSize — loads without error; off-frame coords kept.
NL4  Regression: detect_boundaries still clamps auto-analyzed points to frame.
NL5  JS source — no JS-side clamp (clampPt / Math.min+max on loaded points)
     inside loadProject().
NL6  JS source — no _pendingAutoSave = true from off-frame handling in
     loadProject().
NL7  JS source — no "Clamped … off-frame" toast in loadProject().
"""
import json
import os
import re
import sys
import tempfile
import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

EDITOR_HTML = os.path.join(os.path.dirname(__file__), "..", "templates", "editor.html")


def _read_editor_js():
    with open(EDITOR_HTML, "r") as f:
        return f.read()


def _load_project_body():
    src = _read_editor_js()
    m = re.search(r'async loadProject\s*\(proj\)\s*\{(.+?)^\s*\},',
                  src, re.DOTALL | re.MULTILINE)
    assert m, "loadProject() not found in editor.html"
    return m.group(1)


# ─────────────────────────────────────────────────────────────────────────────
# Fixtures
# ─────────────────────────────────────────────────────────────────────────────

@pytest.fixture()
def egm_with_offframe(tmp_path, monkeypatch):
    """EGM with a point at y = image_height + 100 (clearly off-frame)."""
    iw, ih = 1200, 800
    egm_data = {
        "course": "Stanford",
        "hole": "8",
        "image": "stanford_h8.jpg",
        "imageCourse": "Stanford",
        "imageSize": {"width": iw, "height": ih},
        "polygons": [
            {
                "type": "green",
                "name": "Green",
                "points": [
                    {"x": 100, "y": 100},
                    {"x": 200, "y": ih + 100},   # OFF-FRAME: y = 900 on 800-tall image
                    {"x": -50, "y": 400},         # OFF-FRAME: x < 0
                    {"x": 400, "y": 300},
                ],
            },
        ],
        "contourStep": 0.5,
    }
    egm_dir = tmp_path / "GolfCourses" / "Stanford" / "EGMs"
    egm_dir.mkdir(parents=True)
    fname = "Stanford (Hole 08).egm"
    (egm_dir / fname).write_text(json.dumps(egm_data))

    import app as _app_module
    monkeypatch.setattr(_app_module, "DB_PATH", str(tmp_path / "workspace.db"))
    monkeypatch.setattr(_app_module, "_EGM_BASE", str(tmp_path / "GolfCourses"))
    _app_module.app.config["TESTING"] = True
    with _app_module.app.test_client() as client:
        yield client, fname, egm_data, iw, ih


@pytest.fixture()
def egm_without_imagesize(tmp_path, monkeypatch):
    """Legacy EGM with no imageSize key and an off-frame point."""
    egm_data = {
        "course": "Delaveaga",
        "hole": "3",
        "image": "delaveaga_h3.jpg",
        "imageCourse": "Delaveaga",
        # No imageSize key — legacy format
        "polygons": [
            {
                "type": "green",
                "name": "Green",
                "points": [
                    {"x": 100, "y": 100},
                    {"x": 200, "y": 9999},   # way off-frame — must be preserved
                    {"x": 300, "y": 300},
                ],
            },
        ],
        "contourStep": 0.5,
    }
    egm_dir = tmp_path / "GolfCourses" / "Delaveaga" / "EGMs"
    egm_dir.mkdir(parents=True)
    fname = "Delaveaga (Hole 03).egm"
    (egm_dir / fname).write_text(json.dumps(egm_data))

    import app as _app_module
    monkeypatch.setattr(_app_module, "DB_PATH", str(tmp_path / "workspace.db"))
    monkeypatch.setattr(_app_module, "_EGM_BASE", str(tmp_path / "GolfCourses"))
    _app_module.app.config["TESTING"] = True
    with _app_module.app.test_client() as client:
        yield client, fname, egm_data


# ─────────────────────────────────────────────────────────────────────────────
# NL1: Off-frame point survives round-trip
# ─────────────────────────────────────────────────────────────────────────────

class TestOffFramePointSurvivesLoad:

    def test_offframe_y_preserved(self, egm_with_offframe):
        """NL1a: y = image_height + 100 must come back unchanged from load_boundaries."""
        client, fname, egm_data, iw, ih = egm_with_offframe
        resp = client.get(f"/api/boundaries/load?filename={fname}")
        assert resp.status_code == 200
        data = resp.get_json()
        assert data["status"] == "ok"

        # Find the off-frame point (y = ih + 100 = 900)
        expected_y = ih + 100
        pts = data["polygons"][0]["points"]
        offframe_pt = next((p for p in pts if p["y"] == expected_y), None)
        assert offframe_pt is not None, (
            f"Off-frame point (y={expected_y}) was clamped or removed on load. "
            f"Returned points: {pts}. "
            "load_boundaries must NOT clamp polygon points — return raw EGM coords."
        )

    def test_offframe_negative_x_preserved(self, egm_with_offframe):
        """NL1b: x = -50 (left of frame) must come back unchanged."""
        client, fname, egm_data, iw, ih = egm_with_offframe
        resp = client.get(f"/api/boundaries/load?filename={fname}")
        data = resp.get_json()

        pts = data["polygons"][0]["points"]
        offframe_pt = next((p for p in pts if p["x"] == -50), None)
        assert offframe_pt is not None, (
            f"Off-frame point (x=-50) was clamped or removed on load. "
            f"Returned points: {pts}. "
            "load_boundaries must NOT clamp polygon points."
        )

    def test_inframe_points_also_preserved(self, egm_with_offframe):
        """NL1c: In-frame points are unchanged too (not accidentally mutated)."""
        client, fname, egm_data, iw, ih = egm_with_offframe
        resp = client.get(f"/api/boundaries/load?filename={fname}")
        data = resp.get_json()

        pts = data["polygons"][0]["points"]
        pt100 = next((p for p in pts if p["x"] == 100 and p["y"] == 100), None)
        assert pt100 is not None, (
            "In-frame point (100, 100) missing from load response. "
            f"Returned points: {pts}"
        )


# ─────────────────────────────────────────────────────────────────────────────
# NL2: off_frame_count absent or 0 unconditionally
# ─────────────────────────────────────────────────────────────────────────────

class TestOffFrameCountAbsentOrZero:

    def test_no_offframe_count_or_zero(self, egm_with_offframe):
        """NL2: off_frame_count is absent or 0 even when EGM has off-frame points."""
        client, fname, egm_data, iw, ih = egm_with_offframe
        resp = client.get(f"/api/boundaries/load?filename={fname}")
        assert resp.status_code == 200
        data = resp.get_json()

        count = data.get("off_frame_count", 0)
        assert count == 0, (
            f"off_frame_count={count} — load_boundaries must NOT count or report "
            "off-frame points after the load-time clamp is removed. "
            "Set off_frame_count=0 always, or omit the field entirely."
        )


# ─────────────────────────────────────────────────────────────────────────────
# NL3: Legacy EGM without imageSize — loads without error; coords preserved
# ─────────────────────────────────────────────────────────────────────────────

class TestLegacyEGMWithoutImageSize:

    def test_loads_without_error(self, egm_without_imagesize):
        """NL3a: EGM with no imageSize must load with status=ok."""
        client, fname, egm_data = egm_without_imagesize
        resp = client.get(f"/api/boundaries/load?filename={fname}")
        assert resp.status_code == 200
        data = resp.get_json()
        assert data["status"] == "ok", f"Expected status=ok, got: {data}"

    def test_offframe_coords_preserved_without_imagesize(self, egm_without_imagesize):
        """NL3b: Off-frame point in a legacy EGM (no imageSize) is preserved as-is."""
        client, fname, egm_data = egm_without_imagesize
        resp = client.get(f"/api/boundaries/load?filename={fname}")
        data = resp.get_json()

        pts = data["polygons"][0]["points"]
        offframe_pt = next((p for p in pts if p["y"] == 9999), None)
        assert offframe_pt is not None, (
            f"Off-frame point (y=9999) was altered in legacy EGM load. "
            f"Returned points: {pts}. "
            "Without imageSize, there must be no fallback clamp."
        )


# ─────────────────────────────────────────────────────────────────────────────
# NL4: Regression — detect_boundaries still clamps generated points to frame
# ─────────────────────────────────────────────────────────────────────────────

class TestDetectBoundariesStillClampsGenTime:

    def test_generated_points_within_bounds(self, tmp_path, monkeypatch):
        """NL4: After detect_boundaries, all returned polygon points are within image bounds."""
        try:
            import cv2
            import numpy as np
        except ImportError:
            pytest.skip("cv2/numpy not available")

        w, h = 200, 150
        img = np.zeros((h, w, 3), dtype=np.uint8)
        cv2.rectangle(img, (50, 40), (150, 110), (50, 200, 200), -1)

        img_path = str(tmp_path / "fixture_hole.jpg")
        cv2.imwrite(img_path, img)

        import app as _app_module
        monkeypatch.setattr(_app_module, "DB_PATH", str(tmp_path / "workspace.db"))
        monkeypatch.setattr(_app_module, "_find_image_path",
                            lambda name, preferred_course=None: img_path)
        _app_module.app.config["TESTING"] = True

        with _app_module.app.test_client() as c:
            resp = c.post(
                "/api/detect_boundaries",
                json={"image": "fixture_hole.jpg", "course": "Fixture"},
            )
        assert resp.status_code == 200
        data = resp.get_json()
        assert data["status"] == "ok"

        iw = data["imageSize"]["width"]
        ih = data["imageSize"]["height"]
        violations = []
        for poly in data.get("polygons", []):
            for pt in poly.get("points", []):
                if pt["x"] < 0 or pt["x"] > iw or pt["y"] < 0 or pt["y"] > ih:
                    violations.append((poly.get("name"), pt))

        assert violations == [], (
            f"detect_boundaries returned out-of-frame points after removing load-time clamp: "
            f"{violations}. The generation-time clamp must remain intact."
        )


# ─────────────────────────────────────────────────────────────────────────────
# NL5: JS source — no JS-side clamp block inside loadProject()
# ─────────────────────────────────────────────────────────────────────────────

class TestLoadProjectNoJsClamp:

    def test_no_clamppt_function_in_load_project(self):
        """NL5a: loadProject() must NOT define a clampPt function for loaded points."""
        body = _load_project_body()
        assert "clampPt" not in body, (
            "loadProject() still defines clampPt. "
            "Remove the JS belt-and-suspenders clamp block — off-frame coords must pass through."
        )

    def test_no_clamp_math_on_loaded_poly_points(self):
        """NL5b: loadProject() must not apply Math.min/Math.max to loaded polygon point coords."""
        body = _load_project_body()
        # Specifically disallow the pattern of mapping clampPt over poly.points
        assert "poly.points.map(clamp" not in body and "points.map(clamp" not in body, (
            "loadProject() still maps a clamp function over polygon points on load. "
            "Remove this — intentional off-frame placements must be preserved."
        )


# ─────────────────────────────────────────────────────────────────────────────
# NL6: JS source — no _pendingAutoSave = true from off-frame handling
# ─────────────────────────────────────────────────────────────────────────────

class TestLoadProjectNoDirtyFlag:

    def test_no_pending_autosave_from_offframe_block(self):
        """NL6: loadProject() must not set _pendingAutoSave = true due to off-frame clamping."""
        body = _load_project_body()
        # The off-frame path that sets _pendingAutoSave = true must be gone.
        # We check that clampCount / off_frame_count no longer drives a dirty flag.
        has_clampcount_dirty = (
            ("clampCount" in body or "off_frame_count" in body)
            and "_pendingAutoSave = true" in body
        )
        assert not has_clampcount_dirty, (
            "loadProject() still sets _pendingAutoSave = true based on clampCount / off_frame_count. "
            "Remove this — loading a project with off-frame points must not dirty the project."
        )


# ─────────────────────────────────────────────────────────────────────────────
# NL7: JS source — no "Clamped … off-frame" toast in loadProject()
# ─────────────────────────────────────────────────────────────────────────────

class TestLoadProjectNoOffFrameToast:

    def test_no_clamped_offframe_toast(self):
        """NL7: loadProject() must not show a 'Clamped N off-frame' toast."""
        body = _load_project_body()
        assert "Clamped" not in body or "off-frame" not in body, (
            "loadProject() still shows a 'Clamped N off-frame point(s)' toast. "
            "Remove this message — off-frame points are now intentional and should not be reported."
        )
