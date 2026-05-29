/**
 * YouTube Upload Relay — Google Apps Script
 *
 * Always uploads a new video. If prev_youtube_id is supplied, that video is
 * set to unlisted first (archiving it without losing the URL).
 *
 * The version string (commit hash + date) is appended to the title so each
 * upload is identifiable in YouTube Studio, e.g. "Sample Song [rev.abc1234 · 2026-05-25]".
 *
 * Authentication: Web App runs as USER_DEPLOYING (channel owner).
 *
 * Request body (JSON):
 *   r2_url          string    — presigned GET URL for the new MP4
 *   title           string    — base video title
 *   description     string
 *   tags?           string[]
 *   privacy_status? string    — "public" | "unlisted" | "private"  (default: "public")
 *   version?        string    — appended to title as [rev.<version>]
 *   prev_youtube_id? string   — if set, this video is archived to unlisted
 *
 * Success response (200):  { "video_id": string, "url": string }
 * Error response  (200):   { "error": string }
 */

interface UploadRequest {
  api_key?: string;
  r2_url: string;
  title: string;
  description: string;
  tags?: string[];
  privacy_status?: string;
  version?: string;
  prev_youtube_id?: string;
}

interface UploadResponse {
  video_id: string;
  url: string;
}

interface ErrorResponse {
  error: string;
}

// eslint-disable-next-line @typescript-eslint/no-unused-vars
function doPost(
  e: GoogleAppsScript.Events.DoPost,
): GoogleAppsScript.Content.TextOutput {
  try {
    return handleRequest(e);
  } catch (err) {
    const message = err instanceof Error ? err.message : String(err);
    console.error("Unhandled error:", message);
    return jsonResponse({ error: message });
  }
}

function handleRequest(
  e: GoogleAppsScript.Events.DoPost,
): GoogleAppsScript.Content.TextOutput {
  if (!e.postData?.contents) throw new Error("Empty request body");

  const req = JSON.parse(e.postData.contents) as UploadRequest;

  // Validate shared secret stored in Script Properties.
  // Set via GAS UI: Project Settings → Script Properties → GAS_API_KEY.
  // If the property is absent the check is skipped (facilitates first-time setup).
  const expectedKey = PropertiesService.getScriptProperties().getProperty("GAS_API_KEY");
  if (expectedKey && req.api_key !== expectedKey) {
    throw new Error("Unauthorized");
  }

  if (!req.r2_url) throw new Error("r2_url is required");
  if (!req.title)  throw new Error("title is required");

  const privacyStatus = req.privacy_status ?? "public";
  if (!["public", "unlisted", "private"].includes(privacyStatus)) {
    throw new Error(`Invalid privacy_status: ${privacyStatus}`);
  }

  // Archive previous version to unlisted before uploading the new one
  if (req.prev_youtube_id) {
    console.log("Archiving previous video to unlisted:", req.prev_youtube_id);
    YouTube.Videos!.update(
      { id: req.prev_youtube_id, status: { privacyStatus: "unlisted" } },
      "status",
    );
  }

  // Fetch the new video blob from R2
  console.log("Fetching video from R2:", req.r2_url);
  const fetchResp = UrlFetchApp.fetch(req.r2_url, {
    method: "get",
    muteHttpExceptions: true,
  });
  if (fetchResp.getResponseCode() !== 200) {
    throw new Error(`R2 fetch failed with HTTP ${fetchResp.getResponseCode()}`);
  }
  const blob = fetchResp.getBlob().setName("video.mp4").setContentType("video/mp4");

  // Append version tag to the title for traceability in YouTube Studio
  const versionedTitle = req.version
    ? `${req.title} [rev.${req.version}]`
    : req.title;

  console.log("Uploading to YouTube:", versionedTitle);
  const inserted = YouTube.Videos!.insert(
    {
      snippet: {
        title: versionedTitle,
        description: req.description ?? "",
        tags: req.tags ?? [],
        categoryId: "10", // Music
      },
      status: { privacyStatus },
    },
    "snippet,status",
    blob,
  );

  const videoId = inserted.id;
  if (!videoId) throw new Error("YouTube API returned no video ID");

  console.log("Upload complete:", videoId);
  return jsonResponse({
    video_id: videoId,
    url: `https://www.youtube.com/watch?v=${videoId}`,
  });
}

function jsonResponse(
  data: UploadResponse | ErrorResponse,
): GoogleAppsScript.Content.TextOutput {
  return ContentService.createTextOutput(JSON.stringify(data))
    .setMimeType(ContentService.MimeType.JSON);
}
