"""Test that clipping the _cap_holes to the fringe rect before difference
produces the correct number of interiors (3: green + trap + water)."""
import sys, os
import numpy as np
from shapely.geometry import Polygon as ShapelyPolygon, box as shbox

APP_DIR = "/Volumes/GIT/CLAUDE/SHARED_WORK_FOLDER/app"
sys.path.insert(0, APP_DIR)
os.chdir(APP_DIR)

from gradient_surface_diagnostic import (
    load_egm, _compute_px_to_mm, _px_to_mm_2d, _poly_to_dense_px, _poly_to_raw_catmull_px,
    _clip_polygon_to_fringe_rect,
    PRINT_SIZE_MM, FRINGE_XY_EXPANSION_MM,
    GREEN_FRINGE_GAP_MM, TRAP_FRINGE_GAP_MM, WATER_FRINGE_GAP_MM,
)

egm_path = "/Volumes/GIT/CLAUDE/SHARED_WORK_FOLDER/ItWentIn/GolfCourses/Firefly/EGMs/Firefly (Hole 14).egm"
egm, _img, gpx = load_egm(egm_path)
scale, centroid_px = _compute_px_to_mm(gpx, egm)

half = PRINT_SIZE_MM/2 + FRINGE_XY_EXPANSION_MM/2
_cap_rect = shbox(-half, -half, +half, +half)

# Same trap/water carve polys as build_fringe_mesh
def build_shapely(ptype, gap):
    polys = []
    for p in egm["polygons"]:
        if p.get("type") == ptype:
            pts = _px_to_mm_2d(_poly_to_raw_catmull_px(p), scale, centroid_px)
            sp = ShapelyPolygon(pts).buffer(0)
            sp = _clip_polygon_to_fringe_rect(sp, ptype) or sp
            polys.append(sp.buffer(+gap))
    return polys

_trap_carve = build_shapely("trap", TRAP_FRINGE_GAP_MM)
_water_carve = build_shapely("water", WATER_FRINGE_GAP_MM)
green_polys = [p for p in egm["polygons"] if p.get("type") == "green"]
gpx_pts = _poly_to_dense_px(green_polys[0])
gpx_mm = _px_to_mm_2d(gpx_pts, scale, centroid_px)
green_shapely = ShapelyPolygon(gpx_mm).buffer(0)
green_ex = green_shapely.buffer(+GREEN_FRINGE_GAP_MM) if GREEN_FRINGE_GAP_MM > 0 else green_shapely

# CURRENT BROKEN: subtract raw
bp_broken = _cap_rect
for h in [green_ex] + _trap_carve + _water_carve:
    bp_broken = bp_broken.difference(h)
if hasattr(bp_broken, "geoms"):
    bp_broken = max(bp_broken.geoms, key=lambda g: g.area)
print(f"CURRENT BROKEN: interiors={len(list(bp_broken.interiors))}  area={bp_broken.area:.2f}")

# FIX: clip each hole to _cap_rect first, then subtract
bp_fixed = _cap_rect
for h in [green_ex] + _trap_carve + _water_carve:
    if h is None or h.is_empty:
        continue
    h_clip = h.intersection(_cap_rect)
    if not h_clip.is_valid:
        h_clip = h_clip.buffer(0)
    # Only subtract if the clipped hole is entirely inside the rect
    # (i.e. it's a proper interior hole not a boundary-eating chunk).
    # But even if it touches the boundary, we want to keep the interior hole
    # portion, not eat into the rect. Since intersection is a subset of the rect,
    # subtracting it will always yield a polygon (never eat past the boundary).
    # The question: does shapely still recognize a boundary-touching hole as an interior?
    # -> YES if the hole polygon doesn't include the rect boundary itself. Let's check.
    try:
        bp_fixed = bp_fixed.difference(h_clip)
    except Exception as ex:
        print(f"  diff failed: {ex}")
        continue
if hasattr(bp_fixed, "geoms"):
    bp_fixed = max(bp_fixed.geoms, key=lambda g: g.area)
print(f"FIX (clip-then-diff): interiors={len(list(bp_fixed.interiors))}  area={bp_fixed.area:.2f}")
# Print each interior's bbox to verify
for i, hole in enumerate(bp_fixed.interiors):
    hc = np.array(list(hole.coords))
    print(f"  interior[{i}]: bbox X[{hc[:,0].min():.2f}, {hc[:,0].max():.2f}] Y[{hc[:,1].min():.2f}, {hc[:,1].max():.2f}]  n_pts={len(hc)}")
