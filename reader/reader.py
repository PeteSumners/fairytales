"""
GBA-style Fairytale E-Reader
A retro handheld-inspired reading experience.
"""

import pygame
import json
import os
import sys
from pathlib import Path
from typing import List, Optional
import textwrap

# Add reader directory to path
sys.path.insert(0, str(Path(__file__).parent))

import colors
from sounds import sounds
from audio import AudioPlayer
from media import MediaManager
from bible import BibleLoader

pygame.init()
pygame.mixer.init()

# Paths
ROOT = Path(__file__).parent.parent
OUTPUT_DIR = ROOT / "output" / "fairytales"
AUDIO_DIR = ROOT / "audio"
SAVE_FILE = ROOT / "reader" / "progress.json"

# Bible paths (external)
BIBLE_TEXT = Path(r"C:\Users\PeteS\Desktop\archive\old\godot\projects\Pete's_World_0.2.4\Bible\kjv.txt")
BIBLE_VIDEO_DIR = Path(r"C:\Users\PeteS\Desktop\archive\xfer\Bible")

# Display settings - Higher resolution for readability
WINDOW_WIDTH = 800
WINDOW_HEIGHT = 600
CONTENT_MARGIN = 40  # Margin around content

# Fonts - Proper readable monospace fonts
pygame.font.init()
FONT_TINY = pygame.font.SysFont('Consolas', 12)
FONT_SMALL = pygame.font.SysFont('Consolas', 16)
FONT_MEDIUM = pygame.font.SysFont('Consolas', 18)
FONT_LARGE = pygame.font.SysFont('Consolas', 22)
FONT_TITLE = pygame.font.SysFont('Consolas', 28)
FONT_BODY = pygame.font.SysFont('Georgia', 18)  # Serif for reading


class PixelText:
    """Pixel-perfect text rendering."""

    @staticmethod
    def render(surface, text, pos, font=FONT_MEDIUM, color=None, center=False):
        if color is None:
            color = colors.TEXT_DEFAULT
        rendered = font.render(text, False, color)
        if center:
            rect = rendered.get_rect(center=pos)
            surface.blit(rendered, rect)
        else:
            surface.blit(rendered, pos)
        return rendered.get_size()

    @staticmethod
    def wrap_text(text, font, max_width):
        """Wrap text to fit within max_width."""
        words = text.split(' ')
        lines = []
        current_line = []

        for word in words:
            test_line = ' '.join(current_line + [word])
            width = font.size(test_line)[0]
            if width <= max_width:
                current_line.append(word)
            else:
                if current_line:
                    lines.append(' '.join(current_line))
                current_line = [word]

        if current_line:
            lines.append(' '.join(current_line))

        return lines


class StoryLoader:
    """Load stories from the output directory."""

    @staticmethod
    def get_top_level(bible_loader=None) -> List[dict]:
        """Get top-level menu items (Fairytales folder + Bible)."""
        items = []

        # Add Fairytales folder if it has collections
        fairytale_collections = StoryLoader.get_fairytale_collections()
        if fairytale_collections:
            total_stories = sum(c['story_count'] for c in fairytale_collections)
            items.append({
                'name': 'Fairytales',
                'origin': 'fairytales',
                'story_count': total_stories,
                'is_folder': True,
                'is_bible': False
            })

        # Add Bible if available
        if bible_loader and bible_loader.is_available():
            stats = bible_loader.get_stats()
            items.append({
                'name': 'Holy Bible (KJV)',
                'origin': 'bible',
                'story_count': stats['books'],
                'is_folder': False,
                'is_bible': True
            })

        return items

    @staticmethod
    def get_fairytale_collections() -> List[dict]:
        """Get all fairytale collections (inside the fairytales folder)."""
        collections = []

        if not OUTPUT_DIR.exists():
            return collections

        for origin_dir in OUTPUT_DIR.iterdir():
            if origin_dir.is_dir() and origin_dir.name not in ['__pycache__']:
                stories = StoryLoader.get_stories(origin_dir.name)
                if stories:
                    collections.append({
                        'name': origin_dir.name.replace('-', ' ').title(),
                        'origin': origin_dir.name,
                        'story_count': len(stories),
                        'is_bible': False
                    })
        return collections

    @staticmethod
    def get_collections(bible_loader=None) -> List[dict]:
        """Get all available collections (legacy - returns fairytale collections)."""
        return StoryLoader.get_fairytale_collections()

    @staticmethod
    def get_stories(origin: str) -> List[dict]:
        """Get all stories in a collection."""
        stories = []
        origin_dir = OUTPUT_DIR / origin

        if not origin_dir.exists():
            return stories

        for story_dir in origin_dir.iterdir():
            if story_dir.is_dir():
                metadata_file = story_dir / "metadata.json"
                story_file = story_dir / "story.md"

                if metadata_file.exists() and story_file.exists():
                    try:
                        with open(metadata_file, 'r', encoding='utf-8') as f:
                            metadata = json.load(f)
                        stories.append({
                            'slug': story_dir.name,
                            'title': metadata.get('title', story_dir.name),
                            'author': metadata.get('author', 'Unknown'),
                            'reading_time': metadata.get('reading_time_minutes', 0),
                            'word_count': metadata.get('word_count', 0),
                            'path': story_dir
                        })
                    except:
                        pass

        return sorted(stories, key=lambda s: s['title'])

    @staticmethod
    def load_story_text(story_path: Path) -> str:
        """Load the text of a story."""
        story_file = story_path / "story.md"
        if story_file.exists():
            with open(story_file, 'r', encoding='utf-8') as f:
                text = f.read()
            # Clean markdown
            lines = text.split('\n')
            clean_lines = []
            for line in lines:
                # Skip metadata lines
                if line.startswith('**') or line.startswith('---') or line.startswith('*Source:'):
                    continue
                # Convert headers to plain text
                if line.startswith('#'):
                    line = line.lstrip('#').strip()
                clean_lines.append(line)
            return '\n'.join(clean_lines)
        return ""


class ProgressManager:
    """Manage reading progress, settings, completions, bookmarks, favorites, and stats."""

    DEFAULT_SETTINGS = {
        'font_size': 'medium',  # small, medium, large
        'theme': 'dark',        # dark, light, sepia
    }

    def __init__(self):
        self.progress = {}
        self.settings = dict(self.DEFAULT_SETTINGS)
        self.completions = {}  # {origin/slug: completion_date}
        self.bookmarks = {}    # {origin/slug: [page_numbers]}
        self.favorites = []    # [origin/slug]
        self.audio_positions = {}  # {origin/slug: position_seconds}
        self.stats = {'pages_read': 0, 'reading_time': 0, 'stories_opened': 0}
        self.load()

    def load(self):
        if SAVE_FILE.exists():
            try:
                with open(SAVE_FILE, 'r') as f:
                    data = json.load(f)
                    self.progress = data.get('progress', data)  # backwards compat
                    self.settings = {**self.DEFAULT_SETTINGS, **data.get('settings', {})}
                    self.completions = data.get('completions', {})
                    self.bookmarks = data.get('bookmarks', {})
                    self.favorites = data.get('favorites', [])
                    self.audio_positions = data.get('audio_positions', {})
                    self.stats = data.get('stats', {'pages_read': 0, 'reading_time': 0, 'stories_opened': 0})
            except:
                self.progress = {}

    def save(self):
        SAVE_FILE.parent.mkdir(parents=True, exist_ok=True)
        data = {
            'progress': self.progress,
            'settings': self.settings,
            'completions': self.completions,
            'bookmarks': self.bookmarks,
            'favorites': self.favorites,
            'audio_positions': self.audio_positions,
            'stats': self.stats
        }
        with open(SAVE_FILE, 'w') as f:
            json.dump(data, f, indent=2)

    def get_page(self, origin: str, slug: str) -> int:
        key = f"{origin}/{slug}"
        return self.progress.get(key, {}).get('page', 0)

    def set_page(self, origin: str, slug: str, page: int):
        key = f"{origin}/{slug}"
        if key not in self.progress:
            self.progress[key] = {}
        self.progress[key]['page'] = page
        self.save()

    # Settings methods
    def get_setting(self, key: str):
        return self.settings.get(key, self.DEFAULT_SETTINGS.get(key))

    def set_setting(self, key: str, value):
        self.settings[key] = value
        self.save()

    # Completion methods
    def mark_complete(self, origin: str, slug: str) -> str:
        """Mark a story as complete and return the completion date."""
        from datetime import datetime
        key = f"{origin}/{slug}"
        date_str = datetime.now().strftime("%Y-%m-%d")
        self.completions[key] = date_str
        self.save()
        return date_str

    def unmark_complete(self, origin: str, slug: str):
        """Remove completion status from a story."""
        key = f"{origin}/{slug}"
        if key in self.completions:
            del self.completions[key]
            self.save()

    def get_completion(self, origin: str, slug: str) -> Optional[str]:
        """Get completion date or None if not completed."""
        key = f"{origin}/{slug}"
        return self.completions.get(key)

    def is_complete(self, origin: str, slug: str) -> bool:
        return self.get_completion(origin, slug) is not None

    # Bookmark methods
    def add_bookmark(self, origin: str, slug: str, page: int):
        """Add a bookmark at a specific page."""
        key = f"{origin}/{slug}"
        if key not in self.bookmarks:
            self.bookmarks[key] = []
        if page not in self.bookmarks[key]:
            self.bookmarks[key].append(page)
            self.bookmarks[key].sort()
            self.save()

    def remove_bookmark(self, origin: str, slug: str, page: int):
        """Remove a bookmark at a specific page."""
        key = f"{origin}/{slug}"
        if key in self.bookmarks and page in self.bookmarks[key]:
            self.bookmarks[key].remove(page)
            if not self.bookmarks[key]:
                del self.bookmarks[key]
            self.save()

    def toggle_bookmark(self, origin: str, slug: str, page: int) -> bool:
        """Toggle bookmark and return whether it's now bookmarked."""
        key = f"{origin}/{slug}"
        if key in self.bookmarks and page in self.bookmarks[key]:
            self.remove_bookmark(origin, slug, page)
            return False
        else:
            self.add_bookmark(origin, slug, page)
            return True

    def get_bookmarks(self, origin: str, slug: str) -> List[int]:
        """Get all bookmarks for a story."""
        key = f"{origin}/{slug}"
        return self.bookmarks.get(key, [])

    def is_bookmarked(self, origin: str, slug: str, page: int) -> bool:
        """Check if a specific page is bookmarked."""
        return page in self.get_bookmarks(origin, slug)

    def has_bookmarks(self, origin: str, slug: str) -> bool:
        """Check if story has any bookmarks."""
        key = f"{origin}/{slug}"
        return key in self.bookmarks and len(self.bookmarks[key]) > 0

    # Favorites methods
    def toggle_favorite(self, origin: str, slug: str) -> bool:
        """Toggle favorite status and return whether it's now a favorite."""
        key = f"{origin}/{slug}"
        if key in self.favorites:
            self.favorites.remove(key)
            self.save()
            return False
        else:
            self.favorites.append(key)
            self.save()
            return True

    def is_favorite(self, origin: str, slug: str) -> bool:
        """Check if story is a favorite."""
        return f"{origin}/{slug}" in self.favorites

    # Audio position methods
    def get_audio_position(self, origin: str, slug: str) -> float:
        """Get saved audio position in seconds."""
        key = f"{origin}/{slug}"
        return self.audio_positions.get(key, 0.0)

    def set_audio_position(self, origin: str, slug: str, position: float):
        """Save audio position in seconds."""
        key = f"{origin}/{slug}"
        if position > 5.0:  # Only save if past 5 seconds
            self.audio_positions[key] = position
        elif key in self.audio_positions:
            del self.audio_positions[key]  # Clear if rewound to start
        self.save()

    def clear_audio_position(self, origin: str, slug: str):
        """Clear saved audio position (e.g., when finished)."""
        key = f"{origin}/{slug}"
        if key in self.audio_positions:
            del self.audio_positions[key]
            self.save()

    # Stats methods
    def increment_pages_read(self, count: int = 1):
        """Track pages read."""
        self.stats['pages_read'] = self.stats.get('pages_read', 0) + count
        self.save()

    def increment_stories_opened(self):
        """Track stories opened."""
        self.stats['stories_opened'] = self.stats.get('stories_opened', 0) + 1
        self.save()

    def add_reading_time(self, seconds: int):
        """Track reading time."""
        self.stats['reading_time'] = self.stats.get('reading_time', 0) + seconds
        self.save()


class DecorativeFrame:
    """Draw a clean decorative frame around content."""

    @staticmethod
    def draw(surface):
        """Draw decorative border and header."""
        # Main background
        surface.fill(colors.SCREEN_BG)

        # Decorative border
        border_color = colors.TEXT_DIM
        pygame.draw.rect(surface, border_color, (10, 10, WINDOW_WIDTH - 20, WINDOW_HEIGHT - 20), 2)

        # Inner border for depth
        pygame.draw.rect(surface, colors.SHELL_DARK, (15, 15, WINDOW_WIDTH - 30, WINDOW_HEIGHT - 30), 1)

        # Corner decorations
        corner_size = 12
        corners = [
            (10, 10), (WINDOW_WIDTH - 10 - corner_size, 10),
            (10, WINDOW_HEIGHT - 10 - corner_size), (WINDOW_WIDTH - 10 - corner_size, WINDOW_HEIGHT - 10 - corner_size)
        ]
        for cx, cy in corners:
            pygame.draw.rect(surface, colors.ACCENT, (cx, cy, corner_size, corner_size), 2)


class LibraryScreen:
    """Collection/Story browser screen."""

    def __init__(self, app):
        self.app = app
        self.top_level_items = []  # Fairytales folder + Bible
        self.fairytale_collections = []  # Collections inside Fairytales
        self.stories = []
        self.filtered_stories = []  # Stories after search filter
        self.selected_index = 0
        self.scroll_offset = 0
        self.viewing_collection = None
        self.max_visible = 12  # More items visible at higher res
        self.media_cache = {}  # Cache media availability per story
        self.search_mode = False
        self.search_query = ""
        # Navigation state
        self.is_bible_mode = False
        self.is_fairytales_mode = False  # Inside Fairytales folder
        self.bible_books = []
        self.refresh()

    def refresh(self):
        if self.is_bible_mode:
            # Show all Bible books
            self.bible_books = self.app.bible.get_books()
        elif self.viewing_collection:
            self.stories = StoryLoader.get_stories(self.viewing_collection)
            self._apply_filter()
            # Cache media availability for each story
            for story in self.stories:
                key = f"{self.viewing_collection}/{story['slug']}"
                if key not in self.media_cache:
                    self.media_cache[key] = self.app.media.get_availability(
                        self.viewing_collection, story['title']
                    )
        elif self.is_fairytales_mode:
            # Show fairytale collections
            self.fairytale_collections = StoryLoader.get_fairytale_collections()
        else:
            # Top level: Fairytales folder + Bible
            self.top_level_items = StoryLoader.get_top_level(self.app.bible)

    def _apply_filter(self):
        """Apply search filter to stories."""
        if not self.search_query:
            self.filtered_stories = self.stories
        else:
            query = self.search_query.lower()
            self.filtered_stories = [
                s for s in self.stories
                if query in s['title'].lower()
            ]
        # Reset selection when filter changes
        self.selected_index = min(self.selected_index, max(0, len(self.filtered_stories) - 1))
        self.scroll_offset = 0

    def get_items(self):
        if self.is_bible_mode:
            return self.bible_books
        if self.viewing_collection:
            return self.filtered_stories
        if self.is_fairytales_mode:
            return self.fairytale_collections
        return self.top_level_items

    def handle_event(self, event):
        items = self.get_items()

        if event.type == pygame.KEYDOWN:
            # Search mode handling
            if self.search_mode:
                if event.key == pygame.K_ESCAPE:
                    self.search_mode = False
                    self.search_query = ""
                    self._apply_filter()
                    sounds.play_back()
                elif event.key == pygame.K_RETURN:
                    self.search_mode = False
                    sounds.play_select()
                elif event.key == pygame.K_BACKSPACE:
                    if self.search_query:
                        self.search_query = self.search_query[:-1]
                        self._apply_filter()
                else:
                    # Add character to search
                    char = event.unicode
                    if char and char.isprintable() and len(self.search_query) < 30:
                        self.search_query += char
                        self._apply_filter()
                return

        if not items:
            # Handle slash to enter search even with no results
            if event.type == pygame.KEYDOWN and event.key == pygame.K_SLASH and self.viewing_collection:
                self.search_mode = True
                sounds.play_select()
            return

        if event.type == pygame.KEYDOWN:
            if event.key == pygame.K_UP:
                sounds.play_menu_move()
                self.selected_index = max(0, self.selected_index - 1)
                if self.selected_index < self.scroll_offset:
                    self.scroll_offset = self.selected_index
            elif event.key == pygame.K_DOWN:
                sounds.play_menu_move()
                self.selected_index = min(len(items) - 1, self.selected_index + 1)
                if self.selected_index >= self.scroll_offset + self.max_visible:
                    self.scroll_offset = self.selected_index - self.max_visible + 1
            elif event.key in (pygame.K_RETURN, pygame.K_z, pygame.K_SPACE):
                sounds.play_select()
                if self.is_bible_mode:
                    # Open entire book directly (no chapter selection)
                    book = items[self.selected_index]
                    self.app.open_bible_book(book['name'])
                elif self.viewing_collection:
                    story = items[self.selected_index]
                    key = f"{self.viewing_collection}/{story['slug']}"
                    media = self.media_cache.get(key)
                    # Open story directly with audio only
                    self.app.open_story(self.viewing_collection, story,
                                      with_audio=media.has_audio if media else False)
                elif self.is_fairytales_mode:
                    # Enter a collection from Fairytales folder
                    collection = items[self.selected_index]
                    self.viewing_collection = collection['origin']
                    self.selected_index = 0
                    self.scroll_offset = 0
                    self.refresh()
                else:
                    # Top level - check what was selected
                    item = items[self.selected_index]
                    if item.get('is_bible'):
                        self.is_bible_mode = True
                        self.selected_index = 0
                        self.scroll_offset = 0
                        self.refresh()
                    elif item.get('is_folder'):
                        # Enter Fairytales folder
                        self.is_fairytales_mode = True
                        self.selected_index = 0
                        self.scroll_offset = 0
                        self.refresh()
            elif event.key in (pygame.K_ESCAPE, pygame.K_x, pygame.K_BACKSPACE):
                sounds.play_back()
                if self.is_bible_mode:
                    # Exit Bible mode back to top level
                    self.is_bible_mode = False
                    self.selected_index = 0
                    self.scroll_offset = 0
                    self.refresh()
                elif self.viewing_collection:
                    # Exit collection back to Fairytales folder
                    self.viewing_collection = None
                    self.selected_index = 0
                    self.scroll_offset = 0
                    self.search_query = ""
                    self.search_mode = False
                    self.refresh()
                elif self.is_fairytales_mode:
                    # Exit Fairytales folder back to top level
                    self.is_fairytales_mode = False
                    self.selected_index = 0
                    self.scroll_offset = 0
                    self.refresh()
            elif event.key == pygame.K_SLASH:
                # Enter search mode
                if self.viewing_collection:
                    self.search_mode = True
                    sounds.play_select()
            elif event.key == pygame.K_t:
                colors.next_theme()
            elif event.key == pygame.K_s:
                sounds.play_select()
                self.app.show_settings()
            elif event.key == pygame.K_r:
                # Random story
                if self.viewing_collection and self.stories:
                    import random
                    sounds.play_select()
                    story = random.choice(self.stories)
                    key = f"{self.viewing_collection}/{story['slug']}"
                    media = self.media_cache.get(key)
                    # Open story directly with audio only
                    self.app.open_story(self.viewing_collection, story,
                                      with_audio=media.has_audio if media else False)
            elif event.key == pygame.K_f:
                # Toggle favorite
                if self.viewing_collection and self.stories:
                    story = self.stories[self.selected_index]
                    is_now_favorite = self.app.progress.toggle_favorite(
                        self.viewing_collection, story['slug']
                    )
                    if is_now_favorite:
                        sounds.play_select()
                    else:
                        sounds.play_back()

    def draw(self, surface):
        # Draw frame first
        DecorativeFrame.draw(surface)

        # Header
        if self.is_bible_mode:
            title = "Holy Bible (KJV)"
        elif self.viewing_collection:
            title = self.viewing_collection.replace('-', ' ').title()
        elif self.is_fairytales_mode:
            title = "Fairytales"
        else:
            title = "Library"

        PixelText.render(surface, title, (WINDOW_WIDTH // 2, 40), FONT_TITLE, colors.TEXT_DEFAULT, center=True)

        # Search bar (if in search mode or has query)
        if self.search_mode or self.search_query:
            search_y = 58
            if self.search_mode:
                # Active search mode - show input with cursor
                search_text = f"Search: {self.search_query}_"
                PixelText.render(surface, search_text, (CONTENT_MARGIN + 10, search_y), FONT_SMALL, colors.ACCENT)
            else:
                # Passive filter display
                search_text = f"Filter: {self.search_query} ({len(self.filtered_stories)} results)"
                PixelText.render(surface, search_text, (CONTENT_MARGIN + 10, search_y), FONT_SMALL, colors.TEXT_DIM)

        # Draw divider
        pygame.draw.line(surface, colors.TEXT_DIM, (CONTENT_MARGIN, 75), (WINDOW_WIDTH - CONTENT_MARGIN, 75), 2)

        items = self.get_items()

        if not items:
            PixelText.render(surface, "No stories found", (WINDOW_WIDTH // 2, 200),
                           FONT_LARGE, colors.TEXT_DIM, center=True)
            PixelText.render(surface, "Run: fairytale process", (WINDOW_WIDTH // 2, 240),
                           FONT_MEDIUM, colors.TEXT_DIM, center=True)
            return

        # Draw items
        y = 95
        # Collections need more height, Bible and stories use smaller height
        if self.is_bible_mode or self.viewing_collection:
            item_height = 35
        else:
            item_height = 45
        for i in range(self.scroll_offset, min(self.scroll_offset + self.max_visible, len(items))):
            item = items[i]
            is_selected = i == self.selected_index

            # Selection highlight - full width and proper height
            if is_selected:
                pygame.draw.rect(surface, colors.TEXT_DEFAULT,
                               (CONTENT_MARGIN - 5, y - 8, WINDOW_WIDTH - CONTENT_MARGIN * 2 + 10, item_height),
                               border_radius=4)

            text_color = colors.SCREEN_BG if is_selected else colors.TEXT_DEFAULT

            if self.is_bible_mode:
                # Book item - show name, bookmark count, chapter count, and audio indicator
                book_name = item['name']
                title_x = CONTENT_MARGIN + 15

                # Check for bookmarks (same infrastructure as fairytales)
                bookmarks = self.app.progress.get_bookmarks('bible', book_name)
                if bookmarks:
                    bm_text = f"[{len(bookmarks)}BM]"
                    PixelText.render(surface, bm_text, (title_x, y), FONT_TINY,
                                   colors.SCREEN_BG if is_selected else colors.ACCENT)
                    title_x += len(bm_text) * 6 + 4

                PixelText.render(surface, book_name, (title_x, y), FONT_SMALL, text_color)
                info_str = f"{item['chapters']} ch"
                PixelText.render(surface, info_str, (WINDOW_WIDTH - CONTENT_MARGIN - 80, y),
                               FONT_SMALL, text_color)
                # Show audio indicator if available
                if self.app.bible.has_audio(book_name):
                    PixelText.render(surface, "A", (WINDOW_WIDTH - CONTENT_MARGIN - 110, y),
                                   FONT_SMALL, colors.SCREEN_BG if is_selected else colors.ACCENT)
            elif self.viewing_collection:
                # Check if story is completed
                completion_date = self.app.progress.get_completion(self.viewing_collection, item['slug'])
                is_complete = completion_date is not None
                is_favorite = self.app.progress.is_favorite(self.viewing_collection, item['slug'])
                bookmarks = self.app.progress.get_bookmarks(self.viewing_collection, item['slug'])
                has_bookmarks = len(bookmarks) > 0

                # Story item - show indicators
                title_x = CONTENT_MARGIN + 15
                if is_favorite:
                    PixelText.render(surface, "+", (title_x, y), FONT_SMALL,
                                   colors.SCREEN_BG if is_selected else colors.ACCENT)
                    title_x += 12
                if is_complete:
                    PixelText.render(surface, "*", (title_x, y), FONT_SMALL,
                                   colors.SCREEN_BG if is_selected else colors.ACCENT)
                    title_x += 12
                if has_bookmarks:
                    # Show bookmark count prominently
                    bm_text = f"[{len(bookmarks)}BM]"
                    PixelText.render(surface, bm_text, (title_x, y), FONT_TINY,
                                   colors.SCREEN_BG if is_selected else colors.ACCENT)
                    title_x += len(bm_text) * 6 + 4

                # Auto-scale: use smaller font for long titles
                title = item['title']
                if len(title) > 45:
                    title_font = FONT_TINY
                    max_len = 55
                elif len(title) > 38:
                    title_font = FONT_TINY
                    max_len = 50
                else:
                    title_font = FONT_SMALL
                    max_len = 38
                # Reduce max_len based on indicators shown
                if is_favorite:
                    max_len -= 3
                if is_complete:
                    max_len -= 3
                if has_bookmarks:
                    max_len -= 8  # Bookmark indicator is larger now
                display_title = title[:max_len] + '...' if len(title) > max_len else title
                PixelText.render(surface, display_title, (title_x, y), title_font, text_color)

                # Audio icon (only show if audio available)
                key = f"{self.viewing_collection}/{item['slug']}"
                if key in self.media_cache:
                    media = self.media_cache[key]
                    if media.has_audio:
                        PixelText.render(surface, "A", (WINDOW_WIDTH - CONTENT_MARGIN - 95, y), FONT_SMALL,
                                       colors.SCREEN_BG if is_selected else colors.ACCENT)

                # Time or completion date
                if is_complete:
                    info_str = completion_date  # Show completion date
                else:
                    info_str = f"{item['reading_time']} min"
                PixelText.render(surface, info_str, (WINDOW_WIDTH - CONTENT_MARGIN - 75, y), FONT_SMALL, text_color)
            else:
                # Collection item
                PixelText.render(surface, item['name'], (CONTENT_MARGIN + 15, y), FONT_LARGE, text_color)
                count_str = f"{item['story_count']} stories"
                PixelText.render(surface, count_str, (CONTENT_MARGIN + 15, y + 24), FONT_SMALL,
                               colors.SCREEN_BG if is_selected else colors.TEXT_DIM)

            y += item_height

        # Scroll indicators
        if self.scroll_offset > 0:
            PixelText.render(surface, "▲", (WINDOW_WIDTH - 30, 85), FONT_MEDIUM, colors.TEXT_DIM)
        if self.scroll_offset + self.max_visible < len(items):
            PixelText.render(surface, "▼", (WINDOW_WIDTH - 30, WINDOW_HEIGHT - 60), FONT_MEDIUM, colors.TEXT_DIM)

        # Help text
        if self.viewing_collection:
            help_text = "[Enter] Read [R] Random [F] Fav [/] Search [Esc] Back"
        else:
            help_text = "[Enter] Select   [S] Settings"
        PixelText.render(surface, help_text, (WINDOW_WIDTH // 2, WINDOW_HEIGHT - 30),
                        FONT_SMALL, colors.TEXT_DIM, center=True)


class ReadingScreen:
    """The main reading screen."""

    def __init__(self, app, origin: str, story: dict, with_audio: bool = True):
        self.app = app
        self.origin = origin
        self.story = story
        self.text = StoryLoader.load_story_text(story['path'])
        self.pages = self._paginate()
        self.current_page = self.app.progress.get_page(origin, story['slug'])
        if self.current_page >= len(self.pages):
            self.current_page = 0

        # Audio setup
        self.has_audio = False
        if with_audio:
            self.audio_file = self.app.audio.find_audio_for_story(origin, story['title'])
            self.has_audio = self.audio_file is not None
            if self.has_audio:
                self.app.audio.load(self.audio_file)
                # Restore saved audio position
                saved_pos = self.app.progress.get_audio_position(origin, story['slug'])
                if saved_pos > 0:
                    self.app.audio._start_offset = saved_pos
                sounds.play_chapter_start()

        # Page turn animation state
        self.animating = False
        self.anim_start_time = 0
        self.anim_duration = 0
        self.anim_direction = 1  # 1 = forward, -1 = backward
        self.anim_from_page = 0

    def _paginate(self, line_width: int = 70) -> List[List[str]]:
        """Split text into pages."""
        pages = []
        lines_per_page = 15  # Leave room for bottom HUD

        # Normalize text
        text = self.text.replace('\r\n', '\n').replace('\r', '\n')

        # Split into raw paragraphs
        raw_paragraphs = text.split('\n\n')

        # Clean each paragraph
        cleaned = []
        for para in raw_paragraphs:
            para = ' '.join(para.split('\n'))
            para = ' '.join(para.split())
            para = para.strip()
            if para:
                cleaned.append(para)

        # Detect if source has double-spacing (every line is its own paragraph)
        # If most "paragraphs" are short single lines, join them into real paragraphs
        if len(cleaned) > 10:
            short_count = sum(1 for p in cleaned if len(p) < 80)
            if short_count > len(cleaned) * 0.7:  # Most are short lines
                # Join consecutive prose lines, but preserve verse (rhyming/short lines)
                merged = []
                current = []
                for para in cleaned:
                    # Detect verse: ends with punctuation suggesting rhyme, or very short
                    is_verse = (para.endswith('!') and len(para) < 50) or \
                               (para.endswith(',') and len(para) < 40) or \
                               para.endswith('pick!') or \
                               ('Hither' in para) or ('shake' in para.lower() and len(para) < 40)

                    if is_verse:
                        # Flush current prose
                        if current:
                            merged.append(' '.join(current))
                            current = []
                        merged.append(para)  # Keep verse as separate line
                    else:
                        current.append(para)
                        # Start new paragraph after sentence-ending punctuation + capital
                        if para.endswith(('.', '?', '!', '"')) and len(current) > 2:
                            merged.append(' '.join(current))
                            current = []

                if current:
                    merged.append(' '.join(current))
                cleaned = merged

        # Now wrap and paginate
        all_lines = []
        for para in cleaned:
            wrapped = textwrap.wrap(para, width=line_width)
            all_lines.extend(wrapped)
            all_lines.append('')  # Blank line between paragraphs

        # Split into pages
        current_page = []
        for line in all_lines:
            current_page.append(line)
            if len(current_page) >= lines_per_page:
                pages.append(current_page)
                current_page = []

        if current_page:
            pages.append(current_page)

        return pages if pages else [['']]

    def _start_page_turn(self, direction: int):
        """Start a page turn animation. direction: 1=forward, -1=backward"""
        duration = sounds.play_page_turn()
        self.animating = True
        self.anim_start_time = pygame.time.get_ticks()
        self.anim_duration = duration
        self.anim_direction = direction
        self.anim_from_page = self.current_page - direction  # The page we're leaving

    def _render_page_to_surface(self, page_num: int, content_width: int, content_height: int) -> pygame.Surface:
        """Render a specific page's content to an off-screen surface."""
        surf = pygame.Surface((content_width, content_height))
        surf.fill(colors.SCREEN_BG)

        if page_num < 0 or page_num >= len(self.pages):
            return surf

        y = 20
        line_height = 26
        for line in self.pages[page_num]:
            PixelText.render(surf, line, (20, y), FONT_BODY, colors.TEXT_DEFAULT)
            y += line_height

        return surf

    def handle_event(self, event):
        if event.type == pygame.KEYDOWN:
            # Block input during animation
            if self.animating:
                return

            if event.key in (pygame.K_RIGHT, pygame.K_z):
                if self.current_page < len(self.pages) - 1:
                    self.current_page += 1
                    self._start_page_turn(1)
                    self.app.progress.set_page(self.origin, self.story['slug'], self.current_page)
                    self.app.progress.increment_pages_read()
            elif event.key in (pygame.K_LEFT,):
                if self.current_page > 0:
                    self.current_page -= 1
                    self._start_page_turn(-1)
                    self.app.progress.set_page(self.origin, self.story['slug'], self.current_page)
            elif event.key in (pygame.K_ESCAPE, pygame.K_x, pygame.K_BACKSPACE):
                sounds.play_back()
                # Save audio position before stopping
                if self.has_audio:
                    pos = self.app.audio.get_position()
                    self.app.progress.set_audio_position(self.origin, self.story['slug'], pos)
                self.app.audio.stop()  # Stop audio when leaving
                self.app.close_story()
            elif event.key == pygame.K_t:
                colors.next_theme()
            elif event.key == pygame.K_HOME:
                self.current_page = 0
                self.app.progress.set_page(self.origin, self.story['slug'], 0)
            elif event.key == pygame.K_END:
                self.current_page = len(self.pages) - 1
                self.app.progress.set_page(self.origin, self.story['slug'], self.current_page)
            # Audio controls
            elif event.key == pygame.K_SPACE:
                if self.has_audio:
                    self.app.audio.toggle()
                else:
                    # No audio - use space for page turn
                    if self.current_page < len(self.pages) - 1:
                        self.current_page += 1
                        self._start_page_turn(1)
                        self.app.progress.set_page(self.origin, self.story['slug'], self.current_page)
            elif event.key == pygame.K_COMMA:  # < key - rewind
                if self.has_audio:
                    self.app.audio.seek(-10)
            elif event.key == pygame.K_PERIOD:  # > key - forward
                if self.has_audio:
                    self.app.audio.seek(10)
            elif event.key == pygame.K_MINUS:
                self.app.audio.set_volume(self.app.audio.get_volume() - 0.1)
            elif event.key == pygame.K_EQUALS:  # + key
                self.app.audio.set_volume(self.app.audio.get_volume() + 0.1)
            elif event.key == pygame.K_c:
                # Toggle completion status
                if self.app.progress.is_complete(self.origin, self.story['slug']):
                    self.app.progress.unmark_complete(self.origin, self.story['slug'])
                    sounds.play_back()
                else:
                    self.app.progress.mark_complete(self.origin, self.story['slug'])
                    sounds.play_select()
            elif event.key == pygame.K_b:
                # Toggle bookmark on current page
                is_now_bookmarked = self.app.progress.toggle_bookmark(
                    self.origin, self.story['slug'], self.current_page
                )
                if is_now_bookmarked:
                    sounds.play_select()
                else:
                    sounds.play_back()
            elif event.key == pygame.K_LEFTBRACKET:
                # Jump to previous bookmark
                bookmarks = self.app.progress.get_bookmarks(self.origin, self.story['slug'])
                prev_bookmarks = [b for b in bookmarks if b < self.current_page]
                if prev_bookmarks:
                    old_page = self.current_page
                    self.current_page = max(prev_bookmarks)
                    self._start_page_turn(-1 if self.current_page < old_page else 1)
                    self.app.progress.set_page(self.origin, self.story['slug'], self.current_page)
            elif event.key == pygame.K_RIGHTBRACKET:
                # Jump to next bookmark
                bookmarks = self.app.progress.get_bookmarks(self.origin, self.story['slug'])
                next_bookmarks = [b for b in bookmarks if b > self.current_page]
                if next_bookmarks:
                    old_page = self.current_page
                    self.current_page = min(next_bookmarks)
                    self._start_page_turn(1 if self.current_page > old_page else -1)
                    self.app.progress.set_page(self.origin, self.story['slug'], self.current_page)

    def draw(self, surface):
        # Draw frame
        DecorativeFrame.draw(surface)

        # Title bar - auto-scale font for long titles
        is_complete = self.app.progress.is_complete(self.origin, self.story['slug'])
        complete_indicator = "[DONE] " if is_complete else ""
        title = self.story['title']

        # Auto-scale: use smaller font for long titles
        full_title = complete_indicator + title
        if len(full_title) > 55:
            title_font = FONT_TINY
            max_len = 70
        elif len(full_title) > 45:
            title_font = FONT_TINY
            max_len = 60
        else:
            title_font = FONT_SMALL
            max_len = 50

        display_title = full_title[:max_len] + '...' if len(full_title) > max_len else full_title
        PixelText.render(surface, display_title, (CONTENT_MARGIN + 10, 25), title_font,
                        colors.ACCENT if is_complete else colors.TEXT_DIM)

        # Page number
        page_str = f"PAGE {self.current_page + 1} OF {len(self.pages)}"
        PixelText.render(surface, page_str, (WINDOW_WIDTH - CONTENT_MARGIN - 150, 25), FONT_SMALL, colors.TEXT_DIM)

        # Divider
        pygame.draw.line(surface, colors.TEXT_DIM, (CONTENT_MARGIN, 55), (WINDOW_WIDTH - CONTENT_MARGIN, 55), 2)

        # Render text page
        if self.current_page < len(self.pages):
            y = 75
            line_height = 26

            for line in self.pages[self.current_page]:
                PixelText.render(surface, line, (CONTENT_MARGIN + 20, y), FONT_BODY, colors.TEXT_DEFAULT)
                y += line_height

        # Navigation hints (subtle arrows on sides)
        if self.current_page > 0:
            PixelText.render(surface, "<", (20, WINDOW_HEIGHT // 2 - 50), FONT_LARGE, colors.TEXT_DIM)
        if self.current_page < len(self.pages) - 1:
            PixelText.render(surface, ">", (WINDOW_WIDTH - 35, WINDOW_HEIGHT // 2 - 50), FONT_LARGE, colors.TEXT_DIM)

        # Bottom HUD area - starts at y=480 (leaving 120px for HUD)
        hud_top = 480

        # HUD separator line
        pygame.draw.line(surface, colors.TEXT_DIM, (CONTENT_MARGIN, hud_top), (WINDOW_WIDTH - CONTENT_MARGIN, hud_top), 1)

        # Progress bar
        progress = (self.current_page + 1) / len(self.pages)
        bar_y = hud_top + 15
        bar_width = WINDOW_WIDTH - CONTENT_MARGIN * 2
        pygame.draw.rect(surface, colors.TEXT_DIM, (CONTENT_MARGIN, bar_y, bar_width, 6), border_radius=3)
        pygame.draw.rect(surface, colors.ACCENT, (CONTENT_MARGIN, bar_y, int(bar_width * progress), 6), border_radius=3)

        # Page indicator with bookmark status
        is_bookmarked = self.app.progress.is_bookmarked(self.origin, self.story['slug'], self.current_page)
        all_bookmarks = self.app.progress.get_bookmarks(self.origin, self.story['slug'])

        # Page number
        page_text = f"PAGE {self.current_page + 1} / {len(self.pages)}"
        PixelText.render(surface, page_text, (WINDOW_WIDTH - CONTENT_MARGIN - 120, hud_top + 30), FONT_TINY,
                        colors.TEXT_DIM)

        # Prominent bookmark indicator
        if is_bookmarked:
            PixelText.render(surface, "[BOOKMARKED]", (WINDOW_WIDTH - CONTENT_MARGIN - 120, hud_top + 42), FONT_TINY,
                            colors.ACCENT)
        elif all_bookmarks:
            # Show bookmark count if there are bookmarks but not on this page
            PixelText.render(surface, f"[{len(all_bookmarks)} saved]", (WINDOW_WIDTH - CONTENT_MARGIN - 120, hud_top + 42), FONT_TINY,
                            colors.TEXT_DIM)

        # Audio status bar (if audio available)
        if self.has_audio:
            pos = self.app.audio.get_position()
            pos_str = f"{int(pos // 60)}:{int(pos % 60):02d}"
            vol = int(self.app.audio.get_volume() * 100)

            # Audio indicator
            if self.app.audio.is_playing:
                indicator = "[>]"
            elif self.app.audio.is_paused:
                indicator = "[||]"
            else:
                indicator = "[.]"

            audio_text = f"{indicator} {pos_str}  [< >] Skip 10s  Vol: {vol}% [-/+]  [Space] Play/Pause"
            PixelText.render(surface, audio_text, (CONTENT_MARGIN + 10, hud_top + 30), FONT_TINY, colors.ACCENT)

        # Help text - show bookmark controls prominently
        help_text = "[B] Bookmark  [ Prev ] Next Bookmark  [C] Done  [Esc] Back"
        PixelText.render(surface, help_text, (WINDOW_WIDTH // 2, hud_top + 54),
                        FONT_TINY, colors.TEXT_DIM, center=True)

        # Page turn animation overlay
        if self.animating:
            elapsed = pygame.time.get_ticks() - self.anim_start_time
            if elapsed >= self.anim_duration:
                self.animating = False
            else:
                # Animation progress 0.0 to 1.0
                progress = elapsed / self.anim_duration
                # Ease out curve for natural feel
                eased = 1.0 - (1.0 - progress) ** 2

                content_top = 55
                content_height = hud_top - content_top
                content_width = WINDOW_WIDTH - CONTENT_MARGIN * 2

                # Render old page to a surface
                old_page_surf = self._render_page_to_surface(self.anim_from_page, content_width, content_height)

                if self.anim_direction > 0:
                    # Turning forward - old page slides left, revealing new page
                    slide_offset = int(content_width * eased)
                    # Draw old page sliding left
                    surface.blit(old_page_surf, (CONTENT_MARGIN - slide_offset, content_top))
                    # Draw shadow on the edge of the old page
                    shadow_width = 40
                    edge_x = CONTENT_MARGIN + content_width - slide_offset
                    for i in range(shadow_width):
                        alpha = int(100 * (1.0 - i / shadow_width))
                        shadow_surf = pygame.Surface((2, content_height), pygame.SRCALPHA)
                        shadow_surf.fill((0, 0, 0, alpha))
                        surface.blit(shadow_surf, (edge_x + i, content_top))
                    # Highlight on leading edge
                    highlight_surf = pygame.Surface((3, content_height), pygame.SRCALPHA)
                    highlight_surf.fill((255, 255, 255, 80))
                    surface.blit(highlight_surf, (edge_x - 2, content_top))
                else:
                    # Turning backward - old page slides right, revealing new page
                    slide_offset = int(content_width * eased)
                    # Draw old page sliding right
                    surface.blit(old_page_surf, (CONTENT_MARGIN + slide_offset, content_top))
                    # Draw shadow on the edge of the old page
                    shadow_width = 40
                    edge_x = CONTENT_MARGIN + slide_offset
                    for i in range(shadow_width):
                        alpha = int(100 * (1.0 - i / shadow_width))
                        shadow_surf = pygame.Surface((2, content_height), pygame.SRCALPHA)
                        shadow_surf.fill((0, 0, 0, alpha))
                        surface.blit(shadow_surf, (edge_x - i - 2, content_top))
                    # Highlight on leading edge
                    highlight_surf = pygame.Surface((3, content_height), pygame.SRCALPHA)
                    highlight_surf.fill((255, 255, 255, 80))
                    surface.blit(highlight_surf, (edge_x, content_top))


class BibleReadingScreen:
    """Reading screen for Bible books (entire book, not per-chapter)."""

    def __init__(self, app, book_name: str):
        self.app = app
        self.book_name = book_name
        self.origin = 'bible'  # For bookmark compatibility
        self.slug = book_name  # Unique ID for bookmarks (per book)
        self.audio_slug = f"bible_audio_{book_name}"  # Slug for audio position
        self.text = self.app.bible.get_book_text(book_name)
        self.pages = self._paginate()

        # Restore saved page position (super-bookmark)
        saved_page = self.app.progress.get_page(self.origin, self.slug)
        self.current_page = min(saved_page, len(self.pages) - 1)
        self.saved_page = self.current_page  # Track what position we restored to
        self.saved_audio_pos = 0.0

        # Check for audio (prefers extracted MP3, falls back to MP4)
        self.audio_file = self.app.bible.get_audio_path(book_name)
        self.has_audio = self.audio_file is not None

        if self.has_audio:
            # Load audio and restore saved position
            self.app.audio.load(self.audio_file)
            saved_pos = self.app.progress.get_audio_position(self.origin, self.audio_slug)
            if saved_pos > 0:
                self.app.audio._start_offset = saved_pos
                self.saved_audio_pos = saved_pos

        # Page turn animation state
        self.animating = False
        self.anim_start_time = 0
        self.anim_duration = 0
        self.anim_direction = 1
        self.anim_from_page = 0

    def _paginate(self, line_width: int = 70) -> List[List[str]]:
        """Split text into pages."""
        pages = []
        lines_per_page = 15

        if not self.text:
            return [['']]

        # Split into paragraphs (verses)
        paragraphs = self.text.split('\n\n')

        all_lines = []
        for para in paragraphs:
            wrapped = textwrap.wrap(para, width=line_width)
            all_lines.extend(wrapped)
            all_lines.append('')

        # Split into pages
        current_page = []
        for line in all_lines:
            current_page.append(line)
            if len(current_page) >= lines_per_page:
                pages.append(current_page)
                current_page = []

        if current_page:
            pages.append(current_page)

        return pages if pages else [['']]

    def _start_page_turn(self, direction: int):
        """Start a page turn animation."""
        duration = sounds.play_page_turn()
        self.animating = True
        self.anim_start_time = pygame.time.get_ticks()
        self.anim_duration = duration
        self.anim_direction = direction
        self.anim_from_page = self.current_page - direction

    def _render_page_to_surface(self, page_num: int, content_width: int, content_height: int) -> pygame.Surface:
        """Render a specific page's content to an off-screen surface."""
        surf = pygame.Surface((content_width, content_height))
        surf.fill(colors.SCREEN_BG)

        if page_num < 0 or page_num >= len(self.pages):
            return surf

        y = 20
        line_height = 26
        for line in self.pages[page_num]:
            PixelText.render(surf, line, (20, y), FONT_BODY, colors.TEXT_DEFAULT)
            y += line_height

        return surf

    def handle_event(self, event):
        if event.type == pygame.KEYDOWN:
            # Block input during animation
            if self.animating:
                return

            if event.key in (pygame.K_RIGHT, pygame.K_z):
                if self.current_page < len(self.pages) - 1:
                    self.current_page += 1
                    self._start_page_turn(1)
                    self.app.progress.increment_pages_read()
            elif event.key in (pygame.K_LEFT,):
                if self.current_page > 0:
                    self.current_page -= 1
                    self._start_page_turn(-1)
            elif event.key in (pygame.K_ESCAPE, pygame.K_x, pygame.K_BACKSPACE):
                sounds.play_book_close()
                # Save super-bookmark: page + audio position
                self.app.progress.set_page(self.origin, self.slug, self.current_page)
                if self.has_audio:
                    pos = self.app.audio.get_position()
                    self.app.progress.set_audio_position(self.origin, self.audio_slug, pos)
                self.app.audio.stop()
                self.app.close_bible()
            elif event.key == pygame.K_t:
                colors.next_theme()
            elif event.key == pygame.K_HOME:
                self.current_page = 0
            elif event.key == pygame.K_END:
                self.current_page = len(self.pages) - 1
            # Audio controls (Space = play/pause)
            elif event.key == pygame.K_SPACE:
                if self.has_audio:
                    self.app.audio.toggle()
                else:
                    # No audio - use space for page turn
                    if self.current_page < len(self.pages) - 1:
                        self.current_page += 1
                        self._start_page_turn(1)
                        self.app.progress.increment_pages_read()
            elif event.key == pygame.K_COMMA:  # < key - rewind
                if self.has_audio:
                    self.app.audio.seek(-10)
            elif event.key == pygame.K_PERIOD:  # > key - forward
                if self.has_audio:
                    self.app.audio.seek(10)
            elif event.key == pygame.K_MINUS:
                self.app.audio.set_volume(self.app.audio.get_volume() - 0.1)
            elif event.key == pygame.K_EQUALS:  # + key
                self.app.audio.set_volume(self.app.audio.get_volume() + 0.1)
            elif event.key == pygame.K_r:
                # Resume: jump to saved position (page + audio)
                saved_page = self.app.progress.get_page(self.origin, self.slug)
                saved_audio = self.app.progress.get_audio_position(self.origin, self.audio_slug)
                if saved_page > 0 or saved_audio > 0:
                    sounds.play_select()
                    # Jump to saved page
                    if saved_page != self.current_page:
                        old_page = self.current_page
                        self.current_page = min(saved_page, len(self.pages) - 1)
                        self._start_page_turn(1 if self.current_page > old_page else -1)
                    # Seek audio to saved position
                    if self.has_audio and saved_audio > 0:
                        # Need to seek to absolute position
                        current_pos = self.app.audio.get_position()
                        delta = saved_audio - current_pos
                        if abs(delta) > 1:  # Only seek if more than 1 second difference
                            self.app.audio.seek(delta)
                else:
                    sounds.play_back()  # No saved position
            elif event.key == pygame.K_b:
                # Toggle bookmark on current page
                if self.app.progress.is_bookmarked(self.origin, self.slug, self.current_page):
                    self.app.progress.remove_bookmark(self.origin, self.slug, self.current_page)
                    sounds.play_back()
                else:
                    self.app.progress.add_bookmark(self.origin, self.slug, self.current_page)
                    sounds.play_select()
            elif event.key == pygame.K_LEFTBRACKET:
                # Jump to previous bookmark
                bookmarks = self.app.progress.get_bookmarks(self.origin, self.slug)
                prev_bookmarks = [b for b in bookmarks if b < self.current_page]
                if prev_bookmarks:
                    old_page = self.current_page
                    self.current_page = max(prev_bookmarks)
                    self._start_page_turn(-1 if self.current_page < old_page else 1)
                    self.app.progress.set_page(self.origin, self.slug, self.current_page)
            elif event.key == pygame.K_RIGHTBRACKET:
                # Jump to next bookmark
                bookmarks = self.app.progress.get_bookmarks(self.origin, self.slug)
                next_bookmarks = [b for b in bookmarks if b > self.current_page]
                if next_bookmarks:
                    old_page = self.current_page
                    self.current_page = min(next_bookmarks)
                    self._start_page_turn(1 if self.current_page > old_page else -1)
                    self.app.progress.set_page(self.origin, self.slug, self.current_page)

    def draw(self, surface):
        DecorativeFrame.draw(surface)

        # Title bar - same layout as ReadingScreen
        title = self.book_name
        if self.has_audio:
            title = "[A] " + title
        PixelText.render(surface, title, (CONTENT_MARGIN + 10, 25), FONT_SMALL,
                        colors.ACCENT if self.has_audio else colors.TEXT_DIM)

        # Page number in header
        page_str = f"PAGE {self.current_page + 1} OF {len(self.pages)}"
        PixelText.render(surface, page_str, (WINDOW_WIDTH - CONTENT_MARGIN - 150, 25),
                        FONT_SMALL, colors.TEXT_DIM)

        # Divider
        pygame.draw.line(surface, colors.TEXT_DIM,
                        (CONTENT_MARGIN, 55), (WINDOW_WIDTH - CONTENT_MARGIN, 55), 2)

        # Render text
        if self.current_page < len(self.pages):
            y = 75
            line_height = 26

            for line in self.pages[self.current_page]:
                PixelText.render(surface, line, (CONTENT_MARGIN + 20, y),
                               FONT_BODY, colors.TEXT_DEFAULT)
                y += line_height

        # Navigation hints
        if self.current_page > 0:
            PixelText.render(surface, "<", (20, WINDOW_HEIGHT // 2 - 50),
                           FONT_LARGE, colors.TEXT_DIM)
        if self.current_page < len(self.pages) - 1:
            PixelText.render(surface, ">", (WINDOW_WIDTH - 35, WINDOW_HEIGHT // 2 - 50),
                           FONT_LARGE, colors.TEXT_DIM)

        # Bottom HUD area - same layout as ReadingScreen
        hud_top = 480

        # HUD separator line
        pygame.draw.line(surface, colors.TEXT_DIM,
                        (CONTENT_MARGIN, hud_top), (WINDOW_WIDTH - CONTENT_MARGIN, hud_top), 1)

        # Progress bar
        progress = (self.current_page + 1) / len(self.pages)
        bar_y = hud_top + 15
        bar_width = WINDOW_WIDTH - CONTENT_MARGIN * 2
        pygame.draw.rect(surface, colors.TEXT_DIM,
                        (CONTENT_MARGIN, bar_y, bar_width, 6), border_radius=3)
        pygame.draw.rect(surface, colors.ACCENT,
                        (CONTENT_MARGIN, bar_y, int(bar_width * progress), 6), border_radius=3)

        # Page indicator with bookmark status (same as ReadingScreen)
        is_bookmarked = self.app.progress.is_bookmarked(self.origin, self.slug, self.current_page)
        all_bookmarks = self.app.progress.get_bookmarks(self.origin, self.slug)

        # Page number
        page_text = f"PAGE {self.current_page + 1} / {len(self.pages)}"
        PixelText.render(surface, page_text, (WINDOW_WIDTH - CONTENT_MARGIN - 120, hud_top + 30), FONT_TINY,
                        colors.TEXT_DIM)

        # Prominent bookmark indicator
        if is_bookmarked:
            PixelText.render(surface, "[BOOKMARKED]", (WINDOW_WIDTH - CONTENT_MARGIN - 120, hud_top + 42), FONT_TINY,
                            colors.ACCENT)
        elif all_bookmarks:
            # Show bookmark count if there are bookmarks but not on this page
            PixelText.render(surface, f"[{len(all_bookmarks)} saved]", (WINDOW_WIDTH - CONTENT_MARGIN - 120, hud_top + 42), FONT_TINY,
                            colors.TEXT_DIM)

        # Audio status (if available)
        if self.has_audio:
            pos = self.app.audio.get_position()
            pos_str = f"{int(pos // 60)}:{int(pos % 60):02d}"
            vol = self.app.audio.get_volume()

            if self.app.audio.is_playing:
                indicator = "[>]"
            elif self.app.audio.is_paused:
                indicator = "[||]"
            else:
                indicator = "[.]"

            audio_text = f"{indicator} {pos_str}  [< >] Skip 10s  Vol: {vol}% [-/+]  [Space] Play/Pause"
            PixelText.render(surface, audio_text, (CONTENT_MARGIN + 10, hud_top + 30), FONT_TINY, colors.ACCENT)

        # Help text - show bookmark controls prominently (same as ReadingScreen)
        help_text = "[B] Bookmark  [ Prev ] Next Bookmark  [Esc] Back"
        PixelText.render(surface, help_text, (WINDOW_WIDTH // 2, hud_top + 54),
                        FONT_TINY, colors.TEXT_DIM, center=True)

        # Page turn animation overlay
        if self.animating:
            elapsed = pygame.time.get_ticks() - self.anim_start_time
            if elapsed >= self.anim_duration:
                self.animating = False
            else:
                progress = elapsed / self.anim_duration
                eased = 1.0 - (1.0 - progress) ** 2
                content_top = 55
                content_height = hud_top - content_top
                content_width = WINDOW_WIDTH - CONTENT_MARGIN * 2

                # Render old page to a surface
                old_page_surf = self._render_page_to_surface(self.anim_from_page, content_width, content_height)

                if self.anim_direction > 0:
                    # Turning forward - old page slides left, revealing new page
                    slide_offset = int(content_width * eased)
                    surface.blit(old_page_surf, (CONTENT_MARGIN - slide_offset, content_top))
                    shadow_width = 40
                    edge_x = CONTENT_MARGIN + content_width - slide_offset
                    for i in range(shadow_width):
                        alpha = int(100 * (1.0 - i / shadow_width))
                        shadow_surf = pygame.Surface((2, content_height), pygame.SRCALPHA)
                        shadow_surf.fill((0, 0, 0, alpha))
                        surface.blit(shadow_surf, (edge_x + i, content_top))
                    highlight_surf = pygame.Surface((3, content_height), pygame.SRCALPHA)
                    highlight_surf.fill((255, 255, 255, 80))
                    surface.blit(highlight_surf, (edge_x - 2, content_top))
                else:
                    # Turning backward - old page slides right, revealing new page
                    slide_offset = int(content_width * eased)
                    surface.blit(old_page_surf, (CONTENT_MARGIN + slide_offset, content_top))
                    shadow_width = 40
                    edge_x = CONTENT_MARGIN + slide_offset
                    for i in range(shadow_width):
                        alpha = int(100 * (1.0 - i / shadow_width))
                        shadow_surf = pygame.Surface((2, content_height), pygame.SRCALPHA)
                        shadow_surf.fill((0, 0, 0, alpha))
                        surface.blit(shadow_surf, (edge_x - i - 2, content_top))
                    highlight_surf = pygame.Surface((3, content_height), pygame.SRCALPHA)
                    highlight_surf.fill((255, 255, 255, 80))
                    surface.blit(highlight_surf, (edge_x, content_top))


class SettingsScreen:
    """Settings screen for toggling features."""

    def __init__(self, app):
        self.app = app
        self.selected_index = 0
        self.settings = [
            {
                'key': 'theme',
                'label': 'Theme',
                'options': ['parchment', 'vellum', 'night', 'sepia_dark', 'manuscript'],
                'desc': 'Color scheme for reading'
            },
            {
                'key': 'font_size',
                'label': 'Font Size',
                'options': ['small', 'medium', 'large'],
                'desc': 'Text size in reading mode'
            },
        ]

    def handle_event(self, event):
        if event.type == pygame.KEYDOWN:
            if event.key == pygame.K_UP:
                sounds.play_menu_move()
                self.selected_index = max(0, self.selected_index - 1)
            elif event.key == pygame.K_DOWN:
                sounds.play_menu_move()
                self.selected_index = min(len(self.settings) - 1, self.selected_index + 1)
            elif event.key in (pygame.K_LEFT, pygame.K_RIGHT):
                sounds.play_menu_move()
                setting = self.settings[self.selected_index]
                current = self.app.progress.get_setting(setting['key'])
                options = setting['options']
                idx = options.index(current) if current in options else 0
                if event.key == pygame.K_RIGHT:
                    idx = (idx + 1) % len(options)
                else:
                    idx = (idx - 1) % len(options)
                self.app.progress.set_setting(setting['key'], options[idx])
                # Apply theme immediately
                if setting['key'] == 'theme':
                    colors.set_theme(options[idx])
            elif event.key in (pygame.K_ESCAPE, pygame.K_x, pygame.K_BACKSPACE, pygame.K_s):
                sounds.play_back()
                self.app.close_settings()

    def draw(self, surface):
        DecorativeFrame.draw(surface)

        # Header
        PixelText.render(surface, "Settings", (WINDOW_WIDTH // 2, 40),
                        FONT_TITLE, colors.TEXT_DEFAULT, center=True)

        # Divider
        pygame.draw.line(surface, colors.TEXT_DIM,
                        (CONTENT_MARGIN, 75), (WINDOW_WIDTH - CONTENT_MARGIN, 75), 2)

        # Settings list
        y = 120
        for i, setting in enumerate(self.settings):
            is_selected = i == self.selected_index
            current_value = self.app.progress.get_setting(setting['key'])

            # Selection highlight
            if is_selected:
                pygame.draw.rect(surface, colors.TEXT_DEFAULT,
                               (CONTENT_MARGIN - 5, y - 8, WINDOW_WIDTH - CONTENT_MARGIN * 2 + 10, 60),
                               border_radius=4)

            text_color = colors.SCREEN_BG if is_selected else colors.TEXT_DEFAULT
            desc_color = colors.SHELL_LIGHT if is_selected else colors.TEXT_DIM

            # Setting name
            PixelText.render(surface, setting['label'], (CONTENT_MARGIN + 15, y), FONT_LARGE, text_color)
            PixelText.render(surface, setting['desc'], (CONTENT_MARGIN + 15, y + 24), FONT_TINY, desc_color)

            # Current value with arrows
            value_str = f"< {current_value.upper()} >"
            PixelText.render(surface, value_str, (WINDOW_WIDTH - CONTENT_MARGIN - 150, y + 10),
                           FONT_MEDIUM, text_color)

            y += 80

        # Stats section
        y += 20
        pygame.draw.line(surface, colors.TEXT_DIM,
                        (CONTENT_MARGIN, y), (WINDOW_WIDTH - CONTENT_MARGIN, y), 1)
        y += 20

        PixelText.render(surface, "Reading Statistics", (CONTENT_MARGIN + 15, y), FONT_MEDIUM, colors.TEXT_DIM)
        y += 30

        # Reading stats
        stats = self.app.progress.stats
        pages_read = stats.get('pages_read', 0)
        stories_opened = stats.get('stories_opened', 0)
        completed = len(self.app.progress.completions)
        favorites = len(self.app.progress.favorites)
        total_bookmarks = sum(len(b) for b in self.app.progress.bookmarks.values())

        col1_x = CONTENT_MARGIN + 15
        col2_x = WINDOW_WIDTH // 2 + 20

        PixelText.render(surface, f"Stories Opened: {stories_opened}", (col1_x, y),
                        FONT_SMALL, colors.TEXT_DEFAULT)
        PixelText.render(surface, f"Stories Completed: {completed}", (col2_x, y),
                        FONT_SMALL, colors.TEXT_DEFAULT)
        y += 25
        PixelText.render(surface, f"Pages Read: {pages_read}", (col1_x, y),
                        FONT_SMALL, colors.TEXT_DEFAULT)
        PixelText.render(surface, f"Favorites: {favorites}", (col2_x, y),
                        FONT_SMALL, colors.TEXT_DEFAULT)
        y += 25
        PixelText.render(surface, f"Bookmarks: {total_bookmarks}", (col1_x, y),
                        FONT_SMALL, colors.TEXT_DEFAULT)

        # Media stats
        media_stats = self.app.media.get_stats()
        y += 35
        PixelText.render(surface, "Media Library", (CONTENT_MARGIN + 15, y), FONT_MEDIUM, colors.TEXT_DIM)
        y += 25
        PixelText.render(surface, f"Audio Files: {media_stats['audio_files']}", (col1_x, y),
                        FONT_SMALL, colors.TEXT_DEFAULT)

        # Help
        PixelText.render(surface, "[Up/Down] Select   [Left/Right] Change   [S/Esc] Back",
                        (WINDOW_WIDTH // 2, WINDOW_HEIGHT - 30),
                        FONT_SMALL, colors.TEXT_DIM, center=True)


class FairytaleReader:
    """Main application."""

    def __init__(self):
        self.screen = pygame.display.set_mode((WINDOW_WIDTH, WINDOW_HEIGHT))
        pygame.display.set_caption("Fairytale Reader")

        self.progress = ProgressManager()
        self.audio = AudioPlayer(CACHE_DIR)
        self.media = MediaManager(AUDIO_DIR)
        self.bible = BibleLoader(BIBLE_TEXT, BIBLE_VIDEO_DIR, CACHE_DIR)
        self.library = LibraryScreen(self)
        self.reading_screen = None
        self.settings_screen = None
        self.bible_screen = None
        self.current_screen = 'library'

        # Apply saved theme on startup
        saved_theme = self.progress.get_setting('theme')
        if saved_theme:
            colors.set_theme(saved_theme)

        self.clock = pygame.time.Clock()
        self.running = True

    def show_settings(self):
        """Show the settings screen."""
        self.settings_screen = SettingsScreen(self)
        self.current_screen = 'settings'

    def close_settings(self):
        """Close the settings screen."""
        self.settings_screen = None
        self.current_screen = 'library'

    def open_story(self, origin: str, story: dict, with_audio: bool = True):
        """Open a story with specified options."""
        sounds.play_book_open()
        self.progress.increment_stories_opened()
        self.reading_screen = ReadingScreen(self, origin, story, with_audio=with_audio)
        self.current_screen = 'reading'

    def close_story(self):
        sounds.play_book_close()
        self.reading_screen = None
        self.current_screen = 'library'

    def open_bible_book(self, book_name: str):
        """Open a Bible book for reading (entire book, all chapters)."""
        sounds.play_book_open()
        self.progress.increment_stories_opened()
        self.bible_screen = BibleReadingScreen(self, book_name)
        self.current_screen = 'bible'

    def close_bible(self):
        """Close Bible reading screen."""
        self.bible_screen = None
        self.current_screen = 'library'

    def run(self):
        while self.running:
            for event in pygame.event.get():
                if event.type == pygame.QUIT:
                    self.running = False
                elif event.type == pygame.KEYDOWN:
                    if event.key == pygame.K_q:
                        self.running = False

                # Route events
                if self.current_screen == 'library':
                    self.library.handle_event(event)
                elif self.current_screen == 'reading':
                    self.reading_screen.handle_event(event)
                elif self.current_screen == 'settings':
                    self.settings_screen.handle_event(event)
                elif self.current_screen == 'bible':
                    self.bible_screen.handle_event(event)

            # Draw directly to screen
            if self.current_screen == 'library':
                self.library.draw(self.screen)
            elif self.current_screen == 'reading':
                self.reading_screen.draw(self.screen)
            elif self.current_screen == 'settings':
                self.settings_screen.draw(self.screen)
            elif self.current_screen == 'bible':
                self.bible_screen.draw(self.screen)

            pygame.display.flip()
            self.clock.tick(60)

        pygame.quit()


def main():
    app = FairytaleReader()
    app.run()


if __name__ == '__main__':
    main()
