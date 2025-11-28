"""Configuration and constants for the fairytale collector."""

from pathlib import Path
from dataclasses import dataclass


# Base paths
BASE_DIR = Path(__file__).parent.parent
OUTPUT_DIR = BASE_DIR / "output"
CACHE_DIR = BASE_DIR / "cache"


@dataclass
class GutenbergSource:
    """A Project Gutenberg book source."""
    book_id: int
    title: str
    author: str
    origin: str  # grimm, andersen, lang, etc.


# Known fairytale collections on Project Gutenberg
GUTENBERG_SOURCES = [
    GutenbergSource(
        book_id=2591,
        title="Grimm's Fairy Tales",
        author="Brothers Grimm",
        origin="grimm"
    ),
    GutenbergSource(
        book_id=1597,
        title="Hans Andersen's Fairy Tales",
        author="Hans Christian Andersen",
        origin="andersen"
    ),
    GutenbergSource(
        book_id=503,
        title="The Blue Fairy Book",
        author="Andrew Lang",
        origin="lang"
    ),
    GutenbergSource(
        book_id=640,
        title="The Red Fairy Book",
        author="Andrew Lang",
        origin="lang"
    ),
    GutenbergSource(
        book_id=30580,
        title="The Green Fairy Book",
        author="Andrew Lang",
        origin="lang"
    ),
    GutenbergSource(
        book_id=7871,
        title="The Yellow Fairy Book",
        author="Andrew Lang",
        origin="lang"
    ),
    GutenbergSource(
        book_id=31536,
        title="The Pink Fairy Book",
        author="Andrew Lang",
        origin="lang"
    ),
    GutenbergSource(
        book_id=699,
        title="The Fairy Tales of Charles Perrault",
        author="Charles Perrault",
        origin="perrault"
    ),
]

# Additional illustrated sources for image harvesting
ILLUSTRATED_SOURCES = [
    # Heavily illustrated Lang Fairy Books
    GutenbergSource(book_id=30862, title="The Orange Fairy Book", author="Andrew Lang", origin="lang"),
    GutenbergSource(book_id=27826, title="The Lilac Fairy Book", author="Andrew Lang", origin="lang"),
    GutenbergSource(book_id=18168, title="The Brown Fairy Book", author="Andrew Lang", origin="lang"),
    GutenbergSource(book_id=2435, title="The Crimson Fairy Book", author="Andrew Lang", origin="lang"),
    GutenbergSource(book_id=5325, title="The Violet Fairy Book", author="Andrew Lang", origin="lang"),
    GutenbergSource(book_id=9478, title="The Grey Fairy Book", author="Andrew Lang", origin="lang"),
    GutenbergSource(book_id=9479, title="The Olive Fairy Book", author="Andrew Lang", origin="lang"),
    # Illustrated Grimm editions
    GutenbergSource(book_id=5314, title="Household Tales Vol 1", author="Brothers Grimm", origin="grimm"),
    GutenbergSource(book_id=5315, title="Household Tales Vol 2", author="Brothers Grimm", origin="grimm"),
    GutenbergSource(book_id=19068, title="Grimm's Fairy Stories", author="Brothers Grimm", origin="grimm"),
    GutenbergSource(book_id=11027, title="Grimm's Fairy Tales (Illustrated)", author="Brothers Grimm", origin="grimm"),
    GutenbergSource(book_id=52521, title="Household Stories (Crane)", author="Brothers Grimm", origin="grimm"),
    # Illustrated Andersen
    GutenbergSource(book_id=27200, title="Andersen's Fairy Tales (Illustrated)", author="Hans Christian Andersen", origin="andersen"),
    GutenbergSource(book_id=32572, title="Fairy Tales of Hans Christian Andersen", author="Hans Christian Andersen", origin="andersen"),
    GutenbergSource(book_id=29021, title="What the Moon Saw (Andersen)", author="Hans Christian Andersen", origin="andersen"),
    # More illustrated fairy tale sources
    GutenbergSource(book_id=22661, title="Edmund Dulac's Fairy-Book", author="Edmund Dulac", origin="lang"),
    GutenbergSource(book_id=17860, title="Fairy Tales Every Child Should Know", author="Hamilton Wright Mabie", origin="lang"),
    GutenbergSource(book_id=14101, title="Old-Fashioned Fairy Tales", author="Juliana Horatia Ewing", origin="lang"),
    GutenbergSource(book_id=20748, title="The Old-Fashioned Fairy Book", author="Mrs. Burton Harrison", origin="lang"),
]


# Gutenberg URL patterns
GUTENBERG_BASE_URL = "https://www.gutenberg.org"
GUTENBERG_TEXT_URL = "https://www.gutenberg.org/cache/epub/{book_id}/pg{book_id}.txt"
GUTENBERG_HTML_URL = "https://www.gutenberg.org/cache/epub/{book_id}/pg{book_id}-images.html"


# Words per minute for reading time calculation
WORDS_PER_MINUTE = 200


# Common themes for categorization
THEMES = [
    "magic",
    "transformation",
    "love",
    "adventure",
    "trickery",
    "royalty",
    "animals",
    "nature",
    "family",
    "courage",
    "wisdom",
    "greed",
    "kindness",
    "punishment",
    "reward",
]


# Keywords that suggest a story might be scary
SCARY_KEYWORDS = [
    "death",
    "killed",
    "murder",
    "blood",
    "witch",
    "devour",
    "eaten",
    "chopped",
    "cut off",
    "burned alive",
    "torture",
]


def ensure_directories() -> None:
    """Create necessary directories if they don't exist."""
    OUTPUT_DIR.mkdir(exist_ok=True)
    CACHE_DIR.mkdir(exist_ok=True)
