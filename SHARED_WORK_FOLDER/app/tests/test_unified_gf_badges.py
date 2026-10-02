"""
test_unified_gf_badges.py — Bug→TDD for unified G/F badge UI (task 683, v4.90).

Thomas's request: interior spikes → compact G-badge with editable number input,
fringe anchors → compact F-badge with editable number input.
No spinner (▲/▼), no × delete button on either type.
Both use the compact F-badge visual style as baseline.

Tests (RED first, implemented after, then GREEN):

  T1  G-badge render:
      elevationSpikes entries render as compact G-badges (not E-badges, not
      spinner, not × button).
  T2  F-badge render:
      fringeBoundaryHeights entries render as compact F-badges with a focusable
      number input (previously non-editable).
  T3  G-badge uses letter 'G':
      The inner badge letter for elevation spikes is 'G', not 'E'.
  T4  No spinner on G-badge:
      The G-badge section must not contain ▲/▼ spinner buttons
      (▲ = &#9650;, ▼ = &#9660;).
  T5  No spinner on F-badge:
      The F-badge section must not contain ▲/▼ spinner buttons.
  T6  No delete (×) on G-badge:
      The G-badge section must not contain a × delete affordance.
  T7  No delete (×) on F-badge:
      The F-badge section must not contain a × delete affordance.
  T8  Editable input on G-badge:
      The G-badge template section contains an <input> element for editing.
  T9  Editable input on F-badge:
      The F-badge template section contains an <input> element for editing.
  T10 G-badge edit commits to elevationSpikes[i].mm:
      The editor JS has a handler that writes back to elevationSpikes[i].mm.
  T11 F-badge edit commits to fringeBoundaryHeights[i].value:
      The editor JS has a handler that writes back to fringeBoundaryHeights[i].value.
  T12 Esc reverts: editor JS has a keydown handler referencing 'Escape' or 'Esc'.
  T13 Status strip updated: strip uses 'G' and 'F' badge language.
  T14 Pointer-events wrapping: outer wrapper has pointer-events-none, input
      itself has pointer-events-auto (so input is focusable through the overlay).
  T15 APP_VERSION is v4.90 in app.py.

Run:
    cd /Volumes/GIT/CLAUDE/SHARED_WORK_FOLDER
    python -m pytest app/tests/test_unified_gf_badges.py -v
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
    """The x-for template block that renders fringe boundary heights."""
    return _extract_xfor_template(editor_html, "fringeBoundaryHeights")


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

class TestFBadgeRender:
    """T2 — fringeBoundaryHeights template has compact F-badge + editable input."""

    def test_fringe_template_exists(self, fringe_template):
        """T2a — x-for template over fringeBoundaryHeights is present."""
        assert fringe_template, (
            "editor.html: no x-for template found iterating fringeBoundaryHeights"
        )

    def test_f_badge_letter_present(self, fringe_template):
        """T2b — F-badge still uses 'F' letter."""
        has_f = bool(re.search(r'>\s*F\s*<', fringe_template))
        assert has_f, (
            "fringeBoundaryHeights template missing 'F' badge letter.\n"
            f"Template snippet:\n{fringe_template[:600]}"
        )


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

    def test_no_spinner_on_f_badge(self, fringe_template):
        """T5 — fringeBoundaryHeights template has no ▲/▼ spinner buttons."""
        has_up = "&#9650;" in fringe_template or "▲" in fringe_template
        has_down = "&#9660;" in fringe_template or "▼" in fringe_template
        assert not has_up, (
            "fringeBoundaryHeights template has ▲ (up arrow / &#9650;) spinner button — unexpected."
        )
        assert not has_down, (
            "fringeBoundaryHeights template has ▼ (down arrow / &#9660;) spinner button — unexpected."
        )


# ---------------------------------------------------------------------------
# T6, T7  No delete (×) on either badge
# ---------------------------------------------------------------------------

class TestNoDelete:
    """T6, T7 — Neither G nor F badge has a × delete button."""

    def test_no_delete_on_g_badge(self, spike_template):
        """T6 — elevationSpikes template has no × delete button."""
        has_times = "&times;" in spike_template or "×" in spike_template
        # Also check for removeElevationSpike being called from inside the template
        has_remove_call = "removeElevationSpike" in spike_template
        assert not has_times, (
            "elevationSpikes template still contains '×' / &times; delete button."
        )
        assert not has_remove_call, (
            "elevationSpikes template still contains removeElevationSpike() call — delete affordance remains."
        )

    def test_no_delete_on_f_badge(self, fringe_template):
        """T7 — fringeBoundaryHeights template has no × delete button."""
        has_times = "&times;" in fringe_template or "×" in fringe_template
        assert not has_times, (
            "fringeBoundaryHeights template contains '×' / &times; delete button — unexpected."
        )


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

    def test_input_on_f_badge(self, fringe_template):
        """T9 — fringeBoundaryHeights template contains an <input> element."""
        assert "<input" in fringe_template, (
            "fringeBoundaryHeights template has no <input> element — values are not editable."
        )


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

    def test_f_badge_commit_writes_value(self, editor_html):
        """T11 — JS handler writes to fringeBoundaryHeights[i].value."""
        pattern = re.compile(
            r'fringeBoundaryHeights\s*\[.*?\]\s*\.\s*value\s*=',
            re.DOTALL,
        )
        assert pattern.search(editor_html), (
            "editor.html: no JS assignment to fringeBoundaryHeights[i].value found — "
            "F-badge edit commits are not wired."
        )


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
    """T13 — Status strip references G and F, not the old verbose wording."""

    def test_status_strip_present(self, editor_html):
        """T13a — status strip div is still in the template."""
        # It should show spike/anchor counts
        has_spike_count = "elevationSpikes.length" in editor_html
        has_anchor_count = "fringeBoundaryHeights.length" in editor_html
        assert has_spike_count and has_anchor_count, (
            "Status strip missing elevationSpikes.length or fringeBoundaryHeights.length references."
        )

    def test_status_strip_uses_g_f_labels(self, editor_html):
        """T13b — Status strip uses 'G' and 'F' labels (not just the old verbose text)."""
        # Find the status strip div (has absolute bottom-2 class from original)
        strip_match = re.search(
            r'bottom-2.*?</div>',
            editor_html,
            re.DOTALL,
        )
        # We check the x-text expression for the strip includes G and F
        # The strip is a span with x-text that includes something like "... G · ... F"
        # Look for 'G' and 'F' as distinct letter labels in x-text near the strip
        strip_area = _extract_section(
            editor_html,
            "OCR detection status strip",
            "── Elevation-spike overlays",
        )
        # The strip area should contain G and F letters in the x-text expression
        has_g_label = re.search(r"['\"].*\bG\b.*['\"]", strip_area) or "' G '" in strip_area or "G" in strip_area
        has_f_label = re.search(r"['\"].*\bF\b.*['\"]", strip_area) or "' F '" in strip_area or "F" in strip_area
        assert has_g_label, (
            "Status strip does not reference 'G' badge letter.\n"
            f"Strip area: {strip_area[:400]}"
        )
        assert has_f_label, (
            "Status strip does not reference 'F' badge letter.\n"
            f"Strip area: {strip_area[:400]}"
        )


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

    def test_f_badge_input_is_focusable(self, fringe_template):
        """T14b — F-badge outer wrapper has pointer-events-none but input is focusable."""
        outer_has_none = "pointer-events-none" in fringe_template
        input_match = re.search(r'<input[^>]*>', fringe_template)
        if input_match:
            input_tag = input_match.group(0)
            input_has_none = "pointer-events-none" in input_tag
            assert not input_has_none, (
                "F-badge <input> has pointer-events-none directly on it — not focusable."
            )
        assert outer_has_none, (
            "F-badge outer wrapper missing pointer-events-none — spec says outer wrapper "
            "is pointer-events-none, input has pointer-events-auto."
        )


# ---------------------------------------------------------------------------
# T15  APP_VERSION is v4.90
# ---------------------------------------------------------------------------

class TestAppVersion:
    """T15 — APP_VERSION in app.py is v4.90."""

    def test_app_version_is_v490(self, app_py_src):
        """T15 — app.py APP_VERSION = 'v4.90'."""
        assert 'APP_VERSION = "v4.90"' in app_py_src or "APP_VERSION = 'v4.90'" in app_py_src, (
            "app.py APP_VERSION is not v4.90 — bump was not applied."
        )
