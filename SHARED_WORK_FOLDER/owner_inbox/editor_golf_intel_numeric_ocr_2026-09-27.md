# Golf Intelligence Numeric OCR — Handoff Report
**v1.0** | 2026-09-27 | Sienna

---

## What was built

`app/golf_intel_ocr.py` — new module that detects numeric elevation markers on Golf Intelligence heat map images using EasyOCR (primary) with a Tesseract fallback.

### Public API

```python
extract_numeric_markers(image_path) -> list[tuple[int, int, float]]
# Returns [(x, y, value), ...] where value is a float (mm from base)

generate_diagnostic_overlay(image_path, markers, output_path, version) -> Path
# Writes an annotated PNG with magenta circles + labels at each detection
```

### Pipeline

1. Build a **white-on-colored mask** — near-white pixels (grayscale > 195) that sit on the colored heat-map surface (HSV saturation > 35). This isolates marker text while excluding the gray/white grid background outside the green.
2. Dilate + connected components. Filter by bounding-box size to candidate text patches.
3. For each patch, run **EasyOCR** with a digit+period allowlist.
4. Filter to `X.X` / `X.XX` decimal pattern in range 0.1–99.9.
5. Deduplicate hits within 20px radius (keep highest-confidence reading).
6. Return sorted `(x, y, value)` list.

---

## Test results

```
28 passed, 0 failed
```

File: `app/tests/test_golf_intel_ocr.py`

| Suite | Tests | Notes |
|---|---|---|
| T0 — Unit helpers | 10 | `_is_valid_marker`, `_deduplicate` |
| T1 — Synthetic OCR | 3 | Renders 1.5, 2.8, 4.0 at known positions; all detected |
| T2 — False-positive filter | 3 | Integers and alpha strings correctly rejected |
| T3 — Real image smoke | 4 | DeLaveaga H3: 9 markers; Stanford H8: passes |
| T4 — Overlay writer | 6 | PNG written, same dims, badge visible, marker circles drawn |
| T5 — Idempotency | 2 | Real + synthetic both deterministic |

### Fix applied during this run

The synthetic test helper `_make_synthetic_image` previously rendered **dark text** on the colored background (text_color `(10,10,30)`). The module's mask pipeline requires pixels that are **both** near-white (gray > 195) **and** on a saturated surface (HSV S > 35). Pure dark text fails the first condition; pure white text fails the second.

Fix: the helper now renders **tinted-white text** `(240, 255, 200)` with a dark outline on the colored background:
- Grayscale brightness ≈ 244 — passes gray > 195
- HSV saturation ≈ 55 — passes S > 35

The helper also uses a 22 pt system font (Helvetica, with fallbacks) instead of PIL's 7 px default. EasyOCR requires at least ~15 px tall text for reliable recognition.

---

## Diagnostic overlay

Two overlay PNGs are in `owner_inbox/` for Thomas to spot-check accuracy:

- **`owner_inbox/golf_intel_numeric_ocr_DeLaveaga_Hole3_2026-09-27.png`** — DeLaveaga H3 (816×1391). 9 markers detected: 2.5, 1.4, 4.8, 3.2, 1.4, 2.7, 1.3, 0.4, 1.0.
- **`owner_inbox/golf_intel_numeric_ocr_Stanford_hole8_5396_2026-09-27.png`** — Stanford H8 (815×1227). Written by the prior partial run.

Each overlay shows:
- **Magenta circle** at each detected marker centre
- **Hot-pink label** (value to 1 decimal) to the right of the circle
- **Version badge** in the upper-left corner (dark background, yellow text)
- **Marker count** below the badge

---

## Version bumps

- `app/app.py` APP_VERSION: v4.74 → **v4.75**

---

## Notes for downstream consumers

The `extract_numeric_markers` return type is `list[tuple[int, int, float]]` where each value is a float elevation in mm from the print base (per Thomas's spec). The values are decimal readings (e.g. 2.5, 4.8, 1.3) drawn on the GI heat-map green surface — not the integer scale-bar markers (10, 15, 20, 25) at the image margins.

If EasyOCR is not installed, the module raises `RuntimeError` with install instructions. Tesseract fallback is available via `pip install pytesseract` + `brew install tesseract`.
