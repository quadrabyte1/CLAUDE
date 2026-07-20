"""config.py — ScanConfig dataclass for the movie_scanner library.

ScanConfig holds every tunable parameter that controls what a scan matches.
Pass one to Scanner() to customise behaviour; omit it to use defaults that
mirror the out-of-the-box settings stored in a freshly-initialised DB.
"""

from dataclasses import dataclass, field


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
    title_types : list[str]
        IMDB titleType values to consider. Valid values: "movie", "tvMovie",
        "tvSeries", "short". Default: movie, tvMovie, tvSeries.
    """

    min_rating:     float       = 7.0
    min_votes:      int         = 100
    include_genres: list[str]   = field(default_factory=list)
    exclude_genres: list[str]   = field(default_factory=list)
    title_types:    list[str]   = field(
        default_factory=lambda: ["movie", "tvMovie", "tvSeries"]
    )
