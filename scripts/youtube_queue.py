#!/usr/bin/env python3
"""Manage the YouTube upload retry queue (youtube-queue.json).

Commands
--------
update --meta-dir PATH --sha SHA
    Read meta.json files produced by 05_trigger_gas.py.  Remove variants
    that were successfully uploaded (have a youtube_id).  Add or refresh
    variants that failed.  Dedup: per (song, variant) keep only the entry
    with the latest queued_at timestamp.

read --max N
    Print the first N pending items to stdout in GITHUB_OUTPUT key=value
    format so a matrix job can consume them:

        has_items=true
        pairs=[{"song":"...","variant":"...","sha":"..."},...]
"""

from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

QUEUE_FILE = Path("youtube-queue.json")


# ── Helpers ──────────────────────────────────────────────────────────────────

def _load() -> list:
    if QUEUE_FILE.exists():
        try:
            return json.loads(QUEUE_FILE.read_text())
        except Exception:
            return []
    return []


def _save(queue: list) -> None:
    QUEUE_FILE.write_text(json.dumps(queue, indent=2, ensure_ascii=False) + "\n")


def _dedup(queue: list) -> list:
    """Per (song, variant) keep only the entry with the latest queued_at."""
    best: dict = {}
    for item in queue:
        key = (item["song"], item["variant"])
        if key not in best or item["queued_at"] > best[key]["queued_at"]:
            best[key] = item
    return sorted(best.values(), key=lambda x: x["queued_at"])


# ── Commands ─────────────────────────────────────────────────────────────────

def cmd_update(args: argparse.Namespace) -> None:
    meta_dir = Path(args.meta_dir)
    sha = args.sha
    now = datetime.now(timezone.utc).isoformat()

    succeeded: set = set()
    failed: list = []

    for meta_file in meta_dir.rglob("meta.json"):
        try:
            meta = json.loads(meta_file.read_text())
            song = meta["slug"]
            variant_data = meta.get("variant", {})
            variant = variant_data.get("slug", "default")
            youtube_id = variant_data.get("youtube_id", "")
            if youtube_id:
                succeeded.add((song, variant))
            else:
                failed.append({"song": song, "variant": variant})
        except Exception as exc:
            print(f"[queue] Warning: could not read {meta_file}: {exc}",
                  file=sys.stderr)

    queue = _load()

    # Remove successfully uploaded items
    queue = [q for q in queue if (q["song"], q["variant"]) not in succeeded]

    # Add/refresh failed items
    existing_idx = {(q["song"], q["variant"]): i for i, q in enumerate(queue)}
    for item in failed:
        key = (item["song"], item["variant"])
        if key in existing_idx:
            queue[existing_idx[key]]["sha"] = sha
            queue[existing_idx[key]]["queued_at"] = now
        else:
            queue.append({
                "song": item["song"],
                "variant": item["variant"],
                "sha": sha,
                "queued_at": now,
            })

    queue = _dedup(queue)
    _save(queue)

    print(
        f"[queue] {len(succeeded)} uploaded, {len(failed)} queued/failed,"
        f" {len(queue)} total pending"
    )


def cmd_read(args: argparse.Namespace) -> None:
    queue = _dedup(_load())
    items = queue[: args.max]

    if not items:
        print("has_items=false")
        print("pairs=[]")
        return

    # Strip queued_at from the matrix payload — GHA matrix only needs
    # song, variant, sha
    pairs = [{"song": i["song"], "variant": i["variant"], "sha": i["sha"]}
             for i in items]
    print("has_items=true")
    print(f"pairs={json.dumps(pairs, separators=(',', ':'))}")


# ── Entry point ───────────────────────────────────────────────────────────────

def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)

    p_update = sub.add_parser("update", help="Update queue from meta artifacts")
    p_update.add_argument("--meta-dir", required=True,
                          help="Directory containing downloaded meta-* artifacts")
    p_update.add_argument("--sha", required=True, help="Current commit SHA")

    p_read = sub.add_parser("read", help="Output pending items for GHA matrix")
    p_read.add_argument("--max", type=int, default=5,
                        help="Maximum items to output (default: 5)")

    args = parser.parse_args()
    if args.command == "update":
        cmd_update(args)
    elif args.command == "read":
        cmd_read(args)
    else:
        parser.print_help()
        sys.exit(1)


if __name__ == "__main__":
    main()
