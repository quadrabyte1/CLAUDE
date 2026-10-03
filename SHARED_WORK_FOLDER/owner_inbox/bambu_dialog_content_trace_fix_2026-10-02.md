# Bambu Dialog: Content-Level Trace & Fix
**v1.0** · Finn · 2026-10-02

---

## The 4 Failing Test Outputs (verbatim)

```
FAILED tests/test_bambu_config_injection.py::test_all_12_archive_entries_present
  AssertionError: Generated 3MF is missing 7 expected archive entries:
    - Metadata/filament_sequence.json
    - Metadata/pick_1.png
    - Metadata/plate_1.png
    - Metadata/plate_1_small.png
    - Metadata/plate_no_light_1.png
    - Metadata/slice_info.config
    - Metadata/top_1.png

FAILED tests/test_bambu_config_injection.py::test_new_template_files_match_bytes
  AssertionError: These injected files do not match their templates:
    Metadata/slice_info.config: MISSING from archive
    Metadata/filament_sequence.json: MISSING from archive
    Metadata/pick_1.png: MISSING from archive
    Metadata/plate_1_small.png: MISSING from archive
    Metadata/plate_1.png: MISSING from archive
    Metadata/plate_no_light_1.png: MISSING from archive
    Metadata/top_1.png: MISSING from archive

FAILED tests/test_bambu_config_injection.py::test_content_types_declares_png
  AssertionError: [Content_Types].xml must declare Extension="png" after injection.
  Got:
    <?xml version='1.0' encoding='utf-8'?>
    <Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types">
     <Default Extension="model" ContentType="application/vnd.ms-package.3dmanufacturing-3dmodel+xml"/>
     <Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/>
     <Default Extension="config" ContentType="text/xml"/>
    </Types>

FAILED tests/test_bambu_config_injection.py::test_archive_list_superset_of_blank
  AssertionError: Generated 3MF is missing 7 entries that blank.3mf has:
    - Metadata/filament_sequence.json
    - Metadata/pick_1.png
    - Metadata/plate_1.png
    - Metadata/plate_1_small.png
    - Metadata/plate_no_light_1.png
    - Metadata/slice_info.config
    - Metadata/top_1.png
```

---

## Diff Summary (Generated vs blank.3mf)

`blank.3mf` contains 12 entries:

```
[Content_Types].xml
Metadata/plate_1.png
Metadata/plate_1_small.png
Metadata/plate_no_light_1.png
Metadata/top_1.png
Metadata/pick_1.png
3D/3dmodel.model
Metadata/project_settings.config
Metadata/model_settings.config
Metadata/slice_info.config
Metadata/filament_sequence.json
_rels/.rels
```

Before the fix, `_inject_bambu_extruder_metadata` only produced **5 entries**:
- `[Content_Types].xml` (patched, but missing `png`/`gcode` extensions)
- `3D/3dmodel.model` (geometry, correct)
- `_rels/.rels` (from trimesh, carried through)
- `Metadata/model_settings.config` (injected, correct)
- `Metadata/project_settings.config` (injected, correct)

**7 entries missing** from every generated 3MF:
- `Metadata/slice_info.config` — Bambu client-version metadata
- `Metadata/filament_sequence.json` — filament sequence data
- `Metadata/plate_1.png` — thumbnail
- `Metadata/plate_1_small.png` — small thumbnail
- `Metadata/plate_no_light_1.png` — unlit thumbnail
- `Metadata/top_1.png` — top-view thumbnail
- `Metadata/pick_1.png` — pick thumbnail

Additionally, `[Content_Types].xml` was missing `Extension="png"` and `Extension="gcode"`.

All 7 missing files were already present as templates in `app/templates/bambu/` — they were never wired into the injection loop.

---

## Root Cause (Empirical)

Task-677 correctly identified that the 7 files were needed and created the template files in `app/templates/bambu/`. **But it never added the code to inject them.** The implementation in `_inject_bambu_extruder_metadata` had a `_SKIP_FILES` set of only 3 entries (`model_settings.config`, `project_settings.config`, `[Content_Types].xml`) and only wrote those 3 back. The 7 new templates sat in the directory, loaded by nothing.

Secondary: `[Content_Types].xml` was built by patching the trimesh-generated input XML (which only had `rels` and `model`), adding just `config`. The `content_types.xml` template in `app/templates/bambu/` already has the correct 4-extension set (`rels`, `model`, `png`, `gcode`) — matching `blank.3mf` byte-for-byte — but was never used.

---

## Fix Diff

**File: `app/gradient_surface_diagnostic.py`** — in `_inject_bambu_extruder_metadata()`:

1. Added a `_NEW_TMPL_FILES` dict mapping the 7 archive paths to their template filenames.
2. Loaded all 7 from `app/templates/bambu/` with graceful per-file WARNING fallback (same pattern as `project_settings.config`).
3. Extended `_SKIP_FILES` to include all 7 new arcnames so their inputs (absent in trimesh output anyway) are not accidentally copied.
4. `[Content_Types].xml` now starts from the `content_types.xml` template (which has `png` + `gcode`), then still patches in `config` extension (blank.3mf omits it but Bambu Studio requires it for `.config` files from non-Studio sources).
5. Added a write loop for the 7 new template files after the existing `project_settings.config` write.

**File: `app/app.py`**: `APP_VERSION` bumped `v4.96` → `v4.97`.

---

## Red → Green

| Test | Before | After |
|------|--------|-------|
| `test_all_12_archive_entries_present` | FAIL | PASS |
| `test_new_template_files_match_bytes` | FAIL | PASS |
| `test_content_types_declares_png` | FAIL | PASS |
| `test_archive_list_superset_of_blank` | FAIL | PASS |
| All other 10 tests | PASS | PASS |
| **Total** | **10/14** | **14/14** |

---

## Test Drive for Thomas

1. Reload the web server (port 5051) — it will show `v4.97` in the footer.
2. Generate any hole (e.g. Delaveaga Hole 5) through the normal UI flow.
3. Open the downloaded `.3mf` in Bambu Studio.
4. **Expected: no "invalid config" dialog. Geometry loads directly with extruder assignments visible.**

If the dialog still fires:
- Please capture your exact **Bambu Studio version** from Help → About (the build string, e.g. `02.08.02.61`).
- The template at `app/templates/bambu/project_settings.config` was exported from Bambu Studio `02.08.02.61` (the `X-BBL-Client-Version` in `slice_info.config` confirms this). If your Bambu Studio is a different version, the validator may enforce schema changes we haven't seen yet.
- The blank.3mf in `team_inbox/` was also made with `02.08.02.61` — if you re-export a blank plate from your current version, Nolan/Finn can re-template from it.

---

## Bambu Studio Version Reference

The template files (`project_settings.config`, `slice_info.config`, `blank.3mf`) were all generated from **Bambu Studio `02.08.02.61`** (confirmed from `slice_info.config` header key `X-BBL-Client-Version`). If Bambu Studio auto-updated since `team_inbox/blank.3mf` was created, the validator may have added new required fields. Re-exporting a blank plate from the current version and replacing the templates is the path forward if the dialog persists after this fix.
