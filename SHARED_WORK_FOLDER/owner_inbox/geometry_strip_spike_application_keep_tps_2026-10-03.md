# v0.16 — Strip Gaussian Spike-Application; Keep TPS Harness

**Task 698 · Topo · 2026-10-03**

---

## Audit of Committed-Partial State (what was there, what remained)

The HEAD at the start of this session (`cb4c7a4`) had:

- Header updated to `# v0.15` with correct intent comments.
- `_build_tps_base()` already had `elevation_spikes_mm` marked deprecated in its docstring and emitting a log notice when a non-empty list was passed.
- The `_raw_spikes_early` / `_tps_spikes` **collector** block (lines 3574-3588) was still present — feeding spikes into the TPS call site.
- The `_build_tps_base` call site still passed `elevation_spikes_mm=_tps_spikes`.
- The entire Gaussian bump loop (`SPIKE_SIGMA_MM`, `SPIKE_INFLUENCE_MM`, `SPIKE_HARD_MAX_MM`, the `_raw_spikes` for-loop, `_skipped_in_green` counter, Gaussian MAX-blend over fringe cells, seam override updates, spike peak report) was intact at lines 4084–4257.
- The post-filter FINAL spike-scan with spike-exclusion mask was intact.
- 2 of 7 SA tests were failing (SA2 + SA7) because the Gaussian bump loop was still active.

**Net: the strip was ~30% done. The hardest piece — the actual Gaussian loop — remained.**

---

## What Was Removed

All of the following were deleted from `app/gradient_surface_diagnostic.py`:

| Deleted artefact | Location (pre-strip) |
|---|---|
| `_raw_spikes_early` / `_tps_spikes` collector block | ~lines 3574-3588 |
| `elevation_spikes_mm=_tps_spikes` in `_build_tps_base` call | line 3595 |
| `# ── User-placed elevation spikes` comment block (big header) | ~lines 4084-4136 |
| `from shapely.geometry import Point as _SpikeShapelyPoint` import | line 4137 |
| `_raw_spikes = egm_data.get(...)` | line 4138 |
| `SPIKE_SIGMA_MM = 8.0` | line 4139 |
| `SPIKE_INFLUENCE_MM = 3.5 * SPIKE_SIGMA_MM` | line 4140 |
| `SPIKE_HARD_MAX_MM = 50.0` | line 4141 |
| `spike_touched_cells`, `spike_seam_cells`, `spikes_mm` vars | lines 4142-4144 |
| `_skipped_in_green` counter + print | lines 4146, 4167-4170 |
| Full Gaussian MAX-blend loop over fringe cells | lines 4172-4228 |
| `_seam_updated` dict + seam fold-back | lines 4178, 4209 |
| Spike peak report print loop | lines 4211-4228 |
| `_mask_for_scan` spike-exclusion branch of FINAL spike-scan | lines 4240-4253 |

The FINAL spike-scan is **kept** but simplified: it now always runs the no-spikes branch (unconditional `_count_fringe_spikes` on `Z_final_top + seam_override`).

---

## What Stayed

Every non-spike pipeline is untouched:

| Component | Status |
|---|---|
| `_build_tps_base()` | Kept. Signature unchanged. 16-point outer-frame base ring intact. |
| TPS call site in `build_fringe_mesh` | Kept. Now passes `elevation_spikes_mm=[]` explicitly. |
| Poisson green interior (slope-arrow integration) | Kept. |
| Trap curved surface (nearest-neighbor fringe boundary, −2 mm offset) | Kept. |
| Rake lines, sand chunks, dip-floor guard, water flat slab | Kept. |
| Water-hole lift, frame-cap suspension, seam-reseat | Kept. |
| 16-point outer-frame base ring | Kept inside `_build_tps_base`. |
| Mask-aware median spike filter (3×3 + 5×5 escalation) | Kept (kills interpolation artifacts, not user spikes). |
| FINAL diagnostic fringe spike-scan | Kept (simplified — no exclusion mask needed). |

---

## Signature-Stable Deprecation Notes

### `_build_tps_base(elevation_spikes_mm=...)` — **deprecated, ignored**

- Parameter still accepted; contents silently ignored.
- If a non-empty list is passed, prints:
  `[TPS] DEPRECATED: elevation_spikes_mm passed (N item(s)) but ignored — spike-application pipeline removed in task 698.`
- Call site now passes `elevation_spikes_mm=[]` so the notice is suppressed in normal operation.
- Mirrors the `fringe_boundary_heights_mm` deprecation pattern from task 690.

### `build_fringe_mesh` EGM `elevationSpikes` field — **deprecated, ignored**

- If the EGM dict contains `elevationSpikes` with ≥1 item, prints:
  `[fringe] DEPRECATED: EGM contains N elevationSpikes item(s) — spike-application pipeline removed in task 698.`
- No Gaussian bumps are applied. No crash.

### Comment block near `_build_tps_base`

```
# Current state (task 698, 2026-10-02):
#   Currently only outer-frame base points feed the TPS fit → surface is flat
#   at BASE_THICKNESS_MM.  The spike_application + fringe_boundary_heights
#   pipelines were removed on 2026-10-02 (Thomas pivot — slope-arrow Poisson
#   green surface + manual fringe-height mechanism coming).
#   Future mechanism will feed additional height constraints via a NEW argument
#   or a NEW source — keep the TPS primitive ready for that work.
```

---

## Red → Green Table: `test_strip_spike_application.py`

| Test | Pre-strip | Post-strip |
|---|---|---|
| SA1 `test_empty_spikes_no_bumps` | GREEN (was already passing) | GREEN |
| SA2 `test_spike_in_egm_no_bump_peak` | **RED** | **GREEN** |
| SA3 `test_tps_callable_empty_inputs` | GREEN | GREEN |
| SA4 `test_green_z_varies_with_slope_arrows` | GREEN | GREEN |
| SA5 `test_zero_extra_constraints_builds` | GREEN | GREEN |
| SA6 `test_spike_constants_not_at_module_level` | GREEN | GREEN |
| SA7 `test_spikes_ignored_in_fringe_pipeline` | **RED** | **GREEN** |

**7/7 passing.** Full suite: 442 passed / 34 failed / 20 skipped (was 440/36/20 — net +2 passing, 0 new failures).

The 34 pre-existing failures are all in Sienna's parallel T5 work (editor.html spike UI removal, OCR module deletion, app version badge tests) and 3 TPS interior-spike tests that were already failing before this session.

---

## Test Drive for Thomas

Regenerate any hole (e.g. Delaveaga H5):

1. Open Boundary Editor → load `Delaveaga (Hole 5, 55169).egm`.
2. Hit Generate.
3. **Expected**: green topology still shaped by slope arrows (Poisson). Fringe is near-flat at `BASE_THICKNESS_MM` (≈1.5 mm) — TPS has only the 16-point frame ring. No localized bumps anywhere, even if the EGM has leftover `elevationSpikes` entries.
4. Console will print `[fringe] DEPRECATED: EGM contains N elevationSpikes item(s)...` if old spikes are in the file — informational only, no effect on geometry.
5. No crash. Mesh watertight. Same trap/rake/water behaviour as before.

---

## Version Bumps

| File | Field | Old | New |
|---|---|---|---|
| `app/gradient_surface_diagnostic.py` | header `# v0.NN` | v0.15 | **v0.16** |
| `app/app.py` | `APP_VERSION` | v4.97 | **v4.98** |

---

## Follow-Up: When Grid-Cell Mechanism Arrives

Feed `(cell_center_x_mm, cell_center_y_mm, z_mm)` constraints into `_build_tps_base()` via a new `grid_cell_heights_mm` parameter (mirrors the pattern of `fringe_boundary_heights_mm`). The TPS infrastructure is ready — just add constraints to the existing `all_constraints` list inside `_build_tps_base`.
