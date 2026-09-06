"""Find the actual XY center of the collar bore in the 3MF, compare to the
computed tee-hole location from the EGM."""
import sys
import numpy as np
import trimesh
from shapely.geometry import Polygon as ShapelyPolygon, Point as ShapelyPoint
from shapely.ops import unary_union

APP_DIR = "/Volumes/GIT/CLAUDE/SHARED_WORK_FOLDER/app"
sys.path.insert(0, APP_DIR)
from gradient_surface_diagnostic import (
    load_egm,
    PRINT_SIZE_MM,
    FRINGE_XY_EXPANSION_MM,
    TEE_HOLE_DIAMETER_MM,
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


import sys
three_mf = sys.argv[1] if len(sys.argv) > 1 else "/Volumes/GIT/CLAUDE/SHARED_WORK_FOLDER/ItWentIn/GolfCourses/Firefly/3MFs/Firefly (Hole 14) [108].3mf"
egm_path = "/Volumes/GIT/CLAUDE/SHARED_WORK_FOLDER/ItWentIn/GolfCourses/Firefly/EGMs/Firefly (Hole 14).egm"

egm, _img, _gpx = load_egm(egm_path)
tee = egm["tee_hole"]
x_tl, y_tl = float(tee["x_mm"]), float(tee["y_mm"])
half = PRINT_SIZE_MM / 2 + FRINGE_XY_EXPANSION_MM / 2
cx_expected = -half + x_tl
cy_expected = +half - y_tl

print(f"Expected tee center from EGM: ({cx_expected:.4f}, {cy_expected:.4f})")
print(f"  from top-left ({x_tl:.2f}, {y_tl:.2f}) mm  half={half:.4f}")

sc = trimesh.load(three_mf, force="scene")
nodes = scene_nodes(sc)
fringe = next(v for k, v in nodes.items() if "fringe" in k.lower())

sec = fringe.section(plane_origin=[0, 0, 2.0], plane_normal=[0, 0, 1])
planar, _tf = sec.to_planar()
polys = list(planar.polygons_full)

# Find the tiny circular hole (matches collar bore area ~44 mm^2)
target_area_min = 30
target_area_max = 60
print("\nAll interior holes across all polygons at Z=2:")
best = None
best_score = None
for pi, p in enumerate(polys):
    if p.exterior is None:
        continue
    for hi, hole in enumerate(p.interiors):
        hp = ShapelyPolygon(hole)
        cxh, cyh = hp.centroid.x, hp.centroid.y
        area = hp.area
        perim = hp.length
        # circularity ~ 4*pi*A / P^2 → 1 for circle
        circ = (4 * np.pi * area / (perim ** 2)) if perim > 0 else 0
        print(f"  poly{pi} hole{hi}: area={area:.3f}  perim={perim:.3f}  circ={circ:.3f}  centroid=({cxh:.4f}, {cyh:.4f})")
        if target_area_min <= area <= target_area_max and circ > 0.85:
            # This is likely the bore
            print(f"    ** matches collar bore area & circularity")
            score = abs(area - 44.7)
            if best_score is None or score < best_score:
                best_score = score
                best = (cxh, cyh, area, perim, circ)

if best:
    ax, ay, area, perim, circ = best
    print(f"\nActual collar bore centroid: ({ax:.4f}, {ay:.4f})")
    print(f"  area={area:.4f} mm²  perimeter={perim:.4f} mm  circularity={circ:.4f}")
    print(f"  effective radius from area = {np.sqrt(area/np.pi):.4f} mm")
    dx = ax - cx_expected
    dy = ay - cy_expected
    print(f"\nOFFSET from expected: dX={dx:+.4f} mm  dY={dy:+.4f} mm  distance={np.hypot(dx, dy):.4f} mm")
    # Also check where THIS point maps back to in top-left mm
    x_tl_back = ax - (-half)
    y_tl_back = +half - ay
    print(f"Actual bore in top-left mm: ({x_tl_back:.4f}, {y_tl_back:.4f})")
    print(f"EGM says top-left mm:        ({x_tl:.4f}, {y_tl:.4f})")
