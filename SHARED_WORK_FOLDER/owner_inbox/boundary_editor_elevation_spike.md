# Add Elevation Spike — Boundary Editor (task 657)

**Version bumped:** `v4.10` → **`v4.11`** (footer badge on every main-app page — reload confirmation cue).

## Where the button lives

New toolbar button **"Add Elevation Spike"** sits in the below-canvas action cluster, immediately after **Add Water**, matching the Add Trap / Add Water button pattern exactly:

- Same component: `<button @click="addElevationSpike()" :disabled="!imgLoaded" …>`
- Same size / padding / rounded-md corners
- Same enabled/disabled visual treatment
- Warm-orange fill (`bg-orange-500` / `hover:bg-orange-600`) — distinct from Trap red and Water yellow but stays inside the warm palette
- Tooltip explains what happens and how the ▲/▼ controls work — obvious to Jim on first sight

## Rectangle visual treatment + drag behavior

Each spike renders as an absolutely-positioned HTML overlay inside the canvas container (the canvas itself is a raster surface — interactive rectangles live in the DOM alongside it, positioned via `scale/offsetX/offsetY` so they track the image as the canvas resizes).

Anatomy, left-to-right:
1. **`E` glyph badge** — warm-tan `#F5C77E` background, dark-tan text `#7A4A15`, tells you at a glance it's an Elevation spike (not a trap vertex, not a boulder)
2. **Numeric mm value** — 14px system-font body text with tabular numerals, always formatted `X.X mm`
3. **▲ / ▼ counter buttons** — stacked, each click adjusts by exactly `0.1 mm`, hover fills warm-orange, clamped to `[-50, +50] mm` so a stuck button can't run away
4. **`×` remove button** — warm-red on hover; matches the destructive-action colour used elsewhere

Palette: background `#FFF7ED` (warm-neutral), border `#B8763A` (warm brown), soft shadow, 180ms ease-in-out transitions per Sienna's design principles. No bounce, no flash.

**Drag** uses native pointer events on the overlay itself (not the canvas mousedown pipeline, which is polygon-vertex-specific). Pointerdown on the row starts drag; the ▲/▼/× buttons `.stop` propagation so they don't trigger drag. Movement is clamped inside the fringe-expanded zone (`[-fringePadPx, imgW+fringePadPx]` and same on Y) so a spike can be placed anywhere on the fringe or the green but can't wander off the printable area. `autoSave()` fires only if the pointer actually moved (so a click-through on a button doesn't spam the save endpoint).

## Data shape

Persisted at the **top level** of the `.egm` file (peer to `polygons`, `elevationRange`, etc.), so the backend needed **zero changes** — `save_boundaries` already `json.dump`s the whole client payload.

```json
{
  "elevationSpikes": [
    { "x": 123.45, "y": -50.0, "mm": 14.5 },
    { "x": 600.0,  "y": 200.0, "mm": 7.3 }
  ]
}
```

- `x`, `y` — image-pixel coordinates (float, 2-decimal rounded). Same coordinate system as polygon vertices. `y` can be negative when the spike sits above the image, inside the fringe padding zone.
- `mm` — wanted fringe elevation at that point, mm above base, 1-decimal rounded. Initial value = the current **Elevation range (mm)** setting on the page at click-time (per spec).

**In-app state:** `elevationSpikes: []` on the `polygonEditor()` Alpine component. Reset to `[]` in `startNewProject()`; restored from `data.elevationSpikes` in `loadProject()` (defaults to `[]` when loading a legacy `.egm` that predates spikes — no migration needed).

**Spawn location:** near the top edge of the fringe padding zone (`y = -fringePadPx * 0.5`), horizontally centered with a 30px horizontal stagger per additional spike so they don't stack on top of each other. Lands visibly "on the fringe area" per Thomas's spec, immediately draggable.

## What is intentionally NOT done yet (the smoothing integration)

Per Thomas's "let's try and get that one working first" — the geometry pipeline (Topo's territory) is untouched. `generate_flat_pieces*.py` and `hole9_boundaries.py` were not modified.

**The exact hook Topo will need next** — inside the `.egm` payload consumed by the pipeline, spikes are already present as:

```python
data["elevationSpikes"]  # list[dict] with keys: x (float px), y (float px), mm (float)
```

Topo's follow-up will read that list and drive fringe-height interpolation (probably RBF or IDW) so the fringe surface targets each spike's `mm` value at each `(x, y)` in image-pixel space, then falls back to the current uniform `fringeEdgeHeight` where no spike is nearby. Coord system matches the polygon vertex convention already in use — image-pixel origin at top-left, `+x` right, `+y` down.

## Smoke verification (against a temp DB — live DB untouched)

Ran `/tmp/test_elevation_spike_657.py` with `DB_PATH` and `_EGM_BASE` both monkey-patched to a temp dir before creating the test client:

- **[1/3]** `GET /editor` returns the new button, click handler, state field, `spikeBump` method, and version string `v4.11` — **PASS**
- **[2/3]** `POST /api/boundaries` persists a payload with 2 spikes to a `.egm` in the temp EGM tree (verified path prefix) — **PASS**
- **[3/3]** `GET /api/boundaries/load` round-trips both spikes with exact `x/y/mm` values intact — **PASS**

Neither the real `db/workspace.db` nor any real `ItWentIn/GolfCourses/*/EGMs/` folder was touched.

## Surprises

None significant. Two small notes:

1. **Canvas ≠ interactive.** The editor's canvas is a raster surface; polygon vertices are drawn as pixels and hit-tested by cursor position, not real DOM. I therefore built the spike as an **HTML overlay** absolutely positioned over the canvas, rather than extending the polygon drawing pipeline. This keeps the ▲/▼/× controls trivially interactive and preserves the entire existing polygon draw/hit-test path unchanged.
2. **Save payloads live in two places.** Both `autoSave()` and `generateSTL()` build the outbound payload — they had identical field lists except for `open_in_slicer`, so my one-shot `replace_all` hit only the first. I explicitly edited both so spikes reach the pipeline when Generate is clicked, not just when the editor auto-saves.

---

## v4.12 fix (task 659) — "I don't see a rectangle to drag around"

**Version bumped:** `v4.11` → **`v4.12`**.

### What was actually wrong

The toast fired and the state mutated correctly — the spike *was* being added and rendered. But it rendered **outside the visible area** and got clipped by the canvas container's `overflow-hidden`.

The overlay is HTML positioned inside the canvas container. Its CSS-Y is `imgY * scale + offsetY`, where `offsetY = fringePadY * scale`. So a rendered spike is visible only when `imgY ∈ [-fringePadY, imgH + fringePadY]`.

My v4.11 spawn used the single `fringePadPx = max(fringePadX, fringePadY)` on the Y axis and set `spawnImgY = -fringePadPx * 0.5` unconditionally. Two problems compounded:

1. **`fringePadX` and `fringePadY` differ per image aspect ratio** — using the max value on the Y axis is only correct for square images. On landscape it over-shoots down; on portrait it over-shoots up.
2. **`fringeXyExpansionMm` is currently negative (`-1.057`)**, so the fringe half-extent (`~85.2 mm`) is *smaller* than `printSize/2` (`85.7 mm`). For portrait golf-hole photos (the norm — PGA Palmer 1074×1197, DeLaveaga 1179×1329), `fringePadY` collapses to **0**. That means there is *no fringe pad above the image* — the visible fringe-Y zone is entirely within `[0, imgH]`. Any negative spawn Y renders above the canvas container top edge, and `overflow-hidden` cuts it off. Invisible rectangle.

### The minimal fix

Two small changes in `app/templates/editor.html`:

1. **Store per-axis pads** alongside the existing `fringePadPx`: `fringePadXpx = fringePadX`, `fringePadYpx = fringePadY`. `fringePadPx` (the max) is preserved because the polygon-vertex clamp still uses it — polygons are drawn on the canvas raster, which extends to the max fringe pad on both axes, so that clamp is not the bug.
2. **Spawn Y is now conditional on `fringePadYpx`**:
   - `fringePadYpx > 0` (there's fringe above the image on Y): spawn at `-fringePadYpx * 0.5` (in the pad, same intent as before).
   - `fringePadYpx == 0` (portrait / no Y-axis fringe pad, the common Thomas case): spawn at `imgH * 0.05` (just inside the top of the image, on the fringe/green edge), so the box is immediately visible.
3. **Drag clamp** switched from `±fringePadPx` on both axes to `±fringePadXpx` on X and `±fringePadYpx` on Y — otherwise the user could drag a well-spawned spike back out into the clipped zone.

Verified spawn CSS-Y across the four cardinal aspect ratios (portrait / landscape / two real Thomas images): all now land at a positive CSS-Y comfortably inside the container. Also verified with an 11-assertion temp-DB `test_client()` sweep that renders `/editor`, checks the version bump, both per-axis pad declarations, the resize assignments, the new spawn/drag expressions, and confirms the polygon-vertex clamp is unchanged. Live DB and real EGM tree untouched.

### Honest post-mortem

This is a bug I should have caught in v4.11. I built the spawn math assuming a symmetric fringe pad (single `fringePadPx`), but the fringe zone is inherently per-axis on non-square images, and my chosen HTML-overlay rendering pattern makes that asymmetry matter (unlike the raster canvas, which absorbs it via the expanded-canvas dimensions). The v4.11 smoke test I ran verified the template block renders and round-trips through save/load — it never verified that a freshly-spawned spike actually lands at a visible CSS-Y on a real portrait image. That's the check I should have written.

*Fix delivered by Sienna, Full-Stack Application Developer. Persona at `team/sienna.md`.*
