"""
Task 500 (Topo, 2026-09-09): confirm the fringe-mesh resolution mismatch
that makes grass texture render as coarse triangle spikes.

Measures on the current fringe mesh (Firefly Hole 14, latest 3MF):
  - Top-surface vertex count
  - Average top-surface triangle area / edge length
  - For a given grassSpacing, how many bump centers land, and the
    top-surface-vertex-to-bump-center ratio.

Then re-runs the pipeline WITH the proposed subdivide fix and reports
the new numbers.
"""
import os
import sys
import time
import numpy as np
import trimesh

REPO = "/Volumes/GIT/CLAUDE/SHARED_WORK_FOLDER"
sys.path.insert(0, os.path.join(REPO, "app"))

# We will inspect the LATEST Firefly Hole 14 3MF.
FIREFLY_3MF_DIR = os.path.join(REPO, "ItWentIn/GolfCourses/Firefly/3MFs")
latest = sorted(
    [f for f in os.listdir(FIREFLY_3MF_DIR) if f.endswith(".3mf")],
    key=lambda n: int(n.rsplit("[", 1)[1].rstrip("].3mf"))
)[-1]
path = os.path.join(FIREFLY_3MF_DIR, latest)
print(f"[analyze] {latest}")

scene = trimesh.load(path, process=True)
print(f"[analyze] scene geometries: {list(scene.geometry.keys())}")

fringe_key = None
for k in scene.geometry.keys():
    if k.lower().startswith("fringe"):
        fringe_key = k
        break
if fringe_key is None:
    # Fall back: pick the largest geometry (fringe frame dominates).
    largest = max(scene.geometry.keys(), key=lambda k: len(scene.geometry[k].vertices))
    fringe_key = largest
    print(f"[analyze] no name match; using largest geometry: {fringe_key}")

fringe = scene.geometry[fringe_key]
print(f"[fringe] verts={len(fringe.vertices)}  faces={len(fringe.faces)}")

# -- Top surface = z > BASE_THICKNESS_MM (assume 1.5) --
BASE = 1.5
verts = fringe.vertices
faces = fringe.faces
top_v_mask = verts[:, 2] > BASE
n_top_v = int(top_v_mask.sum())
print(f"[fringe] top-surface verts (z>{BASE}): {n_top_v}")

# Top faces = all three verts above base
face_top_mask = top_v_mask[faces].all(axis=1)
top_faces = faces[face_top_mask]
print(f"[fringe] top-surface faces (all verts z>base): {len(top_faces)}")

# Restrict to horizontal-ish top faces (normal.z > 0.5) — this excludes
# vertical walls that happen to have all three verts above base.
face_normals = fringe.face_normals[face_top_mask]
horiz_mask = face_normals[:, 2] > 0.5
top_faces = top_faces[horiz_mask]
print(f"[fringe] top-surface horizontal faces (nz>0.5): {len(top_faces)}")

# Triangle area + edge length stats
tri_v = verts[top_faces]  # (F,3,3)
a = tri_v[:, 0]
b = tri_v[:, 1]
c = tri_v[:, 2]
edge_ab = np.linalg.norm(b - a, axis=1)
edge_bc = np.linalg.norm(c - b, axis=1)
edge_ca = np.linalg.norm(a - c, axis=1)
all_edges = np.concatenate([edge_ab, edge_bc, edge_ca])
print(f"[fringe] edge length (mm): min={all_edges.min():.3f}  "
      f"mean={all_edges.mean():.3f}  median={np.median(all_edges):.3f}  "
      f"max={all_edges.max():.3f}")

# 2D triangle area (XY only, matches grass footprint)
ax_xy = tri_v[:, :, :2]
v01 = ax_xy[:, 1] - ax_xy[:, 0]
v02 = ax_xy[:, 2] - ax_xy[:, 0]
xy_area = 0.5 * np.abs(v01[:, 0] * v02[:, 1] - v01[:, 1] * v02[:, 0])
print(f"[fringe] XY triangle area (mm²): min={xy_area.min():.6f}  "
      f"mean={xy_area.mean():.3f}  median={np.median(xy_area):.3f}  "
      f"max={xy_area.max():.3f}")
print(f"[fringe] XY area percentiles: p10={np.percentile(xy_area,10):.3f} "
      f"p25={np.percentile(xy_area,25):.3f} "
      f"p50={np.percentile(xy_area,50):.3f} "
      f"p75={np.percentile(xy_area,75):.3f} "
      f"p90={np.percentile(xy_area,90):.3f}")
# Non-degenerate only
big = xy_area[xy_area > 0.01]
print(f"[fringe] XY area (>0.01 mm² only, n={len(big)}): "
      f"mean={big.mean():.3f} median={np.median(big):.3f} "
      f"p25={np.percentile(big,25):.3f} p75={np.percentile(big,75):.3f}")

# Edge stats non-degenerate
big_e = all_edges[all_edges > 0.05]
print(f"[fringe] edge len (>0.05 mm only, n={len(big_e)}): "
      f"mean={big_e.mean():.3f} median={np.median(big_e):.3f}")

# -- Grass bump-center analysis --
# apply_grass_texture: bump R = spacing * 0.48. Vertex within R contributes.
for spacing in (1.0, 2.4, 5.0):
    R = spacing * 0.48
    top_xy = verts[top_v_mask, :2]
    x_min, x_max = top_xy[:, 0].min(), top_xy[:, 0].max()
    y_min, y_max = top_xy[:, 1].min(), top_xy[:, 1].max()

    import math
    cols = max(1, int(math.ceil((x_max - x_min) / spacing)) + 1)
    rows = max(1, int(math.ceil((y_max - y_min) / spacing)) + 1)
    n_bumps = cols * rows

    # Verts within bump radius of nearest center: use KDTree
    from scipy.spatial import cKDTree
    xs_centers = np.linspace(x_min, x_min + (cols - 1) * spacing, cols)
    ys_centers = np.linspace(y_min, y_min + (rows - 1) * spacing, rows)
    gx, gy = np.meshgrid(xs_centers, ys_centers)
    centers = np.column_stack([gx.ravel(), gy.ravel()])
    tree = cKDTree(centers)
    d, _ = tree.query(top_xy, k=1)
    n_hit = int((d < R).sum())
    print(f"[grass spacing={spacing}mm R={R:.3f}mm] "
          f"bumps={n_bumps}  top-verts-in-any-bump={n_hit}  "
          f"({n_hit / max(1, n_top_v) * 100:.1f}% of top verts)  "
          f"verts-per-bump-avg={n_hit / max(1, n_bumps):.2f}")

# -- Estimate seam-vertex density near green boundary --
# Load EGM to get green boundary in mm
print("\n[analyze] seam vertex density near green boundary")
# Approximate by looking at verts near the largest concave hole in the
# fringe top mesh: find edges belonging to only one top face.
from collections import defaultdict
edge_count = defaultdict(int)
for f in top_faces:
    for e in ((f[0], f[1]), (f[1], f[2]), (f[2], f[0])):
        edge_count[tuple(sorted(e))] += 1
boundary_verts = set()
for (u, v), n in edge_count.items():
    if n == 1:
        boundary_verts.add(u)
        boundary_verts.add(v)
print(f"[fringe] top-surface boundary verts: {len(boundary_verts)}")

# Break boundary verts by distance to (0,0) to guess which loop:
bv = np.array(sorted(boundary_verts))
bv_xy = verts[bv, :2]
d_from_origin = np.linalg.norm(bv_xy, axis=1)
# Inner (near green/traps) vs outer (frame ~85mm)
inner_bv = bv[d_from_origin < 75]  # loose: anything inside the rectangle
outer_bv = bv[d_from_origin >= 75]
print(f"[fringe] boundary verts: inner={len(inner_bv)}  outer={len(outer_bv)}")

# For inner boundary verts, estimate spacing along the loop
if len(inner_bv) > 3:
    from scipy.spatial import cKDTree
    inner_xy = verts[inner_bv, :2]
    ktree = cKDTree(inner_xy)
    dists, _ = ktree.query(inner_xy, k=2)  # k=1 is self, k=2 is nearest neighbour
    nn = dists[:, 1]
    print(f"[fringe] inner boundary vert nearest-neighbour spacing (mm): "
          f"min={nn.min():.3f}  mean={nn.mean():.3f}  median={np.median(nn):.3f}")
