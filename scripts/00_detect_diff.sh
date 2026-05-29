#!/usr/bin/env bash
# Detect changed (song, variant) pairs under projects/ and emit a JSON array.
#
# Usage:
#   BASE_REF=origin/main HEAD_REF=HEAD bash scripts/00_detect_diff.sh
#
# Outputs a JSON array of objects, e.g.:
#   [{"song":"yamagata-shihan-kouka","variant":"default"}]
# or [] if nothing changed.
#
# Rules:
#   - A change to projects/{slug}/variants/{variant}/** → that (slug, variant) pair
#   - A change to any other file under projects/{slug}/ (shared files: song.json,
#     *.musicxml) → all variants of that song are included

set -euo pipefail

BASE_REF="${BASE_REF:-HEAD~1}"
HEAD_REF="${HEAD_REF:-HEAD}"

declare -A pairs_set

while IFS= read -r path; do
  if [[ "$path" =~ ^projects/([^/]+)/variants/([^/]+)/ ]]; then
    song="${BASH_REMATCH[1]}"
    variant="${BASH_REMATCH[2]}"
    pairs_set["${song}/${variant}"]=1
  elif [[ "$path" =~ ^projects/([^/]+)/ ]]; then
    song="${BASH_REMATCH[1]}"
    if [[ -d "projects/$song/variants" ]]; then
      for vdir in "projects/$song/variants"/*/; do
        [[ -d "$vdir" ]] || continue
        variant=$(basename "$vdir")
        pairs_set["${song}/${variant}"]=1
      done
    fi
  fi
done < <(git diff --name-only "$BASE_REF" "$HEAD_REF" | { grep '^projects/' || true; })

pairs_json="["
first=true
for key in "${!pairs_set[@]}"; do
  song="${key%%/*}"
  variant="${key##*/}"
  [[ "$first" == "true" ]] || pairs_json+=","
  pairs_json+="{\"song\":\"$song\",\"variant\":\"$variant\"}"
  first=false
done
pairs_json+="]"

echo "$pairs_json"
