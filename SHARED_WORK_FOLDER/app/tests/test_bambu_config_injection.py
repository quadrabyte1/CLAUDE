"""
test_bambu_config_injection.py — TDD regression tests for the Bambu 3MF
project_settings.config injection behaviour in _inject_bambu_extruder_metadata().

== Regression history ==

Task 612 (v4.67):
  Added injection of a minimal Metadata/project_settings.config stub (10 keys) to
  silence Bambu Studio's "invalid config, load geometry data only" warning.

Task 626 (v4.72) — THIS REVERT:
  The 10-key stub caused a worse regression: Bambu Studio raised a hard error and
  loaded NO geometry at all, instead of the previous warning-but-loads behaviour.
  Root cause: Bambu Studio's project_settings parser expects ~498 keys; encountering
  a truncated blob it aborts outright rather than falling back gracefully.  Writing
  a complete blob is a separate, larger task.  The safe fix is to REMOVE the stub
  injection entirely so the pre-task-612 state is restored:
    • No project_settings.config in the output 3MF.
    • Bambu Studio shows the "invalid config" warning dialog but geometry loads.
    • model_settings.config (extruder assignments) is still present.

== Current desired contract ==

  _inject_bambu_extruder_metadata() MUST:
    1. Write Metadata/model_settings.config.
    2. NOT write Metadata/project_settings.config (reverted).
    3. Produce a well-formed ZIP (zipfile.testzip() → None).
    4. Be idempotent (calling twice gives exactly one model_settings.config).

Tests run RED with the task-612 code still in place (project_settings IS present).
Tests run GREEN after the task-626 revert removes the injection.
"""

from __future__ import annotations

import importlib.util
import io
import sys
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
    suitable for passing to _inject_bambu_extruder_metadata().
    """
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
# Fixture
# ---------------------------------------------------------------------------


@pytest.fixture(scope="module")
def gsd():
    """Return the gradient_surface_diagnostic module (skip if unimportable)."""
    try:
        return _load_gsd_module()
    except Exception as exc:
        pytest.skip(f"gradient_surface_diagnostic unavailable: {exc}")


# ---------------------------------------------------------------------------
# Test R1 — project_settings.config must NOT be present after injection
#
# RED with task-612 code (file IS present).
# GREEN after task-626 revert (file is absent — safe fallback to Bambu warning).
# ---------------------------------------------------------------------------

def test_project_settings_config_absent_after_injection(gsd, tmp_path):
    """
    After the task-626 revert, _inject_bambu_extruder_metadata must NOT write
    Metadata/project_settings.config.

    Rationale: a minimal 10-key stub caused Bambu Studio to abort loading
    entirely (hard error, no geometry) instead of the previous warning-but-loads
    state.  Omitting the file restores the pre-task-612 behaviour: Bambu shows
    the 'invalid config' warning dialog but still loads geometry.  A complete
    ~498-key project_settings blob is a future task.
    """
    names = ["green", "fringe", "trap"]
    raw = _make_minimal_trimesh_3mf(names)
    dest = tmp_path / "test_no_project_settings.3mf"
    dest.write_bytes(raw)

    gsd._inject_bambu_extruder_metadata(str(dest), names)

    with zipfile.ZipFile(str(dest)) as z:
        assert "Metadata/project_settings.config" not in z.namelist(), (
            "project_settings.config must NOT be injected after the task-626 revert. "
            "A minimal stub causes Bambu Studio to abort loading entirely. "
            "Omit the file so Bambu shows its warning but still loads geometry."
        )


# ---------------------------------------------------------------------------
# Test R2 — model_settings.config IS present (extruder assignments retained)
# ---------------------------------------------------------------------------

def test_model_settings_config_present_after_injection(gsd, tmp_path):
    """
    model_settings.config (extruder assignments) must still be written after
    the revert — that was the original intent of the function and must not
    regress.
    """
    names = ["green", "fringe", "trap"]
    raw = _make_minimal_trimesh_3mf(names)
    dest = tmp_path / "test_model_settings.3mf"
    dest.write_bytes(raw)

    gsd._inject_bambu_extruder_metadata(str(dest), names)

    with zipfile.ZipFile(str(dest)) as z:
        assert "Metadata/model_settings.config" in z.namelist(), (
            "model_settings.config must be present after injection; "
            "this is the core purpose of _inject_bambu_extruder_metadata."
        )


# ---------------------------------------------------------------------------
# Test R3 — resulting ZIP is well-formed (testzip returns None)
# ---------------------------------------------------------------------------

def test_output_zip_is_wellformed(gsd, tmp_path):
    """
    The 3MF produced by _inject_bambu_extruder_metadata must be a valid ZIP
    archive — zipfile.ZipFile.testzip() returns None on success.
    """
    names = ["green", "fringe"]
    raw = _make_minimal_trimesh_3mf(names)
    dest = tmp_path / "test_zipvalid.3mf"
    dest.write_bytes(raw)

    gsd._inject_bambu_extruder_metadata(str(dest), names)

    result = zipfile.ZipFile(str(dest)).testzip()
    assert result is None, (
        f"3MF archive is corrupt after injection: testzip() reported bad entry {result!r}"
    )


# ---------------------------------------------------------------------------
# Test R4 — idempotent: calling twice produces exactly one model_settings.config
# ---------------------------------------------------------------------------

def test_injection_is_idempotent(gsd, tmp_path):
    """
    Calling _inject_bambu_extruder_metadata twice on the same file must not
    corrupt it or duplicate model_settings.config entries.
    """
    names = ["green", "fringe"]
    raw = _make_minimal_trimesh_3mf(names)
    dest = tmp_path / "test_idempotent.3mf"
    dest.write_bytes(raw)

    gsd._inject_bambu_extruder_metadata(str(dest), names)
    gsd._inject_bambu_extruder_metadata(str(dest), names)  # second call

    with zipfile.ZipFile(str(dest)) as z:
        filenames = z.namelist()
        ms_count = filenames.count("Metadata/model_settings.config")
        ps_count = filenames.count("Metadata/project_settings.config")

    assert ms_count == 1, (
        f"model_settings.config should appear exactly once after two calls, got {ms_count}"
    )
    assert ps_count == 0, (
        f"project_settings.config should not appear after the task-626 revert, got {ps_count}"
    )
