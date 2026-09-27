"""
golf_intel_ocr.py — OCR numeric markers on Golf Intelligence heat maps.

Golf Intelligence heat maps display numeric elevation markers scattered
across the coloured green surface.  The markers are **decimal numbers** in the
format "X.X" (e.g. "1.2", "2.8", "4.0"), rendered as near-black text with a
white outline on top of the coloured heat-map gradient.

The module:
  1. Pre-processes the image to isolate the near-black text pixels
     (which captures both the elevation markers and the direction arrows).
  2. Uses Tesseract in sparse-text mode (PSM 11) with a digits+period
     whitelist to extract numeric tokens.
  3. Filters to values that match the X.X or X.XX pattern and are within
     a plausible elevation range (0.1 .. 99.9).
  4. Deduplicates nearby detections.
  5. Returns [(x, y, value), …] where value is a float.

Usage as millimetres
--------------------
Thomas's initial specification: treat the decimal value as millimetres from
the base of the print item.  Example: marker "2.8" → 2.8 mm elevation.

Public API
----------
extract_numeric_markers(image_path)
    -> list[tuple[int, int, float]]

generate_diagnostic_overlay(image_path, markers, output_path, version)
    -> pathlib.Path

Both functions are importable from this module for downstream use.

OCR library
-----------
Uses pytesseract (wrapper for Tesseract 5 binary) which must be on PATH.
Install: brew install tesseract && pip install pytesseract

CLI usage
---------
    python golf_intel_ocr.py <image_path> [output_path]
"""

from __future__ import annotations

import re
import sys
from pathlib import Path
from typing import Sequence

import cv2
import numpy as np
from PIL import Image, ImageDraw

# ── pytesseract import ─────────────────────────────────────────────────────
try:
    import pytesseract
    _TESSERACT_AVAILABLE = True
except ImportError:
    _TESSERACT_AVAILABLE = False

# ── module-level constants ────────────────────────────────────────────────

# Value range for accepted decimal markers.
_OCR_MIN_VALUE = 0.1
_OCR_MAX_VALUE = 99.9

# Darkness threshold for the text-extraction mask (0-255).
# GI markers are drawn as near-black / dark-navy.
_DARK_THRESHOLD = 80

# Minimum area (px²) of a connected dark component to bother OCR-ing.
_CC_MIN_AREA = 40

# Maximum area — anything bigger is likely a large arrow body or border.
_CC_MAX_AREA = 8000

# Padding around each candidate bounding box sent to Tesseract.
_PATCH_PAD = 8

# Scale applied to candidate patches before OCR (Tesseract prefers ≥30 px tall text).
_PATCH_SCALE = 4

# Minimum Tesseract confidence accepted.
_MIN_CONF = 20

# Duplicate suppression: two detections within this many pixels collapse.
_DEDUP_RADIUS = 18

# Regex that a valid marker string must match (optional leading digit(s), dot, digit(s))
# Accepts: "2.8", "1.2", "4.0", "10.5", "0.9"
_DECIMAL_RE = re.compile(r"^\d{1,2}\.\d{1,2}$")


# ── helpers ────────────────────────────────────────────────────────────────

def _is_valid_marker(s: str) -> bool:
    """Return True iff s is a decimal marker in the expected X.X format."""
    s = s.strip()
    if not _DECIMAL_RE.match(s):
        return False
    try:
        v = float(s)
    except ValueError:
        return False
    return _OCR_MIN_VALUE <= v <= _OCR_MAX_VALUE


def _extract_dark_mask(img_bgr: np.ndarray) -> np.ndarray:
    """
    Build a binary mask of near-black pixels.

    GI heat map numeric markers are rendered in near-black / dark navy on a
    coloured background.  Isolating these pixels provides a high-contrast
    binary image that Tesseract can read reliably.

    Returns a uint8 mask where 255 = dark text pixel, 0 = background.
    """
    gray = cv2.cvtColor(img_bgr, cv2.COLOR_BGR2GRAY)
    # Dark pixel mask (text + arrow bodies)
    dark = (gray < _DARK_THRESHOLD).astype(np.uint8) * 255
    return dark


def _candidate_regions(
    dark_mask: np.ndarray,
) -> list[tuple[int, int, int, int]]:
    """
    Find connected components in the dark mask that could contain a numeric label.

    Returns list of (x, y, w, h) bounding boxes.
    Arrows have large area; numeric labels are smaller groups of dark pixels.
    """
    n_cc, _labels, stats, _centroids = cv2.connectedComponentsWithStats(
        dark_mask, connectivity=8
    )
    regions = []
    for i in range(1, n_cc):
        area = stats[i, cv2.CC_STAT_AREA]
        if not (_CC_MIN_AREA <= area <= _CC_MAX_AREA):
            continue
        x = stats[i, cv2.CC_STAT_LEFT]
        y = stats[i, cv2.CC_STAT_TOP]
        w = stats[i, cv2.CC_STAT_WIDTH]
        h = stats[i, cv2.CC_STAT_HEIGHT]
        # GI labels are compact; skip very elongated shapes (arrow shafts)
        if h > 0 and w / h > 8.0:
            continue  # very wide horizontal bar = not text
        regions.append((x, y, w, h))
    return regions


def _merge_nearby_regions(
    regions: list[tuple[int, int, int, int]],
    gap: int = 20,
) -> list[tuple[int, int, int, int]]:
    """
    Merge bounding boxes that are within `gap` pixels of each other
    (horizontally or vertically) — because a decimal marker "2.8" may
    produce two separate connected components: "2" and "8" split by the
    small period.

    Uses a single-pass greedy merge; returns the merged list.
    """
    if not regions:
        return []

    # Sort by x then y
    rects = sorted(regions, key=lambda r: (r[0], r[1]))
    merged: list[list[int]] = [list(rects[0])]  # [x, y, w, h]

    for rx, ry, rw, rh in rects[1:]:
        # Check against the last merged box
        mx, my, mw, mh = merged[-1]
        # Right edge of merged box
        mr = mx + mw
        rb = ry + rh
        mb = my + mh
        # Expand to a common area if horizontally close and vertically overlapping
        h_close = (rx - mr) <= gap
        v_overlap = not (ry > mb + gap or rb < my - gap)
        if h_close and v_overlap:
            # Merge
            new_x = min(mx, rx)
            new_y = min(my, ry)
            new_r = max(mr, rx + rw)
            new_b = max(mb, rb)
            merged[-1] = [new_x, new_y, new_r - new_x, new_b - new_y]
        else:
            merged.append([rx, ry, rw, rh])
    return [(int(x), int(y), int(w), int(h)) for x, y, w, h in merged]


def _ocr_patch(
    dark_mask: np.ndarray,
    x: int,
    y: int,
    w: int,
    h: int,
) -> list[tuple[int, int, float, int]]:
    """
    Run Tesseract on a padded + upscaled sub-image of the dark mask.
    Returns list of (cx, cy, value, conf).
    """
    mh, mw = dark_mask.shape[:2]
    x1 = max(0, x - _PATCH_PAD)
    y1 = max(0, y - _PATCH_PAD)
    x2 = min(mw, x + w + _PATCH_PAD)
    y2 = min(mh, y + h + _PATCH_PAD)
    patch = dark_mask[y1:y2, x1:x2]

    ph, pw = patch.shape[:2]
    if ph == 0 or pw == 0:
        return []

    # Upscale so Tesseract has plenty of pixels to work with
    scale = _PATCH_SCALE
    big = cv2.resize(patch, (pw * scale, ph * scale), interpolation=cv2.INTER_NEAREST)

    pil_patch = Image.fromarray(big)

    # PSM 11 = sparse text (find all text anywhere in the image)
    # Whitelist: digits and period only
    cfg = "--psm 11 --oem 3 -c tessedit_char_whitelist=0123456789."
    try:
        data = pytesseract.image_to_data(
            pil_patch, config=cfg, output_type=pytesseract.Output.DICT
        )
    except Exception:
        return []

    results = []
    for i, text in enumerate(data["text"]):
        conf = int(data["conf"][i])
        text = text.strip()
        if conf < _MIN_CONF or not text:
            continue
        if not _is_valid_marker(text):
            continue
        value = float(text)
        # Map centre back to original image coords
        bx = data["left"][i]
        by = data["top"][i]
        bw_ = data["width"][i]
        bh_ = data["height"][i]
        cx = int((bx + bw_ / 2) / scale) + x1
        cy = int((by + bh_ / 2) / scale) + y1
        results.append((cx, cy, value, conf))
    return results


def _deduplicate(
    hits: list[tuple[int, int, float, int]],
    radius: int = _DEDUP_RADIUS,
) -> list[tuple[int, int, float]]:
    """
    Collapse detections within `radius` pixels to the highest-confidence hit.
    Returns [(x, y, value), …] sorted by y then x.
    """
    # Sort by confidence descending so the best hit wins when deduplicating
    hits = sorted(hits, key=lambda h: h[3], reverse=True)
    kept: list[tuple[int, int, float, int]] = []
    for h in hits:
        hx, hy = h[0], h[1]
        too_close = any(
            abs(hx - k[0]) < radius and abs(hy - k[1]) < radius
            for k in kept
        )
        if not too_close:
            kept.append(h)
    return sorted([(x, y, v) for x, y, v, _ in kept], key=lambda m: (m[1], m[0]))


# ── main public API ────────────────────────────────────────────────────────

def extract_numeric_markers(
    image_path: str | Path,
) -> list[tuple[int, int, float]]:
    """
    Detect numeric elevation markers on a Golf Intelligence heat map.

    Parameters
    ----------
    image_path : str or Path
        Path to the input image (PNG / JPG).

    Returns
    -------
    list of (x, y, value) tuples
        x, y — pixel coordinates of the detected marker centre.
        value — float elevation value (e.g. 2.8, 4.0, 1.2 …).
                 Treat as millimetres from print base per Thomas's spec.

    Raises
    ------
    FileNotFoundError  if the image cannot be loaded.
    RuntimeError       if Tesseract is not available on PATH.
    """
    if not _TESSERACT_AVAILABLE:
        raise RuntimeError(
            "pytesseract is not installed. Run: pip install pytesseract"
        )

    image_path = Path(image_path)
    img_bgr = cv2.imread(str(image_path))
    if img_bgr is None:
        raise FileNotFoundError(f"Cannot read image: {image_path}")

    dark_mask = _extract_dark_mask(img_bgr)
    regions = _candidate_regions(dark_mask)
    regions = _merge_nearby_regions(regions, gap=20)

    raw_hits: list[tuple[int, int, float, int]] = []
    for x, y, w, h in regions:
        hits = _ocr_patch(dark_mask, x, y, w, h)
        raw_hits.extend(hits)

    return _deduplicate(raw_hits)


def generate_diagnostic_overlay(
    image_path: str | Path,
    markers: Sequence[tuple[int, int, float]],
    output_path: str | Path,
    version: str = "v1.0",
) -> Path:
    """
    Write an annotated PNG that overlays every detected numeric marker
    on the source image.

    For each (x, y, value) in markers:
    - A magenta circle is drawn at (x, y).
    - The value is labelled in hot-pink to the right of the circle.

    A version badge and marker count are placed in the upper-left corner.

    Parameters
    ----------
    image_path  : source image path.
    markers     : list of (x, y, value) returned by extract_numeric_markers.
    output_path : destination PNG path.
    version     : version string baked into the upper-left badge.

    Returns
    -------
    pathlib.Path pointing to the written file.
    """
    img_bgr = cv2.imread(str(image_path))
    if img_bgr is None:
        raise FileNotFoundError(f"Cannot read image: {image_path}")

    img_rgb = cv2.cvtColor(img_bgr, cv2.COLOR_BGR2RGB)
    pil = Image.fromarray(img_rgb)
    draw = ImageDraw.Draw(pil)

    CIRCLE_R = 7
    for mx, my, mv in markers:
        # Magenta ring
        draw.ellipse(
            [mx - CIRCLE_R, my - CIRCLE_R, mx + CIRCLE_R, my + CIRCLE_R],
            outline=(255, 0, 220),
            width=2,
        )
        # Hot-pink label (dark shadow for legibility)
        label = f"{mv:.1f}"
        lx, ly = mx + CIRCLE_R + 2, my - 8
        draw.text((lx + 1, ly + 1), label, fill=(0, 0, 0))
        draw.text((lx, ly), label, fill=(255, 20, 147))  # hot pink

    # ── Version badge — upper-left ─────────────────────────────────────────
    badge = f"Golf Intel OCR {version}"
    bx, by = 6, 6
    badge_w = len(badge) * 7
    badge_h = 14
    draw.rectangle([bx - 2, by - 2, bx + badge_w + 4, by + badge_h + 2], fill=(20, 20, 20))
    draw.text((bx, by), badge, fill=(255, 255, 80))

    count_text = f"{len(markers)} markers"
    cy2 = by + badge_h + 6
    draw.rectangle([bx - 2, cy2 - 2, bx + len(count_text) * 7 + 4, cy2 + badge_h + 2], fill=(20, 20, 20))
    draw.text((bx, cy2), count_text, fill=(200, 200, 200))

    output_path = Path(output_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    pil.save(str(output_path), format="PNG")
    return output_path


# ── CLI / script entrypoint ────────────────────────────────────────────────

def run_overlay(image_path: str, output_path: str | None = None) -> None:
    """One-shot CLI wrapper: detect markers, print them, write overlay PNG."""
    image_path = Path(image_path)
    stem = image_path.stem
    if output_path is None:
        out_dir = Path(__file__).parent.parent / "owner_inbox"
        output_path = out_dir / f"golf_intel_numeric_ocr_{stem}_2026-09-27.png"

    print(f"[golf_intel_ocr] Reading: {image_path}")
    markers = extract_numeric_markers(image_path)
    print(f"[golf_intel_ocr] Detected {len(markers)} markers:")
    for mx, my, mv in markers:
        print(f"  ({mx:4d}, {my:4d})  value={mv:.1f} mm")

    out = generate_diagnostic_overlay(image_path, markers, output_path)
    print(f"[golf_intel_ocr] Overlay saved to: {out}")


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python golf_intel_ocr.py <image_path> [output_path]")
        sys.exit(1)
    _out = sys.argv[2] if len(sys.argv) > 2 else None
    run_overlay(sys.argv[1], _out)
