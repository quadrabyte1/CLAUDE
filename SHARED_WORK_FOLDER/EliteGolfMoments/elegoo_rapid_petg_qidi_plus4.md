# Elegoo Rapid PETG — QIDI Plus4 Settings & Profile Guide

**Prepared by:** Finn (3D Print & Slicer Specialist)
**Date:** 2026-05-12
**Printer:** QIDI Plus4 (X-Plus 4, CoreXY, enclosed, Klipper, direct-drive)
**Slicer:** QIDIStudio (OrcaSlicer fork)
**Filament:** Elegoo Rapid PETG, 1.75 mm
**Companion file:** `Elegoo Rapid PETG @QIDI Plus4.json` (importable QIDIStudio/OrcaSlicer profile)

> **Read first:** This document builds on the generic Elegoo Rapid PETG brief at `elegoo_rapid_petg_settings.md`. Only the Plus4-specific changes and additions are covered here. If you haven't read that file, start there.

---

## 1. What Changes vs. the Generic Brief — Quick Table

| Parameter | Generic Brief | Plus4 Adjustment | Why |
|---|---|---|---|
| **Chamber temp** | Open frame fine; keep ambient ≤ 35 °C | **Chamber OFF for PETG** (set `chamber_temperatures` = 0 in profile); run circulation fan P3 at 100% | Chamber heat causes heat creep and stringing on PETG (see Section 2) |
| **Hotend temp — first layer** | 245–250 °C | 245 °C (start here; run a temp tower) | Same sweet spot; Plus4's 80W bimetal hotend holds temp accurately |
| **Hotend temp — other layers** | 240–250 °C | 240–245 °C | Enclosed cabinet retains ambient warmth; slightly lower end of range reduces stringing risk |
| **Max volumetric speed** | ≤ 18 mm³/s (standard 0.4 brass) | **18–24 mm³/s starting ceiling (test up to 28)** | Plus4's 80W bimetal hotend outperforms standard brass 0.4; QIDI Rapido PETG profile ships at 18; verify via MVS calibration |
| **Print speed — outer wall** | 60–150 mm/s quality | **150 mm/s quality / 200 mm/s draft** | Community tested SUNLU Rapid PETG at 300 mm/s outer with clean results; 150–200 mm/s is a sane starting quality target |
| **Print speed — inner walls / infill** | Up to ~250 mm/s | **200–300 mm/s** | CoreXY motion + high-flow hotend handles it well |
| **Retraction — first layer** | 0.8 mm @ 45 mm/s | Same starting point | Direct-drive; identical to generic brief |
| **Pressure advance** | ~0.04–0.06 (calibrate) | **0.056 starting value** (QIDIStudio Generic PETG @X-Plus 4 shipped value) | QIDI's factory value for this machine + 0.4 nozzle is 0.056 |
| **Bed temp** | 85 °C first layer / 80 °C | **80 °C first layer / 80 °C** | Textured PEI on Plus4 grips PETG well; no glue needed; 80 °C sufficient |
| **First-layer speed** | 20–30 mm/s | **20–25 mm/s** | Same logic; Plus4's enclosed cabinet doesn't change this |
| **Fan — first 3 layers** | 0% (first layer) | 0% for layers 1–3 (`close_fan_the_first_x_layers: 3`) | QIDI PETG profiles all use 3-layer fan suppression |
| **Fan — running** | 30–50% | **20–40% min / 90% max** (matches QIDI Rapido profile) | Enclosed chamber = less ambient cooling; go conservative, raise if bridging is poor |

---

## 2. Chamber Heating for PETG on the Plus4

**Recommendation: Chamber = OFF for PETG.** Set `chamber_temperatures` to 0 (or leave the field out of the filament profile, which QIDIStudio treats as 0).

### Why not use the chamber for PETG?

The Plus4's chamber reaches up to ~60–65 °C. That temperature range is excellent for ABS, ASA, PC, and fiber-filled engineering materials. For PETG it creates two problems:

1. **Heat creep.** PETG's glass transition starts around 70 °C, but the filament begins to soften noticeably above 50–55 °C. A 60 °C chamber raises the temperature of the filament path between the extruder gears and the heatbreak, softening the filament before it reaches the melt zone. The result is grinding, clogging, and inconsistent extrusion — especially on longer prints and during retractions. The qidi-community Plus4-Wiki explicitly flags this: *"For PLA and PETG printing, heat creep from the heated chamber can cause nozzle clogging."*

2. **Increased stringing.** A hot ambient environment keeps the PETG semi-molten during travel moves longer than it needs to be. More stringing and ooze, especially at bridges and crossing moves.

### What to do instead

- Set chamber temp to 0 in the filament profile (no `chamber_temperatures` key = off).
- Run the **circulation fan (P3) at 100%** during PETG prints. This is what the Plus4's Klipper start macro does automatically when `chambertemp == 0` is detected: `M106 P3 S255`. It prevents passive heat buildup from the heated bed from warming the chamber above ambient.
- The enclosed cabinet still provides a **draft-free** environment, which is beneficial — PETG doesn't like cold drafts across the print either. Enclosure draft-free, chamber heater off = ideal.

### The "slightly warm chamber" option

If you want to pre-warm to ~30–35 °C (not using the heater — just letting the heated bed warm the enclosure passively for 5–10 minutes before starting), that's fine. This is not chamber heating; it's just letting the enclosure equilibrate. Don't exceed 40 °C ambient for PETG.

---

## 3. High-Flow Hotend — Realistic MVS on the Plus4

The Plus4's **second-gen 80W bimetal hotend** with integrated throat design is a meaningful step up from a standard V6-style brass 0.4. It is not a "volcano" or high-flow nozzle in the Bambu HF sense — it's a standard 0.4 mm orifice — but the 80W heater, bimetal construction, and integrated throat mean it can maintain set temperature at higher flow rates than a 40W standard hotend.

**Reasonable expectations for Elegoo Rapid PETG:**

| Scenario | Max Volumetric Speed | Notes |
|---|---|---|
| **Starting ceiling (before calibration)** | 18 mm³/s | The QIDI Rapido PETG profile ships at 18; safe starting point |
| **Expected calibrated ceiling** | 22–26 mm³/s | Based on the 80W hotend's thermal mass advantage over standard 40W; community reports 200–300 mm/s PETG speeds which implies ~20–28 mm³/s at 0.2 mm layer height |
| **Do not exceed without testing** | 28 mm³/s | Above this, even the bimetal hotend risks thermal lag with PETG (lower melt index than ABS) |

**Always run the MVS calibration in QIDIStudio** (Calibration → Max Volumetric Speed) to find your actual ceiling. The filament profile ships at 18 mm³/s as a conservative start — raise it after calibration.

---

## 4. Print Speeds — What's Achievable

CoreXY + high-flow hotend + Klipper input shaping = legitimate high-speed PETG is possible on the Plus4. Based on the 3dwithus.com review testing (SUNLU Rapid PETG at 300 mm/s inner walls with no visible flaws) and community reports:

| Speed Profile | Outer Wall | Inner Wall | Infill | First Layer | Travel |
|---|---|---|---|---|---|
| **Quality** | 100–150 mm/s | 200 mm/s | 200 mm/s | 20–25 mm/s | 300 mm/s |
| **Speed / Draft** | 200 mm/s | 300 mm/s | 300 mm/s | 20–25 mm/s | 400 mm/s |

**Practical note:** The first-layer speed is non-negotiable regardless of profile — PETG needs that slow first pass for adhesion. Everything after layer 1 is where the Plus4's speed advantage shows.

**Input shaping disclaimer:** Run QIDIStudio's resonance/input shaping calibration before pushing outer walls above 200 mm/s. Ringing artifacts become visible at high outer wall speeds on any printer if input shaping isn't dialled for the specific machine state (belt tension, any modifications). This is not filament-specific — it's machine calibration. See Section 5.

---

## 5. Retraction, Z-Hop, and Pressure Advance on the Plus4

### Retraction

QIDIStudio's Generic PETG and QIDI Rapido profiles **do not set filament-level retraction** (`filament_retraction_length` is absent). Retraction on QIDI printers is handled at the **machine/printer profile level**, not the filament level. This is correct OrcaSlicer behavior — the printer profile sets retraction defaults, and the filament profile only overrides if needed.

**Starting retraction values (set in the printer profile or process profile):**
- Retraction distance: **0.5–0.8 mm** (direct-drive; start at 0.8, back off if grinding)
- Retraction speed: **35–45 mm/s**
- Z-hop: **0.2 mm** (important for PETG to prevent nozzle drag-stringing)

### Pressure Advance

The Plus4 runs Klipper — the setting is called **Pressure Advance** (not Linear Advance). QIDIStudio surfaces it in the filament profile.

- **QIDI's shipped value** for Generic PETG @X-Plus 4 0.4 nozzle: **0.056**
- **QIDI PETG Rapido @X-Plus 4** (closest analogue to Elegoo Rapid PETG, a fast-flow PETG): **0.054**
- **Starting value for this profile:** `0.055` (midpoint between the two)

This is a reasonable starting number for Elegoo Rapid PETG on the Plus4's 0.4 nozzle. **Run QIDIStudio's Pressure Advance calibration** (Calibration → Pressure Advance) to refine it. The difference between 0.045 and 0.065 shows up as blobs or pulled corners — it's worth 10 minutes to nail down.

**Note:** QIDIStudio does not offer automatic pressure-advance pre-calibration for PETG (it's not in the list of materials that support automatic PA lookup). Manual calibration via the tower or QIDIStudio's calibration wizard is the path.

### Input Shaping / Resonance Calibration

One-liner: run QIDIStudio's **Input Shaping / Resonance Compensation** calibration once after setup and after any significant hardware change (new belt tension, different nozzle, modifications). This is machine-level, not filament-specific, but it directly determines how fast you can push outer walls before ringing artifacts appear. The Plus4 ships with input shaping pre-tuned from the factory; re-run it if you've done any hardware modifications.

---

## 6. Bed and First Layer

The Plus4 ships with a **dual-sided textured PEI plate** (6mm aluminum substrate). This is the best surface for PETG.

| Parameter | Value | Notes |
|---|---|---|
| **Bed temp — first layer** | 80 °C | QIDI ships all PETG profiles at 80 °C first layer on textured PEI |
| **Bed temp — other layers** | 80 °C | Same; PETG doesn't need a step-down on textured PEI |
| **Glue stick** | Not needed | Textured PEI + PETG = good adhesion and clean release when cool |
| **Removal temp** | Let cool to ≤ 40 °C | Parts will pop off cleanly; do NOT pry while hot |
| **First-layer speed** | 20–25 mm/s | Non-negotiable for PETG regardless of printer speed capability |
| **First-layer height** | 0.25–0.30 mm | Slightly taller first layer for good squish/adhesion |

**Warning that still applies from the generic brief:** If you ever swap in a smooth PEI sheet, PETG will over-adhere aggressively. Always use glue stick as a release agent on smooth PEI. The textured sheet avoids this entirely.

---

## 7. Calibration Order in QIDIStudio

Run these in order before using the profile for real parts. QIDIStudio has a Calibration menu with wizards for most of these.

1. **Dry the filament** — 60 °C for 8 hours. No calibration result is reliable on wet PETG.
2. **Temperature tower** — 255 → 235 °C. Find the zone with cleanest bridges, best surface, least stringing.
3. **Flow rate** — QIDIStudio Calibration → Flow Rate. Profile ships at 0.95; typical result 0.93–0.97.
4. **Pressure Advance** — Calibration → Pressure Advance. Profile starts at 0.055; fine-tune to your specific spool.
5. **Max Volumetric Speed** — Calibration → Max Volumetric Speed. Profile starts at 18 mm³/s; test up to 28 mm³/s. Update profile with your measured result.
6. **Retraction test** — Print a two-tower stringing test. Tune retraction distance in 0.2 mm increments.

---

## 8. Importing the Filament Profile JSON

The companion file `Elegoo Rapid PETG @QIDI Plus4.json` is a ready-to-import QIDIStudio filament preset.

**Step-by-step import:**

1. Open **QIDIStudio**.
2. At the top of the screen, locate the **Filament** dropdown (shows the current filament preset).
3. Click the **gear/settings icon** next to the filament dropdown, or open **File → Import → Import Configs**.
4. In the dialog, navigate to the location of `Elegoo Rapid PETG @QIDI Plus4.json` and select it.
5. QIDIStudio will confirm the import. The profile will appear under **User Presets** in the filament list.
6. Select **"Elegoo Rapid PETG @QIDI Plus4"** from the filament dropdown.
7. **Confirm the compatible printer:** The profile is set to `"X-Plus 4 0.4 nozzle"`. If QIDIStudio shows the profile as incompatible, open the filament editor and verify your loaded machine profile matches that name exactly (Settings → Printer → profile name in the title bar).

**After importing — calibrate before trusting:**
The profile is a starting point, not a final answer. The values in it are the best available estimates for this machine + filament combination. After importing, run the calibration order in Section 7 and save your measured values back into the profile (Edit → save changes to user preset).

---

## 9. Concerns / Honest Caveats

1. **`compatible_printers` string.** The profile uses `"X-Plus 4 0.4 nozzle"` — verified directly from QIDIStudio's installed profiles on this machine. If QIDIStudio shows the profile as incompatible or hidden, open the filament editor and check Settings → Printer to confirm your machine's exact profile name. The name must match the machine profile name character-for-character.

2. **MVS ceiling is unverified for Elegoo Rapid PETG specifically.** The 18 mm³/s starting value is taken from QIDI's own Rapido PETG profile. The QIDI Rapido is a similar fast-flow PETG formulation; Elegoo Rapid may behave slightly differently. Run the MVS calibration and update the profile.

3. **Pressure advance = starting ballpark.** 0.055 is the midpoint between QIDI's Generic PETG and Rapido PETG values for this machine. Spool-to-spool variation in Elegoo Rapid PETG means this number should always be verified by running a PA calibration tower.

4. **QIDIStudio version dependency.** Profile format is based on QIDIStudio as of 2026-05-12. If QIDI ships a major slicer update that changes the profile schema, some keys may need updating. Check the `from: "User"` and `instantiation: "true"` flags are preserved.

5. **Chamber temperature = 0 by design.** The profile does not set the `chamber_temperatures` key. On QIDIStudio, this defaults to chamber off. If you accidentally enable the chamber heater via the printer interface during a PETG print, turn it off and max the circulation fan.

---

## 10. Sources

All information verified 2026-05-12.

- [QIDI Plus4 Official Product Page](https://qidi3d.com/products/plus4-3d-printer) — hotend 370 °C max, 80W bimetal, integrated throat design, dual-sided textured PEI, 600 mm/s max speed, 65 °C chamber
- [QIDI Plus4 Technical Specifications](https://us.qidi3d.com/pages/qidi-plus-4-techspecs) — confirmed: chamber "2nd Gen Up to 65 °C Independent Chamber Heating", direct drive, hardened steel gears, bimetal nozzle, 120 °C bed max
- [3dwithus.com QIDI Plus4 Review](https://3dwithus.com/qidi-plus4-review-3d-printer-tests-tips-and-settings) — community review testing SUNLU Rapid PETG at 300 mm/s inner wall with clean results; plus4 speeds achievable
- [qidi-community Plus4-Wiki — Thermal Management (DeepWiki)](https://deepwiki.com/qidi-community/Plus4-Wiki/4-thermal-management) — confirms heat creep risk for PLA/PETG in heated chamber; exhaust fan P3 = max when chambertemp = 0
- [qidi-community Plus4-Wiki — Chamber Heater Investigation (GitHub)](https://github.com/qidi-community/Plus4-Wiki/blob/main/content/chamber-heater-investigation/README.md) — chamber sensor accuracy and heater behavior
- [QIDI Wiki — Pressure Advance Calibration](https://wiki.qidi3d.com/en/software/qidi-slicer/calibration/Pressure-advance) — confirms PETG is not in the auto-calibration list; manual PA calibration required
- [Klipper Pressure Advance Documentation](https://www.klipper3d.org/Pressure_Advance.html) — authoritative reference on PA tuning methodology
- [QIDIStudio installed profiles — X 4 Series filament folder](file:///Applications/QIDIStudio.app/Contents/Resources/profiles/X%204%20Series/filament/) — source for: compatible_printers string `"X-Plus 4 0.4 nozzle"`, Generic PETG@X4 base values (nozzle 245/250, bed 80, fan 40–90%, fan suppress 3 layers, MVS 12, PA 0.056), QIDI PETG Rapido@X4 values (nozzle 250/250, MVS 18, fan 20–40%, PA 0.054, slow_down_layer_time 8)
- [Elegoo Rapid PETG generic brief](elegoo_rapid_petg_settings.md) — base filament specs, drying protocol, and general calibration reference
