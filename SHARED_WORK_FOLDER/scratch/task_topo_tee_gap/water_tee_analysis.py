"""Show water polygon geometry vs tee cylinder + illustrate the gap origin."""
import sys
import numpy as np
from shapely.geometry import Polygon as ShapelyPolygon, Point as SP

APP_DIR = "/Volumes/GIT/CLAUDE/SHARED_WORK_FOLDER/app"
sys.path.insert(0, APP_DIR)
from gradient_surface_diagnostic import (
    load_egm, _compute_px_to_mm, _px_to_mm_2d, _poly_to_dense_px, _poly_to_raw_catmull_px,
    PRINT_SIZE_MM, FRINGE_XY_EXPANSION_MM,
    TEE_HOLE_COLLAR_OD_MM,
    WATER_FRINGE_GAP_MM, TRAP_FRINGE_GAP_MM,
)

egm_path = "/Volumes/GIT/CLAUDE/SHARED_WORK_FOLDER/ItWentIn/GolfCourses/Firefly/EGMs/Firefly (Hole 14).egm"
egm, _img, gpx = load_egm(egm_path)
scale, centroid_px = _compute_px_to_mm(gpx, egm)

tee = egm["tee_hole"]
half = PRINT_SIZE_MM/2 + FRINGE_XY_EXPANSION_MM/2
cx = -half + float(tee["x_mm"])
cy = +half - float(tee["y_mm"])
collar_r = TEE_HOLE_COLLAR_OD_MM/2

print(f"tee mesh XY = ({cx:.4f}, {cy:.4f})   collar_r = {collar_r:.4f}")
print(f"collar footprint disc extends X[{cx-collar_r:.3f},{cx+collar_r:.3f}]  "
      f"Y[{cy-collar_r:.3f},{cy+collar_r:.3f}]")
print()

for poly in egm["polygons"]:
    ptype = poly.get("type")
    if ptype not in ("water", "trap"):
        continue
    pts_raw_px = _poly_to_raw_catmull_px(poly)
    pts_raw_mm = _px_to_mm_2d(pts_raw_px, scale, centroid_px)
    sp_raw = ShapelyPolygon(pts_raw_mm)
    if not sp_raw.is_valid:
        sp_raw = sp_raw.buffer(0)

    gap = WATER_FRINGE_GAP_MM if ptype == "water" else TRAP_FRINGE_GAP_MM
    sp_buf = sp_raw.buffer(+gap)

    tee_pt = SP(cx, cy)
    d_raw = tee_pt.distance(sp_raw)
    d_buf = tee_pt.distance(sp_buf)
    in_raw = sp_raw.contains(tee_pt)
    in_buf = sp_buf.contains(tee_pt)

    print(f"[{ptype}:{poly.get('name')}]")
    print(f"  raw:      bbox={sp_raw.bounds}   dist_to_tee={d_raw:.4f}   contains_tee={in_raw}")
    print(f"  buffered (+{gap}): bbox={sp_buf.bounds}   dist_to_tee={d_buf:.4f}   contains_tee={in_buf}")

    # Collar disc
    collar_disc = tee_pt.buffer(collar_r, resolution=32)
    # Intersection of collar with raw polygon and with buffered polygon
    print(f"  collar_disc.intersects(raw)      = {collar_disc.intersects(sp_raw)}  area={collar_disc.intersection(sp_raw).area:.4f}")
    print(f"  collar_disc.intersects(buffered) = {collar_disc.intersects(sp_buf)}  area={collar_disc.intersection(sp_buf).area:.4f}")

    # Distance from collar OUTER edge (tee_pt buffered by collar_r) to the raw polygon exterior
    # = raw.dist_to_tee - collar_r  (if tee is outside)
    print(f"  distance from collar_outer_edge to raw_water_edge      ≈ {d_raw - collar_r:.4f} mm")
    print(f"  distance from collar_outer_edge to buffered_water_edge ≈ {d_buf - collar_r:.4f} mm")
    print()
