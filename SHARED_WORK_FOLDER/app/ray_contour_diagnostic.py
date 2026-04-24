"""
ray_contour_diagnostic.py — Ray-casting approach to find contour lines in a golf green image.

Phase 1: Cast a ray from the green centroid outward until a black pixel cluster is hit.
Phase 2: From the hit point, walk outward along K sub-rays to trace the contour edge.

Outputs: owner_inbox/debug_ray_contour.png
         owner_inbox/debug_mask_after_phase2.png
"""

from __future__ import annotations

import json
import math
import os
import sys

import cv2
import numpy as np

# ---------------------------------------------------------------------------
# Paths
# ---------------------------------------------------------------------------

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
EGM_PATH = os.path.join(REPO_ROOT, "owner_inbox", "Moffett Filed gimp (Hole 7).egm")
TEAM_INBOX = os.path.join(REPO_ROOT, "team_inbox")
OWNER_INBOX = os.path.join(REPO_ROOT, "owner_inbox")
OUTPUT_PATH = os.path.join(OWNER_INBOX, "debug_ray_contour.png")

# Add app/ to path so we can import generate_stl_3mf
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from generate_stl_3mf import interpolate_catmull_rom, remove_arrows_from_green

# ---------------------------------------------------------------------------
# Parameters
# ---------------------------------------------------------------------------

DARK_THRESHOLD = 50      # HSV Value < this → "black" pixel
PROBE_RADIUS = 3         # radius of circle sample (Phase 1)

# Phase 2 new constants
K_SUB_RAYS = 10              # number of sub-rays per iteration (evenly spaced 360°)
MIN_RAY_LENGTH = 3           # if all sub-rays shorter than this, stop (likely on an arrow, not a contour)
MAX_PHASE2_ITERATIONS = 2000  # safety limit on Phase 2 iterations

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def load_egm(path: str) -> dict:
    with open(path) as f:
        return json.load(f)


def get_green_boundary(egm_data: dict) -> np.ndarray:
    """Return dense Catmull-Rom spline for the green polygon (pixel coords)."""
    for poly in egm_data.get("polygons", []):
        if poly.get("type", "").lower() == "green":
            pts = poly.get("points", [])
            return interpolate_catmull_rom(pts)
    raise ValueError("No green polygon found in EGM file.")


def get_green_centroid(boundary: np.ndarray) -> tuple[int, int]:
    """Return integer (x, y) centroid of the green boundary polygon."""
    cx = float(boundary[:, 0].mean())
    cy = float(boundary[:, 1].mean())
    return (int(round(cx)), int(round(cy)))


def build_dark_mask(image: np.ndarray, green_mask: np.ndarray) -> np.ndarray:
    """
    Build a binary mask: 255 where HSV Value < DARK_THRESHOLD AND inside green.
    """
    hsv = cv2.cvtColor(image, cv2.COLOR_BGR2HSV)
    v = hsv[:, :, 2]
    mask = np.zeros(v.shape, dtype=np.uint8)
    mask[(v < DARK_THRESHOLD) & (green_mask == 255)] = 255
    return mask


def build_green_mask(boundary: np.ndarray, img_shape: tuple) -> np.ndarray:
    """Fill green polygon interior: returns uint8 mask (255 inside)."""
    h, w = img_shape[:2]
    mask = np.zeros((h, w), dtype=np.uint8)
    pts = boundary.astype(np.int32)
    cv2.fillPoly(mask, [pts], 255)
    return mask


def sample_circle_has_black(dark_mask: np.ndarray, cx: int, cy: int, radius: int) -> bool:
    """Return True if ANY pixel within radius of (cx, cy) is black (255 in dark_mask)."""
    h, w = dark_mask.shape
    y0 = max(0, cy - radius)
    y1 = min(h - 1, cy + radius)
    x0 = max(0, cx - radius)
    x1 = min(w - 1, cx + radius)

    for yy in range(y0, y1 + 1):
        for xx in range(x0, x1 + 1):
            if (yy - cy) ** 2 + (xx - cx) ** 2 <= radius * radius:
                if dark_mask[yy, xx] == 255:
                    return True
    return False


def sample_circle_counts(dark_mask: np.ndarray, cx: int, cy: int, radius: int) -> tuple[int, int]:
    """
    Return (n_black, n_nonblack) pixel counts within the circle.
    """
    h, w = dark_mask.shape
    y0 = max(0, cy - radius)
    y1 = min(h - 1, cy + radius)
    x0 = max(0, cx - radius)
    x1 = min(w - 1, cx + radius)

    n_black = 0
    n_nonblack = 0
    for yy in range(y0, y1 + 1):
        for xx in range(x0, x1 + 1):
            if (yy - cy) ** 2 + (xx - cx) ** 2 <= radius * radius:
                if dark_mask[yy, xx] == 255:
                    n_black += 1
                else:
                    n_nonblack += 1
    return n_black, n_nonblack


def ray_step_coords(
    start_x: float,
    start_y: float,
    angle_deg: float,
    length: int,
) -> list[tuple[int, int]]:
    """
    Return list of integer (x, y) pixels along the ray from (start_x, start_y)
    in the given direction for `length` steps.
    """
    angle_rad = math.radians(angle_deg)
    dx = math.cos(angle_rad)
    dy = math.sin(angle_rad)
    coords = []
    for step in range(1, length + 1):
        px = int(round(start_x + dx * step))
        py = int(round(start_y + dy * step))
        coords.append((px, py))
    return coords


def is_inside_green(green_mask: np.ndarray, x: int, y: int) -> bool:
    h, w = green_mask.shape
    if 0 <= y < h and 0 <= x < w:
        return green_mask[y, x] == 255
    return False


# ---------------------------------------------------------------------------
# Phase 1: Cast ray from centroid until black cluster hit
# ---------------------------------------------------------------------------

def phase1_ray_cast(
    dark_mask: np.ndarray,
    green_mask: np.ndarray,
    start: tuple[int, int],
    angle_deg: float,
) -> tuple[tuple[int, int] | None, list[tuple[int, int]]]:
    """
    Step from start outward along angle_deg until a black pixel cluster is found
    or we leave the green boundary.

    Returns (hit_point_or_None, list_of_ray_pixels).
    """
    h, w = dark_mask.shape
    max_steps = max(h, w)  # generous upper bound
    angle_rad = math.radians(angle_deg)
    dx = math.cos(angle_rad)
    dy = math.sin(angle_rad)

    ray_pixels: list[tuple[int, int]] = []
    hit_point: tuple[int, int] | None = None

    for step in range(1, max_steps):
        px = int(round(start[0] + dx * step))
        py = int(round(start[1] + dy * step))

        # Stop if we've left the green
        if not is_inside_green(green_mask, px, py):
            break

        ray_pixels.append((px, py))

        # Check for black pixels in the circle
        if sample_circle_has_black(dark_mask, px, py, PROBE_RADIUS):
            hit_point = (px, py)
            break

    return hit_point, ray_pixels


# ---------------------------------------------------------------------------
# Phase 2: Walk sub-rays from test point, jump to longest, repeat
# ---------------------------------------------------------------------------

def snap_to_black(dark_mask: np.ndarray, cx: int, cy: int, search_radius: int = 5) -> tuple[int, int]:
    """
    Starting from (cx, cy), scan a small neighbourhood and return the coordinates
    of the nearest pixel that is black (dark_mask == 255).  If none is found,
    return the original point unchanged.
    """
    h, w = dark_mask.shape
    best: tuple[int, int] = (cx, cy)
    best_dist2 = float("inf")
    for dy in range(-search_radius, search_radius + 1):
        for dx in range(-search_radius, search_radius + 1):
            nx, ny = cx + dx, cy + dy
            if 0 <= ny < h and 0 <= nx < w:
                if dark_mask[ny, nx] == 255:
                    d2 = dx * dx + dy * dy
                    if d2 < best_dist2:
                        best_dist2 = d2
                        best = (nx, ny)
    return best


def phase2_follow_contour(
    dark_mask: np.ndarray,
    green_mask: np.ndarray,
    hit_point: tuple[int, int],
    label: str = "",
) -> tuple[list[tuple[int, int]], list[tuple[int, int]]]:
    """
    From hit_point, cast K_SUB_RAYS evenly spaced sub-rays each iteration.
    Walk outward pixel by pixel on each sub-ray, counting consecutive black
    pixels. Jump to the end of the longest sub-ray. Mark all tested pixels
    as non-black (0) to prevent revisiting. Repeat until termination.

    Returns (test_points, termination_point_as_list).
    test_points: every center position used (including start).
    """
    h, w = dark_mask.shape
    # Snap to the nearest actual black pixel so sub-rays start on the contour
    cx, cy = snap_to_black(dark_mask, hit_point[0], hit_point[1], search_radius=PROBE_RADIUS + 2)
    if (cx, cy) != hit_point:
        print(f"  [phase2{label}] Snapped start from {hit_point} → ({cx},{cy})")
    test_points: list[tuple[int, int]] = [(cx, cy)]

    angle_step = 360.0 / K_SUB_RAYS  # 36 degrees between sub-rays

    print(f"  [phase2{label}] Starting at ({cx},{cy}), K={K_SUB_RAYS}, max_iter={MAX_PHASE2_ITERATIONS}")

    for iteration in range(MAX_PHASE2_ITERATIONS):
        if iteration % 50 == 0 and iteration > 0:
            print(f"  [phase2{label}] Iteration {iteration}: pos=({cx},{cy})")

        # Cast K sub-rays and measure length of each
        best_length = 0
        best_end: tuple[int, int] = (cx, cy)
        all_tested: list[tuple[int, int]] = []

        for k in range(K_SUB_RAYS):
            angle_deg = k * angle_step
            angle_rad = math.radians(angle_deg)
            dx = math.cos(angle_rad)
            dy = math.sin(angle_rad)

            ray_len = 0
            ray_end: tuple[int, int] = (cx, cy)

            step = 1
            while True:
                px = int(round(cx + dx * step))
                py = int(round(cy + dy * step))

                # Stop if out of image bounds
                if px < 0 or px >= w or py < 0 or py >= h:
                    break

                all_tested.append((px, py))

                # Check if pixel is black
                if dark_mask[py, px] == 255:
                    ray_len += 1
                    ray_end = (px, py)
                    step += 1
                else:
                    # First non-black pixel: stop this sub-ray
                    break

            if ray_len > best_length:
                best_length = ray_len
                best_end = ray_end

        # Erase all tested pixels (mark as non-black = 0)
        for (px, py) in all_tested:
            dark_mask[py, px] = 0

        # Termination: all sub-rays had length zero
        if best_length == 0:
            print(f"  [phase2{label}] Iteration {iteration}: all sub-rays zero length — stopping.")
            break

        # Termination: all sub-rays shorter than MIN_RAY_LENGTH (likely on an arrow)
        if best_length < MIN_RAY_LENGTH:
            print(f"  [phase2{label}] Iteration {iteration}: longest sub-ray only {best_length}px (< {MIN_RAY_LENGTH}) — stopping.")
            break

        # Jump to end of longest sub-ray
        new_cx, new_cy = best_end

        # Termination: new test point is on or outside the green boundary
        if not is_inside_green(green_mask, new_cx, new_cy):
            print(f"  [phase2{label}] Iteration {iteration}: new point ({new_cx},{new_cy}) outside green — stopping.")
            cx, cy = new_cx, new_cy
            test_points.append((cx, cy))
            break

        cx, cy = new_cx, new_cy
        test_points.append((cx, cy))

    else:
        print(f"  [phase2{label}] Reached max iterations ({MAX_PHASE2_ITERATIONS}).")

    termination_point = (cx, cy)
    print(f"  [phase2{label}] Done: {len(test_points)} test points. Terminated at {termination_point}.")
    return test_points, termination_point


# ---------------------------------------------------------------------------
# Main diagnostic
# ---------------------------------------------------------------------------

def main():
    print(f"[ray_contour] Loading EGM: {EGM_PATH}")
    egm_data = load_egm(EGM_PATH)

    # Resolve image path from EGM
    image_name = egm_data.get("image", "")
    image_path = os.path.join(TEAM_INBOX, image_name)
    if not os.path.isfile(image_path):
        raise FileNotFoundError(f"Image not found: {image_path}")
    print(f"[ray_contour] Image: {image_path}")

    # Get green boundary spline
    green_boundary = get_green_boundary(egm_data)
    print(f"[ray_contour] Green boundary: {len(green_boundary)} spline points")

    # Load original image (use for dark pixel detection)
    orig_img = cv2.imread(image_path)
    if orig_img is None:
        raise FileNotFoundError(f"cv2.imread failed: {image_path}")
    h, w = orig_img.shape[:2]

    # Build green interior mask
    green_mask = build_green_mask(green_boundary, orig_img.shape)

    # Get cleaned image (arrows removed) — use this for BOTH visualization and dark mask
    print("[ray_contour] Running remove_arrows_from_green()...")
    cleaned_img, _ = remove_arrows_from_green(image_path, green_boundary)

    # Build dark mask from CLEANED image so arrows don't interfere
    dark_mask = build_dark_mask(cleaned_img, green_mask)
    n_dark = int(dark_mask.sum() // 255)
    print(f"[ray_contour] Dark pixels inside green (cleaned image): {n_dark}")

    # Compute centroid
    centroid = get_green_centroid(green_boundary)
    print(f"[ray_contour] Green centroid: {centroid}")

    # --- Phase 1: Try multiple angles until we find a hit ---
    phase1_angle = 0.0
    hit_point = None
    phase1_ray_pixels: list[tuple[int, int]] = []

    for angle in range(0, 360, 5):
        hp, rp = phase1_ray_cast(dark_mask, green_mask, centroid, float(angle))
        if hp is not None:
            hit_point = hp
            phase1_ray_pixels = rp
            phase1_angle = float(angle)
            print(f"[ray_contour] Phase 1 hit at {hit_point} (angle={angle}°, ray length={len(rp)})")
            break

    if hit_point is None:
        print("[ray_contour] WARNING: Phase 1 found no black pixels in any direction!")
        print("[ray_contour] Saving diagnostic with just the boundary and centroid.")
        diag = cleaned_img.copy()
        pts = green_boundary.astype(np.int32)
        cv2.polylines(diag, [pts], isClosed=True, color=(0, 200, 0), thickness=2)
        cx2, cy2 = centroid
        cv2.circle(diag, (cx2, cy2), 8, (0, 255, 255), -1)
        os.makedirs(OWNER_INBOX, exist_ok=True)
        cv2.imwrite(OUTPUT_PATH, diag)
        print(f"[ray_contour] Saved: {OUTPUT_PATH}")
        return

    # --- Phase 1 (second ray): cast at 180° from original angle ---
    phase1_angle_2 = (phase1_angle + 180) % 360
    print(f"[ray_contour] Phase 1 ray 2: casting at {phase1_angle_2:.0f}° (opposite of {phase1_angle:.0f}°)...")
    hit_point_2, phase1_ray_pixels_2 = phase1_ray_cast(dark_mask, green_mask, centroid, phase1_angle_2)

    if hit_point_2 is not None:
        print(f"[ray_contour] Phase 1 ray 2 hit at {hit_point_2} (angle={phase1_angle_2:.0f}°, ray length={len(phase1_ray_pixels_2)})")
    else:
        print(f"[ray_contour] Phase 1 ray 2: no hit found at {phase1_angle_2:.0f}°.")

    # --- Phase 2 trace 1: follow from first hit point ---
    print("[ray_contour] Running Phase 2 (trace 1)...")
    test_points_1, term_point_1 = phase2_follow_contour(dark_mask, green_mask, hit_point, label="1")
    print(f"[ray_contour] Phase 2 trace 1: {len(test_points_1)} test points")

    # --- Phase 2 trace 2: follow from second hit point ---
    test_points_2: list[tuple[int, int]] = []
    term_point_2: tuple[int, int] | None = None

    if hit_point_2 is not None:
        print("[ray_contour] Running Phase 2 (trace 2)...")
        test_points_2, term_point_2 = phase2_follow_contour(dark_mask, green_mask, hit_point_2, label="2")
        print(f"[ray_contour] Phase 2 trace 2: {len(test_points_2)} test points")
    else:
        print("[ray_contour] Phase 2 trace 2: skipped (no second hit point).")

    # --- Save dark_mask after Phase 2 ---
    mask_debug_path = os.path.join(OWNER_INBOX, "debug_mask_after_phase2.png")
    mask_img = np.zeros((h, w, 3), dtype=np.uint8)
    mask_img[dark_mask == 255] = (255, 255, 255)
    pts_bnd = green_boundary.astype(np.int32)
    cv2.polylines(mask_img, [pts_bnd], isClosed=True, color=(0, 200, 0), thickness=2)
    os.makedirs(OWNER_INBOX, exist_ok=True)
    cv2.imwrite(mask_debug_path, mask_img)
    print(f"[ray_contour] Dark mask after Phase 2 saved: {mask_debug_path}")

    # --- Build diagnostic image ---
    diag = cleaned_img.copy()

    # Draw green boundary (green)
    pts = green_boundary.astype(np.int32)
    cv2.polylines(diag, [pts], isClosed=True, color=(0, 200, 0), thickness=2)

    # Draw Phase 1 ray 1 (blue)
    for (px, py) in phase1_ray_pixels:
        if 0 <= py < h and 0 <= px < w:
            diag[py, px] = (255, 100, 0)

    # Draw Phase 1 ray 2 (magenta)
    for (px, py) in phase1_ray_pixels_2:
        if 0 <= py < h and 0 <= px < w:
            diag[py, px] = (255, 0, 255)

    # Draw centroid (cyan dot)
    cx_c, cy_c = centroid
    cv2.circle(diag, (cx_c, cy_c), 8, (255, 255, 0), -1)
    cv2.circle(diag, (cx_c, cy_c), 9, (0, 0, 0), 1)

    # Draw first hit point (red dot)
    hx, hy = hit_point
    cv2.circle(diag, (hx, hy), 8, (0, 0, 255), -1)
    cv2.circle(diag, (hx, hy), 9, (255, 255, 255), 1)

    # Draw second hit point (red dot) if found
    if hit_point_2 is not None:
        hx2, hy2 = hit_point_2
        cv2.circle(diag, (hx2, hy2), 8, (0, 0, 255), -1)
        cv2.circle(diag, (hx2, hy2), 9, (255, 255, 255), 1)

    # Draw lime green path lines connecting consecutive test points (trace 1)
    LIME_GREEN = (0, 255, 0)
    for i in range(1, len(test_points_1)):
        x0_l, y0_l = test_points_1[i - 1]
        x1_l, y1_l = test_points_1[i]
        cv2.line(diag, (x0_l, y0_l), (x1_l, y1_l), LIME_GREEN, 2)

    # Draw lime green path lines connecting consecutive test points (trace 2)
    for i in range(1, len(test_points_2)):
        x0_l, y0_l = test_points_2[i - 1]
        x1_l, y1_l = test_points_2[i]
        cv2.line(diag, (x0_l, y0_l), (x1_l, y1_l), LIME_GREEN, 2)

    # Draw yellow dots at every test point (trace 1)
    YELLOW = (0, 255, 255)
    for (sx, sy) in test_points_1:
        if 0 <= sy < h and 0 <= sx < w:
            cv2.circle(diag, (sx, sy), 3, YELLOW, -1)

    # Draw yellow dots at every test point (trace 2)
    for (sx, sy) in test_points_2:
        if 0 <= sy < h and 0 <= sx < w:
            cv2.circle(diag, (sx, sy), 3, YELLOW, -1)

    # Draw termination points (orange dots)
    ORANGE = (0, 165, 255)
    cv2.circle(diag, term_point_1, 5, ORANGE, -1)
    cv2.circle(diag, term_point_1, 6, (0, 0, 0), 1)
    if term_point_2 is not None:
        cv2.circle(diag, term_point_2, 5, ORANGE, -1)
        cv2.circle(diag, term_point_2, 6, (0, 0, 0), 1)

    # Add legend text
    font = cv2.FONT_HERSHEY_SIMPLEX
    total_pts = len(test_points_1) + len(test_points_2)
    cv2.putText(diag, f"Centroid (cyan): {centroid}", (10, 30), font, 0.6, (255, 255, 0), 1)
    cv2.putText(diag, f"Phase 1 ray 1 (blue): angle={phase1_angle:.0f}deg  hit={hit_point}", (10, 55), font, 0.6, (255, 100, 0), 1)
    if hit_point_2 is not None:
        cv2.putText(diag, f"Phase 1 ray 2 (magenta): angle={phase1_angle_2:.0f}deg  hit={hit_point_2}", (10, 80), font, 0.6, (255, 0, 255), 1)
    else:
        cv2.putText(diag, f"Phase 1 ray 2 (magenta): angle={phase1_angle_2:.0f}deg  no hit", (10, 80), font, 0.6, (255, 0, 255), 1)
    cv2.putText(diag, f"Phase 2 test points (yellow dots, lime path): {total_pts}", (10, 105), font, 0.55, (0, 255, 0), 1)
    cv2.putText(diag, f"  trace1={len(test_points_1)}  trace2={len(test_points_2)}", (10, 128), font, 0.55, (0, 255, 0), 1)
    cv2.putText(diag, f"Termination points (orange): trace1={term_point_1}  trace2={term_point_2}", (10, 153), font, 0.5, ORANGE, 1)
    cv2.putText(diag, f"K_SUB_RAYS={K_SUB_RAYS}  MAX_PHASE2_ITERATIONS={MAX_PHASE2_ITERATIONS}", (10, 178), font, 0.55, (200, 200, 200), 1)

    # Save diagnostic
    cv2.imwrite(OUTPUT_PATH, diag)
    print(f"[ray_contour] Diagnostic saved: {OUTPUT_PATH}")


if __name__ == "__main__":
    main()
