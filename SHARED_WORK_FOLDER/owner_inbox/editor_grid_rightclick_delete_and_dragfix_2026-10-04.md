# Boundary Editor v5.05 — Grid Right-Click Delete + Click-vs-Drag Fix

**v5.05** · Sienna · 2026-10-05

---

## Right-click handler + convention match

`onRightClick(e)` already owned contour-vertex delete (right-click a contour dot → removes the vertex). The new grid section sits at the top of that same handler, checked first, and follows the identical CSS-px hit-detection pattern already used for hover tooltips in `onMouseMove` (task 710):

```
for each set cell in gridCellHeights:
    compute dotCx/dotCy in canvas CSS px (via _gridCellCanvasPx)
    compute dotR = clamp(5, 10, cell.w)   ← same formula as tooltip
    if (dx² + dy²) <= dotR²:
        delete this.gridCellHeights[idx]
        this._gridHoveredCell = null
        draw(), flash('Grid cell cleared'), autoSave()
        return
```

Miss path: falls through silently. `@contextmenu.prevent="onRightClick($event)"` was already wired on the canvas; no markup change needed.

---

## Click-vs-drag threshold + state machine

New state variable: `_gridMouseDownAt: null` (Alpine data, initialised to null).
New config constant: `GRID_DRAG_THRESHOLD_PX: 5` (Alpine data property).

**Before (broken):** `onMouseDown` called `openGridCell()` immediately and returned — rubber-band drag was impossible once the cursor was over any grid cell.

**After:**

| Event | Grid path |
|-------|-----------|
| `onMouseDown` (left, inside grid cell) | Records `_gridMouseDownAt = {clientX, clientY, col, row, idx}` then **falls through** (no `return`) — global-mouseup listener attaches, rubber-band can still start |
| `onMouseMove` | If `_gridMouseDownAt` is set and movement exceeds `GRID_DRAG_THRESHOLD_PX` → `_gridMouseDownAt = null` (drag detected, pending click abandoned) |
| `onMouseUp` (left) | If `_gridMouseDownAt` is still set (never exceeded threshold) → bare click → calls `openGridCell()`, then nulls the pending state |

Edge case "drag then come back to same cell": once `_gridMouseDownAt` is nulled in `onMouseMove`, it stays null — mouseup sees nothing and does not open the input. Drag wins, always.

---

## Red → green table

| # | Test | RED → GREEN |
|---|------|------------|
| T1 | onRightClick references gridCellHeights | RED → GREEN |
| T2 | delete from gridCellHeights in onRightClick | RED → GREEN |
| T2b | canvas-px hit detection (clientX, dotR) | RED → GREEN |
| T3 | right-click clears _gridHoveredCell | RED → GREEN |
| T4 | right-click calls autoSave | RED → GREEN |
| T5 | miss path guarded by if | RED → GREEN |
| T6 | @contextmenu.prevent regression guard | GREEN (already) |
| T7 | GRID_DRAG_THRESHOLD_PX = 5 | RED → GREEN |
| T8 | _gridMouseDownAt declared, null initial | RED → GREEN |
| T9 | onMouseDown records _gridMouseDownAt, not openGridCell | RED → GREEN |
| T10 | onMouseMove abandons pending on threshold | RED → GREEN |
| T11 | onMouseUp calls openGridCell when pending | RED → GREEN |
| T12 | onMouseUp clears _gridMouseDownAt | RED → GREEN |
| T13 | rubber-band still in onMouseDown, no early return | RED → GREEN |
| T14 | tooltip regression (_gridHoveredCell in onMouseMove) | GREEN (already) |
| T15 | Enter commits (commitGridCell regression) | GREEN (already) |
| T16 | Delete key → deleteGridCell regression | GREEN (already) |
| T17 | APP_VERSION = v5.05 | RED → GREEN |
| T18 | editor.html on-page version = v5.05 | RED → GREEN |

Full suite: **401 passed / 0 failed** (376 pre-existing + 25 new).

---

## Test drive for Thomas

1. Hard-refresh the editor (Cmd+Shift+R).
2. **Bare click on empty canvas inside the grid**: input overlay opens (bare click still works).
3. Press Esc.
4. **Click and drag across the canvas** (start from anywhere on the grid): selection rectangle appears and you can drag-select control points (drag works again — was broken).
5. Set a cell to `10` (click empty cell, type 10, Enter).
6. **Right-click the blue dot**: dot disappears, status strip count drops, "Grid cell cleared" flashes (right-click delete).
