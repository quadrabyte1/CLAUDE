"""downloader.py — atomic, resumable IMDB dataset downloader.

Public surface:
  fetch_dumps(data_dir, on_progress) -> tuple[str, str]
      Download (or reuse cached) basics + ratings gzip dumps into *data_dir*.
      Returns (basics_path, ratings_path).

No Flask/HTTP-server dependencies — pure stdlib.
"""

import gzip as _gzip
import os
import time
import urllib.request
from typing import Callable

DATASET_BASE = "https://datasets.imdbws.com"
BASICS_URL   = f"{DATASET_BASE}/title.basics.tsv.gz"
RATINGS_URL  = f"{DATASET_BASE}/title.ratings.tsv.gz"


def _download(url: str, dest: str, on_progress: Callable[[str], None]) -> None:
    """Atomically stream a URL to a local file with HTTP Range-based resume.

    Writes to ``dest.part`` first and renames to ``dest`` only on successful
    completion — so an interrupted download (Werkzeug reload mid-scan,
    SIGKILL, network drop, disk full) never leaves a truncated file at the
    final path.  Also verifies the byte count against the server's
    Content-Length header when available; a size mismatch triggers a resume
    attempt using the Range header before giving up.

    Resume logic
    ------------
    - If ``.part`` already exists from a prior run, start from that offset.
    - On a short read, re-issue with ``Range: bytes=<got>-`` and append.
    - If the server responds 200 (no Range support) instead of 206, fall back
      to a full restart from byte 0.
    - Up to 5 consecutive stall attempts before raising; backoff doubles each
      time (2 s, 4 s, 8 s, 16 s).

    A gzip integrity spot-check is performed before the atomic rename — cheap
    but catches CDN-mangled files that a byte-count check would miss.
    """
    os.makedirs(os.path.dirname(dest), exist_ok=True)
    part = dest + ".part"
    name = os.path.basename(dest)

    _MAX_STALL    = 5
    _BACKOFF_BASE = 2  # seconds; doubles each stall

    total      = 0
    stall_count = 0
    prev_got   = -1

    while True:
        got = os.path.getsize(part) if os.path.exists(part) else 0

        if got == prev_got:
            stall_count += 1
        else:
            stall_count = 0
        prev_got = got

        if stall_count >= _MAX_STALL:
            if os.path.exists(part):
                os.remove(part)
            raise IOError(
                f"download stalled for {name}: no forward progress after "
                f"{_MAX_STALL} consecutive attempts (last position {got} bytes)"
            )

        if got > 0 or stall_count > 0:
            backoff = _BACKOFF_BASE * (2 ** max(stall_count - 1, 0))
            on_progress(
                f"resuming {name} from "
                f"{got // (1 << 20)}/{total // (1 << 20) if total else '?'} MiB"
                f" (attempt {stall_count + 1}/{_MAX_STALL}) — waiting {backoff}s…"
            )
            time.sleep(backoff)

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

        except OSError:
            on_progress(
                f"{name}: connection dropped at {got // (1 << 20)} MiB — will retry"
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


def fetch_dumps(
    data_dir: str,
    on_progress: Callable[[str], None],
) -> tuple[str, str]:
    """Download today's basics + ratings dumps into *data_dir*.

    Returns
    -------
    tuple[str, str]
        ``(basics_path, ratings_path)`` — absolute paths to the local .gz files.
    """
    basics_path  = os.path.join(data_dir, "title.basics.tsv.gz")
    ratings_path = os.path.join(data_dir, "title.ratings.tsv.gz")
    _download(BASICS_URL,  basics_path,  on_progress)
    _download(RATINGS_URL, ratings_path, on_progress)
    return basics_path, ratings_path
