"""
config.py — Environment-configurable settings for mac_notifier.

All config is read from environment variables with safe defaults.
No Mac-only assumptions; paths degrade gracefully on Linux.

Environment variables:
    NOTIFIER_HERMAN_URL      URL base for Herman's API (default: http://localhost:8765)
    NOTIFIER_POLL_INTERVAL   Poll interval in seconds (default: 60)
    NOTIFIER_GRACE_WINDOW    Grace window in seconds for due-row matching (default: 90)
    NOTIFIER_STATE_FILE      Path to fired.jsonl dedup state (default: ~/.local/share/mac_notifier/fired.jsonl)
    NOTIFIER_LOG_LEVEL       Python log level string (default: INFO)
"""

from __future__ import annotations

import dataclasses
import logging
import os
from pathlib import Path


def _expand(path: str) -> Path:
    """Expand ~ and env vars in a path string."""
    return Path(os.path.expandvars(os.path.expanduser(path)))


# ---------------------------------------------------------------------------
# Module-level constants (read once at import time)
# ---------------------------------------------------------------------------

NOTIFIER_HERMAN_URL: str = os.environ.get("NOTIFIER_HERMAN_URL", "http://localhost:8765")

NOTIFIER_POLL_INTERVAL: int = int(os.environ.get("NOTIFIER_POLL_INTERVAL", "60"))

NOTIFIER_GRACE_WINDOW: int = int(os.environ.get("NOTIFIER_GRACE_WINDOW", "90"))

NOTIFIER_STATE_FILE: Path = _expand(
    os.environ.get(
        "NOTIFIER_STATE_FILE",
        "~/.local/share/mac_notifier/fired.jsonl",
    )
)

NOTIFIER_LOG_LEVEL: str = os.environ.get("NOTIFIER_LOG_LEVEL", "INFO")

NOTIFIER_LOG_FILE: str = os.environ.get("NOTIFIER_LOG_FILE", "/tmp/mac_notifier.log")


# ---------------------------------------------------------------------------
# Config dataclass — structured access with from_env() constructor
# ---------------------------------------------------------------------------


@dataclasses.dataclass(frozen=True)
class Config:
    """Immutable snapshot of notifier configuration from the environment."""

    herman_url: str
    poll_interval: int
    grace_window: int
    state_file: Path
    log_level: str
    log_file: str

    @classmethod
    def from_env(cls) -> "Config":
        """Build a Config from the current environment, applying safe defaults."""
        return cls(
            herman_url=os.environ.get("NOTIFIER_HERMAN_URL", "http://localhost:8765"),
            poll_interval=int(os.environ.get("NOTIFIER_POLL_INTERVAL", "60")),
            grace_window=int(os.environ.get("NOTIFIER_GRACE_WINDOW", "90")),
            state_file=_expand(
                os.environ.get(
                    "NOTIFIER_STATE_FILE",
                    "~/.local/share/mac_notifier/fired.jsonl",
                )
            ),
            log_level=os.environ.get("NOTIFIER_LOG_LEVEL", "INFO"),
            log_file=os.environ.get("NOTIFIER_LOG_FILE", "/tmp/mac_notifier.log"),
        )


# ---------------------------------------------------------------------------
# Logging setup (called once at startup by poller.py)
# ---------------------------------------------------------------------------


def configure_logging(log_level: str = NOTIFIER_LOG_LEVEL, log_file: str = NOTIFIER_LOG_FILE) -> None:
    """Set up root logger to file + stderr."""
    level = getattr(logging, log_level.upper(), logging.INFO)
    handlers: list[logging.Handler] = [logging.StreamHandler()]
    try:
        handlers.append(logging.FileHandler(log_file))
    except OSError:
        pass  # /tmp might be read-only in certain test environments

    logging.basicConfig(
        level=level,
        format="%(asctime)s %(levelname)-8s [mac_notifier] %(message)s",
        datefmt="%Y-%m-%dT%H:%M:%S",
        handlers=handlers,
        force=True,
    )
