"""What does the fringe look like near the tee position (-42, +61)?
- List all triangles whose vertices are within ~10 mm of that point
- Show cross-section at multiple Z near the tee only
"""
import sys
import numpy as np
import trimesh
from shapely.geometry import Polygon as ShapelyPolygon, Point as SP, box as shbox
from shapely.ops import unary_union

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
print(f"tee mesh XY = ({cx:.4f}, {cy:.4f})   collar_r = {TEE_HOLE_COLLAR_OD_MM/2:.4f}")

sc = trimesh.load(three_mf, force="scene")
nodes = scene_nodes(sc)
fringe = next(v for k, v in nodes.items() if "fringe" in k.lower())
V = fringe.vertices
F = fringe.faces
print(f"fringe: verts={len(V)}, faces={len(F)}")

# Vertices within 10 mm of tee
d = np.hypot(V[:,0] - cx, V[:,1] - cy)
near_v = d < 10
print(f"verts within 10 mm of tee: {int(near_v.sum())}")
# Break down by Z
if near_v.any():
    zs = V[near_v, 2]
    print(f"  Z range: [{zs.min():.4f}, {zs.max():.4f}]  mean={zs.mean():.4f}")
    # Show distribution
    for z_lo in np.arange(0, 18, 2):
        z_hi = z_lo + 2
        cnt = int(((zs >= z_lo) & (zs < z_hi)).sum())
        if cnt:
            print(f"    z in [{z_lo:.1f}, {z_hi:.1f}): {cnt}")

# Vertices within 5 mm
for radius in [3.8, 4.0, 5.0, 6.0, 8.0]:
    near = d < radius
    print(f"  within {radius} mm: {int(near.sum())} verts")

# List actual XY of verts within 5 mm to see collar tube
near = d < 5.0
if near.any():
    print(f"\nVerts within 5 mm (sorted by radius):")
    idx = np.where(near)[0]
    for i in sorted(idx, key=lambda i: d[i])[:40]:
        v = V[i]
        print(f"  #{i}: XY=({v[0]:+.4f}, {v[1]:+.4f})  Z={v[2]:.4f}  r={d[i]:.4f}")

# Cross-section clipping ONLY to a small box around the tee
print("\nCross-sections at multiple Z, clipped to ±10 mm box around tee:")
clip_box = shbox(cx-10, cy-10, cx+10, cy+10)
for z in [0.5, 1.5, 2.0, 4.0, 6.0, 8.0]:
    sec = fringe.section(plane_origin=[0,0,z], plane_normal=[0,0,1])
    if sec is None:
        print(f"  Z={z}: no section")
        continue
    planar, _tf = sec.to_planar()
    polys = list(planar.polygons_full)
    filtered = []
    for p in polys:
        if p.intersects(clip_box):
            filtered.append(p.intersection(clip_box))
    print(f"  Z={z}: {len(polys)} total polys, {len(filtered)} near tee")
    for i, p in enumerate(filtered):
        if p.is_empty:
            continue
        if hasattr(p, "geoms"):
            for gj, g in enumerate(p.geoms):
                if g.is_empty or g.area < 0.01:
                    continue
                c = g.centroid
                d_c = np.hypot(c.x - cx, c.y - cy)
                print(f"    piece {i}.{gj}: area={g.area:.4f}  centroid=({c.x:.3f}, {c.y:.3f}) d_tee={d_c:.3f}  bounds={g.bounds}")
        else:
            if p.area < 0.01:
                continue
            c = p.centroid
            d_c = np.hypot(c.x - cx, c.y - cy)
            print(f"    piece {i}: area={p.area:.4f}  centroid=({c.x:.3f}, {c.y:.3f}) d_tee={d_c:.3f}  bounds={p.bounds}")
