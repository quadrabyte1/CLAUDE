"""
AI Team Workspace — Flask application
Serves a Notion-like UI over the workspace SQLite database.
"""

import os
import re
import sqlite3
from datetime import datetime, date
from pathlib import Path
from dotenv import load_dotenv

load_dotenv(Path(__file__).parent / ".env")

from flask import (
    Flask, render_template, request, redirect, url_for, g, abort, jsonify,
    send_from_directory,
)

app = Flask(__name__)

DB_PATH = os.path.join(os.path.dirname(__file__), "..", "db", "workspace.db")

APP_VERSION = "v4.18"  # unified version for all main-app pages, shown in every sticky footer

# ── Display baseline for task counts ──────────────────────────────────────
# Dashboard task counts only reflect tasks created after this id — bumped 2026-07-03
# at owner's request to re-zero the counter; raise this value again to re-zero later.
_TASK_COUNT_BASELINE_MAX_ID = 485

# ── Database initialisation ────────────────────────────────────────────────

_SCHEMA_PATH = os.path.normpath(os.path.join(
    os.path.dirname(__file__), "..", "db", "schema.sql"
))


def init_db():
    """Ensure all required tables exist and run lightweight migrations.

    On a fresh clone (no workspace.db), sourcing db/schema.sql creates every
    table, index, and seed row in one shot. The migrations below remain for
    the benefit of pre-schema.sql databases where columns were added via
    ALTER TABLE at different points in history.
    """
    # Make sure the containing db/ directory exists before SQLite opens it —
    # matters on a fresh clone where the folder may not exist yet.
    os.makedirs(os.path.dirname(DB_PATH), exist_ok=True)
    db = sqlite3.connect(DB_PATH)
    # Apply the canonical schema (idempotent — every statement uses IF NOT
    # EXISTS / INSERT OR IGNORE). This bootstraps a brand-new DB in one call
    # and is a no-op against an existing one.
    if os.path.exists(_SCHEMA_PATH):
        with open(_SCHEMA_PATH) as _f:
            db.executescript(_f.read())
    db.execute("""
        CREATE TABLE IF NOT EXISTS token_usage (
            id INTEGER PRIMARY KEY,
            month TEXT NOT NULL UNIQUE,
            tokens_purchased INTEGER NOT NULL DEFAULT 0,
            tokens_used INTEGER NOT NULL DEFAULT 0,
            updated_at TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%SZ', 'now'))
        )
    """)
    # Migration: add model column to team_members if missing
    cols = [row[1] for row in db.execute("PRAGMA table_info(team_members)").fetchall()]
    if "model" not in cols:
        db.execute("ALTER TABLE team_members ADD COLUMN model TEXT NOT NULL DEFAULT 'sonnet'")
    # Migration: add start_date column to token_usage if missing
    tu_cols = [row[1] for row in db.execute("PRAGMA table_info(token_usage)").fetchall()]
    if "start_date" not in tu_cols:
        db.execute("ALTER TABLE token_usage ADD COLUMN start_date TEXT")
    # Migration: add started_at column to tasks if missing
    task_cols = [row[1] for row in db.execute("PRAGMA table_info(tasks)").fetchall()]
    if "started_at" not in task_cols:
        db.execute("ALTER TABLE tasks ADD COLUMN started_at TEXT")
        db.execute("UPDATE tasks SET started_at = created_at WHERE started_at IS NULL")
    # Migration: create life_areas table if missing
    db.execute("""
        CREATE TABLE IF NOT EXISTS life_areas (
            id          INTEGER PRIMARY KEY,
            name        TEXT    NOT NULL UNIQUE,
            icon        TEXT,
            color       TEXT,
            sort_order  INTEGER NOT NULL DEFAULT 0,
            created_at  TEXT    NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%SZ', 'now')),
            updated_at  TEXT    NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%SZ', 'now'))
        )
    """)
    # Migration: create life_items table if missing
    db.execute("""
        CREATE TABLE IF NOT EXISTS life_items (
            id              INTEGER PRIMARY KEY,
            title           TEXT    NOT NULL,
            notes           TEXT,
            area_id         INTEGER REFERENCES life_areas(id) ON DELETE SET NULL,
            priority        TEXT    NOT NULL DEFAULT 'normal'
                                   CHECK (priority IN ('urgent', 'high', 'normal', 'low')),
            status          TEXT    NOT NULL DEFAULT 'open'
                                   CHECK (status IN ('open', 'done', 'snoozed', 'cancelled')),
            due_date        TEXT,
            recur_rule      TEXT,
            recur_interval  INTEGER,
            recur_anchor    TEXT,
            snoozed_until   TEXT,
            escalation_days INTEGER DEFAULT 3,
            completed_at    TEXT,
            created_at      TEXT    NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%SZ', 'now')),
            updated_at      TEXT    NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%SZ', 'now'))
        )
    """)
    db.execute("CREATE INDEX IF NOT EXISTS idx_life_items_area_id  ON life_items(area_id)")
    db.execute("CREATE INDEX IF NOT EXISTS idx_life_items_status   ON life_items(status)")
    db.execute("CREATE INDEX IF NOT EXISTS idx_life_items_due_date ON life_items(due_date)")
    # Seed life_areas with 7 defaults (idempotent)
    for name, icon, color, sort_order in [
        ("Home",            "🏠", "#8B5CF6", 1),
        ("Health",          "💪", "#10B981", 2),
        ("Finance",         "💰", "#F59E0B", 3),
        ("Relationships",   "👥", "#EC4899", 4),
        ("Career",          "💼", "#3B82F6", 5),
        ("Personal Growth", "📚", "#6366F1", 6),
        ("Admin & Errands", "📋", "#6B7280", 7),
    ]:
        db.execute(
            "INSERT OR IGNORE INTO life_areas (name, icon, color, sort_order) VALUES (?, ?, ?, ?)",
            (name, icon, color, sort_order),
        )
    # Migration: fix Hollis's missing persona_file column
    db.execute(
        """UPDATE team_members SET persona_file='team/hollis.md',
           updated_at=strftime('%Y-%m-%dT%H:%M:%SZ','now')
           WHERE name='Hollis' AND (persona_file IS NULL OR persona_file = '')"""
    )
    db.commit()
    db.close()


init_db()


# ── Database helpers ────────────────────────────────────────────────────────

def get_db():
    """Return a per-request database connection with standard PRAGMAs."""
    if "db" not in g:
        g.db = sqlite3.connect(DB_PATH)
        g.db.row_factory = sqlite3.Row
        g.db.execute("PRAGMA foreign_keys = ON")
        g.db.execute("PRAGMA journal_mode = WAL")
        g.db.execute("PRAGMA busy_timeout = 5000")
    return g.db


@app.teardown_appcontext
def close_db(exc):
    db = g.pop("db", None)
    if db is not None:
        db.close()


def query(sql, args=(), one=False):
    cur = get_db().execute(sql, args)
    rows = cur.fetchall()
    return (rows[0] if rows else None) if one else rows


def execute(sql, args=()):
    db = get_db()
    db.execute(sql, args)
    db.commit()


# ── Model sync helper ───────────────────────────────────────────────────────

_MODEL_RE = re.compile(r"^\-\s+\*\*Model:\*\*\s*(fable|opus|sonnet|haiku)\s*$", re.MULTILINE)
_VALID_TIERS = {"fable", "opus", "sonnet", "haiku"}


def _sync_team_member_models():
    """For every team_member with a persona_file, read the file, parse the
    **Model:** line, and update the DB row if the stored value differs.

    Edge cases handled:
    - persona_file is NULL or empty: skip (no write).
    - File does not exist or cannot be read: skip (no write).
    - Model line missing or unrecognised value: skip (no write).
    Only writes when a valid opus/sonnet/haiku value is positively parsed.
    """
    members = query("SELECT id, name, model, persona_file FROM team_members")
    db = get_db()
    changed = False
    for m in members:
        pf = m["persona_file"]
        if not pf:
            continue
        # Resolve relative path from repo root (parent of app/)
        full_path = os.path.normpath(os.path.join(_REPO_ROOT, pf))
        try:
            with open(full_path, encoding="utf-8", errors="replace") as fh:
                text = fh.read()
        except OSError:
            continue
        match = _MODEL_RE.search(text)
        if not match:
            continue
        declared = match.group(1)
        if declared != m["model"]:
            db.execute(
                "UPDATE team_members SET model=?, updated_at=strftime('%Y-%m-%dT%H:%M:%SZ','now') WHERE id=?",
                (declared, m["id"]),
            )
            changed = True
    if changed:
        db.commit()


# ── Markdown-ish rendering (no deps) ───────────────────────────────────────

def md(text):
    """Minimal markdown to HTML — handles headers, bold, italic, lists,
    code blocks, inline code, links, and paragraphs."""
    if not text:
        return ""
    import html as _html
    text = _html.escape(text)

    # Fenced code blocks
    text = re.sub(
        r"```(\w*)\n(.*?)```",
        lambda m: f'<pre class="bg-[#F7F6F3] rounded-lg p-4 text-sm overflow-x-auto my-4"><code>{m.group(2)}</code></pre>',
        text, flags=re.DOTALL,
    )
    # Inline code
    text = re.sub(r"`([^`]+)`", r'<code class="bg-[#F7F6F3] px-1.5 py-0.5 rounded text-sm">\1</code>', text)
    # Headers
    text = re.sub(r"^#### (.+)$", r'<h4 class="text-base font-semibold mt-6 mb-2 text-[#37352F]">\1</h4>', text, flags=re.MULTILINE)
    text = re.sub(r"^### (.+)$", r'<h3 class="text-lg font-semibold mt-6 mb-2 text-[#37352F]">\1</h3>', text, flags=re.MULTILINE)
    text = re.sub(r"^## (.+)$", r'<h2 class="text-xl font-semibold mt-8 mb-3 text-[#37352F]">\1</h2>', text, flags=re.MULTILINE)
    text = re.sub(r"^# (.+)$", r'<h1 class="text-2xl font-bold mt-8 mb-4 text-[#37352F]">\1</h1>', text, flags=re.MULTILINE)
    # Bold + italic
    text = re.sub(r"\*\*\*(.+?)\*\*\*", r"<strong><em>\1</em></strong>", text)
    text = re.sub(r"\*\*(.+?)\*\*", r"<strong>\1</strong>", text)
    text = re.sub(r"\*(.+?)\*", r"<em>\1</em>", text)
    # Links
    text = re.sub(r"\[([^\]]+)\]\(([^)]+)\)", r'<a href="\2" class="text-[#2383E2] hover:underline">\1</a>', text)
    # Unordered lists
    text = re.sub(r"^- (.+)$", r'<li class="ml-4 list-disc">\1</li>', text, flags=re.MULTILINE)
    # Wrap consecutive <li> in <ul>
    text = re.sub(
        r"((?:<li[^>]*>.*?</li>\n?)+)",
        r'<ul class="my-3 space-y-1">\1</ul>',
        text,
    )
    # Paragraphs — wrap remaining bare lines
    lines = text.split("\n")
    out = []
    for line in lines:
        stripped = line.strip()
        if not stripped:
            out.append("")
        elif stripped.startswith("<"):
            out.append(line)
        else:
            out.append(f'<p class="my-2 leading-relaxed">{stripped}</p>')
    return "\n".join(out)


app.jinja_env.filters["md"] = md


def format_elapsed(seconds):
    if seconds >= 3600:
        h = seconds // 3600
        m = (seconds % 3600) // 60
        return f"{h}h {m}m"
    elif seconds >= 60:
        m = seconds // 60
        s = seconds % 60
        return f"{m}m {s}s"
    else:
        return f"{seconds}s"

app.jinja_env.filters["elapsed"] = format_elapsed


# ── Helpers for templates ──────────────────────────────────────────────────

@app.context_processor
def inject_now():
    return {"now": datetime.utcnow(), "today": date.today().isoformat()}


@app.context_processor
def _inject_app_version():
    return {"app_version": APP_VERSION}


def _is_htmx():
    return request.headers.get("HX-Request") == "true"


def render(template, **kwargs):
    """Render a template. For HTMX requests, is_htmx=True is passed so
    base.html skips the layout shell and returns only the content block."""
    kwargs["is_htmx"] = _is_htmx()
    return render_template(template, **kwargs)


# ── Routes ──────────────────────────────────────────────────────────────────

@app.route("/")
def dashboard():
    _sync_team_member_models()
    team = query("SELECT * FROM team_members ORDER BY name")
    _status_rows = query(
        "SELECT status, COUNT(*) AS c FROM tasks WHERE id > ? GROUP BY status",
        (_TASK_COUNT_BASELINE_MAX_ID,),
    )
    task_counts = {"total": sum(r["c"] for r in _status_rows)}
    for r in _status_rows:
        task_counts[r["status"]] = r["c"]
    # Ensure keys are always present even if no rows exist
    for _s in ("pending", "in_progress", "done", "cancelled"):
        task_counts.setdefault(_s, 0)

    # Per-member in-progress count (full table — reflects reality, not baselined)
    member_active_counts = {
        row["assigned_to"]: row["c"]
        for row in query(
            "SELECT assigned_to, COUNT(*) AS c FROM tasks"
            " WHERE status='in_progress' AND assigned_to IS NOT NULL"
            " GROUP BY assigned_to"
        )
    }
    journal_count = query("SELECT COUNT(*) as c FROM journal_entries", one=True)["c"]

    from datetime import datetime
    updated_at = datetime.now().strftime("%-m/%-d/%Y %H:%M:%S")

    now = datetime.utcnow()
    busy_tasks = {}
    for row in query(
        "SELECT assigned_to, MIN(started_at) as started_at FROM tasks WHERE status='in_progress' AND assigned_to IS NOT NULL AND started_at IS NOT NULL GROUP BY assigned_to"
    ):
        try:
            started = datetime.strptime(row["started_at"], "%Y-%m-%dT%H:%M:%SZ")
            busy_tasks[row["assigned_to"]] = int((now - started).total_seconds())
        except (ValueError, TypeError):
            busy_tasks[row["assigned_to"]] = 0

    recently_done = {row["assigned_to"] for row in query(
        """SELECT DISTINCT assigned_to FROM tasks
           WHERE status='done' AND assigned_to IS NOT NULL
           AND completed_at > strftime('%Y-%m-%dT%H:%M:%SZ', 'now', '-60 seconds')
           /* AND (julianday(completed_at) - julianday(started_at)) * 86400 >= 120 */"""
    )}

    # Per-member current in-progress task (most recently started)
    member_current_tasks = {
        row["assigned_to"]: {"title": row["title"], "description": row["description"] or ""}
        for row in query(
            "SELECT assigned_to, title, description FROM tasks"
            " WHERE status='in_progress' AND assigned_to IS NOT NULL AND started_at IS NOT NULL"
            " GROUP BY assigned_to HAVING started_at = MAX(started_at)"
        )
    }

    # Per-member last activity entry (most recent by created_at)
    _activity_rows = query(
        "SELECT actor, action, details, created_at FROM activity_log"
        " ORDER BY created_at DESC LIMIT 200"
    )
    member_last_activity = {}
    for _row in _activity_rows:
        _actor = _row["actor"]
        if _actor and _actor not in member_last_activity:
            member_last_activity[_actor] = {
                "action": _row["action"],
                "details": _row["details"] or "",
                "created_at": _row["created_at"],
            }

    homunculus = _homunculus_stats()

    return render("dashboard.html", team=team,
                   task_counts=task_counts,
                   journal_count=journal_count, updated_at=updated_at,
                   busy_tasks=busy_tasks, recently_done=recently_done,
                   member_active_counts=member_active_counts,
                   member_current_tasks=member_current_tasks,
                   member_last_activity=member_last_activity,
                   homunculus=homunculus)


_HOMUNCULUS_ACTIVITY_PATH = os.path.normpath(os.path.join(
    os.path.dirname(__file__), "..", "Homunculus", "vault", "_activity.jsonl"
))


def _homunculus_stats():
    """Lightweight Homunculus snapshot for the dashboard. Fast enough to run on every 750ms poll."""
    import json as _json
    import urllib.request, urllib.error

    brain_status = "down"
    brain_version = None
    try:
        with urllib.request.urlopen("http://localhost:8765/health", timeout=0.3) as r:
            h = _json.loads(r.read())
            brain_status = "up"
            brain_version = h.get("package_version")
    except (urllib.error.URLError, OSError, ValueError):
        pass

    total = 0
    today_count = 0
    today_kinds = {}
    last_capture = None
    today_iso = date.today().isoformat()

    if os.path.exists(_HOMUNCULUS_ACTIVITY_PATH):
        try:
            with open(_HOMUNCULUS_ACTIVITY_PATH, "r", encoding="utf-8") as f:
                for line in f:
                    line = line.strip()
                    if not line:
                        continue
                    try:
                        row = _json.loads(line)
                    except _json.JSONDecodeError:
                        continue
                    if row.get("kind") != "parse":
                        continue
                    total += 1
                    if (row.get("at") or "")[:10] == today_iso:
                        today_count += 1
                        kind = (row.get("details") or {}).get("kind", "unknown")
                        today_kinds[kind] = today_kinds.get(kind, 0) + 1
                    last_capture = row
        except OSError:
            pass

    last_summary = None
    if last_capture:
        last_summary = {
            "raw_text": last_capture.get("raw_text", ""),
            "at": last_capture.get("at", ""),
            "kind": (last_capture.get("details") or {}).get("kind", "unknown"),
        }

    # Sort kinds so the display is stable across polls.
    return {
        "brain_status": brain_status,
        "brain_version": brain_version,
        "total": total,
        "today_count": today_count,
        "today_kinds": dict(sorted(today_kinds.items())),
        "last_capture": last_summary,
    }


# ── Research documents helpers ─────────────────────────────────────────────

_REPO_ROOT = os.path.normpath(os.path.join(os.path.dirname(__file__), ".."))
_RESEARCH_DIRS = {
    "Hiring":  os.path.join(_REPO_ROOT, "Team"),
    "Topical": os.path.join(_REPO_ROOT, "owner_inbox"),
}


def _research_title(filepath):
    """Return the first # heading from the file, falling back to the filename stem."""
    try:
        with open(filepath, encoding="utf-8", errors="replace") as f:
            for line in f:
                line = line.strip()
                if line.startswith("# "):
                    return line[2:].strip()
    except OSError:
        pass
    stem = os.path.splitext(os.path.basename(filepath))[0]
    return stem.replace("_", " ").replace("-", " ").title()


def _collect_research_docs():
    """Return list of dicts for all research Markdown files, newest-first by mtime."""
    docs = []
    for badge, dirpath in _RESEARCH_DIRS.items():
        if not os.path.isdir(dirpath):
            continue
        for fname in os.listdir(dirpath):
            if badge == "Hiring":
                if not (fname.startswith("_hiring_research_") and fname.endswith(".md")):
                    continue
            else:  # Topical
                if not ("research" in fname.lower() and fname.endswith(".md")):
                    continue
            full = os.path.join(dirpath, fname)
            if not os.path.isfile(full):
                continue
            mtime = os.path.getmtime(full)
            docs.append({
                "title":  _research_title(full),
                "badge":  badge,
                "mtime":  mtime,
                "date":   datetime.fromtimestamp(mtime).strftime("%Y-%m-%d"),
                # relative path used as URL token — badge prefix avoids collisions
                "url_path": f"{badge.lower()}/{fname}",
            })
    docs.sort(key=lambda d: d["mtime"], reverse=True)
    return docs


@app.route("/research/<path:filename>")
def research_doc(filename):
    """Serve a research Markdown file rendered to HTML.

    filename is expected in the form  <badge_lower>/<basename>  e.g.
    hiring/_hiring_research_foo.md  or  topical/pax_homunculus_research.md
    """
    parts = filename.split("/", 1)
    if len(parts) != 2:
        abort(404)
    badge_key, basename = parts[0].capitalize(), parts[1]

    if badge_key not in _RESEARCH_DIRS:
        abort(404)

    # Reject traversal attempts
    if ".." in basename or "/" in basename or "\\" in basename:
        abort(400)

    dirpath = _RESEARCH_DIRS[badge_key]
    full = os.path.realpath(os.path.join(dirpath, basename))
    allowed = os.path.realpath(dirpath)
    if not full.startswith(allowed + os.sep):
        abort(400)
    if not os.path.isfile(full):
        abort(404)

    with open(full, encoding="utf-8", errors="replace") as f:
        raw = f.read()

    title = _research_title(full)
    content_html = md(raw)
    return render("research_doc.html", title=title, badge=badge_key,
                  content_html=content_html, filename=basename)


@app.route("/team")
def team():
    _sync_team_member_models()
    members = query("SELECT * FROM team_members ORDER BY name")
    return render("team.html", members=members)


@app.route("/api/team/<int:member_id>/model", methods=["PATCH"])
def update_team_member_model(member_id):
    data = request.get_json(force=True, silent=True) or {}
    tier = data.get("model", "").strip().lower()
    if tier not in _VALID_TIERS:
        return jsonify({"error": f"Invalid model tier: {tier!r}"}), 400

    row = query("SELECT * FROM team_members WHERE id=?", (member_id,), one=True)
    if not row:
        abort(404)

    db = get_db()
    db.execute(
        "UPDATE team_members SET model=?, updated_at=strftime('%Y-%m-%dT%H:%M:%SZ','now') WHERE id=?",
        (tier, member_id),
    )
    db.commit()

    if row["persona_file"]:
        full_path = os.path.normpath(os.path.join(_REPO_ROOT, row["persona_file"]))
        try:
            with open(full_path, encoding="utf-8", errors="replace") as fh:
                content = fh.read()
            content = re.sub(r"(- \*\*Model:\*\* )\w+", r"\g<1>" + tier, content)
            with open(full_path, "w", encoding="utf-8") as fh:
                fh.write(content)
        except OSError:
            pass

    readme_path = os.path.normpath(os.path.join(_REPO_ROOT, "team", "README.md"))
    try:
        with open(readme_path, encoding="utf-8") as fh:
            content = fh.read()
        pattern = r"(\| \*\*" + re.escape(row["name"]) + r"\*\* \| [^|]+ \| )\w+( \|)"
        content = re.sub(pattern, r"\g<1>" + tier + r"\2", content)
        with open(readme_path, "w", encoding="utf-8") as fh:
            fh.write(content)
    except OSError:
        pass

    return jsonify({"id": member_id, "model": tier})


@app.route("/tasks")
def tasks():
    status_filter = request.args.get("status", "")
    if status_filter:
        rows = query(
            """SELECT t.*, tm.name as assignee_name
               FROM tasks t LEFT JOIN team_members tm ON t.assigned_to = tm.id
               WHERE t.status = ? ORDER BY t.created_at DESC""",
            (status_filter,),
        )
    else:
        rows = query(
            """SELECT t.*, tm.name as assignee_name
               FROM tasks t LEFT JOIN team_members tm ON t.assigned_to = tm.id
               ORDER BY t.created_at DESC"""
        )
    statuses = ["pending", "in_progress", "blocked", "done", "cancelled"]
    return render("tasks.html", tasks=rows, statuses=statuses,
                   current_status=status_filter)


@app.route("/journal")
def journal_list():
    entries = query("SELECT * FROM journal_entries ORDER BY date DESC")
    return render("journal_list.html", entries=entries)


@app.route("/journal/new", methods=["GET", "POST"])
def journal_new():
    if request.method == "POST":
        entry_date = request.form.get("date", date.today().isoformat())
        title = request.form.get("title", "")
        content = request.form.get("content", "")
        try:
            execute(
                """INSERT INTO journal_entries (date, title, content)
                   VALUES (?, ?, ?)""",
                (entry_date, title, content),
            )
            # Log activity
            execute(
                """INSERT INTO activity_log (actor, action, entity_type, details)
                   VALUES (?, ?, ?, ?)""",
                ("Sienna", "created_journal_entry", "journal_entry",
                 f'Created journal entry: "{title}" for {entry_date}.'),
            )
        except sqlite3.IntegrityError:
            # Date already exists — redirect to edit
            return redirect(url_for("journal_entry", entry_date=entry_date))
        return redirect(url_for("journal_entry", entry_date=entry_date))
    return render("journal_edit.html", entry=None)


@app.route("/journal/<entry_date>", methods=["GET"])
def journal_entry(entry_date):
    entry = query(
        "SELECT * FROM journal_entries WHERE date = ?", (entry_date,), one=True
    )
    if not entry:
        abort(404)
    return render("journal_entry.html", entry=entry)


@app.route("/journal/<entry_date>/edit", methods=["GET", "POST"])
def journal_edit(entry_date):
    entry = query(
        "SELECT * FROM journal_entries WHERE date = ?", (entry_date,), one=True
    )
    if not entry:
        abort(404)
    if request.method == "POST":
        title = request.form.get("title", "")
        content = request.form.get("content", "")
        execute(
            """UPDATE journal_entries SET title=?, content=?,
               updated_at=strftime('%Y-%m-%dT%H:%M:%SZ','now')
               WHERE date=?""",
            (title, content, entry_date),
        )
        return redirect(url_for("journal_entry", entry_date=entry_date))
    return render("journal_edit.html", entry=entry)


@app.route("/documents")
def documents():
    docs = query(
        """SELECT d.*, t.title as task_title
           FROM documents d LEFT JOIN tasks t ON d.task_id = t.id
           ORDER BY d.created_at DESC"""
    )
    return render("documents.html", documents=docs)


@app.route("/activity")
def activity():
    rows = query("SELECT * FROM activity_log ORDER BY created_at DESC")
    return render("activity.html", activities=rows)


# ── Editor routes ──────────────────────────────────────────────────────────

_EGM_BASE = os.path.normpath(
    os.path.join(os.path.dirname(__file__), "..", "ItWentIn", "GolfCourses")
)
_TEAM_INBOX = os.path.join(os.path.dirname(__file__), "..", "team_inbox")


def _find_image_path(image_name: str, preferred_course: str = "") -> str | None:
    """Resolve an image filename to an absolute path.

    Search order:
      1. ``preferred_course``/Images/ (the image's declared source course)
      2. All other course Images/ folders under _EGM_BASE (cross-course fallback)
      3. team_inbox/ (legacy location)
      4. owner_inbox/ (legacy location)

    Returns the absolute path string, or None if not found.
    """
    search_dirs = []
    # 1. Preferred (source) course first
    if preferred_course and os.path.isdir(_EGM_BASE):
        search_dirs.append(os.path.abspath(os.path.join(_EGM_BASE, preferred_course, "Images")))
    # 2. All course Images/ folders (catches cross-course references)
    if os.path.isdir(_EGM_BASE):
        for entry in sorted(os.listdir(_EGM_BASE)):
            if entry == preferred_course:
                continue  # already added above
            candidate_dir = os.path.abspath(os.path.join(_EGM_BASE, entry, "Images"))
            if os.path.isdir(candidate_dir):
                search_dirs.append(candidate_dir)
    # 3. Legacy locations
    search_dirs.append(os.path.abspath(_TEAM_INBOX))
    _owner_inbox = os.path.normpath(os.path.join(os.path.dirname(__file__), "..", "owner_inbox"))
    search_dirs.append(os.path.abspath(_owner_inbox))

    for folder in search_dirs:
        candidate = os.path.join(folder, image_name)
        if os.path.isfile(candidate):
            return candidate
    return None


def _collect_course_images():
    """
    Return a list of image dicts from all GolfCourses/*/Images/ folders.

    Each dict has keys: 'filename', 'course', 'url'
    Falls back to team_inbox images (course=None) for backwards compat.
    Results are sorted case-insensitively: courses A→Z, then filenames A→Z within each course.
    """
    results = []
    exts = ('.png', '.jpg', '.jpeg')
    if os.path.isdir(_EGM_BASE):
        for course in sorted(os.listdir(_EGM_BASE), key=str.casefold):
            img_dir = os.path.join(_EGM_BASE, course, "Images")
            if not os.path.isdir(img_dir):
                continue
            for fname in sorted(os.listdir(img_dir), key=str.casefold):
                if fname.lower().endswith(exts):
                    results.append({
                        "filename": fname,
                        "course": course,
                        "url": f"/egm/images/{course}/{fname}",
                    })
    # Backwards compat: also include team_inbox images
    if os.path.isdir(_TEAM_INBOX):
        for fname in sorted(os.listdir(_TEAM_INBOX), key=str.casefold):
            if fname.lower().endswith(exts):
                results.append({
                    "filename": fname,
                    "course": None,
                    "url": f"/team_inbox/{fname}",
                })
    return results


@app.route("/editor")
def editor():
    """Polygon boundary editor for golf hole images."""
    image = request.args.get("image", "")
    images = [entry["filename"] for entry in _collect_course_images()]
    return render("editor.html", image=image, images=images)


@app.route("/api/images")
def list_images():
    """Return current list of images from all GolfCourses/*/Images/ folders."""
    return jsonify(_collect_course_images())


@app.route("/api/courses", methods=["GET"])
def list_courses():
    """Return case-insensitively sorted list of existing course folder names under GolfCourses/.

    Used by the New Project dialog to surface matching folders before the user
    creates a new (potentially duplicate) folder.
    """
    courses = []
    if os.path.isdir(_EGM_BASE):
        for entry in sorted(os.listdir(_EGM_BASE), key=str.casefold):
            if entry.startswith("."):
                continue
            if os.path.isdir(os.path.join(_EGM_BASE, entry)):
                courses.append(entry)
    resp = jsonify({"courses": courses})
    resp.headers["Cache-Control"] = "no-store"
    return resp


@app.route("/api/courses", methods=["POST"])
def create_course():
    """Create a new course folder under GolfCourses/ with standard subfolders.

    Expects JSON: {"name": "<course folder name>"}
    Returns: {"status": "ok", "course": "<name>"} on success.
    Rejects: empty name, path separators, leading dot, or already-exists (409).
    Subfolders created: 3MFs/, EGMs/, Images/ (no STLs/).
    """
    data = request.get_json(force=True) or {}
    name = (data.get("name") or "").strip()

    # Validate
    if not name:
        return jsonify({"status": "error", "msg": "Course name must not be empty."}), 400
    if "/" in name or "\\" in name:
        return jsonify({"status": "error", "msg": "Course name must not contain path separators."}), 400
    if name.startswith("."):
        return jsonify({"status": "error", "msg": "Course name must not start with a dot."}), 400

    course_root = os.path.normpath(os.path.join(_EGM_BASE, name))
    # Guard against path traversal
    if not course_root.startswith(os.path.normpath(_EGM_BASE) + os.sep):
        return jsonify({"status": "error", "msg": "Invalid course name."}), 400

    if os.path.exists(course_root):
        return jsonify({"status": "error", "msg": f"Folder '{name}' already exists."}), 409

    try:
        for sub in ("3MFs", "EGMs", "Images"):
            os.makedirs(os.path.join(course_root, sub), exist_ok=True)
    except OSError as exc:
        return jsonify({"status": "error", "msg": str(exc)}), 500

    return jsonify({"status": "ok", "course": name})


@app.route("/team_inbox/<path:filename>")
def serve_team_inbox(filename):
    """Serve images from team_inbox for the editor (backwards compat)."""
    inbox = os.path.abspath(_TEAM_INBOX)
    return send_from_directory(inbox, filename)


@app.route("/egm/images/<path:course>/<path:filename>")
def serve_egm_image(course, filename):
    """Serve images from a course's Images/ folder."""
    img_dir = os.path.abspath(os.path.join(_EGM_BASE, course, "Images"))
    return send_from_directory(img_dir, filename)


def _ensure_course_subfolders(course_root: str) -> None:
    """Create 3MFs/, EGMs/, and Images/ under course_root if they don't exist."""
    for sub in ("3MFs", "EGMs", "Images"):
        os.makedirs(os.path.join(course_root, sub), exist_ok=True)


@app.route("/api/boundaries", methods=["POST"])
def save_boundaries():
    """Save polygon boundary coordinates as an .egm file."""
    import json as _json
    data = request.get_json()
    course = data.get("course", "Unknown Course")
    hole = data.get("hole", "0")
    hole_label = str(hole).zfill(2) if str(hole).isdigit() else str(hole)
    filename = f"{course} (Hole {hole_label}).egm"
    # Save to course EGMs/ folder; fall back to owner_inbox for unknown courses
    if course and course != "Unknown Course" and os.path.isdir(_EGM_BASE):
        course_root = os.path.join(_EGM_BASE, course)
        _ensure_course_subfolders(course_root)
        egm_dir = os.path.join(course_root, "EGMs")
    else:
        egm_dir = os.path.join(os.path.dirname(__file__), "..", "owner_inbox")
        os.makedirs(egm_dir, exist_ok=True)
    output = os.path.join(egm_dir, filename)
    with open(output, "w") as f:
        _json.dump(data, f, indent=2)
    return jsonify({"status": "ok", "path": output, "filename": filename})


@app.route("/api/boundaries/list")
def list_boundaries():
    """Return a list of all saved .egm project files from all course EGMs/ folders.

    Courses are enumerated case-insensitively A→Z; files within each course are
    enumerated case-insensitively A→Z.
    """
    import json as _json
    projects = []

    def _scan_dir(scan_dir):
        if not os.path.isdir(scan_dir):
            return
        for fname in sorted(os.listdir(scan_dir), key=str.casefold):
            if not fname.endswith(".egm"):
                continue
            fpath = os.path.join(scan_dir, fname)
            try:
                with open(fpath) as f:
                    data = _json.load(f)
                projects.append({
                    "filename": fname,
                    "course": data.get("course", ""),
                    "hole": data.get("hole", ""),
                    "image": data.get("image", ""),
                    "polygon_count": len(data.get("polygons", [])),
                })
            except Exception:
                pass

    # Scan all GolfCourses/*/EGMs/ directories
    if os.path.isdir(_EGM_BASE):
        for course_name in sorted(os.listdir(_EGM_BASE), key=str.casefold):
            _scan_dir(os.path.join(_EGM_BASE, course_name, "EGMs"))
    # Backwards compat: also scan owner_inbox
    _scan_dir(os.path.join(os.path.dirname(__file__), "..", "owner_inbox"))

    resp = jsonify({"status": "ok", "projects": projects})
    resp.headers["Cache-Control"] = "no-store"
    return resp


@app.route("/api/boundaries/load")
def load_boundaries():
    """Load a saved .egm file by filename and return its contents.

    Searches all GolfCourses/*/EGMs/ directories first, then owner_inbox/.
    """
    import json as _json
    filename = request.args.get("filename", "")
    if not filename or ".." in filename or "/" in filename:
        return jsonify({"status": "error", "msg": "Invalid filename"}), 400

    # Search course EGMs/ folders first
    fpath = None
    if os.path.isdir(_EGM_BASE):
        for course_name in sorted(os.listdir(_EGM_BASE)):
            candidate = os.path.join(_EGM_BASE, course_name, "EGMs", filename)
            if os.path.isfile(candidate):
                fpath = candidate
                break
    # Fallback: owner_inbox
    if fpath is None:
        candidate = os.path.join(os.path.dirname(__file__), "..", "owner_inbox", filename)
        if os.path.isfile(candidate):
            fpath = candidate
    if fpath is None:
        return jsonify({"status": "error", "msg": "File not found"}), 404
    with open(fpath) as f:
        data = _json.load(f)
    data["status"] = "ok"
    # Expose print constants so the editor can size the fringe-expansion zone.
    # generate_stl_3mf imports trimesh/shapely/numpy at module load; on a fresh
    # machine missing any of those, this route used to 500 with an ImportError
    # even though the file itself loaded fine. Fall back to omitting the
    # constants — the editor tolerates them being null via `if (data.print_size_mm != null)`.
    try:
        from generate_stl_3mf import PRINT_SIZE_MM, FRINGE_XY_EXPANSION_MM
        data["print_size_mm"] = PRINT_SIZE_MM
        data["fringe_xy_expansion_mm"] = FRINGE_XY_EXPANSION_MM
    except ImportError as _imp_err:
        print(f"[load_boundaries] WARN: could not import print constants from generate_stl_3mf: {_imp_err!r}")
    return jsonify(data)


@app.route("/api/print_constants")
def print_constants():
    """Return the print-size and fringe-expansion constants needed by the boundary editor."""
    from generate_stl_3mf import PRINT_SIZE_MM, FRINGE_XY_EXPANSION_MM
    return jsonify({
        "status": "ok",
        "print_size_mm": PRINT_SIZE_MM,
        "fringe_xy_expansion_mm": FRINGE_XY_EXPANSION_MM,
    })


@app.route("/api/detect_boundaries", methods=["POST"])
def detect_boundaries():
    """Run quick CV detection on a golf hole image, return initial polygon guesses."""
    import cv2
    import numpy as np
    from scipy.ndimage import binary_fill_holes

    data = request.get_json()
    image_name = data.get("image", "")
    course = data.get("course", "")
    image_course = data.get("imageCourse", "") or course
    if not image_name:
        return jsonify({"status": "error", "msg": "No image specified"}), 400

    # Resolve image to absolute path, searching all course folders as fallback
    img_path = _find_image_path(image_name, preferred_course=image_course)
    print(f"[detect_boundaries] image lookup: name={image_name!r} preferred_course={image_course!r} -> {img_path!r}")
    if img_path is None:
        return jsonify({"status": "error", "msg": f"Image not found: {image_name}"}), 400
    img = cv2.imread(img_path)
    if img is None:
        return jsonify({"status": "error", "msg": f"Cannot read image: {img_path}"}), 400

    h, w = img.shape[:2]
    hsv = cv2.cvtColor(img, cv2.COLOR_BGR2HSV)
    hue = hsv[:, :, 0].astype(float)
    sat = hsv[:, :, 1].astype(float)
    val = hsv[:, :, 2].astype(float)

    # --- Detect putting green: high-saturation colorful contour bands ---
    # Non-green hues (orange, red, yellow, blue, cyan) with high saturation
    contour_bands = (
        ((hue < 30) | (hue > 90)) & (sat > 80) & (val > 80)
    ) | (
        (hue >= 30) & (hue <= 90) & (sat > 120) & (val > 80)
    )
    contour_u8 = (contour_bands.astype(np.uint8)) * 255
    kernel = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (15, 15))
    contour_u8 = cv2.morphologyEx(contour_u8, cv2.MORPH_CLOSE, kernel, iterations=5)
    contour_filled = binary_fill_holes(contour_u8 > 0)
    contour_u8 = (contour_filled.astype(np.uint8)) * 255

    # Largest component = putting green
    n_cc, cc_labels, cc_stats, _ = cv2.connectedComponentsWithStats(contour_u8)
    green_mask = np.zeros((h, w), dtype=np.uint8)
    if n_cc > 1:
        areas = cc_stats[1:, cv2.CC_STAT_AREA]
        largest = 1 + np.argmax(areas)
        green_mask = ((cc_labels == largest) * 255).astype(np.uint8)

    # Smooth green boundary
    green_mask = cv2.GaussianBlur(green_mask, (21, 21), 0)
    _, green_mask = cv2.threshold(green_mask, 127, 255, cv2.THRESH_BINARY)

    # --- Detect sand traps: pale cream/beige ---
    trap_mask = (
        (hue >= 15) & (hue <= 34) &
        (sat >= 15) & (sat <= 60) &
        (val >= 200)
    ).astype(np.uint8) * 255
    kernel_t = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (11, 11))
    trap_mask = cv2.morphologyEx(trap_mask, cv2.MORPH_CLOSE, kernel_t, iterations=3)
    trap_mask = cv2.morphologyEx(trap_mask, cv2.MORPH_OPEN, cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (7, 7)), iterations=2)
    trap_filled = binary_fill_holes(trap_mask > 0)
    trap_mask = (trap_filled.astype(np.uint8)) * 255

    # Find individual traps
    n_t, t_labels, t_stats, t_centroids = cv2.connectedComponentsWithStats(trap_mask)
    traps = []
    for i in range(1, n_t):
        area = t_stats[i, cv2.CC_STAT_AREA]
        if area >= 500:
            traps.append((i, area))
    traps.sort(key=lambda x: x[1], reverse=True)
    traps = traps[:5]  # max 5 traps

    # --- Detect water hazards: royal blue regions ---
    # Royal blue centers around HSV hue 120 in OpenCV's 0-179 scale. We allow
    # 100-130 to tolerate cyan-leaning and violet-leaning blues. Saturation
    # >=130 keeps pale/sky-blue UI overlays out. Value 130-220 excludes the
    # darker dark-blue gradient arrows (V~60-90) that sit on the green and
    # also excludes near-white reflections (V>220).
    # Tuned against ItWentIn/GolfCourses/PGA West-Arnold Palmer/
    # Images/PGA West - Arnold Palmer.png — water samples there register as
    # H=104-105, S~172, V=164-184. Stanford Hole 8 contains no water and
    # produces 0 polygons after morphology + 500 px area filter.
    water_mask = (
        (hue >= 100) & (hue <= 130) &
        (sat >= 130) &
        (val >= 130) & (val <= 220)
    ).astype(np.uint8) * 255
    kernel_w = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (11, 11))
    water_mask = cv2.morphologyEx(water_mask, cv2.MORPH_CLOSE, kernel_w, iterations=3)
    water_mask = cv2.morphologyEx(water_mask, cv2.MORPH_OPEN, cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (7, 7)), iterations=2)
    water_filled = binary_fill_holes(water_mask > 0)
    water_mask = (water_filled.astype(np.uint8)) * 255

    # Find individual water bodies
    n_w, w_labels, w_stats, w_centroids = cv2.connectedComponentsWithStats(water_mask)
    waters = []
    for i in range(1, n_w):
        area = w_stats[i, cv2.CC_STAT_AREA]
        if area >= 500:
            waters.append((i, area))
    waters.sort(key=lambda x: x[1], reverse=True)
    waters = waters[:5]  # max 5 water polygons (same cap as traps)

    def mask_to_polygon(mask, num_points):
        """Extract the largest contour from a mask and resample to num_points."""
        contours, _ = cv2.findContours(mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
        if not contours:
            return []
        cnt = max(contours, key=cv2.contourArea)
        # Resample to num_points evenly spaced along the contour
        cnt = cnt.squeeze()
        if len(cnt.shape) < 2:
            return []
        # Compute cumulative arc length
        n = len(cnt)
        cum = [0.0]
        for j in range(1, n):
            cum.append(cum[-1] + np.linalg.norm(cnt[j] - cnt[j-1]))
        cum.append(cum[-1] + np.linalg.norm(cnt[0] - cnt[-1]))  # close the loop
        total = cum[-1]
        if total == 0:
            return []
        pts = []
        for j in range(num_points):
            target = (j / num_points) * total
            seg = 0
            while seg < n and cum[seg+1] < target:
                seg += 1
            t = (target - cum[seg]) / max(cum[seg+1] - cum[seg], 1e-9)
            a = cnt[seg % n]
            b = cnt[(seg+1) % n]
            px = int(a[0] + t * (b[0] - a[0]))
            py = int(a[1] + t * (b[1] - a[1]))
            pts.append({"x": px, "y": py})
        return pts

    # --- Detect contour lines inside the putting green ---
    # The colored overlay is a SLOPE map (not elevation).  The contour lines
    # (isolines of constant elevation) run along the boundaries between
    # adjacent color bands.  We classify pixels into 7 hue bands so that
    # adjacent-band boundaries give us the 6 isolines visible in the image.
    #
    # Band labels (ordered by hue, NOT by elevation):
    #   0 = Blue/Cyan   (hue 85-100)
    #   1 = Teal         (hue 65-84)
    #   2 = Green        (hue 45-64)
    #   3 = Yellow-green (hue 25-44)
    #   4 = Orange       (hue 15-24)
    #   5 = Red-orange   (hue 5-14)
    #   6 = Dark red     (hue 0-4 + 175-180)
    BAND_RANGES = [
        (85, 100),   # 0: blue/cyan
        (65, 84),    # 1: teal
        (45, 64),    # 2: green
        (25, 44),    # 3: yellow-green / yellow
        (15, 24),    # 4: orange
        (5, 14),     # 5: red-orange
        (0, 4),      # 6: dark red (low end)
    ]
    NUM_BANDS = len(BAND_RANGES)
    MIN_BAND_SAT = 40
    MIN_BAND_VAL = 60

    green_interior = (green_mask > 0)
    label_map = np.full((h, w), -1, dtype=np.int8)

    for band_idx, (h_lo, h_hi) in enumerate(BAND_RANGES):
        band_mask = (
            (hue >= h_lo) & (hue <= h_hi) &
            (sat >= MIN_BAND_SAT) & (val >= MIN_BAND_VAL) &
            green_interior
        )
        label_map[band_mask] = band_idx

    # Red wrap-around (hue 175-180) → band 6
    red_wrap = (
        (hue >= 175) & (hue <= 180) &
        (sat >= MIN_BAND_SAT) & (val >= MIN_BAND_VAL) &
        green_interior
    )
    label_map[red_wrap] = 6

    # Morphological cleanup per band
    clean_kernel = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (7, 7))
    for band_idx in range(NUM_BANDS):
        band_u8 = ((label_map == band_idx).astype(np.uint8)) * 255
        band_u8 = cv2.morphologyEx(band_u8, cv2.MORPH_CLOSE, clean_kernel, iterations=2)
        band_u8 = cv2.morphologyEx(band_u8, cv2.MORPH_OPEN,  clean_kernel, iterations=1)
        label_map[green_interior & (label_map == band_idx)] = -1
        label_map[green_interior & (band_u8 > 0)] = band_idx

    # Pre-compute the green perimeter contour once so endpoint snapping can use it
    _green_contours, _ = cv2.findContours(green_mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_NONE)
    _green_perimeter_pts = None
    if _green_contours:
        _biggest = max(_green_contours, key=cv2.contourArea).squeeze()
        if _biggest.ndim == 2 and len(_biggest) >= 3:
            _green_perimeter_pts = _biggest.astype(float)  # shape (N, 2) as (x, y)

    def _snap_to_green_perimeter(px, py):
        """Return the nearest point on the green perimeter to pixel (px, py)."""
        if _green_perimeter_pts is None:
            return int(px), int(py)
        dists = np.hypot(_green_perimeter_pts[:, 0] - px, _green_perimeter_pts[:, 1] - py)
        idx = int(np.argmin(dists))
        return int(_green_perimeter_pts[idx, 0]), int(_green_perimeter_pts[idx, 1])

    def extract_single_isoline(boundary_mask, num_pts=10):
        """
        Extract ONE ordered polyline from a boundary mask, with endpoints
        snapped to the green perimeter so shapely.ops.split can divide the
        green polygon cleanly.

        All boundary pixels are pooled, skeletonized, and ordered along
        the principal axis via PCA.  Returns a list of {"x","y"} dicts,
        or [] if there aren't enough pixels.
        """
        from skimage.morphology import skeletonize

        if np.count_nonzero(boundary_mask) < 20:
            return []

        # Merge fragments: close gaps in the boundary caused by crosshatch
        merge_kernel = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (11, 11))
        merged = cv2.morphologyEx(boundary_mask, cv2.MORPH_CLOSE, merge_kernel, iterations=3)

        # Skeletonize the merged boundary into a thin line
        thin = skeletonize(merged > 0)
        pts_yx = np.column_stack(np.where(thin))
        if len(pts_yx) < 4:
            pts_yx = np.column_stack(np.where(merged > 0))
        if len(pts_yx) < 4:
            return []

        # Order points along the principal axis (PCA)
        pts_f = pts_yx.astype(float)
        mean = pts_f.mean(axis=0)
        centered = pts_f - mean
        cov = centered.T @ centered
        eigvals, eigvecs = np.linalg.eigh(cov)
        principal = eigvecs[:, -1]
        proj = centered @ principal
        order = np.argsort(proj)
        ordered = pts_yx[order]

        # Subsample to num_pts evenly spaced interior points
        indices = np.linspace(0, len(ordered) - 1, num_pts, dtype=int)
        sampled = ordered[indices]
        interior = [{"x": int(p[1]), "y": int(p[0])} for p in sampled]

        # Snap first and last points to the nearest green perimeter point so
        # the isoline spans cleanly from one edge of the green to the other.
        # This is required for shapely.ops.split to work correctly.
        sx0, sy0 = _snap_to_green_perimeter(interior[0]["x"], interior[0]["y"])
        sx1, sy1 = _snap_to_green_perimeter(interior[-1]["x"], interior[-1]["y"])
        interior[0]  = {"x": sx0, "y": sy0}
        interior[-1] = {"x": sx1, "y": sy1}

        # Guard: if both endpoints snapped to the same perimeter point the line
        # is degenerate — drop it.
        if sx0 == sx1 and sy0 == sy1:
            return []

        return interior

    def band_side(polyline_pts, higher_band_mask):
        """Determine which side of the polyline the higher band is on."""
        if len(polyline_pts) < 2:
            return 'left'
        dx = polyline_pts[-1]["x"] - polyline_pts[0]["x"]
        dy = polyline_pts[-1]["y"] - polyline_pts[0]["y"]
        if dx == 0 and dy == 0:
            return 'left'
        ys, xs = np.where(higher_band_mask > 0)
        if len(xs) == 0:
            return 'left'
        cx, cy = float(xs.mean()), float(ys.mean())
        mid_x = polyline_pts[len(polyline_pts)//2]["x"]
        mid_y = polyline_pts[len(polyline_pts)//2]["y"]
        cross = dx * (cy - mid_y) - dy * (cx - mid_x)
        return 'right' if cross > 0 else 'left'

    contour_lines = []
    contour_counter = 1
    band_present = [
        np.count_nonzero(label_map == b) > 200 for b in range(NUM_BANDS)
    ]

    # Each adjacent band pair produces exactly ONE isoline
    # Iterate from highest band downward (red→blue) so the first contour
    # found is on the left/interior side of the green.
    for hi_band in range(NUM_BANDS - 1, 0, -1):
        lo_band = hi_band - 1
        if not band_present[lo_band] or not band_present[hi_band]:
            continue

        lo_mask = ((label_map == lo_band).astype(np.uint8)) * 255
        hi_mask = ((label_map == hi_band).astype(np.uint8)) * 255

        # Dilate each band slightly and intersect to find the boundary zone
        dil_kernel = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (5, 5))
        lo_dil = cv2.dilate(lo_mask, dil_kernel, iterations=2)
        hi_dil = cv2.dilate(hi_mask, dil_kernel, iterations=2)
        boundary = cv2.bitwise_and(lo_dil, hi_dil)

        # Keep only pixels inside the green
        boundary = cv2.bitwise_and(boundary, green_mask)

        if np.count_nonzero(boundary) < 50:
            continue

        # Extract one isoline from ALL boundary pixels for this band pair
        pts = extract_single_isoline(boundary, num_pts=10)
        if len(pts) < 2:
            continue

        direction = band_side(pts, hi_mask)
        contour_lines.append({
            "name": f"Contour {contour_counter}",
            "type": "contour",
            "closed": False,
            "direction": direction,
            "points": pts,
        })
        contour_counter += 1
        break  # DEBUG: stop after first contour line found

    # Build response
    polygons = []

    # Green polygon (8 points)
    green_pts = mask_to_polygon(green_mask, 8)
    if green_pts:
        polygons.append({"name": "Green", "type": "green", "points": green_pts})

    # Trap polygons (16 points each)
    for idx, (label_id, area) in enumerate(traps):
        t_mask = ((t_labels == label_id) * 255).astype(np.uint8)
        # Smooth
        t_mask = cv2.GaussianBlur(t_mask, (15, 15), 0)
        _, t_mask = cv2.threshold(t_mask, 127, 255, cv2.THRESH_BINARY)
        trap_pts = mask_to_polygon(t_mask, 16)
        if trap_pts:
            polygons.append({"name": f"Trap {idx+1}", "type": "trap", "points": trap_pts})

    # Water polygons (16 points each — same as traps)
    for idx, (label_id, area) in enumerate(waters):
        w_mask = ((w_labels == label_id) * 255).astype(np.uint8)
        # Smooth
        w_mask = cv2.GaussianBlur(w_mask, (15, 15), 0)
        _, w_mask = cv2.threshold(w_mask, 127, 255, cv2.THRESH_BINARY)
        water_pts = mask_to_polygon(w_mask, 16)
        if water_pts:
            polygons.append({"name": f"Water {idx+1}", "type": "water", "points": water_pts})

    # Contour detection disabled — using arrow-gradient Poisson surface instead
    # polygons.extend(contour_lines)

    return jsonify({
        "status": "ok",
        "imageSize": {"width": w, "height": h},
        "polygons": polygons,
        "contourStep": 0.5,
    })


@app.route("/api/find_contours", methods=["POST"])
def find_contours():
    """Find contour lines inside an existing green perimeter.

    Accepts JSON with:
      - image: source image filename
      - green_points: array of {x, y} — dense spline-sampled points along the
        green boundary (sent by the editor, not raw control points)
      - imageSize: {width, height}

    Returns:
      - contours: array of contour line objects with type, direction, points
    """
    import numpy as np
    from generate_stl_3mf import (
        remove_arrows_from_green,
        extract_contour_polylines_from_mask,
    )

    data = request.get_json()
    image_name = data.get("image", "")
    course = data.get("course", "")
    image_course = data.get("imageCourse", "") or course
    green_points = data.get("green_points", [])

    if not image_name or not green_points:
        return jsonify({"status": "error", "msg": "Need image and green_points"}), 400

    # Resolve image to absolute path, searching all course folders as fallback
    img_path = _find_image_path(image_name, preferred_course=image_course)
    print(f"[find_contours] image lookup: name={image_name!r} preferred_course={image_course!r} -> {img_path!r}")
    if img_path is None:
        return jsonify({"status": "error", "msg": f"Image not found: {image_name}"}), 400

    # The editor sends dense spline-sampled points — use them directly as the
    # green boundary polygon (Nx2 float64 array of (x, y) pixel coords).
    green_boundary_px = np.array(
        [[p["x"], p["y"]] for p in green_points], dtype=np.float64
    )

    # Step 1: Remove slope arrows, isolate contour blobs.
    # remove_arrows_from_green saves its own debug image to owner_inbox/.
    try:
        cleaned_img, contour_keep_mask = remove_arrows_from_green(
            img_path, green_boundary_px
        )
    except FileNotFoundError as exc:
        return jsonify({"status": "error", "msg": str(exc)}), 400

    # Step 2: Extract ordered polylines from the contour blob mask.
    # extract_contour_polylines_from_mask saves its own debug image to owner_inbox/.
    polylines = extract_contour_polylines_from_mask(
        contour_keep_mask, green_boundary_px, source_image=cleaned_img
    )

    # Step 3: Convert Nx2 float64 arrays into the editor's expected format.
    contour_lines = []
    for i, polyline in enumerate(polylines):
        contour_lines.append({
            "name": f"Contour {i + 1}",
            "type": "contour",
            "closed": False,
            "direction": "left",
            "points": [{"x": int(pt[0]), "y": int(pt[1])} for pt in polyline],
        })

    print(f"[find_contours] Returning {len(contour_lines)} contour(s) for {image_name}")

    return jsonify({
        "status": "ok",
        "contours": contour_lines,
    })


@app.route("/api/generate_models", methods=["POST"])
def generate_models():
    """Run the full gradient surface pipeline for a course/hole.

    Expects JSON: {"course": "<course name>", "hole": "<hole number>", ...}
    The EGM file must already exist on disk (saved by the editor).

    Returns:
        {"status": "ok", "file": {"name": ..., "path": ..., "type": "3mf"}}
    """
    from gradient_surface_diagnostic import run_pipeline

    data = request.get_json(force=True)
    if not data:
        return jsonify({"status": "error", "msg": "No JSON payload"}), 400

    course = data.get("course", "").strip()
    hole = data.get("hole", "").strip()
    if not course or not hole:
        return jsonify({"status": "error", "msg": "Missing course or hole"}), 400

    # Auto-derive a 5 mm boulders ring around each water polygon when checked
    # (replaces any manual boulders polygons in the EGM). The editor persists
    # this flag to the EGM via autoSave before calling /api/generate_models,
    # but we also forward the request-time value here so the route can override
    # the persisted value if the client ever wants to.
    include_boundary_region = bool(data.get("includeBoundaryRegion", False))
    # Fringe-frame cap toggle (task 669): default True preserves legacy behavior.
    # When False, the water-hole rule at gradient_surface_diagnostic line ~5854
    # skips the per-vertex boundary cap for the fringe mesh, letting the fringe
    # rise to its natural height even where it exceeds the plaque frame.
    # Missing key → True (legacy .egm files never persisted this flag).
    apply_fringe_frame_cap = bool(data.get("applyFringeFrameCap", True))
    open_in_slicer = bool(data.get("open_in_slicer", False))

    hole_label = hole.zfill(2) if hole.isdigit() else hole
    egm_fname = f"{course} (Hole {hole_label}).egm"
    # Look for EGM in course EGMs/ folder first, then owner_inbox fallback
    egm_path = None
    if os.path.isdir(_EGM_BASE):
        candidate = os.path.abspath(os.path.join(_EGM_BASE, course, "EGMs", egm_fname))
        if os.path.exists(candidate):
            egm_path = candidate
    if egm_path is None:
        _owner_inbox = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "owner_inbox"))
        candidate = os.path.join(_owner_inbox, egm_fname)
        if os.path.exists(candidate):
            egm_path = candidate
    if egm_path is None:
        return jsonify({
            "status": "error",
            "msg": f"EGM file not found: {egm_fname}"
        }), 404

    print(f"[generate_models] EGM path:        {egm_path}")

    try:
        three_mf_path = run_pipeline(
            egm_path,
            include_boundary_region=include_boundary_region,
            apply_fringe_frame_cap=apply_fringe_frame_cap,
        )
    except Exception as exc:
        return jsonify({"status": "error", "msg": str(exc)}), 500

    # run_pipeline returns the absolute path with serial in the filename.
    # If for any reason it returns None (old callers), fall back to the plain name.
    if three_mf_path and os.path.exists(three_mf_path):
        three_mf_name = os.path.basename(three_mf_path)
    else:
        # Fallback: old-style name without serial (file may not exist yet)
        three_mf_name = f"{course} (Hole {hole_label}).3mf"
        three_mf_dir = os.path.abspath(os.path.join(_EGM_BASE, course, "3MFs"))
        three_mf_path = os.path.join(three_mf_dir, three_mf_name)
        if not os.path.exists(three_mf_path):
            _owner_inbox = os.path.abspath(
                os.path.join(os.path.dirname(__file__), "..", "owner_inbox")
            )
            three_mf_path = os.path.join(_owner_inbox, three_mf_name)

    print(f"[generate_models] output 3MF path: {os.path.abspath(three_mf_path)}")

    result = {
        "name": three_mf_name,
        "path": os.path.relpath(three_mf_path, os.path.dirname(__file__)),
        "type": "3mf",
    }

    # ── Open in default slicer (macOS file-association) ──────────────────────
    # Uses `open <file>` so the OS hands the .3mf to whatever app owns the
    # extension — no hardcoded Bambu path. If `open` fails, surface stderr so
    # the user knows what went wrong; hint to use Finder as fallback.
    slicer_opened = None
    slicer_error  = None
    if open_in_slicer and three_mf_path and os.path.exists(three_mf_path):
        import subprocess
        try:
            proc = subprocess.run(
                ["open", three_mf_path],
                capture_output=True,
                timeout=10,
            )
            if proc.returncode == 0:
                slicer_opened = True
            else:
                slicer_opened = False
                stderr_text = (proc.stderr or b"").decode(errors="replace").strip()
                slicer_error = (
                    stderr_text
                    or f"`open` exited with code {proc.returncode}. "
                    "Try opening the file manually in Finder."
                )
        except subprocess.TimeoutExpired:
            slicer_opened = False
            slicer_error  = (
                "Timed out waiting for `open` to hand the file to the slicer. "
                "Try opening it manually in Finder."
            )
        except Exception as exc:
            slicer_opened = False
            slicer_error  = str(exc)

    return jsonify({"status": "ok", "file": result,
                    "slicer_opened": slicer_opened, "slicer_error": slicer_error})


# ── Arrow Diagnostic ─────────────────────────────────────────────────────────

@app.route("/diagnostic/arrows", methods=["POST"])
def diagnostic_arrows():
    """Return an annotated PNG showing every detected arrow in a source image.

    Accepts JSON with:
      - image:       source image filename
      - course:      course name (project's course)
      - imageCourse: course folder where the image lives (may differ)
      - green_points: array of {x, y} — dense spline-sampled boundary points

    Returns: image/png — annotated diagnostic image.

    The image is always returned (never 500 without a visual); errors are
    rendered as text overlaid on a black canvas so Thomas can see what went wrong.
    """
    import io
    import math as _math
    import numpy as _np
    import cv2 as _cv2
    from PIL import Image as _PILImage, ImageDraw as _PILDraw, ImageFont as _PILFont
    from flask import Response as _Response

    DIAG_VERSION = "arrow-diag v1.1"
    DIAG_DATE    = "2026-05-22"

    def _error_image(msg: str, w: int = 800, h: int = 400) -> bytes:
        """Return a PNG with the error message written across a dark canvas."""
        img = _PILImage.new("RGB", (w, h), color=(30, 30, 30))
        draw = _PILDraw.Draw(img)
        # Version badge top-left
        draw.rectangle([4, 4, 4 + 200, 4 + 22], fill=(40, 40, 80))
        draw.text((8, 6), DIAG_VERSION, fill=(180, 200, 255))
        # Error text centre
        draw.text((20, h // 2 - 30), "ERROR", fill=(255, 80, 80))
        # Wrap message crudely at ~80 chars
        words = msg.split()
        line, lines = [], []
        for w_ in words:
            if len(" ".join(line + [w_])) > 80:
                lines.append(" ".join(line))
                line = [w_]
            else:
                line.append(w_)
        if line:
            lines.append(" ".join(line))
        y = h // 2
        for ln in lines[:6]:
            draw.text((20, y), ln, fill=(255, 200, 200))
            y += 18
        buf = io.BytesIO()
        img.save(buf, format="PNG")
        return buf.getvalue()

    def _send_png(data: bytes) -> _Response:
        return _Response(data, mimetype="image/png",
                         headers={"Cache-Control": "no-store"})

    # ── Parse request ────────────────────────────────────────────────────────
    try:
        payload = request.get_json(force=True) or {}
        image_name    = payload.get("image", "")
        course        = payload.get("course", "")
        image_course  = payload.get("imageCourse", "") or course
        green_points  = payload.get("green_points", [])
        water_polygons_raw = payload.get("water_polygons", [])

        if not image_name:
            return _send_png(_error_image("No image specified in request."))
        if not green_points:
            return _send_png(_error_image("No green_points in request — draw a green polygon first."))

        # ── Resolve image path ───────────────────────────────────────────────
        img_path = _find_image_path(image_name, preferred_course=image_course)
        if img_path is None:
            return _send_png(_error_image(f"Image not found: {image_name!r}"))

        # ── Load image ───────────────────────────────────────────────────────
        bgr = _cv2.imread(img_path)
        if bgr is None:
            return _send_png(_error_image(f"cv2.imread failed for: {img_path}"))
        img_h, img_w = bgr.shape[:2]

        # ── Build green boundary polygon ─────────────────────────────────────
        green_boundary_px = _np.array(
            [[p["x"], p["y"]] for p in green_points], dtype=_np.float64
        )

        # ── Build water boundary polygons (for false-positive filtering) ─────
        # Any dark blob whose centroid falls inside a water polygon is not a
        # gradient arrow — it's a water-edge glyph, yardage label, or
        # shoreline marking. Build int32 contours for cv2.pointPolygonTest.
        water_boundaries_i = []
        for wpoly in water_polygons_raw:
            if len(wpoly) >= 3:
                water_boundaries_i.append(
                    _np.array([[p["x"], p["y"]] for p in wpoly], dtype=_np.int32)
                )

        # ── Run arrow detector ───────────────────────────────────────────────
        from gradient_surface_diagnostic import detect_arrows
        all_arrows = detect_arrows(bgr, green_boundary_px, dark_threshold=50, max_arrow_area=600)

        # Filter out any arrow whose centroid is inside a water polygon.
        # These are water-shoreline glyphs that happen to sit inside the green
        # boundary polygon but are not gradient arrows.
        n_water_rejected = 0
        arrows = []
        for a in all_arrows:
            in_water = False
            for wb in water_boundaries_i:
                if _cv2.pointPolygonTest(wb, (float(a["cx"]), float(a["cy"])), measureDist=False) >= 0:
                    in_water = True
                    break
            if in_water:
                n_water_rejected += 1
            else:
                arrows.append(a)
        if n_water_rejected > 0:
            print(f"  diagnostic_arrows: rejected {n_water_rejected} arrow(s) whose centroid "
                  f"fell inside a water polygon (water-glyph false-positive class)")

    except Exception as exc:
        import traceback
        return _send_png(_error_image(f"Pipeline error: {exc}\n{traceback.format_exc()[:400]}"))

    # ── Render annotated image ───────────────────────────────────────────────
    try:
        # Convert BGR → RGB for PIL
        rgb = _cv2.cvtColor(bgr, _cv2.COLOR_BGR2RGB)
        pil_img = _PILImage.fromarray(rgb).convert("RGBA")
        overlay = _PILImage.new("RGBA", pil_img.size, (0, 0, 0, 0))
        draw = _PILDraw.Draw(overlay)

        # Draw green boundary — solid white outline so it's visually unambiguous
        # that all gradient arrows sit on the green, not on water or fringe.
        boundary_pts = [(float(pt[0]), float(pt[1])) for pt in green_boundary_px]
        if len(boundary_pts) >= 2:
            draw.line(boundary_pts + [boundary_pts[0]], fill=(255, 255, 255, 255), width=3)

        ARROW_COLOR  = (255, 0, 220, 230)   # magenta fill
        OUTLINE_COL  = (255, 255, 255, 230)  # white outline
        CIRCLE_R     = 8
        ARROW_LEN    = 24
        LABEL_COLOR  = (255, 255, 255, 255)

        for idx, a in enumerate(arrows):
            cx, cy = float(a["cx"]), float(a["cy"])
            dx, dy = a["dx"], a["dy"]
            label  = str(idx + 1)

            # Arrow glyph: white outline then magenta fill arrowedLine
            ex = cx + dx * ARROW_LEN
            ey = cy + dy * ARROW_LEN
            # Draw as a line with a manual arrowhead in the overlay
            draw.line([(cx, cy), (ex, ey)], fill=OUTLINE_COL, width=5)
            draw.line([(cx, cy), (ex, ey)], fill=ARROW_COLOR, width=3)

            # Arrowhead triangle
            angle = _math.atan2(dy, dx)
            tip_x, tip_y = ex, ey
            LEFT_ANGLE  = angle + _math.pi * 0.75
            RIGHT_ANGLE = angle - _math.pi * 0.75
            HEAD_LEN = 10
            lx = tip_x + _math.cos(LEFT_ANGLE)  * HEAD_LEN
            ly = tip_y + _math.sin(LEFT_ANGLE)  * HEAD_LEN
            rx = tip_x + _math.cos(RIGHT_ANGLE) * HEAD_LEN
            ry = tip_y + _math.sin(RIGHT_ANGLE) * HEAD_LEN
            draw.polygon([(tip_x, tip_y), (lx, ly), (rx, ry)], fill=ARROW_COLOR, outline=OUTLINE_COL)

            # Numbered circle at tail
            draw.ellipse(
                [cx - CIRCLE_R - 1, cy - CIRCLE_R - 1,
                 cx + CIRCLE_R + 1, cy + CIRCLE_R + 1],
                fill=OUTLINE_COL,
            )
            draw.ellipse(
                [cx - CIRCLE_R, cy - CIRCLE_R,
                 cx + CIRCLE_R, cy + CIRCLE_R],
                fill=(30, 0, 60, 230),
            )
            draw.text((cx - CIRCLE_R + 2, cy - CIRCLE_R + 1), label, fill=LABEL_COLOR)

        # Composite overlay onto source
        composite = _PILImage.alpha_composite(pil_img, overlay).convert("RGB")
        draw2 = _PILDraw.Draw(composite)

        # ── Version badge (top-left) ─────────────────────────────────────────
        badge_text = f"{DIAG_VERSION}  {DIAG_DATE}"
        bx0, by0 = 6, 6
        bx1, by1 = bx0 + len(badge_text) * 7 + 10, by0 + 20
        draw2.rectangle([bx0, by0, bx1, by1], fill=(20, 10, 50))
        draw2.rectangle([bx0, by0, bx1, by1], outline=(140, 100, 255), width=1)
        draw2.text((bx0 + 5, by0 + 3), badge_text, fill=(200, 180, 255))

        # ── Summary text (top-right) ─────────────────────────────────────────
        n = len(arrows)
        if n == 0:
            summary = "0 arrows detected"
            s_fill  = (255, 80, 80)
        elif n == 1:
            summary = "1 arrow detected"
            s_fill  = (100, 255, 120)
        else:
            summary = f"{n} arrows detected"
            s_fill  = (100, 255, 120)

        s_w = len(summary) * 8 + 16
        sx0 = img_w - s_w - 4
        draw2.rectangle([sx0 - 2, 6, img_w - 4, 28], fill=(20, 10, 50))
        draw2.rectangle([sx0 - 2, 6, img_w - 4, 28], outline=(80, 200, 80), width=1)
        draw2.text((sx0 + 5, 10), summary, fill=s_fill)

        # ── Legend (bottom-left) ─────────────────────────────────────────────
        if arrows:
            LEGEND_LINE_H = 16
            LEGEND_COLS   = 4  # max columns in legend box
            LEGEND_COL_W  = 180

            legend_lines = []
            for idx, a in enumerate(arrows):
                angle_deg = round(_math.degrees(_math.atan2(a["dy"], a["dx"])))
                legend_lines.append(
                    f"  {idx+1:>2}. ({int(a['cx'])}, {int(a['cy'])})  dir={angle_deg}°"
                )

            # Split into columns if many arrows
            n_rows = max(1, -(-len(legend_lines) // LEGEND_COLS))  # ceil div
            columns = []
            for c in range(LEGEND_COLS):
                col = legend_lines[c * n_rows: (c + 1) * n_rows]
                if col:
                    columns.append(col)

            box_h = n_rows * LEGEND_LINE_H + 24
            box_w = len(columns) * LEGEND_COL_W + 16
            lx0, ly0 = 6, img_h - box_h - 6

            draw2.rectangle([lx0, ly0, lx0 + box_w, ly0 + box_h], fill=(15, 8, 40, 210))
            draw2.rectangle([lx0, ly0, lx0 + box_w, ly0 + box_h], outline=(100, 80, 180), width=1)
            draw2.text((lx0 + 8, ly0 + 5), "Arrow  (x, y)  direction", fill=(160, 140, 220))

            for ci, col in enumerate(columns):
                for ri, line in enumerate(col):
                    draw2.text(
                        (lx0 + 8 + ci * LEGEND_COL_W, ly0 + 18 + ri * LEGEND_LINE_H),
                        line,
                        fill=(220, 210, 240),
                    )

        # ── Encode and return ────────────────────────────────────────────────
        buf = io.BytesIO()
        composite.save(buf, format="PNG")
        return _send_png(buf.getvalue())

    except Exception as exc:
        import traceback
        return _send_png(_error_image(f"Render error: {exc}\n{traceback.format_exc()[:400]}"))


# ── Life Manager routes ──────────────────────────────────────────────────────

def _life_next_due(current_due, recur_rule, recur_interval):
    """Return the next ISO due-date string given a recurrence rule."""
    from datetime import timedelta, date as _date
    import calendar

    if not current_due or not recur_rule:
        return None
    try:
        d = _date.fromisoformat(current_due)
    except ValueError:
        return None

    if recur_rule == "daily":
        d = d + timedelta(days=1)
    elif recur_rule == "weekly":
        d = d + timedelta(days=7)
    elif recur_rule == "monthly":
        # Advance one month, clamping to last day if needed
        month = d.month + 1 if d.month < 12 else 1
        year  = d.year if d.month < 12 else d.year + 1
        day   = min(d.day, calendar.monthrange(year, month)[1])
        d = d.replace(year=year, month=month, day=day)
    elif recur_rule == "yearly":
        try:
            d = d.replace(year=d.year + 1)
        except ValueError:
            # Feb 29 edge-case: fall back to Feb 28
            d = d.replace(year=d.year + 1, day=28)
    elif recur_rule == "interval" and recur_interval:
        d = d + timedelta(days=int(recur_interval))
    else:
        return None
    return d.isoformat()


@app.route("/life")
def life():
    area_filter    = request.args.get("area", "")
    priority_filter = request.args.get("priority", "")
    show_done      = request.args.get("show_done", "0") == "1"

    areas = query("SELECT * FROM life_areas ORDER BY sort_order, name")

    # Build base WHERE clause
    filters = ["li.status = 'open'"] if not show_done else ["li.status IN ('open','done')"]
    args = []
    if area_filter:
        filters.append("li.area_id = ?")
        args.append(area_filter)
    if priority_filter:
        filters.append("li.priority = ?")
        args.append(priority_filter)

    where = " AND ".join(filters)
    items = query(
        f"""SELECT li.*, la.name as area_name, la.color as area_color, la.icon as area_icon
            FROM life_items li
            LEFT JOIN life_areas la ON li.area_id = la.id
            WHERE {where}
            ORDER BY
              CASE li.priority WHEN 'urgent' THEN 1 WHEN 'high' THEN 2 WHEN 'normal' THEN 3 ELSE 4 END,
              li.due_date ASC NULLS LAST,
              li.created_at DESC""",
        args,
    )

    today_iso = date.today().isoformat()
    return render("life.html",
                  items=items, areas=areas,
                  area_filter=area_filter, priority_filter=priority_filter,
                  show_done=show_done, today_iso=today_iso)


@app.route("/life/quick-add", methods=["POST"])
def life_quick_add():
    f = request.form
    title = f.get("title", "").strip()
    if not title:
        return redirect(url_for("life"))
    execute(
        """INSERT INTO life_items (title, area_id, priority, due_date)
           VALUES (?, ?, ?, ?)""",
        (
            title,
            f.get("area_id") or None,
            f.get("priority", "normal"),
            f.get("due_date") or None,
        ),
    )
    execute(
        """INSERT INTO activity_log (actor, action, entity_type, details)
           VALUES ('Thomas', 'created_life_item', 'life_item', ?)""",
        (f'Quick-added: "{title}"',),
    )
    if _is_htmx():
        from flask import Response
        return Response("", status=200,
                        headers={"HX-Trigger": "lifeItemUpdated"})
    return redirect(url_for("life"))


@app.route("/life/<int:item_id>/edit", methods=["GET", "POST"])
def life_edit(item_id):
    item  = query("SELECT * FROM life_items WHERE id = ?", (item_id,), one=True)
    areas = query("SELECT * FROM life_areas ORDER BY sort_order, name")
    if not item:
        abort(404)
    if request.method == "POST":
        f = request.form
        execute(
            """UPDATE life_items SET
               title=?, notes=?, area_id=?, priority=?,
               due_date=?, recur_rule=?, recur_interval=?, escalation_days=?,
               updated_at=strftime('%Y-%m-%dT%H:%M:%SZ','now')
               WHERE id=?""",
            (
                f.get("title", "").strip(),
                f.get("notes", "").strip() or None,
                f.get("area_id") or None,
                f.get("priority", "normal"),
                f.get("due_date") or None,
                f.get("recur_rule") or None,
                f.get("recur_interval") or None,
                f.get("escalation_days") or 3,
                item_id,
            ),
        )
        return redirect(url_for("life"))
    return render("life_edit.html", item=item, areas=areas)


@app.route("/life/new", methods=["GET", "POST"])
def life_new():
    areas = query("SELECT * FROM life_areas ORDER BY sort_order, name")
    if request.method == "POST":
        f = request.form
        db = get_db()
        cur = db.execute(
            """INSERT INTO life_items (title, notes, area_id, priority, due_date,
               recur_rule, recur_interval, escalation_days)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
            (
                f.get("title", "").strip(),
                f.get("notes", "").strip() or None,
                f.get("area_id") or None,
                f.get("priority", "normal"),
                f.get("due_date") or None,
                f.get("recur_rule") or None,
                f.get("recur_interval") or None,
                f.get("escalation_days") or 3,
            ),
        )
        db.commit()
        execute(
            """INSERT INTO activity_log (actor, action, entity_type, details)
               VALUES ('Thomas', 'created_life_item', 'life_item', ?)""",
            (f'Created: "{f.get("title", "").strip()}"',),
        )
        return redirect(url_for("life"))
    return render("life_edit.html", item=None, areas=areas)


@app.route("/life/<int:item_id>/complete", methods=["POST"])
def life_complete(item_id):
    item = query("SELECT * FROM life_items WHERE id = ?", (item_id,), one=True)
    if not item:
        abort(404)
    execute(
        """UPDATE life_items SET status='done', completed_at=strftime('%Y-%m-%dT%H:%M:%SZ','now'),
           updated_at=strftime('%Y-%m-%dT%H:%M:%SZ','now')
           WHERE id=?""",
        (item_id,),
    )
    # If recurring, spawn next occurrence
    if item["recur_rule"]:
        next_due = _life_next_due(item["due_date"], item["recur_rule"], item["recur_interval"])
        execute(
            """INSERT INTO life_items
               (title, notes, area_id, priority, due_date, recur_rule, recur_interval,
                recur_anchor, escalation_days)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (
                item["title"], item["notes"], item["area_id"], item["priority"],
                next_due, item["recur_rule"], item["recur_interval"],
                item["recur_anchor"], item["escalation_days"],
            ),
        )
    execute(
        """INSERT INTO activity_log (actor, action, entity_type, details)
           VALUES ('Thomas', 'completed_life_item', 'life_item', ?)""",
        (f'Completed: "{item["title"]}"',),
    )
    if _is_htmx():
        # Return a blank 200 so htmx can swap out the item row
        from flask import Response
        return Response("", status=200,
                        headers={"HX-Trigger": "lifeItemUpdated"})
    return redirect(url_for("life"))


@app.route("/life/<int:item_id>/snooze", methods=["POST"])
def life_snooze(item_id):
    item = query("SELECT * FROM life_items WHERE id = ?", (item_id,), one=True)
    if not item:
        abort(404)
    snoozed_until = request.form.get("snoozed_until", "")
    execute(
        """UPDATE life_items SET status='snoozed', snoozed_until=?,
           updated_at=strftime('%Y-%m-%dT%H:%M:%SZ','now')
           WHERE id=?""",
        (snoozed_until or None, item_id),
    )
    if _is_htmx():
        from flask import Response
        return Response("", status=200,
                        headers={"HX-Trigger": "lifeItemUpdated"})
    return redirect(url_for("life"))


@app.route("/life/<int:item_id>/delete", methods=["POST"])
def life_delete(item_id):
    item = query("SELECT * FROM life_items WHERE id = ?", (item_id,), one=True)
    if not item:
        abort(404)
    execute(
        """UPDATE life_items SET status='cancelled',
           updated_at=strftime('%Y-%m-%dT%H:%M:%SZ','now')
           WHERE id=?""",
        (item_id,),
    )
    if _is_htmx():
        from flask import Response
        return Response("", status=200,
                        headers={"HX-Trigger": "lifeItemUpdated"})
    return redirect(url_for("life"))


@app.route("/life/areas", methods=["GET", "POST"])
def life_areas():
    if request.method == "POST":
        action = request.form.get("action", "add")
        if action == "add":
            execute(
                "INSERT INTO life_areas (name, icon, color, sort_order) VALUES (?, ?, ?, ?)",
                (
                    request.form.get("name", "").strip(),
                    request.form.get("icon", "").strip() or None,
                    request.form.get("color", "#6B7280"),
                    request.form.get("sort_order", 99),
                ),
            )
        elif action == "edit":
            area_id = request.form.get("area_id")
            execute(
                """UPDATE life_areas SET name=?, icon=?, color=?,
                   updated_at=strftime('%Y-%m-%dT%H:%M:%SZ','now')
                   WHERE id=?""",
                (
                    request.form.get("name", "").strip(),
                    request.form.get("icon", "").strip() or None,
                    request.form.get("color", "#6B7280"),
                    area_id,
                ),
            )
        return redirect(url_for("life_areas"))

    areas = query("SELECT * FROM life_areas ORDER BY sort_order, name")
    return render("life_areas.html", areas=areas)


# ── Plaque text generator routes ────────────────────────────────────────────

owner_inbox = os.path.join(os.path.dirname(__file__), "..", "owner_inbox")


@app.route("/plaque")
def plaque_page():
    plate_text_path = os.path.join(os.path.dirname(__file__), "plate_text.py")
    try:
        mtime = os.path.getmtime(plate_text_path)
        from datetime import datetime
        last_modified = datetime.fromtimestamp(mtime).strftime("%Y-%m-%d %H:%M")
    except Exception:
        last_modified = ""
    return render("plaque.html", last_modified=last_modified)


@app.route("/api/fonts")
def api_fonts():
    from plate_text import list_available_fonts
    return jsonify({"fonts": list_available_fonts()})


def _slug_from_lines(line1: str, line2: str) -> str:
    return re.sub(r'[^\w\- ]+', '', (line1 or line2)).strip().replace(' ', '_') or 'custom_plate'


def _normalize_course_key(s: str) -> str:
    """Normalize a course name or user input for comparison.

    Rules applied in order:
    1. Lowercase.
    2. Replace en-dash (U+2013), em-dash (U+2014), and minus (U+2212) with ASCII hyphen.
    3. Collapse runs of whitespace to a single space.
    4. Strip all spaces immediately around hyphens so "a - b", "a-b", "a -b" all
       become the canonical form "a-b" (no spaces around hyphen).
    5. Strip leading/trailing whitespace.
    """
    s = s.lower()
    # Step 2 – Unicode dash variants → ASCII hyphen
    s = s.replace('–', '-').replace('—', '-').replace('−', '-')
    # Step 3 – collapse whitespace
    s = re.sub(r'\s+', ' ', s)
    # Step 4 – remove spaces around hyphens
    s = re.sub(r'\s*-\s*', '-', s)
    # Step 5 – strip edges
    return s.strip()


def _match_courses_from_line(course_line: str) -> list[str]:
    """Find all existing GolfCourses/ subfolders whose normalized name is a
    case-insensitive substring of the normalized course_line, or vice-versa.
    Returns all matches sorted longest-first so the caller can decide whether
    the result is unambiguous (1 match), ambiguous (>1), or absent (0)."""
    from generate_stl_3mf import EGM_BASE
    if not course_line or not os.path.isdir(EGM_BASE):
        return []
    try:
        entries = [e for e in os.listdir(EGM_BASE)
                   if os.path.isdir(os.path.join(EGM_BASE, e)) and not e.startswith('.')]
    except OSError:
        return []
    needle = _normalize_course_key(course_line)
    matches: list[str] = []
    for name in entries:
        haystack = _normalize_course_key(name)
        if needle in haystack or haystack in needle:
            matches.append(name)
    matches.sort(key=len, reverse=True)
    return matches


@app.route("/api/generate_plate", methods=["POST"])
def api_generate_plate():
    import smtplib
    import tempfile
    from email.message import EmailMessage

    data = request.get_json(force=True)
    line1 = data.get("line1", "").strip()
    line2 = data.get("line2", "").strip()
    line3 = data.get("line3", "").strip()
    open_in_slicer = bool(data.get("open_in_slicer"))
    if not (line1 or line2 or line3):
        return jsonify({"status": "error", "msg": "Provide at least one line of text."}), 400

    # ── SMTP config from environment ──────────────────────────────────────────
    smtp_host = os.environ.get("SMTP_HOST", "").strip()
    smtp_user = os.environ.get("SMTP_USER", "").strip()
    smtp_pass = os.environ.get("SMTP_PASS", "").strip()
    if not (smtp_host and smtp_user and smtp_pass):
        missing = [v for v, k in [("SMTP_HOST", smtp_host), ("SMTP_USER", smtp_user), ("SMTP_PASS", smtp_pass)] if not k]
        return jsonify({
            "status": "error",
            "msg": (
                f"SMTP not configured. Set {', '.join(missing)} env vars. "
                "See app/.env.example."
            ),
        }), 500

    smtp_port = int(os.environ.get("SMTP_PORT", "587"))
    smtp_from = os.environ.get("SMTP_FROM", smtp_user).strip() or smtp_user
    smtp_to   = os.environ.get("SMTP_TO", "quadrabyte@pm.me").strip()

    # ── Generate 3MF to a temp file ──────────────────────────────────────────
    slug = _slug_from_lines(line1, line2)
    attachment_name = f"{slug}.3mf"
    tmp_path = None
    try:
        from plate_text import generate_plate_3mf
        with tempfile.NamedTemporaryFile(suffix=".3mf", delete=False) as tf:
            tmp_path = tf.name
        generate_plate_3mf(line1, line2, line3, tmp_path,
                           font_family="Helvetica", bold=False, italic=False)
        with open(tmp_path, "rb") as fh:
            attachment_bytes = fh.read()
    except Exception as exc:
        return jsonify({"status": "error", "msg": f"3MF generation failed: {exc}"}), 500
    finally:
        if tmp_path and os.path.exists(tmp_path):
            try:
                os.unlink(tmp_path)
            except OSError:
                pass

    # ── Optionally write a stable copy for the default slicer ────────────────
    stable_path = None
    if open_in_slicer:
        stable_path = os.path.expanduser(f"~/Downloads/{attachment_name}")
        with open(stable_path, "wb") as fh:
            fh.write(attachment_bytes)

    # ── Build email ───────────────────────────────────────────────────────────
    subject_line = line1 or line2 or line3
    msg = EmailMessage()
    msg["Subject"] = f"Plaque: {subject_line}"
    msg["From"]    = smtp_from
    msg["To"]      = smtp_to
    body_lines = [f"Line 1: {line1}", f"Line 2: {line2}", f"Line 3: {line3}"]
    msg.set_content("\n".join(body_lines))
    msg.add_attachment(
        attachment_bytes,
        maintype="application",
        subtype="octet-stream",
        filename=attachment_name,
    )

    # ── Send via STARTTLS ─────────────────────────────────────────────────────
    smtp_error_resp = None
    try:
        with smtplib.SMTP(smtp_host, smtp_port, timeout=15) as server:
            server.ehlo()
            server.starttls()
            server.ehlo()
            server.login(smtp_user, smtp_pass)
            server.send_message(msg)
    except smtplib.SMTPAuthenticationError as exc:
        smtp_error_resp = jsonify({
            "status": "error",
            "msg": f"SMTP authentication failed (check SMTP_USER / SMTP_PASS): {exc.smtp_error.decode(errors='replace')}",
        }), 500
    except ConnectionRefusedError:
        smtp_error_resp = jsonify({
            "status": "error",
            "msg": f"Connection refused to {smtp_host}:{smtp_port}. Check SMTP_HOST / SMTP_PORT.",
        }), 500
    except smtplib.SMTPConnectError as exc:
        smtp_error_resp = jsonify({
            "status": "error",
            "msg": f"Could not connect to {smtp_host}:{smtp_port}: {exc}",
        }), 500
    except smtplib.SMTPException as exc:
        smtp_error_resp = jsonify({
            "status": "error",
            "msg": f"SMTP error: {exc}",
        }), 500
    except OSError as exc:
        smtp_error_resp = jsonify({
            "status": "error",
            "msg": f"Network error connecting to {smtp_host}:{smtp_port}: {exc}",
        }), 500

    # ── Open in default slicer (macOS file-association) ──────────────────────
    # Uses `open <file>` which honours the OS-registered .3mf handler —
    # whatever the user has set via Finder → Get Info → Open with → Change All.
    # If `open` exits non-zero there is no registered handler; surface the
    # error so the user can fix their file association rather than silently
    # falling back to a hardcoded app path.
    slicer_opened = None
    slicer_error  = None
    if open_in_slicer and stable_path:
        import subprocess
        try:
            result = subprocess.run(
                ["open", stable_path],
                capture_output=True,
                timeout=10,
            )
            if result.returncode == 0:
                slicer_opened = True
            else:
                slicer_opened = False
                stderr_text = (result.stderr or b"").decode(errors="replace").strip()
                slicer_error = stderr_text or (
                    f"`open` exited with code {result.returncode}. "
                    "Check your .3mf file association: Finder → right-click a .3mf → "
                    "Get Info → Open with → Change All."
                )
        except subprocess.TimeoutExpired:
            slicer_opened = False
            slicer_error  = "Timed out waiting for `open` to hand file to the default slicer."
        except Exception as exc:
            slicer_opened = False
            slicer_error  = str(exc)

    if smtp_error_resp is not None:
        return smtp_error_resp

    return jsonify({
        "status": "ok",
        "msg": f"Emailed to {smtp_to}",
        "recipient":    smtp_to,
        "stable_path":  stable_path,
        "slicer_opened": slicer_opened,
        "slicer_error":  slicer_error,
    })


# ── Run ─────────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    # use_reloader explicit so edits pick up regardless of how the process is launched
    app.run(debug=True, host="0.0.0.0", port=5051, use_reloader=True)
