"""Precisely measure the XY gap between the fringe interior wall of the tee bore
and the collar tube outer wall."""
import sys, argparse
import numpy as np
import trimesh
from shapely.geometry import Polygon as ShapelyPolygon, Point as SP
from shapely.ops import unary_union

APP_DIR = "/Volumes/GIT/CLAUDE/SHARED_WORK_FOLDER/app"
sys.path.insert(0, APP_DIR)
from gradient_surface_diagnostic import (
    load_egm, PRINT_SIZE_MM, FRINGE_XY_EXPANSION_MM,
    TEE_HOLE_COLLAR_OD_MM, TEE_HOLE_DIAMETER_MM,
    BASE_THICKNESS_MM,
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


ap = argparse.ArgumentParser()
ap.add_argument("--three_mf", required=True)
ap.add_argument("--egm", required=True)
args = ap.parse_args()

egm, _img, _gpx = load_egm(args.egm)
tee = egm["tee_hole"]
half = PRINT_SIZE_MM/2 + FRINGE_XY_EXPANSION_MM/2
cx = -half + float(tee["x_mm"])
cy = +half - float(tee["y_mm"])
collar_r = TEE_HOLE_COLLAR_OD_MM / 2
inner_r = TEE_HOLE_DIAMETER_MM / 2

print(f"Tee mesh XY = ({cx:.4f}, {cy:.4f})")
print(f"Collar: inner_r={inner_r:.4f}  outer_r={collar_r:.4f}   ID={TEE_HOLE_DIAMETER_MM}  OD={TEE_HOLE_COLLAR_OD_MM}")

sc = trimesh.load(args.three_mf, force="scene")
nodes = scene_nodes(sc)
fringe = next(v for k, v in nodes.items() if "fringe" in k.lower())

# Look for the fringe HOLE around the tee. At Z close to 0 (base slab), examine each polygon's interior loops.
for z in [0.5, 1.0, 2.0, 5.0, 8.0]:
    sec = fringe.section(plane_origin=[0,0,z], plane_normal=[0,0,1])
    if sec is None:
        continue
    planar, _tf = sec.to_planar()
    polys = list(planar.polygons_full)
    print(f"\n=== Z = {z} mm  ({len(polys)} polys) ===")

    tee_pt = SP(cx, cy)
    # For every polygon and every interior hole, check if tee is inside or near
    found_bore = False
    for pi, p in enumerate(polys):
        if p.exterior is None:
            continue
        for hi, hole in enumerate(p.interiors):
            hp = ShapelyPolygon(hole)
            area = hp.area
            if area < 1 or area > 200:
                continue
            # circularity
            perim = hp.length
            circ = (4 * np.pi * area / (perim ** 2)) if perim > 0 else 0
            c = hp.centroid
            d_tc = np.hypot(c.x - cx, c.y - cy)
            print(f"  poly{pi} hole{hi}: area={area:.3f}  circ={circ:.3f}  centroid=({c.x:.4f},{c.y:.4f})  d_tee={d_tc:.4f}")
            # Radii from tee center to hole boundary
            xy = np.array(list(hole.coords))
            radii = np.hypot(xy[:,0]-cx, xy[:,1]-cy)
            r_from_centroid = np.hypot(xy[:,0]-c.x, xy[:,1]-c.y)
            print(f"    radii from tee_center: min={radii.min():.4f} mean={radii.mean():.4f} max={radii.max():.4f}")
            print(f"    radii from hole_centroid: min={r_from_centroid.min():.4f} mean={r_from_centroid.mean():.4f} max={r_from_centroid.max():.4f}")
            # If circular (>0.9) and area matches collar bore area
            expected_bore_area = np.pi * collar_r ** 2
            if 0.85 < circ < 1.1 and abs(area - expected_bore_area) < 5:
                found_bore = True
                # GAP between actual bore center and tee center
                offset_from_tee = d_tc
                fringe_bore_r = np.sqrt(area / np.pi)
                # If perfectly aligned, gap would be: fringe_bore_r - collar_r
                # If misaligned: minimum gap is fringe_bore_r - collar_r - offset
                aligned_gap = fringe_bore_r - collar_r
                worst_gap = fringe_bore_r - collar_r - offset_from_tee
                best_gap = fringe_bore_r - collar_r + offset_from_tee if offset_from_tee > 0 else aligned_gap
                print(f"    -> LOOKS LIKE THE BORE.  bore_r≈{fringe_bore_r:.4f}, offset from tee={offset_from_tee:.4f}")
                print(f"       ideal gap (bore_r-collar_r)     = {aligned_gap:+.4f} mm")
                print(f"       nearest-wall gap  (min direction) = {worst_gap:+.4f} mm  (NEGATIVE=collar collides with fringe)")
                print(f"       far-wall gap      (max direction) = {best_gap:+.4f} mm")
    if not found_bore:
        print("  ! no circular bore-sized hole found near tee")
