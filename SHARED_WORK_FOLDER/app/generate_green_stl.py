#!/usr/bin/env python3
"""
Generate TWO 3D-printable STLs of the Moffett Field G.C. Hole 7 green
from a GolfLogix contour screenshot:
  1. The putting surface (inside the black boundary line)
  2. The fringe (outside the black boundary but inside the overall green complex)

Strategy (ARROW-BASED — no color elevation):
1. Extract a robust green mask (convex hull to avoid bite-outs).
2. Detect the BLACK BOUNDARY LINE to separate putting surface from fringe.
3. Detect arrows — small dark graphical overlays. Find their positions
   and the direction each arrow points (= downhill direction).
4. Find the lowest point — where arrows converge / point toward.
5. Build elevation by integrating UPSTREAM against the arrow flow:
   further from the drain = higher elevation.
6. Smooth into a natural surface and generate TWO STL files.
"""

import cv2
import numpy as np
from scipy.ndimage import gaussian_filter, binary_fill_holes
from scipy.interpolate import RBFInterpolator
from stl import mesh as stl_mesh
import os

# -- Paths -----------------------------------------------------------------
INPUT = "/Users/fourierflight/GIT/CLAUDE-GitHub/SHARED_WORK_FOLDER/team_inbox/Moffet 7.png"
OUTPUT_GREEN = "/Users/fourierflight/GIT/CLAUDE-GitHub/SHARED_WORK_FOLDER/owner_inbox/moffett_7_green.stl"
OUTPUT_FRINGE = "/Users/fourierflight/GIT/CLAUDE-GitHub/SHARED_WORK_FOLDER/owner_inbox/moffett_7_fringe.stl"

# -- Parameters ------------------------------------------------------------
PRINT_SIZE_MM = 178.0        # 7 inches
BASE_THICKNESS_MM = 4.0      # flat base
VERT_EXAGGERATION = 2.5      # so slopes are visible at print scale
MAX_ELEVATION_MM = 12.0      # max height above base
SMOOTH_SIGMA = 6.0           # Gaussian smoothing for the heightmap

# -- 1. Load and crop to green region --------------------------------------
img = cv2.imread(INPUT)
if img is None:
    raise FileNotFoundError(f"Cannot read {INPUT}")

h, w = img.shape[:2]
print(f"Image size: {w}x{h}")

# The green oval is roughly in the center-upper portion of the image.
# Expanded crop to include full bunker extents (bunkers can extend beyond the green).
x1, x2 = int(w * 0.10), int(w * 0.96)
y1, y2 = int(h * 0.10), int(h * 0.63)
crop = img[y1:y2, x1:x2].copy()
ch, cw = crop.shape[:2]
print(f"Crop size: {cw}x{ch}")

# -- 2. Build a ROBUST mask of the green area ------------------------------
hsv = cv2.cvtColor(crop, cv2.COLOR_BGR2HSV)
sat = hsv[:, :, 1].astype(float)
val = hsv[:, :, 2].astype(float)

# Pick up both saturated color pixels and bright white/light pixels
mask_color = (sat > 40) & (val > 60)
mask_white = (sat < 50) & (val > 170)
mask = mask_color | mask_white

# Aggressive morphological closing to seal any gaps
kernel_large = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (15, 15))
kernel_small = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (7, 7))
mask_u8 = (mask.astype(np.uint8)) * 255
mask_u8 = cv2.morphologyEx(mask_u8, cv2.MORPH_CLOSE, kernel_large, iterations=5)
mask_u8 = cv2.morphologyEx(mask_u8, cv2.MORPH_OPEN, kernel_small, iterations=2)

# Keep only the largest connected component
n_labels, labels, stats, centroids = cv2.connectedComponentsWithStats(mask_u8)
if n_labels > 1:
    areas = stats[1:, cv2.CC_STAT_AREA]
    largest = 1 + np.argmax(areas)
    mask_u8 = ((labels == largest) * 255).astype(np.uint8)

# Fill internal holes
mask_bool = binary_fill_holes(mask_u8 > 0)

# Save the pre-hull mask (needed for bunker detection later)
mask_pre_hull = mask_bool.copy()

# CONVEX HULL to fix the upper-right "bite" and any other concavities
mask_for_hull = (mask_bool.astype(np.uint8)) * 255
contours_hull, _ = cv2.findContours(mask_for_hull, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
if contours_hull:
    biggest_contour = max(contours_hull, key=cv2.contourArea)
    hull = cv2.convexHull(biggest_contour)
    hull_mask = np.zeros((ch, cw), dtype=np.uint8)
    cv2.drawContours(hull_mask, [hull], -1, 255, -1)
    mask_bool = hull_mask > 0

mask_u8 = (mask_bool.astype(np.uint8)) * 255
print(f"Green mask pixels (after convex hull): {np.count_nonzero(mask_u8)}")

# ==========================================================================
# -- 2a. DETECT BLACK BOUNDARY LINE (putting surface vs fringe) ------------
# ==========================================================================
print("\n=== PUTTING SURFACE vs FRINGE SEPARATION ===")

# Strategy: The colorful contour lines (red/yellow/green/blue) exist ONLY
# inside the putting surface. The fringe has no contour colors -- it is a
# uniform dark/muted green. Detect colorful + bright pixels and close them
# morphologically to define the putting surface boundary.

hsv_crop = cv2.cvtColor(crop, cv2.COLOR_BGR2HSV)
hue_crop = hsv_crop[:, :, 0].astype(float)
sat_crop = hsv_crop[:, :, 1].astype(float)
val_crop = hsv_crop[:, :, 2].astype(float)

# Step 1: Detect contour-colored pixels (highly saturated and/or bright)
# Core: very saturated pixels (all contour line colors)
core_contour = mask_bool & (sat_crop > 120) & (val_crop > 50)
# Extended: moderately saturated AND bright (lighter contour bands between lines)
extended_contour = mask_bool & (sat_crop > 60) & (val_crop > 100)
all_contour = core_contour | extended_contour
all_contour_u8 = all_contour.astype(np.uint8) * 255
print(f"Contour pixels detected: {np.count_nonzero(all_contour_u8)} "
      f"({np.count_nonzero(all_contour_u8) / max(1, np.count_nonzero(mask_u8)):.1%} of green)")

# Step 2: Aggressively close to fill gaps between contour bands
kernel_close_ps = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (25, 25))
putting_filled = cv2.morphologyEx(all_contour_u8, cv2.MORPH_CLOSE,
                                   kernel_close_ps, iterations=4)
putting_filled = binary_fill_holes(putting_filled > 0)
putting_filled_u8 = (putting_filled.astype(np.uint8)) * 255

# Keep only the largest connected component
n_pf, pf_labels, pf_stats, _ = cv2.connectedComponentsWithStats(putting_filled_u8)
if n_pf > 1:
    pf_areas = pf_stats[1:, cv2.CC_STAT_AREA]
    pf_largest = 1 + np.argmax(pf_areas)
    putting_filled_u8 = ((pf_labels == pf_largest) * 255).astype(np.uint8)

# Step 3: Smooth edges
kernel_smooth_ps = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (11, 11))
putting_smooth_ps = cv2.morphologyEx(putting_filled_u8, cv2.MORPH_CLOSE,
                                      kernel_smooth_ps, iterations=2)
putting_smooth_ps = cv2.morphologyEx(putting_smooth_ps, cv2.MORPH_OPEN,
                                      kernel_smooth_ps, iterations=1)

putting_mask_bool = (putting_smooth_ps > 0) & mask_bool
fringe_mask_bool = mask_bool & (~putting_mask_bool)

putting_pct = np.count_nonzero(putting_mask_bool) / max(1, np.count_nonzero(mask_u8))
fringe_pct = np.count_nonzero(fringe_mask_bool) / max(1, np.count_nonzero(mask_u8))
print(f"Putting surface pixels: {np.count_nonzero(putting_mask_bool)} ({putting_pct:.1%})")
print(f"Fringe pixels: {np.count_nonzero(fringe_mask_bool)} ({fringe_pct:.1%})")

# Sanity check: if fringe is negligible, fall back to erosion
if fringe_pct < 0.03:
    print("WARNING: Fringe too small. Using erosion fallback.")
    kernel_erode_fb = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (20, 20))
    eroded = cv2.erode(mask_u8, kernel_erode_fb, iterations=2) > 0
    eroded = binary_fill_holes(eroded)
    putting_mask_bool = eroded & mask_bool
    fringe_mask_bool = mask_bool & (~putting_mask_bool)
    putting_pct = np.count_nonzero(putting_mask_bool) / max(1, np.count_nonzero(mask_u8))
    fringe_pct = np.count_nonzero(fringe_mask_bool) / max(1, np.count_nonzero(mask_u8))
    print(f"Putting (erosion): {np.count_nonzero(putting_mask_bool)} ({putting_pct:.1%})")
    print(f"Fringe (erosion): {np.count_nonzero(fringe_mask_bool)} ({fringe_pct:.1%})")

# ==========================================================================
# -- 2b. DETECT SAND BUNKERS around the green ------------------------------
# ==========================================================================
print("\n=== BUNKER DETECTION ===")

# Strategy: Detect bunkers by their sandy/tan color on the FULL image.
# Sandy pixels have: Hue ~10-30 (OpenCV 0-180 scale), moderate Sat ~20-120, V > 100.
# Then filter by size and proximity to the green.

hsv_full = cv2.cvtColor(img, cv2.COLOR_BGR2HSV)
hue_full = hsv_full[:, :, 0].astype(float)
sat_full = hsv_full[:, :, 1].astype(float)
val_full = hsv_full[:, :, 2].astype(float)

# Build a tight green mask on the FULL image (high saturation = putting surface)
green_tight = (sat_full > 120) & (val_full > 50)
green_tight_u8 = green_tight.astype(np.uint8) * 255
kernel_gt = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (15, 15))
green_tight_u8 = cv2.morphologyEx(green_tight_u8, cv2.MORPH_CLOSE, kernel_gt, iterations=3)
green_tight_u8 = cv2.morphologyEx(green_tight_u8, cv2.MORPH_OPEN, kernel_gt, iterations=2)
# Keep largest component only
n_gt, gt_labels, gt_stats, _ = cv2.connectedComponentsWithStats(green_tight_u8)
if n_gt > 1:
    gt_areas = gt_stats[1:, cv2.CC_STAT_AREA]
    gt_largest = 1 + np.argmax(gt_areas)
    green_tight_u8 = ((gt_labels == gt_largest) * 255).astype(np.uint8)
green_tight_mask = binary_fill_holes(green_tight_u8 > 0)

# Green centroid in full image coords
gys_full, gxs_full = np.where(green_tight_mask)
green_cx_full = gxs_full.mean()
green_cy_full = gys_full.mean()
print(f"Green centroid (full img): ({green_cx_full:.0f}, {green_cy_full:.0f})")

# Detect sandy/tan colored pixels (bunker color)
sandy_mask = ((hue_full >= 10) & (hue_full <= 30) &
              (sat_full >= 20) & (sat_full <= 120) &
              (val_full >= 100))

# Exclude the putting surface itself
sandy_mask = sandy_mask & (~green_tight_mask)

# Exclude UI areas (bottom bar and top header)
y_ui_limit = int(h * 0.65)
sandy_mask[y_ui_limit:, :] = False
sandy_mask[:int(h * 0.08), :] = False

# Morphological cleanup
sandy_u8 = sandy_mask.astype(np.uint8) * 255
kernel_bc = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (5, 5))
sandy_u8 = cv2.morphologyEx(sandy_u8, cv2.MORPH_CLOSE, kernel_bc, iterations=2)
sandy_u8 = cv2.morphologyEx(sandy_u8, cv2.MORPH_OPEN, kernel_bc, iterations=2)

# Find connected components, filter by size
n_bf, bf_labels, bf_stats, bf_cents = cv2.connectedComponentsWithStats(sandy_u8)

MIN_BUNKER_AREA = 3000
MAX_BUNKER_AREA = 50000

bunker_mask_full = np.zeros((h, w), dtype=bool)
bunker_count = 0

print(f"Sandy-color candidate components (area >= {MIN_BUNKER_AREA}): ", end="")
candidates = sum(1 for lbl in range(1, n_bf) if bf_stats[lbl, cv2.CC_STAT_AREA] >= MIN_BUNKER_AREA)
print(candidates)

for lbl in range(1, n_bf):
    area = bf_stats[lbl, cv2.CC_STAT_AREA]
    if area < MIN_BUNKER_AREA or area > MAX_BUNKER_AREA:
        continue

    cx_bf = bf_cents[lbl, 0]
    cy_bf = bf_cents[lbl, 1]

    # Compute clock position relative to green center
    rel_x = cx_bf - green_cx_full
    rel_y = -(cy_bf - green_cy_full)  # flip y for standard math
    angle_deg = np.degrees(np.arctan2(rel_y, rel_x))
    clock_pos = ((90 - angle_deg) % 360) / 30

    # Skip regions near 12 o'clock (11.5-0.5) and 6 o'clock (5.5-6.5)
    # — these are likely UI overlays, yardage markers, or path artifacts
    if clock_pos < 0.5 or clock_pos > 11.5:
        print(f"  SKIPPED component at ({cx_bf:.0f}, {cy_bf:.0f}), "
              f"area={area}, ~{clock_pos:.1f} o'clock (likely UI element)")
        continue

    bunker_mask_full |= (bf_labels == lbl)
    bunker_count += 1
    bx = bf_stats[lbl, cv2.CC_STAT_LEFT]
    by = bf_stats[lbl, cv2.CC_STAT_TOP]
    bw = bf_stats[lbl, cv2.CC_STAT_WIDTH]
    bh = bf_stats[lbl, cv2.CC_STAT_HEIGHT]
    print(f"  Bunker {bunker_count}: centroid=({cx_bf:.0f}, {cy_bf:.0f}), "
          f"area={area} px, ~{clock_pos:.1f} o'clock, "
          f"bbox=({bx},{by})-({bx+bw},{by+bh})")

print(f"Bunkers found: {bunker_count}")
print(f"Total bunker pixels (full image): {np.count_nonzero(bunker_mask_full)}")

# Map bunker mask from full image to crop coordinates
bunker_in_crop = bunker_mask_full[y1:y2, x1:x2]

# Build a tight green mask in crop coords
green_tight_crop = green_tight_mask[y1:y2, x1:x2]

# A bunker pixel is valid if it's in the bunker mask AND NOT on the putting surface
bunker_mask_bool = bunker_in_crop & (~green_tight_crop)
bunker_mask_u8 = (bunker_mask_bool.astype(np.uint8)) * 255
print(f"Bunker pixels in crop: {np.count_nonzero(bunker_mask_u8)}")

# Carve bunker areas out of the green mask so they don't overlap
mask_bool = mask_bool & (~bunker_mask_bool)
mask_u8 = (mask_bool.astype(np.uint8)) * 255
print(f"Green mask pixels (after bunker carve-out): {np.count_nonzero(mask_u8)}")

# Build a COMBINED mask (green + bunkers) for mesh generation
combined_mask_bool = mask_bool | bunker_mask_bool
combined_mask_u8 = (combined_mask_bool.astype(np.uint8)) * 255
print(f"Combined mask pixels (green + bunkers): {np.count_nonzero(combined_mask_u8)}")

# ==========================================================================
# -- 3. DETECT ARROWS: position + direction --------------------------------
# ==========================================================================
print("\n=== ARROW DETECTION ===")

gray = cv2.cvtColor(crop, cv2.COLOR_BGR2GRAY)

# Erode the mask inward to avoid detecting boundary/edge artifacts as arrows
kernel_erode = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (20, 20))
mask_eroded = cv2.erode(mask_u8, kernel_erode, iterations=1) > 0

# Arrows are small dark marks on the brighter background.
# Detect them as locally-dark blobs within the eroded green mask.
local_mean = cv2.blur(gray.astype(np.float32), (21, 21))
dark_diff = local_mean - gray.astype(np.float32)
dark_diff[~mask_eroded] = 0

# Threshold for dark pixels relative to their neighborhood
arrow_candidate = (dark_diff > 30).astype(np.uint8) * 255

# Clean: remove tiny noise
kernel_tiny = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (2, 2))
arrow_candidate = cv2.morphologyEx(arrow_candidate, cv2.MORPH_OPEN, kernel_tiny, iterations=1)

# Slight dilation to connect arrow parts
kernel_connect = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (2, 2))
arrow_raw = cv2.dilate(arrow_candidate, kernel_connect, iterations=1)

# Filter connected components by size: arrows are small (not contour lines)
green_area = np.count_nonzero(mask_u8)
min_arrow_area = 30      # at least 30 px (filter noise)
max_arrow_area = 600     # arrows are small; contour fragments are larger

n_cc, cc_labels, cc_stats, cc_centroids = cv2.connectedComponentsWithStats(arrow_raw)

arrow_blobs = []  # list of (centroid_x, centroid_y, direction_x, direction_y)

print(f"Connected components found: {n_cc - 1}")
print(f"Arrow area filter: {min_arrow_area} - {max_arrow_area} pixels")

kept_mask = np.zeros_like(arrow_raw)

for lbl in range(1, n_cc):
    area = cc_stats[lbl, cv2.CC_STAT_AREA]
    if area < min_arrow_area or area > max_arrow_area:
        continue

    # Get pixels for this blob
    blob_ys, blob_xs = np.where(cc_labels == lbl)

    # Check aspect ratio / elongation — arrows are elongated
    if len(blob_xs) < 5:
        continue

    # Use PCA to find principal axis (elongation direction)
    pts = np.column_stack([blob_xs.astype(np.float64), blob_ys.astype(np.float64)])
    mean_pt = pts.mean(axis=0)
    centered = pts - mean_pt
    cov = np.cov(centered.T)
    eigenvalues, eigenvectors = np.linalg.eigh(cov)

    # eigenvalues are sorted ascending; the larger one is the principal axis
    # Check elongation ratio
    if eigenvalues[0] < 1e-6:
        elongation = 100.0
    else:
        elongation = eigenvalues[1] / eigenvalues[0]

    # Arrows should be elongated (ratio > 2.0)
    if elongation < 2.0:
        continue

    # Principal direction (the larger eigenvalue's eigenvector)
    principal_dir = eigenvectors[:, 1]  # (dx, dy) in image coords

    # Now determine which end is the "tip" (pointed end = downhill direction).
    # Project all blob pixels onto the principal axis
    projections = centered @ principal_dir
    proj_min, proj_max = projections.min(), projections.max()
    proj_mid = (proj_min + proj_max) / 2.0

    # Split blob into two halves along principal axis
    half_neg = projections < proj_mid
    half_pos = projections >= proj_mid

    # The narrower half is the tip (fewer pixels, or smaller spread perpendicular)
    perp_dir = eigenvectors[:, 0]
    perp_neg = (centered[half_neg] @ perp_dir) if half_neg.sum() > 0 else np.array([0])
    perp_pos = (centered[half_pos] @ perp_dir) if half_pos.sum() > 0 else np.array([0])

    spread_neg = np.std(perp_neg) if len(perp_neg) > 1 else 0
    spread_pos = np.std(perp_pos) if len(perp_pos) > 1 else 0

    # The arrowhead (V/chevron shape) is WIDER than the tail shaft.
    # So the arrow points toward the half with LARGER perpendicular spread.
    # Arrow points in the direction of the arrowhead = downhill.
    if spread_neg > spread_pos:
        # Negative projection side is the arrowhead
        arrow_dir = -principal_dir
    else:
        # Positive projection side is the arrowhead
        arrow_dir = principal_dir

    # Normalize direction
    norm = np.linalg.norm(arrow_dir)
    if norm > 0:
        arrow_dir = arrow_dir / norm

    cx, cy = mean_pt
    arrow_blobs.append((cx, cy, arrow_dir[0], arrow_dir[1]))
    kept_mask[cc_labels == lbl] = 255

print(f"Arrows detected (before outlier filtering): {len(arrow_blobs)}")

# === FIX 1: Filter outlier arrows ===
# Compute average direction, then reject arrows that deviate too far from consensus
if len(arrow_blobs) > 0:
    dirs = np.array([(a[2], a[3]) for a in arrow_blobs])
    avg_dir = dirs.mean(axis=0)
    avg_dir_norm = avg_dir / (np.linalg.norm(avg_dir) + 1e-8)
    print(f"Average arrow direction (pre-filter): dx={avg_dir_norm[0]:.3f}, dy={avg_dir_norm[1]:.3f}")

    # Compute dot product of each arrow with the average direction
    OUTLIER_DOT_THRESHOLD = 0.3
    dot_products = dirs[:, 0] * avg_dir_norm[0] + dirs[:, 1] * avg_dir_norm[1]
    keep_mask_arrows = dot_products >= OUTLIER_DOT_THRESHOLD

    n_removed = int((~keep_mask_arrows).sum())
    arrow_blobs_filtered = [a for a, keep in zip(arrow_blobs, keep_mask_arrows) if keep]
    print(f"Outlier arrows removed: {n_removed} (dot threshold={OUTLIER_DOT_THRESHOLD})")
    for i, (a, dp) in enumerate(zip(arrow_blobs, dot_products)):
        if not keep_mask_arrows[i]:
            print(f"  Removed arrow at ({a[0]:.0f}, {a[1]:.0f}), dir=({a[2]:.3f}, {a[3]:.3f}), dot={dp:.3f}")

    arrow_blobs = arrow_blobs_filtered

    # Recompute average direction after filtering
    dirs = np.array([(a[2], a[3]) for a in arrow_blobs])
    avg_dir = dirs.mean(axis=0)
    avg_dir_norm = avg_dir / (np.linalg.norm(avg_dir) + 1e-8)
    print(f"Average arrow direction (post-filter): dx={avg_dir_norm[0]:.3f}, dy={avg_dir_norm[1]:.3f}")
    print(f"Arrows kept: {len(arrow_blobs)}")
    print(f"  (positive dx = rightward, positive dy = downward)")

    positions = np.array([(a[0], a[1]) for a in arrow_blobs])
    print(f"Arrow position range: x=[{positions[:,0].min():.0f}, {positions[:,0].max():.0f}], "
          f"y=[{positions[:,1].min():.0f}, {positions[:,1].max():.0f}]")

# === FIX 2: Add virtual boundary arrows along the perimeter ===
print("\n=== ADDING VIRTUAL BOUNDARY ARROWS ===")
if len(arrow_blobs) > 0:
    # Find the contour of the mask
    contours_bnd, _ = cv2.findContours(mask_u8, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_NONE)
    if contours_bnd:
        boundary_contour = max(contours_bnd, key=cv2.contourArea)
        boundary_pts = boundary_contour.reshape(-1, 2)  # (N, 2) with (x, y)

        # Sample every ~25 pixels along the boundary
        BOUNDARY_SPACING = 25
        n_boundary = len(boundary_pts)
        indices = np.arange(0, n_boundary, BOUNDARY_SPACING)
        sampled_pts = boundary_pts[indices]

        n_virtual = len(sampled_pts)
        virtual_arrows = []
        for pt in sampled_pts:
            bx, by = float(pt[0]), float(pt[1])
            # Virtual arrow points in the average downhill direction
            virtual_arrows.append((bx, by, avg_dir_norm[0], avg_dir_norm[1]))

        arrow_blobs.extend(virtual_arrows)
        print(f"Virtual boundary arrows added: {n_virtual}")
        print(f"Total arrows (real + virtual): {len(arrow_blobs)}")
    else:
        print("WARNING: No contour found for boundary arrows")

# ==========================================================================
# -- 4. BUILD ELEVATION FROM ARROW FLOW ------------------------------------
# ==========================================================================
print("\n=== BUILDING ELEVATION FROM ARROWS ===")

# Get coordinates of all green mask pixels
ys_m, xs_m = np.where(mask_bool)

if len(arrow_blobs) < 3:
    print(f"WARNING: Only {len(arrow_blobs)} arrows detected. Falling back to "
          "directional assumption (upper-right=high, lower-left=low).")
    # Fallback: use assumed slope direction
    # Normalize coordinates
    x_min_mask, x_max_mask = xs_m.min(), xs_m.max()
    y_min_mask, y_max_mask = ys_m.min(), ys_m.max()
    xs_norm = (xs_m - x_min_mask).astype(np.float32) / max(1, x_max_mask - x_min_mask)
    ys_norm = (ys_m - y_min_mask).astype(np.float32) / max(1, y_max_mask - y_min_mask)
    # Upper-right = high: x increases (right), y decreases (up)
    height_raw = np.zeros((ch, cw), dtype=np.float32)
    height_raw[ys_m, xs_m] = 0.6 * xs_norm - 0.4 * ys_norm
    # Shift to 0..1
    hmin = height_raw[mask_bool].min()
    hmax = height_raw[mask_bool].max()
    if hmax > hmin:
        height_raw[mask_bool] = (height_raw[mask_bool] - hmin) / (hmax - hmin)
else:
    # === Step A: Build a dense gradient field from the sparse arrow vectors ===
    # Each arrow gives us a downhill direction vector at its position.
    # The UPHILL direction is the negative of that.
    # We want elevation to increase in the uphill direction.
    #
    # Strategy: interpolate the arrow vectors across the green to get a dense
    # gradient field, then integrate to get elevation.

    arrow_positions = np.array([(a[0], a[1]) for a in arrow_blobs])
    # Uphill gradient = negative of arrow direction (arrows point downhill)
    arrow_uphill = np.array([(-a[2], -a[3]) for a in arrow_blobs])

    # Downsample the mask grid for efficiency
    step = 4  # process every 4th pixel
    yy, xx = np.mgrid[0:ch:step, 0:cw:step]
    yy_flat = yy.ravel()
    xx_flat = xx.ravel()
    # Keep only points inside mask
    in_mask = mask_bool[yy_flat, xx_flat]
    yy_in = yy_flat[in_mask].astype(np.float64)
    xx_in = xx_flat[in_mask].astype(np.float64)

    print(f"Grid points for interpolation: {len(xx_in)}")

    # Interpolate uphill_x and uphill_y separately using RBF
    # Use a smooth RBF kernel so the field is continuous
    smoothing_param = max(50.0, len(arrow_blobs) * 2.0)

    print("Interpolating gradient field from arrows (RBF)...")
    rbf_gx = RBFInterpolator(
        arrow_positions, arrow_uphill[:, 0],
        kernel='thin_plate_spline',
        smoothing=smoothing_param
    )
    rbf_gy = RBFInterpolator(
        arrow_positions, arrow_uphill[:, 1],
        kernel='thin_plate_spline',
        smoothing=smoothing_param
    )

    query_pts = np.column_stack([xx_in, yy_in])
    gx_dense = rbf_gx(query_pts)
    gy_dense = rbf_gy(query_pts)

    print(f"Gradient field computed. gx range: [{gx_dense.min():.3f}, {gx_dense.max():.3f}], "
          f"gy range: [{gy_dense.min():.3f}, {gy_dense.max():.3f}]")

    # === Step B: Find the lowest point ===
    # The lowest point is where arrows converge — trace each arrow downstream
    # and find the convergence zone.
    # Simple approach: the lowest point is the one with the smallest "uphill potential",
    # which we approximate as the point where the dot product of position with
    # average uphill direction is smallest.
    avg_uphill = -avg_dir_norm  # uphill = opposite of average downhill
    print(f"Average uphill direction: dx={avg_uphill[0]:.3f}, dy={avg_uphill[1]:.3f}")

    # Project all grid points onto the average uphill direction
    # Points with lowest projection are the lowest in elevation
    projections = xx_in * avg_uphill[0] + yy_in * avg_uphill[1]
    lowest_idx = np.argmin(projections)
    lowest_x, lowest_y = xx_in[lowest_idx], yy_in[lowest_idx]
    print(f"Estimated lowest point: ({lowest_x:.0f}, {lowest_y:.0f})")

    # === Step C: Integrate the gradient field to get elevation ===
    # Use Poisson-like integration: elevation at each point is proportional to
    # how far "upstream" it is from the lowest point.
    #
    # Simple and robust approach: for each grid point, compute the dot product
    # of its position (relative to the lowest point) with the local uphill gradient.
    # Then refine with iterative relaxation.

    # First pass: project-based elevation estimate
    # For each point, elevation ~ dot(position - lowest_point, local_uphill_direction)
    rel_x = xx_in - lowest_x
    rel_y = yy_in - lowest_y

    # Normalize gradient vectors
    g_mag = np.sqrt(gx_dense**2 + gy_dense**2)
    g_mag = np.maximum(g_mag, 1e-8)
    gx_norm = gx_dense / g_mag
    gy_norm = gy_dense / g_mag

    # Initial elevation: dot product of position with local uphill direction
    elevation_sparse = rel_x * gx_norm + rel_y * gy_norm

    # Shift so minimum is 0
    elevation_sparse -= elevation_sparse.min()

    # Normalize to [0, 1]
    e_max = elevation_sparse.max()
    if e_max > 0:
        elevation_sparse /= e_max

    print(f"Sparse elevation range: [{elevation_sparse.min():.3f}, {elevation_sparse.max():.3f}]")

    # === Step D: Map sparse elevation back to full grid ===
    # Use RBF interpolation from the sparse grid points to the full mask
    print("Interpolating elevation to full grid...")

    rbf_elev = RBFInterpolator(
        np.column_stack([xx_in, yy_in]),
        elevation_sparse,
        kernel='thin_plate_spline',
        smoothing=100.0
    )

    # Query at all mask pixel positions
    all_query = np.column_stack([xs_m.astype(np.float64), ys_m.astype(np.float64)])

    # Process in chunks to avoid memory issues
    chunk_size = 50000
    elevation_full = np.zeros(len(xs_m), dtype=np.float64)
    for start in range(0, len(xs_m), chunk_size):
        end = min(start + chunk_size, len(xs_m))
        elevation_full[start:end] = rbf_elev(all_query[start:end])
        if start % 200000 == 0 and start > 0:
            print(f"  Interpolated {start}/{len(xs_m)} pixels...")

    # Build the heightmap
    height_raw = np.zeros((ch, cw), dtype=np.float32)
    height_raw[ys_m, xs_m] = elevation_full.astype(np.float32)

    # Normalize to [0, 1]
    hmin = height_raw[mask_bool].min()
    hmax = height_raw[mask_bool].max()
    if hmax > hmin:
        height_raw[mask_bool] = (height_raw[mask_bool] - hmin) / (hmax - hmin)

    print(f"Full heightmap range: [{height_raw[mask_bool].min():.3f}, {height_raw[mask_bool].max():.3f}]")

# ==========================================================================
# -- 5. Smooth and finalize heightmap --------------------------------------
# ==========================================================================
print("\n=== SMOOTHING HEIGHTMAP ===")

# Smooth to create a natural surface
height_smooth = gaussian_filter(height_raw, sigma=SMOOTH_SIGMA * 1.5)
height_smooth[~mask_bool] = 0.0

# Second lighter pass for a silky surface
height_smooth = gaussian_filter(height_smooth, sigma=SMOOTH_SIGMA * 0.8)
height_smooth[~mask_bool] = 0.0

# Re-normalize within mask to 0..1
masked_vals = height_smooth[mask_bool]
if masked_vals.max() > masked_vals.min():
    height_smooth[mask_bool] = (
        (height_smooth[mask_bool] - masked_vals.min()) /
        (masked_vals.max() - masked_vals.min())
    )

print(f"Smoothed height range (pre-clamp): [{height_smooth[mask_bool].min():.3f}, {height_smooth[mask_bool].max():.3f}]")

# === FIX 3: Clamp depressions (remove divots) ===
print("\n=== CLAMPING DEPRESSIONS ===")
# Compute a heavily blurred "local average" — any pixel significantly below
# this local average is a divot that should be pulled up.
local_avg = gaussian_filter(height_smooth, sigma=25.0)
local_avg[~mask_bool] = 0.0
diff_from_avg = height_smooth - local_avg

# Compute stats on the difference within the mask
diff_vals = diff_from_avg[mask_bool]
diff_std = diff_vals.std()
DEPRESSION_THRESHOLD = -1.5 * diff_std  # pixels more than 1.5 sigma below local avg

depression_mask = mask_bool & (diff_from_avg < DEPRESSION_THRESHOLD)
n_depressed = np.count_nonzero(depression_mask)
print(f"Depression threshold: {DEPRESSION_THRESHOLD:.4f} (1.5 * std={diff_std:.4f})")
print(f"Depressed pixels clamped: {n_depressed}")

# Clamp: raise depressed pixels to local_avg + threshold
height_smooth[depression_mask] = local_avg[depression_mask] + DEPRESSION_THRESHOLD
height_smooth[~mask_bool] = 0.0

# === FIX 4: Extra edge smoothing ===
print("\n=== EDGE SMOOTHING ===")
# Compute distance from mask boundary (distance transform)
dist_from_edge = cv2.distanceTransform(mask_u8, cv2.DIST_L2, 5)
EDGE_BAND_PX = 20

# Create a heavily smoothed version for the edge zone
height_edge_smooth = gaussian_filter(height_smooth, sigma=SMOOTH_SIGMA * 3.0)
height_edge_smooth[~mask_bool] = 0.0

# Blend: at the very edge (dist=0), use fully smoothed; at dist>=EDGE_BAND_PX, use original
edge_blend = np.clip(dist_from_edge / EDGE_BAND_PX, 0.0, 1.0)
height_smooth = np.where(
    mask_bool,
    edge_blend * height_smooth + (1.0 - edge_blend) * height_edge_smooth,
    0.0
).astype(np.float32)

# Final re-normalize within mask to 0..1
masked_vals = height_smooth[mask_bool]
if masked_vals.max() > masked_vals.min():
    height_smooth[mask_bool] = (
        (height_smooth[mask_bool] - masked_vals.min()) /
        (masked_vals.max() - masked_vals.min())
    )

print(f"Final smoothed height range: [{height_smooth[mask_bool].min():.3f}, {height_smooth[mask_bool].max():.3f}]")

# ==========================================================================
# -- 6. Scale to physical dimensions --------------------------------------
# ==========================================================================
# Use combined mask (green + bunkers) for the bounding box
ys_combined, xs_combined = np.where(combined_mask_bool)
y_min, y_max = ys_combined.min(), ys_combined.max()
x_min, x_max = xs_combined.min(), xs_combined.max()

margin = 5
y_min_c = max(0, y_min - margin)
y_max_c = min(ch, y_max + margin + 1)
x_min_c = max(0, x_min - margin)
x_max_c = min(cw, x_max + margin + 1)

hmap = height_smooth[y_min_c:y_max_c, x_min_c:x_max_c]
gmask = combined_mask_bool[y_min_c:y_max_c, x_min_c:x_max_c]
# Also crop the bunker-only mask so we know which pixels are bunkers vs green
bmask = bunker_mask_bool[y_min_c:y_max_c, x_min_c:x_max_c]
# Crop the putting surface and fringe masks to the same region
pmask = putting_mask_bool[y_min_c:y_max_c, x_min_c:x_max_c]
fmask = fringe_mask_bool[y_min_c:y_max_c, x_min_c:x_max_c]

# Downsample for manageable mesh size (target ~300x300)
target_res = 300
scale_factor = target_res / max(hmap.shape)
if scale_factor < 1:
    new_h = int(hmap.shape[0] * scale_factor)
    new_w = int(hmap.shape[1] * scale_factor)
    hmap = cv2.resize(hmap.astype(np.float32), (new_w, new_h), interpolation=cv2.INTER_LINEAR)
    gmask_resized = cv2.resize(gmask.astype(np.uint8) * 255, (new_w, new_h),
                               interpolation=cv2.INTER_NEAREST) > 127
    bmask_resized = cv2.resize(bmask.astype(np.uint8) * 255, (new_w, new_h),
                               interpolation=cv2.INTER_NEAREST) > 127
    pmask_resized = cv2.resize(pmask.astype(np.uint8) * 255, (new_w, new_h),
                               interpolation=cv2.INTER_NEAREST) > 127
    fmask_resized = cv2.resize(fmask.astype(np.uint8) * 255, (new_w, new_h),
                               interpolation=cv2.INTER_NEAREST) > 127
else:
    gmask_resized = gmask
    bmask_resized = bmask
    pmask_resized = pmask
    fmask_resized = fmask

rows, cols = hmap.shape
print(f"Heightmap grid: {cols}x{rows}")

# Physical scaling: fit into PRINT_SIZE_MM square
aspect = cols / rows
if aspect >= 1:
    phys_w = PRINT_SIZE_MM
    phys_h = PRINT_SIZE_MM / aspect
else:
    phys_h = PRINT_SIZE_MM
    phys_w = PRINT_SIZE_MM * aspect

dx = phys_w / (cols - 1)
dy = phys_h / (rows - 1)

# Height scaling with exaggeration
elevation = hmap * MAX_ELEVATION_MM * VERT_EXAGGERATION
# Add base thickness for green pixels; flat low height for bunker pixels
BUNKER_HEIGHT_MM = BASE_THICKNESS_MM * 0.5  # bunkers sit at half the base height
green_only_resized = gmask_resized & (~bmask_resized)
elevation_with_base = np.where(
    green_only_resized, elevation + BASE_THICKNESS_MM,
    np.where(bmask_resized, BUNKER_HEIGHT_MM, 0)
)
print(f"\nBunker platform height: {BUNKER_HEIGHT_MM:.1f} mm")
print(f"Bunker pixels in mesh: {np.count_nonzero(bmask_resized)}")
print(f"Green pixels in mesh: {np.count_nonzero(green_only_resized)}")
print(f"Putting surface pixels in mesh: {np.count_nonzero(pmask_resized)}")
print(f"Fringe pixels in mesh: {np.count_nonzero(fmask_resized)}")

# ==========================================================================
# -- 7. Generate STL meshes (GREEN + FRINGE) ------------------------------
# ==========================================================================

def build_stl(region_mask, elevation_with_base, rows, cols, dx, dy, label="region"):
    """Build a watertight STL mesh for a given region mask.

    Uses the SAME coordinate system (dx, dy, rows, cols) so the two pieces
    fit together when placed side by side.
    """
    print(f"\nBuilding mesh triangles for {label}...")
    triangles = []

    def add_tri(v0, v1, v2):
        triangles.append((v0, v1, v2))

    # --- Top surface: triangulate the masked region ---
    for i in range(rows - 1):
        for j in range(cols - 1):
            if (region_mask[i, j] and region_mask[i+1, j] and
                region_mask[i, j+1] and region_mask[i+1, j+1]):
                x0, y0 = j * dx, (rows - 1 - i) * dy
                x1, y1 = (j+1) * dx, (rows - 1 - i) * dy
                x2, y2 = (j+1) * dx, (rows - 1 - (i+1)) * dy
                x3, y3 = j * dx, (rows - 1 - (i+1)) * dy

                z0 = elevation_with_base[i, j]
                z1 = elevation_with_base[i, j+1]
                z2 = elevation_with_base[i+1, j+1]
                z3 = elevation_with_base[i+1, j]

                add_tri((x0, y0, z0), (x1, y1, z1), (x2, y2, z2))
                add_tri((x0, y0, z0), (x2, y2, z2), (x3, y3, z3))

    # --- Bottom surface: flat at z=0 ---
    for i in range(rows - 1):
        for j in range(cols - 1):
            if (region_mask[i, j] and region_mask[i+1, j] and
                region_mask[i, j+1] and region_mask[i+1, j+1]):
                x0, y0 = j * dx, (rows - 1 - i) * dy
                x1, y1 = (j+1) * dx, (rows - 1 - i) * dy
                x2, y2 = (j+1) * dx, (rows - 1 - (i+1)) * dy
                x3, y3 = j * dx, (rows - 1 - (i+1)) * dy

                add_tri((x0, y0, 0), (x2, y2, 0), (x1, y1, 0))
                add_tri((x0, y0, 0), (x3, y3, 0), (x2, y2, 0))

    # --- Side walls ---
    print(f"Building side walls for {label}...")

    quad_inside = np.zeros((rows - 1, cols - 1), dtype=bool)
    for i in range(rows - 1):
        for j in range(cols - 1):
            quad_inside[i, j] = (region_mask[i, j] and region_mask[i+1, j] and
                                 region_mask[i, j+1] and region_mask[i+1, j+1])

    def grid_pos(i, j, z):
        return (j * dx, (rows - 1 - i) * dy, z)

    wall_count = 0

    # Horizontal edges
    for i in range(rows):
        for j in range(cols - 1):
            above = quad_inside[i-1, j] if i > 0 else False
            below = quad_inside[i, j] if i < rows - 1 else False
            if above == below:
                continue

            z_a = float(elevation_with_base[i, j])
            z_b = float(elevation_with_base[i, j+1])
            top_a = grid_pos(i, j, z_a)
            top_b = grid_pos(i, j+1, z_b)
            bot_a = grid_pos(i, j, 0)
            bot_b = grid_pos(i, j+1, 0)

            if below:
                add_tri(top_a, top_b, bot_b)
                add_tri(top_a, bot_b, bot_a)
            else:
                add_tri(top_a, bot_b, top_b)
                add_tri(top_a, bot_a, bot_b)
            wall_count += 2

    # Vertical edges
    for i in range(rows - 1):
        for j in range(cols):
            left = quad_inside[i, j-1] if j > 0 else False
            right = quad_inside[i, j] if j < cols - 1 else False
            if left == right:
                continue

            z_a = float(elevation_with_base[i, j])
            z_b = float(elevation_with_base[i+1, j])
            top_a = grid_pos(i, j, z_a)
            top_b = grid_pos(i+1, j, z_b)
            bot_a = grid_pos(i, j, 0)
            bot_b = grid_pos(i+1, j, 0)

            if right:
                add_tri(top_a, bot_b, top_b)
                add_tri(top_a, bot_a, bot_b)
            else:
                add_tri(top_a, top_b, bot_b)
                add_tri(top_a, bot_b, bot_a)
            wall_count += 2

    print(f"Wall triangles ({label}): {wall_count}")
    print(f"Total triangles ({label}): {len(triangles)}")
    return triangles


def save_stl(triangles, output_path, label=""):
    """Save a list of triangles as an STL file."""
    if len(triangles) == 0:
        print(f"WARNING: No triangles for {label}, skipping STL write.")
        return
    tri_array = np.array(triangles, dtype=np.float32)  # (N, 3, 3)
    solid = stl_mesh.Mesh(np.zeros(len(triangles), dtype=stl_mesh.Mesh.dtype))
    for idx in range(len(triangles)):
        solid.vectors[idx] = tri_array[idx]
    solid.update_normals()
    os.makedirs(os.path.dirname(output_path), exist_ok=True)
    solid.save(output_path)
    file_size = os.path.getsize(output_path)
    print(f"\n{label} STL saved to: {output_path}")
    print(f"  File size: {file_size / 1024:.1f} KB")
    print(f"  Triangle count: {solid.vectors.shape[0]}")
    print(f"  Max elevation: {solid.vectors[:,:,2].max():.1f} mm")


# Build the putting surface mask for STL (putting surface minus bunkers, within combined)
# The putting surface is inside the black boundary, AND part of the green (not bunker)
putting_stl_mask = pmask_resized & gmask_resized
# Bunkers that fall inside the putting boundary stay with the green STL
putting_stl_mask = putting_stl_mask | (bmask_resized & pmask_resized)

# Build the fringe mask for STL (fringe area, plus bunkers in the fringe)
fringe_stl_mask = fmask_resized & gmask_resized
fringe_stl_mask = fringe_stl_mask | (bmask_resized & fmask_resized)
# Also include any bunker pixels that are NOT in the putting area
fringe_stl_mask = fringe_stl_mask | (bmask_resized & (~pmask_resized))

print(f"\nPutting STL mask pixels: {np.count_nonzero(putting_stl_mask)}")
print(f"Fringe STL mask pixels: {np.count_nonzero(fringe_stl_mask)}")

# Generate both STLs using the SAME coordinate system
green_triangles = build_stl(putting_stl_mask, elevation_with_base, rows, cols, dx, dy, "PUTTING GREEN")
fringe_triangles = build_stl(fringe_stl_mask, elevation_with_base, rows, cols, dx, dy, "FRINGE")

# ==========================================================================
# -- 8. Write STL files ---------------------------------------------------
# ==========================================================================
save_stl(green_triangles, OUTPUT_GREEN, "Putting Green")
save_stl(fringe_triangles, OUTPUT_FRINGE, "Fringe")

print(f"\nPhysical size: {phys_w:.1f} x {phys_h:.1f} mm")
print("Both STLs share the same coordinate system — they fit together.")
print("Done!")
