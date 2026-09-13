#!/usr/bin/env python3
"""
topo_measure_gaps_506.py — verify gap halving (task 506).

Loads a 3MF, extracts named component meshes (green, fringe, trap, water),
computes nearest-neighbor XY distance from each cutout's outer-boundary
vertices to the fringe's inner-boundary vertices at that cutout.

Green↔fringe: pretty clean, one outer green polyline vs the inner ring of
the fringe hole around the green.
Trap↔fringe / Water↔fringe: multiple polys possible; concatenate all
boundary points and use nearest-neighbor.

Usage:
    python3 topo_measure_gaps_506.py <path-to-3mf>
"""

from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import trimesh
from scipy.spatial import cKDTree


BASE_Z_THRESH = 2.5  # mm — verts above this are top surface (base is 2 mm)


def _outer_boundary_xy(mesh: trimesh.Trimesh, z_max: float | None = None) -> np.ndarray:
    """Return XY of vertices that lie on the outer boundary of `mesh`.

    Uses trimesh's `outline` (edges belonging to exactly one face). We keep
    the vertices with the LOWEST Z (the base ring at Z=0 for most pieces),
    which is the true horizontal outer boundary at the interface plane.
    """
    outline = mesh.outline()
    if outline is None:
        # Fallback: use all vertices at z <= 0.05
        v = mesh.vertices
        mask = v[:, 2] <= 0.05
        return v[mask, :2]
    pts = np.asarray(outline.vertices)
    if z_max is not None:
        pts = pts[pts[:, 2] <= z_max]
    return pts[:, :2]


def _classify_geometry(name: str) -> str:
    n = name.lower()
    if "green" in n:
        return "green"
    if "fringe" in n:
        return "fringe"
    if "trap" in n or "bunker" in n or "sand" in n:
        return "trap"
    if "water" in n or "pond" in n or "lake" in n:
        return "water"
    return "other"


def measure_3mf(path: Path) -> dict:
    scene = trimesh.load(str(path), force="scene")
    if isinstance(scene, trimesh.Trimesh):
        # Single-mesh 3MF is not what we expect; bail cleanly.
        return {"error": "loaded as single Trimesh, not Scene"}

    # 3MF renames geometry to `geometry_N` — recover semantic names from graph.
    node_to_geom: dict[str, str] = {}
    for node in scene.graph.nodes:
        try:
            _tf, geom_name = scene.graph[node]
            if geom_name is not None:
                node_to_geom[node] = geom_name
        except Exception:
            pass

    groups: dict[str, list] = {
        "green": [], "fringe": [], "trap": [], "water": [], "other": [],
    }
    for node_name, geom_key in node_to_geom.items():
        geom = scene.geometry.get(geom_key)
        if not isinstance(geom, trimesh.Trimesh):
            continue
        cls = _classify_geometry(node_name)
        groups[cls].append((node_name, geom))

    print(f"\n{'='*72}")
    print(f"3MF: {path.name}")
    print(f"{'='*72}")
    for k, lst in groups.items():
        print(f"  {k:6s}: {len(lst)} mesh(es)")
        for nm, gm in lst:
            print(f"           - {nm}  (verts={len(gm.vertices)}, "
                  f"z=[{gm.vertices[:,2].min():.3f}, {gm.vertices[:,2].max():.3f}])")

    if not groups["fringe"]:
        return {"error": "no fringe mesh found"}

    # Combine fringe boundary points
    fringe_bd = np.vstack([_outer_boundary_xy(g, z_max=0.05) for _, g in groups["fringe"]])
    if len(fringe_bd) < 5:
        # Try again without z filter
        fringe_bd = np.vstack([_outer_boundary_xy(g) for _, g in groups["fringe"]])
    print(f"\n  fringe boundary points (z<=0.05): {len(fringe_bd)}")
    fringe_tree = cKDTree(fringe_bd)

    results: dict[str, dict] = {}

    for cutout_kind in ("green", "trap", "water"):
        if not groups[cutout_kind]:
            continue
        cut_bd = np.vstack([_outer_boundary_xy(g, z_max=0.05) for _, g in groups[cutout_kind]])
        if len(cut_bd) < 5:
            cut_bd = np.vstack([_outer_boundary_xy(g) for _, g in groups[cutout_kind]])
        if len(cut_bd) == 0:
            continue
        d, _ = fringe_tree.query(cut_bd, k=1)
        results[cutout_kind] = {
            "n_points": int(len(cut_bd)),
            "median_mm": float(np.median(d)),
            "mean_mm": float(np.mean(d)),
            "p05_mm": float(np.percentile(d, 5)),
            "p95_mm": float(np.percentile(d, 95)),
            "min_mm": float(np.min(d)),
            "max_mm": float(np.max(d)),
        }

    # Green Zmax smoke test
    if groups["green"]:
        green_zmax = max(float(g.vertices[:, 2].max()) for _, g in groups["green"])
        results["green_zmax_mm"] = green_zmax

    return results


def main():
    if len(sys.argv) < 2:
        print("Usage: topo_measure_gaps_506.py <3mf-path> [<3mf-path> ...]")
        sys.exit(1)
    for arg in sys.argv[1:]:
        p = Path(arg).expanduser().resolve()
        if not p.exists():
            print(f"MISSING: {p}")
            continue
        r = measure_3mf(p)
        print("\n  RESULTS:")
        for k, v in r.items():
            if isinstance(v, dict):
                print(f"    {k:8s}: n={v['n_points']:5d}  "
                      f"median={v['median_mm']:.3f} mm  "
                      f"mean={v['mean_mm']:.3f}  "
                      f"p05={v['p05_mm']:.3f}  p95={v['p95_mm']:.3f}  "
                      f"min={v['min_mm']:.3f}  max={v['max_mm']:.3f}")
            else:
                print(f"    {k:20s}: {v}")


if __name__ == "__main__":
    main()
