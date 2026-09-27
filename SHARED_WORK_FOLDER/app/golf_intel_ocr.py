"""
golf_intel_ocr.py — OCR numeric markers on Golf Intelligence heat maps.

Golf Intelligence heat maps display numeric elevation markers scattered
across the coloured green surface.  The markers are **decimal numbers** in
the format "X.X" (e.g. "1.2", "2.8", "4.0"), rendered as near-white text
on a coloured heat-map gradient background.

Pipeline
--------
1. Build a **white-on-colored mask** — extract near-white pixels that fall
   inside the coloured green region.  This isolates the text bodies of the
   elevation markers.
2. Dilate + find connected components.  Filter by size to candidate patches
   that match the expected marker footprint.
3. For each candidate patch, run **EasyOCR** (primary) with a digit+period
   allowlist.  EasyOCR handles this decorative outline font much better than
   Tesseract.
4. Filter results to the X.X / X.XX decimal pattern in a plausible value
   range (0.1 .. 99.9).
5. Deduplicate nearby detections.
6. Return [(x, y, value), …] where value is a float (millimetres from base
   per Thomas's initial specification).

Libraries
---------
EasyOCR (primary)  — ``pip install easyocr`` (no separate binary needed).
pytesseract (fallback) — requires ``brew install tesseract && pip install pytesseract``.
If neither is available the module raises RuntimeError.

Public API
----------
extract_numeric_markers(image_path)
    -> list[tuple[int, int, float]]

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

# Tesseract colon-substitution fix: "2:8" → "2.8"
_COLON_FIX_RE = re.compile(r"(\d):(\d)")

# White-pixel threshold: above this value in grayscale = near-white text
_WHITE_THRESHOLD = 195

# Color saturation threshold: above this = "on the colored green surface"
_SAT_THRESHOLD = 35

# Morphological dilation kernel for the white-on-colored mask.
_DILATION_KERNEL_PX = 5
_DILATION_ITERATIONS = 2

# Size bounds (px) for candidate text patch bounding boxes.
# After dilation the text "blob" will be slightly larger than the raw glyph.
_PATCH_MIN_AREA = 80
_PATCH_MAX_AREA = 5000
_PATCH_MIN_W = 8
_PATCH_MAX_W = 100
_PATCH_MIN_H = 6
_PATCH_MAX_H = 50

# Aspect ratio guard: width/height must be < this (avoids thin contour lines)
_PATCH_MAX_ASPECT = 6.0

# Padding around each candidate box before OCR (original image pixels)
_PATCH_PAD = 12

# Scale factor applied to patches before feeding EasyOCR / Tesseract.
_PATCH_SCALE_MIN_H = 40  # minimum height in px of the scaled patch

# Minimum confidence from OCR (0-1 for EasyOCR, 0-100 for Tesseract)
_EASYOCR_MIN_CONF = 0.35
_TESS_MIN_CONF = 25

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
    """Return float value from a validated marker string, or None."""
    s = s.strip()
    s = _COLON_FIX_RE.sub(r"\1.\2", s)
    if not _DECIMAL_RE.match(s):
        return None
    try:
        v = float(s)
    except ValueError:
        return None
    if not (_OCR_MIN_VALUE <= v <= _OCR_MAX_VALUE):
        return None
    return v


def _build_white_on_colored_mask(img_bgr: np.ndarray) -> np.ndarray:
    """
    Return a binary mask that is HIGH (255) where near-white pixels sit on
    the coloured green surface.

    This isolates the white text bodies of the GI elevation markers while
    excluding the grey/white grid background outside the green.
    """
    gray = cv2.cvtColor(img_bgr, cv2.COLOR_BGR2GRAY)
    hsv = cv2.cvtColor(img_bgr, cv2.COLOR_BGR2HSV)
    # Near-white pixels
    white_px = gray > _WHITE_THRESHOLD
    # Inside colored region (the green surface — saturation > threshold)
    on_color = hsv[:, :, 1] > _SAT_THRESHOLD
    # Combine
    mask = (white_px & on_color).astype(np.uint8) * 255
    # Dilate to join nearby character strokes into a single blob
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


def _ocr_easyocr(
    patch_bgr: np.ndarray,
    cx: int,
    cy: int,
) -> list[tuple[int, int, float, float]]:
    """Run EasyOCR on a patch. Returns [(cx, cy, value, conf)]."""
    reader = _get_easyocr_reader()
    patch_bgr = _scale_patch(patch_bgr)
    results = reader.readtext(
        patch_bgr, detail=1, allowlist="0123456789."
    )
    hits = []
    for _bbox, text, conf in results:
        if conf < _EASYOCR_MIN_CONF or not text.strip():
            continue
        v = _parse_marker_value(text.strip())
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
    cfg = "--psm 11 --oem 3"  # sparse text, no whitelist so period is kept
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
        x, y — pixel centre of the detected marker (original image coords).
        value — float elevation value (e.g. 2.8, 4.0, 1.3 …).
                 Treated as millimetres from the print base per Thomas's spec.

    Raises
    ------
    FileNotFoundError  if the image cannot be loaded.
    RuntimeError       if neither EasyOCR nor Tesseract is available.
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

    ih, iw = img_bgr.shape[:2]

    # ── 1. Build white-on-colored mask and find candidate patches ──────────
    mask = _build_white_on_colored_mask(img_bgr)
    patches = _candidate_patches(mask)

    # ── 2. OCR each candidate ──────────────────────────────────────────────
    raw_hits: list[tuple[int, int, float, float]] = []
    for bx, by, bw, bh in patches:
        # Centre of the detected blob in the original image
        cx = bx + bw // 2
        cy = by + bh // 2
        # Extract padded patch from original image
        x1 = max(0, bx - _PATCH_PAD)
        y1 = max(0, by - _PATCH_PAD)
        x2 = min(iw, bx + bw + _PATCH_PAD)
        y2 = min(ih, by + bh + _PATCH_PAD)
        patch = img_bgr[y1:y2, x1:x2]
        if patch.size == 0:
            continue

        if _EASYOCR_AVAILABLE:
            hits = _ocr_easyocr(patch, cx, cy)
        else:
            hits = _ocr_tesseract(patch, cx, cy)

        raw_hits.extend(hits)

    # ── 3. Deduplicate and return ──────────────────────────────────────────
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

    Parameters
    ----------
    image_path  : source image path.
    markers     : list of (x, y, value) returned by extract_numeric_markers.
    output_path : destination PNG path.
    version     : string baked into the badge (e.g. "v1.0").

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
        # Magenta circle
        draw.ellipse(
            [mx - CIRCLE_R, my - CIRCLE_R, mx + CIRCLE_R, my + CIRCLE_R],
            outline=(255, 0, 220),
            width=2,
        )
        # Hot-pink label with dark shadow
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

    count_text = f"{len(markers)} markers"
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
