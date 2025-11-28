"""Download audio/video from LibriVox and Internet Archive."""

import requests
import time
from pathlib import Path
from dataclasses import dataclass
from typing import Optional

from .config import CACHE_DIR


@dataclass
class AudioSource:
    """A LibriVox or Internet Archive audio source."""
    identifier: str  # Internet Archive identifier
    title: str
    collection: str  # grimm, andersen, etc.
    url: str
    format: str = "mp3"  # mp3, ogg, etc.


@dataclass
class VideoSource:
    """An Internet Archive video source."""
    identifier: str
    title: str
    collection: str
    url: str
    format: str = "mp4"


# Known LibriVox audiobook recordings (via Internet Archive)
LIBRIVOX_SOURCES = [
    AudioSource(
        identifier="grimms_english_librivox",
        title="Grimm's Fairy Tales (LibriVox)",
        collection="grimm",
        url="https://archive.org/details/grimms_english_librivox",
    ),
    AudioSource(
        identifier="grimm_fairy_tales_1202_librivox",
        title="Grimm's Fairy Tales Version 2 (LibriVox)",
        collection="grimm",
        url="https://archive.org/details/grimm_fairy_tales_1202_librivox",
    ),
    AudioSource(
        identifier="andersens_fairytales_librivox",
        title="Andersen's Fairy Tales (LibriVox)",
        collection="andersen",
        url="https://archive.org/details/andersens_fairytales_librivox",
    ),
    AudioSource(
        identifier="blue_fairy_book_0707_librivox",
        title="The Blue Fairy Book (LibriVox)",
        collection="lang",
        url="https://archive.org/details/blue_fairy_book_0707_librivox",
    ),
    AudioSource(
        identifier="red_fairy_book_0908_librivox",
        title="The Red Fairy Book (LibriVox)",
        collection="lang",
        url="https://archive.org/details/red_fairy_book_0908_librivox",
    ),
    AudioSource(
        identifier="green_fairy_book_1012_librivox",
        title="The Green Fairy Book (LibriVox)",
        collection="lang",
        url="https://archive.org/details/green_fairy_book_1012_librivox",
    ),
    AudioSource(
        identifier="orange_fairy_book_1005_librivox",
        title="The Orange Fairy Book (LibriVox)",
        collection="lang",
        url="https://archive.org/details/orange_fairy_book_1005_librivox",
    ),
    AudioSource(
        identifier="lilac_fairy_0707_librivox",
        title="The Lilac Fairy Book (LibriVox)",
        collection="lang",
        url="https://archive.org/details/lilac_fairy_0707_librivox",
    ),
]

# Public domain video adaptations
VIDEO_SOURCES = [
    VideoSource(
        identifier="rhfairytales",
        title="Ray Harryhausen Fairy Tales",
        collection="classic",
        url="https://archive.org/details/rhfairytales",
    ),
    VideoSource(
        identifier="the-worlds-greatest-fairy-tales-sekai-meisaku-dowa-manga-series",
        title="World's Greatest Fairy Tales (Toei Animation)",
        collection="classic",
        url="https://archive.org/details/the-worlds-greatest-fairy-tales-sekai-meisaku-dowa-manga-series",
    ),
]


class InternetArchiveDownloader:
    """Downloads media from Internet Archive."""

    def __init__(self, cache_dir: Optional[Path] = None):
        self.cache_dir = cache_dir or CACHE_DIR
        self.session = requests.Session()
        self.session.headers.update({
            "User-Agent": "FairytaleCollector/0.1 (Educational project)"
        })

    def get_item_files(self, identifier: str) -> list[dict]:
        """Get list of files for an Internet Archive item."""
        metadata_url = f"https://archive.org/metadata/{identifier}/files"

        try:
            response = self.session.get(metadata_url, timeout=30)
            response.raise_for_status()
            data = response.json()
            return data.get("result", [])
        except Exception as e:
            print(f"Error fetching metadata for {identifier}: {e}")
            return []

    def filter_audio_files(self, files: list[dict], format: str = "mp3") -> list[dict]:
        """Filter file list to only audio files of specified format."""
        audio_files = []
        for f in files:
            name = f.get("name", "")
            if name.lower().endswith(f".{format}"):
                # Skip very small files (likely samples/previews)
                size = int(f.get("size", 0))
                if size > 100000:  # > 100KB
                    audio_files.append(f)
        return sorted(audio_files, key=lambda x: x.get("name", ""))

    def filter_video_files(self, files: list[dict], formats: list[str] = None) -> list[dict]:
        """Filter file list to video files."""
        if formats is None:
            formats = ["mp4", "ogv", "avi"]

        video_files = []
        for f in files:
            name = f.get("name", "").lower()
            for fmt in formats:
                if name.endswith(f".{fmt}"):
                    video_files.append(f)
                    break
        return sorted(video_files, key=lambda x: x.get("name", ""))

    def download_file(
        self,
        identifier: str,
        filename: str,
        output_dir: Path,
        force: bool = False
    ) -> Optional[Path]:
        """Download a single file from Internet Archive."""
        output_path = output_dir / filename

        if output_path.exists() and not force:
            return output_path

        url = f"https://archive.org/download/{identifier}/{filename}"

        try:
            print(f"  Downloading {filename}...")
            response = self.session.get(url, timeout=120, stream=True)
            response.raise_for_status()

            output_path.parent.mkdir(parents=True, exist_ok=True)

            with open(output_path, "wb") as f:
                for chunk in response.iter_content(chunk_size=8192):
                    f.write(chunk)

            time.sleep(0.5)  # Be nice to servers
            return output_path

        except Exception as e:
            print(f"  Error downloading {filename}: {e}")
            return None

    def download_audio_collection(
        self,
        source: AudioSource,
        output_dir: Optional[Path] = None,
        format: str = "mp3"
    ) -> list[Path]:
        """Download all audio files for a LibriVox collection."""
        output_dir = output_dir or (self.cache_dir / "audio" / source.identifier)
        output_dir.mkdir(parents=True, exist_ok=True)

        print(f"Fetching file list for {source.title}...")
        files = self.get_item_files(source.identifier)
        audio_files = self.filter_audio_files(files, format)

        print(f"Found {len(audio_files)} {format} files")

        downloaded = []
        for f in audio_files:
            path = self.download_file(source.identifier, f["name"], output_dir)
            if path:
                downloaded.append(path)

        return downloaded

    def download_video_collection(
        self,
        source: VideoSource,
        output_dir: Optional[Path] = None,
    ) -> list[Path]:
        """Download all video files for an Internet Archive collection."""
        output_dir = output_dir or (self.cache_dir / "video" / source.identifier)
        output_dir.mkdir(parents=True, exist_ok=True)

        print(f"Fetching file list for {source.title}...")
        files = self.get_item_files(source.identifier)
        video_files = self.filter_video_files(files)

        print(f"Found {len(video_files)} video files")

        downloaded = []
        for f in video_files:
            path = self.download_file(source.identifier, f["name"], output_dir)
            if path:
                downloaded.append(path)

        return downloaded


def list_available_audio() -> list[AudioSource]:
    """List all known audio sources."""
    return LIBRIVOX_SOURCES


def list_available_video() -> list[VideoSource]:
    """List all known video sources."""
    return VIDEO_SOURCES


def download_all_audio(output_dir: Optional[Path] = None) -> dict[str, list[Path]]:
    """Download all available LibriVox audio."""
    downloader = InternetArchiveDownloader()
    results = {}

    for source in LIBRIVOX_SOURCES:
        print(f"\n{'='*50}")
        print(f"Downloading: {source.title}")
        print(f"{'='*50}")
        paths = downloader.download_audio_collection(source, output_dir)
        results[source.identifier] = paths

    return results


def download_all_video(output_dir: Optional[Path] = None) -> dict[str, list[Path]]:
    """Download all available video content."""
    downloader = InternetArchiveDownloader()
    results = {}

    for source in VIDEO_SOURCES:
        print(f"\n{'='*50}")
        print(f"Downloading: {source.title}")
        print(f"{'='*50}")
        paths = downloader.download_video_collection(source, output_dir)
        results[source.identifier] = paths

    return results
