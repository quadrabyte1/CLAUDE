"""V3: use to_planar (correct hole detection) + apply INVERSE transform to bring polygons to world XY."""
import os, sys
import numpy as np
import trimesh
from shapely.geometry import Polygon as ShapelyPolygon
from shapely.affinity import affine_transform
from shapely.ops import unary_union


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


def cross_section_world(mesh: trimesh.Trimesh, z: float):
    """to_planar()'s tf is planar→world; we apply it to polys to lift back to world XY."""
    sec = mesh.section(plane_origin=[0, 0, z], plane_normal=[0, 0, 1])
    if sec is None:
        return None
    planar, tf = sec.to_planar()
    polys = list(planar.polygons_full)
    if not polys:
        return None
    # tf: 4x4 world-from-planar. Apply the XY components to each Shapely polygon.
    # affine_transform expects (a, b, d, e, xoff, yoff): x' = a*x + b*y + xoff
    a = float(tf[0, 0]); b = float(tf[0, 1]); xoff = float(tf[0, 3])
    d = float(tf[1, 0]); e = float(tf[1, 1]); yoff = float(tf[1, 3])
    matrix = [a, b, d, e, xoff, yoff]
    lifted = [affine_transform(p, matrix) for p in polys]
    return unary_union(lifted)


def main(path_3mf: str, layer_h: float = 0.2):
    scene = trimesh.load(path_3mf, force="scene")
    nodes = scene_nodes(scene)
    fringe = nodes["fringe"]
    trap_names = sorted([n for n in nodes if n.startswith("trap_")])
    water_names = sorted([n for n in nodes if n.startswith("water")])
    print(f"[layer-slicer WORLD v3] {os.path.basename(path_3mf)}, layer_h={layer_h}")

    # Verify transform for fringe at Z=0.5 sanity check
    sanity = cross_section_world(fringe, 0.5)
    if sanity is not None:
        print(f"  [sanity] fringe cross-section at Z=0.5 area = {sanity.area:.1f} mm^2 "
              f"(expect ≈ 21,000 mm^2 for the frame)")

    zmax = float(max(fringe.bounds[1, 2], *(nodes[tn].bounds[1, 2] for tn in trap_names + water_names)))
    layer_zs = np.arange(layer_h / 2, zmax, layer_h)
    print(f"  Z range 0..{zmax:.2f}, {len(layer_zs)} layers, {len(trap_names)} traps + {len(water_names)} water")

    total_conflicts = {}
    for tn in trap_names + water_names:
        tmesh = nodes[tn]
        conflicts = []
        for li, z in enumerate(layer_zs):
            fpoly = cross_section_world(fringe, z)
            if fpoly is None or fpoly.is_empty:
                continue
            tpoly = cross_section_world(tmesh, z)
            if tpoly is None or tpoly.is_empty:
                continue
            inter = fpoly.intersection(tpoly)
            if not inter.is_empty and inter.area > 1e-3:
                conflicts.append((li + 1, float(z), float(inter.area)))
        total_conflicts[tn] = conflicts
        if not conflicts:
            print(f"  {tn}: NO fringe∩{tn} intersections at any layer  OK")
        else:
            total_area = sum(c[2] for c in conflicts)
            print(f"  {tn}: {len(conflicts)} layer(s) with intersection, sum={total_area:.1f} mm^2·layer")
            for li, z, area in conflicts[:8]:
                print(f"    layer {li:3d}  z={z:5.2f}  ∩ area = {area:.3f} mm^2")
            if len(conflicts) > 8:
                print(f"    ... ({len(conflicts) - 8} more)")

    return total_conflicts


if __name__ == "__main__":
    p = sys.argv[1] if len(sys.argv) > 1 else \
        "/Volumes/GIT/CLAUDE/SHARED_WORK_FOLDER/ItWentIn/GolfCourses/DeLaveaga/3MFs/DeLaveaga (Hole 11) [212].3mf"
    main(p)
