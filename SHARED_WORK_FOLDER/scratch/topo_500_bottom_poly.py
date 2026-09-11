"""Print size of the actual bottom_poly in Firefly Hole 14 pipeline."""
import os, sys, numpy as np
REPO = "/Volumes/GIT/CLAUDE/SHARED_WORK_FOLDER"
sys.path.insert(0, os.path.join(REPO, "app"))
os.chdir(os.path.join(REPO, "app"))

import gradient_surface_diagnostic as gsd

_orig_ext = gsd._replace_fringe_with_watertight_extrusion

def _wrap(old, bp, fringe_max_z, label="fringe"):
    print(f"  [BP-INSPECT] bottom_poly: area={bp.area:.1f} mm² "
          f"exterior_pts={len(bp.exterior.coords)} "
          f"interiors={len(list(bp.interiors))} "
          f"interior_pts_total={sum(len(i.coords) for i in bp.interiors)} "
          f"height={fringe_max_z:.2f} mm")
    return _orig_ext(old, bp, fringe_max_z, label)

gsd._replace_fringe_with_watertight_extrusion = _wrap

egm = os.path.join(REPO, "ItWentIn/GolfCourses/Firefly/EGMs/Firefly (Hole 14).egm")
# Don't write final 3MF — patch save
import trimesh
_orig_export = trimesh.Scene.export
def _no_export(self, *a, **k):
    print("  [SKIP EXPORT]")
    return b""
trimesh.Scene.export = _no_export

try:
    gsd.run_pipeline(egm)
except SystemExit:
    pass
except Exception as e:
    print(f"pipeline error: {e}")
