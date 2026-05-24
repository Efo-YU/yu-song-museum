#!/usr/bin/env bash
# Download NEUTRINO package components and SoundFont from Cloudflare R2 into /tmp.
#
# R2 bucket layout (see docs/operator/r2-setup.md for upload instructions):
#
#   neutrino/bin/               — Linux x86-64 binaries (musicXMLtoLabel, neutrino)
#                                  + shared libraries (*.so incl. CUDA/ONNX Runtime)
#   neutrino/model/<SINGER>/    — singer model files (p.bin s.bin t.bin v.bin info.toml)
#   neutrino/settings/dic/      — Japanese phoneme dictionary files
#   soundfonts/default.sf2      — General MIDI SoundFont for FluidSynth
#
# Required env vars:
#   R2_ACCESS_KEY_ID
#   R2_SECRET_ACCESS_KEY
#   R2_ENDPOINT    — https://<account-id>.r2.cloudflarestorage.com
#   R2_BUCKET
#
# Optional env vars:
#   SINGER         — singer model folder name in R2 (default: MERROW)
#   NEUTRINO_DIR   — local extraction target (default: /tmp/neutrino)
#   SF2_PATH       — SoundFont destination (default: /tmp/default.sf2)

set -euo pipefail

SINGER="${SINGER:-MERROW}"
NEUTRINO_DIR="${NEUTRINO_DIR:-/tmp/neutrino}"
SF2_PATH="${SF2_PATH:-/tmp/default.sf2}"

export AWS_ACCESS_KEY_ID="${R2_ACCESS_KEY_ID:?R2_ACCESS_KEY_ID not set}"
export AWS_SECRET_ACCESS_KEY="${R2_SECRET_ACCESS_KEY:?R2_SECRET_ACCESS_KEY not set}"
R2_ENDPOINT="${R2_ENDPOINT:?R2_ENDPOINT not set}"
R2_BUCKET="${R2_BUCKET:?R2_BUCKET not set}"

mkdir -p \
  "$NEUTRINO_DIR/bin" \
  "$NEUTRINO_DIR/model/$SINGER" \
  "$NEUTRINO_DIR/settings/dic"

echo "[fetch] NEUTRINO binaries and shared libraries (bin/)..."
aws s3 sync \
  --endpoint-url "$R2_ENDPOINT" \
  "s3://$R2_BUCKET/neutrino/bin/" \
  "$NEUTRINO_DIR/bin/"
chmod +x "$NEUTRINO_DIR/bin/musicXMLtoLabel" "$NEUTRINO_DIR/bin/neutrino"

echo "[fetch] Singer model: $SINGER..."
aws s3 sync \
  --endpoint-url "$R2_ENDPOINT" \
  "s3://$R2_BUCKET/neutrino/model/$SINGER/" \
  "$NEUTRINO_DIR/model/$SINGER/"

echo "[fetch] Japanese dictionary (settings/dic/)..."
aws s3 sync \
  --endpoint-url "$R2_ENDPOINT" \
  "s3://$R2_BUCKET/neutrino/settings/dic/" \
  "$NEUTRINO_DIR/settings/dic/"

echo "[fetch] SoundFont..."
aws s3 cp \
  --endpoint-url "$R2_ENDPOINT" \
  "s3://$R2_BUCKET/soundfonts/default.sf2" \
  "$SF2_PATH"

echo "[fetch] All components fetched to $NEUTRINO_DIR"
