"""Atomic writes + inbox lock (v1.2 item 2).

The vault sits at the bottom of every capture. Two things must hold:

  (a) Every mutation is atomic at the filesystem level — a crash during
      write must never leave a half-written event file. The implementation
      writes to a tmp sibling and ``os.replace``s onto the target.
  (b) The inbox append is serialized by a POSIX file lock so two
      concurrent captures cannot interleave or write the header twice.
"""

from __future__ import annotations

import threading
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

from homunculus_brain import vault


TZ = ZoneInfo("America/New_York")


def test_write_markdown_uses_tmp_and_replace(tmp_path: Path, monkeypatch):
    """Plant a sentinel at the target path before write; assert the write
    replaces it (the new content wins), and no leftover .tmp.* sibling
    survives a successful write."""
    target = tmp_path / "calendar" / "2026-06" / "test.md"
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text("sentinel from a prior crashed write", encoding="utf-8")
    assert target.read_text() == "sentinel from a prior crashed write"

    vault.write_markdown(
        target,
        {"id": "x", "title": "x"},
        "# fresh body",
    )
    text = target.read_text(encoding="utf-8")
    assert "# fresh body" in text
    assert "sentinel" not in text

    # No leftover tmp sibling.
    siblings = list(target.parent.iterdir())
    tmp_leftovers = [p for p in siblings if ".tmp." in p.name]
    assert tmp_leftovers == [], f"tmp files survived: {tmp_leftovers}"


def test_write_markdown_no_partial_file_on_failure(tmp_path: Path, monkeypatch):
    """If the atomic write raises mid-flight, the target must be untouched
    (it may not exist at all). We monkeypatch ``os.replace`` to simulate
    failure after the tmp file is written; the target must not contain the
    half-written content."""
    import os as _os

    target = tmp_path / "calendar" / "2026-06" / "fail.md"

    def boom(src, dst):
        raise OSError("simulated rename failure")

    monkeypatch.setattr(vault.os, "replace", boom)

    try:
        vault.write_markdown(target, {"id": "x", "title": "x"}, "# never lands")
    except OSError:
        pass

    # Target must not exist (write never succeeded).
    assert not target.exists()
    # No stray tmp left behind (cleanup ran).
    if target.parent.exists():
        leftovers = list(target.parent.iterdir())
        assert leftovers == [], f"tmp files survived a failed write: {leftovers}"


def test_reminder_schedule_write_is_atomic(tmp_path: Path):
    """write_reminder_schedule uses the same atomic path."""
    schedule = [{"event_id": "x", "kind": "strike_0", "fire_at": "2026-06-12T10:00:00-04:00",
                 "tz": "America/New_York", "body": "go", "status": "pending"}]
    target = vault.reminder_path(tmp_path, "x")
    # Plant a corrupted prior version.
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text("{not json", encoding="utf-8")
    vault.write_reminder_schedule(tmp_path, "x", schedule)
    # Now valid JSON.
    import json
    loaded = json.loads(target.read_text())
    assert loaded["event_id"] == "x"


def test_inbox_concurrent_appends_serialize(tmp_path: Path):
    """Two threads append to the inbox simultaneously. Both lines must
    land intact and the header must appear exactly once."""
    now = datetime(2026, 6, 8, 12, 0, tzinfo=TZ)
    # Lots of appenders so any race is overwhelmingly likely to surface.
    N = 20

    def appender(i: int):
        vault.append_inbox(
            tmp_path,
            now,
            f"raw text from thread {i}",
            best_guess="unknown",
            reason=f"thread {i}",
        )

    threads = [threading.Thread(target=appender, args=(i,)) for i in range(N)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()

    content = (tmp_path / "inbox.md").read_text(encoding="utf-8")
    # Exactly one header.
    assert content.count("# Homunculus Inbox") == 1
    # Every appender's line landed.
    for i in range(N):
        assert f"raw text from thread {i}" in content, f"thread {i} missing"
        assert f"Reason: thread {i}" in content


def test_inbox_lock_does_not_corrupt_under_many_writes(tmp_path: Path):
    """Sanity: after many serial appends through the locked helper, the
    file is well-formed (every entry's three lines are present)."""
    now = datetime(2026, 6, 8, 12, 0, tzinfo=TZ)
    for i in range(50):
        vault.append_inbox(tmp_path, now, f"entry {i}", best_guess=None, reason=f"r{i}")

    text = (tmp_path / "inbox.md").read_text(encoding="utf-8")
    # 50 entries each have a '## ' header + a "Best guess:" + a "Reason:" line.
    assert text.count("## ") == 50
    assert text.count("- Best guess:") == 50
    assert text.count("- Reason:") == 50
