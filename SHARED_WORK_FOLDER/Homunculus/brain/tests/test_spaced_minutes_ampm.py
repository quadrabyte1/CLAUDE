"""Regression: whisper-style '8 30 p.m.' (space, no colon) must keep its AM/PM marker."""
from datetime import datetime
from zoneinfo import ZoneInfo

import pytest

from homunculus_brain import date_resolver as dr

TZ = ZoneInfo("America/New_York")
NOW = datetime(2026, 10, 14, 18, 52, tzinfo=TZ)


def _r(time_hint, context_text=None):
    return dr.resolve("today", time_hint, NOW, TZ, verb="remind", context_text=context_text)


@pytest.mark.parametrize("hint", [
    "8 30 p.m.", "8 30 pm", "8:30 p.m.", "8 30 p.m. dinner.", "at 8 30 P.M.", "8 30 PM.",
    "8.30 pm", "20:30",
])
def test_hint_pm_resolves_2030(hint):
    r = _r(hint)
    assert not r.ambiguous, r
    assert (r.resolved_at.hour, r.resolved_at.minute) == (20, 30)


@pytest.mark.parametrize("hint", ["8 30 a.m.", "8 30 AM."])
def test_hint_am_resolves_0830(hint):
    r = _r(hint)
    assert not r.ambiguous, r
    assert (r.resolved_at.hour, r.resolved_at.minute) == (8, 30)


def test_bare_hint_with_marker_only_in_transcript():
    r = _r("8 30", context_text="Set a reminder for today at 8 30 p.m. dinner.")
    assert not r.ambiguous, r
    assert (r.resolved_at.hour, r.resolved_at.minute) == (20, 30)


def test_spaced_minutes_without_marker_still_ambiguous_or_not_guessed_wrong():
    # No marker, no context: must not silently become a bare 8:30 AM guess without asking.
    r = dr.resolve("tomorrow", "8 30", NOW, TZ, verb="remind")
    assert r.ambiguous


def test_oclock_normalisation_kept():
    r = _r("9 o'clock a.m.")
    assert not r.ambiguous and (r.resolved_at.hour, r.resolved_at.minute) == (9, 0)
