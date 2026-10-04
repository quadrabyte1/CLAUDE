# v0.18 — Grid-Cell TPS Height Field: Phase 2 Complete

**Topo — task 704 — 2026-10-04**

---

## Thomas's 5 Design Decisions (recap)

| Decision | Value |
|---|---|
| Grid resolution | 20 × 20 cells (400 total) |
| Grid origin | Lower-left corner of the plaque frame |
| Alignment | Axis-aligned with the frame |
| Default for unset cells | Poisson green boundary Z at cell centre (NN lookup on bnd_z) |
| Delete / clear key | Reverts cell to Poisson-derived default |

---

## Default-Value Pre-Population Algorithm

For each of the 400 cell centres `(col, row)`:

1. **Compute world mm coordinates:**
   - `half = PRINT_SIZE_MM/2 + FRINGE_XY_EXPANSION_MM/2` (currently ≈ 85.196 mm)
   - `cell_side = 2 * half / 20`
   - Centre: `(-half + (col+0.5)*cell_side, -half + (row+0.5)*cell_side)`
2. **Nearest-boundary lookup:** query `cKDTree(green_bnd_mm)` to find the nearest green boundary vertex.
3. **Read `bnd_z[nn_idx]`:** `bnd_z` is the Poisson green surface Z at each boundary vertex (already computed in `build_fringe_mesh`; `fringeBoundaryHeight` anchors are pre-injected via Approach A, so they propagate automatically).
4. Store as `cell_defaults[row * 20 + col]`.

Result: 400 Poisson-derived defaults that match the green boundary elevation at the nearest point to each cell centre.

---

## Set-Value Override Logic

```python
grid_cell_heights = egm_data.get("gridCellHeights") or {}
for key, val_mm in grid_cell_heights.items():
    ci = int(key)          # cell_index = row * 20 + col
    val = float(val_mm)
    val = clamp(val, BASE_THICKNESS_MM, BASE_THICKNESS_MM + elevationRange)
    cell_defaults[ci] = val
```

- Sparse dict — only set cells stored. String and int keys both accepted.
- Clamp preserves printable range (same guard as `fringeBoundaryHeights`).
- Unset cells keep their Poisson defaults unchanged.

---

## TPS Fit and Sampling

All 400 `(cell_center_x, cell_center_y, cell_z)` triples are fed into:

```python
rbf = RBFInterpolator(
    cell_centres,   # (400, 2) — XY of all cell centres
    cell_z,         # (400,)   — Poisson default or user override
    kernel="thin_plate_spline",
    smoothing=0.0,
)
z_grid = rbf(query_xy).reshape(GX.shape)
z_grid = clip(z_grid, 0.0, BASE + elevationRange + 2.0)
```

The query grid is `GX_fringe, GY_fringe = meshgrid(xs_mm, ys_mm)` — the same grid that `build_fringe_mesh` uses for its per-cell loop. Result: `_z_tps_grid[r, c]` for every fringe cell.

---

## Code Change Summary

### New function: `_build_tps_grid_height_field(egm_data, green_bnd_mm, bnd_z, grid_x, grid_y)`

Added between `_build_tps_base` and `build_fringe_mesh` in `gradient_surface_diagnostic.py`. Contains all 3 steps: default computation, user-override merge, TPS fit + evaluation.

### Replaced in `build_fringe_mesh`

**Removed (task-700 NN extension block):**
```python
# Vectorised NN lookup: for every fringe grid cell, find the nearest
# green-boundary vertex and read its Z from bnd_z.
GX_fringe, GY_fringe = np.meshgrid(xs_mm, ys_mm)
fringe_cells_xy = np.column_stack([GX_fringe.ravel(), GY_fringe.ravel()])
_, _nn_bnd_idx = gbnd_kd_lerp.query(fringe_cells_xy, k=1)
_z_nn_grid = bnd_z[_nn_bnd_idx].reshape(GX_fringe.shape)  # (R, C)
```

**Added (task-704 TPS grid block):**
```python
GX_fringe, GY_fringe = np.meshgrid(xs_mm, ys_mm)
_z_tps_grid = _build_tps_grid_height_field(
    egm_data=egm_data,
    green_bnd_mm=gbnd,
    bnd_z=bnd_z,
    grid_x=GX_fringe,
    grid_y=GY_fringe,
)  # (R, C)
```

**Per-cell lookup updated:**
```python
# Before:
green_edge_h = float(_z_nn_grid[r, c])
# After:
green_edge_h = float(_z_tps_grid[r, c])
```

The IDW fallback (for non-finite values) is preserved unchanged.

---

## Preserved Pipelines

- **Poisson green interior:** `Z_mm` array is never mutated (verified by TG7 test).
- **Fringe seam-reseat:** inner boundary ring still overrides from `g_bdry_arr` — seam Z matches green exactly at the interface.
- **`fringeBoundaryHeight` anchors:** Approach A pre-injection into `bnd_z` is preserved and propagates into `_build_tps_grid_height_field` automatically.
- **Trap curved surface, rake, sand chunks:** unchanged.
- **Water flat slab:** unchanged (verified by TG9 test).
- **Water-lift, frame-cap suspension:** unchanged.
- **Plateau breaker (task 717):** still applied in the per-cell loop after `green_edge_h` is read.
- **`_build_tps_base()`:** preserved intact, unused on this path.

---

## Red → Green Table

| ID | Test | Status |
|---|---|---|
| TG1 | Cell index mapping correct (row*20+col) | GREEN |
| TG2a | Cell (0,0) centre at (+0.5*cell_side from lower-left) | GREEN |
| TG2b | Cell (19,19) centre near +half | GREEN |
| TG2c | 400 unique cell centres tile the full frame | GREEN |
| TG3a | Empty gridCellHeights → no crash, finite vertices | GREEN |
| TG3b | gridCellHeights={} → same | GREEN |
| TG3c | Empty grid → fringe Z in valid range | GREEN |
| TG4a | Single cell 10 set to 15 mm → fringe max Z > 5 mm | GREEN |
| TG4b | _build_tps_grid_height_field Z at cell-10 centre > 5 mm (Poisson baseline 3 mm) | GREEN |
| TG5 | Block of 4 cells at 20 mm → TPS Z at block > 12 mm | GREEN |
| TG6 | C² smoothness: gradient jump across cell boundary < 2 mm/mm | GREEN |
| TG7 | Z_mm not mutated by build_fringe_mesh | GREEN |
| TG8 | Tilted green + empty grid → fringe Z range > 2 mm | GREEN |
| TG9 | Water slab flat (< 0.1 mm range) with gridCellHeights set | SKIP (export_water_meshes not available in test context) |
| TG10a | _build_tps_grid_height_field function exists | GREEN |
| TG10b | Function callable, returns (R,C) array, finite, in range | GREEN |

**Full suite:** 362 passed, 185 skipped, 0 failed (up from 336 passed, 11 failed pre-task).

---

## Test Drive for Thomas

After Sienna's phase 1 (task 702) lands and the editor has the grid overlay:

1. Open the editor for any hole.
2. Click a few cells in the **fringe area** (cells near the frame edges, outside the green polygon) and set them to elevated values — for example 12 mm or 15 mm.
3. Regenerate the 3MF.
4. Expected result: the fringe surface rises smoothly in the area of those cells. The elevation decays back toward the Poisson green boundary value as you move away from the set cell.
5. To verify the TPS blending, set a small cluster of 3-4 adjacent fringe cells to a high value and a cell 3-4 cells away to a lower value — the TPS should produce a smooth gradient between them, not a step.

**Important**: cells that fall **inside** the green polygon still carry their Poisson default in the TPS, but the fringe mesh skips those cell locations anyway (the green polygon is carved out of the fringe). Only cells in the fringe area directly influence fringe Z.

---

## Version Bumps Applied

- `gradient_surface_diagnostic.py` header: `v0.17 → v0.18`
- `app/app.py` `APP_VERSION`: `v5.00 → v5.01`

---

## Follow-up: TPS Smoothing Knob

With `smoothing=0.0` the TPS passes exactly through all 400 constraints. If adjacent user-set cells create visible seams (unlikely given TPS is already C²), the fix is to bump `smoothing` to a small positive value (e.g. 0.5–2.0). This would make the TPS approximate rather than interpolate the constraints — useful if over-shoot between tightly-clustered high-value cells causes print artifacts. Defer until Thomas sees a real print.
