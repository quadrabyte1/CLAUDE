# Silent-Loss Bug Fixes — 2026-09-14

<!-- mac_calendar_bridge v0.1.3 · Sprite v0.6.0 -->

---

## Package Versions

| Package | Before | After |
|---|---|---|
| mac_calendar_bridge | 0.1.2 | **0.1.3** |
| Sprite | 0.5.0 | **0.6.0** |

---

## Bug 1 — mac_calendar_bridge: Missed atomic-rename events (fixed in v0.1.3)

### Root Cause

Herman writes vault events atomically: it writes `<file>.md.tmp.<PID>.<N>`, then calls `os.replace` to rename it to `<file>.md`. This is correct and intentional.

The bridge's watchdog handler only implemented `on_created`. When Herman's `.tmp` file appeared, watchdog fired `on_created`; the bridge saw the `.tmp` extension, fell through the "not `.md`" check, and silently did nothing — no log, no error. When `os.replace` fired the MOVE event (src=`.tmp`, dest=`.md`), the bridge had no `on_moved` handler, so watchdog discarded it. The final `.md` was never pushed to Calendar.app.

This is why the Sept 15 "second-meeting-with-myself" event landed in the vault at 16:53:14 but never appeared in Calendar.app.

### Fixes Applied

1. **`on_moved` handler added** — when the MOVE destination is a `.md` file, the bridge calls `push_if_new` on the destination. This is the primary fix for the atomic-rename path.

2. **Explicit `.tmp` guard** — `on_created` now explicitly detects `.tmp` files and logs `DEBUG: "Skipping temp file: <name>"` instead of falling through silently. Future readers and debuggers can see what the bridge is ignoring and why.

3. **Periodic sweep** — a new `periodic_sweep()` function + background daemon thread fires every 60 seconds. It scans the vault for any `.md` not in `pushed.jsonl` and pushes them. If watchdog misses any event for any reason (bug, dropped inotify, OS glitch), the sweep catches it within 60 seconds. Logs at DEBUG when nothing is new; INFO when it finds and dispatches.

4. **Version bump** — `0.1.2 → 0.1.3` in `__init__.py` and `pyproject.toml`.

### Red → Green Summary (7 new tests)

| Test | Before | After |
|---|---|---|
| `test_on_moved_md_destination_dispatches` | FAIL (ImportError / no handler) | PASS |
| `test_on_moved_non_md_destination_ignored` | FAIL | PASS |
| `test_on_moved_directory_ignored` | FAIL | PASS |
| `test_on_created_tmp_file_not_dispatched` | FAIL (no log message) | PASS |
| `test_periodic_sweep_pushes_missed_event` | FAIL (ImportError) | PASS |
| `test_periodic_sweep_skips_already_pushed` | FAIL | PASS |
| `test_periodic_sweep_returns_zero_on_empty_vault` | FAIL | PASS |
| All 130 prior tests | PASS | PASS |

**Total: 137 passed, 2 skipped (the 2 skipped are pre-existing `test_v012_no_account` tests unrelated to these bugs).**

---

## Bug 2 — Sprite: Clarifying questions silently swallowed (fixed in v0.6.0)

### Root Cause

Sprite's `watcher.py` `process_file()` treated any HTTP 200 from Herman as a successful store. After the `post_to_herman()` call, it immediately called `mark_processed(..., disposition="posted")` without inspecting `response.stored`.

Herman's `ParsedCaptureResponse` schema has `stored: bool` as the first field. When Herman cannot resolve an ambiguous time expression (e.g. "10 o'clock" — AM or PM unknown), it returns HTTP 200 with `stored=False`, `clarifying_question="10 o'clock — AM or PM?"`, and `ambiguous_fields=["time"]`. Sprite ignored all of this, wrote `disposition="posted"` with `event_id=null`, and the user never saw the clarifying question anywhere.

The stuck record `f252391221d7037fff9cee8adec821b7` (key `21712b6781ee3791`) is evidence of this: `disposition="posted"`, `event_id=null` — an impossible combination for a successfully scheduled event.

### Fixes Applied

1. **`watcher.py`** — after `post_to_herman()` returns, inspect `herman_resp.stored`. If `False`, route to `inbox.append_to_inbox()` with `clarifying_question`, `day_hint`, `time_hint`, and mark state as `disposition="clarifying"`. Never reach the `"posted"` path when `stored=False`.

2. **`inbox.py`** — `append_to_inbox()` gains a `clarifying_question` parameter. When set, the entry renders with a prominent `⚠️  Awaiting clarification` disposition badge, the parsed intent fields (verb, subject, day hint, time hint), the raw transcript in a blockquote, and the clarifying question in bold (`**Herman asks:** ...`). The standard ambiguous/low-confidence format is unchanged.

3. **`state.py`** — added docstring for the new `"clarifying"` disposition:
   - `"posted"` = stored=True, event_id present (success)
   - `"clarifying"` = stored=False, Herman asked a question (processed but not stored; cold-boot skips it, inbox has the question)
   - `"inbox"` = failed the confidence gate before Herman was ever called
   - `"error"` = pipeline failure

4. **Version bumps** — `pyproject.toml`: `0.5.0 → 0.6.0`; `watcher.py` startup log; `__init__.py`.

### Red → Green Summary (6 new tests)

| Test | Before | After |
|---|---|---|
| `test_clarifying_question_writes_inbox_entry` | FAIL (no inbox file created) | PASS |
| `test_clarifying_question_disposition_is_clarifying` | FAIL (`"posted"` in state) | PASS |
| `test_clarifying_question_inbox_contains_question_bold` | FAIL | PASS |
| `test_clarifying_question_cross_repo_wire_shape` | PASS (wire shape was already correct; test confirms it) | PASS |
| `test_successful_post_still_marks_posted` | PASS (regression guard) | PASS |
| `test_never_mark_posted_when_event_id_is_none` | FAIL (invariant violated) | PASS |
| All 115 prior tests | PASS | PASS |

**Total: 121 passed.**

---

## Thomas's Migration Steps

### 1. Reinstall mac_calendar_bridge + bounce launchd

```bash
cd /Volumes/GIT/CLAUDE/SHARED_WORK_FOLDER/Homunculus/mac_calendar_bridge
pip install -e . --quiet
launchctl unload ~/Library/LaunchAgents/com.homunculus.mac_calendar_bridge.plist 2>/dev/null || true
launchctl load  ~/Library/LaunchAgents/com.homunculus.mac_calendar_bridge.plist
```

### 2. Reinstall Sprite + bounce launchd

```bash
cd /Volumes/GIT/CLAUDE/SHARED_WORK_FOLDER/Sprite
pip install -e . --quiet
launchctl unload ~/Library/LaunchAgents/com.sprite.watcher.plist 2>/dev/null || true
launchctl load  ~/Library/LaunchAgents/com.sprite.watcher.plist
```

### 3. Fix the stuck ambiguous record (two options — recommend Option B)

**Option A — Flip in place:**
Find the line with `"key":"21712b6781ee3791"` in `~/sprite/state/processed.jsonl` and change `"disposition":"posted"` to `"disposition":"clarifying"`. You can do this with any text editor — the file is JSONL, one record per line.

**Option B — Delete and reprocess (recommended):**
Delete the line with `"key":"21712b6781ee3791"` from `~/sprite/state/processed.jsonl`. Cold-boot will re-parse the original `.m4a`, re-run it through the pipeline, POST to Herman again, and this time Sprite v0.6.0 will correctly write the clarifying question to the inbox.

```bash
# Find which line it is first:
grep -n "21712b6781ee3791" ~/sprite/state/processed.jsonl

# Delete that line (replace LINE_NUMBER with the actual number):
sed -i '' 'LINE_NUMBERd' ~/sprite/state/processed.jsonl
```

Then bounce Sprite (step 2 above) — cold-boot will pick it up within a few seconds.

### 4. Confirm Sprite writes the clarifying question to inbox

After Sprite restarts, watch the inbox directory:

```bash
tail -f ~/sprite/inbox/*.md
```

You should see an entry appear for "another meeting with myself" with `⚠️  Awaiting clarification` and `**Herman asks:** 10 o'clock — AM or PM?`

### 5. Watch both logs to confirm the fixes took effect

```bash
# Bridge log — look for "Atomic rename detected" and "periodic sweep" lines:
tail -f /tmp/mac_calendar_bridge.log

# Sprite log:
tail -f /tmp/sprite_watcher.log
```

### 6. Sept 15 "second-meeting" event will backfill within 60 seconds

When mac_calendar_bridge v0.1.3 starts up, the cold-boot sweep will find the `2026-09-15-second-meeting-with-myself.md` vault file (not in `pushed.jsonl`) and push it to Calendar.app immediately. If for any reason it missed it, the periodic sweep fires at T+60s and catches it. You should see the event in Calendar.app within a minute of bouncing the bridge.

---

## What v0.2 / v0.7 Should Address

### mac_calendar_bridge v0.2

- **Two-way idempotency check** via `query_pushed_event_ids()`: on startup (or periodically), query Calendar.app for existing Homunculus events and reconcile `pushed.jsonl`. This catches the case where `pushed.jsonl` was deleted but Calendar.app still has the events.
- **MODIFIED event de-duplication**: the current `on_modified` handler re-parses the file on every modify. A short debounce (1–2 s) would reduce redundant AppleScript calls if Herman updates a file rapidly.
- **Structured JSON log format**: the current log is plaintext. Switching to JSON-lines would make it trivial to grep for specific event_ids or visualize activity.

### Sprite v0.7

- **Clarification re-POST**: surface a mechanism for Thomas to answer Herman's clarifying question and re-POST. Current v0.6.0 writes the question to inbox — the user sees it, but must manually re-capture. v0.7 should let the user answer ("set it for 10 AM") via a new voice memo that references the pending record.
- **Inbox acknowledgment**: a simple `/ack` command or UI that marks a `"clarifying"` record as resolved so it doesn't surface repeatedly.
- **`"posted_no_event"` disposition**: for `note` and `avoid` verbs where `event_id` is legitimately null even on success — removes the `event_id=null` ambiguity that the v0.6.0 invariant test guards against.
- **Replay from inbox**: `scripts/replay_from_inbox.py` — scan inbox files, find `⚠️  Awaiting clarification` entries, and interactively re-POST with a resolved time.
