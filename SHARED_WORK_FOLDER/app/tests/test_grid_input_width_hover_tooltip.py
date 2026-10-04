"""
test_grid_input_width_hover_tooltip.py — Bug→TDD for:
  (a) wider grid cell input at edit time
  (b) hover tooltip on set-cell markers (canvas dots)

Task 710.  RED written first, implementation follows.

Test inventory
==============

T1  Input wider: max-width or explicit width on grid input > 60px (old cap was 60px)
T2  Input container wider: the wrapper div also grows to fit the wider input
T3  Tooltip state: _gridHoveredCell declared in Alpine state (null initial)
T4  Tooltip render: a tooltip div is present in HTML, bound to _gridHoveredCell
T5  Tooltip shows mm value: the tooltip display expression references gridCellHeights
      (so it shows the actual mm value, not a placeholder)
T6  Tooltip hidden while editing: tooltip not shown when _gridActiveCell is active
T7  Tooltip format: the mm value is shown with " mm" suffix (e.g. "12.5 mm")
T8  Unset cells no tooltip: tooltip is conditional on the cell being in gridCellHeights
T9  Mouse move wiring: onMouseMove sets _gridHoveredCell when over a set cell
T10 Regression — grid still 20×20 (GRID_COLS/GRID_ROWS = 20 constants present)
T11 Regression — commitGridCell / cancelGridCell / deleteGridCell still present
T12 Regression — gridCellHeights still in autoSave and loadProject
T13 APP_VERSION bumped beyond v5.03 (Topo already set v5.03; we go to v5.04)
T14 editor.html on-page version bumped beyond v5.02

Run:
    cd /Volumes/GIT/CLAUDE/SHARED_WORK_FOLDER
    python -m pytest app/tests/test_grid_input_width_hover_tooltip.py -v
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


# ---------------------------------------------------------------------------
# T1 — Input max-width > 60px (was max-width:60px before this task)
# ---------------------------------------------------------------------------

class TestInputWider:
    """T1 — The grid cell input is wider than the old 60-px cap."""

    def test_input_max_width_removed_or_wider(self):
        html = _html()
        # Find the grid input element
        inp_start = html.find('x-ref="gridCellInput"')
        assert inp_start != -1, "gridCellInput ref not found"
        inp_block = html[inp_start: inp_start + 900]  # 900 chars — wide enough for all attrs
        # Old cap was max-width:60px — it should be gone or replaced by something wider
        old_cap = re.search(r'max-width\s*:\s*60px', inp_block)
        assert not old_cap, (
            "max-width:60px still present on gridCellInput — input not widened"
        )

    def test_input_min_width_at_least_80px(self):
        html = _html()
        inp_start = html.find('x-ref="gridCellInput"')
        assert inp_start != -1, "gridCellInput ref not found"
        inp_block = html[inp_start: inp_start + 600]
        # min-width must be at least 80px
        m = re.search(r'min-width\s*:\s*(\d+)px', inp_block)
        assert m is not None, "No min-width found on gridCellInput"
        assert int(m.group(1)) >= 80, (
            f"min-width {m.group(1)}px is still too narrow; expected >= 80px"
        )


# ---------------------------------------------------------------------------
# T2 — Container wrapper width also raised to match wider input
# ---------------------------------------------------------------------------

class TestContainerWider:
    """T2 — The absolute wrapper div hosting the input uses a wider min."""

    def test_container_min_width_at_least_80(self):
        html = _html()
        # The wrapper div has :style with Math.max(<N>, ...) for width
        # Old value was Math.max(36, ...) — should now be Math.max(80, ...) or higher
        m = re.search(r'Math\.max\((\d+),\s*_gridActiveCell\.canvasPx\.w\)', html)
        assert m is not None, "Math.max(..., _gridActiveCell.canvasPx.w) not found"
        assert int(m.group(1)) >= 80, (
            f"Math.max floor is {m.group(1)} — should be at least 80 to match wider input"
        )


# ---------------------------------------------------------------------------
# T3 — _gridHoveredCell state variable declared
# ---------------------------------------------------------------------------

class TestHoveredCellState:
    """T3 — _gridHoveredCell is in the Alpine data block, initialised to null."""

    def test_hovered_cell_declared(self):
        html = _html()
        assert "_gridHoveredCell" in html, (
            "_gridHoveredCell not found in editor.html — tooltip state missing"
        )

    def test_hovered_cell_null_initial(self):
        html = _html()
        assert re.search(r'_gridHoveredCell\s*:\s*null', html), (
            "_gridHoveredCell not initialised to null"
        )


# ---------------------------------------------------------------------------
# T4 — Tooltip render div present in HTML
# ---------------------------------------------------------------------------

class TestTooltipRender:
    """T4 — A tooltip element is conditionally shown via _gridHoveredCell."""

    def test_tooltip_div_present(self):
        html = _html()
        # Must have some element whose visibility is keyed off _gridHoveredCell
        assert re.search(
            r'x-show.*_gridHoveredCell|x-if.*_gridHoveredCell|'
            r'_gridHoveredCell.*x-show|_gridHoveredCell.*x-if',
            html, re.DOTALL
        ), "No tooltip element bound to _gridHoveredCell found in editor.html"

    def test_tooltip_positioned_absolutely(self):
        html = _html()
        # Find the tooltip div region — x-show with _gridHoveredCell + absolute position
        m = re.search(r'x-show[^>]*_gridHoveredCell.*?</div>', html, re.DOTALL)
        if m is None:
            # Might be x-if pattern
            m = re.search(r'_gridHoveredCell[^"\']*".*?absolute', html, re.DOTALL)
        assert m is not None or re.search(
            r'_gridHoveredCell.*absolute|absolute.*_gridHoveredCell', html, re.DOTALL
        ), "Tooltip div does not appear to be absolutely positioned"


# ---------------------------------------------------------------------------
# T5 — Tooltip shows mm value from gridCellHeights
# ---------------------------------------------------------------------------

class TestTooltipValue:
    """T5 — The tooltip expression reads from gridCellHeights to display the mm value."""

    def test_tooltip_reads_gridCellHeights(self):
        html = _html()
        # The tooltip text expression must reference gridCellHeights
        # (it uses the hovered cell's idx to look up the mm value)
        assert re.search(
            r'gridCellHeights\[.*_gridHoveredCell|_gridHoveredCell.*gridCellHeights',
            html, re.DOTALL
        ), "Tooltip text does not reference gridCellHeights — value won't display"


# ---------------------------------------------------------------------------
# T6 — Tooltip hidden while input is open (_gridActiveCell is set)
# ---------------------------------------------------------------------------

class TestTooltipHiddenWhileEditing:
    """T6 — Tooltip is suppressed when a cell input is currently open."""

    def test_tooltip_suppressed_during_edit(self):
        html = _html()
        # The x-show expression should guard against _gridActiveCell being set
        assert re.search(
            r'_gridHoveredCell[^>]*&&[^>]*!_gridActiveCell|'
            r'!_gridActiveCell[^>]*&&[^>]*_gridHoveredCell|'
            r'_gridHoveredCell.*_gridActiveCell.*===.*null|'
            r'_gridActiveCell.*===.*null.*_gridHoveredCell',
            html, re.DOTALL
        ), (
            "Tooltip does not suppress itself when _gridActiveCell is active — "
            "tooltip will overlap the input"
        )


# ---------------------------------------------------------------------------
# T7 — Tooltip value displayed with " mm" suffix
# ---------------------------------------------------------------------------

class TestTooltipFormat:
    """T7 — The tooltip shows the value in the form 'X.X mm'."""

    def test_tooltip_mm_suffix(self):
        html = _html()
        # Somewhere near the tooltip, " mm" literal must appear in the expression
        assert re.search(
            r"['\"] mm['\"].*_gridHoveredCell|_gridHoveredCell.*['\"] mm['\"]|"
            r"mm.*gridCellHeights.*Hovered|Hovered.*gridCellHeights.*mm",
            html, re.DOTALL | re.IGNORECASE
        ), "Tooltip does not append ' mm' suffix to the displayed value"


# ---------------------------------------------------------------------------
# T8 — Tooltip only shown for set cells (not unset ones)
# ---------------------------------------------------------------------------

class TestUnsetCellsNoTooltip:
    """T8 — Cells not in gridCellHeights produce no tooltip."""

    def test_hovered_cell_set_only_when_cell_in_gridCellHeights(self):
        html = _html()
        # The onMouseMove / hit detection must only set _gridHoveredCell
        # when the hovered cell index is present in gridCellHeights.
        # Look for patterns: iterates Object.keys(gridCellHeights) (so only set cells
        # are iterated), or explicit !== undefined check, or hasOwnProperty guard.
        assert re.search(
            r'Object\.keys\((?:this\.)?gridCellHeights\)|'
            r'gridCellHeights\[.*\]\s*!==\s*undefined|'
            r'idx\s*in\s*(?:this\.)?gridCellHeights|'
            r'(?:this\.)?gridCellHeights\.hasOwnProperty',
            html, re.DOTALL
        ), (
            "No guard found: _gridHoveredCell may be set for unset cells too — "
            "unset cells would show a tooltip"
        )


# ---------------------------------------------------------------------------
# T9 — onMouseMove wires _gridHoveredCell updates
# ---------------------------------------------------------------------------

class TestMouseMoveWiring:
    """T9 — onMouseMove updates _gridHoveredCell based on dot proximity."""

    def test_onMouseMove_references_gridHoveredCell(self):
        html = _html()
        move_start = html.find("    onMouseMove(e) {")
        assert move_start != -1, "onMouseMove not found"
        move_body = html[move_start: move_start + 5000]  # scan enough to cover the added block
        assert "_gridHoveredCell" in move_body, (
            "onMouseMove does not update _gridHoveredCell — tooltip won't respond to mouse"
        )


# ---------------------------------------------------------------------------
# T10 — Regression: 20×20 grid constants still present
# ---------------------------------------------------------------------------

class TestGridGeometryRegression:
    """T10 — Grid is still 20×20."""

    def test_grid_cols_20_present(self):
        html = _html()
        assert re.search(r'GRID_COLS\s*=\s*20', html), (
            "GRID_COLS = 20 constant missing — grid geometry regression"
        )

    def test_grid_rows_20_present(self):
        html = _html()
        assert re.search(r'GRID_ROWS\s*=\s*20', html), (
            "GRID_ROWS = 20 constant missing — grid geometry regression"
        )


# ---------------------------------------------------------------------------
# T11 — Regression: commit / cancel / delete still present
# ---------------------------------------------------------------------------

class TestGridEditRegression:
    """T11 — Core grid editing functions unchanged."""

    def test_commitGridCell_present(self):
        html = _html()
        assert "commitGridCell()" in html, "commitGridCell() missing"

    def test_cancelGridCell_present(self):
        html = _html()
        assert "cancelGridCell()" in html, "cancelGridCell() missing"

    def test_deleteGridCell_present(self):
        html = _html()
        assert "deleteGridCell(" in html, "deleteGridCell() missing"


# ---------------------------------------------------------------------------
# T12 — Regression: gridCellHeights still in autoSave and loadProject
# ---------------------------------------------------------------------------

class TestGridPersistenceRegression:
    """T12 — gridCellHeights persisted and loaded correctly."""

    def test_gridCellHeights_in_autoSave(self):
        html = _html()
        save_start = html.find("    async autoSave()")
        assert save_start != -1, "autoSave() not found"
        assert "gridCellHeights" in html[save_start: save_start + 5000]

    def test_gridCellHeights_in_loadProject(self):
        html = _html()
        load_start = html.find("    async loadProject(")
        assert load_start != -1, "loadProject() not found"
        assert "gridCellHeights" in html[load_start: load_start + 8000]


# ---------------------------------------------------------------------------
# T13 — APP_VERSION bumped beyond v5.03
# ---------------------------------------------------------------------------

class TestAppVersionBump:
    """T13 — APP_VERSION is v5.04 (Topo set v5.03; this task goes to v5.04)."""

    def test_app_version_is_v5_04(self):
        src = _app_py()
        m = re.search(r'APP_VERSION\s*=\s*["\']v(\d+)\.(\d+)["\']', src)
        assert m is not None, "APP_VERSION not found in app.py"
        major, minor = int(m.group(1)), int(m.group(2))
        assert (major, minor) == (5, 4), (
            f"APP_VERSION is v{major}.{minor} — expected v5.04 after this task's bump"
        )


# ---------------------------------------------------------------------------
# T14 — editor.html on-page version bumped
# ---------------------------------------------------------------------------

class TestEditorHtmlVersionBump:
    """T14 — editor.html on-page version comment is v5.04."""

    def test_editor_version_is_v5_04(self):
        html = _html()
        m = re.search(r'Boundary Editor v(\d+)\.(\d+)', html)
        assert m is not None, "No 'Boundary Editor vX.XX' version string in editor.html"
        major, minor = int(m.group(1)), int(m.group(2))
        assert (major, minor) == (5, 4), (
            f"editor.html version is v{major}.{minor} — expected v5.04"
        )
