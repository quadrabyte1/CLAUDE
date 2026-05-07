# Obsidian Integration — Team-Wide Benefits Memo

**Date:** 2026-05-07  
**Prepared by:** Cairn (PKM Specialist)

---

## The Two-Paragraph Answer

Integrating Obsidian as a shared vault gives every team member the same retrieval surface Thomas already relies on, rather than a fractured pile of Markdown files that live only inside `owner_inbox/` and are never cross-referenced. Right now, Topo's 3MF delivery for PGA West lands in `owner_inbox/` and Hollis's deck-builder research lands two folders away, and neither note knows the other exists. A vault turns those flat deliverables into linked nodes: Hollis's contractor list wikilinks to the deck-blueprint specs Gemma diagrammed; Finn's slicer notes for the Moffett Field hole link back to Topo's rendering rules. Sienna's Flask app already reads `db/workspace.db` — a Dataview query over the same vault gives Thomas (and the team) a live dashboard of every deliverable, course, and research memo without writing a single SQL statement. And plain Markdown on local disk means that ten years from now, when Obsidian has been superseded by whatever comes next, every note is still a readable `.md` file — a guarantee none of the team's current sources (Evernote, Notion) can make.

The compounding benefit is institutional memory that closes the loop Larry is already trying to close manually. Every `INSERT INTO journal_entries` that Reed or any team member runs today produces a row in SQLite that Thomas can only query by writing SQL or reading raw exports — but piped into the vault as a daily note or appended to a `journal_entries` MOC, those entries become searchable, backlinked, and navigable through Obsidian's graph. Larry's delegation flow produces task records; those task records can map to notes grouped by domain (golf rendering, deck project, iOS voice work, trademark clearance) inside Maps of Content that Cairn maintains. When Pax finishes a research sprint, his summary doc already lands in `owner_inbox/` — one more step drops it into the vault with frontmatter tagging it to the right project, so Thomas's Evernote→Obsidian migration and the team's ongoing output land on the same retrieval surface. Over six to twelve months, the team's combined output builds a corpus where "what did we learn about Pylex pier spacing?" and "which Arnold Palmer holes have been rendered?" are answerable by a single Dataview query rather than a manual grep across folders.

---

## Concrete Integration Touchpoints

- **`db/workspace.db` → vault daily notes:** A lightweight export script (or Reed-authored SQLite trigger) pushes each day's `journal_entries` row into an Obsidian daily note, making the journal grep-able and backlinked from project MOCs.
- **`owner_inbox/` deliverables → vault inbox:** Each file Cairn migrates gets YAML frontmatter (`project`, `domain`, `created`, `team_member`) and drops into `00 - Inbox/` for triage into the PARA structure. No files are deleted from `owner_inbox/` — the vault is a linked mirror, not a replacement.
- **`team_inbox/` → capture layer:** Files Thomas drops in `team_inbox/` trigger a Cairn intake pass: parse, add frontmatter, move to vault `00 - Inbox/`, log the ingestion in `activity_log`.
- **`journal_entries` table → vault journal MOC:** A `20 - MOCs/Team Journal.md` note aggregates all journal entries by date, providing backlinks to each topic (deck research, golf rendering, iOS work) automatically.
- **Migration reports → vault `_meta/`:** Cairn's Evernote migration reports, already destined for `owner_inbox/Notes/_migration_reports/`, become first-class vault notes with wikilinks to the notes they describe.
- **Larry's delegation flow → task notes:** Each task INSERT in `tasks` table maps to a project note in `30 - Projects/`, giving Thomas a readable history of what was delegated, to whom, and what was delivered — without opening a SQL client.
- **EliteGolfMoments deliverables → course MOCs:** Each golf course (PGA West, Moffett Field, Stanford, Augusta Ranch) gets a MOC that links to Topo's 3MF files, Finn's slicer notes, and any rendering-rules notes — replacing the current folder-per-course convention with a navigable knowledge map.
- **Deck-blueprint research docs → project MOC:** Hollis's contractor research, Gemma's diagrams, and the v14/v15 build-instruction PDFs all link into a `30 - Projects/West Hartford Deck.md` MOC, giving Thomas a single entry point for the whole project.

---

## Risks / What We'd Give Up

- **Vault sprawl:** Without discipline, the vault becomes another flat folder. Cairn needs a mandate to enforce the PARA structure and prune quarterly — this is ongoing work, not a one-time setup.
- **Plugin lock-in temptation:** Obsidian's plugin ecosystem is powerful but fragile. Any note structure that depends on a community plugin (rather than plain Markdown) breaks portability. Cairn's rule: if removing the plugin breaks the note, the plugin is not used for structural content.
- **Sync conflicts on a shared vault:** If multiple team members (or Thomas's multiple devices) write to the vault simultaneously without a conflict-resolution strategy, `.md` files collide silently. Mitigation: Obsidian Git with a clear branching convention, or iCloud sync with strict single-writer discipline per session.
- **The db ↔ vault relationship needs a keeper:** The SQLite-to-vault pipeline is only as good as the script that runs it. If the sync job drifts or Reed changes the schema, journal entries stop flowing. Someone (Cairn, Reed, or Sienna) owns the integration maintenance.
- **Thomas's Evernote migration is a prerequisite assumption:** If the migration stalls or Thomas decides to keep Evernote as the canonical store, the "same retrieval surface" argument weakens. The vault is most powerful when it is *the* retrieval surface, not one of two.

---

## Recommended First Move

Point the Obsidian vault at `owner_inbox/` as a read-only watched folder and add YAML frontmatter to the five most-referenced deliverables (deck research, golf rendering rules, Moffett Field notes, PGA West notes, the team roster) — that alone demonstrates backlinks and graph view with zero migration risk and no new infrastructure.
