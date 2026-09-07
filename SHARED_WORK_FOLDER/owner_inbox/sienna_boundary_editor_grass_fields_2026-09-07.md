# Boundary Editor — Grass Fields "Ignored" Investigation

**Author:** Sienna (Full-Stack Application Developer)
**Date:** 2026-09-07
**Task ID:** 11
**Problem:** Thomas reports the grass fields (`grassAmplitude`, `grassSpacing`) on the Boundary Editor UI are being ignored.

---

## TL;DR

The plumbing is intact end-to-end. Values typed into the UI are bound to Alpine state, included in the save payload, written to the EGM on disk, and read back by the 3MF pipeline. **The likely reason a user perceives them as "ignored" is the silent early-return in `autoSave()` at `app/templates/editor.html:2000-2001`** — if the user tweaks a grass field before an image has finished loading, before any polygon exists, or with an empty course/hole name, `autoSave()` returns without saving *and without any flash message*. The field value stays in memory but never reaches disk. On next reload, the EGM's old value comes back and the user sees "nothing changed."

There is also a secondary hazard: an EGM edited outside the UI (git checkout of an older revision, a hand edit, a script) can silently override whatever the UI most recently wrote, because the UI has no reload-if-changed watcher on the underlying EGM file. Today's `1.0/1.0` regression on DeLaveaga Hole 11a was introduced this way (see Root Cause of Today's Regression below).

---

## Trace: UI → Disk → Pipeline

### 1. UI binding (Boundary Editor)

- **Fields:** `app/templates/editor.html:60` and `:69`
  ```html
  <input type="number" x-model.number="grassAmplitude" @change="autoSave()" .../>
  <input type="number" x-model.number="grassSpacing"   @change="autoSave()" .../>
  ```
- **Alpine state defaults:** `editor.html:635-636` (`grassAmplitude: 0.5`, `grassSpacing: 2.4`).
- **Load from EGM:** `editor.html:2191-2192` — populates state from the loaded `.egm` JSON, falling back to `0.5 / 2.4` when the field is missing.
- **Reset on New Project:** `editor.html:2255-2256` — resets to `0.5 / 2.4`.

### 2. Save payload

- **`autoSave()` → `POST /api/boundaries`:** `editor.html:2025-2026` includes both fields verbatim.
- **`generate3MF()` → `POST /api/generate_models`:** `editor.html:2388-2389` also includes both fields in the pre-generate autoSave.

### 3. Save handler (Flask)

- **Route:** `app/app.py:867 save_boundaries()` — `json.dump(data, f, indent=2)` writes the entire payload to `<course>/EGMs/<file>.egm`. Grass fields are persisted verbatim; no server-side default injection, no key rename.

### 4. Pipeline read

- **Route:** `app/app.py:1430 generate_models()` reads the EGM from disk by `course + hole` (does NOT use the JSON body's grass values — it re-reads the file). This means: **if `autoSave()` silently skipped, the pipeline uses the STALE on-disk value, not the value currently shown in the UI.**
- **Consumer:** `app/gradient_surface_diagnostic.py:7315-7316`:
  ```python
  grass_amplitude = _egm_data.get("grassAmplitude", 0.5)
  grass_spacing   = _egm_data.get("grassSpacing",   2.4)
  ```
  Applied to the smooth green mesh at `:7325-7331` and to the fringe at `:7470-7476`. Both paths use identical values.

The plumbing itself is not buggy. This matches yesterday's Sienna task #4 finding (that investigation surfaced the `smooth_mesh_flat` orphan bug at line 7681, since fixed by Topo in task #5).

---

## Root Cause of the "Ignored" Feeling

### Primary: `autoSave()` silently skips valid keystroke saves

`editor.html:1999-2001`:

```javascript
async autoSave() {
  if (!this.imgLoaded || this.polygons.length === 0) return;
  if (!this.courseName.trim() || !this.holeName.trim()) return;
  // ...build payload and POST to /api/boundaries
}
```

Any change to `grassAmplitude` or `grassSpacing` fires `@change="autoSave()"`, but the save is dropped without any user-visible flash when:

1. **`!this.imgLoaded`** — user tweaked the field before the golf-hole image finished decoding. Easy on a large PNG or a fresh reload.
2. **`this.polygons.length === 0`** — a brand-new project, or a load in which polygons haven't been restored yet (`_pendingRestore` is populated during `loadProject()` at `:2231` but polygons don't materialize until `loadImage()` finishes).
3. **`!this.courseName.trim() || !this.holeName.trim()`** — course or hole cleared.

Because the guard fires *before* the fetch, there is no HTTP request, no server error, and no `flash()` call. The user sees the input accept their number, but the EGM on disk is unchanged. When they later reload the project (or when `generate_models` reads the EGM), they get the previous value and conclude the field is ignored.

**Multi-user angle (Jim):** this is worse for a second user who is less familiar with the load ordering — they may confidently change grass fields immediately on page load and never see any indication the save was skipped.

### Secondary: no external-change watcher on the EGM file

The UI reads the EGM once on `loadProject()` and then trusts its in-memory state. If the on-disk EGM is mutated between load and next save (git operation, external script, hand edit), the UI's autoSave will happily overwrite it — or, more subtly, if the user Generates without touching any field, the pipeline reads whatever the file has *right now*, not what the UI is showing. This is exactly what produced today's regression trail: commit `53d00f2` wrote `1.0 / 1.0` to `DeLaveaga (Hole 11a).egm` while UI state elsewhere still showed `0.5 / 2.4`.

### Today's `1.0 / 1.0` regression — how it landed

`git show 53d00f2 -- ".../DeLaveaga (Hole 11a).egm"` shows a change from `0.5 / 2.4` to `1 / 1` on 2026-09-07 08:11 as part of a bulk commit that also added new 3MFs and pipeline code. The change is a raw integer (`1`, not `1.0`), which is what `JSON.stringify` from Alpine's `x-model.number` also produces for whole-number inputs — so **the UI could plausibly have written it** if a user typed `1` into each field. However, the accompanying commit message ("update grass parameters in EGM files") reads like an intentional experiment: someone (or an automated agent) was probing whether coarser bumps looked better. The working tree currently has the file reverted to `0.5 / 2.4` (uncommitted local change), consistent with someone realizing the values were wrong and manually fixing them without a UI round-trip.

Either origin — UI save or hand edit — is compatible with the current code. What is *not* consistent with "UI ignored" is any code path that overrides the EGM value. There is none.

---

## Recommended Fix (do NOT apply yet — awaiting Larry's confirmation)

Two-part fix, both in `app/templates/editor.html`. Neither changes the pipeline or the save schema.

### Fix A — Make the autoSave skip visible (small, surgical)

Replace the silent early-return in `autoSave()` at `:2000-2001` with a version that flashes a warning when a save is skipped due to unmet prerequisites AND queues a retry once the prereqs are satisfied. Rough shape:

```javascript
async autoSave() {
  const missing = [];
  if (!this.imgLoaded)                         missing.push('image still loading');
  if (this.polygons.length === 0)              missing.push('no polygons yet');
  if (!this.courseName.trim())                 missing.push('course name empty');
  if (!this.holeName.trim())                   missing.push('hole name empty');
  if (missing.length) {
    this._pendingAutoSave = true;   // retry once prereqs clear
    this.flash('Change kept in memory — will save once ' + missing.join(', '), false, '', 4000);
    return;
  }
  this._pendingAutoSave = false;
  // ...existing save body
}
```

Then invoke `if (this._pendingAutoSave) this.autoSave();` at the tail of `loadImage()` (after `imgLoaded = true` and polygons are restored) so any deferred keystrokes catch up.

### Fix B — Reload-guard the EGM on Generate (belt-and-braces)

Before `/api/generate_models` runs the pipeline, have the client re-POST the current in-memory state to `/api/boundaries` and confirm a fresh checksum (or just await `autoSave()` — it already does this at `editor.html:2361`, but it silently skips if any autoSave guard is unmet). Same underlying fix; primarily a mental model correction: "Generate uses what's on disk, not what's on screen." A small footer badge showing "unsaved changes" when the in-memory state diverges from the last successful save would prevent the user confusion.

### Version bump

If Fix A is applied, bump `APP_VERSION` in `app/app.py:24` from `v4.47` → `v4.48` per team convention (unified version across the main-app pages).

---

## Files Touched (read-only)

- `app/app.py` — routes `/editor`, `/api/boundaries`, `/api/generate_models`, `save_boundaries`, `load_boundaries`.
- `app/templates/editor.html` — Alpine state, form bindings, `autoSave`, `loadProject`, `startNewProject`, `generate3MF`.
- `app/gradient_surface_diagnostic.py` — pipeline consumer of grass values (lines 7315-7331, 7467-7476).
- `ItWentIn/GolfCourses/DeLaveaga/EGMs/DeLaveaga (Hole 11a).egm` — HEAD has `1 / 1`, working tree has `0.5 / 2.4` (uncommitted revert).
- Commit `53d00f2` — introduced the `1.0 / 1.0` regression alongside pipeline improvements.

## Rules Honored

- No `app.test_client()` runs against the live DB or live EGM files.
- No 3MFs regenerated (Topo has parallel ownership).
- No code applied — investigation only, fix recommended and awaiting confirmation.
