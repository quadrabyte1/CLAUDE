"""
Instrument the pipeline: monkey-patch apply_grass_texture to print stats
on the incoming mesh (top-surface horizontal triangles) BEFORE and AFTER
optional subdivision, then run the pipeline on Firefly Hole 14.

This tells us the actual triangle sizes at the moment grass texture is
applied — the number that matters.
"""
import os, sys, time, math, numpy as np, trimesh

REPO = "/Volumes/GIT/CLAUDE/SHARED_WORK_FOLDER"
sys.path.insert(0, os.path.join(REPO, "app"))
os.chdir(os.path.join(REPO, "app"))

import gradient_surface_diagnostic as gsd
from scipy.spatial import cKDTree

_orig_apply = gsd.apply_grass_texture

def _stats(mesh, label):
    v = mesh.vertices
    top = v[:, 2] > gsd.BASE_THICKNESS_MM
    n_top = int(top.sum())
    # Horizontal top faces
    face_normals = mesh.face_normals
    face_top = top[mesh.faces].all(axis=1)
    horiz = face_top & (face_normals[:, 2] > 0.5)
    tf = mesh.faces[horiz]
    if len(tf) == 0:
        print(f"    [{label}] no horiz top faces")
        return
    tri = v[tf]
    ab = np.linalg.norm(tri[:, 1] - tri[:, 0], axis=1)
    bc = np.linalg.norm(tri[:, 2] - tri[:, 1], axis=1)
    ca = np.linalg.norm(tri[:, 0] - tri[:, 2], axis=1)
    e = np.concatenate([ab, bc, ca])
    # XY area
    xy = tri[:, :, :2]
    v01 = xy[:, 1] - xy[:, 0]; v02 = xy[:, 2] - xy[:, 0]
    a = 0.5 * np.abs(v01[:, 0]*v02[:, 1] - v01[:, 1]*v02[:, 0])
    print(f"    [{label}] top_verts={n_top} horiz_top_faces={len(tf)} "
          f"edge_mean={e.mean():.3f} edge_median={np.median(e):.3f} "
          f"edge_max={e.max():.3f} area_mean={a.mean():.3f} area_median={np.median(a):.3f}")

def instrumented_apply(mesh, amplitude=0.5, bump_spacing=2.4, exclude_polyline_xy=None, exclude_radius_mm=0.0):
    print(f"    [instrument] BEFORE apply_grass_texture:")
    _stats(mesh, "before-grass")

    # Compute bump/vertex ratio pre-subdivide
    v = mesh.vertices
    top = v[:, 2] > gsd.BASE_THICKNESS_MM
    top_xy = v[top, :2]
    R = bump_spacing * 0.48
    x_min, x_max = top_xy[:, 0].min(), top_xy[:, 0].max()
    y_min, y_max = top_xy[:, 1].min(), top_xy[:, 1].max()
    cols = max(1, int(math.ceil((x_max - x_min) / bump_spacing)) + 1)
    rows = max(1, int(math.ceil((y_max - y_min) / bump_spacing)) + 1)
    n_bumps = cols * rows
    xs = np.linspace(x_min, x_min + (cols-1)*bump_spacing, cols)
    ys = np.linspace(y_min, y_min + (rows-1)*bump_spacing, rows)
    gx, gy = np.meshgrid(xs, ys)
    centers = np.column_stack([gx.ravel(), gy.ravel()])
    tree = cKDTree(centers)
    d, _ = tree.query(top_xy, k=1)
    hit = (d < R).sum()
    print(f"    [instrument] grass params: spacing={bump_spacing} R={R:.3f} "
          f"bumps={n_bumps} verts_in_bump={hit} "
          f"({hit/max(1,len(top_xy))*100:.1f}% of top verts) "
          f"verts_per_bump_covered={hit/max(1,n_bumps):.2f}")

    return _orig_apply(mesh, amplitude, bump_spacing, exclude_polyline_xy, exclude_radius_mm)

gsd.apply_grass_texture = instrumented_apply

# Run pipeline
egm = os.path.join(REPO, "ItWentIn/GolfCourses/Firefly/EGMs/Firefly (Hole 14).egm")
t0 = time.time()
out = gsd.run_pipeline(egm)
print(f"[done] pipeline took {time.time()-t0:.1f} s → {out}")
