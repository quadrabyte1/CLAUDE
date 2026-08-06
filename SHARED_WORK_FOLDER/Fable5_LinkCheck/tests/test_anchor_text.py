"""
Regression tests for V3.4 anchor-text annotation in crawl-detail entries.

Concept:
  Every broken/self/missing reference in the crawl detail now shows the
  visible text of the anchor that produced it, in parentheses next to
  the URL. Text is extracted with a fallback ladder:

      1. anchor's innerText (trimmed, whitespace collapsed)
      2. else first child <img alt="…">
      3. else the anchor's aria-label attribute
      4. else "" (empty — render no annotation)

  Truncation happens client-side in the template (60 chars + ellipsis).
  The server stores the full captured text on each link entry so the API
  payload stays clean.

These tests exercise both the pure `_extract_anchor_text` helper (the
Python mirror of the browser-side JS extractor) and the /api/status
shape produced by a seeded fake job that carries anchor text on the
new-shape link dicts.

Run with:
    pytest -q Fable5_LinkCheck/tests/test_anchor_text.py
"""

import os
import sys

# Make Fable5_LinkCheck.app importable regardless of pytest cwd.
_HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.dirname(_HERE))

import app as app_module  # noqa: E402
from app import _extract_anchor_text  # noqa: E402


# ── Unit tests: _extract_anchor_text fallback ladder ────────────────────────

def test_inner_text_wins_over_alt_and_aria():
    """Rule 1: innerText is the top of the ladder."""
    html = (
        '<a href="/x" aria-label="ignored">'
        '<img alt="also ignored"> Learn more'
        '</a>'
    )
    assert _extract_anchor_text(html) == "Learn more"


def test_inner_text_whitespace_is_collapsed_and_trimmed():
    """Rule 1 normalisation: runs of any whitespace collapse to single spaces."""
    html = "<a href='/x'>   Hello   \n\t  world   </a>"
    assert _extract_anchor_text(html) == "Hello world"


def test_whitespace_only_inner_text_falls_through_to_alt():
    """
    Whitespace-only innerText MUST be treated as empty — the ladder should
    fall through to the img alt fallback. Guards against the naive
    `.strip()` check that would leave " " as "truthy".
    """
    html = '<a href="/x">   \n   <img alt="Company logo"></a>'
    assert _extract_anchor_text(html) == "Company logo"


def test_img_alt_only_anchor():
    """Rule 2: image-only anchor uses the alt attribute."""
    html = '<a href="/x"><img alt="Company logo"></a>'
    assert _extract_anchor_text(html) == "Company logo"


def test_first_img_alt_wins_when_multiple_images():
    """
    Rule 2 tiebreak: when an anchor has multiple <img> children, the FIRST
    image's alt is used (matches the JS `querySelector('img[alt]')`).
    """
    html = (
        '<a href="/x">'
        '<img alt="first"><img alt="second">'
        '</a>'
    )
    assert _extract_anchor_text(html) == "first"


def test_aria_label_only_anchor():
    """Rule 3: aria-label is used when nothing else exists."""
    html = '<a href="/x" aria-label="Read more"></a>'
    assert _extract_anchor_text(html) == "Read more"


def test_aria_label_beats_missing_alt():
    """Rule 3 beats an <img> without an alt attribute."""
    html = '<a href="/x" aria-label="Read more"><img></a>'
    assert _extract_anchor_text(html) == "Read more"


def test_empty_anchor_returns_empty_string():
    """Rule 4: nothing usable → empty (template renders no annotation)."""
    html = '<a href="/x"></a>'
    assert _extract_anchor_text(html) == ""


def test_completely_bare_input_is_safe():
    """Defensive: empty / None inputs never crash and return ""."""
    assert _extract_anchor_text("") == ""
    assert _extract_anchor_text(None) == ""


def test_whitespace_only_treated_as_empty_no_annotation():
    """
    Whitespace-only anchor (no img, no aria-label) yields "" so the
    template renders a bare URL — no empty "()" placeholder.
    """
    html = "<a href='/x'>   \n\t   </a>"
    assert _extract_anchor_text(html) == ""


# ── /api/status integration: text plumbed through link entries ──────────────

def _seed_anchor_text_job():
    """
    Seed a job that stresses each rung of the fallback ladder AND ensures
    the anchor text survives from `results[…].all_links` / `.self_links`
    through the /api/status payload unchanged (server ships full text;
    truncation happens client-side in the template).

    Layout:
      page1 (200) links to:
        - /good  (200, text="Home")
        - /dead  (404, text="Broken link with a very long description "
                            "that exceeds the sixty-character truncation")
        - self-link back to page1 (text="Reload me")
    """
    job_id = "test-anchor-text-job"
    p1 = "https://site.test/page1"
    good = "https://site.test/good"
    dead = "https://site.test/dead"

    long_text = (
        "Broken link with a very long description "
        "that exceeds the sixty-character truncation limit for sure"
    )

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
                    {"url": good, "text": "Home"},
                    {"url": dead, "text": long_text},
                ],
                "self_links": [
                    {"url": p1, "text": "Reload me"},
                ],
                "external": False,
            },
            good: {
                "status": 200, "success": True, "attempts": 1,
                "succeeded_with": "default", "failure_reason": None,
                "all_links": [], "self_links": [], "external": False,
            },
            dead: {
                "status": 404, "success": False, "attempts": 2,
                "succeeded_with": None, "failure_reason": "http_404",
                "all_links": [], "self_links": [], "external": False,
            },
        },
    }
    return job_id, p1, good, dead, long_text


def _teardown_job(job_id):
    app_module._jobs.pop(job_id, None)


def test_api_ships_text_on_regular_link_entries():
    """Each link entry in a page's `links` list carries the anchor text."""
    job_id, p1, good, dead, _ = _seed_anchor_text_job()
    try:
        data = app_module.app.test_client().get(
            f"/api/status/{job_id}"
        ).get_json()
        page = next(p for p in data["pages"] if p["url"] == p1)
        by_url = {lnk["url"]: lnk for lnk in page["links"]}
        assert by_url[good]["text"] == "Home"
        # dead-link text survives verbatim; truncation is a template concern.
        assert by_url[dead]["text"].startswith("Broken link with a very long")
        assert len(by_url[dead]["text"]) > 60, (
            "server must not truncate — that's the template's job"
        )
    finally:
        _teardown_job(job_id)


def test_api_ships_text_on_self_link_entries():
    """Self-link entries carry text too, so template can render (self, text)."""
    job_id, p1, _, _, _ = _seed_anchor_text_job()
    try:
        data = app_module.app.test_client().get(
            f"/api/status/{job_id}"
        ).get_json()
        page = next(p for p in data["pages"] if p["url"] == p1)
        assert len(page["self_links"]) == 1
        assert page["self_links"][0]["text"] == "Reload me"
        assert page["self_links"][0]["self_link"] is True
    finally:
        _teardown_job(job_id)


def test_legacy_string_shape_in_all_links_still_works():
    """
    Backward compat: pre-V3.4 jobs (and any legacy fixtures) may seed
    `all_links` / `self_links` as plain URL strings. The API must accept
    them and emit `text=""` rather than crashing.
    """
    job_id = "test-legacy-shape"
    p1 = "https://legacy.test/p1"
    q = "https://legacy.test/q"
    app_module._jobs[job_id] = {
        "status": "done", "phase": "done", "traversal": "bfs",
        "request_delay": 0, "max_depth": None, "wait_timeout_ms": 5000,
        "start_url": p1, "current_url": None, "current_depth": 0,
        "queue_size": 0, "capped": False, "error": None,
        "results": {
            p1: {
                "status": 200, "success": True, "attempts": 1,
                "succeeded_with": "default", "failure_reason": None,
                "all_links": [q],       # legacy bare-string shape
                "self_links": [p1],     # legacy bare-string shape
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
        assert page["links"][0]["text"] == ""
        assert page["self_links"][0]["url"] == p1
        assert page["self_links"][0]["text"] == ""
    finally:
        _teardown_job(job_id)


# ── Template contract: the truncation JS function ───────────────────────────
#
# The template ships a `truncateAnchorText(text)` JS helper that:
#   • returns "" for null / undefined / whitespace-only
#   • returns the text as-is when length ≤ 60
#   • else returns first 60 chars + "…"
#
# We assert the source shape (not the runtime behavior — that would need a
# headless-browser round-trip) so future edits don't regress the contract.

def test_template_defines_anchor_text_helpers():
    """The template exposes the client-side truncation helper family."""
    tpl = os.path.join(
        os.path.dirname(_HERE), "templates", "results.html"
    )
    with open(tpl, "r", encoding="utf-8") as f:
        src = f.read()
    assert "truncateAnchorText" in src, (
        "template must define the truncateAnchorText helper (V3.4)"
    )
    assert "anchorTextLabel" in src, (
        "template must define the anchorTextLabel helper (V3.4)"
    )
    assert "ANCHOR_TEXT_LIMIT = 60" in src, (
        "60-char truncation limit must live in the template as a constant"
    )
    # Combined self-link label: `(self, <text>)` in one parenthetical.
    assert "selfLinkCombinedLabel" in src, (
        "template must combine self-link + text into a single parenthetical"
    )


def test_app_version_is_at_least_v34():
    """
    Version confirmation. V3.4 introduced anchor-text; later feature bumps
    (V3.5+) keep the anchor-text contract intact, so this assertion only
    guards the floor. Exact-version pinning lives in the newest feature's
    test file (test_context_snippet.py for V3.5).
    """
    assert app_module.APP_VERSION >= "V3.4"
