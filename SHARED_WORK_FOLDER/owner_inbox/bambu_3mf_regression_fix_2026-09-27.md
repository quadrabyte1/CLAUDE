# Bambu 3MF Regression Fix — v1.0
**2026-09-27 · Finn (3D Print & Slicer Specialist) · Task 626**

---

## Root cause

Task 612 (v4.67) injected a 10-key `Metadata/project_settings.config` JSON stub into every generated 3MF to silence Bambu Studio's "invalid config, load geometry data only" warning.

**The assumption was wrong.** Bambu Studio's `project_settings.config` parser expects approximately 498 keys — a complete slicer profile dump. When it encounters a 10-key blob, it does not fall back gracefully; it aborts the entire file load and displays a hard error with no geometry. That is strictly worse than the original warning state.

Comparison:

| File | Keys | Bambu result |
|---|---|---|
| Real Bambu Studio export | ~498 | Clean load |
| Task-612 stub (broken) | 10 | **Hard abort — nothing loads** |
| No file (pre-612 / reverted) | — | Warning dialog, geometry loads |

The `[Content_Types].xml` was not the problem — real Bambu 3MFs also do not register `.config` as a content type.

---

## Option chosen: C — Revert

Removed the `project_settings.config` injection entirely. The `_inject_bambu_extruder_metadata()` function now writes only `Metadata/model_settings.config` (extruder assignments), as it did before task 612.

**Rationale:** Reliability > speed. Thomas needs to be able to open files. A warning dialog is a known-acceptable state; a hard abort that loads no geometry is not.

Writing a complete, version-matched ~498-key `project_settings.config` is the proper fix for eliminating the warning, but it requires knowing Thomas's exact Bambu Studio version to match the profile format. That is tracked as **future work** (see below).

---

## Files changed

| File | Change |
|---|---|
| `app/gradient_surface_diagnostic.py` | Removed `project_settings.config` build + write block in `_inject_bambu_extruder_metadata()`. Added explanatory comment. Also strips any stale `project_settings.config` from previously-generated files on re-injection. |
| `app/tests/test_bambu_config_injection.py` | Rewrote test suite — 4 regression tests replacing the 6 task-612 tests. Confirmed RED → GREEN. |
| `app/app.py` | `APP_VERSION` bumped `v4.71` → `v4.72` |

---

## Red → Green table

| Test | Purpose | Result |
|---|---|---|
| `test_project_settings_config_absent_after_injection` | Asserts `project_settings.config` is NOT written (revert contract) | RED → GREEN |
| `test_model_settings_config_present_after_injection` | Extruder assignments still present | GREEN → GREEN |
| `test_output_zip_is_wellformed` | `zipfile.testzip()` returns None | GREEN → GREEN |
| `test_injection_is_idempotent` | Two calls → exactly 1 model_settings, 0 project_settings | RED → GREEN |

Full suite: **197 passed, 0 failures.**

---

## Test-drive for Thomas

1. Open the EGM editor (port 5051).
2. Regenerate any hole — e.g., DeLaveaga Hole 05 or Firefly Hole 14.
3. Open the resulting `.3mf` in Bambu Studio.

**Expected:** Bambu Studio shows its "invalid config, load geometry data only" warning dialog. Click through it. **Geometry loads correctly.** Extruder assignments (multi-color) are visible in the object list.

This is identical to the pre-v4.67 behaviour.

---

## Future work: eliminate the warning properly

To remove the warning dialog permanently, `_inject_bambu_extruder_metadata()` needs to write a complete `project_settings.config` that matches Bambu Studio's current schema (~498 keys). The cleanest source for the base blob is exporting a project from Thomas's installed Bambu Studio version, stripping the sliced G-code metadata, and using that as the template. This is a follow-on task — not urgent given the warning is benign and geometry loads correctly.
