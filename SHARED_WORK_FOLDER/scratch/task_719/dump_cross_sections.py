"""Dump fringe cross-section polygon at Z=8, compare against trap_1 polygon."""
import sys, os
import numpy as np
import trimesh
from shapely.geometry import Polygon as ShapelyPolygon
from shapely.ops import unary_union

APP_DIR = "/Volumes/GIT/CLAUDE/SHARED_WORK_FOLDER/app"
sys.path.insert(0, APP_DIR)
from gradient_surface_diagnostic import load_egm, _compute_px_to_mm, _px_to_mm_2d, _poly_to_dense_px, _clip_polygon_to_fringe_rect


def scene_nodes(scene):
    nodes = {}
    for n in scene.graph.nodes:
        try:
            _tf, geom_name = scene.graph[n]
        except Exception:
            continue
        if geom_name is not None and geom_name in scene.geometry:
            nodes[n] = scene.geometry[geom_name]
    return nodes


def main():
    p3mf = "/Volumes/GIT/CLAUDE/SHARED_WORK_FOLDER/ItWentIn/GolfCourses/DeLaveaga/3MFs/DeLaveaga (Hole 11) [212].3mf"
    egm_path = "/Volumes/GIT/CLAUDE/SHARED_WORK_FOLDER/ItWentIn/GolfCourses/DeLaveaga/EGMs/DeLaveaga (Hole 11).egm"
    scene = trimesh.load(p3mf, force="scene")
    nodes = scene_nodes(scene)
    fringe = nodes["fringe"]
    trap1 = nodes["trap_1"]

    egm, _img, gpx = load_egm(egm_path)
    scale, centroid_px = _compute_px_to_mm(gpx, egm)
    trap_polys_raw = [p for p in egm["polygons"] if p.get("type") == "trap"]
    tp1_px = _poly_to_dense_px(trap_polys_raw[0])
    tp1_mm = _px_to_mm_2d(tp1_px, scale, centroid_px)
    tp1_poly = ShapelyPolygon(tp1_mm)
    if not tp1_poly.is_valid:
        tp1_poly = tp1_poly.buffer(0)
    tp1_poly = _clip_polygon_to_fringe_rect(tp1_poly, "Trap 1") or tp1_poly

    # Fringe cross-section at Z = 8
    for z in [4.0, 6.0, 8.0, 9.5]:
        sec = fringe.section(plane_origin=[0, 0, z], plane_normal=[0, 0, 1])
        if sec is None:
            print(f"Z={z}: no fringe section")
            continue
        planar, _tf = sec.to_planar()
        polys = list(planar.polygons_full)
        print(f"\nZ={z}: fringe cross-section = {len(polys)} polygon(s)")
        u = unary_union(polys)
        print(f"  total area = {u.area:.1f} mm^2")
        inter = u.intersection(tp1_poly)
        print(f"  intersects trap_1 polygon = {inter.area:.3f} mm^2")
        # Also intersect against trap_1 mesh's cross-section
        t1_sec = trap1.section(plane_origin=[0, 0, z], plane_normal=[0, 0, 1])
        if t1_sec is not None:
            t1_planar, _tt = t1_sec.to_planar()
            t1_polys = list(t1_planar.polygons_full)
            t1_u = unary_union(t1_polys) if t1_polys else None
            if t1_u is not None:
                print(f"  trap_1 mesh cross-section area = {t1_u.area:.1f} mm^2")
                print(f"  fringe ∩ trap_1 mesh area     = {u.intersection(t1_u).area:.3f} mm^2")

        # Dump largest polygon coords for visualization
        if polys:
            biggest = max(polys, key=lambda p: p.area)
            if biggest.exterior is not None:
                coords = list(biggest.exterior.coords)
                # bbox
                xs = [c[0] for c in coords]; ys = [c[1] for c in coords]
                print(f"  biggest fringe piece bbox: X[{min(xs):.1f},{max(xs):.1f}] Y[{min(ys):.1f},{max(ys):.1f}]  area={biggest.area:.1f}")
                print(f"    interiors: {len(list(biggest.interiors))}")
                for j, hole in enumerate(biggest.interiors):
                    hc = list(hole.coords)
                    hxs = [c[0] for c in hc]; hys = [c[1] for c in hc]
                    ha = ShapelyPolygon(hole).area
                    print(f"    hole {j}: bbox X[{min(hxs):.1f},{max(hxs):.1f}] Y[{min(hys):.1f},{max(hys):.1f}]  area={ha:.1f}")

if __name__ == "__main__":
    main()
