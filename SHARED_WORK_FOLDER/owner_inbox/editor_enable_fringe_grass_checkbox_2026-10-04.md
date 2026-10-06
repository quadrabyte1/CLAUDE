# Enable Fringe Grass Checkbox — v5.06
**Task 714 · Sienna · 2026-10-05**

---

## Checkbox Placement + Default

Added to the config panel in `editor.html`, immediately after the existing **Cap fringe at frame height** checkbox. Section heading: **Fringe grass**. Label text: **Enable Fringe Grass**. Wired with `x-model="enableFringeGrass" @change="autoSave()"`.

Alpine default: `enableFringeGrass: true` — checked by default, so existing behaviour is fully preserved for all current projects.

---

## EGM Schema Addition

New boolean field: `enableFringeGrass` (default `true` on backward-compat load).

- `autoSave()` writes `enableFringeGrass: this.enableFringeGrass` to the EGM JSON.
- `loadProject()` reads it with the `!== false` pattern — missing key in old EGMs defaults to `true`.
- `clearEditorState()` resets to `true`.
- `startNewProject()` resets to `true`.
- `/api/boundaries/load` returns the raw EGM field (no server-side logic needed — pass-through).

---

## Code Change in `gradient_surface_diagnostic.py`

`run_pipeline()` gains a new `enable_fringe_grass: bool | None = None` parameter.

At resolve time (line ~8595), the value is read from the parameter or falls back to `_egm_data.get("enableFringeGrass", True)` — same pattern as `applyFringeFrameCap`.

At the grass application site (line ~8950), both grass calls are wrapped in a single conditional:

```python
if enable_fringe_grass:
    # ... existing apply_grass_texture_v2 / apply_grass_texture calls ...
else:
    print("  Skipping grass texture (enableFringeGrass=False) — fringe will be smooth.")
```

Neither `apply_grass_texture_v2` nor `apply_grass_texture` is modified. The grass texture functions themselves are untouched.

`app.py` `generate_models` route reads `enable_fringe_grass = bool(data.get("enableFringeGrass", True))` and passes it to `run_pipeline(enable_fringe_grass=enable_fringe_grass, ...)`.

---

## Red → Green Table

| # | Test | RED before | GREEN after |
|---|------|-----------|------------|
| T1a | Checkbox `x-model="enableFringeGrass"` in HTML | FAIL | PASS |
| T1b | Label text "Enable Fringe Grass" present | FAIL | PASS |
| T1c | `@change="autoSave()"` wired | FAIL | PASS |
| T2 | Alpine default `enableFringeGrass: true` | FAIL | PASS |
| T3 | `autoSave()` includes `enableFringeGrass` | FAIL | PASS |
| T4 | `loadProject()` assigns `this.enableFringeGrass` | FAIL | PASS |
| T5 | `loadProject()` uses `!== false` pattern | FAIL | PASS |
| T6 | `clearEditorState()` resets to `true` | FAIL | PASS |
| T7 | `startNewProject()` resets to `true` | FAIL | PASS |
| T8 | EGM round-trip `false` → load returns `false` | FAIL | PASS |
| T9 | EGM round-trip `true` → load returns `true` | FAIL | PASS |
| T8b | Old EGM (missing field) → load returns `true` | FAIL | PASS |
| T10 | `run_pipeline` with `false` → grass NOT called | FAIL | PASS |
| T11 | `run_pipeline` with `true` → grass IS called | FAIL | PASS |
| T12 | `app.py` route reads `enableFringeGrass` | FAIL | PASS |
| T12b | `app.py` route passes `enable_fringe_grass` to pipeline | FAIL | PASS |

**Full suite: 431 passed, 0 failed** (baseline was 401; 16 new + 14 previously failing version-assertion tests from task 712 updated to accept ≥ v5.05).

---

## Test Drive for Thomas

1. Hard-refresh the editor (`Cmd+Shift+R`).
2. Open any existing project — the **Enable Fringe Grass** checkbox appears checked in the Fringe grass section of the config panel.
3. Click **Generate** — fringe grass appears as before.
4. Uncheck **Enable Fringe Grass** — the checkbox unchecks, autosave fires immediately.
5. Click **Generate** — the fringe prints smooth; no grass blades. The pipeline log will show: `Skipping grass texture (enableFringeGrass=False) — fringe will be smooth.`
6. Save and reload the project — the checkbox state is preserved (unchecked stays unchecked).
7. Open a new project — checkbox resets to checked (default on).
