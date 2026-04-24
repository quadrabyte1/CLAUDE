"""
ridge_filter_test.py
--------------------
Diagnostic script that applies Frangi and Meijering ridge-detection filters
to the Moffett Field Hole 7 golf green image.

Usage:
    cd /Users/fourierflight/GIT/CLAUDE-GitHub/SHARED_WORK_FOLDER
    python app/ridge_filter_test.py
"""

import json
import os
import sys

import cv2
import numpy as np
from PIL import Image
from skimage.filters import frangi, meijering
from skimage.filters import threshold_otsu
from skimage.morphology import erosion, disk

# ---------------------------------------------------------------------------
# Paths
# ---------------------------------------------------------------------------

REPO_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
OWNER_INBOX = os.path.join(REPO_ROOT, "owner_inbox")
TEAM_INBOX  = os.path.join(REPO_ROOT, "team_inbox")

EGM_FILE    = os.path.join(OWNER_INBOX, "Moffett Field AA (Hole 7).egm")
# Image name is embedded in the EGM; we'll resolve it from team_inbox
OUTPUT_FRANGI        = os.path.join(OWNER_INBOX, "debug_ridge_frangi.png")
OUTPUT_MEIJERING     = os.path.join(OWNER_INBOX, "debug_ridge_meijering.png")
OUTPUT_FRANGI_TUNING = os.path.join(OWNER_INBOX, "debug_frangi_tuning.png")

# ---------------------------------------------------------------------------
# Catmull-Rom (copy from generate_stl_3mf so this script is self-contained)
# ---------------------------------------------------------------------------

CATMULL_SEGMENTS = 20
CATMULL_TENSION  = 0.5


def _catmull_rom_point(p0, p1, p2, p3, t, tension=0.5):
    t2 = t * t
    t3 = t2 * t
    alpha = tension
    return (
        (-alpha * t3 + 2 * alpha * t2 - alpha * t) * p0
        + ((2 - alpha) * t3 + (alpha - 3) * t2 + 1) * p1
        + ((alpha - 2) * t3 + (3 - 2 * alpha) * t2 + alpha * t) * p2
        + (alpha * t3 - alpha * t2) * p3
    )


def interpolate_catmull_rom(control_points, segments=CATMULL_SEGMENTS, tension=CATMULL_TENSION):
    """Return a dense closed 2D polyline (N, 2) for a list of {x, y} dicts."""
    n = len(control_points)
    if n < 3:
        return np.array([[p["x"], p["y"]] for p in control_points], dtype=np.float64)

    pts = np.array([[p["x"], p["y"]] for p in control_points], dtype=np.float64)
    result = []
    for i in range(n):
        p0 = pts[(i - 1) % n]
        p1 = pts[i % n]
        p2 = pts[(i + 1) % n]
        p3 = pts[(i + 2) % n]
        for s in range(segments):
            t = s / segments
            result.append(_catmull_rom_point(p0, p1, p2, p3, t, tension))
    return np.array(result, dtype=np.float64)


# ---------------------------------------------------------------------------
# Helper: build filled boolean mask from a spline polygon
# ---------------------------------------------------------------------------

def polygon_to_mask(spline_xy, img_h, img_w):
    """Return a uint8 mask (255 inside, 0 outside) for a closed spline polygon."""
    pts = spline_xy.astype(np.int32)
    mask = np.zeros((img_h, img_w), dtype=np.uint8)
    cv2.fillPoly(mask, [pts], 255)
    return mask


# ---------------------------------------------------------------------------
# Helper: save a two-panel debug image
# ---------------------------------------------------------------------------

def save_debug_panel(
    filter_response_gray: np.ndarray,  # float32, normalised 0-1, full image size
    ridge_mask: np.ndarray,            # bool, ridge pixels = True
    src_rgb: np.ndarray,               # H×W×3 uint8 RGB source image
    crop_box,                          # (x1, y1, x2, y2) bounding box for cropping
    out_path: str,
    title: str,
):
    """Create and save a side-by-side debug image."""
    x1, y1, x2, y2 = crop_box

    # Left panel: filter response heatmap (applied colormap)
    response_crop = filter_response_gray[y1:y2, x1:x2]
    response_u8   = (response_crop * 255).clip(0, 255).astype(np.uint8)
    heatmap       = cv2.applyColorMap(response_u8, cv2.COLORMAP_INFERNO)  # BGR
    heatmap_rgb   = cv2.cvtColor(heatmap, cv2.COLOR_BGR2RGB)

    # Right panel: source image with lime-green ridge overlay
    overlay = src_rgb[y1:y2, x1:x2].copy()
    ridge_crop = ridge_mask[y1:y2, x1:x2]
    overlay[ridge_crop] = [50, 205, 50]  # lime green

    # Combine side by side
    panel = np.concatenate([heatmap_rgb, overlay], axis=1)

    # Add a thin white label bar at the top
    bar_h = 28
    h, w = panel.shape[:2]
    label_bar = np.full((bar_h, w, 3), 30, dtype=np.uint8)
    cv2.putText(
        label_bar, title, (10, 20),
        cv2.FONT_HERSHEY_SIMPLEX, 0.65, (240, 240, 240), 1, cv2.LINE_AA
    )
    panel = np.concatenate([label_bar, panel], axis=0)

    Image.fromarray(panel).save(out_path)
    print(f"  Saved: {out_path}")


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main():
    # 1. Load EGM
    print(f"Loading EGM: {EGM_FILE}")
    with open(EGM_FILE) as f:
        egm = json.load(f)

    # 2. Find green polygon
    green_polygon = None
    for poly in egm.get("polygons", []):
        if poly.get("type") == "green":
            green_polygon = poly
            break
    if green_polygon is None:
        sys.exit("ERROR: No green polygon found in EGM.")

    print(f"  Green polygon control points: {len(green_polygon['points'])}")

    # 3. Build dense Catmull-Rom spline
    green_spline = interpolate_catmull_rom(green_polygon["points"])
    print(f"  Green spline vertices: {len(green_spline)}")

    # 4. Locate source image
    image_name = egm.get("image", "")
    image_path = os.path.join(TEAM_INBOX, image_name)
    if not os.path.isfile(image_path):
        sys.exit(f"ERROR: Image not found: {image_path}")
    print(f"  Source image: {image_path}")

    # 5. Load image (BGR via cv2, then convert to RGB for display)
    img_bgr = cv2.imread(image_path)
    if img_bgr is None:
        sys.exit(f"ERROR: cv2 could not read: {image_path}")
    img_rgb  = cv2.cvtColor(img_bgr, cv2.COLOR_BGR2RGB)
    img_gray = cv2.cvtColor(img_bgr, cv2.COLOR_BGR2GRAY)  # uint8

    h, w = img_gray.shape
    print(f"  Image size: {w}×{h}")

    # 6. Build green mask
    green_mask = polygon_to_mask(green_spline, h, w)  # uint8 255/0

    # 7. Erode mask by 10 px to avoid boundary artifacts
    eroded_mask = erosion(green_mask > 0, disk(10)).astype(np.uint8) * 255
    print(f"  Eroded green mask pixels: {(eroded_mask > 0).sum():,}")

    # 8. Create float grayscale image where exterior pixels are replaced by
    #    the mean interior value (neutral fill avoids artificial edges at boundary)
    gray_float = img_gray.astype(np.float64) / 255.0
    interior_mean = gray_float[eroded_mask > 0].mean()
    print(f"  Interior mean grey value: {interior_mean:.3f}")

    masked_gray = gray_float.copy()
    masked_gray[eroded_mask == 0] = interior_mean  # neutral fill outside green

    # 9. Compute bounding box for cropping output panels
    ys, xs = np.where(eroded_mask > 0)
    pad = 20
    x1 = max(0,  int(xs.min()) - pad)
    y1 = max(0,  int(ys.min()) - pad)
    x2 = min(w,  int(xs.max()) + pad)
    y2 = min(h,  int(ys.max()) + pad)
    crop_box = (x1, y1, x2, y2)
    print(f"  Crop box: {crop_box}")

    # ---------------------------------------------------------------------------
    # 10. FRANGI filter — parameter tuning comparison
    # ---------------------------------------------------------------------------
    print("\n--- Frangi parameter tuning ---")

    combos = [
        {
            "name": "1_wider_sigmas",
            "label": "Wider sigmas range(1,10)  a=0.5 b=0.5 g=15",
            "sigmas": range(1, 10),
            "alpha": 0.5,
            "beta": 0.5,
            "gamma": 15,
        },
        {
            "name": "2_lower_gamma5",
            "label": "Lower gamma=5  sigmas(2,8) a=0.5 b=0.5",
            "sigmas": range(2, 8),
            "alpha": 0.5,
            "beta": 0.5,
            "gamma": 5,
        },
        {
            "name": "3_lower_gamma1",
            "label": "Even lower gamma=1  sigmas(2,8) a=0.5 b=0.5",
            "sigmas": range(2, 8),
            "alpha": 0.5,
            "beta": 0.5,
            "gamma": 1,
        },
        {
            "name": "4_low_alpha_gamma5",
            "label": "Low alpha=0.3  sigmas(2,8) b=0.5 g=5",
            "sigmas": range(2, 8),
            "alpha": 0.3,
            "beta": 0.5,
            "gamma": 5,
        },
        {
            "name": "5_best_combo",
            "label": "Best combo  sigmas(1,10) a=0.3 b=0.5 g=5",
            "sigmas": range(1, 10),
            "alpha": 0.3,
            "beta": 0.5,
            "gamma": 5,
        },
    ]

    combo_results = []  # list of dicts: {name, label, norm, binary, thresh, n_ridge, max_raw}

    for combo in combos:
        print(f"\n  Combo: {combo['name']}")
        response = frangi(
            masked_gray,
            sigmas=combo["sigmas"],
            alpha=combo["alpha"],
            beta=combo["beta"],
            gamma=combo["gamma"],
            black_ridges=True,
        )
        max_raw = float(response.max())
        print(f"    Max raw response: {max_raw:.6f}")

        r_max = response.max()
        if r_max > 0:
            norm = (response / r_max).astype(np.float32)
        else:
            norm = response.astype(np.float32)

        interior_vals = norm[eroded_mask > 0]
        try:
            thresh = threshold_otsu(interior_vals)
        except Exception:
            thresh = 0.1
        print(f"    Otsu threshold:   {thresh:.4f}")

        binary = (norm > thresh) & (eroded_mask > 0)
        n_ridge = int(binary.sum())
        print(f"    Ridge pixels:     {n_ridge:,}  ({100*n_ridge/(eroded_mask>0).sum():.1f}% of green)")

        combo_results.append({
            "name":    combo["name"],
            "label":   combo["label"],
            "norm":    norm,
            "binary":  binary,
            "thresh":  thresh,
            "n_ridge": n_ridge,
            "max_raw": max_raw,
        })

    # -----------------------------------------------------------------------
    # Build comparison grid image (5 panels, each with lime overlay + label)
    # -----------------------------------------------------------------------
    print(f"\n  Building comparison grid → {OUTPUT_FRANGI_TUNING}")

    panel_images = []
    for res in combo_results:
        x1, y1, x2, y2 = crop_box
        overlay = img_rgb[y1:y2, x1:x2].copy()
        ridge_crop = res["binary"][y1:y2, x1:x2]
        overlay[ridge_crop] = [50, 205, 50]  # lime green

        # Label bar
        bar_h = 36
        ph, pw = overlay.shape[:2]
        label_bar = np.full((bar_h, pw, 3), 20, dtype=np.uint8)
        line1 = res["label"]
        line2 = f"thresh={res['thresh']:.4f}  ridge_px={res['n_ridge']:,}  max_raw={res['max_raw']:.4f}"
        cv2.putText(label_bar, line1, (6, 15),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.45, (240, 240, 60), 1, cv2.LINE_AA)
        cv2.putText(label_bar, line2, (6, 30),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.40, (180, 180, 180), 1, cv2.LINE_AA)
        panel = np.concatenate([label_bar, overlay], axis=0)
        panel_images.append(panel)

    # Arrange in a single row (or wrap if needed) — 5 panels side by side
    # Ensure all panels are same height (they should be, but pad just in case)
    max_h = max(p.shape[0] for p in panel_images)
    padded = []
    for p in panel_images:
        ph, pw = p.shape[:2]
        if ph < max_h:
            pad = np.full((max_h - ph, pw, 3), 20, dtype=np.uint8)
            p = np.concatenate([p, pad], axis=0)
        padded.append(p)

    grid = np.concatenate(padded, axis=1)
    Image.fromarray(grid).save(OUTPUT_FRANGI_TUNING)
    print(f"  Saved: {OUTPUT_FRANGI_TUNING}")

    # -----------------------------------------------------------------------
    # Pick best result: most ridge pixels
    # -----------------------------------------------------------------------
    best = max(combo_results, key=lambda r: r["n_ridge"])
    print(f"\n  Best combo (most ridge pixels): {best['name']}  ({best['n_ridge']:,} px)")

    # Use best result as the canonical debug_ridge_frangi output
    frangi_norm   = best["norm"]
    frangi_binary = best["binary"]
    n_frangi      = best["n_ridge"]
    frangi_thresh = best["thresh"]
    sigmas        = combos[combo_results.index(best)]["sigmas"]

    save_debug_panel(
        frangi_norm, frangi_binary, img_rgb,
        crop_box, OUTPUT_FRANGI,
        f"Frangi BEST ({best['name']})  threshold={frangi_thresh:.4f}  ridge_px={n_frangi:,}"
    )

    # ---------------------------------------------------------------------------
    # 11. MEIJERING filter
    # ---------------------------------------------------------------------------
    print("\n--- Meijering filter ---")

    meijering_response = meijering(
        masked_gray,
        sigmas=sigmas,
        alpha=0.5,
        black_ridges=True,
    )
    print(f"  Response range: [{meijering_response.min():.6f}, {meijering_response.max():.6f}]")

    m_max = meijering_response.max()
    if m_max > 0:
        meij_norm = (meijering_response / m_max).astype(np.float32)
    else:
        meij_norm = meijering_response.astype(np.float32)

    interior_vals_m = meij_norm[eroded_mask > 0]
    try:
        meij_thresh = threshold_otsu(interior_vals_m)
    except Exception:
        meij_thresh = 0.1
    print(f"  Otsu threshold: {meij_thresh:.4f}")

    meij_binary = (meij_norm > meij_thresh) & (eroded_mask > 0)
    n_meij = int(meij_binary.sum())
    print(f"  Ridge pixels detected: {n_meij:,}  ({100*n_meij/(eroded_mask>0).sum():.1f}% of green)")

    save_debug_panel(
        meij_norm, meij_binary, img_rgb,
        crop_box, OUTPUT_MEIJERING,
        f"Meijering  sigmas={list(sigmas)}  threshold={meij_thresh:.4f}  ridge_px={n_meij:,}"
    )

    # ---------------------------------------------------------------------------
    # 12. Comparison summary
    # ---------------------------------------------------------------------------
    print("\n=== Comparison summary ===")
    print(f"  Frangi    ridge pixels: {n_frangi:,}")
    print(f"  Meijering ridge pixels: {n_meij:,}")
    overlap = int((frangi_binary & meij_binary).sum())
    union   = int((frangi_binary | meij_binary).sum())
    iou = overlap / union if union > 0 else 0.0
    print(f"  Overlap (both agree):   {overlap:,}")
    print(f"  Union:                  {union:,}")
    print(f"  IoU:                    {iou:.3f}")
    print("\nDone.")


if __name__ == "__main__":
    main()
