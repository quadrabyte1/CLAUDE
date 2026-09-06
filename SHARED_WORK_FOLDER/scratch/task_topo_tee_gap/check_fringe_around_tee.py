"""Determine whether the fringe surrounds the collar (proper hole+fringe wall)
or leaves a floating collar in a void.

Method: at Z=1.0, look at fringe main body (comp0 only, exclude collar comp1),
and check if that main body contains points at various offsets around the tee.
If YES → fringe extends to the collar (touching, or with a small gap).
If NO → fringe is missing around the tee (visible XY gap).
"""
import sys
import numpy as np
import trimesh
from shapely.geometry import Polygon as ShapelyPolygon, Point as SP
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


three_mf = sys.argv[1] if len(sys.argv) > 1 else "/Volumes/GIT/CLAUDE/SHARED_WORK_FOLDER/ItWentIn/GolfCourses/Firefly/3MFs/Firefly (Hole 14) [108].3mf"
egm_path = "/Volumes/GIT/CLAUDE/SHARED_WORK_FOLDER/ItWentIn/GolfCourses/Firefly/EGMs/Firefly (Hole 14).egm"

egm, _img, _gpx = load_egm(egm_path)
tee = egm["tee_hole"]
half = PRINT_SIZE_MM/2 + FRINGE_XY_EXPANSION_MM/2
cx = -half + float(tee["x_mm"])
cy = +half - float(tee["y_mm"])
collar_r = TEE_HOLE_COLLAR_OD_MM / 2

sc = trimesh.load(three_mf, force="scene")
nodes = scene_nodes(sc)
fringe = next(v for k, v in nodes.items() if "fringe" in k.lower())
comps = fringe.split(only_watertight=False)
# Main body is the biggest by faces
main = max(comps, key=lambda c: len(c.faces))
print(f"Main fringe body: {len(main.vertices)} verts, {len(main.faces)} faces")

# Section the main body at Z=1.0 (should be full fringe cross-section, no collar)
for z in [0.5, 1.0, 3.0, 5.0]:
    sec = main.section(plane_origin=[0,0,z], plane_normal=[0,0,1])
    if sec is None:
        print(f"Z={z}: no section")
        continue
    # Build shapely polygons from the loops (world coords in sec.vertices)
    polys_sh = []
    for ent in sec.entities:
        try:
            pts = sec.vertices[ent.points]
            if len(pts) >= 3:
                sp = ShapelyPolygon(pts[:, :2])
                if not sp.is_valid:
                    sp = sp.buffer(0)
                if not sp.is_empty and sp.area > 0.01:
                    polys_sh.append(sp)
        except Exception:
            continue
    u = unary_union(polys_sh)

    tee_pt = SP(cx, cy)
    # Distance from tee to nearest boundary of u
    boundary_dist = tee_pt.distance(u.boundary if hasattr(u, "boundary") else u)
    contains = u.contains(tee_pt)
    print(f"\nZ={z}: main fringe cross-section unary_union area={u.area:.1f}, boundary loops={len(polys_sh)}")
    print(f"  tee_pt in main fringe? {contains}")
    print(f"  tee_pt distance to main fringe boundary: {boundary_dist:.4f} mm")

    # Sample points around the tee at radius collar_r + guard (0.15, 0.5, 1.0, 2.0 mm)
    for guard in [0.15, 0.5, 1.0, 2.0]:
        r = collar_r + guard
        angles = np.linspace(0, 2*np.pi, 24, endpoint=False)
        n_in = 0
        for a in angles:
            p = SP(cx + r * np.cos(a), cy + r * np.sin(a))
            if u.contains(p):
                n_in += 1
        print(f"  ring at collar_r+{guard}={r:.2f}: {n_in}/24 sample pts inside fringe")
