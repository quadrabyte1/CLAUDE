"""__main__.py — CLI entry point for python3 -m movie_scanner.

Usage
-----
::

    python3 -m movie_scanner                        # uses default DB path
    python3 -m movie_scanner /path/to/scanner.db   # explicit DB path
    python3 -m movie_scanner --data-dir /tmp/data  # explicit data cache dir

The default DB path mirrors where the Flask app expects it:
  ``<repo>/MovieScanner/db/scanner.db``

Progress messages go to stdout so launchd log capture is useful.
"""

import os
import sys
import time

from . import Scanner


def main() -> None:
    # Parse args: first positional = db_path, optional --data-dir
    args = sys.argv[1:]
    data_dir: str | None = None
    db_path:  str | None = None

    i = 0
    while i < len(args):
        if args[i] == "--data-dir" and i + 1 < len(args):
            data_dir = args[i + 1]
            i += 2
        elif not args[i].startswith("-"):
            db_path = args[i]
            i += 1
        else:
            print(f"Unknown argument: {args[i]}", file=sys.stderr)
            sys.exit(1)

    # Default: same location the Flask app uses
    if db_path is None:
        _here = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        db_path = os.path.join(_here, "MovieScanner", "db", "scanner.db")

    def _progress(msg: str) -> None:
        print(f"[{time.strftime('%Y-%m-%d %H:%M:%S')}] {msg}", flush=True)

    _progress(f"scan starting against {db_path}")
    sc = Scanner(db_path=db_path, data_dir=data_dir)
    try:
        summary = sc.scan(on_progress=_progress)
        _progress(
            f"scan complete — run {summary['run_id']}: "
            f"scanned {summary['scanned']:,}, "
            f"new {summary['new_titles']:,}, "
            f"matched {summary['matches']:,}"
        )
    except Exception as exc:
        _progress(f"scan failed: {exc}")
        sys.exit(1)


if __name__ == "__main__":
    main()
