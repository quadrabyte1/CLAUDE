"""
Deep dive: layer-by-layer overlap between fringe and each trap.

For each Z layer (0.2mm layer height), take a horizontal cross-section of the
fringe mesh and of each trap mesh, and check if the two sections' Shapely
polygons INTERSECT at that layer. That's what Bambu Studio's slicer checks
when it emits "gcode path conflict at layer N".
"""
import os
import sys
import json
import numpy as np
import trimesh
from shapely.geometry import Polygon as ShapelyPolygon, MultiPolygon
from shapely.ops import unary_union

APP_DIR = "/Volumes/GIT/CLAUDE/SHARED_WORK_FOLDER/app"
sys.path.insert(0, APP_DIR)


def scene_nodes(scene):
    node_to_mesh = {}
    for n in scene.graph.nodes:
        try:
            _tf, geom_name = scene.graph[n]
        except Exception:
            continue
        if geom_name is None:
            continue
        if geom_name in scene.geometry:
            node_to_mesh[n] = scene.geometry[geom_name]
    return node_to_mesh


def cross_section_polygons(mesh: trimesh.Trimesh, z: float):
    """Return a Shapely MultiPolygon of the mesh's XY footprint at height z."""
    try:
        section = mesh.section(plane_origin=[0, 0, z], plane_normal=[0, 0, 1])
        if section is None:
            return None
        planar, _tf = section.to_planar()
        polys = planar.polygons_full
        if not polys:
            return None
        # planar.polygons_full is a list of shapely Polygons already
        return unary_union(list(polys))
    except Exception as exc:
        return None


def main(path_3mf: str, layer_h: float = 0.2):
    scene = trimesh.load(path_3mf, force="scene")
    nodes = scene_nodes(scene)
    fringe = nodes["fringe"]
    trap_names = sorted([n for n in nodes if n.startswith("trap_")])
    print(f"[layer-slicer] {os.path.basename(path_3mf)}, layer_h={layer_h}")
    print(f"  fringe bounds: {fringe.bounds}")
    for tn in trap_names:
        print(f"  {tn} bounds: {nodes[tn].bounds}")

    # Z range = union
    zmin = 0.0
    zmax = float(max(fringe.bounds[1, 2], *(nodes[tn].bounds[1, 2] for tn in trap_names)))
    print(f"  Z range: {zmin:.2f} .. {zmax:.2f}, layer count = {int(np.ceil(zmax / layer_h))}")

    conflicts_per_trap = {tn: [] for tn in trap_names}
    # Scan every 5th layer for speed, then narrow on hits
    layer_zs = np.arange(layer_h / 2, zmax, layer_h)
    print(f"  scanning {len(layer_zs)} layers")

    # Get fringe cross-section once per layer, then intersect with each trap
    for li, z in enumerate(layer_zs):
        fringe_poly = cross_section_polygons(fringe, z)
        if fringe_poly is None or fringe_poly.is_empty:
            continue
        for tn in trap_names:
            trap_poly = cross_section_polygons(nodes[tn], z)
            if trap_poly is None or trap_poly.is_empty:
                continue
            inter = fringe_poly.intersection(trap_poly)
            if not inter.is_empty and inter.area > 1e-4:
                conflicts_per_trap[tn].append((li + 1, float(z), float(inter.area)))

    print(f"\n== LAYER-BY-LAYER INTERSECTIONS (fringe ∩ trap) ==")
    for tn, hits in conflicts_per_trap.items():
        if not hits:
            print(f"  {tn}: no fringe∩trap intersections at any layer")
        else:
            print(f"  {tn}: {len(hits)} layer(s) with fringe∩trap area > 0")
            for li, z, area in hits[:15]:
                print(f"    layer {li:3d}  z={z:5.2f}  intersection area = {area:.3f} mm^2")
            if len(hits) > 15:
                print(f"    ... ({len(hits) - 15} more)")


if __name__ == "__main__":
    p = sys.argv[1] if len(sys.argv) > 1 else \
        "/Volumes/GIT/CLAUDE/SHARED_WORK_FOLDER/ItWentIn/GolfCourses/DeLaveaga/3MFs/DeLaveaga (Hole 11) [212].3mf"
    main(p)
