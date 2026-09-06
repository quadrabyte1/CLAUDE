"""Plot fringe cross-section at Z=1.0 with tee and collar overlaid."""
import sys, os
import numpy as np
import matplotlib.pyplot as plt
from matplotlib.patches import Circle, Polygon as MplPoly
import trimesh
from shapely.geometry import Polygon as ShapelyPolygon

APP_DIR = "/Volumes/GIT/CLAUDE/SHARED_WORK_FOLDER/app"
sys.path.insert(0, APP_DIR)
from gradient_surface_diagnostic import (
    load_egm, PRINT_SIZE_MM, FRINGE_XY_EXPANSION_MM,
    TEE_HOLE_COLLAR_OD_MM, TEE_HOLE_DIAMETER_MM,
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


three_mf = sys.argv[1] if len(sys.argv) > 1 else "/Volumes/GIT/CLAUDE/SHARED_WORK_FOLDER/ItWentIn/GolfCourses/Firefly/3MFs/Firefly (Hole 14) [110].3mf"
egm_path = "/Volumes/GIT/CLAUDE/SHARED_WORK_FOLDER/ItWentIn/GolfCourses/Firefly/EGMs/Firefly (Hole 14).egm"

egm, _img, _gpx = load_egm(egm_path)
tee = egm["tee_hole"]
half = PRINT_SIZE_MM/2 + FRINGE_XY_EXPANSION_MM/2
cx = -half + float(tee["x_mm"])
cy = +half - float(tee["y_mm"])

sc = trimesh.load(three_mf, force="scene")
nodes = scene_nodes(sc)
fringe = next(v for k, v in nodes.items() if "fringe" in k.lower())

fig, axes = plt.subplots(1, 2, figsize=(18, 9))

for ax, z in zip(axes, [1.0, 5.0]):
    sec = fringe.section(plane_origin=[0,0,z], plane_normal=[0,0,1])
    if sec is None:
        continue
    planar, _tf = sec.to_planar()
    polys = list(planar.polygons_full)
    for i, p in enumerate(polys):
        if p.exterior is None:
            continue
        ec = np.array(list(p.exterior.coords))
        color = f"C{i%10}"
        ax.fill(ec[:,0], ec[:,1], color=color, alpha=0.3, label=f"poly{i} area={p.area:.0f}")
        ax.plot(ec[:,0], ec[:,1], color=color, lw=0.8)
        for j, hole in enumerate(p.interiors):
            hc = np.array(list(hole.coords))
            ax.fill(hc[:,0], hc[:,1], color='white')
            ax.plot(hc[:,0], hc[:,1], 'k-', lw=0.5)

    # Overlay tee position with collar radii
    ax.add_patch(Circle((cx, cy), TEE_HOLE_COLLAR_OD_MM/2, fill=False, edgecolor='red', linewidth=2, label='collar OD (should surround)'))
    ax.add_patch(Circle((cx, cy), TEE_HOLE_DIAMETER_MM/2, fill=False, edgecolor='orange', linewidth=1.5, label='collar ID'))
    ax.plot(cx, cy, 'r+', markersize=15, mew=3, label=f'EGM tee ({cx:.2f},{cy:.2f})')

    ax.set_aspect('equal')
    ax.set_xlim(cx-25, cx+25)
    ax.set_ylim(cy-25, cy+25)
    ax.set_title(f"Fringe cross-section at Z={z} mm — {os.path.basename(three_mf)}")
    ax.legend(loc='upper right', fontsize=7)
    ax.grid(True, alpha=0.3)

out = "/Volumes/GIT/CLAUDE/SHARED_WORK_FOLDER/scratch/task_topo_tee_gap/fringe_slice_at_tee.png"
plt.savefig(out, dpi=140, bbox_inches='tight')
print(f"saved {out}")
