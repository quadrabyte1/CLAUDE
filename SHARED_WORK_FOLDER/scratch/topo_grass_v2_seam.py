"""
Post-A/B seam-integrity + green-Zmax check for grass v2.

3MF scene geometries lose the source node_name; they land as geometry_0..N in
scene-add order: green, fringe, trap_1..N, water_1..N, boulders_1..N.
So geometry_0 = green, geometry_1 = fringe.
"""
import os, sys, glob
import numpy as np
import trimesh
from scipy.spatial import cKDTree

REPO = "/Volumes/GIT/CLAUDE/SHARED_WORK_FOLDER"
sys.path.insert(0, os.path.join(REPO, "app"))
os.chdir(os.path.join(REPO, "app"))
import gradient_surface_diagnostic as gsd

DIR_3MF = os.path.join(REPO, "ItWentIn/GolfCourses/Firefly/3MFs")

targets = sorted(
    p for p in glob.glob(os.path.join(DIR_3MF, "Firefly (Hole 14)*.3mf"))
    if any(p.endswith(sfx) for sfx in ("_A_v1.3mf", "_B_v2_cone.3mf", "_C_v2_pyramid.3mf"))
)
print("Analyzing:", [os.path.basename(t) for t in targets])

for t in targets:
    print("\n" + "="*70)
    print("Analyzing:", os.path.basename(t))
    scene = trimesh.load(t, process=False)
    geoms = list(scene.geometry.items())
    green_name, green = geoms[0]
    fringe_name, fringe = geoms[1]
    print(f"  green:  {green_name}  verts={len(green.vertices)}")
    print(f"  fringe: {fringe_name} verts={len(fringe.vertices)}")

    gv = green.vertices
    fv = fringe.vertices
    top_g = gv[:, 2] > gsd.BASE_THICKNESS_MM
    top_f = fv[:, 2] > gsd.BASE_THICKNESS_MM

    g_top_xy = gv[top_g, :2]
    f_top_xy = fv[top_f, :2]
    gtree = cKDTree(g_top_xy)
    d_xy, nn_idx = gtree.query(f_top_xy, k=1)

    seam_mask = d_xy < 2.0
    if seam_mask.any():
        f_seam_z = fv[top_f, 2][seam_mask]
        g_z_at_seam = gv[top_g, 2][nn_idx[seam_mask]]
        dz_seam = np.abs(f_seam_z - g_z_at_seam)
        print(f"  seam neighborhood: {int(seam_mask.sum())} fringe verts (d_xy<2mm)")
        print(f"    XY-gap min/median/max: {d_xy[seam_mask].min():.4f} / "
              f"{np.median(d_xy[seam_mask]):.4f} / {d_xy[seam_mask].max():.4f} mm")
        print(f"    Z-gap  min/median/max: {dz_seam.min():.4f} / "
              f"{np.median(dz_seam):.4f} / {dz_seam.max():.4f} mm")
        contact = d_xy[seam_mask] < 0.5
        if contact.any():
            print(f"    tight-contact verts (XY<0.5mm): {int(contact.sum())}   "
                  f"Z-gap max={dz_seam[contact].max():.4f} mm")

    print(f"  Green Zmax:  {gv[:, 2].max():.4f} mm (all)   "
          f"{gv[top_g, 2].max():.4f} mm (top-only)")
    print(f"  Fringe Zmax: {fv[:, 2].max():.4f} mm")
