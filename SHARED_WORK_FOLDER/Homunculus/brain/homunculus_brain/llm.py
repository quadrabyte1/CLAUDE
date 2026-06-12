"""LLM wrapper.

Primary backend: Ollama, with structured-output (`format: <json-schema>`)
so the model is forced into a valid ParsedIntent. Backend is swappable via
the OLLAMA_BASE_URL / OLLAMA_MODEL env vars, so when we migrate to a
faster box (Linux + NVIDIA, the new MS-NVIDIA chip, etc.) nothing in the
brain changes.

Fallback: a regex-and-keyword heuristic parser used when Ollama is
unreachable. Keeps tests and offline development functional without
forcing the user to have a model running.
"""

from __future__ import annotations

import json
import logging
import re
from typing import Optional

import httpx

from .schemas import Confidence, IntentKind, ParsedIntent


log = logging.getLogger(__name__)


SYSTEM_PROMPT = """You are Homunculus, a voice-assistant intent parser.

You receive a single short utterance from the user. Extract the structured
intent and return ONLY JSON matching the schema. Never reply with prose.

Rules:
- Pick the SINGLE best `kind` from: calendar_event, tool_note, prompt_note,
  calendar_query, unknown.
- Use `unknown` and `confidence: "low"` if you cannot tell.
- For calendar_event / calendar_query, copy the day expression into
  `day_hint` exactly as the user said it ("Thursday", "tomorrow",
  "next Monday"). Do NOT compute the date — the caller does that.
- Copy the time expression into `time_hint` exactly ("10am", "2:30 PM",
  "morning"). Do NOT convert to 24-hour.
- If the user said an hour 1-12 with NO am/pm and NO 24-hour context
  (e.g. "5:35", "feed Jake at 6"), add "time" to `ambiguous_fields`.
  We will ask "AM or PM?" rather than guess. Hours 0 and 13-23 are
  unambiguous (they can only be a 24-hour reading). Named anchors
  ("noon", "midnight", "morning", "afternoon", "evening", "night")
  are unambiguous too.
- "remind me to X" and "schedule/book/add X" are ALWAYS calendar_event,
  never calendar_query. Use calendar_query only when the user is asking
  about their availability ("am I free…", "do I have anything on…",
  "can we meet…").
- For calendar_event and calendar_query, fill `title` with a short noun
  phrase naming the activity — the verb/object plus any key participant —
  with scheduling words ("schedule", "remind me to", "book") stripped.
  Preserve the casing of proper nouns (people, places, brands); the rest
  may be lowercase. No trailing punctuation.
  Examples:
    "schedule coffee with Jane Thursday at 10am" → title: "coffee with Jane"
    "remind me to call the dentist tomorrow afternoon" → title: "call the dentist"
    "am I free Thursday at 10?" → title: null  (no activity named)
    "book the conference room for the design review Friday" → title: "design review"
  Do NOT include the day or time in `title` — those go in `day_hint` /
  `time_hint`. Do NOT invent a title; leave it null if none is stated.
- Put any names mentioned in `people`.
- Put any topic words (e.g. "woodworking", "gardening") in `tags`.
- If you guessed at any field, list its name in `ambiguous_fields`.
- `raw_text` is the user's utterance verbatim.
- For `prompt_note`, put the full body the user dictated into `body` — the
  prompt and the answer they want to remember. If they only named the topic,
  leave `body` null.
"""


PARSED_INTENT_JSON_SCHEMA = {
    "type": "object",
    "properties": {
        "kind": {"type": "string", "enum": [k.value for k in IntentKind]},
        "confidence": {"type": "string", "enum": [c.value for c in Confidence]},
        "title": {"type": ["string", "null"]},
        "day_hint": {"type": ["string", "null"]},
        "time_hint": {"type": ["string", "null"]},
        "duration_minutes": {"type": ["integer", "null"]},
        "people": {"type": "array", "items": {"type": "string"}},
        "tags": {"type": "array", "items": {"type": "string"}},
        "raw_text": {"type": "string"},
        "ambiguous_fields": {"type": "array", "items": {"type": "string"}},
        "body": {"type": ["string", "null"]},
    },
    "required": ["kind", "confidence", "raw_text"],
}


class LLMUnreachable(Exception):
    pass


async def parse_intent(
    utterance: str,
    *,
    base_url: str,
    model: str,
    timeout_seconds: float = 30.0,
) -> ParsedIntent:
    """Call Ollama with structured output. Falls back to heuristics on failure."""
    try:
        return await _parse_via_ollama(utterance, base_url=base_url, model=model, timeout_seconds=timeout_seconds)
    except (httpx.HTTPError, LLMUnreachable, json.JSONDecodeError, ValueError) as exc:
        log.warning("Ollama parse failed (%s) — falling back to heuristics", exc)
        return heuristic_parse(utterance)


async def _parse_via_ollama(utterance: str, *, base_url: str, model: str, timeout_seconds: float) -> ParsedIntent:
    payload = {
        "model": model,
        "messages": [
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": utterance},
        ],
        "stream": False,
        "format": PARSED_INTENT_JSON_SCHEMA,
        "options": {"temperature": 0.1},
    }

    async with httpx.AsyncClient(timeout=timeout_seconds) as client:
        try:
            resp = await client.post(f"{base_url.rstrip('/')}/api/chat", json=payload)
        except httpx.ConnectError as exc:
            raise LLMUnreachable(f"could not reach Ollama at {base_url}") from exc

        if resp.status_code >= 400:
            raise LLMUnreachable(f"Ollama returned {resp.status_code}: {resp.text[:200]}")

        data = resp.json()

    content = (data.get("message") or {}).get("content")
    if not content:
        raise ValueError("Ollama returned empty content")

    parsed_dict = json.loads(content)
    # Make sure raw_text is always populated even if model dropped it.
    parsed_dict.setdefault("raw_text", utterance)
    return ParsedIntent.model_validate(parsed_dict)


# --- offline heuristic fallback ----------------------------------------------


_TOOL_NOTE_PATTERNS = [
    re.compile(r"\bnote\s+(that|this)\s+tool\b", re.I),
    re.compile(r"\b(remember|note|save)\s+(this|that)\s+(tool|brand|model)\b", re.I),
    re.compile(r"\b(craftsman|dewalt|milwaukee|stanley|makita|bosch|festool)\b", re.I),
]

_PROMPT_NOTE_PATTERNS = [
    re.compile(r"\bsave\s+(this|that)\s+prompt\b", re.I),
    re.compile(r"\b(remember|save)\s+(this|that)\s+(answer|response|claude)\b", re.I),
    re.compile(r"\bclaude\b", re.I),
]

_CALENDAR_QUERY_PATTERNS = [
    re.compile(r"\b(can|could)\s+(we|i)\s+(meet|do)\b", re.I),
    re.compile(r"\bam\s+i\s+(free|busy|available)\b", re.I),
    re.compile(r"\bdo\s+i\s+have\b.*\b(on|at)\b", re.I),
]

_CALENDAR_EVENT_PATTERNS = [
    re.compile(r"\b(add|schedule|book|put)\b.*\b(on|at|for)\b", re.I),
    re.compile(r"\bremind me to\b", re.I),
    re.compile(r"\b(meeting|appointment|call|coffee|lunch|dinner)\b", re.I),
]

_DAY_HINT_RE = re.compile(
    r"\b(today|tomorrow|monday|tuesday|wednesday|thursday|friday|saturday|sunday|"
    r"next\s+\w+|this\s+\w+)\b",
    re.I,
)

_TIME_HINT_RE = re.compile(
    r"\b(\d{1,2}(?::\d{2})?\s*(?:am|pm|a\.m\.|p\.m\.)?|noon|midnight|morning|afternoon|evening|night)\b",
    re.I,
)


def heuristic_parse(utterance: str) -> ParsedIntent:
    text = utterance.strip()
    kind = IntentKind.UNKNOWN
    confidence = Confidence.LOW

    if any(p.search(text) for p in _PROMPT_NOTE_PATTERNS):
        kind, confidence = IntentKind.PROMPT_NOTE, Confidence.MEDIUM
    elif any(p.search(text) for p in _TOOL_NOTE_PATTERNS):
        kind, confidence = IntentKind.TOOL_NOTE, Confidence.MEDIUM
    elif any(p.search(text) for p in _CALENDAR_QUERY_PATTERNS):
        kind, confidence = IntentKind.CALENDAR_QUERY, Confidence.MEDIUM
    elif any(p.search(text) for p in _CALENDAR_EVENT_PATTERNS):
        kind, confidence = IntentKind.CALENDAR_EVENT, Confidence.MEDIUM

    day_match = _DAY_HINT_RE.search(text)
    time_match = _TIME_HINT_RE.search(text)

    title = _extract_title(text, kind)
    body = _extract_prompt_body(text) if kind is IntentKind.PROMPT_NOTE else None

    ambiguous: list[str] = []
    if kind in (IntentKind.CALENDAR_EVENT, IntentKind.CALENDAR_QUERY):
        if not day_match:
            ambiguous.append("day")
        if not time_match:
            ambiguous.append("time")

    return ParsedIntent(
        kind=kind,
        confidence=confidence,
        title=title,
        day_hint=day_match.group(0) if day_match else None,
        time_hint=time_match.group(0) if time_match else None,
        duration_minutes=None,
        people=[],
        tags=[],
        raw_text=utterance,
        ambiguous_fields=ambiguous,
        body=body,
    )


def _extract_title(text: str, kind: IntentKind) -> Optional[str]:
    if kind is IntentKind.TOOL_NOTE:
        # "note that tool — Craftsman open-end wrench" → "Craftsman open-end wrench"
        m = re.search(r"(?:note\s+(?:that|this)\s+tool|note|remember)\s*[—\-:]?\s*(.+)", text, re.I)
        if m:
            return m.group(1).strip(" .,!?").rstrip("-").strip()
    if kind in (IntentKind.CALENDAR_EVENT, IntentKind.CALENDAR_QUERY):
        m = re.search(r"\b(coffee|lunch|dinner|meeting|call|appointment)\b(\s+with\s+\w+)?", text, re.I)
        if m:
            return m.group(0).strip()
    if kind is IntentKind.PROMPT_NOTE:
        m = re.search(r"(?:save|remember|note)\s+(?:this|that)\s+(?:prompt|answer|response)\s*(?:about\s+)?(.+?)(?:\s*[:\-—]\s*body[:\s].*)?$", text, re.I)
        if m and m.group(1):
            return m.group(1).strip(" .,!?")
    return None


def _extract_prompt_body(text: str) -> Optional[str]:
    """Look for an explicit body marker. The heuristic is shallow; the LLM
    will do this better. We just catch the common `... — body: <text>` form.
    """
    m = re.search(r"\bbody\s*[:\-]\s*(.+)$", text, re.I | re.DOTALL)
    if m:
        return m.group(1).strip()
    return None
