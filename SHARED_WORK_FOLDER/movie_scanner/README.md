# movie_scanner

Dataset-agnostic Python library for IMDB delta scanning. Downloads IMDB's free daily-refreshed title dumps, identifies newly-seen titles, applies rating and genre filters, and persists results to a local SQLite database.

Zero Flask / Jinja2 / HTTP-server dependencies — safe to import in any Python context, including Homunculus (Herman).

## What it does

1. Downloads `title.basics.tsv.gz` and `title.ratings.tsv.gz` from [datasets.imdbws.com](https://datasets.imdbws.com) using an atomic, resumable downloader (Range-header resume, gzip integrity check, atomic rename).
2. Identifies titles that are *new since the last scan* (delta only — no re-testing of already-seen tconsts).
3. Filters by: genre exclusions → minimum rating → minimum vote count → genre inclusions.
4. Persists matched titles to SQLite and returns a summary dict.

## Minimal example

```python
from movie_scanner import Scanner, ScanConfig

# Use defaults (reads config from the DB, mirrors the Flask UI settings)
sc = Scanner(db_path="/path/to/scanner.db")
summary = sc.scan(on_progress=print)
# -> {'run_id': 42, 'scanned': 1_200_000, 'new_titles': 314, 'matches': 17}

# Ask "any good new movies since Monday?"
new_titles = sc.new_matches_since("2026-07-14")
for t in new_titles:
    print(t["primary_title"], t["rating"])

# Inspect the last run's metadata
last = sc.latest_run()
print(last["status"], last["matched_titles"])
```

## Programmatic config override

Pass a `ScanConfig` to skip reading from the DB entirely — useful for Homunculus or testing:

```python
from movie_scanner import Scanner, ScanConfig

sc = Scanner(
    db_path="/path/to/scanner.db",
    data_dir="/path/to/data/cache",     # optional; defaults to data/ next to db
    config=ScanConfig(
        min_rating=7.5,
        min_votes=500,
        include_genres=["Sci-Fi", "Drama"],
        exclude_genres=["Horror", "Adult"],
        title_types=["movie"],
    ),
)
summary = sc.scan(on_progress=lambda msg: print(msg))
```

## CLI usage

```bash
# From the repo root — uses the default MovieScanner/db/scanner.db
python3 -m movie_scanner

# Explicit DB path
python3 -m movie_scanner /path/to/scanner.db

# Explicit data directory (where .gz files are cached)
python3 -m movie_scanner --data-dir /tmp/imdb_cache
```

## API reference

### `Scanner(db_path, data_dir=None, config=None)`

Main class. Creates the DB and applies the schema idempotently on instantiation.

| Method | Returns | Description |
|--------|---------|-------------|
| `scan(on_progress=None)` | `dict` | Run a full scan cycle. Progress callback receives `str` messages. |
| `new_matches_since(iso_date)` | `list[dict]` | Matches where `matched_at >= iso_date`. Ordered by rating DESC. |
| `latest_run()` | `dict \| None` | Metadata for the most recent scan run. |

### `ScanConfig`

Dataclass with fields: `min_rating` (float, 7.0), `min_votes` (int, 100), `include_genres` (list, []), `exclude_genres` (list, []), `title_types` (list, ["movie","tvMovie","tvSeries"]).

### `KNOWN_GENRES`

List of all genre strings that appear in IMDB's dataset (28 values). Use this to populate UI dropdowns or validate user input.
