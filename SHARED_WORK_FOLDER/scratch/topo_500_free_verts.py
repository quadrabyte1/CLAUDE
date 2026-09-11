"""Where are the ~5K unfrozen top verts located?"""
import os, sys, numpy as np, trimesh
REPO = "/Volumes/GIT/CLAUDE/SHARED_WORK_FOLDER"
sys.path.insert(0, os.path.join(REPO, "app"))
os.chdir(os.path.join(REPO, "app"))

import gradient_surface_diagnostic as gsd
from scipy.spatial import cKDTree

_captured = {}

_orig_apply = gsd.apply_grass_texture
def _capture(mesh, amplitude=0.5, bump_spacing=2.4, exclude_polyline_xy=None, exclude_radius_mm=0.0):
    _captured['mesh'] = mesh.copy()
    _captured['seam'] = exclude_polyline_xy.copy() if exclude_polyline_xy is not None else None
    _captured['r'] = exclude_radius_mm
    return _orig_apply(mesh, amplitude, bump_spacing, exclude_polyline_xy, exclude_radius_mm)

gsd.apply_grass_texture = _capture
_orig_export = trimesh.Scene.export
def _skip(self, *a, **k): return b""
trimesh.Scene.export = _skip

egm = os.path.join(REPO, "ItWentIn/GolfCourses/Firefly/EGMs/Firefly (Hole 14).egm")
try:
    gsd.run_pipeline(egm)
except Exception as e:
    print(f"err: {e}")

mesh = _captured['mesh']
seam = _captured['seam']
R = _captured['r']
print(f"\n--- mesh at grass time: verts={len(mesh.vertices)} faces={len(mesh.faces)} ---")
print(f"    seam polyline pts: {len(seam)}  exclude radius: {R} mm")

verts = mesh.vertices
top = verts[:, 2] > gsd.BASE_THICKNESS_MM
top_xy = verts[top, :2]

# Match apply_grass_texture protect logic
ktree = cKDTree(seam)
d, _ = ktree.query(top_xy, k=1)
protect = d < R
n_free = int((~protect).sum())
print(f"    protected: {int(protect.sum())}  free: {n_free}")

# Distribution of free verts by distance from nearest seam
free_dists = d[~protect]
print(f"    free vert distances to seam: min={free_dists.min():.2f} "
      f"mean={free_dists.mean():.2f} median={np.median(free_dists):.2f} max={free_dists.max():.2f}")

# Free vert spacing
free_xy = top_xy[~protect]
if len(free_xy) > 2:
    ktree_free = cKDTree(free_xy)
    dd, _ = ktree_free.query(free_xy, k=2)
    nn = dd[:, 1]
    print(f"    free vert nearest-neighbour spacing: min={nn.min():.2f} "
          f"mean={nn.mean():.2f} median={np.median(nn):.2f} max={nn.max():.2f}")

# Try seam radius of 0.5 instead
for r_try in (1.8, 1.5, 1.2, 1.0, 0.5):
    p = d < r_try
    free_n = int((~p).sum())
    free_d = d[~p]
    if len(free_d):
        free_xy_t = top_xy[~p]
        kt = cKDTree(free_xy_t)
        dd, _ = kt.query(free_xy_t, k=2)
        nn = dd[:, 1]
        print(f"    r={r_try}: free={free_n}  free-vert median NN spacing: {np.median(nn):.2f} mm")
