"""
test_gps_preview.py  —  Phase 2 · /api/gps_heightmap_preview endpoint tests
Bug→TDD: RED first, then implement endpoint, then GREEN.
"""
import json
import os
import sys
import base64
import time
import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))


# ──────────────────────────────────────────────────────────────────────────────
# Fixtures
# ──────────────────────────────────────────────────────────────────────────────

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
            _make_cell(36.9960, -122.0000, 36.0, "9q9a"),
            _make_cell(36.9962, -121.9998, 37.0, "9q9b"),
            _make_cell(36.9964, -121.9996, 38.0, "9q9c"),
            _make_cell(36.9966, -121.9994, 36.5, "9q9d"),
            _make_cell(36.9968, -121.9992, 37.5, "9q9e"),
            _make_cell(36.9958, -121.9998, 36.8, "9q9f"),
            _make_cell(36.9970, -122.0002, 37.8, "9q9g"),
        ]
    }
    p = tmp_path / "test.gps"
    p.write_text(json.dumps(gps_data))
    return str(p)


@pytest.fixture()
def app_client(tmp_path, monkeypatch):
    """Return a Flask test client with a temp DB (no live DB touch)."""
    tmp_db = str(tmp_path / "workspace.db")
    import app as _app_module
    monkeypatch.setattr(_app_module, "DB_PATH", tmp_db)
    _app_module.app.config["TESTING"] = True
    with _app_module.app.test_client() as client:
        yield client


VALID_BBOX = json.dumps({
    "lat_min": 36.9955,
    "lng_min": -122.0005,
    "lat_max": 36.9975,
    "lng_max": -121.9985,
})


# ──────────────────────────────────────────────────────────────────────────────
# T13: Preview endpoint returns PNG
# ──────────────────────────────────────────────────────────────────────────────

class TestGpsPreviewEndpoint:

    def test_returns_200_with_valid_params(self, app_client, dummy_gps_file):
        """T13: Valid params → 200 response."""
        resp = app_client.get(
            "/api/gps_heightmap_preview",
            query_string={
                "gps_file": dummy_gps_file,
                "bbox": VALID_BBOX,
                "approach_m": "8.0",
                "grid_size": "100",
            },
        )
        assert resp.status_code == 200

    def test_returns_png_content_type(self, app_client, dummy_gps_file):
        """T13: Response Content-Type is image/png."""
        resp = app_client.get(
            "/api/gps_heightmap_preview",
            query_string={
                "gps_file": dummy_gps_file,
                "bbox": VALID_BBOX,
                "approach_m": "8.0",
                "grid_size": "100",
            },
        )
        assert resp.status_code == 200
        assert "image/png" in resp.content_type

    def test_response_is_valid_png_bytes(self, app_client, dummy_gps_file):
        """T13: Response body starts with PNG magic bytes."""
        resp = app_client.get(
            "/api/gps_heightmap_preview",
            query_string={
                "gps_file": dummy_gps_file,
                "bbox": VALID_BBOX,
                "approach_m": "8.0",
                "grid_size": "100",
            },
        )
        assert resp.status_code == 200
        # PNG magic: \x89PNG\r\n\x1a\n
        png_magic = b"\x89PNG\r\n\x1a\n"
        assert resp.data[:8] == png_magic

    def test_missing_gps_file_param_returns_400(self, app_client):
        """T13: gps_file param missing → 400."""
        resp = app_client.get(
            "/api/gps_heightmap_preview",
            query_string={"bbox": VALID_BBOX},
        )
        assert resp.status_code == 400

    def test_missing_bbox_param_returns_400(self, app_client, dummy_gps_file):
        """T13: bbox param missing → 400."""
        resp = app_client.get(
            "/api/gps_heightmap_preview",
            query_string={"gps_file": dummy_gps_file},
        )
        assert resp.status_code == 400

    def test_nonexistent_gps_file_returns_404(self, app_client):
        """T13: gps_file that doesn't exist → 404."""
        resp = app_client.get(
            "/api/gps_heightmap_preview",
            query_string={
                "gps_file": "/no/such/file.gps",
                "bbox": VALID_BBOX,
            },
        )
        assert resp.status_code == 404


# ──────────────────────────────────────────────────────────────────────────────
# T15: Cache — identical requests within 30 s return same bytes
# ──────────────────────────────────────────────────────────────────────────────

class TestPreviewCache:

    def test_identical_requests_return_identical_bytes(self, app_client, dummy_gps_file):
        """T15: Two identical requests within the cache window return the same PNG."""
        params = {
            "gps_file": dummy_gps_file,
            "bbox": VALID_BBOX,
            "approach_m": "8.0",
            "grid_size": "100",
        }
        resp1 = app_client.get("/api/gps_heightmap_preview", query_string=params)
        resp2 = app_client.get("/api/gps_heightmap_preview", query_string=params)
        assert resp1.status_code == 200
        assert resp2.status_code == 200
        assert resp1.data == resp2.data

    def test_different_params_return_different_bytes(self, app_client, dummy_gps_file, tmp_path):
        """T15 cont: Different params produce distinct results (cache key includes params)."""
        # Create a second GPS file with different altitudes
        gps2 = {
            "geoHashCells": [
                _make_cell(36.9960, -122.0000, 100.0, "x1"),
                _make_cell(36.9965, -121.9995, 150.0, "x2"),
                _make_cell(36.9970, -121.9990, 200.0, "x3"),
            ]
        }
        gps2_path = str(tmp_path / "different.gps")
        import json
        open(gps2_path, "w").write(json.dumps(gps2))

        params1 = {"gps_file": dummy_gps_file, "bbox": VALID_BBOX, "grid_size": "100"}
        params2 = {"gps_file": gps2_path, "bbox": VALID_BBOX, "grid_size": "100"}

        resp1 = app_client.get("/api/gps_heightmap_preview", query_string=params1)
        resp2 = app_client.get("/api/gps_heightmap_preview", query_string=params2)

        assert resp1.status_code == 200
        assert resp2.status_code == 200
        # Different GPS data → different PNG bytes
        assert resp1.data != resp2.data
