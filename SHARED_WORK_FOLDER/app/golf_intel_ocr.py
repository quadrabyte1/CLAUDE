"""
golf_intel_ocr.py — OCR numeric markers on Golf Intelligence heat maps.

Golf Intelligence heat maps display numeric elevation markers scattered
across the coloured green surface.  The markers are **decimal numbers** in
the format "X.X" (e.g. "1.2", "2.8", "4.0"), rendered as near-white text
on a coloured heat-map gradient background.

Note: The distance-ring labels (integers 5, 10, 15, 20, 25, 30) that appear
at the edges of the image are distance-from-pin markers, NOT altitude values.
They are not OCR'd or used by the pipeline.

Pipeline
--------
Pass A — interior saturated pass:
  1. Build a **white-on-colored mask** — extract bright pixels (grayscale > 175)
     inside the coloured green region (saturation > 20).
  2. Dilate + find connected components.  Filter by size.
  3. For each candidate patch, run EasyOCR with three pre-processing variants:
     - original colour patch
     - greyscale patch
     - CLAHE-enhanced + inverted (best for pale text on dark colour)
  4. Accept decimal values (X.X / X.XX) AND integer-decoded values (e.g. "22" → 2.2).
  5. Deduplicate nearby detections.

Public API
----------
extract_numeric_markers(image_path)
    -> list[tuple[int, int, float]]
    Interior decimal markers.

generate_diagnostic_overlay(image_path, markers, output_path, version)
    -> pathlib.Path

CLI
---
    python golf_intel_ocr.py <image_path> [output_path]
"""

from __future__ import annotations

import os
import re
import sys
from pathlib import Path
from typing import Sequence

import cv2
import numpy as np
from PIL import Image, ImageDraw

# ── OCR library selection ────────────────────────────────────────────────
os.environ.setdefault("KMP_DUPLICATE_LIB_OK", "TRUE")  # suppress OMP warning on macOS

try:
    import easyocr as _easyocr_module
    _EASYOCR_AVAILABLE = True
except ImportError:
    _EASYOCR_AVAILABLE = False

try:
    import pytesseract
    _TESSERACT_AVAILABLE = True
except ImportError:
    _TESSERACT_AVAILABLE = False

# Lazily-initialised EasyOCR reader (expensive to create, cheap to reuse)
_EASYOCR_READER: "_easyocr_module.Reader | None" = None  # type: ignore[name-defined]


def _get_easyocr_reader():
    global _EASYOCR_READER
    if _EASYOCR_READER is None:
        _EASYOCR_READER = _easyocr_module.Reader(["en"], gpu=False, verbose=False)
    return _EASYOCR_READER


# ── module-level constants ────────────────────────────────────────────────

# Value range (inclusive) for accepted decimal markers.
_OCR_MIN_VALUE = 0.1
_OCR_MAX_VALUE = 99.9

# Accepted text pattern: X.X  X.XX  XX.X  XX.XX
_DECIMAL_RE = re.compile(r"^\d{1,2}\.\d{1,2}$")

# Two-digit integer pattern for integer-decoded parsing (e.g. "22" → 2.2)
_TWO_DIGIT_RE = re.compile(r"^\d{2}$")

# Tesseract colon-substitution fix: "2:8" → "2.8"
_COLON_FIX_RE = re.compile(r"(\d):(\d)")

# ── Pass A (interior) constants ───────────────────────────────────────────

# White-pixel threshold: above this value in grayscale = near-white text
# Lowered from 195 → 175 to catch dimmer text in cooler heat-map regions.
_WHITE_THRESHOLD = 175

# Color saturation threshold: above this = "on the colored green surface"
# Lowered from 35 → 20 to include edge-of-green pixels.
_SAT_THRESHOLD = 20

# Morphological dilation kernel for the white-on-colored mask.
_DILATION_KERNEL_PX = 5
_DILATION_ITERATIONS = 2

# Size bounds (px) for candidate text patch bounding boxes.
_PATCH_MIN_AREA = 80
_PATCH_MAX_AREA = 5000
_PATCH_MIN_W = 8
_PATCH_MAX_W = 100
_PATCH_MIN_H = 6
# Raised from 50 → 80 (v4.88) so that CC31-class blobs (height ~72 px) pass.
# CC31 on DeLaveaga H5 was a 66×72 component: the dilation kernel merged the
# ~40 px text glyph with adjacent zero-sat exterior grey-grid pixels, bloating
# height to 72 px.  Raising the ceiling to 80 catches these without admitting
# wide contour-line segments (those are blocked by _PATCH_MAX_ASPECT=6.0 first).
_PATCH_MAX_H = 80

# Aspect ratio guard: width/height must be < this (avoids thin contour lines)
_PATCH_MAX_ASPECT = 6.0

# Padding around each candidate box before OCR (original image pixels).
# Increased from 12 → 20 to provide more context for EasyOCR.
_PATCH_PAD = 20

# Scale factor applied to patches before feeding EasyOCR / Tesseract.
# Raised from 40 → 120 so that patches (~62 px tall with 20 px padding around
# a 22 px CC) are upscaled 2× before OCR.  At native size the ~15 px glyphs
# were too small for EasyOCR to recognise reliably (root cause of the 6.0/6.5
# misses on DeLaveaga H5 and similar dark-region markers on other courses).
_PATCH_SCALE_MIN_H = 120  # minimum height in px of the scaled patch

# Minimum confidence from OCR (0-1 for EasyOCR, 0-100 for Tesseract)
_EASYOCR_MIN_CONF = 0.35
_TESS_MIN_CONF = 25

# ── Shared dedup ──────────────────────────────────────────────────────────

# Duplicate suppression radius (px)
_DEDUP_RADIUS = 20


# ── helpers ────────────────────────────────────────────────────────────────

def _is_valid_marker(s: str) -> bool:
    """True iff s is a decimal string matching X.X or X.XX in the valid range."""
    s = s.strip()
    # Fix colon-for-period OCR artefact before checking
    s = _COLON_FIX_RE.sub(r"\1.\2", s)
    if not _DECIMAL_RE.match(s):
        return False
    try:
        v = float(s)
    except ValueError:
        return False
    return _OCR_MIN_VALUE <= v <= _OCR_MAX_VALUE


def _parse_marker_value(s: str) -> float | None:
    """
    Return float value from a validated marker string, or None.

    Accepts:
    - Decimal strings: "2.8", "1.6", "3.05"
    - Two-digit integers decoded as decimals: "22" → 2.2, "14" → 1.4
      (EasyOCR sometimes drops the period for small values)
    """
    s = s.strip()
    s = _COLON_FIX_RE.sub(r"\1.\2", s)

    # Standard decimal
    if _DECIMAL_RE.match(s):
        try:
            v = float(s)
        except ValueError:
            return None
        if _OCR_MIN_VALUE <= v <= _OCR_MAX_VALUE:
            return v

    # Two-digit integer → X.Y (decimal stripped by OCR)
    if _TWO_DIGIT_RE.match(s):
        try:
            v_int = int(s)
        except ValueError:
            return None
        v_dec = v_int / 10.0
        if _OCR_MIN_VALUE <= v_dec <= 9.9:
            return v_dec

    return None


def _build_white_on_colored_mask(img_bgr: np.ndarray) -> np.ndarray:
    """
    Return a binary mask that is HIGH (255) where near-white pixels sit on
    the coloured green surface.

    Thresholds relaxed vs v4.79:
    - grayscale > 175 (was 195) — catches dimmer text in cool heat-map areas
    - saturation > 20 (was 35) — catches edge-of-green pixels
    """
    gray = cv2.cvtColor(img_bgr, cv2.COLOR_BGR2GRAY)
    hsv = cv2.cvtColor(img_bgr, cv2.COLOR_BGR2HSV)
    white_px = gray > _WHITE_THRESHOLD
    on_color = hsv[:, :, 1] > _SAT_THRESHOLD
    mask = (white_px & on_color).astype(np.uint8) * 255
    kern = cv2.getStructuringElement(
        cv2.MORPH_RECT, (_DILATION_KERNEL_PX, _DILATION_KERNEL_PX)
    )
    mask = cv2.dilate(mask, kern, iterations=_DILATION_ITERATIONS)
    return mask


def _candidate_patches(
    mask: np.ndarray,
) -> list[tuple[int, int, int, int]]:
    """
    Find connected components in the white-on-colored mask and filter to
    those whose size matches an expected elevation label.

    Returns list of (x, y, w, h) bounding boxes in original image space.
    """
    n_cc, _labels, stats, _centroids = cv2.connectedComponentsWithStats(
        mask, connectivity=8
    )
    patches = []
    for i in range(1, n_cc):
        area = int(stats[i, cv2.CC_STAT_AREA])
        x = int(stats[i, cv2.CC_STAT_LEFT])
        y = int(stats[i, cv2.CC_STAT_TOP])
        bw = int(stats[i, cv2.CC_STAT_WIDTH])
        bh = int(stats[i, cv2.CC_STAT_HEIGHT])
        if not (_PATCH_MIN_AREA <= area <= _PATCH_MAX_AREA):
            continue
        if not (_PATCH_MIN_W <= bw <= _PATCH_MAX_W):
            continue
        if not (_PATCH_MIN_H <= bh <= _PATCH_MAX_H):
            continue
        if bh > 0 and bw / bh > _PATCH_MAX_ASPECT:
            continue  # likely a thin contour line segment
        patches.append((x, y, bw, bh))
    return patches


def _scale_patch(patch_bgr: np.ndarray, min_h: int = _PATCH_SCALE_MIN_H) -> np.ndarray:
    """Upscale patch so its height >= min_h for better OCR accuracy."""
    ph, pw = patch_bgr.shape[:2]
    if ph < min_h:
        scale = int(np.ceil(min_h / ph))
        patch_bgr = cv2.resize(
            patch_bgr, (pw * scale, ph * scale), interpolation=cv2.INTER_CUBIC
        )
    return patch_bgr


def _preprocess_variants(patch_bgr: np.ndarray) -> list[np.ndarray]:
    """
    Return a list of pre-processed versions of the patch for multi-pass OCR.

    Variants:
    1. Original colour patch (best for bright text on saturated background)
    2. Greyscale (avoids colour confusion for some EasyOCR paths)
    3. CLAHE-enhanced + inverted (best for pale/dim text and exterior labels)
    """
    gray = cv2.cvtColor(patch_bgr, cv2.COLOR_BGR2GRAY)
    clahe = cv2.createCLAHE(clipLimit=3.0, tileGridSize=(4, 4))
    enhanced = clahe.apply(gray)
    inv_enhanced = cv2.bitwise_not(enhanced)
    return [
        patch_bgr,
        cv2.cvtColor(gray, cv2.COLOR_GRAY2BGR),
        cv2.cvtColor(inv_enhanced, cv2.COLOR_GRAY2BGR),
    ]


def _ocr_easyocr(
    patch_bgr: np.ndarray,
    cx: int,
    cy: int,
    parse_fn=_parse_marker_value,
) -> list[tuple[int, int, float, float]]:
    """
    Run EasyOCR on all pre-processed variants of a patch.
    Returns [(cx, cy, value, conf)] using the best (highest-conf) result per variant.
    """
    reader = _get_easyocr_reader()
    hits = []
    for variant in _preprocess_variants(patch_bgr):
        scaled = _scale_patch(variant)
        results = reader.readtext(scaled, detail=1, allowlist="0123456789.")
        for _bbox, text, conf in results:
            if conf < _EASYOCR_MIN_CONF or not text.strip():
                continue
            v = parse_fn(text.strip())
            if v is None:
                continue
            hits.append((cx, cy, v, float(conf)))
    return hits


def _ocr_tesseract(
    patch_bgr: np.ndarray,
    cx: int,
    cy: int,
) -> list[tuple[int, int, float, float]]:
    """Tesseract fallback. Returns [(cx, cy, value, conf)]."""
    patch_bgr = _scale_patch(patch_bgr)
    pil = Image.fromarray(cv2.cvtColor(patch_bgr, cv2.COLOR_BGR2RGB))
    cfg = "--psm 11 --oem 3"
    data = pytesseract.image_to_data(
        pil, config=cfg, output_type=pytesseract.Output.DICT
    )
    hits = []
    for i, text in enumerate(data["text"]):
        conf = int(data["conf"][i])
        if conf < _TESS_MIN_CONF or not text.strip():
            continue
        v = _parse_marker_value(text.strip())
        if v is None:
            continue
        hits.append((cx, cy, v, float(conf) / 100.0))
    return hits


def _deduplicate(
    hits: list[tuple[int, int, float, float]],
    radius: int = _DEDUP_RADIUS,
) -> list[tuple[int, int, float]]:
    """
    Collapse hits within `radius` pixels to the one with the highest confidence.
    Returns [(x, y, value), …] sorted by y then x.
    """
    hits_sorted = sorted(hits, key=lambda h: h[3], reverse=True)
    kept: list[tuple[int, int, float, float]] = []
    for h in hits_sorted:
        hx, hy = h[0], h[1]
        too_close = any(
            abs(hx - k[0]) < radius and abs(hy - k[1]) < radius
            for k in kept
        )
        if not too_close:
            kept.append(h)
    return sorted(
        [(x, y, v) for x, y, v, _ in kept],
        key=lambda m: (m[1], m[0]),
    )


# ── Pass A: interior saturated pass ──────────────────────────────────────

def _pass_a_interior(
    img_bgr: np.ndarray,
) -> list[tuple[int, int, float, float]]:
    """
    Detect interior decimal elevation markers via the white-on-colored mask.

    Returns raw (x, y, value, confidence) hits before deduplication.
    """
    ih, iw = img_bgr.shape[:2]

    mask = _build_white_on_colored_mask(img_bgr)
    patches = _candidate_patches(mask)

    raw_hits: list[tuple[int, int, float, float]] = []
    for bx, by, bw, bh in patches:
        cx = bx + bw // 2
        cy = by + bh // 2
        x1 = max(0, bx - _PATCH_PAD)
        y1 = max(0, by - _PATCH_PAD)
        x2 = min(iw, bx + bw + _PATCH_PAD)
        y2 = min(ih, by + bh + _PATCH_PAD)
        patch = img_bgr[y1:y2, x1:x2]
        if patch.size == 0:
            continue

        if _EASYOCR_AVAILABLE:
            hits = _ocr_easyocr(patch, cx, cy, parse_fn=_parse_marker_value)
        else:
            hits = _ocr_tesseract(patch, cx, cy)

        raw_hits.extend(hits)

    return raw_hits


# ── main public API ────────────────────────────────────────────────────────

def extract_numeric_markers(
    image_path: str | Path,
) -> list[tuple[int, int, float]]:
    """
    Detect numeric elevation markers on a Golf Intelligence heat map.

    Returns interior decimal markers (X.X format) only.  The exterior
    distance-ring labels (5, 10, 15, 20, 25, 30) are distance-from-pin
    values, not altitudes, and are intentionally excluded.

    Parameters
    ----------
    image_path : str or Path

    Returns
    -------
    list of (x, y, value) tuples — interior decimal markers.
    """
    if not _EASYOCR_AVAILABLE and not _TESSERACT_AVAILABLE:
        raise RuntimeError(
            "No OCR engine available. Install: pip install easyocr  OR  "
            "brew install tesseract && pip install pytesseract"
        )

    image_path = Path(image_path)
    img_bgr = cv2.imread(str(image_path))
    if img_bgr is None:
        raise FileNotFoundError(f"Cannot read image: {image_path}")

    raw_hits = _pass_a_interior(img_bgr)
    return _deduplicate(raw_hits)


def generate_diagnostic_overlay(
    image_path: str | Path,
    markers: Sequence[tuple[int, int, float]],
    output_path: str | Path,
    version: str = "v1.0",
) -> Path:
    """
    Write an annotated PNG that marks every detected numeric elevation marker
    on the source image.

    For each (x, y, value) in markers:
    - A magenta circle is drawn at (x, y).
    - The value label is drawn in hot-pink to the right.

    A version badge and marker count are placed in the upper-left corner.
    """
    img_bgr = cv2.imread(str(image_path))
    if img_bgr is None:
        raise FileNotFoundError(f"Cannot read image: {image_path}")

    img_rgb = cv2.cvtColor(img_bgr, cv2.COLOR_BGR2RGB)
    pil = Image.fromarray(img_rgb)
    draw = ImageDraw.Draw(pil)

    CIRCLE_R = 7
    for mx, my, mv in markers:
        draw.ellipse(
            [mx - CIRCLE_R, my - CIRCLE_R, mx + CIRCLE_R, my + CIRCLE_R],
            outline=(255, 0, 220),  # magenta
            width=2,
        )
        label = f"{mv:.1f}"
        lx, ly = mx + CIRCLE_R + 2, my - 8
        draw.text((lx + 1, ly + 1), label, fill=(0, 0, 0))
        draw.text((lx, ly), label, fill=(255, 20, 147))

    # ── Version badge upper-left ───────────────────────────────────────────
    badge = f"Golf Intel OCR {version}"
    bx0, by0 = 6, 6
    badge_w = len(badge) * 7
    badge_h = 14
    draw.rectangle(
        [bx0 - 2, by0 - 2, bx0 + badge_w + 4, by0 + badge_h + 2],
        fill=(20, 20, 20),
    )
    draw.text((bx0, by0), badge, fill=(255, 255, 80))

    count_text = f"{len(markers)} interior markers"
    cy2 = by0 + badge_h + 6
    draw.rectangle(
        [bx0 - 2, cy2 - 2, bx0 + len(count_text) * 7 + 4, cy2 + badge_h + 2],
        fill=(20, 20, 20),
    )
    draw.text((bx0, cy2), count_text, fill=(200, 200, 200))

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
        output_path = out_dir / f"golf_intel_numeric_ocr_{stem}_2026-10-02.png"

    print(f"[golf_intel_ocr] Reading: {image_path}")
    markers = extract_numeric_markers(image_path)
    print(f"[golf_intel_ocr] Detected {len(markers)} markers:")
    for mx, my, mv in markers:
        print(f"  ({mx:4d}, {my:4d})  value={mv}")

    out = generate_diagnostic_overlay(markers=markers, image_path=image_path, output_path=output_path)
    print(f"[golf_intel_ocr] Overlay saved to: {out}")


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python golf_intel_ocr.py <image_path> [output_path]")
        sys.exit(1)
    _out = sys.argv[2] if len(sys.argv) > 2 else None
    run_overlay(sys.argv[1], _out)
