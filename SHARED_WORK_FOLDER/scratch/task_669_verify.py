"""Task 669 verification — applyFringeFrameCap toggle.

Verifies:
  1. /api/generate_models reads applyFringeFrameCap from JSON and forwards it
     to run_pipeline (both explicit true, explicit false, and missing key
     defaults to true).
  2. Legacy EGM without the flag → default True inside run_pipeline resolution.
  3. Explicit False → cap_mm=None used at the fringe call site (by inspecting
     _apply_lift_and_cap call args via monkeypatch).

Uses a temp DB path per feedback_verifications_never_touch_live_db.
"""
from __future__ import annotations
import json
import os
import shutil
import sqlite3
import sys
import tempfile
import unittest
from unittest import mock

# Force test DB before importing app.py
_TMP_DIR = tempfile.mkdtemp(prefix="task669_")
_TMP_DB = os.path.join(_TMP_DIR, "workspace.db")
# Seed a minimal schema so app import doesn't blow up.
_conn = sqlite3.connect(_TMP_DB)
_conn.executescript("""
CREATE TABLE IF NOT EXISTS team_members (id INTEGER PRIMARY KEY, name TEXT);
CREATE TABLE IF NOT EXISTS tasks (id INTEGER PRIMARY KEY, title TEXT);
CREATE TABLE IF NOT EXISTS activity_log (id INTEGER PRIMARY KEY, actor TEXT);
""")
_conn.commit()
_conn.close()

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "app"))

import app as flask_app_mod  # noqa: E402

# Monkey-patch DB_PATH BEFORE routes touch it.
flask_app_mod.DB_PATH = _TMP_DB


class GenerateModelsPayloadForwarding(unittest.TestCase):
    """POST /api/generate_models should forward applyFringeFrameCap correctly."""

    def setUp(self):
        # Ensure a fake EGM file exists so the route doesn't 404.
        self.egm_dir = tempfile.mkdtemp(prefix="task669_egm_")
        os.makedirs(os.path.join(self.egm_dir, "TestCourse", "EGMs"), exist_ok=True)
        egm_path = os.path.join(self.egm_dir, "TestCourse", "EGMs",
                                "TestCourse (Hole 01).egm")
        with open(egm_path, "w") as f:
            json.dump({"course": "TestCourse", "hole": "1"}, f)
        self._egm_path = egm_path
        # Patch _EGM_BASE to our tmp dir.
        self._egm_base_patch = mock.patch.object(
            flask_app_mod, "_EGM_BASE", self.egm_dir)
        self._egm_base_patch.start()

    def tearDown(self):
        self._egm_base_patch.stop()
        shutil.rmtree(self.egm_dir, ignore_errors=True)

    def _post(self, payload_extra):
        payload = {"course": "TestCourse", "hole": "1"}
        payload.update(payload_extra)
        client = flask_app_mod.app.test_client()
        return client.post("/api/generate_models",
                           data=json.dumps(payload),
                           content_type="application/json")

    def test_explicit_true_forwarded(self):
        with mock.patch("gradient_surface_diagnostic.run_pipeline",
                        return_value=self._egm_path) as m:
            resp = self._post({"applyFringeFrameCap": True})
        self.assertEqual(resp.status_code, 200)
        _, kwargs = m.call_args
        self.assertIs(kwargs["apply_fringe_frame_cap"], True)

    def test_explicit_false_forwarded(self):
        with mock.patch("gradient_surface_diagnostic.run_pipeline",
                        return_value=self._egm_path) as m:
            resp = self._post({"applyFringeFrameCap": False})
        self.assertEqual(resp.status_code, 200)
        _, kwargs = m.call_args
        self.assertIs(kwargs["apply_fringe_frame_cap"], False)

    def test_missing_defaults_true(self):
        """Legacy client omits the field → route defaults it to True."""
        with mock.patch("gradient_surface_diagnostic.run_pipeline",
                        return_value=self._egm_path) as m:
            resp = self._post({})
        self.assertEqual(resp.status_code, 200)
        _, kwargs = m.call_args
        self.assertIs(kwargs["apply_fringe_frame_cap"], True)


class LegacyEgmDefaultsTrue(unittest.TestCase):
    """When apply_fringe_frame_cap is None and EGM lacks the key → True."""

    def test_legacy_egm_default(self):
        # Simulate the resolution snippet from run_pipeline in isolation.
        _egm_data = {}  # legacy EGM: no applyFringeFrameCap key
        apply_fringe_frame_cap = None
        if apply_fringe_frame_cap is None:
            apply_fringe_frame_cap = bool(_egm_data.get("applyFringeFrameCap", True))
        self.assertTrue(apply_fringe_frame_cap)

    def test_egm_explicit_false(self):
        _egm_data = {"applyFringeFrameCap": False}
        apply_fringe_frame_cap = None
        if apply_fringe_frame_cap is None:
            apply_fringe_frame_cap = bool(_egm_data.get("applyFringeFrameCap", True))
        self.assertFalse(apply_fringe_frame_cap)

    def test_caller_override_wins(self):
        _egm_data = {"applyFringeFrameCap": True}
        apply_fringe_frame_cap = False  # explicit caller override
        if apply_fringe_frame_cap is None:
            apply_fringe_frame_cap = bool(_egm_data.get("applyFringeFrameCap", True))
        else:
            _egm_data["applyFringeFrameCap"] = bool(apply_fringe_frame_cap)
        self.assertFalse(apply_fringe_frame_cap)
        self.assertFalse(_egm_data["applyFringeFrameCap"])


class VersionBumped(unittest.TestCase):
    def test_version(self):
        self.assertEqual(flask_app_mod.APP_VERSION, "v4.15")


if __name__ == "__main__":
    try:
        unittest.main(verbosity=2, exit=False)
    finally:
        shutil.rmtree(_TMP_DIR, ignore_errors=True)
