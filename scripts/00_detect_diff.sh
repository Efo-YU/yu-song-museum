#!/usr/bin/env bash
# Detect changed (song, version) pairs under projects/ and emit a JSON array.
#
# Usage:
#   BASE_REF=origin/main HEAD_REF=HEAD bash scripts/00_detect_diff.sh
#
# Outputs a JSON array of objects, e.g.:
#   [{"song":"yamagata-shihan-kouka","version":"default"}]
# or [] if nothing changed.
#
# Rules:
#   - A change to projects/{slug}/versions/{version}/** → that (slug, version) pair
#   - A change to any other file under projects/{slug}/ (shared files: song.json,
#     *.musicxml) → all versions of that song are included

set -euo pipefail

BASE_REF="${BASE_REF:-HEAD~1}"
HEAD_REF="${HEAD_REF:-HEAD}"

declare -A pairs_set

while IFS= read -r path; do
  if [[ "$path" =~ ^projects/([^/]+)/versions/([^/]+)/ ]]; then
    song="${BASH_REMATCH[1]}"
    version="${BASH_REMATCH[2]}"
    pairs_set["${song}/${version}"]=1
  elif [[ "$path" =~ ^projects/([^/]+)/ ]]; then
    song="${BASH_REMATCH[1]}"
    if [[ -d "projects/$song/versions" ]]; then
      for vdir in "projects/$song/versions"/*/; do
        [[ -d "$vdir" ]] || continue
        version=$(basename "$vdir")
        pairs_set["${song}/${version}"]=1
      done
    fi
  fi
done < <(git diff --name-only "$BASE_REF" "$HEAD_REF" | { grep '^projects/' || true; })

pairs_json="["
first=true
for key in "${!pairs_set[@]}"; do
  song="${key%%/*}"
  version="${key##*/}"
  [[ "$first" == "true" ]] || pairs_json+=","
  pairs_json+="{\"song\":\"$song\",\"version\":\"$version\"}"
  first=false
done
pairs_json+="]"

echo "$pairs_json"
