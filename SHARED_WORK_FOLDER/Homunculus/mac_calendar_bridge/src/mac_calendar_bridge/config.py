"""
config.py — Environment-configurable paths and settings for mac_calendar_bridge.

All config is read from environment variables with safe defaults.
No Mac-only assumptions here; paths degrade gracefully on Linux.

v0.1.2: BRIDGE_CALENDAR_ACCOUNT env var removed. Calendar.app has no account
concept in AppleScript; the user creates the "Homunculus" calendar in the iCloud
account manually via Calendar.app UI. The bridge verifies it exists at startup.
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
# Vault path — same convention as Herman / Sprite
# ---------------------------------------------------------------------------

HERMAN_VAULT_PATH: Path = _expand(
    os.environ.get(
        "HERMAN_VAULT_PATH",
        "/Volumes/GIT/CLAUDE/SHARED_WORK_FOLDER/Homunculus/vault",
    )
)

CALENDAR_ROOT: Path = HERMAN_VAULT_PATH / "calendar"

# ---------------------------------------------------------------------------
# Bridge settings
# ---------------------------------------------------------------------------

BRIDGE_CALENDAR_NAME: str = os.environ.get("BRIDGE_CALENDAR_NAME", "Homunculus")

BRIDGE_STATE_FILE: Path = _expand(
    os.environ.get(
        "BRIDGE_STATE_FILE",
        "~/.local/share/mac_calendar_bridge/pushed.jsonl",
    )
)

BRIDGE_LOG_LEVEL: str = os.environ.get("BRIDGE_LOG_LEVEL", "INFO")

BRIDGE_LOG_FILE: str = os.environ.get("BRIDGE_LOG_FILE", "/tmp/mac_calendar_bridge.log")

# ---------------------------------------------------------------------------
# Config dataclass — structured access with from_env() constructor
# ---------------------------------------------------------------------------

@dataclasses.dataclass(frozen=True)
class Config:
    """Immutable snapshot of bridge configuration from the environment."""

    herman_vault_path: Path
    calendar_root: Path
    calendar_name: str
    state_file: Path
    log_level: str
    log_file: str

    @classmethod
    def from_env(cls) -> "Config":
        """Build a Config from the current environment, applying safe defaults."""
        vault = _expand(
            os.environ.get(
                "HERMAN_VAULT_PATH",
                "/Volumes/GIT/CLAUDE/SHARED_WORK_FOLDER/Homunculus/vault",
            )
        )
        return cls(
            herman_vault_path=vault,
            calendar_root=vault / "calendar",
            calendar_name=os.environ.get("BRIDGE_CALENDAR_NAME", "Homunculus"),
            state_file=_expand(
                os.environ.get(
                    "BRIDGE_STATE_FILE",
                    "~/.local/share/mac_calendar_bridge/pushed.jsonl",
                )
            ),
            log_level=os.environ.get("BRIDGE_LOG_LEVEL", "INFO"),
            log_file=os.environ.get("BRIDGE_LOG_FILE", "/tmp/mac_calendar_bridge.log"),
        )


# ---------------------------------------------------------------------------
# Logging setup (called once at import time by watcher.py)
# ---------------------------------------------------------------------------

def configure_logging() -> None:
    """Set up root logger to file + stderr."""
    level = getattr(logging, BRIDGE_LOG_LEVEL.upper(), logging.INFO)
    handlers: list[logging.Handler] = [logging.StreamHandler()]
    try:
        handlers.append(logging.FileHandler(BRIDGE_LOG_FILE))
    except OSError:
        pass  # /tmp might be read-only in certain test environments

    logging.basicConfig(
        level=level,
        format="%(asctime)s %(levelname)-8s [mac_calendar_bridge] %(message)s",
        datefmt="%Y-%m-%dT%H:%M:%S",
        handlers=handlers,
        force=True,
    )
