"""Test free-vert density for various pq30a<X> triangulations."""
import os, sys, time, numpy as np, trimesh
REPO = "/Volumes/GIT/CLAUDE/SHARED_WORK_FOLDER"
sys.path.insert(0, os.path.join(REPO, "app"))
os.chdir(os.path.join(REPO, "app"))

import gradient_surface_diagnostic as gsd
from scipy.spatial import cKDTree

_captured = {}

_orig_ext = gsd._replace_fringe_with_watertight_extrusion
def _capture(old, bp, fringe_max_z, label="fringe"):
    _captured['bp'] = bp
    _captured['h'] = fringe_max_z
    return _orig_ext(old, bp, fringe_max_z, label)
gsd._replace_fringe_with_watertight_extrusion = _capture

_orig_apply = gsd.apply_grass_texture
def _capture_g(mesh, amplitude=0.5, bump_spacing=2.4, exclude_polyline_xy=None, exclude_radius_mm=0.0):
    _captured['seam'] = exclude_polyline_xy.copy() if exclude_polyline_xy is not None else None
    _captured['r'] = exclude_radius_mm
    return _orig_apply(mesh, amplitude, bump_spacing, exclude_polyline_xy, exclude_radius_mm)
gsd.apply_grass_texture = _capture_g

_orig_export = trimesh.Scene.export
def _skip(self, *a, **k): return b""
trimesh.Scene.export = _skip

egm = os.path.join(REPO, "ItWentIn/GolfCourses/Firefly/EGMs/Firefly (Hole 14).egm")
try:
    gsd.run_pipeline(egm)
except Exception as e:
    print(f"err: {e}")

bp = _captured['bp']; h = _captured['h']
seam = _captured['seam']; R = _captured['r']

print(f"\n--- Free vert counts by triangle_args, with seam_r={R} ---")
for arg in ("pq30a25", "pq30a5", "pq30a2", "pq30a1", "pq30a0.5", "pq30a0.25"):
    t0 = time.time()
    try:
        m = trimesh.creation.extrude_polygon(bp, height=h, engine="triangle", triangle_args=arg)
        dt = time.time() - t0
        top = m.vertices[:, 2] > (h - 0.01)
        top_xy = m.vertices[top, :2]
        n_top = len(top_xy)
        ktree = cKDTree(seam)
        d, _ = ktree.query(top_xy, k=1)
        # radius options
        for r_try in (2.0, 1.5, 1.2):
            protect = d < r_try
            free = int((~protect).sum())
            free_xy = top_xy[~protect]
            if len(free_xy) > 3:
                kt = cKDTree(free_xy)
                dd, _ = kt.query(free_xy, k=2)
                med_nn = np.median(dd[:, 1])
            else:
                med_nn = -1
            print(f"  {arg}(t={dt:.2f}s) top={n_top} r={r_try}: free={free:>6} "
                  f"free_median_NN={med_nn:.2f} mm  → verts per 25mm² bump = {free * 25 / max(1, gsd.PRINT_SIZE_MM**2 - 3.14*30*30):.1f}")
    except Exception as e:
        print(f"  {arg}: FAIL {e}")
