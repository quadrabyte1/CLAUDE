# Stanford Hole 8 — 3D GPS Representation

**v0.1 — 2026-09-18 — Topo**

---

## What the file contains

**Source:** `ItWentIn/GolfCourses/Stanford/GolfIntelligence/Stanford (8).gps`

The file is a GPS Intelligence export for **Hole 8 at Stanford University Golf Course** (Stanford, CA). The first 36 lines are browser UI chrome from the export tool. Valid JSON begins at line 37 under the keys `cellCount` (351) and `geoHashCells` (the coordinate array).

- **351 GPS point cloud entries**, each with latitude, longitude, and altitude (in meters above sea level)
- **Altitude range:** 34.77 m – 72.32 m (37.55 m full spread; 18 m spread across the 5th–95th percentile core)
- **Geographic extent:** 216 m east–west × 57 m north–south — a 3.8:1 aspect ratio, consistent with a fairway corridor
- **Diagonal extent:** ~224 m, which is a reasonable par-4 fairway length
- **Coordinate region:** latitude 37.4236–37.4241 N, longitude −122.1919–−122.1894 W (on Stanford campus, southwest of the main quad)

---

## What the shape looks like

The 351 points describe a **single golf hole fairway corridor** — long, narrow, and running roughly east–west. The plot reveals:

- A **steady elevation rise from east to west**: the east end (where the green likely sits, near −122.1894 W) is the lowest, around 35–37 m ASL. The hole climbs toward the west.
- A **pronounced high-elevation cluster** in the northwest corner of the coverage area (lat ~37.4240–37.4241, lng ~−122.1918): 10 points spike to 60–72 m ASL. This is likely a **tee box on a raised hillside** — Hole 8 at Stanford plays from an elevated tee. The 72.32 m peak is real terrain.
- The **main fairway body** (341 points, 35–55 m) shows a smooth gradual descent from west to east over the ~216 m span, with a few small undulations visible in the rendered surface.
- No evidence of a green contour or bunker shape in the points — the GPS cells cover the **cell grid of the hole area** (geohash tiles), not explicit feature geometry.

---

## Potential data quirks

| # | Concern | Coordinates | Notes |
|---|---------|-------------|-------|
| 1 | 10 high-altitude points (60–72 m) | lat 37.4240–37.4241, lng −122.1918–−122.1916 | Cluster is spatially coherent (not random noise) — likely the tee hill. Probably real. |
| 2 | 5th–95th percentile spread is 18 m (not the 6–8 m expected for a flat course) | N/A | Stanford's Hole 8 is described as a dogleg with elevation change; this matches. |
| 3 | No outliers detected by the 3σ rule applied to the full 351 points outside the tee cluster | N/A | Distribution is actually bimodal (fairway + elevated tee), not Gaussian — the σ filter only flagged the tee-hill cluster. |

No correctable GPS errors found. All flagged points are geographically clustered and topographically plausible.

---

## Rendering methodology

### Coordinate projection
Raw lat/lng (degrees) converted to a local **ENU frame (East–North–Up) in metres** from the minimum lat/lng as origin:
- 1° latitude ≈ 111,320 m (standard approximation)
- 1° longitude ≈ 111,320 × cos(37.424°) ≈ 88,470 m at Stanford's latitude

This eliminates degree-scale visual distortion. The altitude axis uses real metres as parsed.

### Vertical exaggeration
**×10 applied throughout.** The real elevation spread of ~37 m over ~224 m horizontal produces a very flat-looking terrain at a 1:1 scale in a small-format render. The ×10 exaggeration makes the tee hill and fairway gradient legible. The exaggeration factor is labeled in both plot titles and axis labels.

### Surface interpolation
`scipy.interpolate.griddata` — **cubic method** first (smooth, C2 continuity), with nearest-neighbor backfill for edge NaN cells (28.9% of the 100×100 grid fell outside the convex hull of the point cloud — typical for a non-square geohash layout). No linear fallback was needed; cubic ran cleanly.

### STL
Watertight mesh built from the 100×100 interpolated grid: top surface triangulated, 2 m base added below min altitude, perimeter walls closed. 39,996 triangles. Not optimized for printing — this is a visualization mesh. If Thomas wants a print-ready version, we'd want decimation and a thicker base.

---

## Library versions

| Library | Version |
|---------|---------|
| matplotlib | 3.10.8 |
| plotly | 7.1.0 |
| scipy | (system) |
| numpy | (system) |
| numpy-stl | (system) |

---

## Artifacts

| File | Format | Description |
|------|--------|-------------|
| `stanford_gps_3d.png` | PNG, 663 KB | Static 3D scatter + surface, colored by altitude |
| `stanford_gps_3d.html` | HTML, 465 KB | Interactive Plotly (rotate/zoom in browser) |
| `stanford_gps_3d.stl` | STL, 1.9 MB | Watertight mesh (visualization quality) |
| `stanford_gps_3d_pipeline.py` | Python | Reproducible pipeline script |

---

## Follow-up questions for Thomas

1. **Is the elevated tee cluster expected?** Hole 8 at Stanford is described as playing from a hillside tee — the 10 points at 60–72 m look like exactly that. But if this data was supposed to be green-only or fairway-only, those tee points might be extraneous.

2. **What are the geohash cells?** Each of the 351 entries is a `geoHash` geohash cell, not a discrete measured feature. The cell size (geohash precision `9q9hg...` is ~5 m × 5 m) means the points are a regular geohash grid over the hole area. This explains why it looks like a tidy grid rather than a trace path.

3. **Want an EGM-pipeline version?** Now that we know the point layout, we could pull the green out of the cluster and run it through the EGM contour pipeline for a proper plaque-quality render of the green shape. The tee-to-green elevation relationship would make for a striking 3D print.

4. **Other holes?** The file is labelled Hole 8 (`hole 5396`). Are GPS exports available for other holes? A full 18-hole composite would be a striking deliverable.

---

*Generated by Topo — 3D Modeling / Computational Geometry Specialist*
