"""
clean_1078.py — Cleanup for IMG_1078.JPG (front porch view).
Author: Cass (Architectural Visualization Specialist)

Final approach — based on thorough coordinate analysis:

CLUTTER MAP:
  A. Bins (blue recycle + black trash):  x=0.06–0.18, y=0.56–0.74
     → fence clone: shift y=0.10–0.52 down to y=0.52–0.74 (same x)
     → below-fence ground fill: x=0.00–0.20, y=0.72–0.80

  B. Storm window board:  x=0.60–0.72, y=0.38–0.60
     → clone from between-columns (left of storm board): x=0.48–0.62, y=0.32–0.54
       shifted right to cover storm board

  C. Dog:  x=0.20–0.30, y=0.60–0.74
     → covered by mid debris fill (step D)

  D. Mid boards/debris:  x=0.20–0.42, y=0.56–0.72
     → ground fill (tight, x starts at 0.20 to keep fence)

  E. Lumber pile foreground left:  x=0.00–0.44, y=0.70–1.00
     → ground fill

  F. Shrub tangle foreground right:  x=0.42–0.92, y=0.64–1.00
     → ground fill

KEY RULES:
  - All fill zones: blur_ksize=51, feather=13 (tight)
  - Fence column (x=0.00–0.20) must not be touched by fills except below y=0.70
  - Porch railing (x=0.44–0.68, y=0.52–0.66) must be preserved — NO fills there
"""

import cv2
import numpy as np
import os

os.makedirs("owner_inbox", exist_ok=True)

SCALE = 0.25


# ---------------------------------------------------------------------------
# Utilities
# ---------------------------------------------------------------------------

def laplacian_blend(A, B, mask, levels=4):
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


def blend_patch(img, ref, src_box, dst_box, blur_r=21):
    """Laplacian-blend a patch from ref[src_box] into img at dst_box."""
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
    br = blur_r | 1
    mask = cv2.GaussianBlur(mask, (br, br), 0)
    return laplacian_blend(A, img.astype(np.float32), mask)


def fill_zone(img, x0, y0, x1, y1, bg_color, desat=0.0, blur_ksize=51, feather=13):
    """Solid color fill + double Gaussian blur, feathered at edges."""
    H, W = img.shape[:2]
    x0c, y0c = max(0, x0), max(0, y0)
    x1c, y1c = min(W, x1), min(H, y1)
    if x0c >= x1c or y0c >= y1c:
        return img
    filled = img.copy().astype(np.float32)
    filled[y0c:y1c, x0c:x1c] = bg_color
    k = blur_ksize | 1
    blurred = cv2.GaussianBlur(filled.astype(np.uint8), (k, k), 0).astype(np.float32)
    blurred = cv2.GaussianBlur(blurred.astype(np.uint8), (k, k), 0).astype(np.float32)
    if desat > 0:
        gray = cv2.cvtColor(blurred.astype(np.uint8), cv2.COLOR_BGR2GRAY)
        gray_bgr = cv2.cvtColor(gray, cv2.COLOR_GRAY2BGR).astype(np.float32)
        blurred = blurred * (1 - desat) + gray_bgr * desat
    fk = feather | 1
    zone_mask = np.zeros((H, W), dtype=np.float32)
    zone_mask[y0c:y1c, x0c:x1c] = 1.0
    zone_mask = cv2.GaussianBlur(zone_mask, (fk, fk), 0)
    m = zone_mask[:, :, None]
    result = blurred * m + img.astype(np.float32) * (1 - m)
    return np.clip(result, 0, 255).astype(np.uint8)


def sample_color(img, x0f, y0f, x1f, y1f):
    H, W = img.shape[:2]
    patch = img[int(y0f*H):int(y1f*H), int(x0f*W):int(x1f*W)]
    return patch.reshape(-1, 3).mean(axis=0) if patch.size > 0 else np.array([128., 128., 128.])


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
# IMG_1078.JPG
# ===========================================================================

def clean_1078():
    src_path = "team_inbox/IMG_1078.JPG"
    dst_path = "owner_inbox/house_clean_porch.jpg"
    print(f"\n=== IMG_1078 (front porch side view) ===")
    img, W0, H0 = load(src_path)
    ref = img.copy()
    W, H = img.shape[1], img.shape[0]
    bx = lambda *a: b(*a, W, H)

    # Sample key colors from clean regions of original
    ground_color = sample_color(ref, 0.26, 0.52, 0.38, 0.58)
    shrub_color  = sample_color(ref, 0.36, 0.60, 0.50, 0.68)
    print(f"  Ground: {ground_color.astype(int)}  Shrub: {shrub_color.astype(int)}")

    # ==========================================================
    # STEP A: BINS (x=0.06–0.18, y=0.56–0.74)
    # Strategy: Fence clone — push fence panels from above the bins.
    # The fence runs at x=0.02–0.20, y=0.10–0.54.
    # Shift: src y=0.10–0.52 → dst y=0.52–0.74 (same x-cols).
    # ==========================================================
    print("  A: bins (fence clone, push down)")
    img = blend_patch(img, ref,
                      bx(0.02, 0.10, 0.20, 0.52),   # src: clean fence panels
                      bx(0.02, 0.52, 0.20, 0.74),   # dst: bin zone
                      blur_r=19)

    # Second pass: fill remaining bin area with sampled fence color
    # (in case the clone didn't fully cover — belt + suspenders)
    fence_color = sample_color(ref, 0.04, 0.20, 0.18, 0.48)
    print(f"  Fence color: {fence_color.astype(int)}")
    print("  A2: bins residual (fence-color fill)")
    x0, y0, x1, y1 = bx(0.04, 0.58, 0.18, 0.72)
    img = fill_zone(img, x0, y0, x1, y1, fence_color,
                    desat=0.0, blur_ksize=31, feather=9)

    # ==========================================================
    # STEP B: STORM WINDOW BOARD (x=0.60–0.72, y=0.38–0.60)
    # Two-stage approach:
    # B1. Clone porch interior from just left of the board
    # B2. Fill any residual with sampled porch-interior color
    # ==========================================================
    # Storm board: Clone porch interior from left of board
    # This brings the neighbor-house-through-porch view into the board area.
    # Single clone pass, no secondary fill (secondary fill creates artifact blob).
    print("  B: storm board (porch-interior clone)")
    img = blend_patch(img, ref,
                      bx(0.46, 0.28, 0.62, 0.58),   # src: porch interior left
                      bx(0.58, 0.28, 0.74, 0.58),   # dst: storm board zone
                      blur_r=19)

    # ==========================================================
    # STEP C: MID DEBRIS + DOG (x=0.20–0.42, y=0.56–0.74)
    # Ground fill. x starts at 0.20 (keep fence).
    # ==========================================================
    print("  C: mid debris + dog (ground fill)")
    x0, y0, x1, y1 = bx(0.20, 0.56, 0.42, 0.76)
    img = fill_zone(img, x0, y0, x1, y1, ground_color,
                    desat=0.04, blur_ksize=41, feather=11)

    # ==========================================================
    # STEP D: FENCE BASE (x=0.00–0.20, y=0.70–0.82)
    # Below where fence ends + bins, continuation to ground.
    # ==========================================================
    print("  D: fence base below (ground fill)")
    x0, y0, x1, y1 = bx(0.00, 0.72, 0.22, 0.84)
    img = fill_zone(img, x0, y0, x1, y1, ground_color,
                    desat=0.04, blur_ksize=31, feather=9)

    # ==========================================================
    # STEP E: LUMBER PILE foreground left (x=0.00–0.44, y=0.76–1.00)
    # ==========================================================
    print("  E: lumber pile foreground (ground fill)")
    x0, y0, x1, y1 = bx(0.00, 0.74, 0.44, 1.00)
    img = fill_zone(img, x0, y0, x1, y1, ground_color,
                    desat=0.04, blur_ksize=51, feather=13)

    # ==========================================================
    # STEP F: SHRUB TANGLE foreground right (x=0.42–0.92, y=0.64–1.00)
    # ==========================================================
    print("  F: shrub tangle foreground (shrub-ground fill)")
    x0, y0, x1, y1 = bx(0.40, 0.62, 0.94, 1.00)
    img = fill_zone(img, x0, y0, x1, y1, shrub_color,
                    desat=0.04, blur_ksize=51, feather=13)

    # ==========================================================
    # STEP G: FAR-RIGHT branches against house wall (x=0.88–1.00, y=0.54–0.74)
    # ==========================================================
    print("  G: far-right branches (shrub-ground fill)")
    x0, y0, x1, y1 = bx(0.86, 0.54, 1.00, 0.76)
    img = fill_zone(img, x0, y0, x1, y1, shrub_color,
                    desat=0.04, blur_ksize=35, feather=9)

    save(img, W0, H0, dst_path)


# ---------------------------------------------------------------------------
clean_1078()
print("\nDone.")
