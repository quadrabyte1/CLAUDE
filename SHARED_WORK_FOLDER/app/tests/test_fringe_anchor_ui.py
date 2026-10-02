"""
test_fringe_anchor_ui.py — RETIRED 2026-10-02.

Original purpose (task 679, v4.88): test that fringeBoundaryHeights / F-badge
overlay / anchor status strip were wired up correctly.

Semantic pivot 2026-10-02: exterior ring numbers (10,15,20,25,30) are
distance-from-pin markers, NOT altitude values.  The fringeBoundaryHeights →
F-badge → fringe anchor pipeline has been removed.

All tests in this file are now SKIPPED.  Their replacement is
test_strip_exterior_ocr.py which asserts the *absence* of the removed API.

Run:
    cd /Volumes/GIT/CLAUDE/SHARED_WORK_FOLDER
    python -m pytest app/tests/test_fringe_anchor_ui.py -v
"""
from __future__ import annotations

import pytest


pytestmark = pytest.mark.skip(
    reason="F-badge / fringeBoundaryHeights pipeline removed 2026-10-02. "
           "See test_strip_exterior_ocr.py for the replacement assertions."
)


class TestFringeBoundaryHeightsCount:
    """T4 — RETIRED: fringeBoundaryHeights removed 2026-10-02."""
    def test_fringe_boundary_heights_at_least_4(self):
        pass
    def test_fringe_boundary_heights_have_correct_shape(self):
        pass


class TestEditorHtmlStructure:
    """T5,T6,T7,T8 — RETIRED: F-badge markup removed 2026-10-02."""
    def test_fringe_anchor_badge_markup_present(self):
        pass
    def test_fringe_anchor_xfor_loop_present(self):
        pass
    def test_status_strip_spike_count_present(self):
        pass
    def test_status_strip_anchor_count_present(self):
        pass
    def test_status_strip_has_ocr_summary_text(self):
        pass
    def test_fringe_anchor_badge_uses_F_letter(self):
        pass
    def test_fringe_anchor_positioned_on_canvas(self):
        pass
    def test_fringe_anchor_badge_non_editable_indicator(self):
        pass
