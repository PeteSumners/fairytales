# Fairytale Reader

A PyGame-based e-reader for classic fairytales and the KJV Bible with LibriVox audio playback.

## Features

- **Classic Fairytale Collections**: Grimm, Andersen, Lang's Fairy Books, Perrault
- **KJV Bible**: All 66 books with chapter navigation
- **Audio Playback**: LibriVox audiobook integration
- **Bookmarks**: Save your place with `[B]`, navigate with `[` and `]`
- **Progress Tracking**: Automatically saves reading position
- **Retro Pixel Art UI**: Warm sepia tones with page-turn animations and sound effects

## Requirements

- Python 3.8+
- PyGame
- pygame_gui

## Installation

```bash
pip install pygame pygame_gui
```

## Running the Reader

```bash
cd reader
python reader.py
```

## Controls

| Key | Action |
|-----|--------|
| `Up/Down` | Navigate menus |
| `Left/Right` | Turn pages |
| `Enter` | Select |
| `Esc` | Go back |
| `B` | Toggle bookmark |
| `[` | Previous bookmark |
| `]` | Next bookmark |
| `Space` | Play/pause audio |
| `C` | Mark story complete |

## Data Collection

The `fairytale_collector` module downloads content from Project Gutenberg and LibriVox:

```bash
# Download and process all fairytales
python -m fairytale_collector.cli process-all

# Download audio for a collection
python -m fairytale_collector.cli download-audio grimms_english_librivox

# List available sources
python -m fairytale_collector.cli sources
```

## Available Collections

| ID | Title | Author |
|----|-------|--------|
| 2591 | Grimm's Fairy Tales | Brothers Grimm |
| 1597 | Hans Andersen's Fairy Tales | Hans Christian Andersen |
| 503 | The Blue Fairy Book | Andrew Lang |
| 640 | The Red Fairy Book | Andrew Lang |
| 30580 | The Green Fairy Book | Andrew Lang |
| 7871 | The Yellow Fairy Book | Andrew Lang |
| 31536 | The Pink Fairy Book | Andrew Lang |
| 699 | The Fairy Tales of Charles Perrault | Charles Perrault |

## Project Structure

```
fairytales/
├── reader/               # PyGame e-reader application
│   ├── reader.py         # Main application
│   ├── bible.py          # KJV Bible parser
│   ├── media.py          # Audio file matching
│   ├── audio.py          # Audio playback
│   ├── sounds.py         # UI sound effects
│   └── sfx/              # Sound effect files
├── fairytale_collector/  # Content downloader
│   ├── cli.py            # Command-line interface
│   ├── downloader.py     # Gutenberg downloader
│   └── audio.py          # LibriVox downloader
├── audio/                # LibriVox MP3 narrations (Git LFS)
└── output/               # Processed story text
```

## License

Public domain texts from Project Gutenberg. Audio from LibriVox (public domain).
