# API Specification

Base URL (local): `http://127.0.0.1:8000`

All request/response bodies are JSON unless noted otherwise. All endpoints
except `POST /auth/register`, `POST /auth/login`, and `GET /plans` require:

```text
Authorization: Bearer <access_token>
```

An access token is obtained from `POST /auth/login` and expires after
`JWT_EXPIRE_MINUTES` (default 1440 minutes / 24 hours).

Errors always come back as:

```json
{ "detail": "Human-readable error message." }
```

---

## Health

### `GET /health`

No auth required.

Response `200`:

```json
{ "status": "ok", "service": "new-cut-backend" }
```

---

## Auth

### `POST /auth/register`

Request:

```json
{ "email": "user@example.com", "password": "Password123!" }
```

`password` must be 8-128 characters.

Response `201`:

```json
{
  "id": 1,
  "email": "user@example.com",
  "plan": "free",
  "monthly_usage": 0,
  "usage_limit": 3,
  "usage_month": "2026-07",
  "created_at": "2026-07-14 00:00:00"
}
```

Errors: `409` if the email is already registered, `422` for invalid email/password shape.

### `POST /auth/login`

Request:

```json
{ "email": "user@example.com", "password": "Password123!" }
```

Response `200`:

```json
{ "access_token": "<jwt>", "token_type": "bearer" }
```

Errors: `401` for a wrong email/password.

### `GET /me`

Response `200`: same shape as the register response above (current user, including live `plan`/`usage` fields).

Errors: `401` for a missing/invalid/expired token.

---

## Usage and Plans

### `GET /usage`

Response `200`:

```json
{
  "plan": "free",
  "plan_name": "Free",
  "monthly_usage": 1,
  "usage_limit": 3,
  "remaining": 2,
  "usage_month": "2026-07",
  "max_video_minutes": 10
}
```

### `GET /plans`

No auth required.

Response `200`:

```json
[
  { "id": "free", "name": "Free", "monthly_video_limit": 3, "max_video_minutes": 10, "description": "..." },
  { "id": "lite", "name": "Lite", "monthly_video_limit": 30, "max_video_minutes": 30, "description": "..." },
  { "id": "pro", "name": "Pro", "monthly_video_limit": 150, "max_video_minutes": 120, "description": "..." }
]
```

---

## Videos

### `POST /videos/upload`

`multipart/form-data` with a single field `file` (the `.mp4`).

Response `201`: `VideoResponse` (see below).

Errors: `400` for a non-mp4 file/content-type, `413` if the file exceeds `MAX_UPLOAD_MB`.

### `POST /videos/import-youtube`

Request:

```json
{ "url": "https://www.youtube.com/watch?v=..." }
```

Only `youtube.com` / `youtu.be` hosts are accepted. Downloads and merges the
best available MP4 with `yt-dlp`.

Response `201`: `VideoResponse`.

Errors: `400` for a non-YouTube URL or a yt-dlp download failure, `413` if the
downloaded file exceeds `MAX_UPLOAD_MB`, `500` if `yt-dlp` is not installed.

### `GET /videos`

Response `200`: array of `VideoResponse`, newest first, only videos owned by the current user.

### `GET /videos/{video_id}`

Response `200`: `VideoResponse`. `404` if not found or not owned by the current user.

**`VideoResponse` shape:**

```json
{
  "id": 1,
  "original_filename": "my-video.mp4",
  "stored_filename": "3f9e....mp4",
  "content_type": "video/mp4",
  "file_size": 12345678,
  "status": "uploaded",
  "audio_path": null,
  "error_message": null,
  "created_at": "2026-07-14 00:00:00",
  "updated_at": "2026-07-14 00:00:00"
}
```

`status` is one of: `uploaded`, `extracting_audio`, `audio_extracted`, `transcribing`, `transcribed`, `failed`.

### `POST /videos/{video_id}/analyze`

Starts (or retries) FFmpeg audio extraction. On the first successful run for a
video, this also checks and increments the signed-in user's monthly usage
against their plan limits.

Response `200`: `VideoStatusResponse`:

```json
{ "id": 1, "status": "audio_extracted", "audio_path": "...", "error_message": null, "updated_at": "..." }
```

Errors:
- `404` video not found
- `409` video is in a state that cannot be (re-)analyzed right now (e.g. already `extracting_audio`)
- `403` monthly usage limit reached, or the video is longer than the plan's `max_video_minutes`
- `500` FFmpeg/FFprobe not installed, or extraction failed (message includes the FFmpeg error)

### `GET /videos/{video_id}/status`

Response `200`: `VideoStatusResponse` (see above). `404` if not found.

### `GET /videos/{video_id}/transcript`

Requires `audio_extracted` (or later) status. If a transcript already has
status `transcribed`, returns the cached row; otherwise calls the OpenAI
transcription API (chunking large audio files automatically) and stores the
result.

Response `200`:

```json
{
  "id": 1,
  "video_id": 1,
  "status": "transcribed",
  "text": "full transcript text ...",
  "segments": [ { "index": 0, "start": 0.0, "end": 4.2, "text": "..." } ],
  "error_message": null,
  "created_at": "...",
  "updated_at": "..."
}
```

Errors: `404` video not found, `409` audio not extracted yet, `400` if
`OPENAI_API_KEY` is not configured, `429`/`502`/`500` for OpenAI failures.

### `GET /videos/{video_id}/highlights`

Requires a completed transcript. Returns cached highlights if they already
exist for the video; otherwise asks GPT for 3-5 candidates, validates them,
and saves them.

Response `200`:

```json
[
  {
    "id": 1,
    "video_id": 1,
    "start_time": 12.4,
    "end_time": 45.0,
    "title": "...",
    "reason": "...",
    "content_type": "후킹형",
    "score": 87.5,
    "created_at": "..."
  }
]
```

`content_type` is one of: `정보형`, `꿀팁형`, `후킹형`, `감정형`, `논쟁형`, `웃긴 장면`.

Errors: `404` video not found, `409` transcript not completed yet, `400` if
`OPENAI_API_KEY` is not configured, `502` if GPT's JSON response could not be
parsed or had too few valid candidates.

---

## Clips

### `POST /clips/create`

Request:

```json
{ "highlight_id": 1 }
```

Renders a 9:16 center-cropped clip for the highlight's time range with FFmpeg.

Response `201`: `ClipResponse` (see below).

Errors: `404` highlight (or its video) not found/not owned, `400` invalid time
range, `500` FFmpeg not installed or clip rendering failed.

### `POST /clips/{clip_id}/subtitles`

Request:

```json
{ "style": "basic" }
```

`style` is one of `basic`, `bold`, `shorts` (default `basic`).

Builds an `.ass` subtitle file from the transcript segments overlapping the
clip, then burns it into a new mp4 with FFmpeg.

Response `200`: `ClipResponse`.

Errors: `400` invalid style, `404` clip not found, `409` clip not completed
yet or no transcript segments overlap the clip range, `500` FFmpeg not
installed or burn-in failed.

### `POST /clips/{clip_id}/narration`

Request:

```json
{ "mode": "original_audio" }
```

`mode` is `original_audio` or `ai_narration`.

- `original_audio`: just records the selected mode.
- `ai_narration`: generates a short narration script from the highlight +
  transcript with GPT, synthesizes it with OpenAI TTS, then replaces the
  clip's audio track with FFmpeg (video is copied, not re-encoded).

Response `200`: `ClipResponse`.

Errors: `400` invalid mode or missing `OPENAI_API_KEY`/TTS key, `404` clip or
highlight not found, `409` clip not completed yet, `500` FFmpeg not installed
or narration merge failed, `429`/`502` for OpenAI failures.

### `POST /clips/{clip_id}/metadata`

Generates (and caches) upload-ready title candidates, a description, and
hashtags for the clip via GPT, based on the highlight and overlapping
transcript text. If metadata already exists for the clip, returns the cached
row without calling GPT again.

Response `200`: `ClipMetadataResponse`:

```json
{
  "id": 1,
  "clip_id": 1,
  "title_candidates": ["...", "...", "..."],
  "description": "...",
  "hashtags": ["#...", "#...", "..."],
  "error_message": null,
  "created_at": "...",
  "updated_at": "..."
}
```

Errors: `404` clip/video/highlight not found, `409` no completed transcript or
no transcript overlap for the clip range, `400` missing `OPENAI_API_KEY`,
`502` if GPT's JSON response was invalid or incomplete.

### `GET /clips/{clip_id}/metadata`

Returns previously generated metadata without calling GPT. `404` if the clip
or its metadata does not exist yet (call the `POST` above first).

### `GET /clips/{clip_id}`

Response `200`: `ClipResponse`:

```json
{
  "id": 1,
  "video_id": 1,
  "highlight_id": 1,
  "output_path": "C:\\...\\outputs\\1\\....mp4",
  "subtitle_style": "basic",
  "subtitle_path": "C:\\...\\subtitles\\1\\clip_1_basic.ass",
  "subtitled_output_path": "C:\\...\\outputs\\1\\...basic_subtitled.mp4",
  "tts_mode": "original_audio",
  "narration_script": null,
  "narration_audio_path": null,
  "narrated_output_path": null,
  "status": "completed",
  "error_message": null,
  "created_at": "...",
  "updated_at": "..."
}
```

`status` is one of: `pending`, `processing`, `completed`, `failed`.

### `GET /clips/{clip_id}/download`

Streams the best available render as an `.mp4` file attachment (`narrated` >
`subtitled` > plain clip, in that priority order).

Errors: `404` clip not found, or clip found but the output file is missing on
disk (e.g. deleted manually), `409` if no output has been rendered yet.

---

## Blog Clips

Converts a Naver blog post into a vertical AI-narrated shorts video: scrape
the post's text and images, generate a narration script with GPT, synthesize
it with OpenAI TTS, render an image slideshow with FFmpeg, and burn in
auto-timed captions. Unlike `Clips` above (which is derived from an uploaded
video's highlight), a blog clip has no source video — the whole pipeline runs
in a single request.

### `POST /blog-clips`

Request:

```json
{ "url": "https://blog.naver.com/{blogId}/{logNo}", "style": "shorts" }
```

`style` is one of `basic`, `bold`, `shorts` (default `shorts`). Only
`blog.naver.com` URLs are supported today.

This call runs the full pipeline synchronously (scrape -> download images ->
GPT script -> TTS -> FFmpeg slideshow -> subtitle burn-in -> save) before
responding, so it can take from several seconds up to roughly a minute
depending on OpenAI/FFmpeg latency. There is no background job queue yet —
see `docs/PROJECT_STATUS.md` "Known Gaps" for the planned async follow-up.

Response `201`: `BlogClipResponse` (see below).

Errors:
- `400` non-Naver-blog URL, or unsupported `style`
- `409` fewer than `BLOG_IMAGE_MIN_COUNT` usable images were found on the post
- `502` the blog page could not be fetched, or its content could not be parsed
- `500` FFmpeg/FFprobe not installed, or slideshow/subtitle rendering failed
- `400` `OPENAI_API_KEY` not configured (needed for the narration script and TTS)
- `429`/`502` OpenAI rate limit or API error

### `GET /blog-clips`

Response `200`: array of `BlogClipResponse`, newest first, only blog clips owned by the current user.

### `GET /blog-clips/{blog_clip_id}`

Response `200`: `BlogClipResponse`. `404` if not found or not owned by the current user.

**`BlogClipResponse` shape:**

```json
{
  "id": 1,
  "source_url": "https://blog.naver.com/example/223000000",
  "blog_title": "...",
  "narration_script": "...",
  "subtitle_style": "shorts",
  "video_path": "C:\\...\\outputs\\1\\....mp4",
  "subtitled_video_path": "C:\\...\\outputs\\1\\..._subtitled.mp4",
  "status": "completed",
  "error_message": null,
  "title_candidates": [],
  "description": null,
  "hashtags": [],
  "metadata_error": null,
  "created_at": "...",
  "updated_at": "..."
}
```

`status` is one of: `pending`, `processing`, `completed`, `failed`.

### `POST /blog-clips/{blog_clip_id}/metadata`

Generates (and caches) upload-ready title candidates, a description, and 10
hashtags from the blog title and narration script via GPT. If metadata
already exists, returns the cached row without calling GPT again.

Response `200`: `BlogClipResponse` (with `title_candidates`/`description`/`hashtags` filled in).

Errors: `404` blog clip not found, `409` blog clip is not `completed` yet,
`400` missing `OPENAI_API_KEY`, `502` if GPT's JSON response was invalid or incomplete.

### `GET /blog-clips/{blog_clip_id}/metadata`

Same as `GET /blog-clips/{blog_clip_id}` above (kept as a separate path to
mirror the `Clips` API shape); does not call GPT.

### `GET /blog-clips/{blog_clip_id}/download`

Streams the best available render as an `.mp4` file attachment (subtitled
version if captions were burned in, otherwise the plain slideshow).

Errors: `404` blog clip not found, or found but the output file is missing on
disk, `409` if no output has been rendered yet.

---

## Not Implemented Yet

These were mentioned in the original stage plan but do not exist as separate
endpoints in the current code (see `docs/ARCHITECTURE.md` Known Limitations):

```text
GET /clips/{clip_id}/preview   -- use GET /clips/{clip_id} (output_path) or
                                   GET /clips/{clip_id}/download instead
GET /clips                     -- no "list all my clips" endpoint; clips are
                                   only reachable through their highlight_id
```
