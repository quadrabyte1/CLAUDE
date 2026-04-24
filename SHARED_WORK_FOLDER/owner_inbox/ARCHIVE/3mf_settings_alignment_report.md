# 3MF Slicer Settings Alignment Report

**Prepared by:** Topo (3D Modeling / Computational Geometry Specialist)  
**Date:** 2026-04-14  
**Reference file:** `team_inbox/Matt (with bambu slicer settings dialed in).3mf`  
**Template updated:** `team_inbox/Mike Kallbrier.3mf`

---

## Summary

The Matt reference file's dialed-in Bambu Studio slicer settings have been successfully embedded into our 3MF generation pipeline. All generated nameplate 3MF files will now carry the same `project_settings.config` as the Matt reference.

---

## Settings Found in the Matt Reference File

These are the key print profile settings embedded in `Metadata/project_settings.config`:

### Print Profile
| Setting | Value |
|---------|-------|
| Profile name | `◀ Elegoo PLA -- BambuLab A1` |
| Printer | Bambu Lab A1, 0.4 mm nozzle |
| BambuStudio version | 02.05.03.61 |
| Layer height | 0.2 mm |
| Initial layer height | 0.3 mm |
| Wall loops | 2 |
| Top shell layers | 4 |
| Bottom shell layers | 3 |
| Sparse infill density | 15% |
| Sparse infill pattern | Grid |
| Top surface pattern | Monotonic Line |
| Bottom surface pattern | Monotonic |
| Ironing | No ironing |
| Seam position | Aligned |

### Line Widths
| Setting | Value |
|---------|-------|
| Default line width | 0.42 mm |
| Outer wall | 0.42 mm |
| Inner wall | 0.45 mm |
| Top surface | 0.45 mm |
| Initial layer | 0.5 mm |

### Speeds (mm/s)
| Setting | Value |
|---------|-------|
| Outer wall | 70 |
| Inner wall | 140 |
| Sparse infill | 200 |
| Top surface | 200 |
| Internal solid infill | 200 |
| Initial layer | 25 |
| Travel | 700 |
| Bridge | 50 |

### Temperatures (5-slot AMS)
| Setting | Value |
|---------|-------|
| Nozzle (all slots) | 220°C |
| Nozzle initial layer | 220°C |
| Hot plate (slots 1,2,4,5) | 65°C |
| Hot plate (slot 3 - Overture white) | 55°C |
| Textured plate | Same as hot plate |

### Accelerations
| Setting | Value |
|---------|-------|
| Default | 6000 mm/s² |
| Outer wall | 5000 mm/s² |
| Inner wall | 0 (uses default) |
| Top surface | 2000 mm/s² |
| Initial layer | 500 mm/s² |

### Support & Brim
| Setting | Value |
|---------|-------|
| Supports enabled | Yes |
| Support type | Tree (auto) |
| Brim type | Auto brim |
| Brim width | 5 mm |

### Filament (5-slot AMS)
| Slot | Filament | Colour |
|------|----------|--------|
| 1 | Generic PLA @BBL A1 | #18DC41 (green) |
| 2 | eSUN PLA+ @BBL A1 | #10A331 (dark green) |
| 3 | Overture PLA @BBL A1 | #FFFFFF (white) |
| 4 | Bambu PLA Basic @BBL A1 | #0085D5 (blue) |
| 5 | Generic PLA @BBL A1 | #000000 (black) |

---

## What Our Code Currently Produced

`app/plate_text.py` generates 3MF files by:
1. Extracting the Mike Kallbrier template (`team_inbox/Mike Kallbrier.3mf`)
2. Patching geometry (text meshes, border frame)
3. Patching `Metadata/model_settings.config` (text content)
4. Re-zipping all files — including `Metadata/project_settings.config` unchanged from the template

The Mike Kallbrier template's `project_settings.config` was **already identical** to the Matt reference on all print-quality settings (all 62 critical settings matched). The only differences were:
- BambuStudio version number: `02.05.00.66` vs `02.05.03.61`
- 21 newer firmware-specific keys added in the newer BambuStudio version (fan speed sequencing, filament mixed-material fields, fuzzy skin parameters, etc.)

---

## Changes Made

**One change only:** Replaced the `Metadata/project_settings.config` inside the Mike Kallbrier template with the Matt reference's `project_settings.config`.

- **File modified:** `team_inbox/Mike Kallbrier.3mf`
- **Backup created:** `team_inbox/Mike Kallbrier_backup_before_settings_update.3mf`
- **Result:** Template now carries 559 settings (was 538), version `02.05.03.61` (was `02.05.00.66`)
- **Code changes:** None — `plate_text.py` already passes `project_settings.config` through from the template intact

No changes were needed to `app/plate_text.py` or any other Python file. The architecture was already correct — the fix was updating the template file.

---

## Verification

A test 3MF was generated and verified:

```
[plate_text] Rendering line 1: 'Test Line 1'
[plate_text] Rendering line 2: 'Test Line 2'
[plate_text] Rendering line 3: 'Test Line 3'
[plate_text] Building border mesh
[plate_text] Written: /tmp/test_plate_output.3mf
[plate_text] Verification OK — 5 objects, 21440 total faces
```

All 21 critical settings verified as matching the Matt reference exactly, including version `02.05.03.61`.

---

## Notes

- The filament colors/types in `project_settings.config` reflect a 5-slot AMS setup from the Matt nameplate. These are slicer-assigned per object and can be reassigned in BambuStudio without re-generating the file.
- The `app/generate_stl_3mf.py` (terrain/green model generator) does not write `project_settings.config` — it uses trimesh's scene export which produces minimal 3MF. That file is separate from the nameplate pipeline and was not modified.
