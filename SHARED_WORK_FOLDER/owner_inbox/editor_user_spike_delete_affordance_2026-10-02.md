# Editor — User Spike Delete Affordance

**v4.96 · 2026-10-02 · Sienna**

---

## UX Design

### × placement
A small `×` button sits flush to the right edge of the G-badge pill, separated from the value input by a left border. The badge reads: `[G][value input][×]` for user spikes, and `[G][value input]` (no third segment) for OCR spikes.

### Hover visibility
At rest the `×` is a muted green (`#6B8F6B`) on a transparent background — present but quiet. On hover it snaps to red-on-blush (`#B71C1C` on `#FFEBEE`), making the destructive intent unmistakable before the click. Transition is instant (inline `onmouseover`/`onmouseout`) to avoid any perceived lag on quick mouse movements.

### OCR protection
The `×` element uses `x-show="sp.source === 'user'"` — strict equality, not `!== 'ocr'`. This means:
- OCR spikes (`source: 'ocr'`): button hidden by Alpine, never in the tab order
- User spikes (`source: 'user'`): button visible and interactive
- Legacy spikes with no source field: `loadProject` defaults to `'ocr'` (per T3 backward-compat), so no `×` ever appears

The `removeElevationSpike` function already existed from a previous iteration; the template simply now calls it from the `×` button. No new JS was needed.

---

## Red → Green

| # | Test | RED (before) | GREEN (after) |
|---|------|:---:|:---:|
| T1a | User spike template has × / &times; | FAIL | PASS |
| T1b | × is conditional on sp.source === 'user' | FAIL | PASS |
| T2a | Condition uses === 'user' not !== 'ocr' | PASS (vacuous) | PASS |
| T2b | No unconditional delete | SKIP | PASS |
| T3a | loadProject defaults missing source to 'ocr' | PASS | PASS |
| T3b | Condition excludes null/undefined source | FAIL | PASS |
| T4a | Template calls removeElevationSpike | FAIL | PASS |
| T4b | removeElevationSpike function defined | PASS | PASS |
| T5a | × passes sIdx (removes only clicked spike) | FAIL | PASS |
| T5b | removeElevationSpike uses splice | FAIL | PASS |
| T6 | removeElevationSpike triggers autoSave | FAIL | PASS |
| T7a–k | All regression checks | PASS | PASS |
| T8 | APP_VERSION = v4.96 | FAIL | PASS |
| T9 | editor.html contains '4.96' | FAIL | PASS |

**Full suite: 432 passed, 4 pre-existing Bambu failures (unchanged), 20 skipped.**

---

## Test drive for Thomas

1. Open the Boundary Editor and load any hole project (or create a new one).
2. Click **Add Spike** — cursor goes crosshair.
3. Click anywhere on the canvas to place a spike.
4. The new G-badge appears with a muted **×** on its right edge.
5. Hover the **×** — it turns red.
6. Click **×** — the badge disappears immediately, autosave fires.
7. Any OCR-detected G-badge (those placed by "Run Detection") shows no **×** at all — just `[G][value]`. Click the number to edit its mm value as before; Esc reverts.
