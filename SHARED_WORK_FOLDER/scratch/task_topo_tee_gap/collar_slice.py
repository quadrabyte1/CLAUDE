"""Dump raw exterior coords of the small polygon at Z=0.5, 2.0, 5.0 near the tee."""
import sys
import numpy as np
import trimesh
from shapely.geometry import Polygon as ShapelyPolygon

APP_DIR = "/Volumes/GIT/CLAUDE/SHARED_WORK_FOLDER/app"
sys.path.insert(0, APP_DIR)
from gradient_surface_diagnostic import (
    load_egm, PRINT_SIZE_MM, FRINGE_XY_EXPANSION_MM,
    TEE_HOLE_COLLAR_OD_MM,
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


three_mf = "/Volumes/GIT/CLAUDE/SHARED_WORK_FOLDER/ItWentIn/GolfCourses/Firefly/3MFs/Firefly (Hole 14) [105].3mf"
egm_path = "/Volumes/GIT/CLAUDE/SHARED_WORK_FOLDER/ItWentIn/GolfCourses/Firefly/EGMs/Firefly (Hole 14).egm"

egm, _img, _gpx = load_egm(egm_path)
tee = egm["tee_hole"]
half = PRINT_SIZE_MM/2 + FRINGE_XY_EXPANSION_MM/2
cx = -half + float(tee["x_mm"])
cy = +half - float(tee["y_mm"])

sc = trimesh.load(three_mf, force="scene")
nodes = scene_nodes(sc)
fringe = next(v for k, v in nodes.items() if "fringe" in k.lower())
print(f"tee: ({cx:.4f}, {cy:.4f})")

for z in [0.5, 2.0, 5.0, 8.0]:
    sec = fringe.section(plane_origin=[0,0,z], plane_normal=[0,0,1])
    if sec is None:
        continue
    planar, _tf = sec.to_planar()
    # Also print the discrete entities (line loops)
    print(f"\n=== Z={z} ===")
    polys = list(planar.polygons_full)
    for pi, p in enumerate(polys):
        c = p.centroid
        if p.area > 100 or np.hypot(c.x - cx, c.y - cy) > 15:
            continue
        ec = np.array(list(p.exterior.coords))
        print(f"  poly{pi}: n_ext={len(ec)} area={p.area:.4f} centroid=({c.x:.4f},{c.y:.4f}) bounds={p.bounds}")
        # Print all points
        for i in range(min(len(ec), 12)):
            print(f"    {ec[i,0]:+.4f}, {ec[i,1]:+.4f}")
        print(f"    ...")
    # Also list raw section entities
    print(f"  raw entities (discrete lines): {len(planar.entities)}")
