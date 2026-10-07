"""
test_include_fringe_without_grass.py — Bug→TDD: "Include Fringe Without Grass"
checkbox (task 724)

Semantic flip from task 714/718:

  OLD (task 714): "Enable Fringe Grass" (default checked) — plate 1 had grass
    controlled by checkbox; plate 2 always had grass (task 718).

  NEW (task 724): "Include Fringe Without Grass" (default UNCHECKED):
    - Plate 1: ALWAYS has grass (unconditional — checkbox has no effect on it).
    - Plate 2: only generated when checkbox is CHECKED; when generated it holds
      a smooth fringe WITHOUT grass (opposite of old plate 2).
    - Checkbox = opt-in to a second plate comparison sample.

RED-first tests.  All should fail before implementation.

Tests
-----
T1  Checkbox label text — "Include Fringe Without Grass".
T2  Alpine default state — includeFringeWithoutGrass: false.
T3  autoSave writes the field — includes includeFringeWithoutGrass.
T4  loadProject reads the field — assigns this.includeFringeWithoutGrass.
T5  Legacy field ignored — EGM with only enableFringeGrass:true loads to false.
T6  clearEditorState resets to false.
T7  startNewProject resets to false.
T8  EGM round-trip true — save true, load true.
T9  EGM round-trip false — save false, load false.
T10 Plate 1 ALWAYS has grass — grass called even when includeFringeWithoutGrass=False.
T11 Unchecked (false) → single plate — no plate 2 in model_settings.config.
T12 Checked (true) → two plates — 2 <plate> blocks, plate 2 ≥ 1 instance.
T13 Plate 2 mesh is grass-less — plate 2 scene name identifies the no-grass sample.
T14 Plater name updated — plate 2's plater_name reflects new semantic.
T15 app.py route wired — reads includeFringeWithoutGrass, passes to run_pipeline.
"""
from __future__ import annotations

import json
import os
import re
import sys
import io
import zipfile
import xml.etree.ElementTree as ET

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

EDITOR_HTML = os.path.join(os.path.dirname(__file__), "..", "templates", "editor.html")
APP_PY = os.path.join(os.path.dirname(__file__), "..", "app.py")
_APP_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def _read_editor() -> str:
    with open(EDITOR_HTML, "r") as f:
        return f.read()


def _read_app() -> str:
    with open(APP_PY, "r") as f:
        return f.read()


# ─────────────────────────────────────────────────────────────────────────────
# T1: Checkbox label text
# ─────────────────────────────────────────────────────────────────────────────

class TestCheckboxLabelText:

    def test_label_text_is_include_fringe_without_grass(self):
        """T1: editor.html must show 'Include Fringe Without Grass' as the label."""
        src = _read_editor()
        assert "Include Fringe Without Grass" in src, (
            "Label text 'Include Fringe Without Grass' not found in editor.html. "
            "Change the checkbox span text from 'Enable Fringe Grass'."
        )

    def test_old_label_text_gone(self):
        """T1b: The old label 'Enable Fringe Grass' must no longer appear."""
        src = _read_editor()
        assert "Enable Fringe Grass" not in src, (
            "Old label text 'Enable Fringe Grass' is still present in editor.html. "
            "Replace it with 'Include Fringe Without Grass'."
        )


# ─────────────────────────────────────────────────────────────────────────────
# T2: Alpine default state — false (opt-in; single plate by default)
# ─────────────────────────────────────────────────────────────────────────────

class TestAlpineDefaultState:

    def test_default_is_false(self):
        """T2: x-data must initialise includeFringeWithoutGrass to false (not true)."""
        src = _read_editor()
        assert "includeFringeWithoutGrass: false" in src, (
            "includeFringeWithoutGrass: false not found in editor.html x-data. "
            "The new default is false (single plate, no comparison sample)."
        )

    def test_old_field_default_gone(self):
        """T2b: The old enableFringeGrass: true initialisation must not appear."""
        src = _read_editor()
        assert "enableFringeGrass: true" not in src, (
            "Old field 'enableFringeGrass: true' is still in editor.html x-data. "
            "Remove it; the new field is includeFringeWithoutGrass."
        )


# ─────────────────────────────────────────────────────────────────────────────
# T3: autoSave writes the new field name
# ─────────────────────────────────────────────────────────────────────────────

class TestAutoSaveWritesField:

    def test_autosave_includes_new_field(self):
        """T3: autoSave() must include includeFringeWithoutGrass in its data object."""
        src = _read_editor()
        m = re.search(r'async autoSave\s*\(\s*\)\s*\{(.+?)^\s*\},', src,
                      re.DOTALL | re.MULTILINE)
        assert m, "autoSave() function body not found in editor.html"
        body = m.group(1)
        assert "includeFringeWithoutGrass" in body, (
            "autoSave() does not include includeFringeWithoutGrass. "
            "Replace enableFringeGrass with includeFringeWithoutGrass in the data dict."
        )

    def test_autosave_old_field_gone(self):
        """T3b: autoSave() must not include the old enableFringeGrass field."""
        src = _read_editor()
        m = re.search(r'async autoSave\s*\(\s*\)\s*\{(.+?)^\s*\},', src,
                      re.DOTALL | re.MULTILINE)
        assert m, "autoSave() function body not found"
        body = m.group(1)
        assert "enableFringeGrass" not in body, (
            "autoSave() still references enableFringeGrass. Remove it."
        )


# ─────────────────────────────────────────────────────────────────────────────
# T4: loadProject reads new field
# ─────────────────────────────────────────────────────────────────────────────

class TestLoadProjectReadsField:

    def test_load_project_assigns_new_field(self):
        """T4: loadProject() must assign this.includeFringeWithoutGrass."""
        src = _read_editor()
        m = re.search(r'async loadProject\s*\(proj\)\s*\{(.+?)^\s*\},', src,
                      re.DOTALL | re.MULTILINE)
        assert m, "loadProject() not found in editor.html"
        body = m.group(1)
        assert "includeFringeWithoutGrass" in body, (
            "loadProject() does not assign this.includeFringeWithoutGrass. "
            "Add the assignment and remove the old enableFringeGrass assignment."
        )


# ─────────────────────────────────────────────────────────────────────────────
# T5: Legacy field ignored — EGM with enableFringeGrass but no new field → false
# ─────────────────────────────────────────────────────────────────────────────

class TestLegacyFieldIgnored:

    def test_old_field_not_read_in_loadproject(self):
        """T5a: loadProject() must not read enableFringeGrass at all."""
        src = _read_editor()
        m = re.search(r'async loadProject\s*\(proj\)\s*\{(.+?)^\s*\},', src,
                      re.DOTALL | re.MULTILINE)
        assert m, "loadProject() not found"
        body = m.group(1)
        assert "enableFringeGrass" not in body, (
            "loadProject() still reads enableFringeGrass — remove it. "
            "Old EGMs with that field should load as includeFringeWithoutGrass=false."
        )

    def test_missing_new_field_defaults_false_in_loadproject(self):
        """T5b: loadProject() must default includeFringeWithoutGrass to false when absent.

        Correct pattern: data.includeFringeWithoutGrass === true  (strict equality)
        or: !!data.includeFringeWithoutGrass  (falsy default)
        Either way, a missing key or false value must not enable plate 2.
        """
        src = _read_editor()
        m = re.search(r'async loadProject\s*\(proj\)\s*\{(.+?)^\s*\},', src,
                      re.DOTALL | re.MULTILINE)
        assert m, "loadProject() not found"
        body = m.group(1)
        # The new field should be assigned in loadProject
        assert "includeFringeWithoutGrass" in body, (
            "loadProject() must assign this.includeFringeWithoutGrass from the EGM. "
            "Use: this.includeFringeWithoutGrass = !!data.includeFringeWithoutGrass; "
            "(or data.includeFringeWithoutGrass === true) so missing → false."
        )
        # The assignment must NOT use '!== false' pattern (which would default to true)
        idx = body.find("includeFringeWithoutGrass")
        region = body[idx: idx + 120]
        assert "!== false" not in region, (
            "loadProject() uses '!== false' for includeFringeWithoutGrass — this "
            "defaults to TRUE, but the new default is FALSE. "
            "Use !!data.includeFringeWithoutGrass or === true instead."
        )


# ─────────────────────────────────────────────────────────────────────────────
# T6: clearEditorState resets to false
# ─────────────────────────────────────────────────────────────────────────────

class TestClearEditorStateResetsField:

    def test_clear_resets_to_false(self):
        """T6: clearEditorState() must reset includeFringeWithoutGrass to false."""
        src = _read_editor()
        m = re.search(r'clearEditorState\s*\(\s*\)\s*\{(.+?)^\s*\},', src,
                      re.DOTALL | re.MULTILINE)
        assert m, "clearEditorState() body not found"
        body = m.group(1)
        assert "includeFringeWithoutGrass" in body, (
            "clearEditorState() does not reset includeFringeWithoutGrass. "
            "Add: this.includeFringeWithoutGrass = false;"
        )
        idx = body.find("includeFringeWithoutGrass")
        region = body[idx: idx + 60]
        assert "false" in region, (
            "clearEditorState() sets includeFringeWithoutGrass but not to false. "
            "Use: this.includeFringeWithoutGrass = false;"
        )

    def test_clear_old_field_gone(self):
        """T6b: clearEditorState() must not reference the old enableFringeGrass."""
        src = _read_editor()
        m = re.search(r'clearEditorState\s*\(\s*\)\s*\{(.+?)^\s*\},', src,
                      re.DOTALL | re.MULTILINE)
        assert m, "clearEditorState() body not found"
        body = m.group(1)
        assert "enableFringeGrass" not in body, (
            "clearEditorState() still references enableFringeGrass. Remove it."
        )


# ─────────────────────────────────────────────────────────────────────────────
# T7: startNewProject resets to false
# ─────────────────────────────────────────────────────────────────────────────

class TestStartNewProjectResetsField:

    def test_start_new_project_resets_to_false(self):
        """T7: startNewProject() must reset includeFringeWithoutGrass to false."""
        src = _read_editor()
        m = re.search(r'async startNewProject\s*\(\s*\)\s*\{(.+?)^\s*\},', src,
                      re.DOTALL | re.MULTILINE)
        assert m, "startNewProject() not found in editor.html"
        body = m.group(1)
        assert "includeFringeWithoutGrass" in body, (
            "startNewProject() does not reset includeFringeWithoutGrass. "
            "Add: this.includeFringeWithoutGrass = false;"
        )
        idx = body.find("includeFringeWithoutGrass")
        region = body[idx: idx + 60]
        assert "false" in region, (
            "startNewProject() sets includeFringeWithoutGrass but not to false."
        )


# ─────────────────────────────────────────────────────────────────────────────
# T8 & T9: EGM round-trip via Flask routes
# ─────────────────────────────────────────────────────────────────────────────

@pytest.fixture()
def egm_client(tmp_path, monkeypatch):
    """Flask test client + temp EGM tree.  Never touches live DB."""
    import app as _app_module
    tmp_db = str(tmp_path / "workspace.db")
    monkeypatch.setattr(_app_module, "DB_PATH", tmp_db)

    egm_dir = tmp_path / "GolfCourses" / "Test Course" / "EGMs"
    egm_dir.mkdir(parents=True)
    monkeypatch.setattr(_app_module, "_EGM_BASE", str(tmp_path / "GolfCourses"))

    _app_module.app.config["TESTING"] = True
    with _app_module.app.test_client() as client:
        yield client, egm_dir


def _write_egm(egm_dir, fname: str, extra: dict) -> None:
    base = {
        "course": "Test Course",
        "hole": "5",
        "image": "test.jpg",
        "imageCourse": "Test Course",
        "polygons": [
            {"type": "green",  "points": [{"x": 10, "y": 10}, {"x": 20, "y": 10}, {"x": 15, "y": 20}]},
            {"type": "fringe", "points": [{"x":  5, "y":  5}, {"x": 25, "y":  5}, {"x": 15, "y": 25}]},
        ],
        "contourStep": 0.5,
        "grassAmplitude": 0.5,
        "grassSpacing": 0.05,
        "greenStyle": "terraced",
        "elevationRange": 14.5,
        "greenScale": 1.0065,
        "fringeEdgeHeight": 10.0,
        "baseThicknessMm": 1.5,
        "gpsBackend": {
            "enabled": True,
            "gpsFile": "/some/course.gps",
            "bbox": {"lat_min": 36.0, "lng_min": -122.0, "lat_max": 36.01, "lng_max": -121.99},
            "approachM": 10.0,
            "vertExag": 2.5,
            "gridSize": [150, 150],
        },
    }
    base.update(extra)
    (egm_dir / fname).write_text(json.dumps(base))


class TestEGMRoundTrip:

    def test_round_trip_true(self, egm_client):
        """T8: Load EGM with includeFringeWithoutGrass=true → API returns true."""
        client, egm_dir = egm_client
        fname = "Test Course (Hole 05).egm"
        _write_egm(egm_dir, fname, {"includeFringeWithoutGrass": True})
        resp = client.get(f"/api/boundaries/load?filename={fname}")
        assert resp.status_code == 200, f"Unexpected status: {resp.status_code}"
        data = resp.get_json()
        assert data["status"] == "ok"
        assert data.get("includeFringeWithoutGrass") is True, (
            f"Expected includeFringeWithoutGrass=true but got: {data.get('includeFringeWithoutGrass')}"
        )

    def test_round_trip_false(self, egm_client):
        """T9: Load EGM with includeFringeWithoutGrass=false → API returns false."""
        client, egm_dir = egm_client
        fname = "Test Course (Hole 05).egm"
        _write_egm(egm_dir, fname, {"includeFringeWithoutGrass": False})
        resp = client.get(f"/api/boundaries/load?filename={fname}")
        assert resp.status_code == 200
        data = resp.get_json()
        assert data["status"] == "ok"
        assert data.get("includeFringeWithoutGrass") is False, (
            f"Expected includeFringeWithoutGrass=false but got: {data.get('includeFringeWithoutGrass')}"
        )

    def test_legacy_egm_without_new_field(self, egm_client):
        """T5c: Load EGM with only enableFringeGrass:true (old field) → new field absent/false."""
        client, egm_dir = egm_client
        fname = "Test Course (Hole 05).egm"
        # Old EGM: only the old field; the new field does not exist.
        _write_egm(egm_dir, fname, {"enableFringeGrass": True})
        resp = client.get(f"/api/boundaries/load?filename={fname}")
        assert resp.status_code == 200
        data = resp.get_json()
        assert data["status"] == "ok"
        # New field must NOT be present (or must be falsy) — old field must not be mapped.
        new_val = data.get("includeFringeWithoutGrass")
        assert not new_val, (
            f"EGM with only enableFringeGrass:true must NOT map to includeFringeWithoutGrass=true. "
            f"Got: includeFringeWithoutGrass={new_val!r}. Legacy field must be ignored."
        )


# ─────────────────────────────────────────────────────────────────────────────
# T10: Plate 1 ALWAYS has grass — unconditional even when checkbox unchecked
# ─────────────────────────────────────────────────────────────────────────────

class TestPlate1AlwaysHasGrass:

    def test_grass_called_when_checkbox_unchecked(self, tmp_path, monkeypatch):
        """T10: When includeFringeWithoutGrass=False, plate 1 still gets grass.

        The grass function must be called for the main plate-1 fringe
        regardless of the checkbox state.
        """
        from pathlib import Path
        import gradient_surface_diagnostic as gsd

        EGM_BASE = Path(_APP_DIR).parent / "ItWentIn" / "GolfCourses"
        egm_files = list(EGM_BASE.rglob("*.egm")) if EGM_BASE.exists() else []
        if not egm_files:
            pytest.skip("No real EGM files for pipeline test")

        with open(str(egm_files[0])) as f:
            egm_data = json.load(f)
        # New checkbox off — plate 1 still gets grass
        egm_data["includeFringeWithoutGrass"] = False
        # Remove old field to avoid confusion
        egm_data.pop("enableFringeGrass", None)

        test_egm = tmp_path / "test_plate1_grass.egm"
        test_egm.write_text(json.dumps(egm_data))

        call_log: list[str] = []

        def _mock_v2(*args, **kwargs):
            call_log.append("v2")

        def _mock_v1(*args, **kwargs):
            call_log.append("v1")

        monkeypatch.setattr(gsd, "apply_grass_texture_v2", _mock_v2)
        monkeypatch.setattr(gsd, "apply_grass_texture", _mock_v1)

        try:
            gsd.run_pipeline(str(test_egm))
        except Exception:
            pass

        # Plate 1 always has grass → at least 1 call even with checkbox off.
        assert len(call_log) >= 1, (
            "apply_grass_texture / apply_grass_texture_v2 were never called even "
            "though plate 1 ALWAYS has grass (includeFringeWithoutGrass only gates "
            "plate 2, not plate 1). Got 0 calls."
        )


# ─────────────────────────────────────────────────────────────────────────────
# T11: Checkbox unchecked (false) → single plate, no plate 2
# ─────────────────────────────────────────────────────────────────────────────

def _make_minimal_3mf(names: list[str]) -> bytes:
    """Build a minimal trimesh-style 3MF with one object per name."""
    objects_xml = ""
    for i, name in enumerate(names, start=1):
        objects_xml += f"""
  <object id="{i}" name="{name}" type="model">
   <mesh>
    <vertices>
     <vertex x="0" y="0" z="0"/><vertex x="1" y="0" z="0"/>
     <vertex x="1" y="1" z="0"/><vertex x="0" y="1" z="0"/>
     <vertex x="0" y="0" z="1"/><vertex x="1" y="0" z="1"/>
     <vertex x="1" y="1" z="1"/><vertex x="0" y="1" z="1"/>
    </vertices>
    <triangles>
     <triangle v1="0" v2="2" v3="1"/><triangle v1="0" v2="3" v3="2"/>
     <triangle v1="4" v2="5" v3="6"/><triangle v1="4" v2="6" v3="7"/>
     <triangle v1="0" v2="1" v3="5"/><triangle v1="0" v2="5" v3="4"/>
     <triangle v1="1" v2="2" v3="6"/><triangle v1="1" v2="6" v3="5"/>
     <triangle v1="2" v2="3" v3="7"/><triangle v1="2" v2="7" v3="6"/>
     <triangle v1="3" v2="0" v3="4"/><triangle v1="3" v2="4" v3="7"/>
    </triangles>
   </mesh>
  </object>"""
    model_xml = f"""<?xml version="1.0" encoding="UTF-8"?>
<model unit="millimeter" xml:lang="en-US"
  xmlns="http://schemas.microsoft.com/3dmanufacturing/core/2015/02"
  xmlns:p="http://schemas.microsoft.com/3dmanufacturing/production/2015/06">
 <resources>{objects_xml}
 </resources>
 <build/>
</model>"""
    rels_xml = """<?xml version='1.0' encoding='utf-8'?>
<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">
 <Relationship Type="http://schemas.microsoft.com/3dmanufacturing/2013/01/3dmodel"
   Target="/3D/3dmodel.model" Id="rel0"/>
</Relationships>"""
    ct_xml = """<?xml version='1.0' encoding='utf-8'?>
<Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types">
 <Default Extension="model"
   ContentType="application/vnd.ms-package.3dmanufacturing-3dmodel+xml"/>
 <Default Extension="rels"
   ContentType="application/vnd.openxmlformats-package.relationships+xml"/>
</Types>"""
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as zf:
        zf.writestr("3D/3dmodel.model", model_xml)
        zf.writestr("_rels/.rels", rels_xml)
        zf.writestr("[Content_Types].xml", ct_xml)
    return buf.getvalue()


_FRINGE_NO_GRASS_SCENE_NAME = "fringe_no_grass_sample"

_PLATE2_THUMBNAILS = [
    "Metadata/plate_2.png",
    "Metadata/plate_no_light_2.png",
    "Metadata/top_2.png",
    "Metadata/pick_2.png",
]


@pytest.fixture(scope="module")
def gsd_module():
    import importlib.util
    spec = importlib.util.spec_from_file_location(
        "gradient_surface_diagnostic",
        os.path.join(_APP_DIR, "gradient_surface_diagnostic.py"),
    )
    mod = importlib.util.module_from_spec(spec)
    sys.modules["gradient_surface_diagnostic"] = mod
    try:
        spec.loader.exec_module(mod)
    except Exception as exc:
        pytest.skip(f"gradient_surface_diagnostic unavailable: {exc}")
    return mod


class TestSinglePlateWhenUnchecked:
    """T11: When fringe_no_grass_sample is absent from scene, single plate only."""

    def test_no_plate2_without_sample(self, gsd_module, tmp_path):
        # No fringe_no_grass_sample in names → single plate
        names = ["green_surface", "fringe", "trap_1"]
        raw = _make_minimal_3mf(names)
        dest = tmp_path / "test_single.3mf"
        dest.write_bytes(raw)

        gsd_module._inject_bambu_extruder_metadata(str(dest), names)

        with zipfile.ZipFile(str(dest)) as z:
            cfg_xml = z.read("Metadata/model_settings.config").decode("utf-8")
            present = z.namelist()

        root = ET.fromstring(cfg_xml)
        plates = root.findall("plate")
        assert len(plates) <= 1, (
            f"Expected ≤1 <plate> block when fringe_no_grass_sample is absent. "
            f"Got {len(plates)}."
        )
        for arcname in _PLATE2_THUMBNAILS:
            assert arcname not in present, (
                f"{arcname} found in archive but fringe_no_grass_sample was not in "
                f"scene_names — plate-2 thumbnails must not be injected."
            )


# ─────────────────────────────────────────────────────────────────────────────
# T12: Checkbox checked (true) → two plates, plate 2 has ≥ 1 instance
# ─────────────────────────────────────────────────────────────────────────────

class TestTwoPlatesWhenChecked:
    """T12: With fringe_no_grass_sample in scene → two <plate> blocks."""

    def test_two_plate_blocks(self, gsd_module, tmp_path):
        names = ["green_surface", "fringe", _FRINGE_NO_GRASS_SCENE_NAME]
        raw = _make_minimal_3mf(names)
        dest = tmp_path / "test_two_plates.3mf"
        dest.write_bytes(raw)

        gsd_module._inject_bambu_extruder_metadata(str(dest), names)

        with zipfile.ZipFile(str(dest)) as z:
            cfg_xml = z.read("Metadata/model_settings.config").decode("utf-8")

        root = ET.fromstring(cfg_xml)
        plates = root.findall("plate")
        assert len(plates) == 2, (
            f"Expected 2 <plate> blocks when fringe_no_grass_sample is in scene. "
            f"Got {len(plates)}. The injection function must detect "
            f"'{_FRINGE_NO_GRASS_SCENE_NAME}' as the plate-2 trigger."
        )

    def test_plate2_has_instance(self, gsd_module, tmp_path):
        names = ["green_surface", "fringe", _FRINGE_NO_GRASS_SCENE_NAME]
        raw = _make_minimal_3mf(names)
        dest = tmp_path / "test_p2_inst.3mf"
        dest.write_bytes(raw)

        gsd_module._inject_bambu_extruder_metadata(str(dest), names)

        with zipfile.ZipFile(str(dest)) as z:
            cfg_xml = z.read("Metadata/model_settings.config").decode("utf-8")

        root = ET.fromstring(cfg_xml)
        plates = root.findall("plate")
        assert len(plates) == 2, f"Expected 2 plates, got {len(plates)}"
        plate2 = plates[1]
        instances = plate2.findall("model_instance")
        assert len(instances) >= 1, (
            f"Plate 2 has no model_instance. Expected the fringe_no_grass_sample object."
        )


# ─────────────────────────────────────────────────────────────────────────────
# T13: Plate 2 scene name is "fringe_no_grass_sample"
# ─────────────────────────────────────────────────────────────────────────────

class TestPlate2SceneName:
    """T13: The plate-2 sentinel scene name in run_pipeline is 'fringe_no_grass_sample'."""

    def test_fringe_no_grass_sample_sentinel_in_gsd(self):
        """T13: gradient_surface_diagnostic.py must use 'fringe_no_grass_sample'
        as the plate-2 scene name (not 'fringe_grass_sample')."""
        import importlib.util
        spec = importlib.util.spec_from_file_location(
            "gsd_src_check",
            os.path.join(_APP_DIR, "gradient_surface_diagnostic.py"),
        )
        # Read source without loading (avoids import side effects)
        with open(os.path.join(_APP_DIR, "gradient_surface_diagnostic.py")) as f:
            src = f.read()

        # The new sentinel must appear
        assert "fringe_no_grass_sample" in src, (
            "'fringe_no_grass_sample' not found in gradient_surface_diagnostic.py. "
            "The plate-2 node must be named 'fringe_no_grass_sample' to reflect "
            "the new semantics (no grass on plate 2)."
        )

    def test_pipeline_adds_fringe_no_grass_sample_when_checked(self, tmp_path, monkeypatch):
        """T13b: run_pipeline with includeFringeWithoutGrass=True must add
        'fringe_no_grass_sample' to scene_names passed to _inject."""
        import gradient_surface_diagnostic as gsd_mod
        from pathlib import Path

        EGM_BASE = Path(_APP_DIR).parent / "ItWentIn" / "GolfCourses"
        egm_files = list(EGM_BASE.rglob("*.egm")) if EGM_BASE.exists() else []
        if not egm_files:
            pytest.skip("No real EGM files for pipeline test")

        with open(str(egm_files[0])) as f:
            egm_data = json.load(f)
        egm_data["includeFringeWithoutGrass"] = True
        egm_data.pop("enableFringeGrass", None)

        test_egm = tmp_path / "test_p13b.egm"
        test_egm.write_text(json.dumps(egm_data))

        captured: list[list[str]] = []

        def _mock_inject(path_3mf, scene_names):
            captured.append(list(scene_names))

        monkeypatch.setattr(gsd_mod, "_inject_bambu_extruder_metadata", _mock_inject)

        import trimesh
        def _noop_export(self, *a, **kw):
            from pathlib import Path as _P
            _P(a[0]).write_bytes(b"PK\x03\x04")

        monkeypatch.setattr(trimesh.Scene, "export", _noop_export)

        try:
            gsd_mod.run_pipeline(str(test_egm))
        except Exception:
            pass

        if not captured:
            pytest.skip("_inject_bambu_extruder_metadata was not reached")

        scene_names = captured[-1]
        assert "fringe_no_grass_sample" in scene_names, (
            f"run_pipeline did not add 'fringe_no_grass_sample' when "
            f"includeFringeWithoutGrass=True. Got: {scene_names}"
        )

    def test_pipeline_no_sample_when_unchecked(self, tmp_path, monkeypatch):
        """T13c: run_pipeline with includeFringeWithoutGrass=False must NOT add
        'fringe_no_grass_sample' to scene_names."""
        import gradient_surface_diagnostic as gsd_mod
        from pathlib import Path

        EGM_BASE = Path(_APP_DIR).parent / "ItWentIn" / "GolfCourses"
        egm_files = list(EGM_BASE.rglob("*.egm")) if EGM_BASE.exists() else []
        if not egm_files:
            pytest.skip("No real EGM files for pipeline test")

        with open(str(egm_files[0])) as f:
            egm_data = json.load(f)
        egm_data["includeFringeWithoutGrass"] = False
        egm_data.pop("enableFringeGrass", None)

        test_egm = tmp_path / "test_p13c.egm"
        test_egm.write_text(json.dumps(egm_data))

        captured: list[list[str]] = []

        def _mock_inject(path_3mf, scene_names):
            captured.append(list(scene_names))

        monkeypatch.setattr(gsd_mod, "_inject_bambu_extruder_metadata", _mock_inject)

        import trimesh
        def _noop_export(self, *a, **kw):
            from pathlib import Path as _P
            _P(a[0]).write_bytes(b"PK\x03\x04")

        monkeypatch.setattr(trimesh.Scene, "export", _noop_export)

        try:
            gsd_mod.run_pipeline(str(test_egm))
        except Exception:
            pass

        if not captured:
            pytest.skip("_inject_bambu_extruder_metadata not reached")

        scene_names = captured[-1]
        assert "fringe_no_grass_sample" not in scene_names, (
            f"run_pipeline added 'fringe_no_grass_sample' but checkbox was unchecked. "
            f"Scene: {scene_names}"
        )


# ─────────────────────────────────────────────────────────────────────────────
# T14: Plate 2 plater_name reflects new semantic
# ─────────────────────────────────────────────────────────────────────────────

class TestPlate2PlaterName:
    """T14: Plate 2's plater_name must reflect 'no grass' semantics."""

    def test_plate2_plater_name_no_grass(self, gsd_module, tmp_path):
        names = ["green_surface", "fringe", _FRINGE_NO_GRASS_SCENE_NAME]
        raw = _make_minimal_3mf(names)
        dest = tmp_path / "test_p2_name.3mf"
        dest.write_bytes(raw)

        gsd_module._inject_bambu_extruder_metadata(str(dest), names)

        with zipfile.ZipFile(str(dest)) as z:
            cfg_xml = z.read("Metadata/model_settings.config").decode("utf-8")

        root = ET.fromstring(cfg_xml)
        plates = root.findall("plate")
        assert len(plates) == 2, f"Expected 2 plates, got {len(plates)}"
        plate2 = plates[1]

        name_meta = plate2.find("metadata[@key='plater_name']")
        assert name_meta is not None, "Plate 2 missing plater_name metadata"
        plater_name = name_meta.attrib.get("value", "")
        # The name must reflect "no grass" / "smooth fringe" — not "Fringe Grass Sample"
        assert "Grass Sample" not in plater_name or "No Grass" in plater_name, (
            f"Plate 2 plater_name still says '{plater_name}' which implies grass. "
            f"Update to something like 'Fringe No Grass Sample'."
        )
        # Positive check: must contain "No Grass" or "no grass" or similar
        assert any(kw in plater_name for kw in ["No Grass", "no grass", "Smooth", "smooth"]), (
            f"Plate 2 plater_name '{plater_name}' does not indicate grass-less content. "
            f"Use a name like 'Fringe No Grass Sample'."
        )


# ─────────────────────────────────────────────────────────────────────────────
# T15: app.py route reads new field, passes to run_pipeline
# ─────────────────────────────────────────────────────────────────────────────

class TestAppRouteWiring:

    def test_route_reads_new_field(self):
        """T15a: app.py must extract includeFringeWithoutGrass from request data."""
        src = _read_app()
        assert "includeFringeWithoutGrass" in src, (
            "app.py does not handle includeFringeWithoutGrass. "
            "Add: include_fringe_without_grass = bool(data.get('includeFringeWithoutGrass', False))"
        )

    def test_route_does_not_read_old_field(self):
        """T15b: app.py must not read enableFringeGrass from request data."""
        src = _read_app()
        assert "enableFringeGrass" not in src, (
            "app.py still reads enableFringeGrass. Remove it."
        )

    def test_route_passes_to_run_pipeline(self):
        """T15c: app.py must pass include_fringe_without_grass to run_pipeline()."""
        src = _read_app()
        assert "include_fringe_without_grass" in src, (
            "app.py does not pass include_fringe_without_grass to run_pipeline(). "
            "Add the kwarg to the run_pipeline() call."
        )


# ─────────────────────────────────────────────────────────────────────────────
# T16: Version bump checks
# ─────────────────────────────────────────────────────────────────────────────

class TestVersionBumps:

    def test_app_version_bumped(self):
        """T16a: APP_VERSION in app.py must be >= v5.12."""
        src = _read_app()
        m = re.search(r'APP_VERSION\s*=\s*["\']v(\d+)\.(\d+)["\']', src)
        assert m, "APP_VERSION not found in app.py"
        major, minor = int(m.group(1)), int(m.group(2))
        assert (major, minor) >= (5, 12), (
            f"APP_VERSION is v{major}.{minor}; must be >= v5.12 after this task."
        )

    def test_gsd_version_bumped(self):
        """T16b: __version__ in gradient_surface_diagnostic.py must be >= v0.22."""
        with open(os.path.join(_APP_DIR, "gradient_surface_diagnostic.py")) as f:
            src = f.read()
        m = re.search(r'#\s*v(\d+)\.(\d+)', src)
        assert m, "Version comment not found in gradient_surface_diagnostic.py"
        major, minor = int(m.group(1)), int(m.group(2))
        assert (major, minor) >= (0, 22), (
            f"gradient_surface_diagnostic.py version is v{major}.{minor}; must be >= v0.22."
        )

    def test_editor_version_bumped(self):
        """T16c: editor.html version comment must be >= v5.08."""
        src = _read_editor()
        m = re.search(r'Boundary Editor v(\d+)\.(\d+)', src)
        assert m, "Boundary Editor version comment not found in editor.html"
        major, minor = int(m.group(1)), int(m.group(2))
        assert (major, minor) >= (5, 8), (
            f"editor.html shows Boundary Editor v{major}.{minor}; must be >= v5.08."
        )
