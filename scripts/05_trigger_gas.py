#!/usr/bin/env python3
"""Upload a new YouTube video via the GAS relay, archiving any previous version.

Flow:
  1. Upload output/temp.mp4 to R2 at a temporary path.
  2. Generate a presigned GET URL (valid 1 hour).
  3. POST to GAS:
       - r2_url        — where to fetch the new video
       - prev_youtube_id (if set) — GAS sets this to unlisted before uploading
       - version       — short commit hash + date, appended to the video title
  4. GAS uploads to YouTube, returns the new video_id.
  5. Delete R2 object and local temp.mp4.
  6. Persist new youtube_id into project_metadata.json.
  7. Write output/meta.json.

Required env vars:
    GAS_RELAY_URL
    R2_ACCESS_KEY_ID, R2_SECRET_ACCESS_KEY, R2_ENDPOINT, R2_BUCKET

Optional env vars:
    GITHUB_SHA  — full commit SHA; 7-char prefix used as version tag

Usage:
    python3 scripts/05_trigger_gas.py <song_dir>
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


def main() -> None:
    if len(sys.argv) < 2:
        print(f"Usage: {sys.argv[0]} <song_dir>", file=sys.stderr)
        sys.exit(1)

    song_dir = Path(sys.argv[1])
    out_dir = song_dir / "output"
    temp_mp4 = out_dir / "temp.mp4"
    meta_json_path = out_dir / "meta.json"
    project_meta_path = song_dir / "project_metadata.json"

    if not temp_mp4.exists():
        print(f"ERROR: {temp_mp4} not found — run 04_generate_video.py first",
              file=sys.stderr)
        sys.exit(1)

    meta = json.loads(project_meta_path.read_text())
    song_id: str = meta["id"]
    credits: dict = meta.get("credits", {})
    description = "\n".join(filter(None, [
        f"Composer: {credits['composer']}" if credits.get("composer") else "",
        f"Vocalist: {credits['vocalist']}" if credits.get("vocalist") else "",
        f"Lyricist: {credits['lyricist']}" if credits.get("lyricist") else "",
    ]))

    version = build_version_tag()
    prev_youtube_id: str = meta.get("youtube_id", "")

    # ── Upload temp.mp4 to R2 ────────────────────────────────────────────────
    bucket = get_env("R2_BUCKET")
    r2_key = f"tmp/video/{song_id}/{uuid.uuid4().hex}.mp4"
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

    # ── POST to GAS relay ────────────────────────────────────────────────────
    gas_url = get_env("GAS_RELAY_URL")
    payload: dict = {
        "r2_url": presigned_url,
        "title": meta["title"],
        "description": description,
        "tags": [song_id, "NEUTRINO", "AI singing"],
        "privacy_status": "public",
        "version": version,
    }
    if prev_youtube_id:
        payload["prev_youtube_id"] = prev_youtube_id
        print(f"[gas] Previous video {prev_youtube_id} will be archived to unlisted")

    print(f"[gas] POST → {gas_url}")
    resp = requests.post(gas_url, json=payload, timeout=600)
    resp.raise_for_status()

    result: dict = resp.json()
    if "error" in result:
        print(f"ERROR from GAS: {result['error']}", file=sys.stderr)
        sys.exit(1)

    video_id: str = result["video_id"]
    youtube_url = f"https://www.youtube.com/watch?v={video_id}"
    print(f"[gas] YouTube upload complete: {youtube_url}")

    # ── Clean up R2 object and local temp file ───────────────────────────────
    s3.delete_object(Bucket=bucket, Key=r2_key)
    print(f"[gas] R2 object deleted: {r2_key}")
    temp_mp4.unlink()
    print(f"[gas] Local temp.mp4 deleted")

    # ── Persist new youtube_id ───────────────────────────────────────────────
    meta["youtube_id"] = video_id
    project_meta_path.write_text(
        json.dumps(meta, ensure_ascii=False, indent=2) + "\n"
    )
    print(f"[gas] youtube_id persisted to {project_meta_path}")

    # ── Write meta.json ──────────────────────────────────────────────────────
    output_meta = {
        **meta,
        "youtube_id": video_id,
        "youtube_url": youtube_url,
        "audio_url": f"audio/{song_id}/audio.mp3",
        "score_url": f"scores/{song_id}/vocal.musicxml",
    }
    meta_json_path.write_text(json.dumps(output_meta, ensure_ascii=False, indent=2))
    print(f"[gas] meta.json written: {meta_json_path}")


if __name__ == "__main__":
    main()
