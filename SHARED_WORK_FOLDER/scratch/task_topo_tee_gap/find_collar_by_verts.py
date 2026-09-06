"""Find ALL clusters of vertices at radius 3.78 (collar outer wall) to see if
there are multiple collars concatenated into the fringe."""
import sys
import numpy as np
import trimesh
from scipy.spatial import cKDTree

APP_DIR = "/Volumes/GIT/CLAUDE/SHARED_WORK_FOLDER/app"
sys.path.insert(0, APP_DIR)
from gradient_surface_diagnostic import (
    load_egm, PRINT_SIZE_MM, FRINGE_XY_EXPANSION_MM, TEE_HOLE_COLLAR_OD_MM,
)


def scene_nodes(scene):
    nodes = {}
    for n in scene.graph.nodes:
        try:
            _tf, g = scene.graph[n]
        except Exception:
            continue
        if g is not None and g in scene.geometry:
            nodes[n] = scene.geometry[g]
    return nodes


three_mf = sys.argv[1] if len(sys.argv) > 1 else "/Volumes/GIT/CLAUDE/SHARED_WORK_FOLDER/ItWentIn/GolfCourses/Firefly/3MFs/Firefly (Hole 14) [108].3mf"
egm_path = "/Volumes/GIT/CLAUDE/SHARED_WORK_FOLDER/ItWentIn/GolfCourses/Firefly/EGMs/Firefly (Hole 14).egm"

egm, _img, _gpx = load_egm(egm_path)
tee = egm["tee_hole"]
half = PRINT_SIZE_MM/2 + FRINGE_XY_EXPANSION_MM/2
cx_e = -half + float(tee["x_mm"])
cy_e = +half - float(tee["y_mm"])
r_outer = TEE_HOLE_COLLAR_OD_MM / 2

sc = trimesh.load(three_mf, force="scene")
nodes = scene_nodes(sc)
fringe = next(v for k, v in nodes.items() if "fringe" in k.lower())
V = fringe.vertices
print(f"Expected tee = ({cx_e:.4f}, {cy_e:.4f})")
print(f"Collar outer radius = {r_outer:.4f}, inner = {r_outer - 1.0:.4f}")
print(f"Fringe verts: {len(V)}")

# Split fringe into connected components
comps = fringe.split(only_watertight=False)
print(f"Fringe has {len(comps)} connected components")
for i, c in enumerate(comps):
    cv = c.vertices
    bbox = c.bounds
    xy_c = cv[:, :2].mean(axis=0)
    print(f"  comp{i}: verts={len(cv)} faces={len(c.faces)} watertight={c.is_watertight} "
          f"bounds X[{bbox[0,0]:.2f},{bbox[1,0]:.2f}] Y[{bbox[0,1]:.2f},{bbox[1,1]:.2f}] Z[{bbox[0,2]:.2f},{bbox[1,2]:.2f}] "
          f"centroid_xy=({xy_c[0]:.2f},{xy_c[1]:.2f})")
    # If small, dump the mean XY
    if len(cv) < 500:
        # Find the center (mean XY)
        _mean_x, _mean_y = cv[:, 0].mean(), cv[:, 1].mean()
        # Radii from mean
        r = np.hypot(cv[:, 0] - _mean_x, cv[:, 1] - _mean_y)
        uniq_r, cnts = np.unique(np.round(r, 3), return_counts=True)
        top = sorted(zip(cnts, uniq_r), reverse=True)[:5]
        print(f"    top radii from own mean: {[(f'r={u}', int(c)) for c, u in top]}")
