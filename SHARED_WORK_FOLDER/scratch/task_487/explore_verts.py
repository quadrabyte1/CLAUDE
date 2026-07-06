"""
Task 487 — diagnostic exploration of what's in the post-486 3MF.

Print per-object Z distributions and the top-N absolute-Z verts across
all objects, so we can locate the "pointy peak" the owner is seeing.
"""
from __future__ import annotations

import sys
import zipfile
import xml.etree.ElementTree as ET
from pathlib import Path
import numpy as np


def iter_objects(path):
    with zipfile.ZipFile(path, "r") as z:
        model_names = [n for n in z.namelist() if n.endswith("3dmodel.model")]
        with z.open(model_names[0]) as fh:
            tree = ET.parse(fh)
        root = tree.getroot()
        ns = {"m": "http://schemas.microsoft.com/3dmanufacturing/core/2015/02"}
        for obj in root.findall(".//m:resources/m:object", ns):
            oid = obj.get("id")
            name = obj.get("name", "") or ""
            verts = []
            for v in obj.findall(".//m:mesh/m:vertices/m:vertex", ns):
                verts.append(
                    (float(v.get("x")), float(v.get("y")), float(v.get("z")))
                )
            if verts:
                yield oid, name, np.array(verts, dtype=np.float64)


def main(p):
    p = Path(p)
    print(f"Exploring: {p}")
    all_top_verts = []
    for oid, name, verts in iter_objects(p):
        z = verts[:, 2]
        print(f"\nObject id={oid} name={name!r}  verts={len(verts)}")
        print(f"  z range: {z.min():.3f} .. {z.max():.3f}")
        print(f"  z p50 / p95 / p99 / p99.9: "
              f"{np.percentile(z, 50):.3f} / "
              f"{np.percentile(z, 95):.3f} / "
              f"{np.percentile(z, 99):.3f} / "
              f"{np.percentile(z, 99.9):.3f}")
        # top 5 tallest verts
        idx = np.argsort(z)[-5:][::-1]
        print("  top 5 tallest verts (x, y, z):")
        for i in idx:
            print(f"    ({verts[i,0]:+.2f}, {verts[i,1]:+.2f}, {verts[i,2]:.3f})")
        for v in verts:
            all_top_verts.append((oid, name, v[0], v[1], v[2]))

    # Top 20 tallest across all objects
    print("\n\nTop 20 tallest verts across ALL objects:")
    all_sorted = sorted(all_top_verts, key=lambda t: -t[4])[:20]
    for oid, name, x, y, z in all_sorted:
        print(f"  obj={oid} name={name!r:20}  ({x:+.2f}, {y:+.2f}, {z:.3f})")


if __name__ == "__main__":
    main(sys.argv[1])
