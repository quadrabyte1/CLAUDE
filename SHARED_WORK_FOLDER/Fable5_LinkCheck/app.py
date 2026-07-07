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

# In-memory job store: job_id -> state dict
_jobs: dict = {}

# Safety caps
_MAX_PAGES    = 2000   # same-domain pages to crawl
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
    start_domain = _root_domain(urlparse(start_url).netloc)

    norm_start = _norm(start_url)
    queue: deque[str] = deque([norm_start])
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
            url = queue.popleft() if bfs else queue.pop()
            queued.discard(url)
            if url in visited:
                continue
            visited.add(url)

            job["current_url"] = url
            job["queue_size"] = len(queue) + len(ext_queue)

            status = None
            success = False
            final_attempt = 0
            all_links: list[str] = []

            for attempt in range(5):
                final_attempt = attempt
                try:
                    resp = page.goto(url, wait_until="domcontentloaded", timeout=20_000)
                    status = resp.status if resp else None

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
                                if n not in visited and n not in queued:
                                    queue.append(n)
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

    job_id = uuid.uuid4().hex[:10]
    _jobs[job_id] = {
        "status": "running",
        "phase": "crawl",
        "traversal": traversal,
        "start_url": raw,
        "results": {},
        "current_url": None,
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
        "start_url": job["start_url"],
        "current_url": job["current_url"],
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
    app.run(host="0.0.0.0", port=5052, debug=False)
