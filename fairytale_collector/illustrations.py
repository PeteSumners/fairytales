"""Illustration handling and AI generation stubs for fairytales."""

import re
import shutil
from pathlib import Path
from typing import Optional, Callable
from dataclasses import dataclass

from .models import Story, Illustration
from .config import OUTPUT_DIR, CACHE_DIR


@dataclass
class IllustrationStyle:
    """Defines a visual style for AI-generated illustrations."""
    name: str
    prompt_prefix: str
    prompt_suffix: str

    def format_prompt(self, scene_description: str) -> str:
        return f"{self.prompt_prefix} {scene_description} {self.prompt_suffix}"


# Pre-defined illustration styles
STYLES = {
    "classic": IllustrationStyle(
        name="classic",
        prompt_prefix="A classic fairytale illustration in the style of Arthur Rackham,",
        prompt_suffix="detailed line art with watercolor, vintage storybook aesthetic"
    ),
    "watercolor": IllustrationStyle(
        name="watercolor",
        prompt_prefix="A soft watercolor illustration,",
        prompt_suffix="dreamy and ethereal, children's book style"
    ),
    "woodcut": IllustrationStyle(
        name="woodcut",
        prompt_prefix="A medieval woodcut style illustration,",
        prompt_suffix="black and white, bold lines, folk art aesthetic"
    ),
    "modern": IllustrationStyle(
        name="modern",
        prompt_prefix="A modern digital illustration,",
        prompt_suffix="vibrant colors, whimsical character design"
    ),
    "silhouette": IllustrationStyle(
        name="silhouette",
        prompt_prefix="A paper-cut silhouette illustration,",
        prompt_suffix="dramatic shadows, fairy tale aesthetic"
    ),
}


def extract_scenes(story: Story, max_scenes: int = 5) -> list[str]:
    """Extract key scenes from a story for illustration.

    Uses simple heuristics to identify potential illustration points:
    - Opening scene
    - Major action moments
    - Climax
    - Resolution
    """
    text = story.text
    paragraphs = [p.strip() for p in text.split('\n\n') if p.strip()]

    if not paragraphs:
        return []

    scenes = []

    # Opening scene
    if paragraphs:
        scenes.append(f"Opening scene: {paragraphs[0][:200]}...")

    # Look for action keywords
    action_keywords = [
        'suddenly', 'then', 'at once', 'immediately',
        'transformed', 'appeared', 'vanished', 'discovered',
        'cried out', 'exclaimed', 'shouted'
    ]

    action_paragraphs = []
    for i, para in enumerate(paragraphs[1:-1], start=1):
        para_lower = para.lower()
        if any(keyword in para_lower for keyword in action_keywords):
            action_paragraphs.append((i, para))

    # Take top action scenes (by position distribution)
    if action_paragraphs:
        step = max(1, len(action_paragraphs) // (max_scenes - 2))
        for i in range(0, len(action_paragraphs), step):
            if len(scenes) >= max_scenes - 1:
                break
            _, para = action_paragraphs[i]
            scenes.append(f"Scene: {para[:200]}...")

    # Closing scene
    if len(paragraphs) > 1:
        scenes.append(f"Closing scene: {paragraphs[-1][:200]}...")

    return scenes[:max_scenes]


def generate_illustration_prompt(
    story: Story,
    scene_description: str,
    style: str = "classic"
) -> str:
    """Generate a prompt for AI image generation.

    Args:
        story: The story being illustrated
        scene_description: Description of the specific scene
        style: One of the predefined styles (classic, watercolor, etc.)

    Returns:
        A formatted prompt string for image generation
    """
    style_obj = STYLES.get(style, STYLES["classic"])

    # Extract key elements from the scene
    prompt_parts = [
        style_obj.prompt_prefix,
        f"from the fairytale '{story.metadata.title}',",
        scene_description,
        style_obj.prompt_suffix
    ]

    return ' '.join(prompt_parts)


# Type alias for image generation callback
ImageGenerator = Callable[[str, Path], Optional[Path]]


def generate_illustration(
    story_summary: str,
    style: str = "classic",
    output_path: Optional[Path] = None,
    generator: Optional[ImageGenerator] = None
) -> Optional[Path]:
    """Generate an illustration for a story scene.

    This is a stub function that can be connected to various AI image
    generation backends (DALL-E, Stable Diffusion, Midjourney, etc.)

    Args:
        story_summary: A summary or scene description to illustrate
        style: The illustration style to use
        output_path: Where to save the generated image
        generator: Optional callback function that performs actual generation.
                  Should accept (prompt, output_path) and return the path
                  to the generated image or None on failure.

    Returns:
        Path to the generated image, or None if generation is not configured.
    """
    style_obj = STYLES.get(style, STYLES["classic"])
    prompt = style_obj.format_prompt(story_summary)

    if generator is not None:
        # Use provided generator
        return generator(prompt, output_path)

    # Default stub behavior - just return None and log what would happen
    print(f"[STUB] Would generate illustration with prompt:")
    print(f"  {prompt}")
    print(f"  Output: {output_path}")

    return None


def link_existing_illustration(
    source_path: Path,
    story: Story,
    position: str = "cover",
    description: str = "",
    output_dir: Optional[Path] = None
) -> Illustration:
    """Link an existing illustration to a story.

    Copies the image to the story's illustration directory and
    creates an Illustration metadata object.
    """
    base_dir = output_dir or OUTPUT_DIR
    story_dir = base_dir / story.metadata.origin.value / story.metadata.slug
    illust_dir = story_dir / "illustrations"
    illust_dir.mkdir(parents=True, exist_ok=True)

    # Copy image
    dest_path = illust_dir / f"{position}{source_path.suffix}"
    shutil.copy2(source_path, dest_path)

    illustration = Illustration(
        filename=dest_path.name,
        description=description or f"Illustration for {story.metadata.title}",
        source=str(source_path),
        position=position,
        alt_text=description
    )

    # Add to story metadata
    story.metadata.illustrations.append(illustration)

    return illustration


def find_gutenberg_illustrations(
    book_id: int,
    story_title: str
) -> list[dict]:
    """Find illustrations from a cached Gutenberg book that might match a story.

    Returns list of potential matches with their paths and relevance scores.
    """
    images_dir = CACHE_DIR / f"images_{book_id}"
    if not images_dir.exists():
        return []

    matches = []
    title_words = set(story_title.lower().split())

    for img_path in images_dir.glob("*"):
        if img_path.suffix.lower() not in ['.jpg', '.jpeg', '.png', '.gif']:
            continue

        # Score based on filename similarity to title
        filename_lower = img_path.stem.lower()
        common_words = title_words & set(filename_lower.replace('-', ' ').replace('_', ' ').split())
        score = len(common_words)

        matches.append({
            "path": img_path,
            "filename": img_path.name,
            "score": score
        })

    # Sort by score descending
    matches.sort(key=lambda x: x["score"], reverse=True)

    return matches


class IllustrationManager:
    """Manages illustrations for a collection of stories."""

    def __init__(self, output_dir: Optional[Path] = None):
        self.output_dir = output_dir or OUTPUT_DIR
        self.generator: Optional[ImageGenerator] = None

    def set_generator(self, generator: ImageGenerator) -> None:
        """Set the AI image generation callback."""
        self.generator = generator

    def illustrate_story(
        self,
        story: Story,
        style: str = "classic",
        max_illustrations: int = 3
    ) -> list[Illustration]:
        """Generate illustrations for a story.

        Returns list of created Illustration objects.
        """
        scenes = extract_scenes(story, max_illustrations)
        illustrations = []

        for i, scene in enumerate(scenes):
            position = "cover" if i == 0 else f"scene-{i}"

            story_dir = self.output_dir / story.metadata.origin.value / story.metadata.slug
            illust_dir = story_dir / "illustrations"
            illust_dir.mkdir(parents=True, exist_ok=True)

            output_path = illust_dir / f"{position}.png"
            prompt = generate_illustration_prompt(story, scene, style)

            result_path = generate_illustration(
                scene,
                style=style,
                output_path=output_path,
                generator=self.generator
            )

            if result_path and result_path.exists():
                illustration = Illustration(
                    filename=result_path.name,
                    description=scene[:100],
                    source="ai_generated",
                    position=position,
                    alt_text=f"AI-generated illustration: {scene[:50]}..."
                )
                story.metadata.illustrations.append(illustration)
                illustrations.append(illustration)

        return illustrations
