# v0.07 — Straight Rake + Wide Chunks

**Task #610 · Topo · 2026-09-26**

---

## Rake Revert

The PCA / SVD major-axis logic introduced in task #606 is no longer active. Rake ridges now run parallel to **Y** for every trap, regardless of trap shape or orientation.

**What got deleted vs. kept-behind-flag:**

The PCA block (SVD on exterior-ring vertices → `major_axis` / `minor_axis`) is **kept intact** inside `apply_sand_texture`, gated by a new module-level flag:

```python
SAND_RAKE_ALIGN_TO_MAJOR_AXIS: bool = False  # False = fixed Y-axis; True = PCA major axis
```

- **`False` (default / v0.07):** `major_axis = (0,1)`, `minor_axis = (1,0)`. The cosine wave is keyed on global X. Ridges are constant-X contours, i.e. straight vertical lines parallel to Y.
- **`True` (task #606 behaviour):** full SVD runs on the outer ring, the cosine wave is keyed on the minor-axis projection, ridges follow the trap's long axis.

The `major_axis_angle` log line is updated: it prints `90.0°` (fixed Y) when the flag is False, and the computed PCA angle when True. A new `pca_aligned=False/True` field is also logged.

Confirmed on Firefly H14 output:

```
Sand texture: rake lines, major_axis_angle=90.0°, pca_aligned=False, spacing=1.12 mm, amplitude=1.000 mm
```

---

## Chunk Widening

| Constant | v0.06 | v0.07 |
|---|---|---|
| `SAND_CHUNK_HEIGHT_MM` | 0.6 | **0.6** (unchanged) |
| `SAND_CHUNK_SIGMA_MM` | 1.5 | **3.0** (+1 stop) |
| `SAND_CHUNK_DENSITY_PER_100_MM2` | 0.3 | **0.3** (unchanged) |
| `SAND_CHUNK_MIN` | 3 | **3** (unchanged) |
| `SAND_CHUNK_MAX` | 20 | **20** (unchanged) |

At σ=3.0 mm the Gaussian footprint is ~6 mm at 2σ (was ~3 mm). Adjacent chunks on a 20 mm trap are more likely to overlap and stack, which is why the peak-height test upper bound is set to `amplitude + h * 1.3 * 3` (3-chunk overlap allowance, not 2).

Expected visual change: lumps are noticeably broader, spreading about twice as far from their centres. Height unchanged — they will not feel taller, just fatter.

---

## Red → Green Table

| # | Test | Class | RED reason | GREEN after |
|---|---|---|---|---|
| 1 | `test_rake_align_flag_exists_and_is_false` | `TestRakeYAxisFixed` | flag not defined | `SAND_RAKE_ALIGN_TO_MAJOR_AXIS = False` added |
| 2 | `test_rake_45deg_trap_ridges_along_y` | `TestRakeYAxisFixed` | 45° trap → ~45° ridges (PCA) | 45° trap → ~90° ridges (Y fixed) |
| 3 | `test_rake_y_axis_regression_0deg_trap` | `TestRakeYAxisFixed` | 0° trap → ~0° ridges (PCA) | 0° trap → ~90° ridges (Y fixed) |
| 4 | `test_rake_pca_code_not_in_function_body_when_flag_false` | `TestRakeYAxisFixed` | flag not in function body | `SAND_RAKE_ALIGN_TO_MAJOR_AXIS` referenced in function |
| 5 | `test_sigma_constant_is_3` | `TestChunkSigmaWidened` | `SAND_CHUNK_SIGMA_MM = 1.5` | `SAND_CHUNK_SIGMA_MM = 3.0` |
| 6 | `test_chunk_gaussian_sigma_matches_formula` | `TestChunkSigmaWidened` | r=3.0 decay = exp(-3) ≈ 0.030 (wrong) | r=3.0 decay = exp(-0.5) ≈ 0.364 (correct) |
| 7 | `test_rake_follows_major_axis_30deg` | `TestRakeMajorAxis` | expected ~30° (PCA); now expects ~90° | 30° trap → ~90° ridges (Y fixed) |
| 8 | `test_rake_uses_pca_major_axis_constant_exists` | `TestRakeMajorAxis` | flag not in function body | updated to check flag reference + PCA preserved |
| 9 | `test_chunk_constants_exist` | `TestSandChunkScatter` | `SAND_CHUNK_SIGMA_MM` expected 1.5, got 3.0 | updated expected value to 3.0 |

**Final result: 43 / 43 passed** (full `test_gradient_surface_diagnostic.py` suite).

---

## Visual Check

**Firefly H14** — confirmed via CLI (`gradient_surface_diagnostic.py "Firefly (Hole 14)"`):

```
Sand texture: rake lines, major_axis_angle=90.0°, pca_aligned=False,
              spacing=1.12 mm, amplitude=1.000 mm, ~19 lines,
              dz range [0.022, 0.973] mm on 23981 grid verts + 43 boundary ring verts
Sand texture: 4 chunk bumps applied, max bump dz=1.702 mm on 24024 top verts
```

Straight vertical (Y-axis) rakes confirmed. Chunk bumps present (max dz 1.7 mm reflects the wider σ allowing some overlap stack).

**DeLaveaga H5 / Stanford H8** — CLI blocked by pre-existing image-path mismatches (image filename in EGM does not match filename on disk; unrelated to this task). The test suite's unit tests (`TestRakeYAxisFixed`) confirm fixed-Y rake for any trap shape, including 0°, 45°, and 90° orientations.

---

## Files Changed

- `/Volumes/GIT/CLAUDE/SHARED_WORK_FOLDER/app/gradient_surface_diagnostic.py` — v0.06 → **v0.07**
- `/Volumes/GIT/CLAUDE/SHARED_WORK_FOLDER/app/app.py` — `APP_VERSION` v4.65 → **v4.66**
- `/Volumes/GIT/CLAUDE/SHARED_WORK_FOLDER/app/tests/test_gradient_surface_diagnostic.py` — 9 new/updated tests; total 43
