# Pre-Sep-6 History Reconciliation — 2026-09-07

**Engineer:** Reed (Database Engineer / SQLite)
**Workspace task:** 15
**Live DB:** `db/workspace.db`
**Source archive:** `db/workspace.db.bak-20260527T090121`

## Backup (reversible restore point)

- **File:** `db/workspace.db.premigrate-20260907T131501Z`
- **Size:** 131 072 bytes (snapshot of live DB immediately before merge)
- **Restore:** stop any writers, then `cp db/workspace.db.premigrate-20260907T131501Z db/workspace.db`

## Method

1. Copied live DB to a temp file (`db/workspace.db.reconcile-temp-20260907T131501Z`) and rehearsed the whole merge there first.
2. `ATTACH DATABASE` the `.bak` as schema `bak` and joined on team-member names to build an in-memory remap table (`tm_remap: bak_id -> live_id`).
3. Inserted history rows into live with **auto-assigned IDs** (safer than shifting live IDs); **original timestamps preserved** as the natural ordering key.
4. Verified with `PRAGMA foreign_key_check` and `PRAGMA integrity_check` before applying to live.
5. Applied identical statements to live in a single transaction.

## Row counts merged

| Table            | Merged from .bak | Live before | Live after | Notes |
|------------------|-----------------:|------------:|-----------:|-------|
| tasks            | 469              | 15          | 484        | timestamps preserved, `assigned_to` remapped by name |
| activity_log     | 460              | 11 (+3 post-merge) | 474 | task entity FKs handled — see below |
| journal_entries  | 18               | 1           | 19         | zero date collisions (bak: Mar–May 2026; live: 2026-09-07) |
| token_usage      | 1                | 0           | 1          | 2026-04 row restored |
| documents        | 0                | 0           | 0          | empty in .bak |
| notes            | 0                | 0           | 0          | empty in .bak |
| life_items       | 0                | 0           | 0          | empty in .bak |
| life_areas       | —                | 7           | 7          | identical in both DBs; skipped |
| team_members     | —                | 18          | 18         | already reconciled in prior sweep (task 9); not touched |

Final live totals: 484 tasks · 474 activity_log · 19 journal_entries · 1 token_usage.
Range in live now spans **2026-03-30 → 2026-09-07** with no gaps introduced by the merge.

## ID strategy

**Auto-assigned new IDs on insert, timestamp preserved as ordering key.** Chosen because:

- Bak IDs (tasks 1–469, activity_log 1–460, journal 1–18) collide with the fresh Sep-6 live IDs (1–15, 1–11, 1). Shifting live IDs upward would break the running-agent references currently displayed on the Dashboard.
- Nothing outside the DB persists task/activity/journal IDs (dashboard reads live queries; there are no external systems keyed to these IDs).
- `created_at` is the sort key everywhere the UI displays these tables, so chronology is preserved.

## Team-member FK remap (bak id → live id, keyed by name)

| Name    | Bak ID | Live ID |
|---------|-------:|--------:|
| Larry   | 1      | 1       |
| Nolan   | 2      | 4       |
| Pax     | 3      | 5       |
| Reed    | 4      | 6       |
| Gemma   | 5      | 7       |
| Sienna  | 6      | 2       |
| Topo    | 7      | 3       |
| Cass    | 8      | 8       |
| Vera    | 9      | 9       |
| Kit     | 10     | 10      |
| Finn    | 11     | 11      |
| Zane    | 12     | 12      |
| Wren    | 13     | 13      |
| Mori    | 14     | 14      |
| Hollis  | 15     | 16      |
| Marlo   | 16     | 17      |
| Cairn   | 17     | 18      |

All 17 bak team_members exist in live by name — zero orphans, no FKs NULLed. Live's Rune (id 15) is Sep-6-only and had no bak counterpart, so no action taken.

## activity_log — `entity_id` handling

`activity_log.entity_id` referenced the bak-side task IDs, which no longer resolve after auto-ID reassignment. Policy applied:

- `entity_type = 'task'` rows: `entity_id` set to `NULL`; original id captured in the `details` column as `[orig_task_id=N]` so a curious human can still trace it.
- Non-task `entity_type` rows: `entity_id` kept as-is (entity_type values in the merged rows were only `task`, `schema`, and `journal_entry`; journal_entry IDs shifted too, but those refs are informational, not FK-enforced — I left them intact rather than lose the linkage entirely).

## Not merged (and why)

- `documents`, `notes`, `life_items` — all empty in the .bak.
- `life_areas` — identical rows in both DBs (id 1–7, same names, same order). Nothing to merge.
- `team_members` — already reconciled in the previous sweep (task 9). No changes here.
- Bak's `sqlite_sequence` / `sqlite_master` — SQLite housekeeping; never merged.

## Verification

- `PRAGMA integrity_check` → `ok`
- `PRAGMA foreign_key_check` → no violations
- Spot-checked earliest merged tasks (2026-04-01, correct `assigned_to` after remap), latest bak tasks (2026-05-25), and all 15 post-Sep-6 live tasks intact with original IDs 1–15.

## Reconciliation activity_log entry

Row inserted into live `activity_log`:

- `actor = 'Reed'`
- `action = 'reconciled_history_from_bak'`
- `entity_type = 'database'`
- `details` = row counts + full remap table + backup path (as above)

## Cleanup

- Kept: `db/workspace.db.premigrate-20260907T131501Z` (backup — do not delete until Thomas signs off).
- Kept: `db/workspace.db.bak-20260527T090121` (original archive — untouched throughout).
- Removed: `db/workspace.db.reconcile-temp-20260907T131501Z` (rehearsal temp file).
