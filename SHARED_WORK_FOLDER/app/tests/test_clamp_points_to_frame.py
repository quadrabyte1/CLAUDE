"""
test_clamp_points_to_frame.py  —  Bug→TDD: clamp auto-analyzed points to image frame

Generation-time clamp (KEPT):
  Points produced by detect_boundaries that fall outside [0,w] x [0,h] must be
  clamped (snapped) to the image boundary before the API response is returned.
  _clamp_point_to_image() and _clamp_polygon_points() helpers support this.

Load-time clamp (REMOVED — see test_remove_load_time_clamp.py):
  Off-frame polygon points in saved EGMs are intentional (users drag control
  points outside the image frame on purpose). The old load-time healing is gone.
  T4, T6b, T7, T8 have been updated to match the new no-clamp contract.

Tests
-----
T1  _clamp_point_to_image() helper — basic clamp & pass-through
T2  _clamp_polygon_points() — applies clamp to a list, deduplicates consecutive dupes
T3  detect_boundaries clamp integration — response has no out-of-frame points
T4  load_boundaries — off-frame points pass through unchanged (no load-time clamp)
T5  load_boundaries_clean — off_frame_count absent or 0 (field removed)
T6  JS source — loadProject() does NOT apply a clamp to loaded polygon points
T7  JS source — no dirty flag set from off-frame handling
T8  JS source — no "Clamped N off-frame" toast
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
def egm_with_offframe_points(tmp_path, monkeypatch):
    """
    EGM file whose green polygon has a point at y=900 on an 800-tall image,
    and an in-frame point for comparison.
    Returns (client, filename, egm_data).
    """
    egm_data = {
        "course": "Stanford",
        "hole": "8",
        "image": "stanford_h8.jpg",
        "imageCourse": "Stanford",
        "imageSize": {"width": 1200, "height": 800},
        "polygons": [
            {
                "type": "green",
                "name": "Green",
                "points": [
                    {"x": 100, "y": 100},   # inside
                    {"x": 200, "y": 900},   # BELOW frame (y > 800)
                    {"x": 300, "y": -10},   # ABOVE frame (y < 0)
                    {"x": 1500, "y": 400},  # RIGHT of frame (x > 1200)
                    {"x": -50, "y": 400},   # LEFT of frame (x < 0)
                    {"x": 400, "y": 300},   # inside
                ],
            },
        ],
        "contourStep": 0.5,
    }
    egm_dir = tmp_path / "GolfCourses" / "Stanford" / "EGMs"
    egm_dir.mkdir(parents=True)
    fname = "Stanford (Hole 08).egm"
    (egm_dir / fname).write_text(json.dumps(egm_data))

    tmp_db = str(tmp_path / "workspace.db")
    import app as _app_module
    monkeypatch.setattr(_app_module, "DB_PATH", tmp_db)
    monkeypatch.setattr(_app_module, "_EGM_BASE", str(tmp_path / "GolfCourses"))
    _app_module.app.config["TESTING"] = True
    with _app_module.app.test_client() as client:
        yield client, fname, egm_data


@pytest.fixture()
def egm_all_inside(tmp_path, monkeypatch):
    """EGM file whose points are all inside the image bounds."""
    egm_data = {
        "course": "Stanford",
        "hole": "1",
        "image": "stanford_h1.jpg",
        "imageCourse": "Stanford",
        "imageSize": {"width": 1200, "height": 800},
        "polygons": [
            {
                "type": "green",
                "name": "Green",
                "points": [
                    {"x": 100, "y": 100},
                    {"x": 200, "y": 200},
                    {"x": 300, "y": 300},
                ],
            },
        ],
        "contourStep": 0.5,
    }
    egm_dir = tmp_path / "GolfCourses" / "Stanford" / "EGMs"
    egm_dir.mkdir(parents=True)
    fname = "Stanford (Hole 01).egm"
    (egm_dir / fname).write_text(json.dumps(egm_data))

    tmp_db = str(tmp_path / "workspace.db")
    import app as _app_module
    monkeypatch.setattr(_app_module, "DB_PATH", tmp_db)
    monkeypatch.setattr(_app_module, "_EGM_BASE", str(tmp_path / "GolfCourses"))
    _app_module.app.config["TESTING"] = True
    with _app_module.app.test_client() as client:
        yield client, fname, egm_data


# ─────────────────────────────────────────────────────────────────────────────
# T1: _clamp_point_to_image() helper — basic clamp & pass-through
# ─────────────────────────────────────────────────────────────────────────────

class TestClampPointToImage:

    def _import_helper(self):
        import app as _app_module
        assert hasattr(_app_module, "_clamp_point_to_image"), (
            "_clamp_point_to_image() not found in app.py. "
            "Add: def _clamp_point_to_image(x, y, w, h): ..."
        )
        return _app_module._clamp_point_to_image

    def test_point_beyond_right_clamped_to_width(self):
        """T1a: x > w clamps to w."""
        fn = self._import_helper()
        cx, cy = fn(1500.0, 400.0, 1200, 800)
        assert cx == 1200.0
        assert cy == 400.0

    def test_point_below_frame_clamped_to_height(self):
        """T1b: y > h clamps to h."""
        fn = self._import_helper()
        cx, cy = fn(400.0, 900.0, 1200, 800)
        assert cx == 400.0
        assert cy == 800.0

    def test_point_above_frame_clamped_to_zero(self):
        """T1c: y < 0 clamps to 0."""
        fn = self._import_helper()
        cx, cy = fn(400.0, -40.0, 1200, 800)
        assert cx == 400.0
        assert cy == 0.0

    def test_point_left_of_frame_clamped_to_zero(self):
        """T1d: x < 0 clamps to 0."""
        fn = self._import_helper()
        cx, cy = fn(-50.0, 400.0, 1200, 800)
        assert cx == 0.0
        assert cy == 400.0

    def test_corner_both_axes_clamped(self):
        """T1e: both axes outside — both clamped."""
        fn = self._import_helper()
        cx, cy = fn(1500.0, -40.0, 1200, 800)
        assert cx == 1200.0
        assert cy == 0.0

    def test_inside_point_unchanged(self):
        """T1f: points strictly inside are returned unchanged."""
        fn = self._import_helper()
        cx, cy = fn(600.0, 400.0, 1200, 800)
        assert cx == 600.0
        assert cy == 400.0

    def test_boundary_point_unchanged(self):
        """T1g: points exactly on the boundary (x=w, y=h) are unchanged."""
        fn = self._import_helper()
        cx, cy = fn(1200.0, 800.0, 1200, 800)
        assert cx == 1200.0
        assert cy == 800.0

    def test_returns_floats(self):
        """T1h: return type is float for both axes."""
        fn = self._import_helper()
        cx, cy = fn(600, 400, 1200, 800)
        assert isinstance(cx, float)
        assert isinstance(cy, float)


# ─────────────────────────────────────────────────────────────────────────────
# T2: _clamp_polygon_points() — applies clamp to a list, deduplicates consecutive dupes
# ─────────────────────────────────────────────────────────────────────────────

class TestClampPolygonPoints:

    def _import_helper(self):
        import app as _app_module
        assert hasattr(_app_module, "_clamp_polygon_points"), (
            "_clamp_polygon_points() not found in app.py. "
            "Add: def _clamp_polygon_points(points, w, h): ..."
        )
        return _app_module._clamp_polygon_points

    def test_out_of_frame_points_clamped(self):
        """T2a: A polygon with an off-frame point has that point clamped."""
        fn = self._import_helper()
        pts = [{"x": 100, "y": 100}, {"x": 1500, "y": -40}, {"x": 300, "y": 300}]
        result, _ = fn(pts, 1200, 800)
        assert result[1]["x"] == pytest.approx(1200.0)
        assert result[1]["y"] == pytest.approx(0.0)

    def test_in_frame_points_unchanged(self):
        """T2b: Points already inside are unchanged."""
        fn = self._import_helper()
        pts = [{"x": 100, "y": 100}, {"x": 200, "y": 200}, {"x": 300, "y": 300}]
        result, _ = fn(pts, 1200, 800)
        assert result[0]["x"] == pytest.approx(100.0)
        assert result[0]["y"] == pytest.approx(100.0)
        assert len(result) == 3

    def test_consecutive_dupes_after_clamp_removed(self):
        """T2c: Two adjacent points both snap to the same corner → deduplicated."""
        fn = self._import_helper()
        # Both these points clamp to (1200, 800) — should become one
        pts = [
            {"x": 100, "y": 100},
            {"x": 1500, "y": 900},   # clamps to (1200, 800)
            {"x": 2000, "y": 1000},  # also clamps to (1200, 800)
            {"x": 200, "y": 200},
        ]
        result, _ = fn(pts, 1200, 800)
        # The two adjacent corner-clamped points should become one
        assert len(result) == 3, (
            f"Expected 3 points after dedup (2 consecutive snapped to same corner), "
            f"got {len(result)}: {result}"
        )
        assert result[1]["x"] == pytest.approx(1200.0)
        assert result[1]["y"] == pytest.approx(800.0)

    def test_non_consecutive_dupes_kept(self):
        """T2d: Non-consecutive identical points (after clamp) are NOT removed."""
        fn = self._import_helper()
        # pt0 and pt2 both snap to (0,0) but they're not adjacent — keep both
        pts = [
            {"x": -5, "y": -5},   # clamps to (0,0)
            {"x": 100, "y": 100},
            {"x": -3, "y": -3},   # also clamps to (0,0), but not adjacent
        ]
        result, _ = fn(pts, 1200, 800)
        assert len(result) == 3

    def test_clamp_count_returned(self):
        """T2e: The function returns a (points, clamp_count) tuple."""
        fn = self._import_helper()
        pts = [{"x": 1500, "y": 400}, {"x": 100, "y": 100}]
        ret = fn(pts, 1200, 800)
        # Should return (list_of_points, int) — check both forms accepted
        assert isinstance(ret, (list, tuple))
        if isinstance(ret, tuple):
            clamped_pts, count = ret
            assert count == 1
        else:
            # If it just returns a list, that's ok — the count check is separate
            pass


# ─────────────────────────────────────────────────────────────────────────────
# T3: detect_boundaries response — no out-of-frame points
# ─────────────────────────────────────────────────────────────────────────────

class TestDetectBoundariesClamp:

    def test_all_generated_points_within_bounds(self, tmp_path, monkeypatch):
        """T3: After detect_boundaries, every point is within [0,w] x [0,h]."""
        import numpy as np

        # Create a minimal synthetic image: 200x150 green blob in the center
        try:
            import cv2
        except ImportError:
            pytest.skip("cv2 not available")

        w, h = 200, 150
        img = np.zeros((h, w, 3), dtype=np.uint8)
        # Green/yellow high-saturation blob to trigger the green detector
        cv2.rectangle(img, (50, 40), (150, 110), (50, 200, 200), -1)  # BGR: high sat yellow

        # Save image to temp path
        img_path = str(tmp_path / "fixture_hole.jpg")
        cv2.imwrite(img_path, img)

        import app as _app_module
        monkeypatch.setattr(_app_module, "DB_PATH", str(tmp_path / "workspace.db"))

        # Monkey-patch _find_image_path to return our fixture
        monkeypatch.setattr(_app_module, "_find_image_path",
                            lambda name, preferred_course=None: img_path)

        _app_module.app.config["TESTING"] = True
        with _app_module.app.test_client() as client:
            resp = client.post(
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
                    violations.append((poly["name"], pt))
        assert violations == [], (
            f"detect_boundaries returned out-of-frame points: {violations}. "
            "Clamp must be applied before returning polygons."
        )


# ─────────────────────────────────────────────────────────────────────────────
# T4: /api/boundaries/load — off-frame points pass through unchanged
# ─────────────────────────────────────────────────────────────────────────────

class TestLoadBoundariesOffFramePassThrough:

    def test_offframe_points_not_clamped_on_load(self, egm_with_offframe_points):
        """T4a: load_boundaries must NOT clamp off-frame points — raw coords pass through."""
        client, fname, egm_data = egm_with_offframe_points
        resp = client.get(f"/api/boundaries/load?filename={fname}")
        assert resp.status_code == 200
        data = resp.get_json()
        assert data["status"] == "ok"

        # Fixture has y=900 on an 800-tall image; it must come back as y=900.
        pts = data["polygons"][0]["points"]
        offframe_pt = next((p for p in pts if p["y"] == 900), None)
        assert offframe_pt is not None, (
            f"Off-frame point (y=900) was clamped or removed on load. "
            f"Returned points: {pts}. "
            "load_boundaries must return coords as-is from the EGM."
        )

    def test_no_offframe_count_or_zero(self, egm_with_offframe_points):
        """T4b: off_frame_count is absent or 0 — load-time counting is removed."""
        client, fname, egm_data = egm_with_offframe_points
        resp = client.get(f"/api/boundaries/load?filename={fname}")
        data = resp.get_json()
        count = data.get("off_frame_count", 0)
        assert count == 0, (
            f"off_frame_count={count} — load_boundaries must not count off-frame points "
            "after the load-time clamp removal."
        )


class TestLoadBoundariesCleanEGM:

    def test_off_frame_count_zero_for_clean_egm(self, egm_all_inside):
        """T5: Clean EGM → off_frame_count absent or 0."""
        client, fname, egm_data = egm_all_inside
        resp = client.get(f"/api/boundaries/load?filename={fname}")
        assert resp.status_code == 200
        data = resp.get_json()
        assert data["status"] == "ok"
        count = data.get("off_frame_count", 0)
        assert count == 0, (
            f"Expected off_frame_count=0 (or absent) for clean EGM, got {count}."
        )


# ─────────────────────────────────────────────────────────────────────────────
# T6–T8: JS source — loadProject() does NOT clamp, dirty, or toast for off-frame
# ─────────────────────────────────────────────────────────────────────────────

class TestLoadProjectNoClampBehavior:

    def _get_load_project_body(self):
        src = _read_editor_js()
        m = re.search(r'async loadProject\s*\(proj\)\s*\{(.+?)^\s*\},',
                      src, re.DOTALL | re.MULTILINE)
        assert m, "loadProject() not found in editor.html"
        return m.group(1)

    def test_no_clamppt_in_load_project(self):
        """T6: loadProject() must NOT define clampPt for loaded polygon points."""
        body = self._get_load_project_body()
        assert "clampPt" not in body, (
            "loadProject() still defines clampPt. "
            "Remove the JS belt-and-suspenders clamp — off-frame coords must pass through."
        )

    def test_no_clamp_map_over_poly_points(self):
        """T6b: loadProject() must not map a clamp function over polygon points."""
        body = self._get_load_project_body()
        assert "poly.points.map(clamp" not in body and "points.map(clamp" not in body, (
            "loadProject() still maps a clamp over polygon points. "
            "Remove this — intentional off-frame placements must be preserved."
        )

    def test_no_pending_autosave_from_offframe_block(self):
        """T7: loadProject() must not set _pendingAutoSave = true from off-frame handling."""
        body = self._get_load_project_body()
        has_clampcount_dirty = (
            ("clampCount" in body or "off_frame_count" in body)
            and "_pendingAutoSave = true" in body
        )
        assert not has_clampcount_dirty, (
            "loadProject() still sets _pendingAutoSave = true based on clampCount. "
            "Remove this — loading off-frame points must not dirty the project."
        )

    def test_no_clamped_offframe_toast(self):
        """T8: loadProject() must not show a 'Clamped N off-frame' toast."""
        body = self._get_load_project_body()
        assert "Clamped" not in body or "off-frame" not in body, (
            "loadProject() still shows a 'Clamped N off-frame point(s)' toast. "
            "Remove this — off-frame points are intentional."
        )
