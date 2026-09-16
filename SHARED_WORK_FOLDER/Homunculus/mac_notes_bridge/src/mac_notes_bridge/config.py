"""
config.py — Environment-configurable paths and settings for mac_notes_bridge.

All config is read from environment variables with safe defaults.
No Mac-only assumptions here; paths degrade gracefully on Linux.

Design notes:
- BRIDGE_FOLDER_NAME is the Notes.app folder (default "Homunculus").
  The user creates it manually under iCloud in Notes.app UI.
- BRIDGE_NOTES_ACCOUNT is the Notes.app account (default "iCloud").
  Configurable via env var if the user uses a different account name.
  The bridge will try account-scoped access first; if the AppleScript
  rejects "tell account ...", see verify_folder_exists() fallback docs.
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
# Vault path — same convention as Herman / mac_calendar_bridge
# ---------------------------------------------------------------------------

HERMAN_VAULT_PATH: Path = _expand(
    os.environ.get(
        "HERMAN_VAULT_PATH",
        "/Volumes/GIT/CLAUDE/SHARED_WORK_FOLDER/Homunculus/vault",
    )
)

NOTES_ROOT: Path = HERMAN_VAULT_PATH / "notes"

# ---------------------------------------------------------------------------
# Bridge settings
# ---------------------------------------------------------------------------

BRIDGE_FOLDER_NAME: str = os.environ.get("BRIDGE_FOLDER_NAME", "Homunculus")

# Notes.app account name for the target folder.
# Default is "iCloud". Override if the user's Notes account is named differently.
BRIDGE_NOTES_ACCOUNT: str = os.environ.get("BRIDGE_NOTES_ACCOUNT", "iCloud")

BRIDGE_STATE_FILE: Path = _expand(
    os.environ.get(
        "BRIDGE_STATE_FILE",
        "~/.local/share/mac_notes_bridge/pushed.jsonl",
    )
)

BRIDGE_LOG_LEVEL: str = os.environ.get("BRIDGE_LOG_LEVEL", "INFO")

BRIDGE_LOG_FILE: str = os.environ.get("BRIDGE_LOG_FILE", "/tmp/mac_notes_bridge.log")


# ---------------------------------------------------------------------------
# Config dataclass — structured access with from_env() constructor
# ---------------------------------------------------------------------------

@dataclasses.dataclass(frozen=True)
class Config:
    """Immutable snapshot of bridge configuration from the environment."""

    herman_vault_path: Path
    notes_root: Path
    folder_name: str
    notes_account: str
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
            notes_root=vault / "notes",
            folder_name=os.environ.get("BRIDGE_FOLDER_NAME", "Homunculus"),
            notes_account=os.environ.get("BRIDGE_NOTES_ACCOUNT", "iCloud"),
            state_file=_expand(
                os.environ.get(
                    "BRIDGE_STATE_FILE",
                    "~/.local/share/mac_notes_bridge/pushed.jsonl",
                )
            ),
            log_level=os.environ.get("BRIDGE_LOG_LEVEL", "INFO"),
            log_file=os.environ.get("BRIDGE_LOG_FILE", "/tmp/mac_notes_bridge.log"),
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
        format="%(asctime)s %(levelname)-8s [mac_notes_bridge] %(message)s",
        datefmt="%Y-%m-%dT%H:%M:%S",
        handlers=handlers,
        force=True,
    )
