"""
Task 485 — failing-test-first for the Boundary Editor fringe ramp bug.

Owner observation (task 485):
> "the fringe still meets the frame at its top surface height and then
>  slopes to meet the green"

The fix from task 483 (in `app/gradient_surface_diagnostic.py::build_fringe_mesh`)
is supposed to hold the fringe FLAT at green-edge Z all the way to the frame.

Naive check
-----------
A first attempt compared the mean Z of "near-frame" verts with the mean Z of
"near-green" verts globally.  That failed even on the confirmed-good task 483
test 3MF, because the fringe Z is NOT globally flat — it inherits the green
edge's local Z, which varies around the polygon (a terraced green cycles from
BASE_THICKNESS_MM up to BASE_THICKNESS_MM + elevation_range).  Sampling the
two rings at different angular locations biases the means independently of
any ramp.

Correct check (per-vertex pairing)
----------------------------------
For each near-frame vertex F, find the fringe top-surface vertex G that is
closest to the green boundary AND that shares roughly the same angular
direction from the green centroid as F.  Compare F.z to G.z pairwise.
If the fringe holds flat to the frame, the paired ΔZ should be ≈ 0 (within
tolerance).  If it ramps, ΔZ will be systematically non-zero.

Because we don't have the green polygon in the 3MF, we approximate the green
centroid as the XY centroid of the printable rectangle (all fringe verts are
outside the green and inside the rectangle, so the polygon centroid is well
inside their convex hull).  We then bin verts by polar angle around that
centroid and, in each angular bin, compare the mean Z of the "outer" ring
(near the rect) to the mean Z of the "inner" ring (deep inside the frame,
adjacent to the green polygon).

This test uses the fringe mesh's OWN inner-ring vertices as the ground truth
for green-edge Z at each angular direction.

Usage
-----
    python test_fringe_flat_to_frame.py <path_to_3mf>

Exit code
---------
    0 = flat-to-frame holds (bin-by-bin ΔZ within tolerance)
    1 = FAIL — systematic non-zero ΔZ (ramp) detected
    2 = could not analyse (bad file, no `fringe` object, etc.)
"""
from __future__ import annotations

import sys
import zipfile
import xml.etree.ElementTree as ET
from pathlib import Path
import numpy as np


# Print rectangle half-width — matches PRINT_SIZE_MM/2 + FRINGE_XY_EXPANSION_MM/2
# in gradient_surface_diagnostic.py.
PRINT_SIZE_MM = 171.45
FRINGE_XY_EXPANSION_MM = -1.057
HALF = PRINT_SIZE_MM / 2.0 + FRINGE_XY_EXPANSION_MM / 2.0

# Rings, in mm from the outer rect edge:
NEAR_RECT_MM = 4.0   # "outer ring"  — verts within this of the rectangle
DEEP_INNER_MM = 10.0  # "inner ring" — verts at least this far from every rect edge

# Angular binning
N_BINS = 24                # 24 × 15° bins around the polygon centroid
MIN_VERTS_PER_BIN = 3      # skip bins with fewer verts on either ring
# Per-bin tolerance is loose because corners of a wide fringe strip legitimately
# sample different parts of the green edge on the outer vs. inner ring; the
# systemic (aggregate) delta is the strong signal.
MAX_ABS_DELTA_MEAN_MM = 1.75   # per-bin |mean_outer − mean_inner| tolerance
MAX_ABS_SYSTEMIC_DELTA_MM = 0.75  # aggregate (mean of per-bin deltas) tolerance


def _iter_object_meshes(three_mf_path: Path):
    """Yield (object_id, name, vertices ndarray) for each object in the 3MF."""
    with zipfile.ZipFile(three_mf_path, "r") as z:
        model_names = [n for n in z.namelist() if n.endswith("3dmodel.model")]
        if not model_names:
            raise RuntimeError("no 3dmodel.model in 3mf")
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


def _find_fringe_verts(three_mf_path: Path) -> np.ndarray:
    """Return the vertex array of the object whose name contains 'fringe'."""
    candidates = []
    for oid, name, verts in _iter_object_meshes(three_mf_path):
        candidates.append((oid, name, verts))
        if "fringe" in name.lower():
            return verts

    # Fallback: object whose XY bbox is closest to PRINT_SIZE_MM square
    best = None
    best_score = 1e18
    for oid, name, verts in candidates:
        xy = verts[:, :2]
        dx = xy[:, 0].max() - xy[:, 0].min()
        dy = xy[:, 1].max() - xy[:, 1].min()
        score = abs(dx - PRINT_SIZE_MM) + abs(dy - PRINT_SIZE_MM)
        if score < best_score:
            best_score = score
            best = verts
    if best is None:
        raise RuntimeError("no fringe object found in 3mf")
    return best


def analyse_3mf(three_mf_path: Path) -> int:
    print(f"[task 485] analysing: {three_mf_path.name}")
    try:
        verts = _find_fringe_verts(three_mf_path)
    except Exception as exc:
        print(f"  ERROR: {exc}")
        return 2

    # Top-surface only (z > 0.5 mm rules out wall bottoms at z=0)
    top = verts[verts[:, 2] > 0.5]
    if top.size == 0:
        print("  ERROR: no top-surface vertices (all Z ≤ 0.5)")
        return 2

    # Distance from every top vert to the outer rectangle
    d_rect = np.minimum.reduce([
        top[:, 0] - (-HALF),
        HALF - top[:, 0],
        top[:, 1] - (-HALF),
        HALF - top[:, 1],
    ])
    outer_mask = d_rect < NEAR_RECT_MM
    inner_mask = d_rect > DEEP_INNER_MM
    outer = top[outer_mask]
    inner = top[inner_mask]

    if len(outer) == 0 or len(inner) == 0:
        print(f"  ERROR: outer verts={len(outer)}, inner verts={len(inner)} "
              f"(need both > 0)")
        return 2

    # Angular binning around the printable centroid (origin in mm coords).
    def angle(verts_xy: np.ndarray) -> np.ndarray:
        return np.mod(np.arctan2(verts_xy[:, 1], verts_xy[:, 0]),
                      2.0 * np.pi)

    outer_ang = angle(outer[:, :2])
    inner_ang = angle(inner[:, :2])
    bin_width = 2.0 * np.pi / N_BINS

    print(f"  Total top-surface fringe verts: {len(top)}")
    print(f"  Outer ring (< {NEAR_RECT_MM} mm from rect): {len(outer)} verts")
    print(f"  Inner ring (> {DEEP_INNER_MM} mm from rect): {len(inner)} verts")
    print(f"  Angular bins: {N_BINS} × {np.degrees(bin_width):.1f}°")
    print("")
    print(f"  {'bin':>3}  {'deg':>7}  {'n_out':>6} {'n_in':>6}  "
          f"{'mean_out':>9} {'mean_in':>9}  {'Δ':>7}")

    deltas: list[float] = []
    n_bins_bad = 0
    n_bins_used = 0
    for b in range(N_BINS):
        lo = b * bin_width
        hi = (b + 1) * bin_width
        o_sel = outer[(outer_ang >= lo) & (outer_ang < hi)]
        i_sel = inner[(inner_ang >= lo) & (inner_ang < hi)]
        if len(o_sel) < MIN_VERTS_PER_BIN or len(i_sel) < MIN_VERTS_PER_BIN:
            print(f"  {b:>3}  {np.degrees((lo + hi) / 2):>7.1f}  "
                  f"{len(o_sel):>6} {len(i_sel):>6}  "
                  f"{'-':>9} {'-':>9}  {'skip':>7}")
            continue
        mo = float(o_sel[:, 2].mean())
        mi = float(i_sel[:, 2].mean())
        d = mo - mi
        deltas.append(d)
        n_bins_used += 1
        flag = " OK"
        if abs(d) > MAX_ABS_DELTA_MEAN_MM:
            flag = "!!"
            n_bins_bad += 1
        print(f"  {b:>3}  {np.degrees((lo + hi) / 2):>7.1f}  "
              f"{len(o_sel):>6} {len(i_sel):>6}  "
              f"{mo:>9.2f} {mi:>9.2f}  {d:>+7.2f}  {flag}")

    if not deltas:
        print("  ERROR: no bins had enough verts to compare")
        return 2

    mean_delta = float(np.mean(deltas))
    max_abs_delta = float(np.max(np.abs(deltas)))
    print("")
    print(f"  Bins used: {n_bins_used}  bins over-tolerance (|Δ| > "
          f"{MAX_ABS_DELTA_MEAN_MM} mm): {n_bins_bad}")
    print(f"  Mean per-bin Δ (outer − inner): {mean_delta:+.2f} mm  "
          f"(tolerance ±{MAX_ABS_SYSTEMIC_DELTA_MM} mm)")
    print(f"  Max per-bin |Δ|: {max_abs_delta:.2f} mm  "
          f"(tolerance {MAX_ABS_DELTA_MEAN_MM} mm)")

    ok = (
        abs(mean_delta) <= MAX_ABS_SYSTEMIC_DELTA_MM
        and n_bins_bad == 0
    )
    if ok:
        print("  PASS — fringe holds flat to frame per bin.")
        return 0

    if mean_delta < 0:
        print("  FAIL — outer ring is systematically LOWER than inner ring: "
              "the fringe ramps DOWN to the frame (old task-483 defect).")
    elif mean_delta > 0:
        print("  FAIL — outer ring is systematically HIGHER than inner ring: "
              "the fringe ramps UP to the frame (owner's task-485 observation).")
    else:
        print("  FAIL — no systemic bias but some bins exceed tolerance "
              "(local defect).")
    return 1


def main() -> int:
    if len(sys.argv) < 2:
        print(__doc__)
        return 2
    return analyse_3mf(Path(sys.argv[1]))


if __name__ == "__main__":
    sys.exit(main())
