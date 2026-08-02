"""
MovieScanner — Flask UI over the IMDB dataset delta scanner.

Landing page: config editor + Run Now + recent runs + all matches.

Port: 5053
"""

import json
import os
import sqlite3
import sys
import threading
from datetime import date

from flask import Flask, render_template, request, redirect, url_for, jsonify, make_response, flash, get_flashed_messages

# Ensure the repo root (parent of MovieScanner/) is on the path so the
# movie_scanner package can be imported as a sibling folder.
_REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _REPO_ROOT not in sys.path:
    sys.path.insert(0, _REPO_ROOT)

from movie_scanner import Scanner, KNOWN_GENRES, OMDbClient
from movie_scanner.schema import apply_schema

app = Flask(__name__)
app.config["TEMPLATES_AUTO_RELOAD"] = True
app.jinja_env.auto_reload = True
app.secret_key = "moviescanner-dev"  # required for flash()

APP_VERSION = "V3.3"

DB_PATH = os.path.join(os.path.dirname(__file__), "db", "scanner.db")


@app.context_processor
def _inject_app_version():
    return {"app_version": APP_VERSION}


# ── DB helpers ─────────────────────────────────────────────────────────────

def _conn() -> sqlite3.Connection:
    c = sqlite3.connect(DB_PATH)
    c.execute("PRAGMA foreign_keys = ON")
    c.row_factory = sqlite3.Row
    return c


def _init_db() -> None:
    os.makedirs(os.path.dirname(DB_PATH), exist_ok=True)
    c = sqlite3.connect(DB_PATH)
    apply_schema(c)
    c.close()


_init_db()


def _reconcile_orphaned_runs() -> None:
    """Mark any non-terminal runs as error on startup.

    If the app (or a scan worker thread) was killed mid-scan — by SIGKILL,
    Werkzeug reloader, OOM, or any other unclean exit — the runs row is left
    with status='running' and a non-terminal phase (e.g. 'downloading').
    No try/finally in the worker can catch SIGKILL, so this startup sweep is
    the only reliable safety net.

    Any run still in status='running' at startup-time has no live worker (the
    process that owned it is gone), so we mark it 'error' with a clear note.
    Called once at module load time, before any route can serve the page.
    """
    conn = _conn()
    rows = conn.execute(
        "SELECT id FROM runs WHERE status='running'"
    ).fetchall()
    if rows:
        ids = [r["id"] for r in rows]
        conn.execute(
            f"UPDATE runs SET status='error', phase='error', "
            f"completed_at=strftime('%Y-%m-%dT%H:%M:%SZ','now'), "
            f"error='orphaned — process died before scan completed' "
            f"WHERE id IN ({','.join('?' * len(ids))})",
            ids,
        )
        conn.commit()
        print(
            f"[MovieScanner] reconciled {len(ids)} orphaned run(s): "
            + ", ".join(f"#{i}" for i in ids)
        )
    conn.close()


_reconcile_orphaned_runs()


# ── Concurrency guard ──────────────────────────────────────────────────────

def _scan_in_progress() -> bool:
    """Return True if a live scan worker is running.

    The startup reconciler clears orphaned 'running' rows on every restart,
    so a row with status='running' here means a real live thread owns it.
    """
    conn = _conn()
    row = conn.execute(
        "SELECT 1 FROM runs WHERE status='running' LIMIT 1"
    ).fetchone()
    conn.close()
    return row is not None


_SCAN_BUSY_MSG = "A scan is already running — wait for it to finish before starting another."


# ── Routes ─────────────────────────────────────────────────────────────────

@app.route("/")
def index():
    show_dismissed = request.args.get("show_dismissed", "0") == "1"

    db = _conn()
    cfg_rows = db.execute("SELECT key, value FROM config").fetchall()
    cfg = {r["key"]: r["value"] for r in cfg_rows}
    runs = db.execute("""
        SELECT * FROM (
            SELECT id, started_at, completed_at, status, phase,
                   total_downloaded, new_titles, matched_titles, error
            FROM runs ORDER BY id DESC LIMIT 20
        ) ORDER BY id ASC
    """).fetchall()
    titles_count  = db.execute("SELECT COUNT(*) FROM titles").fetchone()[0]
    matches_count = db.execute("SELECT COUNT(*) FROM matches").fetchone()[0]
    active_count    = db.execute(
        "SELECT COUNT(*) FROM matches WHERE dismissed_at IS NULL"
    ).fetchone()[0]
    dismissed_count = matches_count - active_count

    if show_dismissed:
        matches = db.execute(
            "SELECT tconst, primary_title, start_year, title_type, rating, num_votes, "
            "genres, matched_tags, matched_at, dismissed_at "
            "FROM matches ORDER BY rating DESC, num_votes DESC LIMIT 500"
        ).fetchall()
    else:
        matches = db.execute(
            "SELECT tconst, primary_title, start_year, title_type, rating, num_votes, "
            "genres, matched_tags, matched_at, dismissed_at "
            "FROM matches WHERE dismissed_at IS NULL "
            "ORDER BY rating DESC, num_votes DESC LIMIT 500"
        ).fetchall()

    upside_matches = db.execute(
        "SELECT tconst, primary_title, start_year, title_type, rating, num_votes, "
        "genres, matched_tags, checked_at "
        "FROM upside_matches ORDER BY rating DESC"
    ).fetchall()

    # Most recent checked_at from upside_matches (for the section badge)
    upside_checked_at_row = db.execute(
        "SELECT MAX(checked_at) FROM upside_matches"
    ).fetchone()
    upside_checked_at = upside_checked_at_row[0] if upside_checked_at_row else None

    db.close()

    # Parse the JSON-encoded tag lists into lowercase sets so the template
    # can check membership per genre without doing JSON work.
    try: include_lc = set(t.lower() for t in json.loads(cfg.get("tags", "[]")))
    except json.JSONDecodeError: include_lc = set()
    try: exclude_lc = set(t.lower() for t in json.loads(cfg.get("exclude_tags", "[]")))
    except json.JSONDecodeError: exclude_lc = set()
    try: exclude_countries_str = ", ".join(json.loads(cfg.get("exclude_countries", "[]")))
    except json.JSONDecodeError: exclude_countries_str = ""

    return render_template(
        "index.html",
        config=cfg,
        current_year=date.today().year,
        runs=runs,
        titles_count=titles_count,
        matches_count=matches_count,
        active_count=active_count,
        dismissed_count=dismissed_count,
        show_dismissed=show_dismissed,
        matches=matches,
        known_genres=KNOWN_GENRES,
        include_lc=include_lc,
        exclude_lc=exclude_lc,
        exclude_countries=exclude_countries_str,
        upside_matches=upside_matches,
        upside_checked_at=upside_checked_at,
    )


@app.route("/config", methods=["POST"])
def save_config():
    """Save the config form. Delegates to _save_config_from_form() so the
    Save button honours the same per-genre 3-state radio grid that /run and
    /config_and_rescan already read. Previous implementation looked for a
    comma-separated `tags`/`exclude_tags` field that the template no longer
    posts, silently wiping every include/exclude selection on each Save."""
    _save_config_from_form()
    return redirect(url_for("index"))


def _save_config_from_form():
    """Persist the config form to the DB. Extracted so both /config and
    /config_and_rescan can share the same coercion logic."""
    try:
        min_rating = float(request.form.get("min_rating", "7.0"))
    except ValueError:
        min_rating = 7.0
    try:
        min_votes = int(request.form.get("min_votes", "100"))
    except ValueError:
        min_votes = 100
    try:
        min_year = int(request.form.get("min_year", str(date.today().year)))
    except ValueError:
        min_year = date.today().year

    # Per-genre 3-state grid: each known genre has a radio group
    # `genre_<name>` with values include|ignore|exclude. Missing values
    # (no radio checked, shouldn't happen) default to ignore.
    tags: list[str] = []
    exclude_tags: list[str] = []
    for g in KNOWN_GENRES:
        v = request.form.get(f"genre_{g}", "ignore")
        if   v == "include": tags.append(g)
        elif v == "exclude": exclude_tags.append(g)

    title_types = request.form.getlist("title_types") or ["movie", "tvMovie", "tvSeries"]

    exclude_countries_raw = request.form.get("exclude_countries", "").strip()
    exclude_countries = [c.strip() for c in exclude_countries_raw.split(",") if c.strip()]

    db = _conn()
    for k, v in [
        ("min_rating",        str(min_rating)),
        ("min_votes",         str(min_votes)),
        ("min_year",          str(min_year)),
        ("tags",              json.dumps(tags)),
        ("exclude_tags",      json.dumps(exclude_tags)),
        ("title_types",       json.dumps(title_types)),
        ("exclude_countries", json.dumps(exclude_countries)),
    ]:
        db.execute(
            "INSERT INTO config (key, value) VALUES (?, ?) "
            "ON CONFLICT(key) DO UPDATE SET value=excluded.value",
            (k, v),
        )
    db.commit()
    db.close()


def _spawn_scan_worker() -> None:
    """Start a background thread running the scanner. Same pattern as /run."""
    def worker():
        try:
            Scanner(db_path=DB_PATH).scan(on_progress=lambda msg: None)
        except Exception as e:
            print(f"[MovieScanner] scan error: {e}")
    threading.Thread(target=worker, daemon=True).start()


@app.route("/clear", methods=["POST"])
def clear_all():
    """Wipe run history + match results. Filter/config settings are preserved.

    Per Thomas's V1.7 correction: this button lives in the "Recent runs"
    section and should only clear the run history and its associated
    matches. It must NOT touch the config row — the previous version reset
    every genre radio to Ignore on each click, which surprised the user.

    Preserved:
      - `titles` table (the seen-set — scanner won't re-test old tconsts).
      - `config` table in full (min rating, min votes, title types,
        include/exclude genre selections, omdb_api_key, everything).

    To also reset the seen-set + rerun against saved config, use
    "Save config and rescan all" instead.
    """
    db = _conn()
    # matches has FK REFERENCES runs(id) ON DELETE CASCADE, so wiping runs
    # takes matches with it. Explicit DELETE FROM matches too as a belt.
    db.execute("DELETE FROM matches")
    db.execute("DELETE FROM runs")
    db.commit()
    db.close()
    return redirect(url_for("index"))


@app.route("/config_and_rescan", methods=["POST"])
def save_config_and_rescan():
    """Save the config, wipe the seen-titles + matches tables, and start a
    fresh scan. Every title in tomorrow's dump will be treated as new and
    re-tested against the just-saved config.

    Deliberately preserves `runs` history so the audit trail (including a
    marker row for this wipe) survives — matches for those old runs are
    dropped along with the titles they referenced.
    """
    if _scan_in_progress():
        flash(_SCAN_BUSY_MSG)
        return redirect(url_for("index"))

    _save_config_from_form()

    db = _conn()
    # Matches first (they reference titles + runs); titles second.
    # runs table is intentionally kept so history isn't lost.
    db.execute("DELETE FROM matches")
    db.execute("DELETE FROM titles")
    # Insert a marker run row so the history shows what happened.
    db.execute(
        "INSERT INTO runs (status, phase, completed_at, config_snapshot) "
        "VALUES ('done', 'wiped', strftime('%Y-%m-%dT%H:%M:%SZ','now'), ?)",
        (json.dumps({"note": "titles + matches wiped by 'Save config and rescan all'"}),),
    )
    db.commit()
    db.close()

    _spawn_scan_worker()
    return redirect(url_for("index"))


@app.route("/run", methods=["POST"])
def start_run():
    """Save whatever config values are in the form (so unsaved radio clicks
    aren't silently dropped), then kick off a scan in a background thread.

    The Run button lives inside the config form and submits the same fields
    as Save, so the user's on-screen state is what actually runs — no
    "you had to click Save first" trap.

    NOTE: Scanner.scan() creates and owns its own runs row. We must NOT
    insert a stub row here — doing so causes two rows to appear in Recent
    Runs (the empty stub and the real one from Scanner.scan()).
    """
    if _scan_in_progress():
        flash(_SCAN_BUSY_MSG)
        return redirect(url_for("index"))

    _save_config_from_form()

    def worker():
        try:
            Scanner(db_path=DB_PATH).scan(on_progress=lambda msg: None)
        except Exception as e:
            print(f"[MovieScanner] scan error: {e}")

    threading.Thread(target=worker, daemon=True).start()
    return redirect(url_for("index"))


@app.route("/run/latest")
def latest_run():
    """Redirect to the landing page (results are now inline)."""
    return redirect(url_for("index"))


@app.route("/results/<int:run_id>")
def results_page_deprecated(run_id):
    """301 redirect for any old bookmarks to per-run result pages."""
    return redirect(url_for("index"), code=301)


@app.route("/api/status/<int:run_id>")
def api_status(run_id):
    db = _conn()
    run = db.execute(
        "SELECT id, status, phase, total_downloaded, new_titles, matched_titles, error "
        "FROM runs WHERE id=?",
        (run_id,),
    ).fetchone()
    db.close()
    if not run:
        return jsonify({"status": "not_found"}), 404
    return jsonify({
        **dict(run),
        "message": run["phase"] or "",
    })


@app.route("/api/matches")
def api_matches():
    """All matches across all runs, JSON dump for external tools if desired."""
    db = _conn()
    rows = db.execute(
        "SELECT tconst, primary_title, start_year, title_type, rating, num_votes, "
        "genres, matched_tags, matched_at FROM matches ORDER BY rating DESC LIMIT 5000"
    ).fetchall()
    db.close()
    return jsonify([dict(r) for r in rows])


@app.route("/matches/<tconst>/dismiss", methods=["POST"])
def dismiss_match(tconst: str):
    """Mark a match as dismissed. The row is hidden from the default view but
    still counts in the Total matches stat. Returns 204 No Content."""
    db = _conn()
    db.execute(
        "UPDATE matches SET dismissed_at=strftime('%Y-%m-%dT%H:%M:%SZ','now') "
        "WHERE tconst=?",
        (tconst,),
    )
    db.commit()
    db.close()
    return make_response("", 204)


@app.route("/matches/<tconst>/undismiss", methods=["POST"])
def undismiss_match(tconst: str):
    """Clear a match's dismissed_at timestamp, restoring it to the active list.
    Returns 204 No Content."""
    db = _conn()
    db.execute(
        "UPDATE matches SET dismissed_at=NULL WHERE tconst=?",
        (tconst,),
    )
    db.commit()
    db.close()
    return make_response("", 204)


@app.route("/api/metadata/<tconst>")
def api_metadata(tconst: str):
    """Return OMDb-sourced metadata for a title (from cache or fresh fetch).

    The OMDb API key is read from the ``config`` table so it is never
    hard-coded.  Results are cached in ``title_metadata``; subsequent
    requests for the same tconst are served entirely from SQLite — no
    outbound HTTP call is made.

    JSON response shape (all values str | null):
        plot, released, runtime, director, rt_score, imdb_rating,
        metascore, error
    """
    db = _conn()
    row = db.execute("SELECT value FROM config WHERE key='omdb_api_key'").fetchone()
    db.close()
    if not row:
        return jsonify({"error": "omdb_api_key not configured"}), 500

    client = OMDbClient(api_key=row["value"], db_path=DB_PATH)
    data = client.fetch(tconst)
    return jsonify(data)


@app.route("/upside_rescan", methods=["POST"])
def upside_rescan():
    """Kick off a background rescan of ~500 filter rejects.

    Spawns a daemon thread that calls Scanner.rescan_upside(); the page
    reloads via the redirect while work proceeds in the background.
    Werkzeug auto-reload is safe here — the thread is daemon so it won't
    block on Werkzeug's reloader process exit.
    """
    def worker():
        try:
            Scanner(db_path=DB_PATH).rescan_upside(
                sample_size=500,
                on_progress=lambda msg: print(f"[upside_rescan] {msg}"),
            )
        except Exception as e:
            print(f"[MovieScanner] upside_rescan error: {e}")

    threading.Thread(target=worker, daemon=True).start()
    return redirect(url_for("index"))


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5053, debug=True)
