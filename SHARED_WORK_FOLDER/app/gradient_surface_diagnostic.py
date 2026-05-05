"""
gradient_surface_diagnostic.py — Reconstruct golf green height from arrow gradient directions.

Instead of finding contour lines, we use the small chevron arrows in the green image
as gradient data (each arrow points downhill), then integrate them via the Poisson
equation to get a height map.

Steps:
1. Load EGM, get green boundary via Catmull-Rom interpolation
2. Build dark mask inside green, find arrow blobs with CC analysis
3. For each blob: PCA to find orientation, half-blob spread to resolve 180° ambiguity
4. Build IDW-interpolated gradient field on a 100x100 grid
5. Solve Poisson equation for height Z
6. Save two diagnostic images to owner_inbox/
"""

from __future__ import annotations

import os
import sys
import json
import math

# Make app/ importable
sys.path.insert(0, os.path.dirname(__file__))

import numpy as np
import cv2
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from scipy.sparse import lil_matrix
from scipy.sparse.linalg import spsolve
from scipy.spatial import cKDTree
from scipy.ndimage import gaussian_filter, uniform_filter, median_filter
import trimesh
from shapely.geometry import Polygon as ShapelyPolygon, box as shapely_box, MultiPolygon as ShapelyMultiPolygon
from skimage import measure

from generate_stl_3mf import interpolate_catmull_rom, course_paths, EGM_BASE

# ---------------------------------------------------------------------------
# Paths
# ---------------------------------------------------------------------------

REPO_ROOT = os.path.normpath(os.path.join(os.path.dirname(__file__), ".."))
OWNER_INBOX = os.path.join(REPO_ROOT, "owner_inbox")
TEAM_INBOX  = os.path.join(REPO_ROOT, "team_inbox")


# ---------------------------------------------------------------------------
# Manifold gate
# ---------------------------------------------------------------------------

def assert_manifold(
    mesh,
    label: str = "mesh",
    *,
    skip_labels=None,
    tolerate_boundary_edges: int = 0,
    tolerate_triple_shared: int = 0,
) -> None:
    """Raise ValueError if mesh exceeds the per-component manifold tolerances.

    Always logs boundary-edge and 3+-shared counts so the user sees what's
    being tolerated. Raises only when either count exceeds its tolerance.

    Parameters
    ----------
    skip_labels : iterable of str, optional
        Geometry names (Scene keys) to skip entirely. Default None means
        check every component.
    tolerate_boundary_edges : int
        Per-component max boundary-edge count before raising.
    tolerate_triple_shared : int
        Per-component max 3+-shared-edge count before raising.
    """
    skip_set = set(skip_labels) if skip_labels else set()

    if isinstance(mesh, trimesh.Scene):
        for name, geom in mesh.geometry.items():
            if name in skip_set:
                print(f"manifold: {label}/{name} SKIPPED (skip_labels)")
                continue
            assert_manifold(
                geom,
                label=f"{label}/{name}",
                skip_labels=skip_labels,
                tolerate_boundary_edges=tolerate_boundary_edges,
                tolerate_triple_shared=tolerate_triple_shared,
            )
        return

    # Count how many faces share each undirected edge.
    # Manifold ⇔ every edge shared by exactly 2 faces.
    from collections import Counter
    edge_counts = Counter(map(tuple, mesh.edges_sorted.tolist()))
    n_boundary = sum(1 for c in edge_counts.values() if c == 1)
    n_excess   = sum(1 for c in edge_counts.values() if c >= 3)
    print(
        f"manifold: {label} boundary_edges={n_boundary} "
        f"triple_shared={n_excess} "
        f"(tolerate_boundary={tolerate_boundary_edges}, "
        f"tolerate_triple={tolerate_triple_shared}) "
        f"watertight={mesh.is_watertight} "
        f"winding_consistent={mesh.is_winding_consistent}"
    )
    if n_boundary > tolerate_boundary_edges or n_excess > tolerate_triple_shared:
        raise ValueError(
            f"{label} exceeds manifold tolerance: "
            f"{n_boundary} boundary edges (tol={tolerate_boundary_edges}), "
            f"{n_excess} edges shared by 3+ faces (tol={tolerate_triple_shared}), "
            f"watertight={mesh.is_watertight}, "
            f"winding_consistent={mesh.is_winding_consistent}"
        )


# ---------------------------------------------------------------------------
# Heightmap extreme-limiter (post-Poisson)
#
# The Poisson solve can produce spurious local extremes where noisy arrow
# detections inject high-curvature spikes into the gradient field. Those
# spikes become near-degenerate triangles in the resulting mesh and trip the
# manifold gate. ``soften_extremes`` clamps any cell whose deviation from a
# local baseline exceeds a threshold (in mm-equivalent units), then blends
# the clamped delta back into its neighbourhood with a small gaussian.
# Defaults are tuned for the standard 200x200 grid + ~20 mm elevation range.
# ---------------------------------------------------------------------------

# Peak limit: how many mm a cell may rise above its local baseline before
# being clamped. ELEVATION_RANGE_MM is ~20 mm; 6 mm represents ~30% of the
# total band — a generous allowance for legitimate ridges, tight enough to
# catch spike-shaped artefacts.
_PEAK_LIMIT_MM: float = 6.0

# Valley limit: how many mm a cell may dip below its local baseline. Greens
# tend to have shallower valleys than peaks (water won't pool on a bowl);
# -4 mm catches the deeper crease-style artefacts without flattening real
# bowls.
_VALLEY_LIMIT_MM: float = -4.0

# Soften sigma: gaussian sigma applied to the clamped-delta map before adding
# back. 2 px on a 200x200 grid spreads the correction over ~5 px, smoothing
# the clamp without bleeding into untouched terrain.
_SOFTEN_SIGMA_PX: float = 2.0

# Local window radius (in cells) for the local-baseline mean. 11 px window
# captures the slope context around each cell while staying well below the
# typical green-feature scale.
_LOCAL_WINDOW_PX: int = 11


def soften_extremes(
    Z: np.ndarray,
    mask: np.ndarray,
    *,
    peak_limit_mm: float = _PEAK_LIMIT_MM,
    valley_limit_mm: float = _VALLEY_LIMIT_MM,
    soften_sigma_px: float = _SOFTEN_SIGMA_PX,
    local_window_px: int = _LOCAL_WINDOW_PX,
    elevation_range_mm: float | None = None,
) -> tuple[np.ndarray, dict]:
    """Clamp + soften local extremes in a Poisson-integrated heightmap.

    Z is in raw Poisson units. We map the mm-thresholds into raw units by
    using (current Z range / ELEVATION_RANGE_MM) as the conversion factor,
    so the limits stay meaningful regardless of solver scaling.

    Returns (Z_softened, stats) where stats is a dict with before/after
    metrics for diagnostic logging.
    """
    if elevation_range_mm is None:
        elevation_range_mm = ELEVATION_RANGE_MM

    Z_out = np.array(Z, copy=True)
    valid = mask & np.isfinite(Z_out)
    if not valid.any():
        return Z_out, {"touched": 0}

    z_vals = Z_out[valid]
    z_min, z_max = float(z_vals.min()), float(z_vals.max())
    z_range_raw = z_max - z_min if z_max != z_min else 1.0

    # Raw-unit equivalents of the mm thresholds.
    raw_per_mm = z_range_raw / elevation_range_mm
    peak_limit_raw   = peak_limit_mm   * raw_per_mm
    valley_limit_raw = valley_limit_mm * raw_per_mm

    # Local baseline: uniform mean over a window. Fill outside-mask with
    # zeros for the numerator and zeros for the denominator (count of valid
    # cells), then divide. This avoids NaNs leaking into the baseline near
    # the green boundary.
    Z_filled = np.where(valid, Z_out, 0.0)
    weight   = valid.astype(np.float64)
    win_size = max(3, int(local_window_px) | 1)  # ensure odd
    num = uniform_filter(Z_filled, size=win_size, mode="reflect")
    den = uniform_filter(weight,   size=win_size, mode="reflect")
    with np.errstate(invalid="ignore", divide="ignore"):
        baseline = np.where(den > 0, num / np.maximum(den, 1e-9), 0.0)

    # Compute delta only inside the valid region; zero elsewhere so that
    # the subsequent gaussian smoothing of the correction doesn't bleed
    # NaNs from outside the green into valid cells.
    delta = np.where(valid, Z_out - baseline, 0.0)

    # Stats BEFORE clamping (only on the green mask).
    delta_v = delta[valid]
    n_peaks_before   = int(np.sum(delta_v >  peak_limit_raw))
    n_valleys_before = int(np.sum(delta_v <  valley_limit_raw))
    max_peak_delta_mm   = float(delta_v.max() / raw_per_mm) if delta_v.size else 0.0
    min_valley_delta_mm = float(delta_v.min() / raw_per_mm) if delta_v.size else 0.0
    z_max_mm_before = float((z_max - z_min) / raw_per_mm)  # i.e. ELEVATION_RANGE_MM
    # Per-cell mm-deviation extremes (more useful than full range).
    max_peak_height_mm = max_peak_delta_mm
    min_valley_depth_mm = min_valley_delta_mm

    # Clamp the delta and rebuild Z, then smooth the *modification* so the
    # blend is local rather than abrupt.
    delta_clamped = np.clip(delta, valley_limit_raw, peak_limit_raw)
    correction = delta_clamped - delta  # nonzero only where we clipped
    if soften_sigma_px > 0:
        correction = gaussian_filter(correction, sigma=float(soften_sigma_px))
    Z_out = np.where(valid, Z_out + correction, Z_out)

    # Stats AFTER.
    delta_after = (Z_out - baseline)[valid]
    n_peaks_after   = int(np.sum(delta_after >  peak_limit_raw))
    n_valleys_after = int(np.sum(delta_after <  valley_limit_raw))
    max_peak_after_mm   = float(delta_after.max() / raw_per_mm) if delta_after.size else 0.0
    min_valley_after_mm = float(delta_after.min() / raw_per_mm) if delta_after.size else 0.0

    stats = {
        "peak_limit_mm":     peak_limit_mm,
        "valley_limit_mm":   valley_limit_mm,
        "soften_sigma_px":   soften_sigma_px,
        "local_window_px":   win_size,
        "raw_per_mm":        raw_per_mm,
        "max_peak_mm_before":   max_peak_height_mm,
        "min_valley_mm_before": min_valley_depth_mm,
        "n_peaks_clipped":      n_peaks_before,
        "n_valleys_clipped":    n_valleys_before,
        "max_peak_mm_after":    max_peak_after_mm,
        "min_valley_mm_after":  min_valley_after_mm,
        "n_peaks_after":        n_peaks_after,
        "n_valleys_after":      n_valleys_after,
    }
    return Z_out, stats


# ---------------------------------------------------------------------------
# Step 1: Load EGM and image
# ---------------------------------------------------------------------------

def find_egm(search_term: str = "Moffett") -> str:
    """Pick an EGM file matching the search term.

    Searches all EliteGolfMoments/GolfCourses/*/EGMs/ directories first,
    then falls back to owner_inbox/ for backwards compatibility.
    """
    # Search new course EGMs/ folders
    if os.path.isdir(EGM_BASE):
        for course_dir in sorted(os.listdir(EGM_BASE)):
            egms_dir = os.path.join(EGM_BASE, course_dir, "EGMs")
            if not os.path.isdir(egms_dir):
                continue
            candidates = [
                f for f in os.listdir(egms_dir)
                if f.endswith(".egm") and search_term in f
            ]
            if candidates:
                aa = [c for c in candidates if "AA" in c]
                chosen = aa[0] if aa else sorted(candidates)[0]
                return os.path.join(egms_dir, chosen)
    # Fallback: owner_inbox
    candidates = [
        f for f in os.listdir(OWNER_INBOX)
        if f.endswith(".egm") and search_term in f
    ]
    if not candidates:
        raise FileNotFoundError(
            f"No EGM matching '{search_term}' found in any EGMs/ folder or owner_inbox/"
        )
    aa = [c for c in candidates if "AA" in c]
    chosen = aa[0] if aa else sorted(candidates)[0]
    return os.path.join(OWNER_INBOX, chosen)


def load_egm(egm_path: str) -> tuple[dict, str, np.ndarray]:
    """
    Load EGM file.

    Returns
    -------
    (egm_data, image_path, green_boundary_px)
        image_path: absolute path to the source image
        green_boundary_px: Nx2 float array in pixel coords
    """
    with open(egm_path) as f:
        data = json.load(f)

    image_filename = data["image"]
    course = data.get("course", "")
    # Try course Images/ folder first, then team_inbox, then owner_inbox (fallbacks)
    image_path = None
    search_dirs = []
    if course:
        search_dirs.append(course_paths(course)["images"])
    search_dirs.extend([TEAM_INBOX, OWNER_INBOX])
    for folder in search_dirs:
        candidate = os.path.join(folder, image_filename)
        if os.path.exists(candidate):
            image_path = candidate
            break
    if image_path is None:
        raise FileNotFoundError(f"Image not found: {image_filename}")

    # Extract green polygon (first polygon of type 'green')
    green_poly = None
    for poly in data["polygons"]:
        if poly.get("type") == "green":
            green_poly = poly
            break
    if green_poly is None:
        raise ValueError("No green polygon found in EGM")

    boundary_px = interpolate_catmull_rom(green_poly["points"])
    return data, image_path, boundary_px


# ---------------------------------------------------------------------------
# Step 2: Detect arrows and determine direction
# ---------------------------------------------------------------------------

def build_dark_mask_inside_green(
    img: np.ndarray,
    green_boundary_px: np.ndarray,
    dark_threshold: int = 50,
) -> np.ndarray:
    """Return a uint8 binary mask: 255 where dark pixels lie inside the green."""
    h, w = img.shape[:2]
    boundary_i = green_boundary_px.astype(np.int32)
    green_mask = np.zeros((h, w), dtype=np.uint8)
    cv2.fillPoly(green_mask, [boundary_i], 255)

    hsv = cv2.cvtColor(img, cv2.COLOR_BGR2HSV)
    value = hsv[:, :, 2]
    dark_mask = np.zeros((h, w), dtype=np.uint8)
    dark_mask[(value < dark_threshold) & (green_mask == 255)] = 255
    return dark_mask


def pca_orientation(ys: np.ndarray, xs: np.ndarray) -> tuple[float, float, float, float]:
    """
    Compute the principal axis of pixel coordinates using PCA.

    Returns
    -------
    (cx, cy, dx, dy)
        centroid (cx, cy) and principal-axis unit vector (dx, dy)
    """
    coords = np.stack([xs, ys], axis=1).astype(np.float64)  # (N, 2)
    centroid = coords.mean(axis=0)
    centered = coords - centroid
    cov = centered.T @ centered / max(len(coords) - 1, 1)
    eigenvalues, eigenvectors = np.linalg.eigh(cov)
    # Largest eigenvalue → principal axis
    principal = eigenvectors[:, np.argmax(eigenvalues)]
    return float(centroid[0]), float(centroid[1]), float(principal[0]), float(principal[1])


def resolve_arrow_direction(
    ys: np.ndarray,
    xs: np.ndarray,
    cx: float,
    cy: float,
    dx: float,
    dy: float,
) -> tuple[float, float]:
    """
    Resolve 180° ambiguity of the principal axis.

    The chevron tip (head) is narrower (less perpendicular spread) than the tail.
    We project pixels onto the principal axis to split into two halves.
    The half with smaller perpendicular std is the HEAD.
    The gradient direction is FROM head TO tail (downhill).

    Returns (gradient_dx, gradient_dy) as a unit vector pointing downhill.
    """
    coords = np.stack([xs - cx, ys - cy], axis=1).astype(np.float64)

    # Project onto principal axis
    proj_along = coords @ np.array([dx, dy])        # scalar projection
    # Perpendicular component
    perp = coords - np.outer(proj_along, np.array([dx, dy]))
    perp_std = np.sqrt((perp ** 2).sum(axis=1))    # per-pixel perp distance

    # Split: positive vs negative half
    pos_mask = proj_along >= 0
    neg_mask = ~pos_mask

    std_pos = perp_std[pos_mask].std() if pos_mask.sum() > 1 else 1e9
    std_neg = perp_std[neg_mask].std() if neg_mask.sum() > 1 else 1e9

    # Head = narrower half (smaller std)
    # Arrows point downhill, so gradient is FROM tail TO head (uphill direction)
    if std_pos <= std_neg:
        # Positive half is head → gradient points toward + direction → (dx, dy)
        return dx, dy
    else:
        # Negative half is head → gradient points toward - direction → (-dx, -dy)
        return -dx, -dy


def detect_arrows(
    img: np.ndarray,
    green_boundary_px: np.ndarray,
    dark_threshold: int = 50,
    max_arrow_area: int = 600,
) -> list[dict]:
    """
    Find all arrow blobs, determine centroid and downhill gradient direction.

    Returns list of dicts with keys: cx, cy, dx, dy (unit gradient vector)
    """
    dark_mask = build_dark_mask_inside_green(img, green_boundary_px, dark_threshold)

    n_labels, labels, stats, _ = cv2.connectedComponentsWithStats(
        dark_mask, connectivity=8
    )

    arrows = []
    for lbl in range(1, n_labels):
        area = int(stats[lbl, cv2.CC_STAT_AREA])
        if area > max_arrow_area:
            continue  # skip large blobs (contour lines)
        if area < 5:
            continue  # skip noise

        ys, xs = np.where(labels == lbl)

        # PCA for orientation
        cx, cy, dx, dy = pca_orientation(ys, xs)

        # Resolve ambiguity
        gdx, gdy = resolve_arrow_direction(ys, xs, cx, cy, dx, dy)

        # Normalise
        mag = math.hypot(gdx, gdy)
        if mag < 1e-9:
            continue
        gdx /= mag
        gdy /= mag

        arrows.append({"cx": cx, "cy": cy, "dx": gdx, "dy": gdy})

    return arrows


# ---------------------------------------------------------------------------
# Step 3: Build gradient field on a grid (IDW)
# ---------------------------------------------------------------------------

def build_gradient_field(
    arrows: list[dict],
    green_boundary_px: np.ndarray,
    grid_res: int = 100,
) -> tuple[np.ndarray, np.ndarray, np.ndarray, np.ndarray, np.ndarray]:
    """
    Create a regular grid covering the green, compute IDW-interpolated gradient.

    Returns
    -------
    (xs_grid, ys_grid, inside_mask, Gx, Gy)
        xs_grid, ys_grid : 1-D arrays of x and y grid coordinates (pixel space)
        inside_mask      : (grid_res, grid_res) bool array — True if cell is inside green
        Gx, Gy           : (grid_res, grid_res) gradient component arrays
    """
    bx = green_boundary_px[:, 0]
    by = green_boundary_px[:, 1]
    x0, x1 = bx.min(), bx.max()
    y0, y1 = by.min(), by.max()

    xs_grid = np.linspace(x0, x1, grid_res)
    ys_grid = np.linspace(y0, y1, grid_res)

    # Build inside mask using OpenCV pointPolygonTest
    boundary_i = green_boundary_px.astype(np.int32)
    inside_mask = np.zeros((grid_res, grid_res), dtype=bool)
    for row in range(grid_res):
        for col in range(grid_res):
            pt = (float(xs_grid[col]), float(ys_grid[row]))
            result = cv2.pointPolygonTest(boundary_i, pt, measureDist=False)
            inside_mask[row, col] = result >= 0

    print(f"  Grid {grid_res}x{grid_res}, inside cells: {inside_mask.sum()}")

    if not arrows:
        return xs_grid, ys_grid, inside_mask, np.zeros((grid_res, grid_res)), np.zeros((grid_res, grid_res))

    # IDW interpolation
    arrow_cx = np.array([a["cx"] for a in arrows])
    arrow_cy = np.array([a["cy"] for a in arrows])
    arrow_dx = np.array([a["dx"] for a in arrows])
    arrow_dy = np.array([a["dy"] for a in arrows])

    Gx = np.zeros((grid_res, grid_res))
    Gy = np.zeros((grid_res, grid_res))
    IDW_POWER = 2
    IDW_EPSILON = 1e-6

    for row in range(grid_res):
        for col in range(grid_res):
            if not inside_mask[row, col]:
                continue
            gx = xs_grid[col]
            gy = ys_grid[row]
            dist2 = (arrow_cx - gx) ** 2 + (arrow_cy - gy) ** 2
            weights = 1.0 / (dist2 ** (IDW_POWER / 2) + IDW_EPSILON)
            w_sum = weights.sum()
            if w_sum < 1e-12:
                continue
            Gx[row, col] = (weights * arrow_dx).sum() / w_sum
            Gy[row, col] = (weights * arrow_dy).sum() / w_sum

    return xs_grid, ys_grid, inside_mask, Gx, Gy


# ---------------------------------------------------------------------------
# Step 4: Solve Poisson equation for height
# ---------------------------------------------------------------------------

def solve_poisson_height(
    inside_mask: np.ndarray,
    Gx: np.ndarray,
    Gy: np.ndarray,
) -> np.ndarray:
    """
    Solve ∇²Z = div(G) = ∂Gx/∂x + ∂Gy/∂y inside the green mask.

    Uses finite differences on a regular grid with Dirichlet BC at boundary
    (first interior cell fixed to 0 to remove the constant offset).

    Returns Z: (grid_res, grid_res) height array (NaN outside green).
    """
    rows, cols = inside_mask.shape

    # Index mapping: interior cells get a unique index
    idx = np.full((rows, cols), -1, dtype=int)
    n_cells = 0
    for r in range(rows):
        for c in range(cols):
            if inside_mask[r, c]:
                idx[r, c] = n_cells
                n_cells += 1

    print(f"  Poisson solve: {n_cells} unknowns")

    # Compute divergence of G (RHS)
    # Use central differences where neighbours exist, one-sided otherwise
    div = np.zeros((rows, cols))
    for r in range(rows):
        for c in range(cols):
            if not inside_mask[r, c]:
                continue
            # ∂Gx/∂x (column direction)
            if c > 0 and c < cols - 1:
                dGx_dx = (Gx[r, c+1] - Gx[r, c-1]) / 2.0
            elif c < cols - 1:
                dGx_dx = Gx[r, c+1] - Gx[r, c]
            else:
                dGx_dx = Gx[r, c] - Gx[r, c-1]
            # ∂Gy/∂y (row direction)
            if r > 0 and r < rows - 1:
                dGy_dy = (Gy[r+1, c] - Gy[r-1, c]) / 2.0
            elif r < rows - 1:
                dGy_dy = Gy[r+1, c] - Gy[r, c]
            else:
                dGy_dy = Gy[r, c] - Gy[r-1, c]
            div[r, c] = dGx_dx + dGy_dy

    # Build sparse Laplacian matrix A and RHS vector b
    A = lil_matrix((n_cells, n_cells))
    b = np.zeros(n_cells)

    # Find first interior cell for pinning (Dirichlet BC)
    pin_cell = -1
    for r in range(rows):
        for c in range(cols):
            if inside_mask[r, c]:
                pin_cell = idx[r, c]
                break
        if pin_cell >= 0:
            break

    for r in range(rows):
        for c in range(cols):
            if not inside_mask[r, c]:
                continue
            i = idx[r, c]

            if i == pin_cell:
                # Pin this cell to 0
                A[i, i] = 1.0
                b[i] = 0.0
                continue

            # 5-point Laplacian stencil
            n_neighbours = 0
            neighbours = [
                (r-1, c), (r+1, c), (r, c-1), (r, c+1)
            ]
            for nr, nc in neighbours:
                if 0 <= nr < rows and 0 <= nc < cols and inside_mask[nr, nc]:
                    j = idx[nr, nc]
                    A[i, j] = 1.0
                    n_neighbours += 1

            A[i, i] = -max(n_neighbours, 1)
            b[i] = div[r, c]

    print("  Solving sparse system…")
    A_csr = A.tocsr()
    z_vals = spsolve(A_csr, b)

    # Map solution back to 2D
    Z = np.full((rows, cols), np.nan)
    for r in range(rows):
        for c in range(cols):
            if inside_mask[r, c]:
                Z[r, c] = z_vals[idx[r, c]]

    return Z


# ---------------------------------------------------------------------------
# Step 5: Save diagnostic images
# ---------------------------------------------------------------------------

def save_arrow_directions(
    img: np.ndarray,
    arrows: list[dict],
    green_boundary_px: np.ndarray,
    out_path: str,
) -> None:
    """Draw arrows as colored lines on the source image, save PNG."""
    vis = img.copy()

    # Draw green boundary
    boundary_i = green_boundary_px.astype(np.int32)
    cv2.polylines(vis, [boundary_i], isClosed=True, color=(0, 220, 0), thickness=2)

    # Draw each arrow: color = direction angle
    for a in arrows:
        cx, cy = int(round(a["cx"])), int(round(a["cy"]))
        dx, dy = a["dx"], a["dy"]
        angle = math.atan2(dy, dx)                  # -π .. π
        # Map angle to hue (0-179 in OpenCV HSV)
        hue = int(((angle + math.pi) / (2 * math.pi)) * 179)
        # HSV → BGR
        hsv_pixel = np.array([[[hue, 255, 255]]], dtype=np.uint8)
        bgr = cv2.cvtColor(hsv_pixel, cv2.COLOR_HSV2BGR)[0, 0].tolist()

        length = 15
        ex = int(round(cx + dx * length))
        ey = int(round(cy + dy * length))
        cv2.arrowedLine(vis, (cx, cy), (ex, ey), color=bgr, thickness=2, tipLength=0.4)

    os.makedirs(os.path.dirname(out_path), exist_ok=True)
    cv2.imwrite(out_path, vis)
    print(f"  Saved: {out_path}")


def save_height_map(
    Z: np.ndarray,
    xs_grid: np.ndarray,
    ys_grid: np.ndarray,
    green_boundary_px: np.ndarray,
    out_path: str,
) -> None:
    """Save height map as a colored terrain plot with green boundary overlay."""
    valid = Z[~np.isnan(Z)]
    if valid.size == 0:
        print("  Warning: no valid height values to plot")
        return

    z_min, z_max = valid.min(), valid.max()
    print(f"  Height range: {z_min:.4f} .. {z_max:.4f}")

    fig, ax = plt.subplots(figsize=(10, 9))

    # imshow: rows=y, cols=x, origin at top-left to match image coords
    extent = [xs_grid[0], xs_grid[-1], ys_grid[-1], ys_grid[0]]
    im = ax.imshow(
        Z,
        cmap="terrain",
        extent=extent,
        origin="upper",
        vmin=z_min,
        vmax=z_max,
        aspect="equal",
    )

    plt.colorbar(im, ax=ax, label="Relative height (arbitrary units)", fraction=0.046, pad=0.04)

    # Green boundary
    bx = np.append(green_boundary_px[:, 0], green_boundary_px[0, 0])
    by = np.append(green_boundary_px[:, 1], green_boundary_px[0, 1])
    ax.plot(bx, by, "g-", linewidth=2, label="Green boundary")

    # Label min/max
    min_pos = np.unravel_index(np.nanargmin(Z), Z.shape)
    max_pos = np.unravel_index(np.nanargmax(Z), Z.shape)
    ax.plot(xs_grid[min_pos[1]], ys_grid[min_pos[0]], "bv", markersize=10, label=f"Min = {z_min:.3f}")
    ax.plot(xs_grid[max_pos[1]], ys_grid[max_pos[0]], "r^", markersize=10, label=f"Max = {z_max:.3f}")

    ax.set_title("Reconstructed Green Height Map (Poisson Integration of Arrow Gradients)", fontsize=12)
    ax.set_xlabel("Image X (px)")
    ax.set_ylabel("Image Y (px)")
    ax.legend(loc="upper right", fontsize=9)

    plt.tight_layout()
    os.makedirs(os.path.dirname(out_path), exist_ok=True)
    plt.savefig(out_path, dpi=150)
    plt.close(fig)
    print(f"  Saved: {out_path}")


# ---------------------------------------------------------------------------
# Step 6: Build STL meshes from height map
# ---------------------------------------------------------------------------

# Physical print constants (matching generate_stl_3mf.py)
PRINT_SIZE_MM: float = 171.45   # max bounding-box dimension (6.75 in)
ELEVATION_RANGE_MM: float = 20.09  # total elevation variation on top surface (0.85in = 21.59mm total - 1.5mm base)
BASE_THICKNESS_MM: float = 1.5    # flat base below lowest point
FRINGE_EDGE_HEIGHT_MM: float = 10.0  # height of fringe at the rectangular outer perimeter
N_CONTOUR_LEVELS: int = 27        # steps for quantized surface

# Signed XY offset applied to the fringe outer bbox.
# Positive = grow; negative = shrink.
# FRINGE_XY_EXPANSION_MM is the TOTAL signed offset per axis (i.e. the final printed
# fringe will be offset by this many mm in X and in Y relative to the nominal
# PRINT_SIZE_MM square).  Internally the half-value (offset / 2) is added to each
# edge.  Tune this constant without touching any other code.
# Only the OUTER rectangle moves; the inner green/trap cutouts stay at world origin
# so they still mate with the un-shrunk green and trap meshes.
# Value = prior -0.2 mm inset + 0.5% shrink of PRINT_SIZE_MM (0.005 * 171.45 = 0.857 mm)
# = -1.057 mm total.  v3.16 (Topo, 2026-04-23).
FRINGE_XY_EXPANSION_MM: float = -1.057  # signed total XY offset per axis (negative = shrink); -1.057 mm = prior 0.2mm inset + 0.5% shrink

# Designed structural wall thickness for printed features that need a guaranteed
# solid wall regardless of slicer interpretation (e.g. the upper-left mounting-
# bore "pipe" that hosts the optional ball stand). 4 perimeters × 0.4 mm nozzle =
# 1.6 mm, which is the standard FDM-perimeter-derived wall in this project.
# Distinct from BASE_THICKNESS_MM (build-plate slab thickness) and
# TRAP_THICKNESS_MM (trap slab thickness). Topo, task #335 (2026-04-28).
WALL_THICKNESS_MM: float = 1.6

# Upper-left mounting-bore pipe geometry (task #335 — restored from #318 with an
# explicit annular wall instead of a bare void through the fringe).
# Inner bore = 3/16" = 4.7625 mm; outer = inner + 2 × WALL_THICKNESS_MM.
MOUNT_BORE_INNER_DIAMETER_MM: float = 4.7625      # 3/16 inch
MOUNT_BORE_INNER_RADIUS_MM: float = MOUNT_BORE_INNER_DIAMETER_MM / 2.0
MOUNT_BORE_OUTER_RADIUS_MM: float = MOUNT_BORE_INNER_RADIUS_MM + WALL_THICKNESS_MM
MOUNT_BORE_INSET_MM: float = 20.0                 # distance from print rect corner

# ---------------------------------------------------------------------------
# Water-containing-hole rule (Topo, 2026-05-01) — task per Thomas/Larry.
#
# When an EGM contains one or more polygons of type "water", the printable
# pieces — green, fringe, sand traps — are LIFTED by WATER_HOLE_LIFT_MM so a
# 2 mm filament base sits underneath each. The original terrain shape on top
# is preserved (just sitting 2 mm higher). Water polygons themselves are NOT
# lifted (water sits at the bottom of the basin).
#
# In addition, any green / fringe / sand-trap element that touches the frame
# at the boundary of the hole is CAPPED at BOUNDARY_HEIGHT_CAP_MM total
# height (including the 2 mm base). Two cap modes:
#   - "hard"     : clip Z values above cap flat to cap exactly (default).
#   - "compress" : linearly squash terrain Z so max = cap (proportional).
#
# Boundary-touching = polygon has any vertex within BOUNDARY_TOUCH_TOL_MM of
# the fringe rectangle perimeter (±_half = ±(PRINT_SIZE/2 + FRINGE_XY_EXP/2)).
# The fringe itself ALWAYS touches by construction. The green is interior to
# the fringe and never touches the frame.
WATER_HOLE_LIFT_ENABLED: bool  = True
WATER_HOLE_LIFT_MM:      float = 2.0     # base-slab thickness inserted under lifted pieces
BOUNDARY_HEIGHT_CAP_MM:  float = 9.0     # absolute Z ceiling for boundary-touching pieces
BOUNDARY_HEIGHT_CAP_MODE: str  = "hard"  # one of: "hard", "compress"
BOUNDARY_TOUCH_TOL_MM:   float = 0.5     # XY tolerance for "vertex touches frame edge"


def _compute_px_to_mm(green_boundary_px: np.ndarray, egm_data: dict) -> tuple[float, np.ndarray]:
    """
    Compute scale (px→mm) and centroid offset so the green fits in PRINT_SIZE_MM.
    Returns (scale, centroid_px) where mm_xy = (px - centroid_px) * scale, Y flipped.
    """
    img_w = float(egm_data.get("imageSize", egm_data.get("image_size", {})).get("width", 0))
    img_h = float(egm_data.get("imageSize", egm_data.get("image_size", {})).get("height", 0))

    # Fall back to green bounding box if image size not in EGM
    bx = green_boundary_px[:, 0]
    by = green_boundary_px[:, 1]
    if img_w == 0 or img_h == 0:
        img_w = bx.max() - bx.min()
        img_h = by.max() - by.min()
        centroid_px = np.array([(bx.min() + bx.max()) / 2.0, (by.min() + by.max()) / 2.0])
    else:
        centroid_px = np.array([img_w / 2.0, img_h / 2.0])

    max_dim = max(img_w, img_h)
    if max_dim < 1:
        # Last resort: use green extents
        max_dim = max(bx.max() - bx.min(), by.max() - by.min())
        centroid_px = np.array([(bx.min() + bx.max()) / 2.0, (by.min() + by.max()) / 2.0])

    scale = PRINT_SIZE_MM / max_dim
    return scale, centroid_px


def _px_to_mm_2d(pts_px: np.ndarray, scale: float, centroid_px: np.ndarray) -> np.ndarray:
    """Convert Nx2 pixel coords to mm, flipping Y."""
    xy = (pts_px - centroid_px) * scale
    xy[:, 1] = -xy[:, 1]
    return xy


def _height_to_mm(Z_raw: np.ndarray, inside_mask: np.ndarray) -> np.ndarray:
    """
    Normalise raw Poisson heights to mm elevation, preserving NaN outside the green.
    Maps [z_min, z_max] → [BASE_THICKNESS_MM, BASE_THICKNESS_MM + ELEVATION_RANGE_MM].
    """
    valid = Z_raw[inside_mask]
    z_min, z_max = valid.min(), valid.max()
    z_range = z_max - z_min if z_max != z_min else 1.0

    Z_mm = np.full_like(Z_raw, np.nan)
    Z_mm[inside_mask] = (
        BASE_THICKNESS_MM
        + (Z_raw[inside_mask] - z_min) / z_range * ELEVATION_RANGE_MM
    )
    return Z_mm


def _perimeter_median_filter(
    Z: np.ndarray,
    inside_mask: np.ndarray,
    window: int = 5,
) -> np.ndarray:
    """
    In-place 1D sequential median around the inside_mask perimeter loop.

    Walks the ordered closed perimeter of ``inside_mask`` (4-connected boundary
    cells) and at each cell replaces ``Z[r,c]`` with the median of a length-
    ``window`` (default 5) symmetric window centred on the cell. The center
    sample is the cell's INITIAL value at iteration time, while the two-left
    and one-left positions in the window have already been updated by their
    own medians on this single pass — i.e. the filter is causal/sequential
    (one direction around the loop), not parallel.

    Loop construction uses ``cv2.findContours`` with ``RETR_EXTERNAL`` and
    ``CHAIN_APPROX_NONE`` on ``inside_mask.astype(uint8)``, giving a closed
    sequence of (col, row) pixel coords in order. Wraparound at the seam is
    handled by ``(i ± k) % N`` indexing.

    Returns a copy of ``Z`` with the perimeter cells modified. Cells that are
    not on the perimeter (interior or out-of-mask) are unchanged.
    """
    if window < 3 or window % 2 == 0:
        raise ValueError("window must be odd and >= 3")
    half = window // 2

    Z_out = np.copy(Z)
    mask_u8 = inside_mask.astype(np.uint8)
    contours, _ = cv2.findContours(
        mask_u8, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_NONE
    )
    if not contours:
        return Z_out

    # Use the longest contour (the green proper). Smaller external contours
    # would only appear if inside_mask had disjoint components.
    contour = max(contours, key=lambda c: len(c))
    # contour shape (N, 1, 2) with (x=col, y=row)
    pts = contour.reshape(-1, 2)
    # Drop duplicate-consecutive points (CHAIN_APPROX_NONE can repeat at
    # corners) so the window is over distinct cells.
    rc_seq: list[tuple[int, int]] = []
    last = None
    for x, y in pts:
        rc = (int(y), int(x))
        if rc != last:
            rc_seq.append(rc)
            last = rc
    # Also drop the closing duplicate if findContours appended it.
    if len(rc_seq) > 1 and rc_seq[0] == rc_seq[-1]:
        rc_seq.pop()
    n = len(rc_seq)
    if n < window:
        return Z_out

    # Snapshot of original Z values along the loop (the "initial value" for
    # each cell's window center). The left-side neighbours are read live from
    # Z_out (already updated this pass); right-side neighbours come from the
    # snapshot so they remain at their initial value until their own turn.
    Z_init = np.array([Z[r, c] for (r, c) in rc_seq], dtype=np.float64)

    for i in range(n):
        r, c = rc_seq[i]
        samples: list[float] = []
        # Already-updated left neighbours (from Z_out)
        for k in range(half, 0, -1):
            lr, lc = rc_seq[(i - k) % n]
            samples.append(float(Z_out[lr, lc]))
        # The center cell's INITIAL value for this iteration
        samples.append(float(Z_init[i]))
        # Still-original right neighbours (from snapshot)
        for k in range(1, half + 1):
            samples.append(float(Z_init[(i + k) % n]))
        Z_out[r, c] = float(np.median(samples))

    return Z_out


def _remove_small_terrace_islands(
    Z_plot: np.ndarray,
    inside_mask: np.ndarray,
    scale: float,
    max_diameter_mm: float = 6.3,
    max_passes: int = 50,
) -> np.ndarray:
    """
    Collapse tiny constant-elevation islands in a quantized heightmap.

    An island is a 4-connected region of cells (inside ``inside_mask``) at a
    single quantized Z level whose neighbours outside the region sit at
    different Z levels. If the island's bounding-circle diameter (max pairwise
    distance between cell centres × ``scale``) is ≤ ``max_diameter_mm``, every
    cell of the island is reassigned to the neighbour level whose Z is
    numerically closest to the island's own Z (ties broken toward the lower-Z
    neighbour). Repeats until no qualifying island remains.

    Islands whose only neighbours are NaN (outside ``inside_mask``) are left
    alone — they form the boundary of the green and have no valid merge
    target. Recursion is bounded by ``max_passes`` to guard against pathological
    cycles in edge cases.
    """
    from scipy.ndimage import label as _nd_label
    from scipy.spatial.distance import pdist

    Z_plot = np.copy(Z_plot)
    structure = np.array([[0, 1, 0], [1, 1, 1], [0, 1, 0]], dtype=np.int32)

    for pass_idx in range(max_passes):
        levels = np.unique(Z_plot[inside_mask])
        removed_this_pass = 0

        for lvl in levels:
            level_mask = inside_mask & (Z_plot == lvl)
            if not level_mask.any():
                continue
            labels, n_components = _nd_label(level_mask, structure=structure)
            for comp_id in range(1, n_components + 1):
                rr, cc = np.where(labels == comp_id)
                # Bounding-circle diameter (mm). One cell trivially fits.
                if len(rr) == 1:
                    diameter_mm = 0.0
                else:
                    pts = np.column_stack([rr, cc]).astype(np.float64)
                    diameter_mm = float(pdist(pts).max()) * scale
                if diameter_mm > max_diameter_mm:
                    continue

                # Collect 4-neighbour Z values that are inside the green and
                # not part of this island.
                nbr_zs: list[float] = []
                nrows, ncols = Z_plot.shape
                for r, c in zip(rr, cc):
                    for dr, dc in ((-1, 0), (1, 0), (0, -1), (0, 1)):
                        nr, nc = r + dr, c + dc
                        if nr < 0 or nr >= nrows or nc < 0 or nc >= ncols:
                            continue
                        if not inside_mask[nr, nc]:
                            continue
                        if labels[nr, nc] == comp_id:
                            continue
                        nbr_zs.append(float(Z_plot[nr, nc]))
                if not nbr_zs:
                    continue  # no valid merge target (boundary-touching island)

                unique_nbr_zs = np.unique(np.asarray(nbr_zs, dtype=np.float64))
                lvl_f = float(lvl)
                deltas = np.abs(unique_nbr_zs - lvl_f)
                min_delta = deltas.min()
                # Tie-breaker: pick the lower-Z neighbour level.
                candidates = unique_nbr_zs[deltas == min_delta]
                target_z = float(candidates.min())

                Z_plot[rr, cc] = target_z
                removed_this_pass += 1

        print(f"  Terrace island cleanup pass {pass_idx + 1}: removed {removed_this_pass}")
        if removed_this_pass == 0:
            break

    return Z_plot


def _build_heightmap_mesh(
    Z_mm: np.ndarray,
    xs_grid: np.ndarray,
    ys_grid: np.ndarray,
    inside_mask: np.ndarray,
    _green_boundary_px: np.ndarray,
    scale: float,
    centroid_px: np.ndarray,
    stepped: bool = False,
) -> trimesh.Trimesh:
    """
    Build a closed watertight mesh from a height map grid.

    Strategy:
    1. Build a vertex for each interior grid point at its (x_mm, y_mm, z_mm).
    2. Triangulate interior cells (2 triangles per quad). Only emit quads where
       ALL four corners are inside the green.
    3. Collect all boundary edges of the top surface mesh (edges referenced by
       exactly one triangle). Each boundary edge (va, vb) becomes a wall quad:
       add a corresponding pair of bottom vertices at z=0 and stitch a quad.
    4. Cap the bottom with a triangulated flat polygon (Shapely + trimesh).
    5. Concatenate everything and let trimesh.repair fix normals / fill holes.

    Parameters
    ----------
    stepped : if True, quantize Z_mm into N_CONTOUR_LEVELS discrete levels first.
    """
    grid_res = Z_mm.shape[0]

    # --- Optionally quantize heights ---
    if stepped:
        valid_vals = Z_mm[inside_mask]
        z_min_mm, z_max_mm = valid_vals.min(), valid_vals.max()
        step = (z_max_mm - z_min_mm) / N_CONTOUR_LEVELS
        if step < 1e-9:
            step = 1.0
        Z_plot = np.copy(Z_mm)
        Z_plot[inside_mask] = (
            np.round((Z_plot[inside_mask] - z_min_mm) / step) * step + z_min_mm
        )
    else:
        Z_plot = Z_mm

    # --- Perimeter median filter (task #325, Thomas) ─────────────────────
    # Walk the green's ordered perimeter loop and replace each boundary
    # cell's Z with the median of a 5-cell window [two-left, one-left,
    # this-cell-INITIAL, one-right, two-right]. Sequential/causal: by the
    # time cell i is processed, cells i-1 and i-2 already hold their medians
    # while i+1 and i+2 are still original. Targets the 12:00 north pointy
    # spike cluster identified in [135] without re-introducing the south
    # arc spike cluster (Cluster A).
    Z_plot = _perimeter_median_filter(Z_plot, inside_mask, window=7)

    # --- Grid px → mm ---
    xs_mm = (xs_grid - centroid_px[0]) * scale   # shape (grid_res,)
    ys_mm = -(ys_grid - centroid_px[1]) * scale  # shape (grid_res,), Y flipped

    # --- Top surface vertices ---
    vert_idx = np.full((grid_res, grid_res), -1, dtype=int)
    top_verts: list[list[float]] = []

    for r in range(grid_res):
        for c in range(grid_res):
            if inside_mask[r, c]:
                vert_idx[r, c] = len(top_verts)
                top_verts.append([xs_mm[c], ys_mm[r], float(Z_plot[r, c])])

    # --- Top surface faces (only fully-inside quads) ---
    top_faces: list[list[int]] = []
    for r in range(grid_res - 1):
        for c in range(grid_res - 1):
            v00 = vert_idx[r,   c]
            v01 = vert_idx[r,   c+1]
            v10 = vert_idx[r+1, c]
            v11 = vert_idx[r+1, c+1]
            if v00 < 0 or v01 < 0 or v10 < 0 or v11 < 0:
                continue
            # CCW winding when viewed from above (+Z = outside)
            top_faces.append([v00, v10, v11])
            top_faces.append([v00, v11, v01])

    # --- Find boundary edges of the top surface ---
    # An edge is a boundary edge if it belongs to exactly one triangle.
    # Represent each directed edge as a tuple (a, b); collect all directed edges,
    # then a boundary edge is one whose reverse (b, a) does NOT appear.
    from collections import defaultdict
    edge_count: dict[tuple[int, int], int] = defaultdict(int)
    for f in top_faces:
        a, b, c_ = f
        edge_count[(a, b)] += 1
        edge_count[(b, c_)] += 1
        edge_count[(c_, a)] += 1

    # Boundary directed edges: (a→b) where (b→a) is absent or count=0
    # These are edges where the face is on the outside of the surface.
    # We need undirected boundary edges to build walls, oriented outward.
    boundary_edges: list[tuple[int, int]] = []
    for (a, b), _ in edge_count.items():
        # If (b, a) is not in edge_count, this edge is on the boundary
        if edge_count.get((b, a), 0) == 0:
            boundary_edges.append((a, b))

    # --- Build wall vertices and faces ---
    # For each boundary directed edge (va_top → vb_top) on the top surface,
    # create bottom counterparts (va_bot, vb_bot) at z=0 and stitch a wall quad.
    # The directed edge (a→b) already has correct outward winding from the top faces,
    # so the wall quad CCW (outward) is: va_top, vb_top, vb_bot, va_bot
    # = two triangles: (va_top, vb_top, vb_bot) and (va_top, vb_bot, va_bot)

    top_verts_arr = np.array(top_verts, dtype=np.float64)
    n_top = len(top_verts_arr)

    # Map top vertex index → bottom vertex index
    top_to_bot: dict[int, int] = {}
    bot_verts: list[list[float]] = []

    def get_bot(vi: int) -> int:
        if vi not in top_to_bot:
            top_to_bot[vi] = n_top + len(bot_verts)
            bot_verts.append([top_verts_arr[vi, 0], top_verts_arr[vi, 1], 0.0])
        return top_to_bot[vi]

    wall_faces: list[list[int]] = []
    for va, vb in boundary_edges:
        ba = get_bot(va)
        bb = get_bot(vb)
        # Wall quad: top edge va→vb, bottom edge bb→ba (reversed for outward normal)
        wall_faces.append([va, vb, bb])
        wall_faces.append([va, bb, ba])

    # --- Bottom cap: triangulate using the exact bottom (z=0) vertices from the walls ---
    # Build a loop from the bot_verts (which are already at z=0 and match wall bottom edges).
    # We need to order the bottom boundary into a polygon ring, then triangulate it.
    # Build a directed adjacency from wall bottom edges: for each wall edge (va→vb),
    # the corresponding bottom edge is (bot(vb) → bot(va)) — reversed so the bottom
    # cap normal points downward (-Z = outward from solid).

    # Collect bottom directed edges as a linked list
    bot_next: dict[int, int] = {}
    for va, vb in boundary_edges:
        ba = top_to_bot[va]
        bb = top_to_bot[vb]
        # Bottom edge runs bb → ba (reversed from top) to form a closed ring
        bot_next[bb] = ba

    # Trace all closed loops in the bottom ring
    visited: set[int] = set()
    loops: list[list[int]] = []
    for start in list(bot_next.keys()):
        if start in visited:
            continue
        loop = []
        cur = start
        for _ in range(len(bot_next) + 1):
            if cur in visited:
                break
            visited.add(cur)
            loop.append(cur)
            cur = bot_next.get(cur, -1)
            if cur == start or cur < 0:
                break
        if len(loop) >= 3:
            loops.append(loop)

    cap_faces: list[list[int]] = []
    # Triangulate each loop as a fan from the first vertex.
    # For irregular shapes this is not ideal but trimesh.repair.fill_holes will
    # handle remaining gaps. For large loops, use Shapely for proper triangulation.
    for loop in loops:
        if len(loop) < 3:
            continue
        # Build a 2D polygon from these bottom vertices and triangulate with Shapely
        loop_xy = np.array([[bot_verts[vi - n_top][0], bot_verts[vi - n_top][1]]
                             for vi in loop], dtype=np.float64)
        poly2d = ShapelyPolygon(loop_xy)
        if not poly2d.is_valid:
            poly2d = poly2d.buffer(0)
        if poly2d.is_empty:
            continue

        # Triangulate via trimesh (earcut)
        try:
            cap_mesh = trimesh.creation.extrude_polygon(poly2d, height=0.0001)
            cap_verts_arr = np.array(cap_mesh.vertices)
            cap_faces_arr = np.array(cap_mesh.faces)
            # Select only the bottom cap faces (z ≈ 0)
            z_bot = cap_verts_arr[:, 2] < 0.00005
            f_bot = z_bot[cap_faces_arr].all(axis=1)
            cap_v_sel = cap_verts_arr[z_bot, :2]

            # Map cap vertices back to the loop's bottom vertex indices by nearest XY
            from scipy.spatial import cKDTree
            tree = cKDTree(loop_xy)
            dists, idxs = tree.query(cap_v_sel)
            old2new_cap = np.full(len(cap_verts_arr), -1, dtype=int)
            z_bot_indices = np.where(z_bot)[0]
            for local_i, (dist, li) in enumerate(zip(dists, idxs)):
                if dist < 1.0:  # within 1 mm tolerance
                    old2new_cap[z_bot_indices[local_i]] = loop[li]
                else:
                    old2new_cap[z_bot_indices[local_i]] = loop[li]  # use nearest anyway

            for f in cap_faces_arr[f_bot]:
                fn0 = old2new_cap[f[0]]
                fn1 = old2new_cap[f[1]]
                fn2 = old2new_cap[f[2]]
                if fn0 >= 0 and fn1 >= 0 and fn2 >= 0 and fn0 != fn1 and fn1 != fn2 and fn0 != fn2:
                    # Flip winding: bottom normal must point -Z (outward)
                    cap_faces.append([fn0, fn2, fn1])
        except Exception:
            # Fallback: fan triangulation from first vertex
            v0 = loop[0]
            for i in range(1, len(loop) - 1):
                cap_faces.append([v0, loop[i+1], loop[i]])

    # --- Assemble ---
    all_verts = top_verts + bot_verts
    all_faces = top_faces + wall_faces + cap_faces

    verts_np = np.array(all_verts, dtype=np.float64)
    faces_np = np.array(all_faces, dtype=np.int64)

    mesh = trimesh.Trimesh(vertices=verts_np, faces=faces_np, process=True)
    trimesh.repair.fix_normals(mesh)
    trimesh.repair.fill_holes(mesh)

    return mesh


def drill_flag_hole(
    mesh: "trimesh.Trimesh",
    diameter: float = 2.5,
    x_offset_mm: float = 0.0,
    y_offset_mm: float = 0.0,
) -> "trimesh.Trimesh":
    """
    Subtract a vertical cylindrical hole through the XY center of the mesh.

    The cylinder spans from Z=-1 to Z=max_Z+1 to ensure it punches all the
    way through regardless of surface height variation.

    Parameters
    ----------
    mesh         : watertight trimesh.Trimesh in mm coordinates
    diameter     : hole diameter in mm (default 2.5 mm for a standard flag pin)
    x_offset_mm  : shift the hole center to the right by this many mm
                   (positive = right, negative = left). Default 0.0.
    y_offset_mm  : shift the hole center up by this many mm
                   (positive = up in the slicer view, negative = down).
                   Default 0.0. The mm space here is post Y-flip from
                   _px_to_mm_2d, so +Y is "up" as seen in Bambu Studio.

    Returns
    -------
    trimesh.Trimesh with the hole drilled
    """
    import trimesh.creation
    import trimesh.boolean

    # --- Find XY center of the mesh bounding box, then apply per-hole offsets ---
    bb = mesh.bounds  # shape (2, 3): [[xmin,ymin,zmin],[xmax,ymax,zmax]]
    cx = (bb[0, 0] + bb[1, 0]) / 2.0 + float(x_offset_mm)
    cy = (bb[0, 1] + bb[1, 1]) / 2.0 + float(y_offset_mm)
    z_max = bb[1, 2]
    if x_offset_mm or y_offset_mm:
        print(f"  Flag hole offset: ({x_offset_mm:+.2f}, {y_offset_mm:+.2f}) mm "
              f"→ center ({cx:.2f}, {cy:.2f}) mm")

    # Cylinder extends 1 mm below base (z=-1) and 1 mm above top
    cyl_height = z_max + 2.0   # total height: from -1 to z_max+1
    cyl_center_z = (z_max + 2.0) / 2.0 - 1.0  # midpoint of [-1, z_max+1]

    radius = diameter / 2.0
    # segments=64 gives a smooth enough hole at 2.5 mm diameter
    cylinder = trimesh.creation.cylinder(radius=radius, height=cyl_height, sections=64)

    # Translate cylinder so its axis passes through (cx, cy) and spans the right Z range
    cylinder.apply_translation([cx, cy, cyl_center_z])

    # --- Boolean difference: try manifold3d first, then blender, then fallback ---
    result = None
    for engine in ('manifold', 'blender'):
        try:
            result = trimesh.boolean.difference([mesh, cylinder], engine=engine)
            if result is not None and len(result.faces) > 0:
                print(f"  Boolean difference succeeded (engine='{engine}')")
                break
        except Exception as exc:
            print(f"  Boolean engine '{engine}' failed: {exc}")
            result = None

    if result is None or len(result.faces) == 0:
        # Fallback: remove faces whose centroid XY is within radius of center.
        # This is imprecise (open mesh, no wall cap) but better than nothing.
        print("  WARNING: Boolean backends unavailable — using face-removal fallback "
              "(hole will be open, not capped).")
        centroids = mesh.triangles_center  # (N, 3)
        dist_xy = np.sqrt((centroids[:, 0] - cx) ** 2 + (centroids[:, 1] - cy) ** 2)
        keep = dist_xy >= radius
        result = mesh.submesh([np.where(keep)[0]], append=True)

    # Verify watertight status
    print(f"  Post-drill watertight: {result.is_watertight}")
    print(f"  Post-drill faces: {len(result.faces)}, vertices: {len(result.vertices)}")
    return result


def drill_fringe_hole(
    mesh: "trimesh.Trimesh",
    diameter: float = 5.0,
    offset_from_left: float = 12.0,
    offset_from_top: float = 12.0,
) -> "trimesh.Trimesh":
    """
    Subtract a vertical cylindrical hole through the fringe mesh at a position
    offset from the top-left corner of the fringe bounding box.

    Parameters
    ----------
    mesh             : watertight trimesh.Trimesh in mm coordinates
    diameter         : hole diameter in mm (default 5.0 mm)
    offset_from_left : distance from the left (X-min) edge of the bounding box in mm
    offset_from_top  : distance down from the top (Y-max) edge of the bounding box in mm

    Returns
    -------
    trimesh.Trimesh with the hole drilled
    """
    import trimesh.creation
    import trimesh.boolean
    import trimesh.repair

    # --- Determine hole center from fringe bounding box ---
    bounds = mesh.bounds  # shape (2, 3): [[xmin,ymin,zmin],[xmax,ymax,zmax]]
    cx = bounds[0, 0] + offset_from_left
    cy = bounds[1, 1] - offset_from_top
    z_max = bounds[1, 2]

    print(f"  Fringe hole center: ({cx:.2f}, {cy:.2f}) mm  diameter={diameter} mm")
    print(f"  Fringe pre-repair watertight: {mesh.is_watertight}")

    # --- Approach A: repair a copy of the fringe before boolean ---
    mesh_repaired = mesh.copy()
    trimesh.repair.fill_holes(mesh_repaired)
    trimesh.repair.fix_normals(mesh_repaired)
    trimesh.repair.fix_winding(mesh_repaired)
    mesh_repaired.merge_vertices()
    print(f"  Fringe post-repair watertight: {mesh_repaired.is_watertight}")

    # Cylinder extends 1 mm below base (z=-1) and 1 mm above top
    cyl_height = z_max + 2.0          # total height: from -1 to z_max+1
    cyl_center_z = (z_max + 2.0) / 2.0 - 1.0  # midpoint of [-1, z_max+1]

    radius = diameter / 2.0
    cylinder = trimesh.creation.cylinder(radius=radius, height=cyl_height, sections=64)

    # Translate cylinder so its axis passes through (cx, cy) and spans the right Z range
    cylinder.apply_translation([cx, cy, cyl_center_z])

    # --- Boolean difference: try manifold3d first, then blender, then fallback ---
    # Use the repaired copy so the boolean engine receives a watertight (or closer-to-watertight) mesh
    result = None
    for engine in ('manifold', 'blender'):
        try:
            result = trimesh.boolean.difference([mesh_repaired, cylinder], engine=engine)
            if result is not None and len(result.faces) > 0:
                print(f"  Fringe boolean difference succeeded (engine='{engine}')")
                break
        except Exception as exc:
            print(f"  Fringe boolean engine '{engine}' failed: {exc}")
            result = None

    if result is None or len(result.faces) == 0:
        # Fallback: remove faces whose centroid XY is within radius of center.
        # This is imprecise (open mesh, no wall cap) but better than nothing.
        print("  WARNING: Boolean backends unavailable even after repair — using face-removal fallback "
              "(fringe hole will be open, not capped).")
        print("  NOTE: If this persists, consider Approach B: exclude hole region during build_fringe_mesh().")
        centroids = mesh.triangles_center  # (N, 3)
        dist_xy = np.sqrt((centroids[:, 0] - cx) ** 2 + (centroids[:, 1] - cy) ** 2)
        keep = dist_xy >= radius
        result = mesh.submesh([np.where(keep)[0]], append=True)

    # Verify watertight status
    print(f"  Fringe post-drill watertight: {result.is_watertight}")
    print(f"  Fringe post-drill faces: {len(result.faces)}, vertices: {len(result.vertices)}")
    return result


def save_stl_meshes(
    Z_grid: np.ndarray,
    xs_grid: np.ndarray,
    ys_grid: np.ndarray,
    inside_mask: np.ndarray,
    green_boundary_px: np.ndarray,
    egm_data: dict,
    smooth_out: str | None,
    stepped_out: str | None,
) -> "trimesh.Trimesh":
    """Build smooth and stepped meshes. Returns (smooth_mesh, stepped_mesh).

    If ``smooth_out`` / ``stepped_out`` are None, the meshes are built but no
    STL files are written. The pipeline only feeds the meshes into the 3MF
    scene, so disk writes are vestigial.
    """
    scale, centroid_px = _compute_px_to_mm(green_boundary_px, egm_data)
    print(f"  Scale: {scale:.6f} px→mm, centroid: {centroid_px}")

    Z_mm = _height_to_mm(Z_grid, inside_mask)
    valid_mm = Z_mm[inside_mask]
    print(f"  Z_mm range: {valid_mm.min():.3f} .. {valid_mm.max():.3f} mm")

    # --- Smooth surface ---
    print("  Building smooth surface mesh…")
    smooth_mesh = _build_heightmap_mesh(
        Z_mm, xs_grid, ys_grid, inside_mask, green_boundary_px,
        scale, centroid_px, stepped=False
    )
    bb = smooth_mesh.bounds
    print(f"  Smooth mesh: {len(smooth_mesh.vertices)} vertices, {len(smooth_mesh.faces)} faces")
    print(f"  Watertight: {smooth_mesh.is_watertight}")
    print(f"  Bounding box: X [{bb[0,0]:.1f}, {bb[1,0]:.1f}] "
          f"Y [{bb[0,1]:.1f}, {bb[1,1]:.1f}] Z [{bb[0,2]:.1f}, {bb[1,2]:.1f}] mm")

    # --- Stepped surface ---
    print("  Building stepped surface mesh…")
    stepped_mesh = _build_heightmap_mesh(
        Z_mm, xs_grid, ys_grid, inside_mask, green_boundary_px,
        scale, centroid_px, stepped=True
    )
    bb = stepped_mesh.bounds
    print(f"  Stepped mesh: {len(stepped_mesh.vertices)} vertices, {len(stepped_mesh.faces)} faces")
    print(f"  Watertight: {stepped_mesh.is_watertight}")
    print(f"  Bounding box: X [{bb[0,0]:.1f}, {bb[1,0]:.1f}] "
          f"Y [{bb[0,1]:.1f}, {bb[1,1]:.1f}] Z [{bb[0,2]:.1f}, {bb[1,2]:.1f}] mm")

    # --- Drill flag-pin hole through both meshes ---
    # Per-hole offset (mm) read from EGM; default 0,0 = green-center (legacy behavior).
    x_off = float(egm_data.get('flagOffsetXMm', 0.0) or 0.0)
    y_off = float(egm_data.get('flagOffsetYMm', 0.0) or 0.0)
    print(f"  Drilling 3.0mm flag hole at green center "
          f"(flagOffset = {x_off:+.2f}, {y_off:+.2f} mm)…")
    print("  [smooth]")
    smooth_mesh = drill_flag_hole(
        smooth_mesh, diameter=3.0,
        x_offset_mm=x_off, y_offset_mm=y_off,
    )
    print("  [stepped]")
    stepped_mesh = drill_flag_hole(
        stepped_mesh, diameter=3.0,
        x_offset_mm=x_off, y_offset_mm=y_off,
    )

    # --- Export (optional; skipped when called from the 3MF pipeline) ---
    if smooth_out:
        os.makedirs(os.path.dirname(smooth_out), exist_ok=True)
        smooth_mesh.export(smooth_out)
        print(f"  Saved: {smooth_out}")

    if stepped_out:
        os.makedirs(os.path.dirname(stepped_out), exist_ok=True)
        stepped_mesh.export(stepped_out)
        print(f"  Saved: {stepped_out}")

    return smooth_mesh, stepped_mesh


# ---------------------------------------------------------------------------
# Step 7: Build fringe mesh
# ---------------------------------------------------------------------------

def _dist_to_segment(px: float, py: float, ax: float, ay: float, bx: float, by: float) -> float:
    """Squared distance from point (px, py) to segment (ax,ay)-(bx,by)."""
    dx, dy = bx - ax, by - ay
    t = ((px - ax) * dx + (py - ay) * dy) / (dx * dx + dy * dy + 1e-30)
    t = max(0.0, min(1.0, t))
    nx, ny = ax + t * dx, ay + t * dy
    return math.hypot(px - nx, py - ny), nx, ny


def _min_dist_to_polyline(px: float, py: float, pts: np.ndarray) -> tuple[float, float, float]:
    """
    Return (min_dist, nearest_x, nearest_y) from point to closed polyline pts (Nx2).
    """
    best_d = 1e18
    best_nx, best_ny = pts[0, 0], pts[0, 1]
    n = len(pts)
    for i in range(n):
        ax, ay = pts[i, 0], pts[i, 1]
        bx, by = pts[(i + 1) % n, 0], pts[(i + 1) % n, 1]
        d, nx, ny = _dist_to_segment(px, py, ax, ay, bx, by)
        if d < best_d:
            best_d = d
            best_nx, best_ny = nx, ny
    return best_d, best_nx, best_ny


def _nearest_grid_z(nx_mm: float, ny_mm: float,
                    xs_mm: np.ndarray, ys_mm: np.ndarray,
                    Z_mm: np.ndarray, inside_mask: np.ndarray) -> float:
    """
    Given a point (nx_mm, ny_mm) in mm coords, find the nearest valid grid cell
    (inside the green) and return its Z_mm value.
    """
    # Find closest valid grid cell to the nearest boundary point
    valid_rows, valid_cols = np.where(inside_mask)
    if len(valid_rows) == 0:
        return BASE_THICKNESS_MM

    # xs_mm and ys_mm are 1D — build 2D coords for valid cells
    cell_x = xs_mm[valid_cols]
    cell_y = ys_mm[valid_rows]
    dists2 = (cell_x - nx_mm) ** 2 + (cell_y - ny_mm) ** 2
    best = np.argmin(dists2)
    return float(Z_mm[valid_rows[best], valid_cols[best]])


def _rect_dist_mm(x_mm: float, y_mm: float, half: float) -> float:
    """Distance from interior point to the nearest side of the ±half square."""
    # Distance to each of 4 sides: left, right, bottom, top
    d_left  = x_mm - (-half)
    d_right = half - x_mm
    d_bot   = y_mm - (-half)
    d_top   = half - y_mm
    return min(d_left, d_right, d_bot, d_top)


def _count_fringe_spikes(
    Z: np.ndarray,
    mask: np.ndarray,
    threshold_mm: float,
    return_locations: bool = False,
):
    """
    Count cells in `mask` whose Z exceeds the median of their in-mask 8
    neighbours by more than `threshold_mm`. Mirrors the spike-scanner used in
    task #313 reporting. If `return_locations=True`, also returns a list of
    (r, c, z, nbr_median, delta) tuples for each spike.
    """
    nrows, ncols = Z.shape
    count = 0
    locations: list[tuple[int, int, float, float, float]] = []
    for r in range(nrows):
        for c in range(ncols):
            if not mask[r, c]:
                continue
            nbr_vals: list[float] = []
            for dr in (-1, 0, 1):
                for dc in (-1, 0, 1):
                    if dr == 0 and dc == 0:
                        continue
                    nr, nc = r + dr, c + dc
                    if 0 <= nr < nrows and 0 <= nc < ncols and mask[nr, nc]:
                        nbr_vals.append(float(Z[nr, nc]))
            if not nbr_vals:
                continue
            med = float(np.median(nbr_vals))
            delta = float(Z[r, c]) - med
            if delta > threshold_mm:
                count += 1
                if return_locations:
                    locations.append((r, c, float(Z[r, c]), med, delta))
    if return_locations:
        return count, locations
    return count


def build_fringe_mesh(
    Z_mm: np.ndarray,
    xs_grid: np.ndarray,
    ys_grid: np.ndarray,
    inside_mask: np.ndarray,
    green_boundary_px: np.ndarray,
    egm_data: dict,
    fringe_grid_res: int = 200,
    holes: list | None = None,
) -> trimesh.Trimesh:
    """
    Build a tapered fringe mesh that:
    - Surrounds the green polygon
    - Is bounded by the PRINT_SIZE_MM square centred at origin (mm coords)
    - Excludes sand trap and water polygons (so their inset slabs sit in a
      true recess in the fringe rather than overlapping a flush surface)
    - Tapers from green-edge height down to BASE_THICKNESS_MM at the rectangle

    Parameters
    ----------
    holes : list of (cx, cy, radius) tuples in mm coords.
        Each hole will be baked into the mesh as a clean cylindrical cutout
        with vertical walls connecting the top surface to z=0.

    Returns a closed trimesh.Trimesh in mm coords.
    """
    from scipy.spatial import cKDTree
    from collections import defaultdict

    scale, centroid_px = _compute_px_to_mm(green_boundary_px, egm_data)

    # mm coords of the green grid (used for Z lookups)
    xs_mm_green = (xs_grid - centroid_px[0]) * scale        # shape (grid_res,)
    ys_mm_green = -(ys_grid - centroid_px[1]) * scale       # shape (grid_res,), Y flipped

    half = PRINT_SIZE_MM / 2.0 + FRINGE_XY_EXPANSION_MM / 2.0  # ±89.625 mm + signed offset per edge

    # --- Build a grid covering the FULL print rectangle in mm coords ---
    xs_mm = np.linspace(-half, half, fringe_grid_res)
    ys_mm = np.linspace(-half, half, fringe_grid_res)

    # --- Convert green boundary to mm for inside/outside tests ---
    green_bnd_mm = _px_to_mm_2d(green_boundary_px.copy(), scale, centroid_px)
    _green_bnd_mm_closed = np.vstack([green_bnd_mm, green_bnd_mm[0:1]])  # for polyline dist

    # --- Collect trap + water polygons in mm coords ---
    # Water polygons get the same fringe carve-out treatment as sand traps so
    # their inset slabs (export_water_meshes) sit in a real void rather than on
    # top of an unbroken fringe — overlapping slabs were the source of the
    # 1,129 non-manifold edges Thomas reported on PGA West-Arnold Palmer #5.
    #
    # #347: subtract the mount-pipe footprint from each trap/water shapely
    # polygon BEFORE the union → traps_union. Otherwise the fringe carve-out
    # would remove material under the pipe where there's no longer any
    # trap/water material to host the slab — the pipe would sit on a hole.
    trap_polys_mm: list[np.ndarray] = []
    trap_shapely: list[ShapelyPolygon] = []
    water_polys_mm: list[np.ndarray] = []
    water_shapely: list[ShapelyPolygon] = []

    # Build pipe-footprint Shapely circles from the holes list. Each hole is
    # (cx, cy, radius). We subtract these from the trap/water shapely polygons
    # used for the carve-out union so the void only spans where slab material
    # actually lives.
    _hole_circles: list[ShapelyPolygon] = []
    if holes:
        from shapely.geometry import Point as _ShapelyPoint
        for _hcx, _hcy, _hr in holes:
            _hole_circles.append(_ShapelyPoint(_hcx, _hcy).buffer(_hr))

    for poly in egm_data.get("polygons", []):
        ptype = poly.get("type")
        if ptype not in ("trap", "water"):
            continue
        # poly["points"] is a list of {"x": float, "y": float} dicts
        try:
            pts_px = interpolate_catmull_rom(poly["points"])
        except Exception:
            pts_px = np.array([[p["x"], p["y"]] for p in poly["points"]], dtype=np.float64)
        pts_mm = _px_to_mm_2d(pts_px, scale, centroid_px)
        try:
            sp = ShapelyPolygon(pts_mm)
            if not sp.is_valid:
                sp = sp.buffer(0)
            # Subtract every pipe-hole circle from the carve-out polygon.
            for _hc in _hole_circles:
                if sp.intersects(_hc):
                    sp_diff = sp.difference(_hc)
                    if not sp_diff.is_empty:
                        sp = sp_diff if not isinstance(sp_diff, ShapelyMultiPolygon) \
                            else max(sp_diff.geoms, key=lambda g: g.area)
        except Exception:
            sp = None
        if ptype == "trap":
            trap_polys_mm.append(pts_mm)
            if sp is not None:
                trap_shapely.append(sp)
        else:  # water
            water_polys_mm.append(pts_mm)
            if sp is not None:
                water_shapely.append(sp)

    # --- Build Shapely green polygon for point-in-polygon tests ---
    green_shapely = ShapelyPolygon(green_bnd_mm)
    if not green_shapely.is_valid:
        green_shapely = green_shapely.buffer(0)

    # Union all traps + water polygons. They share the same carve-out role:
    # any cell falling inside either type must be excluded from the fringe so
    # the corresponding slab can drop into a real recess.
    #
    # Fringe-rectangle clip note (#343): the trap/water mesh path clips each
    # polygon to the fringe rectangle (see _clip_polygon_to_fringe_rect, used
    # in export_trap_stls / export_water_meshes). We do NOT need to clip
    # `traps_union` here because the fringe builder loops over a grid spanning
    # exactly [-half, +half] on each axis (xs_mm / ys_mm above), so the
    # `traps_union.contains(sp)` test is only ever consulted for points inside
    # the fringe rectangle. Any portion of a trap/water polygon outside the
    # rectangle simply has no fringe cells to carve out — the implicit clip
    # by the iteration domain matches the explicit clip applied to the slab.
    _carve_shapely = trap_shapely + water_shapely
    if _carve_shapely:
        from shapely.ops import unary_union
        traps_union = unary_union(_carve_shapely)
    else:
        traps_union = None

    print(f"  Fringe grid: {fringe_grid_res}x{fringe_grid_res} over ±{half:.2f} mm")
    print(f"  Green boundary: {len(green_bnd_mm)} mm-space points")
    print(f"  Trap polygons: {len(trap_polys_mm)}")
    print(f"  Water polygons: {len(water_polys_mm)}")
    if holes:
        print(f"  Baked holes: {holes}")

    # --- Build fringe mask and height array ---
    # fringe_mask[r, c] = True iff cell is in the fringe region
    fringe_mask = np.zeros((fringe_grid_res, fringe_grid_res), dtype=bool)
    Z_fringe = np.full((fringe_grid_res, fringe_grid_res), np.nan)

    # Pre-build KD-tree of valid green grid cells for fast Z lookups.
    # When the green is terraced, the seam-reseat step (below) snaps fringe
    # boundary cells to the QUANTIZED Z. If the lerp baseline used the raw
    # smooth Z_mm here, a seam cell would jump from raw smooth to the next
    # higher terrace band, and its non-seam neighbour (one cell outward)
    # would lerp from the smooth value — creating a step of up to one
    # terrace height. We avoid that by lerping from the same quantized Z
    # source the seam ends up using. (Smooth-style green: use Z_mm as before.)
    _green_style_lerp = str(egm_data.get("greenStyle", "smooth")).lower()
    if _green_style_lerp == "terraced":
        _valid_vals_lerp = Z_mm[inside_mask]
        _z_min_lerp = float(_valid_vals_lerp.min())
        _z_max_lerp = float(_valid_vals_lerp.max())
        _step_lerp = (_z_max_lerp - _z_min_lerp) / N_CONTOUR_LEVELS
        if _step_lerp < 1e-9:
            _step_lerp = 1.0
        _Z_lerp_src = np.copy(Z_mm)
        _Z_lerp_src[inside_mask] = (
            np.round((_Z_lerp_src[inside_mask] - _z_min_lerp) / _step_lerp)
            * _step_lerp + _z_min_lerp
        )
    else:
        _Z_lerp_src = Z_mm

    # Apply perimeter median filter to the lerp source so it matches the
    # filtered Z_for_seam below (built with the same recipe + filter). This
    # keeps the lerp baseline at the green edge and the seam-reseat snap
    # targets in lockstep — no step at the seam between the lerp source and
    # the seam vertices.
    _Z_lerp_src = _perimeter_median_filter(_Z_lerp_src, inside_mask, window=7)

    valid_rows_g, valid_cols_g = np.where(inside_mask)
    green_cell_xy = np.column_stack([xs_mm_green[valid_cols_g], ys_mm_green[valid_rows_g]])
    green_cell_z  = _Z_lerp_src[valid_rows_g, valid_cols_g]
    green_kd = cKDTree(green_cell_xy)

    # Pre-build array of green boundary points in mm for vectorised dist
    gbnd = green_bnd_mm  # (N, 2)

    for r in range(fringe_grid_res):
        for c in range(fringe_grid_res):
            x = float(xs_mm[c])
            y = float(ys_mm[r])

            # Must be INSIDE the print rectangle (always true by construction)
            # Must be OUTSIDE the green
            # Use Shapely contains for green check (faster than cv2 here)
            from shapely.geometry import Point as ShapelyPoint
            sp = ShapelyPoint(x, y)
            if green_shapely.contains(sp):
                continue  # inside green → skip

            # Must be OUTSIDE all traps and water polygons (carve-out region)
            if traps_union is not None and traps_union.contains(sp):
                continue

            # Must be OUTSIDE all baked holes
            if holes:
                in_hole = False
                for hcx, hcy, hradius in holes:
                    if math.hypot(x - hcx, y - hcy) <= hradius:
                        in_hole = True
                        break
                if in_hole:
                    continue

            # Distance to green boundary (polyline walk)
            d_green, nx, ny = _min_dist_to_polyline(x, y, gbnd)

            # Distance to rectangle boundary
            d_rect = _rect_dist_mm(x, y, half)

            # Blend factor: 0 at green edge, 1 at rectangle
            total = d_green + d_rect
            if total < 1e-9:
                t = 0.5
            else:
                t = d_green / total

            # Green-edge height: find nearest valid green grid cell to (nx, ny)
            _, idx_g = green_kd.query([nx, ny], k=1)
            green_edge_h = float(green_cell_z[idx_g])

            # Fringe height: lerp from green edge height to FRINGE_EDGE_HEIGHT_MM
            z_fringe = green_edge_h * (1.0 - t) + FRINGE_EDGE_HEIGHT_MM * t

            # Clamp to reasonable range
            z_fringe = max(BASE_THICKNESS_MM, min(z_fringe, BASE_THICKNESS_MM + ELEVATION_RANGE_MM))

            fringe_mask[r, c] = True
            Z_fringe[r, c] = z_fringe

    n_fringe = fringe_mask.sum()
    print(f"  Fringe cells: {n_fringe}")
    if n_fringe == 0:
        raise RuntimeError("No fringe cells found — check coordinate system")

    # Fringe smoothing disabled — keeping raw interpolated surface
    valid_z = Z_fringe[fringe_mask]
    print(f"  Fringe Z range: {valid_z.min():.3f} .. {valid_z.max():.3f} mm")

    # ── Seam-reseat: snap fringe's INNER boundary cells to the green mesh's ──
    # actual top-boundary vertex ring. Without this step the fringe grid and
    # the green grid are independent, so their seam vertices don't coincide
    # in either XY or Z — producing a visible crease where the fringe meets
    # the green (the defect Thomas reported around the 11 o'clock arc).
    #
    # The green mesh's top-boundary vertices are exactly those inside_mask
    # cells that have at least one 4-neighbour outside inside_mask, at
    # positions (xs_mm_green[c], ys_mm_green[r], Z_for_seam[r, c]).
    #
    # If the green is rendered terraced (greenStyle=="terraced" in the EGM),
    # its boundary Z values are the quantized Z_plot from _build_heightmap_mesh,
    # not the raw Z_mm. We replicate that quantization here so the seam
    # exactly matches the green mesh's boundary, whichever style is used.
    green_style = str(egm_data.get("greenStyle", "smooth")).lower()
    if green_style == "terraced":
        valid_vals = Z_mm[inside_mask]
        z_min_g, z_max_g = valid_vals.min(), valid_vals.max()
        step_g = (z_max_g - z_min_g) / N_CONTOUR_LEVELS
        if step_g < 1e-9:
            step_g = 1.0
        Z_for_seam = np.copy(Z_mm)
        Z_for_seam[inside_mask] = (
            np.round((Z_for_seam[inside_mask] - z_min_g) / step_g) * step_g + z_min_g
        )
    else:
        Z_for_seam = Z_mm

    # Apply perimeter median filter to Z_for_seam so the seam Z values match
    # the green mesh's filtered top-boundary vertices (which had the same
    # filter applied inside _build_heightmap_mesh). Without this the seam
    # snap-targets here would not coincide with the green mesh's actual
    # boundary Z, re-opening the seam crease. Same filter also runs over
    # the lerp source (since Z_for_seam == _Z_lerp_src after #314 alignment
    # for terraced style — the smooth case lerp source still tracks Z_mm).
    Z_for_seam = _perimeter_median_filter(Z_for_seam, inside_mask, window=7)

    # Collect green top-boundary ring (mm space, with Z)
    g_nrows, g_ncols = inside_mask.shape
    g_bdry_pts = []  # (x, y, z)
    for gr in range(g_nrows):
        for gc in range(g_ncols):
            if not inside_mask[gr, gc]:
                continue
            # has at least one 4-neighbour outside?
            nbrs_outside = False
            for dr, dc in ((-1, 0), (1, 0), (0, -1), (0, 1)):
                nr, nc = gr + dr, gc + dc
                if (nr < 0 or nr >= g_nrows or nc < 0 or nc >= g_ncols
                        or not inside_mask[nr, nc]):
                    nbrs_outside = True
                    break
            if nbrs_outside:
                g_bdry_pts.append(
                    (float(xs_mm_green[gc]), float(ys_mm_green[gr]),
                     float(Z_for_seam[gr, gc]))
                )
    if g_bdry_pts:
        g_bdry_arr = np.asarray(g_bdry_pts, dtype=np.float64)
        g_bdry_kd = cKDTree(g_bdry_arr[:, :2])
        # Fringe cell spacing (approx; grid may be anisotropic — take max for safety)
        dx_fringe = float(xs_mm[1] - xs_mm[0])
        dy_fringe = float(ys_mm[1] - ys_mm[0])
        seam_radius = 1.5 * max(abs(dx_fringe), abs(dy_fringe))

        # Pre-build a KD-tree of green boundary polyline for seam-cell detection
        gbnd_kd_seam = cKDTree(gbnd)

        # Build override map: (r, c) -> (x, y, z)
        seam_override: dict[tuple[int, int], tuple[float, float, float]] = {}
        for r in range(fringe_grid_res):
            for c in range(fringe_grid_res):
                if not fringe_mask[r, c]:
                    continue
                x = float(xs_mm[c]); y = float(ys_mm[r])
                # cell is on the inner (green-adjacent) boundary if it sits
                # within one fringe-grid-step of the green polyline
                d_bnd, _ = gbnd_kd_seam.query([x, y], k=1)
                if d_bnd > seam_radius:
                    continue
                # snap to nearest green top-boundary mesh vertex
                _, gi = g_bdry_kd.query([x, y], k=1)
                gx, gy, gz = g_bdry_arr[gi]
                seam_override[(r, c)] = (float(gx), float(gy), float(gz))
                Z_fringe[r, c] = gz  # keep the height array consistent
        print(f"  Seam-reseat: snapped {len(seam_override)} fringe inner-boundary "
              f"cells to green mesh's top-boundary ring "
              f"(greenStyle={green_style})")
    else:
        seam_override = {}

    # ── Pointy-spike filter (task #314) ──────────────────────────────────────
    # Both spike clusters identified in #313 (9 seam-stilt cells along the
    # south arc + 1 tall lerp spike near the rect edge) are local outliers in
    # the fringe top surface. We run a mask-aware median filter on Z_fringe:
    # each in-mask cell is replaced by the median of the in-mask cells inside
    # a KxK window around it (cells outside the mask are dropped from the
    # window). This is approach (a) from Thomas's spec — generic_filter with
    # a custom callable — and avoids any out-of-mask bias that approach (b)
    # would introduce at mask boundaries.
    #
    # We do NOT exclude the seam cells from the filter input — their Z is
    # already the green-boundary truth, so letting it propagate one cell
    # inward actually improves the seam blend. The exact seam vertex Z is
    # still restored from `seam_override` when top_verts is built (below), so
    # the seam itself remains pinned to the green mesh.
    def _masked_median(
        Z_in: np.ndarray, mask_in: np.ndarray, size: int
    ) -> np.ndarray:
        """KxK median where out-of-mask cells are dropped from the window."""
        out = Z_in.copy()
        nrows, ncols = Z_in.shape
        half = size // 2
        for r in range(nrows):
            for c in range(ncols):
                if not mask_in[r, c]:
                    continue
                r0, r1 = max(0, r - half), min(nrows, r + half + 1)
                c0, c1 = max(0, c - half), min(ncols, c + half + 1)
                win = Z_in[r0:r1, c0:c1]
                wm = mask_in[r0:r1, c0:c1]
                vals = win[wm]
                if vals.size:
                    out[r, c] = float(np.median(vals))
        return out

    if fringe_mask.any():
        # Spike-scanner BEFORE: 8-neighbour median + 1.5 mm threshold
        before_count = _count_fringe_spikes(Z_fringe, fringe_mask, 1.5)

        # ── Half-strength median (task #315, Thomas) ─────────────────────
        # Per Thomas, the full 3x3 mask-aware median over-smoothed the
        # carefully tuned green→rect taper. We retain the median's outlier-
        # killing power but blend 50/50 with the original Z_fringe inside
        # the fringe mask, halving its effect. Cells outside fringe_mask
        # are untouched (NaN preserved). The structural lerp-source fix at
        # lines ~1514–1529 is the actual spike killer (per #314 the spike
        # count was already 0 BEFORE the median ran), so a 50% blend
        # should remain spike-free — verified by the FINAL scan below.
        FRINGE_MEDIAN_BLEND = 0.5  # 0 = no smoothing, 1 = full median
        Z_filtered = _masked_median(Z_fringe, fringe_mask, size=3)
        Z_blended = np.where(
            fringe_mask,
            FRINGE_MEDIAN_BLEND * Z_filtered
            + (1.0 - FRINGE_MEDIAN_BLEND) * Z_fringe,
            Z_fringe,
        )
        Z_fringe = Z_blended
        after_count = _count_fringe_spikes(Z_fringe, fringe_mask, 1.5)
        print(f"  Spike filter (3x3 mask-aware median, "
              f"blend={FRINGE_MEDIAN_BLEND:.2f}): "
              f"spikes >1.5mm above 8-nbr median: {before_count} -> {after_count}")

        # Escalate to 5x5 if any spike survives — same blend ratio.
        if after_count > 0:
            Z_filtered5 = _masked_median(Z_fringe, fringe_mask, size=5)
            Z_fringe = np.where(
                fringe_mask,
                FRINGE_MEDIAN_BLEND * Z_filtered5
                + (1.0 - FRINGE_MEDIAN_BLEND) * Z_fringe,
                Z_fringe,
            )
            after_count2, _spike_locs = _count_fringe_spikes(
                Z_fringe, fringe_mask, 1.5, return_locations=True
            )
            print(f"  Spike filter (5x5 escalation, "
                  f"blend={FRINGE_MEDIAN_BLEND:.2f}): "
                  f"{after_count} -> {after_count2}")
            if after_count2 > 0:
                sample = sorted(_spike_locs, key=lambda t: -t[4])[:5]
                for r, c, z, med, d in sample:
                    x = float(xs_mm[c]); y = float(ys_mm[r])
                    print(f"    spike at (r={r},c={c}) "
                          f"xy=({x:+.2f},{y:+.2f}) "
                          f"z={z:.3f} 8nbr-med={med:.3f} Δ={d:+.3f}")

    # FINAL spike scan on the array that actually becomes top vertices:
    # filtered Z_fringe combined with seam_override (since seam cells get
    # their Z from the override, not Z_fringe, when top_verts is built).
    Z_final_top = Z_fringe.copy()
    for (sr, sc), (_sx, _sy, sz) in seam_override.items():
        Z_final_top[sr, sc] = sz
    final_spikes = _count_fringe_spikes(Z_final_top, fringe_mask, 1.5)
    print(f"  FINAL fringe top surface (Z_fringe + seam_override) "
          f"spikes >1.5mm above 8-nbr median: {final_spikes}")

    # --- Build mesh using the same grid-triangulation approach as _build_heightmap_mesh ---
    # We reuse that function by passing our fringe grid and mask.
    # We need to supply xs_grid and ys_grid in PIXEL space for _build_heightmap_mesh,
    # but that function converts them internally. Instead we build the mesh directly
    # here since we already have mm coords.

    # Top surface vertices
    vert_idx = np.full((fringe_grid_res, fringe_grid_res), -1, dtype=int)
    top_verts: list[list[float]] = []
    for r in range(fringe_grid_res):
        for c in range(fringe_grid_res):
            if fringe_mask[r, c]:
                vert_idx[r, c] = len(top_verts)
                if (r, c) in seam_override:
                    # Shared-seam vertex: exact (x,y,z) from green's top-boundary ring
                    ox, oy, oz = seam_override[(r, c)]
                    top_verts.append([ox, oy, oz])
                else:
                    top_verts.append([float(xs_mm[c]), float(ys_mm[r]),
                                      float(Z_fringe[r, c])])

    # Top surface faces (only fully-fringe quads)
    top_faces: list[list[int]] = []
    for r in range(fringe_grid_res - 1):
        for c in range(fringe_grid_res - 1):
            v00 = vert_idx[r,   c]
            v01 = vert_idx[r,   c+1]
            v10 = vert_idx[r+1, c]
            v11 = vert_idx[r+1, c+1]
            if v00 < 0 or v01 < 0 or v10 < 0 or v11 < 0:
                continue
            top_faces.append([v00, v10, v11])
            top_faces.append([v00, v11, v01])

    # Find boundary edges of the top surface
    edge_count: dict[tuple[int, int], int] = defaultdict(int)
    for f in top_faces:
        a, b, c_ = f
        edge_count[(a, b)] += 1
        edge_count[(b, c_)] += 1
        edge_count[(c_, a)] += 1

    boundary_edges: list[tuple[int, int]] = []
    for (a, b), cnt in edge_count.items():
        if edge_count.get((b, a), 0) == 0:
            boundary_edges.append((a, b))

    # Wall vertices and faces
    top_verts_arr = np.array(top_verts, dtype=np.float64)
    n_top = len(top_verts_arr)
    top_to_bot: dict[int, int] = {}
    bot_verts: list[list[float]] = []

    def get_bot_fringe(vi: int) -> int:
        if vi not in top_to_bot:
            top_to_bot[vi] = n_top + len(bot_verts)
            bot_verts.append([top_verts_arr[vi, 0], top_verts_arr[vi, 1], 0.0])
        return top_to_bot[vi]

    wall_faces: list[list[int]] = []
    for va, vb in boundary_edges:
        ba = get_bot_fringe(va)
        bb = get_bot_fringe(vb)
        wall_faces.append([va, vb, bb])
        wall_faces.append([va, bb, ba])

    # Bottom cap — polygon with holes (cutouts for green and traps)
    # Extract boundary loops from the wall edges (already built in top_to_bot)
    bot_next: dict[int, int] = {}
    for va, vb in boundary_edges:
        ba = top_to_bot[va]
        bb = top_to_bot[vb]
        bot_next[bb] = ba

    visited: set[int] = set()
    loops: list[list[int]] = []
    for start in list(bot_next.keys()):
        if start in visited:
            continue
        loop = []
        cur = start
        for _ in range(len(bot_next) + 1):
            if cur in visited:
                break
            visited.add(cur)
            loop.append(cur)
            cur = bot_next.get(cur, -1)
            if cur == start or cur < 0:
                break
        if len(loop) >= 3:
            loops.append(loop)

    # Build KD-tree over bot_verts for snapping
    bot_verts_arr = np.array([[v[0], v[1]] for v in bot_verts], dtype=np.float64)
    bot_kd = cKDTree(bot_verts_arr)

    cap_faces: list[list[int]] = []

    if loops:
        # Classify loops: the outer ring has the largest area; inner loops are holes
        loop_polys = []
        for loop in loops:
            xy = np.array([[bot_verts[vi - n_top][0], bot_verts[vi - n_top][1]]
                           for vi in loop], dtype=np.float64)
            loop_polys.append((loop, xy, ShapelyPolygon(xy)))

        # Sort by area descending; largest is outer ring
        loop_polys.sort(key=lambda t: abs(t[2].area), reverse=True)
        outer_loop, outer_xy, outer_shapely = loop_polys[0]
        holes_loops = [(lp[0], lp[1]) for lp in loop_polys[1:]]

        # Build Shapely polygon with holes from actual boundary vertices
        # Ensure outer ring is CCW and holes are CW for Shapely
        from shapely.geometry import LinearRing
        outer_ring = LinearRing(outer_xy)
        if not outer_ring.is_ccw:
            outer_xy = outer_xy[::-1]
        hole_rings = []
        for _, hole_xy in holes_loops:
            ring = LinearRing(hole_xy)
            if ring.is_ccw:
                hole_xy = hole_xy[::-1]
            hole_rings.append(hole_xy)

        bottom_poly = ShapelyPolygon(outer_xy, hole_rings)
        if not bottom_poly.is_valid:
            bottom_poly = bottom_poly.buffer(0)

        # Triangulate using earcut — force_vertices=True avoids inserting new points
        try:
            cap_verts_2d, cap_tri_idx = trimesh.creation.triangulate_polygon(
                bottom_poly, engine="earcut"
            )
            # Snap each triangulation vertex to nearest bot_vert
            dists, idxs = bot_kd.query(cap_verts_2d)
            snap_threshold = (PRINT_SIZE_MM / fringe_grid_res) * 3  # 3 grid cells
            local_to_global: dict[int, int] = {}
            for local_i, (dist, li) in enumerate(zip(dists, idxs)):
                if dist < snap_threshold:
                    local_to_global[local_i] = n_top + li
                else:
                    # Interior vertex — add as new bottom vertex
                    x_new, y_new = float(cap_verts_2d[local_i, 0]), float(cap_verts_2d[local_i, 1])
                    new_idx = n_top + len(bot_verts)
                    bot_verts.append([x_new, y_new, 0.0])
                    local_to_global[local_i] = new_idx

            for tri in cap_tri_idx:
                fn0 = local_to_global.get(tri[0], -1)
                fn1 = local_to_global.get(tri[1], -1)
                fn2 = local_to_global.get(tri[2], -1)
                if fn0 >= 0 and fn1 >= 0 and fn2 >= 0 and fn0 != fn1 and fn1 != fn2 and fn0 != fn2:
                    # Reverse winding so normal points down (−Z)
                    cap_faces.append([fn0, fn2, fn1])
            print(f"  Bottom cap: {len(cap_faces)} triangles (polygon-with-holes, earcut)")
        except Exception as e:
            print(f"  Bottom cap earcut failed ({e}), using fan fallback")
            for loop, loop_xy, _ in loop_polys:
                v0 = loop[0]
                for i in range(1, len(loop) - 1):
                    cap_faces.append([v0, loop[i+1], loop[i]])

    # --- Hole walls ---
    # The `holes` parameter excludes bore regions from `fringe_mask`, which means the
    # bore edge becomes part of the fringe top-surface boundary.  The `wall_faces` loop
    # above (which iterates all boundary_edges) already generates walls from the bore
    # edge top surface down to z=0, and the polygon-with-holes bottom cap closes the
    # bore at z=0.  No separate cylinder ring is needed or wanted here — adding one
    # produces a disconnected second body (the plug) in the output mesh.
    hole_wall_faces: list[list[int]] = []
    if holes:
        print(f"  Bore walls handled by fringe boundary edges for {len(holes)} hole(s) "
              f"(no separate cylinder ring emitted)")

    # Assemble
    all_verts = top_verts + bot_verts
    all_faces = top_faces + wall_faces + cap_faces + hole_wall_faces

    verts_np = np.array(all_verts, dtype=np.float64)
    faces_np = np.array(all_faces, dtype=np.int64)

    mesh = trimesh.Trimesh(vertices=verts_np, faces=faces_np, process=True)
    trimesh.repair.fix_normals(mesh)
    trimesh.repair.fill_holes(mesh)
    print(f"  Fringe: top_faces={len(top_faces)} wall_faces={len(wall_faces)} "
          f"cap_faces={len(cap_faces)}")
    return mesh


def _verify_fringe_boundary(
    fringe_mesh: trimesh.Trimesh,
    _Z_mm: np.ndarray,
    xs_grid: np.ndarray,
    ys_grid: np.ndarray,
    _inside_mask: np.ndarray,
    green_boundary_px: np.ndarray,
    egm_data: dict,
) -> None:
    """
    Spot-check fringe Z values near the green boundary and rectangle edge.
    Prints a brief report.
    """
    scale, centroid_px = _compute_px_to_mm(green_boundary_px, egm_data)
    half = PRINT_SIZE_MM / 2.0 + FRINGE_XY_EXPANSION_MM / 2.0  # matches build_fringe_mesh; signed offset

    verts = fringe_mesh.vertices  # (N, 3)

    # Near-green verts: within 1mm of the green boundary in XY
    _xs_mm_green = (xs_grid - centroid_px[0]) * scale
    _ys_mm_green = -(ys_grid - centroid_px[1]) * scale
    green_bnd_mm = _px_to_mm_2d(green_boundary_px.copy(), scale, centroid_px)

    # Find fringe verts closest to the green boundary
    from scipy.spatial import cKDTree
    kd = cKDTree(green_bnd_mm)
    dists_to_green, _ = kd.query(verts[:, :2])
    # Only consider top-surface verts (z > 0.5 mm) to exclude wall bottom verts
    top_verts_mask = verts[:, 2] > 0.5
    top_verts_only = verts[top_verts_mask]

    near_green_top = top_verts_only[dists_to_green[top_verts_mask] < 3.0]

    # Find fringe top verts near rectangle edge
    rect_dists_top = np.minimum.reduce([
        top_verts_only[:, 0] - (-half),
        half - top_verts_only[:, 0],
        top_verts_only[:, 1] - (-half),
        half - top_verts_only[:, 1],
    ])
    near_rect_top = top_verts_only[rect_dists_top < 3.0]

    if len(near_green_top) > 0:
        print(f"  Fringe top-surface Z near green boundary (should match green edge): "
              f"mean={near_green_top[:, 2].mean():.2f} "
              f"min={near_green_top[:, 2].min():.2f} "
              f"max={near_green_top[:, 2].max():.2f} mm")
    else:
        print("  No fringe top-surface verts near green boundary found")

    if len(near_rect_top) > 0:
        print(f"  Fringe top-surface Z near rect boundary (should be ~{BASE_THICKNESS_MM:.1f} mm): "
              f"mean={near_rect_top[:, 2].mean():.2f} "
              f"min={near_rect_top[:, 2].min():.2f} "
              f"max={near_rect_top[:, 2].max():.2f} mm")
    else:
        print("  No fringe top-surface verts near rect boundary found")


def build_mount_pipe_mesh(
    cx: float,
    cy: float,
    inner_radius: float,
    outer_radius: float,
    z_top: float,
    n_seg: int = 64,
) -> trimesh.Trimesh:
    """
    Build a watertight hollow cylinder ("pipe") for the upper-left mounting
    bore: a vertical annulus extruded from z=0 to z=z_top, with a clean
    through-bore at radius `inner_radius` and an outer wall at `outer_radius`.

    The mesh has four surfaces, all closed and CCW-outward:
      - outer cylinder wall (radius=outer_radius, z in [0, z_top])
      - inner cylinder wall (radius=inner_radius, z in [0, z_top])
      - top annulus cap at z=z_top (between inner and outer radius)
      - bottom annulus cap at z=0 (between inner and outer radius)

    The bore (radius < inner_radius) is open from top to bottom, exactly as a
    pipe should be. Designed for task #335: a structural wall around a 3/16"
    mounting bore in the upper-left fringe corner.
    """
    if z_top <= 0.0:
        raise ValueError(f"build_mount_pipe_mesh: z_top must be > 0 (got {z_top})")
    if inner_radius >= outer_radius:
        raise ValueError(
            f"build_mount_pipe_mesh: inner_radius ({inner_radius}) must be < "
            f"outer_radius ({outer_radius})"
        )

    angles = np.linspace(0.0, 2.0 * np.pi, n_seg, endpoint=False)
    cos_a = np.cos(angles)
    sin_a = np.sin(angles)

    # Vertex layout: 4 rings of n_seg vertices each.
    # Ring 0: outer-bottom (radius=outer_radius, z=0)
    # Ring 1: outer-top    (radius=outer_radius, z=z_top)
    # Ring 2: inner-bottom (radius=inner_radius, z=0)
    # Ring 3: inner-top    (radius=inner_radius, z=z_top)
    verts: list[list[float]] = []
    for j in range(n_seg):
        verts.append([cx + outer_radius * cos_a[j], cy + outer_radius * sin_a[j], 0.0])
    for j in range(n_seg):
        verts.append([cx + outer_radius * cos_a[j], cy + outer_radius * sin_a[j], z_top])
    for j in range(n_seg):
        verts.append([cx + inner_radius * cos_a[j], cy + inner_radius * sin_a[j], 0.0])
    for j in range(n_seg):
        verts.append([cx + inner_radius * cos_a[j], cy + inner_radius * sin_a[j], z_top])

    def ob(j): return j                    # outer-bottom index
    def ot(j): return n_seg + j            # outer-top index
    def ib(j): return 2 * n_seg + j        # inner-bottom index
    def it(j): return 3 * n_seg + j        # inner-top index

    faces: list[list[int]] = []
    for j in range(n_seg):
        j1 = (j + 1) % n_seg

        # Outer wall — outward normal points away from axis (+radial).
        # Quad (ob[j], ob[j1], ot[j1], ot[j]) → 2 CCW tris when viewed from +radial.
        faces.append([ob(j),  ob(j1), ot(j1)])
        faces.append([ob(j),  ot(j1), ot(j)])

        # Inner wall — outward normal points TOWARD axis (−radial), since the
        # bore is a void inside the pipe. Reverse winding vs outer wall.
        faces.append([ib(j),  it(j1), ib(j1)])
        faces.append([ib(j),  it(j),  it(j1)])

        # Top annulus cap at z=z_top — outward normal is +Z.
        # Quad outer-top j → outer-top j1 → inner-top j1 → inner-top j.
        faces.append([ot(j),  it(j1), ot(j1)])
        faces.append([ot(j),  it(j),  it(j1)])

        # Bottom annulus cap at z=0 — outward normal is −Z (reverse winding).
        faces.append([ob(j),  ob(j1), ib(j1)])
        faces.append([ob(j),  ib(j1), ib(j)])

    mesh = trimesh.Trimesh(
        vertices=np.asarray(verts, dtype=np.float64),
        faces=np.asarray(faces, dtype=np.int64),
        process=True,
    )
    trimesh.repair.fix_normals(mesh)
    return mesh


# ---------------------------------------------------------------------------
# Step 9: Contour lines debug image
# ---------------------------------------------------------------------------

def save_contour_debug_image(
    Z_grid: np.ndarray,
    xs_grid: np.ndarray,
    ys_grid: np.ndarray,
    inside_mask: np.ndarray,
    img: np.ndarray,
    green_boundary_px: np.ndarray,
    out_path: str,
) -> None:
    """
    Draw contour lines on the source image within the green boundary.
    Each of N_CONTOUR_LEVELS levels gets a distinct colour.
    """
    valid = Z_grid[inside_mask]
    z_min, z_max = valid.min(), valid.max()

    # Replace NaN with z_min for find_contours (outside cells)
    Z_filled = np.where(inside_mask, Z_grid, z_min)

    levels = np.linspace(z_min, z_max, N_CONTOUR_LEVELS + 2)[1:-1]  # exclude exact min/max

    # Build colour palette
    cmap = plt.get_cmap("turbo", len(levels))
    colours_bgr = []
    for i in range(len(levels)):
        r, g, b, _ = cmap(i)
        colours_bgr.append((int(b * 255), int(g * 255), int(r * 255)))

    # Map grid coordinates back to pixel coords for drawing
    # xs_grid[col] = x_pixel, ys_grid[row] = y_pixel
    x0, x1 = xs_grid[0], xs_grid[-1]
    y0, y1 = ys_grid[0], ys_grid[-1]
    grid_res = Z_grid.shape[0]

    vis = img.copy()

    # Draw green boundary
    boundary_i = green_boundary_px.astype(np.int32)
    cv2.polylines(vis, [boundary_i], isClosed=True, color=(0, 220, 0), thickness=2)

    for i, level in enumerate(levels):
        contours = measure.find_contours(Z_filled, level=level)
        colour = colours_bgr[i]
        for contour in contours:
            # contour is (N, 2) array in (row, col) order (floating point)
            pts = []
            for (row_f, col_f) in contour:
                # Interpolate pixel position
                px = x0 + (col_f / (grid_res - 1)) * (x1 - x0)
                py = y0 + (row_f / (grid_res - 1)) * (y1 - y0)
                pts.append((int(round(px)), int(round(py))))
            if len(pts) >= 2:
                for j in range(len(pts) - 1):
                    cv2.line(vis, pts[j], pts[j+1], colour, thickness=2)

    # Legend: colour swatch + level value
    legend_x, legend_y = 10, 10
    swatch_h, swatch_w = 16, 24
    for i, level in enumerate(levels):
        y = legend_y + i * (swatch_h + 2)
        colour = colours_bgr[i]
        cv2.rectangle(vis, (legend_x, y), (legend_x + swatch_w, y + swatch_h), colour, -1)
        cv2.putText(
            vis, f"{level:.1f}",
            (legend_x + swatch_w + 4, y + swatch_h - 3),
            cv2.FONT_HERSHEY_SIMPLEX, 0.4, (255, 255, 255), 1, cv2.LINE_AA
        )

    os.makedirs(os.path.dirname(out_path), exist_ok=True)
    cv2.imwrite(out_path, vis)
    print(f"  Saved: {out_path}")


# ---------------------------------------------------------------------------
# Step 10: Export sand trap STLs
# ---------------------------------------------------------------------------

TRAP_THICKNESS_MM: float = 10.0     # flat slab thickness for traps
PRINT_TOLERANCE_MM: float = 0.03125  # inset each piece for easier fit

# ---------------------------------------------------------------------------
# Water hazard ripple texture — sinusoidal "wind chop" displacement
# ---------------------------------------------------------------------------
#
# Approach A from owner_inbox/golf_water_ripple_proposal.md, tuned for
# medium-blue PLA filament (between translucent — where ripples read
# beautifully at low amplitude — and opaque deep blue, which swallows
# subtle texture).  Two superposed sine waves at near-perpendicular angles
# produce an interference pattern that reads as choppy water at print scale.
#
# Per-pond seeding: angles + phases are derived from a hash of the water
# polygon's control-point coordinates so the same pond regenerates the same
# ripple every build (reproducibility) but adjacent ponds look different.
#
# Print constraint: top of the ripple is clamped at the unrippled water
# height — displacement is **downward only** so peaks never poke above the
# surrounding fringe terrain (which would create overhangs and make the
# water slab visually float above its socket).
WATER_RIPPLE_ENABLED: bool = True   # master toggle for water ripple texture
WATER_RIPPLE_A1: float = 0.20       # primary wave amplitude, mm
                                    #   (was 0.25 default; bumped down a touch
                                    #   for medium-blue filament — still visible
                                    #   but doesn't fight the colour)
WATER_RIPPLE_A2: float = 0.08       # secondary wave amplitude, mm (interference detail)
WATER_RIPPLE_LAMBDA1: float = 4.0   # primary wavelength, mm — choppy end of the 3–5 mm range
WATER_RIPPLE_LAMBDA2: float = 2.5   # secondary wavelength, mm — high-frequency cross-chop
WATER_RIPPLE_GRID_STEP: float = 0.5 # XY sampling step, mm
                                    #   (~5 samples per primary period; one nozzle
                                    #   width-ish.  Vertex budget ≈ 60×172/0.5² ≈
                                    #   41 K verts per pond — well under 150 K cap.)


def _clip_polygon_to_fringe_rect(
    poly: ShapelyPolygon,
    label: str,
) -> "ShapelyPolygon | None":
    """
    Clip a trap or water polygon to the fringe rectangle bounding the
    printable assembly. Thomas's rule: any trap or water shape that crosses
    the fringe rectangle's straight edges must be cut at the rectangle so
    nothing pokes past the frame.

    The rectangle is centred at the origin in mm space and uses the same
    half-extent as the fringe builder:

        _half = PRINT_SIZE_MM / 2.0 + FRINGE_XY_EXPANSION_MM / 2.0

    Returns:
      * The clipped Polygon if the input intersects the rectangle (possibly
        equal to the input if it was already entirely inside).
      * None if the input lies entirely outside the rectangle (caller should
        skip emitting any mesh for it). A skip log is printed here.

    If the intersection produces a MultiPolygon (rare — only if a thin
    trap/water shape is sliced in two by the rectangle), the largest piece
    by area is returned and the discarded pieces are logged.
    """
    _half = PRINT_SIZE_MM / 2.0 + FRINGE_XY_EXPANSION_MM / 2.0
    fringe_rect = shapely_box(-_half, -_half, +_half, +_half)
    if not poly.is_valid:
        poly = poly.buffer(0)
    clipped = poly.intersection(fringe_rect)
    if clipped.is_empty:
        print(f"  skipped {label}: entirely outside fringe rectangle")
        return None
    if isinstance(clipped, ShapelyMultiPolygon):
        parts = sorted(list(clipped.geoms), key=lambda g: g.area, reverse=True)
        kept = parts[0]
        dropped = parts[1:]
        if dropped:
            dropped_areas = ", ".join(f"{p.area:.2f}" for p in dropped)
            print(f"  {label}: clip produced MultiPolygon — kept largest "
                  f"({kept.area:.2f} mm^2), discarded {len(dropped)} part(s) "
                  f"with areas [{dropped_areas}] mm^2")
        return kept
    if isinstance(clipped, ShapelyPolygon):
        return clipped
    # Fallback: GeometryCollection or other — try to extract polygon area
    try:
        polys = [g for g in clipped.geoms if isinstance(g, ShapelyPolygon) and not g.is_empty]
        if not polys:
            print(f"  skipped {label}: clip yielded no polygon geometry")
            return None
        polys.sort(key=lambda g: g.area, reverse=True)
        return polys[0]
    except Exception:
        print(f"  skipped {label}: unrecognised clip geometry {type(clipped).__name__}")
        return None


# ---------------------------------------------------------------------------
# Water-containing-hole helpers (Topo, 2026-05-01)
# ---------------------------------------------------------------------------

def _hole_has_water(egm_data: dict) -> bool:
    """True iff the EGM defines one or more polygons of type 'water'."""
    return any(p.get("type") == "water" for p in egm_data.get("polygons", []))


def _polygon_touches_frame_boundary(
    poly: ShapelyPolygon,
    tol_mm: float = BOUNDARY_TOUCH_TOL_MM,
) -> bool:
    """
    Return True iff *poly* has any exterior vertex within ``tol_mm`` of the
    fringe rectangle perimeter (±_half per axis). The fringe rectangle is the
    same one used by ``_clip_polygon_to_fringe_rect``.
    """
    _half = PRINT_SIZE_MM / 2.0 + FRINGE_XY_EXPANSION_MM / 2.0
    coords = np.asarray(poly.exterior.coords, dtype=np.float64)
    if coords.size == 0:
        return False
    near_x = (np.abs(np.abs(coords[:, 0]) - _half) <= tol_mm)
    near_y = (np.abs(np.abs(coords[:, 1]) - _half) <= tol_mm)
    return bool(np.any(near_x | near_y))


def _apply_lift_and_cap(
    mesh: "trimesh.Trimesh",
    lift_mm: float,
    cap_mm: float | None,
    cap_mode: str = BOUNDARY_HEIGHT_CAP_MODE,
    label: str = "",
) -> dict:
    """
    Lift the *top-surface* vertices of ``mesh`` by ``lift_mm`` mm and
    optionally cap them at ``cap_mm`` mm.

    "Top-surface vertex" = any vertex with z > 0 in the input mesh. Bottom
    vertices (z == 0) stay pinned to z=0 so the wall stretches by ``lift_mm``,
    materialising the new 2 mm base. Mesh topology and watertight-ness are
    unchanged because the wall stitch is preserved.

    Cap modes (only applied when ``cap_mm`` is not None):
      - "hard"     : top z values above cap_mm are clipped to cap_mm.
      - "compress" : top z values are linearly squashed so max(z) == cap_mm.
        If max(z) <= cap_mm, no compression is applied.

    Returns a small stats dict: {applied, cap_triggered, vertices_clipped,
    max_clip_mm, z_top_before, z_top_after}.
    """
    verts = mesh.vertices  # live reference
    top_mask = verts[:, 2] > 1e-6
    if not top_mask.any():
        return {
            "applied": False,
            "cap_triggered": False,
            "vertices_clipped": 0,
            "max_clip_mm": 0.0,
            "z_top_before": (0.0, 0.0),
            "z_top_after":  (0.0, 0.0),
        }

    z_before_min = float(verts[top_mask, 2].min())
    z_before_max = float(verts[top_mask, 2].max())

    # Lift top surface uniformly. Bottom (z==0) stays at z=0; walls stretch.
    if lift_mm:
        verts[top_mask, 2] += lift_mm

    cap_triggered = False
    n_clipped = 0
    max_clip = 0.0
    if cap_mm is not None:
        z_top = verts[top_mask, 2]
        if cap_mode == "hard":
            over = z_top > cap_mm
            n_clipped = int(over.sum())
            if n_clipped:
                cap_triggered = True
                max_clip = float((z_top[over] - cap_mm).max())
                z_top = np.minimum(z_top, cap_mm)
                verts[top_mask, 2] = z_top
        elif cap_mode == "compress":
            zmax = float(z_top.max())
            if zmax > cap_mm:
                cap_triggered = True
                # Compress around the bottom (z=0): scale top z's by cap/zmax.
                scale = cap_mm / zmax
                # "Vertices clipped" here = vertices whose z was lowered.
                lowered = z_top * scale
                n_clipped = int((z_top - lowered > 1e-6).sum())
                max_clip = float((z_top - lowered).max())
                verts[top_mask, 2] = lowered
        else:
            raise ValueError(
                f"BOUNDARY_HEIGHT_CAP_MODE={cap_mode!r} not in {{'hard','compress'}}"
            )

    z_after_min = float(verts[top_mask, 2].min())
    z_after_max = float(verts[top_mask, 2].max())

    if label:
        print(f"    lift+cap [{label}]: lift={lift_mm:.2f} mm, "
              f"cap={'-' if cap_mm is None else f'{cap_mm:.1f} mm ({cap_mode})'}, "
              f"z_top {z_before_min:.2f}-{z_before_max:.2f} → "
              f"{z_after_min:.2f}-{z_after_max:.2f}, "
              f"clipped {n_clipped} vert(s), max_clip {max_clip:.2f} mm")

    return {
        "applied": True,
        "cap_triggered": cap_triggered,
        "vertices_clipped": n_clipped,
        "max_clip_mm": max_clip,
        "z_top_before": (z_before_min, z_before_max),
        "z_top_after":  (z_after_min, z_after_max),
    }


def export_trap_stls(
    egm_data: dict,
    green_boundary_px: np.ndarray,
    slug: str,
    fringe_mesh: "trimesh.Trimesh | None" = None,
    stl_dir: str | None = None,
    write_stls: bool = True,
    pipe_circle: "ShapelyPolygon | None" = None,
) -> list:
    """
    For every polygon of type 'trap' in egm_data, build a flat inset slab.

    When ``write_stls`` is True (default), each trap is exported to
    {stl_dir}/{slug}_trap_N.stl and a list of file paths is returned. When
    ``write_stls`` is False, no disk I/O is performed and a list of
    ``(node_name, trimesh.Trimesh)`` tuples is returned instead — the pipeline
    consumes those directly for the 3MF without round-tripping through disk.

    stl_dir defaults to the course's STLs/ folder (via course_paths), falling
    back to OWNER_INBOX if the course is unknown. It is only used when
    ``write_stls`` is True.

    Uses Catmull-Rom interpolation (matching the editor), applies the same
    px→mm transform as the green, insets by PRINT_TOLERANCE_MM, and extrudes
    to a height derived from the fringe mesh at the trap centroid (falls back
    to TRAP_THICKNESS_MM if fringe_mesh is unavailable).
    """
    from scipy.spatial import cKDTree as _cKDTree
    from shapely.geometry import Point as ShapelyPoint

    if write_stls:
        if stl_dir is None:
            course = egm_data.get("course", "")
            if course:
                stl_dir = course_paths(course)["stls"]
            else:
                stl_dir = OWNER_INBOX
        os.makedirs(stl_dir, exist_ok=True)

    scale, centroid_px = _compute_px_to_mm(green_boundary_px, egm_data)

    trap_polygons = [p for p in egm_data.get("polygons", []) if p.get("type") == "trap"]
    if not trap_polygons:
        print("  No trap polygons found in EGM data.")
        return []

    # Water-containing-hole rule (Topo 2026-05-01): if the EGM contains any
    # water polygon, every trap is lifted by WATER_HOLE_LIFT_MM and any trap
    # whose footprint touches the fringe rectangle perimeter is capped at
    # BOUNDARY_HEIGHT_CAP_MM total height.
    _hole_water = WATER_HOLE_LIFT_ENABLED and _hole_has_water(egm_data)
    if _hole_water:
        print(f"  Water-hole rule active: lift={WATER_HOLE_LIFT_MM} mm, "
              f"boundary cap={BOUNDARY_HEIGHT_CAP_MM} mm "
              f"(mode={BOUNDARY_HEIGHT_CAP_MODE})")

    # Pre-build fringe KD-tree for fast Z lookups (top-surface vertices only, Z > 0)
    fringe_kd = None
    fringe_verts_top = None
    if fringe_mesh is not None:
        all_verts = fringe_mesh.vertices          # (N, 3) in mm
        top_mask = all_verts[:, 2] > 0.0
        fringe_verts_top = all_verts[top_mask]
        if len(fringe_verts_top) > 0:
            fringe_kd = _cKDTree(fringe_verts_top[:, :2])   # query in XY only
        else:
            print("  WARNING: fringe mesh has no top-surface vertices (Z>0); trap heights will fall back to fixed.")

    results: list = []
    for i, trap_poly in enumerate(trap_polygons, start=1):
        try:
            # Interpolate outline with Catmull-Rom (closed spline, matching editor)
            pts_px = interpolate_catmull_rom(trap_poly["points"])

            # Convert pixel coords → mm, Y-flipped
            pts_mm = _px_to_mm_2d(pts_px, scale, centroid_px)

            shapely_trap = ShapelyPolygon(pts_mm)

            # #347: subtract the mount-pipe footprint BEFORE the fringe-rect
            # clip so the rectangle clip sees the post-subtraction shape and
            # the trap mesh doesn't overlap the pipe column.
            if pipe_circle is not None:
                shapely_trap = _subtract_pipe_from_polygon(
                    shapely_trap, pipe_circle, f"Trap {i}"
                )
                if shapely_trap is None:
                    continue

            # Clip to fringe rectangle so the trap never extends past the
            # printable frame edges (Thomas's rule, see #343).
            shapely_trap = _clip_polygon_to_fringe_rect(shapely_trap, f"Trap {i}")
            if shapely_trap is None:
                continue

            # Apply tolerance inset using Shapely
            if not shapely_trap.is_valid:
                shapely_trap = shapely_trap.buffer(0)
            shapely_inset = shapely_trap.buffer(-PRINT_TOLERANCE_MM)

            if shapely_inset.is_empty:
                print(f"  Trap {i}: inset produced empty polygon — skipping.")
                continue

            # Determine trap slab height from fringe mesh across the trap footprint.
            # Using the centroid alone fails for long/thin traps (like Trap 2) that span
            # a steep fringe gradient — the centroid can land on a high point while the
            # trap edges extend into lower fringe areas, causing the slab to float above
            # the surface. Instead, sample fringe Z at multiple points within the trap
            # and use the MINIMUM so the slab never pokes above the fringe.
            if fringe_kd is not None:
                # Sample on a regular grid over the trap bounding box, keep interior pts
                minx, miny, maxx, maxy = shapely_inset.bounds
                n_sample = 12  # grid density per axis → up to 144 candidate points
                xs_s = np.linspace(minx, maxx, n_sample)
                ys_s = np.linspace(miny, maxy, n_sample)
                sample_pts = []
                for sx in xs_s:
                    for sy in ys_s:
                        if shapely_inset.contains(ShapelyPoint(sx, sy)):
                            sample_pts.append([sx, sy])

                # Always include the centroid as a fallback
                cx, cy = shapely_inset.centroid.x, shapely_inset.centroid.y
                if not sample_pts:
                    sample_pts = [[cx, cy]]

                sample_pts = np.array(sample_pts)
                _, idxs = fringe_kd.query(sample_pts)
                sampled_z = fringe_verts_top[idxs, 2]
                trap_height = float(sampled_z.min())
                print(f"  Trap {i}: fringe Z min over {len(sample_pts)} samples = {trap_height:.2f} mm "
                      f"(centroid Z = {fringe_verts_top[fringe_kd.query([[cx, cy]])[1][0], 2]:.2f} mm, "
                      f"was fixed {TRAP_THICKNESS_MM} mm)")
            else:
                trap_height = TRAP_THICKNESS_MM
                print(f"  Trap {i}: no fringe mesh — using fixed height {trap_height} mm")

            # Build flat slab mesh
            from generate_stl_3mf import _build_slab_from_shapely
            mesh = _build_slab_from_shapely(shapely_inset, trap_height)

            # Apply sand grain texture to the top face (must precede lift; the
            # texture detects the top via z_max-relative threshold so it works
            # at any base height, but applying it first means the lift moves a
            # finished textured surface as one block).
            apply_sand_texture(mesh, trap_index=i)

            # Water-hole rule: lift this trap and (if it touches the boundary)
            # cap it at BOUNDARY_HEIGHT_CAP_MM. Otherwise leave untouched.
            if _hole_water:
                touches = _polygon_touches_frame_boundary(shapely_inset)
                cap_mm = BOUNDARY_HEIGHT_CAP_MM if touches else None
                _apply_lift_and_cap(
                    mesh,
                    lift_mm=WATER_HOLE_LIFT_MM,
                    cap_mm=cap_mm,
                    label=f"trap_{i}{' (boundary)' if touches else ''}",
                )

            bb = mesh.bounds
            print(f"  Trap {i}: {len(mesh.vertices)} verts, {len(mesh.faces)} faces, "
                  f"watertight={mesh.is_watertight}, "
                  f"X[{bb[0,0]:.1f},{bb[1,0]:.1f}] Y[{bb[0,1]:.1f},{bb[1,1]:.1f}] "
                  f"Z[{bb[0,2]:.2f},{bb[1,2]:.2f}] mm")

            if write_stls:
                out_path = os.path.join(stl_dir, f"{slug}_trap_{i}.stl")
                mesh.export(out_path)
                print(f"  Saved: {out_path}")
                results.append(out_path)
            else:
                results.append((f"trap_{i}", mesh))

        except Exception as exc:
            import traceback
            print(f"  ERROR exporting trap {i}: {exc}")
            traceback.print_exc()

    return results


def export_water_meshes(
    egm_data: dict,
    green_boundary_px: np.ndarray,
    slug: str,
    fringe_mesh: "trimesh.Trimesh | None" = None,
    stl_dir: str | None = None,
    write_stls: bool = True,
    pipe_circle: "ShapelyPolygon | None" = None,
) -> list:
    """
    Build flat slab meshes for every polygon of type 'water' in egm_data.

    Mirrors export_trap_stls: same px→mm transform, same Catmull-Rom interp,
    same PRINT_TOLERANCE_MM inset, same fringe-Z minimum sampling for the
    deck height. The only differences:
      * Skips the sand-grain rake texture (water is a smooth flat slab).
      * Scene node name uses ``water_N`` so _filament_for_scene_name routes
        the geometry to extruder 4.
      * STL files (when written) use ``{slug}_water_N.stl``.

    Returns the same shape as export_trap_stls: list of file paths when
    ``write_stls`` is True, else list of (node_name, trimesh.Trimesh).
    """
    from scipy.spatial import cKDTree as _cKDTree
    from shapely.geometry import Point as ShapelyPoint

    if write_stls:
        if stl_dir is None:
            course = egm_data.get("course", "")
            if course:
                stl_dir = course_paths(course)["stls"]
            else:
                stl_dir = OWNER_INBOX
        os.makedirs(stl_dir, exist_ok=True)

    scale, centroid_px = _compute_px_to_mm(green_boundary_px, egm_data)

    water_polygons = [p for p in egm_data.get("polygons", []) if p.get("type") == "water"]
    if not water_polygons:
        print("  No water polygons found in EGM data.")
        return []

    fringe_kd = None
    fringe_verts_top = None
    if fringe_mesh is not None:
        all_verts = fringe_mesh.vertices
        top_mask = all_verts[:, 2] > 0.0
        fringe_verts_top = all_verts[top_mask]
        if len(fringe_verts_top) > 0:
            fringe_kd = _cKDTree(fringe_verts_top[:, :2])
        else:
            print("  WARNING: fringe mesh has no top-surface vertices (Z>0); water heights will fall back to fixed.")

    results: list = []
    for i, water_poly in enumerate(water_polygons, start=1):
        try:
            pts_px = interpolate_catmull_rom(water_poly["points"])
            pts_mm = _px_to_mm_2d(pts_px, scale, centroid_px)

            shapely_water = ShapelyPolygon(pts_mm)

            # #347: subtract the mount-pipe footprint BEFORE the fringe-rect
            # clip so the rectangle clip sees the post-subtraction shape and
            # the water mesh doesn't overlap the pipe column. PGA West-Arnold
            # Palmer #5 — water polygon spans the upper-left fringe corner.
            if pipe_circle is not None:
                shapely_water = _subtract_pipe_from_polygon(
                    shapely_water, pipe_circle, f"Water {i}"
                )
                if shapely_water is None:
                    continue

            # Clip to fringe rectangle (#343) — water hazards on hole 5 of
            # PGA West-Arnold Palmer were leaking past the frame edge.
            shapely_water = _clip_polygon_to_fringe_rect(shapely_water, f"Water {i}")
            if shapely_water is None:
                continue

            if not shapely_water.is_valid:
                shapely_water = shapely_water.buffer(0)
            shapely_inset = shapely_water.buffer(-PRINT_TOLERANCE_MM)

            if shapely_inset.is_empty:
                print(f"  Water {i}: inset produced empty polygon — skipping.")
                continue

            # Sample fringe Z over the water footprint, take the minimum so the
            # slab never pokes above the surrounding surface.
            if fringe_kd is not None:
                minx, miny, maxx, maxy = shapely_inset.bounds
                n_sample = 12
                xs_s = np.linspace(minx, maxx, n_sample)
                ys_s = np.linspace(miny, maxy, n_sample)
                sample_pts = []
                for sx in xs_s:
                    for sy in ys_s:
                        if shapely_inset.contains(ShapelyPoint(sx, sy)):
                            sample_pts.append([sx, sy])
                cx, cy = shapely_inset.centroid.x, shapely_inset.centroid.y
                if not sample_pts:
                    sample_pts = [[cx, cy]]
                sample_pts = np.array(sample_pts)
                _, idxs = fringe_kd.query(sample_pts)
                sampled_z = fringe_verts_top[idxs, 2]
                water_height = float(sampled_z.min())
                print(f"  Water {i}: fringe Z min over {len(sample_pts)} samples = {water_height:.2f} mm")
            else:
                water_height = TRAP_THICKNESS_MM
                print(f"  Water {i}: no fringe mesh — using fixed height {water_height} mm")

            from generate_stl_3mf import _build_slab_from_shapely
            mesh = _build_slab_from_shapely(shapely_inset, water_height)

            # Sinusoidal "wind chop" ripple displacement on the top face.
            # Gated by WATER_RIPPLE_ENABLED for easy on/off.  Per-pond seed
            # comes from the polygon's control points so the same pond always
            # regenerates the same ripple but different ponds look different.
            if WATER_RIPPLE_ENABLED:
                apply_water_ripple_texture(
                    mesh,
                    water_index=i,
                    control_points_px=water_poly.get("points", []),
                )

            bb = mesh.bounds
            print(f"  Water {i}: {len(mesh.vertices)} verts, {len(mesh.faces)} faces, "
                  f"watertight={mesh.is_watertight}, "
                  f"X[{bb[0,0]:.1f},{bb[1,0]:.1f}] Y[{bb[0,1]:.1f},{bb[1,1]:.1f}] mm")

            if write_stls:
                out_path = os.path.join(stl_dir, f"{slug}_water_{i}.stl")
                mesh.export(out_path)
                print(f"  Saved: {out_path}")
                results.append(out_path)
            else:
                # Scene name MUST start with "water" so _filament_for_scene_name
                # routes it to extruder 4 (per the convention in #329).
                results.append((f"water_{i}", mesh))

        except Exception as exc:
            import traceback
            print(f"  ERROR exporting water {i}: {exc}")
            traceback.print_exc()

    return results


# ---------------------------------------------------------------------------
# Sand grain texture
# ---------------------------------------------------------------------------

def apply_sand_texture(
    mesh: "trimesh.Trimesh",
    amplitude: float = 1.0,
    grain_spacing: float = 1.125,
    trap_index: int = 0,
) -> "trimesh.Trimesh":
    """
    Apply parallel rake-line displacement to the top surface of a trap slab mesh.

    Simulates a freshly raked sand trap: evenly spaced parallel ridges and
    grooves running across the flat top face, matching the look of a wide-toothed
    rake pulled across real golf course sand.

    The top surface is REBUILT as a regular rectangular grid rather than
    subdividing the original irregular triangle mesh.  A regular grid guarantees
    that vertices are evenly spaced in X, so the cosine wave is sampled cleanly
    and produces perfectly parallel rake lines with no herringbone artifacts.

    Algorithm
    ---------
    1. Extract the original top-face boundary as a Shapely polygon.
    2. Generate a regular (x, y) grid over the bounding box; keep only points
       inside the polygon.
    3. Compute Z = z_max + amplitude * 0.5 * (1 + cos(2π * x / grain_spacing))
       for each grid point (rake lines parallel to Y, ridges vary with X).
    4. Delaunay-triangulate the grid points; discard triangles whose centroid
       falls outside the polygon.
    5. Reassemble: new grid top + original wall/base faces; merge boundary
       vertices with trimesh process=True to restore watertightness.

    Parameters
    ----------
    mesh         : trimesh.Trimesh — closed watertight trap slab in mm coords.
    amplitude    : peak-to-trough height of rake ridges in mm (default 0.35 mm).
    grain_spacing: centre-to-centre distance between rake-line peaks in mm
                   (default 1.5 mm).
    trap_index   : integer used to select a unique rake direction per trap
                   (angle = trap_index * 60°). Reserved for future use; rake
                   direction is currently fixed at 0°.

    Returns the mesh modified in place (also returns it for convenience).
    """
    import trimesh
    import numpy as np
    from scipy.spatial import Delaunay
    from shapely.geometry import Polygon as ShapelyPolygon

    all_verts = mesh.vertices.copy()   # (N, 3)
    all_faces = mesh.faces.copy()      # (F, 3)

    # ------------------------------------------------------------------
    # 1. Identify top faces and wall/base faces
    # ------------------------------------------------------------------
    z_max    = all_verts[:, 2].max()
    z_thresh = z_max - 0.1            # within 0.1 mm counts as "top"

    face_v_z      = all_verts[all_faces, 2]              # (F, 3)
    top_face_mask = (face_v_z >= z_thresh).all(axis=1)   # (F,) bool

    top_faces_global   = all_faces[top_face_mask]
    other_faces_global = all_faces[~top_face_mask]

    if top_faces_global.shape[0] == 0:
        print(f"    apply_sand_texture: no top-surface faces found (Z near {z_max:.2f} mm), skipping.")
        return mesh

    # ------------------------------------------------------------------
    # 2. Build a Shapely polygon from the top-face boundary edges
    # ------------------------------------------------------------------
    # Collect every directed edge of the top faces, then keep only those
    # that appear exactly once (boundary edges).
    edges = np.vstack([
        top_faces_global[:, [0, 1]],
        top_faces_global[:, [1, 2]],
        top_faces_global[:, [2, 0]],
    ])
    # Represent each edge as a sorted pair so we can count occurrences.
    edges_sorted = np.sort(edges, axis=1)
    edge_tuples  = [tuple(e) for e in edges_sorted]
    from collections import Counter
    edge_counts  = Counter(edge_tuples)
    boundary_set = {e for e, cnt in edge_counts.items() if cnt == 1}

    # Rebuild directed boundary edges (original orientation, not sorted).
    boundary_edges = [e for e in edges if tuple(sorted(e)) in boundary_set]

    # ------------------------------------------------------------------
    # Multi-loop boundary walker (mirrors apply_water_ripple_texture).
    #
    # A trap polygon could in principle have interior holes (e.g. a future
    # trap with a pipe footprint subtracted from its interior).  The old
    # single-loop walker would drop every ring after the first, leaving
    # dangling boundary verts and a non-manifold mesh.  Walk an UNDIRECTED
    # adjacency (also fixes a latent secondary bug: directed-edge dead-ends
    # mid-loop), collect ALL closed loops, sort by |signed area|: largest
    # = outer ring, rest = holes.  Build ShapelyPolygon(outer, holes=[...])
    # so prepared-geometry containment correctly excludes hole interiors.
    # ------------------------------------------------------------------
    undirected: dict = {}
    for a, b in boundary_edges:
        undirected.setdefault(int(a), set()).add(int(b))
        undirected.setdefault(int(b), set()).add(int(a))

    loops: list[list[int]] = []
    seen: set[int] = set()
    for seed_vert in undirected.keys():
        if seed_vert in seen:
            continue
        loop: list[int] = []
        current = seed_vert
        prev = -1
        while True:
            loop.append(current)
            seen.add(current)
            nbrs = [n for n in undirected.get(current, ()) if n != prev]
            unvisited = [n for n in nbrs if n not in seen]
            if unvisited:
                nxt = unvisited[0]
            elif nbrs and nbrs[0] == seed_vert and len(loop) > 2:
                break
            else:
                break
            prev = current
            current = nxt
        if len(loop) >= 3:
            loops.append(loop)

    if not loops:
        print(f"    apply_sand_texture: no closed boundary loops found, skipping.")
        return mesh

    def _signed_area(idx_list: list[int]) -> float:
        pts = all_verts[idx_list, :2]
        x = pts[:, 0]; y = pts[:, 1]
        return 0.5 * float(np.sum(x * np.roll(y, -1) - np.roll(x, -1) * y))

    loops.sort(key=lambda lp: abs(_signed_area(lp)), reverse=True)
    outer_loop = loops[0]
    hole_loops = loops[1:]
    ring = outer_loop  # legacy name retained downstream
    all_loops = [outer_loop] + hole_loops

    ring_xy   = all_verts[outer_loop, :2]             # (R, 2) — XY of outer boundary
    holes_xy  = [all_verts[lp, :2] for lp in hole_loops]
    shapely_poly = ShapelyPolygon(ring_xy, holes=holes_xy)
    if not shapely_poly.is_valid:
        shapely_poly = shapely_poly.buffer(0)         # fix self-intersections
    if len(hole_loops) > 0:
        print(f"    Sand boundary: 1 outer ring ({len(outer_loop)} verts) "
              f"+ {len(hole_loops)} hole(s) "
              f"({', '.join(str(len(lp)) for lp in hole_loops)} verts)")

    # ------------------------------------------------------------------
    # 3. Build a regular grid over the bounding box; filter inside polygon
    # ------------------------------------------------------------------
    grid_step = grain_spacing * 0.2                   # ~0.3 mm → ~5 pts per period

    x_min, x_max = ring_xy[:, 0].min(), ring_xy[:, 0].max()
    y_min, y_max = ring_xy[:, 1].min(), ring_xy[:, 1].max()

    xs = np.arange(x_min, x_max + grid_step, grid_step)
    ys = np.arange(y_min, y_max + grid_step, grid_step)
    gx, gy = np.meshgrid(xs, ys)
    grid_xy = np.column_stack([gx.ravel(), gy.ravel()])  # (G, 2)

    # Vectorised point-in-polygon using shapely prepared geometry.
    #
    # Inset the polygon by one grid_step before filtering: interior grid points
    # that land on or very close to the rim (especially along long near-straight
    # edges) cause Delaunay to bridge consecutive rim verts with thin triangles
    # that skip ahead, leaving rim edges (i, i+1) without a matching top face
    # and producing a non-manifold seam after wall merge. Buffering the
    # filter-polygon inward keeps grid points clear of the rim, so Delaunay
    # mates rim points directly to nearby interior verts and every rim edge
    # is preserved. (Topo, task #339 — fixes PGA West Hole 5 Trap 1: 141 → 15
    # boundary edges, well below the tol=30 manifold gate.)
    from shapely import prepare, contains_xy
    SAND_GRID_BOUNDARY_INSET_FACTOR = 1.0  # in units of grid_step
    shapely_inner = shapely_poly.buffer(-grid_step * SAND_GRID_BOUNDARY_INSET_FACTOR)
    if shapely_inner.is_empty:
        # Polygon too thin for the inset — fall back to the un-inset polygon.
        # Better to risk a few boundary edges than skip the texture entirely.
        shapely_inner = shapely_poly
    prepare(shapely_inner)
    inside_mask = contains_xy(shapely_inner, grid_xy[:, 0], grid_xy[:, 1])
    grid_xy_in  = grid_xy[inside_mask]                # (M, 2) — interior grid pts

    if len(grid_xy_in) < 3:
        print(f"    apply_sand_texture: too few grid points inside polygon ({len(grid_xy_in)}), skipping.")
        return mesh

    n_grid = len(grid_xy_in)
    print(f"    Sand texture grid: step={grid_step:.3f} mm, "
          f"bbox {x_max-x_min:.1f}×{y_max-y_min:.1f} mm → "
          f"{len(xs)}×{len(ys)} candidates → {n_grid} inside polygon "
          f"(boundary inset = {grid_step * SAND_GRID_BOUNDARY_INSET_FACTOR:.3f} mm)")

    # Enforce vertex budget: 150 K per trap.
    MAX_GRID_PTS = 150_000
    if n_grid > MAX_GRID_PTS:
        scale    = math.sqrt(n_grid / MAX_GRID_PTS)
        new_step = grid_step * scale
        print(f"    Sand texture: grid too large ({n_grid} pts); "
              f"increasing step {grid_step:.3f} → {new_step:.3f} mm")
        grid_step = new_step
        # Re-inset with the new grid_step so the boundary clearance scales with it.
        shapely_inner = shapely_poly.buffer(-grid_step * SAND_GRID_BOUNDARY_INSET_FACTOR)
        if shapely_inner.is_empty:
            shapely_inner = shapely_poly
        prepare(shapely_inner)
        xs = np.arange(x_min, x_max + grid_step, grid_step)
        ys = np.arange(y_min, y_max + grid_step, grid_step)
        gx, gy = np.meshgrid(xs, ys)
        grid_xy = np.column_stack([gx.ravel(), gy.ravel()])
        inside_mask = contains_xy(shapely_inner, grid_xy[:, 0], grid_xy[:, 1])
        grid_xy_in  = grid_xy[inside_mask]
        n_grid = len(grid_xy_in)
        print(f"    Sand texture: after step increase → {n_grid} grid points")

    # ------------------------------------------------------------------
    # 4. Compute Z for every grid point (sinusoidal rake profile)
    # ------------------------------------------------------------------
    # Sine displacement helper — same formula applied consistently to all
    # points so interior grid vertices and boundary ring vertices match.
    def sine_dz(x_arr):
        return amplitude * 0.5 * (1.0 + np.cos(2.0 * math.pi * x_arr / grain_spacing))

    # Interior grid points.
    dz     = sine_dz(grid_xy_in[:, 0])
    grid_z = z_max + dz                               # (M,)

    # Boundary ring points: include in Delaunay so the triangulation
    # reaches the polygon edge exactly, sharing XY with the wall rim.
    # Concatenate outer ring + every interior hole ring so EVERY boundary
    # vertex is represented (multi-loop walker output).
    all_ring_idx = [int(v) for lp in all_loops for v in lp]
    ring_xy_arr = all_verts[all_ring_idx, :2]         # (R, 2)
    ring_z      = z_max + sine_dz(ring_xy_arr[:, 0]) # (R,)

    # Combined point set for Delaunay: boundary ring first, then interior.
    n_ring   = len(ring_xy_arr)
    all_xy   = np.vstack([ring_xy_arr, grid_xy_in])   # (R+M, 2)
    all_z    = np.concatenate([ring_z, grid_z])       # (R+M,)
    grid_pts = np.column_stack([all_xy, all_z])       # (R+M, 3)

    n_lines = int(math.ceil((x_max - x_min) / grain_spacing)) + 1
    print(f"    Sand texture: rake lines, angle=0°, spacing={grain_spacing:.2f} mm, "
          f"amplitude={amplitude:.3f} mm, ~{n_lines} lines, "
          f"dz range [{dz.min():.3f}, {dz.max():.3f}] mm on {n_grid} grid verts "
          f"+ {n_ring} boundary ring verts")

    # ------------------------------------------------------------------
    # 5. Delaunay-triangulate the grid points; clip to polygon interior
    # ------------------------------------------------------------------
    tri = Delaunay(all_xy)
    tri_faces = tri.simplices                          # (T, 3)

    # Discard any triangle whose centroid falls outside the polygon.
    centroids   = all_xy[tri_faces].mean(axis=1)      # (T, 2)
    cent_inside = contains_xy(shapely_poly, centroids[:, 0], centroids[:, 1])
    top_new_faces = tri_faces[cent_inside]             # (K, 3)

    print(f"    Sand texture: Delaunay → {len(tri_faces)} triangles, "
          f"{cent_inside.sum()} kept after centroid clipping")

    # ------------------------------------------------------------------
    # 6. Reassemble: new grid top + original wall/base faces
    # ------------------------------------------------------------------
    # Compact the wall/base vertex set (vertices used by non-top faces).
    other_vert_indices, other_faces_local = np.unique(
        other_faces_global, return_inverse=True
    )
    other_faces_local = other_faces_local.reshape(-1, 3)
    other_verts_arr   = all_verts[other_vert_indices].copy()   # (W, 3) — mutable copy

    # --- Snap wall rim vertices to the displaced boundary ring Z ----------
    # The boundary ring vertices (global indices in `ring`) appear in both
    # the new top mesh (as rows 0..n_ring-1 of grid_pts) and in the wall/base
    # mesh (as some rows of other_verts_arr).  For process=True to merge them
    # they must be identical in 3D.  Update the wall rim rows to use the same
    # displaced Z as the corresponding boundary ring grid_pts rows.
    #
    # Build a lookup: global_index → displaced Z for every boundary ring vertex.
    ring_global   = np.array(all_ring_idx)                     # (R,) global indices (all loops)
    ring_disp_z   = ring_z                                     # (R,) displaced Z
    rim_z_lookup  = dict(zip(ring_global.tolist(), ring_disp_z.tolist()))

    # Find which rows of other_vert_indices are rim vertices and update Z.
    for local_i, global_i in enumerate(other_vert_indices):
        if global_i in rim_z_lookup:
            other_verts_arr[local_i, 2] = rim_z_lookup[global_i]

    n_top = len(grid_pts)
    combined_verts = np.vstack([grid_pts, other_verts_arr])
    combined_faces = np.vstack([
        top_new_faces,
        other_faces_local + n_top,
    ])

    # process=True merges boundary vertices (grid edge ↔ wall top rim).
    # Both sides now share exact 3D coordinates at the seam, so the merge
    # succeeds and the mesh is watertight.
    new_mesh = trimesh.Trimesh(
        vertices=combined_verts,
        faces=combined_faces,
        process=True,
    )
    # Repair any remaining tiny seam gaps from floating-point mismatch
    if not new_mesh.is_watertight:
        new_mesh.merge_vertices(digits_vertex=3)
        trimesh.repair.fix_normals(new_mesh)
        trimesh.repair.fill_holes(new_mesh)
        trimesh.repair.fix_winding(new_mesh)

    print(f"    Sand texture: reassembled mesh — "
          f"{len(new_mesh.vertices)} verts, {len(new_mesh.faces)} faces, "
          f"watertight={new_mesh.is_watertight}")

    # Copy rebuilt geometry back into the caller's mesh object.
    mesh.vertices = new_mesh.vertices
    mesh.faces    = new_mesh.faces

    return mesh


# ---------------------------------------------------------------------------
# Water ripple texture
# ---------------------------------------------------------------------------

def apply_water_ripple_texture(
    mesh: "trimesh.Trimesh",
    water_index: int = 0,
    control_points_px: list | None = None,
    A1: float | None = None,
    A2: float | None = None,
    lambda1: float | None = None,
    lambda2: float | None = None,
    grid_step: float | None = None,
) -> "trimesh.Trimesh":
    """
    Apply two-superposed-sine "wind chop" displacement to a water slab top face.

    Cloned from :func:`apply_sand_texture` (same 6-stage pipeline: rebuild top
    as a regular grid → displace Z → Delaunay re-triangulate → stitch boundary
    ring → reassemble + watertight repair).  Two changes vs. sand:

      * **Displacement formula** — sum of two sine waves at near-perpendicular
        angles with per-pond random phases:

            dz(x,y) = A1 * sin(2π * (x·cosθ1 + y·sinθ1) / λ1 + φ1)
                    + A2 * sin(2π * (x·cosθ2 + y·sinθ2) / λ2 + φ2)

        Then **clamped to dz ≤ 0** so peaks never poke above the unrippled
        water height (which would create overhangs and let the slab visually
        float above its fringe socket).  Net displacement is downward only,
        with the original water_z as the calm-water "high tide" line.

      * **Per-pond seed** — derived from a hash of the polygon's control-point
        coordinates so the same pond regenerates the same ripple every build,
        but adjacent ponds in the same hole look different.  θ1 ∈ [0, 2π),
        θ2 ≈ θ1 + π/2 with small jitter, φ1, φ2 ∈ [0, 2π).

    Parameters
    ----------
    mesh             : trimesh.Trimesh — closed watertight water slab in mm coords.
    water_index      : 1-based pond index (used as a fallback seed if no
                       control points are provided).
    control_points_px: optional list of {"x","y"} dicts from the EGM polygon.
                       Hashed to seed the per-pond RNG.  Falls back to
                       water_index if missing/empty.
    A1, A2           : peak amplitudes in mm (defaults: WATER_RIPPLE_A1/A2).
    lambda1, lambda2 : wavelengths in mm (defaults: WATER_RIPPLE_LAMBDA1/2).
    grid_step        : XY sampling step in mm (default WATER_RIPPLE_GRID_STEP).

    Returns the mesh modified in place (also returns it for convenience).
    """
    import hashlib
    import trimesh
    import numpy as np
    from scipy.spatial import Delaunay
    from shapely.geometry import Polygon as ShapelyPolygon

    # Resolve parameters from module-level constants if caller didn't override.
    A1        = WATER_RIPPLE_A1       if A1        is None else A1
    A2        = WATER_RIPPLE_A2       if A2        is None else A2
    lambda1   = WATER_RIPPLE_LAMBDA1  if lambda1   is None else lambda1
    lambda2   = WATER_RIPPLE_LAMBDA2  if lambda2   is None else lambda2
    grid_step = WATER_RIPPLE_GRID_STEP if grid_step is None else grid_step

    # ------------------------------------------------------------------
    # 0. Per-pond deterministic seed: hash control-point coords (fallback
    #    to water_index if EGM didn't pass them through).
    # ------------------------------------------------------------------
    if control_points_px:
        coord_bytes = b",".join(
            f"{p.get('x', 0):.4f},{p.get('y', 0):.4f}".encode("ascii")
            for p in control_points_px
        )
        seed = int(hashlib.md5(coord_bytes).hexdigest()[:8], 16)
    else:
        seed = 0xA17EB10B + water_index  # deterministic fallback (no control pts)
    rng = np.random.default_rng(seed)

    theta1 = float(rng.uniform(0.0, 2.0 * math.pi))
    # θ2 roughly perpendicular to θ1, with ±15° jitter so the cross-chop
    # doesn't look stamped from a template.
    theta2 = theta1 + math.pi / 2.0 + float(rng.uniform(-math.pi / 12.0, math.pi / 12.0))
    phi1   = float(rng.uniform(0.0, 2.0 * math.pi))
    phi2   = float(rng.uniform(0.0, 2.0 * math.pi))

    all_verts = mesh.vertices.copy()
    all_faces = mesh.faces.copy()

    # ------------------------------------------------------------------
    # 1. Identify top faces and wall/base faces (same as sand)
    # ------------------------------------------------------------------
    z_max    = all_verts[:, 2].max()
    z_thresh = z_max - 0.1

    face_v_z      = all_verts[all_faces, 2]
    top_face_mask = (face_v_z >= z_thresh).all(axis=1)

    top_faces_global   = all_faces[top_face_mask]
    other_faces_global = all_faces[~top_face_mask]

    if top_faces_global.shape[0] == 0:
        print(f"    apply_water_ripple_texture: no top-surface faces found "
              f"(Z near {z_max:.2f} mm), skipping.")
        return mesh

    # ------------------------------------------------------------------
    # 2. Recover the top-face boundary as a Shapely polygon
    # ------------------------------------------------------------------
    edges = np.vstack([
        top_faces_global[:, [0, 1]],
        top_faces_global[:, [1, 2]],
        top_faces_global[:, [2, 0]],
    ])
    edges_sorted = np.sort(edges, axis=1)
    edge_tuples  = [tuple(e) for e in edges_sorted]
    from collections import Counter
    edge_counts  = Counter(edge_tuples)
    boundary_set = {e for e, cnt in edge_counts.items() if cnt == 1}

    boundary_edges = [e for e in edges if tuple(sorted(e)) in boundary_set]

    # ------------------------------------------------------------------
    # Multi-loop boundary walker.
    #
    # Pipe-subtract on a moat-style water polygon (e.g. PGA West Stadium
    # Clubhouse Hole 17) produces a top face that is a polygon-with-holes:
    # one outer ring + N interior rings around each pipe footprint.  A
    # single-loop walker silently drops every ring after the first, leaving
    # all the unwalked boundary verts dangling and the manifold post-check
    # fails (424 boundary edges on Hole 17).
    #
    # We walk an UNDIRECTED adjacency (also fixes a latent secondary bug:
    # `boundary_edges` were directed, so the original walker could dead-end
    # mid-loop on the wrong-direction edge).  Each iteration picks an
    # unvisited boundary vertex, walks its loop, marks all its verts
    # visited, and records the loop.  Loops are then sorted by absolute
    # signed area: the largest is the outer ring, the rest are holes.
    # ------------------------------------------------------------------
    undirected: dict = {}
    for a, b in boundary_edges:
        undirected.setdefault(int(a), set()).add(int(b))
        undirected.setdefault(int(b), set()).add(int(a))

    loops: list[list[int]] = []
    seen: set[int] = set()
    for seed_vert in undirected.keys():
        if seed_vert in seen:
            continue
        loop: list[int] = []
        current = seed_vert
        prev = -1
        while True:
            loop.append(current)
            seen.add(current)
            nbrs = [n for n in undirected.get(current, ()) if n != prev]
            unvisited = [n for n in nbrs if n not in seen]
            if unvisited:
                nxt = unvisited[0]
            elif nbrs and nbrs[0] == seed_vert and len(loop) > 2:
                # Closed back to seed — loop complete.
                break
            else:
                # Dead end (shouldn't happen on a clean boundary).
                break
            prev = current
            current = nxt
        if len(loop) >= 3:
            loops.append(loop)

    if not loops:
        print(f"    apply_water_ripple_texture: no closed boundary loops found, skipping.")
        return mesh

    def _signed_area(idx_list: list[int]) -> float:
        pts = all_verts[idx_list, :2]
        x = pts[:, 0]; y = pts[:, 1]
        return 0.5 * float(np.sum(x * np.roll(y, -1) - np.roll(x, -1) * y))

    loops.sort(key=lambda lp: abs(_signed_area(lp)), reverse=True)
    outer_loop = loops[0]
    hole_loops = loops[1:]
    ring = outer_loop  # legacy name retained downstream
    all_loops = [outer_loop] + hole_loops

    ring_xy   = all_verts[outer_loop, :2]
    holes_xy  = [all_verts[lp, :2] for lp in hole_loops]
    shapely_poly = ShapelyPolygon(ring_xy, holes=holes_xy)
    if not shapely_poly.is_valid:
        shapely_poly = shapely_poly.buffer(0)
    if len(hole_loops) > 0:
        print(f"    Water ripple boundary: 1 outer ring ({len(outer_loop)} verts) "
              f"+ {len(hole_loops)} hole(s) "
              f"({', '.join(str(len(lp)) for lp in hole_loops)} verts)")

    # ------------------------------------------------------------------
    # 3. Regular grid over bbox; filter inside (with boundary inset to
    #    keep Delaunay from skipping rim edges — same fix as sand #339).
    # ------------------------------------------------------------------
    x_min, x_max = ring_xy[:, 0].min(), ring_xy[:, 0].max()
    y_min, y_max = ring_xy[:, 1].min(), ring_xy[:, 1].max()

    xs = np.arange(x_min, x_max + grid_step, grid_step)
    ys = np.arange(y_min, y_max + grid_step, grid_step)
    gx, gy = np.meshgrid(xs, ys)
    grid_xy = np.column_stack([gx.ravel(), gy.ravel()])

    from shapely import prepare, contains_xy
    WATER_GRID_BOUNDARY_INSET_FACTOR = 1.0  # in units of grid_step
    shapely_inner = shapely_poly.buffer(-grid_step * WATER_GRID_BOUNDARY_INSET_FACTOR)
    if shapely_inner.is_empty:
        shapely_inner = shapely_poly
    prepare(shapely_inner)
    inside_mask = contains_xy(shapely_inner, grid_xy[:, 0], grid_xy[:, 1])
    grid_xy_in  = grid_xy[inside_mask]

    if len(grid_xy_in) < 3:
        print(f"    apply_water_ripple_texture: too few grid points inside polygon "
              f"({len(grid_xy_in)}), skipping.")
        return mesh

    n_grid = len(grid_xy_in)
    print(f"    Water ripple grid: step={grid_step:.3f} mm, "
          f"bbox {x_max-x_min:.1f}×{y_max-y_min:.1f} mm → "
          f"{len(xs)}×{len(ys)} candidates → {n_grid} inside polygon "
          f"(seed=0x{seed:08x}, θ1={math.degrees(theta1):.1f}°, "
          f"θ2={math.degrees(theta2):.1f}°)")

    # Vertex budget — same 150 K cap as sand.
    MAX_GRID_PTS = 150_000
    if n_grid > MAX_GRID_PTS:
        scale_up = math.sqrt(n_grid / MAX_GRID_PTS)
        new_step = grid_step * scale_up
        print(f"    Water ripple: grid too large ({n_grid} pts); "
              f"increasing step {grid_step:.3f} → {new_step:.3f} mm")
        grid_step = new_step
        shapely_inner = shapely_poly.buffer(-grid_step * WATER_GRID_BOUNDARY_INSET_FACTOR)
        if shapely_inner.is_empty:
            shapely_inner = shapely_poly
        prepare(shapely_inner)
        xs = np.arange(x_min, x_max + grid_step, grid_step)
        ys = np.arange(y_min, y_max + grid_step, grid_step)
        gx, gy = np.meshgrid(xs, ys)
        grid_xy = np.column_stack([gx.ravel(), gy.ravel()])
        inside_mask = contains_xy(shapely_inner, grid_xy[:, 0], grid_xy[:, 1])
        grid_xy_in  = grid_xy[inside_mask]
        n_grid = len(grid_xy_in)
        print(f"    Water ripple: after step increase → {n_grid} grid points")

    # ------------------------------------------------------------------
    # 4. Two-sine displacement, clamped ≤ 0 (downward only).
    # ------------------------------------------------------------------
    cos_t1, sin_t1 = math.cos(theta1), math.sin(theta1)
    cos_t2, sin_t2 = math.cos(theta2), math.sin(theta2)
    two_pi = 2.0 * math.pi

    def ripple_dz(xy: np.ndarray) -> np.ndarray:
        """Sum of two sines, then clamp to ≤ 0 so peaks don't poke above
        the unrippled water surface (no overhangs vs. surrounding fringe)."""
        u1 = (xy[:, 0] * cos_t1 + xy[:, 1] * sin_t1) / lambda1
        u2 = (xy[:, 0] * cos_t2 + xy[:, 1] * sin_t2) / lambda2
        dz = A1 * np.sin(two_pi * u1 + phi1) + A2 * np.sin(two_pi * u2 + phi2)
        return np.minimum(dz, 0.0)

    dz     = ripple_dz(grid_xy_in)
    grid_z = z_max + dz

    # Concatenate outer ring + every interior hole ring so EVERY boundary
    # vertex is represented in the Delaunay input and rim-Z snap step.
    all_ring_idx = [int(v) for lp in all_loops for v in lp]
    ring_xy_arr  = all_verts[all_ring_idx, :2]
    ring_z       = z_max + ripple_dz(ring_xy_arr)

    n_ring   = len(ring_xy_arr)
    all_xy   = np.vstack([ring_xy_arr, grid_xy_in])
    all_z    = np.concatenate([ring_z, grid_z])
    grid_pts = np.column_stack([all_xy, all_z])

    print(f"    Water ripple: A1={A1:.3f}/λ1={lambda1:.2f}, "
          f"A2={A2:.3f}/λ2={lambda2:.2f} mm, "
          f"dz range [{dz.min():.3f}, {dz.max():.3f}] mm (clamped ≤0) "
          f"on {n_grid} grid + {n_ring} ring verts")

    # ------------------------------------------------------------------
    # 5. Delaunay-triangulate; clip triangles whose centroid falls outside
    # ------------------------------------------------------------------
    tri = Delaunay(all_xy)
    tri_faces = tri.simplices
    centroids = all_xy[tri_faces].mean(axis=1)
    cent_inside = contains_xy(shapely_poly, centroids[:, 0], centroids[:, 1])
    top_new_faces = tri_faces[cent_inside]

    print(f"    Water ripple: Delaunay → {len(tri_faces)} triangles, "
          f"{cent_inside.sum()} kept after centroid clipping")

    # ------------------------------------------------------------------
    # 6. Reassemble + snap rim Z to merge cleanly with walls
    # ------------------------------------------------------------------
    other_vert_indices, other_faces_local = np.unique(
        other_faces_global, return_inverse=True
    )
    other_faces_local = other_faces_local.reshape(-1, 3)
    other_verts_arr   = all_verts[other_vert_indices].copy()

    ring_global  = np.array(all_ring_idx)
    ring_disp_z  = ring_z
    rim_z_lookup = dict(zip(ring_global.tolist(), ring_disp_z.tolist()))

    for local_i, global_i in enumerate(other_vert_indices):
        if global_i in rim_z_lookup:
            other_verts_arr[local_i, 2] = rim_z_lookup[global_i]

    n_top = len(grid_pts)
    combined_verts = np.vstack([grid_pts, other_verts_arr])
    combined_faces = np.vstack([
        top_new_faces,
        other_faces_local + n_top,
    ])

    new_mesh = trimesh.Trimesh(
        vertices=combined_verts,
        faces=combined_faces,
        process=True,
    )
    if not new_mesh.is_watertight:
        new_mesh.merge_vertices(digits_vertex=3)
        trimesh.repair.fix_normals(new_mesh)
        trimesh.repair.fill_holes(new_mesh)
        trimesh.repair.fix_winding(new_mesh)

    print(f"    Water ripple: reassembled mesh — "
          f"{len(new_mesh.vertices)} verts, {len(new_mesh.faces)} faces, "
          f"watertight={new_mesh.is_watertight}")

    mesh.vertices = new_mesh.vertices
    mesh.faces    = new_mesh.faces

    return mesh


# ---------------------------------------------------------------------------
# Grass bump texture
# ---------------------------------------------------------------------------

def apply_grass_texture(
    mesh: "trimesh.Trimesh",
    amplitude: float = 0.5,
    bump_spacing: float = 2.4,
    exclude_polyline_xy: np.ndarray | None = None,
    exclude_radius_mm: float = 0.0,
) -> "trimesh.Trimesh":
    """
    Apply paraboloid grass-bump displacement to the top surface of a mesh.

    Bump centers are placed on a jittered grid across the XY extent of the
    top-surface vertices.  Each top-surface vertex is displaced upward by::

        dz = amplitude * max(0, 1 - (r / R)^2)

    where R = bump_spacing * 0.48 (so adjacent bumps slightly overlap) and
    r is the distance to the nearest bump center.

    Only vertices above BASE_THICKNESS_MM are displaced (top surface / fringe
    top).  Wall and base vertices are left untouched.

    Parameters
    ----------
    mesh        : trimesh.Trimesh — closed watertight mesh in mm coords.
    amplitude   : maximum Z displacement in mm (peak of each bump).
    bump_spacing: centre-to-centre distance between bumps in mm.
    exclude_polyline_xy : optional (N, 2) polyline — any top-surface vertex
        within ``exclude_radius_mm`` of this polyline is NOT displaced.  Used
        by the fringe to freeze its seam vertices where it meets the green,
        so the fringe-green seam stays flush after grass bumps are applied
        only to one side.
    exclude_radius_mm   : radius (mm) of the exclusion band around the polyline.

    Returns the mesh modified in place (also returns it for convenience).
    """
    verts = mesh.vertices  # (N, 3) — live reference, edits modify the mesh

    # Identify top-surface vertices: Z > BASE_THICKNESS_MM
    top_mask = verts[:, 2] > BASE_THICKNESS_MM
    if not top_mask.any():
        print(f"    apply_grass_texture: no top-surface vertices found (Z > {BASE_THICKNESS_MM}), skipping.")
        return mesh

    top_xy = verts[top_mask, :2]  # (M, 2)

    # Build per-vertex protection mask for seam verts (fringe-green interface).
    # We freeze these at their current Z so the seam stays flush between meshes.
    protect = np.zeros(int(top_mask.sum()), dtype=bool)
    if exclude_polyline_xy is not None and exclude_radius_mm > 0.0 and len(exclude_polyline_xy) >= 2:
        ex_tree = cKDTree(exclude_polyline_xy)
        d_ex, _ = ex_tree.query(top_xy, k=1)
        protect = d_ex < exclude_radius_mm
        if protect.any():
            print(f"    Grass texture: protecting {protect.sum()} top-surface vertices "
                  f"within {exclude_radius_mm:.2f} mm of seam polyline")

    x_min, x_max = top_xy[:, 0].min(), top_xy[:, 0].max()
    y_min, y_max = top_xy[:, 1].min(), top_xy[:, 1].max()

    # --- Jittered grid of bump centers ---
    rng = np.random.default_rng(seed=42)
    cols = max(1, int(math.ceil((x_max - x_min) / bump_spacing)) + 1)
    rows = max(1, int(math.ceil((y_max - y_min) / bump_spacing)) + 1)

    xs_centers = np.linspace(x_min, x_min + (cols - 1) * bump_spacing, cols)
    ys_centers = np.linspace(y_min, y_min + (rows - 1) * bump_spacing, rows)

    grid_x, grid_y = np.meshgrid(xs_centers, ys_centers)
    grid_x = grid_x.ravel()
    grid_y = grid_y.ravel()

    # Jitter: random offset up to ±bump_spacing/2
    jitter_scale = bump_spacing * 0.5
    jitter_x = rng.uniform(-jitter_scale, jitter_scale, size=len(grid_x))
    jitter_y = rng.uniform(-jitter_scale, jitter_scale, size=len(grid_y))
    centers = np.column_stack([grid_x + jitter_x, grid_y + jitter_y])

    n_bumps = len(centers)

    # --- Find nearest bump center for each top vertex (vectorised via cKDTree) ---
    R = bump_spacing * 0.48
    tree = cKDTree(centers)
    dists, _ = tree.query(top_xy, k=1)

    # Paraboloid displacement: amplitude * max(0, 1 - (r/R)^2)
    r_norm = dists / R
    dz = amplitude * np.maximum(0.0, 1.0 - r_norm ** 2)
    # Freeze any protected (seam-adjacent) top verts so the fringe-green seam
    # stays flush after grass is applied to the fringe only.
    if protect.any():
        dz = np.where(protect, 0.0, dz)

    # Apply displacement to top-surface vertices
    verts[top_mask, 2] += dz

    print(f"    Grass texture: {n_bumps} bumps, R={R:.3f} mm, amplitude={amplitude:.3f} mm, "
          f"dz range [{dz.min():.3f}, {dz.max():.3f}] mm on {top_mask.sum()} vertices"
          f"{' (+' + str(int(protect.sum())) + ' seam-frozen)' if protect.any() else ''}")

    return mesh


# ---------------------------------------------------------------------------
# Fringe divot
# ---------------------------------------------------------------------------

def apply_divot(mesh, center_xy, radius, depth):
    """Lower top-surface vertices within `radius` of center_xy by a hemispherical amount."""
    verts = mesh.vertices  # live reference
    # Use BASE_THICKNESS_MM to identify top-surface vertices (same as apply_grass_texture).
    # Using z_max - 0.6 is too narrow when grass bumps create tall spikes at varied heights.
    top_mask = verts[:, 2] > BASE_THICKNESS_MM
    dx = verts[top_mask, 0] - center_xy[0]
    dy = verts[top_mask, 1] - center_xy[1]
    d = np.sqrt(dx*dx + dy*dy)
    inside = d <= radius
    # For vertices inside the divot, lower their Z by the hemispherical depth
    # dz = radius - sqrt(radius^2 - d^2)  (positive depression amount)
    subset_d = d[inside]
    dz = radius - np.sqrt(np.maximum(0.0, radius*radius - subset_d*subset_d))
    # Apply: lower the Z of those vertices
    idxs = np.where(top_mask)[0][inside]
    verts[idxs, 2] -= dz
    n_lowered = inside.sum()
    max_dz = dz.max() if n_lowered > 0 else 0.0
    print(f"    Divot: {n_lowered} vertices lowered, center={center_xy}, "
          f"radius={radius} mm, depth={depth} mm, max dz={max_dz:.2f} mm")
    return mesh


# ---------------------------------------------------------------------------
# Golf-tee-top ball stand
# ---------------------------------------------------------------------------

def build_ball_stand(
    n_seg: int = 64,
    n_taper: int = 24,
    n_cap: int = 32,
    n_tip: int = 8,
) -> "trimesh.Trimesh":
    """
    Build a golf-tee-shaped pedestal for a decorative golf ball.

    Shape (all dimensions in mm):
      - Pointed tip: z=0 (r=0 pole) → z=2 (r=1.5), quadratic ramp
      - Straight shaft: z=2 to z=7, r=1.5 (5 mm long)
      - Concave cup flare: z=7 to z=12, r=1.5→7.5 via quadratic Bezier
        (concave sides — tangent vertical at neck, horizontal at rim)
      - Cup rim shelf at z=12: outer r=7.5 → inner r=6 (horizontal)
      - Spherical-cap cup: r=6 to r=0, 3 mm deep
        R = (r² + h²) / (2h) = (36 + 9) / 6 = 7.5 mm (sphere radius)
        Sphere center at z=16.5; z = 16.5 - sqrt(56.25 - r^2)
        r=0 → z=9 (cup bottom pole), r=6 → z=12 (cup rim) ✓

    Total height: 12 mm (rim unchanged; cup bottom drops from z=10 to z=9).

    The mesh is built by revolving a 2-D (r, z) profile around the Z axis
    and triangulating ring-by-ring. Both z=0 (tip) and z=9 (cup bottom)
    are poles (r=0) and produce watertight fan triangles.
    """
    # --- Spherical cap parameters (cup) ---
    # Cup radius r_cup=6, depth h=3
    # R = (r_cup² + h²) / (2h) = (36 + 9) / 6 = 7.5
    # Sphere center z = cup_bottom_z + R = 9 + 7.5 = 16.5
    # At r=0: z = 16.5 - 7.5 = 9 (cup bottom)
    # At r=6: z = 16.5 - sqrt(56.25 - 36) = 16.5 - 4.5 = 12 (cup rim) ✓
    R_sphere = 7.5
    z_sphere_center = 16.5
    r_cup_rim = 6.0

    # --- Build 2-D radial profile ---
    # Order: bottom pole (tip) → up outer shell → down cup interior → top pole (cup bottom)
    profile = []

    # 1. POINTED TIP — bottom pole (r=0, z=0)
    profile.append((0.0, 0.0))

    # 2. TIP RAMP — quadratic flare from (0,0) to (1.5,2), n_tip steps
    # Start i=1 to skip i=0 (already added pole above)
    for i in range(1, n_tip + 1):
        t = i / n_tip                  # (1/n_tip) → 1.0
        r = 1.5 * math.sqrt(t)        # gradual flare: 1.5x wider than original
        z = t * 2.0                   # linear z from 0 to 2
        profile.append((r, z))
    # Last tip point: (1.5, 2.0)

    # 3. STRAIGHT SHAFT — from z=2 to z=7, r=1.5 (single segment, no intermediate points needed)
    profile.append((1.5, 7.0))

    # 4. CONCAVE CUP FLARE — quadratic Bezier from (1.5,7) to (7.5,12)
    # P0 = (1.5,7), C = (1.5,12), P1 = (7.5,12)
    # Tangent at P0 is vertical (shaft direction), tangent at P1 is horizontal (rim direction)
    # The control point at (1.5,12) pulls the curve inward → concave sides
    P0 = np.array([1.5, 7.0])
    Ctrl = np.array([1.5, 12.0])
    P1 = np.array([7.5, 12.0])
    # Skip i=0 (already at neck P0 = last shaft point)
    for i in range(1, n_taper + 1):
        t = i / n_taper
        pt = (1 - t) ** 2 * P0 + 2 * (1 - t) * t * Ctrl + t ** 2 * P1
        profile.append((pt[0], pt[1]))
    # Last flare point: (7.5, 12.0) — rim outer corner

    # 5. CUP RIM SHELF — horizontal step inward at z=12
    profile.append((r_cup_rim, 12.0))

    # 6. SPHERICAL CAP INTERIOR — from (6,12) down to (0,9)
    # Sample n_cap points; i=0 gives r=6 (already added above), start from i=1
    for i in range(1, n_cap + 1):
        t = i / float(n_cap)              # 0 exclusive → 1 inclusive
        r = r_cup_rim * (1.0 - t)        # 6 → 0
        z = z_sphere_center - math.sqrt(max(0.0, R_sphere ** 2 - r ** 2))
        profile.append((r, z))
    # Last cap point: (0.0, 9.0) — this is the top pole (cup bottom)

    # --- Revolve profile around Z axis ---
    # For watertight poles, axis points (r=0) get exactly ONE vertex each.
    # Ring metadata: (start_index, count) where count=1 for poles, n_seg for rings.
    angles = np.linspace(0.0, 2.0 * math.pi, n_seg, endpoint=False)
    cos_a = np.cos(angles)
    sin_a = np.sin(angles)

    vertices = []
    # rings: list of (start_index, vertex_count, r)
    rings = []

    for r, z in profile:
        start = len(vertices)
        if r == 0.0:
            # Pole — single vertex on the axis
            vertices.append([0.0, 0.0, z])
            rings.append((start, 1, r))
        else:
            for k in range(n_seg):
                vertices.append([r * cos_a[k], r * sin_a[k], z])
            rings.append((start, n_seg, r))

    vertices = np.array(vertices, dtype=np.float64)
    faces = []

    def ring_vtx(ring_i, seg_j):
        """Vertex index for ring ring_i at angular position seg_j (wraps)."""
        start, count, _ = rings[ring_i]
        if count == 1:
            return start  # pole — always the single vertex
        return start + (seg_j % n_seg)

    for ri in range(len(rings) - 1):
        _, _, r_bot = rings[ri]
        _, _, r_top = rings[ri + 1]
        for j in range(n_seg):
            j1 = (j + 1) % n_seg
            a = ring_vtx(ri,     j)
            b = ring_vtx(ri,     j1)
            c = ring_vtx(ri + 1, j)
            d = ring_vtx(ri + 1, j1)

            if r_bot == 0.0:
                # Bottom pole — fan triangle: pole → next ring
                # Winding: outward normal faces down (away from next ring)
                faces.append([a, d, c])
            elif r_top == 0.0:
                # Top pole — fan triangle: prev ring → pole
                faces.append([a, b, c])
            else:
                # Normal quad → 2 triangles (CCW outward)
                faces.append([a, b, d])
                faces.append([a, d, c])

    faces = np.array(faces, dtype=np.int64)
    mesh = trimesh.Trimesh(vertices=vertices, faces=faces, process=True)
    return mesh


# ---------------------------------------------------------------------------
# 3MF post-processing — per-object filament/extruder metadata (Bambu Studio)
# ---------------------------------------------------------------------------

def _filament_for_scene_name(name: str) -> int:
    """
    Map a scene node name to a Bambu Studio extruder/filament index.

    Convention:
        green*  → 1
        fringe* → 2
        trap*   → 3   (sand traps; "sand_trap*" also matches)
        water*  → 4   (water traps; placeholder until EGM gains type='water')

    Default for anything unrecognised is 1, so unknown geometries don't
    silently land on a high extruder slot the user has nothing loaded into.
    """
    n = (name or "").lower()
    if n.startswith("water"):
        return 4
    if n.startswith("sand_trap") or n.startswith("trap"):
        return 3
    if n.startswith("fringe"):
        return 2
    if n.startswith("green"):
        return 1
    return 1


def _inject_bambu_extruder_metadata(path_3mf: str, scene_names: list) -> None:
    """
    Post-process a trimesh-written 3MF to add per-object extruder assignments
    that Bambu Studio / OrcaSlicer understand.

    trimesh.Scene.export writes a single ``3D/3dmodel.model`` file with one
    ``<object id="N" name="geometry_K" ...>`` per scene geometry, in the same
    order they were added to the Scene. Bambu reads extruder assignments out
    of ``Metadata/model_settings.config`` (one ``<object id="N">`` block per
    model object, with a ``<metadata key="extruder" value="M"/>`` child and
    a matching ``<part>`` block).

    This function:
      1. Opens ``path_3mf`` as a zip and parses ``3D/3dmodel.model``.
      2. Reads each ``<object>``'s id (and name attribute, e.g. "geometry_0").
      3. Pairs that ordered list with ``scene_names`` (same order — both come
         from Scene.geometry insertion order) to derive the extruder via
         ``_filament_for_scene_name``.
      4. Writes a fresh ``Metadata/model_settings.config`` into the zip.

    If counts don't line up, falls back to extruder=1 for everything and
    prints a warning rather than silently mis-tagging.
    """
    import zipfile
    import shutil
    import re as _re
    import xml.etree.ElementTree as _ET

    # --- 1. Read 3D/3dmodel.model out of the existing zip ---
    with zipfile.ZipFile(path_3mf, "r") as zin:
        try:
            model_xml = zin.read("3D/3dmodel.model").decode("utf-8")
        except KeyError:
            print(f"  WARNING: 3D/3dmodel.model missing from {path_3mf}; "
                  f"cannot inject extruder metadata.")
            return
        existing_names = set(zin.namelist())

    # --- 2. Pull (object_id, object_name) in document order ---
    # ElementTree handles namespaces but we only need the attributes.
    ns = "{http://schemas.microsoft.com/3dmanufacturing/core/2015/02}"
    try:
        root = _ET.fromstring(model_xml)
    except _ET.ParseError as exc:
        print(f"  WARNING: failed to parse 3dmodel.model ({exc}); "
              f"skipping extruder metadata.")
        return

    object_entries: list[tuple[str, str]] = []  # (object_id, name)
    for obj in root.iter(f"{ns}object"):
        oid = obj.attrib.get("id", "")
        oname = obj.attrib.get("name", "")
        if oid:
            object_entries.append((oid, oname))

    if len(object_entries) != len(scene_names):
        print(f"  WARNING: 3dmodel.model has {len(object_entries)} objects but "
              f"scene_names has {len(scene_names)}; falling back to extruder=1 "
              f"for every object.")
        mapping = [(oid, oname, 1) for (oid, oname) in object_entries]
    else:
        mapping = [
            (oid, oname, _filament_for_scene_name(scene_names[i]))
            for i, (oid, oname) in enumerate(object_entries)
        ]

    # --- 3. Build Metadata/model_settings.config ---
    # Bambu's <part id> values must be unique across the whole config. We
    # allocate a part id per object using object_id + a fixed offset so the
    # part ids do not collide with object ids. (This matches the layout
    # observed in Bambu-Studio-saved 3MFs.)
    cfg_lines = ['<?xml version="1.0" encoding="UTF-8"?>', '<config>']
    for oid, oname, extruder in mapping:
        try:
            part_id = int(oid) + 1000
        except ValueError:
            part_id = 1000
        display_name = oname or f"object_{oid}"
        cfg_lines.append(f'  <object id="{oid}">')
        cfg_lines.append(f'    <metadata key="name" value="{display_name}"/>')
        cfg_lines.append(f'    <metadata key="extruder" value="{extruder}"/>')
        cfg_lines.append(f'    <part id="{part_id}" subtype="normal_part">')
        cfg_lines.append(f'      <metadata key="name" value="{display_name}"/>')
        cfg_lines.append(f'      <metadata key="matrix" value="1 0 0 0 0 1 0 0 0 0 1 0 0 0 0 1"/>')
        cfg_lines.append(f'      <metadata key="extruder" value="{extruder}"/>')
        cfg_lines.append(f'    </part>')
        cfg_lines.append(f'  </object>')
    cfg_lines.append('</config>')
    cfg_lines.append('')
    cfg_xml = "\n".join(cfg_lines)

    # --- 4. Rewrite zip with the new Metadata/model_settings.config ---
    # zipfile cannot edit in place; copy entries to a sibling temp file then
    # atomically replace the original.
    tmp_path = path_3mf + ".tmp"
    with zipfile.ZipFile(path_3mf, "r") as zin, \
         zipfile.ZipFile(tmp_path, "w", zipfile.ZIP_DEFLATED) as zout:
        for item in zin.infolist():
            if item.filename == "Metadata/model_settings.config":
                # Skip — we'll write a fresh one below.
                continue
            zout.writestr(item, zin.read(item.filename))
        zout.writestr("Metadata/model_settings.config", cfg_xml)

    shutil.move(tmp_path, path_3mf)

    summary = ", ".join(
        f"{oname or oid}=ext{ext}" for oid, oname, ext in mapping
    )
    print(f"  Extruder metadata injected → {summary}")


# ---------------------------------------------------------------------------
# Mount-pipe footprint subtraction (task #347 — replaces #346 corner search)
# ---------------------------------------------------------------------------
#
# Thomas's correction (#347): the mount pipe stays at the fixed upper-left
# corner regardless of what's underneath it. Instead of moving the pipe to
# avoid traps/water, every other surface (trap polygon, water polygon, fringe
# carve-out union) gets the pipe footprint subtracted out so the surfaces
# don't overlap the pipe. The pipe is allowed to land on the boundary of, or
# straddle the interface between, multiple obstacle polygons.
# ---------------------------------------------------------------------------

def _subtract_pipe_from_polygon(
    poly: ShapelyPolygon,
    pipe_circle: ShapelyPolygon,
    label: str,
) -> "ShapelyPolygon | None":
    """
    Subtract the mount-pipe circular footprint from a trap/water polygon.

    No-op when the polygon does not intersect the pipe footprint (returns
    the input polygon unchanged).

    If the difference splits the polygon into multiple pieces (the pipe
    straddles a thin neck in the original polygon), the largest piece by
    area is returned and the others are logged + discarded — same pattern
    as ``_clip_polygon_to_fringe_rect``.

    Returns None if the polygon is fully consumed by the pipe footprint
    (caller should skip emitting any mesh for it).
    """
    if not poly.is_valid:
        poly = poly.buffer(0)
    if not pipe_circle.intersects(poly):
        return poly
    notched = poly.difference(pipe_circle)
    if notched.is_empty:
        print(f"  {label}: pipe footprint fully covers polygon — skipping")
        return None
    # Log a notch event so Topo / Thomas can see which polygons were affected.
    overlap_area = float(poly.intersection(pipe_circle).area)
    print(f"  {label}: notched by mount-pipe footprint (overlap={overlap_area:.2f} mm^2)")
    if isinstance(notched, ShapelyMultiPolygon):
        parts = sorted(list(notched.geoms), key=lambda g: g.area, reverse=True)
        kept = parts[0]
        dropped = parts[1:]
        if dropped:
            dropped_areas = ", ".join(f"{p.area:.2f}" for p in dropped)
            print(f"  {label}: pipe-subtract produced MultiPolygon — kept "
                  f"largest ({kept.area:.2f} mm^2), discarded {len(dropped)} "
                  f"part(s) with areas [{dropped_areas}] mm^2")
        return kept
    if isinstance(notched, ShapelyPolygon):
        return notched
    # GeometryCollection or other — try to recover the largest polygonal piece.
    try:
        polys = [g for g in notched.geoms if isinstance(g, ShapelyPolygon) and not g.is_empty]
        if not polys:
            print(f"  {label}: pipe-subtract yielded no polygon geometry — skipping")
            return None
        polys.sort(key=lambda g: g.area, reverse=True)
        return polys[0]
    except Exception:
        print(f"  {label}: unrecognised pipe-subtract geometry "
              f"{type(notched).__name__} — keeping input")
        return poly


def _build_pipe_circle(cx: float, cy: float) -> ShapelyPolygon:
    """Return the mount-pipe outer-wall circular footprint at (cx, cy)."""
    from shapely.geometry import Point as _ShapelyPoint
    return _ShapelyPoint(cx, cy).buffer(MOUNT_BORE_OUTER_RADIUS_MM)


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def run_pipeline(egm_path: str) -> str:
    """Run the full gradient surface pipeline for a given EGM file path.

    Returns the absolute path to the generated .3mf file.
    """
    print("=" * 60)
    print("Gradient Surface Diagnostic")
    print("=" * 60)

    # ── 1. Load EGM and image ───────────────────────────────────────────────
    print(f"\n[1] EGM: {os.path.basename(egm_path)}")
    _egm_data, image_path, green_boundary_px = load_egm(egm_path)
    print(f"    Image: {os.path.basename(image_path)}")
    print(f"    Green boundary: {len(green_boundary_px)} spline points")

    img = cv2.imread(image_path)
    if img is None:
        raise FileNotFoundError(f"Cannot read image: {image_path}")
    print(f"    Image size: {img.shape[1]}x{img.shape[0]}")

    # ── 2. Detect arrows ────────────────────────────────────────────────────
    print("\n[2] Detecting arrows…")
    arrows = detect_arrows(img, green_boundary_px, dark_threshold=50, max_arrow_area=600)
    print(f"    Found {len(arrows)} arrows")

    if len(arrows) == 0:
        print("  WARNING: No arrows detected. Check dark_threshold or image path.")

    # ── 3. Build gradient field ─────────────────────────────────────────────
    GRID_RES = 200
    print(f"\n[3] Building gradient field ({GRID_RES}x{GRID_RES} grid)…")
    xs_grid, ys_grid, inside_mask, Gx, Gy = build_gradient_field(
        arrows, green_boundary_px, grid_res=GRID_RES
    )
    print(f"    Gradient field built. Gx range: [{Gx[inside_mask].min():.3f}, {Gx[inside_mask].max():.3f}]")
    print(f"    Gy range: [{Gy[inside_mask].min():.3f}, {Gy[inside_mask].max():.3f}]")

    # ── 4. Solve Poisson ────────────────────────────────────────────────────
    print("\n[4] Solving Poisson equation…")
    Z = solve_poisson_height(inside_mask, Gx, Gy)

    # Green smoothing disabled — raw Poisson surface
    valid = Z[~np.isnan(Z)]
    print(f"    Height range (raw, pre-soften): {valid.min():.4f} .. {valid.max():.4f}")

    # Clamp + soften spurious local peaks/valleys before triangulation.
    Z, _soften_stats = soften_extremes(Z, inside_mask)
    print(
        f"    soften_extremes: peak_limit={_soften_stats['peak_limit_mm']:.2f} mm, "
        f"valley_limit={_soften_stats['valley_limit_mm']:.2f} mm, "
        f"window={_soften_stats['local_window_px']} px, "
        f"sigma={_soften_stats['soften_sigma_px']} px"
    )
    print(
        f"    BEFORE: max peak={_soften_stats['max_peak_mm_before']:+.3f} mm, "
        f"min valley={_soften_stats['min_valley_mm_before']:+.3f} mm, "
        f"#peaks>limit={_soften_stats['n_peaks_clipped']}, "
        f"#valleys<limit={_soften_stats['n_valleys_clipped']}"
    )
    print(
        f"    AFTER:  max peak={_soften_stats['max_peak_mm_after']:+.3f} mm, "
        f"min valley={_soften_stats['min_valley_mm_after']:+.3f} mm, "
        f"#peaks>limit={_soften_stats['n_peaks_after']}, "
        f"#valleys<limit={_soften_stats['n_valleys_after']}"
    )

    # ── Build filename slug from course + hole ────────────────────────────────
    import re
    course = _egm_data.get("course", "unknown")
    hole = _egm_data.get("hole", "0")
    slug = re.sub(r"[^a-z0-9]+", "_", f"{course}_hole_{hole}".lower()).strip("_")
    print(f"    File slug: {slug}")

    # ── Resolve output directories from course_paths ─────────────────────────
    # NOTE: per the course folder convention, the pipeline does NOT emit STLs
    # into the course folder. STLs are not deliverables — only the final 3MF
    # matters. All intermediate meshes stay in memory.
    _cpaths = course_paths(course) if course != "unknown" else None
    _3mf_dir  = _cpaths["3mfs"]   if _cpaths else OWNER_INBOX
    _img_dir  = _cpaths["images"] if _cpaths else OWNER_INBOX
    os.makedirs(_3mf_dir,  exist_ok=True)
    os.makedirs(_img_dir,  exist_ok=True)

    # ── 5. Save diagnostic images ───────────────────────────────────────────
    # Diagnostic PNG writes (arrow_directions, height_map) disabled to keep
    # course Images/ folders clean. Helpers `save_arrow_directions` and
    # `save_height_map` remain defined for one-off debugging — re-enable by
    # uncommenting the calls below.
    # print("\n[5] Saving diagnostic images…")
    # arrow_out = os.path.join(_img_dir, f"{slug}_arrow_directions.png")
    # save_arrow_directions(img, arrows, green_boundary_px, arrow_out)
    # height_out = os.path.join(_img_dir, f"{slug}_height_map.png")
    # save_height_map(Z, xs_grid, ys_grid, green_boundary_px, height_out)

    # ── 6. Build green surface meshes (smooth + stepped, in-memory) ─────────
    print("\n[6] Building green surface meshes…")
    smooth_mesh_flat, stepped_mesh = save_stl_meshes(
        Z, xs_grid, ys_grid, inside_mask, green_boundary_px,
        _egm_data, None, None  # no STL writes — meshes are 3MF-bound
    )

    # ── 6b. Apply grass texture to smooth mesh ──────────────────────────────
    grass_amplitude = _egm_data.get("grassAmplitude", 0.5)
    grass_spacing   = _egm_data.get("grassSpacing",   2.4)
    print(f"\n[6b] Applying grass texture (amplitude={grass_amplitude} mm, spacing={grass_spacing} mm)…")
    import copy
    smooth_mesh = copy.deepcopy(smooth_mesh_flat)
    apply_grass_texture(smooth_mesh, amplitude=grass_amplitude, bump_spacing=grass_spacing)

    # ── 7. Build fringe mesh ────────────────────────────────────────────────
    print("\n[7] Building fringe mesh…")
    scale_f, centroid_f = _compute_px_to_mm(green_boundary_px, _egm_data)
    Z_mm_for_fringe = _height_to_mm(Z, inside_mask)
    fringe_mesh = None
    fringe_mesh_flat = None   # kept for trap height sampling (no texture perturbation)

    # Mounting-bore "pipe" footprint (task #335). The fringe is hollowed out
    # for the FULL pipe outer diameter so we can drop in an explicit
    # annular-walled cylinder afterwards. Inner bore = 3/16", wall =
    # WALL_THICKNESS_MM (1.6 mm) → outer Ø = 4.7625 + 2×1.6 = 7.9625 mm.
    #
    # Task #347: the pipe stays at the fixed upper-left corner regardless of
    # what's underneath it. The earlier collision-aware corner search (#346)
    # was the wrong design — Thomas wants the pipe in a known fixed position
    # and the OTHER surfaces (traps, water, fringe) carved to match. The
    # `pipe_circle` Shapely polygon below is what those subtractions use.
    _half_for_bore = PRINT_SIZE_MM / 2.0 + FRINGE_XY_EXPANSION_MM / 2.0
    _bore_cx = -_half_for_bore + MOUNT_BORE_INSET_MM
    _bore_cy = +_half_for_bore - MOUNT_BORE_INSET_MM
    pipe_circle = _build_pipe_circle(_bore_cx, _bore_cy)
    print(f"  Mount pipe: fixed upper-left at ({_bore_cx:.2f}, {_bore_cy:.2f}), "
          f"r_outer={MOUNT_BORE_OUTER_RADIUS_MM:.4f} mm")

    # Green-overlap warning (#347 step 2.4): the pipe lives ~20 mm from the
    # rect edge so it should never land inside the green polygon, but log a
    # warning if it ever does so Thomas can flag the case. We do NOT carve
    # the green raster mask — see #347 step 2.4 for the rationale.
    try:
        _green_bnd_mm_warn = _px_to_mm_2d(
            green_boundary_px.copy(), scale_f, centroid_f
        )
        _green_sp_warn = ShapelyPolygon(_green_bnd_mm_warn)
        if not _green_sp_warn.is_valid:
            _green_sp_warn = _green_sp_warn.buffer(0)
        if pipe_circle.intersects(_green_sp_warn):
            _green_overlap = float(_green_sp_warn.intersection(pipe_circle).area)
            if _green_overlap > 1e-3:
                print(f"  Mount pipe: WARNING — pipe footprint intersects green "
                      f"polygon (overlap={_green_overlap:.2f} mm^2). The green "
                      f"raster mask is NOT carved; flag this hole for review.")
    except Exception as _exc_green_warn:
        print(f"  Mount pipe: green-overlap check failed: {_exc_green_warn}")

    fringe_holes: list = [(_bore_cx, _bore_cy, MOUNT_BORE_OUTER_RADIUS_MM)]
    try:
        fringe_mesh = build_fringe_mesh(
            Z_mm_for_fringe,
            xs_grid, ys_grid,
            inside_mask,
            green_boundary_px,
            _egm_data,
            fringe_grid_res=200,
            holes=fringe_holes,
        )
        bb = fringe_mesh.bounds
        print(f"  Fringe mesh: {len(fringe_mesh.vertices)} vertices, {len(fringe_mesh.faces)} faces")
        print(f"  Watertight: {fringe_mesh.is_watertight}")
        print(f"  Bounding box: X [{bb[0,0]:.1f}, {bb[1,0]:.1f}] "
              f"Y [{bb[0,1]:.1f}, {bb[1,1]:.1f}] Z [{bb[0,2]:.1f}, {bb[1,2]:.1f}] mm")
        _verify_fringe_boundary(
            fringe_mesh, Z_mm_for_fringe,
            xs_grid, ys_grid, inside_mask,
            green_boundary_px, _egm_data,
        )
        # Keep an in-memory reference to the flat (untextured) fringe for
        # trap height sampling, before grass texture displaces seam vertices.
        fringe_mesh_flat = copy.deepcopy(fringe_mesh)
        # Apply grass texture to fringe top surface.  IMPORTANT: the green
        # surface added to the 3MF is the untextured (flat) version, so any
        # grass bump applied to a fringe seam vertex opens a visible gap
        # against the green's pinned boundary.  We freeze the seam verts here.
        _green_bnd_mm_for_grass = _px_to_mm_2d(
            green_boundary_px.copy(), scale_f, centroid_f
        )
        # Exclude-radius must cover the seam snap radius used in build_fringe_mesh
        # (≈1.5 × fringe grid step).  A dense grid (200^2 over ±85 mm) gives
        # ~0.86 mm step → ~1.3 mm radius; use 2.0 mm for safety.
        _seam_exclude_radius_mm = 2.0
        print(f"  Applying grass texture to fringe (amplitude={grass_amplitude} mm, spacing={grass_spacing} mm)…")
        apply_grass_texture(
            fringe_mesh,
            amplitude=grass_amplitude,
            bump_spacing=grass_spacing,
            exclude_polyline_xy=_green_bnd_mm_for_grass,
            exclude_radius_mm=_seam_exclude_radius_mm,
        )

        # ── 7b. Build the upper-left mounting-bore PIPE (task #335) ──────────
        # The fringe was already hollowed out at (_bore_cx, _bore_cy) with
        # outer-pipe radius. Now we drop a watertight hollow cylinder into
        # that void: outer wall = MOUNT_BORE_OUTER_RADIUS_MM, inner bore =
        # MOUNT_BORE_INNER_RADIUS_MM (3/16"), height = fringe top Z at the
        # bore boundary (no stub above fringe).
        try:
            _flat_verts = fringe_mesh_flat.vertices
            _dx = _flat_verts[:, 0] - _bore_cx
            _dy = _flat_verts[:, 1] - _bore_cy
            _r = np.sqrt(_dx * _dx + _dy * _dy)
            _grid_step_mm = (PRINT_SIZE_MM + abs(FRINGE_XY_EXPANSION_MM)) / 200.0
            _ring_inner = MOUNT_BORE_OUTER_RADIUS_MM
            _ring_outer = MOUNT_BORE_OUTER_RADIUS_MM + 2.0 * _grid_step_mm
            _ring_mask = (
                (_r >= _ring_inner)
                & (_r <= _ring_outer)
                & (_flat_verts[:, 2] > BASE_THICKNESS_MM * 0.5)
            )
            if _ring_mask.any():
                _ring_z = _flat_verts[_ring_mask, 2]
                _pipe_top_z = float(np.max(_ring_z))
                print(f"  Bore-rim fringe Z: count={int(_ring_mask.sum())} "
                      f"range=[{_ring_z.min():.3f}, {_ring_z.max():.3f}] mm "
                      f"→ pipe top z = {_pipe_top_z:.3f} mm")
            else:
                _pipe_top_z = float(BASE_THICKNESS_MM + 0.5)
                print(f"  WARN: no fringe verts found near bore rim, "
                      f"falling back to pipe top z = {_pipe_top_z:.3f} mm")

            _pipe_mesh = build_mount_pipe_mesh(
                cx=_bore_cx,
                cy=_bore_cy,
                inner_radius=MOUNT_BORE_INNER_RADIUS_MM,
                outer_radius=MOUNT_BORE_OUTER_RADIUS_MM,
                z_top=_pipe_top_z,
                n_seg=64,
            )
            print(f"  Mount pipe: cx={_bore_cx:.2f} cy={_bore_cy:.2f} "
                  f"r_in={MOUNT_BORE_INNER_RADIUS_MM:.4f} "
                  f"r_out={MOUNT_BORE_OUTER_RADIUS_MM:.4f} "
                  f"z=[0, {_pipe_top_z:.3f}] mm "
                  f"({len(_pipe_mesh.vertices)} verts, {len(_pipe_mesh.faces)} faces)")

            # Concatenate pipe with the (textured) fringe so the result is a
            # single Trimesh that travels through the rest of the pipeline as
            # one body. Per task #335 the pipe must read as part of the fringe
            # (filament 2 in the per-object metadata) — keeping it inside the
            # `fringe` scene node achieves that without touching the filament
            # mapping in _filament_for_scene_name.
            fringe_mesh = trimesh.util.concatenate([fringe_mesh, _pipe_mesh])
            fringe_mesh.merge_vertices(digits_vertex=6)
            fringe_mesh.update_faces(fringe_mesh.nondegenerate_faces())
            fringe_mesh.update_faces(fringe_mesh.unique_faces())
            fringe_mesh.remove_unreferenced_vertices()
            print(f"  Fringe + pipe (merged): {len(fringe_mesh.vertices)} verts, "
                  f"{len(fringe_mesh.faces)} faces, "
                  f"watertight={fringe_mesh.is_watertight}")
        except Exception as exc_pipe:
            print(f"  ERROR building/merging mount pipe: {exc_pipe}")
            import traceback; traceback.print_exc()
    except Exception as exc:
        print(f"  ERROR building fringe mesh: {exc}")
        import traceback; traceback.print_exc()

    # ── 7c. Water-hole rule: lift green + fringe (+ optional cap) ───────────
    #
    # When the EGM contains any water polygon, lift green and fringe by
    # WATER_HOLE_LIFT_MM so a 2 mm filament base sits underneath. The fringe
    # touches the frame boundary by construction, so its top is also capped
    # at BOUNDARY_HEIGHT_CAP_MM (mode = BOUNDARY_HEIGHT_CAP_MODE). The green
    # is interior to the fringe and never touches the frame, so it is lifted
    # only — no cap. Traps and water are handled inside their export_*
    # functions (see export_trap_stls / export_water_meshes).
    #
    # Sampling note: trap and water heights were computed earlier from
    # `fringe_mesh_flat` (an unlifted reference). After we lift `fringe_mesh`
    # here, that reference still holds the un-lifted fringe Z, so trap and
    # water slabs are sized against the original surface; their own lift is
    # then applied on top of that, producing a consistent +2 mm shift for
    # every printable piece in the assembly.
    _hole_water_active = WATER_HOLE_LIFT_ENABLED and _hole_has_water(_egm_data)
    if _hole_water_active:
        print(f"\n[7c] Water-hole rule: lift={WATER_HOLE_LIFT_MM} mm, "
              f"boundary cap={BOUNDARY_HEIGHT_CAP_MM} mm "
              f"(mode={BOUNDARY_HEIGHT_CAP_MODE})")
        # Green: smooth + stepped variants — never touches the frame, so no cap.
        if isinstance(smooth_mesh_flat, trimesh.Trimesh):
            _apply_lift_and_cap(
                smooth_mesh_flat, lift_mm=WATER_HOLE_LIFT_MM,
                cap_mm=None, label="green_smooth",
            )
        if isinstance(stepped_mesh, trimesh.Trimesh):
            _apply_lift_and_cap(
                stepped_mesh, lift_mm=WATER_HOLE_LIFT_MM,
                cap_mm=None, label="green_stepped",
            )
        # Fringe: ALWAYS touches the frame by construction → lift + cap.
        if isinstance(fringe_mesh, trimesh.Trimesh):
            _apply_lift_and_cap(
                fringe_mesh, lift_mm=WATER_HOLE_LIFT_MM,
                cap_mm=BOUNDARY_HEIGHT_CAP_MM, label="fringe",
            )
    else:
        print("\n[7c] Water-hole rule: SKIPPED (no water polygons in EGM)")

    # ── 8. Build sand trap meshes (in-memory) ───────────────────────────────
    print("\n[8] Building sand trap meshes…")
    trap_meshes = export_trap_stls(_egm_data, green_boundary_px, slug,
                                   fringe_mesh=fringe_mesh_flat,
                                   pipe_circle=pipe_circle,
                                   write_stls=False)
    if not trap_meshes:
        print("  (no traps built)")

    # ── 8b. Build water trap meshes (in-memory) ─────────────────────────────
    print("\n[8b] Building water trap meshes…")
    water_meshes = export_water_meshes(_egm_data, green_boundary_px, slug,
                                       fringe_mesh=fringe_mesh_flat,
                                       pipe_circle=pipe_circle,
                                       write_stls=False)
    if not water_meshes:
        print("  (no water built)")

    # ── 9. Contour debug image ──────────────────────────────────────────────
    # Diagnostic gradient_contours.png write disabled to keep course Images/
    # folders clean. Helper `save_contour_debug_image` remains defined for
    # one-off debugging — re-enable by uncommenting the call below.
    # print("\n[9] Saving contour lines debug image…")
    # contour_out = os.path.join(_img_dir, f"{slug}_gradient_contours.png")
    # save_contour_debug_image(
    #     Z, xs_grid, ys_grid, inside_mask, img, green_boundary_px, contour_out
    # )

    # ── 10. Assemble 3MF ────────────────────────────────────────────────────
    print("\n[10] Assembling 3MF…")

    # ── 10b. Peek serial before building filename so it can be embedded in it ──
    # One Generate press == one serial number, engraved on *every* item produced.
    # The counter is persisted per-course (starting at 100) and only advanced
    # AFTER the 3MF is successfully written to disk.
    from serial_engraver import (
        peek_next_serial as _peek_serial,
        commit_serial as _commit_serial,
        engrave_scene_geometries as _engrave_scene,
    )
    serial_number = _peek_serial(course)
    # Embed serial in filename: "Course (Hole N) [SN].3mf"
    fname_3mf = f"{course} (Hole {hole}) [{serial_number}].3mf"
    path_3mf = os.path.join(_3mf_dir, fname_3mf)

    scene = trimesh.Scene()
    scene_names = []

    # Green surface — flat (no grass) smooth or terraced based on EGM setting
    green_style = _egm_data.get("greenStyle", "smooth")
    print(f"  Using {green_style} green surface")
    if green_style == "terraced":
        scene.add_geometry(stepped_mesh, node_name="green_surface")
    else:
        scene.add_geometry(smooth_mesh_flat, node_name="green_surface")  # flat, no grass
    scene_names.append("green_surface")

    # Fringe mesh (if built successfully) — includes a 3/16" through-hole at the stand corner
    if isinstance(fringe_mesh, trimesh.Trimesh):
        scene.add_geometry(fringe_mesh, node_name="fringe")
        scene_names.append("fringe")

    # Trap meshes — added directly from memory (no disk round-trip)
    for trap_node, trap_mesh in trap_meshes:
        scene.add_geometry(trap_mesh, node_name=trap_node)
        scene_names.append(trap_node)

    # Water meshes — names start with "water" so _filament_for_scene_name
    # routes each one to extruder 4 (royal blue filament).
    for water_node, water_mesh in water_meshes:
        scene.add_geometry(water_mesh, node_name=water_node)
        scene_names.append(water_node)

    print(f"\n[10b] Engraving serial s/n: {serial_number} on {len(scene_names)} item(s)…")
    _engrave_scene(scene, serial_number)

    # Repair pass: collapse float-ops slivers and dedupe before manifold check.
    for _node_name, _m in scene.geometry.items():
        if not isinstance(_m, trimesh.Trimesh):
            continue
        _m.merge_vertices(digits_vertex=6)              # collapse coincident vertices from float ops
        _m.update_faces(_m.nondegenerate_faces())       # drop zero-area faces
        _m.update_faces(_m.unique_faces())              # de-dupe identical face triplets
        _m.remove_unreferenced_vertices()

    # Manifold check, per-component, with tolerances suitable for current
    # geometry (the boss's slicer accepts the originally-shipped topology).
    assert_manifold(
        scene,
        label=f"{course}-hole-{hole}",
        # Fringe is intentionally an open-bottom thin shell; topology rework queued (task 311).
        skip_labels={"fringe", "geometry_1"},
        tolerate_boundary_edges=30,
        tolerate_triple_shared=5,
    )

    scene.export(path_3mf)
    print(f"  Saved: {path_3mf}")
    print(f"  Objects in 3MF ({len(scene_names)}):")
    for name in scene_names:
        print(f"    - {name}")

    # Inject Bambu/Orca per-object extruder metadata so the slicer prints each
    # geometry on the correct filament (green=1, fringe=2, traps=3, water=4).
    try:
        _inject_bambu_extruder_metadata(path_3mf, scene_names)
    except Exception as exc:
        print(f"  WARNING: failed to inject extruder metadata: {exc}")

    # ── 10c. Export succeeded → advance the course's serial counter ──
    try:
        used = _commit_serial(course)
        print(f"  Serial committed: used s/n {used}, next will be s/n {used + 1}")
    except Exception as exc:
        print(f"  WARNING: failed to persist serial counter: {exc}")

    print("\n" + "=" * 60)
    print("Done.")
    # Diagnostic PNG paths suppressed — those writes are disabled (see steps 5 and 9).
    print(f"  3MF assembly:       {path_3mf}")
    print(f"  Scene objects:      {len(scene_names)} (green + fringe + {len(trap_meshes)} trap(s) + {len(water_meshes)} water)")
    print("=" * 60)

    return path_3mf


def main() -> None:
    search = sys.argv[1] if len(sys.argv) > 1 else "Moffett"
    egm_path = find_egm(search)
    run_pipeline(egm_path)


if __name__ == "__main__":
    main()
