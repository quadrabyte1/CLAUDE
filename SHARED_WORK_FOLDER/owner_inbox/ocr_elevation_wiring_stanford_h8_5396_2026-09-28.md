# OCR Elevation Wiring — Stanford H8 5396  v1
*2026-09-28 · Sienna · Task 650 · APP_VERSION v4.79*

---

## Investigation Finding

`elevationSpikes` is **fully wired end-to-end to the printed geometry.**

The pipeline already exists: editor Alpine.js state → EGM JSON → `gradient_surface_diagnostic.py` lines 3668–3760 → Gaussian-falloff Gaussian applied to `Z_fringe` array → `build_fringe_mesh` → 3MF vertices. Every `{x, y, mm}` spike placed in the editor already produces a real bump on the printed plate.

There are ~34 references to `elevationSpikes` across the codebase. No new plumbing needed.

---

## Approach Chosen

**Reuse `elevationSpikes` — trivial wiring path.**

The OCR output (`[(x_px, y_px, value_mm), ...]`) just needs to be converted into `[{x, y, mm}]` dicts and fed into the existing Alpine.js `this.elevationSpikes` array. The cleanest injection point is the `/api/detect_boundaries` response — OCR runs on the same image that the boundary detector already has, and `runDetection()` in the editor already handles the response and calls `autoSave()`.

---

## Wiring Diagram

```
extract_numeric_markers(img_path)           [golf_intel_ocr.py]
  → [(x_px, y_px, value_mm), ...]
  → markers_to_elevation_spikes()           [app.py — new]
  → elevationMarkers: [{x, y, mm}]          [/api/detect_boundaries response]
  → runDetection() this.elevationSpikes =   [editor.html — new block]
  → autoSave() → .egm persisted
  → /api/generate_models → run_pipeline
  → gradient_surface_diagnostic.py Z_fringe Gaussian spike
  → 3MF vertices have height ≈ mm at marker positions
```

---

## New Code (app.py)

Two public functions added just above the point-clamping helpers:

- `clamp_ocr_value(v) → float | None` — accepts `0 < v <= 50`, rejects NaN/Inf/negatives/zero/above-50. Strict reject (not clamp) so a mis-read never produces a silent spike.
- `markers_to_elevation_spikes(markers) → list[dict]` — converts OCR tuples to EGM-compatible dicts, dropping out-of-range values with a diagnostic print.

One modification to `/api/detect_boundaries`: after polygon detection, runs `extract_numeric_markers(img_path)` → `markers_to_elevation_spikes()` → appends `"elevationMarkers"` to the JSON response. Wrapped in `try/except` so a missing EasyOCR install never crashes boundary detection.

One modification to `runDetection()` in `editor.html`: after populating `this.polygons` and `this.contours`, reads `result.elevationMarkers` and assigns `this.elevationSpikes`. Flash message appended with spike count.

---

## Red → Green Table

| # | Test | RED reason | GREEN |
|---|------|-----------|-------|
| T1a | `markers_to_elevation_spikes` basic conversion | ImportError | ✅ |
| T1b | mm == OCR value | ImportError | ✅ |
| T1c | x,y are integers | ImportError | ✅ |
| T1d | empty markers → empty spikes | ImportError | ✅ |
| T2a | deterministic output | ImportError | ✅ |
| T2b | order preserved | ImportError | ✅ |
| T3a | empty marker list | ImportError | ✅ |
| T3b | all filtered → empty | ImportError | ✅ |
| T4a–g | `clamp_ocr_value` boundary conditions | ImportError | ✅ |
| T5a | EGM save→load round-trip | ImportError | ✅ |
| T5b | empty spikes round-trip | ImportError | ✅ |
| T6a | detect_boundaries returns elevationMarkers key | KeyError | ✅ |
| T6b | elevationMarkers is a list | KeyError | ✅ |
| T7 | elevationMarkers shape {x,y,mm} | KeyError | ✅ |
| T8a–d | clamp boundary/NaN/Inf | ImportError | ✅ |
| T9a | runDetection reads elevationMarkers | AssertionError | ✅ |
| T9b | runDetection assigns elevationSpikes | AssertionError | ✅ |
| T9c | spikes have mm field | AssertionError | ✅ |
| T10 | zero-value excluded | ImportError | ✅ |

**28 new tests. 273 total tests. 0 regressions.**

---

## Diagnostic Overlay

`owner_inbox/ocr_elevation_wiring_stanford_h8_5396_2026-09-28.png`

8 markers detected on Stanford (Hole 8, 5396):

| Pixel position | Value (mm) |
|---------------|-----------|
| (507, 274) | 1.6 |
| (299, 292) | 0.6 |
| (146, 455) | 2.9 |
| (499, 470) | 2.8 |
| (681, 475) | 2.6 |
| (314, 629) | 2.7 |
| (137, 631) | 4.3 |
| (321, 815) | 2.3 |

Each dot is a magenta circle at the detected pixel centre, with a hot-pink value label and a v1 badge in the upper-left corner.

---

## Test Drive

1. Open the Boundary Editor at `http://localhost:5051/editor`
2. Click **New Project**
3. Select image: `Stanford (hole 8, 5396).png` / course: `Stanford` / hole: `8`
4. Click **Create**
5. The editor auto-detects boundaries (green + LL trap + LR water)
6. OCR runs on the same image — watch the flash message: it now shows `+ N OCR spike(s)` alongside the region count
7. Open the browser console: you'll see `[runDetection] OCR elevation spikes: 8 [...]` with the spike objects
8. The Elevation Spikes panel in the editor will show spikes — confirm their mm values match the table above
9. Click **Regenerate 3MF**
10. Open in Bambu Studio — confirm the fringe has visible bumps at the spike positions (Gaussian falloff, σ=8 mm)

**Key verification:** the bump at (137, 631) value=4.3 mm should be the tallest visible peak on the fringe; (507, 274) value=1.6 mm should be a modest bump near the top-centre.

---

## Follow-up (later phase)

- Interpret OCR values as **slope percent** rather than mm elevation — requires mapping the GI color scale to a gradient, then integrating to get absolute height. That's a separate task and should not touch this wiring.
- UI to manually trim auto-populated spikes (already possible via the existing spike panel — no new work needed for basic use).
