# EGM Rake / Water Fix — v0.03
<!-- version badge: v0.03 / app v4.62 — 2026-09-26 -->

**Topo · Task #600 · 2026-09-26**

---

## Root Cause

Two bugs, both introduced by commit `120c069` (trap) and `aef418d` (water), both in `export_trap_stls` / `export_water_meshes` in `gradient_surface_diagnostic.py`.

**Bug 1 — Rake lines missing on sand traps.**
Commit `120c069` ("Add scripts for grass texture analysis on Firefly Hole 14") added a "per-object flatten" step immediately after `apply_sand_texture(mesh, ...)`. The flatten collapsed every top-surface vertex to `_top_min_z` (the minimum Z among top-face vertices). `apply_sand_texture` had just built a sinusoidal cosine-wave profile with amplitude 0.35 mm across the entire top face; the flatten immediately destroyed that Z variation, leaving a perfectly flat slab with no rake-line texture. The function `apply_sand_texture` itself was never broken — only the caller's post-processing step erased its work.

**Bug 2 — Water slab at wrong height (visually not smooth).**
`apply_water_ripple_texture` (added in commit `80670837`) applies a two-sine downward displacement (`dz ≤ 0`), displacing some top vertices by up to −0.28 mm. Commit `aef418d` added a flatten to the water path as a workaround, intending to make water flat. The flatten succeeded geometrically (all top verts ended at the same Z), but it collapsed to `min_z`, which is the deepest ripple point — meaning the slab sat ~0.28 mm below the fringe-sampled intended height. This caused the water mesh to sink slightly below its fringe socket on every hole. The intended behaviour (per line 5297 docstring) is "smooth flat slab" — no ripple, no flatten needed.

---

## Files Changed

| File | Change |
|---|---|
| `app/gradient_surface_diagnostic.py` | Removed 4-line post-texture flatten from `export_trap_stls`; set `WATER_RIPPLE_ENABLED = False`; removed 4-line post-ripple flatten from `export_water_meshes`; added change note in both locations; bumped version comment to **v0.03** |
| `app/app.py` | Bumped `APP_VERSION` **v4.61 → v4.62** |
| `app/tests/test_gradient_surface_diagnostic.py` | **New file** — 7 tests covering trap rake Z variation, rake peak count, static code guard (no flatten after texture), water ripple flag off, water top flatness, water height accuracy, static code guard (no post-ripple flatten) |

---

## Red → Green Test Table

| # | Test | Before fix | After fix |
|---|---|---|---|
| 1 | `TestTrapRakeLines::test_rake_z_variation_present` | GREEN (tests function alone) | GREEN |
| 2 | `TestTrapRakeLines::test_rake_peak_count_plausible` | GREEN (tests function alone) | GREEN |
| 3 | `TestTrapRakeLines::test_production_code_has_no_post_texture_flatten` | **RED** — `_top_min_z` found in trap path | GREEN |
| 4 | `TestWaterSurface::test_water_ripple_flag_is_disabled` | **RED** — `WATER_RIPPLE_ENABLED = True` | GREEN |
| 5 | `TestWaterSurface::test_water_top_is_flat` | GREEN (flatten made it flat, wrong height) | GREEN |
| 6 | `TestWaterSurface::test_water_top_height_matches_intended_slab_height` | **RED** — delta 0.279 mm > 0.01 mm | GREEN |
| 7 | `TestWaterSurface::test_production_code_has_no_post_ripple_flatten` | **RED** — `_top_min_z` found in water path | GREEN |

Full suite: **121 passed, 1 pre-existing failure** (`test_gps_collapse.py::test_app_version_is_v4_60` — stale test from task 4.60 era, already broken at v4.61, not touched).

---

## Suggested Visual Check

Regenerate **Firefly Hole 14** — it has both a trap and water polygon.

**What to look for in Bambu Studio / PrusaSlicer:**

- **Trap** (extruder 3 / tan): zoom into the top face; you should see parallel ridges running horizontally across the slab — ~17 lines across a typical trap, with peak-to-trough ~0.35 mm. They are subtle but visible on a flat face at moderate light angle.
- **Water** (extruder 4 / blue): the top face should be a perfectly flat, featureless rectangle sitting flush in its fringe socket. Check the Z bounds report in the slicer — top face should be at exactly the fringe-sampled height, not ~0.28 mm below it.

---

*Task #600 closed.*
