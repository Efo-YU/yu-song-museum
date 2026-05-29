#!/usr/bin/env bash
# Download NEUTRINO package components and SoundFont from Cloudflare R2 into /tmp.
#
# R2 bucket layout (see docs/operator/r2-setup.md for upload instructions):
#
#   neutrino/bin/               — Linux x86-64 binaries (musicXMLtoLabel, neutrino)
#                                  + shared libraries (*.so incl. CUDA/ONNX Runtime)
#   neutrino/model/<SINGER>/    — singer model files (p.bin s.bin t.bin v.bin info.toml)
#   neutrino/settings/dic/      — Japanese phoneme dictionary files
#   soundfonts/default.sf3      — General MIDI SoundFont for FluidSynth
#
# Required env vars:
#   R2_ACCESS_KEY_ID
#   R2_SECRET_ACCESS_KEY
#   R2_ENDPOINT    — https://<account-id>.r2.cloudflarestorage.com
#   R2_BUCKET
#
# Optional env vars:
#   SINGER         — singer model folder name in R2 (default: MERROW); used as
#                    fallback when VARIANT_DIR has no "singers" array
#   VARIANT_DIR    — path to the variant directory; when set, all model names
#                    listed in its variant.json "singers" array are fetched
#   NEUTRINO_DIR   — local extraction target (default: /tmp/neutrino)
#   sf3_PATH       — SoundFont destination (default: /tmp/default.sf3)

set -euo pipefail

SINGER="${SINGER:-MERROW}"
NEUTRINO_DIR="${NEUTRINO_DIR:-/tmp/neutrino}"
sf3_PATH="${sf3_PATH:-/tmp/default.sf3}"
VARIANT_DIR="${VARIANT_DIR:-}"

# Resolve the set of models to fetch from variant.json "singers" array, or
# fall back to the single SINGER env var.
resolve_singers() {
  if [[ -n "$VARIANT_DIR" && -f "$VARIANT_DIR/variant.json" ]]; then
    python3 -c "
import json, sys
singers = json.load(open('$VARIANT_DIR/variant.json')).get('singers', [])
if singers:
    print('\n'.join(s['model'] for s in singers))
" 2>/dev/null
  fi
}

mapfile -t SINGER_MODELS < <(resolve_singers)
if [[ ${#SINGER_MODELS[@]} -eq 0 ]]; then
  SINGER_MODELS=("$SINGER")
fi

export AWS_ACCESS_KEY_ID="${R2_ACCESS_KEY_ID:?R2_ACCESS_KEY_ID not set}"
export AWS_SECRET_ACCESS_KEY="${R2_SECRET_ACCESS_KEY:?R2_SECRET_ACCESS_KEY not set}"
R2_ENDPOINT="${R2_ENDPOINT:?R2_ENDPOINT not set}"
R2_BUCKET="${R2_BUCKET:?R2_BUCKET not set}"

mkdir -p \
  "$NEUTRINO_DIR/bin" \
  "$NEUTRINO_DIR/settings/dic"
for m in "${SINGER_MODELS[@]}"; do
  mkdir -p "$NEUTRINO_DIR/model/$m"
done

echo "[fetch] NEUTRINO binaries and shared libraries (bin/)..."
aws s3 sync \
  --endpoint-url "$R2_ENDPOINT" \
  "s3://$R2_BUCKET/neutrino/bin/" \
  "$NEUTRINO_DIR/bin/"
chmod +x "$NEUTRINO_DIR/bin/musicXMLtoLabel" "$NEUTRINO_DIR/bin/neutrino"

echo "[fetch] Singer model(s): ${SINGER_MODELS[*]}..."
for m in "${SINGER_MODELS[@]}"; do
  echo "[fetch]   $m"
  aws s3 sync \
    --endpoint-url "$R2_ENDPOINT" \
    "s3://$R2_BUCKET/neutrino/model/$m/" \
    "$NEUTRINO_DIR/model/$m/"
done

echo "[fetch] Japanese dictionary (settings/dic/)..."
aws s3 sync \
  --endpoint-url "$R2_ENDPOINT" \
  "s3://$R2_BUCKET/neutrino/settings/dic/" \
  "$NEUTRINO_DIR/settings/dic/"

echo "[fetch] SoundFont..."
aws s3 cp \
  --endpoint-url "$R2_ENDPOINT" \
  "s3://$R2_BUCKET/soundfonts/default.sf3" \
  "$sf3_PATH"

echo "[fetch] All components fetched to $NEUTRINO_DIR"
