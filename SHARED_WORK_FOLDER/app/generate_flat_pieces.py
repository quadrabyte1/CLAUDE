#!/usr/bin/env python3
"""
Generate flat 3D-printable STL pieces from the Moffett Field G.C. Hole 7
golf green image. Produces 5 pieces that fit together like a puzzle:
  1. The putting green (inside the black boundary)
  2. The fringe (surrounding area with cutouts for green and traps)
  3-5. Three individual sand traps

All pieces are flat cookie-cutter shapes with uniform thickness.
"""

import cv2
import numpy as np
from scipy.ndimage import binary_fill_holes
from stl import mesh as stl_mesh
import os

# -- Paths -----------------------------------------------------------------
INPUT = "/Users/fourierflight/GIT/CLAUDE-GitHub/SHARED_WORK_FOLDER/team_inbox/Moffett Field 7 (no iso).png"
OUTPUT_DIR = "/Users/fourierflight/GIT/CLAUDE-GitHub/SHARED_WORK_FOLDER/owner_inbox"

OUTPUT_GREEN = os.path.join(OUTPUT_DIR, "moffett_7_green.stl")
OUTPUT_FRINGE = os.path.join(OUTPUT_DIR, "moffett_7_fringe.stl")
OUTPUT_TRAP_1 = os.path.join(OUTPUT_DIR, "moffett_7_trap_1.stl")
OUTPUT_TRAP_2 = os.path.join(OUTPUT_DIR, "moffett_7_trap_2.stl")
OUTPUT_TRAP_3 = os.path.join(OUTPUT_DIR, "moffett_7_trap_3.stl")

# -- Parameters ------------------------------------------------------------
PRINT_SIZE_MM = 178.0   # longest axis
THICKNESS_GREEN_MM = 30.0
THICKNESS_TRAP_MM = 20.0
THICKNESS_FRINGE_MM = 10.0

# ==========================================================================
# 1. Load image and crop to the relevant region
# ==========================================================================
img = cv2.imread(INPUT)
if img is None:
    raise FileNotFoundError(f"Cannot read {INPUT}")

h, w = img.shape[:2]
print(f"Image size: {w}x{h}")

# Crop to the golf hole area — this image is already well-framed
x1, x2 = int(w * 0.02), int(w * 0.98)
y1, y2 = int(h * 0.02), int(h * 0.98)
crop = img[y1:y2, x1:x2].copy()
ch, cw = crop.shape[:2]
print(f"Crop size: {cw}x{ch}")

# ==========================================================================
# 1a. Detect sand traps BEFORE removing UI overlays, so we capture trap
#     pixels that are partially visible around/behind UI elements.
# ==========================================================================
print("\n=== DETECTING SAND TRAPS (pre-UI-removal) ===")

hsv_pre = cv2.cvtColor(crop, cv2.COLOR_BGR2HSV)
hue_pre = hsv_pre[:, :, 0].astype(float)
sat_pre = hsv_pre[:, :, 1].astype(float)
val_pre = hsv_pre[:, :, 2].astype(float)

# Sand traps core: pale cream/tan — tighter tolerances to avoid fringe bleed
trap_core = (
    (hue_pre >= 15) & (hue_pre <= 34) &
    (sat_pre >= 15) & (sat_pre <= 60) &
    (val_pre >= 200)
)
# Gray border pixels: low saturation, moderately bright — only kept if adjacent to core
trap_gray = (
    (sat_pre < 20) &
    (val_pre >= 160)
)

# Only keep gray pixels immediately adjacent to core trap pixels
kernel_near = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (9, 9))
core_dilated = cv2.dilate((trap_core.astype(np.uint8)) * 255, kernel_near, iterations=1)
trap_u8 = ((trap_core.astype(np.uint8)) * 255) | (((trap_gray.astype(np.uint8)) * 255) & core_dilated)

# Moderate closing to bridge small gaps, but not so aggressive it bleeds into fringe
kernel_trap = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (11, 11))
trap_u8 = cv2.morphologyEx(trap_u8, cv2.MORPH_CLOSE, kernel_trap, iterations=3)
# Then open to clean noise without losing the bridged shape
kernel_open = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (7, 7))
trap_u8 = cv2.morphologyEx(trap_u8, cv2.MORPH_OPEN, kernel_open, iterations=2)

# Fill holes
trap_bool = binary_fill_holes(trap_u8 > 0)
trap_u8_early = (trap_bool.astype(np.uint8)) * 255

# ==========================================================================
# 1b. Remove GolfLogix UI elements (white circles, rounded rectangles with
#     text/icons on dark green or gray backgrounds) for green/fringe detection.
# ==========================================================================
print("\n=== REMOVING UI ELEMENTS ===")
gray = cv2.cvtColor(crop, cv2.COLOR_BGR2GRAY)
hsv_check = cv2.cvtColor(crop, cv2.COLOR_BGR2HSV)
ui_removed = 0

# Build a combined UI mask for all elements to remove
ui_mask = np.zeros((ch, cw), dtype=np.uint8)

# --- 1. White/bright circles (yardage markers, icons) ---
circles = cv2.HoughCircles(
    gray, cv2.HOUGH_GRADIENT, dp=1.2, minDist=20,
    param1=80, param2=30, minRadius=8, maxRadius=40
)
if circles is not None:
    circles_arr = np.round(circles[0]).astype(int)
    for (cx, cy, r) in circles_arr:
        mask_circle = np.zeros((ch, cw), dtype=np.uint8)
        cv2.circle(mask_circle, (cx, cy), r, 255, -1)
        circle_val = hsv_check[:, :, 2][mask_circle > 0].mean()
        circle_sat = hsv_check[:, :, 1][mask_circle > 0].mean()
        if circle_val > 160 and circle_sat < 80:
            cv2.circle(ui_mask, (cx, cy), r + 3, 255, -1)
            ui_removed += 1
            print(f"  Removed bright circle at ({cx}, {cy}), r={r}")

# --- 2. Dark UI elements in the bottom region (steering wheel, Sw info box) ---
# These are at the ~6 o'clock position. Scan the bottom 20% of the crop for
# dark blobs that contain white text or have UI-like structure.
bottom_cutoff = int(ch * 0.80)
bottom_gray = gray[bottom_cutoff:, :]
dark_bottom = (bottom_gray < 40).astype(np.uint8) * 255
kernel_db = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (7, 7))
dark_bottom = cv2.morphologyEx(dark_bottom, cv2.MORPH_CLOSE, kernel_db, iterations=3)
n_db, db_labels, db_stats, db_centroids = cv2.connectedComponentsWithStats(dark_bottom)
for i in range(1, n_db):
    area = db_stats[i, cv2.CC_STAT_AREA]
    bx = db_stats[i, cv2.CC_STAT_LEFT]
    by = db_stats[i, cv2.CC_STAT_TOP]
    bw = db_stats[i, cv2.CC_STAT_WIDTH]
    bh = db_stats[i, cv2.CC_STAT_HEIGHT]
    if area < 800 or area > 20000:
        continue
    # Check for white text inside
    blob_pixels = bottom_gray[db_labels == i]
    white_pct = np.sum(blob_pixels > 180) / max(len(blob_pixels), 1)
    # UI blobs have some white text (>3%) or are compact icon-like shapes
    is_ui = white_pct > 0.03 or (area < 3000 and max(bw, bh) / max(min(bw, bh), 1) < 2)
    if is_ui:
        # Add to mask with the correct y offset
        roi = np.zeros((ch, cw), dtype=np.uint8)
        roi[bottom_cutoff:, :] = ((db_labels == i) * 255).astype(np.uint8)
        # Dilate to cover edges
        roi = cv2.dilate(roi, cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (7, 7)), iterations=1)
        ui_mask = cv2.bitwise_or(ui_mask, roi)
        ui_removed += 1
        actual_y = by + bottom_cutoff
        print(f"  Removed dark UI at ({bx},{actual_y}), size={bw}x{bh}, white%={white_pct*100:.1f}")

# --- 3. White/bright rounded rectangles (not sand traps) ---
white_ui = (val_pre > 200) & (sat_pre < 30) & (hue_pre < 15)
white_ui = white_ui & ~(trap_u8_early > 0)
white_ui_u8 = (white_ui.astype(np.uint8)) * 255
kernel_ui = cv2.getStructuringElement(cv2.MORPH_RECT, (5, 5))
white_ui_u8 = cv2.morphologyEx(white_ui_u8, cv2.MORPH_CLOSE, kernel_ui, iterations=2)
contours_ui, _ = cv2.findContours(white_ui_u8, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
for cnt in contours_ui:
    area = cv2.contourArea(cnt)
    x, y, bw, bh = cv2.boundingRect(cnt)
    aspect = max(bw, bh) / max(min(bw, bh), 1)
    if 500 < area < 8000 and aspect < 4 and bw < 120 and bh < 120:
        cv2.drawContours(ui_mask, [cnt], -1, 255, -1)
        ui_removed += 1
        print(f"  Removed bright rect at ({x}, {y}), size={bw}x{bh}")

# --- 4. Dark rounded rectangles (black background with white text) ---
# These have very dark pixels (gray < 40) clustered with some white text pixels
dark_ui = (gray < 40).astype(np.uint8) * 255
# Exclude sand traps and the very dark contour arrows inside the green
# Focus on blobs that contain BOTH dark and bright pixels (text on dark bg)
kernel_dark = cv2.getStructuringElement(cv2.MORPH_RECT, (7, 7))
dark_ui = cv2.morphologyEx(dark_ui, cv2.MORPH_CLOSE, kernel_dark, iterations=3)
contours_dark, _ = cv2.findContours(dark_ui, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
for cnt in contours_dark:
    area = cv2.contourArea(cnt)
    x, y, bw, bh = cv2.boundingRect(cnt)
    if area < 1000 or bw > 250 or bh > 250:
        continue
    # Check if this blob contains white text pixels (mixed dark + bright)
    roi_mask = np.zeros((ch, cw), dtype=np.uint8)
    cv2.drawContours(roi_mask, [cnt], -1, 255, -1)
    roi_vals = gray[roi_mask > 0]
    bright_ratio = np.sum(roi_vals > 180) / max(len(roi_vals), 1)
    dark_ratio = np.sum(roi_vals < 40) / max(len(roi_vals), 1)
    # Dark UI elements: mostly dark with some bright text (5-50% bright)
    if dark_ratio > 0.4 and bright_ratio > 0.05 and bright_ratio < 0.6:
        cv2.drawContours(ui_mask, [cnt], -1, 255, -1)
        ui_removed += 1
        print(f"  Removed dark rect at ({x}, {y}), size={bw}x{bh}")

# --- 5. Semi-transparent info cards (like "9 Iron 134" at 11 o'clock) ---
# These are in the top portion of the image, rectangular, with muted background
# and white text. Only look in the top 30% to avoid false positives.
top_cutoff = int(ch * 0.30)
semi_trans = (val_pre[:top_cutoff, :] > 100) & (val_pre[:top_cutoff, :] < 210) & (sat_pre[:top_cutoff, :] < 60)
semi_u8 = (semi_trans.astype(np.uint8)) * 255
semi_u8 = cv2.morphologyEx(semi_u8, cv2.MORPH_CLOSE,
    cv2.getStructuringElement(cv2.MORPH_RECT, (10, 10)), iterations=3)
contours_semi, _ = cv2.findContours(semi_u8, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
for cnt in contours_semi:
    area = cv2.contourArea(cnt)
    x, y, bw, bh = cv2.boundingRect(cnt)
    aspect = max(bw, bh) / max(min(bw, bh), 1)
    if 2000 < area < 40000 and aspect < 3 and bw < 200 and bh < 200:
        roi_mask = np.zeros((top_cutoff, cw), dtype=np.uint8)
        cv2.drawContours(roi_mask, [cnt], -1, 255, -1)
        roi_vals = gray[:top_cutoff, :][roi_mask > 0]
        white_ratio = np.sum(roi_vals > 200) / max(len(roi_vals), 1)
        if white_ratio > 0.05:
            # Map back to full image mask
            full_roi = np.zeros((ch, cw), dtype=np.uint8)
            full_roi[:top_cutoff, :] = roi_mask
            ui_mask = cv2.bitwise_or(ui_mask, full_roi)
            ui_removed += 1
            print(f"  Removed info card at ({x}, {y}), size={bw}x{bh}")

# Inpaint all UI elements at once
if np.any(ui_mask > 0):
    # Dilate the mask slightly for clean inpainting
    ui_mask = cv2.dilate(ui_mask, cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (5, 5)), iterations=1)
    crop = cv2.inpaint(crop, ui_mask, inpaintRadius=10, flags=cv2.INPAINT_TELEA)
print(f"  Total UI elements removed: {ui_removed}")

# Convert cleaned image to HSV for green/fringe detection
hsv = cv2.cvtColor(crop, cv2.COLOR_BGR2HSV)
hue = hsv[:, :, 0].astype(float)
sat = hsv[:, :, 1].astype(float)
val = hsv[:, :, 2].astype(float)

# ==========================================================================
# 2. Finalize sand trap masks (use the pre-UI-removal detection)
# ==========================================================================
print("\n=== FINALIZING SAND TRAPS ===")
# Use the trap mask detected before UI removal
trap_u8 = trap_u8_early

# Connected components to find individual traps
n_trap_labels, trap_labels, trap_stats, trap_centroids = \
    cv2.connectedComponentsWithStats(trap_u8)

# Filter out tiny noise
min_trap_area = 500
valid_traps = []
for i in range(1, n_trap_labels):
    area = trap_stats[i, cv2.CC_STAT_AREA]
    if area >= min_trap_area:
        valid_traps.append((i, area, trap_centroids[i]))
        print(f"  Trap candidate {len(valid_traps)}: area={area}, "
              f"centroid=({trap_centroids[i][0]:.0f}, {trap_centroids[i][1]:.0f})")

# Sort by area descending and take top 3
valid_traps.sort(key=lambda x: x[1], reverse=True)
traps_to_use = valid_traps[:3]
print(f"Using {len(traps_to_use)} sand traps")

# Create individual trap masks
trap_masks = []
for idx, (label_id, area, centroid) in enumerate(traps_to_use):
    mask = (trap_labels == label_id)
    mask_u8_t = (mask.astype(np.uint8)) * 255
    kernel_smooth = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (7, 7))
    mask_u8_t = cv2.morphologyEx(mask_u8_t, cv2.MORPH_CLOSE, kernel_smooth, iterations=2)
    # Smooth trap edges with heavier Gaussian blur
    mask_u8_t = cv2.GaussianBlur(mask_u8_t, (21, 21), 0)
    _, mask_u8_t = cv2.threshold(mask_u8_t, 127, 255, cv2.THRESH_BINARY)
    # Additional morphological smoothing
    kernel_trap_smooth = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (9, 9))
    mask_u8_t = cv2.morphologyEx(mask_u8_t, cv2.MORPH_OPEN, kernel_trap_smooth, iterations=1)
    mask_u8_t = cv2.morphologyEx(mask_u8_t, cv2.MORPH_CLOSE, kernel_trap_smooth, iterations=1)
    mask_bool_t = mask_u8_t > 0
    trap_masks.append(mask_bool_t)
    print(f"  Trap {idx+1}: {np.count_nonzero(mask_bool_t)} pixels, "
          f"centroid=({centroid[0]:.0f}, {centroid[1]:.0f})")

# Combined trap mask
all_traps_mask = np.zeros((ch, cw), dtype=bool)
for tm in trap_masks:
    all_traps_mask |= tm

# ==========================================================================
# 3. Detect the putting green (inside black boundary line)
# ==========================================================================
print("\n=== DETECTING PUTTING GREEN (radial ray-cast method) ===")

# Strategy: Find a distinctive interior color (orange/yellow from contour bands),
# then cast rays outward radially. On each ray, find the transition:
#   bright/colorful → BLACK LINE → forest green fringe
# The black line crossing point IS the green boundary.

gray_green = cv2.cvtColor(crop, cv2.COLOR_BGR2GRAY)
hsv_clean = cv2.cvtColor(crop, cv2.COLOR_BGR2HSV)

# Find seed: center of mass of orange/yellow pixels (hue ~10-25, high sat, high val)
# These colors only appear inside the green contour bands
orange_yellow = (
    (hsv_clean[:, :, 0] >= 8) & (hsv_clean[:, :, 0] <= 25) &
    (hsv_clean[:, :, 1] > 120) &
    (hsv_clean[:, :, 2] > 150)
)
oy_coords = np.argwhere(orange_yellow)
if len(oy_coords) > 0:
    seed_y, seed_x = oy_coords.mean(axis=0).astype(int)
else:
    seed_y, seed_x = ch // 2, cw // 2
print(f"  Seed point (orange/yellow centroid): ({seed_x}, {seed_y})")

# Cast rays in 720 directions (every 0.5 degrees)
n_rays = 720
boundary_pts = []
for i in range(n_rays):
    angle = 2 * np.pi * i / n_rays
    dx = np.cos(angle)
    dy = np.sin(angle)

    # Walk outward along the ray, collecting grayscale values
    ray_pixels = []
    for step in range(1, max(ch, cw)):
        px = int(seed_x + dx * step)
        py = int(seed_y + dy * step)
        if px < 0 or px >= cw or py < 0 or py >= ch:
            break
        ray_pixels.append((px, py, gray_green[py, px]))

    # Scan the ray for ALL thick dark bands, then take the OUTERMOST one
    # that has fringe (not more contour colors) on its far side.
    # The actual black outline is the last dark crossing before the fringe.
    candidates = []
    i = 0
    while i < len(ray_pixels):
        px, py, g = ray_pixels[i]
        if g < 35:
            dark_start = i
            while i < len(ray_pixels) and ray_pixels[i][2] < 35:
                i += 1
            dark_width = i - dark_start

            if dark_width >= 3 and i < len(ray_pixels):
                # Check what's on the far side
                exit_end = min(i + 20, len(ray_pixels))
                exit_pixels = ray_pixels[i:exit_end]
                if exit_pixels:
                    exit_coords = [(p[0], p[1]) for p in exit_pixels]
                    exit_sats = [float(hsv_clean[ey, ex, 1]) for ex, ey in exit_coords
                                 if 0 <= ey < ch and 0 <= ex < cw]
                    exit_vals = [float(hsv_clean[ey, ex, 2]) for ex, ey in exit_coords
                                 if 0 <= ey < ch and 0 <= ex < cw]
                    if exit_sats:
                        avg_sat = np.mean(exit_sats)
                        avg_val = np.mean(exit_vals)
                        mid_idx = dark_start + dark_width // 2
                        candidates.append((mid_idx, dark_width, avg_sat, avg_val))
        else:
            i += 1

    # Take the outermost candidate that exits to fringe
    # (fringe = not bright/saturated contour interior)
    boundary_pt = None
    for mid_idx, dw, avg_sat, avg_val in reversed(candidates):
        is_fringe = (avg_sat < 100) or (avg_val < 140)
        if is_fringe:
            boundary_pt = (ray_pixels[mid_idx][0], ray_pixels[mid_idx][1])
            break

    if boundary_pt:
        boundary_pts.append(boundary_pt)

print(f"  Rays cast: {n_rays}, boundary points found: {len(boundary_pts)}")

if len(boundary_pts) > 10:
    from scipy.interpolate import splprep, splev
    from scipy.ndimage import median_filter
    bp = np.array(boundary_pts, dtype=float)

    # Compute angle and distance from seed for each boundary point
    ray_angles = np.arctan2(bp[:, 1] - seed_y, bp[:, 0] - seed_x)
    ray_dists = np.sqrt((bp[:, 0] - seed_x)**2 + (bp[:, 1] - seed_y)**2)

    # Sort by angle
    order = np.argsort(ray_angles)
    ray_angles = ray_angles[order]
    ray_dists = ray_dists[order]

    # Apply heavy rolling median filter on distances to eliminate spikes.
    # Window of 91 rays (~45 degrees) — this forces a smooth radius profile.
    filtered_dists = median_filter(ray_dists, size=91, mode='wrap')
    print(f"  Distance range: raw {ray_dists.min():.0f}-{ray_dists.max():.0f}, "
          f"filtered {filtered_dists.min():.0f}-{filtered_dists.max():.0f}")

    # Convert filtered distances back to XY points
    bp_filtered = np.column_stack([
        seed_x + filtered_dists * np.cos(ray_angles),
        seed_y + filtered_dists * np.sin(ray_angles),
    ])

    # Remove near-duplicates
    cleaned = [bp_filtered[0]]
    for p in bp_filtered[1:]:
        if np.linalg.norm(p - cleaned[-1]) > 1:
            cleaned.append(p)
    bp_clean = np.array(cleaned)

    # Fit a periodic B-spline — moderate smoothing (the median filter did the heavy lifting)
    tck, u = splprep([bp_clean[:, 0], bp_clean[:, 1]], s=len(bp_clean) * 2.0, per=True)
    u_new = np.linspace(0, 1, 500)
    x_new, y_new = splev(u_new, tck)
    smooth_pts = np.column_stack([x_new, y_new]).astype(np.int32)

    # Draw as filled polygon
    green_smooth = np.zeros((ch, cw), dtype=np.uint8)
    cv2.fillPoly(green_smooth, [smooth_pts], 255)
    print(f"  Green boundary: {len(bp_clean)} pts -> {len(smooth_pts)} pts (median filtered + spline)")
else:
    print("  WARNING: Not enough boundary points found!")
    green_smooth = np.zeros((ch, cw), dtype=np.uint8)

green_mask = (green_smooth > 0) & (~all_traps_mask)
print(f"  Green mask pixels: {np.count_nonzero(green_mask)}")

# ==========================================================================
# 4. Detect the fringe (dark green area surrounding the green)
# ==========================================================================
print("\n=== DETECTING FRINGE ===")

# The fringe is the dark/forest green area immediately around the green.
# It is darker and more saturated than the fairway (which has mowing stripes).
# Key insight: fairway grass is brighter (higher value) and less saturated
# than the rough/fringe around the green.

# Tighter green detection: fringe/rough is darker than fairway
# Fairway is typically val > 120 with lower saturation; fringe is val < 150
overall_green = (
    (hue >= 30) & (hue <= 90) &
    (sat >= 30) &                    # raised from 20 to exclude pale fairway
    (val >= 30) & (val <= 160)       # lowered from 200 to exclude bright fairway
)

# Gray ISO lines — tighter range to avoid fairway pixels
gray_lines = (sat < 35) & (val >= 50) & (val <= 130)  # tightened val upper from 160

# Combine
fringe_raw = overall_green | gray_lines

# Also include the colorful green interior to build the overall shape
fringe_with_green = fringe_raw | green_mask | all_traps_mask

fringe_u8 = (fringe_with_green.astype(np.uint8)) * 255

# Close and fill — REDUCED aggressiveness to prevent bridging to fairway
# Smaller kernel (9x9 down from 15x15) and fewer iterations (3 down from 5)
kernel_fringe = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (9, 9))
fringe_u8 = cv2.morphologyEx(fringe_u8, cv2.MORPH_CLOSE, kernel_fringe, iterations=3)
fringe_u8 = cv2.morphologyEx(fringe_u8, cv2.MORPH_OPEN, cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (7, 7)), iterations=2)

fringe_filled = binary_fill_holes(fringe_u8 > 0)
fringe_u8 = (fringe_filled.astype(np.uint8)) * 255

# Keep largest component
n_f, f_labels, f_stats, _ = cv2.connectedComponentsWithStats(fringe_u8)
if n_f > 1:
    f_areas = f_stats[1:, cv2.CC_STAT_AREA]
    f_largest = 1 + np.argmax(f_areas)
    fringe_u8 = ((f_labels == f_largest) * 255).astype(np.uint8)

overall_mask = fringe_u8 > 0

# -- Distance constraint: limit fringe extent from green boundary --
# The fringe should not extend more than ~1.5x the green radius from the
# green centroid. This prevents bleeding into the fairway.
from scipy.ndimage import distance_transform_edt
green_dist = distance_transform_edt(~(green_smooth > 0))
# Compute a reasonable max fringe width: use the green's equivalent radius
green_area_px = np.count_nonzero(green_smooth > 0)
green_equiv_radius = np.sqrt(green_area_px / np.pi)
# Fringe typically extends ~40-60% of the green radius at most
max_fringe_dist = green_equiv_radius * 0.6
print(f"  Green equivalent radius: {green_equiv_radius:.0f} px")
print(f"  Max fringe distance from green boundary: {max_fringe_dist:.0f} px")
distance_limit_mask = green_dist <= max_fringe_dist
# Apply the distance constraint — but always keep trap areas
overall_mask = overall_mask & (distance_limit_mask | all_traps_mask)

# Exclude the medium gray area at the top of the image
# The gray area is at the top — detect it and remove
gray_top = (sat < 30) & (val >= 60) & (val <= 170)
gray_top_u8 = (gray_top.astype(np.uint8)) * 255
# Only consider gray in the top portion
gray_top_u8[int(ch * 0.5):, :] = 0
kernel_gt = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (15, 15))
gray_top_u8 = cv2.morphologyEx(gray_top_u8, cv2.MORPH_CLOSE, kernel_gt, iterations=3)
gray_top_bool = gray_top_u8 > 0

# Remove the gray top area from the overall mask
overall_mask = overall_mask & (~gray_top_bool)

# Re-fill and keep largest
overall_u8 = (overall_mask.astype(np.uint8)) * 255
n_o, o_labels, o_stats, _ = cv2.connectedComponentsWithStats(overall_u8)
if n_o > 1:
    o_areas = o_stats[1:, cv2.CC_STAT_AREA]
    o_largest = 1 + np.argmax(o_areas)
    overall_u8 = ((o_labels == o_largest) * 255).astype(np.uint8)
overall_mask = overall_u8 > 0

# Smooth the overall (fringe outer) boundary the same way as the green
overall_smooth_u8 = (overall_mask.astype(np.uint8)) * 255
overall_smooth_u8 = cv2.GaussianBlur(overall_smooth_u8, (31, 31), 0)
_, overall_smooth_u8 = cv2.threshold(overall_smooth_u8, 127, 255, cv2.THRESH_BINARY)
contours_o, _ = cv2.findContours(overall_smooth_u8, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
if contours_o:
    largest_o = max(contours_o, key=cv2.contourArea)
    epsilon_o = 0.002 * cv2.arcLength(largest_o, True)
    approx_o = cv2.approxPolyDP(largest_o, epsilon_o, True)
    overall_smooth_u8 = np.zeros_like(overall_smooth_u8)
    cv2.drawContours(overall_smooth_u8, [approx_o], -1, 255, -1)
    overall_smooth_u8 = cv2.GaussianBlur(overall_smooth_u8, (15, 15), 0)
    _, overall_smooth_u8 = cv2.threshold(overall_smooth_u8, 127, 255, cv2.THRESH_BINARY)
    print(f"  Fringe contour smoothed: {len(largest_o)} pts -> {len(approx_o)} pts")
overall_mask = overall_smooth_u8 > 0

# Re-apply distance constraint after smoothing (smoothing can re-expand)
overall_mask = overall_mask & (distance_limit_mask | all_traps_mask)

# Expand overall_mask to include all trap areas (traps may extend beyond
# the detected green/fringe boundary)
overall_mask = overall_mask | all_traps_mask

# Now the FRINGE is the overall mask minus the green and minus the traps
fringe_mask = overall_mask & (~green_mask) & (~all_traps_mask)

# Ensure the green is within the overall boundary (traps already included)
green_mask = green_mask & overall_mask

print(f"Overall area pixels: {np.count_nonzero(overall_mask)}")
print(f"Fringe mask pixels: {np.count_nonzero(fringe_mask)}")
print(f"Green mask pixels (clipped): {np.count_nonzero(green_mask)}")

# ==========================================================================
# 5. Generate flat STL meshes
# ==========================================================================
print("\n=== GENERATING STL FILES ===")

# Calculate scale: map pixel coordinates to mm
rows_used = np.any(overall_mask, axis=1)
cols_used = np.any(overall_mask, axis=0)
row_min, row_max = np.argmax(rows_used), ch - 1 - np.argmax(rows_used[::-1])
col_min, col_max = np.argmax(cols_used), cw - 1 - np.argmax(cols_used[::-1])

pixel_extent = max(row_max - row_min, col_max - col_min)
scale = PRINT_SIZE_MM / pixel_extent
print(f"Scale: {scale:.4f} mm/pixel")
print(f"Piece dimensions: ~{(col_max - col_min) * scale:.1f} x {(row_max - row_min) * scale:.1f} mm")


def mask_to_flat_stl(mask, output_path, scale, thickness, name="piece"):
    """
    Convert a 2D boolean mask into a flat (cookie-cutter) STL mesh.

    Strategy:
    1. Find contours of the mask (supports holes via hierarchy).
    2. Simplify the contours to reduce vertex count.
    3. Triangulate the top and bottom faces.
    4. Add side walls connecting top and bottom edges.
    """
    mask_u8 = (mask.astype(np.uint8)) * 255

    # Find contours with hierarchy (to handle holes in fringe)
    contours, hierarchy = cv2.findContours(
        mask_u8, cv2.RETR_TREE, cv2.CHAIN_APPROX_SIMPLE
    )

    if not contours:
        print(f"  WARNING: No contours found for {name}")
        return

    # Simplify contours to reduce triangle count
    simplified = []
    for cnt in contours:
        epsilon = 0.002 * cv2.arcLength(cnt, True)
        approx = cv2.approxPolyDP(cnt, epsilon, True)
        if len(approx) >= 3:
            simplified.append(approx)

    if not simplified:
        print(f"  WARNING: No valid contours for {name}")
        return

    # Use cv2.fillPoly approach: rasterize at a reasonable resolution,
    # then extract boundary for walls, and triangulate faces.
    # For simpler approach: triangulate using the contour directly.

    # Approach: Create triangulated mesh from contours
    # Top face at z=thickness, bottom face at z=0, walls connecting them

    all_triangles = []

    # For each contour (outer or hole), we need to process them
    # Use a raster-based triangulation: scan the mask and create a grid of triangles

    # Downsample the mask for reasonable mesh size
    # Target roughly 200x200 grid max
    max_dim = max(mask.shape)
    downsample = max(1, max_dim // 250)

    if downsample > 1:
        small_mask = mask[::downsample, ::downsample]
    else:
        small_mask = mask

    sh, sw = small_mask.shape
    ds = downsample * scale  # mm per grid cell

    # Generate grid-based triangulation
    # For each pixel that's True, create 2 triangles for top face, 2 for bottom
    top_z = thickness
    bot_z = 0.0

    # Offset so that the model is centered
    offset_x = col_min * scale
    offset_y = row_min * scale

    # Count triangles needed
    n_filled = np.count_nonzero(small_mask)

    # Find boundary edges for side walls
    # A boundary edge exists where a filled pixel is adjacent to an empty pixel (or edge)
    padded = np.pad(small_mask, 1, mode='constant', constant_values=False)

    # Top/bottom face triangles: 2 per filled pixel
    # Side wall triangles: 2 per boundary edge
    boundary_right = small_mask & ~padded[1:-1, 2:]  # right neighbor empty
    boundary_left = small_mask & ~padded[1:-1, :-2]   # left neighbor empty
    boundary_down = small_mask & ~padded[2:, 1:-1]     # below neighbor empty
    boundary_up = small_mask & ~padded[:-2, 1:-1]      # above neighbor empty

    n_walls = (np.count_nonzero(boundary_right) + np.count_nonzero(boundary_left) +
               np.count_nonzero(boundary_down) + np.count_nonzero(boundary_up))

    n_total_triangles = n_filled * 2 * 2 + n_walls * 2  # top + bottom + walls
    print(f"  {name}: {n_filled} filled cells, {n_walls} boundary edges, "
          f"{n_total_triangles} triangles")

    stl_data = np.zeros(n_total_triangles, dtype=stl_mesh.Mesh.dtype)
    tri_idx = 0

    # Generate top and bottom face triangles
    filled_coords = np.argwhere(small_mask)  # (row, col) pairs

    for row, col in filled_coords:
        x0 = col * ds
        x1 = (col + 1) * ds
        y0 = (sh - row - 1) * ds
        y1 = (sh - row) * ds

        # Top face (z = top_z), normal pointing up (+z)
        # Triangle 1: (x0,y0) - (x1,y0) - (x1,y1)
        stl_data['vectors'][tri_idx] = [[x0, y0, top_z], [x1, y0, top_z], [x1, y1, top_z]]
        tri_idx += 1
        # Triangle 2: (x0,y0) - (x1,y1) - (x0,y1)
        stl_data['vectors'][tri_idx] = [[x0, y0, top_z], [x1, y1, top_z], [x0, y1, top_z]]
        tri_idx += 1

        # Bottom face (z = 0), normal pointing down (-z) — reverse winding
        stl_data['vectors'][tri_idx] = [[x0, y0, bot_z], [x1, y1, bot_z], [x1, y0, bot_z]]
        tri_idx += 1
        stl_data['vectors'][tri_idx] = [[x0, y0, bot_z], [x0, y1, bot_z], [x1, y1, bot_z]]
        tri_idx += 1

    # Generate side wall triangles
    # Right boundary: edge at x = (col+1)*ds, from y0 to y1
    for row, col in np.argwhere(boundary_right):
        x = (col + 1) * ds
        y0 = (sh - row - 1) * ds
        y1 = (sh - row) * ds
        # Wall facing right (+x normal)
        stl_data['vectors'][tri_idx] = [[x, y0, bot_z], [x, y1, bot_z], [x, y1, top_z]]
        tri_idx += 1
        stl_data['vectors'][tri_idx] = [[x, y0, bot_z], [x, y1, top_z], [x, y0, top_z]]
        tri_idx += 1

    # Left boundary: edge at x = col*ds
    for row, col in np.argwhere(boundary_left):
        x = col * ds
        y0 = (sh - row - 1) * ds
        y1 = (sh - row) * ds
        # Wall facing left (-x normal) — reverse winding
        stl_data['vectors'][tri_idx] = [[x, y0, bot_z], [x, y1, top_z], [x, y1, bot_z]]
        tri_idx += 1
        stl_data['vectors'][tri_idx] = [[x, y0, bot_z], [x, y0, top_z], [x, y1, top_z]]
        tri_idx += 1

    # Down boundary: edge at y = (row+1)*ds
    for row, col in np.argwhere(boundary_down):
        x0 = col * ds
        x1 = (col + 1) * ds
        y = (sh - row - 1) * ds
        # Wall facing down (+y normal)
        stl_data['vectors'][tri_idx] = [[x0, y, bot_z], [x0, y, top_z], [x1, y, top_z]]
        tri_idx += 1
        stl_data['vectors'][tri_idx] = [[x0, y, bot_z], [x1, y, top_z], [x1, y, bot_z]]
        tri_idx += 1

    # Up boundary: edge at y = row*ds
    for row, col in np.argwhere(boundary_up):
        x0 = col * ds
        x1 = (col + 1) * ds
        y = (sh - row) * ds
        # Wall facing up (-y normal) — reverse winding
        stl_data['vectors'][tri_idx] = [[x0, y, bot_z], [x1, y, top_z], [x0, y, top_z]]
        tri_idx += 1
        stl_data['vectors'][tri_idx] = [[x0, y, bot_z], [x1, y, bot_z], [x1, y, top_z]]
        tri_idx += 1

    # Trim if we over-allocated
    stl_data = stl_data[:tri_idx]

    # Create mesh and save
    m = stl_mesh.Mesh(stl_data)
    m.save(output_path)

    # Report size
    x_range = m.x.max() - m.x.min()
    y_range = m.y.max() - m.y.min()
    file_size = os.path.getsize(output_path)
    print(f"  Saved {output_path}")
    print(f"    Dimensions: {x_range:.1f} x {y_range:.1f} x {thickness:.1f} mm")
    print(f"    Triangles: {len(m.data)}, File size: {file_size/1024:.0f} KB")


# Generate all pieces
mask_to_flat_stl(green_mask, OUTPUT_GREEN, scale, THICKNESS_GREEN_MM, "green")

mask_to_flat_stl(fringe_mask, OUTPUT_FRINGE, scale, THICKNESS_FRINGE_MM, "fringe")

for i, tmask in enumerate(trap_masks):
    output = [OUTPUT_TRAP_1, OUTPUT_TRAP_2, OUTPUT_TRAP_3][i]
    mask_to_flat_stl(tmask, output, scale, THICKNESS_TRAP_MM, f"trap_{i+1}")

# ==========================================================================
# 6. Verify puzzle fit
# ==========================================================================
print("\n=== VERIFICATION ===")
# Check that green + fringe + traps approximately equals the overall mask
reconstructed = green_mask | fringe_mask | all_traps_mask
overlap_with_overall = np.count_nonzero(reconstructed & overall_mask)
total_overall = np.count_nonzero(overall_mask)
coverage = overlap_with_overall / total_overall if total_overall > 0 else 0
print(f"Coverage of overall area: {coverage:.1%}")

# Check for overlap between pieces
gf_overlap = np.count_nonzero(green_mask & fringe_mask)
gt_overlap = np.count_nonzero(green_mask & all_traps_mask)
ft_overlap = np.count_nonzero(fringe_mask & all_traps_mask)
print(f"Overlaps — green/fringe: {gf_overlap}, green/traps: {gt_overlap}, fringe/traps: {ft_overlap}")

# ==========================================================================
# 7. Generate debug overlay image
# ==========================================================================
print("\n=== GENERATING DEBUG IMAGE ===")
debug_img = crop.copy()

# Draw each piece mask contour in magenta
piece_masks = [
    (green_mask, "Green", (255, 0, 255)),
    (fringe_mask, "Fringe", (255, 0, 255)),
]
for tm_idx, tm in enumerate(trap_masks):
    piece_masks.append((tm, f"Trap {tm_idx+1}", (255, 0, 255)))

for pmask, pname, color in piece_masks:
    pmask_u8 = (pmask.astype(np.uint8)) * 255
    pcontours, _ = cv2.findContours(pmask_u8, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    cv2.drawContours(debug_img, pcontours, -1, color, 2)

# Also draw the distance limit boundary as a thin cyan line for reference
dist_limit_u8 = (distance_limit_mask.astype(np.uint8)) * 255
dist_contours, _ = cv2.findContours(dist_limit_u8, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
cv2.drawContours(debug_img, dist_contours, -1, (255, 255, 0), 1)

debug_path = os.path.join(OUTPUT_DIR, "debug_final_pieces.jpg")
cv2.imwrite(debug_path, debug_img)
print(f"  Saved debug image: {debug_path}")

print("\nDone! All pieces generated.")
