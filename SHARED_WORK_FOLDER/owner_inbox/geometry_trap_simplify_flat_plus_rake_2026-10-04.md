# v0.19 — Trap Simplify: Flat Top + Rake Lines Only

**2026-10-04 · Topo · Task 708**

---

## Change list

### Removed

| Item | Location |
|------|----------|
| `SAND_CHUNK_HEIGHT_MM` constant | `gradient_surface_diagnostic.py` |
| `SAND_CHUNK_SIGMA_MM` constant | same |
| `SAND_CHUNK_DENSITY_PER_100_MM2` constant | same |
| `SAND_CHUNK_MAX` constant | same |
| `SAND_CHUNK_MIN` constant | same |
| `SAND_CHUNK_UP_FRACTION` constant | same |
| `SAND_CHUNK_FLOOR_THICKNESS_MM` constant | same |
| `_scatter_sand_chunks()` helper function | same |
| Chunk-scatter pass in `apply_sand_texture()` (step 7) | same |
| Per-vertex floor guard clamp (`_use_per_vertex_floor`, `np.maximum(new_z, floor_v)`) | same |

### Changed

| Item | Before | After |
|------|--------|-------|
| `TRAP_SURFACE_CURVED` | `True` (per-point curved, task 666 default) | `False` (flat min, task 708 default) |
| `gradient_surface_diagnostic.py` `__version__` comment | v0.18 | v0.19 |
| `app.py` `APP_VERSION` | v5.02 | v5.03 |

### Kept

- `TRAP_SURFACE_CURVED` flag + curved code path — still reachable by setting `True`
- Rake lines: `SAND_RAKE_ALIGN_TO_MAJOR_AXIS`, rake amplitude/wavelength constants, cosine-wave displacement
- `_compute_trap_height_from_fringe`, `_compute_trap_surface_from_fringe` — still used by both flat and curved paths
- `TRAP_FRINGE_OFFSET_MM = -2.0`, `TRAP_FRINGE_BOUNDARY_BAND_MM = 6.0`
- `base_z_map` parameter in `apply_sand_texture` — API-stable for the curved path
- `BOUNDARY_HEIGHT_CAP_ENABLED = False` — unchanged
- Water-hole lift — unchanged
- Fringe, green, Poisson, grid-cell TPS (v0.18), seam-reseat — all unchanged

---

## Flat-rule recap (task 662 behavior, now default again)

```
trap_Z = min(fringe boundary Z within TRAP_FRINGE_BOUNDARY_BAND_MM)
       + TRAP_FRINGE_OFFSET_MM
       = min(fringe boundary Z) − 2.0 mm
```

Every point on the trap top sits at this single scalar height. The rake cosine wave then adds ±0.5 mm displacement on top (amplitude=1.0 default → peak dz = 1.0 mm, trough = 0). No per-point curvature, no Gaussian bumps.

---

## `TRAP_SURFACE_CURVED` flag

| Value | Behavior |
|-------|----------|
| `False` (default, v0.19) | Flat scalar: `trap_Z = min(fringe boundary Z) − 2 mm` |
| `True` (task 666 path) | Per-point curved: nearest-neighbor fringe Z at each boundary ring sample − 2 mm; interior via griddata cubic |

Flip back to `True` in `gradient_surface_diagnostic.py` line ~5322 to restore the curved surface if needed. Same flag pattern as `SAND_RAKE_ALIGN_TO_MAJOR_AXIS`.

---

## Red → green table

| Test | Description | Result |
|------|-------------|--------|
| TR1 | No `SAND_CHUNK_*` constants in module | RED → GREEN |
| TR2 | No `_scatter_sand_chunks` function | RED → GREEN |
| TR3 | Top-face Z deviation bounded by rake amplitude (no Gaussian outliers) | (was passing) GREEN |
| TR4 | `apply_sand_texture` source contains no `SAND_CHUNK_FLOOR_THICKNESS_MM` | RED → GREEN |
| TR5 | `TRAP_SURFACE_CURVED = False` default | RED → GREEN |
| TR6 | Flat trap on sloped fringe — top Z range ≤ 1.1 mm (rake only) | (was passing) GREEN |
| TR7 | Curved path still reachable — `TRAP_SURFACE_CURVED=True` produces Z range > 1.5 mm | (was passing) GREEN |
| TR8 | Rake ridges present — Z spread ≥ 0.10 mm on flat top | RED → GREEN |
| TR9 | `build_fringe_mesh` regression — valid finite mesh | (was passing) GREEN |
| TR10 | Fresh module load confirms `TRAP_SURFACE_CURVED = False` | RED → GREEN |

Full suite: **376 passed, 212 skipped, 0 failed** (up from 557 collected; the 181-item increase is skipped tests retired today from old chunk/curved-default classes).

---

## Test drive for Thomas — DeLaveaga H5

Regenerate DeLaveaga Hole 5 (multiple traps on a sloped fringe). What to expect:

- **Trap top** is a flat plane. The height is `min(fringe boundary Z around that trap) − 2 mm`. On H5 the fringe varies from roughly 5 mm on the low side to 9 mm on the high side, so each trap will sit at its own flat scalar, not a slope.
- **Rake stripes** are visible across the flat top — parallel Y-axis ridges, ~1.125 mm pitch, ~0.35 mm peak-to-trough amplitude.
- **No scattered chunks or dimples** anywhere on any trap face.
- **Fringe, green, water** — unchanged from v0.18.

---

## Follow-up

Thomas can flip `TRAP_SURFACE_CURVED = True` at line ~5322 in `gradient_surface_diagnostic.py` if he wants the per-point curved surface back later. No other code change required.
