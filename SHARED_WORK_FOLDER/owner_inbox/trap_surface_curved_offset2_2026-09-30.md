# Trap Surface: Curved Per-Point at −2 mm (v0.12)

**v0.12** | Topo | 2026-09-30

---

## Rule Change: flat min-2 → curved per-point at −2

**v0.11 behavior (task 662, flat-min):**

```
trap_Z = min(all fringe boundary Z within 6 mm band) − 2 mm
```

Single scalar applied uniformly. On a sloped fringe with low=6 mm and high=12 mm, the
trap sits at 4 mm everywhere — 2 mm below the low point but (6+2)=8 mm below the high
point. Thomas was seeing 4 mm gaps at the high side.

**v0.12 behavior (this task, per-point):**

```
trap_Z(ring_sample_k) = fringe_Z_nearest_to_k − 2 mm
interior points filled via griddata cubic
```

Each boundary ring sample looks up the single nearest fringe vertex and applies the
2 mm offset to THAT vertex's Z. The gap between the trap edge and the fringe rim is
uniform at every boundary point regardless of fringe slope.

---

## Audit Finding: What the Curved Path Was Doing Before This Fix

The original curved path (v0.09, preserved in v0.11 behind `TRAP_SURFACE_CURVED=True`)
used **max-within-band** per ring sample:

```python
ring_z_boundary[k] = fringe_top[np.array(idxs, dtype=int), 2].max()
# where idxs = all fringe verts within 6 mm of ring_sample_k
```

On a narrow trap where the 6 mm band from the low-Z boundary spans to the high-Z fringe
side, `max()` picks up the high-Z fringe and lifts the trap there. Example: trap half-width
3 mm, step fringe (left=6, right=12), band=6 mm. The left boundary sample at x=−3 has fringe
vertices up to x=+3 in its band — which are at z=12. `max` returns 12. Trap Z = 12−2 = 10 mm,
which is **above** the 6 mm fringe at that point. Gap = 6−10 = −4 mm (trap above fringe). Wrong.

The fix uses `cKDTree.query` (single nearest neighbor) instead of `query_ball_point` + `max`:

```python
_, nn_idxs = fringe_kd.query(ring_pts)
ring_z_boundary = fringe_top[nn_idxs, 2].copy()
```

Each ring sample gets the fringe Z at its own nearest point. Gap is exactly
`|TRAP_FRINGE_OFFSET_MM|` = 2 mm at every boundary point.

---

## History Table

| Version | Date | Change | TRAP_SURFACE_CURVED | TRAP_FRINGE_OFFSET_MM |
|---------|------|--------|---------------------|-----------------------|
| v0.04 | 2026-09-26 | First fringe-height trap (Part 2) | not yet | −2.0 |
| v0.05 | 2026-09-26 | Offset changed per Thomas request | not yet | −4.0 |
| v0.09 | 2026-09-28 | Curved surface (per-sample **max**) | True (default) | −4.0 |
| v0.11 | 2026-09-30 | Reverted to flat min scalar | False (default) | −2.0 |
| **v0.12** | **2026-09-30** | **Per-point nearest (this fix)** | **True (default)** | **−2.0** |

---

## Flag Behavior

`TRAP_SURFACE_CURVED` in `gradient_surface_diagnostic.py`:

| Value | Path | Trap Z |
|-------|------|--------|
| `True` (default v0.12) | per-point nearest NN | `fringe_Z_nearest − 2` at each boundary sample; griddata cubic interior |
| `False` (v0.11 path) | flat min scalar | `min(fringe boundary Z within 6mm) − 2` everywhere |

Setting `TRAP_SURFACE_CURVED = False` restores the v0.11 flat behavior exactly. The flag
follows the same pattern as `SAND_RAKE_ALIGN_TO_MAJOR_AXIS`.

---

## Red → Green Table

| # | Test | Class | RED failure | GREEN result |
|---|------|-------|-------------|--------------|
| N-1 | `test_trap_surface_curved_default_is_true` | `TestCurvedTrapSurfacePerPoint` | `TRAP_SURFACE_CURVED = False` | `True` |
| N-2 | `test_sloped_fringe_uniform_2mm_gap_at_every_point` | `TestCurvedTrapSurfacePerPoint` | left trap Z = 10 mm (6 mm above z_low fringe) | left ≈ 4 mm (2 mm below fringe) |
| M-1 | `test_trap_surface_curved_constant_exists_and_is_false` | `TestTrapSurfaceFlatMin` | `False` when `True` expected | updated to check `True` (v0.12 default) |

Plus updated tests that were locked to max-path expected values or band-based fallback semantics:
- L-2 (`test_sloped_fringe_gives_sloped_trap_surface_curved_mode`): expected Z now computed from per-point nearest fringe (not max in band); still green.
- L-3 (`test_no_adjoining_fringe_fallback_flat`): rewritten to use `fringe_mesh=None` (true no-fringe case); NN path uses any fringe when one exists.
- D-4 (`test_multi_fringe_uses_lower_min`): now explicitly sets `TRAP_SURFACE_CURVED=False` to test the v0.11 min path as a regression guard.

**Final result: 74 tests, all green.**

---

## Test Drive for Thomas

Regenerate DeLaveaga H5 or Firefly H14 via **Create New Project → Regenerate 3MF**.

What to verify:
- Trap top surface follows the slope of the surrounding fringe rim.
- At every point along the trap edge, the trap surface is approximately 2 mm below
  the neighboring fringe — not 4 mm on one side and 0 on the other.
- Rake lines and sand chunks are still visible on the curved trap surface.
- No point on the trap is above the adjacent fringe.

Web page footer shows **v4.84** after browser reload.
