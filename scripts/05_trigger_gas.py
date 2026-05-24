#!/usr/bin/env python3
"""Upload or update a YouTube video via the GAS relay.

First run (no youtube_id in project_metadata.json):
  1. Upload output/temp.mp4 to R2 at a temporary path.
  2. Generate a presigned GET URL.
  3. POST {r2_url, metadata} to GAS → GAS uploads to YouTube → returns video_id.
  4. Delete R2 object and local temp.mp4.
  5. Persist youtube_id back into project_metadata.json.
  6. Write output/meta.json.

Subsequent runs (youtube_id already present):
  1. POST {youtube_id, metadata} to GAS → GAS updates title/description/tags.
  2. Write output/meta.json (same video_id, no new upload).

Required env vars:
    GAS_RELAY_URL
    R2_ACCESS_KEY_ID, R2_SECRET_ACCESS_KEY, R2_ENDPOINT, R2_BUCKET
      (only needed on first run; skipped when youtube_id exists)

Usage:
    python3 scripts/05_trigger_gas.py <song_dir>
"""

from __future__ import annotations

import json
import os
import sys
import uuid
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


def build_payload(meta: dict, song_id: str) -> dict:
    title: str = meta["title"]
    credits: dict = meta.get("credits", {})
    description = "\n".join(filter(None, [
        f"Composer: {credits['composer']}" if credits.get("composer") else "",
        f"Vocalist: {credits['vocalist']}" if credits.get("vocalist") else "",
        f"Lyricist: {credits['lyricist']}" if credits.get("lyricist") else "",
    ]))
    return {
        "title": title,
        "description": description,
        "tags": [song_id, "NEUTRINO", "AI singing"],
        "privacy_status": meta.get("privacy_status", "public"),
    }


def main() -> None:
    if len(sys.argv) < 2:
        print(f"Usage: {sys.argv[0]} <song_dir>", file=sys.stderr)
        sys.exit(1)

    song_dir = Path(sys.argv[1])
    out_dir = song_dir / "output"
    temp_mp4 = out_dir / "temp.mp4"
    meta_json_path = out_dir / "meta.json"
    project_meta_path = song_dir / "project_metadata.json"

    meta = json.loads(project_meta_path.read_text())
    song_id: str = meta["id"]
    existing_youtube_id: str = meta.get("youtube_id", "")

    gas_url = get_env("GAS_RELAY_URL")
    payload = build_payload(meta, song_id)

    if existing_youtube_id:
        # ── Metadata update only (video content unchanged) ───────────────────
        print(f"[gas] Existing video {existing_youtube_id} — updating metadata only")
        payload["youtube_id"] = existing_youtube_id
        resp = requests.post(gas_url, json=payload, timeout=60)
        resp.raise_for_status()
        result: dict = resp.json()
        if "error" in result:
            print(f"ERROR from GAS: {result['error']}", file=sys.stderr)
            sys.exit(1)
        video_id = result["video_id"]
        youtube_url = f"https://www.youtube.com/watch?v={video_id}"
        print(f"[gas] Metadata updated: {youtube_url}")

    else:
        # ── First upload ─────────────────────────────────────────────────────
        if not temp_mp4.exists():
            print(f"ERROR: {temp_mp4} not found — run 04_generate_video.py first",
                  file=sys.stderr)
            sys.exit(1)

        bucket = get_env("R2_BUCKET")
        r2_key = f"tmp/video/{song_id}/{uuid.uuid4().hex}.mp4"
        s3 = make_s3_client()

        print(f"[gas] Uploading {temp_mp4} → r2://{bucket}/{r2_key}")
        with temp_mp4.open("rb") as fh:
            s3.upload_fileobj(fh, bucket, r2_key,
                              ExtraArgs={"ContentType": "video/mp4"})

        presigned_url: str = s3.generate_presigned_url(
            "get_object",
            Params={"Bucket": bucket, "Key": r2_key},
            ExpiresIn=PRESIGNED_EXPIRY,
        )
        print(f"[gas] Presigned URL generated (expires in {PRESIGNED_EXPIRY}s)")

        payload["r2_url"] = presigned_url
        print(f"[gas] POST → {gas_url}")
        resp = requests.post(gas_url, json=payload, timeout=600)
        resp.raise_for_status()
        result = resp.json()
        if "error" in result:
            print(f"ERROR from GAS: {result['error']}", file=sys.stderr)
            sys.exit(1)

        video_id = result["video_id"]
        youtube_url = result.get("url", f"https://www.youtube.com/watch?v={video_id}")
        print(f"[gas] YouTube upload complete: {youtube_url}")

        s3.delete_object(Bucket=bucket, Key=r2_key)
        print(f"[gas] R2 object deleted: {r2_key}")
        temp_mp4.unlink()
        print(f"[gas] Local temp.mp4 deleted")

        # Persist youtube_id into project_metadata.json so the next run
        # knows to update rather than re-upload.
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
