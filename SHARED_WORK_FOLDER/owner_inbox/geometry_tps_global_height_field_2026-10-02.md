# v0.13 — TPS Global Height Field

*Topo · 2026-10-02 · task 684*

---

## Problem statement

Thomas's report (verbatim):

> "the fringe peaks were picked up, most of them, but then the fringe altitude z-value was set right at the boundary and then dropped immediately on either side. on the green side the green didn't meet that new height and the fringe didn't trail from that new height out to the frame Or whatever is out there.
>
> So the second thing is harder, because what I'd like to do is I'd like to do all that fringe checking, setting all those altitudes, do the green checking, but then blend from a fringe height to a specific green height so we get continuous surface everywhere.
>
> In other words, nowhere can the derivative of the gradient be undefined. It has to be smooth everywhere."

Root cause: the base surface was built from two disconnected pieces — a K=24 IDW blend over fringe boundary anchor points, and a separate Poisson-integrated green surface. These two pieces met at a crease: the fringe Z jumped to the anchor value right at the boundary, then fell on either side because neither the IDW (on the fringe) nor the green surface was aware of the other. The derivative was undefined at the seam.

---

## Why TPS

Thin-plate spline (TPS) is the unique C²-smooth interpolant that minimises the integral of squared second derivatives (bending energy) while passing exactly through every constraint point. That mathematical property directly answers the "no undefined derivative anywhere" requirement. Unlike IDW, which blends locally and can produce creases where influence zones meet, TPS fits a single global function. Unlike griddata-cubic, TPS has no triangulation seam. One fit, one surface, everywhere smooth.

---

## Constraints collected

The TPS is built from three sources, merged into one constraint set:

1. **Interior elevation spikes** — every `elevationSpike` entry is converted to mm-space and added as a required height `(x_mm, y_mm, z_mm)`.
2. **Fringe boundary anchors** — every `fringeBoundaryHeight` entry is converted to mm-space, then **snapped to the nearest green-boundary polyline vertex** before being added. This is the same snap used by the prior IDW override (Approach A, task 658).
3. **Outer frame anchors** — 16 evenly-spaced points around a circle at `1.1 × frame_half_extent_mm`, all at `z = BASE_THICKNESS_MM` (1.5 mm). These prevent TPS from extrapolating arbitrarily outward past the last real constraint.

Co-located constraints (same XY within 0.05 mm) are **averaged** with a warning log before fitting.

Solver: `scipy.interpolate.RBFInterpolator(kernel="thin_plate_spline", smoothing=0.0)` — exact interpolation, no smoothing.

---

## Fallback behaviour

- **< 5 unique constraints** → TPS is underdetermined. Falls back to flat `BASE_THICKNESS_MM` and logs a message. In practice the 16 outer-frame anchors always contribute, so this path triggers only in unit tests that pass an empty fringe domain.
- **NaN or zero TPS lookup at a cell** → per-cell IDW fallback (the legacy K=24 path). Guards against any future RBF solver change without breaking the pipeline.

---

## Preserved pipelines

| Pipeline | Status |
|---|---|
| Trap surface — curved per-point (v0.12) | Unchanged. Trap reads TPS-produced fringe Z at the boundary, not raw anchor values. |
| Rake lines on trap top | Unchanged. |
| Sand chunks (±0.6 mm Gaussians) on trap top | Unchanged. |
| Dip-floor guard (per-vertex) | Unchanged. |
| Seam-reseat (fringe inner ring snapped to green polyline Z) | Unchanged. Still overrides the innermost fringe ring from `g_bdry_arr`. |
| Elevation spike Gaussian bumps | Unchanged. Post-TPS spike loop still applies; spikes are also fed into TPS as hard constraints. |
| Water — flat slab | Unchanged. `export_water_meshes` does not call `build_fringe_mesh`. |
| Plateau breaker + fringe-floor tilt | Unchanged. Floor and tilt are applied on top of the TPS-derived `green_edge_h`. |

---

## Red → Green table

| # | Test | RED reason | GREEN after |
|---|---|---|---|
| T1 | TPS fringe-anchor honored | `_build_tps_base` not found | Passes — Z at snapped boundary ≈ 8.0 ± 0.1 mm |
| T2 | TPS interior-spike honored | `_build_tps_base` not found | Passes — Z at spike ≈ 12.0 ± 0.1 mm |
| T3 | Smooth outward decay | `_build_tps_base` not found | Passes — frame edge Z ≈ BASE ± 3 mm |
| T4 | Degenerate 0 constraints | `_build_tps_base` not found | Passes — flat BASE_THICKNESS_MM |
| T5 | C1 seam continuity | `_build_tps_base` not found | Passes — max \|Δ(dZ/dx)\| < 2.0 mm/mm |
| T6 | `build_fringe_mesh` round-trip | Was passing (IDW path) | Still passes — anchor Z preserved ≈ 8.0 ± 0.5 mm |
| T7 | Trap + spike regression | Was passing | Still passes — Z range > 0.5 mm |
| T8 | Water still flat | Skipped (no pipeline context) | Expected skip — water unchanged |
| T9 | Co-located constraints averaged | `_build_tps_base` not found | Passes — no exception, Z ≈ avg |
| T10 | Only frame anchors, no blow-up | `_build_tps_base` not found | Passes — Z stays within printable range |

Existing suite: **88/88 passing** (fringe_boundary_anchors + gradient_surface_diagnostic). No regressions.

---

## Test drive for Thomas

To verify the TPS surface on DeLaveaga H5:

1. Open the Boundary Editor, load DeLaveaga Hole 5.
2. Regenerate the model (Ctrl+G or the Generate button).
3. Look at the fringe around any fringe-boundary-height markers (orange numbers on the boundary line):
   - The fringe should **rise smoothly** from the frame base up to the anchor height, with no sudden spike at the boundary.
   - On the **green side** of the seam, the green surface should meet the fringe at the same height — no step, no gap.
   - The fringe should trail **smoothly outward** toward the frame edge (decaying toward BASE_THICKNESS_MM).
   - Interior **G-spikes** should still produce their bumps on the fringe.

---

## Follow-up flag

TPS with `smoothing=0.0` passes through every constraint exactly. If two anchors are placed very close together at very different heights (e.g., two OCR readings on opposite sides of a 5-mm slope), TPS may produce a steep local gradient between them. If Thomas sees any unexpected dip below BASE_THICKNESS_MM in the fringe, increase `smoothing` from `0.0` to a small positive value (e.g., `0.5`) inside `_build_tps_base`. The current clamp (`np.clip(z_base, 0.0, BASE + elev_range + 2.0)`) catches hard undershoot but a smooth bump from `smoothing > 0` is a cleaner fix.

---

*Changes:*
- `app/gradient_surface_diagnostic.py` — v0.12 → **v0.13**; added `_build_tps_base()`; integrated into `build_fringe_mesh` (TPS replaces per-cell K=24 IDW as the `green_edge_h` source).
- `app/app.py` — APP_VERSION v4.90 → **v4.91**.
- `app/tests/test_tps_global_height_field.py` — new file, 10 tests (9 pass, 1 skip).
