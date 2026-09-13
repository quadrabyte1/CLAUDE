#!/bin/bash
# Stop hook: block Claude from finishing a turn if it edited any file under
# app/ (.py or .html) without bumping APP_VERSION in app/app.py.
#
# Rationale: Thomas's rule — every web-page-adjacent change must tick
# APP_VERSION so a browser reload reflects the change on the sticky footer.
# See memory: feedback_web_page_version_bump.md
set -u
cd "${CLAUDE_PROJECT_DIR:-.}" || exit 0

# Any changes at all in the working tree under app/ (.py or .html)?
# The repo root can be above CLAUDE_PROJECT_DIR (Thomas's SHARED_WORK_FOLDER
# lives one level deep in the /Volumes/GIT/CLAUDE repo), so `git status`
# emits paths like SHARED_WORK_FOLDER/app/app.py. We strip any prefix by
# grep -oE 'app/…'  so the check works regardless of nesting depth.
touched=$(git status --porcelain 2>/dev/null \
          | grep -oE 'app/[^[:space:]]+\.(py|html)$' \
          | sort -u \
          || true)

if [ -z "$touched" ]; then
  exit 0
fi

# Was APP_VERSION's value changed anywhere in the diff?
# APP_VERSION only appears in app/app.py, so a global grep is safe and
# sidesteps repo-root-vs-project-dir path questions entirely.
if git diff HEAD 2>/dev/null | grep -qE '^\+.*APP_VERSION *='; then
  exit 0
fi

# Touched app/ files, but no APP_VERSION bump — block the stop so Claude fixes it.
# Turn the file list into a single JSON-safe string (comma-joined).
files_csv=$(echo "$touched" | tr '\n' ',' | sed 's/,$//')
printf '{"decision":"block","reason":"You edited files under app/ (Python or HTML) without bumping APP_VERSION in app/app.py. Tick APP_VERSION up by one minor version (e.g. v4.52 → v4.53) before finishing this turn. Rule: every web-page-adjacent change must tick APP_VERSION so a browser reload reflects the change on the sticky footer. Files touched: %s"}\n' "$files_csv"
