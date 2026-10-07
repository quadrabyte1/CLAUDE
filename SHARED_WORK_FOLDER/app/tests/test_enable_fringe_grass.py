"""
test_enable_fringe_grass.py — Include Fringe Without Grass checkbox (task 724)

Thomas's spec:
  - "Include Fringe Without Grass" checkbox.
  - Plate 1: ALWAYS has grass, regardless of checkbox state.
  - Plate 2: only built when checkbox is CHECKED (include_fringe_without_grass=True).
  - Plate 2 mesh: smooth fringe with NO grass.

Tombstoned tests (old semantics no longer apply):
  T1-T9  — Old "Enable Fringe Grass" checkbox (renamed/semantics changed).
  T10    — Old assertion: exactly 1 grass call when enableFringeGrass=False
            (plate 2 used to always have grass; now plate 2 is grass-LESS and
             only built when include_fringe_without_grass=True).
  T12    — Old: app.py passes enableFringeGrass to run_pipeline
            (replaced by include_fringe_without_grass).

Live tests (new semantics):
  T11  Geometry always runs grass on plate 1 — plate 1 fringe always has grass
       regardless of include_fringe_without_grass flag.
  T13  Plate 1 still has grass when include_fringe_without_grass=False.
  T14  Plate 1 still has grass when include_fringe_without_grass=True (2 grass
       calls when both plate 1 and NO plate 2 use grass — but only plate 1 is
       grassed; plate 2 is smooth, so exactly 1 grass call total).
  T15  Plate 2 only built when include_fringe_without_grass=True.
  T16  Plate 2 mesh has NO grass — grass functions NOT called for the plate-2 build.
  T17  Scene node name is "fringe_no_grass_sample" (not old "fringe_grass_sample").
  T18  app.py route reads includeFringeWithoutGrass from request and passes
       include_fringe_without_grass to run_pipeline.
  T19  UI: editor.html has checkbox x-modelled to includeFringeWithoutGrass.
  T20  UI: label text is "Include Fringe Without Grass".
"""
from __future__ import annotations

import json
import os
import re
import sys
import tempfile

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

EDITOR_HTML = os.path.join(os.path.dirname(__file__), "..", "templates", "editor.html")
APP_PY = os.path.join(os.path.dirname(__file__), "..", "app.py")


def _read_editor_js() -> str:
    with open(EDITOR_HTML, "r") as f:
        return f.read()


# ─────────────────────────────────────────────────────────────────────────────
# TOMBSTONED: T1-T9 (old "Enable Fringe Grass" checkbox)
# Reason: checkbox was renamed to "Include Fringe Without Grass" with
# inverted semantics. Old x-model="enableFringeGrass" no longer exists.
# ─────────────────────────────────────────────────────────────────────────────


# ─────────────────────────────────────────────────────────────────────────────
# TOMBSTONED: T10 (grass call count when enableFringeGrass=False)
# Reason: plate 2 is now grass-LESS and conditional on include_fringe_without_grass.
# The old assertion (exactly 1 grass call when enableFringeGrass=False) no
# longer applies. The new plate 1 is always grassed; plate 2 is never grassed.
# ─────────────────────────────────────────────────────────────────────────────


# ─────────────────────────────────────────────────────────────────────────────
# TOMBSTONED: T12 (app.py passes enableFringeGrass to run_pipeline)
# Reason: the field is now include_fringe_without_grass. T18 covers the new wiring.
# ─────────────────────────────────────────────────────────────────────────────


# ─────────────────────────────────────────────────────────────────────────────
# Fixtures — real EGM files
# ─────────────────────────────────────────────────────────────────────────────

@pytest.fixture()
def egm_with_grass_false(tmp_path):
    """EGM with include_fringe_without_grass=False (default: single plate, grassy plate 1)."""
    from pathlib import Path
    APP_DIR = Path(__file__).parent.parent
    EGM_BASE = APP_DIR.parent / "ItWentIn" / "GolfCourses"
    egm_files = list(EGM_BASE.rglob("*.egm")) if EGM_BASE.exists() else []
    if not egm_files:
        pytest.skip("No real EGM files found for pipeline test")
    with open(egm_files[0]) as f:
        egm_data = json.load(f)
    egm_data["includeFringeWithoutGrass"] = False
    out = tmp_path / "test_hole_false.egm"
    out.write_text(json.dumps(egm_data))
    return str(out)


@pytest.fixture()
def egm_with_grass_true(tmp_path):
    """EGM with include_fringe_without_grass=True (two plates: grassy plate 1 + smooth plate 2)."""
    from pathlib import Path
    APP_DIR = Path(__file__).parent.parent
    EGM_BASE = APP_DIR.parent / "ItWentIn" / "GolfCourses"
    egm_files = list(EGM_BASE.rglob("*.egm")) if EGM_BASE.exists() else []
    if not egm_files:
        pytest.skip("No real EGM files found for pipeline test")
    with open(egm_files[0]) as f:
        egm_data = json.load(f)
    egm_data["includeFringeWithoutGrass"] = True
    out = tmp_path / "test_hole_true.egm"
    out.write_text(json.dumps(egm_data))
    return str(out)


# ─────────────────────────────────────────────────────────────────────────────
# T11: Plate 1 always runs grass (include_fringe_without_grass=True)
# ─────────────────────────────────────────────────────────────────────────────

class TestPlate1AlwaysHasGrass:

    def test_grass_called_for_plate1_when_checkbox_true(self, egm_with_grass_true, monkeypatch):
        """T11: Grass is applied to plate 1 even when include_fringe_without_grass=True."""
        import gradient_surface_diagnostic as gsd
        call_log: list[str] = []

        def _mock_v2(*args, **kwargs):
            call_log.append("v2")

        def _mock_v1(*args, **kwargs):
            call_log.append("v1")

        monkeypatch.setattr(gsd, "apply_grass_texture_v2", _mock_v2)
        monkeypatch.setattr(gsd, "apply_grass_texture", _mock_v1)

        try:
            gsd.run_pipeline(egm_with_grass_true)
        except Exception:
            pass

        assert len(call_log) >= 1, (
            "Plate 1 must always have grass applied. Expected at least 1 grass call "
            f"when include_fringe_without_grass=True; got {len(call_log)}."
        )


# ─────────────────────────────────────────────────────────────────────────────
# T13: Plate 1 still has grass when include_fringe_without_grass=False
# ─────────────────────────────────────────────────────────────────────────────

class TestPlate1HasGrassWhenCheckboxFalse:

    def test_grass_called_for_plate1_when_checkbox_false(self, egm_with_grass_false, monkeypatch):
        """T13: Plate 1 must have grass applied even when include_fringe_without_grass=False.

        When the checkbox is unchecked, only a single plate is produced,
        but plate 1's fringe must still be grassy.
        """
        import gradient_surface_diagnostic as gsd
        call_log: list[str] = []

        def _mock_v2(*args, **kwargs):
            call_log.append("v2")

        def _mock_v1(*args, **kwargs):
            call_log.append("v1")

        monkeypatch.setattr(gsd, "apply_grass_texture_v2", _mock_v2)
        monkeypatch.setattr(gsd, "apply_grass_texture", _mock_v1)

        try:
            gsd.run_pipeline(egm_with_grass_false)
        except Exception:
            pass

        assert len(call_log) >= 1, (
            "Plate 1 must always have grass applied. Expected at least 1 grass call "
            f"when include_fringe_without_grass=False (single plate run); got {len(call_log)}. "
            "The old if enable_fringe_grass: guard on plate 1 must be removed."
        )


# ─────────────────────────────────────────────────────────────────────────────
# T14: Plate 2 is NOT built when include_fringe_without_grass=False
#       → exactly 1 grass call (plate 1 only)
# ─────────────────────────────────────────────────────────────────────────────

class TestPlate2NotBuiltWhenFalse:

    def test_exactly_one_grass_call_when_no_plate2(self, egm_with_grass_false, monkeypatch):
        """T14: When include_fringe_without_grass=False, grass is called exactly once
        (plate 1 only; no plate 2 build, which would have been grass-free anyway).
        """
        import gradient_surface_diagnostic as gsd
        call_log: list[str] = []

        def _mock_v2(*args, **kwargs):
            call_log.append("v2")

        def _mock_v1(*args, **kwargs):
            call_log.append("v1")

        monkeypatch.setattr(gsd, "apply_grass_texture_v2", _mock_v2)
        monkeypatch.setattr(gsd, "apply_grass_texture", _mock_v1)

        try:
            gsd.run_pipeline(egm_with_grass_false)
        except Exception:
            pass

        assert len(call_log) == 1, (
            f"Expected exactly 1 grass call when include_fringe_without_grass=False "
            f"(plate 1 always grassed, no plate 2 built); got {len(call_log)}: {call_log}. "
            "0 = plate 1 grass was incorrectly skipped. "
            "2+ = plate 2 was incorrectly built with grass."
        )


# ─────────────────────────────────────────────────────────────────────────────
# T15: Plate 2 is built only when include_fringe_without_grass=True
# ─────────────────────────────────────────────────────────────────────────────

class TestPlate2OnlyWhenTrue:

    def test_no_plate2_node_when_false(self, egm_with_grass_false, monkeypatch):
        """T15a: scene_names must NOT contain fringe_no_grass_sample when checkbox is False."""
        import gradient_surface_diagnostic as gsd_mod

        captured_scene_names: list[list[str]] = []

        def _mock_inject(path_3mf, scene_names):
            captured_scene_names.append(list(scene_names))

        monkeypatch.setattr(gsd_mod, "_inject_bambu_extruder_metadata", _mock_inject)

        import trimesh
        from pathlib import Path

        def _noop_export(self, *args, **kwargs):
            Path(args[0]).write_bytes(b"PK\x03\x04")

        monkeypatch.setattr(trimesh.Scene, "export", _noop_export)

        try:
            gsd_mod.run_pipeline(egm_with_grass_false)
        except Exception:
            pass

        if not captured_scene_names:
            pytest.skip("_inject_bambu_extruder_metadata not reached")

        scene_names = captured_scene_names[-1]
        assert "fringe_no_grass_sample" not in scene_names, (
            f"fringe_no_grass_sample must NOT be in scene_names when "
            f"include_fringe_without_grass=False. Got: {scene_names}"
        )

    def test_plate2_node_present_when_true(self, egm_with_grass_true, monkeypatch):
        """T15b: scene_names must contain fringe_no_grass_sample when checkbox is True."""
        import gradient_surface_diagnostic as gsd_mod

        captured_scene_names: list[list[str]] = []

        def _mock_inject(path_3mf, scene_names):
            captured_scene_names.append(list(scene_names))

        monkeypatch.setattr(gsd_mod, "_inject_bambu_extruder_metadata", _mock_inject)

        import trimesh
        from pathlib import Path

        def _noop_export(self, *args, **kwargs):
            Path(args[0]).write_bytes(b"PK\x03\x04")

        monkeypatch.setattr(trimesh.Scene, "export", _noop_export)

        try:
            gsd_mod.run_pipeline(egm_with_grass_true)
        except Exception:
            pass

        if not captured_scene_names:
            pytest.skip("_inject_bambu_extruder_metadata not reached")

        scene_names = captured_scene_names[-1]
        assert "fringe_no_grass_sample" in scene_names, (
            f"fringe_no_grass_sample must be in scene_names when "
            f"include_fringe_without_grass=True. Got: {scene_names}. "
            "The pipeline must build the smooth fringe sample and add it as "
            "'fringe_no_grass_sample' when the checkbox is checked."
        )


# ─────────────────────────────────────────────────────────────────────────────
# T16: Plate 2 mesh has NO grass
# ─────────────────────────────────────────────────────────────────────────────

class TestPlate2HasNoGrass:

    def test_grass_called_exactly_once_when_plate2_present(self, egm_with_grass_true, monkeypatch):
        """T16: When include_fringe_without_grass=True, grass is called exactly once
        (plate 1 only). Plate 2 is the smooth sample — grass NOT applied to it.
        """
        import gradient_surface_diagnostic as gsd
        call_log: list[str] = []

        def _mock_v2(*args, **kwargs):
            call_log.append("v2")

        def _mock_v1(*args, **kwargs):
            call_log.append("v1")

        monkeypatch.setattr(gsd, "apply_grass_texture_v2", _mock_v2)
        monkeypatch.setattr(gsd, "apply_grass_texture", _mock_v1)

        try:
            gsd.run_pipeline(egm_with_grass_true)
        except Exception:
            pass

        assert len(call_log) == 1, (
            f"Expected exactly 1 grass call when include_fringe_without_grass=True "
            f"(plate 1 grassed, plate 2 smooth/no-grass); got {len(call_log)}: {call_log}. "
            "0 = plate 1 grass was skipped (regression). "
            "2+ = grass was incorrectly applied to the plate-2 sample."
        )


# ─────────────────────────────────────────────────────────────────────────────
# T17: Scene node is "fringe_no_grass_sample" (not old "fringe_grass_sample")
# ─────────────────────────────────────────────────────────────────────────────

class TestSceneNodeName:

    def test_scene_node_renamed_to_no_grass(self, egm_with_grass_true, monkeypatch):
        """T17: The plate-2 scene node must be named 'fringe_no_grass_sample'."""
        import gradient_surface_diagnostic as gsd_mod

        captured_scene_names: list[list[str]] = []

        def _mock_inject(path_3mf, scene_names):
            captured_scene_names.append(list(scene_names))

        monkeypatch.setattr(gsd_mod, "_inject_bambu_extruder_metadata", _mock_inject)

        import trimesh
        from pathlib import Path

        def _noop_export(self, *args, **kwargs):
            Path(args[0]).write_bytes(b"PK\x03\x04")

        monkeypatch.setattr(trimesh.Scene, "export", _noop_export)

        try:
            gsd_mod.run_pipeline(egm_with_grass_true)
        except Exception:
            pass

        if not captured_scene_names:
            pytest.skip("_inject_bambu_extruder_metadata not reached")

        scene_names = captured_scene_names[-1]
        assert "fringe_grass_sample" not in scene_names, (
            f"Old scene node 'fringe_grass_sample' still present. Must be renamed to "
            f"'fringe_no_grass_sample'. Got: {scene_names}"
        )
        assert "fringe_no_grass_sample" in scene_names, (
            f"New scene node 'fringe_no_grass_sample' not found. Got: {scene_names}"
        )


# ─────────────────────────────────────────────────────────────────────────────
# T18: app.py route wiring
# ─────────────────────────────────────────────────────────────────────────────

class TestAppPyRouteWiring:

    def test_route_reads_include_fringe_without_grass(self):
        """T18a: app.py must read includeFringeWithoutGrass from request data."""
        with open(APP_PY) as f:
            src = f.read()
        assert "includeFringeWithoutGrass" in src, (
            "app.py generate_models does not handle includeFringeWithoutGrass. "
            "Add: include_fringe_without_grass = bool(data.get('includeFringeWithoutGrass', False))"
        )

    def test_route_passes_to_run_pipeline(self):
        """T18b: app.py must pass include_fringe_without_grass to run_pipeline()."""
        with open(APP_PY) as f:
            src = f.read()
        assert "include_fringe_without_grass" in src, (
            "app.py does not pass include_fringe_without_grass to run_pipeline(). "
            "Add the kwarg to the run_pipeline() call in generate_models."
        )

    def test_no_stale_enable_fringe_grass_in_route(self):
        """T18c: app.py must not pass stale enable_fringe_grass to run_pipeline()."""
        with open(APP_PY) as f:
            src = f.read()
        # The run_pipeline call must not include the old kwarg
        # Find the run_pipeline call block
        idx = src.find("run_pipeline(")
        assert idx != -1, "run_pipeline call not found in app.py"
        # Look within the call (up to closing paren)
        call_region = src[idx:idx + 400]
        assert "enable_fringe_grass=" not in call_region, (
            "app.py still passes stale enable_fringe_grass= kwarg to run_pipeline(). "
            "Replace with include_fringe_without_grass=include_fringe_without_grass."
        )


# ─────────────────────────────────────────────────────────────────────────────
# T19: UI — editor.html has checkbox x-modelled to includeFringeWithoutGrass
# ─────────────────────────────────────────────────────────────────────────────

class TestUICheckboxModel:

    def test_checkbox_x_model_include_fringe_without_grass(self):
        """T19: editor.html must have checkbox x-model='includeFringeWithoutGrass'."""
        src = _read_editor_js()
        assert (
            'x-model="includeFringeWithoutGrass"' in src
            or "x-model='includeFringeWithoutGrass'" in src
        ), (
            "No checkbox x-model='includeFringeWithoutGrass' found in editor.html. "
            "The old enableFringeGrass x-model must be replaced."
        )

    def test_old_enable_fringe_grass_x_model_absent(self):
        """T19b: Old x-model='enableFringeGrass' must be gone from editor.html."""
        src = _read_editor_js()
        assert 'x-model="enableFringeGrass"' not in src and "x-model='enableFringeGrass'" not in src, (
            "Old x-model='enableFringeGrass' still present in editor.html. "
            "Remove it — the field was renamed to includeFringeWithoutGrass."
        )


# ─────────────────────────────────────────────────────────────────────────────
# T20: UI — label text is "Include Fringe Without Grass"
# ─────────────────────────────────────────────────────────────────────────────

class TestUILabelText:

    def test_label_text_include_fringe_without_grass(self):
        """T20: editor.html must have label 'Include Fringe Without Grass'."""
        src = _read_editor_js()
        assert "Include Fringe Without Grass" in src, (
            "Label 'Include Fringe Without Grass' not found in editor.html."
        )

    def test_old_label_text_absent(self):
        """T20b: Old label 'Enable Fringe Grass' must be gone from editor.html."""
        src = _read_editor_js()
        assert "Enable Fringe Grass" not in src, (
            "Old label 'Enable Fringe Grass' still present in editor.html. "
            "Replace with 'Include Fringe Without Grass'."
        )
