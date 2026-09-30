# Remove Load-Time Off-Frame Clamp — v4.83
**v4.83** · Sienna · 2026-09-30

---

## What was removed and why

Thomas intentionally places control points **outside the PNG image frame** — for example, to anchor a boundary that extends beyond the visible aerial photo. These placements were surviving correctly in the EGM file on disk, but every time a project was closed and reopened, the load path was silently snapping those points back to the image edge. The user's intended geometry was destroyed on reload.

**Two components removed:**

1. **Python — `load_boundaries()` in `app/app.py`**: A block that read `imageSize` from the EGM, called `_clamp_polygon_points()` on every loaded polygon, logged healed points, and returned `off_frame_count` in the response. All of this is gone. The route now returns polygon coords exactly as stored in the EGM.

2. **JavaScript — `loadProject()` in `app/templates/editor.html`**: A "belt-and-suspenders" block that read `data.off_frame_count`, defined a `clampPt()` function, mapped it over every polygon's points, showed a "Clamped N off-frame points to the image edge" toast, and set `_pendingAutoSave = true` (which would trigger an autosave that persisted the clamped — incorrect — coordinates). All removed.

---

## What was preserved

**Generation-time clamp — unchanged.** When `detect_boundaries` runs computer-vision analysis to auto-generate polygon suggestions, it still clamps all output points to `[0, w] × [0, h]`. This is correct: auto-generated polygons should start inside the frame; the user can then drag individual control points outside intentionally. The helpers `_clamp_point_to_image()` and `_clamp_polygon_points()` remain in `app.py` and continue to serve this path.

---

## Files changed

| File | Change |
|---|---|
| `app/app.py` | `APP_VERSION` v4.82 → v4.83; removed load-time clamp block from `load_boundaries()` |
| `app/templates/editor.html` | Removed JS clamp block, `clampPt` function, off-frame toast, and `_pendingAutoSave = true` from `loadProject()`; added v4.83 comment |
| `app/tests/test_clamp_points_to_frame.py` | Updated T4–T8 to match new no-clamp contract (old tests for the removed behavior replaced) |
| `app/tests/test_remove_load_time_clamp.py` | New — 11 tests covering the removal (NL1–NL7) |

---

## Red → Green table

| # | Test | File | Description | Result |
|---|---|---|---|---|
| NL1a | `test_offframe_y_preserved` | `test_remove_load_time_clamp.py` | y = image_height + 100 survives load | RED → GREEN |
| NL1b | `test_offframe_negative_x_preserved` | `test_remove_load_time_clamp.py` | x = -50 (left of frame) survives load | RED → GREEN |
| NL1c | `test_inframe_points_also_preserved` | `test_remove_load_time_clamp.py` | In-frame points unchanged | GREEN (regression guard) |
| NL2 | `test_no_offframe_count_or_zero` | `test_remove_load_time_clamp.py` | off_frame_count absent or 0 | RED → GREEN |
| NL3a | `test_loads_without_error` | `test_remove_load_time_clamp.py` | Legacy EGM (no imageSize) loads OK | GREEN (regression guard) |
| NL3b | `test_offframe_coords_preserved_without_imagesize` | `test_remove_load_time_clamp.py` | Off-frame coords preserved in legacy EGM | RED → GREEN |
| NL4 | `test_generated_points_within_bounds` | `test_remove_load_time_clamp.py` | detect_boundaries still clamps gen-time | GREEN (regression guard) |
| NL5a | `test_no_clamppt_function_in_load_project` | `test_remove_load_time_clamp.py` | No clampPt in loadProject JS | RED → GREEN |
| NL5b | `test_no_clamp_math_on_loaded_poly_points` | `test_remove_load_time_clamp.py` | No poly.points.map(clamp…) in loadProject | RED → GREEN |
| NL6 | `test_no_pending_autosave_from_offframe_block` | `test_remove_load_time_clamp.py` | No _pendingAutoSave from off-frame path | RED → GREEN |
| NL7 | `test_no_clamped_offframe_toast` | `test_remove_load_time_clamp.py` | No "Clamped N off-frame" toast | RED → GREEN |

Full suite: **319/319 passed** after changes.

---

## Test drive

1. Open the Boundary Editor and load any project.
2. Drag a control point outside the image frame — past the white PNG boundary.
3. Observe the point is accepted at its off-frame position. The canvas may need to be scrolled/zoomed to see it; the control point dot will be visible at the fringe if close to the edge.
4. **Close the project** (open a different project, or reload the page).
5. **Reopen the original project.**
6. The control point is still at its off-frame position — no toast, no autosave, no snap-back.

---

## Follow-up worth flagging

If a user places a control point far outside the image frame, it may scroll off the visible canvas area and become unreachable via normal mouse interaction. The current canvas pan/zoom should allow reaching points a short distance outside the frame (the fringe zone), but very distant placements could require a "snap to frame" or "find off-frame points" UX affordance. This is a separate reachability task — not addressed here.
