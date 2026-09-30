# Exterior OCR Markers — Fringe/Green Boundary Anchors
## v1.0 — 2026-09-29 · Sienna

---

## Classification approach + point-in-polygon rule

A new `classify_ocr_markers(markers, green_polygon_points)` function in `app/app.py` (line ~1276) splits OCR marker dicts into two groups using a Shapely `Polygon.contains(Point(x, y))` test against the detected green polygon:

- **Interior** — marker pixel position is inside the green polygon → `elevationMarkers` (existing Gaussian spike behavior, unchanged)
- **Exterior** — marker pixel position is on or outside the green polygon → `fringeBoundaryHeights` (new boundary anchor behavior)

Fallback safety: if `green_polygon_points` has fewer than 3 vertices (degenerate or absent polygon), all markers are treated as interior — no crashes, behavior reverts to pre-task state.

The `detect_boundaries` endpoint now calls `classify_ocr_markers` after OCR. The new log line looks like:

```
[detect_boundaries] Golf Intel OCR: 6 raw marker(s) → 5 valid spike(s): 3 interior (elevationMarkers), 2 exterior (fringeBoundaryHeights)
```

---

## API shape change (backward-compatible)

`/api/detect_boundaries` now returns two fields instead of one:

```json
{
  "status": "ok",
  "elevationMarkers": [
    {"x": 210, "y": 185, "mm": 3.9},
    {"x": 310, "y": 220, "mm": 2.1}
  ],
  "fringeBoundaryHeights": [
    {"x": 42, "y": 88, "value": 4.8},
    {"x": 580, "y": 300, "value": 6.2}
  ],
  ...
}
```

- `elevationMarkers` — unchanged from before; each `{x, y, mm}` becomes an elevation spike in the EGM.
- `fringeBoundaryHeights` — new; each `{x, y, value}` is an exterior anchor. Uses `value` (not `mm`) to mark the semantic difference — these are boundary heights, not interior surface bumps.

**Backward-compatible:** older code ignoring `fringeBoundaryHeights` continues to work. The `elevationMarkers` field is unchanged.

The editor's `autoSave` persists `fringeBoundaryHeights` to the EGM JSON (alongside `elevationSpikes`). The geometry pipeline reads it back from `egm_data.get("fringeBoundaryHeights")`. EGMs written before this task simply lack the key — the pipeline treats missing as `[]`.

---

## Geometry integration approach — Approach A (anchors in interpolation)

The fringe surface in `gradient_surface_diagnostic.py::build_fringe_mesh` is built by a per-cell IDW interpolation over `bnd_z` (boundary polyline Z values). The anchor injection is a **pre-pass before the main loop**, not a post-pass override — cleaner and no rewriting of the loop.

### Step 1 — bnd_z override (fringe Z)

After `bnd_z = green_cell_z[_bnd_nearest_idxs].copy()` is computed (~line 3228), a new block loops over `fringeBoundaryHeights`:

1. Convert pixel coords to mm-space (same `_px_to_mm_2d` transform used for polygons)
2. Find the `K_BND_IDW=24` nearest `gbnd` boundary polyline points (KD-tree)
3. Set all 24 `bnd_z` entries to `anchor_value` (clamped to `[BASE_THICKNESS_MM, BASE_THICKNESS_MM + elevation_range_mm]`)

Overriding K=24 points ensures that any fringe cell whose IDW-K=24 query includes the anchor region draws all 24 inputs from the overridden band — IDW returns exactly `anchor_value` at the interface and decays smoothly toward natural Z away from it.

### Step 2 — g_bdry_arr override (green seam Z)

The seam-reseat section uses a separate `g_bdry_arr` (green top-boundary ring from the green grid scan) as its Z source. After `g_bdry_arr` is built, the same anchors override the `K_BND_IDW=24` nearest green ring vertices there too.

This ensures the seam-reseat IDW (K=4 green ring vertices per fringe seam cell) also draws from anchored Z values → fringe seam cell Z == fringe interior Z == anchor_value at the interface.

**Continuity result:** fringe Z = green seam Z = anchor_value at the interface point. The green surface itself (Z_mm, the gradient field) is not modified — only the fringe and fringe seam vertex Z. The printed interface is continuous from the fringe side; the green side matches via the seam-reseat.

**Why Approach A over B (Gaussian pull):** the existing fringe Z builder already uses a bnd_z IDW — injecting into bnd_z reuses that machinery exactly, without adding a separate Gaussian pass-through. No new code paths, no new constants.

---

## Red → green table

| # | Test | Result |
|---|------|--------|
| T1a | interior marker at centroid → `elevationMarkers` | RED → GREEN |
| T1b | exterior marker far outside → `fringeBoundaryHeights` | RED → GREEN |
| T1c | mixed list split correctly (2 interior, 2 exterior) | RED → GREEN |
| T1d | empty marker list → both lists empty | RED → GREEN |
| T1e | no green polygon → all treated as interior (fallback) | RED → GREEN |
| T2a | `/api/detect_boundaries` has both `elevationMarkers` and `fringeBoundaryHeights` keys | RED → GREEN |
| T2b | both fields are lists | RED → GREEN |
| T2c | `fringeBoundaryHeights` entries have `{x, y, value}` with float value | RED → GREEN |
| T3  | single exterior anchor at value=8mm → fringe Z ≈ 8mm at boundary (±0.5mm) | RED → GREEN |
| T4  | fringe seam Z ≈ anchor value at boundary interface (±0.5mm) | RED → GREEN |
| T5  | fringe seam Z vs anchor_value gap < 0.5mm (continuity) | RED → GREEN |
| T6  | same input → same anchored surface (reproducibility) | GREEN (trivially before, still GREEN) |
| T7a | interior spikes still produce Gaussian bumps with empty anchors | GREEN (regression) |
| T7b | absent `fringeBoundaryHeights` key == empty list (backward compat) | GREEN (regression) |

**Full suite: 299 passed, 0 failures.**

---

## Test drive for Thomas

1. **Create New Project** from DeLaveaga H5 (new project flow, not Open-Project on a hand-tuned EGM — boundary-classifier tuning phase rule).
2. Hit **Detect Boundaries**.
   - Interior numbers (slope values scattered across the green) appear in the **OCR Elevation Spikes** panel on the left — same as before.
   - Exterior numbers (on the black outline) do **not** appear in that panel; they are stored silently as `fringeBoundaryHeights` in the EGM and consumed by the geometry pipeline.
   - Flash message now reads: `"Detected N region(s) + … + M fringe anchor(s) — scale=…"` if exterior markers were found.
3. Check the browser console: `[runDetection] OCR fringe boundary heights: N [...]` with the exterior anchor data.
4. **Generate** → fringe rim at each exterior-marker position should rise to the detected mm value, creating visible elevation at the fringe/green boundary wherever the heat map labeled an exterior number.

---

## Version bumps

| File | Before | After |
|------|--------|-------|
| `app/app.py` `APP_VERSION` | v4.80 | v4.81 |
| `app/gradient_surface_diagnostic.py` | v0.09 | v0.10 |

---

## Follow-up: DeLaveaga H5 interior recall (deferred)

Thomas noted some interior numbers on DeLaveaga H5 were not detected. Not scoped to this task. After this ships, run the OCR diagnostic against DeLaveaga H5 and compare detected vs ground-truth interior markers to identify which values the OCR misses. File as a separate task when ready to chase.

---

## Files changed

- `app/app.py` — added `classify_ocr_markers()`, updated `detect_boundaries()`, APP_VERSION v4.81
- `app/gradient_surface_diagnostic.py` — injected fringe boundary anchors into `bnd_z` and `g_bdry_arr` in `build_fringe_mesh`, version v0.10
- `app/templates/editor.html` — `fringeBoundaryHeights` state, `runDetection`, `autoSave`, `loadProject`, `startNewProject`
- `app/tests/test_fringe_boundary_anchors.py` — 14 new tests (new file)
