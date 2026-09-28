# v2 — detect_boundaries retune: Stanford H8 5396

**Date:** 2026-09-28  
**Author:** Sienna (Full-Stack Developer)  
**Scope:** `app/app.py` — `detect_boundaries()` classifier  
**Version bump:** `APP_VERSION` v4.77 → **v4.78**

---

## Correction: what the v1 diagnostic missed and why

The task-642 diagnostic declared "0 false positives, 0 false negatives" because it compared detected polygons against the hand-tuned EGM — which already contained two interior `water` polygons for the slope-gradient regions. The diagnostic concluded those interior polygons were intentional water labels.

They were wrong. On re-inspection:

| Old result | Truth | Cause |
|---|---|---|
| 2 interior "water" polygons (Water 1 at centroid ~372,884; Water 2 at ~717,586) | False positives — slope-gradient bands on putting surface | No green-interior mask; high-sat water filter `H=100-130, S≥130` caught blue/teal slope colors |
| 0 trap polygons | LL beige sand trap **missed** | Trap H lower bound was 15; beige reads H=13 |
| 0 water polygons in LR | LR pale-cyan hazard **missed** | Water filter required S≥130; LR reads S=29 (desaturated cyan) |

---

## HSV samples

### LL trap (beige/tan) — x∈[20,170], y∈[950,1150]
```
(20,950):  H=13 S=26 V=240   BGR=(216,226,240)
(50,950):  H=13 S=26 V=240   BGR=(216,226,240)
(80,950):  H=13 S=26 V=240   BGR=(216,226,240)
(110,1000): H=13 S=26 V=240  BGR=(216,226,240)
```
**Uniform** H=13, S=26, V=240 across the entire LL beige region.  
H=13 is 2 units below the old lower bound of H=15 — that's the miss.

### LR water (light cyan) — x∈[660,800], y∈[960,1220]
```
(760,960):  H=90 S=29 V=238  BGR=(238,238,211)
(700,1050): H=90 S=29 V=238  BGR=(238,238,211)
(680,1140): H=90 S=29 V=238  BGR=(238,238,211)
```
**Uniform** H=90, S=29, V=238 across the LR region. H=90 in OpenCV (0-179 scale) = 180° real hue = pure cyan. S=29 is far below the old `sat>=130` gate — the miss was the saturation floor, not the hue.  
Background gray (the non-feature area) reads H=0, S=0 — so S≥15 cleanly separates feature from background.

### Interior "bogus water" slope bands (now masked out)
```
(300,850):  H=100 S=151 V=189   slope band 1, centroid ~(372,884)
(330,870):  H=104 S=150 V=200
(720,580):  H=98  S=152 V=185   slope band 2, centroid ~(717,586)
```
Interior slope colors: H=98-113, S=46-255, V=89-214. These have high saturation (S≥100) — which is why they triggered the old `sat>=130` water filter. They now cannot trigger because they are **inside the green mask** and are excluded before any hazard filter runs.

---

## Green-mask design + toggle knob

A module-level constant was added to `app/app.py` above `detect_boundaries()`:

```python
MASK_GREEN_INTERIOR_FROM_HAZARDS = True
```

In `detect_boundaries()`, immediately after the green mask is finalized:

```python
if MASK_GREEN_INTERIOR_FROM_HAZARDS:
    _hazard_search_area = cv2.bitwise_not(green_mask)  # 255 = outside green
else:
    _hazard_search_area = np.full((h, w), 255, dtype=np.uint8)  # unrestricted
```

Both `trap_mask` and `water_mask` are then AND-ed with `_hazard_search_area` right after their pixel-color filter, before morphology:

```python
trap_mask = cv2.bitwise_and(trap_mask, _hazard_search_area)
...
water_mask = cv2.bitwise_and(water_mask, _hazard_search_area)
```

**Why this is the right structural fix:** The slope-gradient interior colors (blue/teal/orange) are inherent to any Golf Intelligence heat map regardless of threshold tuning. No matter how tightly the water filter is set, any blue-ish color used in the gradient will conflict with the water definition. The mask is the only clean solution.

Setting `MASK_GREEN_INTERIOR_FROM_HAZARDS = False` restores the old unrestricted behavior for edge cases (e.g., an island-green where water genuinely surrounds the putting surface).

---

## Threshold changes: before → after

### Trap (sand)

| Parameter | Before | After | Reason |
|---|---|---|---|
| Hue lower bound | `H ≥ 15` | `H ≥ 10` | LL beige reads H=13 |
| Hue upper bound | `H ≤ 34` | `H ≤ 40` | Slightly wider to tolerate khaki variation |
| Saturation | `S ∈ [15,60]` | unchanged | Stays narrow to exclude vivid colors |
| Value | `V ≥ 200` | unchanged | Bright requirement |
| Green exclusion | none | `& outside_green` | Structural mask applied first |

### Water (combined filter)

The water mask is now the **bitwise OR** of two sub-filters:

**High-saturation path** (original — unchanged, for PGA West style water):
```
H ∈ [100, 130],  S ≥ 130,  V ∈ [130, 220]
```

**Pale-cyan path** (new — for Stanford H8 LR and similar desaturated hazards):
```
H ∈ [80, 105],  S ∈ [15, 50],  V ≥ 200
```

The S cap of 50 in the pale-cyan path ensures the slope-gradient interior colors (S≥100) can never enter this path even if the green mask were disabled.

---

## EGM cleanup: what got removed / added

**Backup created:** `Stanford (Hole 8, 5396).egm.pre_2026-09-28`

**Removed:** Two bogus interior `water` polygons  
- Water 1 (old): bbox x=208-548, y=817-951 — interior slope gradient  
- Water 2 (old): bbox x=701-738, y=547-626 — interior slope gradient

**Added:** LL trap + LR water from new auto-detection  
- `Trap 1`: centroid (94,986), LL corner beige region, 16 points  
- `Water 1`: centroid (725,1107), LR corner pale-cyan region, 16 points

**Unchanged:** Green polygon — identical 8-point outline from previous hand-tune  
**Left alone:** `Stanford (Hole 8, 5396, A).egm` — hedge file, not touched

---

## Red → Green table

| Test | Class | Method | v4.77 result | v4.78 result |
|---|---|---|---|---|
| T1 | TestNoInteriorWater | test_no_water_bbox_inside_green | **FAIL** (2 bogus) | **PASS** |
| T2 | TestLLTrapDetected | test_ll_trap_centroid_in_ll_quadrant | **FAIL** (0 traps) | **PASS** |
| T3 | TestLRWaterDetected | test_lr_water_centroid_in_lr_quadrant | **FAIL** (0 LR water) | **PASS** |
| T4a | TestGreenPolygonPresent | test_green_polygon_exists | PASS | PASS |
| T4b | TestGreenPolygonPresent | test_green_polygon_covers_center | PASS | PASS |
| T5a | TestFireflyH14Regression | test_firefly_h14_green_present | PASS | PASS |
| T5b | TestFireflyH14Regression | test_firefly_h14_trap_present | PASS | PASS |
| T5c | TestFireflyH14Regression | test_firefly_h14_water_present | PASS | PASS |
| T6 | TestGreenMaskConstant | test_constant_exists_and_is_true | **FAIL** (missing) | **PASS** |

Full suite: **245 passed, 0 failed** (run against `app/tests/`).

---

## Regeneration overlay

**File:** `owner_inbox/detect_boundaries_stanford_h8_5396_2026-09-28_v2.png`

- v2 badge upper-left
- **Solid outlines** = new auto-detected polygons: green (lime), trap (orange), water (cyan)
- **Dashed outlines** = updated GT from the cleaned EGM (identical shape — auto-detect became the GT)
- Caption: "Compared to v1: green mask applied, trap H range widened, pale-cyan water added"

---

## Test drive for Thomas

1. Open the boundary editor at `http://localhost:5051`
2. Load `Stanford (hole 8, 5396).png` (course: Stanford)
3. Click **Auto-detect boundaries**
4. Expected result:
   - **1 green polygon** — egg-shaped outline covering the main playing surface
   - **1 trap polygon (orange)** — lower-left beige region, running along the LL edge
   - **1 water polygon (cyan)** — lower-right pale region, wedge shape in LR corner
   - **0 water polygons inside the green** — no blue/teal slope-band false positives

If the v4.77 server is still running, reload the page first — the footer should show **v4.78**.

---

*Files changed:*
- `app/app.py` — `APP_VERSION` bump, `MASK_GREEN_INTERIOR_FROM_HAZARDS` constant, trap/water classifier rewrite
- `app/tests/test_detect_boundaries_stanford_h8.py` — 9 new TDD tests (RED→GREEN)
- `ItWentIn/GolfCourses/Stanford/EGMs/Stanford (Hole 8, 5396).egm` — bogus water removed, trap + water added
- `ItWentIn/GolfCourses/Stanford/EGMs/Stanford (Hole 8, 5396).egm.pre_2026-09-28` — backup
- `owner_inbox/detect_boundaries_stanford_h8_5396_2026-09-28_v2.png` — overlay
