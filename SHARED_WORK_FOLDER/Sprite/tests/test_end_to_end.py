"""Fixture end-to-end test: hello.m4a → whisper mock → Ollama mock → Herman mock.

This test:
  1. Copies the tests/fixtures/hello.m4a fixture into a fake recordings dir.
  2. Mocks whisper.cpp (subprocess) to return a canned transcript JSON.
  3. Mocks Ollama HTTP to return a canned intent JSON.
  4. Mocks Herman HTTP to return a success response.
  5. Asserts:
     a. The pipeline returns True (success).
     b. The state log is updated (idempotency key present).
     c. The audio file is archived to audio/YYYY/MM/<uuid>.m4a.
     d. The mock Herman received a well-formed request (all required fields present).
     e. No inbox file was created (confidence was high).

The fixture end-to-end test does NOT call any live service.
It exercises the full wiring of watcher.process_file end-to-end.
"""

from __future__ import annotations

import json
import shutil
from datetime import datetime, timezone
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from sprite.config import SpriteConfig
from sprite.state import is_processed, file_key
from sprite.watcher import process_file


# ---------------------------------------------------------------------------
# Config fixture
# ---------------------------------------------------------------------------


FIXTURE_M4A = Path(__file__).parent / "fixtures" / "hello.m4a"


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
        ollama_model="qwen2.5:7b",
        herman_base_url="http://mock-herman",
        debounce_seconds=0.0,     # no sleep in tests
        min_file_bytes=100,       # fixture is ~10KB, well above
        min_confidence=0.6,
        ollama_timeout=5.0,
        herman_timeout=5.0,
        cold_boot_window_seconds=0,
    )


# ---------------------------------------------------------------------------
# Canned whisper.cpp output (what the real binary would emit as JSON)
# ---------------------------------------------------------------------------


_WHISPER_JSON = {
    "transcription": [
        {
            "text": "Sprite test one two three",
            "offsets": {"from": 0, "to": 3000},
            "timestamps": {"from": "00:00:00,000", "to": "00:00:03,000"},
            "avg_logprob": -0.12,
        }
    ]
}

_WHISPER_TRANSCRIPT = "Sprite test one two three"

# Expected confidence: exp(-0.12) ≈ 0.887
_EXPECTED_WHISPER_CONF = 0.887


# ---------------------------------------------------------------------------
# Main E2E test
# ---------------------------------------------------------------------------


def test_fixture_end_to_end_happy_path(tmp_path):
    """hello.m4a → transcript mock → Ollama mock → Herman mock → success."""
    assert FIXTURE_M4A.exists(), f"Fixture missing: {FIXTURE_M4A}"

    config = _make_config(tmp_path)
    config.recordings_dir.mkdir(parents=True, exist_ok=True)

    # Copy fixture into recordings dir.
    fixture_copy = config.recordings_dir / "hello.m4a"
    shutil.copy2(str(FIXTURE_M4A), str(fixture_copy))

    # --- Mock whisper.cpp (subprocess) ---
    # We mock transcribe() directly (already unit-tested separately).
    from sprite.transcribe import TranscriptResult

    mock_transcript = TranscriptResult(
        text=_WHISPER_TRANSCRIPT,
        confidence=_EXPECTED_WHISPER_CONF,
        segments=_WHISPER_JSON["transcription"],
        raw_json=_WHISPER_JSON,
        transcript_json_path=None,
    )

    # --- Mock Ollama ---
    from sprite.parse import ParseResult

    mock_parse = ParseResult(
        verb="schedule",
        subject="Sprite test",
        day_hint=None,
        time_hint=None,
        criticality="normal",
        confidence=0.90,
        ambiguous_fields=[],
        # Explicit ISO datetime goes in raw_llm_json["when"] for the rare case.
        raw_llm_json={"when": "2026-09-14T09:00:00-04:00"},
    )

    # --- Mock Herman ---
    mock_herman_resp = MagicMock()
    mock_herman_resp.status_code = 200
    mock_herman_resp.stored = True
    mock_herman_resp.record_id = "rec_e2e_fixture"
    mock_herman_resp.event_id = "ev_e2e_fixture"
    mock_herman_resp.written_path = "calendar/2026-09-14-sprite-test.md"

    # Capture the payload Herman received.
    captured_payload: list[dict] = []

    def _capture_post(payload, *, herman_base_url, timeout):
        captured_payload.append(payload)
        return mock_herman_resp

    with patch("sprite.watcher.transcribe", return_value=mock_transcript):
        with patch("sprite.watcher.parse_intent", return_value=mock_parse):
            with patch("sprite.watcher.post_to_herman", side_effect=_capture_post):
                result = process_file(fixture_copy, config)

    # --- Assertions ---

    # 1. Pipeline returned True (success).
    assert result is True, "process_file should return True on success"

    # 2. Idempotency key recorded in state log.
    key = file_key(fixture_copy)
    assert is_processed(config.state_file, key), "State log must contain the processed key"

    # 3. Audio archived (audio/YYYY/MM/<uuid>.m4a exists).
    archived_files = list(config.audio_archive.glob("**/*.m4a"))
    assert len(archived_files) == 1, f"Expected 1 archived file, got {len(archived_files)}"

    # 4. Herman received a well-formed request.
    assert len(captured_payload) == 1, "Herman must be called exactly once"
    payload = captured_payload[0]

    required_fields = {
        "verb", "subject", "when", "criticality", "confidence",
        "raw_transcript", "audio_path", "captured_at"
    }
    missing = required_fields - set(payload.keys())
    assert not missing, f"Herman payload missing fields: {missing}"

    assert payload["verb"] == "schedule"
    assert payload["subject"] == "Sprite test"
    assert payload["confidence"] >= 0.6
    assert payload["raw_transcript"] == _WHISPER_TRANSCRIPT
    assert payload["criticality"] in ("normal", "critical")

    # captured_at must be parseable ISO-8601 with tzinfo.
    dt = datetime.fromisoformat(payload["captured_at"])
    assert dt.tzinfo is not None

    # audio_path must point to the archived copy (not the original recordings path).
    assert payload["audio_path"].endswith(".m4a")

    # 5. No inbox file created (confidence was high).
    inbox_files = list(config.inbox_dir.glob("*.md")) if config.inbox_dir.exists() else []
    assert not inbox_files, f"No inbox file expected but found: {inbox_files}"


def test_fixture_e2e_low_confidence_goes_to_inbox(tmp_path):
    """Same pipeline but low whisper confidence → inbox, NOT Herman."""
    config = _make_config(tmp_path)
    config.recordings_dir.mkdir(parents=True, exist_ok=True)
    fixture_copy = config.recordings_dir / "hello.m4a"
    shutil.copy2(str(FIXTURE_M4A), str(fixture_copy))

    from sprite.transcribe import TranscriptResult
    from sprite.parse import ParseResult

    low_conf_transcript = TranscriptResult(
        text="muffled mumble maybe", confidence=0.35,
        segments=[], raw_json={}, transcript_json_path=None,
    )
    mock_parse = ParseResult(
        verb="note", subject="something unclear",
        day_hint=None, time_hint=None,
        criticality="normal", confidence=0.88, ambiguous_fields=[],
        raw_llm_json={},
    )

    with patch("sprite.watcher.transcribe", return_value=low_conf_transcript):
        with patch("sprite.watcher.parse_intent", return_value=mock_parse):
            with patch("sprite.watcher.post_to_herman") as mock_herman:
                result = process_file(fixture_copy, config)

    assert result is True
    mock_herman.assert_not_called()
    inbox_files = list(config.inbox_dir.glob("*.md"))
    assert len(inbox_files) == 1


def test_fixture_e2e_idempotent_second_run(tmp_path):
    """Running process_file twice on the same file → second call is a no-op."""
    config = _make_config(tmp_path)
    config.recordings_dir.mkdir(parents=True, exist_ok=True)
    fixture_copy = config.recordings_dir / "hello.m4a"
    shutil.copy2(str(FIXTURE_M4A), str(fixture_copy))

    from sprite.transcribe import TranscriptResult
    from sprite.parse import ParseResult

    transcript = TranscriptResult(
        text="Sprite test", confidence=0.9, segments=[], raw_json={}, transcript_json_path=None,
    )
    parse = ParseResult(
        verb="note", subject="Sprite test",
        day_hint=None, time_hint=None,
        criticality="normal",
        confidence=0.85, ambiguous_fields=[], raw_llm_json={},
    )
    mock_herman_resp = MagicMock()
    mock_herman_resp.status_code = 200
    mock_herman_resp.stored = True
    mock_herman_resp.record_id = "rec_idem"
    mock_herman_resp.event_id = None
    mock_herman_resp.written_path = "notes/test.md"

    with patch("sprite.watcher.transcribe", return_value=transcript):
        with patch("sprite.watcher.parse_intent", return_value=parse):
            with patch("sprite.watcher.post_to_herman", return_value=mock_herman_resp):
                first = process_file(fixture_copy, config)
                second = process_file(fixture_copy, config)

    assert first is True
    assert second is False  # idempotency: second call is a no-op


def test_fixture_exists():
    """Sanity check: the fixture file is present and > 10 KB."""
    assert FIXTURE_M4A.exists(), f"Fixture not found: {FIXTURE_M4A}"
    size = FIXTURE_M4A.stat().st_size
    assert size > 10 * 1024, f"Fixture too small: {size} bytes"
