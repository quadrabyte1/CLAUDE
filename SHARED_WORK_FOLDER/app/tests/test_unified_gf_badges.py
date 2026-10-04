"""
test_unified_gf_badges.py — Bug→TDD for unified G/F badge UI (task 683, v4.90).
Updated 2026-10-02: F-badge (fringeBoundaryHeights) removed per semantic pivot
(exterior ring numbers are distance-from-pin, not altitude). G-badge tests intact.

Tests still active:

  T1  G-badge render:
      elevationSpikes entries render as compact G-badges (not E-badges, not
      spinner, not × button).
  T3  G-badge uses letter 'G':
      The inner badge letter for elevation spikes is 'G', not 'E'.
  T4  No spinner on G-badge:
      The G-badge section must not contain ▲/▼ spinner buttons
      (▲ = &#9650;, ▼ = &#9660;).
  T6  No delete (×) on G-badge.
  T8  Editable input on G-badge.
  T10 G-badge edit commits to elevationSpikes[i].mm.
  T12 Esc reverts: editor JS has a keydown handler referencing 'Escape' or 'Esc'.
  T14 Pointer-events wrapping on G-badge.
  T15 APP_VERSION is v4.92 in app.py.

Tests retired (F-badge removed 2026-10-02):
  T2  F-badge render          — fringeBoundaryHeights pipeline deleted
  T5  No spinner on F-badge   — ditto
  T7  No delete on F-badge    — ditto
  T9  Editable input F-badge  — ditto
  T11 F commit handler        — ditto
  T13 Status strip G+F labels — strip now shows G only

Run:
    cd /Volumes/GIT/CLAUDE/SHARED_WORK_FOLDER
    python -m pytest app/tests/test_unified_gf_badges.py -v
"""
from __future__ import annotations

import re
import sys
from pathlib import Path

import pytest

# T5 (2026-10-03): G-badge (elevationSpikes) and Add Spike stripped from editor.html.
# All tests in this file are tombstoned until a replacement mechanism ships.
pytestmark = pytest.mark.skip(reason="T5: G-badge/elevationSpikes/spikeMode stripped from editor.html")

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

def _extract_section(html: str, start_marker: str, end_marker: str) -> str:
    """Extract HTML between two markers (inclusive of start, exclusive of end)."""
    start = html.find(start_marker)
    if start == -1:
        return ""
    end = html.find(end_marker, start + len(start_marker))
    if end == -1:
        return html[start:]
    return html[start:end]


def _extract_xfor_template(html: str, iterator_var: str) -> str:
    """
    Extract the first <template x-for> block that iterates over iterator_var.
    Returns the block content (everything between <template ...> and </template>).
    """
    pattern = re.compile(
        r'<template[^>]+x-for[^>]+' + re.escape(iterator_var) + r'[^>]*>(.*?)</template>',
        re.DOTALL | re.IGNORECASE,
    )
    m = pattern.search(html)
    if m:
        return m.group(0)
    return ""


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture(scope="module")
def editor_html() -> str:
    return EDITOR_HTML.read_text(encoding="utf-8")


@pytest.fixture(scope="module")
def app_py_src() -> str:
    return APP_PY.read_text(encoding="utf-8")


@pytest.fixture(scope="module")
def spike_template(editor_html: str) -> str:
    """The x-for template block that renders elevation spikes."""
    return _extract_xfor_template(editor_html, "elevationSpikes")


@pytest.fixture(scope="module")
def fringe_template(editor_html: str) -> str:
    """
    RETIRED 2026-10-02: fringeBoundaryHeights template removed (exterior ring
    numbers are distance-from-pin, not altitude).  Returns empty string so
    retired tests skip gracefully via their own skip marks.
    """
    return ""


# ---------------------------------------------------------------------------
# T1  G-badge render: elevationSpikes uses compact badge (no verbose orange E)
# ---------------------------------------------------------------------------

class TestGBadgeRender:
    """T1 — elevationSpikes template uses compact G-badge style."""

    def test_spike_template_exists(self, spike_template):
        """T1a — x-for template over elevationSpikes is present."""
        assert spike_template, "editor.html: no x-for template found iterating elevationSpikes"

    def test_g_badge_not_e_badge(self, spike_template):
        """T1b — G-badge uses letter 'G', not 'E'."""
        # The badge letter div should contain G, not E
        # E is the old letter; G is the new paradigm
        has_g = bool(re.search(r'>\s*G\s*<', spike_template))
        has_e_as_badge = bool(re.search(r'>\s*E\s*<', spike_template))
        assert has_g, (
            "elevationSpikes template does not contain 'G' as badge letter.\n"
            f"Template snippet:\n{spike_template[:600]}"
        )
        assert not has_e_as_badge, (
            "elevationSpikes template still has 'E' as badge letter — should be 'G'.\n"
            f"Template snippet:\n{spike_template[:600]}"
        )


# ---------------------------------------------------------------------------
# T2  F-badge render: fringeBoundaryHeights has editable input
# ---------------------------------------------------------------------------

@pytest.mark.skip(reason="F-badge removed 2026-10-02: exterior ring numbers are distance-from-pin, not altitude")
class TestFBadgeRender:
    """T2 — RETIRED: fringeBoundaryHeights pipeline deleted 2026-10-02."""

    def test_fringe_template_exists(self, fringe_template):
        pass

    def test_f_badge_letter_present(self, fringe_template):
        pass


# ---------------------------------------------------------------------------
# T3  G-badge uses letter 'G'
# ---------------------------------------------------------------------------

class TestGBadgeLetter:
    """T3 — badge letter for interior spikes is 'G'."""

    def test_g_letter_in_spike_template(self, spike_template):
        """T3 — elevationSpikes badge contains 'G'."""
        assert re.search(r'>\s*G\s*<', spike_template), (
            "elevationSpikes badge letter is not 'G'.\n"
            f"Template: {spike_template[:500]}"
        )


# ---------------------------------------------------------------------------
# T4, T5  No spinner on either badge
# ---------------------------------------------------------------------------

class TestNoSpinner:
    """T4, T5 — Neither G nor F badge has ▲/▼ spinner controls."""

    def test_no_spinner_on_g_badge(self, spike_template):
        """T4 — elevationSpikes template has no ▲/▼ spinner buttons."""
        has_up = "&#9650;" in spike_template or "▲" in spike_template
        has_down = "&#9660;" in spike_template or "▼" in spike_template
        assert not has_up, (
            "elevationSpikes template still has ▲ (up arrow / &#9650;) spinner button."
        )
        assert not has_down, (
            "elevationSpikes template still has ▼ (down arrow / &#9660;) spinner button."
        )

    @pytest.mark.skip(reason="F-badge removed 2026-10-02")
    def test_no_spinner_on_f_badge(self, fringe_template):
        """T5 — RETIRED: fringeBoundaryHeights template deleted 2026-10-02."""
        pass


# ---------------------------------------------------------------------------
# T6, T7  No delete (×) on either badge
# ---------------------------------------------------------------------------

class TestNoDelete:
    """T6, T7 — G badge × delete button (if present) must be conditional on source === 'user';
    OCR spikes must never show an unconditional delete affordance."""

    def test_no_unconditional_delete_on_g_badge(self, spike_template):
        """T6 — if × / &times; appears in the spike template, it must be guarded
        by sp.source === 'user' (x-show or x-if). An unconditional delete button
        would allow OCR spikes to be deleted, which is forbidden.

        Updated 2026-10-02 (v4.96): user-spike delete affordance ships with a
        source guard, so the × IS in the template — the test now verifies the
        guard rather than the absence of ×.
        """
        has_times = "&times;" in spike_template or "×" in spike_template
        if not has_times:
            # No × at all — fully compliant (pre-T4 state)
            return
        # × IS present — verify it is guarded by source === 'user'
        has_source_guard = re.search(
            r"""(?:x-show|x-if)\s*=\s*["'].*?sp\.source\s*===?\s*['"]user['"].*?["']""",
            spike_template,
        )
        assert has_source_guard, (
            "elevationSpikes template contains × / &times; but it is NOT guarded by "
            "sp.source === 'user'. OCR spikes must never show a delete button.\n"
            "Wrap the × button in x-show=\"sp.source === 'user'\"."
        )

    @pytest.mark.skip(reason="F-badge removed 2026-10-02")
    def test_no_delete_on_f_badge(self, fringe_template):
        """T7 — RETIRED: fringeBoundaryHeights template deleted 2026-10-02."""
        pass

    @pytest.mark.skip(reason="F-badge removed 2026-10-02")
    def test_no_delete_on_f_badge(self, fringe_template):
        """T7 — RETIRED: fringeBoundaryHeights template deleted 2026-10-02."""
        pass


# ---------------------------------------------------------------------------
# T8, T9  Editable <input> on both badges
# ---------------------------------------------------------------------------

class TestEditableInput:
    """T8, T9 — Both badge types have a focusable <input> for value editing."""

    def test_input_on_g_badge(self, spike_template):
        """T8 — elevationSpikes template contains an <input> element."""
        assert "<input" in spike_template, (
            "elevationSpikes template has no <input> element — values are not editable."
        )

    @pytest.mark.skip(reason="F-badge removed 2026-10-02")
    def test_input_on_f_badge(self, fringe_template):
        """T9 — RETIRED: fringeBoundaryHeights template deleted 2026-10-02."""
        pass


# ---------------------------------------------------------------------------
# T10, T11  Edit commit handlers write to the correct state fields
# ---------------------------------------------------------------------------

class TestEditCommit:
    """T10, T11 — Edit commit handlers write back to the correct state properties."""

    def test_g_badge_commit_writes_mm(self, editor_html):
        """T10 — JS handler writes to elevationSpikes[i].mm (not some other field)."""
        # Look for assignment to elevationSpikes[...].mm or elevationSpikes[idx].mm
        pattern = re.compile(
            r'elevationSpikes\s*\[.*?\]\s*\.\s*mm\s*=',
            re.DOTALL,
        )
        assert pattern.search(editor_html), (
            "editor.html: no JS assignment to elevationSpikes[i].mm found — "
            "G-badge edit commits are not wired."
        )

    @pytest.mark.skip(reason="F-badge removed 2026-10-02")
    def test_f_badge_commit_writes_value(self, editor_html):
        """T11 — RETIRED: fringeBoundaryHeights pipeline deleted 2026-10-02."""
        pass


# ---------------------------------------------------------------------------
# T12  Esc reverts
# ---------------------------------------------------------------------------

class TestEscReverts:
    """T12 — Keyboard Escape reverts an in-progress edit."""

    def test_escape_handler_present(self, editor_html):
        """T12 — editor.html contains an Escape key handler for badge inputs."""
        has_escape = (
            "'Escape'" in editor_html
            or '"Escape"' in editor_html
            or "'Esc'" in editor_html
            or '"Esc"' in editor_html
            or "@keydown.escape" in editor_html
            or "keydown.esc" in editor_html.lower()
        )
        assert has_escape, (
            "editor.html: no Escape key handler found — Esc-to-revert not implemented."
        )


# ---------------------------------------------------------------------------
# T13  Status strip updated
# ---------------------------------------------------------------------------

class TestStatusStrip:
    """T13 — Status strip references G count (F removed 2026-10-02)."""

    def test_status_strip_present(self, editor_html):
        """T13a — status strip div is still in the template with G spike count."""
        has_spike_count = "elevationSpikes.length" in editor_html
        assert has_spike_count, (
            "Status strip missing elevationSpikes.length reference."
        )

    def test_status_strip_uses_g_label(self, editor_html):
        """T13b — Status strip uses 'G' label."""
        strip_area = _extract_section(
            editor_html,
            "OCR detection status strip",
            "── Elevation-spike overlays",
        )
        has_g_label = re.search(r"['\"].*\bG\b.*['\"]", strip_area) or "G" in strip_area
        assert has_g_label, (
            "Status strip does not reference 'G' badge letter.\n"
            f"Strip area: {strip_area[:400]}"
        )

    @pytest.mark.skip(reason="F-badge removed 2026-10-02: strip now shows G count only")
    def test_status_strip_uses_g_f_labels(self, editor_html):
        """T13b (orig) — RETIRED: F badge removed 2026-10-02."""
        pass


# ---------------------------------------------------------------------------
# T14  Pointer-events: outer wrapper none, input has pointer-events-auto
# ---------------------------------------------------------------------------

class TestPointerEvents:
    """T14 — Outer wrapper has pointer-events-none but input has pointer-events-auto."""

    def test_g_badge_input_is_focusable(self, spike_template):
        """T14a — G-badge outer wrapper has pointer-events-none but input is focusable."""
        # The outer div should have pointer-events-none
        outer_has_none = "pointer-events-none" in spike_template
        # The input itself or a wrapper around it should have pointer-events-auto
        # OR the input appears without pointer-events-none on it directly
        # Key: outer wrapper is pointer-events-none, but the input must be reachable
        input_match = re.search(r'<input[^>]*>', spike_template)
        if input_match:
            input_tag = input_match.group(0)
            # input must NOT itself have pointer-events-none
            input_has_none = "pointer-events-none" in input_tag
            assert not input_has_none, (
                "G-badge <input> has pointer-events-none directly on it — not focusable."
            )
        # Outer wrapper should have pointer-events-none (per spec)
        assert outer_has_none, (
            "G-badge outer wrapper missing pointer-events-none — spec says outer wrapper "
            "is pointer-events-none, input has pointer-events-auto."
        )

    @pytest.mark.skip(reason="F-badge removed 2026-10-02")
    def test_f_badge_input_is_focusable(self, fringe_template):
        """T14b — RETIRED: F-badge template deleted 2026-10-02."""
        pass


# ---------------------------------------------------------------------------
# T15  APP_VERSION is v4.90
# ---------------------------------------------------------------------------

class TestAppVersion:
    """T15 — APP_VERSION in app.py is v4.95+ (updated to v4.96 for user-spike delete affordance)."""

    def test_app_version_is_v494(self, app_py_src):
        """T15 — app.py APP_VERSION = 'v4.95' or later (v4.96 after user-spike delete task)."""
        has_v495 = 'APP_VERSION = "v4.95"' in app_py_src or "APP_VERSION = 'v4.95'" in app_py_src
        has_v496 = 'APP_VERSION = "v4.96"' in app_py_src or "APP_VERSION = 'v4.96'" in app_py_src
        assert has_v495 or has_v496, (
            "app.py APP_VERSION is not v4.95 or v4.96 — version bump not applied."
        )
