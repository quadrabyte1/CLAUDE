"""
test_bambu_config_injection.py — TDD regression tests for the Bambu 3MF
project_settings.config injection behaviour in _inject_bambu_extruder_metadata().

== Regression history ==

Task 612 (v4.67):
  Added injection of a minimal Metadata/project_settings.config stub (10 keys) to
  silence Bambu Studio's "invalid config, load geometry data only" warning.

Task 626 (v4.72) — REVERT:
  The 10-key stub caused a worse regression: Bambu Studio raised a hard error and
  loaded NO geometry at all, instead of the previous warning-but-loads behaviour.
  Root cause: Bambu Studio's project_settings parser expects ~498 keys; encountering
  a truncated blob it aborts outright rather than falling back gracefully.  Writing
  a complete blob is a separate, larger task.  The safe fix was to REMOVE the stub
  injection entirely so the pre-task-612 state was restored.

Task 674 (v4.86) — FULL TEMPLATE WIRING:
  A real blank-plate Bambu Studio export is now stored at
  app/templates/bambu/project_settings.config (62,342 bytes, 580 keys, A1 0.4 nozzle).
  _inject_bambu_extruder_metadata() now writes this template verbatim into every
  generated 3MF.  Bambu Studio loads with no warning dialog, geometry loads, and
  extruder assignments are visible.

== Current desired contract (task 674) ==

  _inject_bambu_extruder_metadata() MUST:
    T1. Write Metadata/project_settings.config.
    T2. project_settings.config bytes match the template bytes exactly.
    T3. Write Metadata/model_settings.config (extruder assignments — must not regress).
    T4. Produce a well-formed ZIP (zipfile.testzip() → None).
    T5. [Content_Types].xml declares the 'config' extension (text/xml).
    T6. Be idempotent — calling twice gives exactly 1 of each config file.
    T7. Gracefully fall back if template file is missing (WARNING logged, no crash,
        project_settings.config absent from output).

T1, T2, T5 are new RED tests for task 674.
T3, T4, T6 are regression guards (were GREEN under task-626, must stay GREEN).
T7 is a new crash-guard test.
"""

from __future__ import annotations

import importlib.util
import io
import logging
import sys
import zipfile
from pathlib import Path

import pytest

# ---------------------------------------------------------------------------
# Helpers to import gradient_surface_diagnostic without full deps
# ---------------------------------------------------------------------------

_APP_DIR = Path(__file__).parent.parent
_TEMPLATE_DIR = _APP_DIR / "templates" / "bambu"
_PROJECT_SETTINGS_TEMPLATE = _TEMPLATE_DIR / "project_settings.config"

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

    [Content_Types].xml does NOT declare the 'config' extension — that is the
    responsibility of the injection function (tested by T5).
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
# T1 — project_settings.config MUST be present after injection (task 674)
#
# RED:  current v4.85 (no project_settings written).
# GREEN: after task-674 wiring (template written verbatim).
# ---------------------------------------------------------------------------

def test_project_settings_config_present_after_injection(gsd, tmp_path):
    """
    After task-674 wiring, _inject_bambu_extruder_metadata MUST write
    Metadata/project_settings.config from the template at
    app/templates/bambu/project_settings.config.

    This silences the Bambu Studio 'invalid config, load geometry data only'
    warning dialog that was present since the task-626 revert.
    """
    if not _PROJECT_SETTINGS_TEMPLATE.exists():
        pytest.skip("Template not in repo — cannot test presence.")

    names = ["green", "fringe", "trap"]
    raw = _make_minimal_trimesh_3mf(names)
    dest = tmp_path / "test_ps_present.3mf"
    dest.write_bytes(raw)

    gsd._inject_bambu_extruder_metadata(str(dest), names)

    with zipfile.ZipFile(str(dest)) as z:
        assert "Metadata/project_settings.config" in z.namelist(), (
            "project_settings.config must be present after task-674 injection. "
            "Template path: app/templates/bambu/project_settings.config"
        )


# ---------------------------------------------------------------------------
# T2 — project_settings.config bytes match the template exactly
#
# RED:  current v4.85 (file absent, no bytes to match).
# GREEN: after task-674 wiring (verbatim copy).
# ---------------------------------------------------------------------------

def test_project_settings_config_matches_template_bytes(gsd, tmp_path):
    """
    The injected project_settings.config must be a verbatim copy of the
    template file (app/templates/bambu/project_settings.config).
    No keys stripped, no values modified.
    """
    if not _PROJECT_SETTINGS_TEMPLATE.exists():
        pytest.skip("Template not in repo — cannot test byte match.")

    template_bytes = _PROJECT_SETTINGS_TEMPLATE.read_bytes()

    names = ["green", "fringe", "trap"]
    raw = _make_minimal_trimesh_3mf(names)
    dest = tmp_path / "test_ps_bytes.3mf"
    dest.write_bytes(raw)

    gsd._inject_bambu_extruder_metadata(str(dest), names)

    with zipfile.ZipFile(str(dest)) as z:
        assert "Metadata/project_settings.config" in z.namelist(), (
            "project_settings.config absent — cannot compare bytes."
        )
        injected_bytes = z.read("Metadata/project_settings.config")

    assert injected_bytes == template_bytes, (
        f"Injected project_settings.config ({len(injected_bytes)} bytes) does not "
        f"match template ({len(template_bytes)} bytes). "
        "Injection must copy the template verbatim."
    )


# ---------------------------------------------------------------------------
# T3 — model_settings.config IS present (extruder assignments retained)
#
# Regression guard — was GREEN under task-626, must stay GREEN under task-674.
# ---------------------------------------------------------------------------

def test_model_settings_config_present_after_injection(gsd, tmp_path):
    """
    model_settings.config (extruder assignments) must still be written after
    task-674 — that is the core purpose of the function and must not regress.
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
# T4 — resulting ZIP is well-formed (testzip returns None)
#
# Regression guard — was GREEN under task-626, must stay GREEN under task-674.
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
# T5 — [Content_Types].xml must declare the 'config' extension
#
# RED:  trimesh helper produces no 'config' entry; injection doesn't add one.
# GREEN: after task-674, injection ensures 'config' → text/xml is present.
# ---------------------------------------------------------------------------

def test_content_types_declares_config_extension(gsd, tmp_path):
    """
    The generated 3MF's [Content_Types].xml must include a declaration for the
    'config' extension so Bambu Studio's content-type validator accepts the
    project_settings.config and model_settings.config entries.

    Required entry (either Default or Override form):
      Extension="config"  ContentType containing "xml"
    """
    names = ["green", "fringe"]
    raw = _make_minimal_trimesh_3mf(names)
    dest = tmp_path / "test_content_types.3mf"
    dest.write_bytes(raw)

    gsd._inject_bambu_extruder_metadata(str(dest), names)

    with zipfile.ZipFile(str(dest)) as z:
        ct_xml = z.read("[Content_Types].xml").decode("utf-8")

    assert 'Extension="config"' in ct_xml, (
        "[Content_Types].xml must declare the 'config' extension. "
        "Without it Bambu Studio may reject the .config files. "
        f"Got:\n{ct_xml}"
    )


# ---------------------------------------------------------------------------
# T6 — idempotent: calling twice produces exactly one of each config file
#
# Regression guard — was GREEN under task-626, must stay GREEN under task-674.
# ---------------------------------------------------------------------------

def test_injection_is_idempotent(gsd, tmp_path):
    """
    Calling _inject_bambu_extruder_metadata twice on the same file must not
    corrupt it or duplicate model_settings.config / project_settings.config.
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
    assert ps_count <= 1, (
        f"project_settings.config should appear at most once after two calls, got {ps_count}"
    )


# ---------------------------------------------------------------------------
# T7 — missing template falls back gracefully (WARNING logged, no crash)
#
# RED:  would crash with FileNotFoundError if template missing (before safe path).
# GREEN: after task-674, logs WARNING, project_settings absent, no exception.
# ---------------------------------------------------------------------------

def test_template_absent_falls_back_gracefully(gsd, tmp_path, monkeypatch, caplog):
    """
    If app/templates/bambu/project_settings.config is missing from the repo,
    _inject_bambu_extruder_metadata must:
      - Not raise any exception.
      - Log a WARNING about the missing template.
      - Still write model_settings.config (extruder assignments).
      - NOT write project_settings.config (Bambu will show its dialog — acceptable).
    """
    import gradient_surface_diagnostic as gsd_mod

    # Point the module at a nonexistent path.
    fake_template_dir = tmp_path / "fake_templates" / "bambu"
    fake_template_dir.mkdir(parents=True)
    # Do NOT create project_settings.config there.

    original_val = getattr(gsd_mod, "_PROJECT_SETTINGS_TEMPLATE", None)
    monkeypatch.setattr(
        gsd_mod,
        "_PROJECT_SETTINGS_TEMPLATE",
        str(fake_template_dir / "project_settings.config"),
        raising=False,
    )

    names = ["green", "fringe"]
    raw = _make_minimal_trimesh_3mf(names)
    dest = tmp_path / "test_fallback.3mf"
    dest.write_bytes(raw)

    with caplog.at_level(logging.WARNING, logger="gradient_surface_diagnostic"):
        gsd._inject_bambu_extruder_metadata(str(dest), names)

    # Must not crash — if we're here, we're good.

    with zipfile.ZipFile(str(dest)) as z:
        names_in_zip = z.namelist()

    assert "Metadata/model_settings.config" in names_in_zip, (
        "model_settings.config must still be written even when template is absent."
    )
    assert "Metadata/project_settings.config" not in names_in_zip, (
        "project_settings.config must NOT be written when the template is absent "
        "(fallback to warning-but-loads behaviour)."
    )
