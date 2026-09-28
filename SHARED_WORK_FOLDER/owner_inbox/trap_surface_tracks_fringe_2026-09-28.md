# v0.09 — Trap Surface Tracks Fringe Topology

**Topo · 2026-09-28 · Task 654**

---

## Old vs New Rule

| | Old (flat slab) | New (curved surface) |
|---|---|---|
| **Height function** | single scalar = `fringe_boundary_max − 4mm` | `trap_Z(x,y) = fringe_Z(x,y) − 4mm` at every boundary point; interior interpolated |
| **Result** | flat top at the maximum fringe-boundary Z | curved top that mirrors the fringe rim everywhere |
| **Typical appearance** | slab looks artificially flat when fringe slopes | slab follows the fringe rim contour, 4mm below it all the way round |

---

## Interpolation Approach: Option A (cubic griddata)

**Chosen approach:** scipy.interpolate.griddata cubic, with linear fallback for any NaN outside the convex hull of the boundary ring, and a mean-boundary-Z fill for any remaining NaN.

**Why A (cubic) over B (nearest-neighbor from full fringe interior):**
- Cubic griddata produces a smooth surface between boundary constraints and avoids the noisy "staircase" artifacts that nearest-neighbor interior sampling can introduce when the fringe mesh is sparse.
- The boundary ring of the trap provides dense, well-distributed sample points (≤1mm spacing after densification), so cubic has enough constraints to work well.
- Option B (copying full fringe gradient into the trap interior) is slower and can produce unrealistic local extrema if the fringe mesh has vertices inside the trap footprint (which the fringe mesh sometimes does, depending on how cutouts are meshed).
- If cubic produces ugly middle-sag artifacts on real holes, B is still an easy swap — the boundary ring Z values are already computed.

**Artifacts to watch for:** If a trap has a very concave boundary ring and the interior is far from all ring points, griddata cubic can produce undershoots. The mean-boundary-Z fallback handles the worst cases, and the 1mm floor guard prevents any visible sink-holes.

---

## Implementation

Three changes in `app/gradient_surface_diagnostic.py`:

### 1. New helper: `_compute_trap_surface_from_fringe`

```python
def _compute_trap_surface_from_fringe(
    trap_poly_mm, fringe_mesh, query_xy,
    boundary_band_mm=TRAP_FRINGE_BOUNDARY_BAND_MM,
    offset_mm=TRAP_FRINGE_OFFSET_MM,
) -> np.ndarray:
```

- Densifies exterior ring at ≤1mm spacing.
- For each ring sample, queries all fringe top vertices within `TRAP_FRINGE_BOUNDARY_BAND_MM` (6mm). Takes max Z across all in-band vertices → boundary trap Z = fringe_max − 4mm.
- Interpolates to arbitrary `query_xy` positions using griddata cubic → linear fallback → mean fill.
- **Fallback:** if fringe is None or no in-band vertices found, returns `TRAP_THICKNESS_MM` (10mm flat) for all query points.

### 2. Modified: `apply_sand_texture`

Added `base_z_map: tuple[np.ndarray, np.ndarray] | None = None` parameter.

- When `None`: unchanged flat behavior (z_max used as uniform base).
- When `(grid_xy, grid_base_z)`: nearest-neighbor lookup from the map provides per-grid-point base Z. Rake and chunks are additive on top of this curved base.
- **Floor guard upgraded:** with `base_z_map`, uses per-vertex `local_base_z + 0.5mm` instead of global `trap_base_z + 0.5mm`. Dimples can't push any vertex below its local curved base + 0.5mm.

### 3. Modified: `export_trap_stls`

Replaced the `_compute_trap_height_from_fringe` call with:
1. Build a dense interior grid over the inset trap footprint.
2. Call `_compute_trap_surface_from_fringe` → get curved Z at every grid point.
3. Set `trap_height = max(curved_Z_array)` for slab extrusion.
4. Pass `base_z_map=(grid_xy, curved_Z)` into `apply_sand_texture`.

The old `_compute_trap_height_from_fringe` is retained as a fallback path (used when the curved computation returns all-flat, indicating no adjoining fringe).

---

## Preserved Interactions

| Feature | Status | How |
|---|---|---|
| **Rake lines** (fixed Y-axis cosine) | Preserved | `_rake_dz(xy)` is still computed and added to `base_z_at(xy)`; the cosine wave is purely additive on the curved base |
| **Sand chunks** (Gaussian mounds ±0.6mm) | Preserved | Applied after rake in step 7 of `apply_sand_texture`; additive on curved+rake surface |
| **Frame-cap suspension** (`BOUNDARY_HEIGHT_CAP_ENABLED=False`) | Unchanged | Cap logic not touched |
| **Dip-floor guard** | Upgraded | Now per-vertex on curved surface: `local_base_z + 0.5mm` lookup via nearest-neighbor into the base_z_map |
| **Water-hole lift** | Unchanged | Applied after `apply_sand_texture`, same as before |

---

## Fallback for Trap With No Adjoining Fringe

If `fringe_mesh` is `None`, or no fringe vertices fall within `TRAP_FRINGE_BOUNDARY_BAND_MM` (6mm) of any ring sample point:

- `_compute_trap_surface_from_fringe` returns `TRAP_THICKNESS_MM` (10.0mm) for all query points.
- `export_trap_stls` detects the flat fallback (all values ≈ TRAP_THICKNESS_MM) and routes to the original scalar path with `base_z_map=None`, producing the same flat slab as before.
- Print: `"no fringe mesh — using fixed height 10.00 mm"`.

Traps that only partially adjoin the fringe are handled naturally: boundary ring samples in the non-adjacent portion get the mean of the adjacent samples (filled via nearest-valid-ring-sample), and griddata interpolates the interior smoothly.

---

## Red → Green Table

| # | Test | Description | Before | After |
|---|---|---|---|---|
| L-1 | `test_flat_fringe_gives_flat_trap_surface` | Flat fringe at Z=H → flat trap at Z=H-4 at boundary and interior samples | RED (function missing) | GREEN |
| L-2 | `test_sloped_fringe_gives_sloped_trap_surface` | Fringe ramp 10→14 → right boundary trap Z > left by ≥0.5mm | RED (function missing) | GREEN |
| L-3 | `test_no_adjoining_fringe_fallback_flat` | Fringe far away (no in-band verts) → returns TRAP_THICKNESS_MM | RED (function missing) | GREEN |
| L-4 | `test_rake_and_chunks_on_curved_base` | `apply_sand_texture` accepts `base_z_map`; slope preserved; rake visible | RED (param missing) | GREEN |
| L-5 | `test_per_vertex_floor_guard_on_curved_base` | All-down chunks with curved base; no vertex below local_base + 0.5mm | RED (param missing) | GREEN |

**Full suite: 57/57 pass** (52 pre-existing + 5 new). No regressions.

---

## Test Drive

**Recommended hole for visual verification:** Firefly H14 or DeLaveaga H3 — both have traps that adjoin a distinctly sloped fringe rim.

**What to look for after regenerating the 3MF:**

1. Open the 3MF in Bambu Studio and inspect the trap slab from the side.
2. **Curved base visible:** the trap top surface should visibly tilt/curve following the fringe rim, not sit as a flat horizontal slab. The 4mm offset should be uniform around the perimeter (not just at the highest point).
3. **Rake still visible:** parallel Y-axis ridges should still be clearly visible across the curved base.
4. **Sand chunks still visible:** discrete mounds and dimples scattered across the raked surface.
5. **No gap or step** between fringe and trap at the interface — the trap should nestle smoothly 4mm below the fringe all the way round.

**Print note:** the curved slab uses the same inset/gap tolerances as before. No fit changes expected. The only visible difference is the trap top no longer reads as artificially flat.

---

## Version Bumps

- `app/gradient_surface_diagnostic.py`: `v0.08 → v0.09`
- `app/app.py` `APP_VERSION`: `v4.79 → v4.80`
