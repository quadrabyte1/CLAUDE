"""
Task 486 — failing-test-first for the fringe "pointy peak" defect.

Owner observation (task 486):
> a pointy peak in the fringe near where the fringe meets the green.
> Screenshot showed a sharp ridge/spike rising out of an otherwise smooth
> green+fringe surface — visually a stray "point" sticking up from a green
> boundary region.

Root cause (owner-agreed):
`build_fringe_mesh` samples the green-edge height with `k=1` nearest-neighbour:
    _, idx_g = green_kd.query([nx, ny], k=1)
    green_edge_h = float(green_cell_z[idx_g])
A single tall green boundary vertex can propagate its Z as a ray of fringe
cells outward to the frame — that ray is the spike.

Test strategy
-------------
Load the fringe object's top-surface vertices from a 3MF. For each vertex,
compute a local neighbourhood (all other verts within RADIUS_MM in XY) and
compare its Z against the neighbourhood MEDIAN. A "spike" is a vertex whose
Z exceeds its local median by more than SPIKE_TOL_MM.

Because a legitimate flat plateau will have local delta ≈ 0 and a legitimate
sloped transition will have local delta small-and-smooth, a stray k=1 ray
shows up as one or more localised vertices whose Z sits well above their
XY-neighbours' median.

Reports:
  - total top-surface fringe verts
  - number of spikes above SPIKE_TOL_MM
  - the top 10 spikes with (x, y, z, local_median, delta)

Exit code
---------
    0 = no spikes above tolerance
    1 = FAIL — spikes detected
    2 = could not analyse (bad file, no fringe object, etc.)
"""
from __future__ import annotations

import sys
import zipfile
import xml.etree.ElementTree as ET
from pathlib import Path
import numpy as np

# Import the fringe-vert loader from the task-485 test to keep behaviour identical.
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "task_485"))
from test_fringe_flat_to_frame import _find_fringe_verts  # noqa: E402

# Spike-scan parameters
#
# On Los Lagos hole 16, the pre-fix (k=1 sampler) 3MF surfaces 5 spikes at
# r=2.0 mm, tol=0.5 mm (max Δ = +0.66 mm at (-36.4, 29.5)); the post-fix
# (k-NN mean) 3MF shows 0. Tightening tolerance to 0.5 mm is deliberate:
# a 0.66 mm bump in an otherwise 17.7 mm plateau is exactly the "point"
# the owner sees on the render — smooth Bambu Studio shading picks it up
# as a highlight spike even though it's only sub-millimetre in Z.
RADIUS_MM = 2.0        # local XY neighbourhood radius
MIN_NEIGHBOURS = 6     # need at least this many neighbours to judge
SPIKE_TOL_MM = 0.5     # Z above local median that counts as a spike
# Ignore wall bottoms AND the serial-number engraving pocket ceiling. Base is
# 1.5 mm, plus a 2.0 mm water-hole lift on Los Lagos 16 → true top surface
# starts at 3.5 mm. Anything below ~2 mm is either z=0 wall bottoms or the
# 1.0 mm engraving pocket ceiling — neither belongs in a spike scan of the
# grass top surface.
TOP_Z_MIN = 2.0


def analyse_spikes(three_mf_path: Path) -> int:
    print(f"[task 486] spike-scan: {three_mf_path.name}")
    try:
        verts = _find_fringe_verts(three_mf_path)
    except Exception as exc:
        print(f"  ERROR: {exc}")
        return 2

    top = verts[verts[:, 2] > TOP_Z_MIN]
    if top.size == 0:
        print("  ERROR: no top-surface vertices")
        return 2

    # Deduplicate — 3MF meshes share verts across triangles, but a single
    # vertex list per object is usually already unique.
    _, uniq_idx = np.unique(np.round(top, 4), axis=0, return_index=True)
    top = top[np.sort(uniq_idx)]

    from scipy.spatial import cKDTree
    kd = cKDTree(top[:, :2])

    print(f"  Top-surface fringe verts (unique): {len(top)}")
    print(f"  Local-median radius: {RADIUS_MM} mm; spike tol: "
          f"{SPIKE_TOL_MM} mm above local median")

    spikes = []   # (delta, x, y, z, median, n_nbr)
    for i in range(len(top)):
        idxs = kd.query_ball_point(top[i, :2], r=RADIUS_MM)
        if len(idxs) - 1 < MIN_NEIGHBOURS:
            continue
        nbr_z = top[idxs, 2]
        med = float(np.median(nbr_z))
        delta = float(top[i, 2] - med)
        if delta > SPIKE_TOL_MM:
            spikes.append(
                (delta, float(top[i, 0]), float(top[i, 1]),
                 float(top[i, 2]), med, len(idxs) - 1)
            )

    spikes.sort(reverse=True)  # largest delta first
    n_spikes = len(spikes)
    print(f"  Spikes above tol: {n_spikes}")

    if spikes:
        print("")
        print(f"  {'rank':>4}  {'x':>8} {'y':>8}  {'z':>8}  "
              f"{'med':>8}  {'Δ':>7}  {'n_nbr':>5}")
        for rank, (d, x, y, z, m, n) in enumerate(spikes[:10], start=1):
            print(f"  {rank:>4}  {x:>8.2f} {y:>8.2f}  {z:>8.2f}  "
                  f"{m:>8.2f}  {d:>+7.2f}  {n:>5}")

    if n_spikes > 0:
        max_delta = spikes[0][0]
        print("")
        print(f"  FAIL — {n_spikes} fringe spike(s) above local median by "
              f"> {SPIKE_TOL_MM} mm  (max Δ = {max_delta:+.2f} mm).")
        return 1

    print("  PASS — no fringe spikes above local-median tolerance.")
    return 0


def main() -> int:
    if len(sys.argv) < 2:
        print(__doc__)
        return 2
    return analyse_spikes(Path(sys.argv[1]))


if __name__ == "__main__":
    sys.exit(main())
