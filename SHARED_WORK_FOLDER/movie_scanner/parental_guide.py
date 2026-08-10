"""parental_guide.py — IMDb parental-guide severity scraper (ISOLATED module).

COMPLIANCE EXCEPTION — approved by Thomas 2026-08-06 for personal use only.
Must be removed before any commercial launch. See
project_moviescanner_commercial_intent memory.

This module is the ONE sanctioned exception to the "never fetch imdb.com/*"
compliance boundary defined at the top of ``omdb.py``. Everything else in
the package must continue to route through licensed sources
(datasets.imdbws.com for dumps, omdbapi.com for enrichment).

Design constraints
------------------
- Isolated: no imports from this module anywhere in ``omdb.py``. All
  touchpoints are grep-able as ``parental_guide``.
- No CLI, no module-level cache — the caller (Scanner) handles caching in
  the ``parental_guide`` DB table.
- Rate-limited: 1 request per 2 s minimum with ±25% jitter. Sleep lives
  in the caller (so tests can monkeypatch it).
- Fail-open: any HTTP/parse failure returns all "unknown" and logs a
  warning; the scanner treats "unknown" as passing by default (this is
  the only permissive default that makes sense when IMDb has no data).

Public API
----------
- ``fetch_parental_guide(tconst, session) -> dict[str, str]``: 5 keys, each
  ``'none' | 'mild' | 'moderate' | 'severe' | 'unknown'``.
- ``parse_parental_guide_html(html) -> dict[str, str]``: pure parser for
  testing (given an HTML string, extract the same 5-key dict).
- ``SEVERITY_RANK``: rank map for comparing severities.
- ``severity_le(a, b) -> bool``: True iff severity a <= b (with ``unknown``
  handled as unranked; see docstring).
- ``CATEGORIES``: ordered tuple of the 5 canonical category keys.
"""

from __future__ import annotations

import logging
import re
from typing import Optional

# BeautifulSoup is a hard requirement of the package (already in
# requirements.txt at the repo root). Import at module load so any
# dependency mismatch surfaces immediately, not on first scrape.
from bs4 import BeautifulSoup  # type: ignore

logger = logging.getLogger(__name__)


# ── Public constants ────────────────────────────────────────────────────────

# Canonical DB / config key order. Matches the Content-severity UI order.
CATEGORIES: tuple[str, ...] = (
    "sex_nudity",
    "violence_gore",
    "profanity",
    "alcohol_drugs",
    "frightening",
)

# Severity levels the scanner recognises. ``unknown`` is what the scraper
# emits when IMDb has no user-submitted rating for a category.
SEVERITY_LEVELS: tuple[str, ...] = ("none", "mild", "moderate", "severe", "unknown")

# Ordered rank used by ``severity_le``. ``unknown`` gets rank 99 so it is
# NEVER <= a real severity (i.e. the ``le`` comparison alone doesn't decide
# whether ``unknown`` passes — the caller must special-case it based on the
# ``exclude_unknown_parental`` config flag).
SEVERITY_RANK: dict[str, int] = {
    "none":     0,
    "mild":     1,
    "moderate": 2,
    "severe":   3,
    "unknown":  99,
}

# Base delay for the caller's rate limiter (seconds between requests).
# The caller is responsible for actually sleeping; this constant is exported
# so the UI/logs can quote the rate.
BASE_DELAY_SEC = 2.0
JITTER_FRAC    = 0.25   # ±25%

# HTTP timeout (seconds).
HTTP_TIMEOUT = 10.0

# Category-header → canonical key map. IMDb has renamed sections a few
# times; support the current label plus a couple of legacy variants so a
# DOM tweak doesn't break the parser overnight.
_HEADER_TO_KEY: dict[str, str] = {
    # Sex & Nudity
    "sex & nudity":              "sex_nudity",
    "sex and nudity":            "sex_nudity",
    # Violence & Gore
    "violence & gore":           "violence_gore",
    "violence and gore":         "violence_gore",
    # Profanity
    "profanity":                 "profanity",
    # Alcohol, Drugs & Smoking
    "alcohol, drugs & smoking":  "alcohol_drugs",
    "alcohol, drugs and smoking":"alcohol_drugs",
    # Frightening & Intense Scenes
    "frightening & intense scenes":  "frightening",
    "frightening and intense scenes":"frightening",
}

# Section ids IMDb currently uses on the parental-guide page. These are a
# secondary lookup path — if the header text has moved but the anchor id
# is still stable, the parser still finds each category.
_SECTION_ID_TO_KEY: dict[str, str] = {
    "advisory-nudity":      "sex_nudity",
    "advisory-violence":    "violence_gore",
    "advisory-profanity":   "profanity",
    "advisory-alcohol":     "alcohol_drugs",
    "advisory-frightening": "frightening",
}

# Any string containing one of these lowercase tokens (as a whole word)
# maps to the corresponding severity. We look at the section body for the
# first hit rather than trying to grab a specific class (IMDb rewrites its
# stylesheet routinely — a text-based signal is much more durable).
_SEVERITY_WORDS: tuple[tuple[str, str], ...] = (
    # Longest first so "severe" wins over "mild severity" garbage.
    ("severe",   "severe"),
    ("moderate", "moderate"),
    ("mild",     "mild"),
    ("none",     "none"),
)

_SEVERITY_WORD_RE = re.compile(
    r"\b(" + "|".join(w for w, _ in _SEVERITY_WORDS) + r")\b",
    re.IGNORECASE,
)


# ── Public helpers ─────────────────────────────────────────────────────────

def _all_unknown() -> dict[str, str]:
    """Return the default 5-key dict with every category set to ``unknown``."""
    return {cat: "unknown" for cat in CATEGORIES}


def severity_le(a: str, b: str) -> bool:
    """Return True iff severity ``a`` is at or below severity ``b``.

    Both arguments are lowercase strings from :data:`SEVERITY_LEVELS`.
    ``unknown`` has rank 99, so ``severity_le('unknown', 'severe') == False``.
    The caller decides whether ``unknown`` passes a filter based on the
    ``exclude_unknown_parental`` config toggle — do not couple that
    business rule into this pure comparison helper.
    """
    if a not in SEVERITY_RANK or b not in SEVERITY_RANK:
        raise ValueError(f"unknown severity: {a!r} / {b!r}")
    return SEVERITY_RANK[a] <= SEVERITY_RANK[b]


# ── HTML parser ─────────────────────────────────────────────────────────────

def parse_parental_guide_html(html: str) -> dict[str, str]:
    """Extract the 5 severity ratings from a parental-guide page's HTML.

    Two lookup strategies are tried, in order:

    1. **Section id anchors** (``advisory-nudity`` etc). Fast and stable
       across IMDb's cosmetic re-skins; only breaks if IMDb renames the
       anchor ids themselves.
    2. **Header text** (``<h3>Sex & Nudity</h3>``, etc). Fallback for
       when the anchor ids change but the human-readable headings persist.

    Once a category's block is located, the first ``none|mild|moderate|
    severe`` word inside that block wins. If no severity word is found or
    the block itself is missing, the category is set to ``unknown``.

    The parser is intentionally forgiving — it returns partial results
    when only some categories can be found, so a DOM tweak that hides
    one category does not zero out the whole scrape.
    """
    result = _all_unknown()

    if not html or not html.strip():
        return result

    soup = BeautifulSoup(html, "html.parser")

    # ── Strategy 1: <section id="advisory-…"> ──────────────────────────────
    found_via_id: set[str] = set()
    for anchor_id, key in _SECTION_ID_TO_KEY.items():
        section = soup.find(id=anchor_id)
        if section is None:
            continue
        sev = _first_severity_in(section)
        if sev is not None:
            result[key] = sev
            found_via_id.add(key)

    # ── Strategy 2: header text ────────────────────────────────────────────
    # Only fill in the categories the anchor pass missed.
    missing = [k for k in CATEGORIES if k not in found_via_id]
    if missing:
        for header in soup.find_all(re.compile(r"^h[1-6]$")):
            header_text = (header.get_text(strip=True) or "").lower()
            key = _HEADER_TO_KEY.get(header_text)
            if key is None or key not in missing:
                continue
            # Look at everything from the header until the next same-level heading.
            block = _collect_until_next_heading(header)
            sev = _first_severity_in(block)
            if sev is not None:
                result[key] = sev

    return result


def _first_severity_in(node) -> Optional[str]:
    """Return the first severity word (none/mild/moderate/severe) inside
    ``node``'s combined text content, lowercased. Returns None on no match.

    ``node`` may be a Tag OR a list of BeautifulSoup elements (as returned
    by :func:`_collect_until_next_heading`).
    """
    if node is None:
        return None
    if isinstance(node, list):
        text = " ".join(getattr(n, "get_text", lambda **_: str(n))(separator=" ", strip=True)
                        for n in node)
    else:
        text = node.get_text(separator=" ", strip=True)
    if not text:
        return None
    m = _SEVERITY_WORD_RE.search(text)
    if not m:
        return None
    return m.group(1).lower()


def _collect_until_next_heading(header) -> list:
    """Collect sibling nodes after *header* until the next heading of the
    same-or-higher level. Returns them as a plain Python list so the
    caller can pass it into :func:`_first_severity_in`.
    """
    level = int(header.name[1])
    out = []
    for sib in header.next_siblings:
        name = getattr(sib, "name", None) or ""
        if name.startswith("h") and len(name) == 2 and name[1].isdigit():
            if int(name[1]) <= level:
                break
        out.append(sib)
    return out


# ── Live fetch ──────────────────────────────────────────────────────────────

# Deliberately a module-level constant so tests can patch it if IMDb
# rejects the exact string. Version-locked to the app version so a future
# support ping from IMDb can trace it.
USER_AGENT = "MovieScanner/3.12 (personal use)"


def fetch_parental_guide(tconst: str, session) -> dict[str, str]:
    """Fetch and parse the parental-guide page for *tconst*.

    Parameters
    ----------
    tconst:
        IMDb title id, e.g. ``"tt0111161"``.
    session:
        A ``requests.Session`` instance owned by the caller. The session
        is used for a single GET with :data:`USER_AGENT`, a 10 s timeout,
        and no retries. Rate limiting is the caller's responsibility.

    Returns
    -------
    dict[str, str]
        Keys: :data:`CATEGORIES`. Values: one of :data:`SEVERITY_LEVELS`.
        Any failure (HTTP error, WAF challenge, empty body, parse failure)
        yields a dict where every value is ``"unknown"`` and emits a log
        warning. The caller should still cache this row so we don't
        retry a broken tconst on every scan.
    """
    url = f"https://www.imdb.com/title/{tconst}/parentalguide/"
    try:
        resp = session.get(
            url,
            headers={"User-Agent": USER_AGENT},
            timeout=HTTP_TIMEOUT,
        )
    except Exception as exc:  # noqa: BLE001 — we deliberately swallow every fetch error
        logger.warning("parental_guide fetch failed for %s: %s", tconst, exc)
        return _all_unknown()

    if resp.status_code != 200:
        logger.warning(
            "parental_guide non-200 for %s: HTTP %s (len %d)",
            tconst, resp.status_code, len(resp.content or b""),
        )
        return _all_unknown()

    try:
        return parse_parental_guide_html(resp.text)
    except Exception as exc:  # noqa: BLE001 — parse robustness > loud failure
        logger.warning("parental_guide parse failed for %s: %s", tconst, exc)
        return _all_unknown()
