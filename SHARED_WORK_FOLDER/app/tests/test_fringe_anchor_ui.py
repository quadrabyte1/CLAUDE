"""
test_fringe_anchor_ui.py — TDD tests for Part B: fringe anchor badge visibility
and status strip (task 679, v4.88).

Tests:
  T4  GET /api/detect_boundaries for DeLaveaga H5 returns fringeBoundaryHeights
      with >= 4 entries (empirically 9 known detectable after v4.88 fix).
  T5  Rendered editor HTML contains fringe-anchor badge markup (data-fringe-anchor).
  T6  Editor HTML contains status strip markup with spike and anchor count
      placeholders.
  T7  fringeBoundaryHeights entries have correct shape {x, y, value}.
  T8  Fringe anchor badges are visually distinct from orange E-spike badges
      (different class/letter in badge markup).

Run:
    cd /Volumes/GIT/CLAUDE/SHARED_WORK_FOLDER
    python -m pytest app/tests/test_fringe_anchor_ui.py -v
"""
from __future__ import annotations

import json
import os
import sys
from pathlib import Path

import pytest

# ---------------------------------------------------------------------------
# Path setup
# ---------------------------------------------------------------------------
APP_DIR = Path(__file__).parent.parent
REPO_ROOT = APP_DIR.parent
sys.path.insert(0, str(APP_DIR))

_DL_H5 = REPO_ROOT / "ItWentIn/GolfCourses/Delaveaga/Images/Delaveaga (Hole 5, 55169).png"


# ---------------------------------------------------------------------------
# Flask test-client fixture (temp DB — never touches live workspace.db)
# ---------------------------------------------------------------------------

@pytest.fixture()
def app_client(tmp_path, monkeypatch):
    """Flask test client with a temp DB."""
    import app as _app_module
    tmp_db = str(tmp_path / "workspace.db")
    tmp_egm_base = str(tmp_path / "GolfCourses")
    monkeypatch.setattr(_app_module, "DB_PATH", tmp_db)
    monkeypatch.setattr(_app_module, "_EGM_BASE", tmp_egm_base)
    _app_module.app.config["TESTING"] = True
    with _app_module.app.test_client() as client:
        yield client


# ---------------------------------------------------------------------------
# T4 — fringeBoundaryHeights count for DeLaveaga H5
# ---------------------------------------------------------------------------

@pytest.mark.skipif(not _DL_H5.exists(), reason="DeLaveaga Hole 5 image not present")
class TestFringeBoundaryHeightsCount:
    """
    T4 — After v4.88 fix, detect_boundaries for DeLaveaga H5 returns
    fringeBoundaryHeights with >= 4 entries.
    """

    def test_fringe_boundary_heights_at_least_4(self, app_client, monkeypatch):
        """T4a — at least 4 fringeBoundaryHeights entries (v4.88 enables exterior OCR)."""
        import app as _app_module
        monkeypatch.setattr(
            _app_module, "_find_image_path",
            lambda name, preferred_course="": str(_DL_H5),
        )
        resp = app_client.post(
            "/api/detect_boundaries",
            data=json.dumps({
                "image": "Delaveaga (Hole 5, 55169).png",
                "course": "Delaveaga",
                "imageCourse": "Delaveaga",
            }),
            content_type="application/json",
        )
        assert resp.status_code == 200
        data = resp.get_json()
        assert data.get("status") == "ok", f"detect_boundaries error: {data}"
        fbh = data.get("fringeBoundaryHeights", [])
        assert len(fbh) >= 4, (
            f"Expected >= 4 fringeBoundaryHeights entries, got {len(fbh)}: {fbh}"
        )

    def test_fringe_boundary_heights_have_correct_shape(self, app_client, monkeypatch):
        """T4b — each fringeBoundaryHeights entry has {x, y, value} with float value."""
        import app as _app_module
        monkeypatch.setattr(
            _app_module, "_find_image_path",
            lambda name, preferred_course="": str(_DL_H5),
        )
        resp = app_client.post(
            "/api/detect_boundaries",
            data=json.dumps({
                "image": "Delaveaga (Hole 5, 55169).png",
                "course": "Delaveaga",
                "imageCourse": "Delaveaga",
            }),
            content_type="application/json",
        )
        data = resp.get_json()
        fbh = data.get("fringeBoundaryHeights", [])
        for entry in fbh:
            assert "x" in entry and "y" in entry and "value" in entry, (
                f"Entry missing required field: {entry}"
            )
            assert isinstance(entry["value"], (int, float)), (
                f"value should be numeric: {entry}"
            )
            assert isinstance(entry["x"], (int, float)), f"x should be numeric: {entry}"
            assert isinstance(entry["y"], (int, float)), f"y should be numeric: {entry}"


# ---------------------------------------------------------------------------
# T5, T6, T7, T8 — Editor HTML structure tests
# ---------------------------------------------------------------------------

class TestEditorHtmlStructure:
    """
    T5 — Editor HTML contains fringe-anchor badge markup (data-fringe-anchor attr).
    T6 — Editor HTML contains status strip markup with spike/anchor counts.
    T7 — fringeBoundaryHeights template iterates via x-for with key='anchor-'.
    T8 — Fringe anchor badge uses 'F' (not 'E') so it's visually distinct from spikes.
    """

    @pytest.fixture(scope="class")
    def editor_html(self):
        """Load editor.html source as a string."""
        path = APP_DIR / "templates" / "editor.html"
        return path.read_text(encoding="utf-8")

    def test_fringe_anchor_badge_markup_present(self, editor_html):
        """T5 — editor.html contains fringe-anchor badge overlay markup."""
        assert "data-fringe-anchor" in editor_html, (
            "editor.html missing data-fringe-anchor attribute on fringe anchor badges"
        )

    def test_fringe_anchor_xfor_loop_present(self, editor_html):
        """T5b — editor.html has an x-for loop iterating fringeBoundaryHeights."""
        assert "fringeBoundaryHeights" in editor_html, (
            "editor.html missing fringeBoundaryHeights reference in template"
        )
        # A template loop that generates fringe anchor badges
        assert "anchor-" in editor_html, (
            "editor.html missing fringe anchor x-for key='anchor-*'"
        )

    def test_status_strip_spike_count_present(self, editor_html):
        """T6a — editor.html contains the spike count display element."""
        # The status strip shows "N interior spikes · M fringe anchors"
        assert "elevationSpikes.length" in editor_html, (
            "editor.html missing elevationSpikes.length reference in status strip"
        )

    def test_status_strip_anchor_count_present(self, editor_html):
        """T6b — editor.html contains the anchor count display element."""
        assert "fringeBoundaryHeights.length" in editor_html, (
            "editor.html missing fringeBoundaryHeights.length reference in status strip"
        )

    def test_status_strip_has_ocr_summary_text(self, editor_html):
        """T6c — editor.html contains the OCR summary strip with recognizable text."""
        # The strip shows "N spikes · M anchors" or similar
        assert "spikes" in editor_html and "anchors" in editor_html, (
            "editor.html status strip missing 'spikes' or 'anchors' text"
        )

    def test_fringe_anchor_badge_uses_F_letter(self, editor_html):
        """T8 — Fringe anchor badge uses 'F' letter, not 'E' (E is for elevation spikes)."""
        # Find the fringe anchor badge template and check it uses F not E
        # The badge letter appears in a data-fringe-anchor context
        import re
        # Look for pattern like: data-fringe-anchor ... F (or similar)
        anchor_section_match = re.search(
            r'data-fringe-anchor.*?(?=data-fringe-anchor|</template>)',
            editor_html,
            re.DOTALL,
        )
        assert anchor_section_match is not None, (
            "Could not find data-fringe-anchor section in editor.html"
        )
        anchor_section = anchor_section_match.group(0)
        # The section should contain 'F' as the badge letter
        # Allow for whitespace around the letter (e.g. "> F\n" or ">F<" or "  F\n")
        import re as _re
        has_f_badge = bool(_re.search(r'>\s*F\s*<', anchor_section))
        assert has_f_badge, (
            f"Fringe anchor badge section does not contain 'F' letter badge. "
            f"Section: {anchor_section[:300]}"
        )

    def test_fringe_anchor_positioned_on_canvas(self, editor_html):
        """T5c — Fringe anchor badges are positioned using scale + offsetX/Y (same as spikes)."""
        # The positioning JS expression matches the spike pattern
        assert "fringeBoundaryHeights" in editor_html
        # Badges must track image position
        assert "offsetX" in editor_html and "offsetY" in editor_html, (
            "editor.html fringe anchor badges missing offsetX/offsetY positioning"
        )

    def test_fringe_anchor_badge_non_editable_indicator(self, editor_html):
        """T5d — Fringe anchor badges have a visual indicator they are non-editable."""
        # Non-editable styling: cursor-default, or pointer-events-none, or disabled button
        # The assignment says: non-editable (greyed out click handler)
        # We check that the anchor section does NOT have the same draggable pattern as spikes
        import re
        anchor_section_match = re.search(
            r'data-fringe-anchor.*?(?=</template>)',
            editor_html,
            re.DOTALL,
        )
        if anchor_section_match:
            section = anchor_section_match.group(0)
            # Should have pointer-events-none or cursor-default (not cursor-grab)
            has_non_editable = (
                "pointer-events-none" in section
                or "cursor-default" in section
                or "cursor-not-allowed" in section
                or "disabled" in section.lower()
            )
            assert has_non_editable, (
                f"Fringe anchor badge section should indicate non-editable state. "
                f"Section snippet: {section[:400]}"
            )
