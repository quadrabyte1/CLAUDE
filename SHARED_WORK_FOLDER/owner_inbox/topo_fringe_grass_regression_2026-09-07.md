# Fringe Grass Regression — Root Cause Report

**Version:** v1.0
**Date:** 2026-09-07
**Author:** Topo
**Task:** workspace task #8

---

## TL;DR

The fringe "grass" stopped looking like grass because the **grass parameters in `DeLaveaga (Hole 11a).egm` were edited**, not because the code regressed. `grassAmplitude` doubled (0.5 → 1.0 mm) and `grassSpacing` was cut to less than half (2.4 → 1.0 mm). At `spacing=1.0`, the bump radius drops to `R = 0.48 mm` and the position jitter (`±0.5 mm`, per line 6592–6595) is the same order as the spacing itself, so the paraboloid bumps stop reading as an ordered blade pattern and instead pile up as chaotic overlapping high-amplitude spikes — i.e. surface noise, not grass.

**Recommended fix:** revert the two EGM values to their defaults. Do **not** revert commit `53d00f2` — the code changes it contains (grass on smooth green + seam-freeze) are unrelated and desirable.

---

## Evidence

### 1. What changed (commit `53d00f2`, 2026-09-07 08:11)

`ItWentIn/GolfCourses/DeLaveaga/EGMs/DeLaveaga (Hole 11a).egm`:

```diff
-  "grassAmplitude": 0.5,
-  "grassSpacing": 2.4,
+  "grassAmplitude": 1,
+  "grassSpacing": 1,
```

That commit's message even calls it out: *"update grass parameters in EGM files."*

### 2. Where the values are consumed

`app/gradient_surface_diagnostic.py`:

- **L7315–7316** — read from EGM with defaults `0.5` and `2.4` (matches the editor UI defaults at `templates/editor.html:635–636`, `2191–2192`, `2255–2256`).
- **L7327–7328** — applied to the smooth green (new in `53d00f2`).
- **L7467–7473** — applied to the **fringe** (this is the one Thomas is seeing).
- **L6520–6619** — `apply_grass_texture()`:
  - `R = bump_spacing * 0.48` (L6600)
  - `jitter_scale = bump_spacing * 0.5` (L6592)
  - `dz = amplitude * max(0, 1 − (r/R)^2)` (L6606)

### 3. Why the new values kill the grass look

| Parameter | Was | Now | Effect on fringe surface |
| --- | --- | --- | --- |
| `grassSpacing` | 2.4 mm | 1.0 mm | Bump density ↑ ~5.8× (area scaling). Each bump radius R falls from 1.152 mm to 0.48 mm. |
| `grassAmplitude` | 0.5 mm | 1.0 mm | Peak Z displacement doubles. |
| Jitter (derived) | ±1.2 mm | ±0.5 mm | Now equal to spacing, so bump centres essentially randomize and heavily overlap. |

The paraboloid model relies on bumps being *distinct* — reasonably spaced, modest amplitude, jitter smaller than spacing. At 1.0/1.0 the field becomes a noisy random-height crust rather than a legible blade pattern.

### 4. Timeline confirmation

- `DeLaveaga (Hole 11a) [246].3mf` — Sep 6 19:10, still built with `0.5 / 2.4` (looks like grass — known good).
- `[247].3mf` — Sep 6 19:17, first build after the EGM edit → regressed.
- `[248].3mf` — Sep 6 19:19, same params → regressed.

### 5. Rulings on the other leads

- **`app/gradient_surface_diagnostic.py` (M in git status)** — `git diff HEAD` on this file is **empty**. The M flag is a mtime/pyc-refresh artifact; the file matches HEAD. Not the cause.
- **Commit `ea5dcae`** — added diagnostic *scripts* under `scratch/task_719/` and expanded `gradient_surface_diagnostic.py`, but did not change `apply_grass_texture()` or the two grass parameters. Not the cause.
- **Commit `53d00f2` code diff** — the only real code change is that the *smooth green* now also gets grass (previously only the fringe did), with the green's boundary vertices seam-frozen. This is a legit improvement, not a regression, and it does not explain the fringe change.

---

## Recommended Fix (NOT applied — awaiting confirmation)

Revert only the two values in the EGM back to defaults:

```json
"grassAmplitude": 0.5,
"grassSpacing": 2.4,
```

File: `ItWentIn/GolfCourses/DeLaveaga/EGMs/DeLaveaga (Hole 11a).egm` (lines 11–12).

Then regenerate the 3MF — it will produce `[249]` with the correct grass look.

If Thomas *wanted* denser bumps, a safer knob is `spacing≈1.6, amplitude≈0.5`: doubles the bump count without collapsing R below the jitter scale. But default is the right first move.

### Optional hardening (separate small PR)

Consider clamping in `apply_grass_texture` so `jitter_scale = min(bump_spacing * 0.5, bump_spacing - 2*R)` (or just cap at `0.35 * bump_spacing`) to prevent this failure mode when the user cranks spacing down. Not urgent.

---

## Files referenced

- `/Volumes/GIT/CLAUDE/SHARED_WORK_FOLDER/ItWentIn/GolfCourses/DeLaveaga/EGMs/DeLaveaga (Hole 11a).egm` — the two values to revert.
- `/Volumes/GIT/CLAUDE/SHARED_WORK_FOLDER/app/gradient_surface_diagnostic.py:6520–6619, 7315–7328, 7467–7473` — grass texture function + call sites.
- `/Volumes/GIT/CLAUDE/SHARED_WORK_FOLDER/app/templates/editor.html:60–69, 635–636, 2191–2192, 2255–2256` — UI defaults (still `0.5 / 2.4`).
- `/Volumes/GIT/CLAUDE/SHARED_WORK_FOLDER/ItWentIn/GolfCourses/DeLaveaga/3MFs/DeLaveaga (Hole 11a) [246].3mf` — last known-good build (Sep 6 19:10).
- `/Volumes/GIT/CLAUDE/SHARED_WORK_FOLDER/ItWentIn/GolfCourses/DeLaveaga/3MFs/DeLaveaga (Hole 11a) [247].3mf`, `[248].3mf` — regressed builds.
