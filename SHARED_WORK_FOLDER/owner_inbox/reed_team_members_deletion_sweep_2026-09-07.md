# Reed — team_members Deletion Sweep

**Date:** 2026-09-07
**Author:** Reed (Database Engineer / SQLite)
**Task ID:** 9

---

## TL;DR — Smoking Gun

Nothing "deleted" the 15 team_members rows. They **never existed on this volume**.

`/Volumes/GIT/CLAUDE/SHARED_WORK_FOLDER/db/workspace.db` is a **brand-new file** first created on **2026-09-06 22:16:23 UTC** when `app/app.py`'s `init_db()` ran against a missing DB path. `init_db()` sourced `db/schema.sql`, which contains only **one** seed row (`Larry`, id=1). Sienna (id=2) and Topo (id=3) were then created ad-hoc by ordinary `INSERT`s later that evening when Larry assigned them tasks 4 and 5. Everyone else was missing until you restored them from `team/README.md` this morning.

The evidence that the DB is genuinely new, not "partially wiped":

| Signal                                | Live `workspace.db`             | `workspace.db.bak-20260527T090121` |
|---------------------------------------|---------------------------------|--------------------------------------|
| File size                             | 114 688 B                       | 638 976 B                            |
| team_members count                    | 18 (3 before your restore)      | 17                                   |
| tasks count                           | 9 (all created ≥ 2026-09-06)    | 469                                  |
| activity_log count                    | 6                               | 460                                  |
| Oldest activity_log created_at        | 2026-09-06T22:16:53Z            | 2026-03-31T13:38:12Z                 |
| Newest activity_log created_at        | 2026-09-07T12:05:56Z            | 2026-05-25T18:24:51Z                 |
| Larry's `created_at`                  | 2026-09-06T22:16:23Z            | (much older)                         |

The live DB has **no history at all** between 2026-05-25 (last activity in the .bak) and 2026-09-06 22:16 (first activity in the live DB). That's a 3.5-month gap that no `DELETE FROM team_members` could produce — a DELETE would leave every other table intact. The whole DB is fresh.

## Root Cause

When the working folder was migrated onto the current external volume `/Volumes/GIT/CLAUDE/` on **2026-09-05 14:17–14:18**, the migration copied `db/workspace.db.bak-20260527T090121` (plus `-shm` and `-wal`) but **did NOT copy the live `db/workspace.db`** from the previous volume. `workspace.db` is git-ignored (commit `ef27fec` on 2026-07-15 removed it from the repo; `.gitignore` has `db/workspace.db` since commit `235c682`) so it wasn't tracked and wasn't recreated by `git checkout`.

On **2026-09-06 22:16:23 UTC** the Flask app started for the first time on this volume (see `app/logs/server.log` first line `06/Sep/2026 18:16:49 GET / HTTP/1.1 200` — 18:16 local ET = 22:16 UTC, matching Larry's row `created_at` to the second). `app/app.py:38–139 init_db()` ran on the missing path, `sqlite3.connect(DB_PATH)` created an empty file, and `db.executescript(open("db/schema.sql").read())` created every table with `CREATE TABLE IF NOT EXISTS` and inserted the single seed row on `db/schema.sql:178–179`:

```sql
INSERT OR IGNORE INTO team_members (id, name, role, status, persona_file, model)
VALUES (1, 'Larry', 'Orchestrator / Team Lead', 'active', 'team/larry.md', 'fable');
```

**Nothing else was seeded.** Sienna and Topo appear because ordinary `INSERT`s in later turns added them when Larry needed to assign tasks:

- Sienna's `created_at` = 2026-09-06T23:21:23Z, 6 s before task 4 was assigned to her at 23:21:29Z.
- Topo's  `created_at` = 2026-09-06T23:24:04Z, 7 s before task 5 was assigned to him at 23:24:11Z.

## Ranked Suspect List

| # | File:Line                                    | Verdict     | Reasoning                                                                                                                          |
|---|----------------------------------------------|-------------|------------------------------------------------------------------------------------------------------------------------------------|
| 1 | `app/app.py:38–139` `init_db()`              | **Cause**   | Sources `db/schema.sql` on every Flask startup. When run against a missing DB, creates all tables and seeds ONLY Larry. Never touches `team/`. |
| 2 | `db/schema.sql:178–179`                      | **Cause**   | The seed block seeds only Larry. Every other team member is expected to be present already. Not the deleter, but the reason the rebuilt DB was almost empty. |
| 3 | `scripts/migrate_to_vault.sh` (invoked earlier) | Contributing | If run without `--reset-db` it *is* supposed to copy `db/workspace.db` verbatim (line 110), but the copy never landed on `/Volumes/GIT/CLAUDE/`. Whoever did the volume migration used a different mechanism (rsync/Finder/etc.) that skipped the git-ignored file. |
| 4 | `db/init_db.py`                              | Cleared     | This script *would* have seeded all persona files (walks `team/` and does `INSERT OR IGNORE`). But it was NOT run on Sep 6 — its team_members rows would have `created_at ≈ Sep 6 evening` in bulk. Instead, only Larry has a Sep-6 22:16 timestamp; Sienna/Topo are hours later. If init_db.py had run, all 18 would be there.
| 5 | `scratch/task_669_verify.py:23–41`           | Cleared     | Sets `_TMP_DB` under `tempfile.mkdtemp`; monkey-patches `flask_app_mod.DB_PATH` before routes touch it. Does not touch live DB. Safe.
| 6 | `scripts/cleanup_after_migration.py`         | Cleared     | Only touches `tasks` (UPDATE status='cancelled') and `documents` (DELETE). Never touches `team_members`. Not the cause.
| 7 | `.claude/sync-larry-model.sh:19`             | Cleared     | Only `UPDATE team_members SET model=... WHERE id=1`. Not destructive.
| 8 | `MovieScanner/app.py:394–461`                | Cleared     | Deletes from `matches`, `runs`, `titles` in the *MovieScanner* DB (`MovieScanner/db/scanner.db`), not `workspace.db`.
| 9 | `db/hole_in_one_v0.3_schema.sql`             | Cleared     | Standalone schema for a different DB (`db/hole_in_one_v0.3.db`). Nothing applies it to `workspace.db`.
|10 | Launchd plists / login items                 | Cleared     | `com.thomas.close-session.plist` runs a read-only audit + one `INSERT INTO journal_entries` (`~/.local/bin/close_session.sh`). `~/.local/bin/start_web_servers.sh` just runs `python3 -u app.py` — but that IS the process that triggered `init_db()` on the missing file at 22:16 UTC.
|11 | `.git/` history                              | Cleared     | `git log --all -- 'db/workspace.db'` shows only `ef27fec take workspace.db out of the repo` on 2026-07-15. The file has been git-ignored ever since. No commits could have "restored" a partial DB.

## Guardrail Recommendations

These are Reed's suggested defenses. **None applied yet** — awaiting Thomas's go-ahead.

### 1. Boot-time integrity check in `app/app.py` (single most valuable)

In `init_db()`, right after sourcing `schema.sql`, compare `team_members` count to the persona files in `team/`. If short, print a loud warning to stderr **and** re-run the equivalent of `db/init_db.py`'s `seed_team_members()` (idempotent `INSERT OR IGNORE`). Catches the exact scenario that just happened.

```python
# End of init_db() — self-heal team_members from persona files
import glob
persona_files = [p for p in glob.glob(os.path.join(os.path.dirname(__file__), "..", "team", "*.md"))
                 if not os.path.basename(p).startswith("_") and os.path.basename(p).lower() != "readme.md"]
have = {r[0] for r in db.execute("SELECT name FROM team_members")}
missing = []
for p in persona_files:
    with open(p) as f:
        name = role = None
        for line in f:
            s = line.strip()
            if s.startswith("- **Name:**"): name = s.split("**Name:**")[1].strip()
            elif s.startswith("- **Role:**"): role = s.split("**Role:**")[1].strip()
            if name and role: break
    if name and role and name not in have:
        rel = "team/" + os.path.basename(p)
        db.execute("INSERT OR IGNORE INTO team_members (name, role, persona_file) VALUES (?,?,?)",
                   (name, role, rel))
        missing.append(name)
if missing:
    import sys
    print(f"[init_db] Self-healed team_members: added {missing}", file=sys.stderr)
    db.commit()
```

### 2. Fold `.bak` into `migrate_to_vault.sh` invariants

Add a post-copy assertion in `migrate_to_vault.sh` after `copy_file "db/workspace.db"`: if the target file is under 100 KB or its `team_members` count is < number of persona files in `team/`, bail out with a hard error. Prevents silent "the DB copy didn't happen" outcomes.

### 3. Nightly logical backup (in addition to file copy)

The existing `.bak-20260527T090121` was made 3+ months ago via file-copy — the timestamped filename suggests a manual `cp`. Reed recommends a nightly `sqlite3 db/workspace.db ".backup db/backups/workspace-$(date +%Y%m%d).db"` (SQLite's online backup API, safe against active WAL). Keep 7 daily + 4 weekly. Trigger from `com.thomas.close-session.plist` at 06:00 ET *before* the audit runs.

### 4. Trigger to block wholesale DELETE from `team_members`

```sql
CREATE TRIGGER IF NOT EXISTS trg_team_members_no_bulk_delete
BEFORE DELETE ON team_members
WHEN (SELECT COUNT(*) FROM team_members) > 3
     AND (SELECT COUNT(*) FROM team_members) - 1 < 3
BEGIN
  SELECT RAISE(ABORT, 'Refusing to delete team_members row that would leave < 3 rows');
END;
```

Useful *if* a rogue `DELETE FROM team_members` ever appears — but note it would NOT have prevented the actual incident, which was a fresh-DB-init, not a delete. So this is a belt-and-suspenders addition, not a fix.

### 5. Add `team_members` to a lightweight schema-plus-seed audit

Ship a `scripts/verify_workspace_db.py` that prints WARN if `SELECT COUNT(*) FROM team_members < number_of_team_files`. Wire it into the close-session launchd job so Thomas sees a red flag in the daily audit if the count drifts.

## Recommended Priority

1. **Guardrail #1** (self-heal on Flask boot) — 15 minutes of work, prevents recurrence directly.
2. **Guardrail #3** (nightly `.backup`) — 30 minutes, saves future incidents of any table loss.
3. **Guardrail #5** (audit) — 15 minutes, gives observability.
4. **Guardrails #2, #4** — optional, defense-in-depth.

## Files Inspected

- `/Volumes/GIT/CLAUDE/SHARED_WORK_FOLDER/app/app.py` (init_db 38–139; team_members refs 65–68, 129–134, 190, 210, 315, 554, 565, 571)
- `/Volumes/GIT/CLAUDE/SHARED_WORK_FOLDER/db/schema.sql` (16–26 CREATE, 178–179 seed)
- `/Volumes/GIT/CLAUDE/SHARED_WORK_FOLDER/db/init_db.py` (49–96 seed_team_members)
- `/Volumes/GIT/CLAUDE/SHARED_WORK_FOLDER/scripts/migrate_to_vault.sh` (96–111 DB block)
- `/Volumes/GIT/CLAUDE/SHARED_WORK_FOLDER/scripts/cleanup_after_migration.py`
- `/Volumes/GIT/CLAUDE/SHARED_WORK_FOLDER/scratch/task_669_verify.py`
- `/Volumes/GIT/CLAUDE/SHARED_WORK_FOLDER/.claude/sync-larry-model.sh`
- `/Volumes/GIT/CLAUDE/SHARED_WORK_FOLDER/app/logs/server.log` (first request 2026-09-06 18:16:49 local)
- `/Volumes/GIT/CLAUDE/SHARED_WORK_FOLDER/db/workspace.db.bak-20260527T090121` (17 rows, timestamped 2026-05-27)
- `~/Library/Logs/start_web_servers.log`
- `~/Library/LaunchAgents/*.plist`
- `git log --all` diffs touching `db/*`, `.gitignore`

## What Reed Did NOT Change

Per Larry's instructions, no code changes have been applied. All findings above are recommendations only.
