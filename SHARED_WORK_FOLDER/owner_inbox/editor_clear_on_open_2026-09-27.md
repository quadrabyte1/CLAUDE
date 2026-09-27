# Boundary Editor — Reset State on Open Project Click
**v1.0** · Sienna · 2026-09-27

---

## Where the click handler lives

| File | Location | Description |
|------|----------|-------------|
| `app/templates/editor.html` | Line 2429 | New `clearEditorState()` method |
| `app/templates/editor.html` | Line 2488 | `loadProject(proj)` — call site |
| `app/templates/editor.html` | Line 2493 | `this.clearEditorState()` — fires before `fetch()` |
| `app/app.py` | Line 26 | `APP_VERSION` bumped `v4.68 → v4.69` |

---

## What state gets cleared vs. preserved

### Cleared on every Open Project click (before fetch)

| State | Field(s) | Notes |
|-------|----------|-------|
| Displayed image | `selectedImage`, `selectedImageUrl`, `selectedImageCourse`, `img`, `imgLoaded`, `imgW`, `imgH` | Canvas is also explicitly cleared |
| Canvas | `ctx.clearRect(0,0,w,h)` | Runs synchronously so no stale pixels while fetch is in-flight |
| Polygons | `polygons`, `selectedPoly`, `selectedVerts`, `_pendingRestore` | All polygon types (green, fringe, trap, water, boulders, contours) |
| Contours | `contours` | Arrow annotations |
| Elevation spikes | `elevationSpikes` | Draggable spike markers |
| Tee-hole marker | `teeHole` | Set to `null` |
| Per-hole settings | `contourStep`, `grassAmplitude`, `grassSpacing`, `greenStyle`, `elevationRange`, `greenScale`, `fringeEdgeHeight`, `baseThicknessMm`, `includeBoundaryRegion`, `applyFringeFrameCap`, `flagOffsetXMm`, `flagOffsetYMm` | Reset to same defaults as New Project |
| GPS backend | `gpsEnabled`, `gpsFile`, `gpsBbox`, `gpsVertExag`, `gpsApproachM`, `gpsGridSize`, `courseGeoRef` | All GPS fields cleared |
| GPS preview | `gpsPreviewDataUrl`, `gpsPreviewError`, `gpsPreviewNotes` | Preview pane goes blank |
| Undo/redo | `undoStack`, `redoStack` | Previous project's history discarded |
| Unsaved-changes badge | `_pendingAutoSave` | Cleared so no false "unsaved" indicator |
| Identity | `courseName`, `holeName` | Header labels blank while loading |

### Preserved (not touched)

| State | Reason |
|-------|--------|
| Project list / `openProjects` | User is choosing from it right now |
| `selectedOpenProject` | Set immediately after clear to show which project is loading |
| Global user preferences | Theme, etc. — not per-project |
| `APP_VERSION` badge | Static; comes from Jinja context |
| Print constants (`printSizeMm`, `fringeXyExpansionMm`) | Server-provided; re-loaded alongside the EGM data |
| GPS file list (`gpsFileList`) | Refreshed after successful load via `refreshGpsFiles()` |

---

## Order of operations

```
User clicks a project row in Open Project dialog
  │
  ▼
loadProject(proj) starts
  │
  ├─ this.selectedOpenProject = proj
  ├─ this.showOpenDialog = false   ← dialog dismisses
  ├─ this.clearEditorState()       ← IMMEDIATE: canvas clears, all state defaults
  │
  ▼
await fetch('/api/boundaries/load?filename=…')
  │
  ├─ HTTP error (4xx / 5xx)
  │   ├─ flash error toast
  │   └─ return   ← state STAYS CLEARED — user sees blank editor
  │
  ├─ JSON parse / data.status !== 'ok'
  │   ├─ flash error toast
  │   └─ return   ← state STAYS CLEARED
  │
  └─ Success
      ├─ Assign all fields from EGM data (course, hole, image, polygons, GPS…)
      ├─ loadImage()           ← triggers canvas render with new image
      ├─ refreshGpsFiles()
      ├─ scheduleGpsPreview()
      └─ flash success toast
```

---

## Red → Green table

| # | Test | Before (RED) | After (GREEN) |
|---|------|:---:|:---:|
| T1a | `clearEditorState()` method exists in JS | FAIL | PASS |
| T1b | `clearEditorState()` resets `this.polygons` | FAIL | PASS |
| T1c | `clearEditorState()` clears `selectedImage` and `imgLoaded` | FAIL | PASS |
| T1d | `clearEditorState()` resets GPS backend fields | FAIL | PASS |
| T1e | `clearEditorState()` resets `elevationSpikes` | FAIL | PASS |
| T1f | `clearEditorState()` resets `contours` | FAIL | PASS |
| T2 | `clearEditorState()` appears before `fetch()` in `loadProject()` | FAIL | PASS |
| T2b | `clearEditorState()` appears before `resp.ok` check | FAIL | PASS |
| T3 | `/api/boundaries/load` returns 200 + polygons on valid file | PASS | PASS |
| T3b | `/api/boundaries/load` returns all per-hole config fields | PASS | PASS |
| T4 | `/api/boundaries/load` 404 on missing file | PASS | PASS |
| T4b | 404 response has human-readable `msg` | PASS | PASS |
| T4c | Path-traversal filename → 400 | PASS | PASS |
| T5 | No EGM field assignments between `fetch()` and `resp.ok` | PASS | PASS |
| T5b | `catch` block does not re-assign state fields | PASS | PASS |
| T6 | No `polygons.push` between `clearEditorState()` and `fetch()` | FAIL | PASS |
| T6b | `/api/boundaries/list` returns correct `polygon_count` | PASS | PASS |

9 RED → GREEN. 8 already passing (unchanged Flask routes).

---

## Manual verification

1. Start the web server (`python app/app.py` or the Login Item — port 5051).
2. Open the Boundary Editor.
3. Click **Open Project** and pick any valid `.egm` file. Verify it loads — image visible, polygons drawn, course/hole name in the header. Version badge should read **v4.69**.
4. Drag a polygon vertex a few pixels (or add an elevation spike). You should see the unsaved-changes badge appear briefly, then auto-save.
5. Click **Open Project** again.  
   **Expected immediately (before choosing a file):** editor goes blank — image clears, all polygons/spikes disappear, course/hole name empties.
6. In the project list, click a file that no longer exists on disk (rename or delete an `.egm` file, or type a bogus URL directly: `/api/boundaries/load?filename=DoesNotExist.egm`).  
   **Expected:** error toast appears, editor remains blank — no stale image or polygons from step 3-4 are shown.
7. Back in the dialog, choose a valid file and confirm it loads correctly (regression check — the happy path still works).

---

## Files changed

- `app/templates/editor.html` — added `clearEditorState()` at line 2429; modified `loadProject()` at line 2488 to call it before fetch
- `app/app.py` — `APP_VERSION` v4.68 → v4.69
- `app/tests/test_editor_clear_on_open.py` — new test file (17 tests)
