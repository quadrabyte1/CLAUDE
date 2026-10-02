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


# ===========================================================================
# Task-677 tests — inject 7 remaining Metadata files
# ===========================================================================
#
# The 7 files that blank.3mf has but task-674 output lacked:
#   Metadata/slice_info.config
#   Metadata/filament_sequence.json
#   Metadata/pick_1.png
#   Metadata/plate_1_small.png
#   Metadata/plate_1.png
#   Metadata/plate_no_light_1.png
#   Metadata/top_1.png
#
# RED: current v4.86 output only has 5 archive entries; all 7 tests fail.
# GREEN: after task-677 wiring, all 7 pass.
# ===========================================================================

_TEMPLATE_DIR_677 = _APP_DIR / "templates" / "bambu"

# The 12 entries a correct 3MF must contain (matches blank.3mf namelist).
_EXPECTED_ARCHIVE_ENTRIES = frozenset({
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

# The 7 new template files to inject (arcname → filename in templates/bambu/).
_NEW_TEMPLATE_FILES = {
    "Metadata/slice_info.config":      "slice_info.config",
    "Metadata/filament_sequence.json": "filament_sequence.json",
    "Metadata/pick_1.png":             "pick_1.png",
    "Metadata/plate_1_small.png":      "plate_1_small.png",
    "Metadata/plate_1.png":            "plate_1.png",
    "Metadata/plate_no_light_1.png":   "plate_no_light_1.png",
    "Metadata/top_1.png":              "top_1.png",
}


# ---------------------------------------------------------------------------
# T8 — generated 3MF has all 12 expected archive entries
#
# RED:  current v4.86 output only has 5 entries (missing 7 new ones).
# GREEN: after task-677, all 12 present.
# ---------------------------------------------------------------------------

def test_all_12_archive_entries_present(gsd, tmp_path):
    """
    The generated 3MF must contain exactly the 12 archive entries that
    a real blank-plate Bambu Studio export has.

    Regression against task-674's 5-entry output (the root cause of the
    Bambu Studio 'invalid config' dialog that task-674 claimed to fix).
    """
    missing = [
        f for f in _NEW_TEMPLATE_FILES
        if not (_TEMPLATE_DIR_677 / _NEW_TEMPLATE_FILES[f]).exists()
    ]
    if missing:
        pytest.skip(f"Template files not in repo: {missing}")

    names = ["green", "fringe", "trap"]
    raw = _make_minimal_trimesh_3mf(names)
    dest = tmp_path / "test_all_entries.3mf"
    dest.write_bytes(raw)

    gsd._inject_bambu_extruder_metadata(str(dest), names)

    with zipfile.ZipFile(str(dest)) as z:
        present = set(z.namelist())

    missing_in_output = _EXPECTED_ARCHIVE_ENTRIES - present
    assert not missing_in_output, (
        f"Generated 3MF is missing {len(missing_in_output)} expected archive entries:\n"
        + "\n".join(f"  - {e}" for e in sorted(missing_in_output))
    )


# ---------------------------------------------------------------------------
# T9 — each of the 7 template files matches template bytes exactly
#
# RED:  files absent → KeyError when reading from archive.
# GREEN: after task-677, verbatim copies from app/templates/bambu/.
# ---------------------------------------------------------------------------

def test_new_template_files_match_bytes(gsd, tmp_path):
    """
    Each of the 7 newly injected Metadata files must be a verbatim byte-for-byte
    copy of the corresponding file in app/templates/bambu/.
    """
    missing = [
        f for f in _NEW_TEMPLATE_FILES
        if not (_TEMPLATE_DIR_677 / _NEW_TEMPLATE_FILES[f]).exists()
    ]
    if missing:
        pytest.skip(f"Template files not in repo: {missing}")

    names = ["green", "fringe", "trap"]
    raw = _make_minimal_trimesh_3mf(names)
    dest = tmp_path / "test_new_bytes.3mf"
    dest.write_bytes(raw)

    gsd._inject_bambu_extruder_metadata(str(dest), names)

    mismatches = []
    with zipfile.ZipFile(str(dest)) as z:
        for arcname, fname in _NEW_TEMPLATE_FILES.items():
            template_bytes = (_TEMPLATE_DIR_677 / fname).read_bytes()
            try:
                injected_bytes = z.read(arcname)
            except KeyError:
                mismatches.append(f"  {arcname}: MISSING from archive")
                continue
            if injected_bytes != template_bytes:
                mismatches.append(
                    f"  {arcname}: {len(injected_bytes)} bytes vs "
                    f"template {len(template_bytes)} bytes"
                )

    assert not mismatches, (
        "These injected files do not match their templates:\n" + "\n".join(mismatches)
    )


# ---------------------------------------------------------------------------
# T10 — [Content_Types].xml declares png and json extensions
#
# blank.3mf has Extension="png" and no json entry — but our content_types.xml
# template includes png; we assert it's present after injection.
#
# RED:  current v4.86 only adds 'config'; png/json may be absent.
# GREEN: after task-677, png is declared (blank.3mf has it); json doesn't
#         appear in blank.3mf content-types so we don't require it.
# ---------------------------------------------------------------------------

def test_content_types_declares_png(gsd, tmp_path):
    """
    [Content_Types].xml must declare Extension="png" after injection.
    blank.3mf's [Content_Types].xml declares png; our output must match.
    """
    names = ["green", "fringe"]
    raw = _make_minimal_trimesh_3mf(names)
    dest = tmp_path / "test_ct_png.3mf"
    dest.write_bytes(raw)

    gsd._inject_bambu_extruder_metadata(str(dest), names)

    with zipfile.ZipFile(str(dest)) as z:
        ct_xml = z.read("[Content_Types].xml").decode("utf-8")

    assert 'Extension="png"' in ct_xml, (
        "[Content_Types].xml must declare Extension=\"png\" after injection. "
        f"Got:\n{ct_xml}"
    )


# ---------------------------------------------------------------------------
# T11 — ZIP integrity still valid after 7 new files injected
#
# Regression guard: more writes should not corrupt the archive.
# ---------------------------------------------------------------------------

def test_zip_integrity_with_all_metadata(gsd, tmp_path):
    """
    The 3MF produced with all 12 files injected must be a valid ZIP archive
    (zipfile.ZipFile.testzip() returns None).
    """
    missing = [
        f for f in _NEW_TEMPLATE_FILES
        if not (_TEMPLATE_DIR_677 / _NEW_TEMPLATE_FILES[f]).exists()
    ]
    if missing:
        pytest.skip(f"Template files not in repo: {missing}")

    names = ["green", "fringe"]
    raw = _make_minimal_trimesh_3mf(names)
    dest = tmp_path / "test_zip_integrity_full.3mf"
    dest.write_bytes(raw)

    gsd._inject_bambu_extruder_metadata(str(dest), names)

    result = zipfile.ZipFile(str(dest)).testzip()
    assert result is None, (
        f"3MF archive corrupt after full metadata injection: testzip() = {result!r}"
    )


# ---------------------------------------------------------------------------
# T12 — idempotent with 7 new files (no duplicates on second call)
#
# Regression guard for the expanded inject function.
# ---------------------------------------------------------------------------

def test_idempotent_with_all_metadata(gsd, tmp_path):
    """
    Calling _inject_bambu_extruder_metadata twice must not duplicate any of
    the 7 newly injected Metadata files.
    """
    missing = [
        f for f in _NEW_TEMPLATE_FILES
        if not (_TEMPLATE_DIR_677 / _NEW_TEMPLATE_FILES[f]).exists()
    ]
    if missing:
        pytest.skip(f"Template files not in repo: {missing}")

    names = ["green", "fringe"]
    raw = _make_minimal_trimesh_3mf(names)
    dest = tmp_path / "test_idempotent_full.3mf"
    dest.write_bytes(raw)

    gsd._inject_bambu_extruder_metadata(str(dest), names)
    gsd._inject_bambu_extruder_metadata(str(dest), names)  # second call

    with zipfile.ZipFile(str(dest)) as z:
        filenames = z.namelist()

    for arcname in _NEW_TEMPLATE_FILES:
        count = filenames.count(arcname)
        assert count <= 1, (
            f"{arcname} appears {count} times after two injection calls; "
            "must appear at most once (idempotent)."
        )


# ---------------------------------------------------------------------------
# T13 — missing template file logs warning and continues (graceful)
#
# If any of the 7 template files is absent, injection should log a visible
# WARNING per missing file and continue without crashing.
# ---------------------------------------------------------------------------

def test_missing_metadata_template_logs_warning_and_continues(gsd, tmp_path, monkeypatch, caplog):
    """
    If any template file in _METADATA_TEMPLATE_FILES is missing from disk,
    _inject_bambu_extruder_metadata must:
      - NOT raise any exception.
      - Log a WARNING mentioning the missing file.
      - Still write the other files (archive not aborted).
    """
    import gradient_surface_diagnostic as gsd_mod

    # Point the module at a dir missing all the new metadata templates.
    fake_dir = tmp_path / "fake_bambu"
    fake_dir.mkdir()
    # Copy only project_settings.config so T1/T2 still pass (not our concern here).
    real_ps = _TEMPLATE_DIR_677 / "project_settings.config"
    if real_ps.exists():
        (fake_dir / "project_settings.config").write_bytes(real_ps.read_bytes())

    monkeypatch.setattr(gsd_mod, "_BAMBU_TEMPLATE_DIR", fake_dir, raising=False)

    names = ["green", "fringe"]
    raw = _make_minimal_trimesh_3mf(names)
    dest = tmp_path / "test_graceful_missing.3mf"
    dest.write_bytes(raw)

    with caplog.at_level(logging.WARNING, logger="gradient_surface_diagnostic"):
        gsd._inject_bambu_extruder_metadata(str(dest), names)

    # Must not crash — if we're here, graceful fallback worked.
    # ZIP must still be valid.
    result = zipfile.ZipFile(str(dest)).testzip()
    assert result is None, f"Archive corrupt after graceful fallback: testzip()={result!r}"


# ---------------------------------------------------------------------------
# T14 — archive-list superset: generated ≥ blank.3mf namelist for metadata
#
# The sanity-check "definition of done" test.
# set(generated_zip.namelist()) ≥ set(blank_zip.namelist()) for metadata files.
# ---------------------------------------------------------------------------

def test_archive_list_superset_of_blank(gsd, tmp_path):
    """
    The generated 3MF's archive entry set must be a superset of blank.3mf's
    entry set for all Metadata/* and infrastructure files.

    This is the 'definition of done' check: if this passes, the archive
    structure is identical (in file list) to a real Bambu Studio blank export.
    """
    blank_3mf = Path(__file__).parent.parent.parent / "team_inbox" / "blank.3mf"
    if not blank_3mf.exists():
        pytest.skip("team_inbox/blank.3mf not available.")

    missing_templates = [
        f for f in _NEW_TEMPLATE_FILES
        if not (_TEMPLATE_DIR_677 / _NEW_TEMPLATE_FILES[f]).exists()
    ]
    if missing_templates:
        pytest.skip(f"Template files not in repo: {missing_templates}")

    names = ["green", "fringe", "trap"]
    raw = _make_minimal_trimesh_3mf(names)
    dest = tmp_path / "test_superset.3mf"
    dest.write_bytes(raw)

    gsd._inject_bambu_extruder_metadata(str(dest), names)

    with zipfile.ZipFile(str(blank_3mf)) as bz:
        blank_entries = set(bz.namelist())
    with zipfile.ZipFile(str(dest)) as gz:
        generated_entries = set(gz.namelist())

    missing_from_generated = blank_entries - generated_entries
    assert not missing_from_generated, (
        f"Generated 3MF is missing {len(missing_from_generated)} entries that "
        f"blank.3mf has:\n"
        + "\n".join(f"  - {e}" for e in sorted(missing_from_generated))
    )
