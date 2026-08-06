"""
Regression tests for V2.8 retry-before-flag policy.

The crawler previously flagged transient failures and bot-detected URLs as
broken, producing false positives Thomas hit in the crawl detail. These
tests lock in the fix by driving `check_with_retry` with deterministic
fake fetchers (no network, no browser).

Run with:
    pytest -q Fable5_LinkCheck/tests/test_retry.py
"""

import os
import sys

# Make Fable5_LinkCheck.app importable regardless of pytest cwd.
_HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.dirname(_HERE))

from app import check_with_retry, _is_bot_detect, BROWSER_UA  # noqa: E402


# ── Test doubles ──────────────────────────────────────────────────────────────

class ScriptedFetch:
    """Callable that returns the next scripted (status, headers, extra) tuple."""
    def __init__(self, outcomes):
        self._outcomes = list(outcomes)
        self.calls = 0

    def __call__(self):
        self.calls += 1
        if not self._outcomes:
            raise AssertionError("ScriptedFetch called more times than scripted")
        result = self._outcomes.pop(0)
        if isinstance(result, Exception):
            raise result
        return result


def _no_sleep(_seconds):
    """Stand-in for time.sleep — keeps tests instant."""
    return None


def _fixed_rnd():
    """Deterministic rnd() → 0.5 puts jitter at zero, keeps tests reproducible."""
    return 0.5


# ── Regression: transient failure → success on retry ─────────────────────────

def test_transient_failure_recovers_on_retry_not_marked_broken():
    """
    A URL that fails on the first request (timeout / connection error) but
    succeeds on retry must NOT be flagged broken. This is the primary
    false-positive class Thomas hit before V2.8.
    """
    default = ScriptedFetch([
        TimeoutError("first hit timed out"),          # attempt 1 — network error
        (200, {}, ["https://example.com/x"]),         # attempt 2 — recovered
    ])
    browser = ScriptedFetch([])  # should never be called

    outcome = check_with_retry(default, browser, sleep=_no_sleep, rnd=_fixed_rnd)

    assert outcome["success"] is True, "recovered URL must NOT be flagged broken"
    assert outcome["attempts"] == 2
    assert outcome["succeeded_with"] == "default"
    assert outcome["status"] == 200
    assert outcome["failure_reason"] is None
    assert default.calls == 2
    assert browser.calls == 0, "escalation must not fire when same-UA retry works"


def test_transient_500_recovers_on_retry_not_marked_broken():
    """A 500 that clears on retry must NOT be flagged broken either."""
    default = ScriptedFetch([
        (500, {}, None),                              # attempt 1 — server error
        (200, {}, []),                                # attempt 2 — recovered
    ])
    browser = ScriptedFetch([])

    outcome = check_with_retry(default, browser, sleep=_no_sleep, rnd=_fixed_rnd)

    assert outcome["success"] is True
    assert outcome["attempts"] == 2
    assert outcome["succeeded_with"] == "default"
    assert browser.calls == 0


# ── Regression: bot-detect → succeeds with browser UA ────────────────────────

def test_bot_detect_403_escalates_to_browser_ua_and_recovers():
    """
    LinkedIn-style 403 twice with the default UA, then 200 with a realistic
    Chrome UA. Must NOT be flagged broken; must record the escalation.
    """
    default = ScriptedFetch([
        (403, {}, None),                              # attempt 1
        (403, {}, None),                              # attempt 2
    ])
    browser = ScriptedFetch([
        (200, {}, []),                                # attempt 3 — UA escalation
    ])

    outcome = check_with_retry(default, browser, sleep=_no_sleep, rnd=_fixed_rnd)

    assert outcome["success"] is True
    assert outcome["attempts"] == 3
    assert outcome["succeeded_with"] == "browser"
    assert outcome["status"] == 200
    assert browser.calls == 1


def test_cloudflare_challenge_503_escalates_to_browser_ua():
    """503 + `cf-mitigated: challenge` header is a bot challenge — escalate."""
    cf_headers = {"cf-mitigated": "challenge", "server": "cloudflare"}
    default = ScriptedFetch([
        (503, cf_headers, None),
        (503, cf_headers, None),
    ])
    browser = ScriptedFetch([(200, {}, [])])

    outcome = check_with_retry(default, browser, sleep=_no_sleep, rnd=_fixed_rnd)

    assert outcome["success"] is True
    assert outcome["succeeded_with"] == "browser"


# ── Regression: real breakage → still flagged ────────────────────────────────

def test_truly_broken_url_flagged_after_all_retries():
    """
    A URL that returns 404 twice (not bot-detect-shaped) must be flagged
    broken WITHOUT the browser-UA escalation firing (404 is a real answer,
    not a bot challenge).
    """
    default = ScriptedFetch([
        (404, {}, None),
        (404, {}, None),
    ])
    browser = ScriptedFetch([])  # must never be called for 404

    outcome = check_with_retry(default, browser, sleep=_no_sleep, rnd=_fixed_rnd)

    assert outcome["success"] is False, "truly-broken URL must still be flagged"
    assert outcome["attempts"] == 2
    assert outcome["succeeded_with"] is None
    assert outcome["status"] == 404
    assert outcome["failure_reason"] == "http_404"
    assert browser.calls == 0, "404 is not bot-detect-shaped — no escalation"


def test_bot_detect_that_fails_even_with_browser_ua_is_flagged():
    """A 403 that stays 403 even under the browser UA is genuinely broken."""
    default = ScriptedFetch([(403, {}, None), (403, {}, None)])
    browser = ScriptedFetch([(403, {}, None)])

    outcome = check_with_retry(default, browser, sleep=_no_sleep, rnd=_fixed_rnd)

    assert outcome["success"] is False
    assert outcome["attempts"] == 3
    assert outcome["succeeded_with"] is None
    assert outcome["status"] == 403
    assert outcome["failure_reason"] == "http_403"


def test_persistent_network_error_flagged_as_network_error():
    """Two consecutive exceptions → broken with a network_error-style reason."""
    default = ScriptedFetch([
        ConnectionError("dns_failure"),
        ConnectionError("dns_failure"),
    ])
    browser = ScriptedFetch([])

    outcome = check_with_retry(default, browser, sleep=_no_sleep, rnd=_fixed_rnd)

    assert outcome["success"] is False
    assert outcome["attempts"] == 2
    assert outcome["succeeded_with"] is None
    assert outcome["status"] is None
    assert outcome["failure_reason"] == "connectionerror"


# ── First-attempt success stays cheap ────────────────────────────────────────

def test_clean_first_hit_no_retry_no_sleep():
    """A 200 on attempt 1 short-circuits — no sleep, no second fetch."""
    slept = []
    default = ScriptedFetch([(200, {}, ["a"])])
    browser = ScriptedFetch([])

    outcome = check_with_retry(
        default, browser,
        sleep=lambda s: slept.append(s), rnd=_fixed_rnd,
    )

    assert outcome["success"] is True
    assert outcome["attempts"] == 1
    assert outcome["succeeded_with"] == "default"
    assert default.calls == 1
    assert browser.calls == 0
    assert slept == [], "clean crawls must not pay any backoff cost"


# ── Bot-detect classifier unit tests ─────────────────────────────────────────

def test_is_bot_detect_flags_classic_codes():
    for code in (403, 406, 451, 999):
        assert _is_bot_detect(code, None) is True, f"{code} should be bot-detect"


def test_is_bot_detect_ignores_normal_errors():
    for code in (404, 500, 502, 504):
        assert _is_bot_detect(code, {}) is False


def test_is_bot_detect_503_only_with_cf_challenge_header():
    assert _is_bot_detect(503, {}) is False
    assert _is_bot_detect(503, {"cf-mitigated": "challenge"}) is True
    # Case-insensitive header keys shouldn't break us.
    assert _is_bot_detect(503, {"CF-Mitigated": "CHALLENGE"}) is True


def test_browser_ua_looks_like_chrome_on_macos():
    """Sanity: a stale UA is worse than none — check the constant is sane."""
    assert "Macintosh" in BROWSER_UA
    assert "Chrome/" in BROWSER_UA
    assert "Safari/" in BROWSER_UA
