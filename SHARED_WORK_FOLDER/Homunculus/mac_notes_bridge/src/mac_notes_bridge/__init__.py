"""
mac_notes_bridge — Push Herman vault notes to macOS Notes.app.

Version 0.1.0 — first release.

Design:
- Watches vault/notes/*.md for new files (watchdog + 60s periodic sweep).
- Parses YAML frontmatter (id, title, captured_at) from each file.
- Pushes note to Notes.app via AppleScript (make new note atomically).
- Idempotency: pushed.jsonl fast-path + title-based Notes.app query slow-path.
- Notes.app folder "Homunculus" must be created manually under iCloud.
  See docs/FIRST_RUN.md Step 1.
"""

VERSION = "0.1.0"
