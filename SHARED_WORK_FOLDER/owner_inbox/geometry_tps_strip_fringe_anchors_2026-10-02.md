# v0.14 — TPS Strip: fringeBoundaryHeights removed from constraint set

**Topo · task 690 · 2026-10-02**

---

## Why the change

Thomas revealed that the exterior fringe numbers (10, 15, 20, 25, 30 — the labels on the distance rings surrounding the green) are **distance-from-pin markers, not altitudes**. The whole exterior-anchor-as-fringe-height paradigm shipped in v4.81 → v4.91 was semantically wrong. Feeding those numbers as height constraints pulled the TPS surface up to arbitrary altitudes near the green boundary.

After this change the TPS base surface is shaped by:

- Interior `elevationSpikes` — placed by Thomas in the editor, real altitude data
- 16 outer-frame anchors at `BASE_THICKNESS_MM` — keep the surface grounded at the print base

The fringe region between the green edge and the outer frame now interpolates smoothly from whatever the interior spikes dictate down to the base — no exterior distance-ring numbers influencing altitude.

---

## Code change: constraint list diff

`_build_tps_base()` in `app/gradient_surface_diagnostic.py`:

**Before (v0.13):**
```python
# Interior spikes
for sp in elevation_spikes_mm: ...  _add(xy, z)

# Fringe boundary anchors (already snapped by caller)
for fa in fringe_boundary_heights_mm: ...  _add(xy, z)   # ← WRONG: distance markers

# Outer frame anchors
for angle in ...: _add(fxy, BASE_THICKNESS_MM)
```

**After (v0.14):**
```python
# Interior spikes
for sp in elevation_spikes_mm: ...  _add(xy, z)

# Fringe boundary anchors — DEPRECATED (task 690): ignored
if fringe_boundary_heights_mm:
    print("[TPS] DEPRECATED: fringe_boundary_heights_mm ... ignored")

# Outer frame anchors
for angle in ...: _add(fxy, BASE_THICKNESS_MM)
```

---

## Signature-stable deprecation note

`_build_tps_base(fringe_boundary_heights_mm=[...])` still **accepts** the parameter without raising. When the list is non-empty, a deprecation notice is printed to stdout. The parameter will be removed once Sienna's T2 (task 691) strips it from all callers.

`build_fringe_mesh()` still receives `_tps_fbh` from the raw EGM, passes it to `_build_tps_base` — it is silently ignored there. The old `bnd_z` override block (IDW fallback path) still runs but is never the primary height source (TPS is always primary when finite).

---

## Red → green table

| # | Test | File | Behavior tested | RED → GREEN |
|---|------|------|-----------------|-------------|
| StripT1a | `test_fringe_anchor_ignored_spike_drives` | `test_tps_strip_fringe_anchors.py` | fbh=(x,y,50) + spike(0,0,8) → Z at anchor < 20 mm (NOT 50) | RED → GREEN |
| StripT1b | `test_fringe_anchor_ignored_no_spike` | `test_tps_strip_fringe_anchors.py` | fbh=(x,y,50) no spike → Z < 10 mm (BASE-driven) | RED → GREEN |
| StripT2 | `test_interior_spike_honored` | `test_tps_strip_fringe_anchors.py` | spike still honored ≈ 8 mm | GREEN (regression guard) |
| StripT3 | `test_frame_z_near_base` | `test_tps_strip_fringe_anchors.py` | frame ring Z ≈ BASE ± 3 mm | GREEN (regression guard) |
| StripT4 | `test_radial_transect_smooth` | `test_tps_strip_fringe_anchors.py` | 2nd-derivative jump < 2 mm/mm (C² smooth) | GREEN (regression guard) |
| StripT5 | `test_degenerate_flat_surface` | `test_tps_strip_fringe_anchors.py` | 0 spikes + 0 fbh → flat at BASE | GREEN (regression guard) |
| StripT6 | `test_nonempty_fbh_warns_not_raises` | `test_tps_strip_fringe_anchors.py` | non-empty fbh → deprecation printed, no raise | RED → GREEN |

Existing `test_tps_global_height_field.py` tests updated to match new semantics:

| # | Old assertion | Updated assertion |
|---|---------------|-------------------|
| T1 | Z at fbh anchor ≈ 8.0 mm | Z at fbh anchor ≈ BASE (anchor ignored) |
| T6 | fringe top Z near boundary ≈ anchor value | fringe top Z ≥ BASE, finite, spike-driven |
| T9 | co-located fbh → Z ≈ avg(6,10)=8 | co-located interior spikes → Z ≈ avg(6,10)=8 |

---

## Test drive: DeLaveaga H5

With this change, re-exporting DeLaveaga H5 through the boundary editor and generating a 3MF will produce:

- **TPS base surface** shaped purely by any interior elevation spikes Thomas has placed + the 16-point base ring at 1.5 mm
- **Fringe region** interpolates smoothly between the spike-driven green-interior Z and the base — no step, no crease where the old F-badge distance labels used to anchor
- **Trap surface** unchanged: curved nearest-neighbor at fringe boundary, −2 mm offset
- **Deprecation notice** in server log: `[TPS] DEPRECATED: fringe_boundary_heights_mm passed (N item(s)) but ignored` — expected, harmless

If H5 currently has no interior elevation spikes set, the fringe will be flat at `BASE_THICKNESS_MM` (1.5 mm) everywhere — which is the honest answer when there is no altitude data, rather than a surface warped by distance markers.

---

## Version

- `gradient_surface_diagnostic.py` `__version__`: **v0.14**
- `APP_VERSION`: **v4.93** (Sienna landed v4.92 first on task 691)
- Full suite: **385 passed**, 20 skipped, 4 pre-existing Bambu failures (not my zone)
