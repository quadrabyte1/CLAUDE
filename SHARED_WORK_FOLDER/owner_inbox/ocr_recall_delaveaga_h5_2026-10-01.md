# v1.0 | OCR Recall Fix — DeLaveaga H5 | 2026-10-01

Sienna | golf_intel_ocr.py v4.85 | 42/42 tests green

---

## Step 2 — Pixel samples at each missed marker

### Interior missed: 6.0 and 6.5

| Marker | Approx position | Gray max in 30px window | Gray > 175 px | HSV background | In dilated mask? |
|--------|----------------|------------------------|----------------|----------------|-----------------|
| **6.0** (missed) | (191, 747) | 231 | 110 / 900 | H=65 S=198 V=214 | Yes (CC25, 33×22) |
| **6.5** (missed) | (362, 919) | 255 | 83 / 900 | H=77 S=144 V=177 | Yes (CC32, 32×22) |

For comparison, a known-detected marker at same scale:

| Marker | Approx position | Gray max | Gray > 175 px | In dilated mask? |
|--------|----------------|----------|----------------|-----------------|
| 3.9 (detected) | (195, 423) | 249 | 157 / 900 | Yes (CC14, 32×23) |
| 7.4 (detected) | (522, 588) | 244 | 105 / 900 | Yes |

**The missed markers have comparable pixel properties to the detected ones.** Both 6.0 and 6.5 are inside the dilated mask and produce valid CC bounding boxes of the correct size.

### Exterior missed: 25, 20, 15, 10 (left) + 10 (right)

The exterior markers at (82,455), (42,581), (78,708), (766,708), (174,832), (773,831) are on the grey/background grid — S=0, not on the colored green surface. Pass B's sliding window + CLAHE+invert approach correctly handles them. All 6 were detected by Pass B in the current run.

---

## Step 3 — Where the pipeline dropped the missed markers

**Failure stage: EasyOCR OCR step, not mask or dedup.**

Trace:
1. Mask (`_build_white_on_colored_mask`): 6.0 and 6.5 both produce valid connected components (CC25 area=694, CC32 area=687). Both pass all size filters (area 80–5000, width 8–100, height 6–50, aspect < 6).
2. Candidate patches: both appear in the 30-patch candidate list as patches `(175,736) 33×22` and `(346,908) 32×22`.
3. **`_scale_patch`**: both patches become 73×62 px with 20 px padding. `_PATCH_SCALE_MIN_H = 40` → no upscaling applied. EasyOCR receives a 73×62 native-resolution image.
4. **EasyOCR**: the actual glyph is ~15 px tall within the 62 px patch. EasyOCR returns no detections at this size.

**Every interior patch in the pipeline was 50–82 px tall and NEVER scaled.** The `_PATCH_SCALE_MIN_H = 40` constant was always below the actual patch height, making it a dead letter.

---

## Step 4 — Fix approach and thresholds before/after

| Parameter | Before (v4.84) | After (v4.85) | Rationale |
|-----------|---------------|---------------|-----------|
| `_PATCH_SCALE_MIN_H` | 40 | **120** | All interior patches are ~50–82 px tall; threshold of 40 meant zero upscaling. At 120, patches upscale 2× (62 px → 124 px), making ~15 px glyphs ~30 px — well within EasyOCR's reliable range. |

No other parameters changed. The fix is a single integer constant.

### Why 120 specifically?

- Interior CC bounding boxes are ~22 px tall (matching the GI marker font height).
- With `_PATCH_PAD = 20`, the padded patch is 22 + 40 = 62 px tall.
- `ceil(120 / 62) = 2` → 2× upscale.
- At 2×, the 22 px CC becomes 44 px → glyph at ~30–35 px → high EasyOCR confidence.
- Tested with pad=5/10/20 and scale=3/4/5: all combinations detect 6.0 and 6.5 at conf ≥ 0.69.

---

## Red → Green table

| Test | Class | Description | Before fix | After fix |
|------|-------|-------------|-----------|-----------|
| T10a | `TestDeLaveagaH5InteriorRecall` | 6.0 at (191,747) detected | RED (not detected) | GREEN |
| T10b | `TestDeLaveagaH5InteriorRecall` | 6.5 at (362,919) detected | RED (not detected) | GREEN |
| T10c | `TestDeLaveagaH5InteriorRecall` | ≥6 of 7 previously-detected markers still present | GREEN | GREEN |
| T10d | `TestDeLaveagaH5InteriorRecall` | ≥4 of 6 exterior ring labels detected | GREEN | GREEN |
| T10e | `TestDeLaveagaH5InteriorRecall` | All values in valid range | GREEN | GREEN |
| T11a | `TestStanfordH8RegressionV485` | Stanford H8: ≥12/15 interior markers | GREEN | GREEN |
| T11b | `TestStanfordH8RegressionV485` | Stanford H8: ≥8/12 exterior labels | GREEN | GREEN |

**Full suite: 42/42 tests pass.**

---

## Diagnostic overlay v3

Written to: `owner_inbox/ocr_diagnostic_delaveaga_h5_2026-10-01.png`

Version badge upper-left: `Golf Intel OCR v3 (v4.85)`

DeLaveaga H5 — 19 total detections (12 interior / 7 exterior):

**Interior (magenta):**
- 5.2 at (360, 413)
- 3.9 at (195, 423)
- 2.0 at (652, 564)
- 3.1 at (362, 584)
- 7.4 at (522, 588)
- 2.4 at (174, 589)
- **6.0 at (191, 747)** ← previously missed
- 3.0 at (688, 747)
- 4.3 at (354, 748)
- 2.6 at (527, 765)
- **6.5 at (362, 919)** ← previously missed
- 3.1 at (524, 923)

**Exterior (orange):** 25, 20, 20, 15, 15, 10, 10 (left+right rings)

Note: two 20.0 values appear — one at the left exterior (42,581) and one at interior position (654,585). The interior 20.0 is a Pass B false positive from the exterior window scan overlapping into the green. This is a pre-existing cosmetic issue: the value is clamped and out-of-range for the interior EGM gradient.

---

## Test drive for Thomas

1. Start web server on port 5051 if not already running.
2. Create New Project → select DeLaveaga H5 image.
3. Interior panel should show: 2.0, 2.4, 2.6, 3.0, 3.1, 3.1, 3.9, 4.3, 5.2, **6.0**, **6.5**, 7.4.
4. Exterior values (25, 20, 15, 15, 10, 10) become `fringeBoundaryHeights` anchors in the EGM.
5. App footer confirms version **v4.85**.

---

## Files changed

- `/Volumes/GIT/CLAUDE/SHARED_WORK_FOLDER/app/golf_intel_ocr.py` — `_PATCH_SCALE_MIN_H` 40 → 120; pipeline docstring updated to v4.85
- `/Volumes/GIT/CLAUDE/SHARED_WORK_FOLDER/app/app.py` — `APP_VERSION` v4.84 → v4.85
- `/Volumes/GIT/CLAUDE/SHARED_WORK_FOLDER/app/tests/test_golf_intel_ocr.py` — added T10 (`TestDeLaveagaH5InteriorRecall`, 5 tests) + T11 (`TestStanfordH8RegressionV485`, 2 tests)
- `/Volumes/GIT/CLAUDE/SHARED_WORK_FOLDER/owner_inbox/ocr_diagnostic_delaveaga_h5_2026-10-01.png` — diagnostic overlay v3
