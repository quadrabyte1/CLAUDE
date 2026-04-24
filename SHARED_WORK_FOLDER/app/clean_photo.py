"""
clean_photo.py — Architectural photo cleanup: Laplacian blend + zone neutralization.
Author: Cass (Architectural Visualization Specialist)

Approach:
  - For zones where a same-content source exists nearby in the image
    (e.g. fence above fence, concrete beside concrete), use Laplacian pyramid
    blending for seamless patch replacement.
  - For complex clutter zones with no clean same-content nearby source,
    apply heavy Gaussian blur + desaturation to neutralize the zone. This
    makes it read as "cleared ground" rather than clutter, which is sufficient
    for deck mockup compositing where a new deck will be composited over it.
  - Small isolated objects (<3% mask area): cv2.inpaint.

Works at 1/4 resolution for speed, upscales to full res for output.
"""

import cv2
import numpy as np
import os

os.makedirs("owner_inbox", exist_ok=True)
SCALE = 0.25


# ---------------------------------------------------------------------------
# Core utilities
# ---------------------------------------------------------------------------

def laplacian_blend(A, B, mask, levels=4):
    """Blend A (new content) over B (original) with mask=1→use A, 0→use B."""
    if mask.ndim == 2:
        mask = np.repeat(mask[:, :, None], 3, axis=2)
    mask = mask.astype(np.float32)
    GA = [A.astype(np.float32)]; GB = [B.astype(np.float32)]; GM = [mask]
    for _ in range(levels):
        GA.append(cv2.pyrDown(GA[-1]))
        GB.append(cv2.pyrDown(GB[-1]))
        GM.append(cv2.pyrDown(GM[-1]))
    LA, LB = [], []
    for i in range(levels):
        up_A = cv2.pyrUp(GA[i+1], dstsize=(GA[i].shape[1], GA[i].shape[0]))
        up_B = cv2.pyrUp(GB[i+1], dstsize=(GB[i].shape[1], GB[i].shape[0]))
        LA.append(GA[i] - up_A); LB.append(GB[i] - up_B)
    LA.append(GA[-1]); LB.append(GB[-1])
    blended = []
    for i in range(levels + 1):
        m = GM[i] if i < len(GM) else GM[-1]
        blended.append(LA[i] * m + LB[i] * (1 - m))
    result = blended[-1]
    for i in range(levels - 1, -1, -1):
        result = cv2.pyrUp(result, dstsize=(blended[i].shape[1], blended[i].shape[0])) + blended[i]
    return np.clip(result, 0, 255).astype(np.uint8)


def blend_patch(img, ref, src_box, dst_box, blur_r=41):
    """
    Laplacian-blend a patch from ref[src_box] into img at dst_box.
    Best used when source and destination have similar content/color.
    """
    sx0, sy0, sx1, sy1 = src_box
    dx0, dy0, dx1, dy1 = dst_box
    H, W = img.shape[:2]
    dx0c, dy0c = max(0, dx0), max(0, dy0)
    dx1c, dy1c = min(W, dx1), min(H, dy1)
    dw, dh = dx1c - dx0c, dy1c - dy0c
    if dw <= 0 or dh <= 0:
        return img
    src_patch = ref[sy0:sy1, sx0:sx1]
    if src_patch.size == 0:
        return img
    src_r = cv2.resize(src_patch, (dw, dh), interpolation=cv2.INTER_LINEAR)
    A = img.copy().astype(np.float32)
    A[dy0c:dy1c, dx0c:dx1c] = src_r
    mask = np.zeros((H, W), dtype=np.float32)
    mask[dy0c:dy1c, dx0c:dx1c] = 1.0
    br = blur_r | 1  # ensure odd
    mask = cv2.GaussianBlur(mask, (br, br), 0)
    return laplacian_blend(A, img.astype(np.float32), mask)


def neutralize_zone(img, x0, y0, x1, y1, desat=0.4):
    """
    Neutralize a clutter zone cleanly:
    1. Sample the average color from the zone BORDER (top/left/right edges)
       — that's what the background continuation should look like.
    2. Fill the zone solid with that color.
    3. Blur the filled zone heavily so it transitions smoothly from the border.
    4. Desaturate to reduce color cast.
    5. Feather-blend back into the original for seamless edges.
    """
    H, W = img.shape[:2]
    x0c, y0c = max(0, x0), max(0, y0)
    x1c, y1c = min(W, x1), min(H, y1)
    if x0c >= x1c or y0c >= y1c:
        return img

    # Sample border color from a thin strip just OUTSIDE the zone (top edge)
    border_h = max(4, (y1c - y0c) // 12)
    border_top = img[max(0, y0c - border_h):y0c, x0c:x1c]
    border_left = img[y0c:y1c, max(0, x0c - border_h):x0c]
    border_right = img[y0c:y1c, x1c:min(W, x1c + border_h)]

    samples = []
    for s in [border_top, border_left, border_right]:
        if s.size > 0:
            samples.append(s.reshape(-1, 3))
    if samples:
        bg_color = np.vstack(samples).mean(axis=0)
    else:
        bg_color = img[y0c:y1c, x0c:x1c].reshape(-1, 3).mean(axis=0)

    # Build a fill image: solid bg_color in zone, original elsewhere
    filled = img.copy().astype(np.float32)
    filled[y0c:y1c, x0c:x1c] = bg_color

    # Blur the filled image to create smooth gradient into the zone
    blurred = cv2.GaussianBlur(filled.astype(np.uint8), (121, 121), 0).astype(np.float32)
    blurred = cv2.GaussianBlur(blurred.astype(np.uint8), (121, 121), 0).astype(np.float32)

    # Desaturate
    if desat > 0:
        gray = cv2.cvtColor(blurred.astype(np.uint8), cv2.COLOR_BGR2GRAY)
        gray_bgr = cv2.cvtColor(gray, cv2.COLOR_GRAY2BGR).astype(np.float32)
        blurred = blurred * (1 - desat) + gray_bgr * desat

    # Feathered zone mask
    zone_mask = np.zeros((H, W), dtype=np.float32)
    zone_mask[y0c:y1c, x0c:x1c] = 1.0
    zone_mask = cv2.GaussianBlur(zone_mask, (71, 71), 0)

    m = zone_mask[:, :, None]
    result = blurred * m + img.astype(np.float32) * (1 - m)
    return np.clip(result, 0, 255).astype(np.uint8)


def inpaint_small(img, polys_frac, radius=8):
    """Single-pass inpaint — only for masks < ~3% of image area."""
    H, W = img.shape[:2]
    mask = np.zeros((H, W), dtype=np.uint8)
    for pts in polys_frac:
        arr = np.array([[int(x*W), int(y*H)] for x, y in pts], np.int32)
        cv2.fillPoly(mask, [arr], 255)
    return cv2.inpaint(img, mask, radius, cv2.INPAINT_NS)


def load(path):
    img = cv2.imread(path)
    if img is None:
        raise FileNotFoundError(path)
    H0, W0 = img.shape[:2]
    return (cv2.resize(img, (int(W0*SCALE), int(H0*SCALE)),
                       interpolation=cv2.INTER_AREA), W0, H0)


def save(img, W0, H0, dst):
    out = cv2.resize(img, (W0, H0), interpolation=cv2.INTER_LANCZOS4)
    cv2.imwrite(dst, out, [cv2.IMWRITE_JPEG_QUALITY, 93])
    print(f"  Saved {dst}")


def b(x0f, y0f, x1f, y1f, W, H):
    return int(x0f*W), int(y0f*H), int(x1f*W), int(y1f*H)


# ===========================================================================
# IMG_1076 2.JPG — straight-on rear view
#
# This photo has the best clean-source opportunities:
#   - White vinyl fence runs the full left side above the clutter
#   - Clean patio concrete visible at right x=0.55–0.92, y=0.68–0.97
#   - Clean grass/ground at right x=0.62–0.92, y=0.54–0.72
#
# Strategy: Laplacian blend for all zones — source content closely matches
# what should be behind the clutter in each area.
# ===========================================================================

def clean_1076():
    src_path = "team_inbox/IMG_1076 2.JPG"
    dst_path = "owner_inbox/house_clean_rear.jpg"
    print(f"\n=== IMG_1076 (rear straight-on) ===")
    img, W0, H0 = load(src_path)
    ref = img.copy()
    W, H = img.shape[1], img.shape[0]
    bx = lambda *a: b(*a, W, H)

    # 1 — lower-left fence zone: fence from same columns above
    print("  1: lower-left (fence blend)")
    img = blend_patch(img, ref, bx(0.00,0.38,0.38,0.58), bx(0.00,0.56,0.38,1.00), blur_r=51)

    # 2 — center patio ground (arch zone): concrete from right
    print("  2: center ground (concrete blend)")
    img = blend_patch(img, ref, bx(0.55,0.68,0.75,0.92), bx(0.37,0.64,0.62,0.92), blur_r=41)

    # 3 — right patio debris: concrete from far right
    print("  3: right patio (concrete blend)")
    img = blend_patch(img, ref, bx(0.72,0.72,0.92,0.97), bx(0.47,0.66,0.73,0.97), blur_r=41)

    # 4 — bins: fence from directly above
    print("  4: bins (fence blend)")
    img = blend_patch(img, ref, bx(0.00,0.36,0.14,0.54), bx(0.00,0.50,0.14,0.82), blur_r=25)

    # 5 — ladder: siding from left of ladder
    print("  5: ladder (siding blend)")
    img = blend_patch(img, ref, bx(0.26,0.28,0.38,0.52), bx(0.36,0.28,0.48,0.54), blur_r=21)

    # 6 — dog on stairs: stair/railing from right of dog
    print("  6: dog (stair blend)")
    img = blend_patch(img, ref, bx(0.50,0.46,0.62,0.68), bx(0.42,0.48,0.58,0.72), blur_r=21)

    # 7 — residual mid-arch (small inpaint ~2%)
    print("  7: arch residual (small inpaint)")
    img = inpaint_small(img, [[(0.37,0.54),(0.50,0.54),(0.50,0.66),(0.37,0.66)]])

    save(img, W0, H0, dst_path)


# ===========================================================================
# IMG_1077 2.JPG — angled rear view
#
# Challenging: the clutter covers most of the lower half. No single clean
# area can serve as source for all zones without visible mismatch.
#
# Strategy:
#   - Bins (small): inpaint
#   - Grill (right edge): blend from clean grass just left of grill
#   - Lower-left tarp + lumber + center arch: neutralize (heavy blur + desat)
#     These become a soft blurred ground plane, ideal for deck compositing
#   - Porch clutter/dog: blend from clean siding/stair above
# ===========================================================================

def clean_1077():
    src_path = "team_inbox/IMG_1077 2.JPG"
    dst_path = "owner_inbox/house_clean_angle.jpg"
    print(f"\n=== IMG_1077 (rear angled) ===")
    img, W0, H0 = load(src_path)
    ref = img.copy()
    W, H = img.shape[1], img.shape[0]
    bx = lambda *a: b(*a, W, H)

    # 1 — grill far-right: blend clean grass from just left (x=0.66–0.84, y=0.50–0.70)
    print("  1: grill (grass blend)")
    img = blend_patch(img, ref, bx(0.66,0.50,0.83,0.70), bx(0.83,0.50,1.00,0.92), blur_r=35)

    # 2 — right debris: blend ground from lower-right
    print("  2: right debris (ground blend)")
    img = blend_patch(img, ref, bx(0.62,0.72,0.80,0.88), bx(0.66,0.56,0.84,0.82), blur_r=25)

    # 3 — bins: small inpaint
    print("  3: bins (small inpaint)")
    img = inpaint_small(img, [[(0.00,0.48),(0.12,0.48),(0.12,0.72),(0.00,0.72)]])

    # 4 — main clutter zone (tarp, lumber, arch, porch, dog): neutralize entire lower section
    print("  4: main clutter zone (neutralize)")
    x0, y0, x1, y1 = bx(0.00,0.42,0.84,1.00)
    img = neutralize_zone(img, x0, y0, x1, y1, desat=0.40)

    save(img, W0, H0, dst_path)


# ===========================================================================
# IMG_1075 2.JPG — patio side view
#
# Challenging: clutter covers most of lower 60% of frame from multiple angles.
# Clean sources: patio flagstone at x=0.00–0.20, y=0.56–0.72 (narrow strip)
#
# Strategy:
#   - Dog foreground: blend patio surface from nearby clean strip
#   - Porch area: blend from porch above
#   - Table, chair, grill, bottom debris: neutralize (blurred ground plane)
# ===========================================================================

def clean_1075():
    src_path = "team_inbox/IMG_1075 2.JPG"
    dst_path = "owner_inbox/house_clean_patio.jpg"
    print(f"\n=== IMG_1075 (patio side) ===")
    img, W0, H0 = load(src_path)
    ref = img.copy()
    W, H = img.shape[1], img.shape[0]
    bx = lambda *a: b(*a, W, H)

    # Image layout (back-porch side view):
    # - Clean patio flagstone: x=0.00–0.20, y=0.56–0.72 (narrow left strip)
    # - Clean lawn/ground right: x=0.52–0.66, y=0.46–0.62 (between porch and table)
    # - Dog: x=0.00–0.28, y=0.68–1.00 (foreground)
    # - Porch lumber/debris: x=0.12–0.38, y=0.40–0.68
    # - Table flat: x=0.36–0.68, y=0.48–0.86
    # - Chair: x=0.66–0.80, y=0.52–0.86
    # - Grill: x=0.80–1.00, y=0.42–0.86
    # All large clutter zones: neutralize (blurred ground plane)

    # 1 — dog foreground: patio blend from left flagstone strip
    print("  1: dog (patio blend)")
    img = blend_patch(img, ref, bx(0.00,0.56,0.20,0.70), bx(0.00,0.68,0.26,1.00), blur_r=31)

    # 2 — entire lower clutter zone: neutralize
    print("  2: lower clutter zone (neutralize)")
    x0, y0, x1, y1 = bx(0.00,0.42,1.00,1.00)
    img = neutralize_zone(img, x0, y0, x1, y1, desat=0.40)

    save(img, W0, H0, dst_path)


# ---------------------------------------------------------------------------
# Run
# ---------------------------------------------------------------------------

clean_1076()
clean_1077()
clean_1075()

print("\nAll done.")
