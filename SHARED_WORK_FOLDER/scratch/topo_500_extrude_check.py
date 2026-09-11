"""What does extrude_polygon actually produce for a fringe-like polygon?"""
import numpy as np, trimesh
from shapely.geometry import box, Polygon, Point

# Fringe frame ±85.2, with green (60mm circle at origin), trap 20mm at (30,0), water 20mm at (-30,0)
rect = box(-85.2, -85.2, 85.2, 85.2)
green = Point(0, 0).buffer(30, resolution=64)
trap = Point(30, 0).buffer(15, resolution=48)
water = Point(-30, 0).buffer(15, resolution=48)
poly = rect.difference(green).difference(trap).difference(water)
print(f"Polygon: area={poly.area:.1f} mm², "
      f"exterior pts={len(poly.exterior.coords)}, "
      f"interiors={len(list(poly.interiors))}, "
      f"total interior pts={sum(len(i.coords) for i in poly.interiors)}")

# Extrude with pq30a25
m = trimesh.creation.extrude_polygon(poly, height=15.0, engine="triangle", triangle_args="pq30a25")
print(f"pq30a25: verts={len(m.vertices)} faces={len(m.faces)}")
top = m.vertices[:, 2] > 14.9
print(f"  top verts: {int(top.sum())}")

# Try pq30a5 (max 5 mm²)
m2 = trimesh.creation.extrude_polygon(poly, height=15.0, engine="triangle", triangle_args="pq30a5")
print(f"pq30a5: verts={len(m2.vertices)} faces={len(m2.faces)}")
top2 = m2.vertices[:, 2] > 14.9
print(f"  top verts: {int(top2.sum())}")

# Try pq30a1
m3 = trimesh.creation.extrude_polygon(poly, height=15.0, engine="triangle", triangle_args="pq30a1")
print(f"pq30a1: verts={len(m3.vertices)} faces={len(m3.faces)}")
top3 = m3.vertices[:, 2] > 14.9
print(f"  top verts: {int(top3.sum())}")
