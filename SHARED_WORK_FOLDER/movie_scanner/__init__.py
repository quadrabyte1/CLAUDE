"""movie_scanner — dataset-agnostic IMDB delta scanner library.

Import surface
--------------
::

    from movie_scanner import Scanner, ScanConfig, KNOWN_GENRES

    sc = Scanner(db_path="/path/to/scanner.db")
    summary = sc.scan(on_progress=print)
    new_this_week = sc.new_matches_since("2026-07-10")
    last_run = sc.latest_run()

Zero Flask / Jinja2 / HTTP-server dependencies — safe to import in any
Python context, including Homunculus (Herman).
"""

__version__ = "1.0.0"

from .config  import ScanConfig
from .genres  import KNOWN_GENRES
from .omdb    import OMDbClient
from .scanner import Scanner

__all__ = ["Scanner", "ScanConfig", "KNOWN_GENRES", "OMDbClient", "__version__"]
