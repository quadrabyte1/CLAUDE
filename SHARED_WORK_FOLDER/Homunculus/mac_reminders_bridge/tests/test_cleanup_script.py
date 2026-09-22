"""
test_cleanup_script.py — Tests for scripts/cleanup_existing_reminders.py.

The cleanup script retroactively rewrites Reminders.app reminder bodies to
strip [herman-id:...] sentinels, # headings, *Captured ...* captions, and
blank lines. Tests mock osascript; never invoke real AppleScript.

All tests follow the Bug→TDD discipline: written RED first, then GREEN after
the script is implemented.
"""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path
from unittest.mock import MagicMock, call, patch

import pytest


# ---------------------------------------------------------------------------
# Import the cleanup script as a module (it lives in scripts/, not a package)
# ---------------------------------------------------------------------------

_SCRIPT_PATH = (
    Path(__file__).parent.parent / "scripts" / "cleanup_existing_reminders.py"
)


def _load_cleanup_module():
    """Dynamically import cleanup_existing_reminders.py as 'cleanup'."""
    spec = importlib.util.spec_from_file_location("cleanup", _SCRIPT_PATH)
    module = importlib.util.module_from_spec(spec)
    # Register in sys.modules so patch("cleanup.run_applescript") resolves correctly
    sys.modules["cleanup"] = module
    spec.loader.exec_module(module)
    return module


# Only load if the script file exists (it will exist after TDD green phase)
try:
    cleanup = _load_cleanup_module()
    _SCRIPT_AVAILABLE = True
except (FileNotFoundError, AttributeError):
    _SCRIPT_AVAILABLE = False
    cleanup = None

skip_if_no_script = pytest.mark.skipif(
    not _SCRIPT_AVAILABLE,
    reason="cleanup_existing_reminders.py not yet implemented (TDD: RED phase)",
)


# ---------------------------------------------------------------------------
# Unit tests on clean_body() — pure function, no osascript
# ---------------------------------------------------------------------------

class TestCleanBody:
    """
    clean_body(raw: str) -> str | None

    Returns the cleaned body, or None if the body is already clean (no-op).
    Tests do NOT depend on osascript.
    """

    @pytest.fixture(autouse=True)
    def require_script(self):
        if not _SCRIPT_AVAILABLE:
            pytest.skip("cleanup_existing_reminders.py not yet implemented")

    def test_strips_herman_id_sentinel(self):
        raw = "Do the thing.\n\n[herman-id:test-id]"
        result = cleanup.clean_body(raw)
        assert result is not None
        assert "[herman-id:" not in result

    def test_strips_h1_heading(self):
        raw = "# do the thing\n\nDo the thing."
        result = cleanup.clean_body(raw)
        assert result is not None
        assert "# do the thing" not in result

    def test_strips_italic_captured_caption(self):
        raw = "*Captured 2026-09-22 13:43 UTC via Sprite.*\n\nDo the thing."
        result = cleanup.clean_body(raw)
        assert result is not None
        assert "Captured" not in result

    def test_collapses_blank_lines(self):
        raw = "First.\n\n\n\nSecond."
        result = cleanup.clean_body(raw)
        assert result is not None
        assert "\n\n" not in result

    def test_already_clean_returns_none(self):
        """A body that needs no changes → returns None (no-op signal)."""
        clean = "Remind me to renew the car registration on October 30th at 10 a.m."
        result = cleanup.clean_body(clean)
        assert result is None

    def test_full_vault_body_cleaned_to_utterance(self):
        """Integration: typical Herman vault body → single utterance line."""
        raw = (
            "# renew car registration\n\n"
            "*Captured 2026-09-22 13:43 UTC via Sprite.*\n\n"
            "Remind me to renew the car registration on October 30th at 10 a.m.\n\n"
            "[herman-id:2026-10-30-renew-car-registration]"
        )
        result = cleanup.clean_body(raw)
        expected = "Remind me to renew the car registration on October 30th at 10 a.m."
        assert result == expected

    def test_preserves_utterance_text(self):
        raw = "# heading\n\nThe real utterance text here."
        result = cleanup.clean_body(raw)
        assert result is not None
        assert "The real utterance text here." in result

    def test_no_leading_trailing_whitespace_in_result(self):
        raw = "\n\n# heading\n\nDo the thing.\n\n"
        result = cleanup.clean_body(raw)
        assert result is not None
        assert result == result.strip()


# ---------------------------------------------------------------------------
# Integration tests — enumerate + rewrite via mocked osascript
# ---------------------------------------------------------------------------

class TestCleanupDryRun:
    """
    dry_run=True (default): enumerates dirty reminders and reports them,
    but does NOT call the set-body AppleScript command.
    """

    @pytest.fixture(autouse=True)
    def require_script(self):
        if not _SCRIPT_AVAILABLE:
            pytest.skip("cleanup_existing_reminders.py not yet implemented")

    def _make_mock_run(self, bodies: list[str], names: list[str]):
        """
        Return a side_effect function for run_applescript that:
        - First call (enumerate names): returns comma-separated names
        - Second call (enumerate bodies): returns the bodies for each name
        """
        call_count = [0]

        def side_effect(script, **kwargs):
            call_count[0] += 1
            if "name of every reminder" in script:
                return ", ".join(names)
            if "body of reminder" in script.lower() or "body of every reminder" in script.lower():
                # Return bodies as comma-separated (AppleScript list format)
                return ", ".join(bodies)
            # For individual body queries — match by name in script
            for i, name in enumerate(names):
                if name in script and i < len(bodies):
                    return bodies[i]
            return ""

        return side_effect

    def test_dry_run_returns_count_of_dirty_reminders(self):
        dirty_body = (
            "# heading\n\n"
            "*Captured 2026-09-22 UTC via Sprite.*\n\n"
            "Do the thing.\n\n"
            "[herman-id:x]"
        )
        clean_body = "Already clean."

        with patch(
            "cleanup.run_applescript",
            side_effect=self._make_mock_run(
                bodies=[dirty_body, clean_body],
                names=["task one", "task two"],
            ),
        ):
            changed, total = cleanup.run_cleanup("Homunculus", apply=False)

        assert total == 2
        assert changed == 1

    def test_dry_run_does_not_call_set_body(self):
        dirty_body = "# heading\n\nDo the thing.\n\n[herman-id:x]"

        set_body_calls = []

        def side_effect(script, **kwargs):
            if "set body" in script:
                set_body_calls.append(script)
            if "name of every reminder" in script:
                return "task one"
            return dirty_body

        with patch("cleanup.run_applescript", side_effect=side_effect):
            cleanup.run_cleanup("Homunculus", apply=False)

        assert set_body_calls == [], (
            "dry_run=True must not call 'set body' AppleScript"
        )


class TestCleanupApply:
    """
    apply=True: actually rewrites dirty reminder bodies via AppleScript.
    """

    @pytest.fixture(autouse=True)
    def require_script(self):
        if not _SCRIPT_AVAILABLE:
            pytest.skip("cleanup_existing_reminders.py not yet implemented")

    def test_apply_calls_set_body_for_dirty_reminders(self):
        dirty_body = (
            "# heading\n\n"
            "*Captured 2026-09-22 UTC via Sprite.*\n\n"
            "Do the thing.\n\n"
            "[herman-id:x]"
        )
        set_body_calls = []

        def side_effect(script, **kwargs):
            if "set body" in script:
                set_body_calls.append(script)
                return ""
            if "name of every reminder" in script:
                return "task one"
            return dirty_body

        with patch("cleanup.run_applescript", side_effect=side_effect):
            changed, total = cleanup.run_cleanup("Homunculus", apply=True)

        assert changed == 1
        assert len(set_body_calls) == 1

    def test_apply_does_not_set_body_for_clean_reminders(self):
        clean_body = "Already clean — no heading, no sentinel."
        set_body_calls = []

        def side_effect(script, **kwargs):
            if "set body" in script:
                set_body_calls.append(script)
                return ""
            if "name of every reminder" in script:
                return "task one"
            return clean_body

        with patch("cleanup.run_applescript", side_effect=side_effect):
            changed, total = cleanup.run_cleanup("Homunculus", apply=True)

        assert changed == 0
        assert set_body_calls == []


class TestCleanupIdempotent:
    """
    Running cleanup twice on already-clean reminders must be a no-op.
    """

    @pytest.fixture(autouse=True)
    def require_script(self):
        if not _SCRIPT_AVAILABLE:
            pytest.skip("cleanup_existing_reminders.py not yet implemented")

    def test_second_run_on_clean_reminders_changes_nothing(self):
        """
        Simulate running after --apply has already cleaned everything.
        clean_body() returns None for each reminder → changed == 0.
        """
        already_clean = "Remind me to renew the car registration on October 30th at 10 a.m."

        def side_effect(script, **kwargs):
            if "set body" in script:
                pytest.fail("set body called on already-clean reminder")
            if "name of every reminder" in script:
                return "renew car registration"
            return already_clean

        with patch("cleanup.run_applescript", side_effect=side_effect):
            changed, total = cleanup.run_cleanup("Homunculus", apply=True)

        assert changed == 0
        assert total == 1
