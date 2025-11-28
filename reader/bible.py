"""
Bible integration for the Fairytale Reader.
Parses KJV text and maps to audio/video files.
"""

from pathlib import Path
from typing import List, Dict, Optional
from dataclasses import dataclass
import re


# Book order and metadata
BIBLE_BOOKS = [
    # Old Testament
    ('Genesis', 'gen', 50), ('Exodus', 'exo', 40), ('Leviticus', 'lev', 27),
    ('Numbers', 'num', 36), ('Deuteronomy', 'deu', 34), ('Joshua', 'jos', 24),
    ('Judges', 'jud', 21), ('Ruth', 'rut', 4), ('1 Samuel', '1sa', 31),
    ('2 Samuel', '2sa', 24), ('1 Kings', '1ki', 22), ('2 Kings', '2ki', 25),
    ('1 Chronicles', '1ch', 29), ('2 Chronicles', '2ch', 36), ('Ezra', 'ezr', 10),
    ('Nehemiah', 'neh', 13), ('Esther', 'est', 10), ('Job', 'job', 42),
    ('Psalms', 'psa', 150), ('Proverbs', 'pro', 31), ('Ecclesiastes', 'ecc', 12),
    ('Song of Solomon', 'sol', 8), ('Isaiah', 'isa', 66), ('Jeremiah', 'jer', 52),
    ('Lamentations', 'lam', 5), ('Ezekiel', 'eze', 48), ('Daniel', 'dan', 12),
    ('Hosea', 'hos', 14), ('Joel', 'joe', 3), ('Amos', 'amo', 9),
    ('Obadiah', 'oba', 1), ('Jonah', 'jon', 4), ('Micah', 'mic', 7),
    ('Nahum', 'nah', 3), ('Habakkuk', 'hab', 3), ('Zephaniah', 'zep', 3),
    ('Haggai', 'hag', 2), ('Zechariah', 'zec', 14), ('Malachi', 'mal', 4),
    # New Testament
    ('Matthew', 'mat', 28), ('Mark', 'mar', 16), ('Luke', 'luk', 24),
    ('John', 'joh', 21), ('Acts', 'act', 28), ('Romans', 'rom', 16),
    ('1 Corinthians', '1co', 16), ('2 Corinthians', '2co', 13),
    ('Galatians', 'gal', 6), ('Ephesians', 'eph', 6), ('Philippians', 'phi', 4),
    ('Colossians', 'col', 4), ('1 Thessalonians', '1th', 5), ('2 Thessalonians', '2th', 3),
    ('1 Timothy', '1ti', 6), ('2 Timothy', '2ti', 4), ('Titus', 'tit', 3),
    ('Philemon', 'phm', 1), ('Hebrews', 'heb', 13), ('James', 'jam', 5),
    ('1 Peter', '1pe', 5), ('2 Peter', '2pe', 3), ('1 John', '1jo', 5),
    ('2 John', '2jo', 1), ('3 John', '3jo', 1), ('Jude', 'jud2', 1),
    ('Revelation', 'rev', 22),
]

# Map book names to video file names
VIDEO_NAME_MAP = {
    'genesis': 'genesis', 'exodus': 'exodus', 'leviticus': 'leviticus',
    'numbers': 'numbers', 'deuteronomy': 'deuteronomy', 'joshua': 'joshua',
    'judges': 'judges', 'ruth': 'ruth', '1 samuel': '1_samuel',
    '2 samuel': '2_samuel', '1 kings': '1_kings', '2 kings': '2_kings',
    '1 chronicles': '1_chronicles', '2 chronicles': '2_chronicles',
    'ezra': 'ezra', 'nehemiah': 'nehemiah', 'esther': 'esther',
    'job': 'job', 'psalms': 'psalms', 'proverbs': 'proverbs',
    'ecclesiastes': 'ecclesiastes', 'song of solomon': 'song_of_songs',
    'isaiah': 'isaiah', 'jeremiah': 'jeremiah', 'lamentations': 'lamentations',
    'ezekiel': 'ezekiel', 'daniel': 'daniel', 'hosea': 'hosea',
    'joel': 'joel', 'amos': 'amos', 'obadiah': 'obadiah',
    'jonah': 'jonah', 'micah': 'micah', 'nahum': 'nahum',
    'habakkuk': 'habakkuk', 'zephaniah': 'zephaniah', 'haggai': 'haggai',
    'zechariah': 'zechariah', 'malachi': 'malachi', 'matthew': 'matthew',
    'mark': 'mark', 'luke': 'luke', 'john': 'john', 'acts': 'acts',
    'romans': 'romans', '1 corinthians': '1_corinthians',
    '2 corinthians': '2_corinthians', 'galatians': 'galatians',
    'ephesians': 'ephesians', 'philippians': 'philippians',
    'colossians': 'colossians', '1 thessalonians': '1_thessalonians',
    '2 thessalonians': '2_thessalonians', '1 timothy': '1_timothy',
    '2 timothy': '2_timothy', 'titus': 'titus', 'philemon': 'philemon',
    'hebrews': 'hebrews', 'james': 'james', '1 peter': '1_peter',
    '2 peter': '2_peter', '1 john': '1_john', '2 john': '2_john',
    '3 john': '3_john', 'jude': 'jude', 'revelation': 'revelation',
}


@dataclass
class BibleVerse:
    """A single verse from the Bible."""
    book: str
    chapter: int
    verse: int
    text: str


@dataclass
class BibleChapter:
    """A chapter with all its verses."""
    book: str
    chapter: int
    verses: List[BibleVerse]

    @property
    def text(self) -> str:
        """Get chapter as readable text with verse numbers."""
        lines = []
        for v in self.verses:
            lines.append(f"[{v.verse}] {v.text}")
        return '\n\n'.join(lines)

    @property
    def word_count(self) -> int:
        return sum(len(v.text.split()) for v in self.verses)


class BibleLoader:
    """Load and parse the KJV Bible."""

    def __init__(self, kjv_path: Path, video_dir: Path = None, cache_dir: Path = None):
        self.kjv_path = Path(kjv_path)
        self.video_dir = Path(video_dir) if video_dir else None
        self.cache_dir = Path(cache_dir) if cache_dir else None
        self._books: Dict[str, List[BibleChapter]] = {}
        self._loaded = False

    def _ensure_loaded(self):
        """Lazy load the Bible text."""
        if self._loaded:
            return
        if not self.kjv_path.exists():
            return

        current_book = None
        current_chapter = None
        current_verses = []

        with open(self.kjv_path, 'r', encoding='utf-8') as f:
            for line in f:
                line = line.strip()
                if not line or line.startswith('KJV') or line.startswith('King James'):
                    continue

                # Parse: "Genesis 1:1\tIn the beginning..."
                if '\t' not in line:
                    continue

                ref, text = line.split('\t', 1)
                # Parse reference: "Genesis 1:1" or "1 Samuel 2:3"
                match = re.match(r'^(.+?)\s+(\d+):(\d+)$', ref)
                if not match:
                    continue

                book = match.group(1)
                chapter = int(match.group(2))
                verse_num = int(match.group(3))

                # New chapter?
                if book != current_book or chapter != current_chapter:
                    # Save previous chapter
                    if current_book and current_verses:
                        if current_book not in self._books:
                            self._books[current_book] = []
                        self._books[current_book].append(
                            BibleChapter(current_book, current_chapter, current_verses)
                        )
                    current_book = book
                    current_chapter = chapter
                    current_verses = []

                # Add verse
                current_verses.append(BibleVerse(book, chapter, verse_num, text))

        # Don't forget the last chapter
        if current_book and current_verses:
            if current_book not in self._books:
                self._books[current_book] = []
            self._books[current_book].append(
                BibleChapter(current_book, current_chapter, current_verses)
            )

        self._loaded = True

    def get_books(self) -> List[dict]:
        """Get list of all books with metadata."""
        self._ensure_loaded()
        books = []
        for name, code, expected_chapters in BIBLE_BOOKS:
            if name in self._books:
                chapters = self._books[name]
                total_verses = sum(len(ch.verses) for ch in chapters)
                books.append({
                    'name': name,
                    'slug': code,
                    'chapters': len(chapters),
                    'verses': total_verses,
                    'has_video': self._has_video(name),
                })
        return books

    def get_chapters(self, book_name: str) -> List[dict]:
        """Get list of chapters in a book."""
        self._ensure_loaded()
        if book_name not in self._books:
            return []

        chapters = []
        for ch in self._books[book_name]:
            chapters.append({
                'book': book_name,
                'chapter': ch.chapter,
                'verses': len(ch.verses),
                'word_count': ch.word_count,
                'reading_time': max(1, ch.word_count // 200),  # ~200 wpm
            })
        return chapters

    def get_chapter_text(self, book_name: str, chapter_num: int) -> Optional[str]:
        """Get the text of a specific chapter."""
        self._ensure_loaded()
        if book_name not in self._books:
            return None

        for ch in self._books[book_name]:
            if ch.chapter == chapter_num:
                return ch.text
        return None

    def get_book_text(self, book_name: str) -> Optional[str]:
        """Get the full text of an entire book (all chapters)."""
        self._ensure_loaded()
        if book_name not in self._books:
            return None

        chapters = self._books[book_name]
        parts = []
        for ch in chapters:
            # Add chapter header
            parts.append(f"--- Chapter {ch.chapter} ---\n")
            parts.append(ch.text)
        return '\n\n'.join(parts)

    def _has_video(self, book_name: str) -> bool:
        """Check if a video exists for this book."""
        if not self.video_dir or not self.video_dir.exists():
            return False
        video_name = VIDEO_NAME_MAP.get(book_name.lower())
        if not video_name:
            return False
        video_file = self.video_dir / f"audio_bible_{video_name}.mp4"
        return video_file.exists()

    def get_video_path(self, book_name: str) -> Optional[Path]:
        """Get the video path for a book."""
        if not self.video_dir or not self.video_dir.exists():
            return None
        video_name = VIDEO_NAME_MAP.get(book_name.lower())
        if not video_name:
            return None
        video_file = self.video_dir / f"audio_bible_{video_name}.mp4"
        return video_file if video_file.exists() else None

    def get_audio_path(self, book_name: str) -> Optional[Path]:
        """Get audio path for a book. Prefers MP3 in cache, falls back to MP4."""
        video_name = VIDEO_NAME_MAP.get(book_name.lower())
        if not video_name:
            return None

        # Check for extracted MP3 in cache first
        if self.cache_dir:
            mp3_file = self.cache_dir / "audio" / "bible" / f"audio_bible_{video_name}.mp3"
            if mp3_file.exists():
                return mp3_file

        # Fall back to MP4 video file
        if self.video_dir and self.video_dir.exists():
            mp4_file = self.video_dir / f"audio_bible_{video_name}.mp4"
            if mp4_file.exists():
                return mp4_file

        return None

    def has_audio(self, book_name: str) -> bool:
        """Check if audio exists for this book."""
        return self.get_audio_path(book_name) is not None

    def is_available(self) -> bool:
        """Check if Bible data is available."""
        return self.kjv_path.exists()

    def get_stats(self) -> dict:
        """Get statistics about the Bible."""
        self._ensure_loaded()
        total_books = len(self._books)
        total_chapters = sum(len(chs) for chs in self._books.values())
        total_verses = sum(
            len(ch.verses)
            for chs in self._books.values()
            for ch in chs
        )
        videos = sum(1 for name, _, _ in BIBLE_BOOKS if self._has_video(name))
        return {
            'books': total_books,
            'chapters': total_chapters,
            'verses': total_verses,
            'videos': videos,
        }
