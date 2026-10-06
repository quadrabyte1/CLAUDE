# v1.0 — Grid Cell Marker: Numeric Text Replaces Blue Dot

**Task 720 · 2026-10-06 · Sienna**

---

## Before / After

**Before** — a filled indigo circle (arc radius ~5 CSS px) rendered at the cell centre:

```
┌──────┬──────┬──────┐
│      │  ●   │      │
│      │      │      │
└──────┴──────┴──────┘
```

**After** — the numeric mm value rendered as centered text in the same indigo accent color:

```
┌──────┬──────┬──────┐
│      │ 7.5  │      │
│      │      │      │
└──────┴──────┴──────┘
```

Format: `toFixed(1)` — always one decimal, no unit suffix on canvas. Unset cells are blank.

---

## What Changed

**`app/templates/editor.html`** — inside `draw()`, the set-cell rendering block (lines ~1426–1444) was replaced:

- Removed: `ctx.beginPath()` / `ctx.arc(...)` / `ctx.fill()` / `ctx.stroke()` dot sequence
- Added: `ctx.textAlign = 'center'` + `ctx.textBaseline = 'middle'` + `ctx.font` set once before the loop, then `ctx.fillText(Number(mm).toFixed(1), cp.x, cp.y)` inside the loop
- Color: `rgba(99,102,241,0.92)` — same indigo family as the old dot; set cells remain visually distinguishable
- Font: `11px -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif` — matches other canvas text (readable, not overwhelming)

**`app/app.py`** — `APP_VERSION` bumped `v5.09` → `v5.10`

**`app/templates/editor.html`** — on-page version comment bumped to `v5.07`

---

## Hit-Detection Approach for Right-Click Delete

No change to hit detection. The right-click handler (`onRightClick`) still uses the existing cell-centred bounding approach:
- Iterates `Object.keys(gridCellHeights)`
- For each set cell, calls `_gridCellCanvasPx(col, row)` to get the cell's CSS-pixel rectangle
- Checks distance from mouse to cell centre with a radius of `Math.max(5, Math.min(pos.w, 10))` px

This radius naturally covers the text glyph (text is narrower than the cell; any click within ~10px of centre deletes). No change needed — the old dot-radius logic is already cell-sized, not glyph-sized.

---

## Hover Tooltip Decision

**Kept.** The tooltip (task 710) shows `"12.5 mm"` (with the unit) on hover. It is now slightly redundant with the on-canvas value, but it:
- Provides the unit label that the canvas omits
- Matches the existing tooltip contract (T9 regression test passes)
- Required zero code changes

The `_gridHoveredCell` hover detection and tooltip div in the HTML are unchanged.

---

## Red → Green Table

| # | Test | RED | GREEN |
|---|------|-----|-------|
| T1 | No `ctx.arc()` in gridCellHeights loop | FAIL | PASS |
| T2 | `ctx.fillText()` in gridCellHeights loop | FAIL | PASS |
| T3 | `textAlign='center'` in `draw()` | FAIL | PASS |
| T3 | `textBaseline='middle'` in `draw()` | FAIL | PASS |
| T4 | Format `.toFixed(1)` in loop | FAIL | PASS |
| T4 | No `mm` suffix in `fillText` call | FAIL | PASS |
| T5 | Blue/indigo fillStyle in rendering block | FAIL | PASS |
| T6 | Right-click still deletes (regression) | PASS | PASS |
| T7 | Right-click hit detection present (regression) | PASS | PASS |
| T8 | Left-click opens input via `openGridCell` (regression) | PASS | PASS |
| T9 | Hover tooltip fires in `onMouseMove` (regression) | PASS | PASS |
| T10 | `fillText` only inside set-cell loop | FAIL | PASS |
| T11 | No `ctx.arc` in loop (belt+suspenders) | FAIL | PASS |
| T12 | `ctx.arc` still present outside loop (polygon vertices) | PASS | PASS |
| T13 | APP_VERSION ≥ v5.10 | FAIL | PASS |
| T14 | editor.html version ≥ v5.07 | FAIL | PASS |

**10 RED → GREEN. 6 already-green regressions stayed green.**

Full HTML-based test suite: **111 passed, 77 skipped** (no failures).

---

## Test Drive for Thomas

1. Hard-refresh the editor page (`Cmd+Shift+R`)
2. Open a project with a background image loaded
3. Click any cell in the altitude-adjustment grid overlay — the inline number input opens
4. Type a value (e.g. `12.5`) and press Enter — the input closes; `12.5` appears centered in that cell in indigo text
5. Set a few more cells — each shows its own numeric value
6. Hover over a cell with a value — tooltip appears showing `"12.5 mm"` (with unit)
7. Right-click a cell with a value — the value disappears (cell cleared), flash message shows
8. Left-click an empty cell — inline input opens again
9. Page footer should read **v5.10**
