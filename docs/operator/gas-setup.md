# GAS relay — setup guide

The pipeline never calls the YouTube Data API directly from CI. Instead,
a Google Apps Script (GAS) Web App running under the channel owner's
Google account acts as a relay. This document describes how to configure
that relay from scratch and how to maintain it afterwards.

See also: [pipeline-checklist.md](pipeline-checklist.md) for the
overall bring-up sequence.

---

## Prerequisites

- A Google account that owns (or is a manager of) the target YouTube
  channel.
- Node.js 20+ in your environment (`node --version`).
- The `gas/` directory from this repository.

---

## 1. Install dependencies

```sh
cd gas
npm install
```

This installs `@google/clasp`, `typescript`, and
`@types/google-apps-script` locally. Do **not** use a global clasp
install — versions differ between machines.

---

## 2. Authenticate clasp with your Google account

```sh
npm run login
# → npm exec clasp login
```

A browser window opens. Sign in with the YouTube channel owner's
account (the account that will publish videos). Grant all requested
OAuth permissions — clasp needs them to create and push GAS projects.

Credentials are stored at `~/.clasprc.json` and persist across
sessions. You only need to run this once per machine.

**Important:** if you are logged in to multiple Google accounts in your
browser, confirm that the correct account is selected before approving.
The relay will upload videos as this account.

---

## 3. GAS project — current state

The GAS project has already been created and linked. The `gas/.clasp.json`
contains:

```json
{
  "scriptId": "1MV_7OsrYMfV598pzIANgjp_N2PufHUnYwwLomZtInsMG4-siJzQV8rbt",
  "rootDir": "/workspaces/yu-song-museum/gas"
}
```

`rootDir` is an absolute path specific to the dev container. If you
work on another machine (or rebuild the container to a different path),
update this field to the absolute path of the `gas/` directory on that
machine. The `scriptId` stays constant.

> **For future reference:** if you ever need to create a new GAS project
> from scratch:
> ```sh
> npm run create
> # → clasp create --type webapp --title "yu-song-museum relay"
> # Prints the new scriptId. Paste it into .clasp.json.
> ```

---

## 4. Enable the YouTube Advanced Service

The relay uses YouTube Data API v3 through GAS's "Advanced Services"
mechanism (not a direct REST call). You must enable it manually in the
GAS editor — it cannot be done via clasp.

1. Open the script in the browser:
   ```sh
   npm run open
   # → clasp open
   ```
2. In the GAS editor: click **Services** (+) in the left sidebar.
3. Search for **YouTube Data API v3**.
4. Select it, leave the identifier as `YouTube`, click **Add**.

The `appsscript.json` file already declares this service under
`enabledAdvancedServices`. The manual step above activates it on the
GAS project — the JSON declaration alone is not sufficient.

---

## 5. Push the TypeScript source

```sh
npm run push
# → clasp push
```

Clasp transpiles `src/youtube_relay.ts` and uploads it together with
`appsscript.json` to the GAS project. The `.claspignore` file prevents
`node_modules/`, `package.json`, and `tsconfig.json` from being
uploaded.

Expected output:

```
Pushing files…
└─ appsscript.json
└─ src/youtube_relay.ts
Pushed 2 files.
```

Verify in the GAS editor (`npm run open`) that `youtube_relay` appears
as a file.

---

## 6. Deploy as a Web App

1. In the GAS editor, click **Deploy → New deployment**.
2. Click the gear icon next to **Select type** and choose **Web app**.
3. Set:
   - **Description:** `initial` (or any label)
   - **Execute as:** `Me` (the channel owner account)
   - **Who has access:** `Anyone`
4. Click **Deploy**.
5. Copy the **Web App URL** — it looks like:
   ```
   https://script.google.com/macros/s/<deployment-id>/exec
   ```

Store this URL as the GHA secret `GAS_RELAY_URL` (see
[pipeline-secrets.md](pipeline-secrets.md)).

> **Access level note:** "Anyone" means anyone who knows the URL can
> POST to it. The URL is not guessable (it contains a long random ID),
> but treat it as a semi-secret. Do not publish it openly.

---

## 7. Smoke-test the relay

Before wiring up CI, test the relay manually with `curl`. First put a
small test MP4 at a reachable URL (e.g. a public R2 presigned URL or a
direct upload), then:

```sh
curl -X POST "<GAS_RELAY_URL>" \
  -H "Content-Type: application/json" \
  -d '{
    "r2_url": "<presigned-url-to-test.mp4>",
    "title": "Test upload",
    "description": "Relay smoke test",
    "privacy_status": "private"
  }'
```

Expected response:

```json
{"video_id":"xxxxxxxxxxx","url":"https://www.youtube.com/watch?v=xxxxxxxxxxx"}
```

If you receive `{"error":"..."}`, check the GAS execution log:
**Executions** in the left sidebar of the GAS editor.

---

## 8. Re-deploy after code changes

Every change to `src/youtube_relay.ts` requires a push and a new
deployment:

```sh
npm run push     # upload updated source
npm run deploy   # create new versioned deployment
```

`npm run deploy` calls `clasp deploy --description "$(date -u ...)"`.
It creates a new numbered version. The Web App URL does not change as
long as you keep deploying to the same deployment entry; the pipeline
secret does not need to be updated.

If you accidentally click **New deployment** instead of **Manage
deployments → edit**, a new URL is generated. Update `GAS_RELAY_URL`
in GitHub secrets if this happens.

---

## Troubleshooting

| Symptom | Likely cause | Fix |
|---------|-------------|-----|
| `clasp login` opens the wrong Google account | Multiple accounts in browser | Use an incognito window, or run `clasp logout` first |
| Push fails with `Permission denied` | clasp token expired or wrong account | `npm run login` again |
| Relay returns `{"error": "R2 fetch failed with HTTP 403"}` | Presigned URL expired | Increase `PRESIGNED_EXPIRY` in `scripts/05_trigger_gas.py` (currently 3600 s) |
| Relay returns `{"error": "YouTube API returned no video ID"}` | YouTube Advanced Service not enabled, or quota exceeded | Check **Services** in GAS editor; check YouTube API quota in Google Cloud Console |
| Relay returns `{"error": "Empty request body"}` | Wrong Content-Type or missing body | Ensure `scripts/05_trigger_gas.py` sends `Content-Type: application/json` |

Last reviewed: 2026-05-23
