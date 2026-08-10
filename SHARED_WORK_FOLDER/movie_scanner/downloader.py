"""downloader.py — atomic, resumable IMDB dataset downloader.

Public surface:
  fetch_dumps(data_dir, on_progress) -> tuple[str, str]
      Download (or reuse cached) basics + ratings gzip dumps into *data_dir*.
      Returns (basics_path, ratings_path).

No Flask/HTTP-server dependencies — pure stdlib.

Compliance note
---------------
This module fetches only IMDb's official published dataset dumps at
``datasets.imdbws.com`` (personal & non-commercial use per IMDb's terms).
It MUST NEVER scrape ``imdb.com/*`` HTML pages — that's an explicit TOS
violation. Per-title enrichment goes through the licensed OMDb API in
``omdb.py``.

V3.9 — Conditional fetches
--------------------------
Each downloaded dump gets a sidecar ``<file>.last_modified`` recording the
server's ``Last-Modified`` header. On subsequent runs we send
``If-Modified-Since: <that-value>``; a ``304 Not Modified`` response means
we reuse the cached file with no bytes transferred — polite to IMDb's CDN
and immune to mid-transfer stalls.
"""

import gzip as _gzip
import os
import random
import time
import urllib.error
import urllib.request
from typing import Callable

DATASET_BASE = "https://datasets.imdbws.com"
BASICS_URL   = f"{DATASET_BASE}/title.basics.tsv.gz"
RATINGS_URL  = f"{DATASET_BASE}/title.ratings.tsv.gz"
EPISODES_URL = f"{DATASET_BASE}/title.episode.tsv.gz"


def _sidecar_path(dest: str) -> str:
    """Return the sidecar path that stores the server's Last-Modified header for *dest*."""
    return dest + ".last_modified"


def _read_last_modified(dest: str) -> str | None:
    """Return the stored Last-Modified value for *dest*, or None if absent."""
    sidecar = _sidecar_path(dest)
    if not os.path.exists(sidecar):
        return None
    try:
        with open(sidecar, "r", encoding="utf-8") as f:
            val = f.read().strip()
        return val or None
    except OSError:
        return None


def _write_last_modified(dest: str, value: str) -> None:
    """Store the server's Last-Modified header alongside *dest*.

    Written atomically via a ``.tmp`` + ``os.replace`` so a mid-write crash
    can never leave a partially-written sidecar.
    """
    sidecar = _sidecar_path(dest)
    tmp = sidecar + ".tmp"
    try:
        with open(tmp, "w", encoding="utf-8") as f:
            f.write(value)
        os.replace(tmp, sidecar)
    except OSError:
        # Best-effort — a failed sidecar write just means we skip the
        # conditional fetch next time; not fatal.
        if os.path.exists(tmp):
            try:
                os.remove(tmp)
            except OSError:
                pass


def _check_not_modified(
    url: str,
    dest: str,
    on_progress: Callable[[str], None],
) -> bool:
    """Issue a HEAD-style conditional probe. Return True if server says 304.

    Uses a real GET with ``If-Modified-Since`` (rather than HEAD) because
    IMDb's CDN answers 304 more reliably on GET+IMS than on HEAD. We never
    read the response body — Python closes the connection when we exit the
    ``with`` block, so 304 truly costs zero payload bytes.

    Returns False (and lets the caller fall through to a normal download) if:
      * we don't have a stored Last-Modified yet, or
      * the cached destination file is missing (nothing to reuse), or
      * the server returns 200 (the file HAS changed), or
      * any network/parse error occurs.
    """
    if not os.path.exists(dest):
        return False
    ims = _read_last_modified(dest)
    if not ims:
        return False

    name = os.path.basename(dest)
    headers = {
        "User-Agent": "MovieScanner/1.0",
        "If-Modified-Since": ims,
    }
    req = urllib.request.Request(url, headers=headers)
    try:
        with urllib.request.urlopen(req, timeout=30) as r:
            # 200 means server has a newer file — fall through to normal download.
            if r.status == 200:
                return False
            # Any other 2xx we didn't ask for → treat as changed, be safe.
            return False
    except urllib.error.HTTPError as exc:
        if exc.code == 304:
            on_progress(f"{name} — unchanged since {ims}, skipping download")
            return True
        # Other HTTP errors (403, 429, 5xx) — let the normal download path
        # handle them with its retry/backoff logic.
        return False
    except OSError:
        # Network hiccup during the probe — fall through to normal download.
        return False


def _download(url: str, dest: str, on_progress: Callable[[str], None]) -> None:
    """Atomically stream a URL to a local file with HTTP Range-based resume.

    Writes to ``dest.part`` first and renames to ``dest`` only on successful
    completion — so an interrupted download (Werkzeug reload mid-scan,
    SIGKILL, network drop, disk full) never leaves a truncated file at the
    final path.  Also verifies the byte count against the server's
    Content-Length header when available; a size mismatch triggers a resume
    attempt using the Range header before giving up.

    Resume + backoff logic (V3.8 hardening — IMDB CDN stalls regularly on
    residential connections partway through the 800 MB basics dump)
    ------------------------------------------------------------------------
    - If ``.part`` already exists from a prior run, start from that offset.
    - On a short read, re-issue with ``Range: bytes=<got>-`` and append.
    - If the server responds 200 (no Range support) instead of 206, fall back
      to a full restart from byte 0.
    - Two independent counters:
        * ``retry_count``  — total re-attempts, any reason, capped at
          ``_MAX_RETRIES`` = 12 (~15 min total wall-clock at max backoff).
        * ``stall_count``  — CONSECUTIVE zero-byte re-attempts (server keeps
          closing before delivering any bytes past ``got``). Capped at
          ``_MAX_STALL`` = 8; resets to 0 as soon as ANY byte lands.
    - Exponential backoff with jitter: 2, 4, 8, 16, 32, 60, 60, 60 s
      (capped at ``_BACKOFF_CAP`` = 60 s, ± up to 25% jitter).
    - A ``socket.timeout`` mid-transfer no longer counts as a stall — only
      truly-zero-progress re-attempts do.

    A gzip integrity spot-check is performed before the atomic rename — cheap
    but catches CDN-mangled files that a byte-count check would miss.
    """
    os.makedirs(os.path.dirname(dest), exist_ok=True)
    part = dest + ".part"
    name = os.path.basename(dest)

    # V3.9 — Conditional fetch: if we have a cached file and a stored
    # Last-Modified header, ask the server whether anything has changed.
    # A 304 means we're already up to date; skip the download entirely.
    if _check_not_modified(url, dest, on_progress):
        return

    _MAX_STALL    = 8      # consecutive zero-progress attempts before we give up
    _MAX_RETRIES  = 12     # total re-attempts across all failure modes
    _BACKOFF_BASE = 2      # seconds; doubles each attempt
    _BACKOFF_CAP  = 60     # seconds; cap the exponential growth

    total          = 0
    stall_count    = 0     # CONSECUTIVE zero-progress attempts (resets on forward motion)
    retry_count    = 0     # TOTAL attempts across all failure modes
    prev_got       = -1
    last_modified  = None  # server's Last-Modified header, captured on success

    while True:
        got = os.path.getsize(part) if os.path.exists(part) else 0

        # Stall detection: only counts when a fresh attempt makes ZERO forward
        # progress. Any bytes at all → resets to 0.  This is the distinction
        # from the V3.7 logic, which incremented on every outer-loop iteration
        # regardless of what happened during the attempt — so a genuinely-
        # progressing download that hit 5 partial reads would still trip.
        if got == prev_got and prev_got >= 0:
            stall_count += 1
        elif got > prev_got:
            stall_count = 0
        prev_got = got

        if stall_count >= _MAX_STALL:
            if os.path.exists(part):
                os.remove(part)
            raise IOError(
                f"download stalled for {name}: no forward progress after "
                f"{_MAX_STALL} consecutive attempts (last position {got} bytes). "
                "Wait a few minutes and hit 'Run scan now' again — IMDB's CDN "
                "throttles residential IPs sporadically."
            )

        if retry_count >= _MAX_RETRIES:
            if os.path.exists(part):
                os.remove(part)
            raise IOError(
                f"download for {name} exhausted {_MAX_RETRIES} retries "
                f"(last position {got} bytes). Try again in a few minutes."
            )

        if got > 0 or retry_count > 0:
            backoff_raw = _BACKOFF_BASE * (2 ** max(retry_count - 1, 0))
            backoff = min(backoff_raw, _BACKOFF_CAP)
            # Jitter: ±25% to avoid synchronised retries hammering the CDN.
            backoff = backoff * (0.75 + 0.5 * random.random())
            on_progress(
                f"resuming {name} from "
                f"{got // (1 << 20)}/{total // (1 << 20) if total else '?'} MiB"
                f" (attempt {retry_count + 1}/{_MAX_RETRIES}, "
                f"stall {stall_count}/{_MAX_STALL}) — waiting {backoff:.1f}s…"
            )
            time.sleep(backoff)

        retry_count += 1

        headers: dict = {"User-Agent": "MovieScanner/1.0"}
        if got > 0:
            headers["Range"] = f"bytes={got}-"

        req = urllib.request.Request(url, headers=headers)

        try:
            with urllib.request.urlopen(req, timeout=120) as r:
                status = r.status

                if got > 0 and status == 200:
                    on_progress(
                        f"{name}: server returned 200 (no Range support) — "
                        "restarting from byte 0"
                    )
                    if os.path.exists(part):
                        os.remove(part)
                    got = 0
                    prev_got = -1

                if total == 0:
                    cl = r.headers.get("content-length")
                    if cl:
                        total = got + int(cl)

                # Capture Last-Modified once per download. On a resume (206)
                # the header may or may not be re-sent; keep the first value
                # we see and don't overwrite with None on later attempts.
                lm = r.headers.get("Last-Modified")
                if lm and not last_modified:
                    last_modified = lm

                open_mode = "ab" if (status == 206) else "wb"
                with open(part, open_mode) as f:
                    while True:
                        chunk = r.read(1 << 16)   # 64 KiB
                        if not chunk:
                            break
                        f.write(chunk)
                        got += len(chunk)
                        if total:
                            on_progress(
                                f"downloading {name}: "
                                f"{got // (1 << 20)}/{total // (1 << 20)} MiB"
                            )

        except OSError as exc:
            # Socket timeouts, connection resets, dropped TCP mid-transfer.
            # These do NOT count as a stall unless the retry that follows also
            # makes zero forward progress.
            on_progress(
                f"{name}: {type(exc).__name__} at {got // (1 << 20)} MiB — will retry"
            )
            continue

        got = os.path.getsize(part) if os.path.exists(part) else 0
        if total and got < total:
            continue

        break

    # gzip integrity spot-check before atomic rename
    if dest.endswith(".gz"):
        try:
            with _gzip.open(part, "rb") as gz:
                while gz.read(1 << 20):
                    pass
        except (EOFError, _gzip.BadGzipFile, OSError) as exc:
            # Peek at the first bytes to distinguish a rate-limit/block page
            # (no gzip magic) from a truncated-but-valid gzip stream.
            peek = b""
            try:
                with open(part, "rb") as fh:
                    peek = fh.read(20)
            except OSError:
                pass
            os.remove(part)
            if len(peek) < 2 or peek[:2] != b"\x1f\x8b":
                peek_str = peek.decode("latin-1")
                raise IOError(
                    f"downloaded {name} is not gzip — server returned {peek_str!r}"
                    " (likely IMDB rate-limit or block page). Wait 1-2 minutes and retry."
                )
            raise IOError(f"downloaded {name} failed gzip check: {exc}")

    os.replace(part, dest)   # atomic on POSIX

    # Store the server's Last-Modified so the next run can send
    # If-Modified-Since and reuse the cache if IMDb hasn't refreshed yet.
    # If the server didn't send the header, we simply do a normal GET next
    # time — that's the "no Last-Modified fallback" from the design.
    if last_modified:
        _write_last_modified(dest, last_modified)


def fetch_dumps(
    data_dir: str,
    on_progress: Callable[[str], None],
) -> tuple[str, str, str]:
    """Download today's basics + ratings + episode dumps into *data_dir*.

    Returns
    -------
    tuple[str, str, str]
        ``(basics_path, ratings_path, episodes_path)`` — absolute paths to
        the local .gz files. ``episodes_path`` was added in V3.13 to support
        the per-season year filter (title.episode.tsv.gz is ~35 MB gzipped).
    """
    basics_path   = os.path.join(data_dir, "title.basics.tsv.gz")
    ratings_path  = os.path.join(data_dir, "title.ratings.tsv.gz")
    episodes_path = os.path.join(data_dir, "title.episode.tsv.gz")
    _download(BASICS_URL,   basics_path,   on_progress)
    _download(RATINGS_URL,  ratings_path,  on_progress)
    _download(EPISODES_URL, episodes_path, on_progress)
    return basics_path, ratings_path, episodes_path
