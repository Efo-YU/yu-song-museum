# GitHub Actions secrets reference

All secrets are stored under **GitHub repository → Settings →
Secrets and variables → Actions → Repository secrets**.

None of these values are committed to the repository. If a secret is
compromised, rotate it immediately and update the GitHub secret.

---

## Required secrets

### R2 / Cloudflare

| Secret name | Description | Where to find it |
|-------------|-------------|-----------------|
| `R2_ACCESS_KEY_ID` | R2 API token key ID | Cloudflare Dashboard → R2 → Manage R2 API Tokens → token detail |
| `R2_SECRET_ACCESS_KEY` | R2 API token secret | Shown once when the token is created — copy immediately |
| `R2_ENDPOINT` | R2 S3-compatible endpoint | `https://<account-id>.r2.cloudflarestorage.com` — Account ID is on the R2 overview page |
| `R2_BUCKET` | R2 bucket name | The name you chose when creating the bucket |

The R2 token needs **Object Read + Write + Delete** permissions on the
bucket. See [r2-setup.md](r2-setup.md) §3.

### GAS relay

| Secret name | Description | Where to find it |
|-------------|-------------|-----------------|
| `GAS_RELAY_URL` | GAS Web App deployment URL | GAS editor → Deploy → Manage deployments → copy URL ending in `/exec` |

The URL looks like:
```
https://script.google.com/macros/s/<long-id>/exec
```

See [gas-setup.md](gas-setup.md) §6.

### NEUTRINO

| Secret name | Description | Example value |
|-------------|-------------|---------------|
| `NEUTRINO_SINGER` | Singer model folder name in R2 | `MERROW` |

Must match the directory name under `neutrino/model/` in R2 exactly
(case-sensitive). See [r2-setup.md](r2-setup.md) §4.2.

---

## How to add a secret

1. Go to the repository on GitHub.
2. Click **Settings** (repository settings, not account settings).
3. In the left sidebar: **Secrets and variables → Actions**.
4. Click **New repository secret**.
5. Enter the **Name** (exactly as shown in the table above) and
   **Secret** (the value). Click **Add secret**.

Repeat for each secret in the table.

---

## Verifying secrets are wired up

After adding all secrets, trigger the pipeline manually:

1. Go to **Actions → Music Production Pipeline**.
2. Click **Run workflow** (top right).
3. In the **song** field, enter a song slug (e.g. `sample-song`).
4. In the **version** field, enter a version slug (e.g. `default`).
5. Click **Run workflow**.

Watch the run. Job 1 ("Pipeline: sample-song/default") will fail at the
"Fetch NEUTRINO models" step if the R2 secrets are wrong, and at
"Upload to YouTube" if the GAS secret is wrong. The step names make
it easy to identify which secret is misconfigured.

---

## Secret rotation

| Secret | Recommended rotation | Notes |
|--------|---------------------|-------|
| `R2_ACCESS_KEY_ID` / `R2_SECRET_ACCESS_KEY` | Annually or on suspected compromise | Create new token first, update GitHub secret, then revoke old token |
| `GAS_RELAY_URL` | Only if a new GAS deployment is created | URL is stable across `clasp deploy` re-runs of the same deployment |
| `NEUTRINO_SINGER` | Only when switching singer models | Update R2 model path at the same time |

Last reviewed: 2026-05-23
