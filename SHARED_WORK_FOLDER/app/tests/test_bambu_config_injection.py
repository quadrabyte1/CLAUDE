"""
test_bambu_config_injection.py — TDD tests for Bambu project_settings.config
injection in _inject_bambu_extruder_metadata().

Bug:
  generate_stl_3mf / gradient_surface_diagnostic emit 3MFs via trimesh.Scene.export
  followed by _inject_bambu_extruder_metadata().  The latter writes
  Metadata/model_settings.config but never writes
  Metadata/project_settings.config.  When Bambu Studio opens such a file it
  displays:
      "The 3mf file has invalid config, load geometry data only"
  and falls back to default printer/filament/process settings.

Root cause:
  Bambu Studio expects project_settings.config to be present whenever
  model_settings.config is present.  A file with model_settings.config but no
  project_settings.config triggers the warning unconditionally.

Fix:
  _inject_bambu_extruder_metadata() must also write a minimal but valid
  Metadata/project_settings.config JSON blob so Bambu Studio can parse it
  without error.  The blob must include at minimum:
    - "version"             (non-empty string)
    - "printer_model"       (non-empty string)
    - "printer_settings_id" (non-empty string)
    - "print_settings_id"   (non-empty string)
    - "filament_settings_id" (list with at least one non-empty string)

Tests run RED before the fix, GREEN after.
"""

from __future__ import annotations

import importlib.util
import io
import json
import os
import sys
import tempfile
import zipfile
from pathlib import Path

import pytest

# ---------------------------------------------------------------------------
# Helpers to import gradient_surface_diagnostic without full deps
# ---------------------------------------------------------------------------

_APP_DIR = Path(__file__).parent.parent
if str(_APP_DIR) not in sys.path:
    sys.path.insert(0, str(_APP_DIR))


def _load_gsd_module():
    """Import gradient_surface_diagnostic, skipping if heavy deps are absent."""
    spec = importlib.util.spec_from_file_location(
        "gradient_surface_diagnostic",
        str(_APP_DIR / "gradient_surface_diagnostic.py"),
    )
    mod = importlib.util.module_from_spec(spec)
    sys.modules["gradient_surface_diagnostic"] = mod
    spec.loader.exec_module(mod)
    return mod


def _make_minimal_trimesh_3mf(names: list[str]) -> bytes:
    """
    Produce the smallest valid trimesh-style 3MF: one object per name,
    with model_settings.config written by _inject_bambu_extruder_metadata()
    before the test calls it again (so the zip starts without it).
    """
    # Minimal 3D model with N objects (same tiny box each)
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


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


@pytest.fixture(scope="module")
def gsd():
    """Return the gradient_surface_diagnostic module (skip if unimportable)."""
    try:
        return _load_gsd_module()
    except Exception as exc:
        pytest.skip(f"gradient_surface_diagnostic unavailable: {exc}")


# ---------------------------------------------------------------------------
# Test A — project_settings.config is PRESENT after injection
# ---------------------------------------------------------------------------

def test_project_settings_config_present_after_injection(gsd, tmp_path):
    """
    RED until fix: _inject_bambu_extruder_metadata does not write
    project_settings.config — it will be absent.
    GREEN after fix: the file is present.
    """
    names = ["green", "fringe", "trap"]
    raw = _make_minimal_trimesh_3mf(names)
    dest = tmp_path / "test_output.3mf"
    dest.write_bytes(raw)

    gsd._inject_bambu_extruder_metadata(str(dest), names)

    with zipfile.ZipFile(str(dest)) as z:
        assert "Metadata/project_settings.config" in z.namelist(), (
            "project_settings.config must be present after _inject_bambu_extruder_metadata; "
            "Bambu Studio raises 'invalid config' without it."
        )


# ---------------------------------------------------------------------------
# Test B — project_settings.config is valid JSON with required keys
# ---------------------------------------------------------------------------

_REQUIRED_PROJECT_KEYS = {
    "version",
    "printer_model",
    "printer_settings_id",
    "print_settings_id",
    "filament_settings_id",
}


def test_project_settings_has_required_keys(gsd, tmp_path):
    """
    project_settings.config must contain all keys Bambu Studio checks first.
    """
    names = ["green", "fringe"]
    raw = _make_minimal_trimesh_3mf(names)
    dest = tmp_path / "test_keys.3mf"
    dest.write_bytes(raw)

    gsd._inject_bambu_extruder_metadata(str(dest), names)

    with zipfile.ZipFile(str(dest)) as z:
        data = json.loads(z.read("Metadata/project_settings.config"))

    for key in _REQUIRED_PROJECT_KEYS:
        assert key in data, f"Required key '{key}' missing from project_settings.config"


# ---------------------------------------------------------------------------
# Test C — required fields are non-empty / non-null
# ---------------------------------------------------------------------------

def test_project_settings_values_non_empty(gsd, tmp_path):
    """
    Every required string field must be non-empty; filament_settings_id must
    be a list with at least one non-empty entry.
    """
    names = ["green"]
    raw = _make_minimal_trimesh_3mf(names)
    dest = tmp_path / "test_values.3mf"
    dest.write_bytes(raw)

    gsd._inject_bambu_extruder_metadata(str(dest), names)

    with zipfile.ZipFile(str(dest)) as z:
        data = json.loads(z.read("Metadata/project_settings.config"))

    for key in ("version", "printer_model", "printer_settings_id", "print_settings_id"):
        val = data.get(key, "")
        assert isinstance(val, str) and val.strip(), (
            f"project_settings['{key}'] must be a non-empty string, got {val!r}"
        )

    fid = data.get("filament_settings_id", [])
    assert isinstance(fid, list) and len(fid) >= 1, (
        f"filament_settings_id must be a non-empty list, got {fid!r}"
    )
    assert fid[0].strip(), (
        f"filament_settings_id[0] must be a non-empty string, got {fid[0]!r}"
    )


# ---------------------------------------------------------------------------
# Test D — project_settings.config uses Bambu schemas (not Qidi)
# ---------------------------------------------------------------------------

def test_project_settings_uses_bambu_schema(gsd, tmp_path):
    """
    The injected project_settings.config must target a Bambu Lab printer
    profile, not a Qidi profile.  Bambu Studio will not recognise Qidi IDs.
    """
    names = ["green", "fringe"]
    raw = _make_minimal_trimesh_3mf(names)
    dest = tmp_path / "test_schema.3mf"
    dest.write_bytes(raw)

    gsd._inject_bambu_extruder_metadata(str(dest), names)

    with zipfile.ZipFile(str(dest)) as z:
        data = json.loads(z.read("Metadata/project_settings.config"))

    printer_id = data.get("printer_settings_id", "")
    assert "Bambu" in printer_id or "BBL" in printer_id, (
        f"printer_settings_id should reference a Bambu Lab profile, got {printer_id!r}"
    )


# ---------------------------------------------------------------------------
# Test E — model_settings.config is STILL present (regression guard)
# ---------------------------------------------------------------------------

def test_model_settings_config_still_present(gsd, tmp_path):
    """
    Injecting project_settings.config must not remove model_settings.config.
    """
    names = ["green", "fringe", "trap"]
    raw = _make_minimal_trimesh_3mf(names)
    dest = tmp_path / "test_regression.3mf"
    dest.write_bytes(raw)

    gsd._inject_bambu_extruder_metadata(str(dest), names)

    with zipfile.ZipFile(str(dest)) as z:
        assert "Metadata/model_settings.config" in z.namelist(), (
            "model_settings.config must still be present after fix"
        )


# ---------------------------------------------------------------------------
# Test F — idempotent: calling twice does not corrupt the file
# ---------------------------------------------------------------------------

def test_injection_is_idempotent(gsd, tmp_path):
    """
    Calling _inject_bambu_extruder_metadata twice on the same file must not
    corrupt it or duplicate config entries.
    """
    names = ["green", "fringe"]
    raw = _make_minimal_trimesh_3mf(names)
    dest = tmp_path / "test_idempotent.3mf"
    dest.write_bytes(raw)

    gsd._inject_bambu_extruder_metadata(str(dest), names)
    gsd._inject_bambu_extruder_metadata(str(dest), names)  # second call

    with zipfile.ZipFile(str(dest)) as z:
        filenames = z.namelist()
        ps_count = filenames.count("Metadata/project_settings.config")
        ms_count = filenames.count("Metadata/model_settings.config")

    assert ps_count == 1, f"project_settings.config should appear exactly once, got {ps_count}"
    assert ms_count == 1, f"model_settings.config should appear exactly once, got {ms_count}"
