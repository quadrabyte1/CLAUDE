# Stanford Hole 8 EGM

**Stanford Hole 8 EGM v0.1 — 2026-09-18 — Topo**

---

## What was built

A GPS-derived EGM (Elite Golf Moments plaque file) for Stanford Golf Course, Hole 8, generated entirely from the geohash GPS point cloud — no hand-drawn contour image required. This is the first EGM in the Stanford folder that derives its green polygon shape directly from measured GPS coordinates rather than a manually traced image overlay.

---

## Green isolation criterion

**Criterion used:** All GPS points in the easternmost **50 m** of the fairway corridor whose altitude is below **41.0 m ASL**.

This captures 104 of the 351 points. They form a ~49 m east-west × ~48 m north-south region at the low end of the hole, with an altitude range of 35.92 – 40.09 m (4.17 m spread). The topological signature — a flat, low-elevation cluster at the terminal east end of a ~216 m fairway corridor — is the standard GPS pattern for a par-4 green approach when using geohash-grid data.

**How Thomas can override:**

Open `owner_inbox/stanford_egm_pipeline.py` and change the two constants near the top:

```python
GREEN_EAST_WINDOW_M = 50.0    # metres back from the east edge to include
GREEN_ALT_CEILING_M = 41.0    # altitude ceiling to exclude fairway shoulder rise
```

Reducing `GREEN_EAST_WINDOW_M` to 35–40 m tightens the polygon around the most likely green surface (eliminating the outer approach cells). Lowering `GREEN_ALT_CEILING_M` to 39.5 m excludes the slight shoulder rise on the east perimeter. Re-running the script regenerates all deliverables.

---

## Topological interpretation

The green occupies an **oblong northeast-tilted area** — wider east-west (49 m) than the north-south dimension of the fairway corridor (48 m). The convex hull polygon has 8 vertices, describing a roughly diamond-to-oval shape consistent with a large approach green on a downhill par 4.

**Green slope:** The altitude rises from west to east across the green surface:

- West edge of green cluster: ~35.9 – 37.5 m ASL (low end, where the fairway leads in)
- East edge: ~39.7 – 40.1 m ASL (slightly elevated back edge)
- South edge (lat ~37.4236): ~37 – 38.3 m ASL
- North edge (lat ~37.4241): ~39.4 – 39.9 m ASL

This means the green slopes **up from front-left (SW) to back-right (NE)** by approximately 2–4 m across its surface — a classic front-to-back slope that feeds approach shots toward the center. At real scale this is a ~4% grade, subtle but meaningful for a putting surface.

The plaque contour map shows this clearly: the lighter green tones (higher) concentrate in the north-east quadrant of the green image; darker tones (lower) sit in the southwest.

---

## Render rules applied

| Rule | Applied how |
|------|-------------|
| Green never capped | `applyFringeFrameCap: true` + `fringeEdgeHeight: 9` — the cap applies only to fringe/trap polygons within ~1 mm of the frame edge; the green polygon itself is uncapped |
| Fringe 9 mm cap | `fringeEdgeHeight: 9` set in EGM params |
| 2 mm base thickness | `baseThicknessMm: 2.0` (safe default for this non-water hole) |
| Plaque 3-line shift | `flagOffsetXMm: 0, flagOffsetYMm: 0` — to be dialed in by Thomas in the EGM editor after a first print; no physical flag position data in the GPS export |
| Water-hole rule | Not triggered — Hole 8 has no water feature in the GPS data |

---

## Deliverables

| File | Description |
|------|-------------|
| `ItWentIn/GolfCourses/Stanford/EGMs/Stanford (Hole 8).egm` | GPS-derived EGM — green polygon from convex hull of 104-point cluster |
| `ItWentIn/GolfCourses/Stanford/Images/Stanford (Hole 8) plaque preview.png` | Top-down contour-filled heightmap of the green region; 8-vertex boundary overlaid |
| `ItWentIn/GolfCourses/Stanford/Images/Stanford (Hole 8) tee-to-green context.png` | Full-hole 3D surface render showing the elevated tee and the fairway descent to the green |
| `owner_inbox/stanford_egm_pipeline.py` | Reproducible pipeline (v0.1) — GPS parse → green isolation → polygon → EGM → PNG renders |
| `owner_inbox/stanford_gps_3d_pipeline.py` | Unchanged v0.1 visualization pipeline from the prior handoff |

`serial.json` was not modified — it tracks 3MF serial numbers only, and no 3MF was generated.

---

## Plaque preview vs tee-to-green context

**Plaque preview (`Stanford (Hole 8) plaque preview.png`):**
Top-down, 7:10 aspect ratio, dark green background. Shows a contour-filled heightmap of the isolated 104-point green cluster with 28 elevation bands in YlGn colormap. White dashed line is the convex hull boundary — the shape that will feed the EGM renderer. GPS sample points are overlaid as scatter dots colored by altitude. Reads like a classic EGM plaque card: you can see the front-to-back slope from the contour spacing.

**Tee-to-green context (`Stanford (Hole 8) tee-to-green context.png`):**
Wide 3D surface render (16:9) of the full 351-point hole, x6 vertical exaggeration. The orange triangle markers in the upper-left region are the 10 elevated tee points (55–72 m ASL) — the spike of the hill is unmistakable. The teal circle markers at the far east (right-front of the render) are the green cluster at 36–40 m ASL. The fairway body (341 points in terrain colormap) connects them in a smooth 155 m descent. The tee-to-green drop is ~23 m mean-to-mean (37 m peak-to-floor), a visually striking elevation relationship for a printed plaque. The text callout in the upper-right corner of the image calls this out explicitly: "Tee-to-green drop: ~23 m over ~155 m horizontal."

---

## Caveats

1. **No labeled green boundary.** The GPS export is a geohash grid over the hole area — every cell covers ~5 m × 5 m and carries a single altitude sample. There is no explicit "this cell is on the green" flag. The 50 m east / 41 m ceiling criterion is topologically motivated but not ground-truth validated.

2. **Convex hull overestimates the green.** A real Stanford Hole 8 green is not a perfect convex polygon. The convex hull (8 vertices) will extend slightly into fringe and approach areas on corners. If Thomas loads this EGM in the editor and compares against the course photo, he may want to nudge 2–3 vertices inward, particularly at the south-west entry point.

3. **No trap polygon.** The geohash resolution (~5 m) cannot reliably distinguish a greenside bunker from the adjacent rough in altitude alone — both might read at similar elevations. The existing `Stanford (Hole 08).egm` has a large Trap 1 polygon; Thomas should copy that trap polygon into this file in the EGM editor if the print should include the bunker.

4. **Flag offset is zeroed out.** The GPS data carries no cup/flag position. Set `flagOffsetXMm` / `flagOffsetYMm` after the first print, per normal EGM workflow.

5. **Naming note.** The folder already contains `Stanford (Hole 08).egm` (zero-padded, pre-existing hand-traced EGM) and `Stanford (Hole 888).egm` (test variant). This new file is `Stanford (Hole 8).egm` (no padding) — it is the GPS-derived variant and is distinct from both prior files.

---

## Follow-ups worth considering

1. **Iterate the green polygon.** Run the pipeline with `GREEN_EAST_WINDOW_M = 35` and compare the tighter polygon against a course aerial or green photo. The tighter window is more likely to be pure-green; the 50 m version clips the approach fringe.

2. **Add Trap 1 from the (Hole 08) EGM.** Copy the existing hand-traced bunker polygon into this EGM's `polygons` array. It will render correctly against the GPS-derived green boundary.

3. **Full Stanford 18-hole batch.** If GPS exports exist for other holes, this pipeline accepts any `.gps` file — just change `GPS_FILE` and rerun. The isolation criterion may need per-hole tuning for par-3s (where the tee and green elevation signatures are inverted).

4. **Feed into the plaque-3MF pipeline.** This EGM is ready to hand to Sienna / the slicer workflow. Serial 173 is the next available slot.

5. **Ground-truth validation.** A satellite/aerial image overlay would let Thomas visually confirm the convex hull aligns with the actual green boundary before committing to a print run.

---

*Generated by Topo — 3D Modeling / Computational Geometry Specialist*
