# Global Serial Counter — Migration Notes
**Date:** 2026-09-21  
**Task:** 562  
**Author:** Sienna

---

## Root Cause

Two interacting bugs made per-course serials collision-prone:

1. **CLI-doesn't-commit bug.** `generate_stl_3mf.py` called `peek_next_serial(course)` to embed the serial in the filename, but never called `commit_serial(course)` after export. The web editor's route (in `gradient_surface_diagnostic.run_pipeline`) did call `commit_serial` after export — so CLI runs left the counter stale.

2. **Per-course scope too narrow.** Even with correct commits, two courses sharing a serial number (e.g. Stanford [173] and DeLaveaga [252]) meant a bare serial stamped on a physical print gave no hint of which course it belonged to. Grepping `[173]` across the tree could match multiple courses.

Live proof: `Stanford (Hole 08) [173].3mf` (CLI, Sep 18, 16 KB flat slab) and `Stanford (Hole 8gi) [173].3mf` (editor, Sep 21, 21 MB real) both exist with the same number.

---

## New Design

**One global counter** at `app/global_serial.json`, starting at 1000.

- Starting at 1000 means old per-course serials (max ~252) are instantly distinguishable from new global serials.
- The counter is committed at the **top of every Generate handler** — the Flask route or the CLI entrypoint — before any pipeline code runs. Pipeline code receives the serial as an explicit `int` argument; it never reads or writes the counter.
- Serials are cheap. A serial burned on a failed generate is fine and by design.
- `app/global_serial.json` uses the same atomic-write pattern (tmp + `os.replace`) as the old per-course files.
- A process-level `threading.Lock` prevents races between concurrent Flask worker threads.

---

## Files Changed

| File | Change |
|------|--------|
| `app/serial_engraver.py` | Added `STARTING_GLOBAL_SERIAL = 1000`, `GLOBAL_SERIAL_PATH`, `_GLOBAL_SERIAL_LOCK`, `peek_next_global_serial()`, `commit_global_serial()`. Kept `peek_next_serial(course)` and `commit_serial(course)` as deprecated shims that log `DeprecationWarning` and route to the global versions. |
| `app/generate_stl_3mf.py` | `generate_from_egm()` gains `serial: int | None = None` parameter. Internal `peek_next_serial()` call removed and replaced with the passed-in value. `generate_from_egm_file()` gains same `serial` parameter, forwarded. CLI `__main__` block calls `commit_global_serial()` and passes result to `generate_from_egm_file()`. |
| `app/gradient_surface_diagnostic.py` | `run_pipeline()` gains `serial: int | None = None` parameter. Internal `peek_next_serial()` / `commit_serial()` calls removed. Filename construction uses the passed-in serial. `main()` CLI entrypoint calls `commit_global_serial()` and passes result. |
| `app/app.py` | `/api/generate_models` route calls `commit_global_serial()` at click time (before any pipeline code) and passes `serial=_serial` to `run_pipeline()`. `APP_VERSION` bumped from v4.55 → v4.56. |
| `app/tests/__init__.py` | Created (empty package marker). |
| `app/tests/test_serial_engraver.py` | 8 TDD tests (written RED first, then implementation made them GREEN). |

---

## Red → Green Summary

All 8 tests were written before the implementation and confirmed to fail (ERROR on `AttributeError: module has no attribute 'GLOBAL_SERIAL_PATH'`). After the implementation:

```
tests/test_serial_engraver.py::test_commit_first_call_returns_starting_value PASSED
tests/test_serial_engraver.py::test_commit_successive_calls                  PASSED
tests/test_serial_engraver.py::test_commit_atomic_concurrent                 PASSED
tests/test_serial_engraver.py::test_peek_does_not_advance                    PASSED
tests/test_serial_engraver.py::test_deprecated_shim_peek                     PASSED
tests/test_serial_engraver.py::test_generate_from_egm_file_uses_explicit_serial PASSED
tests/test_serial_engraver.py::test_flask_route_commits_serial_exactly_once  PASSED
tests/test_serial_engraver.py::test_no_course_serial_json_modified           PASSED

8 passed in 0.65s
```

---

## Migration Notes

### Frozen per-course files
All existing `serial.json` files under `ItWentIn/GolfCourses/*/` are left untouched. They are a historical record: "the last per-course serial used before the switch." Stanford's last was 173; DeLaveaga's last was 251 (next was 252 in the file). Do not delete or reset them.

### Backward-compat shims
`peek_next_serial(course)` and `commit_serial(course)` remain in `serial_engraver.py` but log `DeprecationWarning` and route to the global counter. The `course` argument is ignored. Remove these shims in v0.2 after a full search confirms no callers remain.

### Starting value
`app/global_serial.json` does not exist yet. The first Generate click after deployment will create it with `{"next_serial": 1001}` and return 1000.

---

## Follow-up Suggestions

1. **UI serial preview** — The editor's Generate button could display the next serial before the click (using a lightweight `/api/next_serial` endpoint that calls `peek_next_global_serial()`). Thomas may want this for labelling prints before they come off the bed.

2. **Shim removal audit** — Search `app/` for any remaining calls to `peek_next_serial` or `commit_serial` with a course argument, confirm none remain, then delete the shim functions and their tests (or update tests to assert the shims are gone).

3. **Multi-process safety** — The current lock is thread-level only. If app is ever deployed under a multi-process server (gunicorn workers > 1), the atomic `os.replace` is still safe for the file itself but two processes could race on the read-increment-write cycle. A `fcntl.flock` advisory lock around the read+write would close that gap.
