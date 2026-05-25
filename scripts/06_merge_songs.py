#!/usr/bin/env python3
"""Merge per-song meta.json artifacts into the frontend songs.json database.

Also copies MusicXML scores and MP3 audio into the frontend public tree so
the React app can fetch them at runtime.

Directory layout expected:
    artifacts/meta/<job-name>/meta.json   — downloaded GHA artifacts (meta-*)

Reads (as base database):
    frontend/src/data/songs.json          — existing songs (may not exist yet)

Writes:
    frontend/src/data/songs.json          — merged songs database
    frontend/public/scores/<song_id>/     — MusicXML files
    frontend/public/audio/<song_id>/      — MP3 files

Usage:
    python3 scripts/06_merge_songs.py
"""

from __future__ import annotations

import json
import shutil
from pathlib import Path


REPO_ROOT = Path(__file__).parent.parent
ARTIFACTS_DIR = REPO_ROOT / "artifacts" / "meta"
FRONTEND_DIR = REPO_ROOT / "frontend"
SONGS_JSON = FRONTEND_DIR / "src" / "data" / "songs.json"
PUBLIC_SCORES = FRONTEND_DIR / "public" / "scores"
PUBLIC_AUDIO = FRONTEND_DIR / "public" / "audio"
PROJECTS_DIR = REPO_ROOT / "projects"


def load_existing_songs() -> dict[str, dict]:
    if SONGS_JSON.exists():
        songs = json.loads(SONGS_JSON.read_text())
        return {s["id"]: s for s in songs}
    return {}


def collect_new_metas() -> list[tuple[dict, Path]]:
    metas = []
    if not ARTIFACTS_DIR.exists():
        return metas
    for meta_file in ARTIFACTS_DIR.rglob("meta.json"):
        try:
            metas.append((json.loads(meta_file.read_text()), meta_file.parent))
        except (json.JSONDecodeError, OSError) as exc:
            print(f"WARNING: skipping {meta_file}: {exc}")
    return metas


def copy_assets(song_id: str, artifact_dir: Path) -> None:
    song_dir = PROJECTS_DIR / song_id

    # MusicXML scores — committed source files, always present in the checkout
    score_dest = PUBLIC_SCORES / song_id
    score_dest.mkdir(parents=True, exist_ok=True)
    for xml in song_dir.glob("*.musicxml"):
        shutil.copy2(xml, score_dest / xml.name)

    # MP3 audio — generated output bundled in the meta artifact
    audio_dest = PUBLIC_AUDIO / song_id
    audio_dest.mkdir(parents=True, exist_ok=True)
    mp3 = artifact_dir / "audio.mp3"
    if mp3.exists():
        shutil.copy2(mp3, audio_dest / "audio.mp3")
    else:
        print(f"WARNING: {mp3} not found — audio download will be unavailable for {song_id}")

    # project_metadata.json — copy back so deploy-web can commit youtube_id
    updated_meta = artifact_dir / "project_metadata.json"
    if updated_meta.exists():
        shutil.copy2(updated_meta, song_dir / "project_metadata.json")


def merge_page_config(song_meta: dict) -> dict:
    song_id = song_meta["id"]
    page_config_path = PROJECTS_DIR / song_id / "page_config.json"
    if page_config_path.exists():
        song_meta["page_config"] = json.loads(page_config_path.read_text())
    return song_meta


def main() -> None:
    existing = load_existing_songs()
    new_metas = collect_new_metas()

    if not new_metas:
        print("[merge] No new meta.json artifacts found — nothing to merge")
    else:
        print(f"[merge] Merging {len(new_metas)} song(s)")

    for meta, artifact_dir in new_metas:
        song_id = meta["id"]
        meta = merge_page_config(meta)
        existing[song_id] = meta
        copy_assets(song_id, artifact_dir)
        print(f"[merge] {song_id}: merged and assets copied")

    songs_list = sorted(existing.values(), key=lambda s: s["id"])

    SONGS_JSON.parent.mkdir(parents=True, exist_ok=True)
    SONGS_JSON.write_text(
        json.dumps(songs_list, ensure_ascii=False, indent=2) + "\n"
    )
    print(f"[merge] songs.json written ({len(songs_list)} total songs)")


if __name__ == "__main__":
    main()
