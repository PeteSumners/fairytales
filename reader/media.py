"""
Media availability detection for fairytale reader.
Detects audio for each story.
"""

from pathlib import Path
from typing import Optional, List, Dict
from dataclasses import dataclass
from difflib import SequenceMatcher
import re


@dataclass
class MediaAvailability:
    """What media is available for a story."""
    has_audio: bool = False
    audio_file: Optional[Path] = None


# Audio sources by collection
AUDIO_SOURCES = {
    'grimm': [
        'grimms_english_librivox',
        'grimm_fairy_tales_1202_librivox',
    ],
    'andersen': [
        'andersens_fairytales_librivox',
        'fairy_tales_andersen_librivox',
    ],
    'lang': [
        'blue_fairy_book_0707_librivox',
        'blue_fairy_book_1012_librivox',
        'red_fairy_book_0908_librivox',
        'red_fairy_book_librivox',
        'green_fairy_book_1012_librivox',
        'orange_fairy_book_1005_librivox',
        'lilac_fairy_0707_librivox',
        'yellow_fairy_book_librivox',
        'pink_fairy_book_librivox',
    ],
    'perrault': [
        'fairy_tales_charles_perrault_librivox',
    ],
}


def normalize_title(title: str) -> str:
    """Normalize a title for matching."""
    title = title.lower()
    title = re.sub(r'[^\w\s]', '', title)
    title = re.sub(r'\s+', ' ', title).strip()
    title = re.sub(r'^the\s+', '', title)
    return title


def similarity(a: str, b: str) -> float:
    """Calculate similarity between two strings."""
    return SequenceMatcher(None, a, b).ratio()


class MediaManager:
    """Detects and manages available audio for stories."""

    def __init__(self, cache_dir: Path):
        self.cache_dir = cache_dir
        self._audio_cache: Dict[str, List[Path]] = {}
        self._scan_media()

    def _scan_media(self):
        """Scan cache directories for available audio."""
        audio_dir = self.cache_dir / "audio"
        if audio_dir.exists():
            for source_dir in audio_dir.iterdir():
                if source_dir.is_dir():
                    mp3_files = list(source_dir.glob("*.mp3"))
                    # Filter out 64kb versions
                    mp3_files = [f for f in mp3_files if "_64kb" not in f.name]
                    self._audio_cache[source_dir.name] = mp3_files

    def find_audio(self, origin: str, story_title: str) -> Optional[Path]:
        """Find matching audio file for a story."""
        if origin not in AUDIO_SOURCES:
            return None

        normalized_title = normalize_title(story_title)
        best_match = None
        best_score = 0.0

        for source in AUDIO_SOURCES[origin]:
            if source not in self._audio_cache:
                continue

            for mp3_file in self._audio_cache[source]:
                # Extract title from filename
                filename = mp3_file.stem
                parts = filename.split('_')
                if len(parts) >= 3 and parts[1].isdigit():
                    file_title = '_'.join(parts[2:])
                elif len(parts) >= 2:
                    file_title = '_'.join(parts[1:])
                else:
                    file_title = filename

                file_title = file_title.replace('_', ' ')
                normalized_file = normalize_title(file_title)

                score = similarity(normalized_title, normalized_file)
                if normalized_title in normalized_file or normalized_file in normalized_title:
                    score = max(score, 0.7)

                if score > best_score and score > 0.4:
                    best_score = score
                    best_match = mp3_file

        return best_match

    def get_availability(self, origin: str, story_title: str) -> MediaAvailability:
        """Get media availability for a story."""
        audio = self.find_audio(origin, story_title)
        return MediaAvailability(
            has_audio=audio is not None,
            audio_file=audio,
        )

    def get_stats(self) -> Dict[str, int]:
        """Get statistics about available media."""
        total_audio = sum(len(files) for files in self._audio_cache.values())
        return {
            'audio_files': total_audio,
            'audio_sources': len(self._audio_cache),
        }
