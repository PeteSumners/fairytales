"""Audio preparation and TTS integration for fairytales."""

import re
import subprocess
from pathlib import Path
from typing import Optional, Callable
from dataclasses import dataclass

from .models import Story
from .config import OUTPUT_DIR


@dataclass
class TTSConfig:
    """Configuration for text-to-speech generation."""
    voice: str = "default"
    speed: float = 1.0
    pitch: float = 1.0
    output_format: str = "mp3"


def clean_text_for_tts(text: str) -> str:
    """Clean and normalize text for text-to-speech processing.

    Performs:
    - Removes extra whitespace
    - Expands common abbreviations
    - Normalizes punctuation for natural pauses
    - Removes problematic characters
    - Adds appropriate pauses
    """
    # Normalize whitespace
    text = re.sub(r'\s+', ' ', text)
    text = text.strip()

    # Expand common abbreviations
    abbreviations = {
        r'\bMr\.': 'Mister',
        r'\bMrs\.': 'Missus',
        r'\bMs\.': 'Miss',
        r'\bDr\.': 'Doctor',
        r'\bSt\.': 'Saint',
        r'\bvs\.': 'versus',
        r'\betc\.': 'etcetera',
        r'\be\.g\.': 'for example',
        r'\bi\.e\.': 'that is',
        r"'twas\b": 'it was',
        r"'tis\b": 'it is',
        r"'twill\b": 'it will',
        r"e'er\b": 'ever',
        r"ne'er\b": 'never',
        r"o'er\b": 'over',
    }

    for pattern, replacement in abbreviations.items():
        text = re.sub(pattern, replacement, text, flags=re.IGNORECASE)

    # Handle numbers (spell out small ones for natural speech)
    def replace_number(match):
        num = int(match.group(0))
        if num <= 12:
            words = ['zero', 'one', 'two', 'three', 'four', 'five',
                    'six', 'seven', 'eight', 'nine', 'ten', 'eleven', 'twelve']
            return words[num]
        return match.group(0)

    text = re.sub(r'\b(\d{1,2})\b', replace_number, text)

    # Normalize quotes and dashes
    text = text.replace('"', '"').replace('"', '"')
    text = text.replace(''', "'").replace(''', "'")
    text = text.replace('—', ', ')  # Em dash to pause
    text = text.replace('–', ', ')  # En dash to pause
    text = text.replace('...', '...')  # Normalize ellipsis

    # Add pauses after certain punctuation (for SSML-like behavior)
    # These markers can be processed by TTS engines
    text = re.sub(r'([.!?])\s+', r'\1 <pause> ', text)

    # Remove characters that cause TTS issues
    text = re.sub(r'[*#@^~`|\\<>{}[\]]', '', text)

    # Normalize multiple punctuation
    text = re.sub(r'[.]{2,}', '...', text)
    text = re.sub(r'[!]{2,}', '!', text)
    text = re.sub(r'[?]{2,}', '?', text)

    # Clean up any double spaces created
    text = re.sub(r'\s+', ' ', text)

    return text.strip()


def prepare_story_for_tts(story: Story) -> str:
    """Prepare a complete story for TTS.

    Includes title announcement and cleaned text.
    """
    parts = [
        f"{story.metadata.title}.",
        f"By {story.metadata.author}.",
        "",
        clean_text_for_tts(story.text),
        "",
        "The End."
    ]

    return '\n\n'.join(parts)


def split_into_chunks(text: str, max_chars: int = 5000) -> list[str]:
    """Split text into chunks suitable for TTS processing.

    Splits at sentence boundaries to maintain natural flow.
    """
    # Remove pause markers for chunking
    clean_text = text.replace(' <pause> ', ' ')

    sentences = re.split(r'(?<=[.!?])\s+', clean_text)
    chunks = []
    current_chunk = []
    current_length = 0

    for sentence in sentences:
        sentence_len = len(sentence)
        if current_length + sentence_len > max_chars and current_chunk:
            chunks.append(' '.join(current_chunk))
            current_chunk = [sentence]
            current_length = sentence_len
        else:
            current_chunk.append(sentence)
            current_length += sentence_len + 1

    if current_chunk:
        chunks.append(' '.join(current_chunk))

    return chunks


# Type alias for TTS generation callback
TTSGenerator = Callable[[str, Path, TTSConfig], Optional[Path]]


def generate_audio(
    text: str,
    output_path: Path,
    config: Optional[TTSConfig] = None,
    generator: Optional[TTSGenerator] = None
) -> Optional[Path]:
    """Generate audio from text using TTS.

    This is a stub that can be connected to various TTS backends:
    - Piper (local, fast)
    - Coqui TTS (local, high quality)
    - Cloud services (Google, Amazon, Azure, etc.)

    Args:
        text: The text to convert to speech
        output_path: Where to save the audio file
        config: TTS configuration options
        generator: Optional callback for actual TTS generation

    Returns:
        Path to generated audio, or None if TTS is not configured.
    """
    config = config or TTSConfig()

    if generator is not None:
        return generator(text, output_path, config)

    # Stub behavior
    print(f"[STUB] Would generate audio:")
    print(f"  Text length: {len(text)} characters")
    print(f"  Output: {output_path}")
    print(f"  Voice: {config.voice}")
    print(f"  Speed: {config.speed}")

    return None


def generate_story_audio(
    story: Story,
    output_dir: Optional[Path] = None,
    config: Optional[TTSConfig] = None,
    generator: Optional[TTSGenerator] = None
) -> Optional[Path]:
    """Generate audio for an entire story.

    Args:
        story: The story to convert
        output_dir: Base output directory (default: OUTPUT_DIR)
        config: TTS configuration
        generator: TTS generation callback

    Returns:
        Path to the generated audio file, or None.
    """
    base_dir = output_dir or OUTPUT_DIR
    story_dir = base_dir / story.metadata.origin.value / story.metadata.slug
    story_dir.mkdir(parents=True, exist_ok=True)

    # Prepare text
    tts_text = prepare_story_for_tts(story)
    story.tts_text = tts_text

    # Save TTS-ready text
    tts_text_path = story_dir / "story_tts.txt"
    tts_text_path.write_text(tts_text, encoding="utf-8")

    # Generate audio
    audio_path = story_dir / f"audio.{config.output_format if config else 'mp3'}"
    result = generate_audio(tts_text, audio_path, config, generator)

    if result:
        story.metadata.has_audio = True

    return result


class PiperTTS:
    """Integration with Piper TTS (local, fast text-to-speech)."""

    def __init__(self, piper_path: str = "piper", model_path: Optional[str] = None):
        self.piper_path = piper_path
        self.model_path = model_path

    def is_available(self) -> bool:
        """Check if Piper is installed and accessible."""
        try:
            result = subprocess.run(
                [self.piper_path, "--help"],
                capture_output=True,
                timeout=5
            )
            return result.returncode == 0
        except (subprocess.SubprocessError, FileNotFoundError):
            return False

    def generate(self, text: str, output_path: Path, config: TTSConfig) -> Optional[Path]:
        """Generate audio using Piper."""
        if not self.is_available():
            print("Piper TTS is not available. Install from: https://github.com/rhasspy/piper")
            return None

        cmd = [self.piper_path]

        if self.model_path:
            cmd.extend(["--model", self.model_path])

        cmd.extend(["--output_file", str(output_path)])

        try:
            process = subprocess.Popen(
                cmd,
                stdin=subprocess.PIPE,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE
            )
            stdout, stderr = process.communicate(input=text.encode('utf-8'), timeout=300)

            if process.returncode == 0 and output_path.exists():
                return output_path
            else:
                print(f"Piper error: {stderr.decode()}")
                return None

        except subprocess.SubprocessError as e:
            print(f"Piper subprocess error: {e}")
            return None


class AudioManager:
    """Manages audio generation for stories."""

    def __init__(self, output_dir: Optional[Path] = None):
        self.output_dir = output_dir or OUTPUT_DIR
        self.generator: Optional[TTSGenerator] = None
        self.config = TTSConfig()

    def set_generator(self, generator: TTSGenerator) -> None:
        """Set the TTS generation callback."""
        self.generator = generator

    def use_piper(self, piper_path: str = "piper", model_path: Optional[str] = None) -> bool:
        """Configure to use Piper TTS."""
        piper = PiperTTS(piper_path, model_path)
        if piper.is_available():
            self.generator = piper.generate
            return True
        return False

    def generate_for_story(self, story: Story) -> Optional[Path]:
        """Generate audio for a story."""
        return generate_story_audio(
            story,
            self.output_dir,
            self.config,
            self.generator
        )

    def save_tts_text(self, story: Story) -> Path:
        """Save just the TTS-ready text without generating audio."""
        story_dir = self.output_dir / story.metadata.origin.value / story.metadata.slug
        story_dir.mkdir(parents=True, exist_ok=True)

        tts_text = prepare_story_for_tts(story)
        tts_path = story_dir / "story_tts.txt"
        tts_path.write_text(tts_text, encoding="utf-8")

        return tts_path
