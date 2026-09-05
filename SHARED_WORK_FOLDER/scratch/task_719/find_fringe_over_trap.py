"""Find fringe faces (any face) that sit ABOVE trap_1's XY footprint at high Z."""
import sys, os
import numpy as np
import trimesh
from shapely.geometry import Polygon as ShapelyPolygon, Point, LineString

APP_DIR = "/Volumes/GIT/CLAUDE/SHARED_WORK_FOLDER/app"
sys.path.insert(0, APP_DIR)
from gradient_surface_diagnostic import load_egm, _compute_px_to_mm, _px_to_mm_2d, _poly_to_dense_px, _clip_polygon_to_fringe_rect

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

def main():
    p3mf = "/Volumes/GIT/CLAUDE/SHARED_WORK_FOLDER/ItWentIn/GolfCourses/DeLaveaga/3MFs/DeLaveaga (Hole 11) [212].3mf"
    egm_path = "/Volumes/GIT/CLAUDE/SHARED_WORK_FOLDER/ItWentIn/GolfCourses/DeLaveaga/EGMs/DeLaveaga (Hole 11).egm"

    scene = trimesh.load(p3mf, force="scene")
    nodes = scene_nodes(scene)
    fringe = nodes["fringe"]

    egm, _img, gpx = load_egm(egm_path)
    scale, centroid_px = _compute_px_to_mm(gpx, egm)
    trap_polys_raw = [p for p in egm["polygons"] if p.get("type") == "trap"]
    tp1_px = _poly_to_dense_px(trap_polys_raw[0])
    tp1_mm = _px_to_mm_2d(tp1_px, scale, centroid_px)
    tp1 = ShapelyPolygon(tp1_mm)
    if not tp1.is_valid:
        tp1 = tp1.buffer(0)
    tp1 = _clip_polygon_to_fringe_rect(tp1, "Trap 1") or tp1

    print(f"trap_1 area = {tp1.area:.1f} mm^2, bounds = {tp1.bounds}")
    print(f"fringe mesh: {len(fringe.faces)} faces, Z[{fringe.bounds[0,2]:.2f}, {fringe.bounds[1,2]:.2f}]")

    # For every fringe face, check if ANY vertex sits inside trap_1 polygon
    tri_v = fringe.triangles
    ax, ay = tri_v[:, 0, 0], tri_v[:, 0, 1]
    bx, by = tri_v[:, 1, 0], tri_v[:, 1, 1]
    cx, cy = tri_v[:, 2, 0], tri_v[:, 2, 1]

    from shapely import contains_xy
    va_in = contains_xy(tp1, ax, ay)
    vb_in = contains_xy(tp1, bx, by)
    vc_in = contains_xy(tp1, cx, cy)
    any_in = va_in | vb_in | vc_in
    all_in = va_in & vb_in & vc_in
    print(f"\nfringe faces with ANY vertex inside trap_1: {int(any_in.sum())}")
    print(f"fringe faces with ALL 3 vertices inside trap_1: {int(all_in.sum())}")

    # Also: point-in-triangle test — is trap_1's rep point covered by any fringe tri?
    rep = tp1.representative_point()
    rx, ry = float(rep.x), float(rep.y)
    d1 = (rx - bx) * (ay - by) - (ax - bx) * (ry - by)
    d2 = (rx - cx) * (by - cy) - (bx - cx) * (ry - cy)
    d3 = (rx - ax) * (cy - ay) - (cx - ax) * (ry - ay)
    has_neg = (d1 < 0) | (d2 < 0) | (d3 < 0)
    has_pos = (d1 > 0) | (d2 > 0) | (d3 > 0)
    covers_rep = ~(has_neg & has_pos)
    print(f"fringe faces covering trap_1 rep point ({rx:.2f},{ry:.2f}): {int(covers_rep.sum())}")

    # Sample vertical rays and check Z coverage over trap_1's interior
    print(f"\n== Ray-cast at 20 sample points inside trap_1 ==")
    from shapely.geometry import Point as SP
    import numpy as np
    minx, miny, maxx, maxy = tp1.bounds
    origins = []
    checks_done = 0
    xs = np.linspace(minx + 1, maxx - 1, 6)
    ys = np.linspace(miny + 1, maxy - 1, 6)
    for x in xs:
        for y in ys:
            if not tp1.contains(SP(x, y)):
                continue
            # Ray going up from z=-1
            ori = np.array([[x, y, -1.0]])
            dirs = np.array([[0, 0, 1.0]])
            locs, idx_ray, idx_tri = fringe.ray.intersects_location(ori, dirs)
            if len(locs) == 0:
                continue
            zs = locs[:, 2]
            print(f"  ({x:6.1f},{y:6.1f}) fringe hits at Z: {sorted([f'{z:.2f}' for z in zs])}")
            checks_done += 1
            if checks_done >= 12:
                break
        if checks_done >= 12:
            break


if __name__ == "__main__":
    main()
