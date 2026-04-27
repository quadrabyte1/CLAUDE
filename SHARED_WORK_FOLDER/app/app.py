"""
AI Team Workspace — Flask application
Serves a Notion-like UI over the workspace SQLite database.
"""

import os
import re
import sqlite3
from datetime import datetime, date

from flask import (
    Flask, render_template, request, redirect, url_for, g, abort, jsonify,
    send_from_directory,
)

app = Flask(__name__)

DB_PATH = os.path.join(os.path.dirname(__file__), "..", "db", "workspace.db")


# ── Database initialisation ────────────────────────────────────────────────

def init_db():
    """Ensure all required tables exist and run lightweight migrations."""
    db = sqlite3.connect(DB_PATH)
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

_MODEL_RE = re.compile(r"^\-\s+\*\*Model:\*\*\s*(opus|sonnet|haiku)\s*$", re.MULTILINE)


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
    activity = query(
        "SELECT * FROM activity_log ORDER BY created_at DESC LIMIT 15"
    )
    journal = query(
        "SELECT * FROM journal_entries WHERE date = ? LIMIT 1",
        (date.today().isoformat(),),
        one=True,
    )
    # If no entry today, get the most recent one
    if not journal:
        journal = query(
            "SELECT * FROM journal_entries ORDER BY date DESC LIMIT 1",
            one=True,
        )
    task_counts = {
        "total": query("SELECT COUNT(*) as c FROM tasks", one=True)["c"],
        "pending": query("SELECT COUNT(*) as c FROM tasks WHERE status='pending'", one=True)["c"],
        "in_progress": query("SELECT COUNT(*) as c FROM tasks WHERE status='in_progress'", one=True)["c"],
        "done": query("SELECT COUNT(*) as c FROM tasks WHERE status='done'", one=True)["c"],
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

    research_docs = _collect_research_docs()

    dashboard_version = "v1.2"  # bump this when layout/functionality changes
    return render("dashboard.html", team=team, activity=activity,
                   journal=journal, task_counts=task_counts,
                   journal_count=journal_count, updated_at=updated_at,
                   busy_tasks=busy_tasks, recently_done=recently_done,
                   research_docs=research_docs,
                   dashboard_version=dashboard_version)


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
    os.path.join(os.path.dirname(__file__), "..", "EliteGolfMoments", "GolfCourses")
)
_TEAM_INBOX = os.path.join(os.path.dirname(__file__), "..", "team_inbox")


def _collect_course_images():
    """
    Return a list of image dicts from all GolfCourses/*/Images/ folders.

    Each dict has keys: 'filename', 'course', 'url'
    Falls back to team_inbox images (course=None) for backwards compat.
    """
    results = []
    exts = ('.png', '.jpg', '.jpeg')
    if os.path.isdir(_EGM_BASE):
        for course in sorted(os.listdir(_EGM_BASE)):
            img_dir = os.path.join(_EGM_BASE, course, "Images")
            if not os.path.isdir(img_dir):
                continue
            for fname in sorted(os.listdir(img_dir)):
                if fname.lower().endswith(exts):
                    results.append({
                        "filename": fname,
                        "course": course,
                        "url": f"/egm/images/{course}/{fname}",
                    })
    # Backwards compat: also include team_inbox images
    if os.path.isdir(_TEAM_INBOX):
        for fname in sorted(os.listdir(_TEAM_INBOX)):
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


@app.route("/api/courses")
def list_courses():
    """Return sorted list of existing course folder names under GolfCourses/.

    Used by the New Project dialog to surface matching folders before the user
    creates a new (potentially duplicate) folder.
    """
    courses = []
    if os.path.isdir(_EGM_BASE):
        for entry in sorted(os.listdir(_EGM_BASE)):
            if entry.startswith("."):
                continue
            if os.path.isdir(os.path.join(_EGM_BASE, entry)):
                courses.append(entry)
    resp = jsonify({"courses": courses})
    resp.headers["Cache-Control"] = "no-store"
    return resp


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


@app.route("/api/boundaries", methods=["POST"])
def save_boundaries():
    """Save polygon boundary coordinates as an .egm file."""
    import json as _json
    data = request.get_json()
    course = data.get("course", "Unknown Course")
    hole = data.get("hole", "0")
    filename = f"{course} (Hole {hole}).egm"
    # Save to course EGMs/ folder; fall back to owner_inbox for unknown courses
    if course and course != "Unknown Course" and os.path.isdir(_EGM_BASE):
        egm_dir = os.path.join(_EGM_BASE, course, "EGMs")
    else:
        egm_dir = os.path.join(os.path.dirname(__file__), "..", "owner_inbox")
    os.makedirs(egm_dir, exist_ok=True)
    output = os.path.join(egm_dir, filename)
    with open(output, "w") as f:
        _json.dump(data, f, indent=2)
    return jsonify({"status": "ok", "path": output, "filename": filename})


@app.route("/api/boundaries/list")
def list_boundaries():
    """Return a list of all saved .egm project files from all course EGMs/ folders."""
    import json as _json
    projects = []

    def _scan_dir(scan_dir):
        if not os.path.isdir(scan_dir):
            return
        for fname in sorted(os.listdir(scan_dir)):
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
        for course_name in sorted(os.listdir(_EGM_BASE)):
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
    return jsonify(data)


@app.route("/api/detect_boundaries", methods=["POST"])
def detect_boundaries():
    """Run quick CV detection on a golf hole image, return initial polygon guesses."""
    import cv2
    import numpy as np
    from scipy.ndimage import binary_fill_holes

    data = request.get_json()
    image_name = data.get("image", "")
    course = data.get("course", "")
    if not image_name:
        return jsonify({"status": "error", "msg": "No image specified"}), 400

    # Search course Images/ folder first, then team_inbox as fallback
    img_path = None
    search_dirs = []
    if course and os.path.isdir(_EGM_BASE):
        search_dirs.append(os.path.join(_EGM_BASE, course, "Images"))
    search_dirs.append(os.path.abspath(_TEAM_INBOX))
    for search_dir in search_dirs:
        candidate = os.path.join(search_dir, image_name)
        if os.path.isfile(candidate):
            img_path = candidate
            break
    if img_path is None:
        return jsonify({"status": "error", "msg": "Image not found"}), 400
    img = cv2.imread(img_path)
    if img is None:
        return jsonify({"status": "error", "msg": "Cannot read image"}), 400

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

    # Contour detection disabled — using arrow-gradient Poisson surface instead
    # polygons.extend(contour_lines)

    return jsonify({
        "status": "ok",
        "imageSize": {"width": w, "height": h},
        "polygons": polygons,
        "contourStep": 10.0,
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
    green_points = data.get("green_points", [])

    if not image_name or not green_points:
        return jsonify({"status": "error", "msg": "Need image and green_points"}), 400

    img_path = os.path.join(os.path.dirname(__file__), "..", "team_inbox", image_name)

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

    egm_fname = f"{course} (Hole {hole}).egm"
    # Look for EGM in course EGMs/ folder first, then owner_inbox fallback
    egm_path = None
    if os.path.isdir(_EGM_BASE):
        candidate = os.path.join(_EGM_BASE, course, "EGMs", egm_fname)
        if os.path.exists(candidate):
            egm_path = candidate
    if egm_path is None:
        _owner_inbox = os.path.join(os.path.dirname(__file__), "..", "owner_inbox")
        candidate = os.path.join(_owner_inbox, egm_fname)
        if os.path.exists(candidate):
            egm_path = candidate
    if egm_path is None:
        return jsonify({
            "status": "error",
            "msg": f"EGM file not found: {egm_fname}"
        }), 404

    try:
        three_mf_path = run_pipeline(egm_path)
    except Exception as exc:
        return jsonify({"status": "error", "msg": str(exc)}), 500

    # run_pipeline returns the absolute path with serial in the filename.
    # If for any reason it returns None (old callers), fall back to the plain name.
    if three_mf_path and os.path.exists(three_mf_path):
        three_mf_name = os.path.basename(three_mf_path)
    else:
        # Fallback: old-style name without serial (file may not exist yet)
        three_mf_name = f"{course} (Hole {hole}).3mf"
        three_mf_dir = os.path.join(_EGM_BASE, course, "3MFs")
        three_mf_path = os.path.join(three_mf_dir, three_mf_name)
        if not os.path.exists(three_mf_path):
            _owner_inbox = os.path.join(os.path.dirname(__file__), "..", "owner_inbox")
            three_mf_path = os.path.join(_owner_inbox, three_mf_name)

    result = {
        "name": three_mf_name,
        "path": os.path.relpath(three_mf_path, os.path.dirname(__file__)),
        "type": "3mf",
    }

    return jsonify({"status": "ok", "file": result})


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
    return render("plaque.html", plaque_version="v3.0", last_modified=last_modified)


@app.route("/api/fonts")
def api_fonts():
    from plate_text import list_available_fonts
    return jsonify({"fonts": list_available_fonts()})


def _slug_from_lines(line1: str, line2: str) -> str:
    return re.sub(r'[^\w\- ]+', '', (line2 or line1)).strip().replace(' ', '_') or 'custom_plate'


def _match_course_from_line(line1: str) -> str | None:
    """Find the longest existing GolfCourses/ subfolder whose name appears as a
    whole-word substring of line1 (case-insensitive). Returns the folder's
    actual name, or None if no match."""
    from generate_stl_3mf import EGM_BASE
    if not line1 or not os.path.isdir(EGM_BASE):
        return None
    try:
        entries = [e for e in os.listdir(EGM_BASE)
                   if os.path.isdir(os.path.join(EGM_BASE, e)) and not e.startswith('.')]
    except OSError:
        return None
    matches: list[str] = []
    for name in entries:
        pattern = r'\b' + re.escape(name) + r'\b'
        if re.search(pattern, line1, flags=re.IGNORECASE):
            matches.append(name)
    if not matches:
        return None
    matches.sort(key=len, reverse=True)
    return matches[0]


def _suggest_course_from_line(line1: str) -> str:
    """Derive a suggested course folder name from line1 by trimming common
    suffixes (case-insensitive) such as 'Golf Course', 'Country Club', etc."""
    suffixes = [" Golf Course", " Country Club", " Golf Club", " GC", " CC"]
    s = (line1 or "").strip()
    changed = True
    while changed:
        changed = False
        for sfx in suffixes:
            if s.lower().endswith(sfx.lower()):
                s = s[: -len(sfx)].strip()
                changed = True
                break
    return s or (line1 or "").strip()


_COURSE_NAME_RE = re.compile(r'^[^/\\]+$')


def _validate_course_name(name: str) -> tuple[bool, str]:
    s = (name or "").strip()
    if not s:
        return False, "Course name cannot be empty."
    if "/" in s or "\\" in s:
        return False, "Course name cannot contain path separators."
    if ".." in s:
        return False, "Course name cannot contain '..'."
    if s.startswith("."):
        return False, "Course name cannot start with a dot."
    return True, s


@app.route("/api/generate_plate", methods=["POST"])
def api_generate_plate():
    data = request.get_json(force=True)
    line1 = data.get("line1", "").strip()
    line2 = data.get("line2", "").strip()
    line3 = data.get("line3", "").strip()
    # Ignore any client-supplied `course`/`font`/`bold`/`italic`; server decides.
    if not (line1 or line2 or line3):
        return jsonify({"status": "error", "msg": "Provide at least one line"}), 400

    slug = _slug_from_lines(line1, line2)

    matched = _match_course_from_line(line1)
    if matched is None:
        return jsonify({
            "status": "no_course_match",
            "line1": line1,
            "suggested": _suggest_course_from_line(line1),
        })

    from generate_stl_3mf import course_paths
    cpaths = course_paths(matched)
    os.makedirs(cpaths["3mfs"], exist_ok=True)
    out_path = os.path.join(cpaths["3mfs"], f"{slug}.3mf")

    from plate_text import generate_plate_3mf
    try:
        generate_plate_3mf(line1, line2, line3, out_path,
                           font_family="Orbitron", bold=False, italic=False)
    except Exception as exc:
        return jsonify({"status": "error", "msg": str(exc)}), 500
    return jsonify({
        "status": "ok",
        "filename": os.path.basename(out_path),
        "course": matched,
    })


@app.route("/api/create_course", methods=["POST"])
def api_create_course():
    data = request.get_json(force=True)
    raw_course = data.get("course", "")
    line1 = data.get("line1", "").strip()
    line2 = data.get("line2", "").strip()
    line3 = data.get("line3", "").strip()

    ok, result = _validate_course_name(raw_course)
    if not ok:
        return jsonify({"status": "error", "msg": result}), 400
    course = result

    if not (line1 or line2 or line3):
        return jsonify({"status": "error", "msg": "Provide at least one line"}), 400

    from generate_stl_3mf import course_paths
    cpaths = course_paths(course)
    # Scaffold only the directories that are part of the deliverable pipeline.
    # Per the course folder convention, STLs are not deliverables and the
    # boundary editor produces 3MFs directly — do NOT create an STLs/ folder.
    for key in ("3mfs", "egms", "images"):
        os.makedirs(cpaths[key], exist_ok=True)

    slug = _slug_from_lines(line1, line2)
    out_path = os.path.join(cpaths["3mfs"], f"{slug}.3mf")

    from plate_text import generate_plate_3mf
    try:
        generate_plate_3mf(line1, line2, line3, out_path,
                           font_family="Orbitron", bold=False, italic=False)
    except Exception as exc:
        return jsonify({"status": "error", "msg": str(exc)}), 500
    return jsonify({
        "status": "ok",
        "filename": os.path.basename(out_path),
        "course": course,
    })


# ── Run ─────────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    app.run(debug=True, host="0.0.0.0", port=5051)
