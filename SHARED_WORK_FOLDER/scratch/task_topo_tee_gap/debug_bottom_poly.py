"""Reconstruct bottom_poly assembly step-by-step to figure out why interiors=1
instead of 3 (green, trap, water)."""
import sys, os
import numpy as np
from shapely.geometry import Polygon as ShapelyPolygon, box as shbox
from shapely.ops import unary_union

APP_DIR = "/Volumes/GIT/CLAUDE/SHARED_WORK_FOLDER/app"
sys.path.insert(0, APP_DIR)
os.chdir(APP_DIR)

# Reuse pipeline's helpers
from gradient_surface_diagnostic import (
    load_egm, _compute_px_to_mm, _px_to_mm_2d, _poly_to_dense_px, _poly_to_raw_catmull_px,
    _clip_polygon_to_fringe_rect,
    PRINT_SIZE_MM, FRINGE_XY_EXPANSION_MM,
    GREEN_FRINGE_GAP_MM, TRAP_FRINGE_GAP_MM, WATER_FRINGE_GAP_MM,
)

egm_path = "/Volumes/GIT/CLAUDE/SHARED_WORK_FOLDER/ItWentIn/GolfCourses/Firefly/EGMs/Firefly (Hole 14).egm"
egm, _img, gpx = load_egm(egm_path)
scale, centroid_px = _compute_px_to_mm(gpx, egm)

# Build green_shapely_exclusion
green_polys = [p for p in egm["polygons"] if p.get("type") == "green"]
gpx_pts = _poly_to_dense_px(green_polys[0])
gpx_mm = _px_to_mm_2d(gpx_pts, scale, centroid_px)
green_shapely = ShapelyPolygon(gpx_mm)
if not green_shapely.is_valid:
    green_shapely = green_shapely.buffer(0)
green_shapely_exclusion = green_shapely.buffer(+GREEN_FRINGE_GAP_MM) if GREEN_FRINGE_GAP_MM > 0 else green_shapely
print(f"green exclusion area = {green_shapely_exclusion.area:.4f}")

# Build trap and water shapely using RAW polylines (task 723)
trap_shapely = []
for p in egm["polygons"]:
    if p.get("type") == "trap":
        pts_px = _poly_to_raw_catmull_px(p)
        pts_mm = _px_to_mm_2d(pts_px, scale, centroid_px)
        sp = ShapelyPolygon(pts_mm)
        if not sp.is_valid:
            sp = sp.buffer(0)
        sp = _clip_polygon_to_fringe_rect(sp, "Trap") or sp
        trap_shapely.append(sp)
        print(f"trap area = {sp.area:.4f}  bounds={sp.bounds}")

water_shapely = []
for p in egm["polygons"]:
    if p.get("type") == "water":
        pts_px = _poly_to_raw_catmull_px(p)
        pts_mm = _px_to_mm_2d(pts_px, scale, centroid_px)
        sp = ShapelyPolygon(pts_mm)
        if not sp.is_valid:
            sp = sp.buffer(0)
        sp = _clip_polygon_to_fringe_rect(sp, "Water") or sp
        water_shapely.append(sp)
        print(f"water area = {sp.area:.4f}  bounds={sp.bounds}")

# Apply +GAP buffer as in _trap_carve / _water_carve
_trap_carve = [sp.buffer(+TRAP_FRINGE_GAP_MM) for sp in trap_shapely]
_water_carve = [sp.buffer(+WATER_FRINGE_GAP_MM) for sp in water_shapely]
for i, sp in enumerate(_trap_carve):
    print(f"trap_carve[{i}] area={sp.area:.4f} bounds={sp.bounds} is_valid={sp.is_valid}")
for i, sp in enumerate(_water_carve):
    print(f"water_carve[{i}] area={sp.area:.4f} bounds={sp.bounds} is_valid={sp.is_valid}")

# Now do the SAME assembly as build_fringe_mesh
half = PRINT_SIZE_MM / 2 + FRINGE_XY_EXPANSION_MM / 2
_cap_rect = shbox(-half, -half, +half, +half)
print(f"\n_cap_rect area={_cap_rect.area:.4f} bounds={_cap_rect.bounds}")

_cap_holes = []
if green_shapely_exclusion is not None and not green_shapely_exclusion.is_empty:
    if hasattr(green_shapely_exclusion, "geoms"):
        for _g in green_shapely_exclusion.geoms:
            if _g.exterior is not None:
                _cap_holes.append(ShapelyPolygon(list(_g.exterior.coords)))
    else:
        _cap_holes.append(ShapelyPolygon(list(green_shapely_exclusion.exterior.coords)))
for _tp in _trap_carve:
    if _tp is None or _tp.is_empty:
        continue
    if hasattr(_tp, "geoms"):
        for _g in _tp.geoms:
            if _g.exterior is not None:
                _cap_holes.append(ShapelyPolygon(list(_g.exterior.coords)))
    elif _tp.exterior is not None:
        _cap_holes.append(ShapelyPolygon(list(_tp.exterior.coords)))
for _wp in _water_carve:
    if _wp is None or _wp.is_empty:
        continue
    if hasattr(_wp, "geoms"):
        for _g in _wp.geoms:
            if _g.exterior is not None:
                _cap_holes.append(ShapelyPolygon(list(_g.exterior.coords)))
    elif _wp.exterior is not None:
        _cap_holes.append(ShapelyPolygon(list(_wp.exterior.coords)))

print(f"\n_cap_holes count = {len(_cap_holes)}")
for i, h in enumerate(_cap_holes):
    print(f"  hole[{i}]: area={h.area:.4f} is_valid={h.is_valid} bounds={h.bounds}")

# Now do the difference iteratively
bottom_poly = _cap_rect
for i, _h in enumerate(_cap_holes):
    before_area = bottom_poly.area
    before_interiors = len(list(bottom_poly.interiors)) if hasattr(bottom_poly, "interiors") else -1
    try:
        bottom_poly = bottom_poly.difference(_h)
    except Exception as ex:
        print(f"  diff hole[{i}] FAILED: {ex}")
        continue
    after_area = bottom_poly.area
    if hasattr(bottom_poly, "geoms"):
        after_interiors = sum(len(list(g.interiors)) for g in bottom_poly.geoms)
        print(f"  after hole[{i}]: MultiPolygon with {len(bottom_poly.geoms)} pieces, total_interiors={after_interiors}, area={after_area:.4f}")
    else:
        after_interiors = len(list(bottom_poly.interiors))
        print(f"  after hole[{i}]: Polygon, interiors={after_interiors}, area={after_area:.4f} (was {before_area:.4f})")

# Final
if not bottom_poly.is_valid:
    print("Not valid — buffer(0)")
    bottom_poly = bottom_poly.buffer(0)
if hasattr(bottom_poly, "geoms"):
    print(f"MultiPolygon result — picking largest")
    bottom_poly = max(bottom_poly.geoms, key=lambda g: g.area)
print(f"\nFinal bottom_poly: interiors={len(list(bottom_poly.interiors))}  area={bottom_poly.area:.4f}")
