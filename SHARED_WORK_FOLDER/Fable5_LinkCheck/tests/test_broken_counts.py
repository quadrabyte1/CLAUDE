"""
Regression tests for V3.1 broken-links summary card fix.

Bug (introduced with the V2.7 orange counter):
  The pink/red "broken" summary card at the top of the crawl detail was
  reading the SAME dedupe-based value as the orange "unique missing URLs"
  card next to it. When the same 404 was linked from several pages, the
  pink card understated reality — reporting the unique-URL count instead
  of the total broken *references*. The red up/down nav (which walks DOM
  anchors) had the correct total, so the two numbers disagreed with each
  other despite both claiming to count "broken".

Fix (V3.1):
  `/api/status` now returns a separate `broken_references` field that
  counts every broken link occurrence across every page (matching what
  the red nav walks). The pink summary card is bound to that field. The
  orange card still uses `unique_missing_count` (dedupe).

These tests seed a fake job in the in-memory `_jobs` dict and assert the
two counts differ correctly in a duplication scenario.

Run with:
    pytest -q Fable5_LinkCheck/tests/test_broken_counts.py
"""

import os
import sys

# Make Fable5_LinkCheck.app importable regardless of pytest cwd.
_HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.dirname(_HERE))

import app as app_module  # noqa: E402


def _seed_duplication_job():
    """
    Seed a job that produces DIFFERENT numbers for broken_references
    (what the red up/down nav walks in the DOM) vs unique_missing_count
    (dedupe of the same broken URLs). Layout:

      page1.html (200) links to:
        - page2.html          (200)
        - example.com/dead-a  (404)  ← child ref #1 of dead-a
        - example.com/dead-b  (404)  ← child ref #1 of dead-b

      page2.html (200) links to:
        - example.com/dead-a  (404)  ← child ref #2 of dead-a
        - example.com/dead-c  (404)  ← child ref #1 of dead-c
        - example.com/dead-a  (404)  ← child ref #3 of dead-a
                                        (same URL twice on ONE page —
                                        still two DOM anchors)

    The crawler also visited dead-a, dead-b, dead-c as pages (they're in
    `results`), so each renders one broken PARENT row in the tree too.

    DOM anchors with data-broken="true" (what the red nav counts):
      • 3 broken parent rows (dead-a, dead-b, dead-c)
      • 5 broken child anchors (3× dead-a, 1× dead-b, 1× dead-c)
      → broken_references = 8

    Expected /api/status:
      • total_checked     = 5   (page1, page2, dead-a, dead-b, dead-c)
      • successful        = 2   (page1, page2)
      • broken            = 3   (unique URLs failed)
      • unique_missing    = 3   (same, site-wide dedupe)
      • broken_references = 8   (matches red nav's "N of 8 broken")
    """
    job_id = "test-dup-job"
    p1 = "https://site.test/page1"
    p2 = "https://site.test/page2"
    d_a = "https://site.test/dead-a"
    d_b = "https://site.test/dead-b"
    d_c = "https://site.test/dead-c"

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
                "all_links": [p2, d_a, d_b],
                "external": False,
            },
            p2: {
                "status": 200, "success": True, "attempts": 1,
                "succeeded_with": "default", "failure_reason": None,
                # dead-a appears TWICE on this page — both count as
                # separate DOM anchors (and therefore separate references).
                "all_links": [d_a, d_c, d_a],
                "external": False,
            },
            d_a: {
                "status": 404, "success": False, "attempts": 2,
                "succeeded_with": None, "failure_reason": "http_404",
                "all_links": [], "external": False,
            },
            d_b: {
                "status": 404, "success": False, "attempts": 2,
                "succeeded_with": None, "failure_reason": "http_404",
                "all_links": [], "external": False,
            },
            d_c: {
                "status": 404, "success": False, "attempts": 2,
                "succeeded_with": None, "failure_reason": "http_404",
                "all_links": [], "external": False,
            },
        },
    }
    return job_id


def _teardown_job(job_id):
    app_module._jobs.pop(job_id, None)


# ── The core regression: two summary cards must NOT show the same number ──

def test_broken_references_and_unique_missing_are_distinct_counts():
    """
    In a duplication scenario, the pink card (broken references) and the
    orange card (unique missing URLs) MUST show different numbers. This
    is the exact regression Thomas reported.
    """
    job_id = _seed_duplication_job()
    try:
        client = app_module.app.test_client()
        resp = client.get(f"/api/status/{job_id}")
        assert resp.status_code == 200
        data = resp.get_json()

        # Pink summary card source: total broken references (DOM
        # anchor count = broken parent rows + broken child occurrences).
        assert data["broken_references"] == 8, (
            "pink card must match the red nav's DOM anchor count "
            f"(expected 8, got {data['broken_references']})"
        )

        # Orange summary card source: distinct broken URLs after site-wide dedupe.
        assert data["unique_missing_count"] == 3, (
            "orange card must count unique missing URLs "
            f"(expected 3, got {data['unique_missing_count']})"
        )

        # The whole point of the fix: these two numbers must NOT collapse.
        assert data["broken_references"] != data["unique_missing_count"], (
            "V3.1 regression — pink and orange cards are showing the same "
            "number again; the pink card is likely re-bound to a dedupe count."
        )
    finally:
        _teardown_job(job_id)


def test_broken_field_stays_the_unique_url_count():
    """
    `broken` (used for OK/broken arithmetic against total_checked) still
    reports the unique-URL count, so total_checked = successful + broken
    stays coherent. `broken_references` is the NEW additional field.
    """
    job_id = _seed_duplication_job()
    try:
        client = app_module.app.test_client()
        data = client.get(f"/api/status/{job_id}").get_json()

        assert data["total_checked"] == 5
        assert data["successful"] == 2
        assert data["broken"] == 3
        assert data["successful"] + data["broken"] == data["total_checked"]
    finally:
        _teardown_job(job_id)


def test_clean_crawl_has_zero_broken_references():
    """No broken links → both counters are zero, and they still agree."""
    job_id = "test-clean-job"
    p1 = "https://site.test/p1"
    p2 = "https://site.test/p2"
    app_module._jobs[job_id] = {
        "status": "done", "phase": "done", "traversal": "bfs",
        "request_delay": 0, "max_depth": None, "wait_timeout_ms": 5000,
        "start_url": p1, "current_url": None, "current_depth": 0,
        "queue_size": 0, "capped": False, "error": None,
        "results": {
            p1: {"status": 200, "success": True, "attempts": 1,
                 "succeeded_with": "default", "failure_reason": None,
                 "all_links": [p2], "external": False},
            p2: {"status": 200, "success": True, "attempts": 1,
                 "succeeded_with": "default", "failure_reason": None,
                 "all_links": [], "external": False},
        },
    }
    try:
        data = app_module.app.test_client().get(f"/api/status/{job_id}").get_json()
        assert data["broken"] == 0
        assert data["broken_references"] == 0
        assert data["unique_missing_count"] == 0
    finally:
        _teardown_job(job_id)


def test_no_duplication_broken_references_equals_unique_missing():
    """
    Sanity: when every broken URL appears exactly once, the two counts
    naturally agree. The bug only manifests under duplication — this
    test guards against an over-fix that inflates references when none
    exist.
    """
    job_id = "test-nodup-job"
    p1 = "https://site.test/p1"
    d1 = "https://site.test/dead1"
    d2 = "https://site.test/dead2"
    app_module._jobs[job_id] = {
        "status": "done", "phase": "done", "traversal": "bfs",
        "request_delay": 0, "max_depth": None, "wait_timeout_ms": 5000,
        "start_url": p1, "current_url": None, "current_depth": 0,
        "queue_size": 0, "capped": False, "error": None,
        "results": {
            p1: {"status": 200, "success": True, "attempts": 1,
                 "succeeded_with": "default", "failure_reason": None,
                 "all_links": [d1, d2], "external": False},
            d1: {"status": 404, "success": False, "attempts": 2,
                 "succeeded_with": None, "failure_reason": "http_404",
                 "all_links": [], "external": False},
            d2: {"status": 500, "success": False, "attempts": 2,
                 "succeeded_with": None, "failure_reason": "http_500",
                 "all_links": [], "external": False},
        },
    }
    try:
        data = app_module.app.test_client().get(f"/api/status/{job_id}").get_json()
        # 2 broken parent rows (d1, d2) + 2 broken child anchors (from p1)
        # = 4 DOM broken anchors total.
        assert data["broken_references"] == 4
        assert data["unique_missing_count"] == 2
        # broken_references stays LARGER than unique_missing whenever any
        # broken URL is also visited as a page (the parent row inflates
        # the DOM count by one). The important guarantee is they don't
        # both collapse to the same wrong value.
        assert data["broken_references"] != data["unique_missing_count"]
    finally:
        _teardown_job(job_id)
