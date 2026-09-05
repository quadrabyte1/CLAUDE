"""
V2: cross-section intersection kept in WORLD coordinates (no to_planar).
"""
import os, sys
import numpy as np
import trimesh
from shapely.geometry import Polygon as ShapelyPolygon, MultiPolygon
from shapely.ops import unary_union, polygonize


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


def cross_section_world_polys(mesh: trimesh.Trimesh, z: float):
    """Return a shapely (Multi)Polygon of mesh cross-section AT world Z, keeping world XY."""
    section = mesh.section(plane_origin=[0, 0, z], plane_normal=[0, 0, 1])
    if section is None:
        return None
    # Reconstruct polygons in WORLD XY using section.vertices + section.entities
    v = section.vertices  # (N, 3) world coords
    from shapely.geometry import LineString as _LS
    segs = []
    for e in section.entities:
        pts = v[e.points]
        # each entity is typically a polyline; break into segments
        for i in range(len(pts) - 1):
            a = (float(pts[i][0]), float(pts[i][1]))
            b = (float(pts[i+1][0]), float(pts[i+1][1]))
            if a != b:
                segs.append(_LS([a, b]))
    if not segs:
        return None
    merged = unary_union(segs)
    polys = list(polygonize(merged))
    if not polys:
        return None
    return unary_union(polys)


def main(path_3mf: str, layer_h: float = 0.2):
    scene = trimesh.load(path_3mf, force="scene")
    nodes = scene_nodes(scene)
    fringe = nodes["fringe"]
    trap_names = sorted([n for n in nodes if n.startswith("trap_")])
    water_names = sorted([n for n in nodes if n.startswith("water")])
    print(f"[layer-slicer WORLD] {os.path.basename(path_3mf)}, layer_h={layer_h}")

    zmax = float(max(fringe.bounds[1, 2], *(nodes[tn].bounds[1, 2] for tn in trap_names + water_names)))
    layer_zs = np.arange(layer_h / 2, zmax, layer_h)

    print(f"  Z range 0..{zmax:.2f}, {len(layer_zs)} layers, {len(trap_names)} traps + {len(water_names)} water")

    total_conflicts = {}
    for tn in trap_names + water_names:
        tmesh = nodes[tn]
        conflicts = []
        for li, z in enumerate(layer_zs):
            fpoly = cross_section_world_polys(fringe, z)
            if fpoly is None or fpoly.is_empty:
                continue
            tpoly = cross_section_world_polys(tmesh, z)
            if tpoly is None or tpoly.is_empty:
                continue
            inter = fpoly.intersection(tpoly)
            if not inter.is_empty and inter.area > 1e-3:
                conflicts.append((li + 1, float(z), float(inter.area)))
        total_conflicts[tn] = conflicts
        if not conflicts:
            print(f"  {tn}: NO fringe∩{tn} intersections at any layer  ✓")
        else:
            total_area = sum(c[2] for c in conflicts)
            print(f"  {tn}: {len(conflicts)} layer(s) with intersection, total ={total_area:.1f} mm^2·layer")
            for li, z, area in conflicts[:8]:
                print(f"    layer {li:3d}  z={z:5.2f}  ∩ area = {area:.3f} mm^2")
            if len(conflicts) > 8:
                print(f"    ... ({len(conflicts) - 8} more)")

    return total_conflicts


if __name__ == "__main__":
    p = sys.argv[1] if len(sys.argv) > 1 else \
        "/Volumes/GIT/CLAUDE/SHARED_WORK_FOLDER/ItWentIn/GolfCourses/DeLaveaga/3MFs/DeLaveaga (Hole 11) [212].3mf"
    main(p)
