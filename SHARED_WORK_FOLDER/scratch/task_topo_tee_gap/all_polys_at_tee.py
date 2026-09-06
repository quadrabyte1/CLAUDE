"""List ALL polygons + interiors from cross-sections, filter to near-tee.
This should show the collar tube as its OWN polygon (annulus)."""
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
collar_r = TEE_HOLE_COLLAR_OD_MM/2

sc = trimesh.load(three_mf, force="scene")
nodes = scene_nodes(sc)
fringe = next(v for k, v in nodes.items() if "fringe" in k.lower())
print(f"tee: ({cx:.4f}, {cy:.4f})   collar_r={collar_r:.4f}")

for z in [0.5, 2.0, 5.0]:
    sec = fringe.section(plane_origin=[0,0,z], plane_normal=[0,0,1])
    if sec is None:
        continue
    planar, _tf = sec.to_planar()
    polys = list(planar.polygons_full)
    print(f"\n=== Z={z}  total polys={len(polys)} ===")
    for pi, p in enumerate(polys):
        if p.exterior is None:
            continue
        c = p.centroid
        d_c = np.hypot(c.x - cx, c.y - cy)
        # Show only near-tee polys
        if d_c > 20 and p.area > 100:
            print(f"  poly{pi}: (skipping big far poly, area={p.area:.1f})")
            continue
        print(f"  poly{pi}: area={p.area:.4f}  centroid=({c.x:.4f},{c.y:.4f})  d_tee={d_c:.4f} interiors={len(list(p.interiors))}")
        ec = np.array(list(p.exterior.coords))
        # Radii from tee center
        radii = np.hypot(ec[:,0]-cx, ec[:,1]-cy)
        # Radii from own centroid
        rc = np.hypot(ec[:,0]-c.x, ec[:,1]-c.y)
        print(f"    exterior: {len(ec)} pts, r_from_tee=[{radii.min():.4f},{radii.max():.4f}] r_from_self=[{rc.min():.4f},{rc.max():.4f}]")
        for hi, hole in enumerate(p.interiors):
            hp = ShapelyPolygon(hole)
            hc = np.array(list(hole.coords))
            hrc = np.hypot(hc[:,0]-c.x, hc[:,1]-c.y)
            hr_tee = np.hypot(hc[:,0]-cx, hc[:,1]-cy)
            print(f"    interior{hi}: {len(hc)} pts, area={hp.area:.4f}, r_from_tee=[{hr_tee.min():.4f},{hr_tee.max():.4f}] r_from_ext_centroid=[{hrc.min():.4f},{hrc.max():.4f}]")
