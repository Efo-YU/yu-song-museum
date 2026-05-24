/**
 * YouTube Upload Relay — Google Apps Script
 *
 * Exposes a single POST endpoint that the GHA pipeline calls to upload a
 * video to YouTube without storing OAuth refresh tokens in CI.
 *
 * Authentication model:
 *   The Web App runs as USER_DEPLOYING (the channel owner's account).
 *   The GAS project therefore inherits the owner's YouTube quota and
 *   OAuth session — no CI-side token management required.
 *
 * Expected request body (JSON):
 *   {
 *     "r2_url":        string,   // presigned GET URL to the temp MP4 (≤1 h TTL)
 *     "title":         string,   // YouTube video title
 *     "description":   string,   // video description (plain text)
 *     "tags":          string[],  // optional tag array
 *     "privacy_status": string   // "public" | "unlisted" | "private"
 *   }
 *
 * Success response (200):
 *   { "video_id": string, "url": string }
 *
 * Error response (200 with error field — GAS cannot return non-200):
 *   { "error": string }
 *
 * Deployment:
 *   Deploy as "Web app" → Execute as: Me (channel owner)
 *                       → Who has access: Anyone (to allow CI to POST)
 *   Store the deployment URL in the GHA secret GAS_RELAY_URL.
 */

interface UploadRequest {
  r2_url: string;
  title: string;
  description: string;
  tags?: string[];
  privacy_status?: string;
}

interface UploadResponse {
  video_id: string;
  url: string;
}

interface ErrorResponse {
  error: string;
}

// GAS entry point for HTTP POST
// eslint-disable-next-line @typescript-eslint/no-unused-vars
function doPost(
  e: GoogleAppsScript.Events.DoPost,
): GoogleAppsScript.Content.TextOutput {
  try {
    return handleUpload(e);
  } catch (err) {
    const message = err instanceof Error ? err.message : String(err);
    console.error("Unhandled error:", message);
    return jsonResponse({ error: message });
  }
}

function handleUpload(
  e: GoogleAppsScript.Events.DoPost,
): GoogleAppsScript.Content.TextOutput {
  if (!e.postData || !e.postData.contents) {
    throw new Error("Empty request body");
  }

  const req = JSON.parse(e.postData.contents) as UploadRequest;

  if (!req.r2_url) throw new Error("r2_url is required");
  if (!req.title) throw new Error("title is required");

  const privacyStatus = req.privacy_status ?? "public";
  if (!["public", "unlisted", "private"].includes(privacyStatus)) {
    throw new Error(`Invalid privacy_status: ${privacyStatus}`);
  }

  // Fetch the video blob from R2 via the presigned URL
  console.log("Fetching video from R2:", req.r2_url);
  const fetchResp = UrlFetchApp.fetch(req.r2_url, {
    method: "get",
    muteHttpExceptions: true,
  });

  if (fetchResp.getResponseCode() !== 200) {
    throw new Error(
      `R2 fetch failed with HTTP ${fetchResp.getResponseCode()}`,
    );
  }

  const videoBlob = fetchResp
    .getBlob()
    .setName("video.mp4")
    .setContentType("video/mp4");

  // Build the YouTube video resource
  const videoResource: GoogleAppsScript.YouTube.Schema.Video = {
    snippet: {
      title: req.title,
      description: req.description ?? "",
      tags: req.tags ?? [],
      categoryId: "10", // Music
    },
    status: {
      privacyStatus: privacyStatus,
    },
  };

  // Upload via YouTube Data API v3 (YouTube Advanced Service)
  console.log("Uploading to YouTube:", req.title);
  const inserted = YouTube.Videos!.insert(
    videoResource,
    "snippet,status",
    videoBlob,
  );

  const videoId = inserted.id;
  if (!videoId) {
    throw new Error("YouTube API returned no video ID");
  }

  const response: UploadResponse = {
    video_id: videoId,
    url: `https://www.youtube.com/watch?v=${videoId}`,
  };

  console.log("Upload complete:", response.url);
  return jsonResponse(response);
}

function jsonResponse(
  data: UploadResponse | ErrorResponse,
): GoogleAppsScript.Content.TextOutput {
  return ContentService.createTextOutput(
    JSON.stringify(data),
  ).setMimeType(ContentService.MimeType.JSON);
}
