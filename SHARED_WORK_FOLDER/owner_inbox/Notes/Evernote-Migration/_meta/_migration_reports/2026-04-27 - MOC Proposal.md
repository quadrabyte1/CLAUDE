---
title: "MOC Proposal — Hub-and-Spoke Restructure"
created: 2026-04-27
updated: 2026-04-27
author: Cairn (PKM Specialist)
stage: proposal-only — no notes modified
---

# MOC Proposal — Hub-and-Spoke Restructure

**Date:** 2026-04-27
**Status:** Step (a) — Audit & Propose. No files have been modified.
**Scope:** 574 notes scanned (459 atomic + 9 MOCs + 106 running-journal entries), 72 unique tags catalogued.
**Machine-readable backing data:** `_meta/_working/tag_census.json`

---

## 1. Tag Census

### Raw counts (all tags, 72 total)

| Tag | Count | Sample titles |
|-----|------:|---------------|
| `running-journal` | 109 | Running Journal 2024 — 2024-06-12, Running Journal 2025 — 2025-01-07, Running Journal 2025 — 2025-04-23 |
| `●-●-●-home-●-●-●` | 11 | Drupal, Beer, DroidX version is 2.2 |
| `journal` | 9 | Untitled Note (×8), RelocateLegal = ! |
| `moc` | 9 | MOC — My Notes1 through My Notes5, Running Journal MOCs |
| `enterprise-architect` | 6 | Getting a high resolution diagram image from EA, Enterprise Architect: setting default diagram, Add-in Automation |
| `codepen` | 5 | Neural Noise, Rotating 3D Gallery, Touchstone Pictures Splash Screen |
| `edx` | 4 | Testing, Vagrant notes, making progress, python IDE |
| `laser-engraver` | 4 | grandchild coaster notes, Wainlux Laser L3 Engraver Notes, DA Big Gimping Plug-in… |
| `job-search` | 4 | Thermo Fisher Scientific, Tektronix, Ann Mitchell, Valident |
| `woodworking` | 4 | French cleat Lumber storage rack, Dust collection in the wood shop project, Dewalt shop vac |
| `software` | 3 | Caps Lock Be Gone Utility, Purchased OxygenXML editor, ErrorProvider |
| `●-●-●-work-●-●-●` | 3 | NXP, Keil microVision tool, Coding and Modeling Standards |
| `git` | 3 | Git log, Unstage the latest Git commit, Untitled Note |
| `gms` | 2 | Autodesk's Fusion 360 supports Shapeoko, Note conflict Terese's Birthday Party |
| `andreliz-(go)` | 2 | Drupal, Intuit Online (data access notes) |
| `tools` | 2 | Caps Lock Be Gone Utility, Mac File Comparison |
| `4` | 2 | TODO, sky light bid |
| `c#` | 2 | Using SQLite in C#, ErrorProvider |
| `mac` | 2 | weird mac problems -- possible fixes, Mac File Comparison |
| *(54 tags with count = 1)* | 1 each | See `tag_census.json` for full list |

**Key structural observation:** 374 of 574 notes (65%) have no tags at all. The tag data alone will not suffice for spoke-assignment; content-and-title scanning will be required in step (b).

---

## 2. Tag Groupings — Proposed Decisions

### 2A. Promote to MOC

These substantive topical tags span enough notes — and more importantly, enough *content* — to justify a hub. Note counts below combine tagged notes with content-matched untagged notes (estimated from title/body scan).

| # | MOC Title (proposed) | Source tag(s) | Estimated spoke count | One-sentence scope |
|---|----------------------|---------------|-----------------------|--------------------|
| 1 | **Running** | `running-journal` | ~115 | Aggregates all running-log entries; the hub that the three existing year/chronological MOCs roll up into. |
| 2 | **Woodworking** | `woodworking`, `dust-collection`, `woodcraft` | ~20–25 | Shop projects, techniques, tool notes, and lumber sourcing. |
| 3 | **3D Printing** | `3d-printing`, `gridfinity` | ~15–18 | Printer settings, filament notes, model sources (Printables/Thingiverse), and Gridfinity system. |
| 4 | **Laser Engraver** | `laser-engraver`, `l3` | ~8–10 | Wainlux/L3 machine notes, LightBurn tips, project logs (coasters, etc.). |
| 5 | **Enterprise Architect** | `enterprise-architect` | ~10–12 | Sparx EA how-tos, LemonTree/Git integration, diagram-export techniques, and architecture-reading notes. |
| 6 | **Software Development** | `software`, `git`, `c#`, `csharp`, `python`, `sql`, `codepen`, `programming`, `powershell`, `xml`, `oxygen-xml`, `vagrant`, `web-applications` | ~25–30 | Personal programming notes, code snippets, tool tips, and online-learning saves. |
| 7 | **Job Search** | `job-search` | ~5–8 | Company research notes and contacts from active job searches (2011–2015 era). |
| 8 | **Maker / Electronics** | `cnc`, `led`, `arm`, `moving-to-arm`, `array-converter`, `national-instruments`, `jira-notes` | ~8–10 | Embedded systems work (Keil, NXP, ARM), GPIB/test-bench notes, CNC/Shapeoko. |

**Total estimated atomic spokes across all proposed MOCs: ~220–240 notes** (with significant overlap; a note on 3D-printed woodworking jigs would link to both `[[Woodworking]]` and `[[3D Printing]]`).

### 2B. Keep as Flat Tag — No MOC

These tags are useful metadata facets but do not warrant a hub. They should survive as `#tags` in frontmatter.

| Tag | Rationale |
|-----|-----------|
| `moc` | System tag — marks a file as a Map of Content. Keep. |
| `running-journal` | Facet tag (subordinate to the Running MOC). Keep for Dataview filtering. |
| `tools` | Useful facet; too generic to hub. Merge into `software-dev` tag vocabulary if desired. |
| `mac` | 2 notes only; useful attribute on those notes; no hub warranted. |
| `goodnotes` | 1 note; keep as facet tag. |
| `fema` / `flood-insurance` | Keep as attribute tags on 1 financial note. |
| `backupper` / `synology` | Device/tool facet; keep. |
| `android` | 1 note; keep. |
| `hearing-aids` | 1 note; keep as health facet. |
| `tattoo` / `pelican` | Fine as attribute tags on their single note. |
| `tala` | Family; keep as attribute on that note. |
| `family-data` | Sensitive personal note; keep as tag. |
| `birthday-party` | Event facet; keep. |
| `finances` | 1 note; keep. (See editorial call #2 below on whether to expand.) |
| `therapy` | 1 note; sensitive; keep as tag, no hub. |
| `medtronic` | Company facet on 1 note; keep. |
| `testing` / `vagrant` | Subordinate to Software Development MOC; keep as fine-grained tags within that MOC. |
| `edx` | Online-learning facet; keep. Collapses into Software Development MOC spoke or its own tag. |
| `repo` | 1 note; keep. |
| `notes` | Too generic; retire or keep as is. (See editorial call below.) |
| `businessideas` | 1 note — borderline. See editorial call #3. |

### 2C. Retire / Merge — Noise Tags

These should be removed from the controlled vocabulary. Action required in step (b) when notes are updated.

| Tag | Count | Decision | Notes |
|-----|------:|----------|-------|
| `● ● ● HOME ● ● ●` (raw) / `●-●-●-home-●-●-●` (slugged) | 11 / raw 1 | **Retire.** | Evernote UI decoration, not a real topic. The 11 notes span job-search, household, tech — no coherent hub. Notes will be re-routed to relevant topic MOCs instead. |
| `●-●-●-work-●-●-●` | 3 | **Retire.** | Same as above — Evernote status decorator. Notes belong in Software Development and Maker/Electronics MOCs. |
| `●-●-●-software-●-●-●` | 1 | **Retire.** | Same family of junk decorators. |
| `4` | 2 | **Retire.** | Single-character junk tag. Notes (TODO, sky light bid) are uncategorizable fragments. |
| `journal` | 9 | **Retire.** | Applied to 8 "Untitled Note" entries — short work notes with no shared theme. Tag adds no navigation value. |
| `andreliz-(go)` | 2 | **Retire.** | Apparent personal name/project code from 2011–2012. Unintelligible to future-self. Notes (Drupal, Intuit Online) fold into Software Development. |
| `gms` | 2 | **Retire / clarify.** | Ambiguous acronym — one note is a birthday party logistics note, the other is a CNC tool save. No hub. Remove and let notes stand on their content. (If "GMS" means something to Thomas — flag this as an editorial call.) |
| `malware-and-viruses` | 1 | **Merge into** `software-dev` or standalone tag. | Fine-grained tag on 1 note; fold it. |
| `zillow` | 1 | **Retire.** | Single real-estate save, no topic cluster. |
| `edd` / `unemployment` | 1 each | **Merge.** | Same note, two near-duplicate tags. Retire one; keep `unemployment` as the facet if kept at all. |
| `terese's-web-site` | 1 | **Retire.** | Personal project reference that no longer exists. |
| `the-random-organization` | 1 | **Retire.** | Unclear reference. |
| `luxim` | 1 | **Retire.** | Former company name on 1 work note — keep the note, drop the tag. |
| `array-converter` / `moving-to-arm` | 1 each | **Retire.** | Hyper-specific junk tags from 2011 embedded work. Notes fold into Maker/Electronics. |
| `fax` | 1 | **Retire.** | Single note (FAX testing); no topical cluster. |
| `silverlight` / `mysql` | 1 each | **Retire.** | Dead-tech facets on 1 tutorial note. Fold into Software Development. |
| `c#` + `csharp` | 2+1 | **Merge.** | Near-duplicate. Keep `csharp` (no special chars); retire `c#`. |

**Summary:** 16 tags retire outright; 3 pairs merge; 2 are editorial calls.

---

## 3. Existing 9 MOCs — Disposition

| MOC File | Current title | Notes in index | Verdict |
|----------|--------------|----------------|---------|
| `My Notes1.md` | MOC — My Notes1 | 93 | **Retire.** Pure export-artifact (notebook-level index). Notes redistributed to topic MOCs in step (b). Archive this file in `90 - Archive/`. |
| `My Notes2.md` | MOC — My Notes2 | 91 | **Retire.** Same. |
| `My Notes3.md` | MOC — My Notes3 | 94 | **Retire.** Same. |
| `My Notes4.md` | MOC — My Notes4 | 91 | **Retire.** Same. |
| `My Notes5.md` | MOC — My Notes5 | 90 | **Retire.** Same. |
| `Running Journal (Chronological).md` | MOC — Running Journal (Chronological) | 106 | **Merge into Running MOC.** The chronological index is valuable UX; absorb it into the new `Running` MOC as a "Chronological index" section or keep as a sub-MOC. Editorial call — see below. |
| `Running Journal 2024.md` | MOC — Running Journal 2024 | 42 | **Keep as year sub-MOC,** linked from the Running hub. |
| `Running Journal 2025.md` | MOC — Running Journal 2025 | 64 | **Keep as year sub-MOC,** linked from the Running hub. |
| `● ● ● Home ● ● ●.md` | MOC — ● ● ● Home ● ● ● | 11 | **Retire.** Notes redistributed. File rename or archive. |

**Net change for existing MOCs:** 6 retire/archive, 3 survive (2 as sub-MOCs under Running, 1 potentially merged into new Running hub).

---

## 4. Resulting MOC Structure (Proposed)

A flat list — no hierarchy enforced; links provide the structure.

```
20 - MOCs/
  Running.md                        ~115 spokes  (hub; links to year sub-MOCs)
  Running Journal 2024.md             42 spokes  (keep; repoint to Running hub)
  Running Journal 2025.md             64 spokes  (keep; repoint to Running hub)
  Woodworking.md                    ~20–25 spokes
  3D Printing.md                    ~15–18 spokes
  Laser Engraver.md                   ~8–10 spokes
  Enterprise Architect.md            ~10–12 spokes
  Software Development.md            ~25–30 spokes
  Job Search.md                        ~5–8 spokes
  Maker & Electronics.md              ~8–10 spokes
```

**Total proposed MOCs: 10** (8 new + 2 surviving year sub-MOCs).
**Retiring: 6** (5 notebook indexes + Home MOC).
**Net new files created in step (b): 8** MOC stubs.

---

## 5. Editorial Calls for the Boss

The following items are genuinely on the fence. I need a call before step (b) begins.

**EC-1 — Running MOC vs. Running Journal (Chronological) MOC**
The vault currently has a "Running Journal (Chronological)" MOC that indexes all 106 entries in date order — very useful UX. I could (a) replace it with a single "Running" hub that has a full chronological list, (b) keep both and have "Running" link to "(Chronological)" as a sub-MOC, or (c) keep just the two year MOCs under a new "Running" hub and retire "(Chronological)". Option (b) is my lean — preserves the ergonomics of the existing file — but this is Thomas's call.

**EC-2 — Software Development: one big MOC or split?**
The `software`, `git`, `c#`, `codepen`, `python`, `sql`, `edx`, `vagrant`, and related tags collectively point to ~25–30 notes. These span web dev (CSS/CodePen), scripting (Python/PowerShell), database (SQLite), version control (Git), and online learning (edX/Vagrant). One `[[Software Development]]` hub handles it, but if Thomas regularly wants to navigate just "Git notes" or just "Python" separately, splitting is warranted. My lean: one hub for now, with a section per sub-domain inside the MOC body.

**EC-3 — `gms` tag: what is GMS?**
Two notes carry this tag: a birthday-party logistics note and a Fusion 360/Shapeoko save. If "GMS" is a meaningful acronym to Thomas (company? project?), the notes may need a different routing. If not, retire the tag and route the CNC note to Maker/Electronics. I cannot determine the meaning from content alone.

**EC-4 — Maker/Electronics vs. Enterprise Architect: overlap on work notes**
Several notes tagged `●-●-●-work-●-●-●` (Keil, NXP, Coding and Modeling Standards) are ambiguously "embedded systems work" OR "software architecture reading." The Keil/NXP notes feel like Maker/Electronics; the Coding Standards note feels like Software Development or Enterprise Architect. I'll assign them to my best guess in step (b), but Thomas should spot-check the 50-note dry run specifically for these.

**EC-5 — Job Search MOC: small and dated**
The `job-search` tag has only 4 explicitly tagged notes, all from 2011–2015. Content scanning may find a few more. But this cluster is small, old, and unlikely to grow. Should it be a full MOC or just a flat `job-search` tag with no hub? My lean: keep as a flat tag unless Thomas expects to add more job-search notes in the future.

**EC-6 — "My Notes 1–5" MOCs: archive or delete?**
These are export artifacts with no topical meaning. I recommend archiving (move to `90 - Archive/`) rather than deleting — they preserve the original notebook provenance. But if Thomas wants a clean `20 - MOCs/` folder, deleting them is safe; the notes themselves are unaffected. Requires boss decision before step (b) modifies any MOC file.

---

## 6. Step (b) — Spoke-Application Work Estimate

### What step (b) involves
For each of the ~220–240 atomic notes that belong to one or more proposed MOCs:
1. Add a `[[MOC Name]]` wikilink to the note's frontmatter or body.
2. Add the note entry to the corresponding MOC's index.
3. Apply any tag cleanup (retire junk tags, merge near-duplicates).

The 106 running-journal entries already live in `40 - Areas/Running/` and have robust existing MOC links — they need only a link added pointing to the new `[[Running]]` hub. Net new edits on those files: minimal.

### Volume estimate

| Category | Notes touched | Avg links added/note |
|----------|-------------|----------------------|
| Running-journal entries (existing, add hub link) | ~106 | 1 |
| Atomic notes routed to topic MOCs | ~130–150 | 1.3 |
| Atomic notes needing tag cleanup only | ~30–40 | 0 (tags only) |
| **Total notes touched** | **~270–300** | |
| **Total `[[MOC]]` links added** | **~250–270** | |

~374 notes remain untagged and without obvious topic affiliation (many are "Untitled Note" stubs, snapshot images, or one-off saves). These will **not** be touched in step (b) unless a manual review reveals a missed cluster.

### Risk flags
- **Untitled Notes (106):** Most carry no topical signal. Do not assign MOC links to untitled notes without manual review — risk of mis-routing.
- **Multi-topic notes:** Notes at the intersection of topics (e.g., woodworking + 3D printing) need dual links. The dry-run will surface how many of these exist.
- **`● ● ● HOME ● ● ●` notes:** The 11 notes tagged with this decorator need individual human routing — some are job-search, some are household, some are tech. I will list them in the dry-run report with proposed routing for Thomas to approve.
- **Sensitive notes (Marty Klein / therapy, Family Data, server credentials, AI API keys):** These will be included in the dry-run report's "flag for manual review" section. They should receive no public-facing MOC links.

### Dry-run plan (mandatory before full commit)
Per Cairn's standards, step (b) begins with a ≤50-note sample:
1. Select 50 notes: 20 tagged with known topics, 15 untagged but topically obvious by title, 10 untitled, 5 from the `●-●-●-home-●-●-●` cluster.
2. Apply MOC routing and tag cleanup to the sample only.
3. Deliver a dry-run report: notes touched, links added, proposed routing for the "home" cluster, flags.
4. Thomas spot-checks. Boss approves or requests adjustments.
5. Full run commits only after approval.

**Estimated step (b) duration:** 1 session for dry run + report; 1 session for full run after approval.

---

## 7. Summary Statistics

| Metric | Count |
|--------|------:|
| Notes scanned | 574 |
| Unique tags found | 72 |
| Tags proposed for promotion to MOC | 8 *(becoming new MOC hubs)* |
| Tags proposed to keep as flat tag | ~20 |
| Tags proposed to retire/merge | ~30 |
| Existing MOCs surviving | 3 (2 as sub-MOCs) |
| Existing MOCs retiring/archiving | 6 |
| New MOC files to create in step (b) | 8 |
| Notes with no tags (scope of unassigned work) | 374 |
| Editorial calls requiring boss input | 6 |

---

*Cairn proposes; the boss disposes. No notes were modified in producing this report.*
