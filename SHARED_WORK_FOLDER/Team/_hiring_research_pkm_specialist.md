# Hiring Research — Personal Knowledge Management (PKM) Specialist

**Prepared by:** Pax (Senior Researcher)
**Date:** 2026-04-23
**Trigger:** Seven Evernote HTML exports (4 MB – 164 MB each, single-page concatenated format with embedded media) need to be split, converted to Markdown, and interconnected. Also durable ongoing need for PKM/Zettelkasten hygiene and future migrations (Notion, Apple Notes, etc.).

---

## 1. Role titles in the real world

Practitioners who do this work use a spread of titles. None is fully standardized; the field is new and overlapping:

| Title | Scope | Fit for our need |
|---|---|---|
| **PKM Specialist / Consultant** | Helps individuals build and maintain personal knowledge systems. The phrase most used by practitioners on LinkedIn, in Obsidian/Logseq communities, and by Tiago Forte's "Building a Second Brain" cohort. | Strong fit — covers both migration and ongoing care. |
| **Second Brain Consultant** | Narrower, tied to Forte's CODE/PARA framework. | Too methodology-specific. |
| **Zettelkasten Coach** | Focused on Luhmann-style atomic notes and linking discipline. | Too narrow; doesn't cover ingest/migration. |
| **Digital Archivist** | Institutional role: preservation, metadata standards, migration of legacy records to new digital formats. Certified Archivist (CA) credential exists. | Adjacent — the migration/metadata-preservation instincts are exactly right, but archivists preserve *as-is*; they don't re-author or build knowledge graphs. |
| **Information Architect (personal)** | Designs structure and taxonomies. | Covers design but not ingest/labor. |
| **Knowledge Manager** | Enterprise role, salary ~$86K median in US per ZipRecruiter. | Wrong scale — organizational, not personal. |

**Recommendation:** Call the hire a **PKM Specialist** (primary) with a secondary descriptor like "note-migration and linked-knowledge specialist." This captures both the legacy-ingest work and the forward-looking Zettelkasten/graph work. Avoid "Second Brain Consultant" (too branded) and "Digital Archivist" (implies preservation-only posture).

---

## 2. Core skills and workflows

What practitioners actually do when migrating notes:

1. **Inventory first.** Count notes, total size, notebooks/tags present, oldest/newest timestamps. Decide what's worth migrating vs archiving cold.
2. **Parse the source format.** For Evernote that's either `.enex` (XML with base64-embedded attachments) or HTML (single-page or multi-page). Tools: BeautifulSoup4, html2text, lxml, Pandoc, and the community-standard **Yarle** and **evernote-dump** CLI tools. Obsidian's first-party "Importer" community plugin handles `.enex` well.
3. **Preserve metadata.** Titles, created/updated dates, tags, notebook → folder mapping, source URL, author. Created date is the one that usually drops on naive imports.
4. **Extract media.** Images, PDFs, audio move to an `attachments/` or `_resources/` folder with stable relative paths. Evernote `<en-media hash="...">` tags need rewriting to Markdown image links.
5. **Deduplicate.** Content hash (or fuzzy-hash) the note bodies; titles alone aren't reliable. Dedup pass is always done *after* extraction, *before* linking.
6. **Split mega-notes into atomic notes.** Large Evernote notes often contain many distinct ideas. Practitioners use heading boundaries (`<h1>`, `<h2>`, horizontal rules `<hr>`, strong visual breaks) as split candidates, reviewed by a human. Obsidian's **Note Composer** core plugin codifies the split/merge workflow.
7. **Generate frontmatter.** YAML block with `title`, `created`, `updated`, `source`, `tags`, `aliases`, optional `uid` for stable linking.
8. **Link pass (separate from migration).** Auto-suggest links via keyword/tag co-occurrence or embeddings; human accepts/rejects. Build MOCs.
9. **Validate.** Broken-link report, orphan-note report, dead-image report.

---

## 3. Tools and formats

**Dominant target (2026 consensus):** Markdown files on local disk, edited in **Obsidian**. Reasons:
- Plain text, future-proof, grep-able, git-versionable.
- `[[wikilinks]]` + YAML frontmatter + `#tags` + backlinks + graph view are first-class.
- Vault = a folder; trivial to back up and move.

**Logseq** is strong for block-level / outliner thinkers but is mid-migration to a DB format (2026) and less portable; prefer Obsidian unless the user specifically wants outlines.

**Zettlr** is a better fit for academic writers who live in citations (Zotero/BibTeX/LaTeX). Not our use case.

**Notion, Apple Notes, Evernote, OneNote** are sources, not targets. All have lock-in risks.

**Atomic notes vs long-form:** Modern consensus — atomic for reference/thinking notes, long-form for drafts and published artifacts. Two tiers, same vault, linked.

---

## 4. Linking methodology

Practitioner discipline (drawn from the Zettelkasten community and Obsidian power-users):

- **Tags** = facets / categorical metadata ("#book", "#status/draft", "#area/golf"). Cheap, flat, good for filtering.
- **Backlinks (wikilinks)** = conceptual relationships between specific ideas. Expensive to create; highest-value.
- **MOCs (Maps of Content)** = curated index notes that group related atomic notes. The bridge between "just a tag" and "just a link." Use when a topic has >~10 notes.

**When to link two notes:** when reading note A genuinely makes the reader want to read note B *for a reason you can articulate in the link context.* "These are both about X" is a tag, not a link.

**Common mistakes:**
- **Over-linking** — linking every proper noun. Clutters graph, dilutes signal.
- **Under-linking** — treating notes as filing-cabinet entries, never connecting.
- **Link-rot** — renaming notes without updating references (Obsidian handles this, but cross-vault and external tools don't).
- **Tag sprawl** — inventing a new tag per note. Enforce a controlled vocabulary; prune quarterly.
- **MOC rot** — MOCs that were built once and never updated.

---

## 5. Evernote-specific migration gotchas

Critical — we have HTML exports, not ENEX. The formats differ:

**ENEX** (XML):
- `<en-note>` wraps content (XHTML-ish).
- `<en-media hash="...">` placeholders; binary attachments appear as base64-encoded `<resource>` elements elsewhere in the XML. Files bloat — a 164 MB export is realistic.
- Metadata: `<title>`, `<created>`, `<updated>`, `<tag>` elements, `<note-attributes>` (source-url, author, latitude/longitude).
- Best tool: Obsidian Importer plugin, or Yarle.

**HTML export** (what the user has):
- **Single-page mode:** all notes in one HTML file, separated by structural markers (typically `<div>` blocks with Evernote-specific class names like `en-note`, headings, and horizontal rules). Images live in an adjacent `_resources/` folder, linked by relative path. This is the file format the user has.
- **Multi-page mode:** one HTML file per note + shared `_resources/` + an `index.html`.
- HTML varies by Evernote version; older notes often have malformed or Evernote-proprietary markup (`en-markup`, `en-note` classes; `<div>`-based structure with inline styles).
- Metadata is inconsistent — title is usually an `<h1>` or `<title>` but creation date may be missing or only in the filename / adjacent metadata.

**Practical split strategy for single-page HTML:**
1. Parse with BeautifulSoup4.
2. Identify the note boundary pattern (usually top-level `<div class="en-note">` or `<hr>` between notes, or `<h1>` with Evernote-specific styling).
3. For each note block, extract title (first `<h1>` or heading), body, any inline metadata (date printed at top).
4. Rewrite `<img src="_resources/...">` paths to the new vault's attachment folder.
5. Run html2text (or Pandoc) on each block → Markdown.
6. Emit `.md` file with YAML frontmatter.
7. Copy `_resources/*` into the vault's attachment folder; verify every image reference resolves.

**Known pitfalls:**
- Code blocks and tables: Evernote has no real Markdown code block; they export as `<div>` with monospace font. html2text mangles them; Pandoc does better.
- Lists: Evernote nests lists inconsistently; manual review of a sample is needed.
- Checkboxes / tasks: only ENEX v2+ encodes them; HTML export loses state.
- Embedded PDFs & audio: preserve as attachments; reference in frontmatter.
- Internal note links: Evernote uses `evernote:///` URIs that are dead post-export; map to wikilinks by title (best-effort, imperfect).

---

## 6. Quality bars — what "good" looks like

Output vault structure (recommended):

```
VaultRoot/
  00 - Inbox/                  # unprocessed new captures
  10 - Atomic Notes/           # Zettelkasten-style atomic notes
  20 - MOCs/                   # maps of content
  30 - Projects/               # PARA: active projects
  40 - Areas/                  # PARA: ongoing areas of responsibility
  50 - Resources/              # PARA: reference material
  90 - Archive/                # PARA: inactive
  _attachments/                # images, PDFs, audio
  _templates/                  # note templates
  _meta/                       # migration logs, dedup reports
```

(Use numeric prefixes so folders sort predictably.)

**Filename convention:** `YYYY-MM-DD - Title Case Note Name.md`. The date prefix is the note's *created* date when known; preserves chronology and avoids filename collisions. Some practitioners use pure UIDs (Luhmann-style `202604231530`) — cleaner for the graph, uglier to skim. **Recommendation: human-readable titles with date prefix**, with a `uid:` field in frontmatter for stable linking.

**Frontmatter template:**
```yaml
---
title: "Human-readable title"
uid: 20260423T1530
created: 2019-08-14
updated: 2026-04-23
source: evernote
original_notebook: "Golf Ideas"
tags: [golf, zettelkasten]
aliases: []
---
```

**Link syntax:** `[[YYYY-MM-DD - Title]]` (Obsidian resolves by filename) or `[[uid|display text]]` if UIDs are preferred.

**Quality checks the migration must pass:**
1. Note count in == note count out (minus intentional dedup).
2. Every image referenced in a note file exists on disk.
3. No broken internal links (a report is produced if any exist).
4. Every note has a `created` date (fallback to export date, flagged).
5. A sample of 20 notes is spot-checked by a human before the full migration commits.
6. Dedup report lists exact-match and near-match candidates for review; nothing is deleted without approval.

---

## Recommendation to Nolan

### Role title
**PKM Specialist** — descriptor: "Personal knowledge migration and linked-notes specialist."

### Model tier
**Sonnet.** Justification:
- The work is *implementation-heavy and well-scoped*: parse HTML, emit Markdown, generate frontmatter, wire up links. This is exactly the profile for sonnet per the model-tier guidance in CLAUDE.md.
- Novel reasoning and judgment are concentrated in two places (dedup decisions, link-suggestion curation), both of which are human-in-the-loop gates, not autonomous calls.
- The domain knowledge (Evernote formats, Zettelkasten discipline, Obsidian conventions) is encodable in the persona file — it doesn't need opus-tier reasoning at runtime.
- Keeps the approved 6 opus / 9 sonnet split intact.

Escalation path: if the link-suggestion / graph-design work later becomes genuinely generative (e.g., auto-proposing MOCs from embeddings, reasoning about taxonomy trade-offs), reconsider an opus upgrade then.

### Suggested name
Something short and evocative; Nolan picks the final. Candidates: **Lex** (lexicon, indexing), **Atlas** (maps of content), **Ada** (archivist vibe), **Iris** (look-and-see, indexing), **Cairn** (trail-marker, linked knowledge).

### Core responsibilities (for the persona file)

1. **Ingest legacy notes** from Evernote HTML/ENEX, Notion exports, Apple Notes archives, and arbitrary Markdown dumps. Parse, extract media, preserve title/created/updated/tags/notebook metadata.
2. **Split mega-notes into atomic notes** using heading/HR/visual-break heuristics, with a review report flagging anything ambiguous.
3. **Deduplicate** by content hash and near-match (fuzzy) before linking. Produce a dedup report; delete only with explicit approval.
4. **Generate Obsidian-compatible output**: PARA-style folder structure, YAML frontmatter, `[[wikilinks]]`, `_attachments/` media folder, `_meta/` migration logs.
5. **Build the linked-knowledge graph** — suggest links between notes via keyword / tag / embedding overlap; author MOCs for high-density topics; enforce a controlled tag vocabulary.
6. **Maintain link hygiene ongoing** — find orphans, detect link-rot, prune tag sprawl, refresh MOCs on a cadence.
7. **Run migration dry-runs** — on a sample of ≤50 notes first, report outcomes, then commit the full run only after the boss signs off.
8. **Produce a migration report** for every batch: counts in/out, dedup decisions, broken-link list, orphaned-media list, notes needing manual review.

### Tools the hire should know
BeautifulSoup4, lxml, html2text, Pandoc, Yarle, Obsidian Importer plugin, evernote-dump, Obsidian Note Composer, Dataview plugin, Templater plugin, Git (for vault versioning), basic Python scripting for batch work.

### Methodology the hire should internalize
- Zettelkasten atomicity (one idea per note).
- PARA organization for active/reference material.
- CODE workflow (Capture / Organize / Distill / Express) for ongoing hygiene.
- Human-in-the-loop for every destructive step (dedup, split, delete).

---

## Sources

- [PKM career landscape 2026 — Bloomfire](https://bloomfire.com/blog/career-in-knowledge-management/)
- [Building a Second Brain overview — Forte Labs](https://fortelabs.com/blog/basboverview/)
- [The PARA Method — Forte Labs](https://fortelabs.com/blog/para/)
- [Zettelkasten atomicity guide](https://zettelkasten.de/atomicity/guide/)
- [Evernote ENEX format in depth — MyInfo](https://www.myinfoapp.com/blog/enex-file-format)
- [How Evernote's XML Export Format Works — Evernote blog](https://evernote.com/blog/how-evernotes-xml-export-format-works)
- [Export Notes and Notebooks as ENEX or HTML — Evernote Help](https://help.evernote.com/hc/en-us/articles/209005557-Export-Notes-and-Notebooks-as-ENEX-or-HTML)
- [Migrate Evernote HTML to Obsidian Markdown — dev.to](https://dev.to/techresolve/solved-migrate-evernote-notes-to-obsidian-converting-html-to-markdown-pbm)
- [Migrating from Evernote to Obsidian — Doug Muth](https://www.dmuth.org/migrating-from-evernote-to-obisidian/)
- [Import from Evernote — Obsidian Help](https://help.obsidian.md/import/evernote)
- [evernote-dump on GitHub](https://github.com/exomut/evernote-dump)
- [Building an Evernote to SQLite exporter — Simon Willison](https://simonwillison.net/2020/Oct/16/building-evernote-sqlite-exporter/)
- [Splitting Notes in Obsidian — Sweet Setup](https://thesweetsetup.com/splitting-notes-in-obsidian/)
- [How to Split Long Notes into Atomic Notes — dsebastien.net](https://www.dsebastien.net/how-to-split-long-notes-into-atomic-notes-a-comprehensive-guide/)
- [Obsidian vs Logseq 2026 — Software Scout](https://thesoftwarescout.com/obsidian-vs-logseq-2026-which-note-taking-app-wins/)
- [YAML Frontmatter in Obsidian — Fork My Brain](https://notes.nicolevanderhoeven.com/obsidian-playbook/Using+Obsidian/03+Linking+and+organizing/YAML+Frontmatter)
- [Digital Archivist role overview — CareerExplorer](https://www.careerexplorer.com/careers/digital-archivist/)
