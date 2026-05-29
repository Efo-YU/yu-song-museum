#!/usr/bin/env python3
"""Merge per-variant meta.json artifacts into the frontend songs.json database.

Also copies MusicXML scores and MP3 audio into the frontend public tree so
the React app can fetch them at runtime.

Directory layout expected:
    artifacts/meta/<job-name>/meta.json   — downloaded GHA artifacts (meta-*)

Reads (as base database):
    frontend/src/data/songs.json          — existing songs (may not exist yet)

Writes:
    frontend/src/data/songs.json          — merged songs database
    frontend/public/scores/<song_slug>/   — MusicXML files (shared across variants)
    frontend/public/audio/<song_slug>/<variant_slug>/  — MP3 per variant

Usage:
    python3 scripts/06_merge_songs.py
"""

from __future__ import annotations

import json
import shutil
from pathlib import Path


def _generate_svg(xml_path: Path, svg_path: Path) -> None:
    """Convert MusicXML to SVG. No-op if verovio is unavailable."""
    try:
        import importlib.util as _ilu
        _script = Path(__file__).parent / "07_generate_svg.py"
        spec = _ilu.spec_from_file_location("_gen_svg", _script)
        if spec is None or spec.loader is None:
            return
        mod = _ilu.module_from_spec(spec)
        spec.loader.exec_module(mod)  # type: ignore[union-attr]
        mod.convert(xml_path, svg_path)  # type: ignore[attr-defined]
    except ImportError:
        pass  # verovio not available; SVGs will be absent this run
    except Exception as exc:
        print(f"WARNING: SVG generation failed for {xml_path.name}: {exc}")


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
    """Copy MusicXML files from the song root to public/scores/<slug>/ and generate SVGs."""
    song_dir = PROJECTS_DIR / song_slug
    score_dest = PUBLIC_SCORES / song_slug
    score_dest.mkdir(parents=True, exist_ok=True)
    for xml in song_dir.glob("*.musicxml"):
        dest_xml = score_dest / xml.name
        shutil.copy2(xml, dest_xml)
        _generate_svg(dest_xml, dest_xml.with_suffix(".svg"))


def copy_audio(song_slug: str, variant_slug: str, artifact_dir: Path) -> None:
    """Copy audio.mp3 from the artifact to public/audio/<slug>/<variant>/."""
    audio_dest = PUBLIC_AUDIO / song_slug / variant_slug
    audio_dest.mkdir(parents=True, exist_ok=True)
    mp3 = artifact_dir / "audio.mp3"
    if mp3.exists():
        shutil.copy2(mp3, audio_dest / "audio.mp3")
    else:
        print(f"WARNING: {mp3} not found — audio unavailable for {song_slug}/{variant_slug}")


def persist_variant_json(song_slug: str, variant_slug: str, artifact_dir: Path) -> None:
    """Write back updated variant.json (with youtube_id) from the artifact."""
    updated = artifact_dir / "variant.json"
    if updated.exists():
        dest = PROJECTS_DIR / song_slug / "variants" / variant_slug / "variant.json"
        shutil.copy2(updated, dest)


def main() -> None:
    existing: dict[str, dict] = load_existing_songs()
    new_metas = collect_new_metas()

    if not new_metas:
        print("[merge] No new meta.json artifacts found — nothing to merge")
    else:
        print(f"[merge] Merging {len(new_metas)} variant(s)")

    for meta, artifact_dir in new_metas:
        song_slug: str = meta["slug"]
        variant_data: dict = meta.get("variant", {})
        variant_slug: str = variant_data.get("slug", "default")

        # Always read song-level metadata from the repo's song.json so that
        # credits, lyrics, and descriptions stay in sync with the source of
        # truth rather than whatever was cached in an old artifact or the
        # previously committed songs.json.
        song_json_path = PROJECTS_DIR / song_slug / "song.json"
        if song_json_path.exists():
            live_meta = json.loads(song_json_path.read_text())
        else:
            live_meta = meta  # fallback for songs without a song.json

        # Ensure song entry exists in the database
        if song_slug not in existing:
            existing[song_slug] = {
                "slug": song_slug,
                "title": live_meta.get("title", ""),
                "bpm": live_meta.get("bpm"),
                "key": live_meta.get("key"),
                "credits": live_meta.get("credits"),
                "page_config": live_meta.get("page_config"),
                "variants": [],
            }
        else:
            # Refresh song-level fields from the live song.json
            for field in ("title", "bpm", "key", "credits", "page_config"):
                if field in live_meta:
                    existing[song_slug][field] = live_meta[field]

        # Derive svg_url from score_url (e.g. scores/slug/full.musicxml → .svg)
        if "score_url" in variant_data and "svg_url" not in variant_data:
            variant_data["svg_url"] = variant_data["score_url"].replace(".musicxml", ".svg")

        # Update or insert the variant entry
        variants: list[dict] = existing[song_slug].setdefault("variants", [])
        existing_variant = next((v for v in variants if v["slug"] == variant_slug), None)
        if existing_variant is not None:
            existing_variant.update(variant_data)
        else:
            variants.append(variant_data)

        copy_scores(song_slug)
        copy_audio(song_slug, variant_slug, artifact_dir)
        persist_variant_json(song_slug, variant_slug, artifact_dir)
        print(f"[merge] {song_slug}/{variant_slug}: merged and assets copied")

    # Always copy MusicXML scores for every known song, regardless of whether
    # a pipeline artifact was produced this run.  Score files live in the repo
    # and are always available; audio depends on a successful synth pipeline run.
    all_song_slugs = {s["slug"] for s in existing.values()}
    for slug in all_song_slugs:
        copy_scores(slug)

    # Sort songs by slug, variants within each song by slug
    for song in existing.values():
        song["variants"] = sorted(song.get("variants", []), key=lambda v: v["slug"])
    songs_list = sorted(existing.values(), key=lambda s: s["slug"])

    SONGS_JSON.parent.mkdir(parents=True, exist_ok=True)
    SONGS_JSON.write_text(
        json.dumps(songs_list, ensure_ascii=False, indent=2) + "\n"
    )
    print(f"[merge] songs.json written ({len(songs_list)} total songs)")


if __name__ == "__main__":
    main()
