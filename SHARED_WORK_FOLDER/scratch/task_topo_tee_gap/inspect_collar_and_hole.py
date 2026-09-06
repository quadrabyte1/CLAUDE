"""Inspect the collar tube vs the fringe carve-out hole separately.

The fringe mesh is fringe + collar concatenated. We need to distinguish:
  A) the collar tube (annular cylinder verts around ~cx, cy)
  B) the fringe rectangle's carve-out hole (a hole in the top surface)

Because they're concatenated, both live in fringe geometry.
"""
import sys
import numpy as np
import trimesh
from shapely.geometry import Polygon as ShapelyPolygon
from shapely.ops import unary_union

APP_DIR = "/Volumes/GIT/CLAUDE/SHARED_WORK_FOLDER/app"
sys.path.insert(0, APP_DIR)
from gradient_surface_diagnostic import (
    load_egm,
    PRINT_SIZE_MM,
    FRINGE_XY_EXPANSION_MM,
    TEE_HOLE_COLLAR_OD_MM,
    TEE_HOLE_DIAMETER_MM,
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

egm, _img, _gpx = load_egm(egm_path)
tee = egm["tee_hole"]
half = PRINT_SIZE_MM / 2 + FRINGE_XY_EXPANSION_MM / 2
cx_expected = -half + float(tee["x_mm"])
cy_expected = +half - float(tee["y_mm"])
print(f"EGM tee_hole top-left: ({tee['x_mm']}, {tee['y_mm']}) mm")
print(f"Expected mesh XY:      ({cx_expected:.4f}, {cy_expected:.4f}) mm")
print(f"half = {half:.4f}   PRINT_SIZE_MM={PRINT_SIZE_MM}  FRINGE_XY_EXPANSION_MM={FRINGE_XY_EXPANSION_MM}")

sc = trimesh.load(three_mf, force="scene")
nodes = scene_nodes(sc)
fringe = next(v for k, v in nodes.items() if "fringe" in k.lower())

# ---- Find collar tube by looking for a tight ring of vertices ----
V = fringe.vertices
# Two candidate centers: expected EGM location and the visually-observed hole (~-44.34, 72.39)
for name, (cx, cy) in [("EGM_expected", (cx_expected, cy_expected)),
                        ("observed_bore", (-44.3388, 72.3880))]:
    dxy = np.hypot(V[:, 0] - cx, V[:, 1] - cy)
    # Verts within ~outer_r + 1 mm
    near = dxy < (TEE_HOLE_COLLAR_OD_MM / 2 + 1.0)
    print(f"\n[{name}] center=({cx:.4f}, {cy:.4f})")
    print(f"  vertices within {TEE_HOLE_COLLAR_OD_MM/2 + 1.0:.2f} mm: {near.sum()}")
    if near.any():
        radii = dxy[near]
        zs = V[near, 2]
        print(f"    radii range: {radii.min():.4f} ..  {radii.max():.4f}")
        print(f"    z range:     {zs.min():.4f} ..  {zs.max():.4f}")
        # Count unique radii to identify ring structure (inner/outer walls of collar)
        # Cluster radii into 0.1 mm buckets
        rounded = np.round(radii / 0.1) * 0.1
        uniq, counts = np.unique(rounded, return_counts=True)
        top = sorted(zip(counts, uniq), reverse=True)[:5]
        print(f"    most-common radii buckets (0.1 mm): {[(f'{u:.2f}', int(c)) for c, u in top]}")

# ---- Now look at the fringe's top-surface hole (Z = 4.0 to skip base slab) ----
sec = fringe.section(plane_origin=[0, 0, 4.0], plane_normal=[0, 0, 1])
planar, _tf = sec.to_planar()
polys = list(planar.polygons_full)
print(f"\nZ=4 fringe cross-section: {len(polys)} polygons")
# find hole containing tee_expected OR near it
for pi, p in enumerate(polys):
    if p.exterior is None:
        continue
    for hi, hole in enumerate(p.interiors):
        hp = ShapelyPolygon(hole)
        c = hp.centroid
        area = hp.area
        if area > 20:  # skip micro noise
            print(f"  poly{pi} hole{hi}: area={area:.3f}  centroid=({c.x:.4f}, {c.y:.4f})")

# ---- Also check at Z=0.5 to see the fringe carve/hole area at base ----
print("\nAt Z=0.5 (base layer):")
sec = fringe.section(plane_origin=[0, 0, 0.5], plane_normal=[0, 0, 1])
planar, _tf = sec.to_planar()
polys = list(planar.polygons_full)
for pi, p in enumerate(polys):
    if p.exterior is None:
        continue
    ec = np.array(list(p.exterior.coords))
    print(f"  poly{pi}: area={p.area:.3f}  exterior_bbox X[{ec[:,0].min():.2f},{ec[:,0].max():.2f}] Y[{ec[:,1].min():.2f},{ec[:,1].max():.2f}]")
    for hi, hole in enumerate(p.interiors):
        hp = ShapelyPolygon(hole)
        c = hp.centroid
        area = hp.area
        perim = hp.length
        if area > 5:
            print(f"    hole{hi}: area={area:.3f}  centroid=({c.x:.4f}, {c.y:.4f})  perim={perim:.3f}")
