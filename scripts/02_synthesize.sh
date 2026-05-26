#!/usr/bin/env bash
# Synthesize vocal (NEUTRINO) and render accompaniment (FluidSynth).
#
# Per-phrase synthesis based on NEUTRINO's Run_single_phrase.sh:
#   Bootstrap:  bin/neutrino ... -i <phraselist> -p 1 -m -t
#     → timing inference generates timing.lab + phraselist as a side effect,
#       then synthesizes phrase 1's vocoder output only (~8 s wall-clock for a
#       ~10 s phrase, vs ~100 s if the entire song were synthesized at once)
#   Per remaining phrase:  bin/neutrino ... -i <phraselist> -p N -m -t
#     → synthesizes only phrase N; avoids accumulating the full song's audio
#       in the vocoder output buffer, which causes OOM for songs > ~120 s
#   The per-phrase WAVs are then joined with silence gaps via ffmpeg concat.
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
PHRASELIST="output/${SONG_ID}-phraselist.txt"
rm -f "$PHRASELIST"

# Bootstrap with phrase 1: timing inference generates phraselist as a side effect
# (runs only phrase 1's vocoder instead of the full song — ~8 s vs ~100+ s for a
# long song, and avoids accumulating the full output buffer which causes OOM).
echo "[synth] Step 2a: bootstrap phrase 1 (generates phraselist)"
bin/neutrino \
  "score/label/full/${SONG_ID}.lab" \
  "score/label/timing/${SONG_ID}.lab" \
  "output/${SONG_ID}-1.f0" \
  "output/${SONG_ID}-1.melspec" \
  "output/${SONG_ID}-1.wav" \
  "model/${SINGER}/" \
  -n "$NUM_THREADS" -f "$TRANSPOSE" \
  -i "$PHRASELIST" -p 1 -m -t

mapfile -t PL_IDX    < <(awk '{print $1}' "$PHRASELIST")
mapfile -t PL_START  < <(awk '{print $2}' "$PHRASELIST")
mapfile -t PL_VOICED < <(awk '{print $3}' "$PHRASELIST")
N_PHRASES=${#PL_IDX[@]}

# Total duration from last timestamp in timing label (100 ns units → ms)
TOTAL_MS=$(awk 'END{printf "%.0f", $2/10000}' "score/label/timing/${SONG_ID}.lab")

# Synthesize remaining voiced phrases (phrase 1 already done above)
for (( i=0; i<N_PHRASES; i++ )); do
  idx="${PL_IDX[$i]}"
  if [[ "${PL_VOICED[$i]}" != "1" || "$idx" == "1" ]]; then continue; fi
  if (( i + 1 < N_PHRASES )); then
    end_ms="${PL_START[$((i+1))]}"
  else
    end_ms="$TOTAL_MS"
  fi
  echo "[synth] Step 2b: phrase $idx (${PL_START[$i]}–${end_ms} ms)"
  bin/neutrino \
    "score/label/full/${SONG_ID}.lab" \
    "score/label/timing/${SONG_ID}.lab" \
    "output/${SONG_ID}-${idx}.f0" \
    "output/${SONG_ID}-${idx}.melspec" \
    "output/${SONG_ID}-${idx}.wav" \
    "model/${SINGER}/" \
    -n "$NUM_THREADS" -f "$TRANSPOSE" \
    -i "$PHRASELIST" -p "$idx" -m -t
done

# Probe sample rate from the first voiced phrase
FIRST_IDX=$(awk '$3==1{print $1; exit}' "$PHRASELIST")
SR=$(ffprobe -v error -select_streams a:0 \
  -show_entries stream=sample_rate -of csv=p=0 \
  "output/${SONG_ID}-${FIRST_IDX}.wav")

# Build concat list: voiced phrase WAVs interleaved with generated silence
CONCAT_LIST="output/${SONG_ID}_concat.txt"
> "$CONCAT_LIST"
for (( i=0; i<N_PHRASES; i++ )); do
  idx="${PL_IDX[$i]}"
  start_ms="${PL_START[$i]}"
  if (( i + 1 < N_PHRASES )); then
    end_ms="${PL_START[$((i+1))]}"
  else
    end_ms="$TOTAL_MS"
  fi
  dur_ms=$(( end_ms - start_ms ))
  if (( dur_ms <= 0 )); then continue; fi

  if [[ "${PL_VOICED[$i]}" == "1" ]]; then
    echo "file '$(pwd)/output/${SONG_ID}-${idx}.wav'" >> "$CONCAT_LIST"
  else
    sil="output/${SONG_ID}-sil${idx}.wav"
    dur_s=$(awk -v ms="$dur_ms" 'BEGIN{printf "%.6f", ms/1000}')
    ffmpeg -y -f lavfi -i "anullsrc=r=${SR}:cl=mono" \
      -t "$dur_s" -ar "$SR" -ac 1 -acodec pcm_s16le "$sil"
    echo "file '$(pwd)/$sil'" >> "$CONCAT_LIST"
  fi
done

ffmpeg -y -f concat -safe 0 -i "$CONCAT_LIST" \
  -acodec pcm_s16le -ar "$SR" -ac 1 "output/${SONG_ID}.wav"

# Remove intermediate per-phrase files
rm -f "$CONCAT_LIST"
for (( i=0; i<N_PHRASES; i++ )); do
  idx="${PL_IDX[$i]}"
  rm -f \
    "output/${SONG_ID}-${idx}.f0" \
    "output/${SONG_ID}-${idx}.melspec" \
    "output/${SONG_ID}-${idx}.wav" \
    "output/${SONG_ID}-sil${idx}.wav"
done

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
  # No dedicated accompaniment: derive a backing-vocal track from the vocal
  # synthesis by adding reverb (80 ms echo at 40 % decay).  This gives the
  # mix body without requiring a separate score or MIDI file.
  echo "[synth] No accompaniment file — deriving backing vocal from vocal synthesis"
  ffmpeg -y -i "$OUT_DIR/vocal_raw.wav" \
    -af "aecho=0.8:0.88:80:0.4" \
    -ar 44100 -ac 2 \
    "$OUT_DIR/inst_raw.wav"
fi

echo "[synth] Done: vocal_raw.wav and inst_raw.wav written to $OUT_DIR"
