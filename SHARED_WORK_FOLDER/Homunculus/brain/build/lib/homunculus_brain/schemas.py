"""Pydantic schemas — the contract between the LLM, the router, and the vault.

The LLM is asked to emit a `ParsedIntent`. Everything downstream consumes the
parsed structure, never the raw utterance.
"""

from __future__ import annotations

from datetime import datetime
from enum import Enum
from typing import Literal, Optional

from pydantic import BaseModel, Field


class IntentKind(str, Enum):
    CALENDAR_EVENT = "calendar_event"
    TOOL_NOTE = "tool_note"
    PROMPT_NOTE = "prompt_note"
    CALENDAR_QUERY = "calendar_query"
    UNKNOWN = "unknown"


class Confidence(str, Enum):
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"


class ParsedIntent(BaseModel):
    """Structured output the LLM emits when parsing an utterance."""

    kind: IntentKind
    confidence: Confidence
    title: Optional[str] = None
    # Free-text day hint, e.g. "Thursday", "tomorrow", "next Monday".
    day_hint: Optional[str] = None
    # Free-text time hint, e.g. "10am", "2:30 PM", "morning".
    time_hint: Optional[str] = None
    duration_minutes: Optional[int] = None
    people: list[str] = Field(default_factory=list)
    tags: list[str] = Field(default_factory=list)
    # Original utterance — preserved for the activity log and corrections.
    raw_text: str
    # If the LLM is not sure about a field, name it here so the router can
    # decide to ask a clarifying question instead of silently guessing.
    ambiguous_fields: list[str] = Field(default_factory=list)
    # For prompt_note captures: the full inline body the user dictated
    # (the prompt and answer text). Optional — when missing, the prompt
    # note is saved with a placeholder the user can fill in later.
    body: Optional[str] = None


class CalendarEvent(BaseModel):
    """A scheduled event, persisted as one markdown file in vault/calendar/."""

    id: str
    title: str
    starts_at: datetime
    ends_at: datetime
    tz: str
    duration_minutes: int
    people: list[str] = Field(default_factory=list)
    tags: list[str] = Field(default_factory=list)
    source: Literal["voice", "text", "manual", "rescheduled"] = "voice"
    source_utterance: Optional[str] = None
    created_at: datetime
    updated_at: datetime


class ConflictReport(BaseModel):
    has_direct_conflict: bool
    has_fuzzy_conflict: bool
    direct: list[CalendarEvent] = Field(default_factory=list)
    fuzzy: list[CalendarEvent] = Field(default_factory=list)


class ToolNote(BaseModel):
    id: str
    title: str
    tags: list[str] = Field(default_factory=list)
    captured_at: datetime
    source: Literal["voice", "text"] = "voice"
    source_utterance: Optional[str] = None
    context: Optional[str] = None  # e.g. "noted while watching woodworking video"


class PromptNote(BaseModel):
    id: str
    title: str
    captured_at: datetime
    source: Literal["voice", "text"] = "voice"
    source_utterance: Optional[str] = None
    body: Optional[str] = None


class InboxEntry(BaseModel):
    captured_at: datetime
    raw_text: str
    best_guess: Optional[IntentKind] = None
    reason: str  # why it landed in the inbox


class ReminderKind(str, Enum):
    MORNING_SUMMARY = "morning_summary"
    HEADS_UP_30 = "heads_up_30"
    PRE_5 = "pre_5"
    STRIKE_0 = "strike_0"
    STRIKE_5 = "strike_5"
    STRIKE_10 = "strike_10"
    STRIKE_15 = "strike_15"


class ReminderRow(BaseModel):
    event_id: str
    kind: ReminderKind
    fire_at: datetime
    tz: str
    body: str  # text to display in the notification
    status: Literal["pending", "scheduled", "fired", "acked", "cancelled", "missed"] = "pending"


# --- API request/response shapes ----------------------------------------------


class CaptureRequest(BaseModel):
    text: str
    # Optional: spoken-on time from the phone (ISO 8601). Defaults to server now.
    captured_at: Optional[datetime] = None
    # Optional: tz of the speaker if not the default.
    speaker_tz: Optional[str] = None


class CaptureResponse(BaseModel):
    kind: IntentKind
    confidence: Confidence
    action: Literal["wrote", "needs_confirmation", "needs_clarification", "inbox"]
    spoken_reply: str  # what TTS should say back
    written_path: Optional[str] = None
    conflicts: Optional[ConflictReport] = None
    clarifying_question: Optional[str] = None
    raw_text: str


class HealthResponse(BaseModel):
    status: Literal["ok"]
    design_version: str
    package_version: str
    vault_path: str


class AckRequest(BaseModel):
    """Phone → brain: the user tapped 'OK' on a reminder.

    The brain cancels all later strikes in the same chain so the phone can
    remove them from ``UNUserNotificationCenter`` even if its local view
    disagreed with the brain's record.
    """

    event_id: str
    kind: ReminderKind
    acked_at: Optional[datetime] = None


class AckResponse(BaseModel):
    event_id: str
    acked_kind: ReminderKind
    # The kinds in the same event chain that were cancelled by this ack.
    cancelled_kinds: list[ReminderKind] = Field(default_factory=list)
    # The updated sidecar rows (for the event chain) after the mutation.
    rows: list[ReminderRow] = Field(default_factory=list)
