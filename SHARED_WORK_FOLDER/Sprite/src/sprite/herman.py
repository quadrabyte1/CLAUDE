"""Herman HTTP client — POST /capture/parsed with retries and response logging.

Wire contract:
  Matches ``ParsedCaptureRequest`` in Herman's schemas.py exactly.
  Required fields:
    verb, subject, when, criticality, confidence, raw_transcript,
    audio_path, captured_at

  Optional:
    speaker_tz (Herman reads it from the request; Sprite always sends it)
    day_hint   (v1.3.1) free-text day, e.g. "thursday" — Herman resolves
    time_hint  (v1.3.1) free-text time, e.g. "9am" — Herman resolves
    sprite_uuid (provenance extension; Herman ignores unknown fields per
                 Pydantic's default model_config — safe to add)

  When ``when`` is None and ``day_hint``/``time_hint`` are set, Herman uses
  its authoritative ``date_resolver`` (pure Python, no LLM math) to resolve
  the date. If resolution is ambiguous, Herman returns ``stored=False`` with
  a ``clarifying_question`` the caller should surface to the user.

Response contract:
  Herman returns ``ParsedCaptureResponse`` on 200:
    {stored, record_id, verb, written_path?, event_id?}
  On 422: {"stored": false, "reason": "low_confidence"} (Sprite should never
    hit this since we gate on confidence locally — but we handle it gracefully)
  On 400: {"stored": false, "reason": "schema_violation"}

Retry strategy:
  3 attempts with 1s, 2s backoff. Transient 5xx and connection errors retry.
  4xx errors (client fault) do NOT retry.

Portability:
  Pure httpx — no Mac-only transport.
"""

from __future__ import annotations

import json
import logging
import time
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Optional

import httpx

log = logging.getLogger(__name__)

_ENDPOINT = "/capture/parsed"
_MAX_RETRIES = 3
_RETRY_BACKOFFS = [1.0, 2.0]  # seconds between attempts 1→2, 2→3


# ---------------------------------------------------------------------------
# Request builder
# ---------------------------------------------------------------------------


def build_request(
    *,
    verb: str,
    subject: str,
    when: Optional[str],
    criticality: str,
    confidence: float,
    raw_transcript: str,
    audio_path: str,
    captured_at: datetime,
    speaker_tz: str = "America/New_York",
    sprite_uuid: Optional[str] = None,
    day_hint: Optional[str] = None,
    time_hint: Optional[str] = None,
) -> dict:
    """Build the JSON payload for POST /capture/parsed.

    ``when`` may be:
    - An ISO-8601 string (e.g. "2026-09-17T09:00:00-04:00") — passed as-is.
    - None — omitted (Herman defaults based on verb, or resolves from hints).

    ``day_hint`` / ``time_hint`` (v1.3.1): pass these instead of doing date
    math in Sprite. Herman's authoritative ``date_resolver`` resolves them
    and returns a clarifying question if ambiguous. Prefer these over
    constructing an ISO-8601 string from uncertain LLM output.
    Precedence: if ``when`` is set, Herman ignores the hints.

    This function is the single source of truth for the wire shape.
    Keep it in sync with Herman's ``ParsedCaptureRequest`` in schemas.py.
    """
    payload: dict = {
        "verb": verb,
        "subject": subject,
        "when": when,
        "criticality": criticality,
        "confidence": confidence,
        "raw_transcript": raw_transcript,
        "audio_path": audio_path,
        "captured_at": captured_at.isoformat(),
        "speaker_tz": speaker_tz,
    }
    if day_hint is not None:
        payload["day_hint"] = day_hint
    if time_hint is not None:
        payload["time_hint"] = time_hint
    if sprite_uuid is not None:
        payload["sprite_uuid"] = sprite_uuid
    return payload


# ---------------------------------------------------------------------------
# Response shape
# ---------------------------------------------------------------------------


@dataclass
class HermanResponse:
    status_code: int
    stored: bool
    record_id: Optional[str]
    verb: Optional[str]
    written_path: Optional[str]
    event_id: Optional[str]
    raw_body: dict


class HermanError(RuntimeError):
    """Raised when Herman returns a non-retryable error or all retries are exhausted."""


# ---------------------------------------------------------------------------
# HTTP client
# ---------------------------------------------------------------------------


def post_to_herman(
    payload: dict,
    *,
    herman_base_url: str,
    timeout: float = 15.0,
) -> HermanResponse:
    """POST *payload* to Herman's /capture/parsed with retry-with-backoff.

    Returns a ``HermanResponse`` on success (HTTP 200).
    Raises ``HermanError`` on non-retryable errors or exhausted retries.
    """
    url = herman_base_url.rstrip("/") + _ENDPOINT
    last_exc: Optional[Exception] = None

    for attempt in range(1, _MAX_RETRIES + 1):
        try:
            log.debug("herman: POST %s (attempt %d)", url, attempt)
            with httpx.Client(timeout=timeout) as client:
                resp = client.post(url, json=payload)

            body: dict = {}
            try:
                body = resp.json()
            except Exception:
                body = {"raw": resp.text}

            if resp.status_code == 200:
                log.info(
                    "herman: accepted record_id=%s event_id=%s",
                    body.get("record_id"),
                    body.get("event_id"),
                )
                return HermanResponse(
                    status_code=200,
                    stored=body.get("stored", True),
                    record_id=body.get("record_id"),
                    verb=body.get("verb"),
                    written_path=body.get("written_path"),
                    event_id=body.get("event_id"),
                    raw_body=body,
                )

            if resp.status_code == 422:
                # Low-confidence rejection — should not happen (Sprite gates
                # locally) but handled cleanly.
                log.warning("herman: 422 low_confidence (conf=%.2f)", payload.get("confidence", -1))
                raise HermanError(
                    f"Herman rejected record as low_confidence: {body}"
                )

            if resp.status_code == 400:
                log.error("herman: 400 schema_violation: %s", body)
                raise HermanError(
                    f"Herman returned schema_violation — payload does not match contract: {body}"
                )

            if 400 <= resp.status_code < 500:
                # Other 4xx — don't retry.
                raise HermanError(
                    f"Herman returned non-retryable HTTP {resp.status_code}: {body}"
                )

            # 5xx — retryable.
            log.warning(
                "herman: HTTP %d on attempt %d, will retry", resp.status_code, attempt
            )
            last_exc = HermanError(f"Herman HTTP {resp.status_code}: {body}")

        except (httpx.ConnectError, httpx.TimeoutException) as exc:
            log.warning("herman: network error on attempt %d: %s", attempt, exc)
            last_exc = HermanError(f"Herman unreachable: {exc}")

        # Backoff before next attempt (but not after the last).
        if attempt < _MAX_RETRIES:
            backoff = _RETRY_BACKOFFS[attempt - 1] if attempt - 1 < len(_RETRY_BACKOFFS) else 2.0
            log.debug("herman: backing off %.1f s", backoff)
            time.sleep(backoff)

    raise HermanError(
        f"Herman POST failed after {_MAX_RETRIES} attempts"
    ) from last_exc
