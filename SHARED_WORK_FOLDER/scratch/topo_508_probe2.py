"""
Task 508 probe 2: intercept EVERY stage of tee-bore polygon construction
"""
import sys, os, pickle
sys.path.insert(0, '/Volumes/GIT/CLAUDE/SHARED_WORK_FOLDER/app')

os.environ['FRINGE_WATERTIGHT_REWRITE'] = '1'

# Monkey-patch shapely ops BEFORE importing gsd... actually easier to instrument the fn source
# Instead let me just patch build_fringe_mesh
import gradient_surface_diagnostic as gsd

_orig_build = gsd.build_fringe_mesh

# Grab the source of build_fringe_mesh to see behavior — but instead, patch just the difference
# calls by intercepting Polygon.difference / union with a trace wrapper

from shapely.geometry.base import BaseGeometry
from shapely.geometry import Polygon, Point

# We want to trace only tee-related ops. Look for calls where the operand is the bore disk.
# Simpler: instrument the fringe function directly by pre-computing what the tee_cx/cy will be
# and tracking bottom_poly step-by-step by patching relevant helpers.

# Easier: dump bottom_poly at several points using file writes triggered by a global counter.
_stage_counter = [0]
_stage_dump_path = '/Volumes/GIT/CLAUDE/SHARED_WORK_FOLDER/scratch/task_topo_tee_gap/task_508_stages.pkl'

# Patch _replace_fringe_with_watertight_extrusion to STOP the pipeline early with a full dump
_orig_wr = gsd._replace_fringe_with_watertight_extrusion
_saved = {}
def _patched_wr(old_mesh, bottom_poly, fringe_max_z, label="fringe"):
    _saved['bottom_poly'] = bottom_poly
    _saved['fringe_max_z'] = fringe_max_z
    with open(_stage_dump_path, 'wb') as f:
        pickle.dump(_saved, f)
    # Also stop early
    print(f"  [508 probe] intercepted bottom_poly. Terminating pipeline early.")
    raise SystemExit(0)
gsd._replace_fringe_with_watertight_extrusion = _patched_wr

# Also patch the tee bore section by monkey-patching the module-level Polygon.union to trace
# ...simpler: import shapely.geometry and monkey-patch the .union / .difference bound methods.
# We only need visibility inside build_fringe_mesh. Instrument by patching Polygon.difference:
import shapely.geometry
_orig_diff = shapely.geometry.Polygon.difference
_orig_union = shapely.geometry.Polygon.union
_orig_inter = shapely.geometry.Polygon.intersection

def _diff_traced(self, other):
    result = _orig_diff(self, other)
    # Check if 'other' is the bore disk (small area circle near the tee)
    if hasattr(other, 'area') and 46 < other.area < 51:
        try:
            cx, cy = other.centroid.x, other.centroid.y
            print(f"  [DIFF] operand centroid=({cx:.2f},{cy:.2f}) area={other.area:.2f}")
            print(f"    self area={self.area:.2f}  self bounds={self.bounds}")
            print(f"    result area={result.area:.2f}")
            _saved['pre_bore_diff'] = shapely.geometry.Polygon(self.exterior, [i for i in self.interiors]) if hasattr(self, 'exterior') else self
            _saved['bore_disk'] = other
            _saved['post_bore_diff'] = result
        except Exception as e:
            pass
    return result
shapely.geometry.Polygon.difference = _diff_traced

def _union_traced(self, other):
    result = _orig_union(self, other)
    # Check if 'other' looks like the tee_island (~92 mm² circle)
    if hasattr(other, 'area') and 85 < other.area < 100:
        try:
            cx, cy = other.centroid.x, other.centroid.y
            print(f"  [UNION] operand centroid=({cx:.2f},{cy:.2f}) area={other.area:.2f}")
            print(f"    self area={self.area:.2f}  self bounds={self.bounds}")
            print(f"    result area={result.area:.2f}")
            _saved['pre_island_union'] = shapely.geometry.Polygon(self.exterior, [i for i in self.interiors]) if hasattr(self, 'exterior') else self
            _saved['island'] = other
            _saved['post_island_union'] = result
        except Exception as e:
            pass
    return result
shapely.geometry.Polygon.union = _union_traced

# Run Firefly H14
egm_path = '/Volumes/GIT/CLAUDE/SHARED_WORK_FOLDER/ItWentIn/GolfCourses/Firefly/EGMs/Firefly (Hole 14).egm'
try:
    gsd.run_pipeline(egm_path)
except SystemExit:
    print("[508 probe] Pipeline halted after fringe build. Dump saved.")
