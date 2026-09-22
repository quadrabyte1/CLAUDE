"""Sprite watcher — cold-boot sweep + watchdog event loop.

Portability:
  Uses `watchdog` (pip-installable, cross-platform) instead of FSEvents
  directly. On Linux, `watchdog` falls back to `inotify`. The abstraction
  holds without code changes.

Architecture:
  1. Cold-boot sweep: on startup, scan the recordings directory for any
     .m4a not already in processed.jsonl. Processes in mtime order (oldest
     first) so nothing is silently skipped.
  2. watchdog Observer: watches the recordings directory for CREATE and
     MODIFIED events. Each event is debounced: the file must be mtime-stable
     for DEBOUNCE_SECONDS and larger than MIN_FILE_BYTES before processing.
  3. Pipeline per file:
       icloud.is_mtime_stable → icloud.archive_audio → transcribe →
       parse_intent → (confidence gate) → herman.post OR inbox.append →
       state.mark_processed

Full Disk Access (FDA):
  The group container is TCC-gated. If the directory is unreadable,
  list_m4a_files() returns [] with a clear error log. The watcher does not
  crash-loop — it starts the Observer (which will similarly get empty events)
  and exits the cold-boot sweep cleanly.
"""

from __future__ import annotations

import hashlib
import logging
import os
import signal
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

from watchdog.events import FileCreatedEvent, FileModifiedEvent, FileSystemEventHandler
from watchdog.observers import Observer

from .config import SpriteConfig, load_config
from .herman import HermanError, build_request, post_to_herman
from .icloud import archive_audio, is_icloud_placeholder, is_mtime_stable, list_m4a_files, trigger_icloud_download
from .inbox import append_to_inbox
from .parse import OllamaParseError, OllamaUnreachable, parse_intent
from .state import file_key, is_processed, mark_processed
from .transcribe import WhisperError, transcribe

log = logging.getLogger(__name__)

logging.basicConfig(
    level=os.environ.get("SPRITE_LOG_LEVEL", "INFO"),
    format="%(asctime)s %(levelname)s %(name)s %(message)s",
)


# ---------------------------------------------------------------------------
# Core pipeline
# ---------------------------------------------------------------------------


def _uuid_for(path: Path) -> str:
    """Derive a stable UUID-like string from path + mtime (for archive naming)."""
    mtime = str(path.stat().st_mtime) if path.exists() else "0"
    material = f"{path.name}:{mtime}".encode("utf-8")
    return hashlib.sha256(material).hexdigest()[:32]


def process_file(path: Path, config: SpriteConfig) -> bool:
    """Run the full Sprite pipeline on a single .m4a file.

    Returns True if the file was successfully dispatched (to Herman or inbox),
    False if it was skipped (already processed, too small, not stable) or if
    an unrecoverable error occurred.

    Never raises. All exceptions are caught, logged, and recorded in the
    state log as 'error'.
    """
    # 0. Idempotency check.
    try:
        key = file_key(path)
    except OSError as exc:
        log.warning("process: cannot compute key for %s: %s", path.name, exc)
        return False

    if is_processed(config.state_file, key):
        log.debug("process: %s already processed (key=%s)", path.name, key[:8])
        return False

    # 1. iCloud placeholder: trigger download and skip for now.
    if is_icloud_placeholder(path):
        log.info("process: %s is an iCloud placeholder — triggering download", path.name)
        trigger_icloud_download(path)
        return False

    # 2. Debounce: mtime-stable + size check.
    if not is_mtime_stable(path, config.debounce_seconds, config.min_file_bytes):
        log.debug("process: %s not yet stable, skipping", path.name)
        return False

    log.info("process: starting pipeline for %s", path.name)
    uuid = _uuid_for(path)
    captured_at = datetime.fromtimestamp(path.stat().st_mtime, tz=timezone.utc)

    # 3. Archive audio (copy, never delete original).
    try:
        archived_path = archive_audio(path, config.audio_archive, uuid)
    except Exception as exc:
        log.error("process: archive failed for %s: %s", path.name, exc)
        mark_processed(
            config.state_file, key,
            audio_path=str(path), disposition="error",
            details={"error": f"archive: {exc}"},
        )
        return False

    # 4. Transcribe with whisper.cpp.
    model_path = config.models_dir / "ggml-small.en.bin"
    try:
        transcript_result = transcribe(
            archived_path,
            model_path=model_path,
            transcripts_dir=config.transcripts_dir,
            uuid=uuid,
        )
    except WhisperError as exc:
        log.error("process: transcription failed for %s: %s", path.name, exc)
        mark_processed(
            config.state_file, key,
            audio_path=str(archived_path), disposition="error",
            details={"error": f"whisper: {exc}"},
        )
        return False
    except Exception as exc:
        log.exception("process: unexpected transcription error for %s", path.name)
        mark_processed(
            config.state_file, key,
            audio_path=str(archived_path), disposition="error",
            details={"error": str(exc)},
        )
        return False

    transcript_text = transcript_result.text
    whisper_confidence = transcript_result.confidence
    log.info(
        "process: transcript='%s...' whisper_conf=%.3f",
        transcript_text[:60],
        whisper_confidence,
    )

    # 5. Parse intent via Ollama.
    try:
        parse_result = parse_intent(
            transcript_text,
            ollama_base_url=config.ollama_base_url,
            ollama_model=config.ollama_model,
            timeout=config.ollama_timeout,
            captured_at=captured_at,
        )
    except OllamaUnreachable as exc:
        log.error("process: Ollama unreachable for %s: %s", path.name, exc)
        mark_processed(
            config.state_file, key,
            audio_path=str(archived_path), disposition="error",
            details={"error": f"ollama_unreachable: {exc}"},
        )
        return False
    except OllamaParseError as exc:
        log.error("process: Ollama parse error for %s: %s", path.name, exc)
        mark_processed(
            config.state_file, key,
            audio_path=str(archived_path), disposition="error",
            details={"error": f"ollama_parse: {exc}"},
        )
        return False
    except Exception as exc:
        log.exception("process: unexpected parse error for %s", path.name)
        mark_processed(
            config.state_file, key,
            audio_path=str(archived_path), disposition="error",
            details={"error": str(exc)},
        )
        return False

    # Combine whisper confidence and LLM confidence (take the minimum —
    # a bad transcript contaminates the parse).
    effective_confidence = min(whisper_confidence, parse_result.confidence)
    log.info(
        "process: verb=%s subject='%s' conf=%.3f (whisper=%.3f llm=%.3f) ambiguous=%s",
        parse_result.verb,
        parse_result.subject[:40],
        effective_confidence,
        whisper_confidence,
        parse_result.confidence,
        parse_result.ambiguous_fields,
    )

    # 6. Ambiguity gate: low confidence or ambiguous fields → inbox.
    is_ambiguous = (
        effective_confidence < config.min_confidence
        or bool(parse_result.ambiguous_fields)
        # Avoid verb also routes to inbox per non-goals (M2 scope)
        # keeping avoid out of inbox for now — it's a valid verb with a handler in Herman.
        # Only pure ambiguity gates it.
    )

    if is_ambiguous:
        log.info(
            "process: confidence %.3f < %.1f or ambiguous=%s → inbox",
            effective_confidence,
            config.min_confidence,
            parse_result.ambiguous_fields,
        )
        try:
            inbox_file = append_to_inbox(
                config.inbox_dir,
                captured_at=captured_at,
                transcript=transcript_text,
                verb_hint=parse_result.verb,
                subject_hint=parse_result.subject,
                confidence=effective_confidence,
                ambiguous_fields=parse_result.ambiguous_fields,
                audio_path=str(archived_path),
            )
        except Exception as exc:
            log.error("process: inbox write failed for %s: %s", path.name, exc)
        mark_processed(
            config.state_file, key,
            audio_path=str(archived_path), disposition="inbox",
            details={
                "confidence": effective_confidence,
                "ambiguous_fields": parse_result.ambiguous_fields,
            },
        )
        return True

    # 7. POST to Herman.
    # v0.5.0: ParseResult has day_hint/time_hint instead of a raw `when` string.
    # The rare case where the LLM emitted an explicit ISO-8601 datetime is
    # preserved via raw_llm_json["when"]. Explicit when takes precedence; hints
    # are only sent when no ISO datetime is available (the typical case).
    iso_when: Optional[str] = parse_result.raw_llm_json.get("when") or None
    if iso_when:
        # Validate it's actually parseable before trusting it.
        try:
            from datetime import datetime as _dt
            _dt.fromisoformat(iso_when)
        except (ValueError, TypeError):
            log.warning(
                "process: LLM emitted non-ISO when=%r — ignoring, using hints",
                iso_when,
            )
            iso_when = None

    payload = build_request(
        verb=parse_result.verb,
        subject=parse_result.subject,
        when=iso_when,
        criticality=parse_result.criticality,
        confidence=effective_confidence,
        raw_transcript=transcript_text,
        audio_path=str(archived_path),
        captured_at=captured_at,
        sprite_uuid=uuid,
        day_hint=parse_result.day_hint if not iso_when else None,
        time_hint=parse_result.time_hint if not iso_when else None,
        project=parse_result.project,
    )

    try:
        herman_resp = post_to_herman(
            payload,
            herman_base_url=config.herman_base_url,
            timeout=config.herman_timeout,
        )
    except HermanError as exc:
        log.error("process: Herman POST failed for %s: %s", path.name, exc)
        mark_processed(
            config.state_file, key,
            audio_path=str(archived_path), disposition="error",
            details={"error": f"herman: {exc}"},
        )
        return False

    # v0.6.0: inspect stored field — Herman may return 200 with stored=False
    # when a clarifying question is needed (e.g. "10 o'clock — AM or PM?").
    # NEVER mark as "posted" when stored=False. Route to inbox with the question.
    if not herman_resp.stored:
        clarifying_question = herman_resp.raw_body.get("clarifying_question")
        ambiguous_from_herman = herman_resp.raw_body.get("ambiguous_fields", [])
        log.warning(
            "process: Herman stored=False for %s — clarifying_question=%r ambiguous=%s",
            path.name,
            clarifying_question,
            ambiguous_from_herman,
        )
        try:
            append_to_inbox(
                config.inbox_dir,
                captured_at=captured_at,
                transcript=transcript_text,
                verb_hint=parse_result.verb,
                subject_hint=parse_result.subject,
                confidence=effective_confidence,
                ambiguous_fields=ambiguous_from_herman,
                audio_path=str(archived_path),
                day_hint=parse_result.day_hint,
                time_hint=parse_result.time_hint,
                clarifying_question=clarifying_question,
            )
        except Exception as exc:
            log.error(
                "process: inbox write failed for clarifying response %s: %s",
                path.name, exc,
            )
        mark_processed(
            config.state_file, key,
            audio_path=str(archived_path),
            record_id=herman_resp.record_id,
            disposition="clarifying",
            details={
                "clarifying_question": clarifying_question,
                "ambiguous_fields": ambiguous_from_herman,
                "verb": parse_result.verb,
                "confidence": effective_confidence,
            },
        )
        log.info(
            "process: clarifying — record_id=%s question=%r",
            herman_resp.record_id,
            clarifying_question,
        )
        return True

    mark_processed(
        config.state_file, key,
        audio_path=str(archived_path),
        record_id=herman_resp.record_id,
        disposition="posted",
        details={
            "event_id": herman_resp.event_id,
            "written_path": herman_resp.written_path,
            "verb": parse_result.verb,
            "confidence": effective_confidence,
        },
    )
    log.info(
        "process: done — record_id=%s event_id=%s written_path=%s",
        herman_resp.record_id,
        herman_resp.event_id,
        herman_resp.written_path,
    )
    return True


# ---------------------------------------------------------------------------
# Cold-boot sweep
# ---------------------------------------------------------------------------


def cold_boot_sweep(config: SpriteConfig) -> int:
    """Scan recordings directory for unprocessed .m4a files on startup.

    Returns the count of files dispatched (to Herman or inbox).
    """
    log.info("cold-boot: scanning %s", config.recordings_dir)
    files = list_m4a_files(config.recordings_dir)
    if not files:
        log.info("cold-boot: no .m4a files found (FDA not granted, or folder empty)")
        return 0

    # Sort by mtime (oldest first) to process in recording order.
    files.sort(key=lambda p: p.stat().st_mtime if p.exists() else 0)
    dispatched = 0
    for f in files:
        if process_file(f, config):
            dispatched += 1
    log.info("cold-boot: dispatched %d / %d files", dispatched, len(files))
    return dispatched


# ---------------------------------------------------------------------------
# watchdog event handler
# ---------------------------------------------------------------------------


class _VoiceMemoHandler(FileSystemEventHandler):
    """Watchdog handler that routes new and modified .m4a files into the pipeline."""

    def __init__(self, config: SpriteConfig) -> None:
        super().__init__()
        self._config = config
        # Track pending paths: path → first-seen monotonic time.
        # We don't process immediately; we wait for mtime-stable check.
        self._pending: dict[str, float] = {}

    def on_created(self, event) -> None:
        if not event.is_directory and event.src_path.endswith(".m4a"):
            path = Path(event.src_path)
            self._pending[str(path)] = time.monotonic()
            log.debug("watcher: new file seen: %s", path.name)

    def on_modified(self, event) -> None:
        if not event.is_directory and event.src_path.endswith(".m4a"):
            path = Path(event.src_path)
            self._pending[str(path)] = time.monotonic()

    def drain_pending(self) -> None:
        """Check all pending paths; process those that have been stable long enough."""
        now = time.monotonic()
        ready = [
            p for p, first_seen in list(self._pending.items())
            if now - first_seen >= self._config.debounce_seconds
        ]
        for path_str in ready:
            del self._pending[path_str]
            path = Path(path_str)
            if path.exists():
                process_file(path, self._config)


# ---------------------------------------------------------------------------
# Main entry point
# ---------------------------------------------------------------------------


def main() -> None:
    config = load_config()

    log.info("Sprite watcher v0.9.0 starting")
    log.info("  recordings:  %s", config.recordings_dir)
    log.info("  audio arch:  %s", config.audio_archive)
    log.info("  state file:  %s", config.state_file)
    log.info("  inbox dir:   %s", config.inbox_dir)
    log.info("  herman url:  %s", config.herman_base_url)
    log.info("  ollama url:  %s / %s", config.ollama_base_url, config.ollama_model)

    # Cold-boot sweep.
    cold_boot_sweep(config)

    # Start watchdog Observer.
    handler = _VoiceMemoHandler(config)
    observer = Observer()

    if config.recordings_dir.exists():
        observer.schedule(handler, str(config.recordings_dir), recursive=True)
        log.info("watcher: watching %s", config.recordings_dir)
    else:
        log.error(
            "watcher: recordings directory does not exist: %s\n"
            "Grant Full Disk Access to this process in System Settings → "
            "Privacy & Security → Full Disk Access.",
            config.recordings_dir,
        )

    observer.start()

    # Graceful shutdown on SIGTERM / SIGINT.
    running = True

    def _stop(signum, frame):
        nonlocal running
        log.info("watcher: received signal %d, shutting down", signum)
        running = False

    signal.signal(signal.SIGTERM, _stop)
    signal.signal(signal.SIGINT, _stop)

    try:
        while running:
            handler.drain_pending()
            time.sleep(1.0)
    finally:
        observer.stop()
        observer.join()
        log.info("watcher: stopped")


if __name__ == "__main__":
    main()
