"""
test_generate_gps.py  —  Phase 2 · /api/generate_models GPS backend tests
Bug→TDD: these were written first (RED), then the route was updated (GREEN).
"""
import json
import os
import sys
import tempfile
import shutil
import pytest

# Insert app/ onto path so we can import app.py
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

# ──────────────────────────────────────────────────────────────────────────────
# Minimal EGM factories
# ──────────────────────────────────────────────────────────────────────────────

GEOREF = {
    "imageWidth":     1024,
    "imageHeight":    1024,
    "swCornerLatLng": [36.990, -122.010],
    "neCornerLatLng": [37.010, -121.990],
}

def _gps_egm(gps_file_path, enabled=True, bbox=None):
    """Return a minimal EGM dict with gpsBackend configured."""
    return {
        "course": "Test Course",
        "hole": "04",
        "image": "dummy.png",
        "imageCourse": "Test Course",
        "imageSize": {"width": 1024, "height": 1024},
        "polygons": [
            {
                "type": "green",
                "closed": True,
                "points": [
                    {"x": 300, "y": 300},
                    {"x": 500, "y": 300},
                    {"x": 500, "y": 500},
                    {"x": 300, "y": 500},
                ],
            }
        ],
        "gpsBackend": {
            "enabled": enabled,
            "gpsFile": gps_file_path,
            "bbox": bbox or {
                "lat_min": 36.995,
                "lng_min": -122.002,
                "lat_max": 36.998,
                "lng_max": -121.998,
            },
            "approachM": 8.0,
            "vertExag": 3.0,
            "gridSize": [100, 100],
        },
        "courseGeoRef": GEOREF,
        "contourStep": 0.5,
        "grassAmplitude": 0.5,
        "grassSpacing": 0.05,
        "greenStyle": "smooth",
        "elevationRange": 14.5,
        "greenScale": 1.0065,
        "fringeEdgeHeight": 10.0,
        "baseThicknessMm": 1.5,
        "includeBoundaryRegion": False,
        "applyFringeFrameCap": True,
        "flagOffsetXMm": 0.0,
        "flagOffsetYMm": 0.0,
    }

def _gradient_egm():
    """Return a minimal EGM dict WITHOUT gpsBackend (gradient path)."""
    return {
        "course": "Test Course",
        "hole": "04",
        "image": "dummy.png",
        "imageCourse": "Test Course",
        "imageSize": {"width": 1024, "height": 1024},
        "polygons": [
            {
                "type": "green",
                "closed": True,
                "points": [
                    {"x": 300, "y": 300},
                    {"x": 500, "y": 300},
                    {"x": 500, "y": 500},
                    {"x": 300, "y": 500},
                ],
            }
        ],
        "contourStep": 0.5,
        "grassAmplitude": 0.5,
        "grassSpacing": 0.05,
        "greenStyle": "smooth",
        "elevationRange": 14.5,
        "greenScale": 1.0065,
        "fringeEdgeHeight": 10.0,
        "baseThicknessMm": 1.5,
        "includeBoundaryRegion": False,
        "applyFringeFrameCap": True,
        "flagOffsetXMm": 0.0,
        "flagOffsetYMm": 0.0,
    }


# ──────────────────────────────────────────────────────────────────────────────
# Fixtures — isolated temp dirs to avoid touching live DB / real EGM files
# ──────────────────────────────────────────────────────────────────────────────

@pytest.fixture()
def tmp_egm_dir(tmp_path):
    """Create an isolated temp EGM directory tree for this test."""
    course_dir = tmp_path / "GolfCourses" / "Test Course"
    egm_dir = course_dir / "EGMs"
    egm_dir.mkdir(parents=True)
    (course_dir / "3MFs").mkdir()
    (course_dir / "Images").mkdir()
    return tmp_path, egm_dir


def _make_cell(lat, lng, alt, geohash="x"):
    """Return a geoHashCell dict in Stracka's actual format."""
    return {
        "geoHash": geohash,
        "gpsCoordinate": {"latitude": lat, "longitude": lng, "altitude": alt},
    }


@pytest.fixture()
def dummy_gps_file(tmp_path):
    """Write a minimal valid Stracka GPS file (JSON with geoHashCells)."""
    gps_data = {
        "geoHashCells": [
            _make_cell(36.9963, -121.9998, 36.0, "9q9hxv"),
            _make_cell(36.9965, -121.9996, 37.0, "9q9hxw"),
            _make_cell(36.9967, -121.9994, 38.5, "9q9hxy"),
        ]
    }
    gps_path = tmp_path / "test_course.gps"
    gps_path.write_text(json.dumps(gps_data))
    return str(gps_path)


@pytest.fixture()
def app_client(tmp_egm_dir, monkeypatch):
    """Return a Flask test client with a temp EGM base and temp DB."""
    tmp_base, egm_dir = tmp_egm_dir
    tmp_db = str(tmp_base / "workspace.db")

    # Must patch before importing app so the module-level constants get the
    # temp paths. Use monkeypatch.setenv for lightweight isolation.
    import importlib
    import app as _app_module

    monkeypatch.setattr(_app_module, "_EGM_BASE", str(tmp_base / "GolfCourses"))
    monkeypatch.setattr(_app_module, "DB_PATH", tmp_db)

    _app_module.app.config["TESTING"] = True
    with _app_module.app.test_client() as client:
        yield client, egm_dir


# ──────────────────────────────────────────────────────────────────────────────
# Helper: write EGM to temp dir
# ──────────────────────────────────────────────────────────────────────────────

def _write_egm(egm_dir, egm_dict):
    course = egm_dict["course"]
    hole = str(egm_dict["hole"]).zfill(2) if str(egm_dict["hole"]).isdigit() else egm_dict["hole"]
    fname = f"{course} (Hole {hole}).egm"
    fpath = egm_dir / fname
    fpath.write_text(json.dumps(egm_dict, indent=2))
    return str(fpath)


# ──────────────────────────────────────────────────────────────────────────────
# T9: GPS backend enabled → route validates GPS path (file existence check)
# ──────────────────────────────────────────────────────────────────────────────

class TestGenerateGpsEnabled:

    def test_missing_gps_file_returns_400(self, app_client, tmp_path):
        """T11: gpsBackend.enabled=True but .gps file missing → 400 error."""
        client, egm_dir = app_client
        egm = _gps_egm("/nonexistent/path.gps", enabled=True)
        _write_egm(egm_dir, egm)
        resp = client.post(
            "/api/generate_models",
            json={"course": "Test Course", "hole": "4"},
            content_type="application/json",
        )
        data = resp.get_json()
        assert resp.status_code == 400
        assert data["status"] == "error"
        assert "gps" in data["msg"].lower() or "not found" in data["msg"].lower() or ".gps" in data["msg"].lower()

    def test_missing_georef_returns_400(self, app_client, dummy_gps_file):
        """T12: gpsBackend.enabled=True but no courseGeoRef → 400 error."""
        client, egm_dir = app_client
        egm = _gps_egm(dummy_gps_file, enabled=True)
        del egm["courseGeoRef"]
        _write_egm(egm_dir, egm)
        resp = client.post(
            "/api/generate_models",
            json={"course": "Test Course", "hole": "4"},
            content_type="application/json",
        )
        data = resp.get_json()
        assert resp.status_code == 400
        assert data["status"] == "error"
        assert "georef" in data["msg"].lower() or "geo-ref" in data["msg"].lower() or "geo_ref" in data["msg"].lower() or "courseGeoRef" in data["msg"]


# ──────────────────────────────────────────────────────────────────────────────
# T10: GPS disabled → falls back to gradient path (regression guard)
# ──────────────────────────────────────────────────────────────────────────────

class TestGpsDisabledFallback:

    def test_gps_disabled_does_not_check_gps_file(self, app_client):
        """T10: enabled=False → route does NOT check gpsFile; lets pipeline run normally.

        We just verify that the missing-gps-file validation is NOT triggered.
        The pipeline itself may fail for other reasons (missing image), but the
        error should not be a GPS-file-missing 400.
        """
        client, egm_dir = app_client
        egm = _gps_egm("/nonexistent/path.gps", enabled=False)
        _write_egm(egm_dir, egm)
        resp = client.post(
            "/api/generate_models",
            json={"course": "Test Course", "hole": "4"},
            content_type="application/json",
        )
        data = resp.get_json()
        # Should NOT be a GPS-file-missing 400
        if resp.status_code == 400:
            msg = (data or {}).get("msg", "")
            assert "gps" not in msg.lower() or ".gps" not in msg.lower(), \
                f"GPS file check should be skipped when disabled, got: {msg}"

    def test_no_gps_backend_key_does_not_error(self, app_client):
        """T10 cont: EGM with no gpsBackend key at all — graceful (no GPS check)."""
        client, egm_dir = app_client
        egm = _gradient_egm()
        _write_egm(egm_dir, egm)
        resp = client.post(
            "/api/generate_models",
            json={"course": "Test Course", "hole": "4"},
            content_type="application/json",
        )
        data = resp.get_json()
        if resp.status_code == 400:
            msg = (data or {}).get("msg", "")
            assert ".gps" not in msg.lower(), \
                f"No GPS check expected for non-GPS EGM, got: {msg}"


# ──────────────────────────────────────────────────────────────────────────────
# T9 (direct validation): GPS enable + both prereqs present → passes validation
# ──────────────────────────────────────────────────────────────────────────────

class TestGpsValidationLogic:

    def test_gps_prereqs_validated_before_pipeline(self, app_client, dummy_gps_file):
        """T9: When gps file exists and georef present, validation passes.
        The pipeline will fail downstream (missing image etc.) — that's OK;
        we only verify the GPS pre-check does NOT return 400.
        """
        client, egm_dir = app_client
        egm = _gps_egm(dummy_gps_file, enabled=True)
        _write_egm(egm_dir, egm)
        resp = client.post(
            "/api/generate_models",
            json={"course": "Test Course", "hole": "4"},
            content_type="application/json",
        )
        # A 400 here would mean the GPS pre-check is still failing — should not happen
        # The pipeline may 500 due to missing image; that's acceptable.
        assert resp.status_code != 400, (
            f"GPS pre-validation failed unexpectedly: {resp.get_json()}"
        )
