# Editor GPS Panel — Collapse When Unchecked

**v1.0** · Sienna · 2026-09-25 · Task 596

---

> *"On the boundary editor, when use GPS backend is not checked, let's hide all that stuff. Because it's not used when it's not checked."*
> — Thomas

---

## What changed

The GPS Backend panel in the boundary editor now collapses its body when the **Use GPS backend** checkbox is unchecked.

**Before:** All GPS controls (file picker, map canvas, snap button, bbox display, sliders, preview thumbnail) rendered regardless of the checkbox state.

**After:** Everything below the checkbox hides instantly when unchecked, shows when checked. The panel heading ("GPS Backend") and the checkbox itself stay visible at all times so the user knows the section exists and can re-enable it.

---

## Structural change

A wrapper div was added inside the GPS panel, immediately after the header row:

```html
<div id="gps-backend-body"
     x-show="gpsEnabled"
     x-transition:enter="transition-all ease-out duration-150"
     x-transition:enter-start="opacity-0 -translate-y-1"
     x-transition:enter-end="opacity-100 translate-y-0"
     x-transition:leave="transition-all ease-in duration-150"
     x-transition:leave-start="opacity-100 translate-y-0"
     x-transition:leave-end="opacity-0 -translate-y-1"
     class="space-y-4">
  <!-- GPS file picker, vert exag, approach, gridSize, bbox, map canvas, preview -->
</div>{# /gps-backend-body #}
```

- `x-show="gpsEnabled"` drives show/hide via Alpine's existing reactive state.
- Alpine's `x-transition` directives produce a 150 ms opacity + slight-upward-slide animation on enter/leave (consistent with the panel's design language).
- No new JS state or event handlers were needed — `gpsEnabled` was already the authoritative toggle, and `loadProject()` / `startNewProject()` already set it from the EGM.

**Persistence respected:** `gpsEnabled` is loaded from `data.gpsBackend.enabled` in `loadProject()` and reset to `false` in `startNewProject()`. The collapse state follows the EGM automatically.

---

## Files changed

| File | Change |
|------|--------|
| `app/templates/editor.html` | Added `#gps-backend-body` wrapper + transitions (v4.60 comment) |
| `app/app.py` | APP_VERSION already bumped to v4.60 by Phase 2 (no further change needed) |
| `app/tests/test_gps_collapse.py` | 13 new tests — T16–T20 |

---

## Test results

```
13 new collapse tests (T16–T20): 13 passed
Phase 2 regression (T1–T15): 78 passed
Full app/tests/ suite: 110 passed, 4 pre-existing errors
```

The 4 errors are in `TestRealDataDeLaveaga` — they fail because the real De Laveaga GPS file on disk has malformed JSON (trailing comma). This is a pre-existing issue unrelated to this task.

---

## Migration for Thomas

1. **Hard-refresh the editor tab** (Cmd+Shift+R or Cmd+R). The footer should show **v4.60**.
2. Open any project. The GPS Backend section should show only the heading + checkbox.
3. Check **Use GPS backend** — the full panel should expand with a 150 ms fade.
4. Uncheck it — the panel collapses back, leaving just the heading and checkbox.

---

## Follow-up: other sections worth the same treatment?

Scanned the current editor for other backend-conditional sections. Nothing obvious found — all other settings panels render unconditionally (they have no analogous enabled/disabled toggle). The fringe-cap and boundary-region checkboxes affect generation behavior but their UI inputs are always relevant to show.

No follow-up action needed unless a new conditional section is added.
