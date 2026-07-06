"""
Task 487 — check whether the green mesh's arc near the fringe bulge really is
tall, or whether the k=1 sampler is inventing tallness that isn't there.
"""
from __future__ import annotations

import sys, zipfile, xml.etree.ElementTree as ET
from pathlib import Path
import numpy as np

p = Path(sys.argv[1] if len(sys.argv) > 1
         else "scratch/task_486/Los_Lagos_Hole_16_task_486_test.3mf")
with zipfile.ZipFile(p, "r") as z:
    model_names = [n for n in z.namelist() if n.endswith("3dmodel.model")]
    with z.open(model_names[0]) as fh:
        tree = ET.parse(fh)
    root = tree.getroot()
    ns = {"m": "http://schemas.microsoft.com/3dmanufacturing/core/2015/02"}
    objs = {}
    for obj in root.findall(".//m:resources/m:object", ns):
        oid = obj.get("id")
        verts = []
        for v in obj.findall(".//m:mesh/m:vertices/m:vertex", ns):
            verts.append(
                (float(v.get("x")), float(v.get("y")), float(v.get("z")))
            )
        objs[oid] = np.array(verts, dtype=np.float64)

# geometry_0 (id=1) is the green (dx=106, dy=114, z_max=19.5).
green = objs["1"]
fringe = objs["2"]
print(f"Green nverts={len(green)} z range [{green[:,2].min():.3f}, "
      f"{green[:,2].max():.3f}]")
print(f"Fringe nverts={len(fringe)} z range [{fringe[:,2].min():.3f}, "
      f"{fringe[:,2].max():.3f}]")

# Green verts near the fringe-bulge region  x in [-85, -30]  y in [-8, +20]
mask = ((green[:, 0] >= -85) & (green[:, 0] <= -30)
        & (green[:, 1] >= -10) & (green[:, 1] <= 25)
        & (green[:, 2] > 2.0))
sub = green[mask]
print(f"\nGreen verts inside fringe-bulge XY window (n={mask.sum()}):")
if mask.any():
    print(f"  Z range: [{sub[:,2].min():.3f}, {sub[:,2].max():.3f}]")
    print(f"  Z median: {np.median(sub[:,2]):.3f}   p95: "
          f"{np.percentile(sub[:,2], 95):.3f}   p99: "
          f"{np.percentile(sub[:,2], 99):.3f}")

# Green's HIGHEST verts, where are they?
gtop_idx = np.argsort(green[:, 2])[-30:]
print("\nGreen mesh top 30 tallest verts:")
for i in gtop_idx[::-1]:
    print(f"  ({green[i,0]:+.2f}, {green[i,1]:+.2f}, {green[i,2]:.3f})")
