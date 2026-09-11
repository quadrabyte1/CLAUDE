"""Verify green surface has no grass texture after Topo 2026-09-09 revert.

Reads a 3MF, extracts the `green_surface` and `fringe` nodes, and reports
Z-statistics for their top-vertex layers.

Usage:
    python3 verify_green_grass_removal.py <path_to_3mf>
"""

import sys
import numpy as np
import trimesh


def top_layer_stats(mesh: trimesh.Trimesh, label: str, layer_frac: float = 0.05):
    """Report Z stats for vertices in the top layer_frac of the mesh's Z range."""
    v = mesh.vertices
    zmin, zmax = float(v[:, 2].min()), float(v[:, 2].max())
    zr = zmax - zmin
    if zr <= 0:
        print(f"  [{label}] flat mesh (zmin={zmin}, zmax={zmax})")
        return
    # Top-vertex band = vertices whose Z is within layer_frac of the top.
    thresh = zmax - max(0.5, zr * layer_frac)  # at least 0.5 mm band
    top_mask = v[:, 2] >= thresh
    top_z = v[top_mask, 2]
    print(f"  [{label}] verts={len(v)}  Zmin={zmin:.3f}  Zmax={zmax:.3f}")
    print(f"          top-band (Z>={thresh:.3f}): n={top_mask.sum()}  "
          f"stddev={float(top_z.std()):.4f}  mean={float(top_z.mean()):.3f}")

    # "Interior" for the green: exclude a rim in XY.
    xmin, xmax = float(v[:, 0].min()), float(v[:, 0].max())
    ymin, ymax = float(v[:, 1].min()), float(v[:, 1].max())
    inset_frac = 0.15
    xr = xmax - xmin
    yr = ymax - ymin
    x_lo, x_hi = xmin + xr * inset_frac, xmax - xr * inset_frac
    y_lo, y_hi = ymin + yr * inset_frac, ymax - yr * inset_frac
    interior_mask = (
        top_mask
        & (v[:, 0] >= x_lo) & (v[:, 0] <= x_hi)
        & (v[:, 1] >= y_lo) & (v[:, 1] <= y_hi)
    )
    if interior_mask.any():
        iz = v[interior_mask, 2]
        print(f"          interior top-band (15% inset): n={interior_mask.sum()}  "
              f"stddev={float(iz.std()):.4f}  Zmax={float(iz.max()):.3f}")


def main(path):
    scene = trimesh.load(path)
    if isinstance(scene, trimesh.Trimesh):
        geoms = {"root": scene}
    else:
        geoms = dict(scene.geometry)
    print(f"3MF: {path}")
    print(f"Nodes: {list(geoms.keys())}")
    # 3MFs saved by trimesh Scene lose node_name — identify by vertex count:
    # fringe is always the highest (~200k), green is second highest (~30k),
    # traps/water are far smaller (<5k each).
    items = list(geoms.items())
    items.sort(key=lambda kv: len(kv[1].vertices), reverse=True)
    fringe_name, fringe_mesh = items[0]
    green_name, green_mesh = items[1]
    print(f"\n=== GREEN (guessed: {green_name}) ===")
    top_layer_stats(green_mesh, "green")
    print(f"\n=== FRINGE (guessed: {fringe_name}) ===")
    top_layer_stats(fringe_mesh, "fringe")


if __name__ == "__main__":
    main(sys.argv[1])
