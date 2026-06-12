"""Contract tests for the Ollama SYSTEM_PROMPT.

The test suite is hermetic and never calls a real model, so prompt-only
bugs can't be caught by exercising the LLM path. Instead we assert that
the prompt contains the rules and worked examples we depend on. Any
future edit that drops these turns the test red.

Each test below corresponds to a real bug we hit and fixed.
"""

from __future__ import annotations

from homunculus_brain.llm import SYSTEM_PROMPT


def test_prompt_teaches_title_extraction():
    """Bug 2026-06-08: LLM returned title=null, so spoken_reply said
    "Got it — event, Thursday June 11 at 10:00 AM …" instead of naming
    the activity ("coffee with Jane"). The fallback in
    intent_router.py:117 is `intent.title or "event"`, so the cure has
    to land in the prompt — there's nothing else to extract the title.
    """
    assert "title" in SYSTEM_PROMPT.lower()
    # The prompt must give the model concrete title examples — abstract
    # rules alone were not enough to stop the "event" fallback.
    assert "coffee with Jane" in SYSTEM_PROMPT
    assert "call the dentist" in SYSTEM_PROMPT
    # And tell it NOT to invent one when the user didn't name an activity
    # (otherwise calendar_query utterances get spurious titles).
    assert "leave it null" in SYSTEM_PROMPT or "title: null" in SYSTEM_PROMPT


def test_prompt_preserves_proper_nouns_in_title():
    """Bug 2026-06-08: first pass of the title fix said "Lowercase, no
    trailing punctuation" — which made the model dutifully return
    "coffee with jane". The cure was to carve out proper nouns.
    """
    assert "proper noun" in SYSTEM_PROMPT.lower()


def test_prompt_pins_remind_me_to_as_calendar_event():
    """Bug 2026-06-08: after the first title-rule edit the LLM started
    misclassifying "remind me to call the dentist tomorrow afternoon" as
    calendar_query (returning "You're clear Tuesday June 9 at 1:00 PM").
    The cure was an explicit kind-routing rule in the prompt.
    """
    assert "remind me to" in SYSTEM_PROMPT.lower()
    assert "calendar_event" in SYSTEM_PROMPT


def test_prompt_teaches_ambiguous_time_when_no_ampm():
    """Bug 2026-06-10 17:31 EDT: utterance "Feed Jake at 5:35" came back
    parsed as an event for "Thursday June 11 at 5:35 AM" — the brain
    silently chose AM for a bare hour:minute spoken at 5:31 PM. The
    deterministic resolver was fixed to flag bare 1-12 with no am/pm as
    ambiguous; the prompt must also teach the LLM to mark `time_hint` as
    ambiguous in the same shape so the heuristic and LLM paths agree.
    Per the locked UX rule: missing/ambiguous info → one specific
    clarifying question, never a silent guess.
    """
    p = SYSTEM_PROMPT.lower()
    assert "am" in p and "pm" in p
    # The prompt must explicitly link the no-am/pm case to ambiguous_fields.
    assert "ambiguous_fields" in SYSTEM_PROMPT
    # And carry at least one concrete example of a bare-hour utterance so
    # the model has something to pattern-match against.
    assert "5:35" in SYSTEM_PROMPT or "5:35" in p
