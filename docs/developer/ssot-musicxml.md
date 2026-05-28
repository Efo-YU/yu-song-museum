# SSoT MusicXML — authoring and conversion

This document explains how to use a single combined MusicXML score
(the "SSoT") as the authoritative source for both the NEUTRINO vocal
synthesis and the FluidSynth accompaniment rendering.

Last reviewed: 2026-05-28

## The problem this solves

NEUTRINO requires a flat, linear MusicXML file — no repeat signs, a
single lyric verse in order, and no notation artefacts such as grace
notes or chords in the vocal line.  Previously, these constraints were
met by hand-editing separate `vocal.musicxml` and `inst.musicxml`
files.  With multi-verse songs the hand-editing is error-prone: the
same rhythmic passage must be duplicated once per verse, and any pitch
correction must be applied to every copy.

The SSoT approach lets the composer write a natural score — with repeat
barlines, volta brackets, and multi-verse lyrics — and delegates the
mechanical flattening to `scripts/00_convert_ssot.py`.

## File layout

```
projects/<song>/
├── full.musicxml        ← SSoT: human-authored, committed to git
├── vocal.musicxml       ← generated from full.musicxml; do not edit by hand
├── inst.musicxml        ← generated from full.musicxml; do not edit by hand
└── variants/
    └── <variant>/
        ├── variant.json
        ├── vocal.musicxml  ← optional override for this variant only
        └── inst.musicxml   ← optional override for this variant only
```

`full.musicxml` is the source of truth.  `vocal.musicxml` and
`inst.musicxml` at the song level are generated outputs — overwriting
them directly breaks the SSoT invariant.  Variant-level overrides
(under `variants/<name>/`) remain fully supported for cases that
cannot be expressed in the SSoT (e.g., a transposed edition).

Songs that do not have a `full.musicxml` continue to use their
existing hand-authored `vocal.musicxml` and `inst.musicxml`; the
conversion step is skipped automatically.

## How to author a SSoT score

1. Open MuseScore (or any MusicXML-compatible editor).
2. Create a score with **all** parts:
   - Accompaniment (piano, organ, …) as **Part 1** (or any non-vocal part name)
   - Vocal as a separate part with `instrument-sound = voice.vocals`
     or a part name containing "ボーカル", "Voice", "Vocal", etc.
3. Write repeats naturally:
   - Use forward / backward repeat barlines (`|:` / `:||`)
   - Use 1st-/2nd-ending volta brackets for different final phrases
4. Enter multi-verse lyrics in the vocal part:
   - Verse 1 → `<lyric number="1">` (MuseScore default)
   - Verse 2 → `<lyric number="2">` (MuseScore: right-click note → Add lyric → verse 2)
   - …
5. Export as **MusicXML** (`File → Export → MusicXML`).
6. Save the exported file as `projects/<song>/full.musicxml`.
7. Run the conversion (see below) and commit all three files.

### Part-name detection

The script identifies the vocal part by checking (in order):

| Priority | Check |
|----------|-------|
| 1 | `--vocal-part-id` CLI flag |
| 2 | `ssot.vocal_part_ids` in `song.json` |
| 3 | `<instrument-sound>` starting with `voice.` |
| 4 | `<part-name>` / `<part-abbreviation>` matching a vocal keyword |

Vocal keywords: `voice`, `vocal`, `soprano`, `mezzo`, `tenor`,
`baritone`, `alto`, `bass`, `choir`, `chorus`, `ソプラノ`, `メゾ`,
`アルト`, `テノール`, `バリトン`, `バス`, `ボーカル`, `合唱`, `歌`, `唱`.

If auto-detection fails, add explicit configuration to `song.json`:

```json
{
  "ssot": {
    "vocal_part_ids": ["P2"]
  }
}
```

## Running the conversion

```sh
# One song
make SONG=yamagata-koto-kouka convert-ssot

# Equivalent direct call
python3 scripts/00_convert_ssot.py --song yamagata-koto-kouka

# Force a specific SSoT file or part ID
python3 scripts/00_convert_ssot.py \
  --song yamagata-koto-kouka \
  --ssot projects/yamagata-koto-kouka/full.musicxml \
  --vocal-part-id P2
```

The script writes `vocal.musicxml` and `inst.musicxml` into the song
directory.  Commit all three files together.

The pipeline (`make all`, CI) calls `convert-ssot` automatically
before `synth`, so the generated files are always up to date.

## What the conversion does

### Vocal score (`vocal.musicxml`)

| Operation | Detail |
|-----------|--------|
| Part extraction | Remove all non-vocal parts |
| Repeat expansion | Forward/backward repeats, 1st/2nd/Nth volta brackets, D.C. al Fine, D.C. al Coda, D.S. al Fine, D.S. al Coda, Segno (𝄋), Coda (𝄌), and Fine are all unrolled into a linear sequence of measures |
| Verse merging | After expansion, each pass through a backward-repeated section selects the corresponding lyric verse (`number="1"` on pass 1, `number="2"` on pass 2, …); D.C./D.S. return passes continue the verse counter rather than resetting it; non-repeated sections fall back to verse 1 |
| Chord resolution | When multiple notes sound simultaneously (`<chord/>`), keep only the highest-pitch note |
| Grace note removal | `<grace/>` notes are deleted |
| Slur repair | Slurs that span a rest are split: a `<slur type="stop">` is added to the last sounding note before the rest, and a new `<slur type="start">` is added to the first sounding note after the rest |
| Lyric text cleaning | Japanese and common punctuation (`、`, `。`, `！`, `？`, `「」`, etc.) is stripped from `<text>` elements |
| Dummy lyric fill | Any sounding, non-tied note without a lyric receives the placeholder text `あ` |
| Layout strip | `<print>` elements and barline repeat/ending markers are removed from the expanded output |
| Leading rest | If the first measure of the expanded vocal contains sounding notes, a whole-measure rest is prepended to **both** `vocal.musicxml` and `inst.musicxml`.  NEUTRINO's `musicXMLtoLabel` requires the vocal to begin with a rest; without this it auto-inserts one (vocal only), creating a leading offset.  The decision is made once from the vocal score and applied symmetrically — songs with a piano intro (e.g. koto-kouka, whose vocal already starts with rest measures) receive no extra rest on either track. |
| Short-measure padding | NEUTRINO pads **every** short measure to the full measure duration, including anacrusis (pickup) measures even when `implicit="yes"`.  FluidSynth/music21 does not — it uses the exact notated duration.  If a song has a pickup measure shorter than the time signature (e.g. 3 beats in 4/4), the mismatch causes ≥ 0.75 s of drift per verse pass.  **Fix in `full.musicxml`:** add a rest of the missing duration before the pickup notes, so the measure is already full-length and NEUTRINO performs no padding.  Both tracks then agree on the same duration. |
| Tempo injection | If `song.json` has a `bpm` field and no `<sound tempo>` already exists in the score, a `<direction><sound tempo="N"/></direction>` is prepended to the first measure so NEUTRINO and music21/FluidSynth both use the correct tempo |

### Backing score (`inst.musicxml`)

The backing file contains the accompaniment part(s) with the repeat
structure **preserved**.  The NEUTRINO pipeline renders the backing via
FluidSynth; `02_synthesize.sh` uses music21 as a fallback for
MusicXML → MIDI conversion, and music21's `score.write('midi')`
expands repeats automatically.  This keeps the backing file useful for
DAW users who open it directly in MuseScore or Cubase.

The same tempo injection as for `vocal.musicxml` is applied so that
music21 uses the correct BPM (not its 120 BPM default) when writing MIDI.

## Known limitations

The following constructs are **not** handled by the current
implementation.  Using them in `full.musicxml` will produce an
incorrect linear expansion:

- **Nested repeats** (a repeat section that contains another repeat section)
- **Multiple D.C./D.S. jumps** in the same part (only the first is followed)

If a song requires these, either:
- Flatten the score manually in MuseScore before exporting
- Write the vocal part without repeats directly into `vocal.musicxml` and omit `full.musicxml`

## Troubleshooting

**"No vocal part detected"**
: The heuristic did not match any part.  Add `ssot.vocal_part_ids` to
  `song.json` or use `--vocal-part-id`.

**"vocal.musicxml will contain only rests"**
: The detected vocal part has no sounding notes.  Check that the vocal
  track in MuseScore is not muted / hidden, and re-export.

**Lyric appears as `あ` unexpectedly**
: The note had no lyric in the SSoT (or the lyric was stripped to empty
  by punctuation removal).  Add the lyric in MuseScore and re-export.

**Repeats not expanded correctly**
: Check that the score does not use nested repeats or multiple D.C./D.S.
  jumps (see known limitations above).  Inspect the output file manually
  to verify the expansion; `-v` verbose mode is not yet implemented.
