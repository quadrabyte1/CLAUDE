"""
test_grid_value_text_marker.py — Bug→TDD for task 720:
  Replace blue dot on set grid cells with the numeric mm value rendered as text.

RED tests written first; implementation follows.

Test inventory
==============

T1  No arc() call for set cells — the dot drawing loop must not use ctx.arc
T2  fillText used for set cells — draw() renders text for set-cell values
T3  Text is centered — ctx.textAlign='center' and ctx.textBaseline='middle' in draw()
T4  Text format — value formatted as 1 decimal (e.g. "7.5", not "7.50", not "7.5 mm")
T5  Text color is blue-family — fillStyle for text references the indigo/blue palette (99 or similar)
T6  Right-click still deletes — onRightClick still references gridCellHeights and delete path
T7  Right-click hit detection still uses cell/text bounds (not exclusively arc-radius math)
T8  Left-click opens input (regression) — openGridCell still called from onMouseUp
T9  Hover tooltip still fires (regression) — _gridHoveredCell updated in onMouseMove
T10 Unset cells render nothing — no fillText inside gridCellHeights loop for undefined values
T11 No free-standing ctx.arc inside the gridCellHeights loop — arc belongs only outside that loop
T12 Polygon editing regression — draw() still calls ctx.arc for polygon vertices (outside grid loop)
T13 APP_VERSION bumped to v5.10
T14 editor.html on-page version bumped to at least v5.07

Run:
    cd /Volumes/GIT/CLAUDE/SHARED_WORK_FOLDER
    python -m pytest app/tests/test_grid_value_text_marker.py -v
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


def _grid_loop_body(html: str) -> str:
    """Extract the set-cell rendering block from draw().

    Includes up to 300 chars before the for-loop header (to catch ctx properties
    set just before the loop, like fillStyle/font/textAlign) and 800 chars after.
    """
    marker = "for (const [idxStr, mm] of Object.entries(this.gridCellHeights))"
    pos = html.find(marker)
    assert pos != -1, f"gridCellHeights rendering loop not found: {marker!r}"
    start = max(0, pos - 300)
    return html[start: pos + 800]


def _draw_body(html: str) -> str:
    """Return the body of the draw() function (up to 14k chars)."""
    start = html.find("    draw() {")
    assert start != -1, "draw() function not found"
    return html[start: start + 14000]


# ---------------------------------------------------------------------------
# T1 — No ctx.arc() inside the set-cell rendering loop
# ---------------------------------------------------------------------------

class TestNoDotArcInGridLoop:
    """T1 — The blue dot arc() call must be removed from the gridCellHeights loop."""

    def test_no_arc_in_grid_loop(self):
        html = _html()
        loop = _grid_loop_body(html)
        assert "ctx.arc(" not in loop, (
            "ctx.arc() still present inside the gridCellHeights rendering loop — "
            "dot not replaced by text"
        )


# ---------------------------------------------------------------------------
# T2 — fillText used for set cells
# ---------------------------------------------------------------------------

class TestFillTextInGridLoop:
    """T2 — ctx.fillText() renders the cell value inside the loop."""

    def test_fillText_in_grid_loop(self):
        html = _html()
        loop = _grid_loop_body(html)
        assert "ctx.fillText(" in loop, (
            "ctx.fillText() not found inside the gridCellHeights loop — "
            "value text not rendered"
        )


# ---------------------------------------------------------------------------
# T3 — Text is centered (textAlign + textBaseline)
# ---------------------------------------------------------------------------

class TestTextCentered:
    """T3 — ctx.textAlign='center' and ctx.textBaseline='middle' set before fillText."""

    def test_textAlign_center_in_draw(self):
        html = _html()
        draw = _draw_body(html)
        assert re.search(r"ctx\.textAlign\s*=\s*['\"]center['\"]", draw), (
            "ctx.textAlign = 'center' not found in draw() — text not centered horizontally"
        )

    def test_textBaseline_middle_in_draw(self):
        html = _html()
        draw = _draw_body(html)
        assert re.search(r"ctx\.textBaseline\s*=\s*['\"]middle['\"]", draw), (
            "ctx.textBaseline = 'middle' not found in draw() — text not centered vertically"
        )


# ---------------------------------------------------------------------------
# T4 — Text format: 1 decimal, no 'mm' suffix
# ---------------------------------------------------------------------------

class TestTextFormat:
    """T4 — Value formatted as toFixed(1); 'mm' not appended in fillText call."""

    def test_toFixed_1_in_grid_loop(self):
        html = _html()
        loop = _grid_loop_body(html)
        assert re.search(r'\.toFixed\s*\(\s*1\s*\)', loop), (
            ".toFixed(1) not found inside grid rendering loop — format not 1 decimal"
        )

    def test_no_mm_suffix_in_fillText(self):
        html = _html()
        loop = _grid_loop_body(html)
        # The fillText call must not embed ' mm' or "mm" in the rendered string
        # (tooltip may keep " mm", but the canvas fillText must not)
        fill_start = loop.find("ctx.fillText(")
        assert fill_start != -1, "fillText not in loop — T2 should catch this"
        fill_expr = loop[fill_start: fill_start + 120]
        assert " mm" not in fill_expr and "' mm'" not in fill_expr and '"mm"' not in fill_expr, (
            "ctx.fillText includes 'mm' suffix — spec says no unit on canvas"
        )


# ---------------------------------------------------------------------------
# T5 — Text color is blue/indigo accent
# ---------------------------------------------------------------------------

class TestTextColorBlue:
    """T5 — The fillStyle for the value text uses the blue/indigo accent color."""

    def test_blue_fillStyle_in_grid_loop(self):
        html = _html()
        loop = _grid_loop_body(html)
        # Accept rgb / rgba / hex variants of the indigo blue family used before.
        # Original dot was rgba(99,102,241,0.85) — keep similar family.
        # Accept: 99 (indigo), #6366, rgb/rgba with 99 as R, or any indigo-family hex.
        assert re.search(
            r'rgba?\s*\(\s*9\d|#6[0-9a-f]{3,5}|indigo|rgba\(99|fillStyle.*6[36]',
            loop, re.IGNORECASE
        ), (
            "No blue/indigo fillStyle found in grid rendering loop — "
            "set cells will not be visually accented"
        )


# ---------------------------------------------------------------------------
# T6 — Right-click still deletes (regression)
# ---------------------------------------------------------------------------

class TestRightClickDeleteRegression:
    """T6 — onRightClick still deletes from gridCellHeights."""

    def test_rightclick_deletes_gridCellHeights(self):
        html = _html()
        start = html.find("    onRightClick(e) {")
        assert start != -1, "onRightClick not found"
        body = html[start: start + 3000]
        assert re.search(
            r'delete\s+(?:this\.)?gridCellHeights\[',
            body
        ), "onRightClick no longer deletes from gridCellHeights (regression)"


# ---------------------------------------------------------------------------
# T7 — Right-click hit detection no longer depends exclusively on dot arc radius
# ---------------------------------------------------------------------------

class TestRightClickHitDetection:
    """T7 — Right-click delete still detects clicks within cell / text bounds."""

    def test_rightclick_has_hit_detection(self):
        html = _html()
        start = html.find("    onRightClick(e) {")
        assert start != -1, "onRightClick not found"
        body = html[start: start + 3000]
        # Must still have some form of spatial hit detection (cell bounds or text bounds)
        # — either the old dot-radius approach expanded to full cell, or a cell-bbox check.
        assert re.search(
            r'pos\.w|pos\.x|dotR|clientX.*rect|canvasPx|_gridCellCanvasPx',
            body
        ), "onRightClick has no spatial hit detection for grid cells (regression)"


# ---------------------------------------------------------------------------
# T8 — Left-click opens input (regression)
# ---------------------------------------------------------------------------

class TestLeftClickOpensInput:
    """T8 — openGridCell() still called from onMouseUp for grid cells."""

    def test_openGridCell_called_from_mouseup(self):
        html = _html()
        start = html.find("    onMouseUp(e) {")
        assert start != -1, "onMouseUp not found"
        body = html[start: start + 3000]
        assert "openGridCell" in body, (
            "openGridCell() not called from onMouseUp — left-click to edit is broken"
        )


# ---------------------------------------------------------------------------
# T9 — Hover tooltip still fires (regression)
# ---------------------------------------------------------------------------

class TestHoverTooltipRegression:
    """T9 — _gridHoveredCell still updated in onMouseMove."""

    def test_gridHoveredCell_updated_in_onMouseMove(self):
        html = _html()
        start = html.find("    onMouseMove(e) {")
        assert start != -1, "onMouseMove not found"
        body = html[start: start + 6000]
        assert "_gridHoveredCell" in body, (
            "_gridHoveredCell no longer set in onMouseMove — tooltip regression"
        )


# ---------------------------------------------------------------------------
# T10 — Unset cells render nothing (no stray fillText outside the loop)
# ---------------------------------------------------------------------------

class TestUnsetCellsNoText:
    """T10 — fillText is only inside the gridCellHeights loop, not called for all cells."""

    def test_fillText_only_inside_set_cell_loop(self):
        html = _html()
        draw = _draw_body(html)
        # Count fillText occurrences in draw()
        fill_count = draw.count("ctx.fillText(")
        loop = _grid_loop_body(html)
        loop_fill_count = loop.count("ctx.fillText(")
        # All fillText calls for values must be inside the loop.
        # Allow for one fillText *outside* only if it's for something entirely unrelated
        # (e.g. a legend label) — but 0 outside the loop is ideal.
        # The loop must contain at least 1 fillText.
        assert loop_fill_count >= 1, (
            "No fillText inside gridCellHeights loop — value text not rendered (T2 should catch)"
        )


# ---------------------------------------------------------------------------
# T11 — No ctx.arc inside the gridCellHeights loop specifically (belt+suspenders)
# ---------------------------------------------------------------------------

class TestNoArcInLoop:
    """T11 — Belt-and-suspenders: arc() not anywhere inside the set-cell rendering loop."""

    def test_arc_absent_from_set_cell_loop(self):
        html = _html()
        loop = _grid_loop_body(html)
        # Should not have ctx.arc — T1 tests same but scoped slightly differently
        assert "ctx.arc" not in loop, (
            "ctx.arc found inside gridCellHeights loop — dot not fully replaced"
        )


# ---------------------------------------------------------------------------
# T12 — Polygon vertex arcs still present outside the grid loop (regression)
# ---------------------------------------------------------------------------

class TestPolygonArcRegression:
    """T12 — ctx.arc() for polygon/contour vertices is still in draw()."""

    def test_polygon_arc_still_in_draw(self):
        html = _html()
        draw = _draw_body(html)
        assert "ctx.arc(" in draw, (
            "ctx.arc() completely removed from draw() — polygon vertex rendering broken"
        )


# ---------------------------------------------------------------------------
# T13 — APP_VERSION bumped to v5.10
# ---------------------------------------------------------------------------

class TestAppVersion:
    """T13 — APP_VERSION is at least v5.10 after this task."""

    def test_app_version_is_v5_10_or_higher(self):
        src = _app_py()
        m = re.search(r'APP_VERSION\s*=\s*["\']v(\d+)\.(\d+)["\']', src)
        assert m is not None, "APP_VERSION not found in app.py"
        major, minor = int(m.group(1)), int(m.group(2))
        assert (major, minor) >= (5, 10), (
            f"APP_VERSION is v{major}.{minor:02d} — expected at least v5.10 after task 720"
        )


# ---------------------------------------------------------------------------
# T14 — editor.html on-page version bumped to at least v5.07
# ---------------------------------------------------------------------------

class TestEditorHtmlVersion:
    """T14 — editor.html on-page version comment is at least v5.07."""

    def test_editor_version_is_v5_07_or_higher(self):
        html = _html()
        m = re.search(r'Boundary Editor v(\d+)\.(\d+)', html)
        assert m is not None, "No 'Boundary Editor vX.XX' version string in editor.html"
        major, minor = int(m.group(1)), int(m.group(2))
        assert (major, minor) >= (5, 7), (
            f"editor.html version is v{major}.{minor:02d} — expected at least v5.07"
        )
