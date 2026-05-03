# Water Hazard Ripple Texture — Proposal

**Author:** Topo (3D Modeling / Computational Geometry Specialist)
**Date:** 2026-05-01
**Status:** Investigation + proposal — awaiting Thomas's selection before implementation

---

## 1. Current Implementation (what we'd be modifying)

| Aspect | Finding |
| --- | --- |
| Where it's built | `app/gradient_surface_diagnostic.py` → `export_water_meshes()` (line 2611) |
| Polygon source | EGM file `polygons[]` entries with `type == "water"` (16 control points, Catmull-Rom interpolated) |
| Mesh construction | `_build_slab_from_shapely(shapely_inset, water_height)` in `app/generate_stl_3mf.py` (line 222) — calls `trimesh.creation.extrude_polygon(...)`. Top face = a single triangle fan from Shapely's tessellation. Effectively flat. |
| Z elevation | `water_height` = **minimum fringe-mesh top-Z sampled over the water footprint** (12×12 grid). Sits flush with the lowest point of the surrounding fringe so the slab never pokes above terrain. |
| Inset | -0.25 mm (`PRINT_TOLERANCE_MM`) for clean fit against fringe carve-out |
| Print scale | `PRINT_SIZE_MM = 171.45` (6.75 in square). Pixel→mm scale ≈ **0.13–0.15 mm/px**. Real example: PGA West Hole 5 water is ~60 × 172 mm at print size. |
| Printer / slicer | Bambu Studio + Bambu Lab FDM (per Finn's profile). Standard PLA, 0.2 mm layer height assumed. **Reliable minimum vertical feature ≈ 0.2 mm**, lateral ≈ 0.4 mm (one nozzle width). |
| Existing precedent | `apply_sand_texture()` (line 2752) already does exactly the geometry we need for traps — rebuilds top face as a regular grid + cosine displacement + Delaunay re-triangulation + boundary-ring stitching. **The water ripple should clone this pattern.** |

**Key insight:** there is already a working displacement-texture pipeline in the codebase. We don't need to invent infrastructure — we need a new `apply_water_ripple_texture()` sibling function and one call site in `export_water_meshes()`.

---

## 2. Three Proposed Approaches

For all three: grid step ≈ 0.4 mm (one nozzle width, ~5 samples per ripple period at 2 mm wavelength). Vertex budget ≈ 60 × 172 mm / (0.4 mm)² = ~64,500 verts per water poly. Well under the 150 K cap already used for sand traps.

### A. Linear sinusoidal "wind" ripples

**What:** Two superposed sine waves running across the surface — one dominant direction plus a slight cross-wave for naturalism.

**Equation:**
```
dz(x, y) = A1 * sin(2π * (x*cos(θ1) + y*sin(θ1)) / λ1)
        + A2 * sin(2π * (x*cos(θ2) + y*sin(θ2)) / λ2 + φ)
z(x, y) = water_z + dz(x, y)
```

**Defaults:**
- `A1 = 0.25 mm`, `A2 = 0.10 mm` (peak-to-trough total ≈ 0.7 mm — visible to the eye, well above 0.2 mm layer)
- `λ1 = 6.0 mm`, `λ2 = 3.5 mm` (long primary swell + short cross-chop)
- `θ1 = 15°`, `θ2 = 105°` (nearly perpendicular)
- `φ = π/4`

**Mesh cost:** ~64 K verts, ~128 K triangles per water poly. Adds ~3 MB to a 3MF.

**Print-friendliness:** Excellent. Smooth sine slopes everywhere — max slope ≈ atan(2π·A/λ) ≈ 15° from horizontal. Zero overhangs. No bridge zones. Layer-height-friendly.

**Aesthetic:** Wind-blown lake surface. Directional, clean, looks like water moving. Reads from across the room.

**Complexity:** ~80 LOC (clone of `apply_sand_texture`, swap displacement formula). 1 call site.

---

### B. Radial concentric "droplet" ripples

**What:** Circular rings emanating from 1–3 randomly placed drop points inside the polygon — like raindrops hit the surface seconds ago.

**Equation:**
```
For each drop point (cx_k, cy_k):
  r_k(x,y) = sqrt((x-cx_k)² + (y-cy_k)²)
  ring_k(x,y) = A_k * exp(-r_k / decay_k) * cos(2π * r_k / λ_k - ω_k * t_k)

dz(x,y) = Σ_k ring_k(x,y)
z(x,y) = water_z + dz(x,y)
```

**Defaults:**
- 2 drop points, placed at random interior positions (seeded by water-poly index for reproducibility)
- `A_k = 0.30 mm` peak amplitude
- `λ_k = 4.0 mm` between rings
- `decay_k = 25 mm` (rings fade out over ~25 mm — keeps the look local rather than filling the whole pond)
- Phases offset so the two drop fields don't perfectly align

**Mesh cost:** Same as A (~64 K verts).

**Print-friendliness:** Good. Slightly steeper local slopes near each drop point (atan(2π·A/λ) ≈ 25°), but still well within FDM capability. The exponential decay means amplitude is largest near the drop and tapers off — no global overhangs.

**Aesthetic:** Distinctive "frozen moment" — a raindrop just hit the pond. More narrative than A. Risk: looks artificial if drop placement is bad. Will need a heuristic to keep drops away from the polygon edge so rings have room to develop.

**Complexity:** ~110 LOC. Slightly more tuning surface (drop count, placement seed, decay).

---

### C. Perlin / simplex noise displacement

**What:** Octave-summed coherent noise — organic, no preferred direction, looks like dappled water in still air.

**Equation:**
```
dz(x,y) = A * Σ_{i=0..N-1} (1/2^i) * noise(x * 2^i / λ, y * 2^i / λ, seed)
z(x,y) = water_z + dz(x,y)
```
where `noise()` is 2D simplex noise (e.g. `opensimplex` package).

**Defaults:**
- `A = 0.30 mm`, `N = 3` octaves, `λ = 8.0 mm` base wavelength
- `seed` = water-poly index (reproducible per build)

**Mesh cost:** Same as A.

**Print-friendliness:** Good in principle, but octave-2 component has an effective wavelength of 2 mm and amplitude 0.075 mm — features approach the 0.2 mm vertical threshold and 0.4 mm lateral resolution limit. Tunable, but easy to push past printability if amplitude is bumped.

**Aesthetic:** Subtle dappling, no clear pattern. Feels "natural" but also feels less like *water* and more like a slightly bumpy surface. Hardest of the three to make read as ripples without looking like noise.

**Complexity:** ~70 LOC + new dependency (`opensimplex` ≈ 30 KB pure-Python). Tuning is harder because you can't predict from the parameters how it will look.

---

## 3. Recommendation

**Go with Approach A — linear sinusoidal "wind" ripples.**

Reasoning:
1. **Print scale fits perfectly.** 6 mm wavelength × 0.25 mm amplitude is comfortably above FDM resolution and well below visual-distraction territory. Reads as "rippled water" at arm's length.
2. **Aesthetic match.** The rest of the model uses geometric, regular textures (sand-trap rake lines are *also* parallel cosine waves). Linear water ripples are the same visual language — they will look like a deliberate sibling, not a different artist's work.
3. **Lowest implementation risk.** Clone `apply_sand_texture()` line-for-line, swap the `sine_dz()` body to the two-sine sum, change the call from `apply_sand_texture(mesh, ...)` to `apply_water_ripple(mesh, ...)` inside `export_water_meshes()`. The triangulation, boundary stitching, watertight-merge logic is already proven on every trap currently being printed. No new dependencies.
4. **Tuning surface is small.** Two amplitudes, two wavelengths, two angles. Easy to dial in over one or two test prints. (Approach C, by contrast, has a noise field — what you change to fix one spot you've changed everywhere.)

**Estimated implementation:** ~80 LOC, one new function + one call-site change. ~30 min of coding, then one test slice in Bambu Studio to confirm the ripples actually print as intended at 0.2 mm layer height.

---

## 4. Open Questions for Thomas

1. **Wavelength preference.** I've defaulted to ~6 mm primary ripple wavelength because it reads at arm's length. Do you want it tighter (more "choppy", 3–4 mm) or longer (more "lake swell", 10–12 mm)?
2. **Amplitude appetite.** Default 0.25 mm primary amplitude is *visible but subtle*. Do you want bolder (0.5 mm — clearly textured) or whisper-soft (0.15 mm — you'd feel it under a fingernail but barely see it)?
3. **Per-hole consistency.** Should every water hazard across the entire course catalog use the same direction and wavelength (consistent "wind" across the property), or should each polygon get a different randomized angle so adjacent ponds don't look stamped from the same die?
4. **Filament colour.** Water currently routes to extruder 4 (per scene-name convention). Do we know what colour Thomas slices it as today? That affects whether the ripple shadows will read — translucent blue PLA shows ripples beautifully; deep opaque blue can swallow them.

---

## 5. If Thomas approves Approach A — implementation plan

1. Add `apply_water_ripple()` to `gradient_surface_diagnostic.py`, modeled on `apply_sand_texture()`. Swap `sine_dz` for the two-sine formula. Expose `amp_primary`, `amp_cross`, `lambda_primary`, `lambda_cross`, `theta_primary`, `theta_cross` parameters with the defaults above.
2. In `export_water_meshes()` (same file, line ~2722), after `_build_slab_from_shapely(...)`, add `mesh = apply_water_ripple(mesh, water_index=i)`.
3. Test on PGA West Hole 5 (the only water hazard in the current course set). Inspect 3MF in Bambu Studio layer preview — confirm the ripple pattern is reproduced at 0.2 mm layer height and doesn't trigger top-surface infill artifacts.
4. Iterate amplitude/wavelength based on print result if needed.

End of proposal.
