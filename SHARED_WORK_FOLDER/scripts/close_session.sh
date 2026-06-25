#!/bin/bash
# close_session.sh -- Daily close-session audit wrapper
# Invoked by launchd at 06:00 America/New_York via com.thomas.close-session.plist
# Baked-in absolute paths: launchd inherits no shell PATH.
#
# IMPORTANT -- macOS external-volume restriction:
# launchd cannot execute scripts that reside on non-boot APFS volumes (the GIT
# volume is mounted nosuid). The plist therefore points to a copy of this script
# at ~/.local/bin/close_session.sh (on the boot volume).
# After editing THIS file, re-sync with:
#   cp /Volumes/GIT/CLAUDE/SHARED_WORK_FOLDER/scripts/close_session.sh \
#      ~/.local/bin/close_session.sh && chmod +x ~/.local/bin/close_session.sh

# -- Environment --------------------------------------------------------------
export HOME="/Users/fourierflight"
export LANG="en_US.UTF-8"
export LC_ALL="en_US.UTF-8"
export PATH="/opt/homebrew/bin:/usr/local/bin:/usr/bin:/bin:/usr/sbin:/sbin"

# -- Binaries (absolute, resolved at install time) ----------------------------
CLAUDE="/opt/homebrew/bin/claude"
SQLITE3="/usr/bin/sqlite3"
FIND="/usr/bin/find"

# -- Repo root ----------------------------------------------------------------
REPO="/Volumes/GIT/CLAUDE/SHARED_WORK_FOLDER"
cd "$REPO" || { echo "ERROR: cannot cd to $REPO"; exit 1; }

# -- Log directory ------------------------------------------------------------
TODAY="$(date +%Y-%m-%d)"
LOG_DIR="$HOME/Library/Logs/close-session"
mkdir -p "$LOG_DIR"
LOG_FILE="$LOG_DIR/audit-${TODAY}.log"

# -- Audit prompt (saved to temp file; avoids heredoc + Unicode issues) -------
PROMPT_FILE="/tmp/close_session_prompt_${TODAY}.txt"

# Write the prompt as a Python script to avoid shell Unicode escaping issues
python3 - "$PROMPT_FILE" <<'PYEOF'
import sys
path = sys.argv[1]
prompt = u"""You are a daily close-session audit agent for Thomas's CLAUDE workspace
project. Strict scope: read-only DB queries + ONE INSERT into journal_entries
+ write ONE markdown report file. No code changes, no test runs, no
sub-agent dispatches, no other DB mutations. Target <=5 min.

CWD is /Volumes/GIT/CLAUDE/SHARED_WORK_FOLDER. DB is db/workspace.db. Use
sqlite3 via Bash. Set TODAY=$(date +%Y-%m-%d).

STEP 1 -- Stale in_progress tasks (>24h since started_at):
  sqlite3 db/workspace.db "SELECT id, title, assigned_to, started_at FROM tasks
    WHERE status='in_progress' AND started_at < datetime('now','-24 hours')
    ORDER BY started_at;"

STEP 2 -- Yesterday's completions:
  sqlite3 db/workspace.db "SELECT id, title, assigned_to, completed_at FROM tasks
    WHERE status='done' AND date(completed_at)=date('now','-1 day')
    ORDER BY completed_at;"

STEP 3 -- If any completions, append to journal_entries (write SQL to /tmp/journal.sql
then `sqlite3 db/workspace.db < /tmp/journal.sql`, escaping single quotes as ''):
  INSERT INTO journal_entries (date, title, content)
    VALUES (date('now'), 'Close-Session Roll-up', '<markdown bullet list>')
    ON CONFLICT(date) DO UPDATE SET
      content = journal_entries.content || char(10) || char(10) || excluded.content,
      updated_at = strftime('%Y-%m-%dT%H:%M:%SZ','now');

STEP 4 -- Uncatalogued owner_inbox files (mtime <24h, no matching task):
  find owner_inbox -type f -mtime -1 -not -name '.DS_Store' -not -name '.gitkeep'
  For each path, basename=$(basename "$f"):
    sqlite3 db/workspace.db "SELECT id FROM tasks
      WHERE description LIKE '%$basename%' OR title LIKE '%$basename%' LIMIT 1;"
  If empty result, mark uncatalogued.

STEP 5 -- Write owner_inbox/close_session_${TODAY}.md:

  # Close-Session Audit -- ${TODAY}

  \U0001F7E6 **IMPORTANT** -- Daily 06:00 ET read-only audit + journal append.

  \U0001F7E7 **NEEDS YOUR INPUT**
  > **Stale in_progress tasks (>24h):**
  > - <list or "None">
  >
  > **Uncatalogued owner_inbox files (last 24h, no matching task):**
  > - <list or "None">

  \U0001F7E9 **AGENT REPORT**
  **Yesterday's completed work (<yesterday's date>):**
  - <list or "No tasks marked done yesterday">

  **Journal entry:** <appended / created new / skipped (no completions)>.

  **Audit runtime:** ~<N>s.

STEP 6 -- Exit. No commits, no pushes, no other work.

Emoji prefix convention (use exactly these glyphs):
\U0001F7E6 IMPORTANT | \U0001F7E5 PROBLEM | \U0001F7E7 NEEDS YOUR INPUT | \U0001F7E9 AGENT REPORT
"""
with open(path, 'w', encoding='utf-8') as f:
    f.write(prompt)
print("prompt written to " + path)
PYEOF

if [ ! -f "$PROMPT_FILE" ]; then
    echo "ERROR: failed to write prompt file $PROMPT_FILE" >> "$LOG_FILE"
    exit 1
fi

# -- Invoke claude CLI in non-interactive print mode --------------------------
# -p / --print: print response and exit (non-interactive)
# --dangerously-skip-permissions: launchd session has no TTY for permission prompts
# Prompt is passed via stdin; stdout+stderr go to the dated log
"$CLAUDE" \
    --print \
    --dangerously-skip-permissions \
    < "$PROMPT_FILE" \
    >> "$LOG_FILE" 2>&1

EXIT_CODE=$?

if [ $EXIT_CODE -ne 0 ]; then
    echo "$(date -u +%Y-%m-%dT%H:%M:%SZ) ERROR: claude exited with code $EXIT_CODE" >> "$LOG_FILE"
fi

# -- Cleanup ------------------------------------------------------------------
rm -f "$PROMPT_FILE"

exit $EXIT_CODE
