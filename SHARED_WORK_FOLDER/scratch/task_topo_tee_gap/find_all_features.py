"""Enumerate ALL holes/polygons in fringe cross-section at Z=0.5 to
identify what's at (-44.34, 72.39)."""
import sys
import numpy as np
import trimesh
from shapely.geometry import Polygon as ShapelyPolygon
from shapely.ops import unary_union

APP_DIR = "/Volumes/GIT/CLAUDE/SHARED_WORK_FOLDER/app"
sys.path.insert(0, APP_DIR)
from gradient_surface_diagnostic import (
    load_egm,
    _compute_px_to_mm,
    _px_to_mm_2d,
    _poly_to_dense_px,
    PRINT_SIZE_MM,
    FRINGE_XY_EXPANSION_MM,
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


three_mf = "/Volumes/GIT/CLAUDE/SHARED_WORK_FOLDER/ItWentIn/GolfCourses/Firefly/3MFs/Firefly (Hole 14) [104].3mf"
egm_path = "/Volumes/GIT/CLAUDE/SHARED_WORK_FOLDER/ItWentIn/GolfCourses/Firefly/EGMs/Firefly (Hole 14).egm"

egm, _img, gpx = load_egm(egm_path)
scale, centroid_px = _compute_px_to_mm(gpx, egm)
tee = egm["tee_hole"]
half = PRINT_SIZE_MM / 2 + FRINGE_XY_EXPANSION_MM / 2
cx_e = -half + float(tee["x_mm"])
cy_e = +half - float(tee["y_mm"])

print(f"Expected tee (from EGM): ({cx_e:.4f}, {cy_e:.4f})")

# Compute trap and water bboxes in mm to understand what's near
for poly in egm["polygons"]:
    if poly.get("type") in ("trap", "water", "green"):
        pts_px = _poly_to_dense_px(poly)
        pts_mm = _px_to_mm_2d(pts_px, scale, centroid_px)
        sp = ShapelyPolygon(pts_mm)
        if not sp.is_valid:
            sp = sp.buffer(0)
        bbox = sp.bounds
        c = sp.centroid
        print(f"[{poly.get('type')}:{poly.get('name')}] centroid=({c.x:.3f}, {c.y:.3f}) area={sp.area:.1f} "
              f"bbox X[{bbox[0]:.1f},{bbox[2]:.1f}] Y[{bbox[1]:.1f},{bbox[3]:.1f}]")

# Distance from observed bore (-44.34, 72.39) to nearest trap/water polygon
print("\nDistance from OBSERVED_BORE (-44.34, 72.39) to each polygon:")
from shapely.geometry import Point as SP
tp = SP(-44.3388, 72.3880)
for poly in egm["polygons"]:
    if poly.get("type") in ("trap", "water"):
        pts_px = _poly_to_dense_px(poly)
        pts_mm = _px_to_mm_2d(pts_px, scale, centroid_px)
        sp = ShapelyPolygon(pts_mm)
        if not sp.is_valid:
            sp = sp.buffer(0)
        d = tp.distance(sp)
        contains = sp.contains(tp)
        print(f"  {poly.get('type')}:{poly.get('name')}  distance={d:.4f}  contains={contains}")

# Check the collar mesh position by finding tight vertex cluster with 96 verts each at
# radii 2.78, 3.78 (which we confirmed exists at expected)
sc = trimesh.load(three_mf, force="scene")
nodes = scene_nodes(sc)
fringe = next(v for k, v in nodes.items() if "fringe" in k.lower())
V = fringe.vertices
print(f"\nFringe verts: {len(V)}")

# Scan candidate centers by rounding vertex XY to 0.5 and counting vertices with radii in [2.7, 2.9]
print("\nSearching for annular collar clusters ~radius 3.78 (outer collar wall):")
# For each vertex, look at radius 3.78 from a candidate center = grid of vertex positions rounded
# Simpler: for each pair (vx, vy), test if there are ≥40 verts at distance 3.7-3.85
step = 1.0
xs = np.arange(V[:,0].min(), V[:,0].max(), step)
ys = np.arange(V[:,1].min(), V[:,1].max(), step)
# use a bounding to reduce cost: search near known-important region only
# candidates around collar tube: check near cx_e (-41.99, 61.10) and near (-44.34, 72.39)
for name, (cx, cy) in [("EGM expected", (cx_e, cy_e)),
                        ("observed bore", (-44.3388, 72.3880)),
                        ("shifted -11 in Y", (cx_e, cy_e - 11.29))]:
    dxy = np.hypot(V[:,0] - cx, V[:,1] - cy)
    band = ((dxy > 3.7) & (dxy < 3.85))
    print(f"  center=({cx:+.3f}, {cy:+.3f})  verts in [3.7, 3.85]: {int(band.sum())}")
