"""
Regression tests for V3.5 surrounding-context snippet in crawl-detail
annotations.

Concept:
  V3.4 added the anchor's own visible text next to each URL in the crawl
  detail. V3.5 layers on a second piece — the innerText of the anchor's
  nearest block-level ancestor (p / li / h1-h6 / td / th / div / section /
  article / aside / blockquote / figcaption). That surrounding sentence
  gives Thomas a `Ctrl+F` search-string for generic anchor text like
  "here" or "read more" that would be impossible to locate otherwise.

  Server ships the FULL block innerText (whitespace-collapsed, trimmed),
  no truncation. The template windows it to ~120 chars centered on the
  anchor text's position within the block.

  Rendered examples:
    URL (anchor | "…surrounding sentence with anchor in the middle…")
    URL (self, Home | "…nav: Home About Contact Blog…")
    URL ("first 120 chars of block…")     — anchor text empty/missing

Run with:
    pytest -q Fable5_LinkCheck/tests/test_context_snippet.py
"""

import os
import sys

# Make Fable5_LinkCheck.app importable regardless of pytest cwd.
_HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.dirname(_HERE))

import app as app_module  # noqa: E402
from app import _extract_block_context  # noqa: E402


# ── Unit tests: _extract_block_context (Python mirror of the JS walk) ───────

def test_simple_paragraph_ancestor():
    """<p>Click <a>here</a> for more info</p> → full paragraph text."""
    html = "<p>Click <a href='/x'>here</a> for more info</p>"
    assert _extract_block_context(html) == "Click here for more info"


def test_no_block_ancestor_returns_empty():
    """Anchor with no block-level ancestor → ""."""
    html = "<a href='/x'>bare</a>"
    assert _extract_block_context(html) == ""


def test_nested_span_walks_up_to_block():
    """Anchor wrapped in inline spans finds the paragraph above them."""
    html = (
        "<div><p>Read <span><em>this <a href='/x'>link</a></em></span> now</p></div>"
    )
    # <p> is closer than <div>, so <p>'s innerText wins.
    assert _extract_block_context(html) == "Read this link now"


def test_list_item_is_block_level():
    """<li> counts as block-level and beats an outer <ul>/<ol>."""
    html = "<ul><li>First <a href='/x'>item</a> here</li></ul>"
    assert _extract_block_context(html) == "First item here"


def test_heading_tags_are_block_level():
    """All of h1..h6 are block-level."""
    for h in ("h1", "h2", "h3", "h4", "h5", "h6"):
        html = f"<{h}>See <a href='/x'>this</a></{h}>"
        assert _extract_block_context(html) == "See this", h


def test_whitespace_runs_collapsed_and_trimmed():
    """Multi-space / newline runs collapse to single spaces; leading/trailing stripped."""
    html = "<p>   Lots \n\n  of   \t whitespace <a href='/x'>x</a>   here   </p>"
    assert _extract_block_context(html) == "Lots of whitespace x here"


def test_div_ancestor_when_no_semantic_wrapper():
    """<div> is block-level for the purposes of this walk."""
    html = "<div>Sidebar note: see <a href='/x'>docs</a>.</div>"
    assert _extract_block_context(html) == "Sidebar note: see docs."


def test_empty_or_none_input_safe():
    """Defensive: empty / None inputs never crash."""
    assert _extract_block_context("") == ""
    assert _extract_block_context(None) == ""


# ── Integration: /api/status carries `context` on links & self_links ────────

def _seed_context_job():
    """
    Seed a done job with anchor text + context on both `all_links` and
    `self_links` so the /api/status shape can be asserted end-to-end.
    """
    job_id = "test-context-job"
    p1 = "https://ctx.test/page1"
    good = "https://ctx.test/good"

    app_module._jobs[job_id] = {
        "status": "done",
        "phase": "done",
        "traversal": "bfs",
        "request_delay": 0,
        "max_depth": None,
        "wait_timeout_ms": 5000,
        "start_url": p1,
        "current_url": None,
        "current_depth": 0,
        "queue_size": 0,
        "capped": False,
        "error": None,
        "results": {
            p1: {
                "status": 200, "success": True, "attempts": 1,
                "succeeded_with": "default", "failure_reason": None,
                "all_links": [
                    {
                        "url": good,
                        "text": "here",
                        "context": "Click here to learn more about our founding story",
                    },
                ],
                "self_links": [
                    {
                        "url": p1,
                        "text": "Home",
                        "context": "navigation menu: Home About Contact Blog",
                    },
                ],
                "external": False,
            },
            good: {
                "status": 200, "success": True, "attempts": 1,
                "succeeded_with": "default", "failure_reason": None,
                "all_links": [], "self_links": [], "external": False,
            },
        },
    }
    return job_id, p1, good


def _teardown_job(job_id):
    app_module._jobs.pop(job_id, None)


def test_api_ships_context_on_regular_link_entries():
    """Each link entry in a page's `links` list carries the full context."""
    job_id, p1, good = _seed_context_job()
    try:
        data = app_module.app.test_client().get(
            f"/api/status/{job_id}"
        ).get_json()
        page = next(p for p in data["pages"] if p["url"] == p1)
        entry = next(lnk for lnk in page["links"] if lnk["url"] == good)
        assert entry["context"] == (
            "Click here to learn more about our founding story"
        )
    finally:
        _teardown_job(job_id)


def test_api_ships_context_on_self_link_entries():
    """Self-link entries carry `context` so the template can render (self, Home | \"…\")."""
    job_id, p1, _ = _seed_context_job()
    try:
        data = app_module.app.test_client().get(
            f"/api/status/{job_id}"
        ).get_json()
        page = next(p for p in data["pages"] if p["url"] == p1)
        assert len(page["self_links"]) == 1
        sl = page["self_links"][0]
        assert sl["context"] == "navigation menu: Home About Contact Blog"
        assert sl["text"] == "Home"
        assert sl["self_link"] is True
    finally:
        _teardown_job(job_id)


def test_legacy_shape_without_context_still_works():
    """
    Backward compat: a pre-V3.5 job (dicts with `text` but no `context`,
    or plain-string entries) must round-trip through /api/status without
    crashing, emitting `context=""` on each link entry.
    """
    job_id = "test-legacy-no-context"
    p1 = "https://legacy2.test/p1"
    q = "https://legacy2.test/q"
    app_module._jobs[job_id] = {
        "status": "done", "phase": "done", "traversal": "bfs",
        "request_delay": 0, "max_depth": None, "wait_timeout_ms": 5000,
        "start_url": p1, "current_url": None, "current_depth": 0,
        "queue_size": 0, "capped": False, "error": None,
        "results": {
            p1: {
                "status": 200, "success": True, "attempts": 1,
                "succeeded_with": "default", "failure_reason": None,
                # V3.4-shape dict: text but no context
                "all_links": [{"url": q, "text": "Q"}],
                # legacy bare-string self-link
                "self_links": [p1],
                "external": False,
            },
            q: {
                "status": 200, "success": True, "attempts": 1,
                "succeeded_with": "default", "failure_reason": None,
                "all_links": [], "self_links": [], "external": False,
            },
        },
    }
    try:
        data = app_module.app.test_client().get(
            f"/api/status/{job_id}"
        ).get_json()
        page = next(p for p in data["pages"] if p["url"] == p1)
        assert page["links"][0]["url"] == q
        assert page["links"][0]["text"] == "Q"
        assert page["links"][0]["context"] == ""
        assert page["self_links"][0]["url"] == p1
        assert page["self_links"][0]["text"] == ""
        assert page["self_links"][0]["context"] == ""
    finally:
        _teardown_job(job_id)


# ── Template contract: contextSnippet + label helpers exist ─────────────────

def _template_src():
    tpl = os.path.join(os.path.dirname(_HERE), "templates", "results.html")
    with open(tpl, "r", encoding="utf-8") as f:
        return f.read()


def test_template_defines_context_snippet_helper():
    src = _template_src()
    assert "contextSnippet" in src, (
        "template must define the contextSnippet(context, anchorText) helper (V3.5)"
    )
    assert "CONTEXT_SNIPPET_LIMIT" in src, (
        "120-char window must live in the template as a constant"
    )
    # The straight-quote requirement — smart-quotes would break Ctrl+F.
    assert "&quot;" in src, (
        "template must render straight quotes around the context snippet"
    )


def test_template_defines_anchor_context_label_helper():
    src = _template_src()
    assert "anchorContextLabel" in src, (
        "template must define the anchorContextLabel(text, context) helper"
    )


def test_template_selflink_helper_takes_context_arg():
    """selfLinkCombinedLabel now takes (text, context) — grep the call site."""
    src = _template_src()
    # Must be called with both args on the self-link render path.
    assert "selfLinkCombinedLabel(sl.text, sl.context)" in src, (
        "self-link render path must pass sl.context into selfLinkCombinedLabel"
    )
    # And regular-link render path uses the new anchorContextLabel.
    assert "anchorContextLabel(lnk.text, lnk.context)" in src, (
        "regular-link render path must call anchorContextLabel(text, context)"
    )


# ── Template contract: contextSnippet windowing behavior (source-level) ────
#
# We simulate the helper's behavior in Python for a few cases so any future
# edit that changes the windowing math (center-on-anchor, ~120 char window,
# leading/trailing ellipses) has to change these tests too. We can't run the
# JS itself without a headless-browser round-trip, so we pin the contract in
# both the template source AND in an executable Python model that mirrors it.

def _js_context_snippet_model(context, anchor_text, limit=120):
    """
    Python mirror of `contextSnippet` in results.html. Kept in sync with
    the JS so the tests below stay accurate.
    """
    if context is None:
        return ""
    import re
    full = re.sub(r"\s+", " ", str(context)).strip()
    if not full:
        return ""
    if len(full) <= limit:
        return full
    anchor = "" if anchor_text is None else str(anchor_text).strip()
    start = 0
    if anchor:
        idx = full.lower().find(anchor.lower())
        if idx >= 0:
            anchor_mid = idx + len(anchor) // 2
            start = max(0, anchor_mid - limit // 2)
            start = min(start, max(0, len(full) - limit))
    end = min(len(full), start + limit)
    snippet = full[start:end]
    if start > 0:
        snippet = "…" + snippet
    if end < len(full):
        snippet = snippet + "…"
    return snippet


def test_short_context_returned_verbatim():
    """A block shorter than the window returns unchanged (no ellipses)."""
    ctx = "Click here for more info"
    out = _js_context_snippet_model(ctx, "here")
    assert out == ctx
    assert "…" not in out


def test_long_context_centers_on_anchor_with_ellipses():
    """
    500+ char block with the anchor near the middle → ~120-char window
    with BOTH leading and trailing ellipses, and the anchor text visible
    in the returned snippet.
    """
    prefix = "A" * 240
    suffix = "B" * 240
    ctx = f"{prefix} FIND-ME {suffix}"   # 240 + 1 + 7 + 1 + 240 = 489 chars
    out = _js_context_snippet_model(ctx, "FIND-ME")
    assert out.startswith("…"), "long block must lead with an ellipsis"
    assert out.endswith("…"),   "long block must trail with an ellipsis"
    assert "FIND-ME" in out,    "anchor text must survive inside the window"
    # Window is ~120 chars of block content plus the two ellipses.
    body = out.strip("…")
    assert 100 <= len(body) <= 130, (
        f"window body length {len(body)} outside expected ~120 char range"
    )


def test_long_context_anchor_not_present_falls_back_to_head():
    """
    Anchor text came from alt / aria-label and doesn't literally appear
    in the block → return the first N chars + trailing ellipsis only.
    """
    ctx = "L" * 500
    out = _js_context_snippet_model(ctx, "Company logo")
    assert not out.startswith("…"), "head-fallback must not lead with an ellipsis"
    assert out.endswith("…")
    body = out.rstrip("…")
    assert len(body) == 120


def test_whitespace_only_context_yields_empty_snippet():
    """A block of only spaces / newlines is treated as empty — no snippet."""
    assert _js_context_snippet_model("   \n\t   ", "here") == ""


def test_none_context_yields_empty_snippet():
    """Defensive: None input never crashes."""
    assert _js_context_snippet_model(None, "here") == ""


# ── Version pin ─────────────────────────────────────────────────────────────

def test_app_version_is_v35():
    """V3.5 — surrounding-context snippet ships in this version."""
    assert app_module.APP_VERSION == "V3.5"
