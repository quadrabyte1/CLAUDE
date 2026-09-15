# mac_calendar_bridge v0.1.4 — display_title: clean Calendar surface

**v0.1.4** | Rune | 2026-09-14

---

## Root cause

Herman writes vault titles like `[handle] review the Homunculus enhancement list` deliberately. The `[handle]` / `[handle!]` prefix is a vault-semantic marker: it tells a human browsing markdown files "this is a to-do, not a meeting." That design is correct and intentional — the brain code is untouched.

The problem is that the bridge was passing `event.title` verbatim to the AppleScript `summary:` field in `push_event()`. Calendar.app, iCloud, iPhone, and Apple Watch all display that summary as-is, so you were seeing `[handle] review the Homunculus enhancement list` on your phone.

The bridge is where the translation belongs.

---

## Fix

Added a `display_title` computed property to `EventRecord` in `vault_reader.py`:

| Vault title | Calendar display |
|---|---|
| `[handle] review the list` | `✓ review the list` |
| `[handle!] call the deck contractor` | `🔥 call the deck contractor` |
| `meeting with myself` | `meeting with myself` (unchanged) |

Updated `push_event()` in `applescript.py` to use `event.display_title` instead of `event.title` when building the AppleScript `summary:` string.

The raw `title` field on `EventRecord` is never mutated — vault truth is preserved.

---

## Red → green (TDD)

18 new tests written **before** the implementation, confirmed failing, then green:

**`TestDisplayTitle`** (15 tests):
- `[handle]` prefix stripped, `✓` prepended
- `[handle!]` prefix stripped, `🔥` prepended
- Regular event title passes unchanged
- `[handle]` mid-subject (not leading) is left alone
- `[handle]` in subject-only form (no trailing text) → `✓` / `🔥`
- Extra whitespace between prefix and subject is collapsed
- Raw `.title` field is not mutated

**`TestPushEventUsesDisplayTitle`** (3 tests — regression guard):
- `push_event` with `[handle]` title → AppleScript contains `✓ ...`, not `[handle] ...`
- `push_event` with `[handle!]` title → AppleScript contains `🔥 ...`, not `[handle!] ...`
- `push_event` with regular title → passes through unchanged

**`TestParseEventFile` integration** (2 tests inside `TestDisplayTitle`):
- Vault file with `[handle]` frontmatter → `display_title` uses `✓`
- Vault file with `[handle!]` frontmatter → `display_title` uses `🔥`

Full suite before: **137 passed, 2 skipped**
Full suite after: **155 passed, 2 skipped**

---

## Files changed

- `Homunculus/mac_calendar_bridge/src/mac_calendar_bridge/vault_reader.py` — `display_title` property added to `EventRecord`
- `Homunculus/mac_calendar_bridge/src/mac_calendar_bridge/applescript.py` — `push_event` uses `display_title`; log line shows both vault title and display title
- `Homunculus/mac_calendar_bridge/src/mac_calendar_bridge/__init__.py` — VERSION bumped to `0.1.4`
- `Homunculus/mac_calendar_bridge/pyproject.toml` — version bumped to `0.1.4`
- `Homunculus/mac_calendar_bridge/tests/test_vault_reader.py` — 18 new tests added

---

## Migration: fixing the bad titles already in your Calendar

You have at least one event sitting in iCloud with the ugly `[handle]` title. Two options:

### Option A — Delete and repush (recommended, cleanest)

1. Open **Calendar.app**, find `[handle] review the Homunculus enhancement list`, delete it.
2. Delete the bridge's pushed-state file so it re-pushes everything on next cold sweep:
   ```
   rm ~/.local/share/mac_calendar_bridge/pushed.jsonl
   ```
3. Reinstall the bridge at v0.1.4:
   ```
   pip install -e /Volumes/GIT/CLAUDE/SHARED_WORK_FOLDER/Homunculus/mac_calendar_bridge
   ```
4. Bounce the bridge (launchctl unload / load, or just restart the process). The cold-boot sweep will re-push all events with clean titles.

### Option B — Let them age out

Just deploy v0.1.4 and any future events will have clean titles. Existing `[handle]` events stay as-is until you rename or delete them manually in Calendar.app. This is fine if the existing bad events are already done/irrelevant.

**Recommendation: Option A.** The event you recorded ("review the Homunculus enhancement list") is likely still active. A clean title on your phone is worth the two-minute cleanup.

---

## House rules honored

- Herman brain code (`capture_parsed.py`) untouched — vault semantics preserved.
- Sprite untouched.
- No real `osascript` called in tests — `subprocess.run` mocked throughout.
- No Calendar data deleted from code — Thomas controls deletion.
