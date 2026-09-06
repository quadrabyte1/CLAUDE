"""Get fringe cross-section in WORLD coords (not planar-local).
Extract loops from Path3D entities directly."""
import sys
import numpy as np
import trimesh
from shapely.geometry import Polygon as ShapelyPolygon, Point as SP
from shapely.ops import unary_union

APP_DIR = "/Volumes/GIT/CLAUDE/SHARED_WORK_FOLDER/app"
sys.path.insert(0, APP_DIR)
from gradient_surface_diagnostic import (
    load_egm, PRINT_SIZE_MM, FRINGE_XY_EXPANSION_MM,
    TEE_HOLE_COLLAR_OD_MM, TEE_HOLE_DIAMETER_MM,
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
cx = -half + float(tee["x_mm"])
cy = +half - float(tee["y_mm"])
collar_r = TEE_HOLE_COLLAR_OD_MM / 2

sc = trimesh.load(three_mf, force="scene")
nodes = scene_nodes(sc)
fringe = next(v for k, v in nodes.items() if "fringe" in k.lower())
print(f"tee: ({cx:.4f}, {cy:.4f})  collar_r={collar_r:.4f}")

for z in [0.5, 1.0, 2.0, 5.0]:
    sec = fringe.section(plane_origin=[0,0,z], plane_normal=[0,0,1])
    if sec is None:
        continue
    # Get 3D vertices from Path3D directly (world coords)
    print(f"\n=== Z = {z} mm  ({len(sec.entities)} entities) ===")
    # Build 2D polygons from the world-coord vertices at this Z
    loops_xy = []
    for i, ent in enumerate(sec.entities):
        try:
            pts = sec.vertices[ent.points]
        except Exception:
            continue
        if len(pts) < 3:
            continue
        xy = pts[:, :2]
        # Compute closed area/perimeter
        loops_xy.append(xy)

    # Try to build proper polygons: each closed loop is either an exterior or interior
    print(f"  {len(loops_xy)} loops")
    # Build shapely polygons and use unary_union to combine
    polys = []
    for xy in loops_xy:
        try:
            sp = ShapelyPolygon(xy)
            if not sp.is_valid:
                sp = sp.buffer(0)
            if not sp.is_empty:
                polys.append(sp)
        except Exception as ex:
            print(f"    poly failed: {ex}")
    if not polys:
        continue
    # Look for the loops NEAR the tee
    for i, xy in enumerate(loops_xy):
        # Distance from centroid to tee
        cxi = xy[:, 0].mean(); cyi = xy[:, 1].mean()
        d = np.hypot(cxi - cx, cyi - cy)
        if d > 20:
            continue
        # Radii from mean
        r = np.hypot(xy[:, 0] - cxi, xy[:, 1] - cyi)
        # Radii from tee
        r_tee = np.hypot(xy[:, 0] - cx, xy[:, 1] - cy)
        print(f"  loop{i}: {len(xy)} pts, mean=({cxi:.4f},{cyi:.4f}) d_tee={d:.4f}")
        print(f"          r_from_mean=[{r.min():.4f},{r.max():.4f}]")
        print(f"          r_from_tee =[{r_tee.min():.4f},{r_tee.max():.4f}]")
