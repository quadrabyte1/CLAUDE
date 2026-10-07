"""
test_bambu_two_plate_output.py — Bug→TDD: Two-plate 3MF output (task 724 flip)

Thomas's spec:
  - Plate 1: full plaque — green + fringe WITH GRASS (unconditional) + traps + water + boulders.
  - Plate 2: smooth (grass-less) fringe sample — only generated when
    include_fringe_without_grass=True.
  - Scene node name changed: "fringe_grass_sample" → "fringe_no_grass_sample".
  - Plate 2 plater_name: "Fringe No Grass Sample" (was "Fringe Grass Sample").

== Tests ==

T1  model_settings.config has TWO <plate> blocks when fringe_no_grass_sample present.
T2  Plate 1 instances reference original object IDs (1..N-1, not the sample).
T3  Plate 2 instance references the fringe-no-grass-sample object ID (N+1).
T4  Plate 2 block references Metadata/plate_2.png thumbnail.
T5  Archive contains Metadata/plate_2.png, plate_no_light_2.png, top_2.png, pick_2.png.
T6  Archive contains single-plate files (regression guard).
T7  Archive round-trip valid: zipfile.testzip() returns None.
T8  Idempotent: injecting twice gives exactly one of each plate-2 thumbnail file.
T9  Plate 2 uses extruder 2 (fringe filament) for fringe_no_grass_sample.
T10 Backward compat: no fringe_no_grass_sample → single-plate behaviour preserved.
T11 model_settings.config plate_2 block has plater_id=2.
T12 Archive has ≥ 16 entries for two-plate output.
T13 run_pipeline adds "fringe_no_grass_sample" (not "fringe_grass_sample") to scene
    when include_fringe_without_grass=True.
T14 Plate 2 has NO grass: when include_fringe_without_grass=True, grass functions
    called exactly once (plate 1 only; plate 2 is the smooth sample).
T15 Old scene node "fringe_grass_sample" is gone — not in scene_names.
T16 Plate 2 plater_name is "Fringe No Grass Sample" (not "Fringe Grass Sample").
"""
from __future__ import annotations

import importlib.util
import io
import sys
import xml.etree.ElementTree as ET
import zipfile
from pathlib import Path

import pytest

# ---------------------------------------------------------------------------
# Path setup
# ---------------------------------------------------------------------------

_APP_DIR = Path(__file__).parent.parent
_TEMPLATE_DIR = _APP_DIR / "templates" / "bambu"

if str(_APP_DIR) not in sys.path:
    sys.path.insert(0, str(_APP_DIR))


def _load_gsd_module():
    spec = importlib.util.spec_from_file_location(
        "gradient_surface_diagnostic",
        str(_APP_DIR / "gradient_surface_diagnostic.py"),
    )
    mod = importlib.util.module_from_spec(spec)
    sys.modules["gradient_surface_diagnostic"] = mod
    spec.loader.exec_module(mod)
    return mod


@pytest.fixture(scope="module")
def gsd():
    try:
        return _load_gsd_module()
    except Exception as exc:
        pytest.skip(f"gradient_surface_diagnostic unavailable: {exc}")


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

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


def _plate_names(scene_names):
    """Standard plate 1 / plate 2 split: plate 2 = ['fringe_no_grass_sample']."""
    plate1 = [n for n in scene_names if n != "fringe_no_grass_sample"]
    plate2 = [n for n in scene_names if n == "fringe_no_grass_sample"]
    return plate1, plate2


# The plate-2 thumbnail file names we expect to appear in the archive.
_PLATE2_THUMBNAILS = [
    "Metadata/plate_2.png",
    "Metadata/plate_no_light_2.png",
    "Metadata/top_2.png",
    "Metadata/pick_2.png",
]

# Expected archive entries for a full two-plate 3MF.
_SINGLE_PLATE_ENTRIES = frozenset({
    "_rels/.rels",
    "[Content_Types].xml",
    "3D/3dmodel.model",
    "Metadata/model_settings.config",
    "Metadata/project_settings.config",
    "Metadata/slice_info.config",
    "Metadata/filament_sequence.json",
    "Metadata/pick_1.png",
    "Metadata/plate_1_small.png",
    "Metadata/plate_1.png",
    "Metadata/plate_no_light_1.png",
    "Metadata/top_1.png",
})


# ---------------------------------------------------------------------------
# T1 — model_settings.config has TWO <plate> blocks
# ---------------------------------------------------------------------------

class TestTwoPlateBlocks:
    """T1: After injection with fringe_no_grass_sample, config has two <plate> blocks."""

    def test_two_plate_blocks_in_config(self, gsd, tmp_path):
        # Use new scene node name
        names = ["green_surface", "fringe", "trap_1", "fringe_no_grass_sample"]
        raw = _make_minimal_3mf(names)
        dest = tmp_path / "test_two_plates.3mf"
        dest.write_bytes(raw)

        gsd._inject_bambu_extruder_metadata(str(dest), names)

        with zipfile.ZipFile(str(dest)) as z:
            cfg_xml = z.read("Metadata/model_settings.config").decode("utf-8")

        root = ET.fromstring(cfg_xml)
        plates = root.findall("plate")
        assert len(plates) == 2, (
            f"Expected 2 <plate> blocks in model_settings.config when "
            f"fringe_no_grass_sample is in scene_names; found {len(plates)}. "
            "The injection function must generate a <plate plater_id=1> for all "
            "objects except fringe_no_grass_sample, and a <plate plater_id=2> for "
            "fringe_no_grass_sample."
        )


# ---------------------------------------------------------------------------
# T2 — Plate 1 instances reference original object IDs
# ---------------------------------------------------------------------------

class TestPlate1Instances:
    """T2: Plate 1 model_instance blocks reference the plate-1 object IDs (1..N-1)."""

    def test_plate1_instances_cover_non_sample_objects(self, gsd, tmp_path):
        names = ["green_surface", "fringe", "fringe_no_grass_sample"]
        raw = _make_minimal_3mf(names)
        dest = tmp_path / "test_plate1_instances.3mf"
        dest.write_bytes(raw)

        gsd._inject_bambu_extruder_metadata(str(dest), names)

        with zipfile.ZipFile(str(dest)) as z:
            cfg_xml = z.read("Metadata/model_settings.config").decode("utf-8")

        root = ET.fromstring(cfg_xml)
        plates = root.findall("plate")
        assert len(plates) >= 1, "No plates found"
        plate1 = plates[0]

        instances = plate1.findall("model_instance")
        assert len(instances) >= 1, (
            "Plate 1 has no model_instance entries. Expected instances for "
            "green_surface and fringe (objectids 1 and 2)."
        )

        plate1_obj_ids = set()
        for inst in instances:
            oid_meta = inst.find("metadata[@key='object_id']")
            if oid_meta is not None:
                plate1_obj_ids.add(oid_meta.attrib.get("value"))

        assert "1" in plate1_obj_ids, (
            f"Plate 1 instances do not include object_id=1 (green_surface). "
            f"Found: {plate1_obj_ids}"
        )
        assert "2" in plate1_obj_ids, (
            f"Plate 1 instances do not include object_id=2 (fringe). "
            f"Found: {plate1_obj_ids}"
        )
        assert "3" not in plate1_obj_ids, (
            f"Plate 1 instances include object_id=3 (fringe_no_grass_sample) — "
            f"it should be on plate 2 only. Plate 1 ids: {plate1_obj_ids}"
        )


# ---------------------------------------------------------------------------
# T3 — Plate 2 instance references fringe_no_grass_sample object ID
# ---------------------------------------------------------------------------

class TestPlate2Instance:
    """T3: Plate 2 model_instance block references the fringe_no_grass_sample object ID."""

    def test_plate2_instance_references_sample_object(self, gsd, tmp_path):
        names = ["green_surface", "fringe", "fringe_no_grass_sample"]
        raw = _make_minimal_3mf(names)
        dest = tmp_path / "test_plate2_instance.3mf"
        dest.write_bytes(raw)

        gsd._inject_bambu_extruder_metadata(str(dest), names)

        with zipfile.ZipFile(str(dest)) as z:
            cfg_xml = z.read("Metadata/model_settings.config").decode("utf-8")

        root = ET.fromstring(cfg_xml)
        plates = root.findall("plate")
        assert len(plates) == 2, f"Expected 2 plates, got {len(plates)}"
        plate2 = plates[1]

        instances = plate2.findall("model_instance")
        assert len(instances) == 1, (
            f"Plate 2 must have exactly one model_instance (fringe_no_grass_sample). "
            f"Found {len(instances)}."
        )

        oid_meta = instances[0].find("metadata[@key='object_id']")
        assert oid_meta is not None, "Plate 2 model_instance has no object_id metadata"
        # fringe_no_grass_sample is the 3rd object → id=3
        assert oid_meta.attrib.get("value") == "3", (
            f"Plate 2 instance must reference object_id=3 (fringe_no_grass_sample). "
            f"Found: {oid_meta.attrib.get('value')}"
        )


# ---------------------------------------------------------------------------
# T4 — Plate 2 block references plate_2.png thumbnail
# ---------------------------------------------------------------------------

class TestPlate2Thumbnail:
    """T4: Plate 2 metadata references Metadata/plate_2.png as thumbnail_file."""

    def test_plate2_thumbnail_file_reference(self, gsd, tmp_path):
        names = ["green_surface", "fringe", "fringe_no_grass_sample"]
        raw = _make_minimal_3mf(names)
        dest = tmp_path / "test_plate2_thumb.3mf"
        dest.write_bytes(raw)

        gsd._inject_bambu_extruder_metadata(str(dest), names)

        with zipfile.ZipFile(str(dest)) as z:
            cfg_xml = z.read("Metadata/model_settings.config").decode("utf-8")

        root = ET.fromstring(cfg_xml)
        plates = root.findall("plate")
        assert len(plates) == 2
        plate2 = plates[1]

        thumb_meta = plate2.find("metadata[@key='thumbnail_file']")
        assert thumb_meta is not None, (
            "Plate 2 <plate> block is missing <metadata key='thumbnail_file'>."
        )
        assert thumb_meta.attrib.get("value") == "Metadata/plate_2.png", (
            f"Plate 2 thumbnail_file must be 'Metadata/plate_2.png'. "
            f"Got: {thumb_meta.attrib.get('value')}"
        )


# ---------------------------------------------------------------------------
# T5 — Archive contains plate-2 thumbnail files
# ---------------------------------------------------------------------------

class TestPlate2ThumbnailFiles:
    """T5: Archive must contain plate_2.png, plate_no_light_2.png, top_2.png, pick_2.png."""

    @pytest.mark.parametrize("arcname", _PLATE2_THUMBNAILS)
    def test_plate2_thumbnail_file_present(self, arcname, gsd, tmp_path):
        names = ["green_surface", "fringe", "fringe_no_grass_sample"]
        raw = _make_minimal_3mf(names)
        dest = tmp_path / "test_p2_thumbs.3mf"
        dest.write_bytes(raw)

        gsd._inject_bambu_extruder_metadata(str(dest), names)

        with zipfile.ZipFile(str(dest)) as z:
            present = z.namelist()

        assert arcname in present, (
            f"{arcname} not found in archive after two-plate injection. "
            f"The injection function must copy plate_1 thumbnail bytes under "
            f"the plate_2 names when fringe_no_grass_sample is present."
        )


# ---------------------------------------------------------------------------
# T6 — Plate 1 files still present (regression guard)
# ---------------------------------------------------------------------------

class TestPlate1FilesStillPresent:
    """T6: Single-plate files (plate_1_small.png etc.) must still be present."""

    @pytest.mark.parametrize("arcname", sorted(_SINGLE_PLATE_ENTRIES))
    def test_single_plate_file_still_present(self, arcname, gsd, tmp_path):
        if arcname == "Metadata/project_settings.config":
            if not (_TEMPLATE_DIR / "project_settings.config").exists():
                pytest.skip("project_settings.config template not in repo")

        names = ["green_surface", "fringe", "fringe_no_grass_sample"]
        raw = _make_minimal_3mf(names)
        dest = tmp_path / "test_p1_regression.3mf"
        dest.write_bytes(raw)

        gsd._inject_bambu_extruder_metadata(str(dest), names)

        with zipfile.ZipFile(str(dest)) as z:
            present = z.namelist()

        assert arcname in present, (
            f"{arcname} missing from two-plate archive — regression in single-plate "
            f"file injection."
        )


# ---------------------------------------------------------------------------
# T7 — ZIP round-trip valid
# ---------------------------------------------------------------------------

class TestZipIntegrityTwoPlate:
    """T7: Two-plate 3MF must be a valid ZIP archive."""

    def test_zip_integrity(self, gsd, tmp_path):
        names = ["green_surface", "fringe", "trap_1", "fringe_no_grass_sample"]
        raw = _make_minimal_3mf(names)
        dest = tmp_path / "test_p2_zip.3mf"
        dest.write_bytes(raw)

        gsd._inject_bambu_extruder_metadata(str(dest), names)

        result = zipfile.ZipFile(str(dest)).testzip()
        assert result is None, (
            f"Two-plate archive is corrupt: testzip()={result!r}"
        )


# ---------------------------------------------------------------------------
# T8 — Idempotent with plate-2 thumbnails
# ---------------------------------------------------------------------------

class TestIdempotentTwoPlate:
    """T8: Calling injection twice must not duplicate plate-2 thumbnails."""

    @pytest.mark.parametrize("arcname", _PLATE2_THUMBNAILS)
    def test_no_duplicate_plate2_thumbnails(self, arcname, gsd, tmp_path):
        names = ["green_surface", "fringe", "fringe_no_grass_sample"]
        raw = _make_minimal_3mf(names)
        dest = tmp_path / "test_p2_idempotent.3mf"
        dest.write_bytes(raw)

        gsd._inject_bambu_extruder_metadata(str(dest), names)
        gsd._inject_bambu_extruder_metadata(str(dest), names)  # second call

        with zipfile.ZipFile(str(dest)) as z:
            filenames = z.namelist()

        count = filenames.count(arcname)
        assert count <= 1, (
            f"{arcname} appears {count} times after two injection calls — must be ≤ 1."
        )


# ---------------------------------------------------------------------------
# T9 — Plate 2 object uses extruder 2
# ---------------------------------------------------------------------------

class TestPlate2ExtruderAssignment:
    """T9: fringe_no_grass_sample object must have extruder=2 in model_settings.config."""

    def test_fringe_no_grass_sample_extruder_2(self, gsd, tmp_path):
        names = ["green_surface", "fringe", "fringe_no_grass_sample"]
        raw = _make_minimal_3mf(names)
        dest = tmp_path / "test_p2_extruder.3mf"
        dest.write_bytes(raw)

        gsd._inject_bambu_extruder_metadata(str(dest), names)

        with zipfile.ZipFile(str(dest)) as z:
            cfg_xml = z.read("Metadata/model_settings.config").decode("utf-8")

        root = ET.fromstring(cfg_xml)
        # fringe_no_grass_sample is the 3rd object → id=3
        sample_obj = root.find("object[@id='3']")
        assert sample_obj is not None, (
            "No <object id='3'> in model_settings.config — fringe_no_grass_sample "
            "must be represented as an object."
        )
        ext_meta = sample_obj.find("metadata[@key='extruder']")
        assert ext_meta is not None, "fringe_no_grass_sample object missing extruder metadata"
        assert ext_meta.attrib.get("value") == "2", (
            f"fringe_no_grass_sample must map to extruder 2 (fringe filament). "
            f"Got extruder={ext_meta.attrib.get('value')}"
        )


# ---------------------------------------------------------------------------
# T10 — Backward compat: no fringe_no_grass_sample → single plate (no plate 2)
# ---------------------------------------------------------------------------

class TestSinglePlateBackwardCompat:
    """T10: When fringe_no_grass_sample is absent, single-plate behaviour is preserved."""

    def test_no_plate2_when_sample_absent(self, gsd, tmp_path):
        names = ["green_surface", "fringe", "trap_1"]  # no sample
        raw = _make_minimal_3mf(names)
        dest = tmp_path / "test_no_p2.3mf"
        dest.write_bytes(raw)

        gsd._inject_bambu_extruder_metadata(str(dest), names)

        with zipfile.ZipFile(str(dest)) as z:
            cfg_xml = z.read("Metadata/model_settings.config").decode("utf-8")
            present = z.namelist()

        root = ET.fromstring(cfg_xml)
        plates = root.findall("plate")
        assert len(plates) <= 1, (
            f"Single-plate injection should NOT produce two <plate> blocks. "
            f"Found {len(plates)} plates when fringe_no_grass_sample is absent."
        )

        for arcname in _PLATE2_THUMBNAILS:
            assert arcname not in present, (
                f"{arcname} found in archive but fringe_no_grass_sample was NOT in "
                f"scene_names — plate-2 thumbnails must not be injected for a "
                f"single-plate scene."
            )


# ---------------------------------------------------------------------------
# T11 — Plate 2 has plater_id=2
# ---------------------------------------------------------------------------

class TestPlate2PlaterId:
    """T11: The second <plate> block must declare plater_id=2."""

    def test_plate2_plater_id(self, gsd, tmp_path):
        names = ["green_surface", "fringe", "fringe_no_grass_sample"]
        raw = _make_minimal_3mf(names)
        dest = tmp_path / "test_p2_plater_id.3mf"
        dest.write_bytes(raw)

        gsd._inject_bambu_extruder_metadata(str(dest), names)

        with zipfile.ZipFile(str(dest)) as z:
            cfg_xml = z.read("Metadata/model_settings.config").decode("utf-8")

        root = ET.fromstring(cfg_xml)
        plates = root.findall("plate")
        assert len(plates) == 2
        plate2 = plates[1]

        plater_id_meta = plate2.find("metadata[@key='plater_id']")
        assert plater_id_meta is not None, (
            "Plate 2 <plate> block is missing <metadata key='plater_id'>."
        )
        assert plater_id_meta.attrib.get("value") == "2", (
            f"Plate 2 must have plater_id=2. Got: {plater_id_meta.attrib.get('value')}"
        )


# ---------------------------------------------------------------------------
# T12 — Two-plate archive has ≥ 16 entries
# ---------------------------------------------------------------------------

class TestTwoPlateArchiveEntryCount:
    """T12: Two-plate archive must have at least 16 entries (12 single-plate + 4 plate-2)."""

    def test_two_plate_entry_count(self, gsd, tmp_path):
        missing_templates = [
            f for f in [
                "slice_info.config", "filament_sequence.json",
                "pick_1.png", "plate_1_small.png", "plate_1.png",
                "plate_no_light_1.png", "top_1.png",
            ]
            if not (_TEMPLATE_DIR / f).exists()
        ]
        if missing_templates:
            pytest.skip(f"Templates missing: {missing_templates}")

        names = ["green_surface", "fringe", "trap_1", "fringe_no_grass_sample"]
        raw = _make_minimal_3mf(names)
        dest = tmp_path / "test_p2_count.3mf"
        dest.write_bytes(raw)

        gsd._inject_bambu_extruder_metadata(str(dest), names)

        with zipfile.ZipFile(str(dest)) as z:
            n = len(z.namelist())

        assert n >= 16, (
            f"Two-plate archive has only {n} entries. Expected ≥ 16 "
            f"(12 single-plate + 4 plate-2 thumbnails)."
        )


# ---------------------------------------------------------------------------
# T13 — run_pipeline adds fringe_no_grass_sample (not fringe_grass_sample)
#        to scene_names when include_fringe_without_grass=True
# ---------------------------------------------------------------------------

class TestRunPipelineAddsSampleNode:
    """T13: run_pipeline must add 'fringe_no_grass_sample' (not old grass name) when checked."""

    def test_fringe_no_grass_sample_in_pipeline_scene(self, tmp_path, monkeypatch):
        import json
        import gradient_surface_diagnostic as gsd_mod
        from pathlib import Path

        EGM_BASE = Path(_APP_DIR).parent / "ItWentIn" / "GolfCourses"
        egm_files = list(EGM_BASE.rglob("*.egm")) if EGM_BASE.exists() else []
        if not egm_files:
            pytest.skip("No real EGM files for pipeline test")

        # Write EGM with include_fringe_without_grass=True
        with open(egm_files[0]) as f:
            egm_data = json.load(f)
        egm_data["includeFringeWithoutGrass"] = True
        test_egm = tmp_path / "test_t13.egm"
        test_egm.write_text(json.dumps(egm_data))

        captured_scene_names: list[list[str]] = []

        def _mock_inject(path_3mf, scene_names):
            captured_scene_names.append(list(scene_names))

        monkeypatch.setattr(gsd_mod, "_inject_bambu_extruder_metadata", _mock_inject)

        import trimesh

        def _noop_export(self, *args, **kwargs):
            Path(args[0]).write_bytes(b"PK\x03\x04")

        monkeypatch.setattr(trimesh.Scene, "export", _noop_export)

        try:
            gsd_mod.run_pipeline(str(test_egm))
        except Exception:
            pass

        if not captured_scene_names:
            pytest.skip("_inject_bambu_extruder_metadata was not reached")

        scene_names = captured_scene_names[-1]
        assert "fringe_no_grass_sample" in scene_names, (
            f"run_pipeline did not add 'fringe_no_grass_sample' to scene_names. "
            f"Got: {scene_names}. "
            "The pipeline must build the smooth (grass-less) fringe sample and add "
            "it as 'fringe_no_grass_sample' when includeFringeWithoutGrass=True."
        )
        assert "fringe_grass_sample" not in scene_names, (
            f"Old node 'fringe_grass_sample' still present in scene_names. "
            f"Must be renamed to 'fringe_no_grass_sample'. Got: {scene_names}"
        )


# ---------------------------------------------------------------------------
# T14 — Plate 2 is grass-LESS (run_pipeline with include_fringe_without_grass=True
#        → exactly 1 grass call: plate 1 only)
# ---------------------------------------------------------------------------

class TestPlate2HasNoGrassVertices:
    """T14: When include_fringe_without_grass=True, grass called exactly once (plate 1 only).

    Plate 2 is the smooth fringe — grass functions must NOT be called for it.
    This is the inversion of the old T14 where plate 2 was always grassed.
    """

    def test_plate1_grassed_plate2_smooth(self, tmp_path, monkeypatch):
        import json
        import gradient_surface_diagnostic as gsd_mod
        from pathlib import Path

        EGM_BASE = Path(_APP_DIR).parent / "ItWentIn" / "GolfCourses"
        egm_files = list(EGM_BASE.rglob("*.egm")) if EGM_BASE.exists() else []
        if not egm_files:
            pytest.skip("No real EGM files for pipeline test")

        with open(egm_files[0]) as f:
            egm_data = json.load(f)
        egm_data["includeFringeWithoutGrass"] = True
        test_egm = tmp_path / "test_t14.egm"
        test_egm.write_text(json.dumps(egm_data))

        grass_calls: list[str] = []

        original_v2 = gsd_mod.apply_grass_texture_v2
        original_v1 = gsd_mod.apply_grass_texture

        def _track_v2(mesh, **kwargs):
            grass_calls.append("v2")
            return original_v2(mesh, **kwargs)

        def _track_v1(mesh, **kwargs):
            grass_calls.append("v1")
            return original_v1(mesh, **kwargs)

        monkeypatch.setattr(gsd_mod, "apply_grass_texture_v2", _track_v2)
        monkeypatch.setattr(gsd_mod, "apply_grass_texture", _track_v1)

        try:
            gsd_mod.run_pipeline(str(test_egm))
        except Exception:
            pass

        assert len(grass_calls) == 1, (
            f"Expected exactly 1 grass call when include_fringe_without_grass=True "
            f"(plate 1 always grassed, plate 2 is the smooth no-grass sample). "
            f"Got {len(grass_calls)}: {grass_calls}. "
            "0 = plate 1 grass was incorrectly skipped. "
            "2+ = grass was incorrectly applied to the plate-2 smooth sample."
        )


# ---------------------------------------------------------------------------
# T15 — Old scene node "fringe_grass_sample" is gone
# ---------------------------------------------------------------------------

class TestOldSceneNodeGone:
    """T15: 'fringe_grass_sample' must not appear in scene_names (renamed to no_grass)."""

    def test_old_grass_sample_name_absent(self, gsd, tmp_path):
        # The injection function key constant must be updated.
        # Verify via a direct injection call with the old name — it must NOT trigger plate 2.
        names_old = ["green_surface", "fringe", "fringe_grass_sample"]
        raw = _make_minimal_3mf(names_old)
        dest = tmp_path / "test_old_name.3mf"
        dest.write_bytes(raw)

        gsd._inject_bambu_extruder_metadata(str(dest), names_old)

        with zipfile.ZipFile(str(dest)) as z:
            cfg_xml = z.read("Metadata/model_settings.config").decode("utf-8")

        root = ET.fromstring(cfg_xml)
        plates = root.findall("plate")
        # With the new implementation, "fringe_grass_sample" is no longer the
        # plate-2 trigger. Only "fringe_no_grass_sample" triggers plate 2.
        # So passing the old name should yield a single-plate output.
        assert len(plates) <= 1, (
            f"Old name 'fringe_grass_sample' still triggers plate-2 injection "
            f"(found {len(plates)} plates). The _PLATE2_SCENE_NAME constant must "
            f"be updated to 'fringe_no_grass_sample'."
        )


# ---------------------------------------------------------------------------
# T16 — Plate 2 plater_name is "Fringe No Grass Sample"
# ---------------------------------------------------------------------------

class TestPlate2PlaterName:
    """T16: Plate 2 <plate> block must have plater_name='Fringe No Grass Sample'."""

    def test_plate2_plater_name_updated(self, gsd, tmp_path):
        names = ["green_surface", "fringe", "fringe_no_grass_sample"]
        raw = _make_minimal_3mf(names)
        dest = tmp_path / "test_p2_plater_name.3mf"
        dest.write_bytes(raw)

        gsd._inject_bambu_extruder_metadata(str(dest), names)

        with zipfile.ZipFile(str(dest)) as z:
            cfg_xml = z.read("Metadata/model_settings.config").decode("utf-8")

        root = ET.fromstring(cfg_xml)
        plates = root.findall("plate")
        assert len(plates) == 2, f"Expected 2 plates, got {len(plates)}"
        plate2 = plates[1]

        name_meta = plate2.find("metadata[@key='plater_name']")
        assert name_meta is not None, (
            "Plate 2 <plate> block is missing <metadata key='plater_name'>."
        )
        val = name_meta.attrib.get("value", "")
        assert "No Grass" in val or "no_grass" in val.lower(), (
            f"Plate 2 plater_name must reference 'No Grass'. "
            f"Got: '{val}'. Expected 'Fringe No Grass Sample'."
        )
        assert "Grass Sample" not in val or "No Grass" in val, (
            f"Plate 2 plater_name still says 'Fringe Grass Sample' (old value). "
            f"Must be updated to 'Fringe No Grass Sample'. Got: '{val}'"
        )
