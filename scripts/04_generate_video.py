#!/usr/bin/env python3
"""Generate a video for a song using FFmpeg.

Produces a 1080p video with:
  - A background image (or solid black fallback)
  - An audio waveform visualization bar
  - Title and credits overlay

Usage:
    python3 scripts/04_generate_video.py <song_dir>

Reads:
    <song_dir>/project_metadata.json
    <song_dir>/build_config.json
    <song_dir>/output/audio.wav

Writes:
    <song_dir>/output/temp.mp4   — H.264 video ready for YouTube upload
"""

from __future__ import annotations

import json
import shlex
import subprocess
import sys
from pathlib import Path


def _escape_drawtext(s: str) -> str:
    """Escape characters that are special inside FFmpeg drawtext expressions."""
    return s.replace("'", "\\'").replace(":", "\\:").replace("\\", "\\\\")


def build_filter_graph(
    *,
    has_bg: bool,
    width: int,
    height: int,
    title: str,
    subtitle: str,
    waveform_color: str = "0x00aaff",
) -> str:
    title_esc = _escape_drawtext(title)
    sub_esc = _escape_drawtext(subtitle)

    wave_h = height // 5
    wave_y = (height - wave_h) // 2

    if has_bg:
        # Scale background image to fill the frame
        base = (
            f"[1:v]scale={width}:{height}:force_original_aspect_ratio=increase,"
            f"crop={width}:{height}[bg];"
            f"[0:a]showwaves=s={width}x{wave_h}:mode=cline:colors={waveform_color}[wave];"
            f"[bg][wave]overlay=0:{wave_y}[comp]"
        )
    else:
        base = (
            f"color=c=black:s={width}x{height}:r=30[bg];"
            f"[0:a]showwaves=s={width}x{wave_h}:mode=cline:colors={waveform_color}[wave];"
            f"[bg][wave]overlay=0:{wave_y}[comp]"
        )

    title_size = max(36, height // 20)
    sub_size = max(24, height // 32)
    title_y = height // 4
    sub_y = title_y + title_size + 16

    text_overlay = (
        f"[comp]drawtext="
        f"fontsize={title_size}:fontcolor=white:x=(w-text_w)/2:y={title_y}"
        f":text='{title_esc}':shadowcolor=black:shadowx=2:shadowy=2,"
        f"drawtext="
        f"fontsize={sub_size}:fontcolor=0xcccccc:x=(w-text_w)/2:y={sub_y}"
        f":text='{sub_esc}':shadowcolor=black:shadowx=1:shadowy=1"
        f"[out]"
    )

    return f"{base};{text_overlay}"


def main() -> None:
    if len(sys.argv) < 2:
        print(f"Usage: {sys.argv[0]} <song_dir>", file=sys.stderr)
        sys.exit(1)

    song_dir = Path(sys.argv[1])
    meta = json.loads((song_dir / "project_metadata.json").read_text())
    config = json.loads((song_dir / "build_config.json").read_text())

    out_dir = song_dir / "output"
    audio_wav = out_dir / "audio.wav"
    video_mp4 = out_dir / "temp.mp4"

    if not audio_wav.exists():
        print(f"ERROR: {audio_wav} not found — run 03_mixdown.py first", file=sys.stderr)
        sys.exit(1)

    vs = config.get("video_settings", {})
    resolution: str = vs.get("resolution", "1920x1080")
    fps: int = int(vs.get("fps", 30))
    bg_path: str = vs.get("background_image_path", "")

    width_s, height_s = resolution.split("x")
    width, height = int(width_s), int(height_s)

    title: str = meta.get("title", "Untitled")
    credits: dict = meta.get("credits", {})
    parts = [v for k, v in credits.items() if v]
    subtitle = " / ".join(parts[:3])

    bg_file = song_dir / bg_path if bg_path else None
    has_bg = bool(bg_file and bg_file.exists())

    filter_graph = build_filter_graph(
        has_bg=has_bg,
        width=width,
        height=height,
        title=title,
        subtitle=subtitle,
    )

    cmd = ["ffmpeg", "-y", "-i", str(audio_wav)]
    if has_bg:
        cmd += ["-i", str(bg_file)]
    cmd += [
        "-filter_complex", filter_graph,
        "-map", "[out]",
        "-map", "0:a",
        "-c:v", "libx264",
        "-preset", "medium",
        "-crf", "18",
        "-c:a", "aac",
        "-b:a", "192k",
        "-r", str(fps),
        "-pix_fmt", "yuv420p",
        "-movflags", "+faststart",
        str(video_mp4),
    ]

    print(f"[video] Generating {resolution}@{fps}fps → {video_mp4}")
    subprocess.run(cmd, check=True)
    print(f"[video] Done: {video_mp4}")


if __name__ == "__main__":
    main()
