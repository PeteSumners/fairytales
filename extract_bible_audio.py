"""Extract audio from Bible MP4 files to MP3."""
import subprocess
from pathlib import Path

BIBLE_VIDEO_DIR = Path(r"C:\Users\PeteS\Desktop\archive\xfer\Bible")
OUTPUT_DIR = Path(r"C:\Users\PeteS\Desktop\fairytales\cache\audio\bible")

OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

mp4_files = list(BIBLE_VIDEO_DIR.glob("*.mp4"))
print(f"Found {len(mp4_files)} MP4 files")

for mp4_file in mp4_files:
    mp3_name = mp4_file.stem + ".mp3"
    mp3_path = OUTPUT_DIR / mp3_name

    if mp3_path.exists():
        print(f"  Skipping {mp4_file.name} (already exists)")
        continue

    print(f"  Extracting {mp4_file.name}...")
    try:
        subprocess.run([
            "ffmpeg", "-i", str(mp4_file),
            "-vn",  # No video
            "-acodec", "libmp3lame",
            "-ab", "192k",  # 192 kbps
            "-y",  # Overwrite
            str(mp3_path)
        ], check=True, capture_output=True)
        print(f"    -> {mp3_name}")
    except subprocess.CalledProcessError as e:
        print(f"    ERROR: {e.stderr.decode()[:200]}")

print(f"\nDone! Extracted to {OUTPUT_DIR}")
