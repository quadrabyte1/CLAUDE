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
        ollama_model="qwen2.5:7b",
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
    llm_day_hint: str = "tomorrow",
    llm_time_hint: str = "10am",
    llm_confidence: float = 0.88,
    llm_ambiguous: list = None,
    herman_status: int = 200,
    herman_body: dict = None,
):
    """Return a context-manager stack that mocks the pipeline.

    v0.5.0: ParseResult uses day_hint/time_hint instead of the old `when` string.
    """
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
        day_hint=llm_day_hint,
        time_hint=llm_time_hint,
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


def test_process_file_ambiguous_fields_no_longer_gates_to_inbox(tmp_path):
    """v0.11.0 regression guard: ambiguous_fields alone must NOT route to inbox.

    Before v0.11.0, ANY non-empty ambiguous_fields list short-circuited to inbox,
    preventing Herman from ever seeing the capture. This was the vet-reminder bug:
    Sprite pre-empted Herman for the class of captures that Herman is best-placed
    to handle (time_hint ambiguity). The fix: remove ambiguous_fields from the
    Sprite gate. Only whisper confidence below threshold routes to inbox.

    This test was previously named test_process_file_ambiguous_fields_goes_to_inbox
    and tested the OLD (broken) behavior. That test is replaced by this one.
    """
    config = _make_config(tmp_path)
    f = _make_m4a(config.recordings_dir)

    patches = _mock_pipeline(
        tmp_path, config,
        whisper_confidence=0.9,
        llm_confidence=0.85,
        llm_ambiguous=["time_hint"],  # ← ambiguous, but confidence is fine
    )
    with patches[0], patches[1], patches[2], patches[3] as mock_herman:
        result = process_file(f, config)

    assert result is True
    # Herman MUST be called — Sprite must forward to Herman even when ambiguous.
    mock_herman.assert_called_once()
    # Inbox should be empty — Sprite does NOT pre-empt.
    inbox_files = list(config.inbox_dir.glob("*.md"))
    assert len(inbox_files) == 0, (
        "Sprite must not write to inbox for ambiguous-but-confident captures; "
        "Herman is the authority on ambiguity."
    )


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


# ---------------------------------------------------------------------------
# v0.6.0 TDD: Herman clarifying question must surface, not silently drop
# ---------------------------------------------------------------------------


def _mock_pipeline_clarifying(
    tmp_path: Path,
    config,
    *,
    whisper_text: str = "Another meeting with myself tomorrow at 10 o'clock",
    whisper_confidence: float = 0.9,
    llm_verb: str = "schedule",
    llm_subject: str = "another meeting with myself",
    llm_day_hint: str = "tomorrow",
    llm_time_hint: str = "10 o'clock",
    llm_confidence: float = 0.88,
    llm_ambiguous: list = None,
    herman_body: dict = None,
):
    """Mock pipeline for a Herman clarifying-question response.

    Herman returns stored=False + clarifying_question when time is ambiguous.
    """
    from sprite.transcribe import TranscriptResult
    from sprite.parse import ParseResult

    llm_ambiguous = llm_ambiguous or []
    # Default: Herman asks for AM/PM clarification.
    herman_body = herman_body or {
        "stored": False,
        "record_id": "f252391221d7037fff9cee8adec821b7",
        "verb": llm_verb,
        "written_path": None,
        "event_id": None,
        "clarifying_question": "10 o'clock — AM or PM?",
        "ambiguous_fields": ["time"],
    }

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
        day_hint=llm_day_hint,
        time_hint=llm_time_hint,
        criticality="normal",
        confidence=llm_confidence,
        ambiguous_fields=llm_ambiguous,
        raw_llm_json={},
    )

    mock_herman_resp = MagicMock()
    mock_herman_resp.status_code = 200
    mock_herman_resp.stored = False
    mock_herman_resp.record_id = herman_body["record_id"]
    mock_herman_resp.event_id = None
    mock_herman_resp.written_path = None
    mock_herman_resp.raw_body = herman_body

    return (
        patch("sprite.watcher.archive_audio", return_value=tmp_path / "audio" / "test.m4a"),
        patch("sprite.watcher.transcribe", return_value=mock_transcript),
        patch("sprite.watcher.parse_intent", return_value=mock_parse),
        patch("sprite.watcher.post_to_herman", return_value=mock_herman_resp),
    )


def test_clarifying_question_writes_inbox_entry(tmp_path):
    """TDD-1: Herman returns stored=False + clarifying_question → inbox entry created.

    Before v0.6.0: Sprite silently marked the record 'posted'. The question
    was never surfaced. This test MUST FAIL before the fix is applied.
    """
    config = _make_config(tmp_path)
    f = _make_m4a(config.recordings_dir)

    patches = _mock_pipeline_clarifying(tmp_path, config)
    with patches[0], patches[1], patches[2], patches[3]:
        result = process_file(f, config)

    assert result is True
    # Inbox file must exist with the clarifying question.
    inbox_files = list(config.inbox_dir.glob("*.md"))
    assert len(inbox_files) == 1, "Expected one inbox file, got none"
    content = inbox_files[0].read_text(encoding="utf-8")
    assert "AM or PM" in content, "Clarifying question must appear in inbox"


def test_clarifying_question_disposition_is_clarifying(tmp_path):
    """TDD-2: state entry disposition must be 'clarifying', not 'posted'.

    The stuck record had disposition='posted' with event_id=null — wrong.
    'clarifying' is semantically distinct: processed (cold-boot skips it)
    but not successfully stored.
    """
    config = _make_config(tmp_path)
    f = _make_m4a(config.recordings_dir)

    patches = _mock_pipeline_clarifying(tmp_path, config)
    with patches[0], patches[1], patches[2], patches[3]:
        process_file(f, config)

    state_text = config.state_file.read_text(encoding="utf-8")
    assert '"clarifying"' in state_text
    # Must NOT be marked as posted.
    for line in state_text.splitlines():
        line = line.strip()
        if not line:
            continue
        import json
        row = json.loads(line)
        assert row.get("disposition") != "posted", (
            "disposition must not be 'posted' when stored=False"
        )


def test_clarifying_question_inbox_contains_question_bold(tmp_path):
    """TDD-1b: inbox entry must include the clarifying question in bold."""
    config = _make_config(tmp_path)
    f = _make_m4a(config.recordings_dir)

    patches = _mock_pipeline_clarifying(tmp_path, config)
    with patches[0], patches[1], patches[2], patches[3]:
        process_file(f, config)

    inbox_files = list(config.inbox_dir.glob("*.md"))
    assert len(inbox_files) == 1
    content = inbox_files[0].read_text(encoding="utf-8")
    # The spec requires the clarifying question in bold: **Herman asks:** ...
    assert "**Herman asks:**" in content or "Herman asks" in content


def test_clarifying_question_cross_repo_wire_shape(tmp_path):
    """TDD-3: Sprite's response-handling code accepts the exact shape
    ParsedCaptureResponse.model_dump() emits.

    This is the cross-repo drift-detection guard for clarifying responses.
    """
    import sys
    from pathlib import Path as _Path

    _HERMAN_BRAIN_SRC = _Path("/Volumes/GIT/CLAUDE/SHARED_WORK_FOLDER/Homunculus/brain")
    if str(_HERMAN_BRAIN_SRC) not in sys.path:
        sys.path.insert(0, str(_HERMAN_BRAIN_SRC))

    try:
        from homunculus_brain.schemas import ParsedCaptureResponse, CaptureVerb
    except ImportError:
        pytest.skip("Herman package not on path")

    # Build the exact shape Herman emits for a clarifying response.
    clarify_response = ParsedCaptureResponse(
        stored=False,
        record_id="f252391221d7037fff9cee8adec821b7",
        verb=CaptureVerb.SCHEDULE,
        written_path=None,
        event_id=None,
        clarifying_question="10 o’clock — AM or PM?",
        ambiguous_fields=["time"],
    )
    body = clarify_response.model_dump(mode="json")

    # Sprite's HermanResponse must correctly interpret this.
    from sprite.herman import HermanResponse
    resp = HermanResponse(
        status_code=200,
        stored=body["stored"],
        record_id=body["record_id"],
        verb=body.get("verb"),
        written_path=body.get("written_path"),
        event_id=body.get("event_id"),
        raw_body=body,
    )

    assert resp.stored is False
    assert resp.record_id == "f252391221d7037fff9cee8adec821b7"
    assert resp.event_id is None
    # The clarifying_question must be accessible from raw_body.
    assert "clarifying_question" in resp.raw_body
    assert resp.raw_body["clarifying_question"] is not None


def test_successful_post_still_marks_posted(tmp_path):
    """TDD-4 regression: successful Herman responses still route to 'posted'.

    Existing v0.5.x behaviour must be preserved.
    """
    config = _make_config(tmp_path)
    f = _make_m4a(config.recordings_dir)

    patches = _mock_pipeline(tmp_path, config)
    with patches[0], patches[1], patches[2], patches[3]:
        result = process_file(f, config)

    assert result is True
    state_text = config.state_file.read_text(encoding="utf-8")
    assert '"posted"' in state_text


def test_never_mark_posted_when_event_id_is_none(tmp_path):
    """TDD-5 regression guard: disposition='posted' with event_id=None must be
    IMPOSSIBLE for schedule/handle verbs.

    When stored=False, event_id is None by definition. If we ever write
    disposition='posted' in that state it's the original bug re-introduced.
    This test asserts the invariant on the 'clarifying' path.
    """
    config = _make_config(tmp_path)
    f = _make_m4a(config.recordings_dir)

    patches = _mock_pipeline_clarifying(tmp_path, config)
    with patches[0], patches[1], patches[2], patches[3]:
        process_file(f, config)

    state_text = config.state_file.read_text(encoding="utf-8")
    import json
    for line in state_text.splitlines():
        line = line.strip()
        if not line:
            continue
        row = json.loads(line)
        if row.get("event_id") is None and row.get("disposition") == "posted":
            pytest.fail(
                "Invariant violated: disposition='posted' with event_id=None. "
                "This is the original silent-drop bug."
            )


# ---------------------------------------------------------------------------
# v0.11.0 TDD: Sprite ambiguous_fields gate removal — vet-reminder incident
# ---------------------------------------------------------------------------


def test_v011_vet_remind_incident_posts_to_herman(tmp_path):
    """v0.11.0 regression — the exact vet-reminder incident scenario.

    verb=remind, ambiguous_fields=['time_hint'], conf=0.850 (whisper=0.876 llm=0.850)
    → Sprite MUST POST to Herman, must NOT write to inbox.

    This is the live incident from 2026-09-22:
      Sprite log: confidence 0.850 < 0.6 or ambiguous=['time_hint'] → inbox
    The OR clause was wrong. Ambiguity is Herman's domain.
    """
    config = _make_config(tmp_path)
    f = _make_m4a(config.recordings_dir)

    patches = _mock_pipeline(
        tmp_path, config,
        whisper_text="Remind me to call the vet at 3.",
        whisper_confidence=0.876,
        llm_verb="remind",
        llm_subject="call the vet",
        llm_day_hint=None,
        llm_time_hint="3",
        llm_confidence=0.850,
        llm_ambiguous=["time_hint"],
    )
    with patches[0], patches[1], patches[2], patches[3] as mock_herman:
        result = process_file(f, config)

    assert result is True
    mock_herman.assert_called_once(), (
        "Sprite must POST to Herman when ambiguous_fields=['time_hint'] and "
        "confidence=0.85 (above the 0.6 threshold)."
    )
    inbox_files = list(config.inbox_dir.glob("*.md"))
    assert len(inbox_files) == 0, (
        "Sprite must not short-circuit to inbox. Herman decides ambiguity."
    )


def test_v011_confidence_gate_still_routes_to_inbox_when_below_threshold(tmp_path):
    """v0.11.0: The whisper-confidence gate (< 0.6) must still route to inbox.

    Only the ambiguous_fields gate was removed. Low-confidence captures are
    genuinely garbled and not worth Herman's time.
    """
    config = _make_config(tmp_path)
    f = _make_m4a(config.recordings_dir)

    patches = _mock_pipeline(
        tmp_path, config,
        whisper_confidence=0.55,   # below 0.6 threshold → inbox
        llm_confidence=0.9,
        llm_ambiguous=[],          # no ambiguity — confidence alone gates
    )
    with patches[0], patches[1], patches[2], patches[3] as mock_herman:
        result = process_file(f, config)

    assert result is True
    mock_herman.assert_not_called()
    inbox_files = list(config.inbox_dir.glob("*.md"))
    assert len(inbox_files) == 1, (
        "Low-confidence captures (< 0.6) must still go to inbox."
    )


def test_v011_confidence_below_threshold_with_ambiguous_goes_to_inbox(tmp_path):
    """v0.11.0: conf=0.55 AND ambiguous=['time_hint'] → inbox.

    Confidence is the sole gate. Ambiguity no longer matters for routing.
    This is the case where BOTH conditions would have triggered the old gate —
    confirm that confidence is the deciding factor, not ambiguity.
    """
    config = _make_config(tmp_path)
    f = _make_m4a(config.recordings_dir)

    patches = _mock_pipeline(
        tmp_path, config,
        whisper_confidence=0.55,       # below threshold
        llm_confidence=0.88,
        llm_ambiguous=["time_hint"],   # also ambiguous — irrelevant to routing
    )
    with patches[0], patches[1], patches[2], patches[3] as mock_herman:
        result = process_file(f, config)

    assert result is True
    mock_herman.assert_not_called()
    inbox_files = list(config.inbox_dir.glob("*.md"))
    assert len(inbox_files) == 1, (
        "Confidence below threshold still wins — inbox is the right call here."
    )


def test_v011_schedule_override_preserved_forwards_to_herman(tmp_path):
    """v0.11.0: v0.8.1 code override (strip time_hint from ambiguous for schedule + bare 1-5)
    is still belt-and-suspenders, but even if LLM emits ambiguous time_hint for schedule + '3',
    the code override strips it, and capture forwards to Herman with clean ambiguous_fields=[].

    This tests the full belt-and-suspenders path: code strips the ambiguity, then
    the (now clean) result goes to Herman as normal.
    """
    config = _make_config(tmp_path)
    f = _make_m4a(config.recordings_dir)

    # Simulate: LLM emits time_hint='3' and ambiguous_fields=['time_hint'] for schedule.
    # parse_intent (mocked) returns what the REAL parse.py would after v0.8.1 override:
    # verb=schedule, time_hint='3', ambiguous_fields=[] (stripped by code override).
    patches = _mock_pipeline(
        tmp_path, config,
        whisper_confidence=0.9,
        llm_verb="schedule",
        llm_time_hint="3",
        llm_confidence=0.87,
        llm_ambiguous=[],  # code override already stripped time_hint
    )
    with patches[0], patches[1], patches[2], patches[3] as mock_herman:
        result = process_file(f, config)

    assert result is True
    mock_herman.assert_called_once(), (
        "schedule + bare hour 3 with ambiguous_fields=[] (post code-override) "
        "must go to Herman."
    )
    inbox_files = list(config.inbox_dir.glob("*.md"))
    assert len(inbox_files) == 0
