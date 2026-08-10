"""test_parental_guide.py — regression tests for the parental-guide filter.

COMPLIANCE EXCEPTION — see movie_scanner/parental_guide.py.

Covers:
1. HTML parser — anchor-id and header-only fixtures both yield the
   expected 5-key severity dict.
2. Missing categories decay to ``unknown`` (not None, not an exception).
3. ``severity_le`` ordering: none < mild < moderate < severe < unknown.
4. Ceiling filter behaviour — a title above the ceiling is dropped;
   a title at or below is kept.
5. Unknown handling — passes by default; fails when
   ``exclude_unknown_parental=True``.
6. Scanner integration — the filter is a no-op when every ceiling is
   ``severe`` (no scraping performed).
"""

from __future__ import annotations

import os

import pytest

from movie_scanner import parental_guide as pg


# ── Fixture helpers ────────────────────────────────────────────────────────

_FIXTURE_DIR = os.path.join(os.path.dirname(__file__), "tests", "fixtures")


def _load(name: str) -> str:
    with open(os.path.join(_FIXTURE_DIR, name), "r", encoding="utf-8") as f:
        return f.read()


# ── 1. Parser tests ────────────────────────────────────────────────────────

def test_parses_full_fixture_via_section_ids():
    """Anchor-id strategy — the canonical layout returns all 5 categories."""
    html = _load("parentalguide_tt0111161.html")
    result = pg.parse_parental_guide_html(html)
    assert result == {
        "sex_nudity":    "mild",
        "violence_gore": "severe",
        "profanity":     "severe",
        "alcohol_drugs": "moderate",
        "frightening":   "moderate",
    }


def test_parses_header_only_fixture():
    """Header-text fallback — anchor ids absent, headings still resolve."""
    html = _load("parentalguide_headers_only.html")
    result = pg.parse_parental_guide_html(html)
    assert result == {
        "sex_nudity":    "none",
        "violence_gore": "moderate",
        "profanity":     "mild",
        "alcohol_drugs": "none",
        "frightening":   "mild",
    }


def test_partial_fixture_defaults_missing_to_unknown():
    """A partial page returns the categories it can find and ``unknown``
    for the rest — no exceptions, no zeroing of the whole result."""
    html = _load("parentalguide_partial.html")
    result = pg.parse_parental_guide_html(html)
    assert result["sex_nudity"] == "moderate"
    assert result["frightening"] == "none"
    for missing_cat in ("violence_gore", "profanity", "alcohol_drugs"):
        assert result[missing_cat] == "unknown", missing_cat


def test_empty_html_returns_all_unknown():
    """Empty/whitespace HTML → all-unknown dict, never raises."""
    for garbage in ("", "   ", "\n\n", "<html></html>"):
        result = pg.parse_parental_guide_html(garbage)
        assert set(result.values()) <= {"unknown"}
        assert set(result.keys()) == set(pg.CATEGORIES)


# ── 2. Severity ordering ───────────────────────────────────────────────────

def test_severity_le_ordering():
    """none < mild < moderate < severe; equal values compare True."""
    assert pg.severity_le("none",     "mild")     is True
    assert pg.severity_le("mild",     "moderate") is True
    assert pg.severity_le("moderate", "severe")   is True
    assert pg.severity_le("severe",   "severe")   is True
    assert pg.severity_le("mild",     "none")     is False
    assert pg.severity_le("severe",   "mild")     is False


def test_severity_le_unknown_never_le_a_real_level():
    """``unknown`` has rank 99, so it is never <= any real severity.
    The ``unknown-passes`` rule is applied by the CALLER, not by this
    helper — this test locks that contract in."""
    for real in ("none", "mild", "moderate", "severe"):
        assert pg.severity_le("unknown", real) is False


def test_severity_le_rejects_bad_input():
    with pytest.raises(ValueError):
        pg.severity_le("kinda-bad", "severe")


# ── 3. Filter-behaviour tests (unit — no scanner needed) ──────────────────

def _passes(pg_row: dict, ceilings: dict, exclude_unknown: bool = False) -> bool:
    """Mirror of the pass logic in Scanner._apply_parental_guide_filter,
    extracted here so we can test the rule table without spinning up a
    full scanner. If either implementation changes, the other must too.
    """
    for cat, ceiling in ceilings.items():
        value = pg_row.get(cat, "unknown")
        if value == "unknown":
            if exclude_unknown:
                return False
            continue
        if not pg.severity_le(value, ceiling):
            return False
    return True


def test_filter_drops_title_over_ceiling():
    row = {"sex_nudity": "none", "violence_gore": "severe",
           "profanity": "none", "alcohol_drugs": "none", "frightening": "none"}
    ceilings = {"sex_nudity": "severe", "violence_gore": "mild",
                "profanity": "severe", "alcohol_drugs": "severe", "frightening": "severe"}
    assert _passes(row, ceilings) is False


def test_filter_keeps_title_within_ceiling():
    row = {"sex_nudity": "none", "violence_gore": "mild",
           "profanity": "none", "alcohol_drugs": "none", "frightening": "none"}
    ceilings = {"sex_nudity": "severe", "violence_gore": "mild",
                "profanity": "severe", "alcohol_drugs": "severe", "frightening": "severe"}
    assert _passes(row, ceilings) is True


def test_filter_keeps_title_when_all_severe():
    """The all-severe default matches the "no filter" case: everything passes."""
    row = {"sex_nudity": "severe", "violence_gore": "severe",
           "profanity": "severe", "alcohol_drugs": "severe", "frightening": "severe"}
    ceilings = dict.fromkeys(row.keys(), "severe")
    assert _passes(row, ceilings) is True


# ── 4. Unknown handling ────────────────────────────────────────────────────

def test_unknown_passes_by_default():
    row = {c: "unknown" for c in pg.CATEGORIES}
    ceilings = {"sex_nudity": "mild", "violence_gore": "mild",
                "profanity": "mild", "alcohol_drugs": "mild", "frightening": "mild"}
    assert _passes(row, ceilings, exclude_unknown=False) is True


def test_unknown_fails_when_exclude_unknown_set():
    row = {c: "unknown" for c in pg.CATEGORIES}
    ceilings = dict.fromkeys(pg.CATEGORIES, "severe")
    assert _passes(row, ceilings, exclude_unknown=True) is False


def test_mixed_known_and_unknown_respects_exclude_toggle():
    row = {"sex_nudity": "none", "violence_gore": "unknown",
           "profanity": "none", "alcohol_drugs": "none", "frightening": "none"}
    ceilings = dict.fromkeys(pg.CATEGORIES, "severe")
    # unknown-passes default: title kept
    assert _passes(row, ceilings, exclude_unknown=False) is True
    # unknown-fails: title dropped because violence_gore is unknown
    assert _passes(row, ceilings, exclude_unknown=True)  is False


# ── 5. Scanner integration: filter is inactive by default ─────────────────

def test_scanner_filter_inactive_performs_no_scraping(tmp_path, monkeypatch):
    """When the Apply-filters master switch is off (V3.14 default), the
    scanner must skip the parental-guide phase entirely — no scrape, no
    sleep, no DB write. This is the contract that keeps un-configured
    scans fast."""
    import sqlite3

    from movie_scanner import Scanner, ScanConfig
    from movie_scanner.schema import apply_schema

    db_path = str(tmp_path / "scanner.db")
    conn = sqlite3.connect(db_path)
    apply_schema(conn)
    conn.close()

    # Any call to fetch_parental_guide inside the filter step must fail
    # the test — the default config should short-circuit before touching
    # the network.
    calls = {"n": 0}

    def _boom(*a, **kw):
        calls["n"] += 1
        raise AssertionError("fetch_parental_guide called with inactive filter")

    monkeypatch.setattr("movie_scanner.scanner.fetch_parental_guide", _boom)

    sc = Scanner(db_path=db_path, config=ScanConfig(min_year=0))

    # Bypass the actual scan loop; call the filter helper directly with a
    # single row so we exercise the short-circuit and NOTHING ELSE.
    fake_row = ("tt0000042", "Fake", 2099, "movie", 8.0, 500, "Drama", "drama", 1)
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    try:
        kept, scraped, dropped = sc._apply_parental_guide_filter(
            conn        = conn,
            match_rows  = [fake_row],
            cfg         = ScanConfig(min_year=0),   # all severe, exclude_unknown False
            phase       = lambda name, msg="": None,
            on_progress = lambda msg: None,
        )
    finally:
        conn.close()

    assert scraped == 0
    assert dropped == 0
    assert kept == [fake_row]
    assert calls["n"] == 0


# ── 6. V3.14 Apply-filters master switch ───────────────────────────────────

def test_apply_filters_off_bypasses_ceilings(tmp_path, monkeypatch):
    """V3.14 — even with strict ceilings, apply_parental=False must skip
    the entire parental-guide phase. Ceilings are ignored when the master
    switch is off; the "Apply filters" checkbox is authoritative."""
    import sqlite3

    from movie_scanner import Scanner, ScanConfig
    from movie_scanner.schema import apply_schema

    db_path = str(tmp_path / "scanner.db")
    conn = sqlite3.connect(db_path)
    apply_schema(conn)
    conn.close()

    def _boom(*a, **kw):
        raise AssertionError("fetch_parental_guide called with apply_parental=False")

    monkeypatch.setattr("movie_scanner.scanner.fetch_parental_guide", _boom)

    sc = Scanner(db_path=db_path, config=ScanConfig(min_year=0))
    fake_row = ("tt0000042", "Fake", 2099, "movie", 8.0, 500, "Drama", "drama", 1)

    # Strict ceilings that WOULD normally scrape, but the master switch is off.
    cfg = ScanConfig(
        min_year=0,
        max_sex_nudity="none", max_violence_gore="none", max_profanity="none",
        max_alcohol_drugs="none", max_frightening="none",
        exclude_unknown_parental=True,
        apply_parental=False,
    )
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    try:
        kept, scraped, dropped = sc._apply_parental_guide_filter(
            conn        = conn,
            match_rows  = [fake_row],
            cfg         = cfg,
            phase       = lambda name, msg="": None,
            on_progress = lambda msg: None,
        )
    finally:
        conn.close()

    assert scraped == 0
    assert dropped == 0
    assert kept == [fake_row], "row must pass untouched when master switch is off"
