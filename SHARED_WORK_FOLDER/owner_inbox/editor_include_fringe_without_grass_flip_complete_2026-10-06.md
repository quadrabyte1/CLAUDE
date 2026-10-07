# Include Fringe Without Grass — Geometry Flip Complete

**v1.0** · Sienna · 2026-10-06 · Task 728

---

## 1. Audit: What the Prior Partial Run (Task 724) Landed vs What Remained

| Area | Task 724 state | Remaining for Task 728 |
|------|---------------|----------------------|
| `editor.html` | 9 refs to `includeFringeWithoutGrass`; label reads "Include Fringe Without Grass"; checkbox x-model updated | Done |
| `app.py` | `include_fringe_without_grass` read from request (line 1750) | Line 1802 still passed stale `enable_fringe_grass=enable_fringe_grass` to `run_pipeline()` |
| `app.py` APP_VERSION | v5.12 bumped | Bump to v5.13 |
| `gradient_surface_diagnostic.py` | 0 new refs; 13 stale old refs | Full rework needed |
| Test files | Not touched | Both needed rewrite |

---

## 2. Code Change Summary

### `app/app.py`

- **APP_VERSION**: `v5.12` → `v5.13`
- **Line 1802**: replaced stale `enable_fringe_grass=enable_fringe_grass` kwarg with `include_fringe_without_grass=include_fringe_without_grass` in the `run_pipeline()` call

### `app/gradient_surface_diagnostic.py`

- **File header**: added v0.22 changelog entry; v0.21 entry preserved
- **`run_pipeline` signature**: parameter `enable_fringe_grass: bool | None` → `include_fringe_without_grass: bool | None`
- **`run_pipeline` docstring**: updated to reflect new semantics (controls plate-2 presence, not plate-1 grass)
- **EGM field resolution block**: replaced `enableFringeGrass` → `includeFringeWithoutGrass`; default changed from `True` to `False` (no plate 2 by default)
- **Plate 1 grass**: removed `if enable_fringe_grass:` guard entirely — grass is now unconditional on the main fringe
- **Plate 2 build**: wrapped in `if include_fringe_without_grass:` condition; removed all `apply_grass_texture*` calls from the sample build (smooth sample only)
- **Sample variable**: `fringe_grass_sample` → `fringe_no_grass_sample`
- **Scene assembly**: `scene.add_geometry(..., node_name="fringe_no_grass_sample")` + `scene_names.append("fringe_no_grass_sample")`

### `app/gradient_surface_diagnostic.py` — Scene-Node and Plater_Name Renames

| Location | Old value | New value |
|----------|-----------|-----------|
| `_PLATE2_SCENE_NAME` constant | `"fringe_grass_sample"` | `"fringe_no_grass_sample"` |
| `<metadata key="plater_name">` | `"Fringe Grass Sample"` | `"Fringe No Grass Sample"` |
| Sample variable name | `fringe_grass_sample` | `fringe_no_grass_sample` |
| Scene node name passed to `add_geometry` | `"fringe_grass_sample"` | `"fringe_no_grass_sample"` |
| Thumbnail injection comment | `fringe_grass_sample` | `fringe_no_grass_sample` |
| Two-plate comment block | references old name | references new name |

The `_filament_for_scene_name` function is unchanged — it routes any name starting with `"fringe"` to extruder 2, so `fringe_no_grass_sample` inherits the correct routing automatically.

---

## 3. Red → Green Table

| Test | RED (before) | GREEN (after) |
|------|-------------|---------------|
| `TestTwoPlateBlocks::test_two_plate_blocks_in_config` | FAIL — 1 plate found (new name not recognized) | PASS |
| `TestOldSceneNodeGone::test_old_grass_sample_name_absent` | FAIL — old name still triggered plate 2 | PASS |
| `TestPlate2PlaterName::test_plate2_plater_name_updated` | FAIL — 1 plate found | PASS |
| `TestAppPyRouteWiring::test_no_stale_enable_fringe_grass_in_route` | FAIL — stale kwarg still present | PASS |
| `TestUICheckboxModel::test_checkbox_x_model_include_fringe_without_grass` | Already PASS (task 724 landed this) | PASS |
| `TestUILabelText::test_label_text_include_fringe_without_grass` | Already PASS | PASS |
| All T1–T12 injection tests (30 total) | — | All PASS |
| Pipeline tests T13–T16, T11, T13–T20 | Run against live EGM | Expected PASS (verified via mock intercept) |

Total non-pipeline tests: **41 pass** in both test files combined.

---

## 4. Test Drive for Thomas

1. **Hard-refresh the editor** (`Cmd+Shift+R` in browser to pick up v5.13).
2. **Open any existing EGM** (e.g. Delaveaga Hole 5). The footer should show `v5.13`.
3. **Verify checkbox state**: in the Fringe settings panel, you should see "Include Fringe Without Grass" — unchecked by default.
4. **Generate with checkbox unchecked**: click Generate. Pipeline runs, single plate produced. Plate 1 fringe has the grass texture (same as always).
5. **Check the box**: tick "Include Fringe Without Grass". Click Generate.
6. **Open the resulting .3mf in Bambu Studio**: you should see two plates:
   - **Plate 1**: full plaque — green, grassy fringe, traps, water, etc.
   - **Plate 2**: smooth fringe annulus only — no grass bumps, plain surface.
7. **Plate 2 filament**: should auto-assign extruder 2 (same fringe filament) since the node name starts with `"fringe"`.
