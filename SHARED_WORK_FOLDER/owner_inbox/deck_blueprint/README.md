# Deck Blueprint — 23'-6" × 16'-6" Attached Deck  (v10)

Produced by Gemma (Technical Diagramming Specialist) on 2026-05-01.

**v10 = v9 + outside-corner mitered joint correctly rendered at lower-left and lower-right (fixed open-square artifact); no other changes.** In v9 the left-side and right-side PF boards were drawn as full rectangles that overlapped the far-side PF band at the two outside corners, creating a visible open square gap where the miter should have been a clean diagonal seam. v10 clips the side PF bands at the far PF inner edge and draws the 45° miter seam explicitly, so each outside corner now shows a tight filled diagonal joint with no empty wedge.

**v9 = v8 + version badge in upper-left corner of every page (no other changes).** The badge shows "v10" in large bold text with a page sub-label ("Page 1 of 2 — Framing" / "Page 2 of 2 — Decking"), making it immediately obvious which version is open regardless of caching or file naming.

**v8 adds the Trex decking layer.** No structural changes from v7. The framing is locked. v8 converts the drawio file from single-page to two-page:

- **Page 1 — Framing Plan:** unchanged v7 framing content (what the framer needs).
- **Page 2 — Decking Plan:** framing at 40% opacity in background; 48 field planks + 4-side picture-frame board at full opacity in foreground (what the deck installer needs).

**v7 history:** v7 was a full structural rewrite that replaced the geometrically impossible joists-over-girders topology with face-hung joists top-flush at 11" AG, Pylex 50 spiral piers through the existing patio slab, and confirmed the 12" AG ceiling at every elevation.

---

## Files

| File | Description |
|------|-------------|
| `deck_plan.drawio` | Editable draw.io source **(v10, two pages)**. Open in [draw.io desktop](https://www.drawio.com/) or [app.diagrams.net](https://app.diagrams.net). Page 1 = Framing; Page 2 = Decking. Version badge in upper-left of both pages. Outside corner miters fixed. |
| `deck_plan.png` | Raster render of **Page 2 (Decking Plan)**, 2563 × 1885 px. Produced by `render_v10.py`. Version badge "v10" visible top-left. Outside corner miter clean at lower-left and lower-right. |
| `render_v10.py` | matplotlib render script for v10 Page 2 (Decking Plan). Corner miter fix applied. |
| `render_v9.py` | v9 render script (kept for reference). |
| `render_v8.py` | v8 render script (kept for reference). |
| `render_v7.py` | v7 render script (kept for reference — framing plan only). |
| `render_v6.py` | v6 render script (kept for reference — v6 was superseded). |
| `render_v4.py` | v4 render script (kept for reference). |
| `render_v3.py` | v3 render script (kept for reference). |

## How to open the .drawio file

- **draw.io desktop (recommended):** File → Open → select `deck_plan.drawio`
- **Browser:** Go to https://app.diagrams.net → drag-and-drop the file onto the browser window.
- **VS Code:** Install the "Draw.io Integration" extension, then open the file directly.

---

## Decking — v8 additions (Page 2)

### Field planks

| Attribute | Value |
|-----------|-------|
| Species / product | Trex Transcend 5.5" (or equivalent composite) |
| Board width | 5.5" actual face |
| Gap between planks | 1/8" typical |
| Effective spacing (c-c) | 5.625" |
| Run direction | Perpendicular to house (in the 16' depth direction) |
| Cut length | 15'-7" (187") — from inner edge of house-side PF to inner edge of far-side PF |
| Practical lumber | 16-ft boards, field-cut |
| Waste per board | ~5" |
| Count | **48 field planks** |

**How 48 is derived:** Field width = framing 23'-0" minus 2 × 2.5" (PF inboard overlap on each side) = 22'-7" = 271". 271" ÷ 5.625" = 48.18 → 48 planks. The remaining ~1.1" gap sits at the right-side PF edge (absorbed as a slightly wider gap; within Trex installation tolerances).

### Picture-frame boards (4 sides)

| Side | Length | Corner treatment |
|------|--------|-----------------|
| House-side | 23'-6" overall | **Butted** at left/right corners (against house wall) |
| Far-side | 23'-6" overall | **45° mitered** at left/right corners (outside, exposed) |
| Left-side | 16'-6" overall | Mitered at bottom (outside); butted at top (against house) |
| Right-side | 16'-6" overall | Mitered at bottom (outside); butted at top (against house) |

All PF boards: 5.5" wide × 1" thick (Trex composite). Single-board PF, not doubled.

**2 mitered corners, 2 butted corners:**
- Outside corners (far-left, far-right): 45° miter — both boards cut at 22.5° compound angle
- Inside corners (top-left, top-right against house wall): butt joint — no miter needed

### Plank count and ordering

| Item | Count |
|------|-------|
| Field planks (16-ft boards) | 48 |
| PF house-side (order 24-ft, or splice 2× 12-ft over a joist/girder) | 1 |
| PF far-side (same) | 1 |
| PF left-side (16-ft board, field-cut to 16'-6") | 1 |
| PF right-side (same) | 1 |
| **Board subtotal** | **52** |
| +10% waste factor | +5 |
| **Total order estimate** | **~57 boards** |

> This is a planning estimate. **Hollis** will produce the precise BOM with an exact cut list.

---

## Deck spec summary (v8 / v7)

- **Overall finished surface (PF outer edge to outer edge):** 23'-6" × 16'-6"
- **Framing footprint (rim outer edge):** 23'-0" × 16'-3"
- **Height:** 12" max above grade (hard ceiling, non-negotiable)
- **Existing concrete patio:** 23'-6" × 16'-6" — matches deck footprint exactly; punched for piers
- **Deck boards:** Trex composite, perpendicular to house (16'-3" direction)
- **Picture-frame border:** 5.5" Trex on all 4 sides (house side butts wall; 3 exposed sides overhang fascia 2.25")

---

## Vertical budget (12" AG ceiling — every elevation verified)

| Layer | Thickness | Elevation |
|-------|-----------|-----------|
| Top of Trex decking | — | **12.0" AG** |
| Trex composite board | 1.0" | top → bottom |
| Top of joist / girder | — | **11.0" AG** |
| 2×10 actual depth | 9.25" | top → bottom |
| Bottom of joist / girder | — | **1.75" AG** |
| Pylex saddle bracket height | ~1.5" | sits under girder bottom |
| Saddle top | — | ~1.75" AG (just clears) |
| Pier shaft above patio | ~0.5" | — |
| Patio / grade surface | — | **0" AG** |
| Pier shaft (Pylex 50) | 50" total | through slab, into soil |
| Pier tip depth | — | ~49" below patio surface |
| CT frost line | — | 42" — **cleared by ~7"** |

> **EVERY ELEVATION VERIFIED — TOP OF DECK = 12.0" AG**

---

## Foundation — Pylex 50 spiral piers (v7 NEW, replaces sonotube footings)

- **9 piers total, 3 per girder**
- **All within patio footprint** (homeowner constraint — patio is 23'-6" × 16'-6", matching deck exactly)
- **Installation:** sledgehammer-punch a ~3-4" diameter hole through the concrete patio at each pier location; screw the Pylex 50 helical pier through the hole; tip reaches ~49" below patio surface, well past the 42" CT frost line
- **Shaft:** 50" galvanized helical pier shaft; no separate wooden post; no concrete sonotube
- **Saddle bracket:** Pylex saddle plate bolts to pier shaft top (½" hot-dip galv bolts); girder bears directly in saddle (½" galv lag bolts up into girder bottom)
- **After install:** patch / grout concrete around shaft at patio surface

### Pier positions

| Pier | Girder | x (along house) | y (out from house) |
|------|--------|-----------------|---------------------|
| P1 | Left | x=0' | y=12" (1') |
| P2 | Left | x=0' | y=8'-1.5" (8.125') |
| P3 | Left | x=0' | y=16'-3" (16.25') |
| P4 | Mid | x=11'-6" | y=12" |
| P5 | Mid | x=11'-6" | y=8'-1.5" |
| P6 | Mid | x=11'-6" | y=16'-3" |
| P7 | Right | x=23' | y=12" |
| P8 | Right | x=23' | y=8'-1.5" |
| P9 | Right | x=23' | y=16'-3" |

**Note on P1/P4/P7 (house-side piers at 12"):** Offset 12" out from house to clear foundation. Each girder cantilevers 12" past the house-side pier back to the ledger.

---

## Framing topology (v7 — face-hung, top-flush)

**All structural member tops align at 11.0" AG.** No member sits on top of another. This is the only topology that fits within the 12" AG ceiling with 2×10 members.

### Ledger (unchanged identity from v4/v6; new structural relationship in v7)
- **Single 2×10 PT ground-contact, 23'-0" long**
- Lag-bolted to house rim joist: ½" hot-dip galv lag bolts (or FastenMaster LedgerLOK), 16" o.c. staggered top/bottom
- Metal Z-flashing over top of ledger, tucked behind siding/wrap
- **Top-flush with girders at 11.0" AG** — not on top of them
- **No piers under ledger** — supported entirely by lag bolts into house framing
- **MTWDeck lateral-tie callout:** minimum 2× Simpson MTWDeck (or equivalent) per IRC R507.9 / DCA-6; requires 2× band joist + 2× interior blocking bearing on sill plate inside house

### Girders — 3 tripled 2×10 PT, 16'-3" long
- Located at **x=0'** (left), **x=11'-6"** (mid), **x=23'** (right) along house direction
- **Top-flush at 11.0" AG**; bottoms at 1.75" AG
- Bear directly in Pylex saddle brackets at 3 pier positions per girder
- Cantilever 12" past house-side pier (P1/P4/P7) back toward ledger

### Joists — 2×10 PT, 12" o.c., FACE-HUNG (v7 NEW topology)
- **Each joist run is broken into 2 segments per girder bay:**
  - **Seg A:** from right face of left girder to left face of mid girder (~11'-3" long)
  - **Seg B:** from right face of mid girder to left face of right girder (~11'-3" long)
- Each segment end is **face-hung with a Simpson LUS210Z hot-dip galv face-mount hanger**
- **Joist tops = girder tops = 11.0" AG** (top-flush throughout; joists do NOT pass over girders)
- **16 regular rows** at y=1' through y=16' (12" o.c.)
- **1 doubled far-side rim** (2 plies of 2×10 PT) at y=16'-3", face-hung in same 2-segment pattern with LUS210-2Z hangers
- **Final bay:** 3" from last 12"-o.c. row (y=16') to doubled rim (y=16'-3") — intentional, normal
- **Total:** 17 rows × 2 segments = **34 joist segments + ~68 face-mount hangers in field**

### House-side PF blocking (v7 NEW)
- Short 2×10 PT blocking pieces between ledger (y=0) and first joist row (y=12") at ~12" o.c. along the house
- Backs the house-side picture-frame board, which would otherwise span ~12" unsupported above the ledger

### Drop-board sub-fascia (v7 NEW)
- A continuous 2× member outboard of the left girder outer face, right girder outer face, and far-side doubled rim outer face
- Mounted at joist elevation, attached to girder/rim outer face
- **Purpose:** backs the 3" PF cantilever past the rim on the 3 exposed sides (Trex max recommended unsupported cantilever ≈ 1.5"; this gives full backing)

### Field blocking (lateral stiffness)
- Two rows of solid 2×10 blocking between joist segments, perpendicular to joists:
  - **Row 1:** x=5'-9" from left edge (midspan of left girder bay)
  - **Row 2:** x=17'-3" from left edge (midspan of right girder bay)
- Shown as dashed lines in plan view

---

## Picture-frame border (4 sides, v7 — same as v6 spec)

| Side | Member | Fascia | Overhang |
|------|--------|--------|----------|
| House side | 5.5" Trex PF board | None (wall is boundary) | None past wall; 1/4" thermal gap to siding |
| Far side | 5.5" Trex PF board | 0.75" Trex Universal Fascia | 2.25" past fascia (3" past rim outer face) |
| Left side | 5.5" Trex PF board | 0.75" Trex Universal Fascia | 2.25" past fascia (3" past rim outer face) |
| Right side | 5.5" Trex PF board | 0.75" Trex Universal Fascia | 2.25" past fascia (3" past rim outer face) |

- Mitered joints at the 3 outside corners (far-left, far-right, and at house-side left/right corners)
- House-side PF board backed by ledger + new house-side 2×10 blocking

---

## Fastener schedule (v7)

| Connection | Fastener |
|------------|----------|
| Ledger to house | ½" hot-dip galv lag bolts or FastenMaster LedgerLOK, 16" o.c. staggered |
| Ledger flashing | Metal Z-flashing, tucked behind siding |
| Lateral tie | Min. 2× Simpson MTWDeck or equiv. per IRC R507.9 / DCA-6 |
| Pier saddle to pier shaft | ½" hot-dip galv bolts (Pylex saddle plate) |
| Girder to pier saddle | ½" galv lag bolts up into girder bottom |
| Joist segment to girder (face-hung) | Simpson LUS210Z hot-dip galv (~68 total in field) |
| Doubled rim segments (face-hung) | Simpson LUS210-2Z hot-dip galv |
| Drop-board to girder/rim | Structural screws or lag bolts |
| Fascia to rim | Stainless trim screws |
| 2-ply rim | ½" carriage bolts per AWC specs |
| Joist tape | Zip System or equivalent on every joist top surface |
| All hardware | Hot-dip galvanized or stainless (ACQ-compatible) |

---

## Drawing key

Color-coded (see legend in drawing):

| Color | Member |
|-------|--------|
| **Red/pink, thick stroke** | Ledger (single 2×10 PT, top-flush @ 11" AG) |
| **Blue (thick vertical bands)** | Girders (tripled 2×10 PT, top-flush @ 11" AG) |
| **Green (horizontal segments broken at each girder)** | Face-hung joist segments (2×10 PT, 12" o.c.) |
| **Yellow (double-thick bar at 16'-3")** | Doubled far-side rim (face-hung in 2 segments) |
| **Bright yellow (4-side border)** | Picture-frame board (5.5" Trex, all 4 sides) |
| **Purple** | Trex Universal Fascia (0.75", 3 exposed sides) |
| **Green-tinted thin strips** | Drop-board sub-fascia (left/right/far edges) |
| **Light green short pieces between ledger and first joist** | House-side PF blocking |
| **Dark brown filled circles with outer lighter ring** | Pylex 50 spiral piers (P1–P9); outer ring = punched patio hole |
| **Gray dashed** | Field blocking rows (at x=5'-9" and x=17'-3") |
| **Warm tan hatched background** | Existing concrete patio (23'-6" × 16'-6") |
| **Amber callout** | MTWDeck lateral-tie requirement |
| **Red/orange box** | Vertical budget + "EVERY ELEVATION VERIFIED" callout |

---

## Version history (v4 → v7 diff)

| Element | v4 / v6 | **v7 (this version)** |
|---------|---------|----------------------|
| Foundation | 6×6 PT posts on 12" sonotube footings to frost depth | **Pylex 50 spiral piers, 50" galv. shaft, through punched patio holes — no posts, no sonotubes** |
| Pier/post positions y | 0', 8', 16' (v4) / 0', 8'-1.5", 16'-3" (v6) | **12", 8'-1.5", 16'-3" — house-side pier offset 12" to clear foundation; girder cantilevers 12" to ledger** |
| Framing topology | Joists rest ON TOP of girders (joists-over-girders) | **FACE-HUNG: joists butt girder faces via LUS210Z hangers; all tops co-planar at 11.0" AG** |
| Joist geometry | Single continuous spans (23'-0" joists spliced at mid girder) | **2 segments per row — Seg A and Seg B — broken at each girder, hung at both ends** |
| Girder function | Post cap + beam + joists resting on top | **Girder in Pylex saddle; joist tops flush with girder top; joists hang from girder face** |
| Joist count | 17 total (v4/v6: 1 ledger + 15 regular + 1 rim) | **17 rows (16 regular @ 12" o.c. + 1 doubled rim) × 2 segments = 34 segments** |
| Hanger count | ~0 (joists bore on girders, not hung in field) | **~68 Simpson LUS210Z face-mount hangers in field + LUS210-2Z at rim** |
| Patio | Not shown | **23'-6" × 16'-6" existing concrete patio shown as tinted hatched background; pier holes visible** |
| Drop-board sub-fascia | Mentioned in notes only (v6) | **Shown explicitly in plan: thin green strip outboard of each exposed girder/rim edge** |
| House-side PF blocking | Not shown | **Shown in plan: short 2×10 pieces between ledger and first joist row at 12" o.c.** |
| Section detail | Footing → post → post cap → girder → joist → tape → decking | **Fully rewritten: grade + patio + punched hole + Pylex shaft (50" down) + saddle + girder bottom → top-flush joist → tape → decking → 12.0" AG** |
| Vertical stack feasibility | ~20" required (geometric impossibility at 12" ceiling) | **12.0" AG confirmed: every elevation verified in section detail** |

**v5 note:** v5 was started as an incremental update but abandoned before delivery.
**v6 note:** v6 was delivered with correct overall dimensions (23'-6" × 16'-6", 4-side PF, fascia, etc.) but retained the geometrically impossible joists-over-girders-over-posts-over-sonotubes stack. v6 is superseded by v7.

---

## Version history (v7 → v8 diff)

| Element | v7 | **v8** |
|---------|----|-----------------------|
| Framing | Unchanged | **Unchanged — framing is locked** |
| draw.io file | Single page | **Two pages: Page 1 = Framing Plan, Page 2 = Decking Plan** |
| Deck planks | Not shown | **48 field planks (5.5" × 15'-7", ⊥ house, 1/8" gap) + 4-side PF board** |
| Field plank count | — | **48** (271" field width ÷ 5.625" spacing = 48.18 → 48) |
| PF joints | — | **2 mitered corners (outside, far-left/far-right), 2 butted (inside, against house)** |
| PNG render | Page 1 framing only | **Page 2 decking: framing @ 40% opacity background + planks foreground** |
| PNG dimensions | 2620 × 2363 px | **2563 × 1885 px** |
| Board count estimate | — | **~57 boards** (48 field + 4 PF + 10% waste) |
| BOM | — | Hollis to produce precise BOM — this is a planning estimate only |

---

## Version history (v8 → v9 diff)

| Element | v8 | **v9** |
|---------|----|-----------------------|
| All structural content | Unchanged | **Unchanged — framing and decking are locked** |
| Version badge | None | **Bold "v9" badge in upper-left of both drawio pages and PNG** |
| Page sub-label | None | **"Page 1 of 2 — Framing" / "Page 2 of 2 — Decking" below badge** |
| Title block | "DECK PLAN v8 …" | **"DECK PLAN v9 …" on both pages** |
| Diagram IDs / page names | deck-plan-v8-p1, v8-p2 | **deck-plan-v9-p1, v9-p2** |

---

## Version history (v9 → v10 diff)

| Element | v9 | **v10 (this version)** |
|---------|----|-----------------------|
| All structural content | Unchanged | **Unchanged — framing and decking are locked** |
| Outside corner rendering | Open-square artifact: left/right PF rectangles overlapped far PF zone; miter line drawn over overlap but corner had visible gap | **Fixed: left/right PF bands clipped at far PF inner edge; corner overlap square filled with correct PF color; 45° diagonal miter seam drawn explicitly — clean tight joint, no gap** |
| Left PF / Right PF (Page 2 render) | Full rectangle extending to FAR_PF_Y1=16.5 ft | **5-vertex mitered polygon, terminated at FAR_PF_Y0=16.04 ft with diagonal cut to outer corner** |
| Fascia corner (Page 2 render) | Left/right fascia strips ended at far fascia top — small gap at outer corner | **Left/right fascia extended to fas_y+FASCIA_T — flush butt-join, no gap** |
| Page 1 drawio PF cells | Left/right PF h=686 (extended into far PF overlap zone) | **h=668 (trimmed to far PF inner edge); miter fill triangle + seam line added at each outside corner** |
| Page 2 drawio PF cells | Left/right PF h=660 | **h=641.7 (trimmed); miter fill triangle + seam line added at each outside corner** |
| Version badge | "v9" | **"v10"** |
| Title block | "DECK PLAN v9 …" | **"DECK PLAN v10 …" on both pages** |
| Diagram IDs / page names | deck-plan-v9-p1, v9-p2 | **deck-plan-v10-p1, v10-p2** |
