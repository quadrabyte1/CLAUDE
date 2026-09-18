"""Sprite → Herman parsed-capture pipeline (v1.6).

Sprite (the on-device watcher that turns .m4a voice memos into structured
records) POSTs each parsed record to ``/capture/parsed``. Herman decides
where it lands based on the five verbs:

    schedule → calendar event (vault/calendar/) with the full reminder chain
    note     → timestamped markdown in the vault's notes folder
    handle   → reminder markdown in vault/reminders/ with strike chain
    remind   → synonym for handle; preferred for "remind me…" phrasing
    avoid    → append to ``sprite/warnings.md`` (surfaced in morning summary)

v1.6 changes:
  - handle / remind now write to vault/reminders/<event-id>.md instead of
    vault/calendar/.  vault/calendar/ remains for schedule events only.
  - Title no longer carries [handle] / [handle!] prefix — the vault/reminders/
    directory is itself the semantic signal.  criticality is expressed via
    a frontmatter tag ``criticality: critical``.
  - verb=remind is accepted as a full synonym for verb=handle; both route to
    _handle_handle().  The original verb value is preserved in the response.

Design notes:

* **Provenance is preserved** — every stored record carries the source
  ``.m4a`` path in the frontmatter / activity log so we can rehydrate the
  original audio months later.
* **Idempotency is deterministic** — ``verb + subject + when + captured_at``
  hashes to a stable ``record_id``. Herman keeps a small JSONL sidecar at
  ``vault/_capture_idempotency.jsonl`` mapping keys to prior outputs, so
  a re-POSTed record short-circuits with the same response.
* **Warnings live outside the vault by default** — the ``avoid`` path
  writes to ``~/sprite/warnings.md`` (or ``$SPRITE_WARNINGS_PATH``) so
  Sprite and Herman share the same file. The morning summary reads it
  back verbatim (last-N lines).
* **Low-confidence records are rejected defensively** — Sprite drops them
  into a client-side inbox, but Herman still validates the floor. Records
  below ``min_capture_confidence`` return 422 without touching the vault.
"""

from __future__ import annotations

import hashlib
import json
import logging
import os
from datetime import datetime, time, timedelta
from pathlib import Path
from typing import Any, Optional
from zoneinfo import ZoneInfo

from . import activity_log
from . import calendar as cal
from . import date_resolver
from . import reminders as rem
from . import vault
from .config import Config
from .schemas import (
    CaptureCriticality,
    CaptureVerb,
    ParsedCaptureRequest,
    ParsedCaptureResponse,
)


log = logging.getLogger(__name__)


_IDEMPOTENCY_FILENAME = "_capture_idempotency.jsonl"
_WARNINGS_HEADER = "# Sprite standing warnings\n\nOne line per warning — appended by the brain's /capture/parsed avoid handler.\n\n"
_NOTES_DIRNAME = "notes"
_REMINDERS_DIRNAME = "reminders"  # vault/reminders/ — markdown files for handle/remind captures


# ---------------------------------------------------------------------------
# Public entry point
# ---------------------------------------------------------------------------


def dispatch(
    req: ParsedCaptureRequest,
    *,
    config: Config,
    tz: ZoneInfo,
) -> ParsedCaptureResponse:
    """Handle a single parsed capture. Idempotent by design.

    Returns a ``ParsedCaptureResponse`` with the stable record id and,
    when applicable, the written path or event id.

    Assumes the caller has already enforced the min-confidence floor. See
    ``below_floor`` for the check FastAPI runs before this dispatch.
    """
    record_id = compute_record_id(req)

    # Idempotency short-circuit: if we've stored this exact record before,
    # return the same response without touching downstream state.
    prior = _lookup_prior(config.vault_path, record_id)
    if prior is not None:
        log.info("capture/parsed idempotent replay for record_id=%s", record_id)
        return ParsedCaptureResponse(**prior)

    if req.verb is CaptureVerb.SCHEDULE:
        resp = _handle_schedule(req, config=config, tz=tz, record_id=record_id)
    elif req.verb is CaptureVerb.NOTE:
        resp = _handle_note(req, config=config, tz=tz, record_id=record_id)
    elif req.verb in (CaptureVerb.HANDLE, CaptureVerb.REMIND):
        # remind is a full synonym for handle — both write to vault/reminders/.
        # The original verb value is preserved in req.verb and returned in the
        # response; we never rewrite remind → handle or vice versa.
        resp = _handle_handle(req, config=config, tz=tz, record_id=record_id)
    elif req.verb is CaptureVerb.AVOID:
        resp = _handle_avoid(req, config=config, tz=tz, record_id=record_id)
    else:  # pragma: no cover — enum guarantees no other branch
        raise ValueError(f"unhandled verb: {req.verb!r}")

    # Clarification responses (stored=False due to ambiguous hints) must NOT
    # be recorded in the idempotency log or the activity log — the request
    # was not committed. The client retries with a clarified payload, which
    # will get a different record_id and proceed normally.
    if not resp.stored:
        log.info(
            "capture/parsed needs clarification for record_id=%s: %s",
            record_id,
            resp.clarifying_question,
        )
        return resp

    _record_stored(config.vault_path, record_id, resp)
    activity_log.log(
        config.vault_path,
        "capture_parsed",
        at=req.captured_at,
        event_id=resp.event_id,
        raw_text=req.raw_transcript,
        details={
            "verb": req.verb.value,
            "subject": req.subject,
            "criticality": req.criticality.value,
            "confidence": req.confidence,
            "audio_path": req.audio_path,
            "record_id": record_id,
            "written_path": resp.written_path,
        },
    )
    return resp


def below_floor(req: ParsedCaptureRequest, *, config: Config) -> bool:
    """Return True if the request's confidence is under the configured floor."""
    return req.confidence < config.min_capture_confidence


# ---------------------------------------------------------------------------
# Idempotency
# ---------------------------------------------------------------------------


def compute_record_id(req: ParsedCaptureRequest) -> str:
    """Stable id derived from ``verb + subject + when/hints + captured_at``.

    Deliberately does NOT include the raw transcript or audio path — the
    same intent captured from two takes of the same memo (same when,
    same subject, same verb) is the same record. Audio path is provenance,
    not identity.

    When ``when`` is None, the day_hint+time_hint are included in the key
    so that two records with different hints (e.g. "thursday 9am" vs
    "friday 2pm") hash to different ids even when other fields match.
    """
    if req.when is not None:
        when_part = req.when.isoformat()
    else:
        # Use hints as the temporal identity when no resolved datetime is given.
        day = (req.day_hint or "").strip().lower()
        time = (req.time_hint or "").strip().lower()
        when_part = f"hint:{day}@{time}"
    material = "|".join(
        [
            req.verb.value,
            req.subject.strip().lower(),
            when_part,
            req.captured_at.isoformat(),
        ]
    ).encode("utf-8")
    return hashlib.sha256(material).hexdigest()[:32]


def _idempotency_path(vault_path: Path) -> Path:
    return vault_path / _IDEMPOTENCY_FILENAME


def _lookup_prior(vault_path: Path, record_id: str) -> Optional[dict[str, Any]]:
    path = _idempotency_path(vault_path)
    if not path.exists():
        return None
    # File is small (one line per accepted capture); scan bottom-up so
    # recent replays are O(1) in practice.
    with path.open("r", encoding="utf-8") as f:
        lines = f.readlines()
    for line in reversed(lines):
        line = line.strip()
        if not line:
            continue
        try:
            row = json.loads(line)
        except json.JSONDecodeError:
            continue
        if row.get("record_id") == record_id:
            return row.get("response")
    return None


def _record_stored(vault_path: Path, record_id: str, resp: ParsedCaptureResponse) -> None:
    path = _idempotency_path(vault_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    entry = {
        "record_id": record_id,
        "stored_at": datetime.now().astimezone().isoformat(),
        "response": resp.model_dump(mode="json"),
    }
    with path.open("a", encoding="utf-8") as f:
        f.write(json.dumps(entry, ensure_ascii=False) + "\n")


# ---------------------------------------------------------------------------
# Verb handlers
# ---------------------------------------------------------------------------


def _handle_schedule(
    req: ParsedCaptureRequest,
    *,
    config: Config,
    tz: ZoneInfo,
    record_id: str,
) -> ParsedCaptureResponse:
    # Precedence: explicit when wins; fall through to hints; then default.
    if req.when is not None:
        starts_at = _ensure_tz(req.when, tz)
    elif req.day_hint is not None or req.time_hint is not None:
        # Use date_resolver — no LLM math on this path.
        clarify = _resolve_from_hints(req, config=config, tz=tz, record_id=record_id)
        if clarify is not None:
            return clarify
        resolved = date_resolver.resolve(
            req.day_hint,
            req.time_hint,
            req.captured_at if req.captured_at.tzinfo else req.captured_at.replace(tzinfo=tz),
            tz,
            morning_anchor_hour=config.morning_anchor_hour,
        )
        # resolved_at is non-None here because _resolve_from_hints would have
        # returned a clarification response if it were None.
        assert resolved.resolved_at is not None
        starts_at = resolved.resolved_at
    else:
        # No time given at all → schedule for the next-business-day morning anchor.
        starts_at = _next_business_morning(req.captured_at, config=config, tz=tz)

    duration = config.default_event_duration_minutes
    event = cal.create_event(
        config.vault_path,
        title=req.subject,
        starts_at=starts_at,
        duration_minutes=duration,
        tz_name=str(tz),
        source_utterance=req.raw_transcript,
    )
    rows = rem.build_event_schedule(event)
    rem.persist_event_schedule(config.vault_path, event, rows)
    rem.push_to_phone(rows)

    written = vault.calendar_event_path(config.vault_path, event.starts_at, event.title)
    return ParsedCaptureResponse(
        stored=True,
        record_id=record_id,
        verb=req.verb,
        written_path=_relative(config.vault_path, written),
        event_id=event.id,
    )


def _handle_note(
    req: ParsedCaptureRequest,
    *,
    config: Config,
    tz: ZoneInfo,
    record_id: str,
) -> ParsedCaptureResponse:
    """Timestamped markdown note.

    We drop these under ``vault/notes/`` (not the existing ``tools/`` or
    ``prompts/`` note buckets — those are their own kinds of thing).
    The file name embeds the captured_at date + a slugified subject so
    the note is greppable and ordered chronologically.
    """
    captured = _ensure_tz(req.captured_at, tz)
    notes_dir = config.vault_path / _NOTES_DIRNAME
    notes_dir.mkdir(parents=True, exist_ok=True)
    slug = vault.slugify(req.subject)
    filename = f"{captured.date().isoformat()}-{slug}.md"
    path = notes_dir / filename

    frontmatter = {
        "id": f"{captured.date().isoformat()}-{slug}",
        "title": req.subject,
        "captured_at": captured.isoformat(),
        "source": "sprite",
        "audio_path": req.audio_path,
        "confidence": req.confidence,
    }
    body = (
        f"# {req.subject}\n\n"
        f"*Captured {captured.strftime('%Y-%m-%d %H:%M %Z')} via Sprite.*\n\n"
        f"{req.raw_transcript.strip()}\n"
    )
    vault.write_markdown(path, frontmatter, body)

    return ParsedCaptureResponse(
        stored=True,
        record_id=record_id,
        verb=req.verb,
        written_path=_relative(config.vault_path, path),
    )


def _handle_handle(
    req: ParsedCaptureRequest,
    *,
    config: Config,
    tz: ZoneInfo,
    record_id: str,
) -> ParsedCaptureResponse:
    """Create a Herman reminder for a to-do (handle or remind verb).

    v1.6 semantics:
      - Writes to vault/reminders/<event-id>.md, NOT vault/calendar/.
      - Title carries no [handle] / [handle!] prefix — the vault/reminders/
        directory is the semantic signal for "this is a reminder, not a meeting".
      - criticality=critical is expressed via frontmatter tag criticality: critical
        instead of a title prefix.
      - Both verb=handle and verb=remind route here; the original verb value is
        preserved in the response (never rewritten).

    Reminder schedule (unchanged):
      - when is honored when present; otherwise schedules first alert for 1h
        before the start of the next business day.
      - criticality=critical bumps the whole chain 30 minutes earlier so the
        head-of-chain fires sooner. Herman's escalation tier.
      - Strike-chain JSON sidecars continue to live in vault/_reminders/ —
        the system-managed sidecar directory is unrelated to vault/reminders/.
    """
    # Precedence: explicit when wins; fall through to hints; then default.
    if req.when is not None:
        first_alert = _ensure_tz(req.when, tz)
    elif req.day_hint is not None or req.time_hint is not None:
        # Use date_resolver — no LLM math on this path.
        clarify = _resolve_from_hints(req, config=config, tz=tz, record_id=record_id)
        if clarify is not None:
            return clarify
        resolved = date_resolver.resolve(
            req.day_hint,
            req.time_hint,
            req.captured_at if req.captured_at.tzinfo else req.captured_at.replace(tzinfo=tz),
            tz,
            morning_anchor_hour=config.morning_anchor_hour,
        )
        assert resolved.resolved_at is not None
        first_alert = resolved.resolved_at
    else:
        # Default: 1 hour before start of next business day (business day
        # begins at ``morning_anchor_hour``).
        next_morning = _next_business_morning(req.captured_at, config=config, tz=tz)
        first_alert = next_morning - timedelta(hours=1)

    is_critical = req.criticality is CaptureCriticality.CRITICAL
    if is_critical:
        # Bump the whole chain earlier so the head-of-chain fires sooner.
        starts_at = first_alert - timedelta(minutes=30)
    else:
        starts_at = first_alert

    # Clean subject title — no [handle] / [handle!] prefix.
    # The vault/reminders/ directory is the semantic marker.
    title = req.subject

    # Build a synthetic CalendarEvent to hang the strike chain on.
    # The event_id drives the sidecar at vault/_reminders/<event-id>.json.
    duration = config.default_event_duration_minutes
    event = cal.create_event(
        config.vault_path,
        title=title,
        starts_at=starts_at,
        duration_minutes=duration,
        tz_name=str(tz),
        tags=(["critical"] if is_critical else []),
        source_utterance=req.raw_transcript,
    )
    rows = rem.build_event_schedule(event)
    rem.persist_event_schedule(config.vault_path, event, rows)
    rem.push_to_phone(rows)

    # Write the markdown reminder file to vault/reminders/ (not vault/calendar/).
    # We create the file directly here rather than using cal.create_event's
    # calendar_event_path, which would put it under vault/calendar/.
    reminders_dir = config.vault_path / _REMINDERS_DIRNAME
    reminders_dir.mkdir(parents=True, exist_ok=True)
    reminder_md_path = reminders_dir / f"{event.id}.md"

    frontmatter: dict = {
        "id": event.id,
        "title": title,
        "starts_at": event.starts_at.isoformat(),
        "tz": str(tz),
        "source": "sprite",
        "audio_path": req.audio_path,
        "confidence": req.confidence,
        "verb": req.verb.value,
        "created_at": event.created_at.isoformat(),
    }
    if is_critical:
        frontmatter["criticality"] = "critical"

    body = (
        f"# {title}\n\n"
        f"*Captured {_ensure_tz(req.captured_at, tz).strftime('%Y-%m-%d %H:%M %Z')} via Sprite.*\n\n"
        f"{req.raw_transcript.strip()}\n"
    )
    vault.write_markdown(reminder_md_path, frontmatter, body)

    # Also remove the calendar file that cal.create_event wrote — we do NOT
    # want handle/remind events appearing in vault/calendar/.
    calendar_path = vault.calendar_event_path(
        config.vault_path, event.starts_at, event.title
    )
    import contextlib as _contextlib
    with _contextlib.suppress(FileNotFoundError):
        calendar_path.unlink()
    # Remove the now-empty month directory if it became empty.
    with _contextlib.suppress(Exception):
        calendar_path.parent.rmdir()

    return ParsedCaptureResponse(
        stored=True,
        record_id=record_id,
        verb=req.verb,
        written_path=_relative(config.vault_path, reminder_md_path),
        event_id=event.id,
    )


def _handle_avoid(
    req: ParsedCaptureRequest,
    *,
    config: Config,
    tz: ZoneInfo,
    record_id: str,
) -> ParsedCaptureResponse:
    """Append a warning line to the sprite/warnings.md file.

    Format:  ``- YYYY-MM-DD HH:MM · <subject> · <raw_transcript>``

    The file is created on first write with a short header. It intentionally
    lives outside the Homunculus vault by default (``~/sprite/warnings.md``)
    so Sprite and Herman share a single source of truth.
    """
    captured = _ensure_tz(req.captured_at, tz)
    line = (
        f"- {captured.strftime('%Y-%m-%d %H:%M')} · "
        f"{req.subject.strip()} · "
        f"{_flatten(req.raw_transcript)}\n"
    )
    append_warning(config.sprite_warnings_path, line)

    return ParsedCaptureResponse(
        stored=True,
        record_id=record_id,
        verb=req.verb,
        written_path=str(config.sprite_warnings_path),
    )


def append_warning(warnings_path: Path, line: str) -> None:
    """Append a single already-formatted line to the warnings file.

    Creates the parent directory and prepends the header on first write.
    Kept module-public so the morning-summary composer can share the
    "read the tail of this file" logic if we ever want it.
    """
    warnings_path.parent.mkdir(parents=True, exist_ok=True)
    needs_header = not warnings_path.exists() or warnings_path.stat().st_size == 0
    with warnings_path.open("a", encoding="utf-8") as f:
        if needs_header:
            f.write(_WARNINGS_HEADER)
        f.write(line)
        f.flush()
        os.fsync(f.fileno())


def read_recent_warnings(warnings_path: Path, n: int = 20) -> list[str]:
    """Return the last ``n`` warning lines (most recent first), header stripped.

    Empty list if the file doesn't exist or has no warning lines yet.
    """
    if not warnings_path.exists():
        return []
    text = warnings_path.read_text(encoding="utf-8")
    lines = [ln for ln in text.splitlines() if ln.startswith("- ")]
    if not lines:
        return []
    return list(reversed(lines[-n:]))


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _resolve_from_hints(
    req: ParsedCaptureRequest,
    *,
    config: Config,
    tz: ZoneInfo,
    record_id: str,
) -> Optional[ParsedCaptureResponse]:
    """Run date_resolver against the request's hints.

    Returns a ``ParsedCaptureResponse`` with ``stored=False`` and a
    ``clarifying_question`` if the hints are ambiguous — the caller must
    return this response immediately WITHOUT writing to the vault.

    Returns ``None`` when resolution succeeded; the caller is then
    responsible for calling ``date_resolver.resolve()`` again to obtain the
    ``resolved_at`` datetime.  (We call resolve twice in the success path to
    keep the control flow in the verb handlers readable — date_resolver is
    pure Python and cheap.)
    """
    now = req.captured_at if req.captured_at.tzinfo else req.captured_at.replace(tzinfo=tz)
    result = date_resolver.resolve(
        req.day_hint,
        req.time_hint,
        now,
        tz,
        morning_anchor_hour=config.morning_anchor_hour,
    )
    if result.ambiguous:
        # Build a clarifying question matching the /capture/text style.
        parts = []
        if "time" in result.ambiguous:
            parts.append(f"Did you mean AM or PM? (e.g. '9 AM' or '9 PM')")
        if "day" in result.ambiguous:
            parts.append(f"I couldn't understand the day — could you be more specific?")
        question = " ".join(parts)
        return ParsedCaptureResponse(
            stored=False,
            record_id=record_id,
            verb=req.verb,
            clarifying_question=question,
            ambiguous_fields=list(result.ambiguous),
        )
    return None


def _ensure_tz(dt: datetime, tz: ZoneInfo) -> datetime:
    if dt.tzinfo is None:
        return dt.replace(tzinfo=tz)
    return dt


def _next_business_morning(reference: datetime, *, config: Config, tz: ZoneInfo) -> datetime:
    """Start of the next business day (Mon–Fri) at ``morning_anchor_hour``.

    "Next" means strictly after ``reference``. If reference is Friday
    afternoon, this returns Monday morning. Weekend references skip to
    Monday. Same-day is allowed when reference is BEFORE the morning
    anchor.
    """
    local = _ensure_tz(reference, tz).astimezone(tz)
    anchor = local.replace(hour=config.morning_anchor_hour, minute=0, second=0, microsecond=0)
    if local >= anchor:
        candidate = anchor + timedelta(days=1)
    else:
        candidate = anchor
    # weekday(): Monday=0 … Sunday=6
    while candidate.weekday() >= 5:
        candidate = candidate + timedelta(days=1)
    return candidate


def _flatten(text: str) -> str:
    """Collapse newlines/tabs so the warning line stays one line in Markdown."""
    return " ".join(text.split())


def _relative(vault_path: Path, p: Path) -> str:
    try:
        return str(p.relative_to(vault_path))
    except ValueError:
        return str(p)
