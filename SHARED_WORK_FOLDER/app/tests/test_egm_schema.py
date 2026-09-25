"""
test_egm_schema.py  —  Phase 2 · EGM gpsBackend schema tests
Bug→TDD: these were written first; all should be RED before implementation.
"""
import json
import pytest
from pathlib import Path


# ──────────────────────────────────────────────────────────────────────────────
# Helpers — minimal EGM parser (uses only stdlib, mirrors what app.py does)
# ──────────────────────────────────────────────────────────────────────────────

def parse_egm(raw: dict) -> dict:
    """Return a normalised view of an EGM dict with gpsBackend / courseGeoRef
    fields extracted.  Raises ValueError on invalid gpsBackend content.

    Fields returned
    ---------------
    gps_enabled : bool
    gps_file    : str | None
    bbox        : dict | None   {"lat_min","lng_min","lat_max","lng_max"}
    approach_m  : float
    vert_exag   : float
    grid_size   : list[int, int]
    hole_number : int | None
    geo_ref     : dict | None   the courseGeoRef block
    """
    gps = raw.get("gpsBackend")
    if gps is None:
        return {
            "gps_enabled": False,
            "gps_file": None,
            "bbox": None,
            "approach_m": 8.0,
            "vert_exag": 3.0,
            "grid_size": [200, 200],
            "hole_number": None,
            "geo_ref": raw.get("courseGeoRef"),
        }

    enabled = bool(gps.get("enabled", False))

    if enabled:
        missing = [
            k for k in ("gpsFile", "bbox")
            if not gps.get(k)
        ]
        if missing:
            raise ValueError(
                f"gpsBackend.enabled=true but required fields missing: {missing}"
            )

    bbox = gps.get("bbox")
    if bbox is not None:
        # Normalise — ensure all four keys present
        for k in ("lat_min", "lng_min", "lat_max", "lng_max"):
            if k not in bbox:
                raise ValueError(f"gpsBackend.bbox missing key: {k}")

    return {
        "gps_enabled": enabled,
        "gps_file": gps.get("gpsFile"),
        "bbox": bbox,
        "approach_m": float(gps.get("approachM", 8.0)),
        "vert_exag": float(gps.get("vertExag", 3.0)),
        "grid_size": list(gps.get("gridSize", [200, 200])),
        "hole_number": gps.get("holeNumber"),
        "geo_ref": raw.get("courseGeoRef"),
    }


def serialize_egm(raw: dict) -> dict:
    """Round-trip: parse then re-construct the EGM dict.  For fields we own
    (gpsBackend, courseGeoRef) we reconstruct; everything else passes through."""
    parsed = parse_egm(raw)
    out = {k: v for k, v in raw.items() if k not in ("gpsBackend", "courseGeoRef")}

    if raw.get("gpsBackend") is not None:
        gps_block = {
            "enabled": parsed["gps_enabled"],
            "gpsFile": parsed["gps_file"],
            "bbox": parsed["bbox"],
            "approachM": parsed["approach_m"],
            "vertExag": parsed["vert_exag"],
            "gridSize": parsed["grid_size"],
        }
        if parsed["hole_number"] is not None:
            gps_block["holeNumber"] = parsed["hole_number"]
        out["gpsBackend"] = gps_block

    if raw.get("courseGeoRef") is not None:
        out["courseGeoRef"] = raw["courseGeoRef"]

    return out


# ──────────────────────────────────────────────────────────────────────────────
# Fixtures
# ──────────────────────────────────────────────────────────────────────────────

VALID_GEOREF = {
    "imageWidth": 1024,
    "imageHeight": 1024,
    "swCornerLatLng": [36.99, -122.00],
    "neCornerLatLng": [37.00, -121.99],
}

VALID_GPS_EGM = {
    "course": "Test Course",
    "hole": "4",
    "polygons": [{"type": "green", "points": []}],
    "gpsBackend": {
        "enabled": True,
        "gpsFile": "/path/to/course.gps",
        "bbox": {
            "lat_min": 36.995,
            "lng_min": -121.997,
            "lat_max": 36.998,
            "lng_max": -121.994,
        },
        "holeNumber": 4,
        "approachM": 8.0,
        "vertExag": 3.0,
        "gridSize": [200, 200],
    },
    "courseGeoRef": VALID_GEOREF,
}

LEGACY_EGM = {
    "course": "Old Course",
    "hole": "1",
    "polygons": [{"type": "green", "points": []}],
    "greenStyle": "terraced",
    "contourStep": 0.5,
}


# ──────────────────────────────────────────────────────────────────────────────
# Tests 1-4: Schema parsing
# ──────────────────────────────────────────────────────────────────────────────

class TestGpsBackendParsing:

    def test_parse_enabled_fields_correct_types(self):
        """T1: gpsBackend fields parsed correctly with right types."""
        parsed = parse_egm(VALID_GPS_EGM)
        assert parsed["gps_enabled"] is True
        assert isinstance(parsed["gps_file"], str)
        assert parsed["gps_file"] == "/path/to/course.gps"
        assert isinstance(parsed["bbox"], dict)
        assert parsed["bbox"]["lat_min"] == pytest.approx(36.995)
        assert parsed["bbox"]["lng_max"] == pytest.approx(-121.994)
        assert isinstance(parsed["approach_m"], float)
        assert parsed["approach_m"] == pytest.approx(8.0)
        assert isinstance(parsed["vert_exag"], float)
        assert parsed["vert_exag"] == pytest.approx(3.0)
        assert isinstance(parsed["grid_size"], list)
        assert parsed["grid_size"] == [200, 200]
        assert parsed["hole_number"] == 4

    def test_parse_georef_block(self):
        """T1 cont: courseGeoRef also parsed correctly."""
        parsed = parse_egm(VALID_GPS_EGM)
        assert parsed["geo_ref"] is not None
        assert parsed["geo_ref"]["imageWidth"] == 1024
        assert parsed["geo_ref"]["swCornerLatLng"] == [36.99, -122.00]

    def test_backward_compat_legacy_egm(self):
        """T2: EGM without gpsBackend defaults to disabled / None."""
        parsed = parse_egm(LEGACY_EGM)
        assert parsed["gps_enabled"] is False
        assert parsed["gps_file"] is None
        assert parsed["bbox"] is None
        assert parsed["geo_ref"] is None
        # Defaults are sensible
        assert parsed["approach_m"] == pytest.approx(8.0)
        assert parsed["vert_exag"] == pytest.approx(3.0)
        assert parsed["grid_size"] == [200, 200]

    def test_backward_compat_polygons_preserved(self):
        """T2 cont: existing polygons key survives parsing round-trip."""
        raw = LEGACY_EGM.copy()
        raw["polygons"] = [{"type": "green"}, {"type": "trap"}]
        out = serialize_egm(raw)
        assert out["polygons"] == raw["polygons"]

    def test_round_trip_serialization_identical(self):
        """T3: parse then re-serialize yields identical JSON."""
        original_json = json.dumps(VALID_GPS_EGM, sort_keys=True)
        round_tripped = serialize_egm(VALID_GPS_EGM)
        round_trip_json = json.dumps(round_tripped, sort_keys=True)
        assert original_json == round_trip_json

    def test_round_trip_legacy_egm_identical(self):
        """T3 cont: legacy EGM round-trips identically (no gpsBackend added)."""
        original_json = json.dumps(LEGACY_EGM, sort_keys=True)
        round_tripped = serialize_egm(LEGACY_EGM)
        round_trip_json = json.dumps(round_tripped, sort_keys=True)
        assert original_json == round_trip_json
        assert "gpsBackend" not in round_tripped

    def test_invalid_enabled_missing_gps_file(self):
        """T4: enabled=True but gpsFile missing → clear ValueError."""
        bad = {
            "gpsBackend": {
                "enabled": True,
                # gpsFile missing
                "bbox": {
                    "lat_min": 36.995, "lng_min": -121.997,
                    "lat_max": 36.998, "lng_max": -121.994,
                },
            }
        }
        with pytest.raises(ValueError, match="gpsFile"):
            parse_egm(bad)

    def test_invalid_enabled_missing_bbox(self):
        """T4: enabled=True but bbox missing → clear ValueError."""
        bad = {
            "gpsBackend": {
                "enabled": True,
                "gpsFile": "/some/file.gps",
                # bbox missing
            }
        }
        with pytest.raises(ValueError, match="bbox"):
            parse_egm(bad)

    def test_invalid_bbox_missing_key(self):
        """T4: bbox present but missing lat_max → clear ValueError."""
        bad = {
            "gpsBackend": {
                "enabled": True,
                "gpsFile": "/some/file.gps",
                "bbox": {"lat_min": 36.995, "lng_min": -121.997},
                # lat_max, lng_max missing
            }
        }
        with pytest.raises(ValueError, match="lat_max|lng_max"):
            parse_egm(bad)

    def test_disabled_gps_backend_no_validation_error(self):
        """T4 cont: enabled=False skips required-field validation."""
        egm = {
            "gpsBackend": {
                "enabled": False,
                # gpsFile and bbox intentionally absent
            }
        }
        parsed = parse_egm(egm)
        assert parsed["gps_enabled"] is False
        assert parsed["gps_file"] is None

    def test_defaults_applied_when_optional_fields_absent(self):
        """T1 cont: approachM / vertExag / gridSize default correctly."""
        egm = {
            "gpsBackend": {
                "enabled": True,
                "gpsFile": "/f.gps",
                "bbox": {
                    "lat_min": 36.995, "lng_min": -121.997,
                    "lat_max": 36.998, "lng_max": -121.994,
                },
            }
        }
        parsed = parse_egm(egm)
        assert parsed["approach_m"] == pytest.approx(8.0)
        assert parsed["vert_exag"] == pytest.approx(3.0)
        assert parsed["grid_size"] == [200, 200]
        assert parsed["hole_number"] is None
