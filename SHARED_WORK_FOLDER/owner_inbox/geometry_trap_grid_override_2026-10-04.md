# v0.20 — Trap Altitude Grid-Cell Override

**Topo · Task 716 · 2026-10-05**

---

## Default + Override Rule

**Default (unchanged):** `trap_Z = min(fringe boundary Z along trap perimeter) − 2.0 mm`

This rule fires any time no user-set grid cells fall inside the trap polygon.

**Override:** If one or more blue-dot grid cells (from `gridCellHeights` in the EGM) have their cell centre fall **inside** the trap polygon, `trap_Z = mean(those cell values)` — a flat scalar, same as default.

The trap top stays **flat** in both cases. Only the Z value changes.

---

## Mean-of-Multiple Policy

When more than one set cell falls inside a trap, the override value is `np.mean([values])`. This avoids bias toward either the highest or lowest point. Thomas can later request max / min / first-found; the single call site in `_trap_grid_override` makes that a one-line change.

---

## Shapely `contains` Strict-Interior Behaviour

The containment check uses `ShapelyPolygon.contains(Point(cx, cy))`. Shapely's `contains` is strict interior — a point exactly on the polygon boundary returns `False`. Cell centres that land exactly on the trap outline are excluded. In practice this edge case is rare since the 20×20 grid cell size (~9 mm) is large relative to any trap boundary fluctuation.

---

## Code Change Summary

### New helper — `_trap_grid_override`

Location: `app/gradient_surface_diagnostic.py`, inserted just before `_compute_trap_height_from_fringe` (~line 5634).

```python
def _trap_grid_override(
    trap_poly_mm, grid_cell_heights, cell_side, half, grid_size=20
) -> float | None:
```

- Iterates only SET cells (keys present in `gridCellHeights`).
- Computes cell centre: `cx = -half + (col+0.5)*cell_side`, `cy = -half + (row+0.5)*cell_side`
- Tests `trap_poly_mm.contains(Point(cx, cy))`
- Returns `float(np.mean(hits))` or `None`

### Call site — `export_trap_stls`, flat-mode path

After `trap_height` is determined from fringe (either path), in the `if not TRAP_SURFACE_CURVED:` block:

```python
_gch = egm_data.get("gridCellHeights") or {}
_grid_half = PRINT_SIZE_MM / 2.0 + FRINGE_XY_EXPANSION_MM / 2.0
_grid_cell_side = (2.0 * _grid_half) / 20
_grid_override = _trap_grid_override(shapely_trap, _gch, _grid_cell_side, _grid_half)
if _grid_override is not None:
    trap_height = _grid_override
    _trap_base_z_map = None
```

`egm_data` is already the first parameter of `export_trap_stls`, so no extra pass-through is needed.

---

## Preserved Pipelines

- Rake lines (cosine wave, fixed Y-axis) — unchanged
- Flat default rule (`TRAP_SURFACE_CURVED=False`) — unchanged, fires when no cells inside
- Curved path (`TRAP_SURFACE_CURVED=True`) — unchanged, override not applied on that path
- Trap frame-cap suspension (`BOUNDARY_HEIGHT_CAP_ENABLED=False`) — unchanged
- Water-hole lift (`WATER_HOLE_LIFT_MM`) — unchanged
- Fringe TPS grid-cell surface (task 704) — unchanged
- Poisson green surface — unchanged
- Water flat slab — unchanged

---

## Red → Green Table

| # | Test | Description | Result |
|---|------|-------------|--------|
| TG1a | `TestNoOverrideCells::test_empty_grid_cell_heights_returns_none` | Empty dict → None | RED → GREEN |
| TG1b | `TestNoOverrideCells::test_no_cells_inside_trap_returns_none` | All set cells outside → None | RED → GREEN |
| TG2 | `TestSingleOverrideCell::test_single_inside_cell_returns_its_value` | One inside cell = 7 mm → 7.0 | RED → GREEN |
| TG3 | `TestMultipleOverrideCells::test_two_inside_cells_returns_mean` | 6 mm + 8 mm → mean = 7.0 | RED → GREEN |
| TG4 | `TestOutsideCellsIgnored::test_outside_cell_does_not_trigger_override` | 7 mm inside + 99 mm outside → 7.0 | RED → GREEN |
| TG5 | `TestUnsetCellsNotTrigger::test_unset_cells_do_not_trigger_override` | Large trap, empty dict → None | RED → GREEN |
| TG6 | `TestMultiTrap::test_two_traps_independent_overrides` | Trap A=5.0, Trap B=9.0 | RED → GREEN |
| TG7 | `TestBoundaryEdgeExcluded::test_cell_on_boundary_excluded` | Centre on edge → excluded → None | RED → GREEN |
| TG8 | `TestRakeRegressionAfterOverride::test_rake_visible_after_override` | Rake spread ≥ 0.10 mm after override | PASS (pre-existing) |
| TG9a | `TestRegressionFrameCapAndWaterLift::...boundary_cap...` | Constant still accessible | PASS (pre-existing) |
| TG9b | `TestRegressionFrameCapAndWaterLift::...water_lift...` | Constant still accessible | PASS (pre-existing) |
| TG9c | `TestRegressionFrameCapAndWaterLift::...fringe_offset...` | TRAP_FRINGE_OFFSET_MM = -2.0 | PASS (pre-existing) |
| TG10 | `TestHelperExists::test_trap_grid_override_exists` | Helper callable | RED → GREEN |
| INT | `TestIntegrationOverrideApplied::...` | Full export_trap_stls honours override | RED → GREEN |

**Full suite: 429 passed, 2 pre-existing failures unrelated to this task (hardcoded v5.05 version check).**

---

## Test Drive for Thomas

### Default behaviour (no cells set)

1. Open DeLaveaga H5 in the editor.
2. Hit **Generate** — traps appear at the default altitude (`min fringe Z − 2 mm`).
3. No change from v0.19.

### Override behaviour

1. In the editor, open the 20×20 grid overlay.
2. Click a cell that visually sits inside one of the sand traps (use the trap polygon outline as a guide).
3. Set that cell to **12 mm** (or any value well above the default fringe-min).
4. Hit **Generate**.
5. That trap now sits flat at **12 mm**. Other traps are unchanged.
6. Console will print: `Trap N: grid-cell override active — height X.XX mm → 12.00 mm`

### Multi-trap targeting

- Set a different cell inside each trap to a different height — each trap independently uses its own override.
- Remove the cell value (clear it) — trap reverts to the default fringe-min rule.

---

## Follow-up Options

- **Policy knob:** Mean is the current default. If you want max, min, or first-found, it's a one-line change inside `_trap_grid_override`.
- **Curved-path support:** Override not wired to `TRAP_SURFACE_CURVED=True` yet. Same call site applies if desired.
- **UI badge:** No visual indicator shows which traps are overridden. Could add a coloured dot overlay to the editor if useful.
