/**
 * YouTube Upload Relay — Google Apps Script
 *
 * Two operation modes, selected by the request body:
 *
 * 1. First upload  { r2_url, title, description, tags, privacy_status }
 *    → fetches the MP4 from R2, inserts a new YouTube video, returns video_id.
 *
 * 2. Metadata update  { youtube_id, title, description, tags, privacy_status }
 *    → updates title/description/tags on an existing video, returns video_id.
 *    (YouTube Data API v3 does not support replacing video content.)
 *
 * Authentication: Web App runs as USER_DEPLOYING (channel owner).
 *
 * Success response (200):  { "video_id": string, "url": string }
 * Error response  (200):   { "error": string }   (GAS cannot return non-200)
 */

interface UploadRequest {
  r2_url?: string;       // present on first upload, absent on metadata update
  youtube_id?: string;   // present on metadata update, absent on first upload
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
  if (!req.title) throw new Error("title is required");

  const privacyStatus = req.privacy_status ?? "public";
  if (!["public", "unlisted", "private"].includes(privacyStatus)) {
    throw new Error(`Invalid privacy_status: ${privacyStatus}`);
  }

  if (req.youtube_id) {
    return updateMetadata(req, privacyStatus);
  }
  if (req.r2_url) {
    return uploadNew(req, privacyStatus);
  }
  throw new Error("Request must include either r2_url (upload) or youtube_id (update)");
}

function uploadNew(
  req: UploadRequest,
  privacyStatus: string,
): GoogleAppsScript.Content.TextOutput {
  console.log("Fetching video from R2:", req.r2_url);
  const fetchResp = UrlFetchApp.fetch(req.r2_url!, { method: "get", muteHttpExceptions: true });
  if (fetchResp.getResponseCode() !== 200) {
    throw new Error(`R2 fetch failed with HTTP ${fetchResp.getResponseCode()}`);
  }

  const blob = fetchResp.getBlob().setName("video.mp4").setContentType("video/mp4");

  console.log("Uploading to YouTube:", req.title);
  const inserted = YouTube.Videos!.insert(
    {
      snippet: {
        title: req.title,
        description: req.description ?? "",
        tags: req.tags ?? [],
        categoryId: "10",
      },
      status: { privacyStatus },
    },
    "snippet,status",
    blob,
  );

  const videoId = inserted.id;
  if (!videoId) throw new Error("YouTube API returned no video ID");

  console.log("Upload complete:", videoId);
  return jsonResponse({ video_id: videoId, url: `https://www.youtube.com/watch?v=${videoId}` });
}

function updateMetadata(
  req: UploadRequest,
  privacyStatus: string,
): GoogleAppsScript.Content.TextOutput {
  console.log("Updating metadata for video:", req.youtube_id);
  YouTube.Videos!.update(
    {
      id: req.youtube_id,
      snippet: {
        title: req.title,
        description: req.description ?? "",
        tags: req.tags ?? [],
        categoryId: "10",
      },
      status: { privacyStatus },
    },
    "snippet,status",
  );

  console.log("Metadata updated:", req.youtube_id);
  return jsonResponse({
    video_id: req.youtube_id!,
    url: `https://www.youtube.com/watch?v=${req.youtube_id}`,
  });
}

function jsonResponse(
  data: UploadResponse | ErrorResponse,
): GoogleAppsScript.Content.TextOutput {
  return ContentService.createTextOutput(JSON.stringify(data))
    .setMimeType(ContentService.MimeType.JSON);
}
