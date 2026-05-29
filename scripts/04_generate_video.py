#!/usr/bin/env python3
"""Generate a video for a song version using FFmpeg.

Produces a 1080p video with:
  - A background image (or solid black fallback)
  - An audio waveform visualization bar
  - Title and credits overlay

Usage:
    python3 scripts/04_generate_video.py <song_dir> <version_dir>

Reads:
    <song_dir>/song.json
    <version_dir>/variant.json
    <version_dir>/output/audio.wav

Writes:
    <version_dir>/output/temp.mp4   — H.264 video ready for YouTube upload
"""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path


def _escape_drawtext(s: str) -> str:
    """Escape characters that are special inside FFmpeg drawtext expressions."""
    return s.replace("\\", "\\\\").replace("'", "\\'").replace(":", "\\:")


def _find_cjk_font() -> str | None:
    """Return a path to a CJK-capable font file, or None if unavailable.

    fc-match with lang=ja returns the best match fontconfig can find.
    DejaVu (the GHA default) has no CJK glyphs, so we skip it.
    """
    try:
        result = subprocess.run(
            ["fc-match", ":lang=ja", "-f", "%{file}"],
            capture_output=True, text=True, check=True,
        )
        font_path = result.stdout.strip()
        if font_path and "DejaVu" not in font_path:
            return font_path
    except (subprocess.CalledProcessError, FileNotFoundError):
        pass
    return None


def build_filter_graph(
    *,
    has_bg: bool,
    width: int,
    height: int,
    title: str,
    subtitle: str,
    duration: float,
    waveform_color: str = "0x00aaff",
    cjk_font: str | None = None,
) -> str:
    title_esc = _escape_drawtext(title)
    sub_esc = _escape_drawtext(subtitle)

    wave_h = height // 5
    wave_y = (height - wave_h) // 2

    if has_bg:
        base = (
            f"[1:v]scale={width}:{height}:force_original_aspect_ratio=increase,"
            f"crop={width}:{height}[bg];"
            f"[0:a]showwaves=s={width}x{wave_h}:mode=cline:colors={waveform_color}[wave];"
            f"[bg][wave]overlay=0:{wave_y}[comp]"
        )
    else:
        base = (
            f"color=c=black:s={width}x{height}:r=30:duration={duration}[bg];"
            f"[0:a]showwaves=s={width}x{wave_h}:mode=cline:colors={waveform_color}[wave];"
            f"[bg][wave]overlay=0:{wave_y}[comp]"
        )

    title_size = max(36, height // 20)
    sub_size = max(24, height // 32)
    title_y = height // 4
    sub_y = title_y + title_size + 16

    font_opt = f"fontfile={cjk_font}:" if cjk_font else ""

    text_overlay = (
        f"[comp]drawtext="
        f"{font_opt}fontsize={title_size}:fontcolor=white:x=(w-text_w)/2:y={title_y}"
        f":text='{title_esc}':shadowcolor=black:shadowx=2:shadowy=2,"
        f"drawtext="
        f"{font_opt}fontsize={sub_size}:fontcolor=0xcccccc:x=(w-text_w)/2:y={sub_y}"
        f":text='{sub_esc}':shadowcolor=black:shadowx=1:shadowy=1"
        f"[out]"
    )

    return f"{base};{text_overlay}"


def main() -> None:
    if len(sys.argv) < 3:
        print(f"Usage: {sys.argv[0]} <song_dir> <version_dir>", file=sys.stderr)
        sys.exit(1)

    song_dir = Path(sys.argv[1])
    version_dir = Path(sys.argv[2])

    song_meta = json.loads((song_dir / "song.json").read_text())
    version_meta = json.loads((version_dir / "variant.json").read_text())

    out_dir = version_dir / "output"
    audio_wav = out_dir / "audio.wav"
    video_mp4 = out_dir / "temp.mp4"

    if not audio_wav.exists():
        print(f"ERROR: {audio_wav} not found — run 03_mixdown.py first", file=sys.stderr)
        sys.exit(1)

    vs = version_meta.get("build_config", {}).get("video_settings", {})
    resolution: str = vs.get("resolution", "1920x1080")
    fps: int = int(vs.get("fps", 30))
    bg_path: str = vs.get("background_image_path", "")

    width_s, height_s = resolution.split("x")
    width, height = int(width_s), int(height_s)

    title: str = song_meta.get("title", "Untitled")
    credits: dict = song_meta.get("credits", {})
    parts = [v for k, v in credits.items() if v]
    subtitle = " / ".join(parts[:3])

    bg_file = song_dir / bg_path if bg_path else None
    has_bg = bool(bg_file and bg_file.exists())

    probe = subprocess.run(
        ["ffprobe", "-v", "error", "-show_entries", "format=duration",
         "-of", "default=noprint_wrappers=1:nokey=1", str(audio_wav)],
        capture_output=True, text=True, check=True,
    )
    audio_duration = float(probe.stdout.strip())

    cjk_font = _find_cjk_font()
    if cjk_font:
        print(f"[video] Using CJK font: {cjk_font}")
    else:
        print("[video] WARNING: no CJK font found — Japanese text may render as boxes")

    filter_graph = build_filter_graph(
        has_bg=has_bg,
        width=width,
        height=height,
        title=title,
        subtitle=subtitle,
        duration=audio_duration,
        cjk_font=cjk_font,
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
