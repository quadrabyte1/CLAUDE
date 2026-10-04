# Default Fringe Z = Green Boundary Z Extended to Frame Edge
**v0.17 · Topo · 2026-10-04**

---

## Thomas's Spec (Verbatim)

> "By default, if there aren't any specific elevation notes given in the boundary editor the elevation of the green should be the same as the corresponding elevation sorry the elevation of the fringe should be the same as the corresponding elevation in the green across that interface and all the way out to the edge of the frame."

---

## Design: Nearest-Neighbor Extension via KDTree over Green Boundary

For each fringe cell `(x, y)`:

1. Find the **nearest point on the green polygon boundary** (`gbnd` polyline — already densified to ~2 mm spacing by Catmull-Rom + Chaikin).
2. Look up **`bnd_z[nn_idx]`** — the Poisson green surface Z sampled at that boundary vertex. This array is pre-computed once (`green_kd.query(gbnd, k=1)`) and already has `fringeBoundaryHeight` OCR anchors injected (task 658 Approach A stays untouched).
3. **Hold that Z constant all the way to the frame edge.** No decay toward `BASE_THICKNESS_MM`.

Result: the fringe becomes a radial "extension" of the green rim.

- **Flat green (Z = 7 mm everywhere)** → entire fringe at 7 mm.
- **Tilted green (5 mm left, 8 mm right)** → left fringe plateau at 5 mm, right fringe plateau at 8 mm, with a smooth Voronoi-split transition at corners.
- **Complex green shape** → each fringe cell tracks the Z of its nearest boundary segment, producing a smooth nearest-neighbor field with no hard cliffs.

The vectorised implementation builds a `(fringe_grid_res, fringe_grid_res)` lookup array `_z_nn_grid` in one batched KDTree query before the per-cell loop, so no per-cell query penalty.

---

## Why Not TPS Yet

`_build_tps_base()` is the right tool when user-set grid cells need to **locally override** the nearest-boundary default. That's the future grid-cell elevation mechanism. The default path is simpler:

- **TPS old path** (removed): 16 outer-frame anchors at `BASE_THICKNESS_MM` → flat ~1.5 mm everywhere. Wrong.
- **TPS future path** (coming): user-set cells become TPS constraints that pull the surface up/down locally, while unconstrained cells fall through to the nearest-boundary default.
- **Nearest-boundary default (this task)**: zero constraints needed, fully automatic, geometrically correct for the common case.

`_build_tps_base()` is kept intact and untouched. The function signature, implementation, and deprecation notices are unchanged.

---

## Code Change Summary

**`app/gradient_surface_diagnostic.py`** (v0.16 → v0.17):

In `build_fringe_mesh()`, replaced the TPS global-height-field block (which built `_z_tps_grid` from `_build_tps_base()` driven by 16 outer-frame anchors at `BASE_THICKNESS_MM`) with:

```python
# Vectorised NN lookup: for every fringe grid cell, find the nearest
# green-boundary vertex and read its Z from bnd_z.
GX_fringe, GY_fringe = np.meshgrid(xs_mm, ys_mm)
fringe_cells_xy = np.column_stack([GX_fringe.ravel(), GY_fringe.ravel()])
_, _nn_bnd_idx = gbnd_kd_lerp.query(fringe_cells_xy, k=1)
_z_nn_grid = bnd_z[_nn_bnd_idx].reshape(GX_fringe.shape)
```

In the per-cell loop, replaced:
```python
green_edge_h = float(_z_tps_grid[r, c])   # OLD: TPS → BASE everywhere
```
with:
```python
green_edge_h = float(_z_nn_grid[r, c])    # NEW: nearest green boundary Z
```

`_build_tps_base()` call removed from the hot path. The function itself is intact.

**`app/app.py`**: `APP_VERSION` v4.98 → **v4.99**.

---

## Preserved Pipelines

| Pipeline | Status |
|---|---|
| Poisson green interior surface | Unchanged |
| `bnd_z` pre-computation + `fringeBoundaryHeight` anchors (task 658) | Unchanged — anchors still override `bnd_z` entries before the NN lookup |
| Seam-reseat (task 689) | Unchanged — IDW-blend from `g_bdry_arr` still fires for inner fringe ring |
| Plateau-taper + `BOUNDARY_HEIGHT_CAP_MM` (task 506) | Unchanged — applies after `green_edge_h` is set |
| Fringe floor clamp (`FRINGE_PLATEAU_MARGIN_MM`) | Unchanged |
| Trap curved surface (v0.12 nearest-fringe-Z − 2 mm) | Unchanged |
| Rake texture, sand chunks, dip-floor guard | Unchanged |
| Water flat slab | Unchanged |
| Water-hole lift, frame-cap suspension | Unchanged |
| `_build_tps_base()` primitive | Intact — kept for future grid-cell mechanism |

---

## Red → Green Table

| # | Test | Class | Result |
|---|---|---|---|
| T1 | Fringe mid-edge inherits uniform green Z (7 mm) | `TestFringeInheritsGreenZ` | RED → **GREEN** |
| T2 | Fringe mirrors tilt (left≈5 mm, right≈8 mm) | `TestFringeMirrorsTilt` | RED → **GREEN** |
| T3 | Corner smooth transition (no cliff > 3.5 mm) | `TestFringeCornerTransition` | GREEN (pre-existing) |
| T4 | Frame-edge Z = nearest green boundary Z (not decayed) | `TestFringAtFrameEdge` | RED → **GREEN** |
| T5 | `_build_tps_base` callable with empty inputs | `TestTPSPrimitiveRegression` | GREEN (pre-existing) |
| T6a | Trap pipeline regression | `TestFringeRegressionTrapWater` | RED → **GREEN** |
| T6b | Water pipeline regression | `TestFringeRegressionTrapWater` | RED → **GREEN** |

Full suite: **319 passed, 0 failed, 184 skipped** (baseline was 312/0/184; +7 new).

Two pre-existing tests updated for the new design:
- `test_strip_ocr_elevation_spikes.py::test_app_version_bumped` → updated to expect v4.99
- `test_tps_global_height_field.py::TestTPSTrapRegression::test_trap_not_flattened` → updated to use tilted green (not deprecated spike) as the Z variation source

---

## Test Drive for Thomas

Regenerate **DeLaveaga H5** (or any hole with a sloped green):

**Before this change:** fringe was driven by the TPS 16-point outer-frame ring at `BASE_THICKNESS_MM = 1.5 mm` → whole fringe surface was a nearly-flat slab regardless of green elevation.

**After this change:** the fringe inherits the green's rim Z and holds it out to the frame edge. On a tilted green:
- The high side of the green (e.g., back edge at 8 mm) → back fringe plateau at 8 mm.
- The low side (e.g., front edge at 3.5 mm) → front fringe plateau at 3.5 mm.
- The fringe profile in cross-section goes from the seam Z horizontally to the frame (constant extension, no ramp).

If the green is relatively flat, the fringe will be a single-height plateau at that green boundary Z. If it has notable slope, the fringe will visibly tilt the same way. The green↔fringe seam remains continuous (seam-reseat still fires and pins the inner fringe ring to `g_bdry_arr` Z exactly).

---

## Follow-Up: Grid-Cell Mechanism

When the grid-cell elevation mechanism is dispatched, user-set cells will **override this default locally** via TPS. The design:

1. User sets a cell's elevation via the Boundary Editor.
2. That cell becomes a TPS constraint (XY → Z anchor).
3. `_build_tps_base()` builds a C²-smooth interpolant over the user-set cells.
4. Where the TPS output departs from `_z_nn_grid`, the fringe uses the TPS value.
5. Unconstrained cells fall through to the nearest-boundary default (this task).

`_build_tps_base()` is waiting for that work.
