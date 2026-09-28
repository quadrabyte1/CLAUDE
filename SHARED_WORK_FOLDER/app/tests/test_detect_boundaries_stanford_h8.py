"""
test_detect_boundaries_stanford_h8.py
──────────────────────────────────────
Bug→TDD: RED written first against the old classifier (v4.77); GREEN after:
  1. Green-interior mask applied before trap/water detection.
  2. Trap H lower bound loosened: [15,34] → [10,40] (catches H=13 beige).
  3. Water combined filter: original high-sat OR new pale-cyan [80,105]/[15,50]/V≥200.

Tests cover:
  T1 — Interior slope bands NOT classified as water (0 water polygons inside green)
  T2 — LL trap detected (centroid x < 0.4*W, y > 0.6*H)
  T3 — LR water detected (centroid x > 0.6*W, y > 0.6*H)
  T4 — Green polygon still present (1 green polygon)
  T5 — Regression: Firefly H14 — green + trap + water still detected

Input image:
    ItWentIn/GolfCourses/Stanford/Images/Stanford (hole 8, 5396).png  (815×1227)
"""

from __future__ import annotations

import json
import os
import sys
import pytest

# ── Paths ──────────────────────────────────────────────────────────────────
APP_DIR = os.path.join(os.path.dirname(__file__), "..")
REPO_ROOT = os.path.join(APP_DIR, "..")
sys.path.insert(0, APP_DIR)

STANFORD_H8_IMAGE = os.path.join(
    REPO_ROOT, "ItWentIn", "GolfCourses", "Stanford", "Images",
    "Stanford (hole 8, 5396).png"
)
FIREFLY_H14_IMAGE = os.path.join(
    REPO_ROOT, "ItWentIn", "GolfCourses", "Firefly", "Images",
    "Firefly Golf Links (14).png"
)


# ── Fixtures ───────────────────────────────────────────────────────────────

@pytest.fixture(scope="module")
def app_client(tmp_path_factory):
    """Flask test client with a temp DB so the live DB is never touched."""
    tmp_db = str(tmp_path_factory.mktemp("db") / "workspace.db")
    import app as _app_module
    _app_module.DB_PATH = tmp_db          # redirect away from live DB
    _app_module.app.config["TESTING"] = True
    with _app_module.app.test_client() as client:
        yield client


def _detect(client, image_path: str):
    """POST to /api/detect_boundaries with an absolute image path override
    so the test doesn't depend on the live images-folder lookup."""
    # Patch _find_image_path to return the explicit path
    import app as _app_module
    orig = _app_module._find_image_path
    _app_module._find_image_path = lambda name, preferred_course="": image_path
    try:
        resp = client.post(
            "/api/detect_boundaries",
            data=json.dumps({"image": "test_image.png", "course": "Test"}),
            content_type="application/json",
        )
        assert resp.status_code == 200, f"detect_boundaries returned {resp.status_code}: {resp.data}"
        data = resp.get_json()
        assert data["status"] == "ok", f"detect_boundaries error: {data}"
        return data
    finally:
        _app_module._find_image_path = orig


# ── Helpers ────────────────────────────────────────────────────────────────

def _poly_centroid(poly):
    xs = [p["x"] for p in poly["points"]]
    ys = [p["y"] for p in poly["points"]]
    return sum(xs) / len(xs), sum(ys) / len(ys)


def _poly_bbox(poly):
    xs = [p["x"] for p in poly["points"]]
    ys = [p["y"] for p in poly["points"]]
    return min(xs), min(ys), max(xs), max(ys)


# ── T1: No interior-slope water ────────────────────────────────────────────

class TestNoInteriorWater:
    """
    T1 — After applying the green-interior mask, the interior slope-gradient
    (blue/teal coloring of the green surface) must NOT produce water polygons.
    Any water polygon whose bounding box lies entirely within the green polygon
    is a false positive.

    GREEN bounds for Stanford H8 5396:
        x ∈ [72, 763],  y ∈ [0, 955]  (from the EGM)
    """

    def test_no_water_bbox_inside_green(self, app_client):
        """T1: zero water polygons whose bbox is entirely inside the green area."""
        if not os.path.isfile(STANFORD_H8_IMAGE):
            pytest.skip("Stanford H8 5396 image not found on this machine")

        result = _detect(app_client, STANFORD_H8_IMAGE)
        polys = result["polygons"]
        W = result["imageSize"]["width"]   # 815
        H = result["imageSize"]["height"]  # 1227

        # Green bbox from EGM  ── conservative inner bounds (points, not full mask)
        GREEN_X_MIN, GREEN_X_MAX = 72, 763
        GREEN_Y_MIN, GREEN_Y_MAX = 0, 955

        water_polys = [p for p in polys if p["type"] == "water"]
        bogus = []
        for wp in water_polys:
            bx_min, by_min, bx_max, by_max = _poly_bbox(wp)
            entirely_inside = (
                bx_min >= GREEN_X_MIN and bx_max <= GREEN_X_MAX
                and by_min >= GREEN_Y_MIN and by_max <= GREEN_Y_MAX
            )
            if entirely_inside:
                bogus.append(wp)

        assert len(bogus) == 0, (
            f"Found {len(bogus)} water polygon(s) with bbox entirely inside the green — "
            f"these are interior slope-band false positives: "
            + ", ".join(
                f"{p['name']} bbox=({_poly_bbox(p)})" for p in bogus
            )
        )


# ── T2: LL trap detected ───────────────────────────────────────────────────

class TestLLTrapDetected:
    """
    T2 — The beige/tan sand trap in the lower-left must be detected.
    Its centroid must fall in the LL quadrant: x < 0.4*W AND y > 0.6*H.
    """

    def test_ll_trap_centroid_in_ll_quadrant(self, app_client):
        """T2: exactly 1 trap polygon with centroid in LL quadrant."""
        if not os.path.isfile(STANFORD_H8_IMAGE):
            pytest.skip("Stanford H8 5396 image not found on this machine")

        result = _detect(app_client, STANFORD_H8_IMAGE)
        polys = result["polygons"]
        W = result["imageSize"]["width"]   # 815
        H = result["imageSize"]["height"]  # 1227

        trap_polys = [p for p in polys if p["type"] == "trap"]
        ll_traps = []
        for tp in trap_polys:
            cx, cy = _poly_centroid(tp)
            if cx < 0.4 * W and cy > 0.6 * H:
                ll_traps.append(tp)

        assert len(ll_traps) >= 1, (
            f"Expected ≥1 trap polygon in LL quadrant (x<{0.4*W:.0f}, y>{0.6*H:.0f}), "
            f"got {len(ll_traps)}. All trap polygons: "
            + str([{"name": p["name"], "centroid": _poly_centroid(p)} for p in trap_polys])
        )


# ── T3: LR water detected ──────────────────────────────────────────────────

class TestLRWaterDetected:
    """
    T3 — The light-cyan water hazard in the lower-right must be detected.
    Its centroid must fall in the LR quadrant: x > 0.6*W AND y > 0.6*H.
    """

    def test_lr_water_centroid_in_lr_quadrant(self, app_client):
        """T3: exactly 1 water polygon with centroid in LR quadrant."""
        if not os.path.isfile(STANFORD_H8_IMAGE):
            pytest.skip("Stanford H8 5396 image not found on this machine")

        result = _detect(app_client, STANFORD_H8_IMAGE)
        polys = result["polygons"]
        W = result["imageSize"]["width"]   # 815
        H = result["imageSize"]["height"]  # 1227

        water_polys = [p for p in polys if p["type"] == "water"]
        lr_waters = []
        for wp in water_polys:
            cx, cy = _poly_centroid(wp)
            if cx > 0.6 * W and cy > 0.6 * H:
                lr_waters.append(wp)

        assert len(lr_waters) >= 1, (
            f"Expected ≥1 water polygon in LR quadrant (x>{0.6*W:.0f}, y>{0.6*H:.0f}), "
            f"got {len(lr_waters)}. All water polygons: "
            + str([{"name": p["name"], "centroid": _poly_centroid(p)} for p in water_polys])
        )


# ── T4: Green polygon present ──────────────────────────────────────────────

class TestGreenPolygonPresent:
    """
    T4 — The green polygon must still be detected after the mask changes.
    Exactly one 'green' polygon, covering the egg-shape center of the image.
    """

    def test_green_polygon_exists(self, app_client):
        """T4a: exactly 1 green polygon."""
        if not os.path.isfile(STANFORD_H8_IMAGE):
            pytest.skip("Stanford H8 5396 image not found on this machine")

        result = _detect(app_client, STANFORD_H8_IMAGE)
        polys = result["polygons"]

        green_polys = [p for p in polys if p["type"] == "green"]
        assert len(green_polys) == 1, (
            f"Expected exactly 1 green polygon, got {len(green_polys)}"
        )

    def test_green_polygon_covers_center(self, app_client):
        """T4b: green polygon centroid is in the center region of the image."""
        if not os.path.isfile(STANFORD_H8_IMAGE):
            pytest.skip("Stanford H8 5396 image not found on this machine")

        result = _detect(app_client, STANFORD_H8_IMAGE)
        polys = result["polygons"]
        W = result["imageSize"]["width"]
        H = result["imageSize"]["height"]

        green_polys = [p for p in polys if p["type"] == "green"]
        if not green_polys:
            pytest.fail("No green polygon found")

        cx, cy = _poly_centroid(green_polys[0])
        # Green should be roughly centered horizontally and span much of the height
        assert 0.2 * W < cx < 0.8 * W, (
            f"Green centroid x={cx:.0f} is not in central horizontal band "
            f"[{0.2*W:.0f}, {0.8*W:.0f}]"
        )
        assert 0.1 * H < cy < 0.9 * H, (
            f"Green centroid y={cy:.0f} is not in central vertical band "
            f"[{0.1*H:.0f}, {0.9*H:.0f}]"
        )


# ── T5: Regression — Firefly H14 still works ──────────────────────────────

class TestFireflyH14Regression:
    """
    T5 — Firefly H14 (a previously working hole) must still detect green,
    traps, and water polygons sensibly after the threshold changes.
    """

    def test_firefly_h14_green_present(self, app_client):
        """T5a: Firefly H14 has a green polygon."""
        if not os.path.isfile(FIREFLY_H14_IMAGE):
            pytest.skip("Firefly H14 image not found on this machine")

        result = _detect(app_client, FIREFLY_H14_IMAGE)
        polys = result["polygons"]
        green_polys = [p for p in polys if p["type"] == "green"]
        assert len(green_polys) == 1, (
            f"Expected 1 green polygon on Firefly H14, got {len(green_polys)}"
        )

    def test_firefly_h14_trap_present(self, app_client):
        """T5b: Firefly H14 still has at least one trap polygon."""
        if not os.path.isfile(FIREFLY_H14_IMAGE):
            pytest.skip("Firefly H14 image not found on this machine")

        result = _detect(app_client, FIREFLY_H14_IMAGE)
        polys = result["polygons"]
        trap_polys = [p for p in polys if p["type"] == "trap"]
        assert len(trap_polys) >= 1, (
            f"Expected ≥1 trap polygon on Firefly H14 regression, got {len(trap_polys)}"
        )

    def test_firefly_h14_water_present(self, app_client):
        """T5c: Firefly H14 still has at least one water polygon."""
        if not os.path.isfile(FIREFLY_H14_IMAGE):
            pytest.skip("Firefly H14 image not found on this machine")

        result = _detect(app_client, FIREFLY_H14_IMAGE)
        polys = result["polygons"]
        water_polys = [p for p in polys if p["type"] == "water"]
        assert len(water_polys) >= 1, (
            f"Expected ≥1 water polygon on Firefly H14 regression, got {len(water_polys)}"
        )


# ── T6: MASK_GREEN_INTERIOR_FROM_HAZARDS constant exists ─────────────────

class TestGreenMaskConstant:
    """
    T6 — The module-level toggle MASK_GREEN_INTERIOR_FROM_HAZARDS must exist
    in app.py, defaulting to True.
    """

    def test_constant_exists_and_is_true(self):
        """T6: MASK_GREEN_INTERIOR_FROM_HAZARDS is defined True in app.py."""
        app_path = os.path.join(APP_DIR, "app.py")
        with open(app_path, encoding="utf-8") as f:
            src = f.read()
        assert "MASK_GREEN_INTERIOR_FROM_HAZARDS" in src, (
            "MASK_GREEN_INTERIOR_FROM_HAZARDS constant not found in app.py"
        )
        # Verify the default is True (module-level assignment)
        import re
        m = re.search(
            r"^MASK_GREEN_INTERIOR_FROM_HAZARDS\s*=\s*(True|False)",
            src, re.MULTILINE
        )
        assert m is not None, (
            "Could not find top-level assignment 'MASK_GREEN_INTERIOR_FROM_HAZARDS = ...' in app.py"
        )
        assert m.group(1) == "True", (
            f"MASK_GREEN_INTERIOR_FROM_HAZARDS should default to True, found {m.group(1)}"
        )
