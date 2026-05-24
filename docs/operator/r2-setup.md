# Cloudflare R2 — setup guide

The pipeline uses a Cloudflare R2 bucket for two purposes:

1. **Ephemeral model storage** — NEUTRINO binaries, model, dictionary,
   and SoundFont are downloaded from R2 into the runner's `/tmp` on each
   pipeline run and discarded when the job ends.
2. **Temporary video staging** — the generated `.mp4` is uploaded to a
   temporary R2 path, fetched by the GAS relay, and deleted after the
   YouTube upload completes.

See also: [pipeline-checklist.md](pipeline-checklist.md),
[pipeline-secrets.md](pipeline-secrets.md).

---

## 1. Create a Cloudflare account and R2 bucket

1. Log in to [Cloudflare Dashboard](https://dash.cloudflare.com/).
2. In the left sidebar, click **R2 Object Storage**.
3. Click **Create bucket**.
4. Name: something like `yu-song-museum`.
5. Location: **Automatic** unless you have a latency preference.
6. Click **Create bucket**.

Record the bucket name — it becomes the `R2_BUCKET` secret.

---

## 2. Obtain Account ID and endpoint URL

On the R2 overview page, find your **Account ID** in the right-hand
panel. Your endpoint is:

```
https://<account-id>.r2.cloudflarestorage.com
```

Record this as the `R2_ENDPOINT` secret.

---

## 3. Create an API token with R2 access

1. **R2 → Manage R2 API tokens → Create API token**
2. Settings:
   - **Token name:** `yu-song-museum-pipeline`
   - **Permissions:** `Admin Read & Write` (covers read, write, and delete)
   - **Specify bucket:** select your bucket
3. Click **Create API Token**.
4. Copy **Access Key ID** and **Secret Access Key** immediately — the
   secret is shown only once.

Record these as `R2_ACCESS_KEY_ID` and `R2_SECRET_ACCESS_KEY`.

---

## 4. Required bucket layout

The pipeline (`scripts/01_fetch_models.sh`) expects this exact structure,
derived from the NEUTRINO-online-v3.1.4 package layout.

```
<bucket>/
├── neutrino/
│   ├── bin/
│   │   ├── musicXMLtoLabel                    ← Linux x86-64 executable
│   │   ├── neutrino                           ← Linux x86-64 executable
│   │   ├── libonnxruntime.so(.1/.1.19.2)      ← ONNX Runtime (CPU+GPU)
│   │   ├── libonnxruntime_providers_cuda.so   ← CUDA execution provider
│   │   ├── libonnxruntime_providers_shared.so
│   │   ├── libcudart.so.12                    ← bundled CUDA runtime
│   │   ├── libcudnn*.so.9                     ← bundled cuDNN
│   │   ├── libcublas*.so.12
│   │   ├── libcufft.so.11
│   │   └── libstdc++.so.6
│   ├── model/
│   │   └── <SINGER_NAME>/        ← e.g. MERROW/
│   │       ├── p.bin
│   │       ├── s.bin
│   │       ├── t.bin
│   │       ├── v.bin
│   │       └── info.toml
│   └── settings/
│       └── dic/
│           ├── japanese.utf_8.conf
│           ├── japanese.utf_8.table
│           └── ...               ← all files from NEUTRINO/settings/dic/
└── soundfonts/
    └── default.sf3
```

**Notes on `bin/*.so`:** All `.so` files must be uploaded — the
executables are dynamically linked against them. The CUDA libraries
(`libcudart`, `libcudnn`, etc.) are bundled in `bin/` and loaded
via `LD_LIBRARY_PATH`. On GHA `ubuntu-latest` (no GPU), ONNX Runtime
automatically falls back to its CPU execution provider.

**`NSF/bin/` does not exist in v3.1.4** — NSF functionality is
integrated into the main `bin/`. Do not create this path.

---

## 5. Obtaining the Linux binaries

NEUTRINO's official distribution ships Windows and macOS binaries.
The Linux binaries needed for GHA (`ubuntu-latest`) must be obtained
from the **NEUTRINO Online (Google Colab)** environment, which runs on
Linux.

### Step-by-step

1. **Open the NEUTRINO Colab notebook** (`neutrino.ipynb` in the
   NEUTRINO package) in Google Colab.

2. **Run the Google Drive mount cell** and navigate to your NEUTRINO
   directory on Drive (the directory must already contain the Linux
   version of the NEUTRINO package — see note below).

3. **Extract the binaries** by running a new Colab code cell:

   ```python
   import subprocess, os, boto3
   from botocore.config import Config

   # Fill in your R2 credentials
   R2_ENDPOINT  = "https://<account-id>.r2.cloudflarestorage.com"
   R2_KEY_ID    = "<R2_ACCESS_KEY_ID>"
   R2_SECRET    = "<R2_SECRET_ACCESS_KEY>"
   BUCKET       = "yu-song-museum"
   SINGER       = "MERROW"            # adjust to your singer model name

   s3 = boto3.client("s3",
       endpoint_url=R2_ENDPOINT,
       aws_access_key_id=R2_KEY_ID,
       aws_secret_access_key=R2_SECRET,
       region_name="auto",
       config=Config(signature_version="s3v4"))

   def upload_dir(local_dir, r2_prefix):
       for root, _, files in os.walk(local_dir):
           for fname in files:
               local_path = os.path.join(root, fname)
               rel = os.path.relpath(local_path, local_dir)
               key = f"{r2_prefix}/{rel}"
               print(f"  {local_path} → {key}")
               s3.upload_file(local_path, BUCKET, key)

   # Upload Linux binaries and all shared libraries (CUDA/ONNX included)
   upload_dir("/content/drive/MyDrive/NEUTRINO/bin",         "neutrino/bin")
   # Upload singer model (p.bin s.bin t.bin v.bin info.toml)
   upload_dir(f"/content/drive/MyDrive/NEUTRINO/model/{SINGER}", f"neutrino/model/{SINGER}")
   ```

   > **Note:** The path `/content/drive/MyDrive/NEUTRINO/` must point
   > to a NEUTRINO installation that contains Linux-compatible binaries.
   > If your Drive currently has the Windows package, you will need the
   > Linux version of NEUTRINO — check the official NEUTRINO distribution
   > channel for a Linux/Colab-specific release.

4. **Upload `settings/dic/`** — these files are platform-independent
   and ship with every NEUTRINO package. Upload them from your local
   machine using the script in §6 below.

5. **Verify** by listing the bucket contents (see §7).

---

## 6. Uploading `settings/dic/` and SoundFont locally

The dictionary files and SoundFont do not require Linux binaries and
can be uploaded from any machine using the AWS CLI or rclone.

### Using AWS CLI

```sh
# Configure a profile for R2
aws configure --profile r2
# AWS Access Key ID: <R2_ACCESS_KEY_ID>
# AWS Secret Access Key: <R2_SECRET_ACCESS_KEY>
# Default region: auto
# Default output format: (leave blank)

ENDPOINT="https://<account-id>.r2.cloudflarestorage.com"
BUCKET="yu-song-museum"

# Upload settings/dic/ (from the NEUTRINO package you have locally)
aws s3 sync --profile r2 --endpoint-url "$ENDPOINT" \
  path/to/NEUTRINO/settings/dic/ \
  "s3://$BUCKET/neutrino/settings/dic/"

# Upload SoundFont (e.g. FluidR3_GM.sf3 or MuseScore General.sf3)
aws s3 cp --profile r2 --endpoint-url "$ENDPOINT" \
  path/to/default.sf3 \
  "s3://$BUCKET/soundfonts/default.sf3"
```

### Using rclone

```sh
rclone config  # create remote "r2" (type: s3, provider: Cloudflare)

rclone copy path/to/NEUTRINO/settings/dic/ \
  r2:yu-song-museum/neutrino/settings/dic/ --progress

rclone copy path/to/default.sf3 \
  r2:yu-song-museum/soundfonts/default.sf3 --progress
```

---

## 7. Verify the bucket layout

After all uploads, check the structure with the AWS CLI:

```sh
aws s3 ls --profile r2 --endpoint-url "$ENDPOINT" \
  --recursive "s3://$BUCKET/neutrino/" | awk '{print $4}' | sort
```

Confirm you see entries under each of:

- `neutrino/bin/musicXMLtoLabel`
- `neutrino/bin/neutrino`
- `neutrino/bin/libonnxruntime.so` (and other `.so` files)
- `neutrino/model/<SINGER>/`
- `neutrino/settings/dic/japanese.utf_8.conf` (and other `.conf`/`.table` files)

And separately:

- `soundfonts/default.sf3`

---

## 8. Temporary video prefix

`scripts/05_trigger_gas.py` writes temporary videos to:

```
tmp/video/<song_id>/<uuid>.mp4
```

These are created and deleted within the same pipeline run. No manual
configuration is needed.

---

## 9. CORS and public access

Keep the bucket **private**. The GAS relay fetches temporary videos
via presigned URLs (valid for 3600 s by default). The NEUTRINO model
files must not be publicly accessible due to redistribution
restrictions.

Last reviewed: 2026-05-23
