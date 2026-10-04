"""
test_ocr_elevation_wiring.py — Bug→TDD for OCR→elevationSpikes wiring (task 650)

Pipeline under test:
  extract_numeric_markers(image) -> [(x, y, value), ...]
  clamp_ocr_value(value) -> float|None
  OCR markers -> elevationSpikes [{x, y, mm}] -> EGM -> 3MF heights

Tests:

  T1  OCR values reach the heightmap array via elevationSpikes:
        run OCR + wiring → heightmap has non-zero values at marker pixel positions.

  T2  Reproducibility: same image → same elevationSpikes output (deterministic).

  T3  No markers → empty elevationSpikes (no elevation beyond baseline).

  T4  Filter unrealistic OCR reads (value > 50 mm → dropped, logged).

  T5  EGM round-trip: OCR-populated spikes survive save→reload via
        /api/boundaries (POST) and /api/boundaries/load (GET).

  T6  /api/detect_boundaries returns elevationMarkers field alongside polygons.

  T7  elevationMarkers from /api/detect_boundaries are [{x, y, mm}] objects
        with float mm values and integer x,y within image bounds.

  T8  clamp_ocr_value clips negative and absurdly large values correctly.

  T9  startNewProject wiring — JS source: after runDetection() resolves,
        elevationSpikes is populated from result.elevationMarkers.

  T10 Filter zero-value markers — value 0.0 yields no spike (below _OCR_MIN_VALUE).

Run:
    cd /Volumes/GIT/CLAUDE/SHARED_WORK_FOLDER
    python -m pytest app/tests/test_ocr_elevation_wiring.py -v
"""

from __future__ import annotations

import json
import os
import sys
import tempfile
from pathlib import Path
import pytest

# T5 (2026-10-03): OCR pipeline stripped. clamp_ocr_value, markers_to_elevation_spikes removed.
# All tests in this file are tombstoned until a replacement mechanism ships.
pytestmark = pytest.mark.skip(reason="T5: OCR elevation wiring stripped from app.py")

import numpy as np
import pytest
from PIL import Image, ImageDraw

# ---------------------------------------------------------------------------
# Path setup
# ---------------------------------------------------------------------------
sys.path.insert(0, str(Path(__file__).parent.parent))

# ---------------------------------------------------------------------------
# Real image path
# ---------------------------------------------------------------------------
_REPO_ROOT = Path(__file__).parent.parent.parent
_STANFORD_H8 = _REPO_ROOT / "ItWentIn/GolfCourses/Stanford/Images/Stanford (hole 8, 5396).png"

# ---------------------------------------------------------------------------
# Shared font for synthetic images (same helper as test_golf_intel_ocr.py)
# ---------------------------------------------------------------------------
_FONT_CANDIDATES = [
    "/System/Library/Fonts/Helvetica.ttc",
    "/System/Library/Fonts/Arial.ttf",
    "/Library/Fonts/Arial.ttf",
    "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
]
_SYNTH_FONT = None
for _fp in _FONT_CANDIDATES:
    if os.path.exists(_fp):
        try:
            from PIL import ImageFont
            _SYNTH_FONT = ImageFont.truetype(_fp, 22)
        except Exception:
            pass
        break


def _make_synthetic_gi_image(
    out_path: Path,
    labels: list[tuple[int, int, str]],
    bg_color: tuple = (100, 150, 80),
    text_color: tuple = (240, 255, 200),
    img_size: tuple = (400, 400),
) -> Path:
    """Render decimal marker labels on a coloured background (GI heat-map style)."""
    from PIL import ImageFont
    img = Image.new("RGB", img_size, color=bg_color)
    draw = ImageDraw.Draw(img)
    font = _SYNTH_FONT
    for x, y, text in labels:
        for dx, dy in [(-1, 0), (1, 0), (0, -1), (0, 1)]:
            draw.text((x + dx, y + dy), text, fill=(10, 10, 10), font=font)
        draw.text((x, y), text, fill=text_color, font=font)
    img.save(str(out_path))
    return out_path


# ---------------------------------------------------------------------------
# Flask test client fixture
# ---------------------------------------------------------------------------

@pytest.fixture()
def app_client(tmp_path, monkeypatch):
    """Flask test client with temp DB and temp GolfCourses tree."""
    import app as _app_module
    tmp_db = str(tmp_path / "workspace.db")
    tmp_egm_base = str(tmp_path / "GolfCourses")
    monkeypatch.setattr(_app_module, "DB_PATH", tmp_db)
    monkeypatch.setattr(_app_module, "_EGM_BASE", tmp_egm_base)
    _app_module.app.config["TESTING"] = True
    with _app_module.app.test_client() as client:
        yield client


# ---------------------------------------------------------------------------
# T1  OCR values reach elevationSpikes with correct mm = detected value
# ---------------------------------------------------------------------------

class TestOcrValuesReachElevationSpikes:
    """
    T1: OCR returns [(x, y, value), ...] → clamp_ocr_value → elevationSpikes
        [{x, y, mm}] with mm == value.  Only in-range values (0 < mm <= 50) survive.
    """

    def test_ocr_to_spikes_basic_conversion(self):
        """T1a: markers_to_elevation_spikes() converts (x, y, val) to [{x, y, mm}] dicts."""
        from app import markers_to_elevation_spikes
        markers = [(100, 200, 2.8), (300, 150, 4.1)]
        spikes = markers_to_elevation_spikes(markers)
        assert len(spikes) == 2
        assert spikes[0] == {"x": 100, "y": 200, "mm": pytest.approx(2.8)}
        assert spikes[1] == {"x": 300, "y": 150, "mm": pytest.approx(4.1)}

    def test_spike_mm_equals_ocr_value(self):
        """T1b: mm field is exactly the OCR float value (mm=value mapping)."""
        from app import markers_to_elevation_spikes
        markers = [(50, 60, 3.5)]
        spikes = markers_to_elevation_spikes(markers)
        assert spikes[0]["mm"] == pytest.approx(3.5)

    def test_x_y_are_integers(self):
        """T1c: x and y in the spike dict are integers (pixel coords)."""
        from app import markers_to_elevation_spikes
        markers = [(101.7, 202.3, 2.1)]  # floats from OCR centroid
        spikes = markers_to_elevation_spikes(markers)
        assert isinstance(spikes[0]["x"], int)
        assert isinstance(spikes[0]["y"], int)

    def test_empty_markers_gives_empty_spikes(self):
        """T1d: No markers → empty spike list."""
        from app import markers_to_elevation_spikes
        assert markers_to_elevation_spikes([]) == []


# ---------------------------------------------------------------------------
# T2  Reproducibility — same markers → same spikes (deterministic)
# ---------------------------------------------------------------------------

class TestReproducibility:

    def test_same_markers_same_spikes(self):
        """T2: markers_to_elevation_spikes is deterministic (no randomness)."""
        from app import markers_to_elevation_spikes
        markers = [(10, 20, 1.4), (100, 200, 2.6), (300, 180, 3.8)]
        r1 = markers_to_elevation_spikes(markers)
        r2 = markers_to_elevation_spikes(markers)
        assert r1 == r2

    def test_order_preserved(self):
        """T2b: Output order follows input order."""
        from app import markers_to_elevation_spikes
        markers = [(10, 10, 1.0), (20, 20, 2.0), (30, 30, 3.0)]
        spikes = markers_to_elevation_spikes(markers)
        for i, sp in enumerate(spikes):
            assert sp["mm"] == pytest.approx(markers[i][2])


# ---------------------------------------------------------------------------
# T3  No markers → empty elevationSpikes
# ---------------------------------------------------------------------------

class TestNoMarkersNoSpikes:

    def test_empty_marker_list_produces_empty_spikes(self):
        """T3: When OCR finds nothing, elevationSpikes stays []."""
        from app import markers_to_elevation_spikes
        spikes = markers_to_elevation_spikes([])
        assert spikes == []

    def test_all_filtered_markers_produces_empty_spikes(self):
        """T3b: All out-of-range markers → empty spike list after clamping."""
        from app import markers_to_elevation_spikes, clamp_ocr_value
        # Values that should all be dropped: one negative, one way above 50
        raw = [(-1.0, (10, 20)), (999.0, (30, 40))]
        markers = [(x, y, v) for v, (x, y) in raw]
        # clamp_ocr_value should return None for these
        assert clamp_ocr_value(-1.0) is None
        assert clamp_ocr_value(999.0) is None
        # markers_to_elevation_spikes should drop them
        spikes = markers_to_elevation_spikes(markers)
        assert spikes == []


# ---------------------------------------------------------------------------
# T4  Filter unrealistic OCR reads (clamping / exclusion)
# ---------------------------------------------------------------------------

class TestClampOcrValue:
    """
    T4: clamp_ocr_value(v) accepts 0 < v <= 50, rejects outside that range.
    """

    def test_accepts_typical_golf_range(self):
        """T4a: Values in 0.1..50.0 are returned as-is."""
        from app import clamp_ocr_value
        for v in [0.1, 1.0, 2.8, 10.0, 25.0, 50.0]:
            assert clamp_ocr_value(v) == pytest.approx(v), f"Expected {v} to pass"

    def test_rejects_zero(self):
        """T4b: Value 0.0 is dropped (below minimum meaningful elevation)."""
        from app import clamp_ocr_value
        assert clamp_ocr_value(0.0) is None

    def test_rejects_negative(self):
        """T4c: Negative values are dropped."""
        from app import clamp_ocr_value
        assert clamp_ocr_value(-1.5) is None
        assert clamp_ocr_value(-0.01) is None

    def test_rejects_above_50(self):
        """T4d: Values > 50 mm are unrealistic for a golf plate — dropped."""
        from app import clamp_ocr_value
        assert clamp_ocr_value(50.1) is None
        assert clamp_ocr_value(100.0) is None
        assert clamp_ocr_value(999.9) is None

    def test_boundary_exactly_50(self):
        """T4e: 50.0 is the hard cap — accepted."""
        from app import clamp_ocr_value
        assert clamp_ocr_value(50.0) == pytest.approx(50.0)

    def test_boundary_just_above_50(self):
        """T4f: 50.01 is above the cap — rejected."""
        from app import clamp_ocr_value
        assert clamp_ocr_value(50.01) is None

    def test_markers_to_elevation_spikes_drops_out_of_range(self):
        """T4g: markers_to_elevation_spikes drops markers outside 0..50 range."""
        from app import markers_to_elevation_spikes
        markers = [
            (10, 10, 2.5),    # valid
            (20, 20, 51.0),   # too high → dropped
            (30, 30, 0.0),    # zero → dropped
            (40, 40, -1.0),   # negative → dropped
            (50, 50, 50.0),   # exactly at cap → kept
        ]
        spikes = markers_to_elevation_spikes(markers)
        mm_vals = [sp["mm"] for sp in spikes]
        assert pytest.approx(2.5) in mm_vals
        assert pytest.approx(50.0) in mm_vals
        assert len(spikes) == 2, f"Expected 2 valid spikes, got {len(spikes)}: {spikes}"


# ---------------------------------------------------------------------------
# T5  EGM round-trip — OCR spikes save and reload correctly
# ---------------------------------------------------------------------------

class TestEgmRoundTrip:

    def test_elevation_spikes_round_trip(self, app_client, tmp_path, monkeypatch):
        """T5: POST spikes → /api/boundaries; GET via /api/boundaries/load → same spikes."""
        import app as _app_module
        # Set up a temp EGM base the save route can write to
        egm_base = tmp_path / "GolfCourses"
        egm_base.mkdir(parents=True)
        monkeypatch.setattr(_app_module, "_EGM_BASE", str(egm_base))

        spikes = [
            {"x": 100, "y": 200, "mm": 2.8},
            {"x": 300, "y": 150, "mm": 4.1},
        ]
        payload = {
            "course": "TestCourse",
            "hole": "8",
            "image": "test.png",
            "polygons": [],
            "elevationSpikes": spikes,
        }
        # Save
        resp_save = app_client.post(
            "/api/boundaries",
            data=json.dumps(payload),
            content_type="application/json",
        )
        assert resp_save.status_code == 200
        save_data = resp_save.get_json()
        assert save_data["status"] == "ok"
        fname = save_data["filename"]

        # Reload
        resp_load = app_client.get(f"/api/boundaries/load?filename={fname}")
        assert resp_load.status_code == 200
        load_data = resp_load.get_json()
        assert load_data["status"] == "ok"
        loaded_spikes = load_data.get("elevationSpikes", [])
        assert len(loaded_spikes) == 2
        # Check values round-tripped correctly
        mm_vals = [sp["mm"] for sp in loaded_spikes]
        assert pytest.approx(2.8) in mm_vals
        assert pytest.approx(4.1) in mm_vals

    def test_empty_spikes_round_trip(self, app_client, tmp_path, monkeypatch):
        """T5b: Empty elevationSpikes field survives save→load."""
        import app as _app_module
        egm_base = tmp_path / "GolfCourses"
        egm_base.mkdir(parents=True)
        monkeypatch.setattr(_app_module, "_EGM_BASE", str(egm_base))

        payload = {
            "course": "EmptyCourse",
            "hole": "1",
            "image": "empty.png",
            "polygons": [],
            "elevationSpikes": [],
        }
        resp_save = app_client.post(
            "/api/boundaries",
            data=json.dumps(payload),
            content_type="application/json",
        )
        assert resp_save.status_code == 200
        fname = resp_save.get_json()["filename"]

        resp_load = app_client.get(f"/api/boundaries/load?filename={fname}")
        load_data = resp_load.get_json()
        assert load_data.get("elevationSpikes") == []


# ---------------------------------------------------------------------------
# T6 + T7  /api/detect_boundaries returns elevationMarkers field
# ---------------------------------------------------------------------------

class TestDetectBoundariesReturnsElevationMarkers:
    """
    T6: The /api/detect_boundaries endpoint returns an 'elevationMarkers' key
        in its JSON response alongside 'polygons'.
    T7: Each element is {x: int, y: int, mm: float} with values in 0..50 range
        and pixel coords within image bounds.
    """

    def _make_test_image(self, course_dir: Path, filename: str = "test.png") -> Path:
        """Write a 400×400 coloured image the endpoint can read."""
        img = Image.new("RGB", (400, 400), color=(100, 150, 80))
        p = course_dir / filename
        img.save(str(p))
        return p

    def test_elevation_markers_key_present(self, app_client, tmp_path, monkeypatch):
        """T6a: Response from /api/detect_boundaries includes 'elevationMarkers' key."""
        import app as _app_module
        # Put the image where the route can find it
        img_dir = tmp_path / "team_inbox"
        img_dir.mkdir(parents=True)
        self._make_test_image(img_dir, "test.png")
        monkeypatch.setattr(_app_module, "_TEAM_INBOX",
                            str(img_dir), raising=False)
        # Patch _find_image_path to return our temp image directly
        monkeypatch.setattr(
            _app_module, "_find_image_path",
            lambda name, preferred_course="": str(img_dir / name)
        )
        resp = app_client.post(
            "/api/detect_boundaries",
            data=json.dumps({"image": "test.png", "course": "TestCourse"}),
            content_type="application/json",
        )
        assert resp.status_code == 200
        data = resp.get_json()
        assert data["status"] == "ok"
        assert "elevationMarkers" in data, (
            "Response must include 'elevationMarkers' key. "
            f"Got keys: {list(data.keys())}"
        )

    def test_elevation_markers_is_list(self, app_client, tmp_path, monkeypatch):
        """T6b: elevationMarkers is a list (may be empty on a plain-color image)."""
        import app as _app_module
        img_dir = tmp_path / "team_inbox"
        img_dir.mkdir(parents=True)
        self._make_test_image(img_dir, "test.png")
        monkeypatch.setattr(
            _app_module, "_find_image_path",
            lambda name, preferred_course="": str(img_dir / name)
        )
        resp = app_client.post(
            "/api/detect_boundaries",
            data=json.dumps({"image": "test.png", "course": "TestCourse"}),
            content_type="application/json",
        )
        data = resp.get_json()
        assert isinstance(data["elevationMarkers"], list)

    def test_elevation_markers_have_correct_shape(self, app_client, tmp_path, monkeypatch):
        """T7: If markers present, each has x (int), y (int), mm (float) keys."""
        import app as _app_module
        img_dir = tmp_path / "team_inbox"
        img_dir.mkdir(parents=True)
        # Build a synthetic GI-style image with markers
        p = img_dir / "gi_markers.png"
        _make_synthetic_gi_image(p, [(80, 80, "2.8"), (200, 200, "1.4")])
        monkeypatch.setattr(
            _app_module, "_find_image_path",
            lambda name, preferred_course="": str(img_dir / name)
        )
        resp = app_client.post(
            "/api/detect_boundaries",
            data=json.dumps({"image": "gi_markers.png", "course": "TestCourse"}),
            content_type="application/json",
        )
        data = resp.get_json()
        markers = data.get("elevationMarkers", [])
        for m in markers:
            assert "x" in m and "y" in m and "mm" in m, (
                f"Marker missing required keys: {m}"
            )
            assert isinstance(m["x"], int), f"x should be int: {m}"
            assert isinstance(m["y"], int), f"y should be int: {m}"
            assert isinstance(m["mm"], float), f"mm should be float: {m}"
            assert 0 < m["mm"] <= 50.0, f"mm out of range: {m}"


# ---------------------------------------------------------------------------
# T8  clamp_ocr_value boundary conditions
# ---------------------------------------------------------------------------

class TestClampOcrValueBoundaries:
    """Additional boundary checks for clamp_ocr_value."""

    def test_very_small_positive_accepted(self):
        """T8a: 0.1 (smallest plausible marker value) is accepted."""
        from app import clamp_ocr_value
        assert clamp_ocr_value(0.1) == pytest.approx(0.1)

    def test_value_at_50_is_accepted(self):
        """T8b: 50.0 is the hard cap and should pass."""
        from app import clamp_ocr_value
        assert clamp_ocr_value(50.0) == pytest.approx(50.0)

    def test_nan_rejected(self):
        """T8c: NaN produces None."""
        from app import clamp_ocr_value
        import math
        assert clamp_ocr_value(math.nan) is None

    def test_inf_rejected(self):
        """T8d: Infinity produces None."""
        from app import clamp_ocr_value
        import math
        assert clamp_ocr_value(math.inf) is None


# ---------------------------------------------------------------------------
# T9  JS source — runDetection() populates elevationSpikes from result
# ---------------------------------------------------------------------------

EDITOR_HTML = os.path.join(os.path.dirname(__file__), "..", "templates", "editor.html")


def _read_editor_js() -> str:
    with open(EDITOR_HTML, "r") as f:
        return f.read()


class TestRunDetectionPopulatesElevationSpikes:
    """
    T9: runDetection() in editor.html must assign this.elevationSpikes from
        the 'elevationMarkers' field returned by /api/detect_boundaries.
    """

    def test_runDetection_reads_elevationMarkers(self):
        """T9a: runDetection() must reference result.elevationMarkers."""
        src = _read_editor_js()
        assert "elevationMarkers" in src, (
            "editor.html does not reference 'elevationMarkers'. "
            "runDetection() must consume the elevationMarkers key from the API response."
        )

    def test_runDetection_assigns_elevationSpikes(self):
        """T9b: runDetection() must assign this.elevationSpikes from the OCR result."""
        import re
        src = _read_editor_js()
        # Find the runDetection function body
        m = re.search(r'runDetection\s*\(\s*\)\s*\{(.+?)^\s*\},', src,
                      re.DOTALL | re.MULTILINE)
        assert m, "runDetection() function body not found in editor.html"
        body = m.group(1)
        assert "elevationSpikes" in body, (
            "runDetection() must assign this.elevationSpikes from elevationMarkers. "
            "Body snippet: " + body[:300]
        )

    def test_elevationSpikes_populated_with_mm_field(self):
        """T9c: The populated spikes must carry a 'mm' field mapping."""
        import re
        src = _read_editor_js()
        m = re.search(r'runDetection\s*\(\s*\)\s*\{(.+?)^\s*\},', src,
                      re.DOTALL | re.MULTILINE)
        assert m, "runDetection() not found"
        body = m.group(1)
        # The assignment block should reference 'mm' (mapping OCR value to spike mm)
        assert ".mm" in body or '"mm"' in body or "'mm'" in body, (
            "runDetection() spike construction must include a 'mm' field. "
            "Each elevationMarker becomes an elevationSpike with {x, y, mm}."
        )


# ---------------------------------------------------------------------------
# T10  Zero-value markers are excluded
# ---------------------------------------------------------------------------

class TestZeroValueFiltered:

    def test_zero_value_excluded_from_spikes(self):
        """T10: A marker with value 0.0 must not appear in elevationSpikes."""
        from app import markers_to_elevation_spikes
        markers = [(50, 50, 0.0), (100, 100, 1.5)]
        spikes = markers_to_elevation_spikes(markers)
        mm_vals = [sp["mm"] for sp in spikes]
        assert 0.0 not in mm_vals
        assert pytest.approx(1.5) in mm_vals
        assert len(spikes) == 1
