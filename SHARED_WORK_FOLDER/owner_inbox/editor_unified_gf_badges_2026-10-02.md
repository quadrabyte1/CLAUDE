# Editor — Unified G/F Badge Editable Inputs
**v4.90 · Sienna · 2026-10-02**

---

## What was already landed before the kill (task 683, session 1)

- `APP_VERSION` bumped to **v4.90** in `app/app.py`
- **G-badge template** (`elevationSpikes` x-for loop) fully wired:
  - Compact green chip (background `#E8F5E9`, border `#388E3C`) with letter `G`
  - `<input type="text">` with `:value="sp.mm.toFixed(1)"`
  - Event handlers: `@focus spikeEditStart`, `@blur spikeEditCommit`, Enter commits, Escape reverts
  - Outer wrapper `pointer-events-none`; inner badge and input `pointer-events-auto`
  - No spinner (▲/▼), no × delete button
- **Status strip** updated to show `N G · N F detected` wording
- 17/19 tests in `test_unified_gf_badges.py` GREEN; 2 F-badge tests RED (killed before F-badge wiring)

---

## What was added this session (task 683, resume)

### F-badge editable wiring — `app/templates/editor.html`

Replaced the non-editable `<div x-text="anchor.value.toFixed(1)">` inside the `fringeBoundaryHeights` x-for loop with a full editable `<input>` mirroring the G-badge structure:

```html
<input type="text"
       :value="anchor.value.toFixed(1)"
       @pointerdown.stop
       @focus="anchorEditStart(aIdx)"
       @blur="anchorEditCommit(aIdx, $event.target.value)"
       @keydown.enter.prevent="anchorEditCommit(aIdx, $event.target.value); $event.target.blur()"
       @keydown.escape.prevent="anchorEditCancel(aIdx, $event.target)"
       class="pointer-events-auto"
       style="width:44px; … color:#1A3A6B; …"
       autocomplete="off" spellcheck="false">
```

Blue colour scheme preserved (`#E0EDFF` bg, `#4B7EC8` border, `#1A3A6B` text). No × delete, no spinner. Outer wrapper remains `pointer-events-none`; inner badge div and input have `pointer-events-auto`.

### New JS methods added — `app/templates/editor.html`

Two sets of inline-edit handlers added to the Alpine.js `polygonEditor()` data object:

**G-badge handlers** (`spikeEditStart/Commit/Cancel`) — these were referenced in the HTML template but never defined; added them so the editor doesn't throw at runtime:
- `spikeEditStart(idx)` — snapshot `sp.mm` to `_spikeEditPrev`
- `spikeEditCommit(idx, raw)` — parse, clamp [-50, +50], write `elevationSpikes[idx].mm =`, call `autoSave()`
- `spikeEditCancel(idx, inputEl)` — restore from `_spikeEditPrev`, reset input DOM value

**F-badge handlers** (`anchorEditStart/Commit/Cancel`) — new:
- `anchorEditStart(aIdx)` — snapshot `anchor.value` to `_anchorEditPrev`
- `anchorEditCommit(aIdx, raw)` — parse, clamp, write `fringeBoundaryHeights[aIdx].value =`, call `autoSave()`
- `anchorEditCancel(aIdx, inputEl)` — restore from `_anchorEditPrev`, reset input DOM value

---

## Red → Green: 2 → 0 failing tests

| Test | Before | After |
|------|--------|-------|
| `TestEditableInput::test_input_on_f_badge` | FAILED | PASSED |
| `TestEditCommit::test_f_badge_commit_writes_value` | FAILED | PASSED |

Full `test_unified_gf_badges.py`: **19/19 passed**.

Pre-existing Bambu failures (Finn's `test_bambu_config_injection.py`, 4 failing) are unrelated to this work and unchanged.

---

## Test drive for Thomas

1. Open the Boundary Editor (port 5051)
2. Create New Project → choose **DeLaveaga H5** → run OCR detection
3. After detection completes:
   - **G-badges** (green chips, letter G) appear over interior elevation spikes
   - **F-badges** (blue chips, letter F) appear over fringe boundary anchors
4. Click the number on any **G-badge** → field activates; type a new mm value → press Enter or click away → value commits and autosave fires
5. Click the number on any **F-badge** → same behaviour: field activates, edit, Enter/blur commits, Esc reverts to prior value
6. Status strip bottom-left shows e.g. `3 G · 2 F detected`
7. Neither badge type has a × delete button or ▲/▼ spinner — just the compact chip + editable number
