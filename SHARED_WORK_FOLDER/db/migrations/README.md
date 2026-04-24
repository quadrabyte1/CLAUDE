# Migrations

## Approach

This project uses **PRAGMA user_version** to track the schema version of `workspace.db`. Each migration is a standalone `.sql` file (or `.py` if it needs logic) named with a sequential version number:

```
001_initial_schema.sql
002_add_tags_table.sql
003_add_document_hash.sql
```

### Rules

1. **Never modify a migration that has already been applied.** If you need to change something, write a new migration.
2. **Each migration must include both UP and DOWN sections** (separated by a `-- DOWN` comment). If the down migration would lose data, document that clearly at the top of the file.
3. **Migrations are applied in order.** The current version is stored in `PRAGMA user_version`. A migration file numbered `NNN` brings the database from version `NNN-1` to version `NNN`.
4. **The canonical schema.sql always reflects the latest version.** After writing a new migration, update `schema.sql` to match the end state.

### How to apply

For now, migrations are applied manually:

```bash
# Check current version
sqlite3 db/workspace.db "PRAGMA user_version;"

# Apply a migration (example)
sqlite3 db/workspace.db < db/migrations/002_add_tags_table.sql

# Set the new version
sqlite3 db/workspace.db "PRAGMA user_version = 2;"
```

If the project grows, we can add a `migrate.py` script that automates this loop.

### Current version

| Version | Description            | Date       |
|---------|------------------------|------------|
| 1       | Initial schema         | 2026-03-30 |
| 2       | Add journal_entries    | 2026-03-30 |
