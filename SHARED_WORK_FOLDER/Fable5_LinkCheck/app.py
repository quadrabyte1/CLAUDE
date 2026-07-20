"""
Fable5_LinkCheck — Web link checker using CloakBrowser (stealth Chromium).

Crawls all same-domain hyperlinks starting from a seed URL.
Retries broken links up to 5 attempts (0.5s between retries).
Reports total links found, successful, and broken.

Port: 5052
"""

import uuid
import threading
import time
from collections import deque
from urllib.parse import urlparse, urldefrag

from flask import Flask, render_template, request, redirect, url_for, jsonify

app = Flask(__name__)
# Re-read templates from disk on every render so template edits are visible
# after a browser refresh without needing a server restart (debug=False
# otherwise leaves Jinja's on-disk cache in place).
app.config["TEMPLATES_AUTO_RELOAD"] = True
app.jinja_env.auto_reload = True

# Single source of truth for the version badge shown in the footer of every
# page. Bump on every change; templates read it via the context processor
# below, so there's only one place to update.
APP_VERSION = "V2.5"


@app.context_processor
def _inject_app_version():
    return {"app_version": APP_VERSION}

# In-memory job store: job_id -> state dict
_jobs: dict = {}

# Safety caps
_MAX_PAGES    = 500    # same-domain pages to crawl (hard ceiling; the
                       # user's max_depth control usually kicks in first)
_MAX_EXTERNAL = 500    # external links to probe (no recursion)


# ── URL helpers ────────────────────────────────────────────────────────────────

def _norm(url: str) -> str:
    """Strip fragment and trailing slash for consistent deduplication."""
    url, _ = urldefrag(url)
    return url.rstrip("/") or url


def _root_domain(hostname: str) -> str:
    """'docs.github.com' → 'github.com'  (last two hostname parts)."""
    parts = hostname.split(".")
    return ".".join(parts[-2:]) if len(parts) >= 2 else hostname


def _same_domain(url: str, root_domain: str) -> bool:
    """True when url shares the same registered domain (subdomains included)."""
    try:
        return _root_domain(urlparse(url).netloc) == root_domain
    except Exception:
        return False


# ── Crawler worker (runs in background thread) ─────────────────────────────────

def _crawl_worker(job_id: str, start_url: str) -> None:
    from cloakbrowser import launch

    job = _jobs[job_id]
    bfs = job.get("traversal", "bfs") == "bfs"
    # max_depth = None → unlimited (bounded only by _MAX_PAGES). Otherwise a
    # child link at depth D+1 is only queued when D+1 <= max_depth. The seed
    # URL is at depth 0.
    max_depth = job.get("max_depth")
    wait_ms   = int(job.get("wait_timeout_ms", 5000))
    start_domain = _root_domain(urlparse(start_url).netloc)

    norm_start = _norm(start_url)
    queue: deque[tuple[str, int]] = deque([(norm_start, 0)])
    queued: set[str] = {norm_start}     # mirrors main queue for O(1) lookup
    ext_queue: deque[str] = deque()
    ext_queued: set[str] = set()        # mirrors external queue
    visited: set[str] = set()

    browser = None
    try:
        browser = launch(headless=True)
        page = browser.new_page()

        # ── Phase 1: crawl same-domain pages, collect external links ──────────
        while queue and len(visited) < _MAX_PAGES:
            url, depth = queue.popleft() if bfs else queue.pop()
            queued.discard(url)
            if url in visited:
                continue
            visited.add(url)

            job["current_url"]   = url
            job["current_depth"] = depth
            job["queue_size"]    = len(queue) + len(ext_queue)

            status = None
            success = False
            final_attempt = 0
            all_links: list[str] = []

            for attempt in range(5):
                final_attempt = attempt
                try:
                    # wait_until="load" (not "domcontentloaded") so SPA
                    # frameworks like React have time to hydrate the nav —
                    # without this, sites like IMDB return an empty DOM at
                    # snapshot time and the crawler finds ~0 links.
                    resp = page.goto(url, wait_until="load", timeout=20_000)
                    status = resp.status if resp else None

                    # Give the page's post-load fetches (React hydration,
                    # nav data, etc.) up to `wait_ms` to finish. IMDB serves
                    # a 202 shell and its real anchors only appear ~3s after
                    # load. Sites with background polling never reach
                    # networkidle — that's fine, the wait itself is what
                    # matters. Per-crawl configurable (2s / 5s / 10s).
                    try:
                        page.wait_for_load_state("networkidle", timeout=wait_ms)
                    except Exception:
                        pass

                    if status == 429:
                        # Honour Retry-After if present, else exponential back-off
                        if attempt < 4:
                            try:
                                wait = int(resp.headers.get("retry-after", 0))
                            except Exception:
                                wait = 0
                            if not wait:
                                wait = (2 ** attempt) * 5   # 5, 10, 20, 40 s
                            time.sleep(min(wait, 60))
                        continue

                    if status is not None and status < 400:
                        success = True
                        raw_links: list[str] = page.evaluate(
                            "() => Array.from(document.querySelectorAll('a[href]'))"
                            ".map(a => a.href)"
                            ".filter(h => h.startsWith('http'))"
                        )
                        seen_lnks: set[str] = set()
                        for lnk in raw_links:
                            n = _norm(lnk)
                            if n in seen_lnks:
                                continue
                            seen_lnks.add(n)
                            all_links.append(n)
                            if _same_domain(n, start_domain):
                                # Depth cap: don't queue children of a page at
                                # or beyond max_depth. max_depth=None disables
                                # the cap (only _MAX_PAGES stops the crawl).
                                if n not in visited and n not in queued and (
                                    max_depth is None or depth + 1 <= max_depth
                                ):
                                    queue.append((n, depth + 1))
                                    queued.add(n)
                            else:
                                if (
                                    n not in ext_queued
                                    and n not in visited
                                    and len(ext_queued) < _MAX_EXTERNAL
                                ):
                                    ext_queue.append(n)
                                    ext_queued.add(n)
                        break

                    if attempt < 4:
                        time.sleep(0.5)

                except Exception:
                    if attempt < 4:
                        time.sleep(0.5)

            job["results"][url] = {
                "status": status,
                "success": success,
                "retries": final_attempt,
                "all_links": all_links if success else [],
                "external": False,
            }

            # Polite inter-request delay (prevents triggering rate limits)
            if job.get("request_delay", 0) > 0:
                time.sleep(job["request_delay"])

        if len(visited) >= _MAX_PAGES:
            job["capped"] = True

        # ── Phase 2: probe external links — one fetch, no recursion ──────────
        job["phase"] = "external"
        while ext_queue:
            url = ext_queue.popleft()
            if url in visited:
                continue
            visited.add(url)

            job["current_url"] = url
            job["queue_size"] = len(ext_queue)

            status = None
            success = False
            final_attempt = 0

            for attempt in range(5):
                final_attempt = attempt
                try:
                    resp = page.goto(url, wait_until="domcontentloaded", timeout=10_000)
                    status = resp.status if resp else None
                    if status is not None and status < 400:
                        success = True
                        break
                    if attempt < 4:
                        time.sleep(0.5)
                except Exception:
                    if attempt < 4:
                        time.sleep(0.5)

            job["results"][url] = {
                "status": status,
                "success": success,
                "retries": final_attempt,
                "all_links": [],   # no recursion into external pages
                "external": True,
            }

    except Exception as exc:
        job["error"] = str(exc)

    finally:
        if browser:
            try:
                browser.close()
            except Exception:
                pass
        job["status"] = "done"
        job["current_url"] = None
        job["queue_size"] = 0


# ── Routes ─────────────────────────────────────────────────────────────────────

@app.route("/")
def index():
    return render_template("index.html")


@app.route("/crawl", methods=["POST"])
def start_crawl():
    raw = request.form.get("url", "").strip()
    if not raw.startswith("http"):
        raw = "https://" + raw

    traversal = request.form.get("traversal", "bfs")
    if traversal not in ("bfs", "dfs"):
        traversal = "bfs"

    try:
        request_delay = float(request.form.get("request_delay", 0))
    except (ValueError, TypeError):
        request_delay = 0.0
    if request_delay not in (0.0, 0.5, 1.0, 2.0):
        request_delay = 0.0

    # Max recursion depth. 0 (or non-numeric / >99) → unlimited (None).
    try:
        md = int(request.form.get("max_depth", "2"))
    except (ValueError, TypeError):
        md = 2
    max_depth = None if md <= 0 or md > 99 else md

    # Per-page networkidle wait (must give SPAs like IMDB time to hydrate).
    try:
        wt = int(request.form.get("wait_timeout", "5"))
    except (ValueError, TypeError):
        wt = 5
    if wt not in (2, 5, 10):
        wt = 5
    wait_timeout_ms = wt * 1000

    job_id = uuid.uuid4().hex[:10]
    _jobs[job_id] = {
        "status": "running",
        "phase": "crawl",
        "traversal": traversal,
        "request_delay": request_delay,
        "max_depth": max_depth,
        "wait_timeout_ms": wait_timeout_ms,
        "start_url": raw,
        "results": {},
        "current_url": None,
        "current_depth": 0,
        "queue_size": 1,
        "capped": False,
        "error": None,
    }

    threading.Thread(
        target=_crawl_worker, args=(job_id, raw), daemon=True
    ).start()

    return redirect(url_for("results_page", job_id=job_id))


@app.route("/results/<job_id>")
def results_page(job_id):
    if job_id not in _jobs:
        return "Job not found", 404
    return render_template(
        "results.html",
        job_id=job_id,
        start_url=_jobs[job_id]["start_url"],
        traversal=_jobs[job_id].get("traversal", "bfs"),
        request_delay=_jobs[job_id].get("request_delay", 0),
        max_depth=_jobs[job_id].get("max_depth"),
        wait_timeout_ms=_jobs[job_id].get("wait_timeout_ms", 5000),
    )


@app.route("/api/status/<job_id>")
def api_status(job_id):
    job = _jobs.get(job_id)
    if not job:
        return jsonify({"error": "not found"}), 404

    results = job["results"]
    total = len(results)
    successful = sum(1 for r in results.values() if r["success"])
    broken = total - successful

    broken_urls = [
        {"url": u, "status": r["status"], "retries": r["retries"]}
        for u, r in results.items()
        if not r["success"]
    ]

    # Build link tree: each crawled page with all links it contains,
    # annotated with broken status if that target has been checked.
    pages_data = []
    for page_url, r in results.items():
        links_info = []
        for lnk in r.get("all_links", []):
            lnk_result = results.get(lnk)
            if lnk_result is not None:
                link_broken = not lnk_result["success"]
            else:
                link_broken = None  # external or not yet checked
            links_info.append({
                "url": lnk,
                "broken": link_broken,
                "status": lnk_result["status"] if lnk_result else None,
            })
        pages_data.append({
            "url": page_url,
            "status": r["status"],
            "success": r["success"],
            "links": links_info,
        })

    return jsonify({
        "status": job["status"],
        "phase": job.get("phase", "crawl"),
        "traversal": job.get("traversal", "bfs"),
        "request_delay": job.get("request_delay", 0),
        "max_depth": job.get("max_depth"),
        "wait_timeout_ms": job.get("wait_timeout_ms", 5000),
        "start_url": job["start_url"],
        "current_url": job["current_url"],
        "current_depth": job.get("current_depth", 0),
        "queue_size": job["queue_size"],
        "total_checked": total,
        "successful": successful,
        "broken": broken,
        "broken_urls": broken_urls if job["status"] == "done" else [],
        "pages": pages_data,
        "capped": job.get("capped", False),
        "error": job.get("error"),
    })


if __name__ == "__main__":
    # debug=True enables Werkzeug's file-watching reloader: any change to a
    # watched .py file restarts the server automatically. Template edits are
    # picked up by TEMPLATES_AUTO_RELOAD above (no restart needed).
    app.run(host="0.0.0.0", port=5052, debug=True)
