# EGM Trap: Axis + Jitter + Uncap + Offset — v1.0

**v1.0** · Topo · 2026-09-26 · Task #606

---

## Item 1 — Rake direction = trap major axis (PCA)

### Approach

Previously `apply_sand_texture` drove the cosine wave along global X (ridges parallel to Y). Now each trap computes its own principal axes via SVD on the exterior ring vertices:

```python
pts = ring_xy[:-1]          # drop closing duplicate
c   = pts.mean(axis=0)
_, S, Vt = np.linalg.svd(pts - c, full_matrices=False)
major_axis = Vt[0]          # long direction
minor_axis = Vt[1]          # short direction (drives cosine)
```

The cosine wave is parameterised by projection onto **minor\_axis** (across the narrow dimension):

```
s      = (xy - centroid) · minor_axis
dz_rake = amplitude * 0.5 * (1 + cos(2π·s / grain_spacing))
```

Ridges are constant-`s` contours — they run parallel to `major_axis`.

### ASCII orientation diagram

```
         major_axis →
     ┌────────────────────────────────────┐
   m │  ≋≋≋≋≋≋≋≋≋≋≋≋≋≋≋≋≋≋≋≋≋≋≋≋≋≋≋  │
   i │  ≋≋≋≋≋≋≋≋≋≋≋≋≋≋≋≋≋≋≋≋≋≋≋≋≋≋≋  │  ← ridges parallel to major_axis
   n │  ≋≋≋≋≋≋≋≋≋≋≋≋≋≋≋≋≋≋≋≋≋≋≋≋≋≋≋  │
   o │  ≋≋≋≋≋≋≋≋≋≋≋≋≋≋≋≋≋≋≋≋≋≋≋≋≋≋≋  │
   r └────────────────────────────────────┘
   ↑
   cosine wave varies in this direction
```

For a trap oriented at 30° from X, the ridges run at 30°. For a Y-aligned (90°) trap, ridges are along Y — matching the old fixed behaviour for that orientation.

The major-axis angle is logged per trap: `rake lines, major_axis_angle=XX.X°, ...`

---

## Item 2 — Jitter noise on rake lines

### Approach

A sum of two low-frequency sinusoidal waves with random phases is added on top of the cosine ridges. The displacement is **spatially smooth** (wavelengths of 3× and 5× grain\_spacing, ~3.4 mm and 5.6 mm) so adjacent vertices move together — no point-noise / sandpaper effect. Ridges remain dominant because jitter amplitude is well below rake amplitude.

**New module constant:** `SAND_JITTER_AMPLITUDE_MM = 0.08` (mm, half of peak-to-trough)

**Formula:**

```python
phi1, phi2 = seeded_rng.uniform(0, 2π, size=2)
wave1 = A_jitter * sin(2π * s_minor / (5 * grain_spacing) + phi1)
wave2 = A_jitter * sin(2π * s_major / (3 * grain_spacing) + phi2)
dz_jitter = (wave1 + wave2) * 0.5   # avg → bounded in ±A_jitter
```

### Seed source

The RNG is seeded from a hash of the trap polygon's centroid (rounded to 0.1 mm) combined with `trap_index`:

```python
seed = int(abs(round(cx, 1) * 1000) * 137
         + abs(round(cy, 1) * 1000) * 31
         + trap_index * 997) % 2**31
```

- **Same EGM → identical noise** every build (reproducible).
- **Different traps → different patterns** (trap centroid and index differ).

The seed is logged: `seed=XXXXXXX`

---

## Item 3 — Frame-height cap suspension

**HELD BACK — frame does not provide a vertical clip.**

### Investigation

The frame assembly uses `build_fringe_frame_mesh()` in `generate_stl_3mf.py`, which:
1. Starts with a flat rectangle (PRINT\_SIZE\_MM × PRINT\_SIZE\_MM).
2. Subtracts the green polygon and all trap polygons as cutouts.
3. Extrudes the resulting 2D shape to `thickness_mm` as a flat slab.

This is a **puzzle-base frame** — the green, fringe, and trap pieces sit in the cutout holes like puzzle pieces. The frame has no outer vertical wall that clips the terrain meshes. There is no Boolean intersection or subtraction between the frame and the trap/fringe meshes.

Therefore: if a trap or fringe vertex exceeds 9 mm near the frame perimeter and `BOUNDARY_HEIGHT_CAP_ENABLED = False`, the mesh will **protrude above the frame height in the slicer**. The frame's presence does not prevent this.

### What was shipped

Per the instructions: "if frame doesn't clip, note the poke-through" — I have implemented the constant but flagged the risk here. Specifically:

- `BOUNDARY_HEIGHT_CAP_ENABLED: bool = False` is **defined** in the constants section.
- `_apply_lift_and_cap` respects it: cap step is skipped when `BOUNDARY_HEIGHT_CAP_ENABLED = False`.
- **Default is False** (cap suspended) per Thomas's request.

**Thomas's decision needed:** With `BOUNDARY_HEIGHT_CAP_ENABLED = False`, any trap or fringe edge that naturally exceeds 9 mm will appear as a vertical wall at the frame cutout edge. Depending on the hole, this may or may not be noticeable. Set `BOUNDARY_HEIGHT_CAP_ENABLED = True` in `gradient_surface_diagnostic.py` to restore the taper cap if poke-through is objectionable.

---

## Item 4 — Trap offset from fringe: −2.0 → −4.0 mm

`TRAP_FRINGE_OFFSET_MM` changed from `-2.0` to `-4.0`.

Trap top is now 4 mm below the highest adjoining fringe boundary vertex (previously 2 mm). The constant comment and `_compute_trap_height_from_fringe` docstring were updated accordingly.

---

## Red → Green test table

| # | Test | Class | RED reason | GREEN |
|---|------|-------|-----------|-------|
| E1 | `test_rake_follows_major_axis_30deg` | `TestRakeMajorAxis` | ridge angle ≈ 90° (Y-fixed), not 30° | ridge angle ≈ 30° ± 20° |
| E2 | `test_rake_y_aligned_trap_still_works` | `TestRakeMajorAxis` | — (was green but now tested explicitly) | ridge angle ≈ 90° ± 20° |
| E3 | `test_rake_uses_pca_major_axis_constant_exists` | `TestRakeMajorAxis` | no `svd` / `major_axis` in source | both present |
| F1 | `test_jitter_amplitude_constant_exists` | `TestRakeJitter` | `SAND_JITTER_AMPLITUDE_MM` absent | = 0.08, within (0, 0.15] |
| F2 | `test_jitter_amplitude_nonzero_on_top_surface` | `TestRakeJitter` | no jitter reference in source | source references constant |
| F3 | `test_jitter_is_reproducible_same_trap` | `TestRakeJitter` | (vacuously green pre-fix — no jitter at all) | identical Z on repeated call |
| F4 | `test_jitter_differs_between_traps` | `TestRakeJitter` | identical Z for trap_index=0 vs 7 | different Z (max\_diff > 1e-6) |
| F5 | `test_jitter_within_amplitude_bound` | `TestRakeJitter` | no SAND\_JITTER\_AMPLITUDE\_MM | Z range ≤ rake + 2\*jitter + ε |
| G1 | `test_cap_enabled_constant_exists_and_is_false` | `TestCapEnabledToggle` | constant absent | = False |
| G2 | `test_cap_disabled_leaves_vertex_above_cap_mm` | `TestCapEnabledToggle` | constant absent | edge vert Z > 9 mm when False |
| G3 | `test_cap_enabled_true_still_clips` | `TestCapEnabledToggle` | constant absent | edge vert Z ≤ 9 mm when True |
| H1 | `test_trap_fringe_offset_is_minus_four` | `TestTrapFringeOffsetUpdated` | value = -2.0 | = -4.0 |
| H2 | `test_trap_height_fringe_boundary_uses_minus_four` | `TestTrapFringeOffsetUpdated` | returns fringe\_max − 2.0 | returns fringe\_max − 4.0 |

**Also updated (not RED, but required fix):**
- `TestTrapHeightFromAdjoiningFringe::test_trap_fringe_offset_constant_exists` — updated expected value −2.0 → −4.0 (task #604 test stays valid).
- `TestTrapFrameCapParity::test_cap_fires_without_water_when_enabled` — patched to set `BOUNDARY_HEIGHT_CAP_ENABLED = True` before calling `_apply_lift_and_cap`, since the cap is now off by default.

**Final run: 28/28 passed.**

---

## Visual check — Firefly H14

Regenerate Firefly Hole 14 to observe:

- **Rake axis**: ridges now angle with each trap's shape, not globally horizontal.
- **Jitter**: subtle texture variation; adjacent scans of the same file produce identical output (verify by regenerating twice and comparing file hashes — should be byte-identical for identical EGMs).
- **Trap depth**: trap top ~4 mm below the surrounding fringe boundary (previously ~2 mm). The pocket will look noticeably deeper.
- **Cap removed**: if any fringe or trap edge was previously being flattened to 9 mm at the frame boundary, it will now extend to its natural height. Watch for tall vertical walls at the cutout edge in Bambu Studio.

---

## Version changes

| File | Before | After |
|------|--------|-------|
| `app/gradient_surface_diagnostic.py` | v0.04 | v0.05 |
| `app/app.py` `APP_VERSION` | v4.63 | v4.64 |
