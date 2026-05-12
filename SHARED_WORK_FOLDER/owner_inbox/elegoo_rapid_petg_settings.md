# Elegoo Rapid PETG — Slicer Settings & Starting Profile

**Prepared by:** Finn (3D Print & Slicer Specialist)
**Date:** 2026-05-12
**Filament:** Elegoo Rapid PETG, 1.75 mm

---

## Diagnosis / Context

Elegoo Rapid PETG is a high-speed-optimized PETG formulation rated up to 600 mm/s by the manufacturer. That ceiling is only reachable on high-flow CoreXY machines (Centauri Carbon, Bambu X1C/P1S, Voron, etc.) with a high-flow or volcano hotend; on a standard 0.4 mm brass nozzle the realistic quality ceiling is ~150–200 mm/s and a max volumetric flow of ~18 mm³/s. The filament behaves like PETG with a lower-viscosity formulation — great flow, slightly more stringing risk than a "precision" PETG, and it is hygroscopic. The three most common failure modes are (1) stringing from moisture or temp too high, (2) ripping the smooth PEI sheet off the bed on removal, and (3) poor layer adhesion from running it too cold or with too much cooling fan.

---

## 1. Quick-Start Numbers

> All temps and speeds verified against the official Elegoo data sheet (SpoolScout mirror of manufacturer spec) and cross-checked against community reports on the Bambu Lab forum, Prusa forum, and Sovol/OrcaSlicer forums. Speed ceiling is printer-dependent — **flag your hotend's max volumetric flow before trusting the high end of these ranges.**

| Parameter | First Layer | Other Layers | Notes |
|---|---|---|---|
| **Nozzle temp** | 245–250 °C | 240–250 °C | Mfr range: 240–270 °C. Community sweet spot is 240–250 °C. Above 255 °C stringing increases sharply; above 260 °C bridges collapse. |
| **Bed temp** | 80–85 °C | 75–80 °C | Mfr spec: 65–70 °C (conservative). Community consistently runs 80–85 °C for first layer, stepping down ~5 °C after. |
| **Chamber / enclosure** | Open frame is fine | Open frame is fine | PETG does not need an enclosure and benefits from ambient air flow. Keeping ambient below ~35 °C avoids heat creep. |
| **Print speed** | 20–30 mm/s | 60–150 mm/s quality / up to ~250 mm/s draft | Mfr ceiling: 600 mm/s. Realistic quality ceiling on standard hotend: ~150 mm/s. CoreXY high-flow hotend: 200–300 mm/s. Slow first layer is non-negotiable for PETG. |
| **Max volumetric flow** | — | **≤ 18 mm³/s** (standard hotend) | Community-reported upper limit on standard 0.4 mm brass. High-flow hotends (CHT, Volcano, Bambu HF) can push 25–35 mm³/s. Always cap in slicer to avoid grinding. |
| **Part cooling fan** | **0%** | 30–50% | Never cool the first layer. PETG over-cooled = poor layer adhesion. Do NOT run 100% like PLA. Start at 30%, increase if bridging is poor or surfaces look rough. |
| **Retraction — direct drive** | — | 0.5–1.0 mm @ 25–45 mm/s | Mfr spec: 0.8 mm / 45 mm/s. Community on direct-drive: 0.5–1.0 mm, tune from there. |
| **Retraction — Bowden** | — | 3–5 mm @ 40–60 mm/s | Longer tube = more retraction needed. Start at 3.5 mm, add 0.5 mm increments if stringing persists. |
| **Z-hop** | On | On | 0.2 mm. Prevents nozzle from dragging strings back into the part. Especially important with PETG's tendency to string. |
| **Flow / extrusion multiplier** | 1.00 | 0.95–1.00 | Start at 1.00. Flow calibration often lands at 0.95–0.98 for this filament. Do not assume — run the test. |
| **Pressure advance / linear advance** | — | ~0.04–0.06 (ballpark) | Must calibrate per machine. Bambu users: run built-in calibration. OrcaSlicer users: use the PA calibration tower. Do not skip this — it eliminates blobs and zits. |
| **Layer height** | 0.2–0.25 mm | 0.15–0.30 mm | 0.2 mm is the reliable all-rounder. For a 0.4 mm nozzle, stay between 25% and 75% of nozzle diameter. |
| **First-layer height** | 0.25–0.30 mm | — | Slightly taller than normal for good squish. Combine with slower speed and higher temp. |
| **Drying** | 60 °C for 8 hours | — | Manufacturer spec. Dry before first use and after any extended open-air storage. |

---

## 2. Bed Surface Guide

| Surface | Behavior | Recommendation |
|---|---|---|
| **Textured PEI** | Excellent adhesion, releases cleanly when cool. | **Best choice for PETG.** Let the plate cool to ~40 °C before removing the part — it pops off cleanly. |
| **Smooth PEI** | PETG over-adheres aggressively. Can rip the PEI coating off the spring-steel sheet permanently. | **Apply a thin glue stick layer as a release agent** (not for adhesion — for protection). The glue stick creates a sacrificial barrier. Do NOT print PETG on bare smooth PEI without a release agent. |
| **Glass (plain)** | Mediocre adhesion without treatment. | Glue stick or hairspray for adhesion. |
| **Cool Plate / Bambu Engineering Plate** | Decent; not ideal for PETG. | Use textured PEI instead. |

---

## 3. Per-Slicer "How to Apply"

### Bambu Studio + OrcaSlicer (cross-reference)

- **Built-in profile:** Bambu Studio and OrcaSlicer both ship a generic **PETG** filament profile. There is no dedicated "Elegoo Rapid PETG" profile bundled in the stock install. Community-created profiles exist on MakerWorld (search "Elegoo Rapid PETG") and Printables — useful as a starting reference but always re-calibrate to your machine.
- **Recommended base:** Use the generic **PETG Basic** or **PETG HF** (high-flow) profile in Bambu Studio as your starting point.
  - Clone it, rename it "Elegoo Rapid PETG."
  - Set nozzle to 245 °C / 240 °C (first/other).
  - Set bed to 85 °C / 80 °C.
  - Set max volumetric speed to **18 mm³/s** initially (raise carefully after flow calibration).
  - Fan: 0% first layer, 30–40% afterward.
  - Retraction: direct-drive ~0.8 mm @ 45 mm/s.
  - Run Bambu's built-in **Flow Rate** and **Pressure Advance** calibrations before committing to a real print.
- **OrcaSlicer calibration tools** (see Section 4 below) are more granular than Bambu Studio's built-in tools and are recommended for dialing in this filament properly.

### PrusaSlicer / SuperSlicer

- Start from the **Generic PETG** profile (0.20 mm QUALITY or SPEED depending on your target).
- Apply the temperature, speed, and retraction numbers from the quick-start table above.
- PrusaSlicer ships with a Linear Advance calibration model (Print → Calibration → Linear Advance) — use it.
- Set **Filament cooling → Enable fan** to 30–50%; disable for first layer.

### Cura

- Base on the **Generic PETG** material profile.
- Apply temps, retraction, fan, and speed from the table.
- Enable **Combing mode: Not in Skin** — this reduces surface blobs by keeping the nozzle inside the part during travel.
- Enable **Coast at End** (in special modes) to reduce pressure-advance-style blobs at seams.
- Set **Z Hop When Retracted** to 0.2 mm.

---

## 4. Calibration Checklist

Run these **in order** before trusting the profile for real parts. OrcaSlicer has built-in wizards for all of these (Calibration menu → run directly from the slicer).

- [ ] **Dry the filament** — 60 °C for 8 hours. No calibration is reliable on wet PETG. If you hear popping/crackling while printing, stop and dry.
- [ ] **Temp tower** — Print a temperature tower stepping from 255 °C down to 235 °C (or start from 260 °C if your hotend can do it). Look for the zone with the cleanest bridges, best surface, and least stringing. That's your operating temperature.
- [ ] **Flow rate (extrusion multiplier)** — OrcaSlicer: Calibration → Flow Rate. Aim for a flat, smooth top surface with no gaps or ridges. Typical result for this filament: 0.95–0.98.
- [ ] **Pressure advance / linear advance** — OrcaSlicer: Calibration → Pressure Advance tower. Bambu Studio: built-in calibration. Look for the line that transitions from slow to fast speed with no bump or notch. Starting ballpark: 0.04–0.06 for direct drive on a CoreXY.
- [ ] **Retraction test** — Print a retraction tower or a simple two-tower stringing test. Tune retraction distance in 0.2 mm increments until stringing is gone without grinding.
- [ ] **Max volumetric flow** — OrcaSlicer: Calibration → Max Flow Rate. Find where extrusion becomes inconsistent (grinding, skipping) and back off 10–15% for your working ceiling.

---

## 5. Troubleshooting Table

| Symptom | Most Likely Cause | Fix |
|---|---|---|
| **Stringing** | Temp too high, wet filament, retraction under-tuned | Lower nozzle temp 5 °C at a time; dry the filament first; increase retraction in 0.2 mm steps; enable z-hop |
| **Poor layer adhesion / delamination** | Temp too low, cooling too high | Raise nozzle temp; reduce fan speed (never above 50% for PETG); reduce print speed so each layer has more contact time |
| **Blobs and zits at seam** | Pressure advance not tuned, coasting off | Calibrate pressure advance; enable coasting in slicer; use "Seam: Rear" to hide blobs at the back of the part |
| **Part bonded to bed — won't release** | Printed on bare smooth PEI at high bed temp | Let the plate cool fully (< 40 °C); if it still won't release, do NOT pry — put it in the freezer for 5 minutes. Prevention: use textured PEI, or glue stick as release agent on smooth PEI |
| **PEI coating ripped off the spring-steel sheet** | Over-adhesion on smooth PEI, forced removal while hot | Already damaged — replace the sheet. Future prevention: always use textured PEI for PETG or apply glue stick barrier to smooth PEI |
| **Rough/bubbled surface, cracking sounds** | Wet filament (moisture) | Dry at 60 °C for 8 hours before next run; store in airtight container with desiccant |
| **Under-extrusion / grinding** | Max volumetric speed set too high | Lower max volumetric speed; reduce print speed; check for partial clog |
| **Heat creep / clog after long print** | Hotend cooling inadequate, ambient too warm, printing too slow (heat soak) | Ensure hotend fan is running; lower ambient temperature; do not print slower than ~30 mm/s for PETG (heat soak risk); check PTFE liner isn't degraded |
| **Elephant foot on first layer** | First-layer temp too high, z-offset too low, bed too hot | Raise z-offset slightly; lower first-layer speed; reduce bed temp to 80 °C |
| **Warping / corners lifting** | Bed temp too low, draft across print | Raise bed temp to 85 °C; eliminate drafts; ensure first layer has correct squish |

---

## 6. Drying Note

PETG is hygroscopic. Elegoo's official spec is **60 °C for 8 hours** before use. Community consensus also runs 60 °C for 6–8 hours; some users prefer 65 °C for 4–6 hours on a heated print bed or food dehydrator.

**Signs of wet PETG:**
- Audible popping or crackling during extrusion (moisture boiling off)
- Visible steam at the nozzle tip
- Excessive stringing even with correct retraction
- Rough, foamy, or matte surface finish (normally PETG is glossy)
- Brittle parts with poor layer adhesion
- Inconsistent extrusion / blobs that appear randomly

**Storage:** After drying, store in an airtight container (e.g., vacuum bag or dry box) with silica gel desiccant. Filament left on an open spool in humid conditions will absorb moisture within a few days.

---

## 7. Sources

All specs verified 2026-05-12.

- [Elegoo Rapid PETG — Official US Product Page](https://us.elegoo.com/products/rapid-petg-filament-1-75mm-colored-1kg) — confirms 600 mm/s max speed, 60 °C/8 hr drying, ±0.02 mm dimensional accuracy; nozzle/bed temp NOT listed on this page
- [Elegoo Rapid PETG — Official EU Product Page](https://eu.elegoo.com/en-es/products/rapid-petg-filament-1-75mm-colored-1kg) — same
- [Elegoo Rapid PETG Data Sheet (SpoolScout)](https://www.spoolscout.com/data-sheets/elegoo/petg-rapid-petg) — **primary spec source**: nozzle 240–270 °C, bed 65–70 °C, speed 30–600 mm/s, retraction 0.8 mm / 45 mm/s, melt index 33.3–40.9 g/10 min
- [Bambu Lab Community Forum — ELEGOO Rapid PETG Filament](https://forum.bambulab.com/t/elegoo-rapid-petg-filament/48209) — community settings on A1/P1S/X1; MVS 18, flow ratio 0.96, pressure advance calibration notes
- [Bambu Lab Community Forum — Elegoo PETG Rapid Suggestions](https://forum.bambulab.com/t/elegoo-petg-rapid-suggestions/96245) — additional community tuning reports
- [Prusa Forum — Print Settings for Elegoo Rapid PETG](https://forum.prusa3d.com/forum/filament-materials-and-techniques/print-settings-for-elegoo-rapid-petg/) — nozzle 240 °C, bed 85 °C, drying 60 °C/6–8 hr; retraction disabled on one user's setup; bridging issues above 255 °C
- [Sovol Forum — OrcaSlicer Profile for SV08 + Elegoo Rapid PETG](https://forum.sovol3d.com/t/does-anyone-have-a-good-orca-slicer-profile-for-the-sv08-and-elegoo-rapid-petg/8462) — retraction starting point 0.5–0.8 mm; temp tower recommendation; stringing troubleshooting
- [3D Print Beast — PETG on PEI surfaces](https://www.3dprintbeast.com/petg-on-pei/) — smooth PEI over-adhesion risk, glue stick as release agent explanation
- [Bambu Lab Community Forum — PETG on PEI sheet; Glue or No Glue](https://forum.bambulab.com/t/petg-on-pei-sheet-glue-or-no-glue/18823) — community consensus on glue stick as release agent for smooth PEI
- [Hackaday — Elegoo Rapid PETG vs PETG Pro](https://hackaday.com/2025/07/19/elegoo-rapid-petg-vs-petg-pro-same-price-similar-specs-which-to-buy/) — third-party comparison; Rapid PETG won tensile/layer adhesion tests; Pro PETG has slightly lower moisture sensitivity

---

*⚠️ Flag: Max volumetric flow and top-end print speed are **hotend-dependent**. 18 mm³/s and 150 mm/s are safe starting ceilings for a standard 0.4 mm brass nozzle. High-flow hotends (Bambu HF, CHT insert, Volcano/Dragon HF) can push significantly higher — run the max flow calibration for your specific hardware before exceeding these numbers.*
