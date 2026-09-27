# Boundary Editor — Clamp Points to Image Frame
## v1.0  ·  Sienna  ·  2026-09-27

---

## Where the auto-analysis lives

Auto-analysis code lives entirely in **`app/app.py`** — the Flask route `detect_boundaries()` at line ~1205 (post-edit). It:

1. Reads the image with OpenCV, computes HSV masks for green / trap / water.
2. Calls `mask_to_polygon(mask, num_points)` (inner function) to extract the largest contour and resample it to N evenly-spaced points.
3. Assembles a `polygons` list and returns JSON.

No analysis code lives in `plate_text.py` (that file is strictly 3MF/text mesh generation).

---

## Clamp function + integration point

Two new module-level helpers added to `app/app.py` just before the `detect_boundaries` route:

```python
def _clamp_point_to_image(x, y, w, h):
    return (max(0.0, min(float(w), float(x))),
            max(0.0, min(float(h), float(y))))

def _clamp_polygon_points(points, w, h):
    # → (list_of_clamped_points, clamp_count)
```

**Integration in `detect_boundaries`:** After the green/trap/water polygon lists are assembled (but before the JSON response is built), a loop iterates every polygon and calls `_clamp_polygon_points()`. If any point was clamped, a `print()` log line fires so it shows up in the server console.

---

## Load-time healing design + toast message text

**Route:** `load_boundaries()` in `app/app.py`.

When the EGM has `imageSize: {width, height}` stored, the server now iterates every polygon's points, clamps them with `_clamp_polygon_points()`, and adds `off_frame_count` to the JSON response.

**Client-side (editor.html `loadProject()`):**

```js
const off_frame_count = data.off_frame_count || 0;
let clampCount = off_frame_count;   // server-counted heals
```

Plus a JS belt-and-suspenders clamp (for legacy EGMs that lack `imageSize`) using `data.imageSize` if present.

**Toast message text** (shown when `clampCount > 0`, duration 7 s):

> Clamped N off-frame point(s) to the image edge — Course — Hole X

**Dirty flag:** `this._pendingAutoSave = true` is set when `clampCount > 0`. This causes the existing auto-save mechanism to fire once the image finishes loading, writing the healed coordinates back to disk so the file is clean on next open.

---

## Consecutive-dedup rule

After clamping, `_clamp_polygon_points()` walks the clamped list and removes any point that is identical to the immediately preceding point. This prevents zero-length polygon edges when, e.g., two adjacent vertices both snap to corner `(w, h)`. Non-adjacent identical points (same corner, non-consecutive) are kept to preserve polygon topology.

---

## Red → Green table

| Test | Class | What it covers | RED → GREEN |
|------|-------|----------------|-------------|
| T1a | `TestClampPointToImage` | x > w clamped to w | ✅ |
| T1b | `TestClampPointToImage` | y > h clamped to h | ✅ |
| T1c | `TestClampPointToImage` | y < 0 clamped to 0 | ✅ |
| T1d | `TestClampPointToImage` | x < 0 clamped to 0 | ✅ |
| T1e | `TestClampPointToImage` | Both axes outside → both clamped | ✅ |
| T1f | `TestClampPointToImage` | Inside point unchanged | ✅ |
| T1g | `TestClampPointToImage` | Boundary point (x=w, y=h) unchanged | ✅ |
| T1h | `TestClampPointToImage` | Returns floats | ✅ |
| T2a | `TestClampPolygonPoints` | Off-frame point in list clamped | ✅ |
| T2b | `TestClampPolygonPoints` | In-frame points unchanged | ✅ |
| T2c | `TestClampPolygonPoints` | Consecutive corner-dupes removed | ✅ |
| T2d | `TestClampPolygonPoints` | Non-consecutive dupes kept | ✅ |
| T2e | `TestClampPolygonPoints` | Returns (list, count) tuple | ✅ |
| T3  | `TestDetectBoundariesClamp` | detect_boundaries response: no out-of-frame points | ✅ |
| T4a | `TestLoadBoundariesOffFrameCount` | load returns `off_frame_count` key | ✅ |
| T4b | `TestLoadBoundariesOffFrameCount` | Returned polygons have clamped coords | ✅ |
| T5  | `TestLoadBoundariesCleanEGM` | Clean EGM: `off_frame_count == 0` | ✅ |
| T6a | `TestLoadProjectJsHealing` | JS reads `data.off_frame_count` | ✅ |
| T6b | `TestLoadProjectJsHealing` | JS applies Math.min/max clamp | ✅ |
| T7  | `TestLoadProjectJsHealing` | `_pendingAutoSave` set when clamped | ✅ |
| T8  | `TestLoadProjectJsHealing` | Toast shown conditional on clampCount > 0 | ✅ |

**Full suite:** 210 passed, 0 failed, 0 regressions (was 189 before this task).

---

## Manual verify for Thomas

1. Start the web server on port 5051 (or run `~/.local/bin/start_web_servers.sh`).
2. Open the Boundary Editor → **Open Project** → select **Stanford (Hole 08).egm**.
3. You should see a green toast in the top-right corner:
   > **Clamped N off-frame points to the image edge — Stanford — Hole 8**
4. The previously-stuck control points are now snapped to the nearest frame edge and are fully grabbable via drag.
5. The project is automatically queued for save (the "unsaved" amber badge will briefly appear); once the image loads the fix is written to disk.
6. Re-open the file — the toast should **not** appear this time (`off_frame_count` = 0 since the bad coords were overwritten).

---

## APP_VERSION

Bumped `v4.70 → v4.71` in `app/app.py`. The footer on every page (including the Boundary Editor) shows the new version via the `app_version` context processor — no separate template string to update.

---

## Files changed

- `/Volumes/GIT/CLAUDE/SHARED_WORK_FOLDER/app/app.py` — `APP_VERSION` bump; `_clamp_point_to_image()` and `_clamp_polygon_points()` helpers; clamp loop in `detect_boundaries()`; `off_frame_count` in `load_boundaries()`.
- `/Volumes/GIT/CLAUDE/SHARED_WORK_FOLDER/app/templates/editor.html` — `loadProject()` extended with `off_frame_count` handling, JS belt-and-suspenders clamp, dirty-flag set, conditional toast.
- `/Volumes/GIT/CLAUDE/SHARED_WORK_FOLDER/app/tests/test_clamp_points_to_frame.py` — 21 new tests (RED→GREEN).
