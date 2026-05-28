#!/usr/bin/env python3
"""Merge per-version meta.json artifacts into the frontend songs.json database.

Also copies MusicXML scores and MP3 audio into the frontend public tree so
the React app can fetch them at runtime.

Directory layout expected:
    artifacts/meta/<job-name>/meta.json   — downloaded GHA artifacts (meta-*)

Reads (as base database):
    frontend/src/data/songs.json          — existing songs (may not exist yet)

Writes:
    frontend/src/data/songs.json          — merged songs database
    frontend/public/scores/<song_slug>/   — MusicXML files (shared across versions)
    frontend/public/audio/<song_slug>/<version_slug>/  — MP3 per version

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
    """Load songs.json keyed by slug."""
    if SONGS_JSON.exists():
        songs = json.loads(SONGS_JSON.read_text())
        return {s["slug"]: s for s in songs}
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


def copy_scores(song_slug: str) -> None:
    """Copy MusicXML files from the song root to public/scores/<slug>/."""
    song_dir = PROJECTS_DIR / song_slug
    score_dest = PUBLIC_SCORES / song_slug
    score_dest.mkdir(parents=True, exist_ok=True)
    for xml in song_dir.glob("*.musicxml"):
        shutil.copy2(xml, score_dest / xml.name)


def copy_audio(song_slug: str, version_slug: str, artifact_dir: Path) -> None:
    """Copy audio.mp3 from the artifact to public/audio/<slug>/<version>/."""
    audio_dest = PUBLIC_AUDIO / song_slug / version_slug
    audio_dest.mkdir(parents=True, exist_ok=True)
    mp3 = artifact_dir / "audio.mp3"
    if mp3.exists():
        shutil.copy2(mp3, audio_dest / "audio.mp3")
    else:
        print(f"WARNING: {mp3} not found — audio unavailable for {song_slug}/{version_slug}")


def persist_version_json(song_slug: str, version_slug: str, artifact_dir: Path) -> None:
    """Write back updated version.json (with youtube_id) from the artifact."""
    updated = artifact_dir / "version.json"
    if updated.exists():
        dest = PROJECTS_DIR / song_slug / "versions" / version_slug / "version.json"
        shutil.copy2(updated, dest)


def main() -> None:
    existing: dict[str, dict] = load_existing_songs()
    new_metas = collect_new_metas()

    if not new_metas:
        print("[merge] No new meta.json artifacts found — nothing to merge")
    else:
        print(f"[merge] Merging {len(new_metas)} version(s)")

    for meta, artifact_dir in new_metas:
        song_slug: str = meta["slug"]
        version_data: dict = meta.get("version", {})
        version_slug: str = version_data.get("slug", "default")

        # Ensure song entry exists in the database
        if song_slug not in existing:
            existing[song_slug] = {
                "slug": song_slug,
                "title": meta.get("title", ""),
                "bpm": meta.get("bpm"),
                "key": meta.get("key"),
                "credits": meta.get("credits"),
                "page_config": meta.get("page_config"),
                "versions": [],
            }
        else:
            # Refresh song-level fields from the artifact (they may have changed)
            for field in ("title", "bpm", "key", "credits", "page_config"):
                if field in meta:
                    existing[song_slug][field] = meta[field]

        # Update or insert the version entry
        versions: list[dict] = existing[song_slug].setdefault("versions", [])
        existing_version = next((v for v in versions if v["slug"] == version_slug), None)
        if existing_version is not None:
            existing_version.update(version_data)
        else:
            versions.append(version_data)

        copy_scores(song_slug)
        copy_audio(song_slug, version_slug, artifact_dir)
        persist_version_json(song_slug, version_slug, artifact_dir)
        print(f"[merge] {song_slug}/{version_slug}: merged and assets copied")

    # Sort songs by slug, versions within each song by slug
    for song in existing.values():
        song["versions"] = sorted(song.get("versions", []), key=lambda v: v["slug"])
    songs_list = sorted(existing.values(), key=lambda s: s["slug"])

    SONGS_JSON.parent.mkdir(parents=True, exist_ok=True)
    SONGS_JSON.write_text(
        json.dumps(songs_list, ensure_ascii=False, indent=2) + "\n"
    )
    print(f"[merge] songs.json written ({len(songs_list)} total songs)")


if __name__ == "__main__":
    main()
