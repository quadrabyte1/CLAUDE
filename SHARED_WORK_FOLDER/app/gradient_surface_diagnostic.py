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
import matplotlib.colors as mcolors
from scipy.sparse import lil_matrix
from scipy.sparse.linalg import spsolve
from scipy.spatial import cKDTree
import trimesh
from shapely.geometry import Polygon as ShapelyPolygon
from skimage import measure

from generate_stl_3mf import interpolate_catmull_rom, course_paths, EGM_BASE

# ---------------------------------------------------------------------------
# Paths
# ---------------------------------------------------------------------------

REPO_ROOT = os.path.normpath(os.path.join(os.path.dirname(__file__), ".."))
OWNER_INBOX = os.path.join(REPO_ROOT, "owner_inbox")
TEAM_INBOX  = os.path.join(REPO_ROOT, "team_inbox")

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
    grid_res = rows  # square grid assumed

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


def _build_heightmap_mesh(
    Z_mm: np.ndarray,
    xs_grid: np.ndarray,
    ys_grid: np.ndarray,
    inside_mask: np.ndarray,
    green_boundary_px: np.ndarray,
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
    for (a, b), cnt in edge_count.items():
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


def drill_flag_hole(mesh: "trimesh.Trimesh", diameter: float = 2.5) -> "trimesh.Trimesh":
    """
    Subtract a vertical cylindrical hole through the XY center of the mesh.

    The cylinder spans from Z=-1 to Z=max_Z+1 to ensure it punches all the
    way through regardless of surface height variation.

    Parameters
    ----------
    mesh     : watertight trimesh.Trimesh in mm coordinates
    diameter : hole diameter in mm (default 2.5 mm for a standard flag pin)

    Returns
    -------
    trimesh.Trimesh with the hole drilled
    """
    import trimesh.creation
    import trimesh.boolean

    # --- Find XY center of the mesh bounding box ---
    bb = mesh.bounds  # shape (2, 3): [[xmin,ymin,zmin],[xmax,ymax,zmax]]
    cx = (bb[0, 0] + bb[1, 0]) / 2.0
    cy = (bb[0, 1] + bb[1, 1]) / 2.0
    z_max = bb[1, 2]

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
    smooth_out: str,
    stepped_out: str,
) -> "trimesh.Trimesh":
    """Build and save smooth and stepped STL files. Returns the smooth mesh."""
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
    print("  Drilling 3.0mm flag hole at green center…")
    print("  [smooth]")
    smooth_mesh = drill_flag_hole(smooth_mesh, diameter=3.0)
    print("  [stepped]")
    stepped_mesh = drill_flag_hole(stepped_mesh, diameter=3.0)

    # --- Export ---
    os.makedirs(os.path.dirname(smooth_out), exist_ok=True)
    smooth_mesh.export(smooth_out)
    print(f"  Saved: {smooth_out}")

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
    - Excludes sand trap polygons
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
    green_bnd_mm_closed = np.vstack([green_bnd_mm, green_bnd_mm[0:1]])  # for polyline dist

    # --- Collect trap polygons in mm coords ---
    trap_polys_mm: list[np.ndarray] = []
    trap_shapely: list[ShapelyPolygon] = []
    for poly in egm_data.get("polygons", []):
        if poly.get("type") == "trap":
            # poly["points"] is a list of {"x": float, "y": float} dicts
            try:
                pts_px = interpolate_catmull_rom(poly["points"])
            except Exception:
                pts_px = np.array([[p["x"], p["y"]] for p in poly["points"]], dtype=np.float64)
            pts_mm = _px_to_mm_2d(pts_px, scale, centroid_px)
            trap_polys_mm.append(pts_mm)
            try:
                trap_shapely.append(ShapelyPolygon(pts_mm))
            except Exception:
                pass

    # --- Build Shapely green polygon for point-in-polygon tests ---
    green_shapely = ShapelyPolygon(green_bnd_mm)
    if not green_shapely.is_valid:
        green_shapely = green_shapely.buffer(0)

    # Union all traps
    if trap_shapely:
        from shapely.ops import unary_union
        traps_union = unary_union(trap_shapely)
    else:
        traps_union = None

    print(f"  Fringe grid: {fringe_grid_res}x{fringe_grid_res} over ±{half:.2f} mm")
    print(f"  Green boundary: {len(green_bnd_mm)} mm-space points")
    print(f"  Trap polygons: {len(trap_polys_mm)}")
    if holes:
        print(f"  Baked holes: {holes}")

    # --- Build fringe mask and height array ---
    # fringe_mask[r, c] = True iff cell is in the fringe region
    fringe_mask = np.zeros((fringe_grid_res, fringe_grid_res), dtype=bool)
    Z_fringe = np.full((fringe_grid_res, fringe_grid_res), np.nan)

    # Pre-build KD-tree of valid green grid cells for fast Z lookups
    valid_rows_g, valid_cols_g = np.where(inside_mask)
    green_cell_xy = np.column_stack([xs_mm_green[valid_cols_g], ys_mm_green[valid_rows_g]])
    green_cell_z  = Z_mm[valid_rows_g, valid_cols_g]
    green_kd = cKDTree(green_cell_xy)

    # Pre-build array of green boundary points in mm for vectorised dist
    gbnd = green_bnd_mm  # (N, 2)

    for r in range(fringe_grid_res):
        for c in range(fringe_grid_res):
            x = float(xs_mm[c])
            y = float(ys_mm[r])

            # Must be INSIDE the print rectangle (always true by construction)
            # Must be OUTSIDE the green
            pt = ShapelyPolygon([(x-0.001, y), (x, y+0.001), (x+0.001, y), (x, y-0.001)])  # tiny point approx
            # Use Shapely contains for green check (faster than cv2 here)
            from shapely.geometry import Point as ShapelyPoint
            sp = ShapelyPoint(x, y)
            if green_shapely.contains(sp):
                continue  # inside green → skip

            # Must be OUTSIDE all traps
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

    inner_boundary_rows = []
    inner_boundary_cols = []
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
    return mesh


def _verify_fringe_boundary(
    fringe_mesh: trimesh.Trimesh,
    Z_mm: np.ndarray,
    xs_grid: np.ndarray,
    ys_grid: np.ndarray,
    inside_mask: np.ndarray,
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
    xs_mm_green = (xs_grid - centroid_px[0]) * scale
    ys_mm_green = -(ys_grid - centroid_px[1]) * scale
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


def export_trap_stls(
    egm_data: dict,
    green_boundary_px: np.ndarray,
    slug: str,
    fringe_mesh: "trimesh.Trimesh | None" = None,
    stl_dir: str | None = None,
) -> list[str]:
    """
    For every polygon of type 'trap' in egm_data, build a flat inset slab
    and export it as {stl_dir}/{slug}_trap_N.stl.

    stl_dir defaults to the course's STLs/ folder (via course_paths), falling
    back to OWNER_INBOX if the course is unknown.

    Uses Catmull-Rom interpolation (matching the editor), applies the same
    px→mm transform as the green, insets by PRINT_TOLERANCE_MM, and extrudes
    to a height derived from the fringe mesh at the trap centroid (falls back
    to TRAP_THICKNESS_MM if fringe_mesh is unavailable).

    Returns a list of written file paths.
    """
    from scipy.spatial import cKDTree as _cKDTree
    from shapely.geometry import Point as ShapelyPoint

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

    written: list[str] = []
    for i, trap_poly in enumerate(trap_polygons, start=1):
        try:
            # Interpolate outline with Catmull-Rom (closed spline, matching editor)
            pts_px = interpolate_catmull_rom(trap_poly["points"])

            # Convert pixel coords → mm, Y-flipped
            pts_mm = _px_to_mm_2d(pts_px, scale, centroid_px)

            # Apply tolerance inset using Shapely
            shapely_trap = ShapelyPolygon(pts_mm)
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

            # Apply sand grain texture to the top face
            apply_sand_texture(mesh, trap_index=i)

            out_path = os.path.join(stl_dir, f"{slug}_trap_{i}.stl")
            mesh.export(out_path)

            bb = mesh.bounds
            print(f"  Trap {i}: {len(mesh.vertices)} verts, {len(mesh.faces)} faces, "
                  f"watertight={mesh.is_watertight}, "
                  f"X[{bb[0,0]:.1f},{bb[1,0]:.1f}] Y[{bb[0,1]:.1f},{bb[1,1]:.1f}] mm")
            print(f"  Saved: {out_path}")
            written.append(out_path)

        except Exception as exc:
            import traceback
            print(f"  ERROR exporting trap {i}: {exc}")
            traceback.print_exc()

    return written


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
    from shapely.geometry import Polygon as ShapelyPolygon, MultiPolygon, Point

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

    # Chain boundary edges into an ordered polygon ring.
    adjacency: dict = {}
    for a, b in boundary_edges:
        adjacency.setdefault(a, []).append(b)

    ring: list = []
    start = boundary_edges[0][0]
    current = start
    visited = set()
    while True:
        ring.append(current)
        visited.add(current)
        neighbors = [n for n in adjacency.get(current, []) if n not in visited]
        if not neighbors:
            break
        current = neighbors[0]

    ring_xy = all_verts[ring, :2]                     # (R, 2) — XY of boundary
    shapely_poly = ShapelyPolygon(ring_xy)
    if not shapely_poly.is_valid:
        shapely_poly = shapely_poly.buffer(0)         # fix self-intersections

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
    from shapely import prepare, contains_xy
    prepare(shapely_poly)
    inside_mask = contains_xy(shapely_poly, grid_xy[:, 0], grid_xy[:, 1])
    grid_xy_in  = grid_xy[inside_mask]                # (M, 2) — interior grid pts

    if len(grid_xy_in) < 3:
        print(f"    apply_sand_texture: too few grid points inside polygon ({len(grid_xy_in)}), skipping.")
        return mesh

    n_grid = len(grid_xy_in)
    print(f"    Sand texture grid: step={grid_step:.3f} mm, "
          f"bbox {x_max-x_min:.1f}×{y_max-y_min:.1f} mm → "
          f"{len(xs)}×{len(ys)} candidates → {n_grid} inside polygon")

    # Enforce vertex budget: 150 K per trap.
    MAX_GRID_PTS = 150_000
    if n_grid > MAX_GRID_PTS:
        scale    = math.sqrt(n_grid / MAX_GRID_PTS)
        new_step = grid_step * scale
        print(f"    Sand texture: grid too large ({n_grid} pts); "
              f"increasing step {grid_step:.3f} → {new_step:.3f} mm")
        grid_step = new_step
        xs = np.arange(x_min, x_max + grid_step, grid_step)
        ys = np.arange(y_min, y_max + grid_step, grid_step)
        gx, gy = np.meshgrid(xs, ys)
        grid_xy = np.column_stack([gx.ravel(), gy.ravel()])
        inside_mask = contains_xy(shapely_poly, grid_xy[:, 0], grid_xy[:, 1])
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
    ring_xy_arr = all_verts[ring, :2]                 # (R, 2)
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
    ring_global   = np.array(ring)                             # (R,) global indices
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
    z_max = verts[:, 2].max()
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
    print(f"    Height range: {valid.min():.4f} .. {valid.max():.4f}")

    # ── Build filename slug from course + hole ────────────────────────────────
    import re
    course = _egm_data.get("course", "unknown")
    hole = _egm_data.get("hole", "0")
    slug = re.sub(r"[^a-z0-9]+", "_", f"{course}_hole_{hole}".lower()).strip("_")
    print(f"    File slug: {slug}")

    # ── Resolve output directories from course_paths ─────────────────────────
    _cpaths = course_paths(course) if course != "unknown" else None
    _stl_dir  = _cpaths["stls"]   if _cpaths else OWNER_INBOX
    _3mf_dir  = _cpaths["3mfs"]   if _cpaths else OWNER_INBOX
    _img_dir  = _cpaths["images"] if _cpaths else OWNER_INBOX
    os.makedirs(_stl_dir,  exist_ok=True)
    os.makedirs(_3mf_dir,  exist_ok=True)
    os.makedirs(_img_dir,  exist_ok=True)

    # ── 5. Save diagnostic images ───────────────────────────────────────────
    print("\n[5] Saving diagnostic images…")

    arrow_out = os.path.join(_img_dir, f"{slug}_arrow_directions.png")
    save_arrow_directions(img, arrows, green_boundary_px, arrow_out)

    height_out = os.path.join(_img_dir, f"{slug}_height_map.png")
    save_height_map(Z, xs_grid, ys_grid, green_boundary_px, height_out)

    # ── 6. Build STL meshes ─────────────────────────────────────────────────
    print("\n[6] Building STL meshes…")
    smooth_stl_flat = os.path.join(_stl_dir, f"{slug}_smooth_surface_flat.stl")
    smooth_stl = os.path.join(_stl_dir, f"{slug}_smooth_surface.stl")
    stepped_stl = os.path.join(_stl_dir, f"{slug}_stepped_surface.stl")
    smooth_mesh_flat, stepped_mesh = save_stl_meshes(
        Z, xs_grid, ys_grid, inside_mask, green_boundary_px,
        _egm_data, smooth_stl_flat, stepped_stl
    )

    # ── 6b. Apply grass texture to smooth mesh ──────────────────────────────
    grass_amplitude = _egm_data.get("grassAmplitude", 0.5)
    grass_spacing   = _egm_data.get("grassSpacing",   2.4)
    print(f"\n[6b] Applying grass texture (amplitude={grass_amplitude} mm, spacing={grass_spacing} mm)…")
    import copy
    smooth_mesh = copy.deepcopy(smooth_mesh_flat)
    apply_grass_texture(smooth_mesh, amplitude=grass_amplitude, bump_spacing=grass_spacing)
    os.makedirs(os.path.dirname(smooth_stl), exist_ok=True)
    smooth_mesh.export(smooth_stl)
    print(f"    Saved textured smooth surface: {smooth_stl}")

    # ── 7. Build fringe mesh ────────────────────────────────────────────────
    print("\n[7] Building fringe mesh…")
    scale_f, centroid_f = _compute_px_to_mm(green_boundary_px, _egm_data)
    Z_mm_for_fringe = _height_to_mm(Z, inside_mask)
    fringe_stl = os.path.join(_stl_dir, f"{slug}_fringe.stl")
    fringe_mesh = None
    fringe_mesh_flat = None   # kept for trap height sampling (no texture perturbation)
    # Compute hole position for bored cylinder in fringe.
    # Use the expanded half so the stand hole stays at the correct corner offset.
    _half = PRINT_SIZE_MM / 2.0 + FRINGE_XY_EXPANSION_MM / 2.0
    stand_x = -_half + 20.0
    stand_y = +_half - 20.0
    HOLE_RADIUS = 2.38125  # 4.7625 mm diameter bored cylinder (3/16 in)
    fringe_holes = [(stand_x, stand_y, HOLE_RADIUS)]
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
        # Save untextured fringe flat copy before applying grass texture
        fringe_flat_stl = os.path.join(_stl_dir, f"{slug}_fringe_flat.stl")
        fringe_mesh.export(fringe_flat_stl)
        print(f"  Saved untextured fringe flat: {fringe_flat_stl}")
        # Keep a reference to the flat fringe for trap height sampling
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
        fringe_mesh.export(fringe_stl)
        print(f"  Saved: {fringe_stl}")
    except Exception as exc:
        print(f"  ERROR building fringe mesh: {exc}")
        import traceback; traceback.print_exc()
        fringe_stl = "(failed)"

    # ── 8. Export sand trap STLs ────────────────────────────────────────────
    print("\n[8] Exporting sand trap STLs…")
    trap_stl_paths = export_trap_stls(_egm_data, green_boundary_px, slug,
                                      fringe_mesh=fringe_mesh_flat,
                                      stl_dir=_stl_dir)
    if not trap_stl_paths:
        print("  (no traps exported)")

    # ── 9. Contour debug image ──────────────────────────────────────────────
    print("\n[9] Saving contour lines debug image…")
    contour_out = os.path.join(_img_dir, f"{slug}_gradient_contours.png")
    save_contour_debug_image(
        Z, xs_grid, ys_grid, inside_mask, img, green_boundary_px, contour_out
    )

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

    # Trap meshes — reload from saved STL paths
    for trap_path in trap_stl_paths:
        trap_name = os.path.splitext(os.path.basename(trap_path))[0]
        # Extract just the trap suffix (e.g. "trap_1") for a clean node name
        trap_node = trap_name.replace(slug + "_", "")
        try:
            trap_mesh = trimesh.load(trap_path, force="mesh")
            scene.add_geometry(trap_mesh, node_name=trap_node)
            scene_names.append(trap_node)
        except Exception as exc:
            print(f"  WARNING: could not load trap mesh {trap_path}: {exc}")

    print(f"\n[10b] Engraving serial s/n: {serial_number} on {len(scene_names)} item(s)…")
    _engrave_scene(scene, serial_number)

    scene.export(path_3mf)
    print(f"  Saved: {path_3mf}")
    print(f"  Objects in 3MF ({len(scene_names)}):")
    for name in scene_names:
        print(f"    - {name}")

    # ── 10c. Export succeeded → advance the course's serial counter ──
    try:
        used = _commit_serial(course)
        print(f"  Serial committed: used s/n {used}, next will be s/n {used + 1}")
    except Exception as exc:
        print(f"  WARNING: failed to persist serial counter: {exc}")

    print("\n" + "=" * 60)
    print("Done.")
    print(f"  Arrow directions:   {arrow_out}")
    print(f"  Height map:         {height_out}")
    print(f"  Contour debug:      {contour_out}")
    print(f"  Smooth surface STL: {smooth_stl}  (grass-textured)")
    print(f"  Smooth flat STL:    {smooth_stl_flat}  (untextured reference)")
    print(f"  Stepped surface STL:{stepped_stl}")
    print(f"  Fringe STL:         {fringe_stl}  (grass-textured, 4.7625mm hole)")
    for p in trap_stl_paths:
        print(f"  Trap STL:           {p}")
    print(f"  3MF assembly:       {path_3mf}")
    print("=" * 60)

    return path_3mf


def main() -> None:
    search = sys.argv[1] if len(sys.argv) > 1 else "Moffett"
    egm_path = find_egm(search)
    run_pipeline(egm_path)


if __name__ == "__main__":
    main()
