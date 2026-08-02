"""genres.py — tokens exposed as genre toggles in the UI.

Most entries come from IMDb's title.basics genres field, but user-defined
tokens (e.g. language names like "Tamil") can be added freely. Non-IMDb
tokens will simply not match any title unless a corresponding filter is built.
"""

KNOWN_GENRES: list[str] = [
    "Action", "Adult", "Adventure", "Animation", "Biography", "Comedy",
    "Crime", "Documentary", "Drama", "Family", "Fantasy", "Film-Noir",
    "Game-Show", "History", "Horror", "Music", "Musical", "Mystery",
    "News", "Reality-TV", "Romance", "Sci-Fi", "Short", "Sport",
    "Talk-Show", "Tamil", "Thriller", "War", "Western",
]
