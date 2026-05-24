#!/usr/bin/env bash
# Detect changed projects/ subdirectories and emit a JSON array of song IDs.
#
# Usage:
#   BASE_REF=origin/main HEAD_REF=HEAD bash scripts/00_detect_diff.sh
#
# Outputs a JSON array such as ["song_001","song_002"], or "[]" if nothing changed.
# When called from a GHA pull_request event, set BASE_REF to the base SHA and
# HEAD_REF to the merge SHA (both are available via github.event.* context).

set -euo pipefail

BASE_REF="${BASE_REF:-HEAD~1}"
HEAD_REF="${HEAD_REF:-HEAD}"

changed=$(
  git diff --name-only "$BASE_REF" "$HEAD_REF" \
    | { grep '^projects/' || true; } \
    | awk -F/ '{print $2}' \
    | sort -u \
    | jq -R . \
    | jq -sc .
)

# Default to empty array if nothing matched
echo "${changed:-[]}"
