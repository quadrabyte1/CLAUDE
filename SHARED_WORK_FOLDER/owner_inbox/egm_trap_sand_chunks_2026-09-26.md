# v1.0 · EGM Trap Sand Chunks — Task #608

**Topo · 2026-09-26 · gradient_surface_diagnostic.py v0.06 · APP_VERSION v4.65**

---

## Removal of jitter

`SAND_JITTER_AMPLITUDE_MM` (0.08 mm sinusoidal noise) and all related code
(`_jitter_dz`, `_phi1/_phi2`, `_jitter_wave*_wl`, seed vars) have been **deleted**
from `apply_sand_texture`. The constant was imperceptible at 0.08 mm alongside
0.35 mm rake ridges.

---

## Chunk math

**Bump shape** — radial Gaussian mound centred at `(cx, cy)`:

```
dz(x, y) = h * exp( -((x - cx)² + (y - cy)²) / (2 * σ²) )
```

Contributions from all bumps are summed and added to each top-face vertex after
the rake pass. The bump rises steeply near the centre and falls to ~14% of peak
at 2σ ≈ 3 mm — clearly visible as a discrete mound at print scale.

**Count law:**

```
count = clamp( round( area_mm² / 100 × density ), SAND_CHUNK_MIN, SAND_CHUNK_MAX )
```

Examples at defaults:
| Trap area | Raw count | Clamped |
|-----------|-----------|---------|
| 500 mm²   | round(1.5) = 2 | 3 (floor) |
| 1 625 mm² (Firefly H14) | round(4.9) = 5 | 5 → 4 after polygon mask |
| 3 000 mm² | round(9) = 9 | 9 |
| 50 000 mm²| 150 | 20 (cap) |

**Seed** — reproducible per trap:

```python
seed = int( abs(round(centroid.x, 1) * 1000) * 137
          + abs(round(centroid.y, 1) * 1000) * 31
          + trap_index * 997 ) % (2**31)
```

Same EGM + trap index → identical bump positions and heights on every regeneration.

**Variation** — each bump's `h` and `σ` are jittered so bumps look organic:

- `h_i = SAND_CHUNK_HEIGHT_MM × uniform(0.7, 1.3)`
- `σ_i = SAND_CHUNK_SIGMA_MM × uniform(0.8, 1.2)`

**Placement** — uniform random inside the trap polygon via rejection sampling
(shapely `contains`). Budget: `n_chunks × 200` attempts per trap.

**Application order** — chunks are applied to `new_mesh.vertices` after steps
1–6 (rake rebuild + Delaunay + watertight repair). Since
`BOUNDARY_HEIGHT_CAP_ENABLED = False` (task #606), chunks can push vertices
above the 9 mm cap; that's intentional.

---

## Constants table

| Constant | Default | Notes |
|---|---|---|
| `SAND_CHUNK_HEIGHT_MM` | `0.6` | Gaussian peak in mm. Bump about 2× rake amplitude — visible but not dominant over the rake lines. Raise to 0.9 for more dramatic lumps; lower to 0.4 for subtler texture. |
| `SAND_CHUNK_SIGMA_MM` | `1.5` | Gaussian sigma in mm. Footprint ~3 mm at 2σ. Lower for tighter pips; raise for broader domes. |
| `SAND_CHUNK_DENSITY_PER_100_MM2` | `0.3` | Chunks per 100 mm². 0.1 for very sparse; 0.5 for denser scatter. |
| `SAND_CHUNK_MAX` | `20` | Cap per trap. Prevents over-texturing large traps. |
| `SAND_CHUNK_MIN` | `3` | Floor per trap. Ensures even small traps get a couple of lumps. |

---

## Red → green test table

Class `TestSandChunkScatter` in `app/tests/test_gradient_surface_diagnostic.py`:

| # | Test | RED (before) | GREEN (after) |
|---|------|-------------|--------------|
| I-1a | `test_chunk_constants_exist` | 5 constants missing | All 5 present at correct defaults |
| I-1b | `test_jitter_constant_removed` | `SAND_JITTER_AMPLITUDE_MM` still defined | Constant absent |
| I-2 | `test_chunk_count_law` | `_scatter_sand_chunks` missing | Count correct for 500/3000/50000 mm² |
| I-3 | `test_chunk_reproducibility` | Helper missing | Same poly+index → identical cx/cy/h |
| I-4 | `test_chunk_peak_height_bounds` | `SAND_CHUNK_HEIGHT_MM` missing → skip | Max delta in [0.42, 2.34] mm |
| I-5 | `test_chunk_centres_inside_polygon` | Helper missing | Every centre passes `shapely.contains` |
| I-6 | `test_chunks_additive_to_rake` | `SAND_CHUNK_HEIGHT_MM` missing → skip | max(with) > max(without) by ≥ 0.42 mm |

Class `TestRakeJitter` updated (removed SAND_JITTER_AMPLITUDE_MM references):

| Test | Change |
|------|--------|
| `test_jitter_amplitude_constant_exists` | Replaced by `test_jitter_constant_absent_after_608` (asserts constant is GONE) |
| `test_jitter_amplitude_nonzero_on_top_surface` | Replaced by `test_chunk_scatter_present_on_top_surface` (asserts `_scatter_sand_chunks` called + Z max > rake peak) |
| `test_jitter_is_reproducible_same_trap` | Kept as-is; passes with chunk seeding |
| `test_jitter_differs_between_traps` | Kept; updated docstring to reference chunks |
| `test_jitter_within_amplitude_bound` | Replaced by `test_chunk_z_range_bounded` (bounds Z range against rake + chunk overlap) |

**Full suite: 35/35 passed.**

---

## Visual check

### Firefly H14

1 trap (elongated along ~85° axis, area ≈ 1 100 mm²):

- **4 chunk bumps** placed, max bump dz = **0.731 mm** above rake peak
- Rake lines clearly present (17 lines at 1.12 mm spacing, amplitude 1.0 mm from defaults)
- Top Z range: **12.000 – 13.655 mm** (base 10 mm + 2 mm water lift + rake + chunks)
- Mesh watertight ✓

Expected look: discrete sand lumps visible as small mounds scattered over the
flat-raked trap surface; rake ridges still clearly readable underneath.

### DeLaveaga H5

4 traps regenerated:

| Trap | Area (approx) | Chunks | Max bump dz | Z range | Watertight |
|------|---------------|--------|-------------|---------|------------|
| trap_1 | ~835 mm² | 3 | 0.762 mm | 10.00–11.65 mm | ✓ |
| trap_2 | ~450 mm² | 3 (floor) | 0.965 mm | 10.00–11.96 mm | ✓ |
| trap_3 | ~1750 mm² | 5 | 0.773 mm | 10.00–11.73 mm | ✓ |
| trap_4 | ~950 mm² | 3 (floor) | 0.720 mm | 10.00–11.69 mm | ✓ |

Rake axes vary per trap (50.7°, 35.8°, 114.8°, 119.3°) — all PCA-derived.

### Stanford H8

1 trap (large, area ≈ 3 400 mm²):

- **6 chunk bumps**, max bump dz = **0.738 mm**
- Top Z range: **10.000 – 11.720 mm**
- Watertight ✓

---

## Files changed

- `/Volumes/GIT/CLAUDE/SHARED_WORK_FOLDER/app/gradient_surface_diagnostic.py` — v0.06
  - Header comment block updated
  - Removed: `SAND_JITTER_AMPLITUDE_MM` constant, `_jitter_dz`, seed/phase vars
  - Added: 5 `SAND_CHUNK_*` constants, `_scatter_sand_chunks` helper, chunk-pass step 7 in `apply_sand_texture`
- `/Volumes/GIT/CLAUDE/SHARED_WORK_FOLDER/app/app.py` — `APP_VERSION` v4.64 → v4.65
- `/Volumes/GIT/CLAUDE/SHARED_WORK_FOLDER/app/tests/test_gradient_surface_diagnostic.py`
  - `TestRakeJitter` class updated (5 tests replaced/updated)
  - `TestSandChunkScatter` class added (7 new tests)
