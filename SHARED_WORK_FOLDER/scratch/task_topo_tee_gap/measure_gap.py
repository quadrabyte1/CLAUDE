"""
Measure the XY gap between the tee-peg cylinder (collar) and surrounding
fringe geometry in a generated 3MF.

Reports for the fringe cross-section at a Z slightly above the base slab:
  - detected tee cylinder center (from EGM tee_hole)
  - inner radius of the hole in the fringe around the tee
  - outer radius of the collar tube
  - the XY gap = fringe_hole_inner_radius - collar_outer_radius
"""
import sys, os, argparse
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
    BASE_THICKNESS_MM,
)


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
    ap = argparse.ArgumentParser()
    ap.add_argument("--three_mf", required=True)
    ap.add_argument("--egm", required=True)
    ap.add_argument("--zs", default="0.5,2.0,3.0,4.0,6.0", help="Z slices in mm")
    args = ap.parse_args()

    egm, _img_path, _gpx = load_egm(args.egm)
    tee = egm.get("tee_hole")
    if not tee:
        print("EGM has no tee_hole key")
        return
    x_mm_tl = float(tee["x_mm"])
    y_mm_tl = float(tee["y_mm"])

    half = PRINT_SIZE_MM / 2.0 + FRINGE_XY_EXPANSION_MM / 2.0
    cx = -half + x_mm_tl
    cy = +half - y_mm_tl

    print(f"[TEE] print-top-left ({x_mm_tl:.2f}, {y_mm_tl:.2f}) mm → mesh XY ({cx:.3f}, {cy:.3f}) mm")
    print(f"[TEE] half = {half:.4f} mm  (PRINT_SIZE_MM={PRINT_SIZE_MM}, FRINGE_XY_EXPANSION_MM={FRINGE_XY_EXPANSION_MM})")
    print(f"[TEE] TEE_HOLE_DIAMETER_MM={TEE_HOLE_DIAMETER_MM}  TEE_HOLE_COLLAR_OD_MM={TEE_HOLE_COLLAR_OD_MM}")
    print(f"[TEE] expected collar outer radius = {TEE_HOLE_COLLAR_OD_MM/2:.4f} mm")
    print()

    scene = trimesh.load(args.three_mf, force="scene")
    nodes = scene_nodes(scene)
    print(f"[3MF] geometries: {sorted(nodes.keys())}")

    fringe = None
    for k, v in nodes.items():
        if "fringe" in k.lower():
            fringe = v
            print(f"[3MF] using node '{k}' as fringe  (verts={len(v.vertices)} faces={len(v.faces)})")
            print(f"      bounds: {v.bounds}")
            break
    if fringe is None:
        print("No fringe node found in 3MF")
        return

    # -------- Section the fringe at each Z --------
    for z in [float(z) for z in args.zs.split(",")]:
        print(f"\n=== Z = {z:.3f} mm ===")
        sec = fringe.section(plane_origin=[0, 0, z], plane_normal=[0, 0, 1])
        if sec is None:
            print("  no fringe section at this Z")
            continue
        planar, _tf = sec.to_planar()
        polys = list(planar.polygons_full)
        print(f"  fringe section: {len(polys)} polygon(s)")
        if not polys:
            continue
        # Combine, look for the piece containing the tee point in its hole set
        u = unary_union(polys)
        # For each polygon, find the interior hole that contains the tee (cx, cy)
        # If none contain it, list nearest interior distance.
        tee_pt = ShapelyPoint(cx, cy)
        found = False
        for pi, poly in enumerate(polys if hasattr(u, "geoms") is False and len(polys) > 1 else [u] if not hasattr(u, "geoms") else list(u.geoms)):
            if poly.geom_type != "Polygon":
                continue
            for hi, hole in enumerate(poly.interiors):
                hpoly = ShapelyPolygon(hole)
                if hpoly.contains(tee_pt) or hpoly.buffer(0.001).contains(tee_pt):
                    # Measure inner radius by distance to hole boundary from tee center
                    dist_to_boundary = tee_pt.distance(hpoly.exterior)
                    # Compute mean/min/max radius from tee center to hole vertices
                    xy = np.array(list(hole.coords))
                    radii = np.hypot(xy[:, 0] - cx, xy[:, 1] - cy)
                    print(f"  [poly{pi} hole{hi}] contains tee center: inner_r  min={radii.min():.4f}  mean={radii.mean():.4f}  max={radii.max():.4f} mm")
                    print(f"                                          dist center→boundary = {dist_to_boundary:.4f} mm")
                    print(f"                                          area = {hpoly.area:.4f} mm²  perimeter = {hpoly.length:.4f} mm")
                    gap = radii.min() - TEE_HOLE_COLLAR_OD_MM / 2.0
                    print(f"  GAP  (min inner_r − collar_outer_r) = {gap:.4f} mm")
                    found = True
        if not found:
            # No hole contains the tee — perhaps the fringe cross-section is empty near it,
            # or the fringe stops before the tee (fringe/tee not touching!)
            # Fallback: find nearest boundary of every polygon.
            print("  ! No interior hole contains the tee center.")
            for pi, poly in enumerate(polys):
                d_ext = tee_pt.distance(poly.exterior)
                print(f"    poly{pi}: dist tee→exterior = {d_ext:.4f} mm  area={poly.area:.1f}")
                for hi, hole in enumerate(poly.interiors):
                    d = tee_pt.distance(hole)
                    print(f"      hole{hi} area={ShapelyPolygon(hole).area:.3f} dist tee→boundary = {d:.4f} mm")


if __name__ == "__main__":
    main()
