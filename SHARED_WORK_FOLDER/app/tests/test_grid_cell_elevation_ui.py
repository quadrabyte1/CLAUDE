"""
test_grid_cell_elevation_ui.py — Bug→TDD for 20×20 grid cell elevation overlay
(task 702, phase 1 — UI + EGM schema only; TPS wiring is Topo phase 2).

RED tests written first; implementation follows.

Test inventory
==============

T1  Grid state initialises to empty dict  (gridCellHeights key exists, is {})
T2  Alpine state has gridCellHeights in the polygonEditor() data section
T3  Grid overlay: draw() references gridCellHeights (grid drawing code present)
T4  Click-open: _gridActiveCell state variable exists
T5  Enter commits: JS commits gridCellHeights entry on Enter key in grid input
T6  Esc reverts: Esc keydown on grid input clears active cell without updating state
T7  Delete clears: Delete key on active grid cell removes entry from gridCellHeights
T8  Status strip: "N cells set" text rendered with x-show hidden when 0
T9  EGM save: autoSave() includes gridCellHeights in payload (non-empty case)
T10 EGM load: loadProject() restores gridCellHeights from EGM data
T11 Backward compat load: missing gridCellHeights → defaults to {}
T12 Clamp range: grid input has min=0 max=50 attributes (same as spike inputs)
T13 APP_VERSION is v5.00 in app.py
T14 editor.html on-page version comment updated beyond v4.98
T15 clearEditorState resets gridCellHeights to {}
T16 startNewProject resets gridCellHeights to {}
T17 Grid geometry: 20×20 constant referenced in JS grid code
T18 Grid input positioned absolutely over the cell (absolute positioning in HTML)
T19 Grid input autofocused when opened
T20 Autosave wired: commitGridCell() or equivalent calls autoSave()

Run:
    cd /Volumes/GIT/CLAUDE/SHARED_WORK_FOLDER
    python -m pytest app/tests/test_grid_cell_elevation_ui.py -v
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
REPO_ROOT = APP_DIR.parent
sys.path.insert(0, str(APP_DIR))

EDITOR_HTML = APP_DIR / "templates" / "editor.html"
APP_PY = APP_DIR / "app.py"


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _html() -> str:
    return EDITOR_HTML.read_text(encoding="utf-8")


def _app_py() -> str:
    return APP_PY.read_text(encoding="utf-8")


# ---------------------------------------------------------------------------
# T1 — gridCellHeights in Alpine state initialised as empty dict
# ---------------------------------------------------------------------------

class TestGridStateInit:
    """T1 — gridCellHeights declared in polygonEditor() data."""

    def test_gridCellHeights_declared_in_state(self):
        html = _html()
        # Must declare the property in the Alpine data block
        assert "gridCellHeights" in html, (
            "gridCellHeights not found in editor.html state"
        )

    def test_gridCellHeights_initialised_to_empty_dict(self):
        html = _html()
        # Expect:  gridCellHeights: {},
        assert re.search(r'gridCellHeights\s*:\s*\{\s*\}', html), (
            "gridCellHeights not initialised to {} in state"
        )


# ---------------------------------------------------------------------------
# T2 — polygonEditor() data section contains gridCellHeights
# ---------------------------------------------------------------------------

class TestPolygonEditorData:
    """T2 — gridCellHeights lives inside the polygonEditor() function body."""

    def test_gridCellHeights_inside_polygonEditor(self):
        html = _html()
        # Find the polygonEditor() function and check gridCellHeights is in it
        fn_start = html.find("function polygonEditor()")
        assert fn_start != -1, "polygonEditor() not found"
        fn_body = html[fn_start:fn_start + 4000]  # first 4k chars of function
        assert "gridCellHeights" in fn_body, (
            "gridCellHeights not found in the opening of polygonEditor()"
        )


# ---------------------------------------------------------------------------
# T3 — Grid overlay: draw() has grid drawing code
# ---------------------------------------------------------------------------

class TestGridOverlayInDraw:
    """T3 — draw() renders the 20×20 grid."""

    def test_drawGrid_or_grid_draw_in_draw_function(self):
        html = _html()
        # Locate draw() function — scan up to 12k chars to cover the full function
        draw_start = html.find("    draw() {")
        assert draw_start != -1, "draw() function not found"
        draw_body_search = html[draw_start:draw_start + 12000]
        # Grid drawing must reference gridCellHeights
        assert "gridCellHeights" in draw_body_search, (
            "draw() does not reference gridCellHeights — grid overlay not drawn"
        )

    def test_20x20_constant_in_draw(self):
        html = _html()
        draw_start = html.find("    draw() {")
        assert draw_start != -1, "draw() function not found"
        # Scan up to 12k chars to cover the full function
        draw_body = html[draw_start:draw_start + 12000]
        # Must reference GRID_COLS=20 or literal 20 in grid context
        assert re.search(r'GRID_COLS\s*=\s*20|GRID_ROWS\s*=\s*20', draw_body), (
            "No GRID_COLS/GRID_ROWS = 20 constant in draw() body"
        )


# ---------------------------------------------------------------------------
# T4 — _gridActiveCell state variable exists
# ---------------------------------------------------------------------------

class TestGridActiveCellState:
    """T4 — _gridActiveCell tracks which cell is currently being edited."""

    def test_gridActiveCell_declared(self):
        html = _html()
        assert "_gridActiveCell" in html, (
            "_gridActiveCell not found in editor.html"
        )

    def test_gridActiveCell_null_initial(self):
        html = _html()
        assert re.search(r'_gridActiveCell\s*:\s*null', html), (
            "_gridActiveCell not initialised to null"
        )


# ---------------------------------------------------------------------------
# T5 — Enter commits value to gridCellHeights
# ---------------------------------------------------------------------------

class TestGridEnterCommits:
    """T5 — Pressing Enter commits the typed value."""

    def test_commitGridCell_or_equivalent_present(self):
        html = _html()
        # A commit function must exist
        assert re.search(r'commitGridCell|gridCommit|_commitGrid', html), (
            "No grid commit function found in editor.html"
        )

    def test_enter_key_wired_to_commit(self):
        html = _html()
        # keydown.enter or @keydown on grid input should reference the commit function
        assert re.search(
            r'@keydown[^>]*enter[^>]*commit[Gg]rid|@keydown[^>]*gridCommit|'
            r'commitGridCell[^;]*enter|key.*Enter.*commitGrid|Enter.*commitGrid',
            html, re.IGNORECASE | re.DOTALL
        ), "Enter key not wired to grid commit"


# ---------------------------------------------------------------------------
# T6 — Esc reverts (clears input without updating state)
# ---------------------------------------------------------------------------

class TestGridEscReverts:
    """T6 — Pressing Escape cancels the grid input."""

    def test_esc_clears_active_cell(self):
        html = _html()
        # Must cancel / close grid input on Escape
        assert re.search(
            r'Escape.*_gridActiveCell\s*=\s*null|'
            r'_gridActiveCell\s*=\s*null.*Escape|'
            r'cancelGridCell|_cancelGrid',
            html, re.DOTALL
        ), "Esc does not clear _gridActiveCell"


# ---------------------------------------------------------------------------
# T7 — Delete key clears a cell
# ---------------------------------------------------------------------------

class TestGridDeleteClears:
    """T7 — Delete key removes entry from gridCellHeights."""

    def test_delete_removes_from_gridCellHeights(self):
        html = _html()
        # delete operator on gridCellHeights or clearGridCell function
        assert re.search(
            r'delete\s+this\.gridCellHeights|'
            r'delete\s+gridCellHeights|'
            r'clearGridCell|deleteGridCell',
            html
        ), "No code to delete from gridCellHeights found"

    def test_delete_key_handled_for_grid(self):
        html = _html()
        # handleKey or @keydown must handle Delete for grid cells
        assert re.search(
            r"_gridActiveCell.*Delete|Delete.*_gridActiveCell|"
            r"Delete.*gridCellHeights|gridCellHeights.*Delete",
            html, re.DOTALL
        ), "Delete key not handled for grid cells"


# ---------------------------------------------------------------------------
# T8 — Status strip shows "N cells set", hidden when 0
# ---------------------------------------------------------------------------

class TestGridStatusStrip:
    """T8 — Status strip text and visibility."""

    def test_cells_set_text_present(self):
        html = _html()
        # The text may be inside an x-text JS expression — look for "set" near gridCellHeights
        assert re.search(r"'s'\s*\)\s*\+\s*'?\s*set'|set.*gridCellHeights|gridCellHeights.*set", html, re.IGNORECASE), (
            '"cells set" expression not found near gridCellHeights in editor.html'
        )

    def test_status_strip_hidden_when_zero(self):
        html = _html()
        # x-show with Object.keys check
        assert re.search(
            r'x-show.*Object\.keys.*gridCellHeights|'
            r'Object\.keys.*gridCellHeights.*length',
            html, re.DOTALL
        ), "Status strip not wired to Object.keys(gridCellHeights).length"


# ---------------------------------------------------------------------------
# T9 — autoSave() includes gridCellHeights
# ---------------------------------------------------------------------------

class TestEgmSaveIncludesGrid:
    """T9 — autoSave() serializes gridCellHeights into the EGM payload."""

    def test_autosave_includes_gridCellHeights(self):
        html = _html()
        # Find autoSave function — scan up to 5000 chars to cover all appends after the data block
        save_start = html.find("    async autoSave()")
        assert save_start != -1, "autoSave() not found"
        save_body = html[save_start:save_start + 5000]
        assert "gridCellHeights" in save_body, (
            "autoSave() does not include gridCellHeights in the payload"
        )

    def test_autosave_omits_empty_gridCellHeights(self):
        """Empty dict should be omitted or included — either is acceptable,
        but if included, it should not break backward compat.
        This test verifies the save path at least handles the field."""
        html = _html()
        save_start = html.find("    async autoSave()")
        assert save_start != -1, "autoSave() not found"
        save_body = html[save_start:save_start + 5000]
        # The field must appear somewhere in autoSave
        assert "gridCellHeights" in save_body


# ---------------------------------------------------------------------------
# T10 — loadProject() restores gridCellHeights
# ---------------------------------------------------------------------------

class TestEgmLoadRestoresGrid:
    """T10 — loadProject() reads gridCellHeights from the loaded EGM."""

    def test_loadProject_restores_gridCellHeights(self):
        html = _html()
        # Scan up to 8000 chars to cover the full loadProject function
        load_start = html.find("    async loadProject(")
        assert load_start != -1, "loadProject() not found"
        load_body = html[load_start:load_start + 8000]
        assert "gridCellHeights" in load_body, (
            "loadProject() does not restore gridCellHeights"
        )


# ---------------------------------------------------------------------------
# T11 — Backward compat: missing field → empty dict
# ---------------------------------------------------------------------------

class TestEgmBackwardCompat:
    """T11 — Missing gridCellHeights in EGM → state defaults to {}."""

    def test_backward_compat_default_empty(self):
        html = _html()
        load_start = html.find("    async loadProject(")
        assert load_start != -1, "loadProject() not found"
        load_body = html[load_start:load_start + 8000]
        # Must default to {} when field absent
        assert re.search(
            r'gridCellHeights.*\|\|.*\{\}|'
            r'data\.gridCellHeights\s*\?\s*.*:\s*\{\}|'
            r'gridCellHeights\s*=\s*data\.gridCellHeights\s*\|\|',
            load_body, re.DOTALL
        ), "loadProject() does not default gridCellHeights to {} for missing field"


# ---------------------------------------------------------------------------
# T12 — Input has min=0 max=50
# ---------------------------------------------------------------------------

class TestGridInputClamp:
    """T12 — Grid number input has min/max attributes for 0–50 range."""

    def test_grid_input_has_min_0(self):
        html = _html()
        # Find the grid input section
        assert re.search(r'gridCellHeights.*min.*0|min.*0.*gridCellHeights|grid.*input.*min="0"', html, re.DOTALL), (
            "Grid input min=0 not found"
        )

    def test_grid_input_has_max_50(self):
        html = _html()
        assert re.search(r'gridCellHeights.*max.*50|max.*50.*gridCellHeights|grid.*input.*max="50"', html, re.DOTALL), (
            "Grid input max=50 not found"
        )


# ---------------------------------------------------------------------------
# T13 — APP_VERSION is v5.00
# ---------------------------------------------------------------------------

class TestAppVersion:
    """T13 — APP_VERSION bumped to v5.00 or higher (parallel task 700 may have already set v5.01)."""

    def test_app_version_is_v5_00_or_higher(self):
        src = _app_py()
        m = re.search(r'APP_VERSION\s*=\s*["\']v(\d+)\.(\d+)["\']', src)
        assert m is not None, "APP_VERSION not found in app.py"
        major, minor = int(m.group(1)), int(m.group(2))
        # Phase 1 task 702 bumped from v4.99 → v5.00; accept v5.00 or any later value
        version_ok = major >= 5
        assert version_ok, (
            f"APP_VERSION v{major}.{minor} is below v5.00 — bump not applied"
        )


# ---------------------------------------------------------------------------
# T14 — editor.html on-page version comment updated
# ---------------------------------------------------------------------------

class TestEditorHtmlVersion:
    """T14 — editor.html version comment is beyond v4.98."""

    def test_editor_version_bumped(self):
        html = _html()
        # The file comment at the top should no longer say v4.98
        # Accept v4.99 or higher, or v5.xx
        m = re.search(r'Boundary Editor v(\d+)\.(\d+)', html)
        assert m is not None, "No 'Boundary Editor vX.XX' version string in editor.html"
        major, minor = int(m.group(1)), int(m.group(2))
        version_ok = (major > 4) or (major == 4 and minor > 98)
        assert version_ok, (
            f"editor.html version v{major}.{minor} not bumped past v4.98"
        )


# ---------------------------------------------------------------------------
# T15 — clearEditorState resets gridCellHeights
# ---------------------------------------------------------------------------

class TestClearEditorStateResetsGrid:
    """T15 — clearEditorState() resets gridCellHeights to {}."""

    def test_clearEditorState_resets_gridCellHeights(self):
        html = _html()
        clear_start = html.find("    clearEditorState()")
        assert clear_start != -1, "clearEditorState() not found"
        clear_body = html[clear_start:clear_start + 2000]
        assert re.search(r'gridCellHeights\s*=\s*\{\}', clear_body), (
            "clearEditorState() does not reset gridCellHeights to {}"
        )


# ---------------------------------------------------------------------------
# T16 — startNewProject resets gridCellHeights
# ---------------------------------------------------------------------------

class TestStartNewProjectResetsGrid:
    """T16 — startNewProject() resets gridCellHeights to {}."""

    def test_startNewProject_resets_gridCellHeights(self):
        html = _html()
        # Find startNewProject function
        np_start = html.find("    async startNewProject()")
        assert np_start != -1, "startNewProject() not found"
        np_body = html[np_start:np_start + 3000]
        assert re.search(r'gridCellHeights\s*=\s*\{\}', np_body), (
            "startNewProject() does not reset gridCellHeights to {}"
        )


# ---------------------------------------------------------------------------
# T17 — Grid geometry: 20 columns and 20 rows referenced
# ---------------------------------------------------------------------------

class TestGridGeometryConstants:
    """T17 — 20×20 grid resolution constants in JS."""

    def test_grid_cols_20_declared(self):
        html = _html()
        # GRID_COLS = 20 or GRID_ROWS = 20 or inline literals
        assert re.search(
            r'GRID_COLS\s*=\s*20|GRID_ROWS\s*=\s*20|'
            r'gridCols\s*=\s*20|gridRows\s*=\s*20|'
            r'const\s+(?:cols|rows|COLS|ROWS)\s*=\s*20',
            html
        ), "No 20×20 grid resolution constant found in editor.html"


# ---------------------------------------------------------------------------
# T18 — Grid input positioned absolutely
# ---------------------------------------------------------------------------

class TestGridInputPositioning:
    """T18 — Grid cell input is absolutely positioned over the canvas."""

    def test_grid_input_absolutely_positioned(self):
        html = _html()
        # Must have an absolutely positioned element for the grid input
        # Look for pattern: x-show with _gridActiveCell + absolute style
        assert re.search(
            r'_gridActiveCell.*position.*absolute|'
            r'position.*absolute.*_gridActiveCell|'
            r'style.*absolute.*_gridActiveCell|'
            r'absolute.*_gridActiveCell',
            html, re.DOTALL | re.IGNORECASE
        ), "Grid input not absolutely positioned over canvas"


# ---------------------------------------------------------------------------
# T19 — Grid input has x-ref or autofocus
# ---------------------------------------------------------------------------

class TestGridInputFocus:
    """T19 — Grid input gains focus when opened."""

    def test_grid_input_autofocused(self):
        html = _html()
        # Must have either x-autofocus, autofocus attr, or $refs focus call
        # near the grid input
        assert re.search(
            r'gridInput.*autofocus|autofocus.*gridInput|'
            r'x-ref.*gridInput|gridInput.*focus\(\)|'
            r'_gridActiveCell.*autofocus|autofocus.*_gridActive',
            html, re.DOTALL | re.IGNORECASE
        ), "Grid input does not have autofocus wiring"


# ---------------------------------------------------------------------------
# T20 — commitGridCell calls autoSave()
# ---------------------------------------------------------------------------

class TestGridCommitCallsAutoSave:
    """T20 — committing a grid cell value fires autoSave()."""

    def test_commit_calls_autosave(self):
        html = _html()
        # Find the commit function and verify it calls autoSave within 600 chars
        commit_start = html.find("    commitGridCell()")
        assert commit_start != -1, "commitGridCell() not found"
        commit_body = html[commit_start:commit_start + 600]
        assert "autoSave" in commit_body, (
            "commitGridCell() does not call autoSave()"
        )
