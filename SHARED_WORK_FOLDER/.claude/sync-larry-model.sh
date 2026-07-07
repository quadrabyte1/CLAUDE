#!/bin/zsh
# Reads the current model from ~/.claude/settings.json and syncs Larry's
# model tier to the workspace DB, team/larry.md, and team/README.md.

MODEL=$(jq -r '.model // ""' ~/.claude/settings.json 2>/dev/null || echo "")

case "$MODEL" in
  *fable*)  TIER="fable" ;;
  *opus*)   TIER="opus" ;;
  *sonnet*) TIER="sonnet" ;;
  *haiku*)  TIER="haiku" ;;
  *)        exit 0 ;;
esac

DB="/Volumes/GIT/CLAUDE/SHARED_WORK_FOLDER/db/workspace.db"
LARRY_MD="/Volumes/GIT/CLAUDE/SHARED_WORK_FOLDER/team/larry.md"
README_MD="/Volumes/GIT/CLAUDE/SHARED_WORK_FOLDER/team/README.md"

sqlite3 "$DB" "UPDATE team_members SET model='$TIER', updated_at=strftime('%Y-%m-%dT%H:%M:%SZ','now') WHERE id=1;" 2>/dev/null

python3 - "$TIER" "$LARRY_MD" "$README_MD" <<'PYEOF'
import re, sys
tier, larry_md, readme_md = sys.argv[1], sys.argv[2], sys.argv[3]

with open(larry_md, 'r') as f:
    c = f.read()
c = re.sub(r'(- \*\*Model:\*\* )\w+', r'\g<1>' + tier, c)
with open(larry_md, 'w') as f:
    f.write(c)

with open(readme_md, 'r') as f:
    c = f.read()
c = re.sub(r'(\| \*\*Larry\*\* \| Orchestrator & Team Lead \| )\w+', r'\g<1>' + tier, c)
with open(readme_md, 'w') as f:
    f.write(c)
PYEOF
