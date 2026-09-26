# v1 — Firefly Hole 14 Sand-Trap Left-Edge Chamfer: Diagnosis

**Topo / 2026-09-26 / Task 602**

---

## What Thomas Saw

Firefly Hole 14, regenerated after the rake-fix (v0.03 / v4.62): the left side wall of Trap 1 is not vertical — it is beveled/chamfered, cutting diagonally from the interior top surface (~11–12 mm) down to ~9 mm at the frame-edge face. The bevel spans roughly the leftmost **6 mm** of the trap's 16.5 mm width.

No screenshot was found in `owner_inbox/`. (Screenshots from the prior turn were of DeLaveaga, not Firefly.)

---

## Diagnosis: Intended Cap Rule — Not a Bug

### Root cause

The edge-band cap (`_apply_lift_and_cap`, lines 4942–5070) applies a **1 mm hard zone + 5 mm taper** on every mesh that touches the frame perimeter. For a water-hole, this fires on both the fringe and every trap.

Trap 1's left wall sits flush against the frame left edge (confirmed by geometry: leftmost EGM points are at `px ≈ -16.8 → mm ≈ -85.20`, exactly the frame's `±85.197 mm` half-extent). After the 2 mm water-hole lift, all trap top vertices are at **Z ≈ 11–12 mm**. The cap clips them toward 9 mm based on distance from the frame:

| Distance from left frame edge | Cap strength | Top-face Z (example: slab at 12 mm lifted) |
|---|---|---|
| 0 mm (frame wall) | 1.00 | 9.00 mm |
| 0.7 mm | 1.00 | 9.00 mm |
| 1.0 mm | 1.00 | 9.00 mm |
| 1.7 mm | 0.86 | 9.42 mm |
| 2.0 mm | 0.80 | 9.60 mm |
| 3.0 mm | 0.60 | 10.2 mm |
| 4.0 mm | 0.40 | 10.8 mm |
| 6.0 mm | 0.00 | 12.0 mm (untouched) |

That 9 mm → 12 mm gradient across 6 mm is the chamfer. The trap is only **16.5 mm wide**, so the left 6 mm = **36% of the trap width** is visually tapered.

### The cap logic is working exactly as designed

The 5 mm taper (`BOUNDARY_CAP_TAPER_MM = 5.0`) was added deliberately by task #488 (see comment block at lines 1261–1268) to avoid a **hard cliff** where a trap reaches the frame — cells inside the 1 mm band get clipped to 9 mm while cells 1 mm further in keep natural Z (~12 mm), which reads in the slicer as a sharp 3 mm vertical wall step. The taper softens that step into a gradual slope.

So the cap IS doing what it says. The question is whether the taper is desirable for a narrow trap.

### The rake fix did NOT introduce this

The chamfer has been present since **[156]** (2026-09-11, commit `aef418d`), which is the first Firefly H14 3MF ever generated. The previous "post-texture flatten" (removed by fix #600 on 2026-09-26) ran *before* the lift+cap, so the cap was always seeing the same flat-slab surface. The flatten masked the rake lines but did not change the cap's effect on the left wall. Thomas is noticing the chamfer now because fix #600 was a moment of fresh eyes on the slicer view.

---

## Files Changed

None. This is a design-question outcome. No code was modified, no version was bumped.

---

## Recommendation for Thomas

The chamfer is a product of `BOUNDARY_CAP_TAPER_MM = 5.0` working correctly on a narrow trap. Three options:

### Option A — Leave it as-is
The taper keeps the picture-frame edge clean. The 6 mm bevel on a narrow trap is the aesthetic tradeoff. On most wide traps it is invisible because 6 mm is a small fraction of the width.

### Option B — Reduce the taper for traps only
Add a `trap_cap_taper_mm` override (defaulting to, say, 1.0 or 2.0 mm) and pass it through `_apply_lift_and_cap`. This tightens the taper zone specifically for traps while keeping the wide 5 mm taper for the fringe (which caused the original task #488 cliff complaint).

Geometry at `BOUNDARY_CAP_TAPER_MM = 1.0 mm` (total zone = 2 mm):

| Distance from edge | Cap strength | Z (12 mm slab) |
|---|---|---|
| 0 mm | 1.00 | 9.00 mm |
| 1.0 mm | 1.00 | 9.00 mm |
| 1.5 mm | 0.50 | 10.5 mm |
| 2.0 mm | 0.00 | 12.0 mm |

That confines the bevel to the leftmost ~2 mm — effectively invisible at the 1 mm scale used in the frame-edge rule description.

### Option C — Disable the cap for traps entirely (`applyFringeFrameCap`-style flag)
The EGM already has `applyFringeFrameCap` (gated in the fringe path). A matching `applyTrapFrameCap` flag per trap (or globally) would let you turn off the cap for traps that sit flush against the edge, while keeping it on for the fringe.

---

## Next Step Required from Thomas

Please let Larry know which option you prefer, and Topo will implement it with a TDD red→green cycle.

- **Option A** → no work needed; close task.
- **Option B** → Topo adds `BOUNDARY_CAP_TAPER_TRAP_MM` constant (default `1.0`), threads it through `export_trap_stls` → `_apply_lift_and_cap`, writes failing geometry test, fixes, shows red→green. Version bumps: GSD v0.03 → v0.04, app v4.62 → v4.63.
- **Option C** → Topo adds per-trap cap flag, similar scope to Option B.
