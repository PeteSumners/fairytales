"""
High-quality sound effects for e-reader.
Uses real recorded WAV files for realistic book sounds.
Falls back to procedural generation if files unavailable.
"""

import pygame
from pathlib import Path
import array
import math
import random

pygame.mixer.init(frequency=44100, size=-16, channels=2, buffer=512)

# Sound effects directory
SFX_DIR = Path(__file__).parent / "sfx"


def load_wav_sound(filename: str, volume: float = 0.5) -> pygame.mixer.Sound:
    """Load a WAV file as a pygame Sound, with volume adjustment."""
    path = SFX_DIR / filename
    if path.exists():
        sound = pygame.mixer.Sound(str(path))
        sound.set_volume(volume)
        return sound
    return None


# Fallback procedural generators for when WAV files aren't available
def generate_soft_click(frequency=800, duration=0.03, volume=0.1):
    """Generate a soft organic click - like a book spine."""
    sample_rate = 44100
    n_samples = int(sample_rate * duration)
    samples = array.array('h')

    for i in range(n_samples):
        t = i / n_samples
        envelope = (1 - t) ** 3
        tone1 = math.sin(2 * math.pi * frequency * (i / sample_rate))
        tone2 = math.sin(2 * math.pi * (frequency * 1.02) * (i / sample_rate)) * 0.5
        noise = random.uniform(-0.1, 0.1)
        value = int(32767 * volume * (tone1 + tone2 + noise) * envelope / 1.6)
        samples.append(value)
        samples.append(value)

    return pygame.mixer.Sound(buffer=samples)


def generate_ambient_tone(frequency=110, duration=0.15, volume=0.05):
    """Generate a deep ambient tone - like a distant bell."""
    sample_rate = 44100
    n_samples = int(sample_rate * duration)
    samples = array.array('h')

    for i in range(n_samples):
        t = i / n_samples
        if t < 0.2:
            envelope = (t / 0.2) ** 2
        else:
            envelope = ((1 - t) / 0.8) ** 1.5
        fundamental = math.sin(2 * math.pi * frequency * (i / sample_rate))
        harmonic2 = math.sin(2 * math.pi * frequency * 2.02 * (i / sample_rate)) * 0.5
        harmonic3 = math.sin(2 * math.pi * frequency * 3.01 * (i / sample_rate)) * 0.25
        combined = (fundamental + harmonic2 + harmonic3) / 1.75
        value = int(32767 * volume * combined * envelope)
        samples.append(value)
        samples.append(int(value * 0.95))

    return pygame.mixer.Sound(buffer=samples)


class SoundManager:
    """Manages all reader sounds - high-quality realistic style."""

    def __init__(self):
        self.enabled = True
        self._cache = {}
        self._page_turns = []  # (sound, duration_ms) pairs
        self._load_sounds()

    def _load_sounds(self):
        """Pre-load all sound effects."""
        # Page turn variations (for variety) with durations
        page_files = [
            'page_turn_hd.wav',
            'page_turn_hd2.wav',
            'page_turn_hd3.wav',
            'page_turn.wav',
            'page_turn2.wav',
        ]
        for f in page_files:
            sound = load_wav_sound(f, volume=0.4)
            if sound:
                # Get duration in milliseconds
                duration_ms = int(sound.get_length() * 1000)
                self._page_turns.append((sound, duration_ms))

        # Book open/close with durations
        book_open = load_wav_sound('book_open.wav', volume=0.5)
        if book_open:
            self._cache['book_open'] = (book_open, int(book_open.get_length() * 1000))

        book_close = load_wav_sound('book_close.wav', volume=0.5)
        if book_close:
            self._cache['book_close'] = (book_close, int(book_close.get_length() * 1000))

    def play_page_turn(self) -> int:
        """Paper page turn sound - random selection. Returns duration in ms."""
        if not self.enabled:
            return 300  # Default animation duration

        if self._page_turns:
            # Random selection for natural variety
            sound, duration_ms = random.choice(self._page_turns)
            sound.play()
            return duration_ms
        else:
            # Fallback to procedural
            if 'page_fallback' not in self._cache:
                self._cache['page_fallback'] = generate_soft_click(300, 0.08, 0.15)
            self._cache['page_fallback'].play()
            return 300

    def play_select(self):
        """Soft selection confirmation."""
        if not self.enabled:
            return
        if 'select' not in self._cache:
            self._cache['select'] = generate_soft_click(600, 0.05, 0.12)
        self._cache['select'].play()
        if 'select_ambient' not in self._cache:
            self._cache['select_ambient'] = generate_ambient_tone(150, 0.2, 0.03)
        self._cache['select_ambient'].play()

    def play_back(self):
        """Soft back/cancel sound."""
        if not self.enabled:
            return
        if 'back' not in self._cache:
            self._cache['back'] = generate_soft_click(400, 0.04, 0.1)
        self._cache['back'].play()

    def play_menu_move(self):
        """Subtle menu navigation sound."""
        if not self.enabled:
            return
        if 'move' not in self._cache:
            self._cache['move'] = generate_soft_click(500, 0.02, 0.06)
        self._cache['move'].play()

    def play_chapter_start(self):
        """Ambient tone for starting a new chapter/story."""
        if not self.enabled:
            return
        if 'chapter' not in self._cache:
            self._cache['chapter'] = generate_ambient_tone(110, 0.4, 0.08)
        self._cache['chapter'].play()

    def play_book_open(self) -> int:
        """Book opening sound - when entering a story. Returns duration in ms."""
        if not self.enabled:
            return 350

        cached = self._cache.get('book_open')
        if cached:
            sound, duration_ms = cached
            sound.play()
            return duration_ms
        else:
            # Fallback
            if 'book_open_fallback' not in self._cache:
                self._cache['book_open_fallback'] = generate_ambient_tone(80, 0.3, 0.1)
            self._cache['book_open_fallback'].play()
            return 350

    def play_book_close(self) -> int:
        """Book closing sound - when exiting a story. Returns duration in ms."""
        if not self.enabled:
            return 250

        cached = self._cache.get('book_close')
        if cached:
            sound, duration_ms = cached
            sound.play()
            return duration_ms
        else:
            # Fallback
            if 'book_close_fallback' not in self._cache:
                self._cache['book_close_fallback'] = generate_soft_click(200, 0.08, 0.15)
            self._cache['book_close_fallback'].play()
            return 250


sounds = SoundManager()
