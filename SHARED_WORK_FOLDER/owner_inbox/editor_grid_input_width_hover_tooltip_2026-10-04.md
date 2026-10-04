# v5.04 — Grid Input Width + Dot Hover Tooltip

**Sienna · Task 710 · 2026-10-04**

---

## Input Width — Before / After

| Property | Before | After |
|---|---|---|
| `min-width` on `<input>` | `36px` | `80px` |
| `max-width` on `<input>` | `60px` (hard cap) | removed |
| `px` padding class | `px-1` | `px-2` |
| Container `Math.max` floor | `Math.max(36, cell.w)` | `Math.max(80, cell.w)` |

The input now comfortably shows `12.5 mm` (3 digits + decimal) without truncation. It still stretches to fill the cell width when the cell is wider than 80 px.

---

## Tooltip Approach + Format

**Approach:** Canvas mouse-tracking + floating Alpine div (native `title=` not viable since dots are drawn on `<canvas>`).

**Implementation:**
- New Alpine state: `_gridHoveredCell: null` — holds `{idx, canvasPx}` when hovering a set cell, `null` otherwise.
- `onMouseMove` iterates `Object.keys(gridCellHeights)`, converts each cell index to a `_gridCellCanvasPx` position, and checks if the CSS-px mouse distance to the dot centre falls within `dotR = max(5, min(cell.w, 10))` px.
- `openGridCell()` immediately clears `_gridHoveredCell` so the tooltip never overlaps the input.

**Tooltip div:** absolutely positioned, `z-index:40`, dark pill style (`bg-gray-800 text-white`), centred above the dot via `translate(-50%, -110%)`.

**Format:** `"12.5 mm"` — the raw stored number (already clamped 0–50) concatenated with `' mm'`.

**Guard:** tooltip `x-show` requires `_gridHoveredCell !== null && _gridActiveCell === null`.

---

## Red → Green Table

| # | Test | RED reason | GREEN after |
|---|---|---|---|
| T1a | `test_input_max_width_removed_or_wider` | `max-width:60px` still present | removed |
| T1b | `test_input_min_width_at_least_80px` | min-width was 36 px | bumped to 80 px |
| T2 | `test_container_min_width_at_least_80` | `Math.max(36,...)` | `Math.max(80,...)` |
| T3a | `test_hovered_cell_declared` | `_gridHoveredCell` absent | added to state |
| T3b | `test_hovered_cell_null_initial` | absent | `_gridHoveredCell: null` added |
| T4a | `test_tooltip_div_present` | no tooltip element | `x-show="_gridHoveredCell !== null && _gridActiveCell === null"` div added |
| T4b | `test_tooltip_positioned_absolutely` | absent | div is `absolute` |
| T5 | `test_tooltip_reads_gridCellHeights` | absent | `x-text` reads `gridCellHeights[_gridHoveredCell.idx]` |
| T6 | `test_tooltip_suppressed_during_edit` | absent | `_gridActiveCell === null` guard |
| T7 | `test_tooltip_mm_suffix` | absent | `+ ' mm'` in x-text expression |
| T8 | `test_hovered_cell_set_only_when_cell_in_gridCellHeights` | absent | iterates `Object.keys(gridCellHeights)` — only set cells |
| T9 | `test_onMouseMove_references_gridHoveredCell` | absent | detection block added at end of `onMouseMove` |
| T13 | `test_app_version_is_v5_04` | was v5.03 | bumped to v5.04 |
| T14 | `test_editor_version_is_v5_04` | was v5.02 | bumped to v5.04 |

Full suite: **376 passed / 0 failed** (212 skipped — pre-existing skips unrelated to this task).

---

## Test Drive for Thomas

1. Hard-refresh the editor (`Cmd+Shift+R`).
2. Load or create a project with an image on the canvas.
3. Click any grid cell — the input box appears. It is now **wider** (~80 px minimum), showing `12.5` or `7.5` without crowding.
4. Type `12.5` and press **Enter** — the cell is committed, a blue dot appears on the canvas.
5. Move the mouse slowly over the blue dot — a dark pill tooltip appears above it reading **`12.5 mm`**.
6. Move away — tooltip disappears.
7. Click the dot's cell again — tooltip is gone while the input is open. Press **Esc** to cancel.
8. Version badge in the footer shows **v5.04**.
