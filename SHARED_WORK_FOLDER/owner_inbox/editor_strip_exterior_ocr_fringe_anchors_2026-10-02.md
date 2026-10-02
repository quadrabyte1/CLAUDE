# Strip Exterior OCR / Fringe Anchors (v1.0 · 2026-10-02)

**v1.0** | Task 691 | Sienna | 2026-10-02

---

## Why the change

Thomas revealed that the exterior ring numbers (10, 15, 20, 25, 30) around the green on Golf Intelligence heat maps are **distance-from-pin markers**, not altitude values. The entire `fringeBoundaryHeights` → F-badge → fringe anchor pipeline that shipped last week was semantically wrong: it was treating distance values as elevation input to the surface geometry. Everything downstream was plausible-looking but physically incorrect. The pipeline has been fully removed.

---

## Deleted items checklist

- [x] `golf_intel_ocr.py` — `_EXT_*` constants (7 removed), `_parse_exterior_value()`, `_pass_b_exterior()`, `extract_numeric_markers_with_exterior()`, exterior coloring in `generate_diagnostic_overlay()`
- [x] `app.py` — `extract_numeric_markers_with_exterior` import, `classify_ocr_markers` call in `detect_boundaries`, `fringe_boundary_heights` local variable, `fringeBoundaryHeights` field in JSON response
- [x] `editor.html` — `fringeBoundaryHeights` Alpine state field, F-badge `<template x-for>` block, `anchorEditStart/Commit/Cancel` methods, `_anchorEditPrev` state, F count in status strip, `fringeBoundaryHeights` in `_clearProjectState()`, EGM save path (autoSave + generate 3MF), EGM load path
- [x] Status strip — now shows `N G detected` only; hidden when no spikes
- [x] EGM load path — gracefully ignores `fringeBoundaryHeights` field in legacy files (comment left explaining why)

**Preserved:**

- Interior OCR pass (`extract_numeric_markers`) — unchanged
- G-badge overlay and editable spike input — unchanged
- `elevationSpikes` state / EGM round-trip — unchanged
- `classify_ocr_markers` function — still in `app.py` (used by existing tests, available if needed later)
- `gradient_surface_diagnostic.py` — not touched (Topo's zone, T1 parallel task)

---

## Files touched

| File | Change |
|---|---|
| `app/golf_intel_ocr.py` | -77 lines: removed Pass B constants, `_parse_exterior_value`, `_pass_b_exterior`, `extract_numeric_markers_with_exterior`; simplified overlay |
| `app/app.py` | -22 lines: removed `fringeBoundaryHeights` from `detect_boundaries`; bumped APP_VERSION v4.93 → v4.94 |
| `app/templates/editor.html` | -45 lines: removed F-badge template, `fringeBoundaryHeights` state, anchorEdit methods, save/load paths, strip F-count |
| `app/tests/test_strip_exterior_ocr.py` | +240 lines: new C1–C6 test suite (RED first, then GREEN) |
| `app/tests/test_fringe_anchor_ui.py` | Rewritten: all tests skipped with tombstone message |
| `app/tests/test_golf_intel_ocr.py` | Removed exterior test data + T7; updated T6, T8, T9, T10, T11, T12 to use `extract_numeric_markers` |
| `app/tests/test_unified_gf_badges.py` | F-badge tests (T2,T5,T7,T9,T11,T13b,T14b) marked skip; T15 bumped to v4.94 |
| `app/tests/test_fringe_boundary_anchors.py` | T2 API shape tests updated; T2c retired |

---

## Red → Green table

| Test | Before (RED) | After (GREEN) |
|---|---|---|
| C1a — detect_boundaries no fringeBoundaryHeights (real image) | FAIL: returned 9 entries | PASS: returns `[]` |
| C1b — detect_boundaries no fringeBoundaryHeights (mock) | FAIL | PASS |
| C2a — no `_EXT_` constants in golf_intel_ocr.py | FAIL: 7 found | PASS |
| C2b — no `extract_numeric_markers_with_exterior` | FAIL | PASS |
| C2c — no `_pass_b_exterior` function | FAIL | PASS |
| C2d — no `_EXTERIOR_VALID_INTS` | FAIL | PASS |
| C3a — no `data-fringe-anchor` in editor.html | FAIL | PASS |
| C3b — no x-for loop over fringeBoundaryHeights | FAIL | PASS |
| C3c — no anchorEditStart/Commit/Cancel | FAIL | PASS |
| C4a — status strip no fringeBoundaryHeights.length | FAIL | PASS |
| C4b — status strip still shows elevationSpikes.length | PASS (regression) | PASS |
| C5a — EGM save path no fringeBoundaryHeights | FAIL | PASS |
| C5b — EGM load path no fringeBoundaryHeights state population | FAIL | PASS |
| C6a–C6d — interior OCR + G-badges + detect_boundaries regression | PASS | PASS |

**Suite total: 385 passed, 20 skipped, 4 pre-existing Bambu failures (not in scope)**

---

## Test drive for Thomas

1. Open the Boundary Editor → Create New Project → **DeLaveaga Hole 5**
2. Detection completes → you should see **G-badges only** (green/teal) on the interior elevation spikes — no blue F-badges anywhere
3. Status strip bottom-left shows **`N G detected`** (no F count)
4. Click any G-badge number → edit inline → Enter commits → Esc reverts
5. Autosave fires — open the saved `.egm` and confirm there is no `fringeBoundaryHeights` key
6. Load an older EGM that has `fringeBoundaryHeights` → loads without error, no F-badges shown (legacy field silently ignored)
7. Regenerate 3MF → surface shape driven by interior spikes + frame base via Topo's TPS (T1 parallel task) — no fringe anchor influence

---

## Follow-up tasks queued

- **T3** — Add Spike placement mode (click canvas to place a new G-badge)
- **T4** — Delete affordance for user-created spikes (× button on G-badge)
