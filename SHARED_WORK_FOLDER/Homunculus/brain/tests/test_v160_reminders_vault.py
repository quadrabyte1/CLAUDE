"""Herman v1.6.0 — vault/reminders/ and verb=remind TDD suite.

RED-first tests (written before the implementation). They must FAIL against
v1.5.0 code and PASS after the v1.6.0 implementation.

What is under test:
  1. verb=remind accepted identically to verb=handle
  2. _handle_handle writes to vault/reminders/ not vault/calendar/
  3. No [handle] / [handle!] prefix on the stored file title
  4. criticality=critical → frontmatter tag criticality: critical
  5. verb=remind preserves the original verb value in the response
  6. vault/calendar/ is NOT written when verb=handle (or remind)
  7. The CaptureVerb enum carries REMIND
  8. Idempotency: remind + handle same (verb differs in record_id)

Rules:
  - Every test uses tmp_path for the vault. Never touches the live vault.
  - No real osascript, no real Ollama, no running services.
"""

from __future__ import annotations

import json
from datetime import datetime, timedelta
from pathlib import Path
from zoneinfo import ZoneInfo

import pytest
from fastapi.testclient import TestClient

from homunculus_brain import calendar as cal
from homunculus_brain import reminders as rem
from homunculus_brain.schemas import (
    CaptureCriticality,
    CaptureVerb,
)
from homunculus_brain.server import create_app


TZ = ZoneInfo("America/New_York")
NOW = datetime(2026, 9, 15, 9, 0, tzinfo=TZ)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _client(tmp_path: Path, monkeypatch) -> TestClient:
    monkeypatch.setenv("HOMUNCULUS_VAULT", str(tmp_path))
    monkeypatch.setenv("HOMUNCULUS_TZ", "America/New_York")
    monkeypatch.setenv("OLLAMA_BASE_URL", "http://127.0.0.1:1")
    monkeypatch.setenv(
        "SPRITE_WARNINGS_PATH",
        str(tmp_path / "sprite" / "warnings.md"),
    )
    monkeypatch.setenv("HOMUNCULUS_MIN_CONFIDENCE", "0.6")
    return TestClient(create_app())


def _base(verb: str = "handle", **overrides) -> dict:
    payload = {
        "verb": verb,
        "subject": "kiss the baby",
        "when": (NOW + timedelta(hours=3)).isoformat(),
        "criticality": "normal",
        "confidence": 0.9,
        "raw_transcript": "kiss the baby",
        "audio_path": "/tmp/test.m4a",
        "captured_at": NOW.isoformat(),
    }
    payload.update(overrides)
    return payload


# ---------------------------------------------------------------------------
# 1. CaptureVerb enum carries REMIND
# ---------------------------------------------------------------------------


def test_capture_verb_enum_has_remind():
    """CaptureVerb must have a REMIND member with value 'remind'."""
    assert CaptureVerb.REMIND.value == "remind"


# ---------------------------------------------------------------------------
# 2. verb=remind is accepted (HTTP 200)
# ---------------------------------------------------------------------------


def test_verb_remind_accepted_returns_200(tmp_path, monkeypatch):
    client = _client(tmp_path, monkeypatch)
    r = client.post("/capture/parsed", json=_base(verb="remind"))
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["stored"] is True


# ---------------------------------------------------------------------------
# 3. verb=remind writes to vault/reminders/ not vault/calendar/
# ---------------------------------------------------------------------------


def test_verb_remind_writes_to_vault_reminders_dir(tmp_path, monkeypatch):
    """_handle_handle must write to vault/reminders/, not vault/calendar/."""
    client = _client(tmp_path, monkeypatch)
    r = client.post("/capture/parsed", json=_base(verb="remind"))
    assert r.status_code == 200, r.text
    body = r.json()

    # vault/reminders/ must have a .md file
    reminders_dir = tmp_path / "reminders"
    md_files = list(reminders_dir.rglob("*.md"))
    assert md_files, "Expected a .md file in vault/reminders/"

    # vault/calendar/ must be empty (no handle events there)
    calendar_md = list((tmp_path / "calendar").rglob("*.md")) if (tmp_path / "calendar").exists() else []
    assert calendar_md == [], f"Expected no .md in vault/calendar/ for handle, got: {calendar_md}"


def test_verb_handle_writes_to_vault_reminders_dir(tmp_path, monkeypatch):
    """verb=handle must also write to vault/reminders/, not vault/calendar/."""
    client = _client(tmp_path, monkeypatch)
    r = client.post("/capture/parsed", json=_base(verb="handle"))
    assert r.status_code == 200, r.text

    reminders_dir = tmp_path / "reminders"
    md_files = list(reminders_dir.rglob("*.md"))
    assert md_files, "Expected a .md file in vault/reminders/"

    calendar_md = list((tmp_path / "calendar").rglob("*.md")) if (tmp_path / "calendar").exists() else []
    assert calendar_md == [], f"Expected no .md in vault/calendar/ for handle"


# ---------------------------------------------------------------------------
# 4. No [handle] / [handle!] title prefix in the written file
# ---------------------------------------------------------------------------


def test_handle_written_file_has_no_bracket_prefix(tmp_path, monkeypatch):
    """The vault/reminders/ file must NOT have [handle] or [handle!] in the title."""
    client = _client(tmp_path, monkeypatch)
    r = client.post("/capture/parsed", json=_base(verb="handle", subject="call the vet"))
    assert r.status_code == 200, r.text

    reminders_dir = tmp_path / "reminders"
    md_files = list(reminders_dir.rglob("*.md"))
    assert md_files, "No file found"
    content = md_files[0].read_text()
    assert "[handle]" not in content, f"[handle] prefix found in file: {content[:200]}"
    assert "[handle!]" not in content, f"[handle!] prefix found in file: {content[:200]}"


# ---------------------------------------------------------------------------
# 5. criticality=critical → frontmatter tag criticality: critical
# ---------------------------------------------------------------------------


def test_critical_handle_has_criticality_tag(tmp_path, monkeypatch):
    """A critical handle must write frontmatter with criticality: critical."""
    client = _client(tmp_path, monkeypatch)
    r = client.post(
        "/capture/parsed",
        json=_base(verb="handle", subject="drop off passport", criticality="critical"),
    )
    assert r.status_code == 200, r.text

    reminders_dir = tmp_path / "reminders"
    md_files = list(reminders_dir.rglob("*.md"))
    assert md_files
    content = md_files[0].read_text()
    assert "criticality: critical" in content, (
        f"Expected 'criticality: critical' in frontmatter. File content:\n{content[:300]}"
    )


def test_normal_handle_has_no_critical_tag(tmp_path, monkeypatch):
    """A normal (non-critical) handle must NOT write criticality: critical."""
    client = _client(tmp_path, monkeypatch)
    r = client.post(
        "/capture/parsed",
        json=_base(verb="handle", subject="water the plants", criticality="normal"),
    )
    assert r.status_code == 200, r.text

    reminders_dir = tmp_path / "reminders"
    md_files = list(reminders_dir.rglob("*.md"))
    assert md_files
    content = md_files[0].read_text()
    assert "criticality: critical" not in content, (
        f"Found unexpected 'criticality: critical' for normal criticality. "
        f"File content:\n{content[:300]}"
    )


# ---------------------------------------------------------------------------
# 6. verb value in response is preserved (remind → remind, not rewritten)
# ---------------------------------------------------------------------------


def test_verb_remind_preserved_in_response(tmp_path, monkeypatch):
    """The response verb must be 'remind', not rewritten to 'handle'."""
    client = _client(tmp_path, monkeypatch)
    r = client.post("/capture/parsed", json=_base(verb="remind"))
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["verb"] == "remind", (
        f"Expected verb='remind' preserved in response, got {body['verb']!r}"
    )


# ---------------------------------------------------------------------------
# 7. verb=remind creates a strike chain (same as handle)
# ---------------------------------------------------------------------------


def test_verb_remind_creates_strike_chain(tmp_path, monkeypatch):
    client = _client(tmp_path, monkeypatch)
    r = client.post(
        "/capture/parsed",
        json=_base(verb="remind", subject="pick up milk"),
    )
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["event_id"]

    rows = rem.read_event_rows(tmp_path, body["event_id"])
    kinds = {row.kind.value for row in rows}
    assert "strike_0" in kinds, f"No strike_0 in strike chain: {kinds}"
    assert "strike_15" in kinds, f"No strike_15 in strike chain: {kinds}"


# ---------------------------------------------------------------------------
# 8. vault/calendar/ still gets schedule events (regression guard)
# ---------------------------------------------------------------------------


def test_schedule_verb_still_writes_to_calendar(tmp_path, monkeypatch):
    """schedule verb must still write to vault/calendar/ (regression guard)."""
    client = _client(tmp_path, monkeypatch)
    r = client.post(
        "/capture/parsed",
        json=_base(verb="schedule", subject="dentist appointment"),
    )
    assert r.status_code == 200, r.text

    calendar_md = list((tmp_path / "calendar").rglob("*.md"))
    assert calendar_md, "schedule verb must write to vault/calendar/"

    reminders_md = list((tmp_path / "reminders").rglob("*.md")) if (tmp_path / "reminders").exists() else []
    assert reminders_md == [], f"schedule must NOT write to vault/reminders/"


# ---------------------------------------------------------------------------
# 9. critical remind bumps chain earlier (mirrors existing critical handle test)
# ---------------------------------------------------------------------------


def test_critical_remind_bumps_chain_earlier(tmp_path, monkeypatch):
    """A critical remind fires its head-of-chain earlier (same logic as critical handle)."""
    client = _client(tmp_path, monkeypatch)
    when = NOW + timedelta(hours=3)
    r = client.post(
        "/capture/parsed",
        json=_base(verb="remind", subject="renew passport", when=when.isoformat(), criticality="critical"),
    )
    assert r.status_code == 200, r.text
    body = r.json()

    rows = rem.read_event_rows(tmp_path, body["event_id"])
    strike_0 = next(row for row in rows if row.kind.value == "strike_0")
    # Critical shifts the underlying event 30 min earlier.
    assert strike_0.fire_at == when - timedelta(minutes=30)
