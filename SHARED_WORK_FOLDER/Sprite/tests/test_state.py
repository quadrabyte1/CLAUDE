"""Tests for sprite.state — processed.jsonl idempotency and append behavior."""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path

import pytest

from sprite.state import file_key, is_processed, mark_processed


# ---------------------------------------------------------------------------
# file_key
# ---------------------------------------------------------------------------


def test_file_key_returns_16_hex_chars(tmp_path):
    f = tmp_path / "test.m4a"
    f.write_bytes(b"\x00" * 1024)
    key = file_key(f)
    assert len(key) == 16
    int(key, 16)  # must be valid hex


def test_file_key_is_deterministic(tmp_path):
    f = tmp_path / "test.m4a"
    f.write_bytes(b"abc" * 500)
    assert file_key(f) == file_key(f)


def test_file_key_differs_for_different_content(tmp_path):
    a = tmp_path / "a.m4a"
    b = tmp_path / "b.m4a"
    a.write_bytes(b"aaa" * 100)
    b.write_bytes(b"bbb" * 100)
    assert file_key(a) != file_key(b)


def test_file_key_uses_only_first_64kb(tmp_path):
    """Two files with same first 64 KB but different tails → same key."""
    prefix = b"X" * (64 * 1024)
    a = tmp_path / "a.m4a"
    b = tmp_path / "b.m4a"
    a.write_bytes(prefix + b"tail_a" * 1000)
    b.write_bytes(prefix + b"tail_b" * 1000)
    assert file_key(a) == file_key(b)


# ---------------------------------------------------------------------------
# is_processed / mark_processed
# ---------------------------------------------------------------------------


def test_is_processed_returns_false_when_file_missing(tmp_path):
    state_file = tmp_path / "state" / "processed.jsonl"
    assert not is_processed(state_file, "abc123")


def test_mark_then_is_processed(tmp_path):
    state_file = tmp_path / "processed.jsonl"
    mark_processed(state_file, "abc123", disposition="posted")
    assert is_processed(state_file, "abc123")


def test_mark_creates_parent_dirs(tmp_path):
    state_file = tmp_path / "deep" / "nested" / "processed.jsonl"
    mark_processed(state_file, "key1", disposition="inbox")
    assert state_file.exists()


def test_is_processed_returns_false_for_unknown_key(tmp_path):
    state_file = tmp_path / "processed.jsonl"
    mark_processed(state_file, "known_key", disposition="posted")
    assert not is_processed(state_file, "unknown_key")


def test_multiple_keys_coexist(tmp_path):
    state_file = tmp_path / "processed.jsonl"
    mark_processed(state_file, "key_a", disposition="posted")
    mark_processed(state_file, "key_b", disposition="inbox")
    mark_processed(state_file, "key_c", disposition="error")
    assert is_processed(state_file, "key_a")
    assert is_processed(state_file, "key_b")
    assert is_processed(state_file, "key_c")
    assert not is_processed(state_file, "key_d")


def test_mark_processed_entry_is_valid_json(tmp_path):
    state_file = tmp_path / "processed.jsonl"
    mark_processed(
        state_file,
        "testkey",
        audio_path="/tmp/x.m4a",
        record_id="rec123",
        disposition="posted",
        details={"verb": "note", "confidence": 0.85},
    )
    lines = [ln for ln in state_file.read_text().splitlines() if ln.strip()]
    assert len(lines) == 1
    row = json.loads(lines[0])
    assert row["key"] == "testkey"
    assert row["audio_path"] == "/tmp/x.m4a"
    assert row["record_id"] == "rec123"
    assert row["disposition"] == "posted"
    assert row["verb"] == "note"
    assert row["confidence"] == 0.85


def test_append_only_does_not_overwrite(tmp_path):
    """Each mark_processed appends; old lines are never removed."""
    state_file = tmp_path / "processed.jsonl"
    mark_processed(state_file, "first", disposition="posted")
    mark_processed(state_file, "second", disposition="inbox")
    lines = [ln for ln in state_file.read_text().splitlines() if ln.strip()]
    assert len(lines) == 2
    keys = [json.loads(l)["key"] for l in lines]
    assert keys == ["first", "second"]


def test_processed_at_is_utc_iso(tmp_path):
    state_file = tmp_path / "processed.jsonl"
    mark_processed(state_file, "k", disposition="posted")
    row = json.loads(state_file.read_text().strip())
    # Must parse as a valid UTC datetime.
    dt = datetime.fromisoformat(row["processed_at"])
    assert dt.tzinfo is not None
