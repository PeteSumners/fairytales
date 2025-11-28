"""Command-line interface for the Fairytale Collector."""

import sys
import click
from pathlib import Path
from rich.console import Console
from rich.table import Table
from rich.progress import Progress, SpinnerColumn, TextColumn, BarColumn
from rich.panel import Panel

from . import __version__
from .config import GUTENBERG_SOURCES, OUTPUT_DIR, ensure_directories
from .downloader import GutenbergDownloader, download_collection
from .parser import parse_collection
from .outputs import (
    save_story_markdown,
    save_collection_markdown,
    save_story_html,
    save_collection_html,
    story_to_epub,
    collection_to_epub,
)
from .audio import AudioManager, prepare_story_for_tts
from .illustrations import IllustrationManager, STYLES
from .media_sources import (
    InternetArchiveDownloader,
    LIBRIVOX_SOURCES,
    VIDEO_SOURCES,
    list_available_audio,
    list_available_video,
)

# Use ASCII-safe console on Windows to avoid encoding issues
if sys.platform == "win32":
    console = Console(force_terminal=True, legacy_windows=True)
else:
    console = Console()


@click.group()
@click.version_option(version=__version__)
def cli():
    """Fairytale Collector - Download and package public domain fairytales."""
    ensure_directories()


@cli.command()
def sources():
    """List available fairytale sources."""
    table = Table(title="Available Fairytale Collections")
    table.add_column("ID", style="cyan")
    table.add_column("Title", style="green")
    table.add_column("Author", style="yellow")
    table.add_column("Origin", style="magenta")

    for source in GUTENBERG_SOURCES:
        table.add_row(
            str(source.book_id),
            source.title,
            source.author,
            source.origin
        )

    console.print(table)


@cli.command()
@click.argument("book_id", type=int)
@click.option("--include-images/--no-images", default=True, help="Download images")
def download(book_id: int, include_images: bool):
    """Download a fairytale collection from Project Gutenberg."""
    # Find the source
    source = None
    for s in GUTENBERG_SOURCES:
        if s.book_id == book_id:
            source = s
            break

    if not source:
        console.print(f"[red]Unknown book ID: {book_id}[/red]")
        console.print("Use 'fairytale sources' to see available collections.")
        return

    console.print(f"[cyan]Downloading {source.title}...[/cyan]")
    result = download_collection(source, include_images)
    console.print(f"[green]Downloaded {source.title}[/green]")
    if result["images"]:
        console.print(f"  Images: {len(result['images'])}")


@cli.command()
@click.argument("book_id", type=int)
@click.option("--format", "-f", "output_format",
              type=click.Choice(["markdown", "html", "epub", "all"]),
              default="all", help="Output format")
@click.option("--output", "-o", type=click.Path(), default=None,
              help="Output directory")
@click.option("--tts/--no-tts", default=True, help="Generate TTS-ready text")
def process(book_id: int, output_format: str, output: str, tts: bool):
    """Download and process a fairytale collection into readable formats."""
    # Find the source
    source = None
    for s in GUTENBERG_SOURCES:
        if s.book_id == book_id:
            source = s
            break

    if not source:
        console.print(f"[red]Unknown book ID: {book_id}[/red]")
        return

    output_dir = Path(output) if output else OUTPUT_DIR

    # Download
    console.print(f"[cyan]Downloading {source.title}...[/cyan]")
    result = download_collection(source, include_images=True)
    console.print("[green]Downloaded![/green]")

    # Parse
    console.print("[cyan]Parsing stories...[/cyan]")
    collection = parse_collection(result["text"], source)
    console.print(f"[green]Found {len(collection.stories)} stories![/green]")

    # Generate outputs
    if output_format in ["markdown", "all"]:
        console.print("[cyan]Generating Markdown...[/cyan]")
        save_collection_markdown(collection, output_dir)
        console.print("[green]Markdown complete![/green]")

    if output_format in ["html", "all"]:
        console.print("[cyan]Generating HTML...[/cyan]")
        save_collection_html(collection, output_dir)
        console.print("[green]HTML complete![/green]")

    if output_format in ["epub", "all"]:
        console.print("[cyan]Generating EPUB...[/cyan]")
        epub_path = output_dir / f"{collection.slug}.epub"
        collection_to_epub(collection, epub_path)
        console.print("[green]EPUB complete![/green]")

    if tts:
        console.print("[cyan]Generating TTS text...[/cyan]")
        audio_manager = AudioManager(output_dir)
        for story in collection.stories:
            audio_manager.save_tts_text(story)
        console.print("[green]TTS text complete![/green]")

    # Summary
    console.print()
    console.print(Panel(
        f"[green]Successfully processed {source.title}![/green]\n\n"
        f"Stories: {len(collection.stories)}\n"
        f"Output: {output_dir / collection.origin.value}",
        title="Complete"
    ))


@cli.command()
@click.argument("book_id", type=int)
def list_stories(book_id: int):
    """List all stories in a collection."""
    source = None
    for s in GUTENBERG_SOURCES:
        if s.book_id == book_id:
            source = s
            break

    if not source:
        console.print(f"[red]Unknown book ID: {book_id}[/red]")
        return

    with console.status("Loading collection..."):
        downloader = GutenbergDownloader()
        text = downloader.get_text(source)
        collection = parse_collection(text, source)

    table = Table(title=f"Stories in {source.title}")
    table.add_column("#", style="cyan", width=4)
    table.add_column("Title", style="green")
    table.add_column("Words", style="yellow", justify="right")
    table.add_column("Time", style="magenta", justify="right")
    table.add_column("Rating", style="blue")

    for i, story in enumerate(collection.stories, 1):
        scary = " [red]![/red]" if story.metadata.is_scary else ""
        table.add_row(
            str(i),
            story.metadata.title + scary,
            f"{story.metadata.word_count:,}",
            f"{story.metadata.reading_time_minutes} min",
            story.metadata.age_rating.value.replace("_", " ").title()
        )

    console.print(table)
    console.print(f"\n[dim]! = Contains darker themes[/dim]")


@cli.command()
@click.option("--origin", "-o", type=str, default=None,
              help="Filter by origin (grimm, andersen, lang, etc.)")
@click.option("--max-time", "-t", type=int, default=None,
              help="Maximum reading time in minutes")
@click.option("--safe/--all", default=False,
              help="Only show non-scary stories (bedtime mode)")
def browse(origin: str, max_time: int, safe: bool):
    """Browse all downloaded stories with filters."""
    output_dir = OUTPUT_DIR

    if not output_dir.exists():
        console.print("[yellow]No stories downloaded yet. Use 'fairytale process' first.[/yellow]")
        return

    stories = []

    # Find all metadata files
    for metadata_path in output_dir.rglob("metadata.json"):
        from .models import StoryMetadata
        try:
            metadata = StoryMetadata.load(metadata_path)

            # Apply filters
            if origin and metadata.origin.value != origin:
                continue
            if max_time and metadata.reading_time_minutes > max_time:
                continue
            if safe and metadata.is_scary:
                continue

            stories.append(metadata)
        except Exception:
            continue

    if not stories:
        console.print("[yellow]No stories match your criteria.[/yellow]")
        return

    table = Table(title="Available Stories")
    table.add_column("Title", style="green")
    table.add_column("Author", style="yellow")
    table.add_column("Origin", style="cyan")
    table.add_column("Time", style="magenta", justify="right")

    for story in sorted(stories, key=lambda s: s.title):
        table.add_row(
            story.title,
            story.author,
            story.origin.value.title(),
            f"{story.reading_time_minutes} min"
        )

    console.print(table)
    console.print(f"\n[dim]Total: {len(stories)} stories[/dim]")


@cli.command()
def styles():
    """List available illustration styles."""
    table = Table(title="Illustration Styles")
    table.add_column("Style", style="cyan")
    table.add_column("Description", style="green")

    for name, style in STYLES.items():
        table.add_row(
            name,
            f"{style.prompt_prefix}... {style.prompt_suffix}"
        )

    console.print(table)


@cli.command()
def bedtime():
    """Pick a random bedtime-appropriate story."""
    import random
    output_dir = OUTPUT_DIR

    if not output_dir.exists():
        console.print("[yellow]No stories downloaded yet.[/yellow]")
        return

    stories = []
    for metadata_path in output_dir.rglob("metadata.json"):
        from .models import StoryMetadata
        try:
            metadata = StoryMetadata.load(metadata_path)
            # Bedtime criteria: not scary, under 15 minutes
            if not metadata.is_scary and metadata.reading_time_minutes <= 15:
                stories.append((metadata, metadata_path.parent))
        except Exception:
            continue

    if not stories:
        console.print("[yellow]No suitable bedtime stories found.[/yellow]")
        return

    metadata, story_dir = random.choice(stories)

    console.print(Panel(
        f"[bold green]{metadata.title}[/bold green]\n\n"
        f"By {metadata.author}\n"
        f"Reading time: {metadata.reading_time_minutes} minutes\n\n"
        f"[dim]Story location: {story_dir / 'story.md'}[/dim]",
        title="Tonight's Bedtime Story"
    ))


@cli.command()
@click.argument("book_ids", type=int, nargs=-1)
@click.option("--all", "download_all", is_flag=True, help="Download all known collections")
def download_all_cmd(book_ids: tuple, download_all: bool):
    """Download multiple collections at once."""
    if download_all:
        sources = GUTENBERG_SOURCES
    elif book_ids:
        sources = [s for s in GUTENBERG_SOURCES if s.book_id in book_ids]
    else:
        console.print("[yellow]Specify book IDs or use --all[/yellow]")
        return

    for source in sources:
        console.print(f"[cyan]Processing {source.title}...[/cyan]")

        result = download_collection(source, include_images=True)
        collection = parse_collection(result["text"], source)
        save_collection_markdown(collection)
        save_collection_html(collection)

        epub_path = OUTPUT_DIR / f"{collection.slug}.epub"
        collection_to_epub(collection, epub_path)

        console.print(f"[green]{source.title} - {len(collection.stories)} stories[/green]")

    console.print(f"\n[green]All collections processed![/green]")


@cli.command()
def audio_sources():
    """List available LibriVox audiobook sources."""
    table = Table(title="Available Audio Sources (LibriVox via Internet Archive)")
    table.add_column("ID", style="cyan")
    table.add_column("Title", style="green")
    table.add_column("Collection", style="yellow")

    for source in LIBRIVOX_SOURCES:
        table.add_row(
            source.identifier,
            source.title,
            source.collection
        )

    console.print(table)
    console.print("\n[dim]Use 'fairytale download-audio <id>' to download[/dim]")


@cli.command()
def video_sources():
    """List available video sources from Internet Archive."""
    table = Table(title="Available Video Sources (Internet Archive)")
    table.add_column("ID", style="cyan")
    table.add_column("Title", style="green")
    table.add_column("Collection", style="yellow")

    for source in VIDEO_SOURCES:
        table.add_row(
            source.identifier,
            source.title,
            source.collection
        )

    console.print(table)
    console.print("\n[dim]Use 'fairytale download-video <id>' to download[/dim]")


@cli.command()
@click.argument("identifier", required=False)
@click.option("--all", "download_all", is_flag=True, help="Download all audio sources")
@click.option("--list-files", is_flag=True, help="Just list files without downloading")
def download_audio(identifier: str, download_all: bool, list_files: bool):
    """Download LibriVox audiobooks from Internet Archive."""
    downloader = InternetArchiveDownloader()

    if download_all:
        sources = LIBRIVOX_SOURCES
    elif identifier:
        sources = [s for s in LIBRIVOX_SOURCES if s.identifier == identifier]
        if not sources:
            console.print(f"[red]Unknown audio source: {identifier}[/red]")
            console.print("Use 'fairytale audio-sources' to see available sources.")
            return
    else:
        console.print("[yellow]Specify an identifier or use --all[/yellow]")
        return

    for source in sources:
        console.print(f"\n[cyan]{'='*50}[/cyan]")
        console.print(f"[bold]{source.title}[/bold]")
        console.print(f"[cyan]{'='*50}[/cyan]")

        files = downloader.get_item_files(source.identifier)
        audio_files = downloader.filter_audio_files(files)

        if list_files:
            console.print(f"\n[green]Found {len(audio_files)} audio files:[/green]")
            for f in audio_files:
                size_mb = int(f.get("size", 0)) / 1024 / 1024
                console.print(f"  - {f['name']} ({size_mb:.1f} MB)")
        else:
            console.print(f"[green]Downloading {len(audio_files)} files...[/green]")
            paths = downloader.download_audio_collection(source)
            console.print(f"[green]Downloaded {len(paths)} files to cache/audio/{source.identifier}/[/green]")


@cli.command()
@click.argument("identifier", required=False)
@click.option("--all", "download_all", is_flag=True, help="Download all video sources")
@click.option("--list-files", is_flag=True, help="Just list files without downloading")
def download_video(identifier: str, download_all: bool, list_files: bool):
    """Download video content from Internet Archive."""
    downloader = InternetArchiveDownloader()

    if download_all:
        sources = VIDEO_SOURCES
    elif identifier:
        sources = [s for s in VIDEO_SOURCES if s.identifier == identifier]
        if not sources:
            console.print(f"[red]Unknown video source: {identifier}[/red]")
            console.print("Use 'fairytale video-sources' to see available sources.")
            return
    else:
        console.print("[yellow]Specify an identifier or use --all[/yellow]")
        return

    for source in sources:
        console.print(f"\n[cyan]{'='*50}[/cyan]")
        console.print(f"[bold]{source.title}[/bold]")
        console.print(f"[cyan]{'='*50}[/cyan]")

        files = downloader.get_item_files(source.identifier)
        video_files = downloader.filter_video_files(files)

        if list_files:
            console.print(f"\n[green]Found {len(video_files)} video files:[/green]")
            for f in video_files:
                size_mb = int(f.get("size", 0)) / 1024 / 1024
                console.print(f"  - {f['name']} ({size_mb:.1f} MB)")
        else:
            console.print(f"[green]Downloading {len(video_files)} files...[/green]")
            paths = downloader.download_video_collection(source)
            console.print(f"[green]Downloaded {len(paths)} files to cache/video/{source.identifier}/[/green]")


def main():
    """Entry point for the CLI."""
    cli()


if __name__ == "__main__":
    main()
