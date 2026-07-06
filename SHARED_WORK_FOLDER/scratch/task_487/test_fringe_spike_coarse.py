"""
Task 487 — COARSE spike-scan for the fringe "pointy peak" defect.

Task 486's spike scanner (RADIUS=2mm, tol=0.5mm, min_nbrs=6) was too fine-scale
to catch what the owner was actually seeing. The screenshot showed a peak
several millimetres tall — a genuine "pointy peak" — not a sub-mm bump. This
test widens the scan window and raises the tolerance so a real, tall,
visually obvious spike is what triggers the failure.

Coarse parameters (owner-specified in task 487):
    RADIUS_MM       = 7.0     (6-8 mm range — grabs enough context for a real peak)
    SPIKE_TOL_MM    = 3.0     (a true "pointy peak" is at least 3 mm over local median)
    MIN_NEIGHBOURS  = 10      (need a solid median)
    TOP_Z_MIN       = 2.0     (rule out z=0 walls and 1mm engraving-pocket ceiling)

Exit code
---------
    0 = no coarse spikes above tolerance
    1 = FAIL — coarse spike(s) detected
    2 = could not analyse (bad file, no fringe object)
"""
from __future__ import annotations

import sys
from pathlib import Path
import numpy as np

# Reuse the fringe-vert loader from the task-485 test.
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "task_485"))
from test_fringe_flat_to_frame import _find_fringe_verts  # noqa: E402

RADIUS_MM = 7.0
MIN_NEIGHBOURS = 10
SPIKE_TOL_MM = 3.0
TOP_Z_MIN = 2.0


def analyse_spikes(three_mf_path: Path) -> int:
    print(f"[task 487] COARSE spike-scan: {three_mf_path.name}")
    print(f"  radius={RADIUS_MM} mm  tol={SPIKE_TOL_MM} mm  "
          f"min_nbrs={MIN_NEIGHBOURS}  top_z_min={TOP_Z_MIN} mm")
    try:
        verts = _find_fringe_verts(three_mf_path)
    except Exception as exc:
        print(f"  ERROR: {exc}")
        return 2

    top = verts[verts[:, 2] > TOP_Z_MIN]
    if top.size == 0:
        print("  ERROR: no top-surface vertices")
        return 2

    _, uniq_idx = np.unique(np.round(top, 4), axis=0, return_index=True)
    top = top[np.sort(uniq_idx)]

    from scipy.spatial import cKDTree
    kd = cKDTree(top[:, :2])

    print(f"  Top-surface fringe verts (unique): {len(top)}")

    spikes = []  # (delta, x, y, z, median, n_nbr)
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

    spikes.sort(reverse=True)
    n_spikes = len(spikes)
    print(f"  Coarse spikes above tol: {n_spikes}")

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
        print(f"  FAIL — {n_spikes} COARSE fringe spike(s) above local median "
              f"by > {SPIKE_TOL_MM} mm  (max Δ = {max_delta:+.2f} mm).")
        return 1

    print("  PASS — no coarse fringe spikes above local-median tolerance.")
    return 0


def main() -> int:
    if len(sys.argv) < 2:
        print(__doc__)
        return 2
    return analyse_spikes(Path(sys.argv[1]))


if __name__ == "__main__":
    sys.exit(main())
