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
# synthesized WAV is copied back to $VERSION_DIR/output/.
#
# Required env vars:
#   SONG_DIR     — path to the song directory, e.g. projects/yamagata-shihan-kouka
#   VARIANT_DIR  — path to the variant directory, e.g. projects/yamagata-shihan-kouka/variants/default
#
# Optional env vars:
#   SINGER        — NEUTRINO singer model name, used as fallback when variant.json
#                   does not specify a "singers" array (default: MERROW)
#   NEUTRINO_DIR  — path to the fetched NEUTRINO package (default: /tmp/neutrino)
#   sf3_PATH      — SoundFont file path (default: /tmp/default.sf3)
#   NUM_THREADS   — synthesis parallelism (default: 4)
#   TRANSPOSE     — semitone shift, 0 = no change (default: 0)
#
# Multi-singer support:
#   When variant.json contains a "singers" array, each entry is synthesized
#   separately and the results are mixed:
#     "singers": [
#       {"model": "MERROW", "volume": 1.0},
#       {"model": "ITAKO",  "volume": 0.6}
#     ]
#   Volumes are applied before amix so relative loudness is preserved.
#   When "singers" is absent or empty, falls back to the SINGER env var
#   with volume 1.0 (existing behaviour).
#
# Output files written to $VERSION_DIR/output/:
#   vocal_raw.wav — synthesized vocal WAV (sample rate set by NEUTRINO model)
#   inst_raw.wav  — rendered accompaniment (44100 Hz, stereo)

set -euo pipefail

SONG_DIR="${SONG_DIR:?SONG_DIR not set}"
VARIANT_DIR="${VARIANT_DIR:?VARIANT_DIR not set}"
SINGER="${SINGER:-MERROW}"
NEUTRINO_DIR="${NEUTRINO_DIR:-/tmp/neutrino}"
sf3_PATH="${sf3_PATH:-/tmp/default.sf3}"
NUM_THREADS="${NUM_THREADS:-4}"
TRANSPOSE="${TRANSPOSE:-0}"

SONG_SLUG=$(basename "$SONG_DIR")
VARIANT_SLUG=$(basename "$VARIANT_DIR")
# Unique stem for NEUTRINO's intermediate files; avoids collisions in parallel runs
SCORE_ID="${SONG_SLUG}-${VARIANT_SLUG}"

ABS_SONG="$(cd "$SONG_DIR" && pwd)"
ABS_VERSION="$(cd "$VARIANT_DIR" && pwd)"
NEUTRINO_ABS="$(cd "$NEUTRINO_DIR" && pwd)"
OUT_DIR="$ABS_VERSION/output"

mkdir -p "$OUT_DIR"

# ── Read singer list from variant.json ───────────────────────────────────────
# Output format: one "model:volume" pair per line.
# Falls back to $SINGER env var with volume 1.0 when "singers" is absent/empty.
read_singers() {
  python3 - "$ABS_VERSION/variant.json" "$SINGER" <<'PYEOF'
import json, sys

path, fallback = sys.argv[1], sys.argv[2]
try:
    data = json.load(open(path))
    singers = data.get("singers", [])
except Exception:
    singers = []

if singers:
    for s in singers:
        model = s.get("model", fallback)
        vol   = float(s.get("volume", 1.0))
        print(f"{model}:{vol}")
else:
    print(f"{fallback}:1.0")
PYEOF
}

mapfile -t SINGER_ENTRIES < <(read_singers)
SINGER_COUNT=${#SINGER_ENTRIES[@]}

# ── no_accompaniment flag (checked early so we can exit before NEUTRINO) ──────
NO_INST=$(python3 -c "
import json, sys
try:
    d = json.load(open('$ABS_VERSION/variant.json'))
    print('true' if d.get('no_accompaniment', False) else 'false')
except: print('false')
" 2>/dev/null || echo "false")

# ── Skip-vocal flag ───────────────────────────────────────────────────────────
# Read skip_vocal_synthesis from variant.json (default: false).
# Also skip if no vocal.musicxml exists in either version dir or song dir.
SKIP_VOCAL=$(python3 -c "
import json, sys
try:
    d = json.load(open('$ABS_VERSION/variant.json'))
    print('true' if d.get('skip_vocal_synthesis', False) else 'false')
except: print('false')
" 2>/dev/null || echo "false")

# If the flag is not set, still skip when no vocal MusicXML is available
if [[ "$SKIP_VOCAL" == "false" ]]; then
  if [[ ! -f "$ABS_VERSION/vocal.musicxml" && ! -f "$ABS_SONG/vocal.musicxml" ]]; then
    SKIP_VOCAL="true"
  fi
fi

# ── Vocal synthesis (NEUTRINO) ───────────────────────────────────────────────

if [[ "$SKIP_VOCAL" == "true" ]]; then
  echo "[synth] Skipping vocal synthesis — generating 1 s silent placeholder"
  ffmpeg -y -f lavfi -i "anullsrc=r=44100:cl=mono" -t 1 \
    -ar 44100 -ac 1 "$OUT_DIR/vocal_raw.wav"
else

# Resolve vocal MusicXML: version-level override wins over song-level default
if [[ -f "$ABS_VERSION/vocal.musicxml" ]]; then
  VOCAL_XML="$ABS_VERSION/vocal.musicxml"
else
  VOCAL_XML="$ABS_SONG/vocal.musicxml"
fi

mkdir -p \
  "$NEUTRINO_ABS/score/musicxml" \
  "$NEUTRINO_ABS/score/label/full" \
  "$NEUTRINO_ABS/score/label/mono" \
  "$NEUTRINO_ABS/score/label/timing" \
  "$NEUTRINO_ABS/output"

cp "$VOCAL_XML" "$NEUTRINO_ABS/score/musicxml/${SCORE_ID}.musicxml"

cd "$NEUTRINO_ABS"
export LD_LIBRARY_PATH="$NEUTRINO_ABS/bin${LD_LIBRARY_PATH:+:$LD_LIBRARY_PATH}"

echo "[synth] Step 1: MusicXML → label"
bin/musicXMLtoLabel \
  "score/musicxml/${SCORE_ID}.musicxml" \
  "score/label/full/${SCORE_ID}.lab" \
  "score/label/mono/${SCORE_ID}.lab"

# ── Per-singer NEUTRINO synthesis ───────────────────────────────────────────
# synthesize_singer <model> <out_wav>
#   Runs all phrases for the given model and writes the combined WAV.
synthesize_singer() {
  local MODEL="$1"
  local OUT_WAV="$2"

  echo "[synth] Step 2: Neural synthesis → WAV (model: $MODEL)"
  local PHRASELIST="output/${SCORE_ID}-phraselist.txt"
  rm -f "$PHRASELIST"

  echo "[synth] Step 2a: bootstrap phrase 1 (generates phraselist)"
  bin/neutrino \
    "score/label/full/${SCORE_ID}.lab" \
    "score/label/timing/${SCORE_ID}.lab" \
    "output/${SCORE_ID}-1.f0" \
    "output/${SCORE_ID}-1.melspec" \
    "output/${SCORE_ID}-1.wav" \
    "model/${MODEL}/" \
    -n "$NUM_THREADS" -f "$TRANSPOSE" \
    -i "$PHRASELIST" -p 1 -m -t

  mapfile -t PL_IDX    < <(awk '{print $1}' "$PHRASELIST")
  mapfile -t PL_START  < <(awk '{print $2}' "$PHRASELIST")
  mapfile -t PL_VOICED < <(awk '{print $3}' "$PHRASELIST")
  local N_PHRASES=${#PL_IDX[@]}

  local TOTAL_MS
  TOTAL_MS=$(awk 'END{printf "%.0f", $2/10000}' "score/label/timing/${SCORE_ID}.lab")

  for (( i=0; i<N_PHRASES; i++ )); do
    local idx="${PL_IDX[$i]}"
    if [[ "${PL_VOICED[$i]}" != "1" || "$idx" == "1" ]]; then continue; fi
    local end_ms
    if (( i + 1 < N_PHRASES )); then
      end_ms="${PL_START[$((i+1))]}"
    else
      end_ms="$TOTAL_MS"
    fi
    echo "[synth] Step 2b: phrase $idx (${PL_START[$i]}–${end_ms} ms)"
    bin/neutrino \
      "score/label/full/${SCORE_ID}.lab" \
      "score/label/timing/${SCORE_ID}.lab" \
      "output/${SCORE_ID}-${idx}.f0" \
      "output/${SCORE_ID}-${idx}.melspec" \
      "output/${SCORE_ID}-${idx}.wav" \
      "model/${MODEL}/" \
      -n "$NUM_THREADS" -f "$TRANSPOSE" \
      -i "$PHRASELIST" -p "$idx" -m -t
  done

  local FIRST_IDX
  FIRST_IDX=$(awk '$3==1{print $1; exit}' "$PHRASELIST")
  local SR
  SR=$(ffprobe -v error -select_streams a:0 \
    -show_entries stream=sample_rate -of csv=p=0 \
    "output/${SCORE_ID}-${FIRST_IDX}.wav")

  local CONCAT_LIST="output/${SCORE_ID}_concat.txt"
  > "$CONCAT_LIST"
  for (( i=0; i<N_PHRASES; i++ )); do
    local idx="${PL_IDX[$i]}"
    local start_ms="${PL_START[$i]}"
    local end_ms
    if (( i + 1 < N_PHRASES )); then
      end_ms="${PL_START[$((i+1))]}"
    else
      end_ms="$TOTAL_MS"
    fi
    local dur_ms=$(( end_ms - start_ms ))
    if (( dur_ms <= 0 )); then continue; fi

    if [[ "${PL_VOICED[$i]}" == "1" ]]; then
      echo "file '$(pwd)/output/${SCORE_ID}-${idx}.wav'" >> "$CONCAT_LIST"
    else
      local sil="output/${SCORE_ID}-sil${idx}.wav"
      local dur_s
      dur_s=$(awk -v ms="$dur_ms" 'BEGIN{printf "%.6f", ms/1000}')
      ffmpeg -y -f lavfi -i "anullsrc=r=${SR}:cl=mono" \
        -t "$dur_s" -ar "$SR" -ac 1 -acodec pcm_s16le "$sil"
      echo "file '$(pwd)/$sil'" >> "$CONCAT_LIST"
    fi
  done

  ffmpeg -y -f concat -safe 0 -i "$CONCAT_LIST" \
    -acodec pcm_s16le -ar "$SR" -ac 1 "$OUT_WAV"

  rm -f "$CONCAT_LIST"
  for (( i=0; i<N_PHRASES; i++ )); do
    local idx="${PL_IDX[$i]}"
    rm -f \
      "output/${SCORE_ID}-${idx}.f0" \
      "output/${SCORE_ID}-${idx}.melspec" \
      "output/${SCORE_ID}-${idx}.wav" \
      "output/${SCORE_ID}-sil${idx}.wav"
  done

  echo "[synth] Singer $MODEL done: $OUT_WAV"
}

# ── Synthesize all singers ───────────────────────────────────────────────────
SINGER_WAVS=()
SINGER_VOLUMES=()

for entry in "${SINGER_ENTRIES[@]}"; do
  MODEL="${entry%%:*}"
  VOL="${entry##*:}"
  SINGER_WAV="output/${SCORE_ID}-${MODEL}.wav"
  synthesize_singer "$MODEL" "$SINGER_WAV"
  SINGER_WAVS+=("$(pwd)/$SINGER_WAV")
  SINGER_VOLUMES+=("$VOL")
done

# ── Mix singers (or just rename if single) ──────────────────────────────────
cd - >/dev/null

if [[ "$SINGER_COUNT" -eq 1 ]]; then
  cp "${SINGER_WAVS[0]}" "$OUT_DIR/vocal_raw.wav"
  rm -f "${SINGER_WAVS[0]}"
else
  echo "[synth] Mixing $SINGER_COUNT singers"
  FILTER=""
  INPUT_ARGS=()
  for i in "${!SINGER_WAVS[@]}"; do
    INPUT_ARGS+=("-i" "${SINGER_WAVS[$i]}")
    FILTER+="[${i}:a]volume=${SINGER_VOLUMES[$i]}[s${i}];"
  done
  # Build amix input list: [s0][s1]...[sN-1]
  MIX_INPUTS=""
  for i in "${!SINGER_WAVS[@]}"; do
    MIX_INPUTS+="[s${i}]"
  done
  FILTER+="${MIX_INPUTS}amix=inputs=${SINGER_COUNT}:normalize=0[out]"

  ffmpeg -y "${INPUT_ARGS[@]}" \
    -filter_complex "$FILTER" \
    -map "[out]" -acodec pcm_s16le "$OUT_DIR/vocal_raw.wav"

  for wav in "${SINGER_WAVS[@]}"; do rm -f "$wav"; done
fi

echo "[synth] Vocal synthesis complete: $OUT_DIR/vocal_raw.wav"

fi  # end: SKIP_VOCAL == false (NEUTRINO synthesis block)

# ── Accompaniment rendering (FluidSynth) ─────────────────────────────────────

if [[ "$NO_INST" == "true" ]]; then
  echo "[synth] no_accompaniment=true — generating 1 s silent inst placeholder"
  ffmpeg -y -f lavfi -i "anullsrc=r=44100:cl=stereo" -t 1 \
    -ar 44100 -ac 2 "$OUT_DIR/inst_raw.wav"
  echo "[synth] Done: vocal_raw.wav and inst_raw.wav written to $OUT_DIR"
  exit 0
fi

# Resolve inst file: version-level override wins over song-level default
INST_MID=""
INST_XML=""
if [[ -f "$ABS_VERSION/inst.mid" ]]; then
  INST_MID="$ABS_VERSION/inst.mid"
elif [[ -f "$ABS_SONG/inst.mid" ]]; then
  INST_MID="$ABS_SONG/inst.mid"
elif [[ -f "$ABS_VERSION/inst.musicxml" ]]; then
  INST_XML="$ABS_VERSION/inst.musicxml"
elif [[ -f "$ABS_SONG/inst.musicxml" ]]; then
  INST_XML="$ABS_SONG/inst.musicxml"
fi

INST_TMP_MID="$OUT_DIR/inst_tmp.mid"

if [[ -n "$INST_MID" ]]; then
  echo "[synth] Rendering accompaniment from inst.mid"
  fluidsynth -ni "$sf3_PATH" "$INST_MID" \
    -F "$OUT_DIR/inst_raw.wav" -r 44100

elif [[ -n "$INST_XML" ]]; then
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
    exit 1
  fi
  fluidsynth -ni "$sf3_PATH" "$INST_TMP_MID" \
    -F "$OUT_DIR/inst_raw.wav" -r 44100

else
  echo "[synth] No accompaniment file — deriving backing vocal from vocal synthesis"
  ffmpeg -y -i "$OUT_DIR/vocal_raw.wav" \
    -af "aecho=0.8:0.88:80:0.4" \
    -ar 44100 -ac 2 \
    "$OUT_DIR/inst_raw.wav"
fi

echo "[synth] Done: vocal_raw.wav and inst_raw.wav written to $OUT_DIR"
