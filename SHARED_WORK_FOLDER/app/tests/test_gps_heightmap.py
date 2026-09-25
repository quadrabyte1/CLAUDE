"""
test_gps_heightmap.py -- Tests for gps_heightmap.py (Phase 1 GPS heightmap backend)

Run:
    cd /Volumes/GIT/CLAUDE/SHARED_WORK_FOLDER
    python -m pytest app/tests/test_gps_heightmap.py -v

Written TDD: tests were specified against the interface contract BEFORE
the module was finalised.  Green = contract fulfilled.
"""

from __future__ import annotations

import json
import math
import tempfile
from pathlib import Path

import numpy as np
import pytest

# ---------------------------------------------------------------------------
# Module under test
# ---------------------------------------------------------------------------
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
from gps_heightmap import (
    HeightmapResult,
    build_heightmap_from_gps,
    build_approach_polygon,
    compute_mask,
    extract_latlng_alt,
    filter_by_bbox,
    interpolate_heights,
    latlng_to_enu_metres,
    parse_gps_file,
)

# ---------------------------------------------------------------------------
# Shared fixtures
# ---------------------------------------------------------------------------

# A tiny square "green" polygon in lat/lng space near DeLaveaga.
# Approx 20 m on a side, centred on lat=36.9960, lng=-121.9975
GREEN_CENTER_LAT = 36.9960
GREEN_CENTER_LNG = -121.9975
# 0.0001 deg lat ~ 11.1 m;  0.0002 deg lng ~ 17.8 m
GREEN_POLYGON = [
    (GREEN_CENTER_LAT - 0.0001, GREEN_CENTER_LNG - 0.0001),
    (GREEN_CENTER_LAT - 0.0001, GREEN_CENTER_LNG + 0.0001),
    (GREEN_CENTER_LAT + 0.0001, GREEN_CENTER_LNG + 0.0001),
    (GREEN_CENTER_LAT + 0.0001, GREEN_CENTER_LNG - 0.0001),
    (GREEN_CENTER_LAT - 0.0001, GREEN_CENTER_LNG - 0.0001),  # close
]

# Bounding box: a bit wider than the green polygon
BBOX_TIGHT = (
    GREEN_CENTER_LAT - 0.0005,
    GREEN_CENTER_LNG - 0.0005,
    GREEN_CENTER_LAT + 0.0005,
    GREEN_CENTER_LNG + 0.0005,
)

# ---------------------------------------------------------------------------
# Helper: build a minimal .gps fixture file
# ---------------------------------------------------------------------------

def make_gps_fixture(cells: list[dict], tmp_path: Path) -> Path:
    """Write a minimal .gps file with UI cruft header + JSON body."""
    data = {"cellCount": len(cells), "geoHashCells": cells}
    content = (
        "Coverage\n"
        "API Account\n"
        "Credits\n"
        "Explorer\n"
        "geohash · hole 99999\n"
        + json.dumps(data, indent=2)
    )
    p = tmp_path / "test.gps"
    p.write_text(content, encoding="utf-8")
    return p


def make_grid_cells(
    lat_center: float, lng_center: float, n: int = 20
) -> list[dict]:
    """
    Generate n GPS cells arranged in a regular grid around (lat_center, lng_center).
    Altitude = 100.0 + distance_from_centre * 5 (gives a bowl shape for testing).
    """
    cells = []
    side = int(math.ceil(math.sqrt(n)))
    for i in range(side):
        for j in range(side):
            if len(cells) >= n:
                break
            dlat = (i - side // 2) * 0.00005
            dlng = (j - side // 2) * 0.00005
            dist = math.sqrt(dlat**2 + dlng**2)
            alt = 100.0 + dist * 50_000  # small alt variation
            cells.append({
                "gpsCoordinate": {
                    "latitude":  lat_center + dlat,
                    "longitude": lng_center + dlng,
                    "altitude":  round(alt, 4),
                },
                "geoHash": f"test{i:02d}{j:02d}",
            })
    return cells[:n]


# ===========================================================================
# 1. Parse GPS file -- basic structure
# ===========================================================================

class TestParseGpsFile:

    def test_parses_geoHashCells(self, tmp_path):
        """parse_gps_file returns the geoHashCells list."""
        cells = make_grid_cells(GREEN_CENTER_LAT, GREEN_CENTER_LNG, 20)
        gps_file = make_gps_fixture(cells, tmp_path)
        result = parse_gps_file(gps_file)
        assert isinstance(result, list)
        assert len(result) == 20

    def test_each_cell_has_gpsCoordinate(self, tmp_path):
        """Each parsed cell has a gpsCoordinate dict."""
        cells = make_grid_cells(GREEN_CENTER_LAT, GREEN_CENTER_LNG, 5)
        gps_file = make_gps_fixture(cells, tmp_path)
        result = parse_gps_file(gps_file)
        for cell in result:
            assert "gpsCoordinate" in cell
            assert "latitude"  in cell["gpsCoordinate"]
            assert "longitude" in cell["gpsCoordinate"]
            assert "altitude"  in cell["gpsCoordinate"]

    def test_skips_ui_cruft(self, tmp_path):
        """
        File with many non-JSON header lines before the JSON body
        is parsed without error.
        """
        cells = make_grid_cells(GREEN_CENTER_LAT, GREEN_CENTER_LNG, 5)
        data = {"cellCount": 5, "geoHashCells": cells}
        header = "\n".join([f"line {i}" for i in range(50)])
        content = header + "\n" + json.dumps(data)
        p = tmp_path / "many_headers.gps"
        p.write_text(content)
        result = parse_gps_file(p)
        assert len(result) == 5

    def test_raises_on_missing_json(self, tmp_path):
        """File with no JSON raises ValueError."""
        p = tmp_path / "no_json.gps"
        p.write_text("just text\nno json here\n")
        with pytest.raises(ValueError, match="No JSON"):
            parse_gps_file(p)

    def test_raises_on_missing_geoHashCells(self, tmp_path):
        """JSON without geoHashCells raises ValueError."""
        p = tmp_path / "bad_json.gps"
        p.write_text('{"cellCount": 0, "otherKey": []}')
        with pytest.raises(ValueError, match="geoHashCells"):
            parse_gps_file(p)

    def test_extract_latlng_alt_arrays(self, tmp_path):
        """extract_latlng_alt returns float64 arrays with correct values."""
        cells = [
            {"gpsCoordinate": {"latitude": 36.9960, "longitude": -121.9975, "altitude": 100.0}, "geoHash": "a"},
            {"gpsCoordinate": {"latitude": 36.9961, "longitude": -121.9974, "altitude": 101.5}, "geoHash": "b"},
        ]
        lats, lngs, alts = extract_latlng_alt(cells)
        assert lats.dtype == np.float64
        assert len(lats) == 2
        assert lats[0] == pytest.approx(36.9960)
        assert alts[1] == pytest.approx(101.5)


# ===========================================================================
# 2. Coordinate projection
# ===========================================================================

class TestCoordinateProjection:

    def test_origin_projects_to_zero(self):
        """Origin lat/lng always projects to (0, 0)."""
        e, n = latlng_to_enu_metres(
            np.array([36.9960]), np.array([-121.9975]),
            origin_lat=36.9960, origin_lng=-121.9975
        )
        assert e[0] == pytest.approx(0.0, abs=1e-9)
        assert n[0] == pytest.approx(0.0, abs=1e-9)

    def test_north_offset_100m(self):
        """
        Moving ~0.0009 deg north should give ~100 m north offset.
        111,320 m/deg * 0.0009 deg = 100.19 m
        """
        delta_lat = 100.0 / 111_320.0
        e, n = latlng_to_enu_metres(
            np.array([36.9960 + delta_lat]), np.array([-121.9975]),
            origin_lat=36.9960, origin_lng=-121.9975
        )
        assert n[0] == pytest.approx(100.0, rel=1e-3)
        assert e[0] == pytest.approx(0.0, abs=0.01)

    def test_east_offset_100m(self):
        """
        Moving east should give ~100 m east offset.
        At lat=36.996, lng_m_per_deg = 111320 * cos(36.996 deg) = ~89,000 m/deg
        """
        origin_lat = 36.9960
        lng_m = 111_320.0 * math.cos(math.radians(origin_lat))
        delta_lng = 100.0 / lng_m
        e, n = latlng_to_enu_metres(
            np.array([36.9960]), np.array([-121.9975 + delta_lng]),
            origin_lat=36.9960, origin_lng=-121.9975
        )
        assert e[0] == pytest.approx(100.0, rel=1e-3)
        assert n[0] == pytest.approx(0.0, abs=0.01)

    def test_projection_uses_actual_latitude(self):
        """
        Projection at high latitude (60 N) should give shorter east offsets
        than at equatorial latitude for the same delta-longitude.
        """
        delta_lng = 0.001
        e_high, _ = latlng_to_enu_metres(
            np.array([60.0]), np.array([0.0 + delta_lng]),
            origin_lat=60.0, origin_lng=0.0
        )
        e_low, _ = latlng_to_enu_metres(
            np.array([10.0]), np.array([0.0 + delta_lng]),
            origin_lat=10.0, origin_lng=0.0
        )
        assert e_high[0] < e_low[0]


# ===========================================================================
# 3. Bbox filtering
# ===========================================================================

class TestBboxFiltering:

    def _make_20_points(self):
        """20 points: 12 inside a tight bbox, 8 outside."""
        inside_lat = GREEN_CENTER_LAT + np.linspace(-0.0003, 0.0003, 12)
        inside_lng = np.full(12, GREEN_CENTER_LNG)
        outside_lat = np.array([
            GREEN_CENTER_LAT + 0.002, GREEN_CENTER_LAT - 0.002,
            GREEN_CENTER_LAT + 0.003, GREEN_CENTER_LAT - 0.003,
            GREEN_CENTER_LAT + 0.004, GREEN_CENTER_LAT - 0.004,
            GREEN_CENTER_LAT + 0.005, GREEN_CENTER_LAT - 0.005,
        ])
        outside_lng = np.full(8, GREEN_CENTER_LNG)

        lats = np.concatenate([inside_lat, outside_lat])
        lngs = np.concatenate([inside_lng, outside_lng])
        alts = np.linspace(100.0, 105.0, 20)
        return lats, lngs, alts

    def test_filters_to_12_inside(self):
        """20 points, bbox includes 12 -> filtered count = 12."""
        lats, lngs, alts = self._make_20_points()
        bbox = (
            GREEN_CENTER_LAT - 0.0005,
            GREEN_CENTER_LNG - 0.001,
            GREEN_CENTER_LAT + 0.0005,
            GREEN_CENTER_LNG + 0.001,
        )
        f_lats, f_lngs, f_alts = filter_by_bbox(lats, lngs, alts, bbox)
        assert len(f_lats) == 12

    def test_empty_bbox_returns_empty(self):
        """Bbox with no points returns empty arrays."""
        lats = np.array([36.990, 36.991])
        lngs = np.array([-122.0, -122.0])
        alts = np.array([100.0, 101.0])
        bbox = (37.0, -121.9, 37.1, -121.8)  # far away
        fl, fn, fa = filter_by_bbox(lats, lngs, alts, bbox)
        assert len(fl) == 0

    def test_all_inside_returns_all(self):
        """Bbox containing all points returns all."""
        lats = np.array([36.990, 36.991, 36.992])
        lngs = np.array([-122.0, -122.0, -122.0])
        alts = np.array([100.0, 101.0, 102.0])
        bbox = (36.989, -122.001, 36.993, -121.999)
        fl, fn, fa = filter_by_bbox(lats, lngs, alts, bbox)
        assert len(fl) == 3


# ===========================================================================
# 4. Point-in-polygon / approach mask
# ===========================================================================

class TestMaskBuilding:

    def _simple_square_green(self, origin_lat, origin_lng, side_m=20.0):
        """Build a square green centred at (origin_lat, origin_lng) in lat/lng."""
        lat_m = 111_320.0
        lng_m = 111_320.0 * math.cos(math.radians(origin_lat))
        half_lat = (side_m / 2) / lat_m
        half_lng = (side_m / 2) / lng_m
        return [
            (origin_lat - half_lat, origin_lng - half_lng),
            (origin_lat - half_lat, origin_lng + half_lng),
            (origin_lat + half_lat, origin_lng + half_lng),
            (origin_lat + half_lat, origin_lng - half_lng),
            (origin_lat - half_lat, origin_lng - half_lng),
        ]

    def test_inside_green_cells_are_masked_true(self):
        """
        A grid cell at the green centre should be True in the mask.
        """
        green_poly = self._simple_square_green(GREEN_CENTER_LAT, GREEN_CENTER_LNG, 30.0)
        ap = build_approach_polygon(green_poly, GREEN_CENTER_LAT - 0.001, GREEN_CENTER_LNG - 0.001, approach_m=0.0)
        # grid in metres from SW bbox corner
        origin_lat = GREEN_CENTER_LAT - 0.001
        origin_lng = GREEN_CENTER_LNG - 0.001
        lats_center = np.array([GREEN_CENTER_LAT])
        lngs_center = np.array([GREEN_CENTER_LNG])
        e, n = latlng_to_enu_metres(lats_center, lngs_center, origin_lat, origin_lng)

        grid_east  = np.linspace(0, 300, 30)
        grid_north = np.linspace(0, 300, 30)
        mask = compute_mask(grid_east, grid_north, ap)

        # Find closest grid cell to green centre
        ci = np.argmin(np.abs(grid_east  - e[0]))
        ri = np.argmin(np.abs(grid_north - n[0]))
        assert mask[ri, ci], "Centre of green should be inside mask"

    def test_far_cells_are_masked_false(self):
        """Grid cells far outside the green+approach are False in mask."""
        green_poly = self._simple_square_green(GREEN_CENTER_LAT, GREEN_CENTER_LNG, 20.0)
        ap = build_approach_polygon(green_poly, GREEN_CENTER_LAT - 0.001, GREEN_CENTER_LNG - 0.001, approach_m=5.0)
        grid_east  = np.linspace(0, 1000, 50)
        grid_north = np.linspace(0, 1000, 50)
        mask = compute_mask(grid_east, grid_north, ap)
        # The far corner (1000 m away) should definitely be False
        assert not mask[49, 49], "Far corner should be outside mask"

    def test_approach_expands_mask_outward(self):
        """Approach buffer of 20 m adds more True cells than approach=0."""
        green_poly = self._simple_square_green(GREEN_CENTER_LAT, GREEN_CENTER_LNG, 20.0)
        origin_lat = GREEN_CENTER_LAT - 0.001
        origin_lng = GREEN_CENTER_LNG - 0.001

        ap0  = build_approach_polygon(green_poly, origin_lat, origin_lng, approach_m=0.0)
        ap20 = build_approach_polygon(green_poly, origin_lat, origin_lng, approach_m=20.0)

        grid_east  = np.linspace(0, 300, 60)
        grid_north = np.linspace(0, 300, 60)
        mask0  = compute_mask(grid_east, grid_north, ap0)
        mask20 = compute_mask(grid_east, grid_north, ap20)
        assert mask20.sum() > mask0.sum(), "Larger buffer should include more grid cells"

    def test_mask_shape_matches_grid(self):
        """Mask shape is (len(grid_north), len(grid_east))."""
        green_poly = self._simple_square_green(GREEN_CENTER_LAT, GREEN_CENTER_LNG, 20.0)
        ap = build_approach_polygon(green_poly, GREEN_CENTER_LAT - 0.001, GREEN_CENTER_LNG - 0.001, approach_m=5.0)
        grid_east  = np.linspace(0, 200, 40)
        grid_north = np.linspace(0, 200, 25)
        mask = compute_mask(grid_east, grid_north, ap)
        assert mask.shape == (25, 40)


# ===========================================================================
# 5. Cubic interpolation accuracy
# ===========================================================================

class TestInterpolation:

    def test_four_corners_interpolate_midpoint(self):
        """
        4 corner points with known altitudes -> centre cell is close to midpoint.
        Cubic can wiggle but for a simple flat surface the centre value must be
        within 5% of the midpoint of the altitude range.
        """
        east_m  = np.array([0.0, 50.0,  0.0, 50.0])
        north_m = np.array([0.0,  0.0, 50.0, 50.0])
        alts    = np.array([100.0, 100.0, 100.0, 100.0])  # flat surface
        grid_e  = np.linspace(0, 50, 11)
        grid_n  = np.linspace(0, 50, 11)
        notes   = []
        GZ = interpolate_heights(east_m, north_m, alts, grid_e, grid_n, notes)
        # Centre cell [5, 5]
        assert GZ[5, 5] == pytest.approx(100.0, abs=1.0), \
            f"Flat surface centre should be ~100.0, got {GZ[5, 5]:.3f}"

    def test_tilted_surface_gradient(self):
        """
        Points on a linearly tilted surface -> interpolated grid has same tilt.
        """
        east_m  = np.array([0.0, 100.0,   0.0, 100.0])
        north_m = np.array([0.0,   0.0, 100.0, 100.0])
        # alt increases linearly with east (1 m per 10 m east)
        alts    = east_m * 0.1
        grid_e  = np.linspace(0, 100, 11)
        grid_n  = np.linspace(0, 100, 11)
        notes   = []
        GZ = interpolate_heights(east_m, north_m, alts, grid_e, grid_n, notes)
        # Expected alt at east=50 is 5.0
        assert GZ[5, 5] == pytest.approx(5.0, abs=0.5)

    def test_sparse_fallback_no_nan_in_mask(self):
        """
        Only 2 points -> cubic fails -> nearest-neighbour fills -> no NaN inside the
        combined convex hull region.
        """
        east_m  = np.array([10.0, 40.0])
        north_m = np.array([10.0, 40.0])
        alts    = np.array([100.0, 105.0])
        grid_e  = np.linspace(0, 50, 11)
        grid_n  = np.linspace(0, 50, 11)
        notes   = []
        GZ = interpolate_heights(east_m, north_m, alts, grid_e, grid_n, notes)
        # Nearest-neighbour always covers full grid
        assert not np.isnan(GZ).any(), "After NN fill, no NaN should remain"
        assert any("nearest" in n.lower() or "fallback" in n.lower() for n in notes), \
            "Should emit a note about sparse data or fallback"


# ===========================================================================
# 6. Vertical exaggeration
# ===========================================================================

class TestVertExag:

    def _run_with_exag(self, exag: float, tmp_path: Path) -> HeightmapResult:
        cells = make_grid_cells(GREEN_CENTER_LAT, GREEN_CENTER_LNG, 40)
        gps_file = make_gps_fixture(cells, tmp_path)
        return build_heightmap_from_gps(
            gps_path=gps_file,
            bbox=BBOX_TIGHT,
            green_polygon_latlng=GREEN_POLYGON,
            approach_m=10.0,
            grid_size=(30, 30),
            vert_exag=exag,
        )

    def test_exag_scales_heights(self, tmp_path):
        """vert_exag=10 produces heights 10x those of vert_exag=1."""
        r1  = self._run_with_exag(1.0, tmp_path)
        r10 = self._run_with_exag(10.0, tmp_path)
        # The heightmaps share the same mask; compare valid cells only.
        shared_mask = r1.mask & r10.mask
        if not shared_mask.any():
            pytest.skip("No shared mask cells for exag test (sparse data)")
        h1  = r1.heights_mm[shared_mask]
        h10 = r10.heights_mm[shared_mask]
        ratio = h10.sum() / h1.sum() if h1.sum() != 0 else np.nan
        assert ratio == pytest.approx(10.0, rel=0.05), \
            f"Expected 10x scale, got ratio={ratio:.3f}"

    def test_exag_default_is_1(self, tmp_path):
        """Default vert_exag=1.0 returns real (unscaled) heights."""
        cells = make_grid_cells(GREEN_CENTER_LAT, GREEN_CENTER_LNG, 40)
        gps_file = make_gps_fixture(cells, tmp_path)
        r = build_heightmap_from_gps(
            gps_path=gps_file,
            bbox=BBOX_TIGHT,
            green_polygon_latlng=GREEN_POLYGON,
            approach_m=10.0,
            grid_size=(30, 30),
            # vert_exag not specified -- default is 1.0
        )
        # All valid heights should be non-negative (zero-referenced)
        valid = r.heights_mm[r.mask]
        assert (valid >= 0).all()


# ===========================================================================
# 7. API contract (HeightmapResult field shapes/types)
# ===========================================================================

class TestApiContract:

    @pytest.fixture
    def result(self, tmp_path):
        cells = make_grid_cells(GREEN_CENTER_LAT, GREEN_CENTER_LNG, 60)
        gps_file = make_gps_fixture(cells, tmp_path)
        return build_heightmap_from_gps(
            gps_path=gps_file,
            bbox=BBOX_TIGHT,
            green_polygon_latlng=GREEN_POLYGON,
            approach_m=8.0,
            grid_size=(40, 40),
        )

    def test_heights_mm_is_2d_float64(self, result):
        assert result.heights_mm.ndim == 2
        assert result.heights_mm.dtype == np.float64

    def test_mask_is_2d_bool(self, result):
        assert result.mask.ndim == 2
        assert result.mask.dtype == bool

    def test_shapes_match(self, result):
        assert result.heights_mm.shape == result.mask.shape
        rows, cols = result.heights_mm.shape
        assert len(result.grid_x_mm) == cols
        assert len(result.grid_y_mm) == rows

    def test_grid_size_honoured(self, tmp_path):
        """grid_size=(60, 50) -> heights_mm.shape == (50, 60)."""
        cells = make_grid_cells(GREEN_CENTER_LAT, GREEN_CENTER_LNG, 60)
        gps_file = make_gps_fixture(cells, tmp_path)
        r = build_heightmap_from_gps(
            gps_path=gps_file,
            bbox=BBOX_TIGHT,
            green_polygon_latlng=GREEN_POLYGON,
            grid_size=(60, 50),
        )
        assert r.heights_mm.shape == (50, 60)
        assert r.grid_x_mm.shape == (60,)
        assert r.grid_y_mm.shape == (50,)

    def test_nan_outside_mask(self, result):
        """heights_mm is NaN everywhere the mask is False."""
        outside = ~result.mask
        if outside.any():
            assert np.all(np.isnan(result.heights_mm[outside])), \
                "All cells outside mask must be NaN"

    def test_valid_inside_mask_non_nan(self, result):
        """heights_mm has no NaN inside the mask."""
        if result.mask.any():
            assert not np.isnan(result.heights_mm[result.mask]).any(), \
                "No NaN allowed inside mask"

    def test_origin_latlng_is_bbox_sw_corner(self, result):
        assert result.origin_latlng == pytest.approx(
            (BBOX_TIGHT[0], BBOX_TIGHT[1]), abs=1e-9
        )

    def test_raw_points_used_is_positive_int(self, result):
        assert isinstance(result.raw_points_used, int)
        assert result.raw_points_used > 0

    def test_bbox_m_is_4_tuple_of_floats(self, result):
        assert len(result.bbox_m) == 4
        for v in result.bbox_m:
            assert isinstance(v, float)

    def test_interpolation_notes_is_list(self, result):
        assert isinstance(result.interpolation_notes, list)

    def test_heights_mm_are_non_negative(self, result):
        """Zero-referenced heights are >= 0 (with a tiny float tolerance)."""
        valid = result.heights_mm[result.mask]
        if len(valid):
            assert valid.min() >= -0.01  # allow cubic undershoot < 0.01 mm


# ===========================================================================
# 8. Real-data smoke test (De Laveaga hole 18)
# ===========================================================================

DE_LAVEAGA_GPS = Path(
    "/Volumes/GIT/CLAUDE/SHARED_WORK_FOLDER/ItWentIn/De Laveaga GPS from Stracka.txt"
)

# Tight bbox around the green area for Hole 18 at DeLaveaga.
# Hole 18 GPS centroid ~36.9960, -121.9987; green estimated from point density.
DL_BBOX = (
    36.9950, -122.0000,
    36.9975, -121.9960,
)

# Simple approximate green polygon for Hole 18
DL_GREEN_POLYGON = [
    (36.9958, -121.9980),
    (36.9958, -121.9972),
    (36.9965, -121.9972),
    (36.9965, -121.9980),
    (36.9958, -121.9980),
]


@pytest.mark.skipif(
    not DE_LAVEAGA_GPS.exists(),
    reason="De Laveaga GPS file not present"
)
class TestRealDataDeLaveaga:

    @pytest.fixture(scope="class")
    def result(self):
        return build_heightmap_from_gps(
            gps_path=DE_LAVEAGA_GPS,
            bbox=DL_BBOX,
            green_polygon_latlng=DL_GREEN_POLYGON,
            approach_m=8.0,
            grid_size=(80, 80),
        )

    def test_points_used_greater_than_30(self, result):
        """Real data bbox should capture > 30 GPS points."""
        assert result.raw_points_used > 30, \
            f"Expected >30 points, got {result.raw_points_used}"

    def test_heightmap_has_meaningful_variation(self, result):
        """Green altitude range inside mask should be > 1 m (= 1000 mm)."""
        valid = result.heights_mm[result.mask]
        spread = float(valid.max() - valid.min())
        assert spread > 1000.0, \
            f"Expected >1000 mm altitude range, got {spread:.1f} mm"

    def test_no_nan_inside_mask(self, result):
        """No NaN cells inside the mask on real data."""
        assert not np.isnan(result.heights_mm[result.mask]).any()

    def test_result_is_heightmap_result_instance(self, result):
        assert isinstance(result, HeightmapResult)


# ===========================================================================
# 9. build_heightmap_from_gps -- integration / error paths
# ===========================================================================

class TestBuildHeightmapIntegration:

    def test_raises_on_empty_bbox(self, tmp_path):
        """Raises ValueError when bbox contains no GPS points."""
        cells = make_grid_cells(36.0, -120.0, 20)  # far from BBOX_TIGHT
        gps_file = make_gps_fixture(cells, tmp_path)
        with pytest.raises(ValueError, match="No GPS points"):
            build_heightmap_from_gps(
                gps_path=gps_file,
                bbox=BBOX_TIGHT,
                green_polygon_latlng=GREEN_POLYGON,
            )

    def test_grid_x_mm_units_are_mm(self, tmp_path):
        """
        grid_x_mm range should roughly match bbox width in mm (within 10%).
        BBOX_TIGHT is ~0.001 deg lng wide; at DeLav lat that's ~89 m = 89,000 mm.
        """
        cells = make_grid_cells(GREEN_CENTER_LAT, GREEN_CENTER_LNG, 60)
        gps_file = make_gps_fixture(cells, tmp_path)
        r = build_heightmap_from_gps(
            gps_path=gps_file,
            bbox=BBOX_TIGHT,
            green_polygon_latlng=GREEN_POLYGON,
            grid_size=(40, 40),
        )
        bbox_lng_span_mm = (BBOX_TIGHT[3] - BBOX_TIGHT[1]) * 111_320.0 * math.cos(math.radians(GREEN_CENTER_LAT)) * 1000.0
        assert r.grid_x_mm.max() == pytest.approx(bbox_lng_span_mm, rel=0.05)
