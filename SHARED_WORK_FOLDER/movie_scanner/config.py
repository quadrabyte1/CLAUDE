"""config.py — ScanConfig dataclass for the movie_scanner library.

ScanConfig holds every tunable parameter that controls what a scan matches.
Pass one to Scanner() to customise behaviour; omit it to use defaults that
mirror the out-of-the-box settings stored in a freshly-initialised DB.
"""

from dataclasses import dataclass, field
from datetime import date


@dataclass
class ScanConfig:
    """Runtime parameters for a MovieScanner scan.

    Attributes
    ----------
    min_rating : float
        Minimum IMDB average rating (0.0–10.0). Titles below this are skipped.
        Default: 7.0
    min_votes : int
        Minimum number of IMDB user votes. Filters out titles with too few
        ratings to be reliable. Default: 100.
    include_genres : list[str]
        Titles must have at least one of these genres to pass the genre filter.
        Case-insensitive. Empty list means the genre filter auto-passes (any
        genre is accepted).
    exclude_genres : list[str]
        A single match against any of these genres skips the title entirely,
        regardless of rating or include_genres. Case-insensitive.
    min_year : int
        Minimum start_year (inclusive). Default: current calendar year.
        Set to 0 to disable the year filter. Titles with unknown year are
        treated as failing the filter when it is enabled.
    title_types : list[str]
        IMDB titleType values to consider. Valid values: "movie", "tvMovie",
        "tvSeries", "short". Default: movie, tvMovie, tvSeries.
    """

    min_rating:       float       = 7.0
    min_votes:        int         = 100
    min_year:         int         = field(default_factory=lambda: date.today().year)
    include_genres:   list[str]   = field(default_factory=list)
    exclude_genres:   list[str]   = field(default_factory=list)
    title_types:      list[str]   = field(
        default_factory=lambda: ["movie", "tvMovie", "tvSeries"]
    )
    exclude_countries: list[str]  = field(default_factory=list)
    """Titles whose OMDb Country matches (case-insensitive, substring OK —
    e.g. 'India' matches 'India, USA') any of these are skipped.
    Empty list means no country filter."""

    # ── Parental-guide severity ceilings (V3.12) ────────────────────────────
    # COMPLIANCE EXCEPTION — these fields drive the imdb.com parentalguide
    # scraper in ``movie_scanner/parental_guide.py``. Personal use only.
    # Default 'severe' means the filter is inactive (all titles pass).
    max_sex_nudity:    str = "severe"
    max_violence_gore: str = "severe"
    max_profanity:     str = "severe"
    max_alcohol_drugs: str = "severe"
    max_frightening:   str = "severe"
    exclude_unknown_parental: bool = False
    """If True, any category with severity ``unknown`` fails the filter
    (title excluded). Default False = ``unknown`` PASSES any ceiling."""

    # ── V3.14 — master switch for the parental-guide phase ──────────────────
    # When False (the default), Scanner skips the parental_guide phase
    # entirely — no scraping, no cache lookups, no ceilings applied. The
    # 5 severity ceilings above are IGNORED. When True, the ceilings are
    # honoured as before. This mirrors the "Apply filters" checkbox next
    # to the Content-severity heading in the web UI. Keeps the default
    # scan fast (no ~2s/title penalty) while letting Thomas opt in.
    apply_parental: bool = False
