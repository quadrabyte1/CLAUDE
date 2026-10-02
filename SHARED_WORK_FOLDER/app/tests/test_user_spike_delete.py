"""
test_user_spike_delete.py — Bug→TDD for user-spike delete affordance (task 693, v4.96).

Feature: G-badges where source === "user" get a small × button alongside the
         editable value input.  G-badges where source === "ocr" (default) show
         NO delete button — current behavior preserved for OCR spikes.

Clicking × removes the spike from elevationSpikes[] and fires autosave.
No confirmation dialog.

Tests:

  T1  User spike shows ×: a G-badge with source:"user" renders a delete button
      (identifiable by x-show / conditional binding referencing source === 'user').
  T2  OCR spike has no × at runtime: the × button is guarded by a conditional
      that requires source === 'user' — so OCR spikes won't show it.
  T3  OCR spike with no source field has no × (backward compat): the delete
      button condition uses === "user" (not !== "ocr"), so missing source → "ocr"
      → no button.
  T4  Click × removes spike: editor.html has removeElevationSpike() function
      referenced from within the spike template × button.
  T5  Click × removes only the clicked spike: removeElevationSpike(sIdx) is called
      with the loop index so only that spike is spliced out.
  T6  Delete triggers autosave: removeElevationSpike calls _pendingAutoSave or
      autoSave.
  T7  Regression — all of the following still present:
      T7a spikeEditStart still present
      T7b spikeEditCommit still present
      T7c spikeEditCancel still present
      T7d @keydown.escape.prevent still on spike input
      T7e pointer-events-none still on outer spike wrapper
      T7f elevationSpikes.length still in status strip
      T7g source: 'user' literal still in placement code
      T7h OCR spikes still get source: 'ocr' in detection wiring
      T7i placement mode (spikeMode) still toggles
  T8  APP_VERSION is v4.96 in app.py.
  T9  Editor on-page version string bumped (contains 4.96).

Run:
    cd /Volumes/GIT/CLAUDE/SHARED_WORK_FOLDER
    python -m pytest app/tests/test_user_spike_delete.py -v
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
    pattern = re.compile(
        r'<template[^>]+x-for[^>]+elevationSpikes[^>]*>(.*?)</template>',
        re.DOTALL | re.IGNORECASE,
    )
    m = pattern.search(editor_html)
    return m.group(0) if m else ""


# ---------------------------------------------------------------------------
# T1  User spike shows × (conditional delete button present in template)
# ---------------------------------------------------------------------------

class TestUserSpikeDeleteButton:
    """T1 — spike template contains a × button that is conditionally shown for source='user'."""

    def test_delete_button_element_present(self, spike_template):
        """T1a — spike template has a × (×) or 'x-delete' affordance element."""
        has_times = "&times;" in spike_template or "×" in spike_template
        assert has_times, (
            "spike template has no × / &times; delete button.\n"
            "Add a <button> with &times; inside the elevationSpikes x-for template.\n"
            f"Template: {spike_template[:600]}"
        )

    def test_delete_button_conditioned_on_source_user(self, spike_template):
        """T1b — the × button is conditional on sp.source === 'user' (x-show or x-if)."""
        # We expect either:
        #   x-show="sp.source === 'user'"
        #   x-if="sp.source === 'user'"
        # The condition must target source === "user"
        has_user_condition = re.search(
            r"""(?:x-show|x-if)\s*=\s*["'].*?sp\.source\s*===?\s*['"]user['"].*?["']""",
            spike_template,
        )
        assert has_user_condition, (
            "spike template: × button is not conditionally bound to sp.source === 'user'.\n"
            "Use x-show=\"sp.source === 'user'\" or x-if=\"sp.source === 'user'\" on the × button.\n"
            f"Template snippet: {spike_template[:800]}"
        )


# ---------------------------------------------------------------------------
# T2  OCR spike has no × at runtime (condition is source === 'user', not !source)
# ---------------------------------------------------------------------------

class TestOCRSpikeNoDelete:
    """T2 — × button is guarded by source === 'user'; an 'ocr' spike will never show it."""

    def test_condition_is_equality_to_user_not_inequality_to_ocr(self, spike_template):
        """T2 — condition uses === 'user' not !== 'ocr' or !sp.source so ocr spikes are safe."""
        # A condition like sp.source !== 'ocr' would pass for null/undefined source too.
        # We want strict equality to 'user'.
        # Check that there's no !== 'ocr' condition that could accidentally show
        # the button for novel source values.
        bad_condition = re.search(
            r"""(?:x-show|x-if)\s*=\s*["'].*?sp\.source\s*!==?\s*['"]ocr['"].*?["']""",
            spike_template,
        )
        assert not bad_condition, (
            "spike template: × button uses sp.source !== 'ocr' condition.\n"
            "Use sp.source === 'user' instead — strict equality to 'user' keeps OCR spikes safe."
        )

    def test_no_unconditional_delete(self, spike_template):
        """T2b — the × button is not unconditional (must be inside x-show or x-if block)."""
        # If there's a × in the template, it must be paired with a source condition
        if "&times;" not in spike_template and "×" not in spike_template:
            pytest.skip("No × in template yet — T1 will catch that")
        has_condition = re.search(
            r"""(?:x-show|x-if)\s*=\s*["'].*?source""",
            spike_template,
        )
        assert has_condition, (
            "spike template has × but no x-show/x-if binding on source — "
            "all spikes (including OCR) would show a delete button."
        )


# ---------------------------------------------------------------------------
# T3  Backward compat: no-source spike defaults to ocr → no delete button
# ---------------------------------------------------------------------------

class TestBackwardCompatNoDelete:
    """T3 — spikes without source field load as 'ocr' (per T3 T8) and show no ×."""

    def test_load_project_defaults_source_to_ocr(self, editor_html):
        """T3 — loadProject uses sp.source || 'ocr' so missing-source → 'ocr' → no × shown."""
        has_ocr_default = re.search(
            r"source.*?\|\|.*?['\"]ocr['\"]|['\"]ocr['\"].*?\|\|.*?source",
            editor_html,
        )
        assert has_ocr_default, (
            "editor.html: loadProject does not default missing source to 'ocr'.\n"
            "Without this, a spike with no source field would also lack the user condition,\n"
            "causing the × to potentially appear or behave unexpectedly."
        )

    def test_delete_condition_excludes_null_source(self, spike_template):
        """T3b — condition sp.source === 'user' naturally excludes null/undefined/missing."""
        # This is a logical assertion based on T1b — if T1b passes, T3b is also satisfied.
        # We check that the equality form (not a truthy check) is used.
        has_strict_equality = re.search(
            r"""sp\.source\s*===?\s*['"]user['"]""",
            spike_template,
        )
        assert has_strict_equality, (
            "spike template × condition does not use strict equality to 'user'.\n"
            "sp.source === 'user' is required to exclude null/undefined/missing source."
        )


# ---------------------------------------------------------------------------
# T4  Click × calls removeElevationSpike (function must exist and be wired)
# ---------------------------------------------------------------------------

class TestClickRemovesSpike:
    """T4 — clicking × calls removeElevationSpike(), which is defined in JS."""

    def test_remove_elevation_spike_called_from_template(self, spike_template):
        """T4a — the × button's @click calls removeElevationSpike."""
        has_remove_call = "removeElevationSpike" in spike_template
        assert has_remove_call, (
            "spike template: × button does not call removeElevationSpike.\n"
            "Add @click=\"removeElevationSpike(sIdx)\" to the × button."
        )

    def test_remove_elevation_spike_function_defined(self, editor_html):
        """T4b — removeElevationSpike(idx) function is defined in editor.html JS."""
        has_func = re.search(
            r'removeElevationSpike\s*\(',
            editor_html,
        )
        assert has_func, (
            "editor.html: removeElevationSpike function not found.\n"
            "Define removeElevationSpike(idx) in the Alpine data object."
        )


# ---------------------------------------------------------------------------
# T5  Click × removes only the clicked spike (passes sIdx)
# ---------------------------------------------------------------------------

class TestDeleteRemovesOnlyClickedSpike:
    """T5 — removeElevationSpike is called with sIdx (loop index) so only that spike is removed."""

    def test_remove_called_with_loop_index(self, spike_template):
        """T5 — @click on × passes sIdx to removeElevationSpike."""
        # The call should be removeElevationSpike(sIdx) — the exact loop variable
        has_index_call = re.search(
            r'removeElevationSpike\s*\(\s*sIdx\s*\)',
            spike_template,
        )
        assert has_index_call, (
            "spike template: removeElevationSpike called without sIdx.\n"
            "Must be removeElevationSpike(sIdx) to remove only the clicked spike.\n"
            f"Template: {spike_template[:800]}"
        )

    def test_remove_function_uses_splice(self, editor_html):
        """T5b — removeElevationSpike uses splice(idx, 1) to remove exactly one entry."""
        # Locate the JS function definition by finding 'removeElevationSpike(idx)'
        # (the definition form, not '@click.stop="removeElevationSpike(sIdx)"').
        decl_start = editor_html.find("removeElevationSpike(idx)")
        if decl_start == -1:
            pytest.fail("removeElevationSpike(idx) function definition not found in editor.html")
        # Take a 400-char window from the declaration to capture the function body
        body = editor_html[decl_start: decl_start + 400]
        has_splice = re.search(r'\.splice\s*\(', body)
        assert has_splice, (
            "removeElevationSpike: no splice() call found — function may not remove the entry.\n"
            "Use this.elevationSpikes.splice(idx, 1).\n"
            f"Body searched: {body[:400]}"
        )


# ---------------------------------------------------------------------------
# T6  Delete triggers autosave (_pendingAutoSave fires on remove)
# ---------------------------------------------------------------------------

class TestDeleteTriggersAutosave:
    """T6 — removeElevationSpike fires autosave after removing the spike."""

    def test_remove_function_triggers_autosave(self, editor_html):
        """T6 — removeElevationSpike calls autoSave() or sets _pendingAutoSave."""
        # Find the JS function definition (not the template @click call).
        # Definition looks like: removeElevationSpike(idx) {
        func_start = editor_html.find("removeElevationSpike(idx)")
        if func_start == -1:
            pytest.fail("removeElevationSpike(idx) function definition not found in editor.html")

        # Take a 400-char window starting from the function definition
        window = editor_html[func_start: func_start + 400]
        has_autosave = (
            "autoSave()" in window
            or "_pendingAutoSave" in window
            or "autoSave =" in window
        )
        assert has_autosave, (
            "removeElevationSpike: no autoSave() or _pendingAutoSave found in function body.\n"
            "Deletion must trigger autosave so the EGM reflects the change.\n"
            f"Function window: {window}"
        )


# ---------------------------------------------------------------------------
# T7  Regression: existing behaviors still intact after adding delete affordance
# ---------------------------------------------------------------------------

class TestRegressions:
    """T7 — All pre-existing behaviors survive the delete affordance addition."""

    def test_spike_edit_start_still_present(self, editor_html):
        """T7a — spikeEditStart function still in editor.html."""
        assert "spikeEditStart" in editor_html, "spikeEditStart missing — G-badge edit regression."

    def test_spike_edit_commit_still_present(self, editor_html):
        """T7b — spikeEditCommit function still in editor.html."""
        assert "spikeEditCommit" in editor_html, "spikeEditCommit missing — G-badge edit regression."

    def test_spike_edit_cancel_still_present(self, editor_html):
        """T7c — spikeEditCancel function still in editor.html."""
        assert "spikeEditCancel" in editor_html, "spikeEditCancel missing — G-badge edit regression."

    def test_keydown_escape_still_on_input(self, spike_template):
        """T7d — @keydown.escape.prevent still on the spike input element."""
        has_esc = (
            "@keydown.escape" in spike_template
            or "keydown.escape" in spike_template
        )
        assert has_esc, (
            "G-badge input: @keydown.escape.prevent handler missing — Esc-to-revert regression."
        )

    def test_pointer_events_none_on_wrapper(self, spike_template):
        """T7e — outer spike wrapper still has pointer-events-none."""
        assert "pointer-events-none" in spike_template, (
            "spike template outer wrapper: pointer-events-none missing — drag regression."
        )

    def test_elevation_spikes_length_in_status_strip(self, editor_html):
        """T7f — elevationSpikes.length still referenced in status strip."""
        assert "elevationSpikes.length" in editor_html, (
            "editor.html: status strip no longer references elevationSpikes.length."
        )

    def test_source_user_literal_in_placement_code(self, editor_html):
        """T7g — source: 'user' literal still present in placement logic."""
        has_source_user = (
            "source: 'user'" in editor_html
            or 'source: "user"' in editor_html
        )
        assert has_source_user, (
            "editor.html: source: 'user' literal missing — placement mode regression."
        )

    def test_ocr_source_in_detection_wiring(self, editor_html):
        """T7h — OCR detection still tags spikes with source: 'ocr'."""
        has_source_ocr = (
            "source: 'ocr'" in editor_html
            or "source: \"ocr\"" in editor_html
        )
        assert has_source_ocr, (
            "editor.html: source: 'ocr' literal missing — OCR detection wiring regression."
        )

    def test_spike_mode_toggle_still_present(self, editor_html):
        """T7i — spikeMode toggle (placement mode) still present."""
        assert "spikeMode" in editor_html, (
            "editor.html: spikeMode removed — placement mode regression."
        )

    def test_user_spike_input_still_editable(self, spike_template):
        """T7j — user spike input is still editable (no pointer-events-none on input itself)."""
        input_match = re.search(r'<input[^>]*>', spike_template)
        if not input_match:
            pytest.fail("No <input> in spike template — edit regression.")
        input_tag = input_match.group(0)
        assert "pointer-events-none" not in input_tag, (
            "G-badge <input> has pointer-events-none directly on it — not focusable/editable."
        )

    def test_no_delete_button_fires_from_non_user_action(self, spike_template):
        """T7k — × button has @pointerdown.stop and/or @click.stop to isolate its events."""
        # The × button should prevent propagation so its click doesn't
        # accidentally trigger other canvas events.
        # Extract the <button> element that contains &times;
        if "&times;" not in spike_template and "×" not in spike_template:
            pytest.skip("No × in template yet — T1 will catch that")

        # Find the <button ... > element containing &times;
        btn_match = re.search(
            r'<button[^>]*>(?:[^<]|<(?!button))*?(?:&times;|×)(?:[^<]|<(?!button))*?</button>',
            spike_template,
            re.DOTALL,
        )
        if not btn_match:
            # Fallback: look for @pointerdown.stop anywhere in the template near &times;
            has_stop = "@pointerdown.stop" in spike_template or "@click.stop" in spike_template
            assert has_stop, (
                "× button: no event propagation stop found in spike template.\n"
                "Add @pointerdown.stop to the × button to prevent canvas mousedown from firing."
            )
            return

        btn_html = btn_match.group(0)
        has_stop = (
            "@pointerdown.stop" in btn_html
            or "@click.stop" in btn_html
            or "stopPropagation" in btn_html
            # Also accept the button being inside a @pointerdown.stop parent — check parent element
            or "@pointerdown.stop" in spike_template
        )
        assert has_stop, (
            "× button: no event propagation stop found on the button element.\n"
            "Add @pointerdown.stop to the × button to prevent canvas mousedown from firing.\n"
            f"Button HTML: {btn_html}"
        )


# ---------------------------------------------------------------------------
# T8  APP_VERSION is v4.96
# ---------------------------------------------------------------------------

class TestAppVersion:
    """T8 — APP_VERSION in app.py is v4.96."""

    def test_app_version_is_v496(self, app_py_src):
        """T8 — app.py APP_VERSION = 'v4.96'."""
        assert 'APP_VERSION = "v4.96"' in app_py_src or "APP_VERSION = 'v4.96'" in app_py_src, (
            "app.py APP_VERSION is not v4.96 — version bump not applied."
        )


# ---------------------------------------------------------------------------
# T9  Editor on-page version string bumped to 4.96
# ---------------------------------------------------------------------------

class TestEditorVersion:
    """T9 — editor.html on-page version string mentions 4.96."""

    def test_editor_html_version_string(self, editor_html):
        """T9 — editor.html contains '4.96' in a version comment or badge."""
        assert "4.96" in editor_html, (
            "editor.html: no '4.96' version string found.\n"
            "Bump the on-page version comment (e.g. {# … v4.96 … #}) in editor.html."
        )
