# detect_boundaries Diagnostic — Stanford H8 5396

**v1** · Sienna · 2026-09-28

---

## Image Inventory

**File:** `ItWentIn/GolfCourses/Stanford/Images/Stanford (hole 8, 5396).png`
**Size:** 815 × 1227 px

### What is visually present

| Feature | Location | Notes |
|---|---|---|
| Green egg (slope map) | Center–upper 80% of image | Full-image filling colored gradient oval; hue shifts from yellow-green (top) through teal to blue (bottom-right edge) |
| Slope arrows | Scattered throughout green | Dark blue/cyan arrows pointing downhill; H=100-105, S=255, V~89 — very dark, high-saturation |
| Numeric markers (0.6 / 1.4 / 1.7 / 2.1 / 2.2 / 2.6 / 2.7 / 2.8 / 2.9 / 3.0 / 3.8 / 4.3 / 5.4) | Various positions inside green | White text labels for gradient values |
| Distance rings (5–30) | Inside/around green center | Light circular overlays |
| Beige/tan region on left | x=[0–120], y=[660–1100] approx | RGB≈(240,226,216); HSV H=13, S=26, V=240. Very subtle warm tint — almost white-gray. Not a true beige; saturation is only 26. |
| Light-cyan region on bottom-right | x=[600–815], y=[950–1227] approx | RGB≈(211,238,238); HSV H=90, S=29, V=238. Nearly white, extremely low saturation. |
| © 2026 StrackaLine watermark | Bottom area | Light text |
| Light-cyan arc (Water 1) | x=[208–548], y=[817–955] | H=100–115, S=130–170, V=170–220. Represents a cyan-colored slope band at the lower left of the green visualization. |
| Small blue patch (Water 2) | x=[701–738], y=[547–626] | H=100–104, S=135–155, V=185–195. A small blue region on the right interior side of the green. |

---

## Ground Truth (from EGM)

File: `ItWentIn/GolfCourses/Stanford/EGMs/Stanford (Hole 8, 5396).egm`
(Alternate `Stanford (Hole 8, 5396, A).egm` is identical — same 3 polygons.)

| Polygon | Type | Points | Bbox (x, y, w×h) | Notes |
|---|---|---|---|---|
| Green | green | 8 | (72, 0, 691×955) | Covers essentially the full image width from y=0 (top edge) to y=955 |
| Water 1 | water | 16 | (208, 817, 340×138) | Lower-left arc at y=[817–955] — the light-cyan pool region |
| Water 2 | water | 16 | (701, 547, 37×79) | Right-side interior blue patch at y=[547–626] |

**No fringe, trap, or contour polygons in the EGM.**

Note on naming: Thomas calls these polygons "Water" for rendering purposes (the EGM pipeline uses a water-type polygon to apply a water visual effect). They correspond to the cyan/blue slope-color bands in the StrackaLine image, not actual water hazards on the golf course.

---

## detect_boundaries Output

Called directly on `Stanford (hole 8, 5396).png` with the algorithm from `app/app.py` lines 1233–1615.

| Polygon | Type | Points | Bbox (x, y, w×h) | Raw mask area |
|---|---|---|---|---|
| Green | green | 8 | (72, 0, 691×955) | 513,237 px |
| Water 1 | water | 16 | (208, 817, 340×134) | 28,438 px |
| Water 2 | water | 16 | (701, 547, 37×79) | 1,575 px |

**Mask pixel counts:**
- `green_mask`: 513,237 px (51.3% of image)
- `trap_mask`: 0 px
- `water_mask`: 30,013 px total (2 components, both ≥500 px threshold)

**Green polygon precision:** All 8 detected control points match ground truth exactly — pixel-perfect agreement.

**Water polygon precision:** Water 1 bbox is (208, 817, 340×134) vs GT (208, 817, 340×138) — 4px height difference, negligible. Water 2 bbox is identical to GT.

### HSV key observations

| Location | H | S | V | Interpretation |
|---|---|---|---|---|
| Water 1 center (380, 880) | 104 | 255 | 100 | Dark arrow pixel — V=100 < threshold (130), not counted |
| Water 1 body (360, 860) | 101 | 151 | 192 | Passes water filter (H=100–130, S≥130, V=130–220) |
| Water 2 center (720, 585) | 98 | 152 | 183 | H=98 is just below water range (needs ≥100) — not individually matched but region detected after morphology |
| Green center (400, 450) | 76 | 228 | 201 | Pure green hue, high saturation — drives green detection |
| Beige left (25, 700) | 13 | 26 | 240 | H=13 is below trap range (15–34); S=26 is in range but H misses — no trap detection |
| Bottom-right cyan (750, 1100) | 90 | 29 | 238 | S=29 << 130 water threshold — never detected as water |
| Slope arrow (450, 600) | 105 | 255 | 89 | V=89 < 130 — excluded from water mask correctly |

---

## Deltas

### False Positives (detected where Thomas drew nothing)
**None.** Every detected polygon corresponds to a ground-truth polygon.

### False Negatives (missed real features)
**None.** All 3 GT polygons (1 green + 2 water) are detected.

### Mislabels (right location, wrong type)
**None** for this image. However, note:

- The two "Water" polygons are actually the blue slope-color bands inside the StrackaLine green visualization, not actual golf-course water hazards. Thomas intentionally labeled them as Water for the rendering effect. The detector finds them by the same HSV criterion. This is a correct match by label, even if the real-world interpretation is "slope color" not "water hazard."

### Known-issue check: water false-positives from internal gradient

The brief flags this as a prior known issue. On this image:

- The slope arrow pixels have H=100–105, S=255, V=89. The V=89 < 130 threshold **excludes** all slope arrows from the water mask — the V≥130 gate is doing its job.
- There are 1,012 raw water-range pixels scattered inside the green above y=800. After morphology + 500px area filter, these do **not** form an extra spurious polygon — the only upper-green component that passes the filter is Water 2 (area=1,575), which is a true positive.
- **Conclusion:** The internal-gradient false-positive issue is not active on this specific StrackaLine image under current thresholds.

### Why no trap is detected

The "beige/tan region" at the left side of the image measures H=13, S=26, V=240 (RGB ≈ 240,226,216). The trap filter requires H in [15, 34]. H=13 is 2 units below the lower bound — the tan background is excluded. The region also has only S=26, which barely enters the S≥15 window but doesn't form any blob after morphology (no area ≥500).

There are **zero trap pixels** across the entire image.

### Why the light-cyan bottom-right is not detected as water

The bottom-right StrackaLine background has H=90, S=29, V=238. The water filter requires S≥130. S=29 is 4.5× below threshold. This region never enters the water mask.

---

## Recommended Next Steps

Thomas should pick one of these approaches before the next classifier work session. These are options, not prescriptions.

### Option 1 — Leave it as-is (no action)

**Summary:** For this specific image, the detector achieves pixel-perfect polygon accuracy. Nothing is broken.

**Pro:** Zero engineering effort. Already works.

**Con:** This performance is specific to Stanford H8 with the current StrackaLine color palette. A different StrackaLine image with a differently-colored slope map (or a Golf Intelligence image) may expose the water false-positive issue that the brief describes.

**When to choose:** If the next images to process are all StrackaLine images similar to this one.

---

### Option 2 — Add a Green-Interior Exclusion zone for the water filter

**Summary:** After detecting the green polygon, subtract a shrunk version of the green mask from the water candidate region. Only allow water detections in areas that lie outside (or on the very edge of) the green boundary.

**Pro:** Directly prevents the internal-gradient false-positive pattern even if it does emerge on another image. Low surgical change — one `cv2.erode` call and a mask subtraction.

**Con:** This image has Thomas's Water polygons **inside** the green boundary. Applying this exclusion would cause false negatives on those real detections. It would only be safe if the water filter were split: one pass for external water (outside green), one pass for interior cyan blobs.

**When to choose:** When moving to Golf Intelligence images where the internal shading false-positives are confirmed to be a real problem.

---

### Option 3 — Separate StrackaLine vs. Golf Intelligence classifier path

**Summary:** Detect which image source is being processed (file name contains "5396" or course folder is StrackaLine-origin vs. Golf Intelligence) and apply different HSV thresholds or polygon-type logic per source.

**Pro:** Cleanest long-term solution. Each source gets tuned thresholds. No awkward compromises.

**Con:** Requires classifying the image source at detection time. Adds branching complexity. The file-naming convention ("5396" in StrackaLine filenames) is currently implicit, not a metadata field.

**When to choose:** When Golf Intelligence images are being run through the same pipeline and confirmed to produce different false-positive patterns.

---

### Option 4 — Add a minimum-eccentricity filter for water polygons

**Summary:** Real water hazards tend to be large, irregular blobs. The interior-gradient false-positives (when they occur) tend to be small, elongated stripes. Add an area-weighted shape filter: discard any water component whose bounding-box aspect ratio is > 5:1 or whose area is < 1,000 px.

**Pro:** Simple numeric filter, no geometric masking needed. Would catch thin gradient-stripe false-positives.

**Con:** Water 2 on this image has area=1,575 px and bbox 37×79 (aspect ~2:1). It just barely passes. A tighter threshold might incorrectly eliminate it. Also doesn't address the fundamental issue — it's a heuristic, not a principled fix.

**When to choose:** As a cheap first line of defense before committing to Option 2 or 3.

---

## Deliverable

- Overlay PNG: `owner_inbox/detect_boundaries_stanford_h8_5396_2026-09-28.png`
  - Solid outlines = detected polygons (green=bright green, water=cyan)
  - Dashed outlines = ground-truth EGM polygons (green=neon green, water=gold)
  - Legend and title bar included, version badge v1 in upper-left
- This report: `owner_inbox/detect_boundaries_stanford_h8_5396_diagnostic_2026-09-28.md`
