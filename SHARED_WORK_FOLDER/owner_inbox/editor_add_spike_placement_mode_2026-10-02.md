# Editor: Add Spike Placement Mode — v4.95

**v1.0** · Sienna · 2026-10-02 · Task 692

---

## UX Design

### Toolbar Button

A new **Add Spike** button appears in the below-canvas action row (replacing the old "Add Elevation Spike" programmatic-spawn button). Styling:

- **Idle:** orange-500 (matches the elevation-spike color family)
- **Active/pressed:** orange-700 + orange ring (ring-2 ring-orange-400) — gives unambiguous visual feedback that placement mode is on
- **Disabled:** orange-500/40 when no image is loaded

### Placement Mode Flow

1. Click **Add Spike** → `spikeMode = true`
2. Canvas cursor changes to `crosshair` (via `:style` binding, not JS mutation)
3. Status strip at bottom-left swaps from the "N G detected" pill to a orange hint banner: **"Click to place a spike · Esc to cancel"**
4. Next left-click anywhere on the canvas places the spike at that image-pixel position. Placement mode exits immediately (`spikeMode = false`).
5. The new G-badge input is auto-focused via `data-spike-input` + `$nextTick` so the user can type the mm value immediately.
6. Clicking **Add Spike** again while already in placement mode toggles it off (same button = cancel).

### Esc Cancels

`handleKey()` has a new Escape branch (checked before the contour-mode Escape branch):

```js
if (e.key === 'Escape' && this.spikeMode) {
  this.spikeMode = false;
  this.flash('Spike placement cancelled', true);
  return;
}
```

### Clicks on Existing Badges

Existing G-badge input wrappers already have `@pointerdown.stop`, which prevents `onMouseDown` from firing on the canvas when the user focuses an existing badge while in placement mode. No new code needed.

### Clicks Outside the Green Polygon

No polygon-interior guard was added. `onMouseDown` in placement mode uses the raw `canvasToImg(e)` coordinates without any containment check. This is intentional: the entire point is placing spikes on elevated fringe areas the heat map can't represent.

---

## Schema Addition: `source` Field

### New field

```json
{ "x": 123, "y": 456, "mm": 5.5, "source": "ocr" }
{ "x": 200, "y": 300, "mm": 7.0, "source": "user" }
```

| source | Meaning |
|--------|---------|
| `"ocr"` | Detected automatically from the heat-map scan |
| `"user"` | Placed manually by the user via Add Spike |

### Where it's written

- **OCR detection** (`runDetection → result.elevationMarkers.map`): tags all OCR spikes with `source: 'ocr'`
- **User placement** (`onMouseDown` in spike mode): tags with `source: 'user'`
- **autoSave serialization** (both the `/api/boundaries` call and the generate payload): includes `source: sp.source || 'ocr'`
- **loadProject**: maps `source: sp.source || 'ocr'` — backward compat baked in

### Backward compat

EGMs saved before v4.95 have no `source` field on spikes. On load, `sp.source || 'ocr'` defaults them to `"ocr"`. No migration needed.

---

## Red → Green Table

| # | Test | Class | Result |
|---|------|-------|--------|
| T1a | Add Spike text in editor | `TestToolbarButton` | RED → GREEN |
| T1b | Wrapped in `<button>` element | `TestToolbarButton` | RED → GREEN |
| T2a | `spikeMode` flag in Alpine state | `TestPlacementModeState` | RED → GREEN |
| T2b | Add Spike button has @click handler | `TestPlacementModeState` | RED → GREEN |
| T2c | Button has active-state class binding | `TestPlacementModeState` | RED → GREEN |
| T3a | `onMouseDown` checks `spikeMode` | `TestCanvasClickPlacesSpike` | RED → GREEN |
| T3b | Placement sets `source: 'user'` | `TestCanvasClickPlacesSpike` | RED → GREEN |
| T3c | Default mm = nearest spike or 0 | `TestCanvasClickPlacesSpike` | already GREEN (existing mm scan) |
| T3d | Placement mode exits after click | `TestCanvasClickPlacesSpike` | RED → GREEN |
| T4 | Esc clears spikeMode in handleKey | `TestEscCancels` | RED → GREEN |
| T5 | No polygon-interior guard in placement | `TestClickOutsidePolygonPlaces` | GREEN (no guard added) |
| T6 | Existing badge has @pointerdown.stop | `TestExistingBadgeClickNoNewSpike` | already GREEN |
| T7a | autoSave serializes `source` | `TestSchemaRoundTrip` | RED → GREEN |
| T7b | loadProject preserves `source` | `TestSchemaRoundTrip` | RED → GREEN |
| T8 | Missing source defaults to "ocr" on load | `TestBackwardCompat` | RED → GREEN |
| T9a-d | G-badge edit handlers unchanged | `TestRegressionGBadgeEdit` | all GREEN |
| T10 | Status strip shows `elevationSpikes.length` | `TestStatusStrip` | already GREEN |
| T11a | Placement hint text present | `TestPlacementHint` | RED → GREEN |
| T11b | Hint is `x-show="spikeMode"` | `TestPlacementHint` | RED → GREEN |
| T12 | APP_VERSION = v4.95 | `TestAppVersion` | RED → GREEN |

**Suite total:** 23/23 new tests GREEN. Full suite: 408 passed, 4 pre-existing Bambu failures unchanged, 20 skipped.

---

## Test Drive for Thomas

1. Open the editor — load the Delaveaga Hole 5 EGM (or any hole with an image)
2. Click **Add Spike** in the toolbar — button goes orange-dark with a ring; canvas cursor becomes a crosshair; bottom-left shows "Click to place a spike · Esc to cancel"
3. Click an area of the fringe where you know real-world ground is higher than the heat map suggests (e.g. the uphill fringe edge)
4. A G-badge appears at that exact pixel with the input auto-focused (value defaults to nearest existing spike's mm, or 0.0 if there are none)
5. Type the real-world height in mm (e.g. `8.5`) and press Enter — value commits, autoSave fires
6. Click **Generate** — the TPS pipeline now has an extra constraint at that fringe location, pulling the surface up; the regenerated 3MF fringe will rise at that point via the Gaussian bump

To cancel without placing: press **Esc** or click **Add Spike** again.

---

## Follow-up: T4 — Delete Affordance (Queued)

T4 (delete user-placed spikes only, not OCR spikes) is queued and ready to dispatch. The `source` field added in this task is the prerequisite — T4 will use `sp.source === 'user'` to gate the delete button.
