"""Parse fairytale collections and split them into individual stories."""

import re
from typing import Optional
from .models import Story, StoryMetadata, Collection, StoryOrigin, AgeRating
from .config import GutenbergSource, SCARY_KEYWORDS, WORDS_PER_MINUTE


def slugify(text: str, max_length: int = 50) -> str:
    """Convert text to a URL-friendly slug."""
    text = text.lower().strip()
    text = re.sub(r'[^\w\s-]', '', text)
    text = re.sub(r'[-\s]+', '-', text)
    slug = text.strip('-')
    # Truncate to max_length, but try to break at a word boundary
    if len(slug) > max_length:
        slug = slug[:max_length].rsplit('-', 1)[0]
    return slug


def is_valid_story_title(title: str) -> bool:
    """Check if a detected title is likely a real story title."""
    title_lower = title.lower()

    # Skip if it contains chapter markers
    skip_patterns = [
        'chapter', 'contents', 'preface', 'introduction', 'appendix',
        'index', 'note', 'footnote', 'volume', 'part i', 'part ii',
        'editor', 'translator', 'copyright', 'gutenberg'
    ]
    if any(pattern in title_lower for pattern in skip_patterns):
        return False

    # Skip if title is too long (likely a table of contents)
    if len(title) > 80:
        return False

    # Skip if title has too many dashes (likely a list)
    if title.count('-') > 3:
        return False

    return True


def clean_gutenberg_text(text: str) -> str:
    """Remove Project Gutenberg header/footer boilerplate."""
    # Find start of actual content
    start_markers = [
        "*** START OF THE PROJECT GUTENBERG",
        "*** START OF THIS PROJECT GUTENBERG",
        "*END*THE SMALL PRINT",
    ]
    end_markers = [
        "*** END OF THE PROJECT GUTENBERG",
        "*** END OF THIS PROJECT GUTENBERG",
        "End of the Project Gutenberg",
        "End of Project Gutenberg",
    ]

    start_pos = 0
    for marker in start_markers:
        pos = text.find(marker)
        if pos != -1:
            # Find the end of that line
            newline_pos = text.find('\n', pos)
            if newline_pos != -1:
                start_pos = newline_pos + 1
                break

    end_pos = len(text)
    for marker in end_markers:
        pos = text.find(marker)
        if pos != -1:
            end_pos = pos
            break

    return text[start_pos:end_pos].strip()


def detect_story_boundaries(text: str, origin: str) -> list[tuple[str, int, int]]:
    """Detect individual story boundaries in a collection.

    Returns list of (title, start_pos, end_pos) tuples.
    """
    stories = []

    if origin == "grimm":
        # Grimm's tales often have numbered titles or all-caps titles
        pattern = r'\n\s*([A-Z][A-Z\s,\'-]+)\n\s*\n'
        matches = list(re.finditer(pattern, text))

        # Filter to actual story titles
        valid_matches = []
        for m in matches:
            title = m.group(1).strip()
            if len(title) > 3 and is_valid_story_title(title):
                valid_matches.append(m)

        for i, match in enumerate(valid_matches):
            title = match.group(1).strip().title()
            start = match.end()
            end = valid_matches[i + 1].start() if i + 1 < len(valid_matches) else len(text)
            if end - start > 500:  # Min story length
                stories.append((title, start, end))

    elif origin == "andersen":
        # Andersen's tales often have title followed by dashes or centered
        pattern = r'\n\s{10,}([A-Z][A-Za-z\s,\'-]+)\n'
        matches = list(re.finditer(pattern, text))

        for i, match in enumerate(matches):
            title = match.group(1).strip()
            if len(title) > 3 and is_valid_story_title(title):
                start = match.end()
                end = matches[i + 1].start() if i + 1 < len(matches) else len(text)
                if end - start > 500:
                    stories.append((title, start, end))

    elif origin == "lang":
        # Lang's fairy books have clear story titles
        pattern = r'\n\s*([A-Z][A-Z\s,\'-]+)\n\s*\n'
        matches = list(re.finditer(pattern, text))

        for i, match in enumerate(matches):
            title = match.group(1).strip().title()
            if len(title) > 3 and is_valid_story_title(title):
                start = match.end()
                end = matches[i + 1].start() if i + 1 < len(matches) else len(text)
                if end - start > 500:
                    stories.append((title, start, end))

    elif origin == "perrault":
        # Perrault's tales - look for centered titles
        pattern = r'\n\s{5,}([A-Z][A-Za-z\s,\'-]{3,60})\s*\n'
        matches = list(re.finditer(pattern, text))

        for i, match in enumerate(matches):
            title = match.group(1).strip()
            if len(title) > 3 and is_valid_story_title(title):
                start = match.end()
                end = matches[i + 1].start() if i + 1 < len(matches) else len(text)
                if end - start > 500:
                    stories.append((title, start, end))

    else:
        # Generic fallback: look for capitalized titles
        pattern = r'\n\s*([A-Z][A-Za-z\s,\'-]{5,60})\n\s*\n'
        matches = list(re.finditer(pattern, text))

        for i, match in enumerate(matches):
            title = match.group(1).strip()
            if is_valid_story_title(title):
                start = match.end()
                end = matches[i + 1].start() if i + 1 < len(matches) else len(text)
                if end - start > 500:
                    stories.append((title, start, end))

    return stories


def assess_scariness(text: str) -> bool:
    """Check if a story contains potentially scary content."""
    text_lower = text.lower()
    scary_count = sum(1 for keyword in SCARY_KEYWORDS if keyword in text_lower)
    return scary_count >= 2


def estimate_age_rating(text: str, is_scary: bool) -> AgeRating:
    """Estimate appropriate age rating for a story."""
    text_lower = text.lower()

    # Check for mature themes
    mature_keywords = ['murder', 'torture', 'blood', 'death', 'killed']
    mature_count = sum(1 for kw in mature_keywords if kw in text_lower)

    if mature_count >= 3:
        return AgeRating.MATURE
    elif is_scary or mature_count >= 1:
        return AgeRating.OLDER_CHILDREN
    elif len(text.split()) > 3000:
        return AgeRating.CHILDREN
    else:
        return AgeRating.YOUNG_CHILDREN


def parse_collection(
    text: str,
    source: GutenbergSource,
    source_url: str = ""
) -> Collection:
    """Parse a complete fairytale collection into individual stories."""
    # Clean the text
    cleaned_text = clean_gutenberg_text(text)

    # Detect story boundaries
    boundaries = detect_story_boundaries(cleaned_text, source.origin)

    # Create story objects
    stories = []
    origin = StoryOrigin(source.origin) if source.origin in [e.value for e in StoryOrigin] else StoryOrigin.OTHER

    for title, start, end in boundaries:
        story_text = cleaned_text[start:end].strip()

        # Clean up the story text
        story_text = re.sub(r'\n{3,}', '\n\n', story_text)
        story_text = story_text.strip()

        if not story_text or len(story_text) < 100:
            continue

        # Assess content
        is_scary = assess_scariness(story_text)
        age_rating = estimate_age_rating(story_text, is_scary)

        # Calculate stats
        word_count = len(story_text.split())
        reading_time = max(1, word_count // WORDS_PER_MINUTE)

        metadata = StoryMetadata(
            title=title,
            slug=slugify(title),
            origin=origin,
            author=source.author,
            source_url=source_url or f"https://www.gutenberg.org/ebooks/{source.book_id}",
            word_count=word_count,
            reading_time_minutes=reading_time,
            age_rating=age_rating,
            is_scary=is_scary,
        )

        story = Story(metadata=metadata, text=story_text)
        stories.append(story)

    return Collection(
        name=source.title,
        slug=slugify(source.title),
        author=source.author,
        origin=origin,
        source_url=source_url or f"https://www.gutenberg.org/ebooks/{source.book_id}",
        stories=stories
    )


def extract_story_by_title(
    text: str,
    title: str,
    source: GutenbergSource
) -> Optional[Story]:
    """Extract a single story by title from a collection."""
    collection = parse_collection(text, source)

    title_lower = title.lower()
    for story in collection.stories:
        if story.metadata.title.lower() == title_lower:
            return story
        if title_lower in story.metadata.title.lower():
            return story

    return None
