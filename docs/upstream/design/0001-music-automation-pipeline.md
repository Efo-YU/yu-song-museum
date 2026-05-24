---
status: accepted
date: 2026-05-23
authors: [s231268]
supersedes: []
superseded-by: null
---

# Design 0001: Music Automation Pipeline

A CI/CD-for-music-production platform that fully automates the path
from MusicXML / JSON update (push or merge) to audio synthesis,
accompaniment mix, video generation, YouTube upload, and website
deployment — processing only the songs that actually changed.

---

## 1. Design principles

### 1.1 Everything as Code & Separation of Concerns

Vocal and accompaniment data (`MusicXML`) plus metadata, audio/video
generation config, and web-display config are managed as entirely
separate JSON files. Every output artifact must be reproducible from
these declarative source files.

### 1.2 Incremental processing (diff-matrix execution)

Instead of rebuilding the whole repository on every run, `git diff`
identifies which `projects/` subdirectories changed; only those are
passed into a dynamic GHA matrix for parallel processing. This
conserves both GHA runner-minutes and external API quota.

### 1.3 Strict licensing & ephemeral resources (R2 direct fetch)

Redistribution-restricted models (e.g. NEUTRINO) and large SoundFont
files are **not** stored in GHA cache (`actions/cache`). They are
downloaded from Cloudflare R2 into the runner's `/tmp` on each run
and discarded immediately afterward.

### 1.4 GAS relay — solving the token/quota problem

Instead of calling the YouTube API directly from CI, a Google Apps
Script (GAS) Web App running under the creator's own Google account
acts as a relay. This prevents OAuth refresh-token expiry and ensures
stable uploads.

### 1.5 Storage optimisation — no video persistence

To prevent GHA artifact exhaustion, **no `.mp4` files are ever saved
as GHA artifacts**. A generated video is uploaded to a temporary R2
location, forwarded to YouTube via GAS, and then immediately deleted.
Audio files (`.wav` / `.mp3`) are retained for a short window
(e.g. 7 days) as the only persistent binary artifact.

### 1.6 Local / CI consistency (shared script layer)

All processing logic lives as modular scripts under `scripts/` and is
invoked uniformly via `Makefile`. This eliminates divergence between
the local development environment and the GHA Ubuntu CPU runner.

### 1.7 Client-side score rendering (frontend offload)

Rather than running a headless browser in CI to produce score images,
the React frontend uses **OpenSheetMusicDisplay (OSMD)** to render
MusicXML client-side. CI is kept free of browser dependencies.

---

## 2. Architecture

### 2.1 Pipeline sequence

```
Push / Merge
    │
    ▼
Job 0 — Diff detect
  git diff → list of changed projects/ dirs → JSON array
    │ (skip if empty)
    ▼
Job 1 — Pipeline matrix  (one instance per changed song, run in parallel)
  ├─ Fetch ephemeral models from R2 → /tmp
  ├─ Synthesize (NEUTRINO) + render accompaniment (FluidSynth) → audio.wav
  ├─ actions/upload-artifact  audio.wav  (7-day retention)
  ├─ Generate video → temp.mp4
  ├─ Upload temp.mp4 to R2 (temporary path)
  ├─ POST temp R2 URL + metadata → GAS Web App
  │       GAS fetches temp.mp4, uploads to YouTube, returns video ID
  ├─ Delete temp.mp4 locally and delete R2 object
  └─ actions/upload-artifact  meta.json (video ID + metadata)
    │
    ▼  (after all matrix instances complete)
Job 2 — Web deploy  [concurrency group: deploy-web]
  ├─ Download all meta.json artifacts
  ├─ Merge into songs.json
  ├─ Copy MusicXML and audio to frontend/public/
  ├─ Vite build
  └─ Deploy to GitHub Pages
```

### 2.2 Component diagram

```
┌─────────────────────────────────┐
│           Git Repository         │
│  scripts/00_detect_diff.sh       │
│  projects/song_XXX/              │
└────────────┬────────────────────┘
             │ Push / Merge
             ▼
┌─────────────────────────────────────────────────────┐
│                  GitHub Actions                      │
│                                                      │
│  Job 0: Diff Detect                                  │
│    └──[JSON array of changed songs]──►               │
│                                                      │
│  Job 1: Pipeline Matrix (per song)                   │
│    ├─ Synth & Mix ─────────────────► Audio Artifact  │
│    ├─ Video Gen                                       │
│    └─ GAS Trigger ─────────────────► meta.json Artif │
│                                                      │
│  Job 2: Web Deploy [concurrency: deploy-web]         │
│    ├─ Merge meta.json → songs.json                   │
│    └─ Vite build → GitHub Pages                      │
└────────────────────────┬────────────────────────────┘
                         │
          ┌──────────────┼──────────────┐
          ▼              ▼              ▼
  ┌──────────────┐  ┌─────────┐  ┌──────────────┐
  │ Cloudflare R2│  │ GAS Web │  │   YouTube    │
  │ - Models     │  │  App    │  │              │
  │ - Temp MP4   │  └────┬────┘  └──────────────┘
  └──────────────┘       │ Upload via YouTube Data API
                         └──────────────────────────►

  ┌─────────────────────────────────────┐
  │       GitHub Pages (Frontend)        │
  │  React SPA  +  OSMD (CSR)            │
  │  songs.json · MusicXML · audio       │
  └─────────────────────────────────────┘
```

---

## 3. Repository layout

```
.
├── .github/
│   └── workflows/
│       └── pipeline.yml           # GHA workflow (Job 0–2, serial/matrix)
│
├── projects/                      # Per-song source files
│   └── song_001/
│       ├── project_metadata.json  # Title, BPM, key, credits
│       ├── build_config.json      # Gain, effects, video resolution
│       ├── page_config.json       # Theme colour, OSMD zoom, download flags
│       ├── vocal.musicxml         # Vocal part
│       └── inst.musicxml          # Accompaniment part (or MIDI)
│
├── scripts/                       # Execution modules — GHA and local share these
│   ├── 00_detect_diff.sh          # Identify changed projects/ subdirectories
│   ├── 01_fetch_models.sh         # Download models from R2 (no GHA cache)
│   ├── 02_synthesize.sh           # NEUTRINO synthesis + FluidSynth render
│   ├── 03_mixdown.py              # FFmpeg mix driven by build_config.json
│   ├── 04_generate_video.py       # Video generation (MoviePy etc.)
│   └── 05_trigger_gas.py          # R2 temporary upload + GAS relay call
│
├── gas/
│   └── youtube_relay.gs           # GAS — YouTube Advanced Service upload
│
├── frontend/                      # React + Vite SPA
│   ├── public/
│   │   └── scores/                # MusicXML placed here at deploy time
│   ├── src/
│   │   ├── components/
│   │   │   └── ScoreViewer.tsx    # OSMD client-side rendering component
│   │   └── data/
│   │       └── songs.json         # Generated by Job 2; song database
│   ├── package.json
│   └── vite.config.js
│
└── Makefile                       # Local task runner (make synth SONG=song_001)
```

---

## 4. Configuration schema (Separation of Concerns)

Each song directory holds three JSON files with distinct responsibilities.

### 4.1 `project_metadata.json` — single source of truth

Used by: video title/credits overlay, YouTube description, web page header.

```jsonc
{
  "id": "song_001",
  "title": "Song Title",
  "bpm": 120,
  "key": "C major",
  "credits": {
    "vocalist": "...",
    "composer": "...",
    "lyricist": "..."
  }
}
```

### 4.2 `build_config.json` — build engine configuration

Used by: `02_synthesize.sh` through `04_generate_video.py`.

```jsonc
{
  "audio_settings": {
    "vocal_volume": 1.0,
    "inst_volume": 0.8,
    "effects": []
  },
  "video_settings": {
    "resolution": "1920x1080",
    "fps": 30,
    "style": "waveform",
    "background_image_path": "assets/bg.png"
  }
}
```

### 4.3 `page_config.json` — frontend configuration

Used by: React components after Job 2 merges it into `songs.json`.

```jsonc
{
  "theme": {
    "primary_color": "#4a90d9"
  },
  "description_markdown": "...",
  "score_viewer_settings": {
    "default_zoom": 1.0,
    "default_visible_parts": ["vocal", "inst"]
  },
  "downloads": {
    "allow_xml": true,
    "allow_mp3": true
  }
}
```

---

## 5. Step-by-step execution notes

### Step 0 — Diff detection (Job 0)

`git diff HEAD~1 HEAD --name-only` identifies every changed file; the
script extracts the set of `projects/song_XXX/` prefixes and emits a
JSON array. If the array is empty, all downstream jobs are skipped.
The array is passed to `strategy: matrix` in Job 1.

### Step 1 — Synthesis and mix (Job 1)

* **Timeout**: no explicit `timeout-minutes` is set; GPU-less audio
  rendering on a CPU runner is slow and accepted as-is.
* **Local parity**: each CI step calls `make <target> SONG=<id>` so
  the exact same command works locally.
* **Future score-sync video**: if per-frame score synchronisation is
  ever needed inside the video, it will be implemented inside
  `04_generate_video.py` by parsing MusicXML timestamps — not in the
  web frontend.

### Step 2 — YouTube upload via GAS relay (Job 1)

1. `04_generate_video.py` produces `temp.mp4`.
2. `05_trigger_gas.py` uploads `temp.mp4` to a temporary R2 path,
   then POSTs `{r2_url, metadata}` to the GAS Web App.
3. GAS fetches the video from R2, uploads it to YouTube (YouTube
   Advanced Service), and returns the video ID.
4. `05_trigger_gas.py` deletes `temp.mp4` locally and the R2 object.
5. Video ID plus metadata are written to `meta.json` and saved as a
   GHA artifact.

### Step 3 — Web deploy (Job 2)

* **Concurrency**: `concurrency: group: deploy-web` serialises the
  deploy step even when multiple matrix instances finish around the
  same time, preventing `songs.json` merge conflicts.
* `songs.json` is built by merging all `meta.json` artifacts from the
  current run with the previous `songs.json` from the Pages branch.
* MusicXML files and audio are copied into `frontend/public/` so the
  React app can fetch them at runtime; OSMD renders the scores
  client-side without any CI image-generation step.

---

## 6. Open questions / deferred decisions

| # | Question | Notes |
|---|----------|-------|
| 1 | NEUTRINO model versioning and R2 path scheme | Needs an ADR once a versioning policy is chosen |
| 2 | R2 temporary URL expiry window | Must be long enough for GAS to fetch but short enough to limit exposure |
| 3 | Exact Vite / React dependency versions | Verify at scaffold time via `pnpm create vite` |
| 4 | GAS deployment and secret management | OAuth client ID / secret stored in GHA secrets; relay URL stored separately |
| 5 | Error recovery — partial matrix failure | Define whether a failed song blocks the web deploy or is silently skipped |
