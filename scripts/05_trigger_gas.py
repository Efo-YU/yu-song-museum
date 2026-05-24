#!/usr/bin/env python3
"""Upload the generated video to R2 temporarily and trigger the GAS relay.

Flow:
  1. Upload <song_dir>/output/temp.mp4 to R2 at a temporary path.
  2. Generate a presigned GET URL (valid 1 hour).
  3. POST {r2_url, metadata} to the GAS Web App.
  4. GAS fetches the video, uploads to YouTube, returns the video ID.
  5. Delete temp.mp4 locally and the R2 object.
  6. Write <song_dir>/output/meta.json with the video ID and metadata.

Required env vars:
    GAS_RELAY_URL          — deployed GAS Web App URL (do-execute endpoint)
    R2_ACCESS_KEY_ID       — R2 API token key ID
    R2_SECRET_ACCESS_KEY   — R2 API token secret
    R2_ENDPOINT            — https://<account>.r2.cloudflarestorage.com
    R2_BUCKET              — R2 bucket name

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


def main() -> None:
    if len(sys.argv) < 2:
        print(f"Usage: {sys.argv[0]} <song_dir>", file=sys.stderr)
        sys.exit(1)

    song_dir = Path(sys.argv[1])
    out_dir = song_dir / "output"
    temp_mp4 = out_dir / "temp.mp4"
    meta_json = out_dir / "meta.json"

    if not temp_mp4.exists():
        print(f"ERROR: {temp_mp4} not found — run 04_generate_video.py first", file=sys.stderr)
        sys.exit(1)

    meta = json.loads((song_dir / "project_metadata.json").read_text())
    song_id: str = meta["id"]
    title: str = meta["title"]
    credits: dict = meta.get("credits", {})
    description_parts = [
        f"Composer: {credits['composer']}" if credits.get("composer") else "",
        f"Vocalist: {credits['vocalist']}" if credits.get("vocalist") else "",
        f"Lyricist: {credits['lyricist']}" if credits.get("lyricist") else "",
    ]
    description = "\n".join(p for p in description_parts if p)

    bucket = get_env("R2_BUCKET")
    r2_key = f"tmp/video/{song_id}/{uuid.uuid4().hex}.mp4"

    s3 = make_s3_client()

    # ── Upload temp.mp4 to R2 ────────────────────────────────────────────────
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
    payload = {
        "r2_url": presigned_url,
        "title": title,
        "description": description,
        "tags": [song_id, "NEUTRINO", "AI singing"],
        "privacy_status": "public",
    }

    print(f"[gas] POST → {gas_url}")
    resp = requests.post(gas_url, json=payload, timeout=600)
    resp.raise_for_status()

    result: dict = resp.json()
    if "error" in result:
        print(f"ERROR from GAS: {result['error']}", file=sys.stderr)
        sys.exit(1)

    video_id: str = result["video_id"]
    youtube_url: str = result.get("url", f"https://www.youtube.com/watch?v={video_id}")
    print(f"[gas] YouTube upload complete: {youtube_url}")

    # ── Clean up R2 object and local temp file ───────────────────────────────
    s3.delete_object(Bucket=bucket, Key=r2_key)
    print(f"[gas] R2 object deleted: {r2_key}")

    temp_mp4.unlink()
    print(f"[gas] Local temp.mp4 deleted")

    # ── Write meta.json ──────────────────────────────────────────────────────
    output_meta = {
        **meta,
        "youtube_id": video_id,
        "youtube_url": youtube_url,
        "audio_url": f"/audio/{song_id}/audio.mp3",
        "score_url": f"/scores/{song_id}/vocal.musicxml",
    }
    meta_json.write_text(json.dumps(output_meta, ensure_ascii=False, indent=2))
    print(f"[gas] meta.json written: {meta_json}")


if __name__ == "__main__":
    main()
