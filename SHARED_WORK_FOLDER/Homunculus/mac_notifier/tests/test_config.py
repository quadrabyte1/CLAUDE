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
        env = {k: v for k, v in os.environ.items() if k != "NOTIFIER_GRACE_WINDOW"}
        with mock.patch.dict(os.environ, env, clear=True):
            c = Config.from_env()
        assert c.grace_window == 90

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
