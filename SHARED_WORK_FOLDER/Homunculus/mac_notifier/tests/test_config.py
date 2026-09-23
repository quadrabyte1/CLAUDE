"""
test_config.py — Tests for mac_notifier.config

Covers:
- Default values when no env vars are set
- Env var overrides
- Path expansion (~ expansion)
- Config.from_env() dataclass
- configure_logging() doesn't crash
"""

from __future__ import annotations

import os
from pathlib import Path
from unittest import mock

from mac_notifier.config import Config


# ---------------------------------------------------------------------------
# Tests: Config.from_env() defaults
# ---------------------------------------------------------------------------


class TestConfigDefaults:
    def test_default_herman_url(self):
        with mock.patch.dict(os.environ, {}, clear=False):
            os.environ.pop("NOTIFIER_HERMAN_URL", None)
            c = Config.from_env()
        assert c.herman_url == "http://localhost:8765"

    def test_default_poll_interval(self):
        env = {k: v for k, v in os.environ.items() if k != "NOTIFIER_POLL_INTERVAL"}
        with mock.patch.dict(os.environ, env, clear=True):
            c = Config.from_env()
        assert c.poll_interval == 60

    def test_default_grace_window(self):
        # v0.2.0: default raised from 90 → 300 (5 minutes, per timer_stop incident).
        env = {k: v for k, v in os.environ.items() if k != "NOTIFIER_GRACE_WINDOW"}
        with mock.patch.dict(os.environ, env, clear=True):
            c = Config.from_env()
        assert c.grace_window == 300

    def test_default_log_level(self):
        env = {k: v for k, v in os.environ.items() if k != "NOTIFIER_LOG_LEVEL"}
        with mock.patch.dict(os.environ, env, clear=True):
            c = Config.from_env()
        assert c.log_level == "INFO"

    def test_default_log_file(self):
        env = {k: v for k, v in os.environ.items() if k != "NOTIFIER_LOG_FILE"}
        with mock.patch.dict(os.environ, env, clear=True):
            c = Config.from_env()
        assert c.log_file == "/tmp/mac_notifier.log"

    def test_default_state_file_is_path(self):
        env = {k: v for k, v in os.environ.items() if k != "NOTIFIER_STATE_FILE"}
        with mock.patch.dict(os.environ, env, clear=True):
            c = Config.from_env()
        assert isinstance(c.state_file, Path)
        assert "mac_notifier" in str(c.state_file)
        assert "fired.jsonl" in str(c.state_file)

    def test_default_state_file_tilde_expanded(self):
        env = {k: v for k, v in os.environ.items() if k != "NOTIFIER_STATE_FILE"}
        with mock.patch.dict(os.environ, env, clear=True):
            c = Config.from_env()
        # ~ must be expanded — path should not contain literal tilde
        assert "~" not in str(c.state_file)


# ---------------------------------------------------------------------------
# Tests: Config.from_env() env var overrides
# ---------------------------------------------------------------------------


class TestConfigEnvOverrides:
    def test_override_herman_url(self):
        with mock.patch.dict(os.environ, {"NOTIFIER_HERMAN_URL": "http://10.0.0.1:9000"}):
            c = Config.from_env()
        assert c.herman_url == "http://10.0.0.1:9000"

    def test_override_poll_interval(self):
        with mock.patch.dict(os.environ, {"NOTIFIER_POLL_INTERVAL": "30"}):
            c = Config.from_env()
        assert c.poll_interval == 30

    def test_override_grace_window(self):
        with mock.patch.dict(os.environ, {"NOTIFIER_GRACE_WINDOW": "120"}):
            c = Config.from_env()
        assert c.grace_window == 120

    def test_override_log_level(self):
        with mock.patch.dict(os.environ, {"NOTIFIER_LOG_LEVEL": "DEBUG"}):
            c = Config.from_env()
        assert c.log_level == "DEBUG"

    def test_override_state_file(self):
        with mock.patch.dict(os.environ, {"NOTIFIER_STATE_FILE": "/tmp/test_fired.jsonl"}):
            c = Config.from_env()
        assert c.state_file == Path("/tmp/test_fired.jsonl")

    def test_override_log_file(self):
        with mock.patch.dict(os.environ, {"NOTIFIER_LOG_FILE": "/tmp/test_notifier.log"}):
            c = Config.from_env()
        assert c.log_file == "/tmp/test_notifier.log"


# ---------------------------------------------------------------------------
# Tests: configure_logging doesn't crash
# ---------------------------------------------------------------------------


class TestConfigureLogging:
    def test_configure_logging_no_crash(self):
        """configure_logging should not raise even if log file is /dev/null."""
        from mac_notifier.config import configure_logging
        # Should not raise
        configure_logging(log_level="DEBUG", log_file="/dev/null")

    def test_configure_logging_bad_log_file_no_crash(self):
        """configure_logging silently skips an unwritable log file."""
        from mac_notifier.config import configure_logging
        # Should not raise (OSError is caught internally)
        configure_logging(log_level="INFO", log_file="/nonexistent/path/cant_write.log")


# ---------------------------------------------------------------------------
# Tests: Config is frozen (immutable)
# ---------------------------------------------------------------------------


class TestConfigImmutable:
    def test_config_is_frozen(self):
        import dataclasses
        import pytest
        c = Config.from_env()
        with pytest.raises((dataclasses.FrozenInstanceError, AttributeError)):
            c.poll_interval = 999  # type: ignore[misc]


# ---------------------------------------------------------------------------
# v0.2.0 TDD: Default grace window raised to 300 — timer_stop incident
# ---------------------------------------------------------------------------


class TestGraceWindowV020:
    """v0.2.0 regression suite.

    The timer_stop incident: notifications arriving 99s after fire_at were
    being skipped because the 90s grace window was one second too tight.
    The fix: raise default grace window from 90 → 300 (5 minutes).

    Poll interval is 60s. Any notification can drift by up to one full poll
    cycle (~60s) plus jitter before it's seen. 300s provides comfortable
    headroom without letting genuinely-stale notifications fire.
    """

    def test_default_grace_window_is_300(self):
        """Default NOTIFIER_GRACE_WINDOW must be 300, not 90.

        Regression guard: any future accidental lowering will fail this test.
        This was the timer_stop incident — 99s was 9s past the old 90s limit.
        """
        env = {k: v for k, v in os.environ.items() if k != "NOTIFIER_GRACE_WINDOW"}
        with mock.patch.dict(os.environ, env, clear=True):
            c = Config.from_env()
        assert c.grace_window == 300, (
            f"Default grace_window must be 300 (5 minutes). Got {c.grace_window}. "
            "The timer_stop incident showed 90s is too tight for a 60s poll cycle."
        )

    def test_module_level_constant_is_300(self):
        """The module-level NOTIFIER_GRACE_WINDOW constant must also be 300.

        Both the module-level constant and the Config dataclass default must
        agree. Divergence would be a subtle source of inconsistency.
        """
        import importlib
        import mac_notifier.config as cfg_mod
        # Reload to get the module-level constant without env var influence.
        env = {k: v for k, v in os.environ.items() if k != "NOTIFIER_GRACE_WINDOW"}
        with mock.patch.dict(os.environ, env, clear=True):
            importlib.reload(cfg_mod)
            grace = cfg_mod.NOTIFIER_GRACE_WINDOW
        assert grace == 300, (
            f"Module-level NOTIFIER_GRACE_WINDOW must be 300. Got {grace}."
        )

    def test_env_override_still_works(self):
        """NOTIFIER_GRACE_WINDOW env var override must still apply.

        Backward-compat: operators who set NOTIFIER_GRACE_WINDOW explicitly
        in their plist/env must continue to get their configured value.
        """
        with mock.patch.dict(os.environ, {"NOTIFIER_GRACE_WINDOW": "600"}):
            c = Config.from_env()
        assert c.grace_window == 600, (
            "Env var override must be honored even after default change."
        )

    def test_plist_has_300(self):
        """The deploy plist must specify NOTIFIER_GRACE_WINDOW=300.

        Spec requirement: set the plist explicitly so the launchd environment
        matches the new default. This prevents confusion if an old plist is
        installed alongside a new binary.
        """
        from pathlib import Path as _Path
        plist_path = _Path(
            "/Volumes/GIT/CLAUDE/SHARED_WORK_FOLDER/Homunculus/mac_notifier/"
            "deploy/com.homunculus.mac_notifier.plist"
        )
        assert plist_path.exists(), f"Plist not found at {plist_path}"
        content = plist_path.read_text(encoding="utf-8")
        # The plist must set NOTIFIER_GRACE_WINDOW to 300.
        # Simple text check: the string "300" must appear in a plausible position
        # near the NOTIFIER_GRACE_WINDOW key.
        assert "NOTIFIER_GRACE_WINDOW" in content, "Plist missing NOTIFIER_GRACE_WINDOW key"
        # Check that the value 300 appears after the key.
        key_pos = content.index("NOTIFIER_GRACE_WINDOW")
        value_region = content[key_pos:key_pos + 200]
        assert "300" in value_region, (
            f"Plist NOTIFIER_GRACE_WINDOW must be 300. Nearby text:\n{value_region}"
        )
