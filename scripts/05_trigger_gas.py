#!/usr/bin/env python3
"""Upload a new YouTube video via the GAS relay, archiving any previous variant.

Flow:
  1. Upload output/temp.mp4 to R2 at a temporary path.
  2. Generate a presigned GET URL (valid 1 hour).
  3. POST to GAS:
       - r2_url        — where to fetch the new video
       - prev_youtube_id (if set) — GAS sets this to unlisted before uploading
       - version       — short commit hash + date, appended to the video title
  4. GAS uploads to YouTube, returns the new video_id.
  5. Delete R2 object and local temp.mp4.
  6. Persist new youtube_id into variant.json.
  7. Write output/meta.json.

Required env vars:
    GAS_RELAY_URL
    R2_ACCESS_KEY_ID, R2_SECRET_ACCESS_KEY, R2_ENDPOINT, R2_BUCKET

Optional env vars:
    GITHUB_SHA   — full commit SHA; 7-char prefix used as version tag
    GAS_API_KEY  — shared secret validated by the GAS relay; omit only for
                   first-time setup before the Script Property is configured

Usage:
    python3 scripts/05_trigger_gas.py <song_dir> <variant_dir>
"""

from __future__ import annotations

import json
import os
import sys
import uuid
from datetime import datetime, timezone
from pathlib import Path

import boto3  # type: ignore[import-untyped]
import requests  # type: ignore[import-untyped]
from botocore.config import Config  # type: ignore[import-untyped]

PRESIGNED_EXPIRY = 3600  # seconds


def get_env(name: str) -> str:
    value = os.environ.get(name, "")
    if not value:
        print(f"ERROR: env var {name} is not set", file=sys.stderr)
        sys.exit(1)
    return value


def make_s3_client() -> "boto3.client":
    return boto3.client(
        "s3",
        endpoint_url=get_env("R2_ENDPOINT"),
        aws_access_key_id=get_env("R2_ACCESS_KEY_ID"),
        aws_secret_access_key=get_env("R2_SECRET_ACCESS_KEY"),
        region_name="auto",
        config=Config(signature_version="s3v4"),
    )


def build_version_tag() -> str:
    sha = os.environ.get("GITHUB_SHA", "")
    date = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    if sha:
        return f"{sha[:7]} · {date}"
    return date


def _write_meta(
    meta_json_path: Path,
    song_meta: dict,
    variant_meta: dict,
    song_slug: str,
    variant_slug: str,
    video_id: str = "",
    youtube_url: str = "",
) -> None:
    """Write meta.json with or without youtube_id.

    Called on both success and failure so deploy-web always has an artifact
    to merge, and update-queue can distinguish uploaded from pending variants.
    """
    variant_entry = {
        **{k: v for k, v in variant_meta.items() if k != "build_config"},
        "audio_url": f"audio/{song_slug}/{variant_slug}/audio.mp3",
        "score_url": (
            f"scores/{song_slug}/{variant_meta.get('score_file', 'vocal.musicxml')}"
        ),
    }
    if video_id:
        variant_entry["youtube_id"] = video_id
        variant_entry["youtube_url"] = youtube_url
    output_meta = {**song_meta, "variant": variant_entry}
    meta_json_path.write_text(json.dumps(output_meta, ensure_ascii=False, indent=2))
    print(f"[gas] meta.json written: {meta_json_path}")


def main() -> None:
    if len(sys.argv) < 3:
        print(f"Usage: {sys.argv[0]} <song_dir> <variant_dir>", file=sys.stderr)
        sys.exit(1)

    song_dir = Path(sys.argv[1])
    variant_dir = Path(sys.argv[2])

    song_slug = song_dir.name
    variant_slug = variant_dir.name

    out_dir = variant_dir / "output"
    temp_mp4 = out_dir / "temp.mp4"
    meta_json_path = out_dir / "meta.json"
    variant_json_path = variant_dir / "variant.json"

    if not temp_mp4.exists():
        print(f"ERROR: {temp_mp4} not found — run 04_generate_video.py first",
              file=sys.stderr)
        sys.exit(1)

    song_meta = json.loads((song_dir / "song.json").read_text())
    variant_meta = json.loads(variant_json_path.read_text())

    credits: dict = song_meta.get("credits", {})
    description = "\n".join(filter(None, [
        f"Composer: {credits['composer']}" if credits.get("composer") else "",
        f"Vocalist: {credits['vocalist']}" if credits.get("vocalist") else "",
        f"Lyricist: {credits['lyricist']}" if credits.get("lyricist") else "",
    ]))

    commit_version = build_version_tag()
    prev_youtube_id: str = variant_meta.get("youtube_id", "")

    try:
        # ── Upload temp.mp4 to R2 ────────────────────────────────────────────
        bucket = get_env("R2_BUCKET")
        r2_key = f"tmp/video/{song_slug}/{variant_slug}/{uuid.uuid4().hex}.mp4"
        s3 = make_s3_client()

        print(f"[gas] Uploading {temp_mp4} → r2://{bucket}/{r2_key}")
        with temp_mp4.open("rb") as fh:
            s3.upload_fileobj(fh, bucket, r2_key, ExtraArgs={"ContentType": "video/mp4"})

        presigned_url: str = s3.generate_presigned_url(
            "get_object",
            Params={"Bucket": bucket, "Key": r2_key},
            ExpiresIn=PRESIGNED_EXPIRY,
        )
        print(f"[gas] Presigned URL generated (expires in {PRESIGNED_EXPIRY}s)")

        # ── POST to GAS relay ────────────────────────────────────────────────
        gas_url = get_env("GAS_RELAY_URL")
        payload: dict = {
            "r2_url": presigned_url,
            "title": song_meta["title"],
            "description": description,
            "tags": [song_slug, variant_slug, "NEUTRINO", "AI singing"],
            "privacy_status": "public",
            "version": commit_version,
        }
        gas_api_key = os.environ.get("GAS_API_KEY", "")
        if gas_api_key:
            payload["api_key"] = gas_api_key
        if prev_youtube_id:
            payload["prev_youtube_id"] = prev_youtube_id
            print(f"[gas] Previous video {prev_youtube_id} will be archived to unlisted")

        print(f"[gas] POST → {gas_url}")
        resp = requests.post(gas_url, json=payload, timeout=600)
        resp.raise_for_status()

        result: dict = resp.json()
        if "error" in result:
            raise RuntimeError(f"GAS relay error: {result['error']}")

        video_id: str = result["video_id"]
        youtube_url = f"https://www.youtube.com/watch?v={video_id}"
        print(f"[gas] YouTube upload complete: {youtube_url}")

        # ── Clean up R2 object and local temp file ───────────────────────────
        s3.delete_object(Bucket=bucket, Key=r2_key)
        print(f"[gas] R2 object deleted: {r2_key}")
        temp_mp4.unlink()
        print(f"[gas] Local temp.mp4 deleted")

        # ── Persist new youtube_id into variant.json ─────────────────────────
        variant_meta["youtube_id"] = video_id
        variant_json_path.write_text(
            json.dumps(variant_meta, ensure_ascii=False, indent=2) + "\n"
        )
        print(f"[gas] youtube_id persisted to {variant_json_path}")

        # ── Write meta.json (success) ────────────────────────────────────────
        _write_meta(meta_json_path, song_meta, variant_meta,
                    song_slug, variant_slug, video_id, youtube_url)

    except Exception as exc:
        # Write meta.json without youtube_id so deploy-web can still deploy
        # audio and update-queue can enqueue this variant for tomorrow's retry.
        print(f"[gas] Upload failed: {exc}", file=sys.stderr)
        _write_meta(meta_json_path, song_meta, variant_meta, song_slug, variant_slug)
        sys.exit(1)


if __name__ == "__main__":
    main()
