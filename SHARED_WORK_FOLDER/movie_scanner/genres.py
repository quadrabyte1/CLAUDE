"""genres.py — canonical list of IMDB genre values.

Every genre value that appears in IMDB's title.basics.tsv dataset. If IMDB
ever adds a new genre, add it here; both the Flask UI and any programmatic
consumer (e.g. Homunculus) will pick it up automatically.
"""

KNOWN_GENRES: list[str] = [
    "Action", "Adult", "Adventure", "Animation", "Biography", "Comedy",
    "Crime", "Documentary", "Drama", "Family", "Fantasy", "Film-Noir",
    "Game-Show", "History", "Horror", "Music", "Musical", "Mystery",
    "News", "Reality-TV", "Romance", "Sci-Fi", "Short", "Sport",
    "Talk-Show", "Thriller", "War", "Western",
]
