"""Intent parser — preprocessor (regex) + Ollama call with JSON-schema constraint.

Design:
  1. Preprocessor runs first (no LLM). Regex patterns extract:
     - criticality: "mark critical", "important", "urgent", "don't let me forget"
     - verb hints: schedule / note / handle / avoid
  2. Ollama call with format=JSON schema (constrained decoding via GBNF).
     Temperature 0.2. Few-shot examples in system prompt. Math NEVER in prompt.
  3. Post-process: merge preprocessor criticality (LLM cannot override it
     downward — only upward), validate confidence, detect ambiguous_fields.

v0.5.0 — M3 alignment: LLM now emits ``day_hint`` and ``time_hint`` instead
of a ``when`` string. The LLM does NOT know what today is. It does NOT compute
dates. It copies verbatim day/time expressions from the utterance into the two
hint fields. Herman's authoritative ``date_resolver`` (pure Python, no LLM) is
the only entity that resolves those hints to a UTC datetime.

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
# Output schema (v0.5.0 — day_hint/time_hint replace the old `when` string)
#
# The LLM must NOT emit a resolved date. It copies the user's exact phrasing:
#   "tomorrow at 10am" → day_hint="tomorrow", time_hint="10am"
#   "September 18th at 10 AM" → day_hint="September 18th", time_hint="10 AM"
#   "next Tuesday" → day_hint="next Tuesday", time_hint=null
#   "call the contractor at 5:35" → day_hint=null, time_hint="5:35"
#
# If the user says nothing about time → both null.
# If the user gives an explicit ISO-8601 datetime (typed input, very rare in
# speech) → the LLM MAY emit `when` as an ISO string. That optional field is
# NOT in `required`; it is listed in `properties` for completeness only.
# ---------------------------------------------------------------------------

_INTENT_JSON_SCHEMA = {
    "type": "object",
    "required": [
        "verb", "subject", "day_hint", "time_hint",
        "criticality", "confidence", "ambiguous_fields",
    ],
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
        "day_hint": {
            "type": ["string", "null"],
            "description": (
                "Verbatim day expression from the utterance. "
                "Copy exactly: 'tomorrow', 'Thursday', 'September 18th', 'next Monday'. "
                "Do NOT resolve. Do NOT convert to a date. Null if no day reference."
            ),
        },
        "time_hint": {
            "type": ["string", "null"],
            "description": (
                "Verbatim time expression from the utterance. "
                "Copy exactly: '10am', '9:00 AM', 'noon', '5:35'. "
                "Do NOT add AM/PM if the user did not say it. "
                "Null if no time reference."
            ),
        },
        "when": {
            "type": ["string", "null"],
            "description": (
                "Optional. Emit ONLY when the user provided an explicit, "
                "unambiguous ISO-8601 datetime string (e.g. '2026-09-18T10:00:00-04:00'). "
                "For all relative expressions use day_hint/time_hint instead. "
                "Leave null (or omit) in the typical voice-memo case."
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
                "List field names that are unclear "
                "(e.g. ['day_hint', 'subject', 'time_hint']). "
                "Include 'time_hint' when the user gave a bare hour "
                "without AM/PM and context does not resolve it. "
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
Given a voice-memo transcript, output a single JSON object.

CRITICAL RULE: You do not know what today is. You do not compute dates. You
do not resolve relative expressions like "tomorrow" or "Thursday" to calendar
dates. You copy the user's exact phrasing into the hint fields and let the
downstream date resolver do the math.

Output these keys:

  verb           — one of: schedule, note, handle, avoid
  subject        — short noun phrase (what this is about)
  day_hint       — verbatim day expression ("tomorrow", "Thursday", "next Monday",
                   "September 18th"), or null if no day reference
  time_hint      — verbatim time expression ("10am", "9:00 AM", "noon", "5:35"),
                   or null if no time reference
  when           — null in almost all cases; use ONLY for an explicit ISO-8601
                   datetime string the user actually said (rare)
  criticality    — "normal" or "critical" (critical only when user says so explicitly)
  confidence     — float 0.0–1.0 (your confidence in verb + subject)
  ambiguous_fields — list of field names you are unsure about; include "time_hint"
                   when the user gave a bare hour with no AM/PM (e.g. "5:35")

Verb definitions:
  schedule — put something on the calendar (requires a time reference)
  note     — remember a fact, insight, or reference (no deadline)
  handle   — do-this-soon to-do (may or may not have a deadline)
  avoid    — standing warning or constraint ("avoid scheduling X", "Sam is allergic to Y")

AM/PM rule:
  If the user says "5:35" without AM or PM, copy "5:35" into time_hint as-is.
  Do NOT guess whether it is morning or afternoon. Add "time_hint" to
  ambiguous_fields so the resolver can ask.

Emit JSON only. No prose. No markdown fences.

--- EXAMPLES ---

Transcript: "Let's set a second meeting with myself tomorrow at 10am."
Output:
{"verb":"schedule","subject":"second meeting with myself","day_hint":"tomorrow","time_hint":"10am","when":null,"criticality":"normal","confidence":0.92,"ambiguous_fields":[]}

Transcript: "dentist appointment September 18th at 10 AM"
Output:
{"verb":"schedule","subject":"dentist appointment","day_hint":"September 18th","time_hint":"10 AM","when":null,"criticality":"normal","confidence":0.95,"ambiguous_fields":[]}

Transcript: "gym next Tuesday"
Output:
{"verb":"schedule","subject":"gym","day_hint":"next Tuesday","time_hint":null,"when":null,"criticality":"normal","confidence":0.88,"ambiguous_fields":[]}

Transcript: "call the contractor at 5:35"
Output:
{"verb":"handle","subject":"call the contractor","day_hint":null,"time_hint":"5:35","when":null,"criticality":"normal","confidence":0.85,"ambiguous_fields":["time_hint"]}

Transcript: "remember to call the deck contractor Thursday, mark critical"
Output:
{"verb":"handle","subject":"call deck contractor","day_hint":"Thursday","time_hint":null,"when":null,"criticality":"critical","confidence":0.88,"ambiguous_fields":[]}

Transcript: "note that the LED reflects off the terrazzo"
Output:
{"verb":"note","subject":"LED reflects off terrazzo","day_hint":null,"time_hint":null,"when":null,"criticality":"normal","confidence":0.85,"ambiguous_fields":[]}
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
    day_hint: Optional[str]   # verbatim day expression from utterance, or None
    time_hint: Optional[str]  # verbatim time expression from utterance, or None
    criticality: str          # normal | critical
    confidence: float
    ambiguous_fields: list[str]
    raw_llm_json: dict        # for provenance / debugging
    # `when` is intentionally absent. If the LLM emits an ISO string in the
    # optional `when` field, we expose it via `raw_llm_json["when"]`. The
    # watcher pipeline checks raw_llm_json to detect the rare ISO case.


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

    Returns a ``ParseResult`` with ``day_hint`` and ``time_hint`` — verbatim
    expressions the user spoke. The LLM does NOT resolve dates; that is the
    job of Herman's authoritative ``date_resolver`` (pure Python, no LLM math).

    ``captured_at`` and ``speaker_tz`` are included in the user message for
    context (e.g., transcript provenance) but NOT for date resolution — the
    LLM must not use them to compute a calendar date.
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
        "format": _INTENT_JSON_SCHEMA,
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
        day_hint=data.get("day_hint"),
        time_hint=data.get("time_hint"),
        criticality=criticality,
        confidence=float(data["confidence"]),
        ambiguous_fields=list(data.get("ambiguous_fields", [])),
        raw_llm_json=data,
    )
