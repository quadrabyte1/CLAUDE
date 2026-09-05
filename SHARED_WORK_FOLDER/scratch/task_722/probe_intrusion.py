"""Count fringe faces with >=2 XY-vertices strictly inside each trap footprint.

Extract each trap as a separate component from geometry_2 (traps mesh), take its
XY footprint via unary_union of the bottom-cap triangles, then count fringe
triangles where >=2 XY vertices lie inside that footprint (unbuffered).

Usage: python probe_intrusion.py <path_to.3mf>
"""
import sys
import numpy as np
import trimesh
from shapely.geometry import Polygon, Point, MultiPolygon
from shapely.ops import unary_union
from shapely.prepared import prep

path = sys.argv[1]
scene = trimesh.load(path)
print(f"Scene: {list(scene.geometry.keys())}")

fringe = None
traps_mesh = None
water_mesh = None
for name, m in scene.geometry.items():
    if not isinstance(m, trimesh.Trimesh):
        continue
    if name == "geometry_1":
        fringe = m
    elif name == "geometry_2":
        traps_mesh = m
    elif name == "geometry_3":
        water_mesh = m

if fringe is None:
    print("NO FRINGE"); sys.exit(1)
print(f"fringe faces: {len(fringe.faces)}")

def footprint_from_bottom(mesh, z_tol=0.01):
    """Union XY projections of triangles at z=0 (bottom cap)."""
    tris = mesh.triangles
    zmax_per = tris[:, :, 2].max(axis=1)
    zmin_per = tris[:, :, 2].min(axis=1)
    # bottom cap: all 3 z ~ 0
    mask = zmax_per <= z_tol
    bottom = tris[mask]
    print(f"    bottom-cap triangles: {len(bottom)} / {len(tris)}")
    polys = []
    for tri in bottom:
        p = Polygon([(tri[0, 0], tri[0, 1]),
                     (tri[1, 0], tri[1, 1]),
                     (tri[2, 0], tri[2, 1])])
        if not p.is_valid:
            p = p.buffer(0)
        if not p.is_empty and p.area > 1e-6:
            polys.append(p)
    if not polys:
        return None
    return unary_union(polys)

def split_and_get_footprints(mesh, label):
    """Split mesh into connected components, take footprint of each."""
    parts = mesh.split(only_watertight=False)
    out = []
    print(f"  {label}: {len(parts)} component(s)")
    for i, p in enumerate(parts, start=1):
        fp = footprint_from_bottom(p)
        if fp is None or fp.is_empty:
            print(f"    {label} #{i}: empty footprint")
            continue
        # If multipolygon, keep largest
        if isinstance(fp, MultiPolygon):
            fp = max(fp.geoms, key=lambda g: g.area)
        # Drop interior holes (trap polygons are simple)
        if getattr(fp, "interiors", None):
            fp = Polygon(fp.exterior)
        print(f"    {label} #{i}: area={fp.area:.1f} mm^2 bounds={[round(b,1) for b in fp.bounds]}")
        out.append((f"{label}_{i}", fp))
    return out

def count_intrusions(fringe_mesh, poly, label):
    tris = fringe_mesh.triangles  # (N,3,3)
    n_faces = len(tris)
    xy_flat = tris[:, :, :2].reshape(-1, 2)  # (3N, 2)
    pp = prep(poly)
    # bbox pre-filter for speed
    xmin, ymin, xmax, ymax = poly.bounds
    xf = xy_flat[:, 0]; yf = xy_flat[:, 1]
    in_bbox = (xf >= xmin) & (xf <= xmax) & (yf >= ymin) & (yf <= ymax)
    inside = np.zeros(len(xy_flat), dtype=bool)
    for idx in np.where(in_bbox)[0]:
        inside[idx] = pp.contains(Point(xf[idx], yf[idx]))
    inside_per_tri = inside.reshape(n_faces, 3).sum(axis=1)
    n_ge1 = int((inside_per_tri >= 1).sum())
    n_ge2 = int((inside_per_tri >= 2).sum())
    n_3 = int((inside_per_tri == 3).sum())
    print(f"  [{label}] fringe verts_inside_bbox={int(in_bbox.sum())}, "
          f"faces >=1 inside: {n_ge1}, >=2: {n_ge2}, all 3: {n_3}")
    return n_ge2

targets = []
if traps_mesh is not None:
    targets += split_and_get_footprints(traps_mesh, "trap")
if water_mesh is not None:
    targets += split_and_get_footprints(water_mesh, "water")

total = 0
for name, poly in targets:
    n = count_intrusions(fringe, poly, name)
    total += n
print(f"\nTOTAL fringe faces with >=2 vtx inside a cutout: {total}")
