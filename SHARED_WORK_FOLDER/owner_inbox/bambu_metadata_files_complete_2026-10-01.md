# Bambu Metadata Injection Fix — v4.87
**Task 677 · Finn · 2026-10-01**

---

## What was missing in task 674's output

Task 674 (v4.86) injected `Metadata/project_settings.config` and patched `[Content_Types].xml` to declare the `config` extension. That fixed the primary missing file but the generated archive still only had **5 entries**, while a real Bambu Studio blank-plate export has **12**. The 7 missing files were:

| Missing from generated 3MF | Present in blank.3mf |
|---|---|
| `Metadata/slice_info.config` | yes |
| `Metadata/filament_sequence.json` | yes |
| `Metadata/pick_1.png` | yes |
| `Metadata/plate_1_small.png` | yes |
| `Metadata/plate_1.png` | yes |
| `Metadata/plate_no_light_1.png` | yes |
| `Metadata/top_1.png` | yes |

The unit tests in task 674 only checked file presence + ZIP validity — they didn't compare against `blank.3mf`'s namelist, so the gap went undetected until you loaded it in Bambu Studio.

---

## Full list of files now injected

All 12 archive entries are now present in every generated 3MF:

| Archive path | Source | Notes |
|---|---|---|
| `_rels/.rels` | trimesh output | unchanged |
| `[Content_Types].xml` | patched by injection | config + png + gcode now declared |
| `3D/3dmodel.model` | trimesh output | hole geometry |
| `Metadata/model_settings.config` | generated | per-object extruder assignments |
| `Metadata/project_settings.config` | `app/templates/bambu/project_settings.config` | 62,342 bytes, A1 0.4 nozzle profile |
| `Metadata/slice_info.config` | `app/templates/bambu/slice_info.config` | slicer version header |
| `Metadata/filament_sequence.json` | `app/templates/bambu/filament_sequence.json` | blank plate sequence |
| `Metadata/pick_1.png` | `app/templates/bambu/pick_1.png` | 1,096 bytes blank thumbnail |
| `Metadata/plate_1_small.png` | `app/templates/bambu/plate_1_small.png` | 143 bytes blank thumbnail |
| `Metadata/plate_1.png` | `app/templates/bambu/plate_1.png` | 1,096 bytes blank thumbnail |
| `Metadata/plate_no_light_1.png` | `app/templates/bambu/plate_no_light_1.png` | 1,096 bytes blank thumbnail |
| `Metadata/top_1.png` | `app/templates/bambu/top_1.png` | 1,096 bytes blank thumbnail |

All 7 new template files are verbatim copies from `team_inbox/blank.3mf` (extracted at task-677 time).

---

## [Content_Types].xml diff

**Before (v4.86 output):**
```xml
<?xml version="1.0" encoding="UTF-8"?>
<Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types">
 <Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/>
 <Default Extension="model" ContentType="application/vnd.ms-package.3dmanufacturing-3dmodel+xml"/>
 <Default Extension="config" ContentType="text/xml"/>
</Types>
```

**After (v4.87 output, matches blank.3mf):**
```xml
<?xml version="1.0" encoding="UTF-8"?>
<Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types">
 <Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/>
 <Default Extension="model" ContentType="application/vnd.ms-package.3dmanufacturing-3dmodel+xml"/>
 <Default Extension="config" ContentType="text/xml"/>
 <Default Extension="png" ContentType="image/png"/>
 <Default Extension="gcode" ContentType="text/x.gcode"/>
</Types>
```

The injection function now ensures `config`, `png`, and `gcode` are all declared, matching what `blank.3mf` declares exactly (copied from Thomas's real Bambu Studio export — no invented content types).

---

## Red → Green table

| Test | Description | Status |
|---|---|---|
| T1 | `project_settings.config` present (regression guard, was GREEN) | GREEN |
| T2 | `project_settings.config` bytes match template (regression guard) | GREEN |
| T3 | `model_settings.config` present (regression guard) | GREEN |
| T4 | ZIP integrity — `testzip()` returns None (regression guard) | GREEN |
| T5 | `[Content_Types].xml` declares `config` extension (regression guard) | GREEN |
| T6 | Idempotent — two calls → at most 1 of each config file (regression guard) | GREEN |
| T7 | Missing project_settings template → graceful fallback, WARNING logged | GREEN |
| **T8** | **All 12 expected archive entries present** | **RED → GREEN** |
| **T9** | **Each of the 7 new files matches template bytes exactly** | **RED → GREEN** |
| **T10** | **`[Content_Types].xml` declares `png` extension** | **RED → GREEN** |
| **T11** | **ZIP integrity with all 12 files injected** | **RED → GREEN** |
| **T12** | **Idempotent with all 7 new metadata files** | **RED → GREEN** |
| **T13** | **Missing metadata template → WARNING logged, continues without crash** | **RED → GREEN** |
| **T14** | **Archive-list superset of blank.3mf (definition-of-done check)** | **RED → GREEN** |

Full suite result: **344 passed, 0 failed** (was 337 before this task).

---

## Archive-list comparison: generated vs blank.3mf

```
blank.3mf namelist:
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

generated 3MF namelist (v4.87):
  3D/3dmodel.model           ← hole-specific (content differs, expected)
  _rels/.rels
  Metadata/model_settings.config  ← hole-specific (content differs, expected)
  [Content_Types].xml
  Metadata/project_settings.config
  Metadata/slice_info.config
  Metadata/filament_sequence.json
  Metadata/pick_1.png
  Metadata/plate_1_small.png
  Metadata/plate_1.png
  Metadata/plate_no_light_1.png
  Metadata/top_1.png

Result: sets are equal. T14 passes.
```

---

## Test drive for Thomas

1. Open the EGM web app (port 5051).
2. Select **Firefly H14** (or any hole).
3. Click **Generate 3MF** and download/open in Bambu Studio.
4. Expected: Bambu Studio loads with **no "invalid config" dialog**. Geometry should be visible immediately with correct extruder assignments.

If the dialog still appears: the remaining cause is likely inside `Metadata/project_settings.config` — a printer-model mismatch or a key Bambu's specific version requires. Report back with the exact dialog text and Bambu Studio version, and we'll extract the next layer.

---

## Honest acknowledgment

Unit tests (including T14) verify the archive structure matches `blank.3mf` exactly. **They cannot drive Bambu Studio's GUI validator.** The only definitive test is Thomas loading the file in Bambu Studio. If the dialog still fires after this fix, the root cause is something inside `project_settings.config`'s content (not the archive structure), and we'll need to diff Thomas's real sliced export against our template.

---

## Files changed

- `/Volumes/GIT/CLAUDE/SHARED_WORK_FOLDER/app/gradient_surface_diagnostic.py` — added `_BAMBU_TEMPLATE_DIR`, `_METADATA_TEMPLATE_FILES`, extended `_inject_bambu_extruder_metadata` (steps 3c + updated step 4/7)
- `/Volumes/GIT/CLAUDE/SHARED_WORK_FOLDER/app/app.py` — `APP_VERSION` v4.86 → v4.87
- `/Volumes/GIT/CLAUDE/SHARED_WORK_FOLDER/app/templates/bambu/` — added 6 new template files (filament_sequence.json, pick_1.png, plate_1.png, plate_1_small.png, plate_no_light_1.png, top_1.png); slice_info.config was already present
- `/Volumes/GIT/CLAUDE/SHARED_WORK_FOLDER/app/tests/test_bambu_config_injection.py` — added T8–T14 (7 new tests)
