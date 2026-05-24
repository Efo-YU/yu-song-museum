# Pipeline bring-up checklist

Work through this list top-to-bottom before triggering the pipeline
for the first time. Each item links to a detailed guide.

Estimated total time: 2–4 hours, depending on model upload speed.

---

## Phase 1 — External service setup

### 1.1 Cloudflare R2

- [ ] Create a Cloudflare account (if you do not have one).
- [ ] Create an R2 bucket. → [r2-setup.md §1](r2-setup.md#1-create-a-cloudflare-account-and-r2-bucket)
- [ ] Record your **Account ID** and construct the endpoint URL.
      → [r2-setup.md §2](r2-setup.md#2-obtain-your-account-id-and-endpoint-url)
- [ ] Create an R2 API token (Admin Read + Write).
      → [r2-setup.md §3](r2-setup.md#3-create-an-api-token-with-r2-access)
- [ ] **Upload Linux binaries** (`neutrino/bin/` — all files including `.so` libs)
      via NEUTRINO Colab. → [r2-setup.md §5](r2-setup.md#5-obtaining-the-linux-binaries)
- [ ] **Upload singer model** to `neutrino/model/<SINGER>/`.
      → [r2-setup.md §5](r2-setup.md#5-obtaining-the-linux-binaries) (Colab upload cell)
- [ ] **Upload `settings/dic/`** (platform-independent, upload locally).
      → [r2-setup.md §6](r2-setup.md#6-uploading-settingsdic-and-soundfont-locally)
- [ ] **Upload SoundFont** to `soundfonts/default.sf3`.
      → [r2-setup.md §6](r2-setup.md#6-uploading-settingsdic-and-soundfont-locally)
- [ ] Verify bucket layout. → [r2-setup.md §7](r2-setup.md#7-verify-the-bucket-layout)

### 1.2 Google Apps Script relay

- [ ] `cd gas && npm install`
- [ ] `npm run login` — authenticate clasp with the YouTube channel owner's account.
      → [gas-setup.md §2](gas-setup.md#2-authenticate-clasp-with-your-google-account)
- [ ] _(Already done)_ GAS project is linked via `gas/.clasp.json`.
      Confirm `scriptId` is not the placeholder value.
- [ ] `npm run push` — upload `youtube_relay.ts` to GAS.
      → [gas-setup.md §5](gas-setup.md#5-push-the-typescript-source)
- [ ] Enable **YouTube Data API v3** Advanced Service in the GAS editor.
      → [gas-setup.md §4](gas-setup.md#4-enable-the-youtube-advanced-service)
- [ ] Deploy as a **Web App** (Execute as: Me; Who has access: Anyone).
      → [gas-setup.md §6](gas-setup.md#6-deploy-as-a-web-app)
- [ ] Record the **Web App URL** ending in `/exec`.
- [ ] Smoke-test the relay with `curl`. → [gas-setup.md §7](gas-setup.md#7-smoke-test-the-relay)

---

## Phase 2 — GitHub repository setup

### 2.1 Enable GitHub Pages

1. Go to **Settings → Pages**.
2. Source: **GitHub Actions** (not "Deploy from a branch").
3. Click **Save**.

This creates the `github-pages` environment that `pipeline.yml`
references. The first deploy will set the published URL.

### 2.2 Add all required secrets

Add each secret listed in [pipeline-secrets.md](pipeline-secrets.md):

- [ ] `R2_ACCESS_KEY_ID`
- [ ] `R2_SECRET_ACCESS_KEY`
- [ ] `R2_ENDPOINT`
- [ ] `R2_BUCKET`
- [ ] `GAS_RELAY_URL`
- [ ] `NEUTRINO_SINGER`

### 2.3 Merge the implementation PR

The pipeline branch (`feat/music-automation-pipeline`) must be merged
to `main` before the push trigger fires:

```sh
# On GitHub: open a PR from feat/music-automation-pipeline → main
# and merge it after review.
```

---

## Phase 3 — Prepare a real song

The sample `projects/song_001/` contains a placeholder MusicXML.
Replace it with real content before running the pipeline in production:

### 3.1 Vocal MusicXML (`vocal.musicxml`)

- Must be valid MusicXML 3.1 with Japanese lyrics if using a Japanese
  singer model (NEUTRINO requires kana/romaji lyrics).
- Test locally: `make SONG=song_001 synth` (requires NEUTRINO installed
  at `/tmp/neutrino` — fetch first with `make SONG=song_001 fetch-models`).

### 3.2 Accompaniment (`inst.mid` or `inst.musicxml`)

- Provide `inst.mid` (MIDI) for direct FluidSynth rendering.
- Or `inst.musicxml` if MuseScore is installed in the environment
  (CI runner has no MuseScore — MIDI is strongly preferred).

### 3.3 JSON configuration

Review and edit:

| File                    | Key fields to check                                  |
| ----------------------- | ---------------------------------------------------- |
| `project_metadata.json` | `title`, `bpm`, `key`, `credits`                     |
| `build_config.json`     | `vocal_volume`, `inst_volume`, `resolution`          |
| `page_config.json`      | `primary_color`, `description_markdown`, `allow_mp3` |

---

## Phase 4 — First pipeline run

### 4.1 Manual trigger (recommended for first run)

1. Go to **Actions → Music Production Pipeline**.
2. Click **Run workflow**.
3. Enter `song_001` in the **song_id** field.
4. Click **Run workflow**.

Watch each job:

- **Job 0 (detect-diff):** should output `has_changes=true`
- **Job 1 (pipeline: song_001):** watch for errors in each step
- **Job 2 (deploy-web):** deploys to GitHub Pages

### 4.2 Confirm outputs

- YouTube: the channel should have a new (private or public) video.
- GitHub Pages: visit the published URL and confirm the song appears
  in the list and the embedded YouTube player works.
- Scores: click into the song page; the OSMD score viewer should render
  the MusicXML.

### 4.3 Switch to push-triggered mode

Once the manual run succeeds, all future changes to `projects/**` on
`main` trigger the pipeline automatically.

---

## Ongoing operations

| Task                                                   | Command / Location                                                                                    |
| ------------------------------------------------------ | ----------------------------------------------------------------------------------------------------- |
| Add a new song                                         | Create `projects/song_NNN/` with the three JSON files and `vocal.musicxml`, commit and push to `main` |
| Update GAS relay code                                  | `cd gas && npm run push && npm run deploy`                                                            |
| Rotate R2 credentials                                  | Create new token in Cloudflare, update GitHub secret, revoke old token                                |
| Re-process an existing song without changing its files | Trigger workflow manually with `song_id=song_NNN`                                                     |
| Check pipeline logs                                    | GitHub → Actions → select the run → expand each step                                                  |

Last reviewed: 2026-05-23
