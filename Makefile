## Music Automation Pipeline — local task runner
##
## All targets accept SONG=<song-slug> VARIANT=<variant-slug>.
## They mirror the GHA pipeline steps exactly so CI behaviour
## is reproducible on a developer's machine.
##
## Prerequisites (install in your environment):
##   ffmpeg, fluidsynth, python3, pip packages: boto3 requests music21
##   NEUTRINO binaries fetched via `make fetch-models`
##
## Required env vars for targets that touch cloud resources:
##   R2_ACCESS_KEY_ID, R2_SECRET_ACCESS_KEY, R2_ENDPOINT, R2_BUCKET,
##   GAS_RELAY_URL, SINGER
##
## SSoT workflow:
##   Edit projects/<song>/full.musicxml in a notation editor, then run
##   `make SONG=<slug> convert-ssot` to regenerate vocal.musicxml and
##   inst.musicxml before running synth.

SONG        ?= yamagata-koto-kouka
VARIANT     ?= with-piano
SINGER      ?= MERROW
NEUTRINO_DIR ?= /tmp/neutrino
sf3_PATH    ?= /tmp/default.sf3
SONG_DIR     = projects/$(SONG)
VARIANT_DIR  = projects/$(SONG)/variants/$(VARIANT)

.PHONY: all fetch-models convert-ssot synth mix video upload-gas merge-songs \
        build-frontend dev-frontend \
        dev-populate dev-synth-populate \
        setup clean clean-dev help

## Run the full pipeline for one variant (except YouTube upload)
all: fetch-models convert-ssot synth mix video

## Download NEUTRINO models and SoundFont from R2
fetch-models:
	bash scripts/01_fetch_models.sh

## Convert full.musicxml SSoT into vocal.musicxml + inst.musicxml (no-op if absent)
convert-ssot:
	@if [ -f "$(SONG_DIR)/full.musicxml" ]; then \
		python3 scripts/00_convert_ssot.py --song $(SONG); \
	else \
		echo "[convert-ssot] $(SONG_DIR)/full.musicxml not found — skipping"; \
	fi

## Synthesize vocal and render accompaniment
synth:
	SONG_DIR=$(SONG_DIR) VARIANT_DIR=$(VARIANT_DIR) \
	SINGER=$(SINGER) \
	NEUTRINO_DIR=$(NEUTRINO_DIR) sf3_PATH=$(sf3_PATH) \
	bash scripts/02_synthesize.sh

## Mix vocal + accompaniment
mix:
	python3 scripts/03_mixdown.py $(VARIANT_DIR)

## Generate video (writes temp.mp4)
video:
	python3 scripts/04_generate_video.py $(SONG_DIR) $(VARIANT_DIR)

## Upload temp.mp4 via GAS relay and write meta.json
upload-gas:
	python3 scripts/05_trigger_gas.py $(SONG_DIR) $(VARIANT_DIR)

## Merge all meta.json artifacts into songs.json and copy assets
merge-songs:
	python3 scripts/06_merge_songs.py

## Build the React frontend
build-frontend:
	cd frontend && pnpm install && pnpm build

## Start the Vite dev server
dev-frontend:
	cd frontend && pnpm install && pnpm dev

## Detect which (song, variant) pairs changed (for scripting / debugging)
detect-diff:
	@bash scripts/00_detect_diff.sh

## ── Local dev helpers ────────────────────────────────────────────────────────
## Populate frontend/public/{audio,scores}/ and songs.json from local outputs.
## Run after `make synth mix` to see audio in the browser.
dev-populate:
	python3 scripts/dev-populate.py

## Synthesize + mix one variant, then populate the frontend (local dev only).
##   make dev-synth-populate SONG=yamagata-shihan-kouka VARIANT=with-organ
dev-synth-populate: convert-ssot synth mix dev-populate

## Apply local git-index settings (skip-worktree on generated files).
## Run once after a fresh clone or Dev Container rebuild.
## The devcontainer postCreateCommand calls this automatically.
setup:
	git update-index --skip-worktree frontend/src/data/songs.json

## Remove generated output for one variant
clean:
	rm -rf $(VARIANT_DIR)/output

## Remove ALL local-dev frontend assets and reset songs.json to [].
## Safe to run before committing.
clean-dev:
	rm -rf frontend/public/audio frontend/public/scores
	git restore frontend/src/data/songs.json

## Show this help
help:
	@grep -E '^##' Makefile | sed 's/## //'
