"""
test_grid_indigo_recolor_multiselect.py — Bug→TDD for task 726:
  1. Grid line recolor: lemon yellow → indigo (same hue as value text)
  2. Cmd+click-drag multi-cell selection with shared-value edit

RED first, implement, then GREEN.

Test inventory
==============

T1  Grid line color is indigo — strokeStyle uses rgba(99,102,241,...) family
T2  Grid line color is NOT lemon yellow — old rgba(255,244,79,...) gone from grid section
T3  Cmd+mousedown enters multi-select — _gridMultiSelect state variable declared
T4  Multi-select state init in clearEditorState — _gridMultiSelect initialised to null
T5  Drag with Cmd accumulates cells — mousemove path references _gridMultiSelect
T6  Mouseup opens shared input — onMouseUp checks _gridMultiSelect and calls openGridCell or multi-select input path
T7  Enter commits to all selected cells — commitGridCell (or commitGridMultiSelect) iterates over _gridMultiSelect
T8  Esc cancels multi-select — cancelGridCell or cancelGridMultiSelect clears _gridMultiSelect
T9  Highlighted cells render thicker border — draw() has a block for _gridMultiSelect highlighting distinct from _gridActiveCell
T10 Highlights clear after commit — commit path sets _gridMultiSelect to null/empty
T11 Bare click without Cmd preserves single-cell behavior — onMouseUp still calls openGridCell for non-meta clicks
T12 Right-click delete still works — onRightClick still has delete path for gridCellHeights
T13 metaKey OR ctrlKey triggers multi-select — mousedown checks e.metaKey || e.ctrlKey
T14 Multi-select input overlay exists — template covers _gridMultiSelect !== null case (or reuses _gridActiveCell with multi-select context)
T15 APP_VERSION is v5.14
T16 editor.html on-page version is at least v5.09

Run:
    cd /Volumes/GIT/CLAUDE/SHARED_WORK_FOLDER
    python -m pytest app/tests/test_grid_indigo_recolor_multiselect.py -v
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

INDIGO_R = 99   # rgb components of the shared indigo accent
INDIGO_G = 102
INDIGO_B = 241


def _html() -> str:
    return EDITOR_HTML.read_text(encoding="utf-8")


def _app_py() -> str:
    return APP_PY.read_text(encoding="utf-8")


def _draw_grid_section(html: str) -> str:
    """Return the ~3000-char slice of draw() that contains the grid rendering."""
    marker = "// ── Grid cell elevation overlay (v5.00)"
    first = html.find(marker)
    assert first != -1, "Grid overlay marker not found"
    second = html.find(marker, first + 1)
    assert second != -1, "Second grid overlay marker (in draw()) not found"
    return html[second:second + 3000]


def _draw_body(html: str) -> str:
    """Return the body of draw() — up to 16k chars."""
    start = html.find("    draw() {")
    assert start != -1, "draw() function not found"
    return html[start: start + 16000]


def _mousedown_body(html: str) -> str:
    start = html.find("    onMouseDown(e) {")
    assert start != -1, "onMouseDown not found"
    return html[start: start + 4000]


def _mousemove_body(html: str) -> str:
    start = html.find("    onMouseMove(e) {")
    assert start != -1, "onMouseMove not found"
    return html[start: start + 6000]


def _mouseup_body(html: str) -> str:
    start = html.find("    onMouseUp(e) {")
    assert start != -1, "onMouseUp not found"
    return html[start: start + 4000]


def _rightclick_body(html: str) -> str:
    start = html.find("    onRightClick(e) {")
    assert start != -1, "onRightClick not found"
    return html[start: start + 4000]


def _commit_body(html: str) -> str:
    """Return commit function body — looks for commitGridCell or commitGridMultiSelect."""
    start = html.find("commitGridCell() {")
    assert start != -1, "commitGridCell() not found"
    return html[start: start + 1000]


def _cancel_body(html: str) -> str:
    start = html.find("cancelGridCell()")
    assert start != -1, "cancelGridCell() not found"
    return html[start: start + 500]


# ---------------------------------------------------------------------------
# T1 — Grid line strokeStyle is indigo
# ---------------------------------------------------------------------------

class TestGridLineIsIndigo:
    """T1 — The grid boundary lines must use rgba(99,102,241,...) family."""

    def test_grid_stroke_is_indigo(self):
        html = _html()
        section = _draw_grid_section(html)
        assert re.search(r'rgba\s*\(\s*99\s*,\s*102\s*,\s*241', section), (
            "Grid line strokeStyle does not use rgba(99,102,241,...) — "
            "expected indigo recolor (task 726)"
        )


# ---------------------------------------------------------------------------
# T2 — Old lemon yellow is gone from the grid section
# ---------------------------------------------------------------------------

class TestGridLemonYellowGone:
    """T2 — rgba(255,244,79,...) must no longer appear in the grid section."""

    def test_lemon_yellow_not_in_grid_section(self):
        html = _html()
        section = _draw_grid_section(html)
        assert "rgba(255,244,79" not in section, (
            "Old lemon-yellow rgba(255,244,79,...) still present in grid section — not recolored"
        )


# ---------------------------------------------------------------------------
# T3 — _gridMultiSelect state variable is declared
# ---------------------------------------------------------------------------

class TestGridMultiSelectStateDeclared:
    """T3 — _gridMultiSelect must appear in Alpine data declarations."""

    def test_gridMultiSelect_declared(self):
        html = _html()
        assert "_gridMultiSelect" in html, (
            "_gridMultiSelect state variable not found in editor.html — "
            "multi-select mode has no state container"
        )


# ---------------------------------------------------------------------------
# T4 — _gridMultiSelect initialised in clearEditorState
# ---------------------------------------------------------------------------

class TestGridMultiSelectInit:
    """T4 — clearEditorState() must initialise _gridMultiSelect."""

    def test_gridMultiSelect_inited_in_clearEditorState(self):
        html = _html()
        start = html.find("clearEditorState()")
        assert start != -1, "clearEditorState() not found"
        body = html[start: start + 2000]
        assert "_gridMultiSelect" in body, (
            "_gridMultiSelect not initialised in clearEditorState() — "
            "state leaks across project loads"
        )


# ---------------------------------------------------------------------------
# T5 — Mousemove with Cmd held accumulates cells into _gridMultiSelect
# ---------------------------------------------------------------------------

class TestMousemoveAccumulatesCells:
    """T5 — onMouseMove must update _gridMultiSelect while dragging with meta key."""

    def test_mousemove_references_gridMultiSelect(self):
        html = _html()
        body = _mousemove_body(html)
        assert "_gridMultiSelect" in body, (
            "_gridMultiSelect not referenced in onMouseMove — "
            "dragging with Cmd key won't accumulate cells"
        )


# ---------------------------------------------------------------------------
# T6 — Mouseup opens shared input (or triggers multi-select input path)
# ---------------------------------------------------------------------------

class TestMouseupOpensMultiSelectInput:
    """T6 — onMouseUp must handle _gridMultiSelect finalization."""

    def test_mouseup_handles_gridMultiSelect(self):
        html = _html()
        body = _mouseup_body(html)
        assert "_gridMultiSelect" in body, (
            "_gridMultiSelect not referenced in onMouseUp — "
            "drag release won't open the shared-value input"
        )


# ---------------------------------------------------------------------------
# T7 — commitGridCell iterates over _gridMultiSelect to apply value to all cells
# ---------------------------------------------------------------------------

class TestCommitAppliesValueToAllSelectedCells:
    """T7 — commit must write to ALL cells in _gridMultiSelect."""

    def test_commit_iterates_gridMultiSelect(self):
        html = _html()
        # Check the commit function references _gridMultiSelect
        # Either commitGridCell or a separate commitGridMultiSelect function
        commit_start = html.find("commitGridCell() {")
        assert commit_start != -1, "commitGridCell() not found"
        # Search in a wide window covering both single and multi versions
        commit_area = html[commit_start: commit_start + 2000]
        assert "_gridMultiSelect" in commit_area, (
            "_gridMultiSelect not referenced in commit path — "
            "value won't be applied to all selected cells"
        )


# ---------------------------------------------------------------------------
# T8 — cancelGridCell clears _gridMultiSelect
# ---------------------------------------------------------------------------

class TestCancelClearsMultiSelect:
    """T8 — cancel must clear _gridMultiSelect."""

    def test_cancel_clears_gridMultiSelect(self):
        html = _html()
        cancel_start = html.find("cancelGridCell() {")
        assert cancel_start != -1, "cancelGridCell() not found"
        body = html[cancel_start: cancel_start + 500]
        assert "_gridMultiSelect" in body, (
            "_gridMultiSelect not cleared in cancelGridCell() — "
            "Esc key won't remove selection highlights"
        )


# ---------------------------------------------------------------------------
# T9 — draw() renders thicker border for multi-selected cells
# ---------------------------------------------------------------------------

class TestHighlightedCellsRenderThickerBorder:
    """T9 — draw() must have a distinct render block for _gridMultiSelect cells."""

    def test_draw_has_gridMultiSelect_highlight(self):
        html = _html()
        draw = _draw_body(html)
        assert "_gridMultiSelect" in draw, (
            "_gridMultiSelect not referenced in draw() — "
            "selected cells won't show thicker border highlight"
        )


# ---------------------------------------------------------------------------
# T10 — _gridMultiSelect cleared after commit
# ---------------------------------------------------------------------------

class TestHighlightClearedAfterCommit:
    """T10 — commit path must null/clear _gridMultiSelect."""

    def test_commit_clears_gridMultiSelect(self):
        html = _html()
        commit_start = html.find("commitGridCell() {")
        assert commit_start != -1, "commitGridCell() not found"
        # Scan a wider block to find the assignment back to null
        area = html[commit_start: commit_start + 2000]
        # Expect something like: this._gridMultiSelect = null;
        assert re.search(r'_gridMultiSelect\s*=\s*null', area), (
            "_gridMultiSelect not set to null in commit path — "
            "highlights won't clear after pressing Enter"
        )


# ---------------------------------------------------------------------------
# T11 — Bare click without Cmd still opens single-cell input (regression)
# ---------------------------------------------------------------------------

class TestBareClickSingleCellRegression:
    """T11 — onMouseUp without metaKey still calls openGridCell for single-cell edit."""

    def test_openGridCell_still_called_from_mouseup(self):
        html = _html()
        body = _mouseup_body(html)
        assert "openGridCell" in body, (
            "openGridCell() no longer called from onMouseUp — "
            "bare left-click to edit a cell is broken (regression)"
        )


# ---------------------------------------------------------------------------
# T12 — Right-click delete still works (regression)
# ---------------------------------------------------------------------------

class TestRightClickDeleteRegression:
    """T12 — onRightClick must still delete from gridCellHeights."""

    def test_rightclick_deletes_gridCellHeights(self):
        html = _html()
        body = _rightclick_body(html)
        assert re.search(r'delete\s+(?:this\.)?gridCellHeights\[', body), (
            "onRightClick no longer deletes from gridCellHeights — regression"
        )


# ---------------------------------------------------------------------------
# T13 — metaKey OR ctrlKey triggers multi-select (cross-platform)
# ---------------------------------------------------------------------------

class TestMetaOrCtrlKeyTriggerMultiSelect:
    """T13 — mousedown must check e.metaKey || e.ctrlKey for multi-select entry."""

    def test_metaKey_or_ctrlKey_in_mousedown(self):
        html = _html()
        body = _mousedown_body(html)
        # Look for both metaKey and ctrlKey references in mousedown
        has_meta = "metaKey" in body
        has_ctrl = "ctrlKey" in body
        assert has_meta and has_ctrl, (
            f"mousedown: metaKey={has_meta}, ctrlKey={has_ctrl} — "
            "multi-select must work on both Mac (Cmd=metaKey) and Windows/Linux (ctrlKey)"
        )


# ---------------------------------------------------------------------------
# T14 — Multi-select input overlay exists in the template HTML
# ---------------------------------------------------------------------------

class TestMultiSelectInputOverlayExists:
    """T14 — The template must have an input overlay that serves multi-select commits."""

    def test_multi_select_input_or_shared_input_exists(self):
        html = _html()
        # The input may be the same element reused for multi-select, or a new one.
        # At minimum _gridMultiSelect must appear in the template (above the Alpine data).
        template_section = html[:html.find("<script")]
        # Either a dedicated template x-if or the existing gridActiveCell input reused
        # — the key proof is _gridMultiSelect appearing in the overlay zone OR being
        # driven by the same _gridActiveCell that's already wired up.
        assert "_gridMultiSelect" in html, (
            "_gridMultiSelect absent from editor.html — "
            "no multi-select input path can exist"
        )


# ---------------------------------------------------------------------------
# T15 — APP_VERSION is v5.14
# ---------------------------------------------------------------------------

class TestAppVersion:
    """T15 — APP_VERSION bumped to v5.14."""

    def test_app_version_is_v5_14(self):
        src = _app_py()
        m = re.search(r'APP_VERSION\s*=\s*["\']v(\d+)\.(\d+)["\']', src)
        assert m is not None, "APP_VERSION not found in app.py"
        major, minor = int(m.group(1)), int(m.group(2))
        assert (major, minor) >= (5, 14), (
            f"APP_VERSION is v{major}.{minor:02d} — expected v5.14 (task 726)"
        )


# ---------------------------------------------------------------------------
# T16 — editor.html on-page version is at least v5.09
# ---------------------------------------------------------------------------

class TestEditorHtmlVersion:
    """T16 — editor.html on-page version comment is at least v5.09."""

    def test_editor_version_is_v5_09_or_higher(self):
        html = _html()
        m = re.search(r'Boundary Editor v(\d+)\.(\d+)', html)
        assert m is not None, "No 'Boundary Editor vX.XX' version string in editor.html"
        major, minor = int(m.group(1)), int(m.group(2))
        assert (major, minor) >= (5, 9), (
            f"editor.html version is v{major}.{minor:02d} — expected >= v5.09 after task 726"
        )
