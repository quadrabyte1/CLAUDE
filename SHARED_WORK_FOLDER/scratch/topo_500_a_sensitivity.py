"""Test extrude_polygon a= values on the REAL Firefly bottom_poly."""
import os, sys, time, numpy as np, trimesh
REPO = "/Volumes/GIT/CLAUDE/SHARED_WORK_FOLDER"
sys.path.insert(0, os.path.join(REPO, "app"))
os.chdir(os.path.join(REPO, "app"))

import gradient_surface_diagnostic as gsd
_captured = {}

_orig_ext = gsd._replace_fringe_with_watertight_extrusion
def _capture(old, bp, fringe_max_z, label="fringe"):
    _captured['bp'] = bp
    _captured['h'] = fringe_max_z
    return _orig_ext(old, bp, fringe_max_z, label)
gsd._replace_fringe_with_watertight_extrusion = _capture

_orig_export = trimesh.Scene.export
def _skip(self, *a, **k): return b""
trimesh.Scene.export = _skip

egm = os.path.join(REPO, "ItWentIn/GolfCourses/Firefly/EGMs/Firefly (Hole 14).egm")
try:
    gsd.run_pipeline(egm)
except Exception as e:
    print(f"err: {e}")

bp = _captured['bp']; h = _captured['h']
print(f"\n--- Testing pq30a<X> on bp area={bp.area:.1f} interiors={len(list(bp.interiors))} boundary_pts_total={len(bp.exterior.coords) + sum(len(i.coords) for i in bp.interiors)} ---\n")

for arg in ("pq30a25", "pq30a10", "pq30a5", "pq30a2", "pq30a1", "pq30a0.5"):
    t0 = time.time()
    try:
        m = trimesh.creation.extrude_polygon(bp, height=h, engine="triangle", triangle_args=arg)
        dt = time.time() - t0
        top = m.vertices[:, 2] > (h - 0.01)
        n_top = int(top.sum())
        # top face stats
        top_face = top[m.faces].all(axis=1)
        # horiz filter (nz > 0.5)
        fn = m.face_normals
        htf = top_face & (fn[:, 2] > 0.5)
        tf = m.faces[htf]
        if len(tf):
            tri = m.vertices[tf]
            ab = np.linalg.norm(tri[:,1]-tri[:,0], axis=1)
            bc = np.linalg.norm(tri[:,2]-tri[:,1], axis=1)
            ca = np.linalg.norm(tri[:,0]-tri[:,2], axis=1)
            e = np.concatenate([ab, bc, ca])
            xy = tri[:,:,:2]
            v01 = xy[:,1]-xy[:,0]; v02 = xy[:,2]-xy[:,0]
            a = 0.5 * np.abs(v01[:,0]*v02[:,1] - v01[:,1]*v02[:,0])
            print(f"  {arg}: verts={len(m.vertices):>7} faces={len(m.faces):>7} "
                  f"top_verts={n_top:>7} horiz_top_faces={len(tf):>7} "
                  f"edge_mean={e.mean():.2f} edge_median={np.median(e):.2f} "
                  f"area_mean={a.mean():.2f} area_median={np.median(a):.2f} "
                  f"time={dt:.1f}s")
    except Exception as e:
        print(f"  {arg}: FAILED {e}")
