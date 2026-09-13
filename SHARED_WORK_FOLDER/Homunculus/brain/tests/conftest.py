"""Test-wide fixtures.

v1.3: default the Sprite warnings path into a session-scoped tmp dir so
no test — existing or new — can accidentally touch the user's real
``~/sprite/warnings.md``. Individual tests that want to inspect the
warnings file override ``SPRITE_WARNINGS_PATH`` explicitly.
"""

from __future__ import annotations

import os
import pytest


@pytest.fixture(autouse=True)
def _isolate_sprite_warnings(tmp_path_factory, monkeypatch):
    default = tmp_path_factory.mktemp("sprite_default") / "warnings.md"
    monkeypatch.setenv("SPRITE_WARNINGS_PATH", str(default))
    yield
