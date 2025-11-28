"""Data models for fairytale storage and metadata."""

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from pathlib import Path
from typing import Optional
import json


class StoryOrigin(Enum):
    GRIMM = "grimm"
    ANDERSEN = "andersen"
    LANG = "lang"
    PERRAULT = "perrault"
    OTHER = "other"


class AgeRating(Enum):
    ALL_AGES = "all_ages"
    YOUNG_CHILDREN = "young_children"  # 3-6
    CHILDREN = "children"  # 6-10
    OLDER_CHILDREN = "older_children"  # 10+
    MATURE = "mature"  # Contains darker themes


@dataclass
class Illustration:
    """Represents an illustration for a story."""
    filename: str
    description: str
    source: str  # URL or "ai_generated"
    position: str  # "cover", "scene-1", etc.
    alt_text: str = ""

    def to_dict(self) -> dict:
        return {
            "filename": self.filename,
            "description": self.description,
            "source": self.source,
            "position": self.position,
            "alt_text": self.alt_text
        }

    @classmethod
    def from_dict(cls, data: dict) -> "Illustration":
        return cls(**data)


@dataclass
class StoryMetadata:
    """Metadata for a single fairytale."""
    title: str
    slug: str
    origin: StoryOrigin
    author: str
    source_url: str
    word_count: int = 0
    reading_time_minutes: int = 0
    themes: list[str] = field(default_factory=list)
    characters: list[str] = field(default_factory=list)
    age_rating: AgeRating = AgeRating.ALL_AGES
    is_scary: bool = False
    illustrations: list[Illustration] = field(default_factory=list)
    has_audio: bool = False
    date_added: str = field(default_factory=lambda: datetime.now().isoformat())
    summary: str = ""

    def to_dict(self) -> dict:
        return {
            "title": self.title,
            "slug": self.slug,
            "origin": self.origin.value,
            "author": self.author,
            "source_url": self.source_url,
            "word_count": self.word_count,
            "reading_time_minutes": self.reading_time_minutes,
            "themes": self.themes,
            "characters": self.characters,
            "age_rating": self.age_rating.value,
            "is_scary": self.is_scary,
            "illustrations": [ill.to_dict() for ill in self.illustrations],
            "has_audio": self.has_audio,
            "date_added": self.date_added,
            "summary": self.summary
        }

    @classmethod
    def from_dict(cls, data: dict) -> "StoryMetadata":
        data = data.copy()
        data["origin"] = StoryOrigin(data["origin"])
        data["age_rating"] = AgeRating(data["age_rating"])
        data["illustrations"] = [Illustration.from_dict(ill) for ill in data.get("illustrations", [])]
        return cls(**data)

    def save(self, path: Path) -> None:
        """Save metadata to a JSON file."""
        with open(path, "w", encoding="utf-8") as f:
            json.dump(self.to_dict(), f, indent=2, ensure_ascii=False)

    @classmethod
    def load(cls, path: Path) -> "StoryMetadata":
        """Load metadata from a JSON file."""
        with open(path, "r", encoding="utf-8") as f:
            return cls.from_dict(json.load(f))


@dataclass
class Story:
    """A complete fairytale with text and metadata."""
    metadata: StoryMetadata
    text: str
    tts_text: str = ""  # Cleaned text suitable for TTS

    def calculate_stats(self) -> None:
        """Calculate word count and reading time."""
        words = self.text.split()
        self.metadata.word_count = len(words)
        # Average reading speed: 200 words per minute
        self.metadata.reading_time_minutes = max(1, len(words) // 200)


@dataclass
class Collection:
    """A collection of stories (e.g., Grimm's Fairy Tales)."""
    name: str
    slug: str
    author: str
    origin: StoryOrigin
    source_url: str
    stories: list[Story] = field(default_factory=list)

    def to_dict(self) -> dict:
        return {
            "name": self.name,
            "slug": self.slug,
            "author": self.author,
            "origin": self.origin.value,
            "source_url": self.source_url,
            "story_count": len(self.stories)
        }
