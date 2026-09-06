"""Save an image of the bottom_poly around the tee position."""
import sys, os
import numpy as np
import matplotlib.pyplot as plt
from matplotlib.patches import Circle
from shapely.geometry import Polygon as ShapelyPolygon, box as shbox

APP_DIR = "/Volumes/GIT/CLAUDE/SHARED_WORK_FOLDER/app"
sys.path.insert(0, APP_DIR)
os.chdir(APP_DIR)

from gradient_surface_diagnostic import (
    load_egm, _compute_px_to_mm, _px_to_mm_2d, _poly_to_dense_px, _poly_to_raw_catmull_px,
    _clip_polygon_to_fringe_rect,
    PRINT_SIZE_MM, FRINGE_XY_EXPANSION_MM,
    GREEN_FRINGE_GAP_MM, TRAP_FRINGE_GAP_MM, WATER_FRINGE_GAP_MM,
    TEE_HOLE_COLLAR_OD_MM, TEE_HOLE_DIAMETER_MM,
)

egm_path = "/Volumes/GIT/CLAUDE/SHARED_WORK_FOLDER/ItWentIn/GolfCourses/Firefly/EGMs/Firefly (Hole 14).egm"
egm, _img, gpx = load_egm(egm_path)
scale, centroid_px = _compute_px_to_mm(gpx, egm)

tee = egm["tee_hole"]
half = PRINT_SIZE_MM / 2 + FRINGE_XY_EXPANSION_MM / 2
cx = -half + float(tee["x_mm"])
cy = +half - float(tee["y_mm"])

# Build all cap polygons
green_polys = [p for p in egm["polygons"] if p.get("type") == "green"]
gpx_pts = _poly_to_dense_px(green_polys[0])
gpx_mm = _px_to_mm_2d(gpx_pts, scale, centroid_px)
green_shapely = ShapelyPolygon(gpx_mm).buffer(0)
green_ex = green_shapely.buffer(+GREEN_FRINGE_GAP_MM)

trap_polys = []
for p in egm["polygons"]:
    if p.get("type") == "trap":
        pts = _px_to_mm_2d(_poly_to_raw_catmull_px(p), scale, centroid_px)
        sp = ShapelyPolygon(pts).buffer(0)
        sp = _clip_polygon_to_fringe_rect(sp, "Trap") or sp
        trap_polys.append(sp.buffer(+TRAP_FRINGE_GAP_MM))

water_polys = []
for p in egm["polygons"]:
    if p.get("type") == "water":
        pts = _px_to_mm_2d(_poly_to_raw_catmull_px(p), scale, centroid_px)
        sp = ShapelyPolygon(pts).buffer(0)
        sp = _clip_polygon_to_fringe_rect(sp, "Water") or sp
        water_polys.append(sp.buffer(+WATER_FRINGE_GAP_MM))

# Do the difference
_cap_rect = shbox(-half, -half, +half, +half)
bp = _cap_rect
bp = bp.difference(green_ex)
for tp in trap_polys:
    bp = bp.difference(tp)
for wp in water_polys:
    bp = bp.difference(wp)
if hasattr(bp, "geoms"):
    bp = max(bp.geoms, key=lambda g: g.area)

print(f"bottom_poly: interiors={len(list(bp.interiors))}  area={bp.area:.4f}")

# Plot exterior of bp and interiors near the tee
fig, ax = plt.subplots(figsize=(10, 10))
# Exterior
ex = np.array(list(bp.exterior.coords))
ax.plot(ex[:,0], ex[:,1], 'b-', linewidth=1, label='bottom_poly.exterior')
for i, hole in enumerate(bp.interiors):
    hc = np.array(list(hole.coords))
    ax.plot(hc[:,0], hc[:,1], 'g-', linewidth=1)
    ax.fill(hc[:,0], hc[:,1], color='lightgreen', alpha=0.3)

# Show trap and water polygon boundaries in dashed
for tp in trap_polys:
    xy = np.array(list(tp.exterior.coords))
    ax.plot(xy[:,0], xy[:,1], 'r--', linewidth=0.8, alpha=0.7, label='trap buffered')
for wp in water_polys:
    xy = np.array(list(wp.exterior.coords))
    ax.plot(xy[:,0], xy[:,1], 'c--', linewidth=0.8, alpha=0.7, label='water buffered')

# Cap rect
ax.plot(*_cap_rect.exterior.xy, 'k--', linewidth=0.6, alpha=0.5)

# Tee position
ax.add_patch(Circle((cx, cy), TEE_HOLE_COLLAR_OD_MM/2, fill=False, edgecolor='red', linewidth=1.5, label='collar OD'))
ax.add_patch(Circle((cx, cy), TEE_HOLE_DIAMETER_MM/2, fill=False, edgecolor='orange', linewidth=1.5, label='collar ID'))
ax.plot(cx, cy, 'r+', markersize=15, label=f'tee ({cx:.2f},{cy:.2f})')

ax.set_aspect('equal')
ax.set_title(f"Firefly H14 bottom_poly assembly (v4.46 broken)")
ax.legend(loc='upper right', fontsize=8)
out = "/Volumes/GIT/CLAUDE/SHARED_WORK_FOLDER/scratch/task_topo_tee_gap/bottom_poly_full.png"
plt.savefig(out, dpi=120, bbox_inches='tight')
print(f"saved {out}")

# Zoom to tee region
ax.set_xlim(cx-15, cx+15)
ax.set_ylim(cy-15, cy+15)
out2 = "/Volumes/GIT/CLAUDE/SHARED_WORK_FOLDER/scratch/task_topo_tee_gap/bottom_poly_zoom.png"
plt.savefig(out2, dpi=150, bbox_inches='tight')
print(f"saved {out2}")
