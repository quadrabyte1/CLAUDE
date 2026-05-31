#!/usr/bin/env bash
# Migrate the Larry-team orchestration skeleton to a new Obsidian-vault working directory.
#
# Usage:
#   scripts/migrate_to_vault.sh <target_path> [--reset-db] [--dry-run]
#
# Copies only the orchestration substrate (CLAUDE.md, team/, db/, .claude/settings.local.json,
# _templates/, plus empty inbox/journal folders). Leaves all project-specific work behind.
#
#   --reset-db   Rebuild workspace.db from schema.sql instead of copying live DB.
#   --dry-run    Print what would happen; copy nothing.

set -euo pipefail

SRC="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"

TARGET=""
RESET_DB=0
DRY_RUN=0

while [[ $# -gt 0 ]]; do
  case "$1" in
    --reset-db) RESET_DB=1; shift ;;
    --dry-run)  DRY_RUN=1; shift ;;
    -h|--help)
      sed -n '2,12p' "$0"; exit 0 ;;
    -*)
      echo "Unknown flag: $1" >&2; exit 2 ;;
    *)
      if [[ -z "$TARGET" ]]; then TARGET="$1"; else
        echo "Unexpected arg: $1" >&2; exit 2
      fi
      shift ;;
  esac
done

if [[ -z "$TARGET" ]]; then
  echo "Usage: $0 <target_path> [--reset-db] [--dry-run]" >&2
  exit 2
fi

# Resolve target to an absolute path without requiring it to exist yet.
TARGET="$(cd "$(dirname "$TARGET")" 2>/dev/null && pwd)/$(basename "$TARGET")" \
  || { echo "Cannot resolve parent of target: $TARGET" >&2; exit 1; }

if [[ "$TARGET" == "$SRC"* ]]; then
  echo "Refusing to migrate into source tree: $TARGET" >&2
  exit 1
fi

run() {
  if [[ $DRY_RUN -eq 1 ]]; then
    echo "DRY  $*"
  else
    echo "RUN  $*"
    "$@"
  fi
}

echo "Source:  $SRC"
echo "Target:  $TARGET"
echo "Reset DB: $RESET_DB    Dry-run: $DRY_RUN"
echo

# 1. Create target tree.
run mkdir -p "$TARGET"
for d in team db _templates owner_inbox team_inbox journal .claude; do
  run mkdir -p "$TARGET/$d"
done

# 2. Files that copy verbatim.
copy_file() {
  local rel="$1"
  if [[ -e "$SRC/$rel" ]]; then
    run cp -p "$SRC/$rel" "$TARGET/$rel"
  else
    echo "skip (missing): $rel"
  fi
}

copy_dir() {
  local rel="$1"
  if [[ -d "$SRC/$rel" ]]; then
    # -a preserves perms + timestamps; trailing /. copies contents into the existing dir.
    run cp -a "$SRC/$rel/." "$TARGET/$rel/"
  else
    echo "skip (missing): $rel/"
  fi
}

copy_file "CLAUDE.md"
copy_dir  "team"
copy_dir  "_templates"
copy_file ".claude/settings.local.json"

# 3. DB: schema + migrations + init script always. workspace.db conditional.
copy_file "db/schema.sql"
copy_file "db/init_db.py"
copy_dir  "db/migrations"

if [[ $RESET_DB -eq 1 ]]; then
  echo
  echo "DB reset requested — initializing fresh workspace.db from schema."
  if [[ $DRY_RUN -eq 0 ]]; then
    ( cd "$TARGET" && python3 db/init_db.py )
  else
    echo "DRY  python3 db/init_db.py  (in $TARGET)"
  fi
else
  copy_file "db/workspace.db"
fi

# 4. .gitkeep stubs so empty folders survive git.
for d in owner_inbox team_inbox journal; do
  if [[ -z "$(ls -A "$TARGET/$d" 2>/dev/null)" ]]; then
    run touch "$TARGET/$d/.gitkeep"
  fi
done

# 5. Drop a tiny README at the target root pointing the next session at CLAUDE.md.
if [[ ! -e "$TARGET/README.md" && $DRY_RUN -eq 0 ]]; then
  cat > "$TARGET/README.md" <<'EOF'
# Larry workspace (Obsidian vault)

Orchestration substrate migrated from SHARED_WORK_FOLDER.
Start by reading `CLAUDE.md`. Team personas live in `team/`. Workspace DB at `db/workspace.db`.
EOF
  echo "WRITE README.md"
fi

echo
echo "Done."
if [[ $DRY_RUN -eq 0 && $RESET_DB -eq 0 ]]; then
  echo "Reminder: stale in-progress tasks may have carried over. Run a cleanup pass in the new vault."
fi
