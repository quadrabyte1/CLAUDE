"""
test_course_georef.py  —  Phase 2 · pixel ↔ lat/lng conversion tests
Bug→TDD: these were written first (RED), then course_georef.py was implemented.
"""
import sys
import os
import pytest

# Allow importing from app/ directly
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from course_georef import pixel_to_latlng, latlng_to_pixel, validate_georef, green_polygon_px_to_latlng


# ──────────────────────────────────────────────────────────────────────────────
# Fixtures
# ──────────────────────────────────────────────────────────────────────────────

GEOREF = {
    "imageWidth":     1000,
    "imageHeight":    800,
    "swCornerLatLng": [36.990, -122.010],  # SW = bottom-left = south, west
    "neCornerLatLng": [37.010, -121.990],  # NE = top-right  = north, east
}

# Derived constants for assertions
LAT_SW, LNG_SW = 36.990, -122.010
LAT_NE, LNG_NE = 37.010, -121.990
IMG_W, IMG_H = 1000.0, 800.0


# ──────────────────────────────────────────────────────────────────────────────
# Tests 5-8
# ──────────────────────────────────────────────────────────────────────────────

class TestPixelToLatLng:

    def test_sw_corner_pixel(self):
        """T5: SW geographic corner = bottom-left pixel (0, H)."""
        lat, lng = pixel_to_latlng(0, IMG_H, GEOREF)
        assert lat == pytest.approx(LAT_SW, abs=1e-7)
        assert lng == pytest.approx(LNG_SW, abs=1e-7)

    def test_ne_corner_pixel(self):
        """T5: NE geographic corner = top-right pixel (W, 0)."""
        lat, lng = pixel_to_latlng(IMG_W, 0, GEOREF)
        assert lat == pytest.approx(LAT_NE, abs=1e-7)
        assert lng == pytest.approx(LNG_NE, abs=1e-7)

    def test_sw_corner_sw_pixel_alias(self):
        """T5: (0, 0) = top-left = NW geographic corner (lat_ne, lng_sw)."""
        lat, lng = pixel_to_latlng(0, 0, GEOREF)
        assert lat == pytest.approx(LAT_NE, abs=1e-7)   # top = north
        assert lng == pytest.approx(LNG_SW, abs=1e-7)   # left = west

    def test_center_pixel(self):
        """T5: center of image = center of bbox."""
        lat, lng = pixel_to_latlng(IMG_W / 2, IMG_H / 2, GEOREF)
        assert lat == pytest.approx((LAT_SW + LAT_NE) / 2, abs=1e-7)
        assert lng == pytest.approx((LNG_SW + LNG_NE) / 2, abs=1e-7)

    def test_interior_point_linear(self):
        """T5: quarter-way across image."""
        lat, lng = pixel_to_latlng(IMG_W * 0.25, IMG_H * 0.25, GEOREF)
        # frac_x=0.25 → lng = LNG_SW + 0.25*(LNG_NE-LNG_SW)
        expected_lng = LNG_SW + 0.25 * (LNG_NE - LNG_SW)
        # frac_y=0.25 → lat = LAT_NE - 0.25*(LAT_NE-LAT_SW)  (Y flipped)
        expected_lat = LAT_NE - 0.25 * (LAT_NE - LAT_SW)
        assert lat == pytest.approx(expected_lat, abs=1e-7)
        assert lng == pytest.approx(expected_lng, abs=1e-7)


class TestLatLngToPixel:

    def test_sw_corner_latlng(self):
        """T6: SW corner lat/lng → bottom-left pixel."""
        px_x, px_y = latlng_to_pixel(LAT_SW, LNG_SW, GEOREF)
        assert px_x == pytest.approx(0.0, abs=1e-6)
        assert px_y == pytest.approx(IMG_H, abs=1e-6)

    def test_ne_corner_latlng(self):
        """T6: NE corner lat/lng → top-right pixel."""
        px_x, px_y = latlng_to_pixel(LAT_NE, LNG_NE, GEOREF)
        assert px_x == pytest.approx(IMG_W, abs=1e-6)
        assert px_y == pytest.approx(0.0, abs=1e-6)

    def test_center_latlng(self):
        """T6: center lat/lng → center pixel."""
        cx_lat = (LAT_SW + LAT_NE) / 2
        cx_lng = (LNG_SW + LNG_NE) / 2
        px_x, px_y = latlng_to_pixel(cx_lat, cx_lng, GEOREF)
        assert px_x == pytest.approx(IMG_W / 2, abs=1e-6)
        assert px_y == pytest.approx(IMG_H / 2, abs=1e-6)

    def test_out_of_bounds_not_clamped(self):
        """T6: out-of-bounds lat/lng returns coords outside image (not clamped)."""
        # Slightly north of NE corner
        px_x, px_y = latlng_to_pixel(LAT_NE + 0.001, LNG_NE + 0.001, GEOREF)
        assert px_x > IMG_W
        assert px_y < 0  # north of top edge


class TestRoundTrip:

    def test_pixel_to_latlng_to_pixel(self):
        """T7: pixel → latlng → pixel returns original within 1 px."""
        test_points = [
            (0.0,          0.0),
            (IMG_W,        IMG_H),
            (IMG_W * 0.5,  IMG_H * 0.5),
            (IMG_W * 0.1,  IMG_H * 0.9),
            (IMG_W * 0.73, IMG_H * 0.42),
        ]
        for px_x, px_y in test_points:
            lat, lng = pixel_to_latlng(px_x, px_y, GEOREF)
            back_x, back_y = latlng_to_pixel(lat, lng, GEOREF)
            assert back_x == pytest.approx(px_x, abs=1e-4), f"x round-trip failed at {(px_x, px_y)}"
            assert back_y == pytest.approx(px_y, abs=1e-4), f"y round-trip failed at {(px_x, px_y)}"

    def test_latlng_to_pixel_to_latlng(self):
        """T7 cont: latlng → pixel → latlng round-trip."""
        test_latlng = [
            (LAT_SW, LNG_SW),
            (LAT_NE, LNG_NE),
            ((LAT_SW + LAT_NE) / 2, (LNG_SW + LNG_NE) / 2),
            (LAT_SW + 0.01, LNG_SW + 0.01),
        ]
        for lat, lng in test_latlng:
            px_x, px_y = latlng_to_pixel(lat, lng, GEOREF)
            back_lat, back_lng = pixel_to_latlng(px_x, px_y, GEOREF)
            assert back_lat == pytest.approx(lat, abs=1e-9), f"lat round-trip failed at {(lat,lng)}"
            assert back_lng == pytest.approx(lng, abs=1e-9), f"lng round-trip failed at {(lat,lng)}"


class TestValidateGeoref:

    def test_missing_georef_raises(self):
        """T8: None georef → clear error."""
        with pytest.raises(ValueError, match="courseGeoRef is not set"):
            validate_georef(None)

    def test_missing_key_raises(self):
        """T8: missing a required key → error naming the key."""
        bad = {k: v for k, v in GEOREF.items() if k != "swCornerLatLng"}
        with pytest.raises(ValueError, match="swCornerLatLng"):
            validate_georef(bad)

    def test_zero_image_width_raises(self):
        """T8: imageWidth=0 → error."""
        bad = {**GEOREF, "imageWidth": 0}
        with pytest.raises(ValueError, match="imageWidth"):
            validate_georef(bad)

    def test_latitude_inverted_raises(self):
        """T8: SW lat >= NE lat → error explaining fix."""
        bad = {**GEOREF, "swCornerLatLng": [37.010, -122.010]}  # SW lat > NE lat
        with pytest.raises(ValueError, match="SW latitude"):
            validate_georef(bad)

    def test_longitude_inverted_raises(self):
        """T8: SW lng >= NE lng → error."""
        bad = {**GEOREF, "swCornerLatLng": [36.990, -121.990]}  # SW lng > NE lng
        with pytest.raises(ValueError, match="SW longitude"):
            validate_georef(bad)

    def test_valid_georef_no_raise(self):
        """T8 cont: valid georef passes without error."""
        validate_georef(GEOREF)  # should not raise


class TestGreenPolygonConversion:

    def test_green_polygon_px_to_latlng(self):
        """Polygon dicts [{x,y}] converted correctly."""
        pts = [
            {"x": 0.0, "y": IMG_H},           # SW corner
            {"x": IMG_W, "y": 0.0},            # NE corner
            {"x": IMG_W / 2, "y": IMG_H / 2},  # center
        ]
        result = green_polygon_px_to_latlng(pts, GEOREF)
        assert len(result) == 3
        assert result[0] == pytest.approx((LAT_SW, LNG_SW), abs=1e-7)
        assert result[1] == pytest.approx((LAT_NE, LNG_NE), abs=1e-7)
        center_lat = (LAT_SW + LAT_NE) / 2
        center_lng = (LNG_SW + LNG_NE) / 2
        assert result[2] == pytest.approx((center_lat, center_lng), abs=1e-7)

    def test_green_polygon_missing_georef_raises(self):
        """Missing georef raises from green_polygon_px_to_latlng."""
        with pytest.raises(ValueError, match="courseGeoRef"):
            green_polygon_px_to_latlng([{"x": 0, "y": 0}], None)
