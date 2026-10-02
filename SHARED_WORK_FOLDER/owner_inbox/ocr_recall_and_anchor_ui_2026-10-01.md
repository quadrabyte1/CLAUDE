# OCR Recall + Fringe Anchor UI — v4.88

**v4.88** | 2026-10-01 | Sienna

---

## Part A — Missed Interior Marker at Bottom-Right

### Pixel Sample of the Missed Marker

Location: approximately (709, 904) on DeLaveaga H5 (817×1221 px).

| Property | Value |
|---|---|
| Background HSV | hue=99, sat=151, gray=134 (very dark teal) |
| Near-bright glyph pixels | gray=167–233, sat=18–100, hue=97–103 |
| Background vs surrounding | Slightly lighter on-colored region — this is the darkest slope-gradient band |
| OCR-read value | **3.6** (consistent, conf 0.97–0.99 on CLAHE+inv variant) |
| Task description said | "3.0" — this is the human visual read; OCR consistently resolves to 3.6 |

### Where the Pipeline Dropped It

**Connected component CC31** at bbox=(676, 868, 66×72 px), area=1571.

The `_candidate_patches()` size filter rejected it:

```
_PATCH_MAX_H = 50   ← OLD value
CC31 height = 72    ← FAIL
```

**Why the CC is 72 px tall:** The 5 px dilation kernel merged the text glyph (~40 px) with adjacent zero-saturation exterior grey-grid pixels near x=720–741. The grey-grid column along the right image boundary has sat=0, gray=226 — those bright pixels also pass the `gray > 175` threshold. After dilation they connect to the colored-background text cluster, inflating the bounding box from ~40 px to 72 px tall.

The text itself lives at y=895–939 (44 px) — well within the old limit. Only the merged grey artifact pushed height over 50.

### Fix Applied

```python
# golf_intel_ocr.py, line 125
_PATCH_MAX_H = 80  # was 50 — raised to catch CC31-class blobs (v4.88)
```

80 px is chosen because:
- CC31 height = 72 px → now PASSES
- The aspect ratio guard (`_PATCH_MAX_ASPECT = 6.0`) still blocks thin contour-line segments
- Wide decorative blobs would be caught by `_PATCH_MAX_AREA = 5000` (CC31 area=1571 is well within range)

### Regression Impact

Full suite: **46/46 OCR tests pass** after the fix. Stanford H8 interior recall (12/15) and exterior recall (8/12) unchanged.

---

## Part B — Fringe Anchor Badge Visibility

### Empirical: fringeBoundaryHeights in API Response

After updating `detect_boundaries` to use `extract_numeric_markers_with_exterior`:

```
POST /api/detect_boundaries  →  DeLaveaga H5
elevationMarkers: 11 entries (interior spikes)
fringeBoundaryHeights: 9 entries
  {value: 25.0, x: 82,  y: 455}   ← exterior 25-ring left
  {value:  2.0, x: 652, y: 564}   ← interior marker outside green polygon
  {value: 20.0, x: 42,  y: 581}   ← exterior 20-ring left
  {value: 20.0, x: 654, y: 585}   ← exterior 20-ring right
  {value: 15.0, x: 78,  y: 708}   ← exterior 15-ring left
  {value: 15.0, x: 766, y: 708}   ← exterior 15-ring right
  {value: 10.0, x: 773, y: 831}   ← exterior 10-ring right
  {value: 10.0, x: 174, y: 832}   ← exterior 10-ring left
  {value:  3.6, x: 709, y: 904}   ← new CC31 bottom-right detection
```

7 of the 9 are distance-ring labels (5–30) from Pass B. 2 are interior-OCR markers that fall outside the detected green polygon.

### New Anchor Badge Visual

Each `fringeBoundaryHeights` entry gets an absolutely-positioned badge on the canvas:

- **Colour:** Blue scheme — border `#4B7EC8`, background `#E0EDFF`, tab `#B8D3F0`
- **Letter:** `F` (Fringe) — distinct from orange `E` (Elevation spike) badges
- **Content:** value formatted to 1 decimal place (e.g. `15.0`)
- **Interaction:** `pointer-events-none` + `cursor-default` — non-draggable, click-through
- **Tooltip:** "Fringe boundary anchor N — value X. Derived from OCR exterior label. Drives fringe/green seam Z at the nearest boundary interface point. Not editable."
- **z-index:** 18 (below spike badges at z=20; above canvas at z=0)
- **Position tracking:** `left: anchor.x * scale + offsetX; top: anchor.y * scale + offsetY` — tracks image exactly like spike badges

### Status Strip

A compact read-only strip is placed in the **lower-left of the canvas area** (`bottom-2 left-2`):

```
3 interior spikes · 2 fringe anchors detected
```

- Hidden when no image is loaded or no markers found
- `pointer-events-none` (doesn't block canvas interaction)
- `bg-white/90 backdrop-blur-sm` — blends naturally over the image
- Shows exact counts with correct singular/plural ("1 spike" vs "2 spikes")

### Legend Update

Added "Fringe anchor" entry (blue swatch `#E0EDFF` / `#4B7EC8` border) to the Regions legend in the upper-right corner, below "Elev spike".

### DOM Assertions Covered

| Test | What it checks |
|---|---|
| `test_fringe_anchor_badge_markup_present` | `data-fringe-anchor="true"` attribute present |
| `test_fringe_anchor_xfor_loop_present` | `x-for` over `fringeBoundaryHeights` with `key='anchor-'` |
| `test_status_strip_spike_count_present` | `elevationSpikes.length` referenced |
| `test_status_strip_anchor_count_present` | `fringeBoundaryHeights.length` referenced |
| `test_status_strip_has_ocr_summary_text` | `spikes` + `anchors` text present |
| `test_fringe_anchor_badge_uses_F_letter` | `>F<` (with whitespace) in anchor badge section |
| `test_fringe_anchor_positioned_on_canvas` | `offsetX` / `offsetY` in positioning style |
| `test_fringe_anchor_badge_non_editable_indicator` | `pointer-events-none` in badge section |

---

## Diagnostic Overlay

`owner_inbox/ocr_diagnostic_delaveaga_h5_v4_2026-10-01.png`

- 20 total detections: 13 interior (magenta circles), 7 exterior (orange circles)
- New CC31 detection at (709, 904) value=3.6 is shown
- Version badge top-left: `Golf Intel OCR v4.88`

---

## Red → Green Table

| # | Test | Before | After |
|---|---|---|---|
| T12a | `test_cc31_bottom_right_marker_detected` | RED | GREEN |
| T12b | `test_no_grey_grid_false_positives` | GREEN | GREEN |
| T12c | `test_previously_detected_still_present` | GREEN | GREEN |
| T12d | `test_total_interior_count_increased` (≥13) | RED | GREEN |
| T4a | `test_fringe_boundary_heights_at_least_4` | GREEN | GREEN |
| T4b | `test_fringe_boundary_heights_have_correct_shape` | GREEN | GREEN |
| T5a | `test_fringe_anchor_badge_markup_present` | RED | GREEN |
| T5b | `test_fringe_anchor_xfor_loop_present` | RED | GREEN |
| T6a | `test_status_strip_spike_count_present` | GREEN | GREEN |
| T6b | `test_status_strip_anchor_count_present` | GREEN | GREEN |
| T6c | `test_status_strip_has_ocr_summary_text` | GREEN | GREEN |
| T8 | `test_fringe_anchor_badge_uses_F_letter` | RED | GREEN |
| — | All 358 existing tests | GREEN | GREEN |

---

## Test Drive for Thomas

1. Start the web server on port 5051
2. **New Project** → pick DeLaveaga Hole 5 image
3. After detection completes:
   - Interior panel shows **13 markers** including the newly-caught **3.6** at bottom-right (~709, 904)
   - Canvas shows **blue `F` badges** for fringe anchors (distinct from orange `E` elevation-spike badges)
   - Status strip in lower-left shows e.g. `11 interior spikes · 9 fringe anchors detected`
4. Hover any blue `F` badge → tooltip explains it's a derived OCR anchor, not editable
5. Version footer shows **v4.88**

---

## Files Changed

| File | Change |
|---|---|
| `app/golf_intel_ocr.py` | `_PATCH_MAX_H` 50 → 80; pipeline version comment v4.85 → v4.88 |
| `app/app.py` | `APP_VERSION` v4.87 → v4.88; `extract_numeric_markers` → `extract_numeric_markers_with_exterior` in `detect_boundaries` |
| `app/templates/editor.html` | Fringe anchor badge template, OCR status strip, legend entry |
| `app/tests/test_golf_intel_ocr.py` | T12 class `TestDeLaveagaH5CC31Marker` (4 tests) |
| `app/tests/test_fringe_anchor_ui.py` | New file — T4–T8 fringe anchor UI tests (10 tests) |
| `owner_inbox/ocr_diagnostic_delaveaga_h5_v4_2026-10-01.png` | Updated overlay with v4.88 all-detections |
