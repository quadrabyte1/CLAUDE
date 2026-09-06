"""What Z is the fringe top surface at the tee location?
- Sample fringe top verts in a small disk around the tee
- Compare to tube_top (11.39 mm) and collar Z range
"""
import sys
import numpy as np
import trimesh

APP_DIR = "/Volumes/GIT/CLAUDE/SHARED_WORK_FOLDER/app"
sys.path.insert(0, APP_DIR)
from gradient_surface_diagnostic import (
    load_egm, PRINT_SIZE_MM, FRINGE_XY_EXPANSION_MM,
    TEE_HOLE_COLLAR_OD_MM,
    BASE_THICKNESS_MM,
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


for path in ["/Volumes/GIT/CLAUDE/SHARED_WORK_FOLDER/ItWentIn/GolfCourses/Firefly/3MFs/Firefly (Hole 14) [104].3mf",
             "/Volumes/GIT/CLAUDE/SHARED_WORK_FOLDER/ItWentIn/GolfCourses/Firefly/3MFs/Firefly (Hole 14) [110].3mf"]:
    egm_path = "/Volumes/GIT/CLAUDE/SHARED_WORK_FOLDER/ItWentIn/GolfCourses/Firefly/EGMs/Firefly (Hole 14).egm"
    egm, _img, _gpx = load_egm(egm_path)
    tee = egm["tee_hole"]
    half = PRINT_SIZE_MM/2 + FRINGE_XY_EXPANSION_MM/2
    cx = -half + float(tee["x_mm"])
    cy = +half - float(tee["y_mm"])
    collar_r = TEE_HOLE_COLLAR_OD_MM / 2

    sc = trimesh.load(path, force="scene")
    nodes = scene_nodes(sc)
    fringe = next(v for k, v in nodes.items() if "fringe" in k.lower())
    comps = fringe.split(only_watertight=False)
    main = max(comps, key=lambda c: len(c.faces))
    collar_comp = min(comps, key=lambda c: len(c.faces))

    V = main.vertices
    dxy = np.hypot(V[:, 0] - cx, V[:, 1] - cy)

    print(f"\n=== {path.split('/')[-1]} ===")
    print(f"Main body verts: {len(V)}")
    print(f"Collar comp Z range: {collar_comp.bounds[0,2]:.4f} .. {collar_comp.bounds[1,2]:.4f}")
    tube_top = collar_comp.bounds[1, 2]

    # Top surface = z > BASE_THICKNESS_MM * 0.5 (2mm base slab, water lift adds another 2mm)
    for r_range in [(0, 3.5), (3.5, 5.0), (5.0, 10.0), (10.0, 20.0)]:
        r_lo, r_hi = r_range
        mask = (dxy >= r_lo) & (dxy < r_hi) & (V[:, 2] > 1.5)  # top-surface only
        if mask.any():
            zs = V[mask, 2]
            print(f"  main body verts in r=[{r_lo:.1f},{r_hi:.1f}] mm with Z>1.5: n={int(mask.sum())} Z=[{zs.min():.3f},{zs.max():.3f}] mean={zs.mean():.3f}")
        else:
            print(f"  main body verts in r=[{r_lo:.1f},{r_hi:.1f}] mm with Z>1.5: NONE")

    # Also: sample the raw top surface at tee position by finding the max Z of any main-body vertex within 1 mm
    close_v = dxy < 1.0
    if close_v.any():
        print(f"  Nearest main-body top verts within 1 mm of tee: n={int(close_v.sum())} Zmax={V[close_v, 2].max():.3f}")
    else:
        print(f"  No main-body verts within 1 mm of tee")

    print(f"  Collar tube top Z: {tube_top:.3f}")
    print(f"  --> If fringe_top > collar_top at tee, collar is BURIED (no gap visible)")
    print(f"  --> If fringe_top < collar_top at tee, collar POKES OUT")
