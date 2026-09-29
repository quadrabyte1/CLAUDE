"""TDD tests for Herman v2.4.2 — Delete button onclick fix (dashboard v0.7).

Bug: timerBtns() generates an onclick with \\'${esc(project)}\\' which in a
JS template literal evaluates to unescaped single quotes around the project
name, breaking the confirm() call.

Fix: use double-quote delimiters around the project name in the confirm text:
  confirm('Delete timer "${esc(project)}"? This cannot be undone.')

Tests written RED first against v0.6 (broken) code, then turn GREEN after fix.

Coverage:
  D1. Delete onclick DOM value does NOT contain a bare unescaped ' around the
      project name inside the confirm() argument (the core bug regression).
  D2. Delete onclick DOM value CONTAINS the project name in the confirm text.
  D3. Start/Stop onclicks still parse cleanly (no regression).
  D4. Dashboard version is v0.7 after the fix.
  D5. Herman VERSION is 2.4.2 after the fix.

NOTE on apostrophe edge case (D6 — follow-up, not in scope):
  A project name like "Bob's Timer" would still break the JS argument to
  timerAction() because esc() does not encode single quotes. This affects
  Start, Stop, and Delete equally and is a pre-existing issue not introduced
  by this fix. Tracked as a future follow-up.
"""

from __future__ import annotations

import re
from pathlib import Path

import pytest


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _get_dashboard_html(tmp_path: Path, monkeypatch) -> str:
    """Return the raw dashboard HTML string."""
    monkeypatch.setenv("HOMUNCULUS_VAULT", str(tmp_path))
    monkeypatch.setenv("HOMUNCULUS_TZ", "America/New_York")
    monkeypatch.setenv("OLLAMA_BASE_URL", "http://127.0.0.1:1")
    monkeypatch.setenv("SPRITE_WARNINGS_PATH", str(tmp_path / "sprite" / "warnings.md"))
    monkeypatch.setenv("HOMUNCULUS_MIN_CONFIDENCE", "0.6")
    from homunculus_brain.server import create_app
    from fastapi.testclient import TestClient

    with TestClient(create_app()) as client:
        r = client.get("/dashboard/")
        assert r.status_code == 200
        return r.text


def _extract_delete_onclick(html: str) -> str:
    """Extract the onclick attribute value from the Delete button template.

    The timerBtns() function is embedded in the HTML as a JS function.
    We search for the template literal segment that produces the Delete button.
    Returns the raw Python/JS source string for the onclick value.
    """
    # Match the onclick attribute of the Delete button inside the JS function
    # The source looks like:
    #   onclick="if(confirm('Delete timer ...${esc(project)}...')){...}"
    m = re.search(
        r'onclick="(if\(confirm\([^)]+\)\)\{timerAction\([^}]+\);\})"',
        html,
    )
    if m:
        return m.group(1)
    # Broader match: grab everything from onclick=" up to }"
    m2 = re.search(
        r"""onclick="(if\(confirm\(.*?timerAction\('/timer/delete'.*?\);}\))"  """,
        html,
        re.DOTALL,
    )
    if m2:
        return m2.group(1)
    # Just return the entire timerBtns function body for inspection
    return ""


def _extract_timer_btns_source(html: str) -> str:
    """Return the source text of the timerBtns() JS function from the HTML.

    Uses a multiline pattern to grab everything from 'function timerBtns'
    up to the closing brace at column 0 — avoids stopping at the first '}'
    inside the template literal.
    """
    m = re.search(
        r"function timerBtns\(.*?\)(.*?)^\}",
        html,
        re.DOTALL | re.MULTILINE,
    )
    if m:
        return m.group(1)
    return ""


# ---------------------------------------------------------------------------
# D1. Core regression: no stray unescaped single quote around project name
#     inside the confirm() argument of the Delete onclick.
# ---------------------------------------------------------------------------


def test_delete_onclick_confirm_no_bare_single_quote_around_project(
    tmp_path: Path, monkeypatch
):
    """Delete button's confirm text must NOT use unescaped single quotes to wrap
    the project name.

    The bug: the template literal source had \\'${esc(project)}\\'  which in
    JS evaluates to '${esc(project)}'  — producing stray single quotes that
    break confirm().

    The fix: use double-quote delimiters ("${esc(project)}") so the confirm
    argument has no embedded unescaped single quotes around the name.

    We verify the JS source in the served HTML:
    - Must NOT match the pattern  \\'${esc(project)}\\'
      (the broken backslash-single-quote escape)
    - OR the pattern  '${esc(project)}'  appearing inside a JS single-quote
      delimited string (the unescaped version that would break confirm())
    """
    html = _get_dashboard_html(tmp_path, monkeypatch)
    btns_src = _extract_timer_btns_source(html)
    assert btns_src, "Could not locate timerBtns() function in dashboard HTML"

    # The broken pattern: escaped single quotes wrapping the project name
    # In Python source \\' → in JS source \'  (which is the bug)
    broken_pattern = r"\\'${esc(project)}\\'"
    assert broken_pattern not in btns_src, (
        f"Delete onclick still uses the broken \\' escape pattern.\n"
        f"Found in timerBtns source:\n{btns_src}\n\n"
        "Fix: change to use double quotes: \"${{esc(project)}}\" in the confirm text."
    )

    # Also check: the confirm() call's argument must NOT wrap the project name
    # with single quotes.  Specifically, inside the confirm() call we must NOT
    # see  \'${esc(project)}\'  or  '${esc(project)}'  since both produce
    # bare single quotes that break the JS string literal.
    #
    # We extract just the confirm() argument from the Delete button's onclick.
    confirm_match = re.search(
        r"confirm\(('.*?')\)",
        btns_src,
        re.DOTALL,
    )
    assert confirm_match, (
        "Could not find confirm('...') call in Delete button onclick.\n"
        f"timerBtns source:\n{btns_src}"
    )
    confirm_arg = confirm_match.group(1)

    # The confirm argument must not have the pattern  \'${esc(project)}\'
    # (backslash-escaped single quotes wrapping the project name — the original bug)
    assert r"\\'${esc(project)}\\'" not in confirm_arg and \
           r"\'${esc(project)}\'" not in confirm_arg, (
        f"Delete button confirm() still uses backslash-single-quote to wrap project.\n"
        f"confirm arg: {confirm_arg!r}\n"
        "Fix: use double quotes around the project name in confirm text."
    )

    # The confirm argument must not have BARE '${esc(project)}' (unescaped)
    # that would produce a string-breaking literal quote when JS evaluates it.
    # After the fix the project name should be wrapped with " not '.
    assert "'${esc(project)}'" not in confirm_arg, (
        f"Delete button confirm() wraps project name in bare single quotes.\n"
        f"confirm arg: {confirm_arg!r}\n"
        "Fix: use double quotes: confirm('Delete timer \"${{esc(project)}}\"? ...')"
    )


# ---------------------------------------------------------------------------
# D2. Delete onclick must include the project name interpolation in confirm text
# ---------------------------------------------------------------------------


def test_delete_onclick_confirm_includes_project_name(tmp_path: Path, monkeypatch):
    """The Delete button's confirm text must still include ${esc(project)} so
    the user sees the project name in the dialog."""
    html = _get_dashboard_html(tmp_path, monkeypatch)
    btns_src = _extract_timer_btns_source(html)
    assert btns_src, "Could not locate timerBtns() function in dashboard HTML"

    # The confirm() call must include ${esc(project)} somewhere inside it
    assert "${esc(project)}" in btns_src, (
        "Delete onclick confirm() text must include ${esc(project)} so the "
        "user sees the project name in the dialog.\n"
        f"timerBtns source:\n{btns_src}"
    )

    # And the confirm text must mention 'Delete timer' or 'delete'
    assert "Delete timer" in btns_src or "delete" in btns_src.lower(), (
        "Delete button confirm text must reference 'Delete timer'.\n"
        f"timerBtns source:\n{btns_src}"
    )


# ---------------------------------------------------------------------------
# D3. Regression: Start and Stop onclicks are unaffected
# ---------------------------------------------------------------------------


def test_start_stop_onclicks_still_present(tmp_path: Path, monkeypatch):
    """Start and Stop buttons' timerAction calls are still present in timerBtns."""
    html = _get_dashboard_html(tmp_path, monkeypatch)
    btns_src = _extract_timer_btns_source(html)
    assert btns_src, "Could not locate timerBtns() function in dashboard HTML"

    assert "/timer/start" in btns_src, (
        "Start button's timerAction('/timer/start') missing from timerBtns()."
    )
    assert "/timer/stop" in btns_src, (
        "Stop button's timerAction('/timer/stop') missing from timerBtns()."
    )
    assert "/timer/delete" in btns_src, (
        "Delete button's timerAction('/timer/delete') missing from timerBtns()."
    )


def test_start_onclick_no_confirm(tmp_path: Path, monkeypatch):
    """Start button must NOT have a confirm() guard (no double-confirm UX)."""
    html = _get_dashboard_html(tmp_path, monkeypatch)
    btns_src = _extract_timer_btns_source(html)

    # The Start button line should NOT have confirm() — only Delete should
    # Extract the start button line
    start_line_match = re.search(r"tbtn-start.*?onclick=\"([^\"]+)\"", btns_src, re.DOTALL)
    if start_line_match:
        start_onclick = start_line_match.group(1)
        assert "confirm" not in start_onclick, (
            f"Start button should not have a confirm() guard, but got: {start_onclick!r}"
        )


# ---------------------------------------------------------------------------
# D4. Dashboard version must be v0.7 after the fix
# ---------------------------------------------------------------------------


def test_dashboard_version_is_v07(tmp_path: Path, monkeypatch):
    """DASHBOARD_VERSION must be v0.7 after the delete-button fix ships."""
    from homunculus_brain.dashboard import DASHBOARD_VERSION, DASHBOARD_HTML
    assert DASHBOARD_VERSION == "v0.7", (
        f"Expected DASHBOARD_VERSION='v0.7', got {DASHBOARD_VERSION!r}. "
        "Bump DASHBOARD_VERSION in dashboard.py as part of this fix."
    )
    assert "v0.7" in DASHBOARD_HTML, "v0.7 must be baked into DASHBOARD_HTML"


# ---------------------------------------------------------------------------
# D5. Herman VERSION must be >= 2.4.2 after the fix
# v2.5.0 update: version bumped to 2.5.0 for the AM/PM disambiguation feature.
# The delete-button fix shipped in 2.4.2; subsequent versions must be >= that.
# ---------------------------------------------------------------------------


def test_herman_version_is_at_least_242():
    """Herman VERSION must be >= 2.4.2 (delete-button fix baseline).

    v2.5.0 update: VERSION is now 2.5.0 (AM/PM disambiguation feature).
    The delete-button fix is baked in at 2.4.2; this test relaxes to >= 2.4.2.
    """
    from homunculus_brain import VERSION
    major, minor, patch = (int(x) for x in VERSION.split("."))
    assert (major, minor, patch) >= (2, 4, 2), (
        f"Herman VERSION must be >= 2.4.2 (delete-button fix baseline). Got {VERSION!r}."
    )
