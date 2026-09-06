"""Look inside comp1 (the collar) at its actual vertex distribution."""
import sys
import numpy as np
import trimesh

APP_DIR = "/Volumes/GIT/CLAUDE/SHARED_WORK_FOLDER/app"
sys.path.insert(0, APP_DIR)


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

sc = trimesh.load(three_mf, force="scene")
nodes = scene_nodes(sc)
fringe = next(v for k, v in nodes.items() if "fringe" in k.lower())
comps = fringe.split(only_watertight=False)
comp1 = comps[1]

print(f"comp1: {len(comp1.vertices)} verts")

# Group by Z
zs = np.unique(comp1.vertices[:, 2])
print(f"unique Z values: {zs}")
for z in zs:
    mask = np.isclose(comp1.vertices[:, 2], z)
    xy = comp1.vertices[mask, :2]
    mean_x, mean_y = xy[:, 0].mean(), xy[:, 1].mean()
    r = np.hypot(xy[:, 0] - mean_x, xy[:, 1] - mean_y)
    r_from_expected = np.hypot(xy[:, 0] + 41.9965, xy[:, 1] - 61.0965)
    print(f"  Z={z:.4f}: {mask.sum()} verts, mean XY=({mean_x:.4f}, {mean_y:.4f}), r_from_mean [{r.min():.4f},{r.max():.4f}], r_from_tee [{r_from_expected.min():.4f},{r_from_expected.max():.4f}]")

# Cross-section comp1 at Z=1.0
sec = comp1.section(plane_origin=[0,0,1.0], plane_normal=[0,0,1])
if sec is not None:
    planar, _tf = sec.to_planar()
    polys = list(planar.polygons_full)
    print(f"\ncomp1 cross-section at Z=1.0: {len(polys)} polys")
    for i, p in enumerate(polys):
        ec = np.array(list(p.exterior.coords))
        cx, cy = ec[:, 0].mean(), ec[:, 1].mean()
        print(f"  poly{i}: exterior mean=({cx:.4f}, {cy:.4f}) area={p.area:.4f}")
        for j, hole in enumerate(p.interiors):
            hc = np.array(list(hole.coords))
            hmx, hmy = hc[:, 0].mean(), hc[:, 1].mean()
            print(f"    hole{j} mean=({hmx:.4f}, {hmy:.4f}) area={list(hole.coords) and 0}")

# Look at raw section entities
if sec is not None:
    print(f"\nsec (Path3D) — entities: {len(sec.entities)}")
    for i, ent in enumerate(sec.entities[:6]):
        pts = sec.vertices[ent.points]
        print(f"  entity {i}: {len(pts)} pts, first={pts[0]}, last={pts[-1]}")
