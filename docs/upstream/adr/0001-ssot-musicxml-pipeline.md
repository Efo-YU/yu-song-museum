# ADR 0001 — SSoT MusicXML as the canonical score source

| Field | Value |
|-------|-------|
| Status | accepted |
| Date | 2026-05-28 |
| Deciders | Efo-YU |

## Context

Multi-verse songs expose a fundamental mismatch between how composers
write music and what the NEUTRINO synthesis engine expects.

**Composer's view:** A repeat section with two verses is written once
with both verse lyrics stacked (`<lyric number="1">` / `<lyric
number="2">`), plus a repeat barline.  A notation editor renders this
compactly, and both verses are maintained in one place.

**NEUTRINO's requirement:** A flat, linear MusicXML with exactly one
lyric verse, no repeat signs, no grace notes, no chord clusters in the
vocal line.

Previously this gap was bridged manually: a developer would copy the
repeated passage, inline both verses as sequential measures, and
hand-edit a separate `vocal.musicxml`.  This is error-prone and makes
pitch corrections tedious (must be applied to every copy).

A similar but simpler mismatch exists for the accompaniment:
`inst.musicxml` was a hand-split copy of the piano part, sometimes
drifting from the full score as the composition evolved.

## Decision

Introduce a single-source-of-truth (SSoT) convention:

1. The file `projects/<song>/full.musicxml` is the **canonical
   score** — the version a human edits.  It contains all parts,
   repeat signs, volta brackets, and multi-verse lyrics.

2. A new script `scripts/00_convert_ssot.py` reads `full.musicxml`
   and generates:
   - `projects/<song>/vocal.musicxml` — NEUTRINO-ready: vocal part
     only, repeats expanded, lyrics merged, artefacts cleaned.
   - `projects/<song>/inst.musicxml` — backing: accompaniment parts
     only, repeat structure preserved for DAW / FluidSynth.

3. The pipeline (`Makefile` and GHA) runs `convert-ssot` automatically
   before `synth` whenever `full.musicxml` is present.  Songs without
   `full.musicxml` are unaffected (their hand-authored files are used
   as before).

4. Generated files are committed alongside the SSoT so that the
   pipeline can run without re-generating them mid-CI (they are not
   gitignored).  The SSoT principle is enforced by convention: the
   developer workflow is edit `full.musicxml` → run `convert-ssot` →
   commit all three.

## Alternatives considered

### A. Keep hand-editing separate vocal/inst files

Rejected: O(verses × repeated-sections) maintenance cost; error rate
increases as the catalogue grows.

### B. Use music21 for repeat expansion

music21's `stream.expandRepeats()` correctly handles most repeat types.
However, the round-trip through music21 can alter notation details
(beam groups, slur bezier handles) and the lyric-verse selection logic
after expansion requires custom code regardless.  Direct XML
manipulation via `xml.etree.ElementTree` gives full control with no
additional dependency (music21 is used elsewhere in the pipeline for
MusicXML → MIDI, not for score transformation).

### C. Gitignore the generated vocal.musicxml / inst.musicxml

Pro: enforces single truth mechanically.
Con: the CI pipeline cannot run without first generating the files;
adds a mandatory pre-synth step even when `full.musicxml` has not
changed.  Given the project's current size and the need for backward
compatibility with songs that have no SSoT yet, committing the
generated files is simpler.

## Consequences

- `full.musicxml` is now the entry point for score authoring; editing
  `vocal.musicxml` / `inst.musicxml` directly is an anti-pattern.
- A change to `full.musicxml` triggers all variants of the song
  (existing `00_detect_diff.sh` already handles this).
- Songs without `full.musicxml` continue to work unchanged.
- Supported repeat constructs: forward/backward barlines and 1st/2nd
  volta brackets.  D.C./D.S./Coda and nested repeats are not supported
  in v1 (documented in `docs/developer/ssot-musicxml.md`).
- `song.json` gains an optional `ssot` field for explicit part-ID
  configuration when heuristic detection fails.
