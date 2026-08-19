# Polar Filaments PHA — Bambu Studio Settings

## Filament

| Parameter | Value | Notes |
|-----------|-------|-------|
| Nozzle Temp (1st layer) | 203°C | Polar PHA baseline (SpoolBites) |
| Nozzle Temp (other layers) | 203°C | Stable across layers |
| Bed Temp | 60°C | Polar PHA blend; higher thermal mass with aggressive fan ramp |
| Chamber Temp | Keep <45°C | Open enclosure doors on X1C/P1S; add external fans if needed |
| Drying | Optional | PHA is less moisture-critical than PETG/Nylon; if ambient is dry, skip. If humid, 4–6 hrs at 50–60°C |

## Process

| Parameter | Value | Notes |
|-----------|-------|-------|
| Wall Loops | 3–4 | Standard PLA; increase to 4 if text/fine features fail |
| Brim | 6 loops, 5 mm width | Anchors footprint; critical for PHA blends with aggressive cooling |
| Top/Bottom Layers | 4 (top) / 3 (bottom) | PHA needs robust enclosure to prevent gaps |
| Infill Pattern | Gyroid | Reduce stringing vs. grid; default for PHA blends |
| Infill Density | 15–20% | Standard; increase if part needs rigidity |
| Layer Height | 0.2mm | Start conservative; 0.15mm for detail, 0.3mm for speed trade-off |
| Print Speed | 80–100 mm/s | PHA blends tolerate standard PLA speeds; dial back to 60 mm/s if stringing occurs |
| First Layer Speed | 20–30 mm/s | Slow first layer for bed adhesion |
| First-Layer Flow | 1.05 | Increase squish; locks first layer harder to prevent L2+ peel |
| Fan Speed (Layer 1) | 0% | No cooling layer 1; ensures adhesion |
| Fan Speed (Layer 2–3) | 30–40% | Gradual ramp starts at L2; prevents shock contraction |
| Fan Speed (Layer 4+) | 80% | Reach full cooling by L4; safer than immediate 100% |
| Retraction Distance | 2–2.5mm | PHA requires lower retraction than PLA; less is often better |
| Retraction Speed | 30–40 mm/s | Standard direct-drive speed |
| Z-Seam | Random or Shortest | Minimize visible seams; PHA is slightly more forgiving than PLA |
| Ironing | Off | Only enable if top surface roughness is problematic |
| Support Type | Tree (if needed) | Reduces material waste and interface scarring |

---

## Sources

- **Nozzle/Bed temps:** [SpoolBites PHA by Brand](https://www.spoolbites.com/materials/pha) — lists Polar Filament Biodegradable at 203°C nozzle, 55°C bed
- **Fan cooling strategy & retraction:** [WebSearch — PHA filament Bambu Studio community settings](https://bambureviews.com/posts/bambu-filament-settings-guide/) + community consensus from Bambu Lab forums and r/3Dprinting (0% L1 / 100% L2+, 2–3mm retraction)
- **Chamber & enclosure:** [WebSearch — PHA Bambu Lab printing guide](https://www.spoolbites.com/materials/pha) — open enclosure, add external fans
- **General PHA behavior:** ColorFabb allPHA and community best practices (moisture-tolerant blend, strong layer adhesion, lower retraction than PLA)

---

## Tips

- **First print:** Run at **80 mm/s** and **0–55°C bed** with **100% fan from L2**. If stringing appears, cut fan to 80% or reduce speed to 60 mm/s.
- **Temperature tower:** If you want to dial in nozzle temp precisely, run 190–210°C tower (optional; 203°C is a solid starting point).
- **Flow calibration:** Polar PHA blends typically run 1.0 (100% flow) out of the box. If under-extruding, bump to 1.02–1.05.
- **Bed adhesion:** Polar PHA sticks well at 55°C on textured PEI or cool plate. If adhesion fails, try 60°C bed and a wide brim (8–12 loops).
- **Post-print:** PHA is home-compostable per Polar's specs, but for long-term storage, keep spools sealed in a dry box (not strictly necessary, but extends shelf life).

---

## Layer-2 Peel Fix (Task 667)

If your print **un-sticks at layer 2–3** (first layer adhesion looks fine, then thermal contraction lifts the part):

**Filament**
| Parameter | Change |
|-----------|--------|
| Bed Temp | 55°C → **60°C** |
| Fan Speed (L2–3) | 100% → **30–40%** |
| Fan Speed (L4+) | N/A → **80%** |

**Process**
| Parameter | Change |
|-----------|--------|
| First-Layer Flow | 1.0 → **1.05** |
| Brim | None → **6 loops, 5 mm width** |

**Why:** The original 100% fan at L2 + 55°C bed caused shock contraction. Gradual ramp (30% → 60% → 80%) + higher bed temp + stronger first-layer squish + brim anchoring prevents L2+ lifting.

**Try in order:**
1. Apply all four changes above; print at 80 mm/s.
2. If still lifting, bump first-layer flow to 1.07 and lower live-Z by 0.02 mm.
3. If persists, raise bed to 62–65°C or add gluestick prep.
