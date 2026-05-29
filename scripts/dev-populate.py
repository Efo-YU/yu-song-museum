#!/usr/bin/env python3
"""Populate frontend data for local development.

NOT for CI use — CI runs 06_merge_songs.py with GHA artifacts instead.

This script:
  1. Reads song metadata from projects/*/song.json and variant metadata
     from projects/*/variants/*/variant.json.
  2. Copies MusicXML scores (song root) → frontend/public/scores/{slug}/.
  3. Copies audio.mp3 (if already synthesized) from
     projects/{slug}/variants/{variant}/output/audio.mp3
     → frontend/public/audio/{slug}/{variant}/audio.mp3
     and sets audio_url in songs.json for that variant.
  4. Writes frontend/src/data/songs.json.

Typical workflow:
  # First time: synthesize one or more variants
  make SONG=yamagata-shihan-kouka VARIANT=with-organ synth mix

  # Then populate the frontend
  python3 scripts/dev-populate.py

  # Or do both in one step
  make dev-synth-populate SONG=yamagata-shihan-kouka VARIANT=with-organ

Reset songs.json to the committed empty state:
  git restore frontend/src/data/songs.json
"""

from __future__ import annotations

import json
import shutil
import sys
from pathlib import Path


def _generate_svg(xml_path: Path, svg_path: Path) -> None:
    """Convert a single MusicXML to SVG. No-op if verovio is unavailable."""
    try:
        from scripts_07_generate_svg import convert as _convert  # type: ignore[import]
    except ImportError:
        # Resolve relative to this file so it works regardless of CWD
        import importlib.util as _ilu
        spec = _ilu.spec_from_file_location(
            "scripts_07_generate_svg",
            Path(__file__).parent / "07_generate_svg.py",
        )
        if spec is None or spec.loader is None:
            print("  [svg] Could not load 07_generate_svg.py — skipping")
            return
        mod = _ilu.module_from_spec(spec)
        spec.loader.exec_module(mod)  # type: ignore[union-attr]
        _convert = mod.convert  # type: ignore[attr-defined]

    try:
        _convert(xml_path, svg_path)
    except ImportError:
        print("  [svg] verovio not installed — skipping SVG generation"
              " (run: pip install verovio)")
    except Exception as exc:
        print(f"  [svg] WARNING: {exc}")

REPO = Path(__file__).parent.parent
PROJECTS = REPO / "projects"
SONGS_JSON = REPO / "frontend" / "src" / "data" / "songs.json"
PUBLIC_SCORES = REPO / "frontend" / "public" / "scores"
PUBLIC_AUDIO = REPO / "frontend" / "public" / "audio"


def main() -> None:
    songs = []
    audio_count = 0

    for song_dir in sorted(PROJECTS.iterdir()):
        if not song_dir.is_dir() or not (song_dir / "song.json").exists():
            continue

        song = json.loads((song_dir / "song.json").read_text())
        slug: str = song["slug"]

        # Copy all song-root MusicXML files to public/scores/{slug}/ and generate SVGs
        score_dest = PUBLIC_SCORES / slug
        score_dest.mkdir(parents=True, exist_ok=True)
        for xml in song_dir.glob("*.musicxml"):
            dest_xml = score_dest / xml.name
            shutil.copy2(xml, dest_xml)
            _generate_svg(dest_xml, dest_xml.with_suffix(".svg"))

        variants = []
        variants_dir = song_dir / "variants"
        if variants_dir.exists():
            for vdir in sorted(variants_dir.iterdir()):
                if not vdir.is_dir() or not (vdir / "variant.json").exists():
                    continue

                vmeta = json.loads((vdir / "variant.json").read_text())
                vslug: str = vmeta["slug"]
                score_file: str = vmeta.get("score_file", "vocal.musicxml")
                svg_file: str = score_file.replace(".musicxml", ".svg")

                entry: dict = {
                    "slug": vslug,
                    "label": vmeta["label"],
                    "description": vmeta.get("description", ""),
                    "score_url": f"scores/{slug}/{score_file}",
                    "svg_url": f"scores/{slug}/{svg_file}",
                    "score_viewer_settings": vmeta.get("score_viewer_settings"),
                }

                # Include audio_url only when the MP3 has actually been synthesized
                mp3_src = vdir / "output" / "audio.mp3"
                if mp3_src.exists():
                    dest_dir = PUBLIC_AUDIO / slug / vslug
                    dest_dir.mkdir(parents=True, exist_ok=True)
                    shutil.copy2(mp3_src, dest_dir / "audio.mp3")
                    entry["audio_url"] = f"audio/{slug}/{vslug}/audio.mp3"
                    audio_count += 1
                    print(f"  [{vslug}] audio OK")
                else:
                    print(f"  [{vslug}] no audio yet"
                          f" — run: make SONG={slug} VARIANT={vslug} synth mix")

                variants.append(entry)

        songs.append({**song, "variants": variants})
        print(f"{slug}: {len(variants)} variant(s)")

    SONGS_JSON.parent.mkdir(parents=True, exist_ok=True)
    SONGS_JSON.write_text(json.dumps(songs, ensure_ascii=False, indent=2) + "\n")

    print(f"\n[dev-populate] songs.json written"
          f" ({len(songs)} songs, {audio_count} variant(s) with audio)")
    print("[dev-populate] NOTE: songs.json is now local-dev state.")
    print("[dev-populate] Reset before committing:"
          " git restore frontend/src/data/songs.json")


if __name__ == "__main__":
    main()
