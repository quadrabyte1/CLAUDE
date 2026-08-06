"""
Fable5_LinkCheck — Web link checker using CloakBrowser (stealth Chromium).

Crawls all same-domain hyperlinks starting from a seed URL.
Reports total links found, successful, and broken.

Retry-before-flag policy (V2.8):
  1. First hit with the default CloakBrowser context.
  2. On failure, wait ~1.5s (with jitter) and retry once with the SAME UA.
     Handles transient network/DNS/503 hiccups.
  3. If the second failure looks bot-detect-shaped (403/406/451/999, or a
     Cloudflare-challenge 503), retry ONCE with a realistic Chrome-on-macOS
     browser UA.
  4. Only after all applicable retries fail do we mark the URL broken.

429s keep the existing Retry-After honouring exponential back-off.

Port: 5052
"""

import re
import uuid
import random
import threading
import time
from collections import deque
from html.parser import HTMLParser
from urllib.parse import urlparse, urldefrag, urlunparse, urljoin

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
APP_VERSION = "V3.5"

# ── Retry policy constants ────────────────────────────────────────────────────
# Status codes that strongly suggest bot-detection rather than a real outage.
# On these, we escalate to a realistic browser UA before giving up.
BOT_DETECT_STATUSES = {403, 406, 451, 999}

# Realistic Chrome-on-macOS User-Agent used for the bot-detect escalation.
# Kept intentionally recent — servers that sniff for "old Chrome" also flag
# stale UAs as bot traffic. Bump periodically.
BROWSER_UA = (
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
    "AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/131.0.0.0 Safari/537.36"
)

# Base backoff between the first failure and the same-UA retry. Jittered
# ±30% at call time so parallel crawlers don't sync up on the target host.
_RETRY_BACKOFF_SEC = 1.5


@app.context_processor
def _inject_app_version():
    return {"app_version": APP_VERSION}

# In-memory job store: job_id -> state dict
_jobs: dict = {}

# Safety caps
_MAX_PAGES    = 500    # same-domain pages to crawl (hard ceiling; the
                       # user's max_depth control usually kicks in first)
_MAX_EXTERNAL = 500    # external links to probe (no recursion)


# ── Anchor-text extraction (V3.4) ─────────────────────────────────────────────

_WS_RUN = re.compile(r"\s+")


class _AnchorTextParser(HTMLParser):
    """
    Minimal HTML parser that walks a single `<a>…</a>` string and captures
    the pieces we need for the V3.4 text-extraction fallback ladder:

        1. anchor's own visible text (whitespace-collapsed, trimmed)
        2. else first child `<img alt="…">` alt attribute
        3. else the anchor's `aria-label` attribute
        4. else "" (render nothing)

    Kept stdlib-only so the extraction logic is unit-testable without
    Playwright — same rules as the JS side of `_make_page_fetcher`.
    """

    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.aria_label = ""
        self.first_img_alt = ""
        self._text_parts: list[str] = []
        self._in_anchor = False

    def handle_starttag(self, tag, attrs):
        attrs_d = dict(attrs)
        if tag == "a" and not self._in_anchor:
            self._in_anchor = True
            self.aria_label = (attrs_d.get("aria-label") or "").strip()
        elif tag == "img" and self._in_anchor and not self.first_img_alt:
            self.first_img_alt = (attrs_d.get("alt") or "").strip()

    def handle_endtag(self, tag):
        if tag == "a":
            self._in_anchor = False

    def handle_data(self, data):
        if self._in_anchor:
            self._text_parts.append(data)

    @property
    def inner_text(self) -> str:
        joined = "".join(self._text_parts)
        return _WS_RUN.sub(" ", joined).strip()


def _extract_anchor_text(anchor_html: str) -> str:
    """
    Apply the V3.4 fallback ladder to a raw `<a>…</a>` HTML string and
    return the visible text (or "" if nothing usable exists).

    Ladder:
        1. innerText — trimmed, internal whitespace collapsed to single space
        2. else first child <img alt="…">
        3. else the anchor's aria-label attribute
        4. else ""

    Whitespace-only strings collapse to "". The browser-side JS in
    `_make_page_fetcher` implements the exact same rules; this helper
    exists so tests can verify the rules deterministically.
    """
    if not anchor_html:
        return ""
    parser = _AnchorTextParser()
    try:
        parser.feed(anchor_html)
    except Exception:
        return ""
    if parser.inner_text:
        return parser.inner_text
    if parser.first_img_alt:
        return parser.first_img_alt
    if parser.aria_label:
        return parser.aria_label
    return ""


# ── Block-context extraction (V3.5) ───────────────────────────────────────────

# Block-level tags whose innerText we quote as the surrounding-context
# snippet for an anchor. Mirrors the JS `BLOCK_TAGS` set in
# `_make_page_fetcher` so the two extractors agree byte-for-byte on which
# ancestor wins the walk.
_BLOCK_TAGS = frozenset({
    "p", "li", "h1", "h2", "h3", "h4", "h5", "h6",
    "td", "th", "div", "section", "article",
    "aside", "blockquote", "figcaption",
})


class _BlockContextParser(HTMLParser):
    """
    Stdlib-only mirror of the browser-side "nearest block-level ancestor
    innerText" walk. Given a fragment containing exactly ONE `<a>` tag,
    returns the innerText of the closest enclosing block-level tag with
    whitespace collapsed and trimmed. If the anchor has no block-level
    ancestor in the fragment, returns `""`.

    Kept as a parser (not a regex) so nested tags — the common case for
    real-world markup — are handled by tracking the open-tag stack rather
    than string search.
    """

    def __init__(self):
        super().__init__(convert_charrefs=True)
        # Stack of {tag, text_parts, is_block} frames. On `<a>` we snapshot
        # the *deepest* block frame currently on the stack — that's the
        # anchor's nearest block-level ancestor. When we later close that
        # block, its accumulated text is our answer.
        self._stack: list[dict] = []
        self._captured_frame: dict | None = None
        self._captured_text: str = ""

    def handle_starttag(self, tag, attrs):
        is_block = tag.lower() in _BLOCK_TAGS
        frame = {"tag": tag.lower(), "text_parts": [], "is_block": is_block}
        self._stack.append(frame)
        if tag.lower() == "a" and self._captured_frame is None:
            # Find the deepest block frame currently on the stack (excluding
            # the anchor itself, which is at the top).
            for f in reversed(self._stack[:-1]):
                if f["is_block"]:
                    self._captured_frame = f
                    break

    def handle_endtag(self, tag):
        # Pop matching frames off the stack. Malformed HTML that closes an
        # unopened tag is silently ignored (matches browser leniency).
        for i in range(len(self._stack) - 1, -1, -1):
            if self._stack[i]["tag"] == tag.lower():
                closed = self._stack.pop(i)
                if closed is self._captured_frame and not self._captured_text:
                    joined = "".join(closed["text_parts"])
                    self._captured_text = _WS_RUN.sub(" ", joined).strip()
                break

    def handle_data(self, data):
        # Append text to every open frame — innerText of an ancestor
        # includes text from all its descendants.
        for f in self._stack:
            f["text_parts"].append(data)

    @property
    def context(self) -> str:
        if self._captured_text:
            return self._captured_text
        # Fragment ended without ever closing the captured block (e.g. a
        # <p> that wraps the whole snippet without a trailing </p>).
        # Flush what we've got.
        if self._captured_frame is not None:
            joined = "".join(self._captured_frame["text_parts"])
            return _WS_RUN.sub(" ", joined).strip()
        return ""


def _extract_block_context(html: str) -> str:
    """
    Return the whitespace-collapsed innerText of the nearest block-level
    ancestor of the first `<a>` in `html`, or `""` if there is none.

    Mirrors the JS walk in `_make_page_fetcher`. Tests use this to verify
    extraction rules without needing a real browser.
    """
    if not html:
        return ""
    parser = _BlockContextParser()
    try:
        parser.feed(html)
    except Exception:
        return ""
    return parser.context


# ── URL helpers ────────────────────────────────────────────────────────────────

def _norm(url: str) -> str:
    """Strip fragment and trailing slash for consistent deduplication."""
    url, _ = urldefrag(url)
    return url.rstrip("/") or url


def _norm_missing(url: str) -> str:
    """
    Site-wide dedup key for the "Unique Missing URLs" counter.

    Normalises a broken URL by:
      • lowercasing the host
      • stripping the fragment ("#…")
      • stripping the query string ("?…")
      • keeping the path EXACTLY as-is (a trailing "/" is preserved and
        treated as distinct from the same path without it, because servers
        treat them as distinct routes).

    Scheme and port are preserved verbatim so http vs https and non-default
    ports don't collapse together.
    """
    try:
        p = urlparse(url)
    except Exception:
        return url
    netloc = p.netloc.lower()
    # urlunparse takes a 6-tuple; blank out query (#4) and fragment (#5).
    return urlunparse((p.scheme, netloc, p.path, p.params, "", ""))


def _is_self_link(href: str, current_url: str) -> bool:
    """
    V3.3 — reflexive self-link detector.

    Returns True when `href`, resolved against `current_url`, points back to
    the same page WITHOUT a fragment. That's a bug — clicking such a link
    reloads the current page for no reason.

    Rule (strict — no false positives on intra-page anchors):
      1. resolved(href).strip_fragment == normalized(current_url)   AND
      2. resolved(href).fragment == ''  (i.e. `href` does not carry a #anchor)

    Examples for current_url = "https://example.com/foo":
      • href=""                              → self-link  ✅
      • href="/foo"                          → self-link  ✅
      • href="https://example.com/foo"       → self-link  ✅
      • href="#section"    (resolves to foo#section)  → NOT a self-link
      • href="/foo#section"                  → NOT a self-link
      • href="/bar"                          → NOT a self-link

    Normalisation mirrors `_norm_missing` (lowercased host, path preserved
    verbatim including trailing slash, query/fragment stripped) so
    comparisons agree with the rest of the pipeline.
    """
    if href is None:
        return False
    try:
        target = urljoin(current_url, href)
        parsed = urlparse(target)
    except Exception:
        return False
    # Rule 2: any fragment on the resolved target disqualifies immediately.
    # An intra-page anchor ("#section", "/foo#section") always survives here
    # unless its containing href has no fragment of its own.
    if parsed.fragment:
        return False
    # Rule 1: strip-fragment target must equal the normalized current URL.
    target_norm  = _norm_missing(target)
    current_norm = _norm_missing(current_url)
    return target_norm == current_norm


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


# ── Retry policy ───────────────────────────────────────────────────────────────

def _is_bot_detect(status, headers) -> bool:
    """
    True when the failure shape suggests bot-detection (rather than a real
    outage). Covers the classic set (403, 406, 451, 999) plus Cloudflare's
    "503 + cf-mitigated: challenge" pattern.

    `headers` may be None (network error) or any dict-like; case-insensitive
    header keys are handled defensively.
    """
    if status in BOT_DETECT_STATUSES:
        return True
    if status == 503 and headers:
        try:
            for k, v in headers.items():
                if k.lower() == "cf-mitigated" and "challenge" in str(v).lower():
                    return True
        except Exception:
            pass
    return False


def _sleep_with_jitter(base: float, sleep=time.sleep, rnd=random.random) -> None:
    """Sleep for `base` seconds ±30% (uniform jitter). Injectable for tests."""
    jitter = base * 0.3 * (2 * rnd() - 1)   # rnd() in [0,1) → jitter in [-0.3, +0.3]·base
    sleep(max(0.0, base + jitter))


def check_with_retry(
    fetch_default,
    fetch_browser=None,
    *,
    sleep=time.sleep,
    rnd=random.random,
):
    """
    Run the V2.8 retry-before-flag policy against two fetch callables.

    Parameters
    ----------
    fetch_default : callable() -> (status, headers, extra)
        Performs the request with the default (CloakBrowser) context.
        `status` is an int HTTP status or None.
        `headers` is a dict-like of response headers, or None on network error.
        `extra` is any payload the caller wants back on success (e.g. the
        list of anchors extracted from the page). Ignored on failure.
        The callable MAY raise — an exception is treated as a network-layer
        failure (status=None, headers=None, extra=None).
    fetch_browser : callable() -> (status, headers, extra) or None
        Same shape, but with a realistic browser UA. Called only when the
        second failure is bot-detect-shaped. If None, the escalation step
        is skipped (useful for external-link probes where we've decided not
        to spin up a second context).

    Returns
    -------
    dict with keys:
        status          — final HTTP status (or None)
        success         — bool
        attempts        — 1..3
        succeeded_with  — "default" | "browser" | None
        failure_reason  — short tag: "http_<code>" | "network_error" | None
        extra           — passthrough from the winning fetch, or None
    """
    def _run(fetch):
        try:
            status, headers, extra = fetch()
            return status, headers, extra, None
        except Exception as exc:
            # Any exception collapses to a network-layer failure. We keep
            # the exception type in the failure_reason so Thomas can tell
            # a timeout from a DNS blip in the crawl detail.
            return None, None, None, type(exc).__name__.lower()

    # ── Attempt 1: default UA ────────────────────────────────────────────────
    status, headers, extra, err = _run(fetch_default)
    if status is not None and status < 400:
        return {
            "status": status, "success": True, "attempts": 1,
            "succeeded_with": "default", "failure_reason": None, "extra": extra,
        }

    # ── Attempt 2: same UA after a jittered backoff ──────────────────────────
    _sleep_with_jitter(_RETRY_BACKOFF_SEC, sleep=sleep, rnd=rnd)
    status, headers, extra, err = _run(fetch_default)
    if status is not None and status < 400:
        return {
            "status": status, "success": True, "attempts": 2,
            "succeeded_with": "default", "failure_reason": None, "extra": extra,
        }

    # ── Attempt 3: escalate to browser UA if the shape says "bot-detect" ────
    if fetch_browser is not None and _is_bot_detect(status, headers):
        status_b, headers_b, extra_b, err_b = _run(fetch_browser)
        if status_b is not None and status_b < 400:
            return {
                "status": status_b, "success": True, "attempts": 3,
                "succeeded_with": "browser", "failure_reason": None,
                "extra": extra_b,
            }
        # Escalation also failed — surface the browser-UA status as the final.
        status, err = status_b, err_b
        return {
            "status": status, "success": False, "attempts": 3,
            "succeeded_with": None,
            "failure_reason": (f"http_{status}" if status else (err or "network_error")),
            "extra": None,
        }

    # Not bot-detect-shaped, or no browser fetcher available — give up.
    return {
        "status": status, "success": False, "attempts": 2,
        "succeeded_with": None,
        "failure_reason": (f"http_{status}" if status else (err or "network_error")),
        "extra": None,
    }


# ── Crawler worker (runs in background thread) ─────────────────────────────────

def _make_page_fetcher(page, url: str, *, wait_until: str, timeout_ms: int,
                       networkidle_ms: int | None = None,
                       extract_links: bool = False):
    """
    Build a zero-arg fetcher for `check_with_retry` that navigates `page` to
    `url` and returns (status, headers, extra).

    `extra` is the list of anchor hrefs when `extract_links=True`, else None.
    Exceptions bubble out — `check_with_retry` catches them and turns them
    into network_error failures.
    """
    def _fetch():
        resp = page.goto(url, wait_until=wait_until, timeout=timeout_ms)
        status = resp.status if resp else None
        headers = None
        if resp is not None:
            try:
                headers = resp.headers  # Playwright returns a dict
            except Exception:
                headers = None

        # Give SPAs time to hydrate before we extract anchors. Only relevant
        # to same-domain crawl (where we actually read the DOM); external
        # probes skip this via networkidle_ms=None.
        if networkidle_ms:
            try:
                page.wait_for_load_state("networkidle", timeout=networkidle_ms)
            except Exception:
                pass

        extra = None
        if extract_links and status is not None and status < 400:
            # V3.4 — return {href, text} pairs so the crawl detail can show
            # WHICH link on the page produced each broken/self/missing
            # reference. Text-extraction fallback ladder mirrored on the
            # Python side by `_extract_anchor_text` for tests:
            #   1. anchor innerText (trimmed, whitespace collapsed)
            #   2. else first child <img alt="…">
            #   3. else anchor's aria-label
            #   4. else ""  (empty — render bare URL)
            #
            # V3.5 — also capture `context`: the innerText of the nearest
            # block-level ancestor (p / li / h1-h6 / td / th / div / section
            # / article / aside / blockquote / figcaption). Whitespace runs
            # collapsed to single spaces, trimmed. Full block text is sent
            # unmodified — the template windows/truncates for display so the
            # API payload stays clean and future consumers get raw data.
            # `""` when the anchor has no block-level ancestor (link parked
            # directly in `<body>` with no wrapper).
            extra = page.evaluate(
                """() => {
                    const BLOCK_TAGS = new Set([
                        'P','LI','H1','H2','H3','H4','H5','H6',
                        'TD','TH','DIV','SECTION','ARTICLE',
                        'ASIDE','BLOCKQUOTE','FIGCAPTION'
                    ]);
                    return Array.from(document.querySelectorAll('a[href]'))
                        .filter(a => a.href && a.href.startsWith('http'))
                        .map(a => {
                            let text = (a.innerText || '').replace(/\\s+/g, ' ').trim();
                            if (!text) {
                                const img = a.querySelector('img[alt]');
                                if (img) text = (img.getAttribute('alt') || '').trim();
                            }
                            if (!text) {
                                text = (a.getAttribute('aria-label') || '').trim();
                            }
                            // Walk up to the nearest block-level ancestor.
                            // Stop at document root — if we never hit one,
                            // context stays "".
                            let context = '';
                            let node = a.parentElement;
                            while (node) {
                                if (BLOCK_TAGS.has(node.tagName)) {
                                    context = (node.innerText || '')
                                        .replace(/\\s+/g, ' ')
                                        .trim();
                                    break;
                                }
                                node = node.parentElement;
                            }
                            return { href: a.href, text: text, context: context };
                        });
                }"""
            )
        return status, headers, extra

    return _fetch


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
    # Lazy browser-UA context — created the first time an escalation is
    # needed, then reused for all subsequent escalations. Keeps clean crawls
    # from paying the extra-context cost.
    browser_ctx = {"page": None}

    def _get_browser_page():
        if browser_ctx["page"] is None:
            ctx = browser.new_context(user_agent=BROWSER_UA)
            browser_ctx["page"] = ctx.new_page()
        return browser_ctx["page"]

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

            # 429 back-off (Retry-After honoured) sits OUTSIDE the retry
            # helper because it needs a much longer, header-driven wait
            # than the transient/bot-detect flow. Up to 3 rate-limit
            # cycles, then hand the URL to the standard retry pipeline.
            for rl_attempt in range(3):
                try:
                    resp = page.goto(url, wait_until="load", timeout=20_000)
                    if resp and resp.status == 429:
                        try:
                            wait = int(resp.headers.get("retry-after", 0))
                        except Exception:
                            wait = 0
                        if not wait:
                            wait = (2 ** rl_attempt) * 5    # 5, 10, 20 s
                        time.sleep(min(wait, 60))
                        continue
                except Exception:
                    pass
                break

            fetch_default = _make_page_fetcher(
                page, url,
                wait_until="load", timeout_ms=20_000,
                networkidle_ms=wait_ms, extract_links=True,
            )
            fetch_browser = lambda: _make_page_fetcher(   # noqa: E731 — small closure
                _get_browser_page(), url,
                wait_until="load", timeout_ms=20_000,
                networkidle_ms=wait_ms, extract_links=True,
            )()

            outcome = check_with_retry(fetch_default, fetch_browser)

            # V3.4 — link entries carry the anchor's visible text alongside
            # the normalized URL: {"url": str, "text": str}. `text` may be
            # "" when the anchor has no innerText / img alt / aria-label.
            all_links: list[dict] = []
            # V3.3 — self-links (reflexive: link on page X pointing back
            # to X itself, without a fragment). Collected here BEFORE
            # normalisation so the fragment survives the check. Recorded
            # per-page in the same shape as regular links, but they never
            # enter the crawl queue and never contribute to broken counts.
            self_links_on_page: list[dict] = []
            if outcome["success"]:
                raw_links = outcome["extra"] or []
                seen_lnks: set[str] = set()
                seen_self: set[str] = set()
                for raw in raw_links:
                    # V3.4 — accept both new-shape dicts ({href, text}) from
                    # the JS extractor and legacy plain strings (defensive
                    # fallback if evaluate() ever regresses to a bare list).
                    # V3.5 — dicts may also carry `context` (innerText of the
                    # nearest block-level ancestor). Missing/empty → "".
                    if isinstance(raw, dict):
                        lnk = raw.get("href") or ""
                        text = raw.get("text") or ""
                        context = raw.get("context") or ""
                    else:
                        lnk = raw or ""
                        text = ""
                        context = ""
                    if not lnk:
                        continue
                    # Detect self-links against the RAW resolved href so
                    # `#anchor` fragments are still visible (they get
                    # stripped by `_norm` a few lines below). Self-links
                    # bypass the crawl queue and the HTTP retry ladder —
                    # they're structurally broken, not HTTP broken.
                    if _is_self_link(lnk, url):
                        # Dedupe on the resolved absolute URL so the same
                        # `<a href="">` repeated on the page only lands
                        # once per unique target. First occurrence's text
                        # wins (stable, predictable ordering).
                        if lnk not in seen_self:
                            seen_self.add(lnk)
                            self_links_on_page.append(
                                {"url": lnk, "text": text, "context": context}
                            )
                        continue
                    n = _norm(lnk)
                    if n in seen_lnks:
                        continue
                    seen_lnks.add(n)
                    all_links.append({"url": n, "text": text, "context": context})
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

            job["results"][url] = {
                "status": outcome["status"],
                "success": outcome["success"],
                "attempts": outcome["attempts"],
                "succeeded_with": outcome["succeeded_with"],
                "failure_reason": outcome["failure_reason"],
                "all_links": all_links,
                "self_links": self_links_on_page,
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

            fetch_default = _make_page_fetcher(
                page, url,
                wait_until="domcontentloaded", timeout_ms=10_000,
            )
            fetch_browser = lambda: _make_page_fetcher(   # noqa: E731
                _get_browser_page(), url,
                wait_until="domcontentloaded", timeout_ms=10_000,
            )()

            outcome = check_with_retry(fetch_default, fetch_browser)

            job["results"][url] = {
                "status": outcome["status"],
                "success": outcome["success"],
                "attempts": outcome["attempts"],
                "succeeded_with": outcome["succeeded_with"],
                "failure_reason": outcome["failure_reason"],
                "all_links": [],   # no recursion into external pages
                "self_links": [],  # external pages aren't checked for self-links
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
        {
            "url": u,
            "status": r["status"],
            "attempts": r.get("attempts", 1),
            "failure_reason": r.get("failure_reason"),
        }
        for u, r in results.items()
        if not r["success"]
    ]

    # ── Unique Missing URLs (site-wide dedupe) ────────────────────────────
    # Every broken *reference* across every page is a "broken link" — the
    # existing `broken` counter above stays as-is. The list below collapses
    # those references to distinct normalized URLs (see _norm_missing) so
    # Thomas can see how many *unique* endpoints are actually failing.
    # Sorted case-insensitive for a stable, alphabetized nav order.
    unique_missing_seen: dict = {}
    for u, r in results.items():
        if r["success"]:
            continue
        key = _norm_missing(u)
        if key not in unique_missing_seen:
            unique_missing_seen[key] = {
                "url": key,
                "status": r["status"],
            }
    unique_missing_urls = sorted(
        unique_missing_seen.values(), key=lambda x: x["url"].lower()
    )

    # Build link tree: each crawled page with all links it contains,
    # annotated with broken status if that target has been checked.
    #
    # V3.1 — while we're iterating, tally `broken_references`: every DOM
    # occurrence of a broken link in the crawl detail tree. This matches
    # exactly what the red up/down nav walks (all `[data-broken="true"]`
    # anchors), which comprises:
    #   • one anchor per crawled page whose fetch failed  (parent row)
    #   • one anchor per broken child link in every page's link list
    # A 404 URL that's crawled AND linked from 3 pages therefore counts
    # 4 times (1 parent + 3 children) — same as the nav's "N of M". The
    # pink summary card binds to THIS number; `broken` (unique-URL count)
    # still powers OK/broken arithmetic against `total_checked`.
    broken_references = 0
    # V3.3 — total reflexive self-link occurrences across the crawl. Same
    # counting shape as `broken_references`: one increment per DOM anchor,
    # so a page with two `<a href="">` tags counts as 2. Powers the BLUE
    # summary card + the blue up/down nav in results.html.
    self_reference_count = 0
    pages_data = []
    for page_url, r in results.items():
        if not r["success"]:
            # Parent page rendered as a broken row (results.html marks
            # `!p.success` parent anchors with data-broken="true").
            broken_references += 1
        links_info = []
        for entry in r.get("all_links", []):
            # V3.4 — link entries are `{url, text}` dicts. Older seeded
            # fixtures (and any legacy shape) may still be bare strings,
            # so we accept both. Missing/empty text falls through as "".
            # V3.5 — entries may also carry `context` (nearest block-level
            # ancestor's innerText). Missing → "".
            if isinstance(entry, dict):
                lnk = entry.get("url") or ""
                lnk_text = entry.get("text") or ""
                lnk_context = entry.get("context") or ""
            else:
                lnk = entry or ""
                lnk_text = ""
                lnk_context = ""
            if not lnk:
                continue
            lnk_result = results.get(lnk)
            if lnk_result is not None:
                link_broken = not lnk_result["success"]
            else:
                link_broken = None  # external or not yet checked
            if link_broken is True:
                broken_references += 1
            links_info.append({
                "url": lnk,
                # V3.4 — visible anchor text (innerText → img alt → aria-label
                # → ""). Template truncates at 60 chars and hides empty.
                "text": lnk_text,
                # V3.5 — full innerText of nearest block-level ancestor.
                # Template windows this to ~120 chars centered on the anchor
                # text for the "|"-separated third annotation piece.
                "context": lnk_context,
                "broken": link_broken,
                "status": lnk_result["status"] if lnk_result else None,
                # Retry metadata for the badge in the crawl detail. `attempts`
                # is 1..3; `succeeded_with` is "default" | "browser" | null
                # (null on true failures). Present on every checked link.
                "attempts": lnk_result.get("attempts") if lnk_result else None,
                "succeeded_with": (
                    lnk_result.get("succeeded_with") if lnk_result else None
                ),
                "failure_reason": (
                    lnk_result.get("failure_reason") if lnk_result else None
                ),
                # Only broken links carry a missing_key — the front-end uses
                # it to group DOM occurrences by unique missing URL for the
                # orange nav. Non-broken and unknown-state links stay null.
                "missing_key": _norm_missing(lnk) if link_broken else None,
                # V3.3 — self-link flag is always False on regular link rows;
                # actual self-links live in the sibling `self_links` array
                # below and are rendered as their own row type.
                "self_link": False,
            })

        # V3.3 — self-links carried through in the same shape as other links
        # so the template can render them uniformly. `broken` is None (we
        # never fetched them) and `self_link: true` is the discriminator.
        self_links_info = []
        for sl_entry in r.get("self_links", []):
            # V3.4 — same dict-or-string tolerance as regular links.
            # V3.5 — also plumb `context` from the ancestor walk.
            if isinstance(sl_entry, dict):
                sl_url = sl_entry.get("url") or ""
                sl_text = sl_entry.get("text") or ""
                sl_context = sl_entry.get("context") or ""
            else:
                sl_url = sl_entry or ""
                sl_text = ""
                sl_context = ""
            if not sl_url:
                continue
            self_reference_count += 1
            self_links_info.append({
                "url": sl_url,
                "text": sl_text,
                "context": sl_context,
                "broken": None,
                "status": None,
                "attempts": None,
                "succeeded_with": None,
                "failure_reason": None,
                "missing_key": None,
                "self_link": True,
            })

        pages_data.append({
            "url": page_url,
            "status": r["status"],
            "success": r["success"],
            "attempts": r.get("attempts", 1),
            "succeeded_with": r.get("succeeded_with"),
            "failure_reason": r.get("failure_reason"),
            "missing_key": _norm_missing(page_url) if not r["success"] else None,
            "links": links_info,
            "self_links": self_links_info,
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
        # V3.1 — total broken *references* across every page (duplicates
        # counted). Matches the DOM anchor count the red up/down nav walks
        # and drives the pink summary card. Distinct from `broken` (unique
        # URL count = total_checked - successful).
        "broken_references": broken_references,
        # V3.3 — total reflexive self-link occurrences across the crawl
        # (duplicates counted). Distinct from broken_references: self-links
        # aren't fetched, aren't retried, and don't contribute to broken/
        # unique-missing counts. They live in their own blue category.
        "self_reference_count": self_reference_count,
        "broken_urls": broken_urls if job["status"] == "done" else [],
        "unique_missing_count": len(unique_missing_urls),
        "unique_missing_urls": unique_missing_urls,
        "pages": pages_data,
        "capped": job.get("capped", False),
        "error": job.get("error"),
    })


if __name__ == "__main__":
    # debug=True enables Werkzeug's file-watching reloader: any change to a
    # watched .py file restarts the server automatically. Template edits are
    # picked up by TEMPLATES_AUTO_RELOAD above (no restart needed).
    app.run(host="0.0.0.0", port=5052, debug=True)
