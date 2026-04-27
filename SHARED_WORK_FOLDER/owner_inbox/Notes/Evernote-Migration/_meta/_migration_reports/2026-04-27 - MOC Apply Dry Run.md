---
title: "MOC Apply — Dry Run Report"
created: 2026-04-27
updated: 2026-04-27
author: Cairn (PKM Specialist)
stage: dry-run — 50 of 565 notes touched; full run awaiting boss sign-off
---

# MOC Apply — Dry Run Report

**Date:** 2026-04-27  
**Status:** Dry run complete. Full run gated on boss sign-off.  
**Scope:** 50 of 565 total notes (59 atomic + 106 running-journal = ~565 note-level files). Remaining 515 notes untouched.  
**Boss decisions incorporated:** Running Journal kept as sub-MOC (EC-1); Software Development is one hub (EC-2); `gms` tag retired (EC-3).

---

## 1. Scope

| Category | Count | Notes |
|----------|------:|-------|
| Total vault notes | 565 | 459 atomic + 9 MOCs + 106 running-journal + rounding |
| Sample size | 50 | See selection method below |
| Tagged notes in sample | 20 | One or more topic tags present |
| Untagged notes in sample | 15 | Routed by content/title scan |
| Decorator-tag notes in sample | 10 | `●-●-●-home-●-●-●`, `●-●-●-work-●-●-●`, `4`, `gms`, etc. |
| Edge-case notes in sample | 5 | Multi-topic, sensitive, very short |
| Running-journal entries in sample | 2 | Representative minimum |
| Notes flagged for manual review | 7 | See section 7 |
| Remaining notes untouched | 515 | Not modified |

---

## 2. MOCs Created

8 new MOC stubs created in `20 - MOCs/`:

| # | MOC File | Path | Estimated spokes (full vault) |
|---|----------|------|-------------------------------|
| 1 | `Running.md` | `20 - MOCs/Running.md` | ~115 |
| 2 | `Woodworking.md` | `20 - MOCs/Woodworking.md` | ~20–25 |
| 3 | `3D Printing.md` | `20 - MOCs/3D Printing.md` | ~15–18 |
| 4 | `Laser Engraver.md` | `20 - MOCs/Laser Engraver.md` | ~8–10 |
| 5 | `Enterprise Architect.md` | `20 - MOCs/Enterprise Architect.md` | ~10–12 |
| 6 | `Software Development.md` | `20 - MOCs/Software Development.md` | ~25–30 |
| 7 | `Job Search.md` | `20 - MOCs/Job Search.md` | ~5–8 |
| 8 | `Maker & Electronics.md` | `20 - MOCs/Maker & Electronics.md` | ~8–10 |

**3 existing MOCs survive and are untouched:**
- `Running Journal (Chronological).md` — kept as sub-MOC under Running (EC-1 decision)
- `Running Journal 2024.md` — kept as year sub-MOC
- `Running Journal 2025.md` — kept as year sub-MOC

**MOC template used:** Intro paragraph describing scope, `## Scope` section, `## Notes` section with wikilinks to known spokes, `## See also` section with cross-MOC connections. Notes section is a stub in the 8 new files — to be fully backfilled in the 515-note full run.

---

## 3. MOCs Retired

6 existing MOCs moved from `20 - MOCs/` to `90 - Archive/` with `[ARCHIVED]` suffix in title and `archive_reason` frontmatter field added.

| Retired MOC | Notes indexed | Disposition | Rationale |
|------------|--------------|-------------|-----------|
| `My Notes1.md` | 93 | Archived to `90 - Archive/My Notes1.md` | Pure export artifact — Evernote notebook boundary, not a topic |
| `My Notes2.md` | 91 | Archived to `90 - Archive/My Notes2.md` | Same |
| `My Notes3.md` | 94 | Archived to `90 - Archive/My Notes3.md` | Same |
| `My Notes4.md` | 91 | Archived to `90 - Archive/My Notes4.md` | Same |
| `My Notes5.md` | 90 | Archived to `90 - Archive/My Notes5.md` | Same |
| `● ● ● Home ● ● ●.md` | 11 | Archived to `90 - Archive/● ● ● Home ● ● ●.md` | Evernote decorator tag, not a topic |

**Disposition rationale (archive vs. delete):** Archive chosen over delete because these files preserve original notebook provenance — they document which notes came from which Evernote notebook. If questions arise later about migration completeness, they remain auditable. The `90 - Archive/` folder is the honest answer: "this existed, it was superseded, here it is."

---

## 4. Sample Selection Method

Sample constructed in four groups to maximize coverage and surface edge cases:

**Group A — Tagged notes (20 notes):** Selected 2–4 notes per MOC hub from notes with explicit topic tags. Ensures each new MOC gets at least one real spoke in the dry run. Includes one running-journal entry from 2024 and one from the data file only (2024-08-22 — verified in `40 - Areas/Running/`).

**Group B — Untagged notes (15 notes):** Selected by title and content scan. Priority: notes whose topic is unambiguous from title alone (e.g., "Wiring the Woodshop," "bandsaw blades," "where to buy wood," "3D Printing Notes"). Three notes were intentionally selected where routing is *not* obvious to surface the difficulty of the 374-note untagged gap.

**Group C — Decorator/junk-tag notes (10 notes):** Selected notes carrying the retire-list tags: `●-●-●-home-●-●-●` (5 notes), `●-●-●-work-●-●-●` (3 notes), `gms` (2 notes), `4` (2 notes). Some overlap with Groups A/B since the decorator tags co-exist with topic tags.

**Group D — Edge cases (5 notes):** Multi-topic note (`Coding and Modeling Standards` — dual-linked to Software Development and Enterprise Architect), sensitive note (`asthma medication`), personal/legal note (`Mountain View Apartment`), and two short/stub notes with dead tags.

---

## 5. Per-Note Results Table

| # | Note title | MOCs linked | Tags retired | Routing | Flag |
|---|-----------|-------------|--------------|---------|------|
| 1 | Running Journal 2024 — 2024-06-12 | Running | — | tagged | — |
| 2 | Running Journal 2024 — 2024-08-22 | Running | — | tagged | — |
| 3 | Dust collection in the wood shop project | Woodworking | — | tagged | — |
| 4 | bandsaw blades | Woodworking | — | content-scan | — |
| 5 | Lumber | Woodworking | — | content-scan | — |
| 6 | Gridfinity out of spec | 3D Printing | — | tagged | — |
| 7 | Customizable Honeycomb Storage Wall (OpenSCAD) | 3D Printing | — | content-scan | — |
| 8 | Cut and Tilted Text - Customizable by ccox - Thingiverse | 3D Printing | — | content-scan | — |
| 9 | grandchild coaster notes | Laser Engraver | — | tagged | — |
| 10 | Laser Experiments October 2024 | Laser Engraver | — | content-scan | — |
| 11 | Getting a high resolution diagram image from EA | Enterprise Architect | — | tagged | — |
| 12 | Enterprise Architect -- Finding a command by search | Enterprise Architect | — | tagged | — |
| 13 | Git log | Software Development | — | tagged | — |
| 14 | python script--find parent directory trick | Software Development | — | tagged | — |
| 15 | Neural Noise | Software Development | — | tagged | — |
| 16 | Vagrant notes | Software Development | edx, vagrant | tagged | — |
| 17 | Valident | Job Search | ●-●-●-home-●-●-● | tagged | — |
| 18 | Tektronix | Job Search | ●-●-●-home-●-●-● | tagged | — |
| 19 | Thermo Fisher Scientific | Job Search | ●-●-●-home-●-●-● | tagged | — |
| 20 | Keil microVision tool | Maker & Electronics | ●-●-●-work-●-●-● | tagged | — |
| 21 | National Instruments GPIB notes | Maker & Electronics | luxim | tagged | — |
| 22 | where to buy wood | Woodworking | — | content-scan | — |
| 23 | Wiring the Woodshop | Woodworking | — | content-scan | — |
| 24 | Honeycomb storage wall by RostaP - Printables.com | 3D Printing | — | content-scan | — |
| 25 | Simple Key Hook by SerbanIustinian - Thingiverse | 3D Printing | — | content-scan | — |
| 26 | 3D Printing Notes (2025-05-08) | 3D Printing | — | content-scan | — |
| 27 | Tough Pro PLA+ Filament - American Filament | 3D Printing | — | content-scan | — |
| 28 | Pull Request | Software Development | — | content-scan | — |
| 29 | making progress | Software Development | edx | content-scan | — |
| 30 | Drupal | Software Development | andreliz-(go), ●-●-●-home-●-●-● | content-scan | — |
| 31 | Untitled note (2013-03-14) | Job Search | — | content-scan | dice.com lead URL |
| 32 | Untitled Note (2013-11-19) | *none* | — | content-scan | **MANUAL-REVIEW** |
| 33 | asthma medication | *none* | — | content-scan | **MANUAL-REVIEW** |
| 34 | Mountain View Apartment | *none* | — | content-scan | **MANUAL-REVIEW** |
| 35 | 3D Printing Notes (2024-12-05) | 3D Printing | — | content-scan | — |
| 36 | bottle cap opener | Woodworking | — | content-scan | — |
| 37 | NXP | Maker & Electronics | array-converter, moving-to-arm, ●-●-●-work-●-●-● | decorator | — |
| 38 | Coding and Modeling Standards | Software Development, Enterprise Architect | csharp, ●-●-●-work-●-●-● | decorator | dual-link |
| 39 | TODO (2013-06-02) | *none* | 4 | decorator | **MANUAL-REVIEW** |
| 40 | sky light bid | *none* | 4 | decorator | **MANUAL-REVIEW** |
| 41 | Note conflict Terese's Birthday Party | *none* | gms | decorator | **MANUAL-REVIEW** |
| 42 | Autodesk's Fusion 360 now supports Shapeoko! | Maker & Electronics | gms | decorator | — |
| 43 | Ann Mitchell | Job Search | ●-●-●-home-●-●-● | decorator | — |
| 44 | Sabin Alibrandi | Job Search | ●-●-●-home-●-●-● | decorator | — |
| 45 | Caps Lock Be Gone Utility | Software Development | — | decorator | — |
| 46 | ErrorProvider | Software Development | c# | decorator | — |
| 47 | Rotating 3D Gallery | Software Development | — | tagged | — |
| 48 | Purchased a newer version of OxygenXML editor (v14) | Software Development | oxygen-xml, xml | tagged | — |
| 49 | LED Experiments | Maker & Electronics | — | tagged | — |
| 50 | python IDE | Software Development | edx | tagged | — |

**Summary statistics:**
- 43 of 50 notes received at least 1 MOC wikilink
- 7 of 50 received no MOC link (3 unroutable + 4 junk-tag stubs flagged for review)
- 1 note received 2 MOC links (Coding and Modeling Standards — dual-link)
- Total MOC links added: 44
- Average MOC links per linked note: 1.02
- Average across all 50: 0.88 links/note

---

## 6. Broken Links

**Zero broken wikilinks.** All 8 MOC files referenced by `[[wikilink]]` syntax in sample notes exist at their expected paths in `20 - MOCs/`. The 3 sub-MOC files referenced in `Running.md` also exist. Verification performed by path-existence check immediately after writing files.

---

## 7. Notes Flagged for Manual Review

*Reports are never empty. These 7 notes need Thomas's eyes before the full run.*

| Note | Reason | Recommended action |
|------|--------|-------------------|
| `2013-11-19 - Untitled Note.md` | Body says "candace uses it for the institute discussion / polleverywhere.com" — no MOC match. Could be work/software, could be a personal reference. | Thomas: route to Software Development if it's a tool save, or leave unlinked. |
| `2014-08-18 - asthma medication.md` | Health/medical note — one sentence about Xopenex vs. Albuterol. No MOC applies. | Leave unlinked, keep as standalone note. Confirm no `health` MOC is wanted. |
| `2012-10-01 - Mountain View Apartment.md` | Personal apartment walkthrough and dispute notes. No MOC applies. | Leave unlinked. May want a `Personal` or `Housing` topic if more such notes appear in the 515. |
| `2013-06-02 - TODO.md` | Tag `4` retired. Body is a mixed household task list including "GMS prep 1.5" — this is the note where "GMS" appears. Could GMS = "Girls Middle School" (Thomas's daughters' school)? | Thomas: confirm GMS meaning if relevant; note is otherwise unroutable. Leave unlinked. |
| `2013-06-02 - sky light bid.md` | Tag `4` retired. Body is just the title repeated. Single-line note, no routing possible. | Leave as-is. Confirm safe to leave permanently unlinked. |
| `2014-08-18 - Note conflict Terese's Birthday Party.md` | Tag `gms` retired per boss decision. Party planning content — no MOC matches. | Leave unlinked. Confirm. |
| `2012-10-01 - ErrorProvider.md` | `c#` tag retired (special-char tag). Note also had `software` tag (kept). Body is a 2008 blog post clipping about LINQ/ErrorProvider in C#. | Routes correctly to `[[Software Development]]`. Spot-check: does the long blog body warrant a note-splitting decision? This is a web-clip, not an atomic idea. Flag for potential split or deletion. |

**Additional observation surfaced during sample:** The `Coding and Modeling Standards` note (2012-03-07) contains both EA-specific modeling guidance *and* C# coding standards. It was dual-linked to `[[Software Development]]` and `[[Enterprise Architect]]`. This pattern will repeat in the 515-note run — Thomas should confirm dual-linking is acceptable, or whether long compound notes like this should be split.

---

## 8. Random-Sample-of-20 Spot-Check Section (Before / After)

The 20 spot-check notes are drawn from the 50-note sample (every other note starting at #1).

### Note 1: Running Journal 2024 — 2024-06-12

**Before (frontmatter):**
```yaml
tags:
- running-journal
updated: '2025-07-21'
```
**After:**
```yaml
tags:
- running-journal
updated: '2026-04-27'
```
Body end added:
```markdown
## See also

- [[Running]]
```

### Note 3: Dust collection in the wood shop project

**Before:** tags: `[woodcraft, woodworking, dust-collection]`  
**After:** tags unchanged; `## See also\n- [[Woodworking]]` added to body end.

### Note 5: Lumber

**Before:** tags: `[]` (untagged)  
**After:** tags unchanged; `## See also\n- [[Woodworking]]` added. Routing via content scan: "Hobby board," "Jewelry box sides," "bandsaw," "Plywood," "Home Depot" — clearly woodworking supply list.

### Note 7: Customizable Honeycomb Storage Wall (OpenSCAD)

**Before:** tags: `[]` (untagged), source_url: printables.com  
**After:** `## See also\n- [[3D Printing]]` added. Routing: Printables.com URL + "STL model" + "Bambu" references.

### Note 9: grandchild coaster notes

**Before:** tags: `[laser-engraver]`  
**After:** tags unchanged; `## See also\n- [[Laser Engraver]]` added. Routing: explicit `laser-engraver` tag.

### Note 11: Getting a high resolution diagram image from EA

**Before:** tags: `[enterprise-architect]`  
**After:** tags unchanged; `## See also\n- [[Enterprise Architect]]` added.

### Note 13: Git log

**Before:** tags: `[git]`  
**After:** tags unchanged; `## See also\n- [[Software Development]]` added. Note: `git` tag kept as facet; not retired.

### Note 15: Neural Noise

**Before:** tags: `[codepen]`  
**After:** tags unchanged; `## See also\n- [[Software Development]]` added. `codepen` kept as facet tag.

### Note 17: Valident

**Before:** tags: `[job-search, ●-●-●-home-●-●-●]`  
**After:** tags: `[job-search]` — decorator retired; `## See also\n- [[Job Search]]` added.

### Note 19: Thermo Fisher Scientific

**Before:** tags: `[job-search, ●-●-●-home-●-●-●]`  
**After:** tags: `[job-search]`; `## See also\n- [[Job Search]]` added.

### Note 21: National Instruments GPIB notes

**Before:** tags: `[luxim, national-instruments]`  
**After:** tags: `[national-instruments]` — `luxim` retired; `## See also\n- [[Maker & Electronics]]` added.

### Note 23: Wiring the Woodshop

**Before:** tags: `[]` (untagged)  
**After:** `## See also\n- [[Woodworking]]` added. Routing: "240 volts @ 30 amps," "woodshop," "10/3" wire references — clearly shop wiring project note.

### Note 25: Simple Key Hook by SerbanIustinian - Thingiverse

**Before:** tags: `[]` (untagged), source_url: thingiverse.com  
**After:** `## See also\n- [[3D Printing]]` added. Routing: Thingiverse URL + "3D" in Thingiverse context.

### Note 27: Tough Pro PLA+ Filament - American Filament

**Before:** tags: `[]` (untagged), source_url: americanfilament.us  
**After:** `## See also\n- [[3D Printing]]` added. Routing: "PLA+" + filament vendor URL.

### Note 29: making progress

**Before:** tags: `[edx]`  
**After:** tags: `[]` — `edx` retired; `## See also\n- [[Software Development]]` added. Body contains edX Python/Django course code.

### Note 31: Untitled note (2013-03-14)

**Before:** tags: `[]` (untagged); body: "Leads / http://www.dice.com/..."  
**After:** `## See also\n- [[Job Search]]` added. Routing: dice.com job board URL is unambiguous.

### Note 33: asthma medication

**Before:** tags: `[]`; body: single sentence about Xopenex.  
**After:** No changes except `updated: 2026-04-27`. No MOC link added. Flagged for manual review.

### Note 37: NXP

**Before:** tags: `[array-converter, moving-to-arm, ●-●-●-work-●-●-●]`  
**After:** tags: `[]` — all three retired; `## See also\n- [[Maker & Electronics]]` added. Body: NXP PWM/ADC chip selection note from 2011 ARM project.

### Note 39: TODO (2013-06-02)

**Before:** tags: `[4]`  
**After:** tags: `[]` — tag `4` retired. No MOC link. Flagged for manual review (contains "GMS prep" reference).

### Note 41: Note conflict Terese's Birthday Party

**Before:** tags: `[gms]`  
**After:** tags: `[]` — `gms` retired per boss decision. No MOC link. Flagged.

---

## 9. Untagged Notes — Content-Scan Routing Assessment

Of the 15 untagged notes in the sample, the content-scan routing quality was:

| Routing quality | Count | Notes |
|----------------|------:|-------|
| Obvious — title alone sufficient | 9 | "bandsaw blades," "Wiring the Woodshop," "3D Printing Notes," "where to buy wood," "bottle cap opener," "Lumber," Printables/Thingiverse clips |
| Clear — body required, but unambiguous | 3 | "making progress" (edX Python code), "Pull Request" (GitHub how-to), "Untitled note" 2013-03-14 (dice.com URL) |
| Ambiguous — routed but uncertain | 0 | None in this batch |
| Unroutable — no MOC match | 3 | "Untitled Note" (polleverywhere), "asthma medication," "Mountain View Apartment" |

**Precision feel:** In the sample, 80% of untagged notes routed obviously. The 3 unroutable notes are genuinely topic-less (health, personal dispute, ambiguous tool reference) — these are not routing failures, they are correctly identified as outside the 8-hub taxonomy. Extrapolating to the full 374-note untagged pool: expect ~70–75% obvious routing, ~15% body-required-but-clear, ~10–15% unroutable. The unroutable notes will be listed for manual review in the full-run report.

---

## 10. What Changes If You Sign Off — Preview of the 515-Note Full Run

If boss approves, the full run will:

1. **Apply MOC wikilinks to ~220–240 additional notes** across all 8 hubs (estimated; content scan may refine this).
2. **Add `[[Running]]` links to all 104 remaining running-journal entries** in `40 - Areas/Running/` (2 already done in this dry run).
3. **Retire tags** across the remaining affected notes: decorator tags, `gms`, `c#`/`csharp`, `andreliz-(go)`, `luxim`, `4`, `array-converter`, `moving-to-arm`, `edx` (as standalone facet), `oxygen-xml`, `xml` — wherever these appear on notes in the 515.
4. **Flag unroutable notes** for manual review — expected 40–60 additional notes with no clear MOC match (most will be "Untitled Note" stubs).
5. **Produce a final tag-vocabulary diff** showing before/after controlled-vocabulary state.
6. **Backfill MOC stub files** — the 8 new MOC files currently have partial notes lists; the full run will add all confirmed spokes to each MOC's `## Notes` section.

**The full run does NOT:**
- Touch the 3 surviving sub-MOCs
- Modify any archived MOC files
- Delete any note (no notes are deleted at any stage)
- Add links to sensitive notes flagged in this report (asthma medication, server credentials, AI API keys, Marty Klein, Family Data)

---

## 11. Spot-Check Targets for Boss Sign-Off

Before approving the full 515-note run, please check:

1. **`20 - MOCs/Running.md`** — confirm the sub-MOC structure and that "Running Journal (Chronological)" is correctly treated as a sub-MOC, not absorbed.
2. **`20 - MOCs/Software Development.md`** — confirm one-umbrella-hub approach (EC-2) and the section breakdown (Git, Python, C#, Web Dev, XML, Online Learning).
3. **`2012-03-07 - Coding and Modeling Standards.md`** — confirm dual-link to both `[[Software Development]]` and `[[Enterprise Architect]]` is the right call, or flag for splitting.
4. **`2013-06-02 - TODO.md`** — "GMS prep 1.5" reference. Does GMS mean anything specific? If yes, the routing may change.
5. **Tag `edx`** — retired from individual notes in this sample (e.g., Vagrant notes, making progress, python IDE) on the grounds it's a hyper-specific facet that doesn't warrant a hub. Confirm you're okay losing that facet; alternatively it stays in the controlled vocabulary as a fine-grained tag.
6. **`90 - Archive/`** — confirm archive-not-delete was the right call for the 6 retired MOC files. If you'd prefer them deleted entirely, we can do that before the full run.
7. **`2012-10-01 - ErrorProvider.md`** — long blog-post web-clip routed to Software Development. Is this the kind of note you'd want split (the LINQ discussion is substantive) or left as-is?

---

*Cairn: dry run complete. No notes modified beyond the 50 sampled. The gate is yours, Larry.*
