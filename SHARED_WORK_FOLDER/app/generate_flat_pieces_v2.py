#!/usr/bin/env python3
"""
generate_flat_pieces_v2.py  --  Universal GolfLogix Green Segmentation Pipeline
================================================================================
Coarse-to-fine segmentation of a GolfLogix hole screenshot into 3D-printable
STL pieces: putting green, fringe, and sand traps.

No hardcoded crop coordinates. All thresholds are relative/adaptive, computed
from the image itself (except sand trap HSV, which is proven stable).

Usage:
    python3 generate_flat_pieces_v2.py "path/to/image.png" --hole 9
"""

import argparse
import cv2
import numpy as np
from scipy.ndimage import binary_fill_holes
from stl import mesh as stl_mesh
import os
import sys

# ===========================================================================
# Constants
# ===========================================================================
PRINT_SIZE_MM = 178.0
THICKNESS_GREEN_MM = 30.0
THICKNESS_TRAP_MM = 20.0
THICKNESS_FRINGE_MM = 10.0

# Sand trap HSV thresholds (proven stable across holes)
TRAP_H_MIN, TRAP_H_MAX = 15, 34
TRAP_S_MIN, TRAP_S_MAX = 15, 60
TRAP_V_MIN = 200

MIN_TRAP_AREA = 400  # minimum pixels for a trap blob


# ===========================================================================
# Argument parsing
# ===========================================================================
def parse_args():
    parser = argparse.ArgumentParser(
        description="Generate flat 3D-printable STL pieces from a GolfLogix hole screenshot."
    )
    parser.add_argument("image", help="Path to input GolfLogix screenshot")
    parser.add_argument("--hole", type=int, required=True, help="Hole number (for output naming)")
    parser.add_argument("--output-dir", default=None,
                        help="Output directory (default: owner_inbox/ next to app/)")
    return parser.parse_args()


# ===========================================================================
# STL generation (reused from v1 with minor cleanup)
# ===========================================================================
def mask_to_flat_stl(mask, output_path, scale, thickness, row_min, col_min, name="piece"):
    """
    Convert a 2D boolean mask into a flat (cookie-cutter) STL mesh.

    Strategy:
    1. Downsample the mask to a manageable grid.
    2. For each filled cell, emit top-face and bottom-face triangle pairs.
    3. For each boundary edge (filled next to empty), emit side-wall triangles.
    """
    mask_u8 = (mask.astype(np.uint8)) * 255

    contours, _ = cv2.findContours(mask_u8, cv2.RETR_TREE, cv2.CHAIN_APPROX_SIMPLE)
    if not contours:
        print(f"  WARNING: No contours found for {name}")
        return False

    # Downsample for reasonable mesh size
    max_dim = max(mask.shape)
    downsample = max(1, max_dim // 250)

    if downsample > 1:
        small_mask = mask[::downsample, ::downsample]
    else:
        small_mask = mask

    sh, sw = small_mask.shape
    ds = downsample * scale  # mm per grid cell

    top_z = thickness
    bot_z = 0.0

    n_filled = np.count_nonzero(small_mask)
    if n_filled == 0:
        print(f"  WARNING: Empty mask for {name}")
        return False

    # Find boundary edges
    padded = np.pad(small_mask, 1, mode='constant', constant_values=False)
    boundary_right = small_mask & ~padded[1:-1, 2:]
    boundary_left = small_mask & ~padded[1:-1, :-2]
    boundary_down = small_mask & ~padded[2:, 1:-1]
    boundary_up = small_mask & ~padded[:-2, 1:-1]

    n_walls = (np.count_nonzero(boundary_right) + np.count_nonzero(boundary_left) +
               np.count_nonzero(boundary_down) + np.count_nonzero(boundary_up))

    n_total_triangles = n_filled * 2 * 2 + n_walls * 2
    print(f"  {name}: {n_filled} filled cells, {n_walls} boundary edges, "
          f"{n_total_triangles} triangles")

    stl_data = np.zeros(n_total_triangles, dtype=stl_mesh.Mesh.dtype)
    tri_idx = 0

    filled_coords = np.argwhere(small_mask)

    for row, col in filled_coords:
        x0 = col * ds
        x1 = (col + 1) * ds
        y0 = (sh - row - 1) * ds
        y1 = (sh - row) * ds

        # Top face
        stl_data['vectors'][tri_idx] = [[x0, y0, top_z], [x1, y0, top_z], [x1, y1, top_z]]
        tri_idx += 1
        stl_data['vectors'][tri_idx] = [[x0, y0, top_z], [x1, y1, top_z], [x0, y1, top_z]]
        tri_idx += 1

        # Bottom face (reversed winding)
        stl_data['vectors'][tri_idx] = [[x0, y0, bot_z], [x1, y1, bot_z], [x1, y0, bot_z]]
        tri_idx += 1
        stl_data['vectors'][tri_idx] = [[x0, y0, bot_z], [x0, y1, bot_z], [x1, y1, bot_z]]
        tri_idx += 1

    # Side walls
    for row, col in np.argwhere(boundary_right):
        x = (col + 1) * ds
        y0 = (sh - row - 1) * ds
        y1 = (sh - row) * ds
        stl_data['vectors'][tri_idx] = [[x, y0, bot_z], [x, y1, bot_z], [x, y1, top_z]]
        tri_idx += 1
        stl_data['vectors'][tri_idx] = [[x, y0, bot_z], [x, y1, top_z], [x, y0, top_z]]
        tri_idx += 1

    for row, col in np.argwhere(boundary_left):
        x = col * ds
        y0 = (sh - row - 1) * ds
        y1 = (sh - row) * ds
        stl_data['vectors'][tri_idx] = [[x, y0, bot_z], [x, y1, top_z], [x, y1, bot_z]]
        tri_idx += 1
        stl_data['vectors'][tri_idx] = [[x, y0, bot_z], [x, y0, top_z], [x, y1, top_z]]
        tri_idx += 1

    for row, col in np.argwhere(boundary_down):
        x0 = col * ds
        x1 = (col + 1) * ds
        y = (sh - row - 1) * ds
        stl_data['vectors'][tri_idx] = [[x0, y, bot_z], [x0, y, top_z], [x1, y, top_z]]
        tri_idx += 1
        stl_data['vectors'][tri_idx] = [[x0, y, bot_z], [x1, y, top_z], [x1, y, bot_z]]
        tri_idx += 1

    for row, col in np.argwhere(boundary_up):
        x0 = col * ds
        x1 = (col + 1) * ds
        y = (sh - row) * ds
        stl_data['vectors'][tri_idx] = [[x0, y, bot_z], [x1, y, top_z], [x0, y, top_z]]
        tri_idx += 1
        stl_data['vectors'][tri_idx] = [[x0, y, bot_z], [x1, y, bot_z], [x1, y, top_z]]
        tri_idx += 1

    stl_data = stl_data[:tri_idx]
    m = stl_mesh.Mesh(stl_data)
    m.save(output_path)

    x_range = m.x.max() - m.x.min()
    y_range = m.y.max() - m.y.min()
    file_size = os.path.getsize(output_path)
    print(f"  Saved {output_path}")
    print(f"    Dimensions: {x_range:.1f} x {y_range:.1f} x {thickness:.1f} mm")
    print(f"    Triangles: {len(m.data)}, File size: {file_size/1024:.0f} KB")
    return True


# ===========================================================================
# STEP 1: Segment the green complex from the dark background
# ===========================================================================
def segment_complex(img_bgr):
    """
    Detect the entire green complex (putting surface + fringe + traps) as a
    single bright/colorful island against the dark fairway background.

    Strategy: The green complex contains the colorful contour bands (non-green
    hues like blue, cyan, yellow, orange, red with high saturation) plus the
    fringe (dark muted green) and traps (cream/beige). The fairway is uniform
    green with moderate saturation.

    We detect the "colorful interior" first (contour bands), then expand outward
    to include the surrounding fringe/trap area using morphological dilation
    constrained by a brightness floor.

    Returns the complex mask (bool).
    """
    print("\n=== STEP 1: SEGMENT GREEN COMPLEX FROM BACKGROUND ===")

    h, w = img_bgr.shape[:2]
    hsv = cv2.cvtColor(img_bgr, cv2.COLOR_BGR2HSV)
    hue = hsv[:, :, 0].astype(float)
    sat = hsv[:, :, 1].astype(float)
    val = hsv[:, :, 2].astype(float)

    # -- A. Detect colorful contour bands (the defining feature of the green) --
    # These have non-green hues (blue, cyan, orange, red, yellow) AND high saturation.
    # In OpenCV HSV: green hue ~ 35-85. Everything outside that range with sat>80
    # is likely a contour band.
    non_green_colorful = (
        ((hue < 35) | (hue > 85)) &
        (sat > 80) &
        (val > 60)
    )
    # Also include very saturated green-ish pixels (the teal/cyan bands)
    # that are more saturated than the fairway
    very_saturated_green = (
        (hue >= 35) & (hue <= 100) &
        (sat > 150) &
        (val > 80)
    )
    contour_bands = non_green_colorful | very_saturated_green

    contour_area = np.count_nonzero(contour_bands)
    print(f"  Contour band pixels: {contour_area} ({100*contour_area/(h*w):.1f}% of image)")

    # -- B. Also detect sand trap pixels (they're part of the complex) --
    trap_pixels = (
        (hue >= TRAP_H_MIN) & (hue <= TRAP_H_MAX) &
        (sat >= TRAP_S_MIN) & (sat <= TRAP_S_MAX) &
        (val >= TRAP_V_MIN)
    )

    # -- C. Build the core from contour bands --
    # Close the contour band mask to form the putting surface outline,
    # then fill the interior. Do NOT include traps in the seed -- they
    # are far away and would cause fill to span the whole image.
    contour_u8 = (contour_bands.astype(np.uint8)) * 255

    # Close with a moderate kernel to merge nearby band pixels into a solid shape
    kernel = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (15, 15))
    contour_u8 = cv2.morphologyEx(contour_u8, cv2.MORPH_CLOSE, kernel, iterations=4)

    # Keep only the largest connected blob of contour bands
    n_cb, cb_labels, cb_stats, _ = cv2.connectedComponentsWithStats(contour_u8)
    if n_cb > 2:
        cb_areas = cb_stats[1:, cv2.CC_STAT_AREA]
        cb_largest = 1 + np.argmax(cb_areas)
        contour_u8 = ((cb_labels == cb_largest) * 255).astype(np.uint8)

    # Fill holes -- this fills the interior of the putting green
    contour_filled = binary_fill_holes(contour_u8 > 0)
    core_mask = contour_filled
    core_area = np.count_nonzero(core_mask)
    print(f"  Core (contour bands closed + filled): {core_area} pixels")

    # Sanity: core should be < 60% of image; if not, the fill leaked
    if core_area > 0.60 * (h * w):
        print("  WARNING: Core fill leaked -- falling back to convex hull of contour bands")
        # Use convex hull of the contour band pixels instead
        band_points = np.argwhere(contour_bands)  # (row, col)
        if len(band_points) > 5:
            # Convert to cv2 format (x, y)
            pts_cv = band_points[:, ::-1].reshape(-1, 1, 2).astype(np.int32)
            hull = cv2.convexHull(pts_cv)
            core_mask_u8 = np.zeros((h, w), dtype=np.uint8)
            cv2.fillPoly(core_mask_u8, [hull], 255)
            core_mask = core_mask_u8 > 0
            core_area = np.count_nonzero(core_mask)
            print(f"  Convex hull core: {core_area} pixels")

    # Now also merge trap pixels into the core for the complex boundary
    # (but not for the fill step above)
    core_plus_traps = core_mask | trap_pixels

    # Keep the largest connected component
    cpt_u8 = (core_plus_traps.astype(np.uint8)) * 255
    n_labels, labels, stats, centroids = cv2.connectedComponentsWithStats(cpt_u8)
    if n_labels < 2:
        print("  WARNING: No complex seed detected! Using full image.")
        return np.ones((h, w), dtype=bool)

    areas = stats[1:, cv2.CC_STAT_AREA]
    largest_label = 1 + np.argmax(areas)
    core_mask = (labels == largest_label)
    core_area = np.count_nonzero(core_mask)
    print(f"  Core + traps (largest component): {core_area} pixels")

    # -- D. Expand outward to include the fringe --
    # The fringe is the dark green border around the putting surface.
    # Dilate the core generously, then intersect with "not obviously fairway."
    # The fairway has a distinct uniform texture; the fringe is darker.

    # Compute the equivalent radius of the core for proportional dilation
    core_equiv_radius = np.sqrt(core_area / np.pi)
    # Fringe typically extends ~15-25% of the green radius
    expand_pixels = int(core_equiv_radius * 0.2)
    expand_pixels = max(expand_pixels, 15)  # minimum expansion
    print(f"  Core equiv radius: {core_equiv_radius:.0f} px, expanding by {expand_pixels} px")

    # Dilate the core
    expand_kernel = cv2.getStructuringElement(cv2.MORPH_ELLIPSE,
                                               (2*expand_pixels+1, 2*expand_pixels+1))
    expanded_u8 = cv2.dilate((core_mask.astype(np.uint8)) * 255, expand_kernel, iterations=1)

    # Constrain: only keep expanded pixels that are NOT bright fairway
    # Fairway is moderate green (hue 35-85, sat 40-130, val 50-180)
    # The fringe is DARKER than the fairway (lower value) or has different character.
    # We use a permissive constraint: exclude pixels that are clearly "far away"
    # open grass (very uniform green with moderate brightness).

    # Actually, a simpler approach: just use the expanded mask as-is, since the
    # dilation is proportional and won't reach the fairway if sized right.
    # But add a value floor to exclude the very dark image borders.
    value_floor = (val > 25)
    complex_mask = (expanded_u8 > 0) & value_floor

    # Fill holes
    complex_mask = binary_fill_holes(complex_mask)

    # Smooth the boundary
    complex_u8 = (complex_mask.astype(np.uint8)) * 255
    complex_u8 = cv2.GaussianBlur(complex_u8, (21, 21), 0)
    _, complex_u8 = cv2.threshold(complex_u8, 127, 255, cv2.THRESH_BINARY)
    complex_mask = complex_u8 > 0

    # Keep largest component
    n_labels2, labels2, stats2, centroids2 = cv2.connectedComponentsWithStats(complex_u8)
    if n_labels2 > 2:
        areas2 = stats2[1:, cv2.CC_STAT_AREA]
        largest2 = 1 + np.argmax(areas2)
        complex_mask = (labels2 == largest2)

    complex_area = np.count_nonzero(complex_mask)
    total_pixels = h * w
    print(f"  Complex area: {complex_area} pixels ({100*complex_area/total_pixels:.1f}% of image)")

    # Sanity check: if complex > 80% of image, the segmentation likely failed
    if complex_area > 0.80 * total_pixels:
        print("  WARNING: Complex covers >80% of image -- tightening expansion")
        # Fall back to just the core with a small expansion
        small_expand = max(10, int(core_equiv_radius * 0.1))
        small_kernel = cv2.getStructuringElement(cv2.MORPH_ELLIPSE,
                                                  (2*small_expand+1, 2*small_expand+1))
        expanded_u8 = cv2.dilate((core_mask.astype(np.uint8)) * 255, small_kernel, iterations=1)
        complex_mask = binary_fill_holes(expanded_u8 > 0)
        complex_u8 = (complex_mask.astype(np.uint8)) * 255
        complex_u8 = cv2.GaussianBlur(complex_u8, (21, 21), 0)
        _, complex_u8 = cv2.threshold(complex_u8, 127, 255, cv2.THRESH_BINARY)
        complex_mask = complex_u8 > 0
        complex_area = np.count_nonzero(complex_mask)
        print(f"  Tightened complex: {complex_area} pixels ({100*complex_area/total_pixels:.1f}% of image)")

    return complex_mask


# ===========================================================================
# STEP 2: Remove UI elements
# ===========================================================================
def remove_ui_elements(img_bgr, complex_mask):
    """
    Detect and inpaint GolfLogix UI overlays: white circles, info boxes,
    the white distance line, etc.

    Returns the cleaned image.
    """
    print("\n=== STEP 2: REMOVE UI ELEMENTS ===")

    h, w = img_bgr.shape[:2]
    cleaned = img_bgr.copy()
    gray = cv2.cvtColor(img_bgr, cv2.COLOR_BGR2GRAY)
    hsv = cv2.cvtColor(img_bgr, cv2.COLOR_BGR2HSV)
    val = hsv[:, :, 2].astype(float)
    sat = hsv[:, :, 1].astype(float)

    ui_mask = np.zeros((h, w), dtype=np.uint8)
    ui_count = 0

    # --- A. White circles (yardage markers) ---
    circles = cv2.HoughCircles(
        gray, cv2.HOUGH_GRADIENT, dp=1.2, minDist=20,
        param1=80, param2=30, minRadius=8, maxRadius=50
    )
    if circles is not None:
        for (cx, cy, r) in np.round(circles[0]).astype(int):
            mask_circle = np.zeros((h, w), dtype=np.uint8)
            cv2.circle(mask_circle, (cx, cy), r, 255, -1)
            circle_val = val[mask_circle > 0].mean()
            circle_sat = sat[mask_circle > 0].mean()
            if circle_val > 160 and circle_sat < 80:
                cv2.circle(ui_mask, (cx, cy), r + 4, 255, -1)
                ui_count += 1
                print(f"  Removed circle at ({cx},{cy}) r={r}")

    # --- B. White distance line ---
    # The line is a thin, bright, near-vertical feature running from the green
    # toward the bottom of the image. Detect as a bright narrow column region.
    # Look for columns where many pixels are very bright and low saturation.
    white_line_mask = (val > 220) & (sat < 30)
    white_line_u8 = (white_line_mask.astype(np.uint8)) * 255

    # Find thin vertical structures via morphological filtering
    # Use a tall narrow kernel to isolate vertical lines
    vert_kernel = cv2.getStructuringElement(cv2.MORPH_RECT, (3, 30))
    vert_features = cv2.morphologyEx(white_line_u8, cv2.MORPH_OPEN, vert_kernel)

    if np.any(vert_features > 0):
        # Dilate slightly to cover the full line width
        line_dilate = cv2.dilate(vert_features, cv2.getStructuringElement(cv2.MORPH_RECT, (7, 3)), iterations=1)
        ui_mask = cv2.bitwise_or(ui_mask, line_dilate)
        line_pixels = np.count_nonzero(vert_features)
        if line_pixels > 50:
            ui_count += 1
            print(f"  Removed white distance line ({line_pixels} pixels)")

    # --- C. Bright UI rectangles (white/light info boxes) ---
    # These are bright (V>200), low saturation, compact blobs
    bright_ui = (val > 200) & (sat < 30)
    bright_ui_u8 = (bright_ui.astype(np.uint8)) * 255
    kernel_ui = cv2.getStructuringElement(cv2.MORPH_RECT, (5, 5))
    bright_ui_u8 = cv2.morphologyEx(bright_ui_u8, cv2.MORPH_CLOSE, kernel_ui, iterations=2)
    contours_bui, _ = cv2.findContours(bright_ui_u8, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    for cnt in contours_bui:
        area = cv2.contourArea(cnt)
        x, y, bw, bh = cv2.boundingRect(cnt)
        aspect = max(bw, bh) / max(min(bw, bh), 1)
        if 300 < area < 15000 and aspect < 5 and bw < 200 and bh < 200:
            cv2.drawContours(ui_mask, [cnt], -1, 255, -1)
            ui_count += 1
            print(f"  Removed bright UI rect at ({x},{y}) {bw}x{bh}")

    # --- D. Dark UI rectangles (dark bg with white text) ---
    dark_ui = (gray < 40).astype(np.uint8) * 255
    kernel_dark = cv2.getStructuringElement(cv2.MORPH_RECT, (7, 7))
    dark_ui = cv2.morphologyEx(dark_ui, cv2.MORPH_CLOSE, kernel_dark, iterations=3)
    contours_dui, _ = cv2.findContours(dark_ui, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    for cnt in contours_dui:
        area = cv2.contourArea(cnt)
        x, y, bw, bh = cv2.boundingRect(cnt)
        if area < 800 or bw > 300 or bh > 300:
            continue
        roi_mask = np.zeros((h, w), dtype=np.uint8)
        cv2.drawContours(roi_mask, [cnt], -1, 255, -1)
        roi_vals = gray[roi_mask > 0]
        bright_ratio = np.sum(roi_vals > 180) / max(len(roi_vals), 1)
        dark_ratio = np.sum(roi_vals < 40) / max(len(roi_vals), 1)
        if dark_ratio > 0.4 and 0.05 < bright_ratio < 0.6:
            cv2.drawContours(ui_mask, [cnt], -1, 255, -1)
            ui_count += 1
            print(f"  Removed dark UI rect at ({x},{y}) {bw}x{bh}")

    # --- E. Semi-transparent info cards (top portion) ---
    top_cutoff = int(h * 0.35)
    semi = (val[:top_cutoff, :] > 100) & (val[:top_cutoff, :] < 210) & (sat[:top_cutoff, :] < 60)
    semi_u8 = (semi.astype(np.uint8)) * 255
    semi_u8 = cv2.morphologyEx(semi_u8, cv2.MORPH_CLOSE,
                                cv2.getStructuringElement(cv2.MORPH_RECT, (10, 10)), iterations=3)
    contours_semi, _ = cv2.findContours(semi_u8, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    for cnt in contours_semi:
        area = cv2.contourArea(cnt)
        x, y, bw, bh = cv2.boundingRect(cnt)
        aspect = max(bw, bh) / max(min(bw, bh), 1)
        if 2000 < area < 40000 and aspect < 3 and bw < 250 and bh < 250:
            roi_mask_s = np.zeros((top_cutoff, w), dtype=np.uint8)
            cv2.drawContours(roi_mask_s, [cnt], -1, 255, -1)
            roi_vals_s = gray[:top_cutoff, :][roi_mask_s > 0]
            white_ratio = np.sum(roi_vals_s > 200) / max(len(roi_vals_s), 1)
            if white_ratio > 0.05:
                full_roi = np.zeros((h, w), dtype=np.uint8)
                full_roi[:top_cutoff, :] = roi_mask_s
                ui_mask = cv2.bitwise_or(ui_mask, full_roi)
                ui_count += 1
                print(f"  Removed info card at ({x},{y}) {bw}x{bh}")

    # Inpaint
    if np.any(ui_mask > 0):
        ui_mask = cv2.dilate(ui_mask, cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (5, 5)), iterations=1)
        cleaned = cv2.inpaint(cleaned, ui_mask, inpaintRadius=10, flags=cv2.INPAINT_TELEA)

    print(f"  Total UI elements removed: {ui_count}")
    return cleaned


# ===========================================================================
# STEP 3: Identify sand traps within the complex
# ===========================================================================
def detect_traps(img_bgr, complex_mask):
    """
    Detect sand traps using proven HSV thresholds (H15-34, S15-60, V200+).
    Only keep blobs within/adjacent to the complex mask.

    Returns a list of individual trap masks (bool) and the combined trap mask.
    """
    print("\n=== STEP 3: DETECT SAND TRAPS ===")

    h, w = img_bgr.shape[:2]
    hsv = cv2.cvtColor(img_bgr, cv2.COLOR_BGR2HSV)
    hue = hsv[:, :, 0].astype(float)
    sat = hsv[:, :, 1].astype(float)
    val = hsv[:, :, 2].astype(float)

    # Core trap pixels
    trap_core = (
        (hue >= TRAP_H_MIN) & (hue <= TRAP_H_MAX) &
        (sat >= TRAP_S_MIN) & (sat <= TRAP_S_MAX) &
        (val >= TRAP_V_MIN)
    )

    # Gray border pixels (only kept if adjacent to core)
    trap_gray = (sat < 20) & (val >= 160)
    kernel_near = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (9, 9))
    core_dilated = cv2.dilate((trap_core.astype(np.uint8)) * 255, kernel_near, iterations=1)
    trap_u8 = ((trap_core.astype(np.uint8)) * 255) | (((trap_gray.astype(np.uint8)) * 255) & core_dilated)

    # Morphological cleanup
    kernel_close = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (11, 11))
    trap_u8 = cv2.morphologyEx(trap_u8, cv2.MORPH_CLOSE, kernel_close, iterations=3)
    kernel_open = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (7, 7))
    trap_u8 = cv2.morphologyEx(trap_u8, cv2.MORPH_OPEN, kernel_open, iterations=2)

    # Fill holes
    trap_filled = binary_fill_holes(trap_u8 > 0)
    trap_u8 = (trap_filled.astype(np.uint8)) * 255

    # Restrict to within or near the complex.
    # Use a very generous dilation so traps at the edge aren't clipped.
    # Traps can be quite far from the green boundary on some holes.
    complex_dilated = cv2.dilate(
        (complex_mask.astype(np.uint8)) * 255,
        cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (101, 101)),
        iterations=1
    )
    trap_u8 = trap_u8 & complex_dilated

    # Connected components
    n_labels, labels, stats, centroids = cv2.connectedComponentsWithStats(trap_u8)

    valid_traps = []
    for i in range(1, n_labels):
        area = stats[i, cv2.CC_STAT_AREA]
        if area >= MIN_TRAP_AREA:
            valid_traps.append((i, area, centroids[i]))
            print(f"  Trap candidate: area={area}, centroid=({centroids[i][0]:.0f}, {centroids[i][1]:.0f})")

    # Sort by area descending
    valid_traps.sort(key=lambda x: x[1], reverse=True)

    # Filter: keep traps that are at least 10% the size of the largest
    if valid_traps:
        largest_area = valid_traps[0][1]
        min_relative = max(MIN_TRAP_AREA, int(largest_area * 0.10))
        valid_traps = [t for t in valid_traps if t[1] >= min_relative]
        print(f"  Relative area threshold: {min_relative} px (10% of largest)")

    print(f"  Found {len(valid_traps)} trap(s) after filtering")

    # Create individual smoothed trap masks
    trap_masks = []
    for idx, (label_id, area, centroid) in enumerate(valid_traps):
        mask = (labels == label_id)
        mask_u8 = (mask.astype(np.uint8)) * 255
        # Smooth edges
        kernel_smooth = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (7, 7))
        mask_u8 = cv2.morphologyEx(mask_u8, cv2.MORPH_CLOSE, kernel_smooth, iterations=2)
        mask_u8 = cv2.GaussianBlur(mask_u8, (21, 21), 0)
        _, mask_u8 = cv2.threshold(mask_u8, 127, 255, cv2.THRESH_BINARY)
        kernel_final = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (9, 9))
        mask_u8 = cv2.morphologyEx(mask_u8, cv2.MORPH_OPEN, kernel_final, iterations=1)
        mask_u8 = cv2.morphologyEx(mask_u8, cv2.MORPH_CLOSE, kernel_final, iterations=1)
        mask_bool = mask_u8 > 0
        trap_masks.append(mask_bool)
        print(f"  Trap {idx+1}: {np.count_nonzero(mask_bool)} pixels")

    # Combined mask
    all_traps = np.zeros((h, w), dtype=bool)
    for tm in trap_masks:
        all_traps |= tm

    return trap_masks, all_traps


# ===========================================================================
# STEP 4: Separate putting green from fringe using RELATIVE saturation
# ===========================================================================
def segment_green_from_fringe(img_bgr, complex_mask, all_traps_mask):
    """
    Within the complex (minus traps), separate the putting surface from the
    fringe using relative saturation analysis.

    The putting surface has colorful contour bands (high saturation).
    The fringe is low-saturation dark green.

    Uses Otsu's method on the saturation channel within the complex,
    then region-grows from the highest-saturation area.

    Returns the green mask (bool).
    """
    print("\n=== STEP 4: SEPARATE GREEN FROM FRINGE (relative saturation) ===")

    h, w = img_bgr.shape[:2]
    hsv = cv2.cvtColor(img_bgr, cv2.COLOR_BGR2HSV)
    hue = hsv[:, :, 0].astype(float)
    sat = hsv[:, :, 1].astype(float)
    val = hsv[:, :, 2].astype(float)

    # Region of interest: complex minus traps
    roi_mask = complex_mask & (~all_traps_mask)
    roi_pixels_sat = sat[roi_mask]
    roi_pixels_val = val[roi_mask]

    if len(roi_pixels_sat) == 0:
        print("  WARNING: No ROI pixels for green/fringe separation!")
        return np.zeros((h, w), dtype=bool)

    # Statistics within the ROI
    sat_mean = roi_pixels_sat.mean()
    sat_std = roi_pixels_sat.std()
    sat_median = np.median(roi_pixels_sat)
    val_mean = roi_pixels_val.mean()
    print(f"  ROI saturation: mean={sat_mean:.1f}, std={sat_std:.1f}, median={sat_median:.1f}")
    print(f"  ROI value: mean={val_mean:.1f}")

    # The putting surface is characterized by the colorful contour bands.
    # Approach: detect pixels that are part of the contour-band region
    # (non-green hues with high saturation, OR very high saturation green).
    # Then fill the interior between the bands.

    # Contour band detection within ROI
    non_green_in_roi = roi_mask & (
        ((hue < 35) | (hue > 85)) &
        (sat > 70) &
        (val > 50)
    )
    high_sat_green_in_roi = roi_mask & (
        (hue >= 35) & (hue <= 100) &
        (sat > 130) &
        (val > 60)
    )
    contour_pixels = non_green_in_roi | high_sat_green_in_roi

    contour_count = np.count_nonzero(contour_pixels)
    roi_count = np.count_nonzero(roi_mask)
    print(f"  Contour band pixels in ROI: {contour_count} ({100*contour_count/max(roi_count,1):.1f}%)")

    # Close the contour band mask heavily to fill the interior
    contour_u8 = (contour_pixels.astype(np.uint8)) * 255
    kernel_close = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (21, 21))
    contour_u8 = cv2.morphologyEx(contour_u8, cv2.MORPH_CLOSE, kernel_close, iterations=5)

    # Fill holes -- the bands surround the interior
    contour_filled = binary_fill_holes(contour_u8 > 0)
    contour_u8 = (contour_filled.astype(np.uint8)) * 255

    # Keep only the largest component
    n_labels, labels, stats, centroids = cv2.connectedComponentsWithStats(contour_u8)
    if n_labels < 2:
        print("  WARNING: No green detected from contour bands!")
        # Fallback: use Otsu on saturation
        roi_sat_vals = np.clip(sat[roi_mask], 0, 255).astype(np.uint8)
        otsu_thresh, _ = cv2.threshold(roi_sat_vals, 0, 255,
                                        cv2.THRESH_BINARY + cv2.THRESH_OTSU)
        print(f"  Fallback Otsu threshold: {otsu_thresh:.1f}")
        green_candidate = roi_mask & (sat >= otsu_thresh)
        green_u8 = (green_candidate.astype(np.uint8)) * 255
        kernel = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (11, 11))
        green_u8 = cv2.morphologyEx(green_u8, cv2.MORPH_CLOSE, kernel, iterations=4)
        green_filled = binary_fill_holes(green_u8 > 0)
        green_mask = green_filled & roi_mask
        green_area = np.count_nonzero(green_mask)
        complex_area = np.count_nonzero(complex_mask)
        print(f"  Green area (fallback): {green_area} pixels "
              f"({100*green_area/max(complex_area,1):.1f}% of complex)")
        return green_mask

    areas = stats[1:, cv2.CC_STAT_AREA]
    largest_label = 1 + np.argmax(areas)
    green_mask = (labels == largest_label)

    # Constrain to ROI
    green_mask = green_mask & roi_mask

    # Smooth the green boundary
    green_u8 = (green_mask.astype(np.uint8)) * 255
    green_u8 = cv2.GaussianBlur(green_u8, (21, 21), 0)
    _, green_u8 = cv2.threshold(green_u8, 127, 255, cv2.THRESH_BINARY)

    # Fill holes one more time after smoothing
    green_mask = binary_fill_holes(green_u8 > 0)

    # Clip to complex minus traps
    green_mask = green_mask & complex_mask & (~all_traps_mask)

    green_area = np.count_nonzero(green_mask)
    complex_area = np.count_nonzero(complex_mask)
    print(f"  Green area: {green_area} pixels ({100*green_area/max(complex_area,1):.1f}% of complex)")

    return green_mask


# ===========================================================================
# STEP 5: Fringe = complex minus green minus traps
# ===========================================================================
def compute_fringe(complex_mask, green_mask, all_traps_mask):
    """Fringe is whatever remains in the complex after removing green and traps.
    Keep only the largest connected component and smooth."""
    print("\n=== STEP 5: COMPUTE FRINGE ===")
    fringe_mask = complex_mask & (~green_mask) & (~all_traps_mask)

    # Keep only the largest connected component to remove scattered fragments
    fringe_u8 = (fringe_mask.astype(np.uint8)) * 255
    n_labels, labels, stats, _ = cv2.connectedComponentsWithStats(fringe_u8)
    if n_labels > 2:
        areas = stats[1:, cv2.CC_STAT_AREA]
        largest = 1 + np.argmax(areas)
        fringe_mask = (labels == largest)
        print(f"  Kept largest fringe component ({areas.max()} px), "
              f"removed {n_labels - 2} small fragments")
    elif n_labels == 2:
        fringe_mask = (labels == 1)

    # Smooth the fringe boundary
    fringe_u8 = (fringe_mask.astype(np.uint8)) * 255
    fringe_u8 = cv2.GaussianBlur(fringe_u8, (15, 15), 0)
    _, fringe_u8 = cv2.threshold(fringe_u8, 127, 255, cv2.THRESH_BINARY)
    fringe_mask = fringe_u8 > 0

    # Re-enforce: no overlap with green or traps
    fringe_mask = fringe_mask & (~green_mask) & (~all_traps_mask)

    fringe_area = np.count_nonzero(fringe_mask)
    complex_area = np.count_nonzero(complex_mask)
    print(f"  Fringe area: {fringe_area} pixels ({100*fringe_area/max(complex_area,1):.1f}% of complex)")
    return fringe_mask


# ===========================================================================
# STEP 6: Generate flat STL meshes
# ===========================================================================
def generate_stls(green_mask, fringe_mask, trap_masks, overall_mask, output_dir, hole):
    """Generate STL files for all pieces."""
    print("\n=== STEP 6: GENERATE STL FILES ===")

    h, w = overall_mask.shape

    # Calculate scale
    rows_used = np.any(overall_mask, axis=1)
    cols_used = np.any(overall_mask, axis=0)
    if not np.any(rows_used) or not np.any(cols_used):
        print("  ERROR: Overall mask is empty!")
        return

    row_min = np.argmax(rows_used)
    row_max = h - 1 - np.argmax(rows_used[::-1])
    col_min = np.argmax(cols_used)
    col_max = w - 1 - np.argmax(cols_used[::-1])

    pixel_extent = max(row_max - row_min, col_max - col_min)
    scale = PRINT_SIZE_MM / pixel_extent
    print(f"  Scale: {scale:.4f} mm/pixel")
    print(f"  Piece dimensions: ~{(col_max - col_min) * scale:.1f} x {(row_max - row_min) * scale:.1f} mm")

    # Green
    green_path = os.path.join(output_dir, f"moffett_{hole}_green.stl")
    mask_to_flat_stl(green_mask, green_path, scale, THICKNESS_GREEN_MM, row_min, col_min, "green")

    # Fringe
    fringe_path = os.path.join(output_dir, f"moffett_{hole}_fringe.stl")
    mask_to_flat_stl(fringe_mask, fringe_path, scale, THICKNESS_FRINGE_MM, row_min, col_min, "fringe")

    # Traps
    for i, tmask in enumerate(trap_masks):
        trap_path = os.path.join(output_dir, f"moffett_{hole}_trap_{i+1}.stl")
        mask_to_flat_stl(tmask, trap_path, scale, THICKNESS_TRAP_MM, row_min, col_min, f"trap_{i+1}")


# ===========================================================================
# STEP 7: Debug output
# ===========================================================================
def generate_debug_image(img_bgr, green_mask, fringe_mask, trap_masks, complex_mask, output_dir):
    """Save debug overlay with magenta contour outlines for all pieces."""
    print("\n=== STEP 7: GENERATE DEBUG IMAGE ===")

    debug_img = img_bgr.copy()
    color = (255, 0, 255)  # magenta

    pieces = [
        (green_mask, "Green"),
        (fringe_mask, "Fringe"),
    ]
    for i, tm in enumerate(trap_masks):
        pieces.append((tm, f"Trap {i+1}"))

    for pmask, pname in pieces:
        pmask_u8 = (pmask.astype(np.uint8)) * 255
        pcontours, _ = cv2.findContours(pmask_u8, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
        cv2.drawContours(debug_img, pcontours, -1, color, 2)
        print(f"  Drew {pname} contour ({len(pcontours)} component(s))")

    # Draw complex boundary in cyan for reference
    complex_u8 = (complex_mask.astype(np.uint8)) * 255
    complex_contours, _ = cv2.findContours(complex_u8, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    cv2.drawContours(debug_img, complex_contours, -1, (255, 255, 0), 1)

    debug_path = os.path.join(output_dir, "debug_final_pieces.jpg")
    cv2.imwrite(debug_path, debug_img)
    print(f"  Saved debug image: {debug_path}")


# ===========================================================================
# STEP 8: Verification
# ===========================================================================
def verify(green_mask, fringe_mask, trap_masks, complex_mask):
    """Print coverage and overlap statistics."""
    print("\n=== STEP 8: VERIFICATION ===")

    all_traps = np.zeros_like(green_mask, dtype=bool)
    for tm in trap_masks:
        all_traps |= tm

    reconstructed = green_mask | fringe_mask | all_traps
    total_complex = np.count_nonzero(complex_mask)
    coverage = np.count_nonzero(reconstructed & complex_mask) / max(total_complex, 1)
    print(f"  Coverage of complex: {coverage:.1%}")

    # Pieces outside complex
    outside = np.count_nonzero(reconstructed & (~complex_mask))
    print(f"  Pixels outside complex: {outside}")

    # Overlaps
    gf = np.count_nonzero(green_mask & fringe_mask)
    gt = np.count_nonzero(green_mask & all_traps)
    ft = np.count_nonzero(fringe_mask & all_traps)
    print(f"  Overlaps -- green/fringe: {gf}, green/traps: {gt}, fringe/traps: {ft}")

    # Piece sizes
    print(f"  Green: {np.count_nonzero(green_mask)} px")
    print(f"  Fringe: {np.count_nonzero(fringe_mask)} px")
    for i, tm in enumerate(trap_masks):
        print(f"  Trap {i+1}: {np.count_nonzero(tm)} px")


# ===========================================================================
# MAIN
# ===========================================================================
def main():
    args = parse_args()

    # Resolve paths
    image_path = args.image
    hole = args.hole

    # Default output dir: owner_inbox/ sibling to app/
    if args.output_dir:
        output_dir = args.output_dir
    else:
        script_dir = os.path.dirname(os.path.abspath(__file__))
        output_dir = os.path.join(os.path.dirname(script_dir), "owner_inbox")

    os.makedirs(output_dir, exist_ok=True)

    print(f"Input image: {image_path}")
    print(f"Hole: {hole}")
    print(f"Output dir: {output_dir}")

    # Load image
    img = cv2.imread(image_path)
    if img is None:
        print(f"ERROR: Cannot read image: {image_path}")
        sys.exit(1)

    h, w = img.shape[:2]
    print(f"Image size: {w}x{h}")

    # Step 1: Segment the green complex
    complex_mask = segment_complex(img)

    # Step 2: Remove UI elements
    cleaned = remove_ui_elements(img, complex_mask)

    # Step 3: Detect sand traps (use original image for trap detection,
    # since UI removal might alter trap-colored pixels)
    trap_masks, all_traps = detect_traps(img, complex_mask)

    # Expand complex to include all trap pixels (traps may extend beyond the
    # initial complex boundary)
    if np.any(all_traps & (~complex_mask)):
        expanded = complex_mask | all_traps
        # Dilate slightly to create fringe around traps too
        trap_border = cv2.dilate(
            (all_traps.astype(np.uint8)) * 255,
            cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (15, 15)),
            iterations=1
        ) > 0
        complex_mask = expanded | trap_border
        # Fill and smooth
        complex_mask = binary_fill_holes(complex_mask)
        complex_u8 = (complex_mask.astype(np.uint8)) * 255
        complex_u8 = cv2.GaussianBlur(complex_u8, (15, 15), 0)
        _, complex_u8 = cv2.threshold(complex_u8, 127, 255, cv2.THRESH_BINARY)
        complex_mask = complex_u8 > 0
        print(f"  Complex expanded to include traps: {np.count_nonzero(complex_mask)} pixels")

    # Step 4: Separate green from fringe (use cleaned image)
    green_mask = segment_green_from_fringe(cleaned, complex_mask, all_traps)

    # Step 5: Compute fringe
    fringe_mask = compute_fringe(complex_mask, green_mask, all_traps)

    # Step 6: Generate STLs
    overall_mask = complex_mask  # the complex IS the overall boundary
    generate_stls(green_mask, fringe_mask, trap_masks, overall_mask, output_dir, hole)

    # Step 7: Debug image
    generate_debug_image(img, green_mask, fringe_mask, trap_masks, complex_mask, output_dir)

    # Step 8: Verification
    verify(green_mask, fringe_mask, trap_masks, complex_mask)

    print("\nDone! All pieces generated.")


if __name__ == "__main__":
    main()
