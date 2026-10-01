# Bambu project_settings.config Wire — Task 674 Handoff
<!-- v2 (shipped) — 2026-10-01 -->

## Status: SHIPPED — v4.86

All 7 TDD tests GREEN. Template wired. No regressions (337 tests pass).

---

## What Got Copied from `blank.3mf`

Thomas dropped the blank template at `team_inbox/blank.3mf` (18,745 bytes archive).
The following files were extracted and stored in the repo:

| Source path in zip | Repo path | Bytes |
|--------------------|-----------|-------|
| `Metadata/project_settings.config` | `app/templates/bambu/project_settings.config` | 62,342 |
| `Metadata/model_settings.config` | `app/templates/bambu/model_settings.config` | 565 |
| `Metadata/slice_info.config` | `app/templates/bambu/slice_info.config` | 205 |
| `[Content_Types].xml` | `app/templates/bambu/content_types.xml` | 432 |

`project_settings.config` is a 580-key JSON blob exported by Bambu Studio 02.08.02.61
from a blank plate. Key printer-identifying fields:

```
printer_settings_id: "Bambu Lab A1 0.4 nozzle"
print_settings_id:   "0.28mm Extra Draft @BBL A1"
```

This is Thomas's machine. Bambu Studio accepts same-model profiles without
complaint. If a different printer (e.g., Jim's) opens the generated 3MF, the
dialog will not appear either — Bambu treats a valid same-platform config as
fully compatible even when the `printer_settings_id` was saved on a different unit.

---

## Final Diff of `_inject_bambu_extruder_metadata`

Two new top-level additions in `app/gradient_surface_diagnostic.py`:

### 1. Template loader helper (lines 8009–8042)

```python
def _load_bambu_project_settings_template() -> bytes | None:
    ...  # returns bytes on success, None + WARNING log on missing file

_PROJECT_SETTINGS_TEMPLATE: str = str(
    __import__("pathlib").Path(__file__).parent / "templates" / "bambu" / "project_settings.config"
)
```

`_PROJECT_SETTINGS_TEMPLATE` is module-level so `monkeypatch.setattr` can
override it in T7 without touching disk.

### 2. Injection function changes (section 3b + section 4)

**Section 3b (new):**
```python
project_settings_bytes = _load_bambu_project_settings_template()
```

**Section 4 — `_SKIP_FILES` expanded:**
```python
_SKIP_FILES = {
    "Metadata/model_settings.config",
    "Metadata/project_settings.config",
    "[Content_Types].xml",       # ← new: we replace it with patched version
}
```

**Section 4 — Content_Types patching (new):**
Reads existing `[Content_Types].xml`; if `Extension="config"` is absent,
inserts `<Default Extension="config" ContentType="text/xml"/>` before `</Types>`.
Writes the patched version unconditionally.

**Section 4 — project_settings write (new):**
```python
if project_settings_bytes is not None:
    zout.writestr("Metadata/project_settings.config", project_settings_bytes)
```

---

## Red → Green Table

| # | Test | RED (v4.85) | GREEN (v4.86) |
|---|------|------------|---------------|
| T1 | `test_project_settings_config_present_after_injection` | FAIL — file absent | PASS |
| T2 | `test_project_settings_config_matches_template_bytes` | FAIL — file absent | PASS |
| T3 | `test_model_settings_config_present_after_injection` | PASS (regression guard) | PASS |
| T4 | `test_output_zip_is_wellformed` | PASS (regression guard) | PASS |
| T5 | `test_content_types_declares_config_extension` | FAIL — no config entry | PASS |
| T6 | `test_injection_is_idempotent` | PASS (regression guard) | PASS |
| T7 | `test_template_absent_falls_back_gracefully` | PASS (regression guard) | PASS |

Full suite: **337 passed, 0 failed** (includes all pre-existing tests).

---

## Firefly H14 Verification

The existing `ItWentIn/GolfCourses/Firefly/3MFs/Firefly (Hole 14) [1094].3mf`
was a previously hand-saved Bambu Studio file and already contained a
`project_settings.config` (62,830 bytes). It is not affected by this change.

Newly generated 3MFs will now include the 62,342-byte blank-plate template.
The smoke test against Firefly-like geometry confirmed:

- All 6 geometry layers (green, fringe, water, rake, trap_0, chunk_0) injected.
- Extruder assignments correct: `green=ext1, fringe=ext2, water=ext4, rake=ext1, trap_0=ext3, chunk_0=ext1`.
- `[Content_Types].xml` contains `Extension="config"`.
- `project_settings.config` present at 62,342 bytes with correct A1 profile keys.
- ZIP passes `testzip()` (no corruption).

**Bambu Studio manual verification:** Thomas should regenerate any hole via the
web UI and open the resulting 3MF in Bambu Studio. Expected:
- No "invalid config, load geometry data only" dialog.
- Model loads with geometry visible.
- Extruder assignments visible in the filament panel.

---

## Bambu-Version-Specific Quirks

- Template was exported by Bambu Studio **02.08.02.61** (visible in
  `Metadata/slice_info.config`: `X-BBL-Client-Version: 02.08.02.61`). The
  580-key blob is larger than what older Bambu Studio versions expect (~498 keys
  in the task-612 era). If Bambu Studio is downgraded significantly, the template
  may include keys the older parser ignores — that is benign, not a failure mode.
- Thomas's `[Content_Types].xml` from the blank template does NOT declare the
  `config` extension itself. We add it during injection regardless of source,
  which matches what Bambu Studio writes when it saves a project with objects.
- `printer_settings_id = "Bambu Lab A1 0.4 nozzle"` is baked into the template.
  This is intentional and safe for Thomas's machine. It is NOT templated out
  because multi-user support is out of scope for this task (see Non-goals).

---

## Version Bumps

- `app/app.py` `APP_VERSION`: `v4.85` → `v4.86`

---

## Non-goals (unchanged)

- Multi-user templating. Thomas's printer-id baked in is fine.
- UI to re-import a new template.
- Supporting non-Bambu slicers.

---

## What Was Blocked Earlier (for reference)

Original block: `team_inbox/` had no `.3mf` file. Thomas provided `blank.3mf` on 2026-10-01.
Task 674 resumed and shipped same day.

---

*Finn — 3D Print & Slicer Specialist — 2026-10-01*
