"""At Z=8, dump every fringe cross-section piece + check which intersects trap_1 mesh section."""
import sys
import numpy as np
import trimesh
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

def main():
    p3mf = "/Volumes/GIT/CLAUDE/SHARED_WORK_FOLDER/ItWentIn/GolfCourses/DeLaveaga/3MFs/DeLaveaga (Hole 11) [212].3mf"
    scene = trimesh.load(p3mf, force="scene")
    nodes = scene_nodes(scene)
    fringe = nodes["fringe"]
    trap1 = nodes["trap_1"]

    z = 8.0
    sec_f = fringe.section(plane_origin=[0, 0, z], plane_normal=[0, 0, 1])
    pf, _tf = sec_f.to_planar()
    fringe_polys = list(pf.polygons_full)
    print(f"Z={z}: fringe = {len(fringe_polys)} polygons")

    sec_t = trap1.section(plane_origin=[0, 0, z], plane_normal=[0, 0, 1])
    pt, _tt = sec_t.to_planar()
    trap_polys = list(pt.polygons_full)
    print(f"Z={z}: trap_1 = {len(trap_polys)} polygons")
    for i, tp in enumerate(trap_polys):
        b = tp.bounds
        print(f"  trap_1 piece {i}: bbox X[{b[0]:.1f},{b[2]:.1f}] Y[{b[1]:.1f},{b[3]:.1f}] area={tp.area:.1f}")

    trap_u = unary_union(trap_polys)

    print(f"\nFringe pieces that intersect trap_1 mesh cross-section:")
    for i, fp in enumerate(fringe_polys):
        inter = fp.intersection(trap_u)
        if inter.is_empty or inter.area < 0.01:
            continue
        b = fp.bounds
        print(f"  fringe piece {i}: bbox X[{b[0]:.1f},{b[2]:.1f}] Y[{b[1]:.1f},{b[3]:.1f}] "
              f"area={fp.area:.1f}  ∩trap_1={inter.area:.2f}  interiors={len(list(fp.interiors))}")

    # Compare with fringe's own SHAPELY footprint at ANY Z (e.g. bottom cap)
    # The bottom cap should have the trap cutouts.
    z = 0.5
    sec_f0 = fringe.section(plane_origin=[0, 0, z], plane_normal=[0, 0, 1])
    if sec_f0 is not None:
        pf0, _ = sec_f0.to_planar()
        fringe_bottom = unary_union(list(pf0.polygons_full))
        print(f"\nZ={z} (bottom slab) fringe cross-section area = {fringe_bottom.area:.1f} mm^2")
        inter_bot = fringe_bottom.intersection(trap_u)
        print(f"  fringe(bottom) ∩ trap_1(z=8) = {inter_bot.area:.2f} mm^2")


if __name__ == "__main__":
    main()
