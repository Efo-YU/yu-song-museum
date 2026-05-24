## Music Automation Pipeline — local task runner
##
## All targets accept SONG=<song_id> (default: song_001).
## They mirror the GHA pipeline steps exactly so CI behaviour
## is reproducible on a developer's machine.
##
## Prerequisites (install in your environment):
##   ffmpeg, fluidsynth, python3, pip packages: boto3 requests
##   NEUTRINO binaries fetched via `make fetch-models`
##
## Required env vars for targets that touch cloud resources:
##   R2_ACCESS_KEY_ID, R2_SECRET_ACCESS_KEY, R2_ENDPOINT, R2_BUCKET,
##   GAS_RELAY_URL, SINGER

SONG        ?= song_001
SINGER      ?= MERROW
NEUTRINO_DIR ?= /tmp/neutrino
sf3_PATH    ?= /tmp/default.sf3
SONG_DIR     = projects/$(SONG)

.PHONY: all fetch-models synth mix video upload-gas merge-songs \
        build-frontend dev-frontend clean help

## Run the full pipeline for one song (except YouTube upload)
all: fetch-models synth mix video

## Download NEUTRINO models and SoundFont from R2
fetch-models:
	bash scripts/01_fetch_models.sh

## Synthesize vocal and render accompaniment
synth:
	SONG_DIR=$(SONG_DIR) SINGER=$(SINGER) \
	NEUTRINO_DIR=$(NEUTRINO_DIR) sf3_PATH=$(sf3_PATH) \
	bash scripts/02_synthesize.sh

## Mix vocal + accompaniment
mix:
	python3 scripts/03_mixdown.py $(SONG_DIR)

## Generate video (writes temp.mp4)
video:
	python3 scripts/04_generate_video.py $(SONG_DIR)

## Upload temp.mp4 via GAS relay and write meta.json
upload-gas:
	python3 scripts/05_trigger_gas.py $(SONG_DIR)

## Merge all meta.json artifacts into songs.json and copy assets
merge-songs:
	python3 scripts/06_merge_songs.py

## Build the React frontend
build-frontend:
	cd frontend && pnpm install && pnpm build

## Start the Vite dev server
dev-frontend:
	cd frontend && pnpm install && pnpm dev

## Detect which songs changed (for scripting / debugging)
detect-diff:
	@bash scripts/00_detect_diff.sh

## Remove generated output for one song
clean:
	rm -rf $(SONG_DIR)/output

## Show this help
help:
	@grep -E '^##' Makefile | sed 's/## //'
