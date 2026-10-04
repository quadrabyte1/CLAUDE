# Boundary Editor — Grid Cell Elevation Overlay Phase 1

**v1.0 · Sienna · 2026-10-04**

---

## Design Decisions Matched to Memory Spec

| Spec requirement | Implemented |
|---|---|
| 20×20 cells across entire print area | `GRID_COLS = 20`, `GRID_ROWS = 20` |
| Grid origin lower-left of frame | Row 0 = bottom of print area in image-pixel space (`(GRID_ROWS-1-row)` transform) |
| Axis-aligned, no rotation | Canvas lines drawn in imgToCanvas() space, which is always axis-aligned |
| `cell_index = row * 20 + col` | Used as dict key throughout |
| `gridCellHeights: {cell_index: mm}` sparse dict | Stored in Alpine state |
| Delete key clears a cell | `handleKey` → `deleteGridCell()` |
| Clamp 0–50 mm | Input attributes `min="0" max="50"`, also enforced in `commitGridCell()` via `Math.max(0, Math.min(50, raw))` |
| EGM round-trip | autoSave writes `gridCellHeights`, loadProject restores it with `|| {}` fallback |
| No TPS wiring (phase 2 Topo) | Grid values stored; not consumed by geometry pipeline yet |

---

## Visual Layout

```
┌────────────────────────────────────────────────────┐
│  Canvas area                                        │
│  ┌──────────────────────────────────────────────┐  │
│  │ · · · · · · · · · · · · · · · · · · · ·     │  │  <- faint grid lines (rgba 90,90,160 @ 20% opacity)
│  │ · · · · · · · · · · · · · · · · · · · ·     │  │
│  │ · · · [●] · · · · · · ·[●]· · · · · · ·     │  │  <- indigo dot = set cell
│  │ · · · · · · · · · · · · · · · · · · · ·     │  │
│  │ · · · · · · · · · · · · · · · · · · · ·     │  │
│  │ · · · · · [■]  ...rest of cells ...  · ·     │  │  <- active cell = indigo fill + border
│  │                    ┌──────┐                  │  │
│  │                    │ 7.0  │                  │  │  <- floating input, appears above cell
│  │                    └──────┘                  │  │
│  └──────────────────────────────────────────────┘  │
│                                                      │
│  Status strip: [2 cells set]  (hidden when 0)       │
└────────────────────────────────────────────────────┘
```

- **Grid lines**: 21 vertical + 21 horizontal lines at low opacity (rgba 90,90,160 @ 20%). Drawn last-in-overlay so polygons remain fully visible.
- **Set cells**: small indigo dot (radius ~4px) at cell centre. White stroke ring for contrast.
- **Active cell**: semi-transparent indigo fill + 2px indigo border rectangle over the cell.
- **Input**: positioned absolutely above the active cell (`transform: translateY(-100%)`), autofocused, `min=0 max=50 step=0.5`.
- **Status strip**: indigo badge next to existing unsaved-changes badge. Text: "N cell set" / "N cells set". Hidden via `x-show="Object.keys(gridCellHeights).length > 0"`.

---

## EGM Schema Addition

The `gridCellHeights` field is a **sparse dict** at the top level of the EGM JSON:

```json
{
  "course": "Delaveaga",
  "hole": "5",
  ...existing fields...,
  "gridCellHeights": {
    "42": 7.0,
    "210": 12.5,
    "399": 3.0
  }
}
```

- **Key**: `cell_index` (integer as string), `cell_index = row * 20 + col`
- **Value**: height in mm (float, clamped 0–50)
- **Row 0**: bottom row of the print area (lower-left origin per spec)
- **Omitted when empty**: `autoSave()` only writes the field when at least one cell is set, keeping legacy EGMs byte-identical
- **Backward compat load**: `data.gridCellHeights || {}` — missing field silently defaults to empty dict, no error

---

## Red → Green Table

| # | Test | Result |
|---|---|---|
| T1 | `gridCellHeights` declared and init to `{}` in Alpine state | RED → GREEN |
| T2 | `gridCellHeights` inside `polygonEditor()` function body | RED → GREEN |
| T3 | `draw()` references `gridCellHeights` (overlay drawn) | RED → GREEN |
| T4 | `_gridActiveCell` state variable exists, init to `null` | RED → GREEN |
| T5 | Enter key wired to `commitGridCell()` | RED → GREEN |
| T6 | Esc cancels via `cancelGridCell()` | RED → GREEN |
| T7 | Delete removes entry from `gridCellHeights` | RED → GREEN |
| T8 | Status strip "N cells set", hidden when 0 | RED → GREEN |
| T9 | `autoSave()` includes `gridCellHeights` in payload | RED → GREEN |
| T10 | `loadProject()` restores `gridCellHeights` from EGM | RED → GREEN |
| T11 | Missing field in legacy EGM → defaults to `{}` | RED → GREEN |
| T12 | Input has `min=0 max=50` attributes | RED → GREEN |
| T13 | `APP_VERSION` is `v5.00` in `app.py` | RED → GREEN |
| T14 | editor.html on-page version bumped past v4.98 | RED → GREEN |
| T15 | `clearEditorState()` resets `gridCellHeights` to `{}` | RED → GREEN |
| T16 | `startNewProject()` resets `gridCellHeights` to `{}` | RED → GREEN |
| T17 | `GRID_COLS = 20` / `GRID_ROWS = 20` constants present | RED → GREEN |
| T18 | Grid input absolutely positioned over canvas | RED → GREEN |
| T19 | Grid input has `autofocus` | RED → GREEN |
| T20 | `commitGridCell()` calls `autoSave()` | RED → GREEN |

**All 28 new tests GREEN. Full suite: 362 passed, 185 skipped, 0 failures.**

---

## Test Drive for Thomas

1. Open the Boundary Editor at port 5051.
2. Click **New Project**, pick a course + hole + image, wait for image to load.
3. The canvas now shows a faint 20×20 grid overlaid on the print area.
4. **Click any empty area** inside the print zone — a small number input appears floating above the cell.
5. Type `7` → press Enter.
6. The input closes; a small indigo dot appears at that cell's centre.
7. The status strip at the bottom of the action bar now shows **"1 cell set"** in an indigo badge.
8. Click the same cell again — the input reopens pre-filled with `7`.
9. Press Esc — input closes, value unchanged.
10. Click the cell again → the input opens → press Delete (while the input is empty or without the input focused) — cell clears, dot disappears, status strip hides.
11. Set 3 cells. Close the project. Reopen it via **Open Project**.
12. All 3 cells are restored with their original values. Status strip shows "3 cells set".

---

## Phase 2 Note

Cell values are stored in the EGM and round-trip correctly. The generated 3MF does **not yet reflect them** — that wiring is Topo's phase-2 task (task 704). Once Topo feeds `gridCellHeights` into `_build_tps_base()` as `(cell_center_x_mm, cell_center_y_mm, mm)` constraints, the surface will locally track your typed values with TPS-smooth blending everywhere else.

---

## Files Changed

- `/Volumes/GIT/CLAUDE/SHARED_WORK_FOLDER/app/app.py` — APP_VERSION bumped to `v5.00`
- `/Volumes/GIT/CLAUDE/SHARED_WORK_FOLDER/app/templates/editor.html` — version comment, Alpine state, draw() overlay, grid helpers, onMouseDown intercept, handleKey Delete guard, autoSave payload, loadProject restore, clearEditorState reset, startNewProject reset, HTML input overlay, status strip
- `/Volumes/GIT/CLAUDE/SHARED_WORK_FOLDER/app/tests/test_grid_cell_elevation_ui.py` — 28 new Bug→TDD tests (all GREEN)
- `/Volumes/GIT/CLAUDE/SHARED_WORK_FOLDER/app/tests/test_strip_ocr_elevation_spikes.py` — version assertions updated to range guards (pinned v4.99 / "4.98" assertions updated to accept v5.00)
