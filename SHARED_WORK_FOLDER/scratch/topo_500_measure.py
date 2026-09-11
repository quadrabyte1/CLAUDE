"""
Instrument the pipeline again to measure the FIX:
- top-surface vertex count / edge stats
- grass free vs protected
- fringe build time
"""
import os, sys, time, math, numpy as np, trimesh
REPO = "/Volumes/GIT/CLAUDE/SHARED_WORK_FOLDER"
sys.path.insert(0, os.path.join(REPO, "app"))
os.chdir(os.path.join(REPO, "app"))

import gradient_surface_diagnostic as gsd
from scipy.spatial import cKDTree

_fringe_time = [None]
_orig_build = gsd.build_fringe_mesh
def _time_build(*a, **k):
    t0 = time.time()
    res = _orig_build(*a, **k)
    _fringe_time[0] = time.time() - t0
    print(f"  [instr] build_fringe_mesh took {_fringe_time[0]:.2f} s")
    return res
gsd.build_fringe_mesh = _time_build

_orig_apply = gsd.apply_grass_texture
def _capture(mesh, amplitude=0.5, bump_spacing=2.4, exclude_polyline_xy=None, exclude_radius_mm=0.0):
    v = mesh.vertices
    top = v[:, 2] > gsd.BASE_THICKNESS_MM
    n_top = int(top.sum())
    fn = mesh.face_normals
    face_top = top[mesh.faces].all(axis=1)
    horiz = face_top & (fn[:, 2] > 0.5)
    tf = mesh.faces[horiz]
    tri = v[tf]
    ab = np.linalg.norm(tri[:,1]-tri[:,0], axis=1)
    bc = np.linalg.norm(tri[:,2]-tri[:,1], axis=1)
    ca = np.linalg.norm(tri[:,0]-tri[:,2], axis=1)
    e = np.concatenate([ab, bc, ca])
    # non-degenerate edges
    e_big = e[e > 0.05]
    print(f"  [instr-BEFORE-GRASS] top_verts={n_top} horiz_top_faces={len(tf)} "
          f"edge_mean_nz={e_big.mean():.3f} edge_median_nz={np.median(e_big):.3f}")
    # free vs frozen
    top_xy = v[top, :2]
    ktree = cKDTree(exclude_polyline_xy)
    d, _ = ktree.query(top_xy, k=1)
    protect = d < exclude_radius_mm
    free = int((~protect).sum())
    print(f"  [instr-BEFORE-GRASS] seam_r={exclude_radius_mm} → protected={int(protect.sum())} free={free}")
    return _orig_apply(mesh, amplitude, bump_spacing, exclude_polyline_xy, exclude_radius_mm)
gsd.apply_grass_texture = _capture

egm = os.path.join(REPO, "ItWentIn/GolfCourses/Firefly/EGMs/Firefly (Hole 14).egm")
t0 = time.time()
out = gsd.run_pipeline(egm)
print(f"\n[done] total pipeline {time.time()-t0:.1f}s → {out}")
print(f"[done] fringe build only {_fringe_time[0]:.2f}s")
