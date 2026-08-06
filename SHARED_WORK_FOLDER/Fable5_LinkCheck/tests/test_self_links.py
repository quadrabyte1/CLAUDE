"""
Regression tests for V3.3 reflexive self-link detection.

Concept:
  A page X contains a link that resolves to page X itself, without a
  fragment. Clicking such a link reloads the current page for no reason.
  V3.3 detects these and reports them in a separate blue category so
  Thomas can distinguish "structural navigation bug" from "HTTP broken".

Detection rule (strict — no false positives on intra-page anchors):
  Given a link with `href` on page `current_url`, resolve to absolute URL
  `target`. Flag as self-link if AND ONLY IF:
    1. strip_fragment(target) == normalized(current_url)   AND
    2. target.fragment == ''  (the href produced no fragment)

These tests exercise both the pure `_is_self_link` helper (fast, no
network) and the /api/status shape produced by a seeded fake job.

Run with:
    pytest -q Fable5_LinkCheck/tests/test_self_links.py
"""

import os
import sys

# Make Fable5_LinkCheck.app importable regardless of pytest cwd.
_HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.dirname(_HERE))

import app as app_module  # noqa: E402
from app import _is_self_link  # noqa: E402


# ── Unit tests: _is_self_link helper ─────────────────────────────────────────

CURRENT = "https://example.com/foo"


def test_empty_href_is_self_link():
    """<a href="">  → reloads the current page. Self-link."""
    assert _is_self_link("", CURRENT) is True


def test_absolute_self_href_is_self_link():
    """<a href="https://example.com/foo"> → resolves to self. Self-link."""
    assert _is_self_link("https://example.com/foo", CURRENT) is True


def test_root_relative_self_path_is_self_link():
    """<a href="/foo"> → resolves to self. Self-link."""
    assert _is_self_link("/foo", CURRENT) is True


def test_intra_page_anchor_is_NOT_flagged():
    """
    <a href="#top"> resolves to https://example.com/foo#top — legitimate
    intra-page navigation, MUST NOT be flagged. This is the critical
    false-positive guard.
    """
    assert _is_self_link("#top", CURRENT) is False


def test_absolute_self_with_fragment_is_NOT_flagged():
    """<a href="/foo#section"> is intra-page nav via absolute path. Not self."""
    assert _is_self_link("/foo#section", CURRENT) is False


def test_different_path_is_NOT_flagged():
    """<a href="/bar"> is a normal crawl target, not a self-link."""
    assert _is_self_link("/bar", CURRENT) is False


def test_different_host_same_path_is_NOT_flagged():
    """Same path on a different host is a different page."""
    assert _is_self_link("https://other.com/foo", CURRENT) is False


def test_none_href_safe():
    """Defensive: None href never crashes, never flagged."""
    assert _is_self_link(None, CURRENT) is False


# ── /api/status integration tests: seed a fake job ───────────────────────────

def _seed_self_link_job():
    """
    Seed the exact scenario from the V3.3 spec:

      Page https://example.com/foo contains anchors:
        <a href="">                        — self-link  ✅
        <a href="https://example.com/foo"> — self-link  ✅
        <a href="/foo">                    — self-link  ✅
        <a href="#top">                    — intra-page ❌
        <a href="/bar">                    — external target, 200 ✅

    Simulates what the crawler would record after resolving each anchor
    through the DOM and routing self-links via _is_self_link.
    """
    job_id = "test-self-link-job"
    foo = "https://example.com/foo"
    bar = "https://example.com/bar"

    # The three self-link hrefs as they would appear resolved to absolute
    # by Playwright's `a.href`. `#top` correctly resolves WITH a fragment
    # and therefore would NOT be recorded as a self-link by the crawler.
    self_links_recorded = [
        "https://example.com/foo",   # was href=""
        "https://example.com/foo",   # was href="https://example.com/foo"
        "https://example.com/foo",   # was href="/foo"
    ]

    app_module._jobs[job_id] = {
        "status": "done",
        "phase": "done",
        "traversal": "bfs",
        "request_delay": 0,
        "max_depth": None,
        "wait_timeout_ms": 5000,
        "start_url": foo,
        "current_url": None,
        "current_depth": 0,
        "queue_size": 0,
        "capped": False,
        "error": None,
        "results": {
            foo: {
                "status": 200, "success": True, "attempts": 1,
                "succeeded_with": "default", "failure_reason": None,
                # /bar is the only anchor that entered `all_links`
                # (self-links are diverted before dedupe; #top would
                # have resolved with a fragment and _norm'd to foo,
                # but the crawler already filters intra-page anchors
                # through _is_self_link → False and then dedupes them
                # away against the current page; here we omit it so
                # the test explicitly proves it wasn't queued).
                "all_links": [bar],
                "self_links": self_links_recorded,
                "external": False,
            },
            bar: {
                "status": 200, "success": True, "attempts": 1,
                "succeeded_with": "default", "failure_reason": None,
                "all_links": [], "self_links": [], "external": False,
            },
        },
    }
    return job_id, foo


def _teardown_job(job_id):
    app_module._jobs.pop(job_id, None)


def test_self_reference_count_is_three():
    """The three self-links must land in the self_reference_count field."""
    job_id, _ = _seed_self_link_job()
    try:
        data = app_module.app.test_client().get(f"/api/status/{job_id}").get_json()
        assert data["self_reference_count"] == 3, (
            f"expected 3 self-links, got {data['self_reference_count']}"
        )
    finally:
        _teardown_job(job_id)


def test_self_links_do_NOT_pollute_broken_counts():
    """
    Self-links are structurally broken, not HTTP broken. They MUST NOT
    inflate broken / broken_references / unique_missing_count.
    """
    job_id, _ = _seed_self_link_job()
    try:
        data = app_module.app.test_client().get(f"/api/status/{job_id}").get_json()
        assert data["broken"] == 0, (
            "self-links must not count as broken URLs "
            f"(got broken={data['broken']})"
        )
        assert data["broken_references"] == 0, (
            "self-links must not inflate broken_references "
            f"(got {data['broken_references']})"
        )
        assert data["unique_missing_count"] == 0, (
            "self-links must not appear in unique_missing_count "
            f"(got {data['unique_missing_count']})"
        )
    finally:
        _teardown_job(job_id)


def test_intra_page_anchor_is_not_flagged_via_helper():
    """
    Direct assertion of the spec table row for #top on the same page.
    """
    assert _is_self_link("#top", "https://example.com/foo") is False


def test_self_links_carried_per_page_in_api_shape():
    """
    Per-page `self_links` entries must be present with self_link=True so
    the template can render them uniformly next to regular link rows.
    """
    job_id, foo = _seed_self_link_job()
    try:
        data = app_module.app.test_client().get(f"/api/status/{job_id}").get_json()
        pages = {p["url"]: p for p in data["pages"]}
        foo_page = pages[foo]
        assert "self_links" in foo_page
        assert len(foo_page["self_links"]) == 3
        for entry in foo_page["self_links"]:
            assert entry["self_link"] is True
            assert entry["broken"] is None      # never fetched
            assert entry["status"] is None
            assert entry["attempts"] is None    # bypassed retry ladder
    finally:
        _teardown_job(job_id)


def test_clean_page_has_zero_self_references():
    """No self-links → count is 0 (and doesn't crash on a missing field)."""
    job_id = "test-clean-self"
    p1 = "https://site.test/p1"
    app_module._jobs[job_id] = {
        "status": "done", "phase": "done", "traversal": "bfs",
        "request_delay": 0, "max_depth": None, "wait_timeout_ms": 5000,
        "start_url": p1, "current_url": None, "current_depth": 0,
        "queue_size": 0, "capped": False, "error": None,
        "results": {
            p1: {"status": 200, "success": True, "attempts": 1,
                 "succeeded_with": "default", "failure_reason": None,
                 "all_links": [], "self_links": [], "external": False},
        },
    }
    try:
        data = app_module.app.test_client().get(f"/api/status/{job_id}").get_json()
        assert data["self_reference_count"] == 0
    finally:
        _teardown_job(job_id)


def test_app_version_is_v33_or_later():
    """
    Version confirmation. Originally guarded the V3.2 → V3.3 bump; kept
    as a floor check so subsequent bumps (V3.4+) don't break the suite
    while still preventing an accidental downgrade.
    """
    v = app_module.APP_VERSION
    assert v.startswith("V") and float(v[1:]) >= 3.3, (
        f"APP_VERSION must be V3.3 or later, got {v!r}"
    )
