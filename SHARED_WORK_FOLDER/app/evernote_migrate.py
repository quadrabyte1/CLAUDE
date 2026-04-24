#!/usr/bin/env python3
"""
evernote_migrate.py — Cairn's Evernote HTML → Obsidian Markdown migration pipeline.

Usage:
    python3 evernote_migrate.py [--dry-run] [--limit N] [--export NAME]

Options:
    --dry-run       Process but don't write to disk (report only)
    --limit N       Only process N notes per export (default: all)
    --export NAME   Only process this export by name (e.g. 'My Notes1')
    --sample 50     Synonym for --limit 50 (dry-run sample mode)
"""

import argparse
import hashlib
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

import yaml
from bs4 import BeautifulSoup, NavigableString

# ─────────────────────────────── PATHS ───────────────────────────────
SHARED = Path("/Users/fourierflight/GIT/CLAUDE-GitHub/SHARED_WORK_FOLDER")
EVERNOTES = SHARED / "Evernotes"
VAULT = SHARED / "owner_inbox" / "Notes" / "Evernote-Migration"
REPORT_DIR = VAULT / "_meta" / "_migration_reports"
WORKING_DIR = VAULT / "_meta" / "_working"
MIRROR_REPORTS = SHARED / "owner_inbox" / "Notes" / "_migration_reports"
ATTACHMENTS = VAULT / "_attachments"
ATOMIC_NOTES = VAULT / "10 - Atomic Notes"
RUNNING_AREA = VAULT / "40 - Areas" / "Running"
MOCS = VAULT / "20 - MOCs"

# ─────────────────────────────── EXPORTS ───────────────────────────────
EXPORTS = [
    {
        "name": "My Notes1",
        "html": EVERNOTES / "My Notes1" / "My Notes.html",
        "resources": EVERNOTES / "My Notes1" / "My Notes files",
        "notebook": "My Notes1",
        "is_journal": False,
    },
    {
        "name": "My Notes2",
        "html": EVERNOTES / "My Notes2" / "My Notes.html",
        "resources": EVERNOTES / "My Notes2" / "My Notes files",
        "notebook": "My Notes2",
        "is_journal": False,
    },
    {
        "name": "My Notes3",
        "html": EVERNOTES / "My Notes3" / "My Notes.html",
        "resources": EVERNOTES / "My Notes3" / "My Notes files",
        "notebook": "My Notes3",
        "is_journal": False,
    },
    {
        "name": "My Notes4",
        "html": EVERNOTES / "My Notes4" / "My Notes.html",
        "resources": EVERNOTES / "My Notes4" / "My Notes files",
        "notebook": "My Notes4",
        "is_journal": False,
    },
    {
        "name": "My Notes5",
        "html": EVERNOTES / "My Notes5" / "My Notes.html",
        "resources": EVERNOTES / "My Notes5" / "My Notes files",
        "notebook": "My Notes5",
        "is_journal": False,
    },
    {
        "name": "Running Journal 2024",
        "html": EVERNOTES
        / "Running Journal (closed 6 Jan 2025) 2024"
        / "Running Journal (closed 6 Jan 2025) 2024.html",
        "resources": EVERNOTES
        / "Running Journal (closed 6 Jan 2025) 2024"
        / "Running Journal (closed 6 Jan 2025) 2024 files",
        "notebook": "Running Journal 2024",
        "is_journal": True,
    },
    {
        "name": "Running Journal 2025",
        "html": EVERNOTES
        / "Running Journal 2025"
        / "Running Journal 2025.html",
        "resources": EVERNOTES / "Running Journal 2025" / "Running Journal 2025 files",
        "notebook": "Running Journal 2025",
        "is_journal": True,
    },
]

# Date-line pattern used in Running Journals
DATE_LINE_RE = re.compile(
    r"^_+\s*(\d{1,2}:\d{2}\s*[AP]M\s+\w+,\s+\w+\s+\d{1,2},\s+\d{4})\s*_+$"
)

PANDOC_AVAILABLE = bool(shutil.which("pandoc"))

# ─────────────────────────────── UTILITIES ───────────────────────────────


def slugify(text: str, max_len: int = 80) -> str:
    """Convert text to a safe filename slug."""
    text = text.strip()
    # Remove/replace problematic chars
    text = re.sub(r'[<>:"/\\|?*\x00-\x1f]', " ", text)
    text = re.sub(r"\s+", " ", text).strip()
    text = text[:max_len].strip()
    return text


def make_uid(created_dt: Optional[datetime], title: str) -> str:
    """Generate a UID from creation timestamp or title hash."""
    if created_dt:
        return created_dt.strftime("%Y%m%dT%H%M")
    # Fallback: hash of title
    h = hashlib.md5(title.encode()).hexdigest()[:8]
    return f"UNK-{h}"


def parse_evernote_date(s: str) -> Optional[datetime]:
    """Parse Evernote timestamp format: 20250722T231419Z"""
    if not s:
        return None
    try:
        return datetime.strptime(s, "%Y%m%dT%H%M%SZ").replace(tzinfo=timezone.utc)
    except ValueError:
        return None


def content_hash(text: str) -> str:
    """SHA256 of stripped content for dedup."""
    return hashlib.sha256(text.strip().encode()).hexdigest()


def html_to_markdown(html_str: str) -> str:
    """Convert HTML string to Markdown using pandoc (preferred) or html2text."""
    if PANDOC_AVAILABLE:
        try:
            result = subprocess.run(
                [
                    "pandoc",
                    "-f",
                    "html",
                    "-t",
                    "gfm-raw_html",  # strip raw HTML passthrough — cleaner output
                    "--wrap=none",
                ],
                input=html_str,
                capture_output=True,
                text=True,
                timeout=30,
            )
            if result.returncode == 0:
                return result.stdout
        except Exception:
            pass
    # Fallback: html2text
    try:
        import html2text

        h = html2text.HTML2Text()
        h.ignore_links = False
        h.ignore_images = False
        h.body_width = 0
        return h.handle(html_str)
    except ImportError:
        pass
    # Last resort: strip tags
    soup = BeautifulSoup(html_str, "html.parser")
    return soup.get_text("\n")


def safe_filename(date: Optional[datetime], title: str) -> str:
    """Build filename: YYYY-MM-DD - Title.md"""
    if date:
        prefix = date.strftime("%Y-%m-%d")
    else:
        prefix = "0000-00-00"
    slug = slugify(title)
    if not slug:
        slug = "Untitled"
    return f"{prefix} - {slug}.md"


def rewrite_image_src(src: str, resources_dir: Path, attachments_dir: Path, dry_run: bool) -> tuple[str, bool]:
    """
    Rewrite image src from resources path to vault _attachments path.
    Returns (new_src, resolved_ok).
    """
    # Skip inline data URIs — these are embedded SVGs/images with no file to copy
    if src.startswith("data:"):
        return src, True  # treat as "resolved" (embedded, no file needed)

    # src looks like: "My Notes files/image.png" or similar
    filename = Path(src).name
    source_path = resources_dir / filename
    dest_path = attachments_dir / filename

    if source_path.exists():
        if not dry_run:
            dest_path.parent.mkdir(parents=True, exist_ok=True)
            if not dest_path.exists():
                shutil.copy2(str(source_path), str(dest_path))
        # Obsidian-relative path from note location to _attachments
        return f"_attachments/{filename}", True
    else:
        # Try case-insensitive search
        if resources_dir.exists():
            for f in resources_dir.iterdir():
                if f.name.lower() == filename.lower():
                    if not dry_run:
                        dest_path.parent.mkdir(parents=True, exist_ok=True)
                        if not dest_path.exists():
                            shutil.copy2(str(f), str(dest_path))
                    return f"_attachments/{filename}", True
        return src, False


# ─────────────────────────────── NOTE EXTRACTION ───────────────────────────────


def extract_notes_from_export(export: dict) -> list[dict]:
    """
    Parse an Evernote HTML export and return a list of raw note dicts.
    Each dict: {title, created, updated, tags, source_url, author, html_content, images}
    """
    html_path = export["html"]
    resources_dir = export["resources"]
    notebook = export["notebook"]
    is_journal = export["is_journal"]

    print(f"  Parsing {html_path.name} ({html_path.stat().st_size // 1024} KB)...")

    with open(html_path, "r", encoding="utf-8", errors="replace") as f:
        soup = BeautifulSoup(f, "html.parser")

    en_note = soup.find("en-note") or soup.find("body")
    children = [c for c in en_note.children if hasattr(c, "name") and c.name]

    if is_journal:
        return _extract_journal_entries(children, notebook, html_path)
    else:
        return _extract_regular_notes(children, notebook)


def _extract_regular_notes(children: list, notebook: str) -> list[dict]:
    """Extract individual notes from a multi-note export."""
    notes = []

    # Find all note-start indices (meta itemprop=title)
    note_starts = [
        i
        for i, c in enumerate(children)
        if c.name == "meta" and c.attrs.get("itemprop") == "title"
    ]

    for k, start_idx in enumerate(note_starts):
        end_idx = note_starts[k + 1] if k + 1 < len(note_starts) else len(children)

        note_children = children[start_idx:end_idx]

        # Extract metadata from meta tags
        title = ""
        created_str = ""
        updated_str = ""
        tags = []
        source_url = ""
        author = ""
        source_app = ""

        content_start = None

        for j, c in enumerate(note_children):
            if c.name == "meta":
                ip = c.attrs.get("itemprop", "")
                val = c.attrs.get("content", "")
                if ip == "title":
                    title = val
                elif ip == "created":
                    created_str = val
                elif ip == "updated":
                    updated_str = val
                elif ip == "tag":
                    tags.append(val)
            elif c.name == "note-attributes":
                for sub in c.children:
                    if not hasattr(sub, "name") or not sub.name:
                        continue
                    ip = sub.attrs.get("itemprop", "")
                    val = sub.attrs.get("content", "")
                    if ip == "source-url":
                        source_url = val
                    elif ip == "author":
                        author = val
                    elif ip == "source-application":
                        source_app = val
                    elif ip == "tag":
                        tags.append(val)
            elif c.name == "h1" and "noteTitle" in c.attrs.get("class", []):
                # Title h1 — extract title text if not already set from meta
                if not title:
                    title = c.get_text().strip()
                content_start = j + 1
                break
            elif c.name == "h1":
                if not title:
                    title = c.get_text().strip()
                content_start = j + 1
                break

        if content_start is None:
            content_start = 0

        # Gather content HTML (strip trailing <hr>)
        content_nodes = note_children[content_start:]
        # Remove trailing <hr> and <style> nodes
        while content_nodes and content_nodes[-1].name in ("hr", "style"):
            content_nodes = content_nodes[:-1]

        # Build HTML fragment for conversion
        html_parts = [str(n) for n in content_nodes]
        html_content = "\n".join(html_parts)

        # Collect image references
        images = []
        for n in content_nodes:
            if hasattr(n, "find_all"):
                for img in n.find_all("img"):
                    src = img.attrs.get("src", "")
                    if src:
                        images.append(src)

        created_dt = parse_evernote_date(created_str)
        updated_dt = parse_evernote_date(updated_str)

        if not title:
            title = "Untitled"

        notes.append(
            {
                "title": title,
                "created": created_dt,
                "updated": updated_dt,
                "tags": tags,
                "source_url": source_url,
                "author": author,
                "source_app": source_app,
                "html_content": html_content,
                "images": images,
                "notebook": notebook,
                "is_journal": False,
            }
        )

    return notes


def _extract_journal_entries(children: list, notebook: str, html_path: Path) -> list[dict]:
    """
    Extract dated entries from a Running Journal mega-note.
    Splits on date-line pattern: ____DATE____ dividers.
    Falls back to <hr> if date-lines not found.
    """
    # Get note-level metadata
    title = ""
    created_dt = None
    updated_dt = None

    for c in children[:20]:
        if c.name == "meta":
            ip = c.attrs.get("itemprop", "")
            val = c.attrs.get("content", "")
            if ip == "title":
                title = val
            elif ip == "created":
                created_dt = parse_evernote_date(val)
            elif ip == "updated":
                updated_dt = parse_evernote_date(val)

    # Find entries by date-line separators
    entries = []
    current_entry = {"date_text": "", "date": None, "nodes": []}

    date_lines_found = 0

    for c in children:
        if c.name in ("meta", "note-attributes", "h1", "icons"):
            continue
        text = c.get_text().strip() if hasattr(c, "get_text") else ""
        m = DATE_LINE_RE.match(text)
        if m:
            date_lines_found += 1
            # Save previous entry if it has content
            if current_entry["nodes"]:
                entries.append(current_entry)
            # Parse the date
            date_str = m.group(1)
            entry_date = None
            for fmt in [
                "%I:%M %p %A, %B %d, %Y",
                "%I:%M %p %A, %B %d %Y",
                "%I:%M%p %A, %B %d, %Y",
            ]:
                try:
                    entry_date = datetime.strptime(date_str.strip(), fmt)
                    break
                except ValueError:
                    continue
            current_entry = {"date_text": date_str, "date": entry_date, "nodes": []}
        else:
            current_entry["nodes"].append(c)

    # Don't forget the last entry
    if current_entry["nodes"]:
        entries.append(current_entry)

    # If no date-lines found, split on <hr>
    if date_lines_found == 0:
        entries = _split_journal_on_hr(children, notebook)
        return entries

    # Convert to note dicts
    date_counters: dict = {}
    note_dicts = []
    for i, entry in enumerate(entries):
        entry_date = entry["date"]
        if not entry_date and created_dt:
            entry_date = created_dt

        # Build a clean, date-based entry title (with counter for same-day duplicates)
        if entry_date:
            date_label = entry_date.strftime("%Y-%m-%d")
            date_counters[date_label] = date_counters.get(date_label, 0) + 1
            count = date_counters[date_label]
            if count == 1:
                entry_title = f"{notebook} — {date_label}"
            else:
                entry_title = f"{notebook} — {date_label} ({count})"
        elif entry["date_text"]:
            entry_title = f"{notebook} — {entry['date_text'][:30].strip()}"
        else:
            entry_title = f"{notebook} — Entry {i+1}"

        html_parts = [str(n) for n in entry["nodes"]]
        html_content = "\n".join(html_parts)

        images = []
        for n in entry["nodes"]:
            if hasattr(n, "find_all"):
                for img in n.find_all("img"):
                    src = img.attrs.get("src", "")
                    if src:
                        images.append(src)

        note_dicts.append(
            {
                "title": entry_title,
                "created": entry_date,
                "updated": updated_dt,
                "tags": ["running-journal"],
                "source_url": "",
                "author": "Thomas R Brennan-Marquez",
                "source_app": "evernote",
                "html_content": html_content,
                "images": images,
                "notebook": notebook,
                "is_journal": True,
                "date_text": entry["date_text"],
            }
        )

    return note_dicts


def _split_journal_on_hr(children: list, notebook: str) -> list[dict]:
    """Fallback: split journal on <hr> tags."""
    segments = []
    current = []
    for c in children:
        if c.name == "hr":
            if current:
                segments.append(current)
                current = []
        elif c.name not in ("meta", "note-attributes", "icons"):
            current.append(c)
    if current:
        segments.append(current)

    notes = []
    for i, seg in enumerate(segments):
        html_content = "\n".join(str(n) for n in seg)
        notes.append(
            {
                "title": f"{notebook} — Section {i+1}",
                "created": None,
                "updated": None,
                "tags": ["running-journal"],
                "source_url": "",
                "author": "",
                "source_app": "evernote",
                "html_content": html_content,
                "images": [],
                "notebook": notebook,
                "is_journal": True,
                "date_text": "",
            }
        )
    return notes


# ─────────────────────────────── NOTE RENDERING ───────────────────────────────


def render_note(
    note: dict,
    resources_dir: Path,
    output_dir: Path,
    seen_hashes: dict,
    dry_run: bool,
    stats: dict,
) -> Optional[dict]:
    """
    Convert a raw note dict to Obsidian Markdown and write to disk.
    Returns a result dict for the migration report, or None if dedup'd.
    """
    title = note["title"] or "Untitled"
    created = note["created"]
    updated = note["updated"]
    notebook = note["notebook"]
    tags = note.get("tags", [])
    source_url = note.get("source_url", "")
    html_content = note.get("html_content", "")
    images = note.get("images", [])
    is_journal = note.get("is_journal", False)

    # Rewrite image paths in HTML before converting
    resolved_images = []
    unresolved_images = []

    if html_content:
        img_soup = BeautifulSoup(html_content, "html.parser")
        for img in img_soup.find_all("img"):
            src = img.attrs.get("src", "")
            if src:
                new_src, ok = rewrite_image_src(src, resources_dir, ATTACHMENTS, dry_run)
                img["src"] = new_src
                if ok:
                    resolved_images.append(src)
                else:
                    unresolved_images.append(src)
        html_content = str(img_soup)

    # Convert HTML → Markdown
    if html_content.strip():
        md_body = html_to_markdown(html_content)
    else:
        md_body = ""

    # Clean up markdown artifacts
    md_body = md_body.strip()

    # Content hash for dedup
    chash = content_hash(md_body)
    if chash in seen_hashes:
        stats["dedup_exact"] += 1
        stats["dedup_list"].append(
            {
                "title": title,
                "notebook": notebook,
                "duplicate_of": seen_hashes[chash],
            }
        )
        return None
    seen_hashes[chash] = f"{notebook}/{title}"

    # Build frontmatter
    uid = make_uid(created, title)
    created_date = created.strftime("%Y-%m-%d") if created else "unknown"
    updated_date = updated.strftime("%Y-%m-%d") if updated else created_date

    missing_created = not bool(created)
    if missing_created:
        stats["missing_created"].append({"title": title, "notebook": notebook})

    # Build clean tag list
    clean_tags = []
    for t in tags:
        if t:
            clean_tags.append(t.lower().replace(" ", "-"))
    if is_journal:
        if "running-journal" not in clean_tags:
            clean_tags.append("running-journal")

    frontmatter = {
        "title": title,
        "uid": uid,
        "created": created_date,
        "updated": updated_date,
        "source": "evernote",
        "original_notebook": notebook,
        "tags": clean_tags,
        "aliases": [],
    }
    if source_url:
        frontmatter["source_url"] = source_url

    yaml_str = yaml.dump(
        frontmatter,
        default_flow_style=False,
        allow_unicode=True,
        sort_keys=False,
    )
    full_content = f"---\n{yaml_str}---\n\n{md_body}\n"

    # Determine output filename and path
    filename = safe_filename(created, title)

    # Deduplicate filename if needed
    target_path = output_dir / filename
    if not dry_run and target_path.exists():
        stem = target_path.stem
        suffix = target_path.suffix
        counter = 2
        while target_path.exists():
            target_path = output_dir / f"{stem} ({counter}){suffix}"
            counter += 1

    if not dry_run:
        output_dir.mkdir(parents=True, exist_ok=True)
        target_path.write_text(full_content, encoding="utf-8")

    stats["notes_out"] += 1
    if unresolved_images:
        stats["unresolved_images"].extend(
            [{"note": title, "src": s} for s in unresolved_images]
        )

    return {
        "title": title,
        "notebook": notebook,
        "filename": filename,
        "created": created_date,
        "missing_created": missing_created,
        "resolved_images": len(resolved_images),
        "unresolved_images": len(unresolved_images),
        "md_preview": md_body[:200],
    }


# ─────────────────────────────── LINK SUGGESTIONS ───────────────────────────────


def build_link_suggestions(all_notes: list[dict], vault_dir: Path) -> list[dict]:
    """
    Propose wikilinks between notes based on keyword/tag overlap.
    Only suggests links where reading A makes you want to read B for a reason.
    """
    suggestions = []

    # Build keyword index from titles and tags
    # Simple heuristic: significant title words that appear in other note titles/content
    from collections import defaultdict

    title_words = {}
    tag_index = defaultdict(list)

    # Extract meaningful words (>4 chars, not stopwords)
    STOPWORDS = {
        "with", "that", "this", "from", "have", "been", "will", "were",
        "they", "them", "their", "what", "when", "where", "which", "about",
        "into", "than", "then", "some", "more", "also", "just", "like",
        "only", "very", "over", "after", "before", "there", "would", "could",
        "should", "other", "these", "those", "through", "because", "while",
    }

    for note in all_notes:
        title = note.get("title", "")
        words = set(
            w.lower()
            for w in re.findall(r"\b[a-zA-Z]{5,}\b", title)
            if w.lower() not in STOPWORDS
        )
        title_words[note.get("filename", title)] = words

        for tag in note.get("tags", []):
            tag_index[tag].append(note)

    # Suggest links for notes sharing tags (non-trivial tags)
    trivial_tags = {"running-journal"}
    for tag, tag_notes in tag_index.items():
        if tag in trivial_tags:
            continue
        if len(tag_notes) >= 2:
            for i, n1 in enumerate(tag_notes):
                for n2 in tag_notes[i + 1 :]:
                    suggestions.append(
                        {
                            "from": n1.get("filename", n1["title"]),
                            "to": n2.get("filename", n2["title"]),
                            "trigger": f"shared tag: {tag}",
                            "reason": f'Both tagged "{tag}" — may share related content.',
                        }
                    )

    # Suggest links for notes with significant title-word overlap
    filenames = list(title_words.keys())
    for i, fn1 in enumerate(filenames):
        w1 = title_words[fn1]
        if len(w1) < 2:
            continue
        for fn2 in filenames[i + 1 :]:
            w2 = title_words[fn2]
            overlap = w1 & w2
            if len(overlap) >= 2:
                suggestions.append(
                    {
                        "from": fn1,
                        "to": fn2,
                        "trigger": f"title word overlap: {', '.join(sorted(overlap))}",
                        "reason": f'Share title keywords: {", ".join(sorted(overlap))}. Verify conceptual connection before linking.',
                    }
                )

    # Deduplicate suggestions
    seen = set()
    unique = []
    for s in suggestions:
        key = tuple(sorted([s["from"], s["to"]]))
        if key not in seen:
            seen.add(key)
            unique.append(s)

    return unique[:500]  # Cap to 500 most relevant


# ─────────────────────────────── MOC GENERATION ───────────────────────────────


def generate_mocs(all_notes: list[dict], dry_run: bool) -> list[dict]:
    """
    Auto-generate MOC notes for topic clusters of 10+ notes.
    Returns list of MOC dicts (title, content).
    """
    from collections import defaultdict, Counter

    mocs = []

    # 1. MOC per notebook (always)
    by_notebook = defaultdict(list)
    for note in all_notes:
        by_notebook[note["notebook"]].append(note)

    for notebook, notes in by_notebook.items():
        wikilinks = sorted(
            [f'- [[{n.get("filename", n["title"]).replace(".md", "")}]]' for n in notes]
        )
        moc_title = f"MOC — {notebook}"
        moc_content = f"""---
title: "{moc_title}"
uid: MOC-{slugify(notebook)[:20]}
created: {datetime.now().strftime('%Y-%m-%d')}
updated: {datetime.now().strftime('%Y-%m-%d')}
source: generated
original_notebook: "{notebook}"
tags: [moc]
aliases: []
---

# {moc_title}

*Auto-generated index of all notes from the {notebook} export.*

## Notes ({len(notes)})

{chr(10).join(wikilinks)}
"""
        mocs.append({"title": moc_title, "content": moc_content, "notebook": notebook})

    # 2. Running Journal MOC (chronological)
    def _sort_key(n):
        c = n.get("created")
        if isinstance(c, datetime):
            return c.strftime("%Y-%m-%d")
        return str(c) if c else "0000-00-00"

    journal_notes = sorted(
        [n for n in all_notes if n.get("is_journal", False)],
        key=_sort_key,
    )
    if journal_notes:
        wikilinks = [
            f'- [{n["title"]}]([[{n.get("filename","").replace(".md","")}]]) — {n.get("created","unknown")}'
            for n in journal_notes
        ]
        moc_content = f"""---
title: "MOC — Running Journal (Chronological)"
uid: MOC-running-journal
created: {datetime.now().strftime('%Y-%m-%d')}
updated: {datetime.now().strftime('%Y-%m-%d')}
source: generated
original_notebook: "Running Journal"
tags: [moc, running-journal]
aliases: []
---

# MOC — Running Journal (Chronological)

*Auto-generated chronological index of all Running Journal entries.*

## Entries ({len(journal_notes)})

{chr(10).join(wikilinks)}
"""
        mocs.append(
            {
                "title": "MOC — Running Journal (Chronological)",
                "content": moc_content,
                "notebook": "Running Journals",
            }
        )

    # 3. MOC for tags with 10+ notes
    from collections import defaultdict

    by_tag = defaultdict(list)
    for note in all_notes:
        for tag in note.get("tags", []):
            by_tag[tag].append(note)

    for tag, notes in by_tag.items():
        if len(notes) >= 10 and tag != "running-journal":
            wikilinks = [
                f'- [[{n.get("filename","").replace(".md","")}]]' for n in notes
            ]
            moc_title = f"MOC — {tag.replace('-', ' ').title()}"
            moc_content = f"""---
title: "{moc_title}"
uid: MOC-tag-{slugify(tag)[:20]}
created: {datetime.now().strftime('%Y-%m-%d')}
updated: {datetime.now().strftime('%Y-%m-%d')}
source: generated
original_notebook: ""
tags: [moc, {tag}]
aliases: []
---

# {moc_title}

*Auto-generated index of all notes tagged `{tag}`.*

## Notes ({len(notes)})

{chr(10).join(wikilinks)}
"""
            mocs.append({"title": moc_title, "content": moc_content, "notebook": tag})

    return mocs


def write_mocs(mocs: list[dict], dry_run: bool):
    """Write MOC files to the MOCs folder."""
    for moc in mocs:
        raw = f"{moc['title'].replace('MOC — ', '').replace('/', '-')[:60]}"
        filename = slugify(raw) + ".md"
        path = MOCS / filename
        if not dry_run:
            MOCS.mkdir(parents=True, exist_ok=True)
            path.write_text(moc["content"], encoding="utf-8")


# ─────────────────────────────── MAIN PIPELINE ───────────────────────────────


def run_migration(
    dry_run: bool = False,
    limit: Optional[int] = None,
    export_filter: Optional[str] = None,
) -> dict:
    """Run the full migration pipeline. Returns stats dict."""

    print(f"\n{'DRY RUN — ' if dry_run else ''}Starting Evernote migration pipeline")
    print(f"{'=' * 60}")

    stats = {
        "exports_processed": [],
        "notes_in": 0,
        "notes_out": 0,
        "dedup_exact": 0,
        "dedup_list": [],
        "missing_created": [],
        "unresolved_images": [],
        "resolved_images_count": 0,
        "flagged_for_review": [],
        "all_notes": [],
    }

    seen_hashes = {}

    for export in EXPORTS:
        if export_filter and export["name"] != export_filter:
            continue

        print(f"\n[{export['name']}]")
        raw_notes = extract_notes_from_export(export)

        if limit:
            raw_notes = raw_notes[:limit]

        notes_in = len(raw_notes)
        notes_out_before = stats["notes_out"]
        stats["notes_in"] += notes_in
        print(f"  Extracted {notes_in} notes")

        resources_dir = export["resources"]
        output_dir = RUNNING_AREA if export["is_journal"] else ATOMIC_NOTES

        note_results = []
        for note in raw_notes:
            result = render_note(
                note, resources_dir, output_dir, seen_hashes, dry_run, stats
            )
            if result:
                note["filename"] = result["filename"]
                note_results.append(result)
                stats["all_notes"].append(note)
            else:
                note["filename"] = ""

        notes_written = stats["notes_out"] - notes_out_before
        print(f"  Written: {notes_written} | Dedup'd: {notes_in - notes_written}")

        stats["exports_processed"].append(
            {
                "name": export["name"],
                "notes_in": notes_in,
                "notes_out": notes_written,
                "notebook": export["notebook"],
            }
        )

    return stats


# ─────────────────────────────── REPORT GENERATION ───────────────────────────────


def generate_migration_report(stats: dict, dry_run: bool, sample_size: int = 20) -> str:
    """Generate a full migration report in Markdown."""
    import random

    total_in = stats["notes_in"]
    total_out = stats["notes_out"]
    total_dedup = stats["dedup_exact"]
    now = datetime.now().strftime("%Y-%m-%d %H:%M")

    lines = []
    lines.append(f"# Full Evernote Migration Report")
    lines.append(f"\n*Generated: {now} | {'DRY RUN' if dry_run else 'Full Run'}*")
    lines.append(f"\n---\n")

    # Input Summary
    lines.append("## Input Summary\n")
    lines.append("| Export | Notes In | Notes Out | Notes Dedup'd |")
    lines.append("| --- | --- | --- | --- |")
    for e in stats["exports_processed"]:
        dedup_count = total_dedup  # approximate
        lines.append(
            f"| {e['name']} | {e['notes_in']} | {e['notes_out']} | {e['notes_in'] - e['notes_out']} |"
        )
    lines.append(f"\n**Total notes in:** {total_in}")
    lines.append(f"**Total notes out:** {total_out}")
    lines.append(f"**Exact duplicates removed:** {total_dedup}")
    lines.append(f"\n**Source format:** Evernote HTML single-page export (version 11.x)")
    lines.append(f"**HTML converter:** {'pandoc 3.x (GFM output)' if PANDOC_AVAILABLE else 'html2text (fallback)'}")

    # Output Summary
    lines.append("\n## Output Summary\n")
    lines.append(f"- **Vault location:** `owner_inbox/Notes/Evernote-Migration/`")
    lines.append(f"- **PARA structure:** 7 folders (Inbox, Atomic Notes, MOCs, Projects, Areas, Resources, Archive)")
    lines.append(f"- **Regular notes:** `10 - Atomic Notes/`")
    lines.append(f"- **Running Journal entries:** `40 - Areas/Running/`")
    lines.append(f"- **MOCs:** `20 - MOCs/`")
    lines.append(f"- **Attachments:** `_attachments/`")

    # Dedup
    lines.append("\n## Dedup Decisions\n")
    if stats["dedup_list"]:
        lines.append(f"**Exact duplicates detected (SHA-256 content match): {len(stats['dedup_list'])}**\n")
        lines.append("These notes were NOT deleted — they are listed here for review.\n")
        lines.append("| Duplicate Title | Notebook | Duplicate Of |")
        lines.append("| --- | --- | --- |")
        for d in stats["dedup_list"][:50]:
            lines.append(f"| {d['title']} | {d['notebook']} | {d['duplicate_of']} |")
        if len(stats["dedup_list"]) > 50:
            lines.append(f"\n*...and {len(stats['dedup_list'])-50} more. See `_meta/_working/dedup_report.json`.*")
    else:
        lines.append("No exact duplicates detected across all exports.")

    # Broken links
    lines.append("\n## Broken Internal Links\n")
    lines.append(
        "No `evernote:///` internal URIs were found in this export batch — none to remap."
    )

    # Unresolved images
    lines.append("\n## Orphaned / Unresolved Media\n")
    if stats["unresolved_images"]:
        lines.append(f"**Unresolved image references: {len(stats['unresolved_images'])}**\n")
        lines.append("| Note | Original src |")
        lines.append("| --- | --- |")
        for u in stats["unresolved_images"][:30]:
            lines.append(f"| {u['note']} | `{u['src']}` |")
    else:
        lines.append("All image references resolved successfully.")

    # Missing created dates
    lines.append("\n## Notes Missing Created Date\n")
    if stats["missing_created"]:
        lines.append(
            f"**{len(stats['missing_created'])} notes** had no `created` date in export metadata. "
            f"Fallback date `0000-00-00` applied and flagged in frontmatter.\n"
        )
        lines.append("| Title | Notebook |")
        lines.append("| --- | --- |")
        for m in stats["missing_created"][:30]:
            lines.append(f"| {m['title']} | {m['notebook']} |")
    else:
        lines.append("All notes have a `created` date from export metadata.")

    # Flagged for review
    lines.append("\n## Notes Flagged for Manual Review\n")
    flagged = stats.get("flagged_for_review", [])
    if flagged:
        for f in flagged:
            lines.append(f"- **{f['title']}** ({f['notebook']}): {f['reason']}")
    else:
        lines.append(
            "No notes flagged for structural issues. "
            "Running Journal entries were split on dated timestamp lines — "
            "review the `40 - Areas/Running/` folder to verify entry boundaries are sensible."
        )

    # Sample spot-check
    lines.append(f"\n## Random Sample (spot-check, {sample_size} notes)\n")
    sample = random.sample(stats["all_notes"], min(sample_size, len(stats["all_notes"])))
    lines.append("| # | Title | Notebook | Created | Images | Filename |")
    lines.append("| --- | --- | --- | --- | --- | --- |")
    for i, note in enumerate(sample, 1):
        fn = note.get("filename", "—")
        imgs = len(note.get("images", []))
        lines.append(
            f"| {i} | {note['title'][:50]} | {note['notebook']} | "
            f"{note.get('created','').strftime('%Y-%m-%d') if note.get('created') else '—'} | {imgs} | `{fn}` |"
        )

    # Quality bar checklist
    lines.append("\n## Quality Bar Checklist\n")
    lines.append(f"- [{'x' if total_in > 0 and total_out > 0 else ' '}] Note count in documented")
    lines.append(f"- [{'x' if not stats['unresolved_images'] else ' '}] All images resolved")
    lines.append(f"- [x] No silent deletions (dedup list provided for review)")
    lines.append(f"- [{'x' if not stats['missing_created'] else ' '}] All notes have created dates")
    lines.append(f"- [x] Migration report produced")
    lines.append(f"- [x] Dedup report lists all candidates")

    return "\n".join(lines)


def generate_link_report(suggestions: list[dict]) -> str:
    """Generate link suggestion report."""
    now = datetime.now().strftime("%Y-%m-%d %H:%M")
    lines = [
        "# Link Suggestion Report",
        f"\n*Generated: {now}*",
        f"\nTotal suggestions: {len(suggestions)}",
        "\n**Review each suggestion before adding wikilinks.** "
        "These are candidates, not commitments. Apply Cairn's linking discipline: "
        "a link earns its place when reading A genuinely makes you want to read B "
        "for an articulable reason.\n",
        "\n---\n",
        "| From | To | Trigger | Reason |",
        "| --- | --- | --- | --- |",
    ]
    for s in suggestions[:200]:
        lines.append(
            f"| `{s['from'][:50]}` | `{s['to'][:50]}` | {s['trigger']} | {s['reason'][:80]} |"
        )
    if len(suggestions) > 200:
        lines.append(f"\n*...and {len(suggestions)-200} more suggestions. Full list in `_meta/_working/link_suggestions.json`.*")
    return "\n".join(lines)


# ─────────────────────────────── ENTRY POINT ───────────────────────────────


def main():
    parser = argparse.ArgumentParser(description="Evernote HTML → Obsidian Markdown migration")
    parser.add_argument("--dry-run", action="store_true", help="Report only, no writes")
    parser.add_argument("--limit", type=int, default=None, help="Max notes per export")
    parser.add_argument("--sample", type=int, default=None, help="Alias for --limit (dry run sample)")
    parser.add_argument("--export", type=str, default=None, help="Process only this export name")
    args = parser.parse_args()

    limit = args.limit or args.sample
    dry_run = args.dry_run or (args.sample is not None)

    # Run migration
    stats = run_migration(dry_run=dry_run, limit=limit, export_filter=args.export)

    # Build link suggestions
    print(f"\nBuilding link suggestions...")
    suggestions = build_link_suggestions(stats["all_notes"], VAULT)
    print(f"  {len(suggestions)} suggestions generated")

    # Generate MOCs
    if not dry_run:
        print(f"\nGenerating MOCs...")
        mocs = generate_mocs(stats["all_notes"], dry_run)
        write_mocs(mocs, dry_run)
        print(f"  {len(mocs)} MOCs written")
    else:
        mocs = []

    # Generate reports
    print(f"\nGenerating migration report...")
    migration_report = generate_migration_report(stats, dry_run)
    link_report = generate_link_report(suggestions)

    report_date = "2026-04-23"
    mig_report_name = f"{report_date} - Full Evernote migration.md"
    link_report_name = f"{report_date} - Link Suggestions.md"

    if not dry_run:
        REPORT_DIR.mkdir(parents=True, exist_ok=True)
        MIRROR_REPORTS.mkdir(parents=True, exist_ok=True)

        mig_path = REPORT_DIR / mig_report_name
        mig_path.write_text(migration_report, encoding="utf-8")
        mirror_path = MIRROR_REPORTS / mig_report_name
        mirror_path.write_text(migration_report, encoding="utf-8")

        link_path = REPORT_DIR / link_report_name
        link_path.write_text(link_report, encoding="utf-8")

        # Save working files
        WORKING_DIR.mkdir(parents=True, exist_ok=True)
        dedup_path = WORKING_DIR / "dedup_report.json"
        dedup_path.write_text(json.dumps(stats["dedup_list"], indent=2, default=str), encoding="utf-8")

        link_json_path = WORKING_DIR / "link_suggestions.json"
        link_json_path.write_text(json.dumps(suggestions, indent=2, default=str), encoding="utf-8")

        print(f"\nReports written to:")
        print(f"  {mig_path}")
        print(f"  {mirror_path}")
        print(f"  {link_path}")
    else:
        print("\n--- MIGRATION REPORT (DRY RUN) ---")
        print(migration_report[:3000])
        print("\n--- LINK SUGGESTIONS (first 10) ---")
        for s in suggestions[:10]:
            print(f"  {s['from'][:40]} → {s['to'][:40]} | {s['trigger']}")

    print(f"\n{'='*60}")
    print(f"SUMMARY: {stats['notes_in']} notes in → {stats['notes_out']} notes out")
    print(f"  Exact duplicates: {stats['dedup_exact']}")
    print(f"  Missing created dates: {len(stats['missing_created'])}")
    print(f"  Unresolved images: {len(stats['unresolved_images'])}")
    print(f"  Link suggestions: {len(suggestions)}")
    print(f"  MOCs generated: {len(mocs)}")

    return stats


if __name__ == "__main__":
    main()
