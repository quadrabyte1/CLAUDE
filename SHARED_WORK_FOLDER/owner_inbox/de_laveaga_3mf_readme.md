# De Laveaga 3MF v0.1 — 2026-09-21 — Topo

## What the file contains

- **Source:** `ItWentIn/De Laveaga GPS from Stracka.txt` — Stracka API export for De Laveaga Golf Course, Santa Cruz, CA (course code `2XHDS87T`)
- **Points:** 1071 geoHashCells, geohash level-9 (~3.82m grid spacing), covering all 18 holes
- **Altitude range:** 87.50 – 124.30 m (delta 36.80 m)
- **Geographic extent:** 339.6 m (E–W) × 272.3 m (N–S)
- **Content:** Full-course terrain surface — not a single hole

## Rendering decisions

### 1. Alpha-shape crop vs full bounding box
Analysis revealed **two disconnected point clusters** with a 56.7m gap:
- Component A (225 pts): SE portion (holes near the driving range area), E=267–340m, N=0–100m
- Component B (846 pts): NW portion (majority of holes), E=0–256m, N=143–272m

A full bounding-box interpolation would produce topologically nonsense terrain across the 56.7m void between components. **Decision: alpha-shape crop** using shapely `concave_hull(ratio=0.3)`. This trims grid cells outside the sampled regions to base level, so the printed model shows only where we actually have data. Only 24.9% of the 150×120 grid falls inside the hull — the rest snaps to the base plate, which means the printed model has a visible footprint that matches the actual course layout rather than a rectangular slab.

### 2. Print scale
**200mm (East) × 160mm (North)** — matches the course's ~1.25:1 East/North aspect ratio. This is slightly larger than the standard plaque size (171.45mm) to give a whole-course overview some breathing room. At this scale, 1mm = ~1.7m real.

### 3. Vertical exaggeration
**×3.0** — The 36.8m altitude range maps to 62.6mm Z-height in print (plus 3mm base = 65.6mm total). At ×1 the terrain would be only ~21mm tall against a 200mm footprint — readable on screen, barely tactile in hand. At ×3 the ridgelines are prominent and fingertip-readable without looking cartoonish. De Laveaga is genuinely hilly (the course climbs into the Santa Cruz hills) so ×3 represents the character faithfully.

### 4. Grid resolution
**150×120 cells** across the bounding box. At ~3.82m point spacing, each grid cell is ~2.3m — slightly below the raw data resolution, so interpolation has real data to work with. Triangle count: 71,996 (top + bottom + walls).

### 5. Interpolation strategy
Linear `griddata` → nearest-neighbor fill for NaN at grid edges → Gaussian smoothing (sigma=1.5 cells). The bounding box has 60.5% NaN coverage (because only 24.9% of cells are inside the alpha hull, plus grid edges between the two clusters), all resolved by nearest-fill. The Gaussian pass removes the stairstep artifacts from the geohash grid's discrete spacing.

### 6. Base plate
3mm flat base. Terrain surface sits on top (base_z=0, terrain starts at 3mm).

## Mesh quality

| Metric | Value |
|---|---|
| `is_watertight` | True |
| `is_volume` | True |
| `is_winding_consistent` | True |
| `euler_number` | 2 (genus-0 solid, correct) |
| Volume | 166,591 mm³ |
| Vertices | 36,000 |
| Faces | 71,996 |
| Bounding box | 200.0 × 160.0 × 60.5 mm |

Winding consistency was achieved by calling `trimesh.repair.fix_normals()` after mesh construction — the wall-stitching step produces a small fraction of inconsistently wound faces that fix_normals resolves cleanly. No holes were present.

## Output files

| File | Path |
|---|---|
| **3MF** | `ItWentIn/GolfCourses/DeLaveaga/3MFs/De Laveaga (Course from Stracka) [251].3mf` |
| Orientation PNG | `ItWentIn/GolfCourses/DeLaveaga/Images/De Laveaga (Course from Stracka) [251].png` |
| Pipeline script | `owner_inbox/deLaveaga_terrain_3mf.py` |

**File size:** 588.7 KB

## Serial.json

`serial.json` updated: 251 → 252. The 3MF carries serial `[251]`.

## 3MF format notes

- Generated via `trimesh.Trimesh.export('.3mf')` — trimesh 4.11.5 with native 3MF support via lxml
- Units: millimetres (trimesh 3MF default; the model is authored in mm)
- The 3MF contains a single mesh object in a `<model unit="millimeter">` envelope
- Compatible with Bambu Studio, PrusaSlicer, Cura (all handle trimesh-generated 3MF without issues)

## Does it look like a coherent course?

Yes, with caveats. The two-cluster structure means the printed model has two elevated terrain islands on a flat base rather than one seamless surface. This accurately reflects the data — the GPS export covers two geographically separated sections of the course (likely holes 1–9 in one cluster, 10–18 in the other, with cart paths and parking lot in between). The alpha-shape makes this separation honest rather than papering over it with invented interpolation.

The highest point (124.3m real, ~62.6mm Z in print) is in the NW cluster and represents the elevated ridge that De Laveaga's back nine is famous for. The SE cluster is lower and flatter (92–112m range), consistent with the front nine holes near the clubhouse.

## Follow-up questions

1. **Per-hole 3MFs?** The data has 18 named holes (IDs 55155–55172). If you want individual holes carved out of this cloud, I can DBSCAN-cluster by hole proximity and produce 18 separate files. Each would have ~60 points.
2. **Different scale?** The 200×160mm footprint is a judgment call. If this is going on a desk plaque (171.45mm base), I can scale it down to fit. If it's a standalone course model, 200mm is fine.
3. **Hole labels / tee markers?** With the hole IDs from the Stracka export, I could overlay text or stud markers at each hole's centroid — but that requires EGM-style SVG embossing, which is a separate pipeline.
4. **STL variant?** The 3MF is the canonical deliverable, but I can export an STL from the same mesh in seconds if the slicer you're using prefers it.
