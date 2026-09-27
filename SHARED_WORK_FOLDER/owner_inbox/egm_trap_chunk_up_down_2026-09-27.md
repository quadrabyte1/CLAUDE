# Sand Trap Chunk Up/Down Mix + Count Bump — v0.08

**v0.08** · 2026-09-27 · Topo · Task #614

---

## Sign Mix (50/50 default, floor guard)

Each sand chunk now gets a random sign drawn from the same seeded RNG used for
positions and magnitudes, so a given trap always produces the same up/down
pattern across renders.

**New constant:**
```python
SAND_CHUNK_UP_FRACTION: float = 0.5   # 1.0 = all mounds, 0.0 = all dimples
SAND_CHUNK_FLOOR_THICKNESS_MM: float = 0.5  # dimple floor guard (mm above slab base)
```

**How sign is assigned** (inside `_scatter_sand_chunks`):
```python
sign = 1.0 if rng.random() < SAND_CHUNK_UP_FRACTION else -1.0
chunks.append((px, py, h_mag * sign, sig_i))
```
The sign draw follows the position and magnitude draws in the same RNG sequence,
so the full tuple `(x, y, |h|, sigma, sign)` is fully reproducible.

**Floor guard** (in `apply_sand_texture`, section 7):
After accumulating all Gaussian contributions per top-surface vertex:
```python
trap_base_z = float(new_mesh.vertices[:, 2].min())
floor_z     = trap_base_z + SAND_CHUNK_FLOOR_THICKNESS_MM   # e.g. 0 + 0.5 = 0.5 mm
new_z = new_mesh.vertices[top_indices, 2] + dz_chunks
new_z = np.maximum(new_z, floor_z)   # clamp — no vertex below 0.5 mm
```
This ensures overlapping dimples cannot punch through the slab bottom even at
extreme `UP_FRACTION = 0.0` scenarios. For all-up chunks the guard is a no-op.

---

## Count Bump

| Constant | Before (v0.07) | After (v0.08) |
|---|---|---|
| `SAND_CHUNK_DENSITY_PER_100_MM2` | 0.3 | **0.5** |
| `SAND_CHUNK_MAX` | 20 | **30** |
| `SAND_CHUNK_MIN` | 3 | **4** |

Example count law with new density:

| Trap area | Raw count | Clamped |
|---|---|---|
| 100 mm² | round(0.5) = 1 | MIN → **4** |
| 2000 mm² | round(10) = 10 | **10** (in range) |
| 10 000 mm² | round(50) = 50 | MAX → **30** |

Height (0.6 mm) and sigma (3.0 mm) are unchanged.

---

## Red → Green Table

| Test | Class | RED state (v0.07) | GREEN (v0.08) |
|---|---|---|---|
| `test_updated_count_constants` | `TestChunkUpDown` | density=0.3, max=20, min=3 | density=0.5, max=30, min=4 |
| `test_up_fraction_constant_exists` | `TestChunkUpDown` | constant missing | `SAND_CHUNK_UP_FRACTION = 0.5` |
| `test_count_law_updated` | `TestChunkUpDown` | wrong counts | correct at new density |
| `test_both_signs_present_default_fraction` | `TestChunkUpDown` | all h > 0 | mixed signs present |
| `test_sign_assignment_reproducible` | `TestChunkUpDown` | (trivially green all-same-sign) | identical signs across 2 calls |
| `test_all_up_when_fraction_one` | `TestChunkUpDown` | fraction not respected | all h > 0 when UP_FRACTION=1.0 |
| `test_all_down_when_fraction_zero` | `TestChunkUpDown` | fraction not respected | all h < 0 when UP_FRACTION=0.0 |
| `test_floor_guard_prevents_deep_dimples` | `TestChunkUpDown` | vertices below floor | all top verts >= base + 0.5 mm |
| `test_all_up_no_floor_clamp_needed` | `TestChunkUpDown` | (new) | all-up max Z unchanged by guard |

**Existing tests updated to new constants:**
- `TestSandChunkScatter::test_chunk_constants_exist` — expected density 0.3→0.5, max 20→30, min 3→4
- `TestSandChunkScatter::test_chunk_count_law` — test cases updated for new density
- `TestRakeJitter::test_chunk_z_range_bounded` — upper bound widened for mixed-sign Z range

**Final run: 52/52 passed.**

---

## Visual Check — Firefly H14

Firefly Hole 14 has one trap, polygon area ≈ 42 610 px² (large trap).

With v0.07 (density=0.3, max=20, all up): 20 chunks, all mounds.

With v0.08 (density=0.5, max=30, 50/50):
- **30 chunks** (capped at MAX=30) — roughly 50% more bumps than before
- **12 up / 18 down** (random seed outcome for trap_index=0)
- Heights range: +0.74 mm (mound) to −0.75 mm (dimple)
- Floor guard active at base_z + 0.5 mm; none of the 30 dimples on this trap hit the floor

The printed surface will show clearly visible discrete mounds (up to ~0.74 mm
above the rake baseline) and pits/dimples (sinking up to ~0.75 mm below the
rake baseline). Overlapping same-sign chunks partly stack; overlapping
opposite-sign chunks partially cancel — realistic sand texture.

---

**Files changed:**
- `/Volumes/GIT/CLAUDE/SHARED_WORK_FOLDER/app/gradient_surface_diagnostic.py` — v0.07 → v0.08
- `/Volumes/GIT/CLAUDE/SHARED_WORK_FOLDER/app/app.py` — APP_VERSION v4.67 → v4.68
- `/Volumes/GIT/CLAUDE/SHARED_WORK_FOLDER/app/tests/test_gradient_surface_diagnostic.py` — 9 tests added, 3 tests updated
