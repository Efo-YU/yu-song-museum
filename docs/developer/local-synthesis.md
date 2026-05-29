# Running synthesis locally

This covers the full `synth → mix → video` pipeline on a developer machine,
using the `./neutrino` and `./soundfonts` mirrors that are gitignored.

> **SSoT workflow:** If a song has `projects/<song>/full.musicxml`, run
> `make SONG=<slug> convert-ssot` first to regenerate `vocal.musicxml` and
> `inst.musicxml` from it.  See
> [ssot-musicxml.md](ssot-musicxml.md) for the full authoring guide.

## Prerequisites

| Item | Location | Notes |
| ---- | -------- | ----- |
| NEUTRINO binaries + models | `./neutrino/` | gitignored mirror of the R2 prefix; contains `bin/`, `model/`, `score/`, `output/` |
| SoundFont | `./soundfonts/default.sf3` | gitignored mirror |
| Python deps | system / venv | `ffmpeg`, `fluidsynth`, `python3`; `pip install music21` for MusicXML→MIDI fallback |

> **Obtaining the binaries.** Run `make fetch-models` once after setting the R2
> env vars (`R2_ACCESS_KEY_ID`, `R2_SECRET_ACCESS_KEY`, `R2_ENDPOINT`,
> `R2_BUCKET`).  Alternatively, copy the files manually.  The layout inside
> `./neutrino/` must match what `01_fetch_models.sh` creates:
> `bin/`, `model/<SINGER>/`, `score/musicxml/`, `score/label/`, `output/`.

## Run one variant

```sh
make SONG=yamagata-shihan-kouka VARIANT=default \
     NEUTRINO_DIR=/workspaces/yu-song-museum/neutrino \
     sf3_PATH=/workspaces/yu-song-museum/soundfonts/default.sf3 \
     synth mix video
```

Outputs land in `projects/yamagata-shihan-kouka/variants/default/output/`:

| File | Description |
| ---- | ----------- |
| `vocal_raw.wav` | NEUTRINO synthesized vocal (48 kHz mono PCM) |
| `inst_raw.wav` | FluidSynth accompaniment or aecho backing vocal (44.1 kHz stereo) |
| `audio.wav` | Mixed-down WAV |
| `audio.mp3` | Mixed-down MP3 (192 kbps) |
| `temp.mp4` | Score video (without YouTube upload) |

## Run all songs (default variant)

```sh
for s in yamagata-shihan-kouka yamagata-nourin-shoyoka yamagata-koto-kouka yonezawa-kogyo-kouka; do
  make SONG=$s VARIANT=default \
       NEUTRINO_DIR=/workspaces/yu-song-museum/neutrino \
       sf3_PATH=/workspaces/yu-song-museum/soundfonts/default.sf3 \
       synth mix
done
```

`sample-song` is a placeholder; skip it unless testing the pipeline itself.

## Project directory layout

```
projects/<song-slug>/
  song.json                    # title, bpm, key, credits, page_config
  vocal.musicxml               # shared vocal score (all variants)
  inst.musicxml                # optional shared accompaniment score
  variants/
    <variant-slug>/
      variant.json             # label, build_config, score_viewer_settings
      vocal.musicxml           # optional per-variant score override
      inst.musicxml            # optional per-variant accompaniment override
      output/                  # generated files (gitignored)
```

## Environment variables

| Variable | Default | Override |
| -------- | ------- | -------- |
| `NEUTRINO_DIR` | `/tmp/neutrino` | `./neutrino` for local mirrors |
| `sf3_PATH` | `/tmp/default.sf3` | `./soundfonts/default.sf3` |
| `SINGER` | `MERROW` | Any model under `neutrino/model/` |
| `NUM_THREADS` | `4` | Raise on machines with many cores |
| `TRANSPOSE` | `0` | Semitone shift applied to synthesis |

## How synthesis works (brief)

`02_synthesize.sh` runs NEUTRINO in **per-phrase mode** to avoid OOM on long
songs (≥ ~120 s):

1. **Bootstrap phrase 1** — `bin/neutrino … -i phraselist.txt -p 1 -m -t`
   This generates the phraselist as a side effect (~8 s for a 10 s phrase).
2. **Remaining phrases** — one `bin/neutrino … -p N` call per voiced phrase.
   Each call is bounded to that phrase's audio; RAM usage stays low.
3. **Concat** — voiced phrases and silence gaps are joined with `ffmpeg -f concat`.

Score resolution order (variant-level overrides song-level):

1. `variants/<variant>/vocal.musicxml` if present
2. `vocal.musicxml` at the song root (fallback)

Same resolution applies to `inst.mid` and `inst.musicxml`.

## Troubleshooting

**`MuseScore not found; falling back to music21`** — harmless warning.
music21 handles the MusicXML→MIDI conversion.  Install MuseScore only if
you need the playback-exact rendering that MuseScore provides.

**Synthesis OOM / killed** — check that `vocal.musicxml` has phrase-boundary
rests (quarter rests at natural breath points).  Without pauses NEUTRINO
groups the entire song into one phrase, accumulating all audio in RAM.

**`inst_raw.wav` duration differs from `vocal_raw.wav`** — expected for
`yamagata-koto-kouka`, whose piano has a coda; both WAVs start at t=0 and
the mix uses the longer track.  For other songs a mismatch of more than ~1 s
indicates a missing verse in `inst.musicxml`.

**Cleaning up between runs** — `make SONG=yamagata-shihan-kouka VARIANT=default clean`
removes everything in the variant's `output/` directory.
