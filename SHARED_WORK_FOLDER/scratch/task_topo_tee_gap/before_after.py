"""Before/after diagnostic:
- Plot fringe main-body top-surface verts (Z>3) near tee position
- Plot collar tube cross-section
- Overlay collar OD/ID for reference
"""
import sys, os
import numpy as np
import matplotlib.pyplot as plt
from matplotlib.patches import Circle
import trimesh

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


BEFORE = "/Volumes/GIT/CLAUDE/SHARED_WORK_FOLDER/ItWentIn/GolfCourses/Firefly/3MFs/Firefly (Hole 14) [104].3mf"
AFTER = "/Volumes/GIT/CLAUDE/SHARED_WORK_FOLDER/ItWentIn/GolfCourses/Firefly/3MFs/Firefly (Hole 14) [110].3mf"

egm_path = "/Volumes/GIT/CLAUDE/SHARED_WORK_FOLDER/ItWentIn/GolfCourses/Firefly/EGMs/Firefly (Hole 14).egm"
egm, _img, _gpx = load_egm(egm_path)
tee = egm["tee_hole"]
half = PRINT_SIZE_MM/2 + FRINGE_XY_EXPANSION_MM/2
cx = -half + float(tee["x_mm"])
cy = +half - float(tee["y_mm"])

fig, axes = plt.subplots(1, 2, figsize=(18, 9))

for ax, three_mf, title in zip(axes, [BEFORE, AFTER], ["BEFORE v4.46 (Firefly [104])", "AFTER v4.47 (Firefly [110]) — task 748 fix"]):
    sc = trimesh.load(three_mf, force="scene")
    nodes = scene_nodes(sc)
    fringe = next(v for k, v in nodes.items() if "fringe" in k.lower())
    comps = fringe.split(only_watertight=False)
    main = max(comps, key=lambda c: len(c.faces))
    collar = min(comps, key=lambda c: len(c.faces))
    V = main.vertices
    dxy = np.hypot(V[:, 0] - cx, V[:, 1] - cy)
    # Top-surface verts within 15 mm of tee
    near_top = (dxy < 15) & (V[:, 2] > 3.0)
    xy = V[near_top, :2]
    ax.scatter(xy[:, 0], xy[:, 1], s=3, c='steelblue', alpha=0.5, label=f'fringe top verts (Z>3) — {near_top.sum()}')

    # Collar tube verts
    Vc = collar.vertices
    ax.scatter(Vc[:, 0], Vc[:, 1], s=8, c='green', alpha=0.6, label=f'collar tube verts')

    # Collar OD / ID
    ax.add_patch(Circle((cx, cy), TEE_HOLE_COLLAR_OD_MM/2, fill=False, edgecolor='red', linewidth=2, label=f'collar OD (r={TEE_HOLE_COLLAR_OD_MM/2:.3f})'))
    ax.add_patch(Circle((cx, cy), TEE_HOLE_DIAMETER_MM/2, fill=False, edgecolor='orange', linewidth=1.5, label=f'collar ID / bore (r={TEE_HOLE_DIAMETER_MM/2:.3f})'))
    # Ideal fringe boundary (collar_r + 0.15 guard)
    ax.add_patch(Circle((cx, cy), TEE_HOLE_COLLAR_OD_MM/2 + 0.15, fill=False, edgecolor='purple', linewidth=1, ls='--', label='ideal fringe inner boundary (collar_r+0.15)'))
    ax.plot(cx, cy, 'k+', markersize=15, mew=2)
    ax.set_aspect('equal')
    ax.set_xlim(cx-10, cx+10)
    ax.set_ylim(cy-10, cy+10)
    ax.grid(True, alpha=0.3)
    ax.set_title(title)
    ax.legend(loc='upper right', fontsize=7)

fig.suptitle(f"Firefly Hole 14 tee-cylinder fringe gap  |  tee mesh XY=({cx:.2f},{cy:.2f})", fontsize=12)
out = "/Volumes/GIT/CLAUDE/SHARED_WORK_FOLDER/scratch/task_topo_tee_gap/before_after.png"
plt.savefig(out, dpi=140, bbox_inches='tight')
print(f"saved {out}")
