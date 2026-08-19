# Boundary Editor — Fringe Frame Cap Toggle

**Task:** 669
**Delivered by:** Sienna
**Date:** 2026-08-19
**New APP_VERSION:** `v4.15` (was `v4.14`)

## What shipped

A generation-time checkbox that lets you disable the fringe-cap clip on
water holes when you want the fringe to rise to its natural terrain height
even where that exceeds the plaque frame.

## Checkbox

- **Label:** `Cap fringe at frame height`
- **Header:** `Fringe cap` (uppercase micro-label above)
- **Helper text:** `Prevents the fringe from rising above the plaque frame near the edges (water holes only).`
- **Tooltip:** `On water holes, clip fringe top vertices near the frame perimeter so the fringe never rises above the frame. Uncheck to let the fringe rise to its natural height (may exceed the frame).`
- **Default:** **checked** (feature ON — preserves legacy behavior exactly).
- **Placement:** `app/templates/editor.html`, in the generation-controls row,
  directly to the right of the existing `Boundary region` checkbox.

## Payload / .egm field

- **Name:** `applyFringeFrameCap` (camelCase, matches JS conventions)
- **Round-trip:** included in the `autoSave()` payload posted to
  `/api/boundaries`, which JSON-dumps the whole payload into the `.egm`
  file — so it persists automatically.
- **Legacy .egm handling:** any `.egm` that lacks the key is treated as
  **True** on load in three places, so historical projects behave
  identically to today:
  1. `editor.html` `loadProject()`: `data.applyFringeFrameCap !== false`
  2. `app.py` `/api/generate_models`: `bool(data.get("applyFringeFrameCap", True))`
  3. `gradient_surface_diagnostic.py` `run_pipeline()`:
     `bool(_egm_data.get("applyFringeFrameCap", True))`

## Fringe call-site identified

**Line 5854** (label=`"fringe"`) in
`app/gradient_surface_diagnostic.py`, inside the `# ── 7c. Water-hole rule`
block of `run_pipeline`. The other three `_apply_lift_and_cap` calls are
NOT touched:

| Line | Label           | Role                                        | Gated? |
|------|-----------------|---------------------------------------------|--------|
| 3459 | `trap_<i>`      | Sand-trap lift + boundary cap (water holes) | no     |
| 5843 | `green_smooth`  | Green lift only (`cap_mm=None`)             | no     |
| 5848 | `green_stepped` | Green lift only (`cap_mm=None`)             | no     |
| 5854 | `fringe`        | **Fringe lift + boundary cap**              | **yes** |

Fringe context snippet (post-change):

```python
# Fringe: ALWAYS touches the frame by construction → lift + cap
# (cap gated by applyFringeFrameCap — task 669).
if isinstance(fringe_mesh, trimesh.Trimesh):
    _fringe_cap = BOUNDARY_HEIGHT_CAP_MM if apply_fringe_frame_cap else None
    _fringe_label = "fringe" if apply_fringe_frame_cap else "fringe (cap disabled)"
    _apply_lift_and_cap(
        fringe_mesh, lift_mm=WATER_HOLE_LIFT_MM,
        cap_mm=_fringe_cap, label=_fringe_label,
    )
```

Note: when the cap is disabled, the water-hole *lift* still applies (fringe
still sits on the 2 mm base slab). Only the per-vertex boundary-band clip is
skipped, which is exactly what the request called for. `_apply_lift_and_cap`
already supports `cap_mm=None` as a first-class no-op (that's what the two
green calls use), so this required no signature change.

## Route wiring

`/api/generate_models` reads `applyFringeFrameCap` from the JSON payload
(default `True`) and forwards it to `run_pipeline(...,
apply_fringe_frame_cap=...)`. `run_pipeline` grew a new
`apply_fringe_frame_cap: bool | None = None` parameter with the same
three-way resolution pattern used by `include_boundary_region`:
caller override > EGM value > default (True).

## Files changed

- `app/app.py` — `APP_VERSION` bump; `/api/generate_models` reads flag and
  forwards.
- `app/gradient_surface_diagnostic.py` — `run_pipeline` signature and
  resolution; fringe call-site gate at line ~5854.
- `app/templates/editor.html` — checkbox UI; state field; autoSave payload;
  generate payload; loadProject legacy-default; startNewProject reset.

## Verification

Ran `scratch/task_669_verify.py` — **7/7 tests pass**:

- `test_explicit_true_forwarded` — POST with `applyFringeFrameCap: true` →
  `run_pipeline` receives `apply_fringe_frame_cap=True`.
- `test_explicit_false_forwarded` — POST with `applyFringeFrameCap: false` →
  `run_pipeline` receives `apply_fringe_frame_cap=False`.
- `test_missing_defaults_true` — legacy client omits the key → route
  defaults to `True`.
- `test_legacy_egm_default` — legacy EGM (no key) resolves to `True`.
- `test_egm_explicit_false` — EGM with `False` resolves to `False`.
- `test_caller_override_wins` — explicit caller value overrides EGM value
  AND is persisted back into `_egm_data`.
- `test_version` — `APP_VERSION == "v4.15"`.

Test harness uses a temp workspace DB
(`/var/folders/…/task669_/workspace.db`) per
`feedback_verifications_never_touch_live_db`. The live `db/workspace.db`
mtime was unchanged by the test run (verified via `stat`).

## Regression posture

With the default `applyFringeFrameCap: true`, the fringe call site behaves
byte-identically to before this change (same `cap_mm=BOUNDARY_HEIGHT_CAP_MM`,
same `label="fringe"`, same lift). No existing project will render
differently unless the user deliberately unchecks the box.

## For Thomas & Jim

The checkbox is on the same row as `Boundary region`. Uncheck it when a
water-hole fringe is being aggressively clipped at the frame and you want
to see the un-capped natural terrain. Save-and-reload keeps your choice per
project. To go back to legacy behavior, re-check the box — done.
