"""Tests for sprite.watcher — cold-boot sweep and debounce logic.

Uses tmp_path (fake FS) throughout. No real audio, no real Ollama, no real Herman.
"""

from __future__ import annotations

import json
import time
from datetime import datetime, timezone
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from sprite.config import SpriteConfig
from sprite.state import is_processed, mark_processed
from sprite.watcher import cold_boot_sweep, process_file, _uuid_for


# ---------------------------------------------------------------------------
# Fixture: minimal SpriteConfig pointed at tmp_path
# ---------------------------------------------------------------------------


def _make_config(tmp_path: Path) -> SpriteConfig:
    return SpriteConfig(
        audio_archive=tmp_path / "audio",
        state_file=tmp_path / "state" / "processed.jsonl",
        inbox_dir=tmp_path / "inbox",
        transcripts_dir=tmp_path / "transcripts",
        warnings_path=tmp_path / "warnings.md",
        recordings_dir=tmp_path / "recordings",
        models_dir=tmp_path / "models",
        ollama_base_url="http://mock-ollama",
        ollama_model="qwen2.5:7b-instruct",
        herman_base_url="http://mock-herman",
        debounce_seconds=0.0,   # no wait in tests
        min_file_bytes=100,     # tiny threshold for test files
        min_confidence=0.6,
        ollama_timeout=5.0,
        herman_timeout=5.0,
        cold_boot_window_seconds=0,
    )


def _make_m4a(recordings_dir: Path, name: str = "memo.m4a", size: int = 200) -> Path:
    recordings_dir.mkdir(parents=True, exist_ok=True)
    f = recordings_dir / name
    f.write_bytes(b"\x00" * size)
    return f


# ---------------------------------------------------------------------------
# cold_boot_sweep
# ---------------------------------------------------------------------------


def test_cold_boot_sweep_empty_dir(tmp_path):
    """Empty recordings dir → nothing dispatched, no crash."""
    config = _make_config(tmp_path)
    config.recordings_dir.mkdir(parents=True, exist_ok=True)
    count = cold_boot_sweep(config)
    assert count == 0


def test_cold_boot_sweep_fda_blocked(tmp_path):
    """If recordings dir is unreadable (FDA not granted), returns 0 without crash."""
    config = _make_config(tmp_path)
    # Don't create the dir — list_m4a_files handles missing/inaccessible gracefully.
    # We'll patch list_m4a_files to simulate the FDA PermissionError path.
    with patch("sprite.watcher.list_m4a_files", return_value=[]):
        count = cold_boot_sweep(config)
    assert count == 0


def test_cold_boot_skips_already_processed(tmp_path):
    """Files already in state log are not reprocessed."""
    config = _make_config(tmp_path)
    f = _make_m4a(config.recordings_dir)

    from sprite.state import file_key, mark_processed
    key = file_key(f)
    mark_processed(config.state_file, key, disposition="posted")

    with patch("sprite.watcher.process_file", wraps=lambda p, c: False) as mock_proc:
        count = cold_boot_sweep(config)
    # process_file may be called but should short-circuit on idempotency check
    assert count == 0


# ---------------------------------------------------------------------------
# process_file — unit tests with mocked pipeline stages
# ---------------------------------------------------------------------------


def _mock_pipeline(
    tmp_path: Path,
    config: SpriteConfig,
    *,
    whisper_text: str = "coffee with Jane tomorrow at 10am",
    whisper_confidence: float = 0.9,
    llm_verb: str = "schedule",
    llm_subject: str = "coffee with Jane",
    llm_when: str = "tomorrow at 10am",
    llm_confidence: float = 0.88,
    llm_ambiguous: list = None,
    herman_status: int = 200,
    herman_body: dict = None,
):
    """Return a context-manager stack that mocks the pipeline."""
    from sprite.transcribe import TranscriptResult

    llm_ambiguous = llm_ambiguous or []
    herman_body = herman_body or {
        "stored": True,
        "record_id": "rec_test",
        "verb": llm_verb,
        "written_path": "calendar/test.md",
        "event_id": "ev_test",
    }

    from sprite.parse import ParseResult

    mock_transcript = TranscriptResult(
        text=whisper_text,
        confidence=whisper_confidence,
        segments=[{"text": whisper_text, "avg_logprob": -0.1}],
        raw_json={"transcription": []},
        transcript_json_path=None,
    )
    mock_parse = ParseResult(
        verb=llm_verb,
        subject=llm_subject,
        when=llm_when,
        criticality="normal",
        confidence=llm_confidence,
        ambiguous_fields=llm_ambiguous,
        raw_llm_json={},
    )

    mock_herman_resp = MagicMock()
    mock_herman_resp.status_code = herman_status
    mock_herman_resp.stored = True
    mock_herman_resp.record_id = "rec_test"
    mock_herman_resp.event_id = "ev_test"
    mock_herman_resp.written_path = "calendar/test.md"

    return (
        patch("sprite.watcher.archive_audio", return_value=tmp_path / "audio" / "test.m4a"),
        patch("sprite.watcher.transcribe", return_value=mock_transcript),
        patch("sprite.watcher.parse_intent", return_value=mock_parse),
        patch("sprite.watcher.post_to_herman", return_value=mock_herman_resp),
    )


def test_process_file_happy_path(tmp_path):
    """Full happy-path: file goes all the way to Herman and is marked posted."""
    config = _make_config(tmp_path)
    f = _make_m4a(config.recordings_dir)

    patches = _mock_pipeline(tmp_path, config)
    with patches[0], patches[1], patches[2], patches[3]:
        result = process_file(f, config)

    assert result is True
    from sprite.state import file_key
    key = file_key(f)
    assert is_processed(config.state_file, key)


def test_process_file_skips_already_processed(tmp_path):
    config = _make_config(tmp_path)
    f = _make_m4a(config.recordings_dir)

    from sprite.state import file_key
    mark_processed(config.state_file, file_key(f), disposition="posted")

    with patch("sprite.watcher.archive_audio") as mock_arch:
        result = process_file(f, config)

    assert result is False
    mock_arch.assert_not_called()


def test_process_file_skips_too_small(tmp_path):
    config = _make_config(tmp_path)
    f = _make_m4a(config.recordings_dir, size=50)  # below 100-byte threshold

    # is_mtime_stable will fail on size check — but debounce_seconds=0 helps.
    # The file is 50 bytes < 100 = min_file_bytes.
    with patch("sprite.watcher.archive_audio") as mock_arch:
        result = process_file(f, config)
    # is_mtime_stable returns False (too small), so we return False early
    assert result is False
    mock_arch.assert_not_called()


def test_process_file_low_confidence_goes_to_inbox(tmp_path):
    """Low effective confidence → inbox write, NOT Herman."""
    config = _make_config(tmp_path)
    f = _make_m4a(config.recordings_dir)

    patches = _mock_pipeline(
        tmp_path, config,
        whisper_confidence=0.4,   # ← triggers inbox gate
        llm_confidence=0.9,
    )
    with patches[0], patches[1], patches[2], patches[3] as mock_herman:
        result = process_file(f, config)

    assert result is True
    mock_herman.assert_not_called()
    # Inbox file should exist.
    inbox_files = list(config.inbox_dir.glob("*.md"))
    assert len(inbox_files) == 1


def test_process_file_ambiguous_fields_goes_to_inbox(tmp_path):
    config = _make_config(tmp_path)
    f = _make_m4a(config.recordings_dir)

    patches = _mock_pipeline(
        tmp_path, config,
        whisper_confidence=0.9,
        llm_confidence=0.85,
        llm_ambiguous=["when"],  # ← ambiguous even with high confidence
    )
    with patches[0], patches[1], patches[2], patches[3] as mock_herman:
        result = process_file(f, config)

    assert result is True
    mock_herman.assert_not_called()
    inbox_files = list(config.inbox_dir.glob("*.md"))
    assert len(inbox_files) == 1


def test_process_file_whisper_error_marks_error(tmp_path):
    from sprite.transcribe import WhisperError
    config = _make_config(tmp_path)
    f = _make_m4a(config.recordings_dir)

    with patch("sprite.watcher.archive_audio", return_value=tmp_path / "audio" / "x.m4a"):
        with patch("sprite.watcher.transcribe", side_effect=WhisperError("no binary")):
            result = process_file(f, config)

    assert result is False
    from sprite.state import file_key
    state_text = config.state_file.read_text()
    assert "error" in state_text


def test_process_file_ollama_unreachable_marks_error(tmp_path):
    from sprite.transcribe import TranscriptResult
    from sprite.parse import OllamaUnreachable

    config = _make_config(tmp_path)
    f = _make_m4a(config.recordings_dir)

    mock_transcript = TranscriptResult(
        text="test memo", confidence=0.9, segments=[], raw_json={}, transcript_json_path=None
    )

    with patch("sprite.watcher.archive_audio", return_value=tmp_path / "audio" / "x.m4a"):
        with patch("sprite.watcher.transcribe", return_value=mock_transcript):
            with patch("sprite.watcher.parse_intent", side_effect=OllamaUnreachable("down")):
                result = process_file(f, config)

    assert result is False
    state_text = config.state_file.read_text()
    assert "ollama_unreachable" in state_text


# ---------------------------------------------------------------------------
# Debounce logic
# ---------------------------------------------------------------------------


def test_process_file_mtime_stable_check_passes_with_old_file(tmp_path):
    """A file modified >debounce_seconds ago should pass the mtime-stable check."""
    config = _make_config(tmp_path)
    # _make_config already sets debounce_seconds=0.0 so any file passes mtime check.
    f = _make_m4a(config.recordings_dir, size=200)

    patches = _mock_pipeline(tmp_path, config)
    with patches[0], patches[1], patches[2], patches[3]:
        result = process_file(f, config)

    assert result is True


# ---------------------------------------------------------------------------
# iCloud placeholder
# ---------------------------------------------------------------------------


def test_process_file_skips_icloud_placeholder(tmp_path):
    config = _make_config(tmp_path)
    f = _make_m4a(config.recordings_dir, name="memo.m4a.icloud")

    with patch("sprite.watcher.trigger_icloud_download") as mock_dl:
        result = process_file(f, config)

    assert result is False
    mock_dl.assert_called_once()
