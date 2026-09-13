"""Intent parser — preprocessor (regex) + Ollama call with JSON-schema constraint.

Design:
  1. Preprocessor runs first (no LLM). Regex patterns extract:
     - criticality: "mark critical", "important", "urgent", "don't let me forget"
     - verb hints: schedule / note / handle / avoid
  2. Ollama call with format=JSON schema (constrained decoding via GBNF).
     Temperature 0.2. One-shot example in system prompt. Math never in prompt.
  3. Post-process: merge preprocessor criticality (LLM cannot override it
     downward — only upward), validate confidence, detect ambiguous_fields.

Portability:
  No MLX, no CoreML, no Mac-only audio. Talks to Ollama HTTP API only.
  On Linux with vLLM, swap OLLAMA_BASE_URL to the vLLM OpenAI-compat endpoint;
  the format/schema field travels identically.

Ollama JSON schema constraint:
  We use the Ollama v0.5+ `format` field with the JSON schema dict. GBNF
  enforces structural validity — content accuracy is the prompt's job.
"""

from __future__ import annotations

import json
import logging
import re
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Optional

import httpx

log = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Output schema (matches scoping §3 + Herman's ParsedCaptureRequest)
# ---------------------------------------------------------------------------

_PARSE_SCHEMA = {
    "type": "object",
    "required": ["verb", "subject", "when", "criticality", "confidence", "ambiguous_fields"],
    "additionalProperties": False,
    "properties": {
        "verb": {
            "type": "string",
            "enum": ["schedule", "note", "handle", "avoid"],
            "description": "Primary action verb.",
        },
        "subject": {
            "type": "string",
            "description": "Short noun phrase — what the memo is about.",
        },
        "when": {
            "type": ["string", "null"],
            "description": (
                "ISO-8601 datetime with timezone offset if extractable; "
                "null if no time reference is present."
            ),
        },
        "criticality": {
            "type": "string",
            "enum": ["normal", "critical"],
            "description": "'critical' when the user marks urgency explicitly.",
        },
        "confidence": {
            "type": "number",
            "minimum": 0.0,
            "maximum": 1.0,
            "description": (
                "Your confidence that the verb and subject are correct. "
                "Use < 0.6 when you are unsure."
            ),
        },
        "ambiguous_fields": {
            "type": "array",
            "items": {"type": "string"},
            "description": (
                "List field names that are unclear (e.g. ['when', 'subject']). "
                "Empty list when nothing is ambiguous."
            ),
        },
    },
}

# ---------------------------------------------------------------------------
# System prompt
# ---------------------------------------------------------------------------

_SYSTEM_PROMPT = """\
You are a voice-memo intent extractor for a personal assistant named Sprite.
Given a voice-memo transcript, output a single JSON object with these keys:

  verb        — one of: schedule, note, handle, avoid
  subject     — short noun phrase (what this is about)
  when        — ISO-8601 datetime with offset, or null if not mentioned
  criticality — "normal" or "critical" (critical only when user says urgent/important/critical)
  confidence  — float 0.0–1.0 (your confidence in verb + subject)
  ambiguous_fields — list of field names you are unsure about (empty list if none)

Verb definitions:
  schedule — put something on the calendar (requires a time)
  note     — remember a fact, insight, or reference (no deadline)
  handle   — do-this-soon to-do (may or may not have a deadline)
  avoid    — standing warning or constraint ("avoid scheduling X", "Sam is allergic to Y")

Rules:
  - Never do date arithmetic. If "tomorrow" or "Thursday" is mentioned, emit the
    relative expression in the `when` field as a descriptive string — NOT an ISO date.
    Example: when="thursday at 10am" is acceptable when you cannot resolve the date.
  - If confidence < 0.6 on verb OR subject, list those fields in ambiguous_fields.
  - Emit JSON only. No prose. No markdown fences.

Example:

Transcript: "remember to call the deck contractor Thursday, mark critical"

Output:
{"verb":"handle","subject":"call deck contractor","when":"thursday","criticality":"critical","confidence":0.88,"ambiguous_fields":[]}
"""

# ---------------------------------------------------------------------------
# Preprocessor regex patterns
# ---------------------------------------------------------------------------

_CRITICAL_RE = re.compile(
    r"\b(mark\s+critical|mark\s+urgent|important|urgent|critical|don[''']?t\s+let\s+me\s+forget)\b",
    re.IGNORECASE,
)

_VERB_HINTS: list[tuple[re.Pattern, str]] = [
    (re.compile(r"\b(schedule|set\s+up|book|calendar)\b", re.IGNORECASE), "schedule"),
    (re.compile(r"\b(avoid|don[''']?t\s+schedule|never\s+book|allergic)\b", re.IGNORECASE), "avoid"),
    (re.compile(r"\b(note|remember|jot|record|write\s+down)\b", re.IGNORECASE), "note"),
    (re.compile(r"\b(handle|deal\s+with|take\s+care|call|email|remind|do|fix)\b", re.IGNORECASE), "handle"),
]


@dataclass
class PreprocessorHints:
    forced_critical: bool       # regex found explicit criticality marker
    verb_hint: Optional[str]    # strongest verb signal from regex (may be None)


def _preprocess(transcript: str) -> PreprocessorHints:
    """Extract criticality and verb signals without touching the LLM."""
    forced_critical = bool(_CRITICAL_RE.search(transcript))

    verb_hint: Optional[str] = None
    for pattern, verb in _VERB_HINTS:
        if pattern.search(transcript):
            verb_hint = verb
            break  # first match wins (patterns ordered by specificity)

    return PreprocessorHints(forced_critical=forced_critical, verb_hint=verb_hint)


# ---------------------------------------------------------------------------
# Ollama call
# ---------------------------------------------------------------------------


@dataclass
class ParseResult:
    verb: str               # schedule | note | handle | avoid
    subject: str
    when: Optional[str]     # raw string from LLM (may be relative), or None
    criticality: str        # normal | critical
    confidence: float
    ambiguous_fields: list[str]
    raw_llm_json: dict      # for provenance / debugging


class OllamaUnreachable(RuntimeError):
    """Raised when Ollama HTTP endpoint is not reachable."""


class OllamaParseError(RuntimeError):
    """Raised when Ollama returns structurally invalid JSON for our schema."""


def parse_intent(
    transcript: str,
    *,
    ollama_base_url: str,
    ollama_model: str,
    timeout: float = 30.0,
    captured_at: Optional[datetime] = None,
    speaker_tz: str = "America/New_York",
) -> ParseResult:
    """Run preprocessor then call Ollama for structured intent extraction.

    ``captured_at`` and ``speaker_tz`` are injected into the user prompt
    to help the LLM interpret relative date expressions — but the *resolver*
    (Python, not LLM) is responsible for converting "thursday" to an ISO
    date. See the watcher pipeline for where date resolution happens
    (future M3 work; for now we emit the raw ``when`` string and Herman
    resolves it server-side via its own date_resolver).
    """
    hints = _preprocess(transcript)

    # Build user message with context hints.
    captured_str = (
        captured_at.astimezone(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
        if captured_at
        else "unknown"
    )
    verb_hint_note = (
        f"\n[Preprocessor hint: verb is likely '{hints.verb_hint}']"
        if hints.verb_hint
        else ""
    )
    user_msg = (
        f"Memo captured at: {captured_str} ({speaker_tz})\n"
        f"Transcript: {transcript.strip()}"
        f"{verb_hint_note}"
    )

    payload = {
        "model": ollama_model,
        "prompt": user_msg,
        "system": _SYSTEM_PROMPT,
        "stream": False,
        "options": {"temperature": 0.2, "num_predict": 256},
        "format": _PARSE_SCHEMA,
    }

    try:
        with httpx.Client(timeout=timeout) as client:
            resp = client.post(f"{ollama_base_url}/api/generate", json=payload)
        resp.raise_for_status()
    except httpx.ConnectError as exc:
        raise OllamaUnreachable(
            f"Ollama not reachable at {ollama_base_url}: {exc}"
        ) from exc
    except httpx.TimeoutException as exc:
        raise OllamaUnreachable(
            f"Ollama timed out after {timeout}s: {exc}"
        ) from exc
    except httpx.HTTPStatusError as exc:
        raise OllamaUnreachable(
            f"Ollama returned HTTP {exc.response.status_code}: {exc.response.text[:200]}"
        ) from exc

    raw_text = resp.json().get("response", "")
    try:
        data = json.loads(raw_text)
    except json.JSONDecodeError as exc:
        raise OllamaParseError(
            f"Ollama response is not valid JSON: {raw_text[:200]}"
        ) from exc

    # Validate required keys.
    for key in ("verb", "subject", "confidence", "ambiguous_fields"):
        if key not in data:
            raise OllamaParseError(f"Ollama JSON missing required key: {key!r}")

    # Preprocessor criticality override: forced_critical can only raise to
    # "critical", never lower it. LLM can override upward but not downward.
    criticality = data.get("criticality", "normal")
    if hints.forced_critical:
        criticality = "critical"

    return ParseResult(
        verb=data["verb"],
        subject=data["subject"],
        when=data.get("when"),
        criticality=criticality,
        confidence=float(data["confidence"]),
        ambiguous_fields=list(data.get("ambiguous_fields", [])),
        raw_llm_json=data,
    )
