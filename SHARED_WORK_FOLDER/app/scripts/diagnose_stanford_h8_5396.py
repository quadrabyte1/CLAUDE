"""
diagnose_stanford_h8_5396.py
────────────────────────────
Diagnostic: run detect_boundaries() logic on Stanford H8 5396 (StrackaLine image)
and produce an annotated overlay PNG + printed polygon inventory.

Usage:
    cd /Volumes/GIT/CLAUDE/SHARED_WORK_FOLDER/app
    python scripts/diagnose_stanford_h8_5396.py

Outputs:
    owner_inbox/detect_boundaries_stanford_h8_5396_2026-09-28.png
"""

import os
import sys
import json

# Make sure the app/ directory is on the path (for any helpers we copy inline)
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
APP_DIR = os.path.dirname(SCRIPT_DIR)
REPO_ROOT = os.path.dirname(APP_DIR)

sys.path.insert(0, APP_DIR)

# ── paths ──────────────────────────────────────────────────────────────────
IMAGE_PATH = os.path.join(
    REPO_ROOT, "ItWentIn", "GolfCourses", "Stanford", "Images",
    "Stanford (hole 8, 5396).png"
)
OUT_PNG = os.path.join(REPO_ROOT, "owner_inbox",
                       "detect_boundaries_stanford_h8_5396_2026-09-28.png")

assert os.path.isfile(IMAGE_PATH), f"Image not found: {IMAGE_PATH}"

import cv2
import numpy as np
from scipy.ndimage import binary_fill_holes

# ── copy of the pure detection logic from detect_boundaries() ──────────────
img = cv2.imread(IMAGE_PATH)
assert img is not None, "cv2.imread returned None"

h, w = img.shape[:2]
print(f"Image size: {w}x{h}")

hsv = cv2.cvtColor(img, cv2.COLOR_BGR2HSV)
hue = hsv[:, :, 0].astype(float)
sat = hsv[:, :, 1].astype(float)
val = hsv[:, :, 2].astype(float)

# ── Green detection ────────────────────────────────────────────────────────
contour_bands = (
    ((hue < 30) | (hue > 90)) & (sat > 80) & (val > 80)
) | (
    (hue >= 30) & (hue <= 90) & (sat > 120) & (val > 80)
)
contour_u8 = (contour_bands.astype(np.uint8)) * 255
kernel = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (15, 15))
contour_u8 = cv2.morphologyEx(contour_u8, cv2.MORPH_CLOSE, kernel, iterations=5)
contour_filled = binary_fill_holes(contour_u8 > 0)
contour_u8 = (contour_filled.astype(np.uint8)) * 255

n_cc, cc_labels, cc_stats, _ = cv2.connectedComponentsWithStats(contour_u8)
green_mask = np.zeros((h, w), dtype=np.uint8)
if n_cc > 1:
    areas = cc_stats[1:, cv2.CC_STAT_AREA]
    largest = 1 + np.argmax(areas)
    green_mask = ((cc_labels == largest) * 255).astype(np.uint8)

green_mask = cv2.GaussianBlur(green_mask, (21, 21), 0)
_, green_mask = cv2.threshold(green_mask, 127, 255, cv2.THRESH_BINARY)

# ── Trap detection ─────────────────────────────────────────────────────────
trap_mask = (
    (hue >= 15) & (hue <= 34) &
    (sat >= 15) & (sat <= 60) &
    (val >= 200)
).astype(np.uint8) * 255
kernel_t = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (11, 11))
trap_mask = cv2.morphologyEx(trap_mask, cv2.MORPH_CLOSE, kernel_t, iterations=3)
trap_mask = cv2.morphologyEx(trap_mask, cv2.MORPH_OPEN,
                             cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (7, 7)), iterations=2)
trap_filled = binary_fill_holes(trap_mask > 0)
trap_mask = (trap_filled.astype(np.uint8)) * 255

n_t, t_labels, t_stats, t_centroids = cv2.connectedComponentsWithStats(trap_mask)
traps = []
for i in range(1, n_t):
    area = t_stats[i, cv2.CC_STAT_AREA]
    if area >= 500:
        traps.append((i, area))
traps.sort(key=lambda x: x[1], reverse=True)
traps = traps[:5]

# ── Water detection ────────────────────────────────────────────────────────
water_mask = (
    (hue >= 100) & (hue <= 130) &
    (sat >= 130) &
    (val >= 130) & (val <= 220)
).astype(np.uint8) * 255
kernel_w = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (11, 11))
water_mask = cv2.morphologyEx(water_mask, cv2.MORPH_CLOSE, kernel_w, iterations=3)
water_mask = cv2.morphologyEx(water_mask, cv2.MORPH_OPEN,
                              cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (7, 7)), iterations=2)
water_filled = binary_fill_holes(water_mask > 0)
water_mask = (water_filled.astype(np.uint8)) * 255

n_w, w_labels, w_stats, w_centroids = cv2.connectedComponentsWithStats(water_mask)
waters = []
for i in range(1, n_w):
    area = w_stats[i, cv2.CC_STAT_AREA]
    if area >= 500:
        waters.append((i, area))
waters.sort(key=lambda x: x[1], reverse=True)
waters = waters[:5]

# ── mask_to_polygon helper ─────────────────────────────────────────────────
def mask_to_polygon(mask, num_points):
    contours, _ = cv2.findContours(mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    if not contours:
        return []
    cnt = max(contours, key=cv2.contourArea)
    cnt = cnt.squeeze()
    if len(cnt.shape) < 2:
        return []
    n = len(cnt)
    cum = [0.0]
    for j in range(1, n):
        cum.append(cum[-1] + np.linalg.norm(cnt[j] - cnt[j-1]))
    cum.append(cum[-1] + np.linalg.norm(cnt[0] - cnt[-1]))
    total = cum[-1]
    if total == 0:
        return []
    pts = []
    for j in range(num_points):
        target = (j / num_points) * total
        seg = 0
        while seg < n and cum[seg+1] < target:
            seg += 1
        t = (target - cum[seg]) / max(cum[seg+1] - cum[seg], 1e-9)
        a = cnt[seg % n]
        b = cnt[(seg+1) % n]
        px = int(a[0] + t * (b[0] - a[0]))
        py = int(a[1] + t * (b[1] - a[1]))
        pts.append({"x": px, "y": py})
    return pts

# ── Build polygon list (mirrors detect_boundaries response) ────────────────
polygons = []

green_pts = mask_to_polygon(green_mask, 8)
if green_pts:
    polygons.append({"name": "Green", "type": "green", "points": green_pts})

for idx, (label_id, area) in enumerate(traps):
    t_mask_single = ((t_labels == label_id) * 255).astype(np.uint8)
    t_mask_single = cv2.GaussianBlur(t_mask_single, (15, 15), 0)
    _, t_mask_single = cv2.threshold(t_mask_single, 127, 255, cv2.THRESH_BINARY)
    trap_pts = mask_to_polygon(t_mask_single, 16)
    if trap_pts:
        polygons.append({"name": f"Trap {idx+1}", "type": "trap",
                         "points": trap_pts, "_area": int(area)})

for idx, (label_id, area) in enumerate(waters):
    w_mask_single = ((w_labels == label_id) * 255).astype(np.uint8)
    w_mask_single = cv2.GaussianBlur(w_mask_single, (15, 15), 0)
    _, w_mask_single = cv2.threshold(w_mask_single, 127, 255, cv2.THRESH_BINARY)
    water_pts = mask_to_polygon(w_mask_single, 16)
    if water_pts:
        polygons.append({"name": f"Water {idx+1}", "type": "water",
                         "points": water_pts, "_area": int(area)})

# ── Print polygon inventory ────────────────────────────────────────────────
print(f"\n=== detect_boundaries output ===")
print(f"Total polygons: {len(polygons)}")
for poly in polygons:
    pts = poly["points"]
    xs = [p["x"] for p in pts]
    ys = [p["y"] for p in pts]
    bbox_x = min(xs)
    bbox_y = min(ys)
    bbox_w = max(xs) - min(xs)
    bbox_h = max(ys) - min(ys)
    area_str = f"  raw_area={poly.get('_area', 'n/a')}" if '_area' in poly else ""
    print(f"  {poly['name']} ({poly['type']}): {len(pts)} pts  bbox=({bbox_x},{bbox_y},{bbox_w}x{bbox_h}){area_str}")

# ── Build extra diagnostic: mask pixel stats ──────────────────────────────
green_pixel_count = int(np.count_nonzero(green_mask))
trap_pixel_count  = int(np.count_nonzero(trap_mask))
water_pixel_count = int(np.count_nonzero(water_mask))
print(f"\nMask pixel counts:")
print(f"  green_mask  : {green_pixel_count} px")
print(f"  trap_mask   : {trap_pixel_count} px")
print(f"  water_mask  : {water_pixel_count} px")
print(f"  image total : {h*w} px")

# Report all raw water components (before 500px area filter)
print(f"\nAll raw water components (pre-filter):")
for i in range(1, n_w):
    area = w_stats[i, cv2.CC_STAT_AREA]
    cx = int(w_centroids[i][0])
    cy = int(w_centroids[i][1])
    print(f"  component {i}: area={area}  centroid=({cx},{cy})")

# Also sample HSV at key regions to see what the green interior looks like
# Sample the light-cyan area at the bottom-right of the image (ground truth Water 1 area)
# Ground truth Water 1 centroid is approx (380, 880)
# Ground truth Water 2 centroid is approx (720, 585)
sample_pts_labeled = [
    ("GT-Water1-center",  380, 880),
    ("GT-Water2-center",  720, 585),
    ("Green-center",      400, 450),
    ("Beige-left-region", 100, 600),
    ("Bottom-right",      650, 1100),
]
print(f"\nHSV samples at key locations:")
for label, sx, sy in sample_pts_labeled:
    if 0 <= sy < h and 0 <= sx < w:
        H = hsv[sy, sx, 0]
        S = hsv[sy, sx, 1]
        V = hsv[sy, sx, 2]
        print(f"  {label:30s} ({sx:4d},{sy:4d})  H={H:3d} S={S:3d} V={V:3d}")

# ── Generate overlay PNG ───────────────────────────────────────────────────
overlay = img.copy()

# Color scheme (BGR):
#   green  = (0, 200, 0)         bright green outline
#   fringe = (255, 255, 255)     white outline (no fringe detected)
#   trap   = (0, 165, 255)       orange outline + semi-transparent fill
#   water  = (255, 255, 0)       cyan outline + semi-transparent fill
TYPE_COLORS = {
    "green": (0, 200, 0),
    "fringe": (255, 255, 255),
    "trap": (0, 165, 255),    # BGR orange
    "water": (255, 200, 0),   # BGR cyan-ish (yellow-green → actually use pure cyan)
}
TYPE_COLORS_DISPLAY = {
    "green": (0, 200, 0),
    "fringe": (255, 255, 255),
    "trap": (0, 128, 255),
    "water": (255, 220, 0),
}

# True cyan in BGR = (255, 255, 0)
TYPE_COLORS["water"] = (255, 255, 0)

# Draw semi-transparent fills for trap and water
fill_layer = overlay.copy()
for poly in polygons:
    pts_arr = np.array([[p["x"], p["y"]] for p in poly["points"]], dtype=np.int32)
    ptype = poly["type"]
    color = TYPE_COLORS.get(ptype, (255, 255, 255))
    if ptype in ("trap", "water"):
        cv2.fillPoly(fill_layer, [pts_arr], color)

alpha = 0.35
cv2.addWeighted(fill_layer, alpha, overlay, 1 - alpha, 0, overlay)

# Draw outlines for all types
for poly in polygons:
    pts_arr = np.array([[p["x"], p["y"]] for p in poly["points"]], dtype=np.int32)
    ptype = poly["type"]
    color = TYPE_COLORS.get(ptype, (255, 255, 255))
    cv2.polylines(overlay, [pts_arr], isClosed=True, color=color, thickness=3)
    # Draw control points
    for pt in poly["points"]:
        cv2.circle(overlay, (pt["x"], pt["y"]), 5, color, -1)
        cv2.circle(overlay, (pt["x"], pt["y"]), 5, (0, 0, 0), 1)

# ── Title bar ─────────────────────────────────────────────────────────────
# Prepend a black header bar
HEADER_H = 80
header = np.zeros((HEADER_H, w, 3), dtype=np.uint8)
cv2.putText(header,
            "Stanford H8 5396 -- detect_boundaries diagnostic 2026-09-28",
            (10, 32), cv2.FONT_HERSHEY_SIMPLEX, 0.65, (255, 255, 255), 1, cv2.LINE_AA)

# Version badge upper-left (white box)
badge_text = "v1"
(btw, bth), _ = cv2.getTextSize(badge_text, cv2.FONT_HERSHEY_SIMPLEX, 0.8, 2)
cv2.rectangle(header, (4, 40), (btw + 16, 40 + bth + 10), (255, 255, 255), -1)
cv2.putText(header, badge_text, (10, 40 + bth + 4),
            cv2.FONT_HERSHEY_SIMPLEX, 0.8, (0, 0, 0), 2, cv2.LINE_AA)

# ── Legend ────────────────────────────────────────────────────────────────
legend_items = []
type_counts = {}
for poly in polygons:
    t = poly["type"]
    type_counts[t] = type_counts.get(t, 0) + 1

for ptype, color in [("green", (0, 200, 0)), ("trap", (0, 128, 255)),
                      ("water", (255, 255, 0)), ("fringe", (255, 255, 255))]:
    count = type_counts.get(ptype, 0)
    legend_items.append((ptype.capitalize(), color, count))

LEGEND_H = 30 * len(legend_items) + 20
legend_strip = np.zeros((LEGEND_H, w, 3), dtype=np.uint8)
for row_idx, (label, color, count) in enumerate(legend_items):
    y_base = 20 + row_idx * 30
    cv2.rectangle(legend_strip, (10, y_base - 12), (30, y_base + 4), color, -1)
    cv2.rectangle(legend_strip, (10, y_base - 12), (30, y_base + 4), (200, 200, 200), 1)
    cv2.putText(legend_strip,
                f"{label}: {count}",
                (38, y_base), cv2.FONT_HERSHEY_SIMPLEX, 0.6, (220, 220, 220), 1, cv2.LINE_AA)

final = np.vstack([header, overlay, legend_strip])
cv2.imwrite(OUT_PNG, final)
print(f"\nOverlay PNG saved: {OUT_PNG}")

# ── Also dump JSON summary for the report ─────────────────────────────────
summary = {
    "image_size": {"width": w, "height": h},
    "polygons": [
        {
            "name": p["name"],
            "type": p["type"],
            "point_count": len(p["points"]),
            "bbox": {
                "x": min(pt["x"] for pt in p["points"]),
                "y": min(pt["y"] for pt in p["points"]),
                "w": max(pt["x"] for pt in p["points"]) - min(pt["x"] for pt in p["points"]),
                "h": max(pt["y"] for pt in p["points"]) - min(pt["y"] for pt in p["points"]),
            },
            "raw_area": p.get("_area"),
        }
        for p in polygons
    ],
    "mask_pixel_counts": {
        "green": green_pixel_count,
        "trap": trap_pixel_count,
        "water": water_pixel_count,
    },
    "water_components_pre_filter": [
        {"component": i,
         "area": int(w_stats[i, cv2.CC_STAT_AREA]),
         "centroid": (int(w_centroids[i][0]), int(w_centroids[i][1]))}
        for i in range(1, n_w)
    ],
}
print(json.dumps(summary, indent=2))
