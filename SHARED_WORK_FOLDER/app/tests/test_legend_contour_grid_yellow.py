"""
test_legend_contour_grid_yellow.py — Bug→TDD for:
  1. Contour legend row removal (task 706 part A)
  2. Grid overlay recolor to lemon yellow (task 706 part B)

RED first, then implement, then GREEN.

Test inventory
==============

T1  Legend has NO contour entry (row with text "Contour" must not appear)
T2  Legend still has Green entry (regression)
T3  Legend still has Trap entry (regression)
T4  Legend still has Water entry (regression)
T5  Legend still has Fringe anchor entry (regression)
T6  Grid stroke uses lemon-yellow hex #FFF44F (not the old indigo rgba)
T7  Grid draw section does NOT contain the old indigo grid stroke color rgba(90,90,160
T8  APP_VERSION is v5.02 in app.py
T9  editor.html on-page version comment is v5.02

Run:
    cd /Volumes/GIT/CLAUDE/SHARED_WORK_FOLDER
    python -m pytest app/tests/test_legend_contour_grid_yellow.py -v
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

LEMON_YELLOW = "#FFF44F"


def _html() -> str:
    return EDITOR_HTML.read_text(encoding="utf-8")


def _app_py() -> str:
    return APP_PY.read_text(encoding="utf-8")


# ---------------------------------------------------------------------------
# T1 — Legend has NO "Contour" entry
# ---------------------------------------------------------------------------

class TestLegendContourRemoved:
    """T1 — The contour row must not appear in the legend."""

    def test_no_contour_text_in_legend(self):
        html = _html()
        # Find the legend section
        legend_start = html.find("{# ── Region legend")
        assert legend_start != -1, "Legend section not found"
        # The legend ends before the tee-hole marker section
        legend_end = html.find("{# ── Tee-hole marker", legend_start)
        if legend_end == -1:
            legend_end = legend_start + 2000
        legend_html = html[legend_start:legend_end]
        # Must NOT contain the word "Contour" as a legend label
        assert ">Contour<" not in legend_html, (
            "Legend still contains a 'Contour' entry — it should be removed"
        )

    def test_no_ffe600_in_legend(self):
        html = _html()
        # Find the legend section
        legend_start = html.find("{# ── Region legend")
        assert legend_start != -1, "Legend section not found"
        legend_end = html.find("{# ── Tee-hole marker", legend_start)
        if legend_end == -1:
            legend_end = legend_start + 2000
        legend_html = html[legend_start:legend_end]
        # The contour-coded yellow swatch must not appear in the legend
        assert "#FFE600" not in legend_html, (
            "Legend still contains #FFE600 contour color swatch — remove it"
        )


# ---------------------------------------------------------------------------
# T2–T5 — Legend regression: other rows must still be present
# ---------------------------------------------------------------------------

class TestLegendRegressions:
    """T2–T5 — Remaining legend rows survive the contour removal."""

    def _legend(self) -> str:
        html = _html()
        start = html.find("{# ── Region legend")
        assert start != -1, "Legend section not found"
        end = html.find("{# ── Tee-hole marker", start)
        if end == -1:
            end = start + 2000
        return html[start:end]

    def test_green_legend_row_present(self):
        """T2 — Green row still in legend."""
        assert ">Green<" in self._legend(), "Green legend row missing"

    def test_trap_legend_row_present(self):
        """T3 — Trap row still in legend."""
        assert ">Trap<" in self._legend(), "Trap legend row missing"

    def test_water_legend_row_present(self):
        """T4 — Water row still in legend."""
        assert ">Water<" in self._legend(), "Water legend row missing"

    def test_fringe_anchor_legend_row_present(self):
        """T5 — Fringe anchor row still in legend."""
        legend = self._legend()
        assert "Fringe anchor" in legend, "Fringe anchor legend row missing"


# ---------------------------------------------------------------------------
# T6 — Grid stroke is lemon yellow #FFF44F
# ---------------------------------------------------------------------------

def _draw_grid_section(html: str) -> str:
    """Return the ~2000-char slice of draw() that contains the grid rendering."""
    # The grid drawing code is the SECOND occurrence of the grid overlay comment
    # (first is in the Alpine state declaration block; second is inside draw())
    marker = "// ── Grid cell elevation overlay (v5.00)"
    first = html.find(marker)
    assert first != -1, "Grid overlay marker not found"
    second = html.find(marker, first + 1)
    assert second != -1, "Second grid overlay marker (in draw()) not found"
    return html[second:second + 2000]


class TestGridLemonYellow:
    """T6 — Grid cell boundary lines use lemon yellow."""

    def test_grid_stroke_is_lemon_yellow(self):
        html = _html()
        section = _draw_grid_section(html)
        assert LEMON_YELLOW in section, (
            f"Grid stroke color {LEMON_YELLOW} not found in draw() grid section"
        )


# ---------------------------------------------------------------------------
# T7 — Old indigo grid stroke is gone from the grid section
# ---------------------------------------------------------------------------

class TestGridOldIndigoGone:
    """T7 — The faint indigo grid stroke must be replaced."""

    def test_old_indigo_not_in_grid_section(self):
        html = _html()
        section = _draw_grid_section(html)
        # Old color: rgba(90,90,160,...)
        assert "rgba(90,90,160" not in section, (
            "Old indigo grid stroke rgba(90,90,160,...) still present — not replaced"
        )


# ---------------------------------------------------------------------------
# T8 — APP_VERSION is v5.03
# ---------------------------------------------------------------------------

class TestAppVersionBump:
    """T8 — APP_VERSION bumped to v5.03 (task 708: trap simplify flat+rake)."""

    def test_app_version_is_v5_02(self):
        """Updated: now checks v5.03 (bumped by task 708)."""
        src = _app_py()
        m = re.search(r'APP_VERSION\s*=\s*["\']v(\d+)\.(\d+)["\']', src)
        assert m is not None, "APP_VERSION not found in app.py"
        major, minor = int(m.group(1)), int(m.group(2))
        assert (major, minor) >= (5, 3), (
            f"APP_VERSION is v{major}.{minor:02d} — expected >= v5.03 (task 708)"
        )


# ---------------------------------------------------------------------------
# T9 — editor.html on-page version is v5.02 or newer
# ---------------------------------------------------------------------------

class TestEditorHtmlVersionBump:
    """T9 — editor.html version string is v5.02 or later (bumped each task)."""

    def test_editor_version_is_v5_02(self):
        """Updated: accept v5.02 or any later version (editor.html advances independently)."""
        html = _html()
        m = re.search(r'Boundary Editor v(\d+)\.(\d+)', html)
        assert m is not None, "No 'Boundary Editor vX.XX' version string in editor.html"
        major, minor = int(m.group(1)), int(m.group(2))
        assert (major, minor) >= (5, 2), (
            f"editor.html version is v{major}.{minor:02d} — expected >= v5.02"
        )
