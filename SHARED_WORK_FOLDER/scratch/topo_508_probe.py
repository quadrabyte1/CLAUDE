"""
Task 508 probe: reproduce the fringe polygon build to see WHY the tee bore isn't
actually a void in the final mesh. Monkey-patch _replace_fringe_with_watertight_extrusion
to dump the incoming bottom_poly to a pickle for post-inspection.
"""
import sys, os, pickle
sys.path.insert(0, '/Volumes/GIT/CLAUDE/SHARED_WORK_FOLDER/app')

# Force water-hole scenario
os.environ['FRINGE_WATERTIGHT_REWRITE'] = '1'

import gradient_surface_diagnostic as gsd

# Monkey-patch to intercept bottom_poly
_orig_wr = gsd._replace_fringe_with_watertight_extrusion
def _patched_wr(old_mesh, bottom_poly, fringe_max_z, label="fringe"):
    dump = {
        'bottom_poly': bottom_poly,
        'fringe_max_z': fringe_max_z,
        'label': label,
    }
    with open('/Volumes/GIT/CLAUDE/SHARED_WORK_FOLDER/scratch/task_topo_tee_gap/task_508_bottom_poly.pkl', 'wb') as f:
        pickle.dump(dump, f)
    print(f"  [508 probe] intercepted bottom_poly: area={bottom_poly.area:.1f} mm² interiors={len(list(bottom_poly.interiors))}")
    return _orig_wr(old_mesh, bottom_poly, fringe_max_z, label)
gsd._replace_fringe_with_watertight_extrusion = _patched_wr

# Also intercept drill_tee_hole for logging
_orig_drill = gsd.drill_tee_hole
def _patched_drill(mesh, x_mm_from_topleft, y_mm_from_topleft, **kw):
    print(f"  [508 probe] drill_tee_hole called: xy_tl=({x_mm_from_topleft}, {y_mm_from_topleft})")
    return _orig_drill(mesh, x_mm_from_topleft, y_mm_from_topleft, **kw)
gsd.drill_tee_hole = _patched_drill

# Run pipeline on Firefly H14
egm_path = '/Volumes/GIT/CLAUDE/SHARED_WORK_FOLDER/ItWentIn/GolfCourses/Firefly/EGMs/Firefly (Hole 14).egm'
gsd.run_pipeline(egm_path)
