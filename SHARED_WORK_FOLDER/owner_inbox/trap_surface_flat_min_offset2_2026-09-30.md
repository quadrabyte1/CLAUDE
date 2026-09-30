# v0.11 — Trap Surface: Flat Min, 2mm Offset

**2026-09-30 · Topo · Task 662**

---

## Rule Change: History Table

| Version | Rule | Anchor | Offset |
|---------|------|--------|--------|
| v0.04 | Flat scalar | max(boundary Z) | −2.0 mm |
| v0.05 | Flat scalar | max(boundary Z) | −4.0 mm |
| v0.09 | Curved per-point | fringe_Z(x,y) per boundary sample | −4.0 mm |
| **v0.11** | **Flat scalar** | **min(boundary Z)** | **−2.0 mm** |

**v0.11 rule:** `trap_top_Z = min(fringe boundary Z within 6mm of trap perimeter) − 2.0 mm`

This ensures the trap top never rises above the lowest fringe interface point around its entire perimeter. On a level course the result is identical to the v0.04 rule. On a sloped fringe the trap sits relative to the _lowest_ entry point rather than the highest, which is geometrically safer (no undercut at the low side).

---

## Flat vs Curved Flag

A module-level flag `TRAP_SURFACE_CURVED` (default `False`) controls behavior, matching the `SAND_RAKE_ALIGN_TO_MAJOR_AXIS` pattern:

```python
TRAP_SURFACE_CURVED: bool = False  # False = flat min (v0.11 default); True = per-point curved (task 654)
```

- `False` (default): `_compute_trap_surface_from_fringe` collects all boundary-band fringe Z values, takes the global `min`, subtracts 2mm, and fills the entire query array with that scalar. The slab is flat. `base_z_map=None` is passed to `apply_sand_texture`.

- `True`: restores task-654 per-point behavior. For each boundary ring sample the **max** fringe Z in the band is used (preserving the per-side max semantics from v0.04–v0.09), interior points are filled via `scipy.interpolate.griddata` cubic + linear fallback, and the result is passed as `base_z_map` to `apply_sand_texture`.

Both paths return `np.ndarray` of shape `(N,)`, keeping the caller signature identical.

---

## Preserved Interactions

| Feature | Behavior |
|---------|----------|
| Rake lines | Applied additive on the flat base (`base_z_map=None`), exactly as before task 654. |
| Sand chunks | Applied after rake, additive. Gaussian mounds ±0.6mm (unchanged). |
| Dip-floor guard | Scalar per-slab: `trap_base_z + 0.5mm`. The per-vertex curved guard (task 654) is only active when `TRAP_SURFACE_CURVED=True` and `base_z_map` is set. |
| Frame-cap suspension | `BOUNDARY_HEIGHT_CAP_ENABLED = False` unchanged — no cap applied. |
| Fallback (no fringe) | `TRAP_THICKNESS_MM = 10.0` flat slab, both curved and flat paths. |

---

## Red → Green Table

| # | Test | Before | After |
|---|------|--------|-------|
| M-1 | `TRAP_SURFACE_CURVED` constant exists, default `False` | FAIL (absent) | PASS |
| M-2 | `TRAP_FRINGE_OFFSET_MM = -2.0` | FAIL (`-4.0`) | PASS |
| M-3 | Flat surface: boundary [8,10,12,14] → Z=6.0 everywhere | FAIL (curved, wrong offset) | PASS |
| M-4 | Uses min not max: result=6 not 10/12 | FAIL (max used) | PASS |
| M-5 | Offset is 2.0mm constant + numeric (fringe_min=8 → trap=6) | FAIL (`-4.0` → result=4) | PASS |
| M-6 | Rake + chunks still visible on flat 6mm base | PASS (pre-existing) | PASS |
| M-7 | Dip-floor guard scalar: no vertex below `trap_base_z + 0.5` | PASS (pre-existing) | PASS |
| M-8 | `TRAP_SURFACE_CURVED=True` restores per-point slope | FAIL (flag absent) | PASS |
| M-9 | No-fringe fallback → `TRAP_THICKNESS_MM=10.0` | PASS (pre-existing) | PASS |

All 57 pre-existing tests maintained. Total: **66 passed, 0 failed**.

---

## Test Drive for Thomas

**Recommended holes:** DeLaveaga H5 or Firefly H14 (both have sand traps on sloped fringe).

**What to expect:**

1. Regenerate 3MF via Create New Project (boundary-classifier-tuning phase rule).
2. Open the trap STL in Bambu Studio. The trap top surface should be a **flat plane** — no visible slope or warp.
3. The height of that flat plane is `min(fringe Z around the trap perimeter) − 2mm`. On a hole where the fringe slopes, the trap will sit at the level of the *low* side of the fringe, not the high side.
4. Rake stripes and sand chunks are still present on top of the flat base — scan the surface at print scale.
5. Console output will read: `Trap 0: flat surface, height = X.XX mm (fringe_boundary_min + -2.0 mm offset)`

**To verify the curved path is still alive:** temporarily set `TRAP_SURFACE_CURVED = True` in `gradient_surface_diagnostic.py`, regenerate the same hole, and confirm the trap surface follows the fringe slope (right/high side of trap higher than left/low side). Set it back to `False` when done.

---

## Files Changed

- `/Volumes/GIT/CLAUDE/SHARED_WORK_FOLDER/app/gradient_surface_diagnostic.py` — v0.10 → v0.11 header, `TRAP_FRINGE_OFFSET_MM` -4.0 → -2.0, `TRAP_SURFACE_CURVED = False` added, `_compute_trap_surface_from_fringe` dispatches on flag, `_compute_trap_height_from_fringe` uses min/max by flag.
- `/Volumes/GIT/CLAUDE/SHARED_WORK_FOLDER/app/app.py` — `APP_VERSION` v4.81 → v4.82.
- `/Volumes/GIT/CLAUDE/SHARED_WORK_FOLDER/app/tests/test_gradient_surface_diagnostic.py` — 9 new tests (class M), 4 stale tests updated for -2.0 and min-based rule.
