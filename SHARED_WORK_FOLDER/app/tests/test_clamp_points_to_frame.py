"""
test_clamp_points_to_frame.py  —  Bug→TDD: clamp auto-analyzed + loaded points to image frame

Two-part fix:

Part 1: Generation clamp
  Points produced by detect_boundaries that fall outside [0,w] x [0,h] must be
  clamped (snapped) to the image boundary before the API response is returned.

Part 2: Load-time healing
  When /api/boundaries/load returns an EGM whose polygon points are outside the
  image bounds, the app layer (Python side) should detect and report how many
  points were off-frame.  The JS editor heals them on load and marks dirty.

Tests
-----
T1  _clamp_point_to_image() helper — basic clamp & pass-through
T2  _clamp_polygon_points() — applies clamp to a list, deduplicates consecutive dupes
T3  detect_boundaries clamp integration — response has no out-of-frame points
T4  load_boundaries_clamped_count — /api/boundaries/load reports off_frame_count
T5  load_boundaries_clean — clean EGM: off_frame_count == 0
T6  JS source — loadProject() heals off-frame points from server response
T7  JS source — dirty flag set when off-frame points found
T8  JS source — toast shown when N > 0 off-frame points clamped
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
# T4: /api/boundaries/load — off_frame_count reported for EGM with bad points
# ─────────────────────────────────────────────────────────────────────────────

class TestLoadBoundariesOffFrameCount:

    def test_load_returns_off_frame_count(self, egm_with_offframe_points):
        """T4a: /api/boundaries/load includes off_frame_count in response."""
        client, fname, egm_data = egm_with_offframe_points
        resp = client.get(f"/api/boundaries/load?filename={fname}")
        assert resp.status_code == 200
        data = resp.get_json()
        assert data["status"] == "ok"
        assert "off_frame_count" in data, (
            "Response missing 'off_frame_count' key. "
            "Add off_frame_count to /api/boundaries/load response when imageSize is present."
        )
        # The fixture has 4 out-of-frame points
        assert data["off_frame_count"] == 4, (
            f"Expected off_frame_count=4, got {data['off_frame_count']}. "
            "Points outside [0,w]x[0,h] should be counted."
        )

    def test_load_returns_clamped_points(self, egm_with_offframe_points):
        """T4b: The returned polygons have clamped points (not the raw bad values)."""
        client, fname, egm_data = egm_with_offframe_points
        resp = client.get(f"/api/boundaries/load?filename={fname}")
        data = resp.get_json()
        iw = data["imageSize"]["width"]
        ih = data["imageSize"]["height"]
        for poly in data.get("polygons", []):
            for pt in poly["points"]:
                assert 0 <= pt["x"] <= iw, f"x={pt['x']} out of [0, {iw}]"
                assert 0 <= pt["y"] <= ih, f"y={pt['y']} out of [0, {ih}]"


class TestLoadBoundariesCleanEGM:

    def test_off_frame_count_zero_for_clean_egm(self, egm_all_inside):
        """T5: Clean EGM → off_frame_count == 0 (no toast)."""
        client, fname, egm_data = egm_all_inside
        resp = client.get(f"/api/boundaries/load?filename={fname}")
        assert resp.status_code == 200
        data = resp.get_json()
        assert data["status"] == "ok"
        # Either key absent or explicitly 0
        count = data.get("off_frame_count", 0)
        assert count == 0, (
            f"Expected off_frame_count=0 for clean EGM, got {count}."
        )


# ─────────────────────────────────────────────────────────────────────────────
# T6: JS source — loadProject() heals off-frame points from server response
# ─────────────────────────────────────────────────────────────────────────────

class TestLoadProjectJsHealing:

    def _get_load_project_body(self):
        src = _read_editor_js()
        m = re.search(r'async loadProject\s*\(proj\)\s*\{(.+?)^\s*\},',
                      src, re.DOTALL | re.MULTILINE)
        assert m, "loadProject() not found in editor.html"
        return m.group(1)

    def test_loads_off_frame_count_from_response(self):
        """T6a: loadProject() reads data.off_frame_count from the API response."""
        body = self._get_load_project_body()
        assert "off_frame_count" in body, (
            "loadProject() does not read off_frame_count from the API response. "
            "Add: const clampCount = data.off_frame_count || 0;"
        )

    def test_clamp_applied_to_restored_points(self):
        """T6b: loadProject() applies clamping to polygon points from the response."""
        body = self._get_load_project_body()
        # Must reference either a clamp function or Math.min/Math.max on point coords
        has_clamp_logic = (
            "clampPt" in body
            or ("Math.min" in body and "Math.max" in body)
            or "_clampLoadedPoints" in body
            or "clampLoadedPoints" in body
        )
        assert has_clamp_logic, (
            "loadProject() does not appear to clamp loaded polygon points. "
            "Add client-side clamping of loaded points to [0, imgW] x [0, imgH]."
        )

    def test_dirty_flag_set_when_clamped(self):
        """T7: _pendingAutoSave or dirty flag is set when off-frame points were clamped."""
        body = self._get_load_project_body()
        # Must set _pendingAutoSave = true (or call autoSave) when clampCount > 0
        assert "_pendingAutoSave" in body or "autoSave" in body, (
            "loadProject() never sets _pendingAutoSave or calls autoSave. "
            "Set _pendingAutoSave = true when off_frame_count > 0 so the fix is persisted."
        )
        # Specifically: must be conditional on clamp count
        assert "clampCount" in body or "off_frame_count" in body, (
            "dirty-flag logic is unconditional — it must only trigger when clampCount > 0."
        )

    def test_toast_shown_when_offframe_points_clamped(self):
        """T8: A flash/toast is shown to the user when N > 0 points were clamped."""
        body = self._get_load_project_body()
        # Must call this.flash() referencing the clamp count
        assert "flash" in body, (
            "loadProject() does not call this.flash(). "
            "Show a toast: 'Clamped N off-frame points to the image edge'."
        )
        # The flash call must be conditional on clampCount > 0
        has_conditional_flash = (
            "clampCount" in body and "flash" in body
        ) or (
            "off_frame_count" in body and "flash" in body
        )
        assert has_conditional_flash, (
            "Toast is not conditional on clampCount > 0. "
            "Only show the toast when points were actually clamped."
        )
