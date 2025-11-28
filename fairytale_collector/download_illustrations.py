"""Download and organize illustrations from all Gutenberg fairy tale sources."""

import re
import json
import time
from pathlib import Path
from bs4 import BeautifulSoup
from dataclasses import dataclass
from typing import Optional, List

from .config import (
    GUTENBERG_SOURCES,
    ILLUSTRATED_SOURCES,
    CACHE_DIR,
)
from .downloader import GutenbergDownloader


@dataclass
class ImageMapping:
    """Maps an image to a story."""
    image_path: str
    story_title: str
    origin: str
    book_id: int
    alt_text: str
    context: str  # Text near the image


def normalize_title(title: str) -> str:
    """Normalize story title for matching."""
    title = title.lower()
    title = re.sub(r'[^\w\s]', '', title)
    title = re.sub(r'\s+', ' ', title).strip()
    title = re.sub(r'^the\s+', '', title)
    return title


def is_valid_story_title(text: str) -> bool:
    """Check if text looks like a valid story title."""
    if not text or len(text) < 3 or len(text) > 150:
        return False

    text_lower = text.lower()

    # Skip common garbage patterns
    skip_patterns = [
        'chapter', 'part ', 'contents', 'preface', 'introduction',
        'transcriber', 'project gutenberg', 'ebook', 'e-book',
        'illustration', 'frontispiece', 'title page', 'copyright',
        'table of', 'list of', 'note', 'footnote', 'appendix',
        'editor', 'translator', 'volume', 'index', 'by the same',
        'dedication', 'acknowledgment', 'foreword', 'epilogue',
        'the end', 'finis', 'end of', 'version', 'variant',
        '(i)', '(ii)', '(iii)', '(iv)', '(v)', '(vi)', '(vii)', '(viii)',
        'first version', 'second version', 'third version',
        'household stories', 'fairy tales', 'fairy stories'
    ]

    for pattern in skip_patterns:
        if pattern in text_lower:
            return False

    # Skip if it's mostly numbers or punctuation
    alpha_count = sum(1 for c in text if c.isalpha())
    if alpha_count < len(text) * 0.5:
        return False

    return True


def extract_title_from_alt(alt_text: str) -> Optional[str]:
    """Extract story title from image alt text."""
    if not alt_text or len(alt_text) < 3:
        return None

    # Clean up alt text
    alt = alt_text.strip()

    # Skip generic alts
    skip_terms = ['illustration', 'list of', 'page', 'household stories', 'fairy tales',
                  'grimm', 'andersen', 'translated', 'collection']
    alt_lower = alt.lower()
    if any(term in alt_lower for term in skip_terms):
        # But it might have a title after a dash or quote
        pass

    # Try to extract title - often format is "STORY TITLE - description" or "STORY TITLE"
    # Take the first part before common separators
    for sep in [' - ', ' "', ' – ', ' — ']:
        if sep in alt:
            alt = alt.split(sep)[0]
            break

    # Clean up
    alt = alt.strip(' .-"\'')

    # Skip if too short or too long
    if len(alt) < 3 or len(alt) > 100:
        return None

    # Skip if looks like metadata
    if any(x in alt.lower() for x in ['illustration', 'page', 'list']):
        return None

    return alt


def extract_story_image_mappings(book_id: int, html: str, images_dir: Path, origin: str) -> list[ImageMapping]:
    """Extract image-to-story mappings from HTML structure."""
    soup = BeautifulSoup(html, 'lxml')
    mappings = []

    current_chapter = ""

    # Process document looking for chapters and images
    for element in soup.find_all(['h1', 'h2', 'h3', 'h4', 'img', 'p']):
        # Track chapter/story titles
        if element.name in ['h1', 'h2', 'h3', 'h4']:
            text = element.get_text(strip=True)
            if is_valid_story_title(text):
                current_chapter = text

        # Process images
        elif element.name == 'img':
            src = element.get('src', '')
            if not src:
                continue

            filename = Path(src).name
            local_path = images_dir / filename

            if not local_path.exists():
                continue

            # Skip tiny images (likely decorations)
            try:
                size = local_path.stat().st_size
                if size < 5000:  # < 5KB probably a decoration
                    continue
            except:
                pass

            alt_text = element.get('alt', '')

            # Get surrounding text for context
            context = ""
            prev_sib = element.find_previous_sibling('p')
            if prev_sib:
                context = prev_sib.get_text(strip=True)[:100]

            # Determine story title - prefer alt text if it looks like a title
            story_title = None
            alt_title = extract_title_from_alt(alt_text)
            if alt_title and is_valid_story_title(alt_title):
                story_title = alt_title
            elif current_chapter:
                story_title = current_chapter

            if story_title:
                mappings.append(ImageMapping(
                    image_path=str(local_path),
                    story_title=story_title,
                    origin=origin,
                    book_id=book_id,
                    alt_text=alt_text,
                    context=context
                ))

    return mappings


def download_all_illustrations(force: bool = False) -> dict:
    """Download illustrations from all sources and build mappings."""
    downloader = GutenbergDownloader()
    all_sources = GUTENBERG_SOURCES + ILLUSTRATED_SOURCES

    results = {
        'total_images': 0,
        'total_mappings': 0,
        'by_origin': {},
        'mappings': []
    }

    for source in all_sources:
        print(f"\n{'='*50}")
        print(f"Processing: {source.title} (ID: {source.book_id})")
        print(f"{'='*50}")

        images_dir = CACHE_DIR / f"images_{source.book_id}"
        images_dir.mkdir(exist_ok=True)

        try:
            # Download HTML with images
            html = downloader.get_html(source, force_download=force)

            # Download all images
            images = downloader.get_images(source, images_dir, force_download=force)
            print(f"  Downloaded {len(images)} images")

            if images:
                # Extract mappings
                mappings = extract_story_image_mappings(
                    source.book_id, html, images_dir, source.origin
                )
                print(f"  Created {len(mappings)} story mappings")

                results['total_images'] += len(images)
                results['total_mappings'] += len(mappings)

                if source.origin not in results['by_origin']:
                    results['by_origin'][source.origin] = {'images': 0, 'mappings': 0}
                results['by_origin'][source.origin]['images'] += len(images)
                results['by_origin'][source.origin]['mappings'] += len(mappings)

                # Store mappings
                for m in mappings:
                    results['mappings'].append({
                        'image_path': m.image_path,
                        'story_title': m.story_title,
                        'normalized_title': normalize_title(m.story_title),
                        'origin': m.origin,
                        'book_id': m.book_id,
                        'alt_text': m.alt_text
                    })

            time.sleep(1)  # Be nice to Gutenberg

        except Exception as e:
            print(f"  Error: {e}")
            continue

    # Save mappings to JSON
    mappings_file = CACHE_DIR / "image_mappings.json"
    with open(mappings_file, 'w', encoding='utf-8') as f:
        json.dump(results, f, indent=2, ensure_ascii=False)

    print(f"\n{'='*50}")
    print(f"TOTAL: {results['total_images']} images, {results['total_mappings']} mappings")
    print(f"Saved mappings to: {mappings_file}")

    return results


def load_image_mappings() -> dict:
    """Load the image mappings from cache."""
    mappings_file = CACHE_DIR / "image_mappings.json"
    if mappings_file.exists():
        with open(mappings_file, 'r', encoding='utf-8') as f:
            return json.load(f)
    return {'mappings': []}


def find_images_for_story(story_title: str, origin: str) -> list[str]:
    """Find all images that match a story title."""
    data = load_image_mappings()
    normalized = normalize_title(story_title)

    matches = []
    for mapping in data.get('mappings', []):
        if mapping['origin'] != origin:
            continue

        # Check for match
        mapping_normalized = mapping['normalized_title']

        # Exact match or substantial overlap
        if normalized == mapping_normalized:
            matches.append(mapping['image_path'])
        elif normalized in mapping_normalized or mapping_normalized in normalized:
            matches.append(mapping['image_path'])
        else:
            # Check word overlap
            story_words = set(normalized.split())
            mapping_words = set(mapping_normalized.split())
            overlap = story_words & mapping_words
            if len(overlap) >= 2 or (len(overlap) >= 1 and len(story_words) <= 3):
                matches.append(mapping['image_path'])

    return matches


def rebuild_mappings_from_catalog():
    """Rebuild image mappings using actual story catalog and fuzzy matching."""
    from difflib import SequenceMatcher
    from .config import OUTPUT_DIR, CACHE_DIR, GUTENBERG_SOURCES, ILLUSTRATED_SOURCES

    # Get all story titles by origin
    story_catalog = {}
    for origin_dir in OUTPUT_DIR.iterdir():
        if not origin_dir.is_dir() or origin_dir.name.startswith('_'):
            continue
        origin = origin_dir.name
        story_catalog[origin] = []
        for story_dir in origin_dir.iterdir():
            if story_dir.is_dir():
                metadata_file = story_dir / "metadata.json"
                if metadata_file.exists():
                    import json
                    with open(metadata_file, encoding='utf-8') as f:
                        meta = json.load(f)
                        story_catalog[origin].append({
                            'title': meta.get('title', story_dir.name),
                            'normalized': normalize_title(meta.get('title', story_dir.name))
                        })

    # Map book IDs to origins
    book_origins = {}
    for src in GUTENBERG_SOURCES + ILLUSTRATED_SOURCES:
        book_origins[src.book_id] = src.origin

    results = {
        'total_images': 0,
        'total_mappings': 0,
        'by_origin': {},
        'mappings': []
    }

    # Process each image directory
    for images_dir in CACHE_DIR.glob("images_*"):
        if not images_dir.is_dir():
            continue
        try:
            book_id = int(images_dir.name.split('_')[1])
        except:
            continue

        origin = book_origins.get(book_id)
        if not origin or origin not in story_catalog:
            continue

        stories = story_catalog[origin]
        if not stories:
            continue

        # Get all images
        images = list(images_dir.glob("*.jpg")) + list(images_dir.glob("*.png")) + list(images_dir.glob("*.gif"))

        for img_path in images:
            # Skip tiny images
            try:
                if img_path.stat().st_size < 5000:
                    continue
            except:
                continue

            # Try to match image filename to a story
            img_name = normalize_title(img_path.stem.replace('-', ' ').replace('_', ' '))

            best_match = None
            best_score = 0.0

            for story in stories:
                story_norm = story['normalized']

                # Check word overlap
                img_words = set(img_name.split())
                story_words = set(story_norm.split())
                overlap = img_words & story_words

                # Calculate similarity
                score = SequenceMatcher(None, img_name, story_norm).ratio()

                # Boost for word overlap
                if overlap:
                    score += len(overlap) * 0.15

                # Boost for containment
                if story_norm in img_name or img_name in story_norm:
                    score += 0.3

                if score > best_score and score > 0.35:
                    best_score = score
                    best_match = story

            if best_match:
                results['total_images'] += 1
                results['total_mappings'] += 1

                if origin not in results['by_origin']:
                    results['by_origin'][origin] = {'images': 0, 'mappings': 0}
                results['by_origin'][origin]['images'] += 1
                results['by_origin'][origin]['mappings'] += 1

                results['mappings'].append({
                    'image_path': str(img_path),
                    'story_title': best_match['title'],
                    'normalized_title': best_match['normalized'],
                    'origin': origin,
                    'book_id': book_id,
                    'alt_text': '',
                    'match_score': round(best_score, 2)
                })

    # Save
    mappings_file = CACHE_DIR / "image_mappings.json"
    import json
    with open(mappings_file, 'w', encoding='utf-8') as f:
        json.dump(results, f, indent=2, ensure_ascii=False)

    print(f"Rebuilt mappings: {results['total_mappings']} images matched to stories")
    for origin, stats in results['by_origin'].items():
        print(f"  {origin}: {stats['mappings']} matches")

    return results


def combined_mapping():
    """Use both HTML parsing and catalog matching for best coverage."""
    from difflib import SequenceMatcher
    from .config import OUTPUT_DIR, CACHE_DIR, GUTENBERG_SOURCES, ILLUSTRATED_SOURCES
    import json

    # First, run HTML-based extraction
    print("Phase 1: HTML-based extraction...")
    html_results = download_all_illustrations()

    # Get all story titles by origin for validation
    story_catalog = {}
    for origin_dir in OUTPUT_DIR.iterdir():
        if not origin_dir.is_dir() or origin_dir.name.startswith('_'):
            continue
        origin = origin_dir.name
        story_catalog[origin] = set()
        for story_dir in origin_dir.iterdir():
            if story_dir.is_dir():
                metadata_file = story_dir / "metadata.json"
                if metadata_file.exists():
                    with open(metadata_file, encoding='utf-8') as f:
                        meta = json.load(f)
                        story_catalog[origin].add(normalize_title(meta.get('title', '')))

    # Filter and validate mappings
    print("\nPhase 2: Validating and matching to catalog...")
    valid_mappings = []
    by_origin = {}

    for mapping in html_results.get('mappings', []):
        origin = mapping['origin']
        norm_title = mapping['normalized_title']

        if origin not in story_catalog:
            continue

        # Check if this title matches any story in catalog
        best_match = None
        best_score = 0.0

        for catalog_title in story_catalog[origin]:
            # Check similarity
            score = SequenceMatcher(None, norm_title, catalog_title).ratio()

            # Boost for word overlap
            title_words = set(norm_title.split())
            catalog_words = set(catalog_title.split())
            overlap = title_words & catalog_words
            if overlap:
                score += len(overlap) * 0.1

            # Boost for containment
            if catalog_title in norm_title or norm_title in catalog_title:
                score += 0.25

            if score > best_score:
                best_score = score
                best_match = catalog_title

        # Accept if good enough match
        if best_score > 0.4 and best_match:
            mapping['normalized_title'] = best_match
            mapping['match_score'] = round(best_score, 2)
            valid_mappings.append(mapping)

            if origin not in by_origin:
                by_origin[origin] = {'images': 0, 'mappings': 0}
            by_origin[origin]['images'] += 1
            by_origin[origin]['mappings'] += 1

    # Save validated mappings
    results = {
        'total_images': len(valid_mappings),
        'total_mappings': len(valid_mappings),
        'by_origin': by_origin,
        'mappings': valid_mappings
    }

    mappings_file = CACHE_DIR / "image_mappings.json"
    with open(mappings_file, 'w', encoding='utf-8') as f:
        json.dump(results, f, indent=2, ensure_ascii=False)

    print(f"\nFinal: {len(valid_mappings)} images matched to stories")
    for origin, stats in by_origin.items():
        print(f"  {origin}: {stats['mappings']} matches")

    return results


if __name__ == '__main__':
    import sys
    if len(sys.argv) > 1 and sys.argv[1] == '--rebuild':
        rebuild_mappings_from_catalog()
    elif len(sys.argv) > 1 and sys.argv[1] == '--combined':
        combined_mapping()
    else:
        download_all_illustrations()
