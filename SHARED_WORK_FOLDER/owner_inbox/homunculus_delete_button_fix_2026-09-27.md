# Homunculus Delete Button Fix — v0.7 / Herman 2.4.2
<!-- v1.0 · 2026-09-27 -->

## What was fixed

The **Delete** button on the Herman dashboard did nothing on click. The other two buttons (Start, Stop) worked correctly.

**Root cause:** In `homunculus_brain/dashboard.py`, the `timerBtns()` JS function built the Delete onclick via a template literal. The Python source `\\'` in that string produces `\'` in JS source. Inside a template literal, `\'` is a valid JS escape that simply yields `'`. So the confirm() call received the project name wrapped in bare single quotes — which broke the JS string literal and caused a silent syntax error.

Example of the broken DOM output for project "Golf Timer":

```
if(confirm('Delete timer 'Golf Timer'? This cannot be undone.'))...
```

**Fix:** Replace the `\'` delimiters with HTML entity `&quot;` (which decodes to `"` when the browser parses the innerHTML-assigned HTML). The confirm dialog now shows double quotes around the project name, which is unambiguous and safe.

Fixed DOM output:

```
if(confirm('Delete timer "Golf Timer"? This cannot be undone.'))...
```

## Files changed

| File | Change |
|---|---|
| `homunculus_brain/dashboard.py` | Line ~973: `\\'${esc(project)}\\'` → `&quot;${esc(project)}&quot;` in Delete onclick; `DASHBOARD_VERSION` v0.6 → **v0.7** |
| `homunculus_brain/__init__.py` | `VERSION` 2.4.1 → **2.4.2** |
| `tests/test_delete_button_fix.py` | New TDD file — 6 tests written RED first, then GREEN |
| `tests/test_dashboard.py` | Updated 2 stale v0.6 version assertions → v0.7 |
| `tests/test_timer_row_buttons.py` | Updated stale v0.6 / 2.4.0 exact checks → minimum-version checks |
| `tests/test_timers_routes.py` | Updated stale v0.6 version assertion → v0.7 |

## TDD cycle

**RED (before fix):**
- `test_delete_onclick_confirm_no_bare_single_quote_around_project` — FAILED (found `\'${esc(project)}\'` in confirm arg)
- `test_dashboard_version_is_v07` — FAILED (was v0.6)
- `test_herman_version_is_242` — FAILED (was 2.4.1)

**GREEN (after fix):** All 6 new tests pass. Full suite: **312 passed, 0 failed**.

## Apostrophe follow-up (not in scope)

Project names containing `'` (e.g. "Bob's Timer") would still produce broken JS in the `timerAction(...)` argument for all three buttons (Start, Stop, Delete equally). This is a pre-existing limitation. `esc()` does not encode single quotes. Fix-forward when needed: add `'` → `&#39;` to `esc()` or pass the project name via a `data-` attribute.

## Manual verify steps

1. Hard-refresh browser: **Cmd+Shift+R** (check v0.7 badge in upper-left)
2. Click **Delete** on any timer — confirm dialog appears with project name in double quotes
3. Click **OK** — timer disappears from the list
4. Start and Stop still work normally
