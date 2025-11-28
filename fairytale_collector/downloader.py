"""Download fairytale collections from Project Gutenberg and other sources."""

import requests
import time
from pathlib import Path
from typing import Optional
from bs4 import BeautifulSoup

from .config import (
    GUTENBERG_TEXT_URL,
    GUTENBERG_HTML_URL,
    GUTENBERG_BASE_URL,
    CACHE_DIR,
    GutenbergSource,
    ensure_directories,
)


class DownloadError(Exception):
    """Raised when a download fails."""
    pass


class GutenbergDownloader:
    """Downloads books and images from Project Gutenberg."""

    def __init__(self, cache_dir: Optional[Path] = None):
        self.cache_dir = cache_dir or CACHE_DIR
        ensure_directories()
        self.session = requests.Session()
        self.session.headers.update({
            "User-Agent": "FairytaleCollector/0.1 (Educational project)"
        })

    def get_text(self, source: GutenbergSource, force_download: bool = False) -> str:
        """Download or retrieve cached plain text of a book."""
        cache_file = self.cache_dir / f"gutenberg_{source.book_id}.txt"

        if cache_file.exists() and not force_download:
            return cache_file.read_text(encoding="utf-8")

        url = GUTENBERG_TEXT_URL.format(book_id=source.book_id)
        response = self._fetch(url)
        text = response.text

        # Cache the result
        cache_file.write_text(text, encoding="utf-8")
        return text

    def get_html(self, source: GutenbergSource, force_download: bool = False) -> str:
        """Download or retrieve cached HTML version (with images) of a book."""
        cache_file = self.cache_dir / f"gutenberg_{source.book_id}.html"

        if cache_file.exists() and not force_download:
            return cache_file.read_text(encoding="utf-8")

        url = GUTENBERG_HTML_URL.format(book_id=source.book_id)
        response = self._fetch(url)
        html = response.text

        # Cache the result
        cache_file.write_text(html, encoding="utf-8")
        return html

    def get_images(
        self,
        source: GutenbergSource,
        output_dir: Path,
        force_download: bool = False
    ) -> list[dict]:
        """Download all images from a Gutenberg book.

        Returns a list of dicts with image info: {filename, url, alt_text}
        """
        html = self.get_html(source, force_download)
        soup = BeautifulSoup(html, "lxml")
        images = []

        # Find all images
        for img in soup.find_all("img"):
            src = img.get("src", "")
            if not src:
                continue

            # Build full URL
            if src.startswith("http"):
                img_url = src
            else:
                img_url = f"{GUTENBERG_BASE_URL}/cache/epub/{source.book_id}/{src}"

            filename = Path(src).name
            output_path = output_dir / filename

            # Download if not exists
            if not output_path.exists() or force_download:
                try:
                    img_response = self._fetch(img_url)
                    output_path.write_bytes(img_response.content)
                except DownloadError:
                    continue

            images.append({
                "filename": filename,
                "url": img_url,
                "alt_text": img.get("alt", ""),
                "local_path": str(output_path)
            })

        return images

    def _fetch(self, url: str, retries: int = 3) -> requests.Response:
        """Fetch a URL with retries and rate limiting."""
        for attempt in range(retries):
            try:
                response = self.session.get(url, timeout=30)
                response.raise_for_status()
                # Be nice to Gutenberg servers
                time.sleep(1)
                return response
            except requests.RequestException as e:
                if attempt == retries - 1:
                    raise DownloadError(f"Failed to download {url}: {e}")
                time.sleep(2 ** attempt)  # Exponential backoff

        raise DownloadError(f"Failed to download {url} after {retries} attempts")


def download_collection(source: GutenbergSource, include_images: bool = True) -> dict:
    """Download a complete fairytale collection.

    Returns a dict with:
        - text: The plain text content
        - html: The HTML content (if available)
        - images: List of downloaded images (if include_images=True)
    """
    downloader = GutenbergDownloader()

    result = {
        "source": source,
        "text": downloader.get_text(source),
        "html": None,
        "images": []
    }

    if include_images:
        try:
            result["html"] = downloader.get_html(source)
            images_dir = CACHE_DIR / f"images_{source.book_id}"
            images_dir.mkdir(exist_ok=True)
            result["images"] = downloader.get_images(source, images_dir)
        except DownloadError:
            pass  # Images are optional

    return result
