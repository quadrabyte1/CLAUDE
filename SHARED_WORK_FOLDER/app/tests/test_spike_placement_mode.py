"""
test_spike_placement_mode.py — Bug→TDD for Add Spike placement mode (task 692, v4.95).

Feature: toolbar "Add Spike" button → cursor crosshair → canvas click places a spike
         at that image-pixel position with source="user".

Tests:

  T1  Toolbar button renders: "Add Spike" button (or aria-label) exists in editor toolbar.
  T2  Click button enters placement mode: button has active/pressed state binding and a
      placement-mode flag (spikeMode or similar) in Alpine state.
  T3  Canvas click in placement mode adds a spike:
      a. new entry appended to elevationSpikes
      b. entry has source: "user"
      c. default value = nearest existing spike's mm, or 0 if none
      d. placement mode exits after click
      e. autosave fires (spikeMode false after placement)
  T4  Esc cancels: handleKey has a branch for Escape that clears spike placement mode.
  T5  Click outside green polygon still places: spike placement uses raw canvas→image
      coords without clipping to polygon interior.
  T6  Existing G-badge click does NOT produce a new spike: badge input has
      @pointerdown.stop (or equivalent) to prevent canvas mousedown from firing.
  T7  Schema round-trip: source field is written in autosave serialization,
      and is read back during loadProject with value preserved.
  T8  Backward compat: load EGM where spikes have no source → treated as "ocr".
  T9  Regression: G-badge edit handlers (spikeEditStart/spikeEditCommit/spikeEditCancel)
      still exist in editor.html.
  T10 Status strip still shows elevationSpikes.length (total count — source-agnostic).
  T11 Placement mode hint: status strip or elsewhere shows placement hint text
      (e.g. "Click to place" or "Esc to cancel") while in placement mode.
  T12 APP_VERSION is v4.95 in app.py.

Run:
    cd /Volumes/GIT/CLAUDE/SHARED_WORK_FOLDER
    python -m pytest app/tests/test_spike_placement_mode.py -v
"""
from __future__ import annotations

import re
import sys
from pathlib import Path
import pytest

# T5 (2026-10-03): Add Spike / spikeMode / startSpikePlacement stripped from editor.html.
# All tests in this file are tombstoned until a replacement mechanism ships.
pytestmark = pytest.mark.skip(reason="T5: spikeMode/Add Spike/startSpikePlacement stripped from editor.html")

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
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture(scope="module")
def editor_html() -> str:
    return EDITOR_HTML.read_text(encoding="utf-8")


@pytest.fixture(scope="module")
def app_py_src() -> str:
    return APP_PY.read_text(encoding="utf-8")


def _extract_xfor_template(html: str, iterator_var: str) -> str:
    """Extract the first x-for template block iterating over iterator_var."""
    pattern = re.compile(
        r'<template[^>]+x-for[^>]+' + re.escape(iterator_var) + r'[^>]*>(.*?)</template>',
        re.DOTALL | re.IGNORECASE,
    )
    m = pattern.search(html)
    return m.group(0) if m else ""


@pytest.fixture(scope="module")
def spike_template(editor_html: str) -> str:
    return _extract_xfor_template(editor_html, "elevationSpikes")


# ---------------------------------------------------------------------------
# T1  Toolbar button renders
# ---------------------------------------------------------------------------

class TestToolbarButton:
    """T1 — "Add Spike" button (or aria-labeled equivalent) exists in toolbar."""

    def test_add_spike_button_text_or_label(self, editor_html):
        """T1a — button with text 'Add Spike' or aria-label 'Add Spike' is in editor.html."""
        has_text = re.search(
            r'Add\s+Spike',
            editor_html,
            re.IGNORECASE,
        )
        assert has_text, (
            "editor.html: no 'Add Spike' text or aria-label found in toolbar. "
            "Expected a button labelled 'Add Spike' (or 'Add spike')."
        )

    def test_add_spike_button_is_a_button_element(self, editor_html):
        """T1b — 'Add Spike' appears inside a <button> element."""
        # Look for <button ...>...Add Spike...</button>
        pattern = re.compile(
            r'<button[^>]*>(?:[^<]|<(?!button))*?Add\s+Spike(?:[^<]|<(?!button))*?</button>',
            re.DOTALL | re.IGNORECASE,
        )
        # Also accept aria-label="Add Spike" on a button
        has_button_text = pattern.search(editor_html)
        has_aria = re.search(r'<button[^>]*aria-label\s*=\s*["\']Add Spike["\']', editor_html, re.IGNORECASE)
        assert has_button_text or has_aria, (
            "editor.html: 'Add Spike' does not appear inside a <button> element.\n"
            "Either add the label text or an aria-label='Add Spike' to the button."
        )


# ---------------------------------------------------------------------------
# T2  Click button enters placement mode (Alpine state flag + active class binding)
# ---------------------------------------------------------------------------

class TestPlacementModeState:
    """T2 — Clicking Add Spike sets a placement-mode flag in Alpine state."""

    def test_spike_mode_flag_in_state(self, editor_html):
        """T2a — Alpine data has a spikeMode (or spikePlacementMode / addSpikeMode) boolean."""
        has_flag = (
            "spikeMode" in editor_html
            or "spikePlacementMode" in editor_html
            or "addSpikeMode" in editor_html
        )
        assert has_flag, (
            "editor.html: no placement-mode flag found in Alpine state. "
            "Expected spikeMode / spikePlacementMode / addSpikeMode."
        )

    def test_add_spike_button_has_click_handler(self, editor_html):
        """T2b — Add Spike button has an @click handler that enters placement mode."""
        # The click handler should reference startSpikePlacement / spikeMode / etc.
        # Most natural: @click="startSpikePlacement()" or @click="spikeMode = true"
        has_handler = re.search(
            r'Add\s+Spike.*?@click|@click.*?Add\s+Spike',
            editor_html,
            re.DOTALL | re.IGNORECASE,
        )
        # Also accept: the button that has @click with spike-mode ref
        has_spike_click = re.search(
            r'@click\s*=\s*["\'](?:startSpikePlacement|spikeMode\s*=\s*true|enterSpikeMode)\s*["\']',
            editor_html,
            re.IGNORECASE,
        )
        # Combine: if button text has 'Add Spike' nearby a @click
        btn_block = re.search(
            r'<button[^>]*>.*?Add\s+Spike.*?</button>',
            editor_html,
            re.DOTALL | re.IGNORECASE,
        )
        if btn_block:
            has_click_in_btn = "@click" in btn_block.group(0)
        else:
            has_click_in_btn = False

        assert has_click_in_btn or has_spike_click, (
            "editor.html: Add Spike button has no @click handler that enters placement mode."
        )

    def test_add_spike_button_active_state_binding(self, editor_html):
        """T2c — Add Spike button has a class binding reflecting spikeMode/pressed state."""
        # The button should have :class or x-bind:class or a conditional class for the active state
        # Most natural: :class="spikeMode ? 'ring-2 ...' : '...'"
        has_class_binding = re.search(
            r'spikeMode|spikePlacementMode|addSpikeMode',
            editor_html,
        )
        assert has_class_binding, (
            "editor.html: no placement-mode flag reference found — "
            "button active state binding not wired."
        )


# ---------------------------------------------------------------------------
# T3  Canvas click in placement mode adds a spike
# ---------------------------------------------------------------------------

class TestCanvasClickPlacesSpike:
    """T3 — onMouseDown places a spike when spikeMode is active."""

    def test_on_mouse_down_checks_spike_mode(self, editor_html):
        """T3a — onMouseDown function contains a branch for spike placement mode."""
        # Look for spike-mode conditional inside the onMouseDown function body
        # (between 'onMouseDown' and the next top-level function)
        func_match = re.search(
            r'onMouseDown\s*\(.*?\{(.*?)(?=\n\s{4}[a-zA-Z_$][\w$]*\s*[:(])',
            editor_html,
            re.DOTALL,
        )
        if func_match:
            body = func_match.group(1)
        else:
            # Fall back to scanning the whole file for the pattern
            body = editor_html

        has_spike_branch = (
            "spikeMode" in body
            or "spikePlacementMode" in body
            or "addSpikeMode" in body
        )
        assert has_spike_branch, (
            "editor.html: onMouseDown does not branch on spike placement mode. "
            "When spikeMode is active, a click should add a spike."
        )

    def test_spike_placement_sets_source_user(self, editor_html):
        """T3b — spike created during placement mode carries source: 'user'."""
        # The push call for a user-placed spike must include source:'user'
        has_source_user = (
            "source: 'user'" in editor_html
            or 'source: "user"' in editor_html
        )
        assert has_source_user, (
            "editor.html: no source: 'user' literal found. "
            "User-placed spikes must be tagged with source: 'user'."
        )

    def test_spike_placement_default_mm_nearest_or_zero(self, editor_html):
        """T3c — placement code computes default mm as nearest existing spike or 0."""
        # Look for a pattern that scans elevationSpikes for nearest mm, or falls back to 0
        has_nearest_logic = re.search(
            r'elevationSpikes.*?\.mm|\.mm.*?elevationSpikes',
            editor_html,
            re.DOTALL,
        )
        # Also check for explicit fallback to 0 near placement logic
        has_fallback = re.search(
            r'(?:defaultMm|spikeDefaultMm|nearestMm|defMm)\s*=.*?0',
            editor_html,
        ) or re.search(
            r'\.length\s*[><=!]+\s*0.*?\.mm|\.mm.*?\.length\s*[><=!]+\s*0',
            editor_html,
            re.DOTALL,
        )
        assert has_nearest_logic or has_fallback, (
            "editor.html: placement code does not reference elevationSpikes[].mm for default value. "
            "New user spike mm should default to nearest existing spike's mm, or 0."
        )

    def test_placement_mode_exits_after_click(self, editor_html):
        """T3d — After placing a spike, placement mode flag is set to false."""
        # The handler must clear spikeMode after placing
        has_exit = re.search(
            r'spikeMode\s*=\s*false|spikePlacementMode\s*=\s*false|addSpikeMode\s*=\s*false',
            editor_html,
        )
        assert has_exit, (
            "editor.html: placement mode flag is never set to false. "
            "After placing a spike, spikeMode must be cleared."
        )


# ---------------------------------------------------------------------------
# T4  Esc cancels placement mode
# ---------------------------------------------------------------------------

class TestEscCancels:
    """T4 — Pressing Escape while in placement mode exits without placing a spike."""

    def test_handle_key_clears_spike_mode_on_escape(self, editor_html):
        """T4 — handleKey has an Escape branch that clears the spike-mode flag."""
        # handleKey already handles other Escape cases; it must also handle spikeMode
        # Locate the handleKey function body
        hk_match = re.search(
            r'handleKey\s*\(.*?\{(.*)',
            editor_html,
            re.DOTALL,
        )
        body = hk_match.group(1) if hk_match else editor_html

        # Should have: e.key === 'Escape' (or similar) AND spike mode cleared
        escape_pattern = re.search(r"['\"]Escape['\"]", body)
        spike_clear = re.search(
            r'spikeMode\s*=\s*false|spikePlacementMode\s*=\s*false|addSpikeMode\s*=\s*false',
            body,
        )
        assert escape_pattern and spike_clear, (
            "editor.html handleKey: no Escape branch that clears the spike placement mode flag.\n"
            f"escape_pattern={'found' if escape_pattern else 'MISSING'}; "
            f"spike_clear={'found' if spike_clear else 'MISSING'}"
        )


# ---------------------------------------------------------------------------
# T5  Click outside polygon still places (no polygon-interior guard)
# ---------------------------------------------------------------------------

class TestClickOutsidePolygonPlaces:
    """T5 — Spike placement does NOT guard on polygon interior; any canvas click works."""

    def test_no_polygon_interior_guard_in_placement(self, editor_html):
        """T5 — placement code should NOT call pointInPolygon / isInsideGreen etc."""
        # Find the block of code near source: 'user' push
        # If there's a pointInPolygon check gating the spike push, that's wrong
        # We'll look for the spike push block and ensure no isInsideGreen nearby
        source_user_idx = editor_html.find("source: 'user'")
        if source_user_idx == -1:
            source_user_idx = editor_html.find('source: "user"')

        if source_user_idx == -1:
            pytest.skip("source: 'user' not yet in file — T3b will catch this")

        # Check 200 chars before/after the push for polygon-interior guards
        region = editor_html[max(0, source_user_idx - 200): source_user_idx + 200]
        has_guard = (
            "pointInPolygon" in region
            or "isInsideGreen" in region
            or "insidePolygon" in region
        )
        assert not has_guard, (
            "editor.html: spike placement code has a polygon-interior guard — "
            "exterior placement (fringe use case) would be blocked. Remove the guard."
        )


# ---------------------------------------------------------------------------
# T6  Existing G-badge click does NOT place a new spike
# ---------------------------------------------------------------------------

class TestExistingBadgeClickNoNewSpike:
    """T6 — Clicking an existing G-badge input focuses it; doesn't create a new spike."""

    def test_badge_input_has_pointer_stop(self, spike_template):
        """T6 — G-badge input or its wrapper has @pointerdown.stop to block canvas mousedown."""
        has_stop = (
            "@pointerdown.stop" in spike_template
            or "pointerdown.stop" in spike_template
        )
        assert has_stop, (
            "G-badge spike template: no @pointerdown.stop on input or wrapper. "
            "Without this, clicking an existing badge in placement mode would "
            "fire onMouseDown and create a second spike."
        )


# ---------------------------------------------------------------------------
# T7  Schema round-trip: source field preserved
# ---------------------------------------------------------------------------

class TestSchemaRoundTrip:
    """T7 — elevationSpikes serialization includes the source field."""

    def test_autosave_serializes_source(self, editor_html):
        """T7a — autoSave serialization of elevationSpikes includes sp.source."""
        # Find the autoSave / buildPayload section that maps elevationSpikes
        # There should be a .source or source: sp.source in the mapping
        has_source_in_save = re.search(
            r'elevationSpikes.*?\.map\s*\(.*?source.*?\)',
            editor_html,
            re.DOTALL,
        )
        # Also look for sp.source directly
        has_sp_source = "sp.source" in editor_html

        assert has_source_in_save or has_sp_source, (
            "editor.html: autoSave serialization of elevationSpikes does not include "
            "sp.source — the source field will be lost on save."
        )

    def test_load_project_preserves_source(self, editor_html):
        """T7b — loadProject maps source field when populating elevationSpikes."""
        # Find the Array.isArray(data.elevationSpikes) block in loadProject
        load_match = re.search(
            r'Array\.isArray\(data\.elevationSpikes\).*?\.map\s*\(sp\s*=>\s*\({(.*?)\}\)',
            editor_html,
            re.DOTALL,
        )
        body = load_match.group(1) if load_match else editor_html

        has_source = "source" in body
        assert has_source, (
            "editor.html: loadProject elevationSpikes mapping does not include 'source'. "
            "The field will not survive a load round-trip.\n"
            f"Load map body: {body[:300]}"
        )


# ---------------------------------------------------------------------------
# T8  Backward compat: missing source → "ocr"
# ---------------------------------------------------------------------------

class TestBackwardCompat:
    """T8 — EGMs without source field on spikes default to 'ocr' on load."""

    def test_load_defaults_source_to_ocr(self, editor_html):
        """T8 — loadProject uses sp.source || 'ocr' (or equivalent default)."""
        # Look for the fallback pattern near elevationSpikes mapping
        has_ocr_default = re.search(
            r"source.*?['\"]ocr['\"]|['\"]ocr['\"].*?source",
            editor_html,
        )
        assert has_ocr_default, (
            "editor.html: loadProject does not default missing source to 'ocr'. "
            "Use sp.source || 'ocr' or similar in the elevationSpikes .map()."
        )


# ---------------------------------------------------------------------------
# T9  Regression: existing G-badge edit handlers still present
# ---------------------------------------------------------------------------

class TestRegressionGBadgeEdit:
    """T9 — Existing G-badge inline edit handlers are untouched."""

    def test_spike_edit_start_still_present(self, editor_html):
        """T9a — spikeEditStart function still in editor.html."""
        assert "spikeEditStart" in editor_html, (
            "spikeEditStart missing — G-badge edit regression."
        )

    def test_spike_edit_commit_still_present(self, editor_html):
        """T9b — spikeEditCommit function still in editor.html."""
        assert "spikeEditCommit" in editor_html, (
            "spikeEditCommit missing — G-badge edit regression."
        )

    def test_spike_edit_cancel_still_present(self, editor_html):
        """T9c — spikeEditCancel function still in editor.html."""
        assert "spikeEditCancel" in editor_html, (
            "spikeEditCancel missing — G-badge edit regression."
        )

    def test_esc_revert_still_wired_on_input(self, spike_template):
        """T9d — G-badge input still has @keydown.escape.prevent handler."""
        has_esc = (
            "@keydown.escape" in spike_template
            or "keydown.escape" in spike_template
        )
        assert has_esc, (
            "G-badge input: @keydown.escape.prevent handler missing — "
            "Esc-to-revert regression."
        )


# ---------------------------------------------------------------------------
# T10  Status strip shows total elevationSpikes.length
# ---------------------------------------------------------------------------

class TestStatusStrip:
    """T10 — Status strip still shows elevationSpikes.length (total, source-agnostic)."""

    def test_status_strip_has_length_ref(self, editor_html):
        """T10 — elevationSpikes.length used in status strip."""
        assert "elevationSpikes.length" in editor_html, (
            "editor.html: status strip no longer references elevationSpikes.length."
        )


# ---------------------------------------------------------------------------
# T11  Placement mode hint visible while in placement mode
# ---------------------------------------------------------------------------

class TestPlacementHint:
    """T11 — When spikeMode is active, user sees a placement hint."""

    def test_placement_hint_text_present(self, editor_html):
        """T11 — editor.html contains hint text for placement mode (click to place / Esc)."""
        has_hint = re.search(
            r'Click.*?place.*?spike|place.*?spike.*?Esc|Esc.*?cancel|spike.*?place',
            editor_html,
            re.IGNORECASE | re.DOTALL,
        )
        assert has_hint, (
            "editor.html: no placement-mode hint text found. "
            "Show something like 'Click to place a spike · Esc to cancel' while spikeMode is active."
        )

    def test_hint_is_conditional_on_spike_mode(self, editor_html):
        """T11b — hint visibility is tied to the spikeMode flag (x-show or :class)."""
        # The hint element should have x-show="spikeMode" or similar
        has_conditional = re.search(
            r'x-show\s*=\s*["\'].*?(?:spikeMode|spikePlacementMode|addSpikeMode)',
            editor_html,
        ) or re.search(
            r'(?:spikeMode|spikePlacementMode|addSpikeMode).*?x-show',
            editor_html,
            re.DOTALL,
        )
        assert has_conditional, (
            "editor.html: placement hint is not conditionally shown via x-show bound to spikeMode. "
            "Without x-show, the hint will always be visible."
        )


# ---------------------------------------------------------------------------
# T12  APP_VERSION is v4.95
# ---------------------------------------------------------------------------

class TestAppVersion:
    """T12 — APP_VERSION in app.py is v4.95+ (updated to v4.96 for user-spike delete affordance)."""

    def test_app_version_is_v495(self, app_py_src):
        """T12 — app.py APP_VERSION is v4.95 or later (v4.96 after user-spike delete task)."""
        has_v495 = 'APP_VERSION = "v4.95"' in app_py_src or "APP_VERSION = 'v4.95'" in app_py_src
        has_v496 = 'APP_VERSION = "v4.96"' in app_py_src or "APP_VERSION = 'v4.96'" in app_py_src
        assert has_v495 or has_v496, (
            "app.py APP_VERSION is not v4.95 or v4.96 — version bump not applied."
        )
