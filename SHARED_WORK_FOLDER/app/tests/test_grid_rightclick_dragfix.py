"""
test_grid_rightclick_dragfix.py — Bug→TDD for:
  (a) Right-click on set-cell dot deletes it (follows contour spline convention)
  (b) Click-vs-drag discrimination: bare click opens input; click+drag = selection rect

Task 712.  RED written first, implementation follows.

Test inventory
==============

T1  Right-click handler: onRightClick contains grid dot hit check
T2  Right-click on dot: delete path — delete gridCellHeights[idx] in onRightClick
T3  Right-click on dot clears tooltip state (_gridHoveredCell = null after delete)
T4  Right-click fires autoSave after delete
T5  Right-click on empty cell: no delete — miss path exists (no-op beyond prevent default)
T6  Right-click convention: @contextmenu.prevent wired on canvas (already present, regression guard)
T7  Drag threshold constant GRID_DRAG_THRESHOLD_PX = 5 declared
T8  _gridMouseDownAt state variable declared in Alpine data (null initial)
T9  onMouseDown for grid cell: records _gridMouseDownAt instead of immediately calling openGridCell
T10 onMouseMove: abandons pending grid cell if drag threshold exceeded (_gridMouseDownAt cleared)
T11 onMouseUp: calls openGridCell when _gridMouseDownAt is set AND threshold not exceeded
T12 onMouseUp: clears _gridMouseDownAt after handling (so it's reset each click)
T13 Rubber band drag still reached: onMouseDown falls through to rubberBand logic when drag exceeds threshold
T14 Regression — tooltip still works (_gridHoveredCell in onMouseMove)
T15 Regression — Enter commits input (commitGridCell wired to keydown.enter)
T16 Regression — Delete key from open cell still works (deleteGridCell in keydown handler)
T17 APP_VERSION bumped to v5.05
T18 editor.html on-page version is v5.05

Run:
    cd /Volumes/GIT/CLAUDE/SHARED_WORK_FOLDER
    python -m pytest app/tests/test_grid_rightclick_dragfix.py -v
"""
from __future__ import annotations

import re
import sys
from pathlib import Path

import pytest

# ---------------------------------------------------------------------------
# Path setup
# ---------------------------------------------------------------------------
APP_DIR = Path(__file__).parent.parent
sys.path.insert(0, str(APP_DIR))

EDITOR_HTML = APP_DIR / "templates" / "editor.html"
APP_PY = APP_DIR / "app.py"


def _html() -> str:
    return EDITOR_HTML.read_text(encoding="utf-8")


def _app_py() -> str:
    return APP_PY.read_text(encoding="utf-8")


def _right_click_body() -> str:
    html = _html()
    start = html.find("    onRightClick(e) {")
    assert start != -1, "onRightClick not found in editor.html"
    return html[start: start + 3000]


def _mouse_down_body() -> str:
    html = _html()
    start = html.find("    onMouseDown(e) {")
    assert start != -1, "onMouseDown not found"
    return html[start: start + 3000]


def _mouse_move_body() -> str:
    html = _html()
    start = html.find("    onMouseMove(e) {")
    assert start != -1, "onMouseMove not found"
    return html[start: start + 6000]


def _mouse_up_body() -> str:
    html = _html()
    start = html.find("    onMouseUp(e) {")
    assert start != -1, "onMouseUp not found"
    return html[start: start + 3000]


# ---------------------------------------------------------------------------
# T1 — onRightClick has a grid dot hit section
# ---------------------------------------------------------------------------

class TestRightClickHandler:
    """T1 — onRightClick checks for grid dot proximity."""

    def test_rightclick_has_grid_hit_check(self):
        body = _right_click_body()
        # Must reference gridCellHeights and the delete path
        assert "gridCellHeights" in body, (
            "onRightClick does not reference gridCellHeights — grid delete not implemented"
        )


# ---------------------------------------------------------------------------
# T2 — Right-click on set-cell dot deletes the cell
# ---------------------------------------------------------------------------

class TestRightClickDeletesDot:
    """T2 — Hitting a dot on right-click removes it from gridCellHeights."""

    def test_delete_in_rightclick(self):
        body = _right_click_body()
        assert re.search(
            r'delete\s+this\.gridCellHeights\[|delete\s+gridCellHeights\[',
            body
        ), "onRightClick does not delete from gridCellHeights"

    def test_rightclick_uses_canvas_px_hit_detection(self):
        body = _right_click_body()
        # The grid hit detection for right-click must work in canvas CSS px space
        # (same as the hover detection: e.clientX - rect.left etc.)
        assert re.search(
            r'clientX.*rect\.left|dotR|Math\.hypot|dx.*dx.*dy.*dy',
            body, re.DOTALL
        ), (
            "onRightClick does not appear to use dot-radius hit detection "
            "(expected clientX/clientY + dotR pattern)"
        )


# ---------------------------------------------------------------------------
# T3 — Right-click delete clears tooltip state
# ---------------------------------------------------------------------------

class TestRightClickClearsTooltip:
    """T3 — After deleting a dot, _gridHoveredCell is nulled."""

    def test_rightclick_clears_hovered_cell(self):
        body = _right_click_body()
        assert re.search(
            r'_gridHoveredCell\s*=\s*null',
            body
        ), "onRightClick does not clear _gridHoveredCell after delete"


# ---------------------------------------------------------------------------
# T4 — Right-click delete fires autoSave
# ---------------------------------------------------------------------------

class TestRightClickAutoSave:
    """T4 — autoSave() is called after a dot is deleted via right-click."""

    def test_rightclick_calls_autosave(self):
        body = _right_click_body()
        assert "autoSave" in body, (
            "onRightClick does not call autoSave() after grid cell delete"
        )


# ---------------------------------------------------------------------------
# T5 — Right-click on empty cell is a no-op (miss path)
# ---------------------------------------------------------------------------

class TestRightClickMissIsNoop:
    """T5 — Right-click that misses all dots does nothing beyond prevent default."""

    def test_rightclick_has_miss_path(self):
        body = _right_click_body()
        # The function must have conditional logic — not always deleting.
        # Verify the delete happens inside an `if` block (not unconditionally).
        delete_pos = body.find("delete this.gridCellHeights")
        if delete_pos == -1:
            delete_pos = body.find("delete gridCellHeights")
        assert delete_pos != -1, "No delete call found — T2 should have caught this"
        # There must be an `if` (or equivalent) before the delete within the grid section
        grid_section_start = body.find("gridCellHeights")
        assert grid_section_start != -1
        section = body[grid_section_start: delete_pos + 80]
        assert re.search(r'\bif\b', section), (
            "Grid cell delete in onRightClick does not appear guarded by an if — "
            "every right-click would delete even on empty cells"
        )


# ---------------------------------------------------------------------------
# T6 — @contextmenu.prevent is wired on canvas (regression guard)
# ---------------------------------------------------------------------------

class TestContextMenuPrevented:
    """T6 — @contextmenu.prevent on canvas element prevents native context menu."""

    def test_contextmenu_prevent_on_canvas(self):
        html = _html()
        assert "@contextmenu.prevent" in html, (
            "@contextmenu.prevent not found on canvas — native context menu will appear"
        )

    def test_contextmenu_calls_onRightClick(self):
        html = _html()
        assert re.search(r'@contextmenu\.prevent\s*=\s*["\']onRightClick\(\$event\)', html), (
            "@contextmenu.prevent does not invoke onRightClick($event)"
        )


# ---------------------------------------------------------------------------
# T7 — GRID_DRAG_THRESHOLD_PX = 5 constant declared
# ---------------------------------------------------------------------------

class TestDragThresholdConstant:
    """T7 — The 5-px drag discrimination threshold is defined as a named constant."""

    def test_grid_drag_threshold_declared(self):
        html = _html()
        # Accepts Alpine data property form (GRID_DRAG_THRESHOLD_PX: 5)
        # or standalone const form (GRID_DRAG_THRESHOLD_PX = 5)
        assert re.search(r'GRID_DRAG_THRESHOLD_PX\s*[=:]\s*5', html), (
            "GRID_DRAG_THRESHOLD_PX = 5 (or : 5) constant not found in editor.html"
        )


# ---------------------------------------------------------------------------
# T8 — _gridMouseDownAt state variable in Alpine data
# ---------------------------------------------------------------------------

class TestGridMouseDownAtState:
    """T8 — _gridMouseDownAt holds pending click info before threshold decision."""

    def test_gridMouseDownAt_declared(self):
        html = _html()
        assert "_gridMouseDownAt" in html, (
            "_gridMouseDownAt not declared in editor.html"
        )

    def test_gridMouseDownAt_null_initial(self):
        html = _html()
        assert re.search(r'_gridMouseDownAt\s*:\s*null', html), (
            "_gridMouseDownAt not initialised to null"
        )


# ---------------------------------------------------------------------------
# T9 — onMouseDown defers grid cell open (records pending state instead)
# ---------------------------------------------------------------------------

class TestMouseDownDefersGridOpen:
    """T9 — onMouseDown records _gridMouseDownAt instead of calling openGridCell immediately."""

    def test_mousedown_records_gridMouseDownAt(self):
        body = _mouse_down_body()
        assert "_gridMouseDownAt" in body, (
            "onMouseDown does not set _gridMouseDownAt — still opening immediately"
        )

    def test_mousedown_does_not_call_openGridCell_directly(self):
        body = _mouse_down_body()
        # openGridCell must NOT be called directly from onMouseDown for the grid path.
        # It should be deferred to onMouseUp.
        assert "openGridCell" not in body, (
            "onMouseDown still calls openGridCell() directly — "
            "click/drag discrimination not implemented"
        )


# ---------------------------------------------------------------------------
# T10 — onMouseMove abandons pending cell if drag threshold exceeded
# ---------------------------------------------------------------------------

class TestMouseMoveAbandonsPendingCell:
    """T10 — onMouseMove clears _gridMouseDownAt when movement exceeds threshold."""

    def test_mousemove_clears_gridMouseDownAt_on_drag(self):
        body = _mouse_move_body()
        assert "_gridMouseDownAt" in body, (
            "onMouseMove does not reference _gridMouseDownAt — "
            "drag threshold check not implemented"
        )

    def test_mousemove_uses_drag_threshold(self):
        body = _mouse_move_body()
        assert re.search(r'GRID_DRAG_THRESHOLD_PX', body), (
            "onMouseMove does not reference GRID_DRAG_THRESHOLD_PX — "
            "drag abandonment threshold not checked in mousemove"
        )


# ---------------------------------------------------------------------------
# T11 — onMouseUp calls openGridCell when pending and threshold not exceeded
# ---------------------------------------------------------------------------

class TestMouseUpOpensGridCell:
    """T11 — onMouseUp completes the click by calling openGridCell."""

    def test_mouseup_calls_openGridCell(self):
        body = _mouse_up_body()
        assert "openGridCell" in body, (
            "onMouseUp does not call openGridCell — bare click will never open the input"
        )

    def test_mouseup_checks_gridMouseDownAt(self):
        body = _mouse_up_body()
        assert "_gridMouseDownAt" in body, (
            "onMouseUp does not check _gridMouseDownAt — "
            "click/drag discrimination not implemented in mouseup"
        )


# ---------------------------------------------------------------------------
# T12 — onMouseUp clears _gridMouseDownAt after handling
# ---------------------------------------------------------------------------

class TestMouseUpClearsPending:
    """T12 — _gridMouseDownAt is nulled in onMouseUp to reset for next click."""

    def test_mouseup_clears_gridMouseDownAt(self):
        body = _mouse_up_body()
        assert re.search(r'_gridMouseDownAt\s*=\s*null', body), (
            "onMouseUp does not clear _gridMouseDownAt — pending state leaks between clicks"
        )


# ---------------------------------------------------------------------------
# T13 — Rubber band drag still reachable (regression: was shadowed by grid open)
# ---------------------------------------------------------------------------

class TestRubberBandDragStillReachable:
    """T13 — The rubber band selection path in onMouseDown is still reachable.

    With the old code, a click anywhere inside a grid cell would immediately
    open the input and `return`, preventing rubber band from starting.
    After the fix, grid cells only record _gridMouseDownAt — so the rubber band
    path can still start when the user drags.
    """

    def test_rubberBand_code_still_present_in_mousedown(self):
        body = _mouse_down_body()
        assert "rubberBand" in body, (
            "rubberBand logic is missing from onMouseDown — regression"
        )

    def test_mousedown_does_not_return_early_in_grid_path(self):
        body = _mouse_down_body()
        # After recording _gridMouseDownAt, the code must NOT `return` immediately —
        # it should fall through so the global mouseup listener is attached and
        # the rubber band can start on drag.
        # Find where _gridMouseDownAt is set:
        pending_pos = body.find("_gridMouseDownAt")
        if pending_pos == -1:
            pytest.skip("_gridMouseDownAt not found — T8/T9 should catch this")
        # Extract a short window after the pending-set
        window = body[pending_pos: pending_pos + 300]
        # The old `return` after openGridCell must be gone — there should NOT be
        # an immediate `return;` right after the _gridMouseDownAt assignment.
        # Allow up to ~120 chars for the assignment itself; then check for return.
        assignment_end = window.find(";")
        if assignment_end != -1:
            after_assign = window[assignment_end + 1: assignment_end + 50].strip()
            assert not after_assign.startswith("return"), (
                "onMouseDown immediately returns after setting _gridMouseDownAt — "
                "rubber band drag will still be blocked"
            )


# ---------------------------------------------------------------------------
# T14 — Regression: tooltip still works (_gridHoveredCell updated in onMouseMove)
# ---------------------------------------------------------------------------

class TestTooltipRegression:
    """T14 — Hover tooltip (task 710) is unbroken."""

    def test_gridHoveredCell_still_updated_in_onMouseMove(self):
        body = _mouse_move_body()
        assert "_gridHoveredCell" in body, (
            "_gridHoveredCell no longer updated in onMouseMove — tooltip regression"
        )


# ---------------------------------------------------------------------------
# T15 — Regression: Enter key commits grid input
# ---------------------------------------------------------------------------

class TestEnterCommitsRegression:
    """T15 — Enter key still wired to commitGridCell()."""

    def test_enter_commits_gridcell(self):
        html = _html()
        assert re.search(
            r'@keydown[^>]*enter[^>]*commitGridCell|commitGridCell.*keydown.*enter',
            html, re.IGNORECASE | re.DOTALL
        ), "Enter key → commitGridCell() wiring is missing (regression)"


# ---------------------------------------------------------------------------
# T16 — Regression: Delete key from open cell still works
# ---------------------------------------------------------------------------

class TestDeleteKeyRegression:
    """T16 — Delete key in open grid cell still calls deleteGridCell."""

    def test_delete_key_calls_deleteGridCell(self):
        html = _html()
        assert re.search(
            r'deleteGridCell.*Delete|Delete.*deleteGridCell|'
            r'deleteGridCell\(this\._gridActiveCell\.idx\)',
            html, re.DOTALL
        ), "Delete key → deleteGridCell() wiring missing (regression)"


# ---------------------------------------------------------------------------
# T17 — APP_VERSION bumped to v5.05
# ---------------------------------------------------------------------------

class TestAppVersionBump:
    """T17 — APP_VERSION is v5.05."""

    def test_app_version_is_v5_05(self):
        src = _app_py()
        m = re.search(r'APP_VERSION\s*=\s*["\']v(\d+)\.(\d+)["\']', src)
        assert m is not None, "APP_VERSION not found in app.py"
        major, minor = int(m.group(1)), int(m.group(2))
        assert (major, minor) == (5, 5), (
            f"APP_VERSION is v{major}.{minor:02d} — expected v5.05"
        )


# ---------------------------------------------------------------------------
# T18 — editor.html on-page version is v5.05
# ---------------------------------------------------------------------------

class TestEditorHtmlVersionBump:
    """T18 — editor.html on-page version comment is v5.05."""

    def test_editor_version_is_v5_05(self):
        html = _html()
        m = re.search(r'Boundary Editor v(\d+)\.(\d+)', html)
        assert m is not None, "No 'Boundary Editor vX.XX' version string in editor.html"
        major, minor = int(m.group(1)), int(m.group(2))
        assert (major, minor) == (5, 5), (
            f"editor.html version is v{major}.{minor:02d} — expected v5.05"
        )
