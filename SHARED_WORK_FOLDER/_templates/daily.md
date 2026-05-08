---
title: "{{date:YYYY-MM-DD}}"
created: {{date:YYYY-MM-DD}}
tags: [daily-note]
---

# {{date:YYYY-MM-DD}}

## Today's tasks (from DB)

<!-- PHASE 2 STUB — Reed will wire this up via SQLite bridge -->
<!-- Dataview or Templater query to pull tasks WHERE date(started_at) = this note's date -->
<!-- Example placeholder (Dataview, requires obsidian-dataview plugin + SQLite bridge):
```dataview
TABLE title, status, assigned_to
FROM ""
WHERE file.name = this.file.name
```
-->

> _Tasks not yet loaded — SQLite bridge pending (Phase 2)._

---

## Notes

<!-- Free-form notes for the day. Wikilink liberally: [[concept]], [[person]], [[project]]. -->

---

## Activity log (from DB)

<!-- PHASE 2 STUB — Reed will wire this up via SQLite bridge -->
<!-- Query: SELECT actor, action, details FROM activity_log WHERE date(created_at) = '<this date>' ORDER BY created_at ASC -->
<!-- Rendered here as a read-only generated block, regenerated on open via Templater or a watcher script -->

> _Activity log not yet loaded — SQLite bridge pending (Phase 2)._

---

## Journal entry (syncs to DB)

<!-- PHASE 2 STUB — When this section is saved, the watcher script mirrors it into journal_entries table -->
<!-- Source of truth for prose: this file. DB row is a replica. -->

<!-- Write your journal entry here. The bridge will sync on file save. -->
