"""
Audio playback for LibriVox audiobooks.
Matches stories to audio files and provides playback controls.
"""

import pygame
import re
from pathlib import Path
from typing import Optional, List
from difflib import SequenceMatcher


# Audio cache locations by collection
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
    # Lowercase, remove punctuation, collapse whitespace
    title = title.lower()
    title = re.sub(r'[^\w\s]', '', title)
    title = re.sub(r'\s+', ' ', title).strip()
    # Remove common prefixes
    title = re.sub(r'^the\s+', '', title)
    return title


def similarity(a: str, b: str) -> float:
    """Calculate similarity between two strings."""
    return SequenceMatcher(None, a, b).ratio()


class AudioPlayer:
    """Manages audiobook playback."""

    def __init__(self, cache_dir: Path):
        self.cache_dir = cache_dir / "audio"
        self.current_file: Optional[Path] = None
        self.is_playing = False
        self.is_paused = False
        self._start_offset = 0.0  # Track where we started from for seeking
        self._pause_pos = 0.0  # Position when paused
        pygame.mixer.music.set_volume(0.8)

    def find_audio_for_story(self, origin: str, story_title: str) -> Optional[Path]:
        """Find matching audio file for a story."""
        if origin not in AUDIO_SOURCES:
            return None

        normalized_title = normalize_title(story_title)

        # Search through audio sources for this origin
        best_match = None
        best_score = 0.0

        for source in AUDIO_SOURCES[origin]:
            source_dir = self.cache_dir / source
            if not source_dir.exists():
                continue

            for mp3_file in source_dir.glob("*.mp3"):
                # Skip 64kb versions (lower quality)
                if "_64kb" in mp3_file.name:
                    continue

                # Extract title from filename
                # Format: prefix_##_title.mp3 or prefix_title.mp3
                filename = mp3_file.stem
                # Remove common prefixes like "grimm_01_"
                parts = filename.split('_')
                if len(parts) >= 3 and parts[1].isdigit():
                    file_title = '_'.join(parts[2:])
                elif len(parts) >= 2:
                    file_title = '_'.join(parts[1:])
                else:
                    file_title = filename

                file_title = file_title.replace('_', ' ')
                normalized_file = normalize_title(file_title)

                # Check similarity
                score = similarity(normalized_title, normalized_file)

                # Also check if one contains the other
                if normalized_title in normalized_file or normalized_file in normalized_title:
                    score = max(score, 0.7)

                if score > best_score and score > 0.4:
                    best_score = score
                    best_match = mp3_file

        return best_match

    def list_available_audio(self, origin: str) -> List[Path]:
        """List all available audio files for an origin."""
        audio_files = []

        if origin not in AUDIO_SOURCES:
            return audio_files

        for source in AUDIO_SOURCES[origin]:
            source_dir = self.cache_dir / source
            if source_dir.exists():
                for mp3_file in source_dir.glob("*.mp3"):
                    if "_64kb" not in mp3_file.name:
                        audio_files.append(mp3_file)

        return sorted(audio_files, key=lambda p: p.name)

    def load(self, audio_file: Path) -> bool:
        """Load an audio file for playback."""
        try:
            pygame.mixer.music.load(str(audio_file))
            self.current_file = audio_file
            self.is_playing = False
            self.is_paused = False
            self._start_offset = 0.0
            self._pause_pos = 0.0
            return True
        except Exception as e:
            print(f"Error loading audio: {e}")
            return False

    def play(self):
        """Start or resume playback."""
        if self.current_file is None:
            return

        if self.is_paused:
            # Resume from paused position
            pygame.mixer.music.play(start=self._pause_pos)
            self._start_offset = self._pause_pos
        else:
            pygame.mixer.music.play(start=self._start_offset)

        self.is_playing = True
        self.is_paused = False

    def pause(self):
        """Pause playback."""
        if self.is_playing:
            # Save current position before pausing
            self._pause_pos = self.get_position()
            pygame.mixer.music.stop()  # Use stop instead of pause for better seek support
            self.is_paused = True
            self.is_playing = False

    def toggle(self):
        """Toggle play/pause."""
        if self.is_playing:
            self.pause()
        else:
            self.play()

    def stop(self):
        """Stop playback."""
        pygame.mixer.music.stop()
        self.is_playing = False
        self.is_paused = False
        self._start_offset = 0.0
        self._pause_pos = 0.0

    def seek(self, delta_seconds: float):
        """Seek by delta from current position."""
        if self.current_file:
            try:
                current = self.get_position()
                new_pos = max(0, current + delta_seconds)
                self._start_offset = new_pos

                if self.is_playing:
                    pygame.mixer.music.play(start=new_pos)
                elif self.is_paused:
                    self._pause_pos = new_pos
            except Exception as e:
                print(f"Seek error: {e}")

    def get_position(self) -> float:
        """Get current playback position in seconds."""
        if self.is_paused:
            return self._pause_pos
        elif self.is_playing:
            # get_pos returns ms since play() was called
            return self._start_offset + (pygame.mixer.music.get_pos() / 1000.0)
        return 0.0

    def set_volume(self, volume: float):
        """Set volume (0.0 to 1.0)."""
        pygame.mixer.music.set_volume(max(0.0, min(1.0, volume)))

    def get_volume(self) -> float:
        """Get current volume."""
        return pygame.mixer.music.get_volume()

    def is_active(self) -> bool:
        """Check if audio is loaded and ready."""
        return self.current_file is not None

    def get_status(self) -> str:
        """Get playback status string."""
        if not self.current_file:
            return "No audio"
        if self.is_playing:
            return "Playing"
        if self.is_paused:
            return "Paused"
        return "Stopped"

    def get_filename(self) -> str:
        """Get current filename (display friendly)."""
        if self.current_file:
            return self.current_file.stem.replace('_', ' ').title()
        return ""
