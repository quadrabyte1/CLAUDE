"""
Task 487 — deeper diagnostic: what does the fringe Z field look like?

Locate fringe verts, split into an XY histogram, print regional Z stats.
The "pointy peak" the owner sees may be a BULGE (several-vert plateau), not
a single-vertex spike — the coarse scanner misses those because the local
median inside the bulge is high too.
"""
from __future__ import annotations

import sys
from pathlib import Path
import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "task_485"))
from test_fringe_flat_to_frame import _find_fringe_verts  # noqa: E402


def main(p):
    p = Path(p)
    verts = _find_fringe_verts(p)
    top = verts[verts[:, 2] > 2.0]
    _, uniq = np.unique(np.round(top, 4), axis=0, return_index=True)
    top = top[np.sort(uniq)]

    print(f"Fringe object top verts: {len(top)}")
    print(f"Z global: min={top[:,2].min():.3f} med={np.median(top[:,2]):.3f} "
          f"max={top[:,2].max():.3f}")
    print(f"Z p50/p75/p90/p95/p99/p99.9: "
          f"{np.percentile(top[:,2], 50):.3f} / "
          f"{np.percentile(top[:,2], 75):.3f} / "
          f"{np.percentile(top[:,2], 90):.3f} / "
          f"{np.percentile(top[:,2], 95):.3f} / "
          f"{np.percentile(top[:,2], 99):.3f} / "
          f"{np.percentile(top[:,2], 99.9):.3f}")

    # 20x20 mm bins over XY
    print("\n20x20 mm XY bin Z stats (only bins with 10+ verts):")
    BIN = 20.0
    x = top[:, 0]; y = top[:, 1]; z = top[:, 2]
    xmin, xmax = x.min(), x.max()
    ymin, ymax = y.min(), y.max()
    nx = int(np.ceil((xmax - xmin) / BIN)) + 1
    ny = int(np.ceil((ymax - ymin) / BIN)) + 1
    global_med = float(np.median(z))
    print(f"Global fringe top-Z median = {global_med:.3f}")
    print(f"{'x_lo':>7} {'y_lo':>7}  {'n':>5}  "
          f"{'z_min':>7} {'z_med':>7} {'z_max':>7}  {'Δmed':>7}")
    hot = []
    for i in range(nx):
        for j in range(ny):
            xl = xmin + i * BIN
            yl = ymin + j * BIN
            m = (x >= xl) & (x < xl + BIN) & (y >= yl) & (y < yl + BIN)
            if m.sum() < 10:
                continue
            zsub = z[m]
            hot.append(
                (xl, yl, int(m.sum()), float(zsub.min()),
                 float(np.median(zsub)), float(zsub.max()),
                 float(np.median(zsub) - global_med))
            )
    hot.sort(key=lambda t: -t[6])  # largest Δmed first
    for xl, yl, n, zmn, zmd, zmx, dm in hot[:20]:
        print(f"{xl:>7.1f} {yl:>7.1f}  {n:>5}  "
              f"{zmn:>7.3f} {zmd:>7.3f} {zmx:>7.3f}  {dm:>+7.3f}")

    # Also: find the tallest local cluster (top-1% Z) and print its extent
    z99 = float(np.percentile(z, 99))
    mask99 = z > z99
    print(f"\nVerts above global p99 (z>{z99:.2f}): {mask99.sum()}")
    if mask99.any():
        p99pts = top[mask99]
        print(f"  XY bbox: x=[{p99pts[:,0].min():.2f}, {p99pts[:,0].max():.2f}]"
              f"  y=[{p99pts[:,1].min():.2f}, {p99pts[:,1].max():.2f}]"
              f"  z range=[{p99pts[:,2].min():.3f}, {p99pts[:,2].max():.3f}]")


if __name__ == "__main__":
    main(sys.argv[1])
