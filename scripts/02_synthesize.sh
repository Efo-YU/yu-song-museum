#!/usr/bin/env bash
# Synthesize vocal (NEUTRINO) and render accompaniment (FluidSynth).
#
# Invocation follows NEUTRINO's official Run.sh exactly:
#   bin/musicXMLtoLabel  <in.musicxml>  <out_full.lab>  <out_mono.lab>
#   bin/neutrino         <full.lab>  <timing.lab>  <out.f0>  <out.melspec>
#                        <out.wav>   model/<SINGER>/  -n <threads>  -f <transpose>
#                        -m -t
#
# NEUTRINO must run from its own root directory (shared libraries are
# resolved via LD_LIBRARY_PATH=$PWD/bin — bin/ contains all .so files
# including ONNX Runtime and bundled CUDA libs; no separate NSF/bin/ in v3).
# Input MusicXML is copied into NEUTRINO's score/musicxml/ tree;
# synthesized WAV is copied back to $SONG_DIR/output/.
#
# Required env vars:
#   SONG_DIR    — path to the song directory, e.g. projects/song_001
#
# Optional env vars:
#   SINGER        — NEUTRINO singer model name (default: MERROW)
#   NEUTRINO_DIR  — path to the fetched NEUTRINO package (default: /tmp/neutrino)
#   sf3_PATH      — SoundFont file path (default: /tmp/default.sf3)
#   NUM_THREADS   — synthesis parallelism (default: 4)
#   TRANSPOSE     — semitone shift, 0 = no change (default: 0)
#
# Output files written to $SONG_DIR/output/:
#   vocal_raw.wav — synthesized vocal WAV (sample rate set by NEUTRINO model)
#   inst_raw.wav  — rendered accompaniment (44100 Hz, stereo)

set -euo pipefail

SONG_DIR="${SONG_DIR:?SONG_DIR not set}"
SINGER="${SINGER:-MERROW}"
NEUTRINO_DIR="${NEUTRINO_DIR:-/tmp/neutrino}"
sf3_PATH="${sf3_PATH:-/tmp/default.sf3}"
NUM_THREADS="${NUM_THREADS:-4}"
TRANSPOSE="${TRANSPOSE:-0}"

SONG_ID=$(basename "$SONG_DIR")
ABS_SONG="$(cd "$SONG_DIR" && pwd)"
NEUTRINO_ABS="$(cd "$NEUTRINO_DIR" && pwd)"
OUT_DIR="$ABS_SONG/output"

mkdir -p "$OUT_DIR"

# ── Vocal synthesis (NEUTRINO) ───────────────────────────────────────────────

# Prepare NEUTRINO's internal working directories
mkdir -p \
  "$NEUTRINO_ABS/score/musicxml" \
  "$NEUTRINO_ABS/score/label/full" \
  "$NEUTRINO_ABS/score/label/mono" \
  "$NEUTRINO_ABS/score/label/timing" \
  "$NEUTRINO_ABS/output"

# Copy input MusicXML into NEUTRINO's expected location
cp "$ABS_SONG/vocal.musicxml" "$NEUTRINO_ABS/score/musicxml/${SONG_ID}.musicxml"

cd "$NEUTRINO_ABS"
# bin/ contains all shared libraries (ONNX Runtime + bundled CUDA libs).
# ONNX Runtime falls back to CPU automatically when no CUDA GPU is present.
export LD_LIBRARY_PATH="$NEUTRINO_ABS/bin${LD_LIBRARY_PATH:+:$LD_LIBRARY_PATH}"

echo "[synth] Step 1: MusicXML → label"
bin/musicXMLtoLabel \
  "score/musicxml/${SONG_ID}.musicxml" \
  "score/label/full/${SONG_ID}.lab" \
  "score/label/mono/${SONG_ID}.lab"

echo "[synth] Step 2: Neural synthesis → WAV"
bin/neutrino \
  "score/label/full/${SONG_ID}.lab" \
  "score/label/timing/${SONG_ID}.lab" \
  "output/${SONG_ID}.f0" \
  "output/${SONG_ID}.melspec" \
  "output/${SONG_ID}.wav" \
  "model/${SINGER}/" \
  -n "$NUM_THREADS" \
  -f "$TRANSPOSE" \
  -m \
  -t

cd - >/dev/null

# Copy synthesized WAV to the song output directory
cp "$NEUTRINO_ABS/output/${SONG_ID}.wav" "$OUT_DIR/vocal_raw.wav"
echo "[synth] Vocal synthesis complete: $OUT_DIR/vocal_raw.wav"

# ── Accompaniment rendering (FluidSynth) ─────────────────────────────────────

INST_MID="$ABS_SONG/inst.mid"
INST_XML="$ABS_SONG/inst.musicxml"
INST_TMP_MID="$OUT_DIR/inst_tmp.mid"

if [[ -f "$INST_MID" ]]; then
  echo "[synth] Rendering accompaniment from inst.mid"
  fluidsynth -ni "$sf3_PATH" "$INST_MID" \
    -F "$OUT_DIR/inst_raw.wav" -r 44100

elif [[ -f "$INST_XML" ]]; then
  echo "[synth] Converting inst.musicxml → MIDI"
  if command -v musescore4 &>/dev/null; then
    musescore4 -o "$INST_TMP_MID" "$INST_XML"
  elif command -v musescore3 &>/dev/null; then
    musescore3 -o "$INST_TMP_MID" "$INST_XML"
  elif command -v mscore &>/dev/null; then
    mscore -o "$INST_TMP_MID" "$INST_XML"
  elif python3 -c "import music21" 2>/dev/null; then
    echo "[synth]   MuseScore not found; falling back to music21"
    python3 - "$INST_XML" "$INST_TMP_MID" <<'PYEOF'
import sys
from music21 import converter
score = converter.parse(sys.argv[1])
score.write("midi", fp=sys.argv[2])
PYEOF
  else
    echo "ERROR: inst.musicxml present but neither MuseScore nor music21 is available."
    echo "  Install MuseScore, run: pip install music21, or provide inst.mid."
    exit 1
  fi
  fluidsynth -ni "$sf3_PATH" "$INST_TMP_MID" \
    -F "$OUT_DIR/inst_raw.wav" -r 44100

else
  echo "[synth] No accompaniment file — generating silence matched to vocal length"
  duration=$(ffprobe -v error \
    -show_entries format=duration \
    -of csv=p=0 \
    "$OUT_DIR/vocal_raw.wav")
  ffmpeg -y \
    -f lavfi -i "anullsrc=r=44100:cl=stereo" \
    -t "$duration" \
    "$OUT_DIR/inst_raw.wav"
fi

echo "[synth] Done: vocal_raw.wav and inst_raw.wav written to $OUT_DIR"
