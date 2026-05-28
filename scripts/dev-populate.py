#!/usr/bin/env python3
"""Populate frontend data for local development.

NOT for CI use — CI runs 06_merge_songs.py with GHA artifacts instead.

This script:
  1. Reads song metadata from projects/*/song.json and version metadata
     from projects/*/versions/*/version.json.
  2. Copies MusicXML scores (song root) → frontend/public/scores/{slug}/.
  3. Copies audio.mp3 (if already synthesized) from
     projects/{slug}/versions/{version}/output/audio.mp3
     → frontend/public/audio/{slug}/{version}/audio.mp3
     and sets audio_url in songs.json for that version.
  4. Writes frontend/src/data/songs.json.

Typical workflow:
  # First time: synthesize one or more versions
  make SONG=yamagata-shihan-kouka VERSION=with-organ synth mix

  # Then populate the frontend
  python3 scripts/dev-populate.py

  # Or do both in one step
  make dev-synth-populate SONG=yamagata-shihan-kouka VERSION=with-organ

Reset songs.json to the committed empty state:
  git restore frontend/src/data/songs.json
"""

from __future__ import annotations

import json
import shutil
import sys
from pathlib import Path

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

        # Copy all song-root MusicXML files to public/scores/{slug}/
        score_dest = PUBLIC_SCORES / slug
        score_dest.mkdir(parents=True, exist_ok=True)
        for xml in song_dir.glob("*.musicxml"):
            shutil.copy2(xml, score_dest / xml.name)

        versions = []
        versions_dir = song_dir / "versions"
        if versions_dir.exists():
            for vdir in sorted(versions_dir.iterdir()):
                if not vdir.is_dir() or not (vdir / "version.json").exists():
                    continue

                vmeta = json.loads((vdir / "version.json").read_text())
                vslug: str = vmeta["slug"]
                score_file: str = vmeta.get("score_file", "vocal.musicxml")

                entry: dict = {
                    "slug": vslug,
                    "label": vmeta["label"],
                    "description": vmeta.get("description", ""),
                    "score_url": f"scores/{slug}/{score_file}",
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
                          f" — run: make SONG={slug} VERSION={vslug} synth mix")

                versions.append(entry)

        songs.append({**song, "versions": versions})
        print(f"{slug}: {len(versions)} version(s)")

    SONGS_JSON.parent.mkdir(parents=True, exist_ok=True)
    SONGS_JSON.write_text(json.dumps(songs, ensure_ascii=False, indent=2) + "\n")

    print(f"\n[dev-populate] songs.json written"
          f" ({len(songs)} songs, {audio_count} version(s) with audio)")
    print("[dev-populate] NOTE: songs.json is now local-dev state.")
    print("[dev-populate] Reset before committing:"
          " git restore frontend/src/data/songs.json")


if __name__ == "__main__":
    main()
