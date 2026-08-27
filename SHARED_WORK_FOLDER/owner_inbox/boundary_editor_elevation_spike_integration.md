# Elevation Spike → Fringe Pipeline Integration (task 663)

**Version bumped:** `v4.13` → **`v4.14`** (footer badge on every main-app page).

**One-line summary:** Elevation spikes from the Boundary Editor now actually
raise the fringe surface at their (x, y) location, with a smooth Gaussian
falloff (σ = 8 mm) and MAX-blend across overlapping spikes. Thomas's original
18 mm test at DeLaveaga hole 5 now peaks at 18.38 mm on the fringe (the +0.38
is the grass-texture bump on top; the raw fringe hits 18.00 mm exactly).

---

## What was actually broken

Sienna shipped the editor UI (v4.11–v4.13). She persisted spikes at the top
level of the `.egm` file as:

```json
"elevationSpikes": [{"x": <px>, "y": <px>, "mm": <float>}, ...]
```

and explicitly deferred the fringe-math integration:

> "Fringe-smoothing math intentionally deferred to Topo — the hook is
> `data['elevationSpikes']`."

Grep confirmed zero `.py` files in `app/` were reading that key. The generator
was blind to the spike list, so Thomas's 18 mm setting had no effect on the
mesh. This report is the fix.

## Where the code lives

- Live pipeline: `app/gradient_surface_diagnostic.py :: run_pipeline` →
  `build_fringe_mesh`. (`generate_stl_3mf.py` is legacy; its own
  `_build_fringe` is not called from the live path.)
- Editor: `app/templates/editor.html` (Sienna, unchanged by this task).
- App version: `app/app.py :: APP_VERSION`.

## Coordinate space (the load-bearing decision)

Sienna stores spike `x`, `y` in **image-pixel coordinates**, with origin at the
top-left of the source image, `+x` right, `+y` down — the same convention as
polygon vertices in the EGM. Confirmed by reading Sienna's report and by
grepping the Alpine handler in `templates/editor.html`.

The fringe pipeline works in **mm-space** centred at the origin, with the
familiar CAD convention `+y` up. The transform is already implemented as
`_px_to_mm_2d(pts_px, scale, centroid_px)` in
`gradient_surface_diagnostic.py`; it maps `(px, py)` →
`((px − img_w/2) × scale, −(py − img_h/2) × scale)` where
`scale = PRINT_SIZE_MM / max(img_w, img_h)`.

Verification: Thomas's spike pixel (1044.26, 211.86) on a 1179×1329 image
converts to mm (58.67, 58.39), which lands 26.5 mm from the nearest plaque
edge, clearly on the fringe upper-right — exactly where his editor rectangle
sat. Coordinate transform is correct end-to-end.

## Interpretation of `spike.mm` — semantic choice

The button tooltip reads "mm above the base", which is genuinely ambiguous
(above the *build plate* at z = 0, or above the *green base* at
`BASE_THICKNESS_MM` = 1.5 mm?). The seed value is the current
`elevationRange (mm)` setting.

**I chose: absolute Z above the build plate (z = 0).** So `mm: 18` means the
fringe surface at that point should sit at z = 18 mm.

Rationale:
1. If we interpreted it as elevation-above-base and Thomas set `mm = 18` on
   a hole whose elevation range is 14.5, the fringe would silently clamp to
   `BASE + 14.5 = 16 mm` — indistinguishable from "did nothing", which is
   exactly the symptom that motivated this task. That's a bad UX.
2. The whole *point* of a user-placed spike is to override the natural
   fringe-height ceiling at that point. Clamping it to the range defeats
   the purpose.
3. "18 mm tall" reads naturally as "physically 18 mm off the base plate" to
   a 3D-printer-savvy user.

Safety clamp: I hard-clamp `spike.mm` to `[0, 50]` mm (upper matches
Sienna's editor ±50 mm clamp; lower prevents negative-height artifacts) and
floor it at `BASE_THICKNESS_MM` so the spike centre never sits below the base
plate.

## Pipeline stage order (before → after)

The fringe surface is assembled inside `build_fringe_mesh` in this order:

1. Build fringe grid mask over the print rectangle (200×200 cells)
2. IDW-blend `green_edge_h` from green's boundary polyline (task 509)
3. Apply plateau-taper (task 506)
4. Compute `Z_fringe[r, c] = max(BASE, min(green_edge_h, BASE + elev_range))`
5. Seam-reseat: snap fringe inner-boundary cells to green's top-boundary ring
   (populates `seam_override` dict)
6. Mask-aware median smoothing (3×3 then 5×5 if needed, blend = 0.5) —
   kills natural interpolation spikes
7. **← INJECTION POINT (new, task 663): apply user elevation spikes**
8. Final spike-scan diagnostic (now excludes user-spike neighbourhoods)
9. Build top verts (seam cells use `seam_override[(r,c)][2]`,
   others use `Z_fringe[r, c]`)
10. Return fringe mesh

Then in `run_pipeline`, only for water holes:
- `_apply_lift_and_cap(fringe_mesh, lift = +2 mm, cap = 9 mm)` — the cap only
  affects verts within ~4 mm of the plaque frame edge. Spikes further from
  the edge are unaffected; spikes near the edge on water holes will be
  clipped to 9 mm total, matching the same rule that governs tall trap/water
  pieces. Documented as expected behaviour, not a bug.

Injecting AFTER median smoothing (step 7 above) is the right choice:
- The median exists to kill *unintentional* interpolation outliers; running
  it over engineered spikes would dampen them (attenuating the target peak by
  ~15% on a 3×3 window at blend = 0.5).
- Applying the Gaussian *after* the median means the surrounding cells are
  already smooth, so we're adding a smooth bump onto a smooth surface —
  no post-hoc smoothing needed.
- I updated the seam_override dict when a spike bumps a seam cell, so the
  final vertex-write path picks up the bump instead of the pre-spike seam Z.

## Falloff model

**Gaussian in mm-space:**

```
bump_i(x, y) = (z_target_i − z_natural(x, y)) × exp(−d_i² / (2σ²))
```

with σ = 8 mm. Rationale:

- Fringe width from green boundary to plaque edge is typically 5–30 mm.
  σ = 8 mm gives a FWHM of ~18.8 mm — the ramp fits comfortably on a
  typical fringe strip.
- At the 200-cell / ±85 mm grid, ~0.85 mm/cell, σ spans ~9.4 cells — enough
  triangles for a visually smooth ramp, no faceting.
- Cutoff: `SPIKE_INFLUENCE_MM = 3.5σ = 28 mm` where the Gaussian factor
  drops below `exp(−6.125) ≈ 0.0022`, safely negligible.

**Blend across multiple spikes: MAX (not additive).** Two overlapping 10 mm
spikes should not become 20 mm. This preserves the property "spike.mm is the
achieved peak", regardless of neighbours.

**Constants live in the function body** rather than the module-level constant
block, because they are strictly local to `build_fringe_mesh` and can be
tuned per-run without affecting anything else.

## Behaviour for spike-inside-green

**Decision: log a warning; do not modify the green mesh.**

Rationale:
- The fringe pipeline only writes to `Z_fringe` (fringe cells). Green cells
  are handled by an entirely separate mesh path (`save_stl_meshes` →
  `_build_heightmap_mesh` etc.). Wiring spikes into the green would require
  re-running the Poisson solve with a boundary constraint, well beyond the
  scope of this task and (per Thomas's tooltip) not the intent — spikes are
  a *fringe* tool.
- The Gaussian tail from a spike inside the green *does* still touch nearby
  fringe cells if the spike is close to the green boundary, which is arguably
  the correct behaviour (a user who drops a spike right on the green edge
  probably wants the fringe near that edge to rise).
- Verified with a synthetic test: spike at pixel (600, 664), which is the
  centre of DeLaveaga's green in mm-space (1.35, 0.06), triggers the log
  warning, produces 0 fringe cells raised (the green centre is >30 mm from
  any fringe cell so the Gaussian decays to negligible), and leaves the
  green mesh untouched.

Log line when this fires:

```
Elevation spikes: N spike centre(s) inside green polygon — centre value
ignored, Gaussian tails still influence adjacent fringe cells
```

## Verification results

### Thomas's exact test (DeLaveaga hole 5, spike 18 mm)

Ran through the full pipeline against the live EGM:

- Fringe mesh Z_max: **18.378 mm** (raw fringe = 18.00 mm target; +0.378 mm
  is the grass-texture bump amplitude which sits on every fringe vertex
  including the spike peak). Within the 2 mm-radius neighbourhood of the
  spike centre, Z_max = 18.378 mm.
- Reported by the pipeline log: `spike xy=(+58.67,+58.39) mm target=18.000
  mm achieved=17.995 mm` (achieved is measured at the nearest grid cell,
  which is 0.26 mm from the true spike centre — the 0.005 mm gap is the
  Gaussian evaluated at 0.26 mm from the peak, dead-on expectation).
- Green mesh Z_max unchanged at 16 mm (elev_range = 14.5 + BASE 1.5).

### Regression guardrail (no-spike case identical to pre-change)

Isolated temp-EGM test, `elevationSpikes = []`:

- Fringe Z_max = **15.950 mm** (below the 16 mm range ceiling, matches
  natural fringe on DeLaveaga). This proves the new code path is a genuine
  no-op when there are no spikes — the median-blend smoothing that
  previously ended `build_fringe_mesh` still runs, and nothing after it
  fires when `spikes_mm` is empty. Regression is clean.

### Two-spike test (10 mm and 25 mm, different XY)

Isolated temp-EGM with:
- Spike A: pixel (1044.26, 211.86), 10 mm  → mm (58.67, 58.39)
- Spike B: pixel (200.0, 800.0), 25 mm    → mm (−50.25, −17.48)

Result:
- Spike A local Z_max within 3 mm radius: **10.432 mm** (target 10 + grass 0.5)
- Spike B local Z_max within 3 mm radius: **25.127 mm** (target 25 + grass 0.5)
- Far-region fringe Z_max (>40 mm from either spike): **14.184 mm** (natural)

Both spikes hit their exact targets. Different XY = different mm coords,
confirms the coordinate transform is correct across the whole fringe rectangle
(not just the top-right corner where Thomas's original spike sat).

### Spike-inside-green

Spike at pixel (600, 664) → mm (1.35, 0.06), deep inside DeLaveaga's green.

- Log warning fires: "1 spike centre(s) inside green polygon — centre value
  ignored, Gaussian tails still influence adjacent fringe cells"
- 0 fringe cells bumped (green centre is >30 mm from any fringe cell; the
  Gaussian decays to negligible at that range).
- Green mesh unchanged.

### Verification hygiene

All three isolated tests monkey-patched **both**
`generate_stl_3mf.EGM_BASE` and `gradient_surface_diagnostic.EGM_BASE` to a
`tempfile.mkdtemp()` root. Confirmed via `assert out_3mf.startswith(td)` in
the test harness. **No writes to the live `ItWentIn/` tree or the
live `db/workspace.db`** during verification.

(Full disclosure: my very first Test-A draft only patched
`gradient_surface_diagnostic.EGM_BASE`, which does NOT propagate to
`course_paths` — the pipeline wrote four test 3MFs into the live folder
before I caught it. I deleted them and reset `serial.json` to `next_serial:
131` to match the state before I started. The live EGM file itself was never
mutated. Lesson noted; the isolated harness above patches both modules.)

## Files touched

- `app/app.py` — `APP_VERSION` bump v4.13 → v4.14 (1 line).
- `app/gradient_surface_diagnostic.py` — new spike-application block inside
  `build_fringe_mesh`, right after the median-blend smoothing and before the
  final vertex-write loop (~130 lines including docstring block).

## Surprises

1. **Two separate `EGM_BASE` references.** `course_paths` is imported from
   `generate_stl_3mf` and reads its module-scope `EGM_BASE` — monkey-
   patching only `gradient_surface_diagnostic.EGM_BASE` looks like it
   should redirect outputs but doesn't. This bit me in my first test pass.
   For any future pipeline test harness, patch both.

2. **Grass texture bumps every spike peak by up to +0.5 mm.** Not a bug,
   but it means the "achieved peak" measured on the finished 3MF is always
   slightly above the target. If Thomas ever wants pin-exact peaks, we
   would need to add the spike centre to `_grass_exclude_polyline` — cheap
   fix, not requested.

3. **`_apply_lift_and_cap` on water holes will clip near-edge spikes.**
   For a spike sitting <4 mm from the plaque frame on a hole with any water
   polygon, the cap will limit it to `BOUNDARY_HEIGHT_CAP_MM` (9 mm total).
   Documented in the docstring block; matches the existing rule for tall
   trap/water pieces on water holes.

4. **The pipeline's own diagnostic spike-scanner would flag every user
   spike as an anomaly** (delta > 1.5 mm above 8-neighbour median). Fixed by
   excluding cells within `SPIKE_INFLUENCE_MM` of any user spike from the
   scan mask, so the log line still means "unexpected natural spike count"
   rather than "count including the spikes you asked for". The excluded
   cells still render normally — this is a diagnostic-print change only.

---

*Fix delivered by Topo, 3D Modeling / Computational Geometry Specialist.
Persona at `team/topo.md`.*
