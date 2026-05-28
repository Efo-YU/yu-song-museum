#!/usr/bin/env python3
"""Mix vocal and accompaniment with FFmpeg, driven by version.json.

Usage:
    python3 scripts/03_mixdown.py <version_dir>

Reads:
    <version_dir>/version.json              — build_config.audio_settings
    <version_dir>/output/vocal_raw.wav
    <version_dir>/output/inst_raw.wav

Writes:
    <version_dir>/output/audio.wav    — final mixed audio (WAV, 44100 Hz, stereo)
    <version_dir>/output/audio.mp3    — web-delivery copy (CBR 192 kbps)
"""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path


def build_filter(vocal_vol: float, inst_vol: float, effects: list[dict]) -> str:
    chains = [
        f"[0:a]volume={vocal_vol}[v]",
        f"[1:a]volume={inst_vol}[i]",
        "[v][i]amix=inputs=2:duration=longest[mixed]",
    ]

    label = "mixed"
    for fx in effects:
        kind = fx.get("type", "")
        if kind == "highpass":
            freq = fx.get("frequency", 80)
            chains.append(f"[{label}]highpass=f={freq}[{label}_hp]")
            label = f"{label}_hp"
        elif kind == "lowpass":
            freq = fx.get("frequency", 16000)
            chains.append(f"[{label}]lowpass=f={freq}[{label}_lp]")
            label = f"{label}_lp"
        elif kind == "equalizer":
            freq = fx.get("frequency", 1000)
            width = fx.get("width", 200)
            gain = fx.get("gain", 0)
            chains.append(
                f"[{label}]equalizer=f={freq}:width_type=h:width={width}:g={gain}[{label}_eq]"
            )
            label = f"{label}_eq"

    chains.append(f"[{label}]alimiter=limit=0.99[out]")
    return ";".join(chains)


def main() -> None:
    if len(sys.argv) < 2:
        print(f"Usage: {sys.argv[0]} <version_dir>", file=sys.stderr)
        sys.exit(1)

    version_dir = Path(sys.argv[1])
    config = json.loads((version_dir / "version.json").read_text())

    audio = config.get("build_config", {}).get("audio_settings", {})
    vocal_vol = float(audio.get("vocal_volume", 1.0))
    inst_vol = float(audio.get("inst_volume", 0.8))
    effects: list[dict] = audio.get("effects", [])

    out_dir = version_dir / "output"
    vocal_wav = out_dir / "vocal_raw.wav"
    inst_wav = out_dir / "inst_raw.wav"
    output_wav = out_dir / "audio.wav"
    output_mp3 = out_dir / "audio.mp3"

    for p in (vocal_wav, inst_wav):
        if not p.exists():
            print(f"ERROR: expected file not found: {p}", file=sys.stderr)
            sys.exit(1)

    filter_graph = build_filter(vocal_vol, inst_vol, effects)

    print(f"[mix] Mixing with vocal={vocal_vol} inst={inst_vol} effects={len(effects)}")

    subprocess.run(
        [
            "ffmpeg", "-y",
            "-i", str(vocal_wav),
            "-i", str(inst_wav),
            "-filter_complex", filter_graph,
            "-map", "[out]",
            "-ar", "44100",
            "-ac", "2",
            str(output_wav),
        ],
        check=True,
    )

    print("[mix] Encoding MP3...")
    subprocess.run(
        [
            "ffmpeg", "-y",
            "-i", str(output_wav),
            "-b:a", "192k",
            str(output_mp3),
        ],
        check=True,
    )

    print(f"[mix] Done: {output_wav}, {output_mp3}")


if __name__ == "__main__":
    main()
