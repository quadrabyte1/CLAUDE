# v0.1 · EGM Trap Frame-Cap + Fringe-Height Fix · 2026-09-26

**Task #604 — Topo**  
`gradient_surface_diagnostic.py` v0.03 → v0.04 · `app.py` v4.62 → v4.63

---

## What fringe frame-cap rule was found

The fringe uses `_apply_lift_and_cap` (defined at line ~4942) in **"hard" mode**:

- **1 mm hard band** (`BOUNDARY_CAP_BAND_MM = 1.0`): vertices within 1 mm of the frame edge are clipped to `BOUNDARY_HEIGHT_CAP_MM = 9.0 mm` at full strength.
- **5 mm linear taper** (`BOUNDARY_CAP_TAPER_MM = 5.0`): vertices between 1–6 mm from the frame edge get a linearly decaying clip (full strength at 1 mm, zero at 6 mm). Interior vertices beyond 6 mm are untouched.
- **Gate**: controlled by the EGM-level `applyFringeFrameCap` flag (default `True`). When `False`, `cap_mm=None` is passed and no clipping occurs.

Key line references:
- Constants: lines 1260, 1268 (BOUNDARY_CAP_BAND_MM, BOUNDARY_CAP_TAPER_MM)
- `_apply_lift_and_cap` body: lines 4998–5041
- Pipeline call for fringe: lines 7996–8001 (gated by `apply_fringe_frame_cap`)

**Before fix (trap):** `_apply_lift_and_cap` for traps only fired inside `if _hole_water:` (line 5382 in v0.03). A trap on a non-water hole — like Firefly H14, which has both a trap and a water polygon — received the cap, but a trap on a dry hole received no cap at all. The 36%-width bevel Thomas saw was caused by the 5 mm taper acting on a narrow trap, with nothing to limit it.

---

## How it was mirrored onto traps (Part 1)

1. `export_trap_stls` gains a new keyword argument `apply_fringe_frame_cap: bool = True`.

2. The old `if _hole_water:` gate around `_apply_lift_and_cap` is **replaced** by an unconditional call:

   ```python
   touches = _polygon_touches_frame_boundary(shapely_inset)
   _apply_lift_and_cap(
       mesh,
       lift_mm=WATER_HOLE_LIFT_MM if _hole_water else 0.0,
       cap_mm=_trap_cap_mm,   # BOUNDARY_HEIGHT_CAP_MM or None
       label=...,
   )
   ```

   where `_trap_cap_mm = BOUNDARY_HEIGHT_CAP_MM if apply_fringe_frame_cap else None`.

3. The pipeline call at step [8] passes `apply_fringe_frame_cap=apply_fringe_frame_cap` (the resolved EGM flag value, already computed at line 7507).

Result: traps now use **exactly the same 1 mm hard + 5 mm taper cap at 9 mm** as fringe, gated by the same `applyFringeFrameCap` toggle. No new per-polygon flag was needed — the EGM-level flag already controls the behavior for all geometry types.

---

## How "adjoining fringe" was defined and why (Part 2)

**EGM data has no "fringe" polygon type.** The fringe is the entire annular region between the green polygon and the plaque frame, built algorithmically by `build_fringe_mesh`. There is therefore no polygon to query for "which fringe is adjacent to this trap."

The correct definition is: **fringe top-surface mesh vertices within `TRAP_FRINGE_BOUNDARY_BAND_MM` (6 mm) of the trap polygon's exterior ring.**

Rationale:
- 6 mm captures the immediately surrounding fringe cells (fringe mesh grid step ≈ 0.5 mm at 200×200 resolution over a ~100 mm print, so 6 mm gives ~12 rows of fringe cells around the trap edge — plenty of coverage).
- Querying by proximity to the **exterior ring** (not the interior) is correct: we want the fringe height at the rim of the trap, not somewhere in the middle of the trap footprint.
- The query uses `scipy.spatial.cKDTree.query_ball_point` on the trap's densified exterior ring samples (≤1 mm spacing), then collects all fringe vertices within the band and takes `max(z)`.

New constants (added near line 4815):
- `TRAP_FRINGE_BOUNDARY_BAND_MM: float = 6.0`
- `TRAP_FRINGE_OFFSET_MM: float = -2.0`

New helper function (inserted before `export_trap_stls`):
- `_compute_trap_height_from_fringe(trap_poly_mm, fringe_mesh, boundary_band_mm, offset_mm) → float`

The old interior-grid sampling (12×12 grid, `.max()`, no offset) is fully replaced by the new boundary-band sampling in `export_trap_stls`.

---

## Sequencing choice

`fringe_mesh_flat` (a `copy.deepcopy` taken at line 7803, before grass texture and before the water-hole lift) is passed to `export_trap_stls` at step [8].

This is correct: the trap height must be sized against the **same coordinate frame** as the trap slab (pre-lift, no texture displacement). After the fringe-boundary max is found, the 2 mm offset already bakes in the "trap is 2 mm below fringe rim" rule. If the water-hole lift applies, it shifts the trap and fringe uniformly upward together — the relative offset is preserved.

If we sampled from the already-lifted `fringe_mesh` instead, trap slabs would be sized 2 mm too high before their own lift was applied, producing a net +0 offset instead of −2 mm.

---

## Fallback for trap with no adjoining fringe

`_compute_trap_height_from_fringe` returns `TRAP_THICKNESS_MM` (10.0 mm) when:
- `fringe_mesh is None` (fringe build failed or not yet computed), OR
- fringe mesh has no top-surface vertices (z > 0), OR
- after the band query still finds no vertices (an impossible geometry in normal usage, but the code falls back to nearest-neighbour before giving up).

This is the same fixed-height fallback that existed before.

---

## Red → Green test table

| # | Test | RED before fix | GREEN after fix |
|---|------|---------------|-----------------|
| C1 | `test_cap_fires_without_water_when_enabled` | FAIL — cap only fired on water holes | PASS |
| C2 | `test_cap_skipped_when_apply_fringe_frame_cap_false` | PASS (already worked) | PASS |
| C3 | `test_export_trap_stls_accepts_apply_fringe_frame_cap_kwarg` | FAIL — kwarg missing | PASS |
| C4 | `test_production_code_cap_not_gated_by_hole_water` | FAIL — `apply_fringe_frame_cap` not in function body | PASS |
| D1 | `test_trap_fringe_offset_constant_exists` | FAIL — constant missing | PASS |
| D2 | `test_trap_height_is_fringe_boundary_max_minus_offset` | FAIL — helper missing | PASS |
| D3 | `test_fallback_no_fringe_mesh` | FAIL — helper missing | PASS |
| D4 | `test_multi_fringe_uses_higher_max` | FAIL — helper missing | PASS |

Full suite: **15/15 in `test_gradient_surface_diagnostic.py`**, **129/130 across all `app/tests/`** (the 1 remaining failure is a pre-existing stale version pin in `test_gps_collapse.py::test_app_version_is_v4_60` that expected v4.60 — it was failing before this change at v4.62 and is unrelated to this task).

---

## Recommendation

Regenerate **Firefly Hole 14** first.

Before this fix, its trap received `_apply_lift_and_cap` (it's a water hole), so it had the cap, but the trap height was sampled from interior fringe max (no offset). After this fix:

1. **Trap height** will be `fringe_boundary_max − 2 mm` — the trap top will sit visibly recessed below the fringe rim instead of flush with it.
2. **Frame-edge cap** behavior is unchanged for Firefly H14 (it was already getting the cap via the water path). The taper behavior is the same 1 mm + 5 mm rule.

For **dry holes with traps** (DeLaveaga H5, DeLaveaga H8, etc.): these were previously getting **no** frame-edge cap at all. After this fix, any trap vertex within 6 mm of the frame edge will be capped at 9 mm. This is the big visible correction — those traps should now terminate cleanly at the frame edge like the fringe does, with no visible chamfer.
