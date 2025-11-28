"""Output generators for various formats: Markdown, EPUB, HTML."""

import re
from pathlib import Path
from typing import Optional
from datetime import datetime

from .models import Story, Collection, StoryMetadata
from .config import OUTPUT_DIR, ensure_directories


# ============================================================================
# MARKDOWN OUTPUT
# ============================================================================

def story_to_markdown(story: Story, include_metadata: bool = True) -> str:
    """Convert a story to Markdown format."""
    lines = []

    # Title
    lines.append(f"# {story.metadata.title}")
    lines.append("")

    if include_metadata:
        lines.append(f"**Author:** {story.metadata.author}")
        lines.append(f"**Origin:** {story.metadata.origin.value.title()}")
        lines.append(f"**Reading Time:** {story.metadata.reading_time_minutes} min")
        lines.append(f"**Word Count:** {story.metadata.word_count:,}")
        if story.metadata.is_scary:
            lines.append("**Note:** This story contains some darker themes.")
        lines.append("")
        lines.append("---")
        lines.append("")

    # Story text - convert to proper paragraphs
    paragraphs = story.text.split('\n\n')
    for para in paragraphs:
        cleaned = ' '.join(para.split())
        if cleaned:
            lines.append(cleaned)
            lines.append("")

    # Footer
    lines.append("---")
    lines.append("")
    lines.append(f"*Source: [{story.metadata.source_url}]({story.metadata.source_url})*")

    return '\n'.join(lines)


def save_story_markdown(story: Story, output_dir: Optional[Path] = None) -> Path:
    """Save a story as a Markdown file in the proper directory structure."""
    ensure_directories()
    base_dir = output_dir or OUTPUT_DIR

    # Create directory structure: /origin/story-slug/
    story_dir = base_dir / story.metadata.origin.value / story.metadata.slug
    story_dir.mkdir(parents=True, exist_ok=True)

    # Save the markdown
    md_path = story_dir / "story.md"
    md_content = story_to_markdown(story)
    md_path.write_text(md_content, encoding="utf-8")

    # Save metadata
    metadata_path = story_dir / "metadata.json"
    story.metadata.save(metadata_path)

    # Create illustrations directory
    (story_dir / "illustrations").mkdir(exist_ok=True)

    return story_dir


def save_collection_markdown(collection: Collection, output_dir: Optional[Path] = None) -> Path:
    """Save all stories in a collection as Markdown files."""
    ensure_directories()
    base_dir = output_dir or OUTPUT_DIR

    # Ensure the origin directory exists
    origin_dir = base_dir / collection.origin.value
    origin_dir.mkdir(parents=True, exist_ok=True)

    for story in collection.stories:
        save_story_markdown(story, base_dir)

    # Create collection index
    index_path = origin_dir / "index.md"
    index_lines = [
        f"# {collection.name}",
        "",
        f"**Author:** {collection.author}",
        f"**Stories:** {len(collection.stories)}",
        "",
        "## Table of Contents",
        "",
    ]

    for story in sorted(collection.stories, key=lambda s: s.metadata.title):
        index_lines.append(f"- [{story.metadata.title}]({story.metadata.slug}/story.md) "
                          f"({story.metadata.reading_time_minutes} min)")

    index_path.write_text('\n'.join(index_lines), encoding="utf-8")

    return base_dir / collection.origin.value


# ============================================================================
# EPUB OUTPUT
# ============================================================================

def story_to_epub(story: Story, output_path: Path) -> Path:
    """Convert a story to EPUB format."""
    try:
        from ebooklib import epub
    except ImportError:
        raise ImportError("ebooklib is required for EPUB generation. Install with: pip install ebooklib")

    book = epub.EpubBook()

    # Set metadata
    book.set_identifier(f"fairytale-{story.metadata.slug}")
    book.set_title(story.metadata.title)
    book.set_language('en')
    book.add_author(story.metadata.author)

    # Add metadata
    book.add_metadata('DC', 'description', story.metadata.summary or f"A fairytale from {story.metadata.origin.value}")
    book.add_metadata('DC', 'source', story.metadata.source_url)

    # Create chapter
    chapter = epub.EpubHtml(title=story.metadata.title, file_name='story.xhtml', lang='en')

    # Convert text to HTML
    paragraphs = story.text.split('\n\n')
    html_paragraphs = [f"<p>{' '.join(p.split())}</p>" for p in paragraphs if p.strip()]
    html_content = f"""
    <html>
    <head><title>{story.metadata.title}</title></head>
    <body>
        <h1>{story.metadata.title}</h1>
        <p class="author">By {story.metadata.author}</p>
        {''.join(html_paragraphs)}
    </body>
    </html>
    """
    chapter.set_content(html_content)

    book.add_item(chapter)

    # Add navigation
    book.toc = [epub.Link('story.xhtml', story.metadata.title, 'story')]
    book.add_item(epub.EpubNcx())
    book.add_item(epub.EpubNav())

    # Add CSS
    style = '''
    body { font-family: Georgia, serif; line-height: 1.6; margin: 2em; }
    h1 { text-align: center; margin-bottom: 0.5em; }
    .author { text-align: center; font-style: italic; margin-bottom: 2em; }
    p { text-indent: 1.5em; margin: 0.5em 0; }
    '''
    nav_css = epub.EpubItem(uid="style", file_name="style.css", media_type="text/css", content=style)
    book.add_item(nav_css)
    chapter.add_link(href='style.css', rel='stylesheet', type='text/css')

    book.spine = ['nav', chapter]

    # Write EPUB
    output_path.parent.mkdir(parents=True, exist_ok=True)
    epub.write_epub(str(output_path), book, {})

    return output_path


def collection_to_epub(collection: Collection, output_path: Path) -> Path:
    """Convert an entire collection to a single EPUB."""
    try:
        from ebooklib import epub
    except ImportError:
        raise ImportError("ebooklib is required for EPUB generation.")

    book = epub.EpubBook()

    # Set metadata
    book.set_identifier(f"fairytale-collection-{collection.slug}")
    book.set_title(collection.name)
    book.set_language('en')
    book.add_author(collection.author)

    chapters = []
    toc = []

    for i, story in enumerate(collection.stories):
        chapter = epub.EpubHtml(
            title=story.metadata.title,
            file_name=f'story_{i:03d}.xhtml',
            lang='en'
        )

        paragraphs = story.text.split('\n\n')
        html_paragraphs = [f"<p>{' '.join(p.split())}</p>" for p in paragraphs if p.strip()]
        html_content = f"""
        <html>
        <head><title>{story.metadata.title}</title></head>
        <body>
            <h1>{story.metadata.title}</h1>
            {''.join(html_paragraphs)}
        </body>
        </html>
        """
        chapter.set_content(html_content)
        book.add_item(chapter)
        chapters.append(chapter)
        toc.append(epub.Link(f'story_{i:03d}.xhtml', story.metadata.title, f'story_{i}'))

    book.toc = toc
    book.add_item(epub.EpubNcx())
    book.add_item(epub.EpubNav())

    # Add CSS
    style = '''
    body { font-family: Georgia, serif; line-height: 1.6; margin: 2em; }
    h1 { text-align: center; margin-bottom: 1em; page-break-before: always; }
    p { text-indent: 1.5em; margin: 0.5em 0; }
    '''
    nav_css = epub.EpubItem(uid="style", file_name="style.css", media_type="text/css", content=style)
    book.add_item(nav_css)

    book.spine = ['nav'] + chapters

    output_path.parent.mkdir(parents=True, exist_ok=True)
    epub.write_epub(str(output_path), book, {})

    return output_path


# ============================================================================
# HTML OUTPUT
# ============================================================================

HTML_TEMPLATE = """<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>{title}</title>
    <style>
        :root {{
            --bg-color: #fdf6e3;
            --text-color: #333;
            --accent-color: #8b4513;
            --border-color: #ddd;
        }}

        @media (prefers-color-scheme: dark) {{
            :root {{
                --bg-color: #1a1a2e;
                --text-color: #eee;
                --accent-color: #d4a574;
                --border-color: #444;
            }}
        }}

        * {{
            box-sizing: border-box;
        }}

        body {{
            font-family: 'Palatino Linotype', 'Book Antiqua', Palatino, serif;
            line-height: 1.8;
            max-width: 750px;
            margin: 0 auto;
            padding: 2rem;
            background-color: var(--bg-color);
            color: var(--text-color);
        }}

        h1 {{
            text-align: center;
            font-size: 2.5rem;
            margin-bottom: 0.5rem;
            color: var(--accent-color);
            border-bottom: 2px solid var(--accent-color);
            padding-bottom: 1rem;
        }}

        .metadata {{
            text-align: center;
            font-style: italic;
            color: #666;
            margin-bottom: 2rem;
            padding-bottom: 1rem;
            border-bottom: 1px solid var(--border-color);
        }}

        .metadata span {{
            margin: 0 1rem;
        }}

        .story-content p {{
            text-indent: 2em;
            margin: 1em 0;
            text-align: justify;
        }}

        .story-content p:first-of-type {{
            text-indent: 0;
        }}

        .story-content p:first-of-type::first-letter {{
            font-size: 3.5em;
            float: left;
            line-height: 1;
            padding-right: 0.1em;
            color: var(--accent-color);
            font-weight: bold;
        }}

        footer {{
            margin-top: 3rem;
            padding-top: 1rem;
            border-top: 1px solid var(--border-color);
            font-size: 0.9rem;
            color: #666;
            text-align: center;
        }}

        footer a {{
            color: var(--accent-color);
        }}

        .warning {{
            background: #fff3cd;
            border: 1px solid #ffc107;
            padding: 0.5rem 1rem;
            border-radius: 4px;
            margin-bottom: 1rem;
            text-align: center;
        }}

        @media (prefers-color-scheme: dark) {{
            .warning {{
                background: #3d3200;
                border-color: #665200;
            }}
        }}
    </style>
</head>
<body>
    <article>
        <h1>{title}</h1>
        <div class="metadata">
            <span>By {author}</span>
            <span>{reading_time} min read</span>
            <span>{word_count} words</span>
        </div>
        {warning}
        <div class="story-content">
            {content}
        </div>
    </article>
    <footer>
        <p>Source: <a href="{source_url}">{source_url}</a></p>
        <p>Generated by Fairytale Collector</p>
    </footer>
</body>
</html>
"""

INDEX_HTML_TEMPLATE = """<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>{title} - Fairytale Collection</title>
    <style>
        :root {{
            --bg-color: #fdf6e3;
            --text-color: #333;
            --accent-color: #8b4513;
            --card-bg: #fff;
            --border-color: #ddd;
        }}

        @media (prefers-color-scheme: dark) {{
            :root {{
                --bg-color: #1a1a2e;
                --text-color: #eee;
                --accent-color: #d4a574;
                --card-bg: #252545;
                --border-color: #444;
            }}
        }}

        body {{
            font-family: 'Palatino Linotype', 'Book Antiqua', Palatino, serif;
            line-height: 1.6;
            max-width: 1000px;
            margin: 0 auto;
            padding: 2rem;
            background-color: var(--bg-color);
            color: var(--text-color);
        }}

        h1 {{
            text-align: center;
            color: var(--accent-color);
            border-bottom: 2px solid var(--accent-color);
            padding-bottom: 1rem;
        }}

        .subtitle {{
            text-align: center;
            font-style: italic;
            margin-bottom: 2rem;
        }}

        .story-grid {{
            display: grid;
            grid-template-columns: repeat(auto-fill, minmax(280px, 1fr));
            gap: 1.5rem;
        }}

        .story-card {{
            background: var(--card-bg);
            border: 1px solid var(--border-color);
            border-radius: 8px;
            padding: 1.5rem;
            text-decoration: none;
            color: var(--text-color);
            transition: transform 0.2s, box-shadow 0.2s;
        }}

        .story-card:hover {{
            transform: translateY(-3px);
            box-shadow: 0 4px 12px rgba(0,0,0,0.15);
        }}

        .story-card h3 {{
            margin: 0 0 0.5rem 0;
            color: var(--accent-color);
        }}

        .story-card .meta {{
            font-size: 0.85rem;
            color: #666;
        }}

        .story-card .warning {{
            font-size: 0.8rem;
            color: #d9534f;
            margin-top: 0.5rem;
        }}
    </style>
</head>
<body>
    <h1>{title}</h1>
    <p class="subtitle">By {author} &mdash; {story_count} stories</p>

    <div class="story-grid">
        {story_cards}
    </div>
</body>
</html>
"""


def story_to_html(story: Story) -> str:
    """Convert a story to styled HTML."""
    # Convert paragraphs to HTML
    paragraphs = story.text.split('\n\n')
    html_paragraphs = [f"<p>{' '.join(p.split())}</p>" for p in paragraphs if p.strip()]

    warning = ""
    if story.metadata.is_scary:
        warning = '<div class="warning">This story contains some darker themes.</div>'

    return HTML_TEMPLATE.format(
        title=story.metadata.title,
        author=story.metadata.author,
        reading_time=story.metadata.reading_time_minutes,
        word_count=f"{story.metadata.word_count:,}",
        warning=warning,
        content='\n'.join(html_paragraphs),
        source_url=story.metadata.source_url
    )


def save_story_html(story: Story, output_dir: Optional[Path] = None) -> Path:
    """Save a story as an HTML file."""
    ensure_directories()
    base_dir = output_dir or OUTPUT_DIR

    story_dir = base_dir / story.metadata.origin.value / story.metadata.slug
    story_dir.mkdir(parents=True, exist_ok=True)

    html_path = story_dir / "story.html"
    html_content = story_to_html(story)
    html_path.write_text(html_content, encoding="utf-8")

    return html_path


def save_collection_html(collection: Collection, output_dir: Optional[Path] = None) -> Path:
    """Save all stories in a collection as HTML files with an index."""
    ensure_directories()
    base_dir = output_dir or OUTPUT_DIR

    # Save individual stories
    for story in collection.stories:
        save_story_html(story, base_dir)

    # Create index page
    story_cards = []
    for story in sorted(collection.stories, key=lambda s: s.metadata.title):
        warning = '<div class="warning">Contains darker themes</div>' if story.metadata.is_scary else ''
        card = f'''
        <a href="{story.metadata.slug}/story.html" class="story-card">
            <h3>{story.metadata.title}</h3>
            <div class="meta">{story.metadata.reading_time_minutes} min read &mdash; {story.metadata.word_count:,} words</div>
            {warning}
        </a>
        '''
        story_cards.append(card)

    index_html = INDEX_HTML_TEMPLATE.format(
        title=collection.name,
        author=collection.author,
        story_count=len(collection.stories),
        story_cards='\n'.join(story_cards)
    )

    index_path = base_dir / collection.origin.value / "index.html"
    index_path.write_text(index_html, encoding="utf-8")

    return base_dir / collection.origin.value
