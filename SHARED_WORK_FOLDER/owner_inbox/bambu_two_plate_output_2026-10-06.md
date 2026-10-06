# v1.0 — Two-Plate 3MF Output
**Task 718 · Finn · 2026-10-06**

---

## Thomas's spec

> "Can we put another plate on the 3MF output file? And on that plate just put another copy of the fringe, but with the grass feature included."

- **Plate 1** (unchanged): full plaque — green + fringe (grass per checkbox) + traps + water + boulders.
- **Plate 2** (new): fringe annulus with grass **unconditionally enabled** regardless of the Enable Fringe Grass checkbox. Use case: inspect texture quality separately from a full plaque print.

---

## 3MF schema diff: single-plate → two-plate

### `Metadata/model_settings.config`

**Before (single-plate):** Only `<object>` blocks; no `<model_instance>` plate assignments.

**After (two-plate):** Two `<plate>` blocks with `<model_instance>` children assigning objects to plates — matches the exact structure in `ItWentIn/Flag.3mf` (a real Bambu Studio 4-plate export):

```xml
<config>
  <!-- object blocks for all N+1 meshes (unchanged extruder mapping) -->
  <object id="1"><metadata key="extruder" value="1"/>...</object>
  <object id="N+1"><metadata key="extruder" value="2"/>...</object>  <!-- fringe_grass_sample -->

  <!-- Plate 1: all objects except fringe_grass_sample -->
  <plate>
    <metadata key="plater_id" value="1"/>
    <metadata key="thumbnail_file" value="Metadata/plate_1.png"/>
    <model_instance>
      <metadata key="object_id" value="1"/>
      <metadata key="instance_id" value="0"/>
    </model_instance>
    <!-- one entry per plate-1 object -->
  </plate>

  <!-- Plate 2: fringe_grass_sample only -->
  <plate>
    <metadata key="plater_id" value="2"/>
    <metadata key="plater_name" value="Fringe Grass Sample"/>
    <metadata key="thumbnail_file" value="Metadata/plate_2.png"/>
    <model_instance>
      <metadata key="object_id" value="N+1"/>
      <metadata key="instance_id" value="0"/>
    </model_instance>
  </plate>

  <assemble/>
</config>
```

### New archive entries (task 718)

| File | Source |
|---|---|
| `Metadata/plate_2.png` | Copy of `plate_1.png` (placeholder; Bambu regenerates on first slice) |
| `Metadata/plate_no_light_2.png` | Copy of `plate_no_light_1.png` |
| `Metadata/top_2.png` | Copy of `top_1.png` |
| `Metadata/pick_2.png` | Copy of `pick_1.png` |

Total archive entries: 12 (single-plate) + 4 (plate-2 thumbnails) = **16**.

---

## How plate 2's fringe mesh is built

In `run_pipeline` step **7a-ii** (inserted between the plate-1 grass application and the mount-pipe build in step 7b):

1. Call `build_fringe_mesh(...)` with the same inputs as plate 1 — same `Z_mm_for_fringe`, `xs_grid`, `ys_grid`, `inside_mask`, `green_boundary_px`, `_egm_data`, and `fringe_holes`.
2. Apply `apply_grass_texture_v2` (or `apply_grass_texture`) **unconditionally** — grass always on regardless of the EGM checkbox.
3. Store result in `fringe_grass_sample`; add to scene AFTER all plate-1 objects so its objectid (N+1) is highest.

Scene node name: `"fringe_grass_sample"` — the `startswith("fringe")` check in `_filament_for_scene_name` routes it to extruder 2 (same as the main fringe). No mount-pipe bore is added to the sample.

**Note:** The current sample uses the same trap/water carve-out geometry as plate 1 (the annulus has the same recesses). If you want plate 2 to be a clean uncarved annulus, see the Follow-up section below.

---

## Reused vs. new thumbnail / config files

| File | Status |
|---|---|
| All 12 single-plate files | Unchanged — injected verbatim as before |
| `Metadata/plate_2.png` | New — copied from `plate_1.png` template |
| `Metadata/plate_no_light_2.png` | New — copied from `plate_no_light_1.png` |
| `Metadata/top_2.png` | New — copied from `top_1.png` |
| `Metadata/pick_2.png` | New — copied from `pick_1.png` |
| `Metadata/model_settings.config` | Regenerated — now has two `<plate>` blocks |

---

## Red → Green table

| # | Test | RED cause | GREEN |
|---|---|---|---|
| T1 | `model_settings.config` has 2 `<plate>` blocks | Old code wrote zero plate blocks | Injection generates 2 when `fringe_grass_sample` in names |
| T2 | Plate 1 instances ref original object IDs (1..N) | No instances written | Plate-1 block has `<model_instance>` for all non-sample objects |
| T3 | Plate 2 instance refs `fringe_grass_sample` object | No plate-2 block | Plate-2 block has 1 `<model_instance>` for the sample |
| T4 | Plate-2 block refs `Metadata/plate_2.png` | No plate-2 block | Plate-2 metadata declares `plate_2.png` as `thumbnail_file` |
| T5 | Archive has `plate_2.png`, `plate_no_light_2.png`, etc. | Files not injected | Plate-1 thumbnail bytes copied under plate-2 arcnames |
| T6 | Plate-1 files still present (regression) | (was passing) | Still GREEN |
| T7 | ZIP integrity | (was passing) | Still GREEN |
| T8 | Idempotent: no duplicate plate-2 thumbnails | `_SKIP_FILES` didn't include plate-2 arcnames | Added plate-2 arcnames to `_SKIP_FILES` |
| T9 | `fringe_grass_sample` → extruder 2 | (was passing via filament mapping) | Still GREEN |
| T10 | No plate-2 when sample absent | (was passing) | Still GREEN |
| T11 | Plate-2 block has `plater_id=2` | No plate-2 block | `<metadata key="plater_id" value="2"/>` present |
| T12 | Two-plate archive has ≥16 entries | Only 12 entries | 16 entries present |
| T13 | `fringe_grass_sample` in `scene_names` | Not added to scene | Added to scene after boulders, before 3MF assembly |
| T14 | Grass called when plate-1 grass disabled | 0 calls when False | 1 call for plate-2 sample even when `enableFringeGrass=False` |

**Regression update — task 714 T10:**
`test_grass_not_called_when_disabled` previously asserted 0 grass calls when `enableFringeGrass=False`. Task 718 intentionally fires grass for the plate-2 sample, so the test was updated to assert `== 1 call` (plate-2 only — plate-1 fringe correctly skipped).

**Final suite: `462 passed, 0 failed`** (was 431 before task 718; +31 new tests)

---

## Test drive for Thomas

1. Open the EGM web app (port 5051).
2. Select any hole (e.g. **Delaveaga H5**).
3. Click **Generate 3MF** and save the file.
4. Open the `.3mf` in Bambu Studio.

**Expected:**
- Bambu Studio shows **two plates** in the plate selector.
- **Plate 1** is the full plaque: green + fringe + traps + water/boulders (unchanged from before).
- **Plate 2** is labelled "Fringe Grass Sample" and shows just the fringe annulus with visible grass bumps — regardless of whether the Enable Fringe Grass checkbox was on or off when generating.
- No "invalid config" dialog on open.
- Plate-2 thumbnails are placeholder copies of plate 1; Bambu will update them after the first slice.

**To verify grass is always on in plate 2:**
1. Uncheck Enable Fringe Grass in the editor.
2. Generate 3MF.
3. In Bambu Studio: plate 1 fringe is smooth. Plate 2 fringe has grass bumps.

---

## Follow-up: clean annular fringe for plate 2

Currently plate 2's fringe has the same trap/water carve-outs as plate 1. For a cleaner "pure texture sample," we could suppress those carveouts so plate 2 is an unbroken annulus. This would require either:
- Passing a modified `egm_data` copy with polygons list filtered to green-only, or
- Adding a `suppress_carveouts: bool = False` parameter to `build_fringe_mesh`.

Not blocked — flag when Thomas reviews plate 2 in Bambu and decides whether the current carve-out version is sufficient.

---

## Files changed

- `/Volumes/GIT/CLAUDE/SHARED_WORK_FOLDER/app/gradient_surface_diagnostic.py` — v0.21: two-plate injection + plate-2 fringe sample build in step 7a-ii.
- `/Volumes/GIT/CLAUDE/SHARED_WORK_FOLDER/app/app.py` — `APP_VERSION` v5.07 → **v5.08**.
- `/Volumes/GIT/CLAUDE/SHARED_WORK_FOLDER/app/tests/test_bambu_two_plate_output.py` — 31 new RED→GREEN tests (new file).
- `/Volumes/GIT/CLAUDE/SHARED_WORK_FOLDER/app/tests/test_enable_fringe_grass.py` — T10 updated to `== 1 call` (plate-2 always fires grass).
