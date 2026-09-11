"""Inspect each geometry in the latest Firefly 3MF."""
import os, trimesh, numpy as np
REPO = "/Volumes/GIT/CLAUDE/SHARED_WORK_FOLDER"
FIREFLY = os.path.join(REPO, "ItWentIn/GolfCourses/Firefly/3MFs")
latest = sorted(
    [f for f in os.listdir(FIREFLY) if f.endswith(".3mf")],
    key=lambda n: int(n.rsplit("[", 1)[1].rstrip("].3mf"))
)[-1]
print(latest)
scene = trimesh.load(os.path.join(FIREFLY, latest), process=False)
for k, m in scene.geometry.items():
    v = m.vertices
    print(f"{k}: verts={len(v)} faces={len(m.faces)}  "
          f"X[{v[:,0].min():.1f},{v[:,0].max():.1f}] "
          f"Y[{v[:,1].min():.1f},{v[:,1].max():.1f}] "
          f"Z[{v[:,2].min():.2f},{v[:,2].max():.2f}]")
