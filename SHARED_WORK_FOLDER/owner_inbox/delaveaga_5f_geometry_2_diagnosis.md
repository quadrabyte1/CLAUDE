# Delaveaga Hole 5f — `geometry_2` "floating regions" diagnosis

**File:** `ItWentIn/GolfCourses/Delaveaga/3MFs/Delaveaga (Hole 5f) [1440].3mf`
**EGM:** `ItWentIn/GolfCourses/Delaveaga/EGMs/Delaveaga (Hole 5f).egm` (Oct 14 09:59)

## 1 — What `geometry_2` is

`geometry_2` is **Trap 1** — the top-of-image bunker. The 3MF insertion order in `gradient_surface_diagnostic.run_pipeline` (line 9904+) is: green_surface, fringe, trap_1..4. Cross-referencing mm bounds against the EGM polygons with a Y-flipped px→mm transform matches `Trap 1`'s X[-14.5,20.4] Y[60.9,85.7] against mesh bounds X[-14.72,20.43] Y[60.60,85.17] exactly. Trap 1 does extend to the top frame edge in the EGM (5 points at pixel y=0), but `_clip_polygon_to_fringe_rect` (line 6495) clips it cleanly to the fringe rectangle before extrusion — **the frame clip is not the issue.**

## 2 — Why Bambu calls it "floating"

| metric | value |
|---|---|
| triangles | 19 367 |
| connected components (`split`) | **1** (not two separate shells) |
| `is_watertight` | False |
| Euler number | 0 |
| boundary edges (count=1) | **13** |
| boundary-edge Z range | 8.98 – 9.92 mm (top surface) |
| `fill_holes()` result | still not watertight |

The 13 boundary edges form **two small topology holes in the top face**, both in the interior of the trap (not at the frame boundary):

- **Cluster A** (6 edges) near XY (2.1-4.2, 66-71), ~2 mm wide
- **Cluster B** (7 edges) near XY (8.4-16.3, 78.9-81.8), ~8 mm wide

Both clusters span the sand-rake cosine displacement (dz 0.0 – 0.9 mm), confirming they sit on the textured top surface. This matches `geometry_5` (Trap 4) which has 11 boundary edges in the same topological pattern.

## 3 — Root cause

**Thomas's hypothesis is partially right.** Trap 1 is the culprit, but **not because the frame cut-off produced a disconnected shell**. The actual cause is in `apply_sand_texture()` at `gradient_surface_diagnostic.py:7715`: the `scipy.spatial.Delaunay(all_xy)` re-triangulation of (boundary ring + interior rake grid) occasionally yields triangles whose edges don't match their neighbours cleanly, leaving pinhole topology holes. The post-repair `new_mesh.merge_vertices(digits_vertex=3)` + `fill_holes()` at line 7769 uses a 10⁻³ mm coordinate tolerance that catches float-drift seams but **cannot close holes caused by non-matching triangle topology**. This has been present at least since [1433] (same 13 + 11 boundary-edge counts across runs).

## 4 — Proposed fix (concept)

In `apply_sand_texture()` after the Delaunay step, replace the single-tolerance repair with a **constrained triangulation** approach: feed Shapely's trap polygon boundary as mandatory edges into a constrained Delaunay (e.g., `triangle` library or `shapely.ops.triangulate` with constraint lines), so every boundary ring segment is guaranteed to appear in the output triangulation. Fallback option if adding a dep is undesirable: after the current Delaunay call, iterate the boundary ring in order and explicitly stitch any ring edge that is NOT present in `tri.simplices` by inserting a fan from the adjacent interior vertex. The problem is deterministic (same holes in same locations across runs), so a verification loop asserting `is_watertight` on each trap mesh before returning is cheap insurance.

## Second pass — root cause + fix (2026-10-14, Topo)

### What the prior fix did and why it was insufficient

The first pass added `_fill_missing_ring_edges` which fanned triangles from each missing ring edge A-B to the nearest interior Delaunay vertex. That fix did close ring edges, but it introduced its own problem (adding a fan triangle (A, B, C) creates 2 new interior edges A-C, B-C — if neither was pre-existing, each becomes count=1, i.e. a NEW interior boundary edge). Meanwhile a second, deeper problem was present all along: when `scipy.spatial.Delaunay` + the centroid-outside clip dropped triangles along near-rim slivers, **some surviving triangles were left with interior count=1 edges forming a 6-vertex "slit" or 4-vertex "butterfly" quadrilateral** that no ring-edge pass could see. The RuntimeError guard the first pass added did NOT fire for [1441].3mf because the mesh was passed through `fill_holes()` which closed the SMALL slit (seeing it as a hole) but could not solve the butterfly without creating non-manifold edges, and `is_watertight` was true-ish momentarily but the final 3MF ended up with 13 boundary edges on geom_2 after the subsequent repair pass.

### Which hypothesis was right

**Hypothesis 1 was closest, with a twist.** The fan-fill was correctly computing `loops_local` (indices were right), but the *remaining* bedges after fan-fill were **not ring edges at all** — they were purely-interior boundary edges, i.e. edges between non-ring vertices on the sand grid where a Delaunay triangle had been dropped by the centroid clip. The confirming diagnostic from the regen was:
```
Sand ring-stitch: ring_edges=46 present_before=44 missing=2 added=2
Sand texture bedge forensic (n=7):
  edge (42,6514)  ... len_xy=2.3474     ← ring_vert 42 to interior 6514
  edge (42,6865)  ... len_xy=4.0591     ← ring_vert 42 to interior 6865
  edge (43,6865)  ... len_xy=3.9923     ← ring_vert 43 to interior 6865
  edge (43,6989)  ... len_xy=3.0652     ← ring_vert 43 to interior 6989
  edge (6514,6629) ... len_xy=0.7115    ← chain of interior-only bedges
  edge (6629,6866) ...
  edge (6866,6989) ...
```
These 7 bedges form a 6-vertex chain plus a 4-vertex butterfly quadrilateral straddling the ring segment 42-43. Fan-fill correctly closed the 2 missing ring edges but the OTHER edges remained. Partially hypothesis 2 was also implicated: `trimesh.repair.fill_holes` in the post-reassembly step was adding overlapping triangles that pushed one edge to count=4 (non-manifold) and `scene.add_geometry` + `_m.merge_vertices` + `.unique_faces` in the scene-wide repair didn't recover from that.

### Fix

Four changes to `app/gradient_surface_diagnostic.py`:

1. **Smarter ring-stitch**: `_fill_missing_ring_edges` now prefers an existing shared-neighbour vertex X (one that is already connected to BOTH A and B in `top_faces`) over the nearest-interior fallback. Adding (A, B, X) closes the ring edge WITHOUT introducing new boundary edges.
2. **Dropped-Delaunay-triangle resurrection**: new `_close_interior_boundary_edges` scans the pre-clip Delaunay simplex set and re-adds any triangle that would close a remaining non-ring count=1 edge, provided its centroid is inside the trap polygon and its addition doesn't push an existing edge past count=2.
3. **Iterative earcut with diagonal selection**: new `_earcut_interior_pinholes` walks interior-boundary chains, orders them CCW, and ear-clips each in 2D (XY plane). For the common 4-vertex quadrilateral case ("butterfly"), it explicitly picks the diagonal with count 0 in the current triangulation so adding both triangles keeps every edge manifold. The pass is called up to 5× so partially-closed chains converge.
4. **Non-manifold prune + fill_holes rollback**: new `_prune_non_manifold_additions` and a guard around `trimesh.repair.fill_holes` that rolls back the fill_holes additions if they introduce count≥3 edges.

The RuntimeError guard around `new_mesh.is_watertight` from the first pass stays, now a tripwire rather than a frequent crash.

### Before/after on the FINAL 3MF

| geometry | before `[1441].3mf` | after `[1456].3mf` |
|---|---|---|
| geometry_0 (green) | watertight=True, bedges=0 | watertight=True, bedges=0 |
| geometry_1 (fringe) | watertight=True, bedges=0 | watertight=True, bedges=0 |
| geometry_2 (trap_1) | **watertight=False, bedges=13** | **watertight=True, bedges=0** |
| geometry_3 (trap_2) | watertight=True, bedges=0 | watertight=True, bedges=0 |
| geometry_4 (trap_3) | watertight=True, bedges=0 | watertight=True, bedges=0 |
| geometry_5 (trap_4) | **watertight=False, bedges=11** | **watertight=True, bedges=0** |

All checks done by re-loading the FINAL 3MF with `trimesh.load(..., force='scene')` and counting `np.unique(np.sort(m.edges, axis=1), return_counts=True)[1] == 1`.

### New 3MF for Thomas

`/Volumes/GIT/CLAUDE/SHARED_WORK_FOLDER/ItWentIn/GolfCourses/Delaveaga/3MFs/Delaveaga (Hole 5f) [1456].3mf`

Re-slice this one in Bambu Studio. The "floating regions" + "empty layer between 8.9 and 9.5" warnings on geometry_2 should both be gone.
