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

Converts a blog/article post into a vertical AI-narrated shorts video: scrape
the post's text and images, generate a narration script with GPT, synthesize
it with OpenAI TTS, render an image slideshow with FFmpeg, and burn in
auto-timed captions. Unlike `Clips` above (which is derived from an uploaded
video's highlight), a blog clip has no source video.

As of Stage 16, any blog/article URL is accepted, not just
`blog.naver.com`. Naver blog posts use a dedicated scraper that targets
Naver's known post structure exactly; every other URL goes through a generic
best-effort scraper (common container selectors, falling back to "the
`<div>` with the most text" if none match) — see `docs/PROJECT_STATUS.md`
"Stage 16 details" for how it works and its limitations (heavily
JS-rendered pages or scraping-blocked sites can still fail).

As of Stage 15, this pipeline runs **asynchronously**. As of Stage 17 it is
a **multi-phase** job; Stage 18 adds a board-editing phase:

1. `POST /blog-clips` inserts a `pending` row and returns immediately. Phase 1
   (scrape -> download image candidates -> generate three script-tone
   candidates) runs in the background until `status: "awaiting_images"`.
2. `PUT /blog-clips/{id}/images/selection` confirms which candidates to use
   and moves to `status: "awaiting_script"`.
3. `POST /blog-clips/{id}/select-script` with a chosen tone auto-creates
   boards (one per **selected** image) and stops at `status: "awaiting_boards"`.
4. While `awaiting_boards`, use the board CRUD/reorder endpoints to edit
   scenes (optional).
5. `POST /blog-clips/{id}/render` resumes Phase 2 (TTS -> slideshow ->
   subtitle burn-in) until `completed` or `failed`. The first completed
   output is also stored as a `blog_clip_versions` row (Stage 24).
6. After `completed`, `POST /blog-clips/{id}/versions` can queue additional
   renders (other tones or board regenerate) without resetting the parent.

Poll `GET /blog-clips/{blog_clip_id}` (e.g. every 2 seconds) while status is
`pending`/`processing`. Stop polling when status is `awaiting_images`,
`awaiting_script`, `awaiting_boards`, `completed`, or `failed`. Poll
`GET /blog-clips/{id}/versions` while any version is `pending`/`processing`.

### `POST /blog-clips`

Request:

```json
{
  "url": "https://blog.naver.com/{blogId}/{logNo}",
  "style": "shorts",
  "target_length": "short",
  "narration_language": "original"
}
```

- `style`: `basic` \| `bold` \| `shorts` (default `shorts`)
- `target_length`: `short` \| `long` (default `short`) — biases GPT candidate
  length (~10–20s vs ~30–45s)
- `narration_language`: `original` \| `ko` \| `en` \| `ja` (default `original`)
  — language for narration scripts (`original` matches the source post)
- `url`: any valid HTTP(S) URL — Naver blog posts and most other blog/article
  URLs (Tistory, brunch, news sites, etc.) are supported, see the Stage 16 note
  above

Validates the URL/options and inserts the row synchronously, then schedules
Phase 1 in the background. The response reflects the freshly created row
before any pipeline work has happened: `status: "pending"`,
`progress_stage: "queued"`, `progress_percent: 0`.

Response `201`: `BlogClipResponse` (see below).

Errors from request validation (returned synchronously, before scheduling
the background task):
- `400` unsupported `style`, `target_length`, or `narration_language`
- `422` malformed `url` (not a valid HTTP(S) URL)

Errors that can occur during the background pipeline (not returned by this
call — they instead show up as `status: "failed"` with `error_message` set
when you poll `GET /blog-clips/{blog_clip_id}` afterward):
- fewer than `BLOG_IMAGE_MIN_COUNT` usable images were found on the post
- the blog page could not be fetched, its content could not be parsed, or
  (for a Naver URL) the blog ID/post number couldn't be extracted from the URL
- GPT returned incomplete script-tone candidates
- FFmpeg/FFprobe not installed, or slideshow/subtitle rendering failed
  (Phase 2, after script selection)
- `OPENAI_API_KEY` not configured (needed for the narration script and TTS)
- OpenAI rate limit or API error

### `GET /blog-clips/{blog_clip_id}/images`

List image candidates for the blog short (after Phase 1 has downloaded them).

Response `200`: array of:

```json
{
  "id": 1,
  "blog_clip_id": 3,
  "order_index": 0,
  "source_url": "https://...",
  "selected": true,
  "created_at": "...",
  "updated_at": "..."
}
```

### `PUT /blog-clips/{blog_clip_id}/images/selection`

Confirm which candidates to use. Allowed only while `status` is
`awaiting_images`. Enforces `BLOG_IMAGE_MIN_COUNT` … `BLOG_IMAGE_MAX_COUNT`
(default 3–8). On success moves to `awaiting_script`.

Request:

```json
{ "image_ids": [1, 3, 5] }
```

Response `200`: `BlogClipResponse` with `status: "awaiting_script"`.

Errors: `404`, `409` not `awaiting_images`, `400` invalid count / ids.

### `GET /blog-clips/{blog_clip_id}/images/{image_id}/file`

Authenticated image stream for candidate preview (same media types as board
images).

### `POST /blog-clips/{blog_clip_id}/select-script`

Choose one of the three generated narration tones. Allowed only after image
selection (`awaiting_script`). Auto-creates boards from **selected** images
and pauses for editing — does **not** start rendering.

Request:

```json
{ "tone": "hook" }
```

`tone` is one of `summary`, `hook`, `detailed`.

Response `200`: `BlogClipResponse` with the selected `script_tone`,
`narration_script` filled from that candidate, and status moved to
`awaiting_boards` / `awaiting_boards` (50%). Use the board endpoints to
inspect or edit boards, then call `POST .../render`.

Errors:
- `400` unsupported `tone`
- `404` blog clip not found
- `409` blog clip is not currently `awaiting_script`, or the chosen tone is
  missing from `script_candidates`

### `GET /blog-clips/{blog_clip_id}/boards`

Response `200`: array of `BoardResponse`, sorted by `order_index`.

```json
[
  {
    "id": 1,
    "blog_clip_id": 7,
    "order_index": 0,
    "image_path": "C:\\...\\storage\\blog\\images\\1\\7\\abc.jpg",
    "text": "첫 번째 보드 나레이션",
    "speaker": null,
    "duration_seconds": null,
    "created_at": "...",
    "updated_at": "..."
  }
]
```

Allowed in any status (read-only). Returns `[]` for legacy completed clips
with no boards.

### `POST /blog-clips/{blog_clip_id}/boards`

Add a board using an already-downloaded image from this blog clip.

Request:

```json
{ "image_path": "C:\\...\\abc.jpg", "text": "추가 문구", "order_index": null }
```

Response `201`: `BoardResponse`.

Errors: `400` invalid `image_path`, `404` not found, `409` status is not
`awaiting_boards`.

### `PATCH /blog-clips/{blog_clip_id}/boards/{board_id}`

Request (all fields optional; omitted fields are left unchanged):

```json
{
  "text": "수정된 문구",
  "duration_seconds": 3.5,
  "image_path": "C:\\...\\other.jpg",
  "speaker": "nova"
}
```

`speaker` is an OpenAI voice id from `GET /voices`, or `null` / `""` to clear
back to the default (`OPENAI_TTS_VOICE`). Unknown ids return `400`.

`sfx_asset_id` (Stage 23) is an `audio_assets` id with `kind=sfx`, or `null`
to clear. Plays at the board's start during render mix.

Response `200`: `BoardResponse`.

### `PATCH /blog-clips/{blog_clip_id}/tts-settings`

Set narration playback speed for the next render (Stage 21). Only while
`awaiting_boards`.

Request:

```json
{ "tts_speed": 1.1 }
```

`tts_speed` must be between `0.25` and `4.0`.

Response `200`: `BlogClipResponse` (includes updated `tts_speed`).

### `PATCH /blog-clips/{blog_clip_id}/default-voice`

Set the project default AI voice and speed (W3). Only while `awaiting_boards`.

Request:

```json
{ "voice_id": "alloy", "tts_speed": 1.0, "apply_to_all_boards": true }
```

- `voice_id`: OpenAI TTS catalog id from `GET /voices`
- `tts_speed`: `0.25`–`4.0` (also updates clip `tts_speed`)
- `apply_to_all_boards`: when true (default), sets every board `speaker` to
  `voice_id`

Stores `blog_clips.default_voice` as fallback when a board `speaker` is null.

Response `200`: `BlogClipResponse`.

### `PATCH /blog-clips/{blog_clip_id}/wizard-step`

Persist the client wizard sub-step while `status` is `awaiting_boards`.
Used so reopening a project from the workroom restores the flow step.

Request:

```json
{ "wizard_step": "video_style" }
```

`wizard_step` is one of `video_style`, `edit_mode`, `quick`, `ready`
(legacy `boards`/`voice`/`style` coerce to `edit_mode`).  
`select-script` seeds `wizard_step` to `edit_mode`.
Quick path uses `edit_mode` → `video_style` → `quick`. Detail path picks style inside BoardEditor.

Response `200`: `BlogClipResponse`.

Errors: `404`, `409` not `awaiting_boards`, `400` invalid step.

### `GET /visual-styles`

List system visual style presets (Remotion layout/caption packs).

Response `200`: array of
`{ slug, label, description, badge, previewImage, layout, caption, transitionSec, kenBurns }`.

### `PATCH /blog-clips/{blog_clip_id}/visual-style`

Set Remotion visual style while `awaiting_boards`.

Request:

```json
{ "visual_style": "card_news" }
```

`visual_style` is one of `fullscreen`, `card_news`, `info_dark`, `bold_hook`.

Response `200`: `BlogClipResponse` with updated `visual_style`.

### `PATCH /blog-clips/{blog_clip_id}/template`

Apply a subtitle template to this blog clip (Stage 22). Only while
`awaiting_boards`. The template must be a system preset or owned by the user.

Request:

```json
{ "template_id": 3 }
```

Response `200`: `BlogClipResponse` with updated `subtitle_template_id`
(and `subtitle_style` set to the system slug when the template is a builtin).

Errors: `404` blog clip or template not found, `409` status is not
`awaiting_boards`.

### `PATCH /blog-clips/{blog_clip_id}/audio-settings`

Set BGM / auto-audio flags for the next render (Stage 23 + W4). Only while
`awaiting_boards`.

Request (fields optional; omitted fields unchanged):

```json
{ "bgm_asset_id": 1, "bgm_volume": 0.18, "auto_bgm": false, "auto_sfx": true }
```

- `bgm_asset_id`: `audio_assets` id with `kind=bgm`, or `null` to turn BGM off.
  Setting a concrete id clears `auto_bgm`.
- `bgm_volume`: `0.0`–`0.5` (hard cap so BGM cannot bury TTS; default `0.18`)
- `auto_bgm`: when true, clears `bgm_asset_id`; at `POST .../render` the
  server picks a system BGM from `target_length` + `script_tone`
- `auto_sfx`: when true, at render start places a system SFX on boards after
  the first (transitions)

Response `200`: `BlogClipResponse`.

Per-board SFX uses `PATCH .../boards/{board_id}` with `{ "sfx_asset_id": 3 }`
(or `null` to clear). SFX plays at that board's start time during `amix`.

### `DELETE /blog-clips/{blog_clip_id}/boards/{board_id}`

Response `204`. Remaining boards are reindexed 0..N-1.

### `GET /blog-clips/{blog_clip_id}/boards/{board_id}/image`

Streams the board's image file for authenticated preview/thumbnail use.
Ownership is checked; the path must resolve inside that clip's downloaded
image directory.

Response `200`: image bytes (`image/jpeg`, `image/png`, etc.).

Errors: `404` blog clip or board not found, or file missing on disk;
`400` if the stored path is outside the clip image folder.

The browser cannot use the absolute `image_path` from `BoardResponse`
directly — clients should `fetch` this endpoint with
`Authorization: Bearer ...` and display via a blob URL.

### `PUT /blog-clips/{blog_clip_id}/boards/reorder`

Request:

```json
{ "board_ids": [12, 10, 11] }
```

Must be a permutation of all current board IDs.

Response `200`: full reordered `BoardResponse` list.

### `GET /blog-clips/{blog_clip_id}/stock-search`

Search free stock photos via Pexels for use on boards (Stage 20).

Query params:
- `query` (required): search keywords
- `page` (optional, default `1`, >= 1)
- `per_page` (optional, default `12`, 1–24)

Requires `PEXELS_API_KEY` in the backend environment. Portrait orientation is
requested from Pexels to better match 9:16 boards.

Response `200`:

```json
{
  "query": "cafe",
  "page": 1,
  "per_page": 12,
  "total_results": 8000,
  "photos": [
    {
      "id": 123,
      "photographer": "Jane Doe",
      "alt": "Latte art",
      "preview_url": "https://images.pexels.com/...",
      "download_url": "https://images.pexels.com/...",
      "width": 3000,
      "height": 4000
    }
  ]
}
```

Errors:
- `404` blog clip not found / not owned
- `400` missing/invalid `PEXELS_API_KEY`, empty query, or invalid paging
- `502` upstream Pexels request failed

### `POST /blog-clips/{blog_clip_id}/boards/{board_id}/stock-image`

Download a Pexels image URL into this clip's image folder and set it as the
board's `image_path`. Only allowed while status is `awaiting_boards`.
Only `images.pexels.com` URLs are accepted.

Request:

```json
{ "download_url": "https://images.pexels.com/photos/..." }
```

Response `200`: updated `BoardResponse`.

Errors:
- `404` blog clip or board not found
- `400` missing/invalid API key, non-Pexels URL, or status is not
  `awaiting_boards` (same mutation gate as other board edits)
- `502` download failed

### `POST /blog-clips/{blog_clip_id}/render`

Confirm boards and start Phase 2 rendering.

Response `200`: `BlogClipResponse` with `status: "processing"`,
`progress_stage: "synthesizing_audio"` (55%). Rendering continues in the
background.

Errors:
- `404` not found
- `409` status is not `awaiting_boards`, or zero boards remain, or all board
  texts are empty

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
  "script_tone": "hook",
  "script_candidates": {
    "summary": "...",
    "hook": "...",
    "detailed": "..."
  },
  "subtitle_style": "shorts",
  "subtitle_template_id": 3,
  "video_path": "C:\\...\\outputs\\1\\....mp4",
  "subtitled_video_path": "C:\\...\\outputs\\1\\..._subtitled.mp4",
  "status": "completed",
  "progress_stage": "done",
  "progress_percent": 100,
  "error_message": null,
  "title_candidates": [],
  "description": null,
  "hashtags": [],
  "metadata_error": null,
  "tts_speed": 1.0,
  "bgm_asset_id": null,
  "bgm_volume": 0.18,
  "active_version_id": 1,
  "target_length": "short",
  "narration_language": "original",
  "default_voice": "alloy",
  "auto_bgm": false,
  "auto_sfx": false,
  "wizard_step": "video_style",
  "visual_style": "fullscreen",
  "created_at": "...",
  "updated_at": "..."
}
```

`tts_speed` is the OpenAI TTS speed used at render (default `1.0`).
`subtitle_template_id` selects the ASS caption preset for blog render
(Stage 22); when null, `subtitle_style` builtin fallback is used.
`bgm_asset_id` / `bgm_volume` control optional BGM mix (Stage 23).
`active_version_id` points at the version mirrored into this row's path/
metadata fields (Stage 24); parent `GET .../download` still returns that
active output.
`target_length` / `narration_language` are set at create time (W1) and
influence Phase 1 GPT script candidates only.
`default_voice` (W3) is the clip-level voice fallback; `auto_bgm` /
`auto_sfx` (W4) are resolved at render start.
`visual_style` selects the Remotion layout/caption preset.
`wizard_step` is the flow sub-step while
`awaiting_boards` (null otherwise / earlier phases).

`status` is one of: `pending`, `processing`, `awaiting_images`,
`awaiting_script`, `awaiting_boards`, `completed`, `failed`.

`progress_stage` is one of (in order): `queued` (0%), `scraping` (10%),
`downloading_images` (25%), `generating_script` (40%), `awaiting_images`
(42%, waits for image selection), `awaiting_script` (45%, waits for
`select-script`), `awaiting_boards` (50%, waits for board edits + `render`),
`synthesizing_audio` (55%), `rendering_video` (75%), `burning_subtitles`
(90%), `done` (100%). A `failed` row keeps whatever
`progress_stage`/`progress_percent` it last reached before the error, so you
can tell which step failed.

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
version if captions were burned in, otherwise the plain slideshow). This is
the **active** version (Stage 24); use the per-version download endpoint for
other outputs.

Errors: `404` blog clip not found, or found but the output file is missing on
disk, `409` if no output has been rendered yet.

### `GET /blog-clips/{blog_clip_id}/versions`

Authenticated. Lists version rows for the clip (newest/oldest by id ascending).
Completed clips created before Stage 24 get a single backfilled version on
first list.

Response `200`: array of `BlogClipVersionResponse`.

### `POST /blog-clips/{blog_clip_id}/versions`

Queue one or more additional renders. Parent must be `completed`.

Request:

```json
{ "mode": "all_tones", "tone": null, "set_active": false }
```

- `mode: "boards"` — re-render current boards as a new version (label
  `보드 재생성`).
- `mode: "tone"` — render one candidate tone (`tone` required); does not
  overwrite stored boards.
- `mode: "all_tones"` — queue every candidate tone that does not already
  have a pending/processing/completed version.

Response `201`: array of newly created `BlogClipVersionResponse` rows
(`status: "pending"`). Each continues in the background via
`run_blog_clip_version_pipeline`.

Errors: `404` not found, `400` bad mode/tone, `409` parent not completed /
no boards / no remaining tones.

### `POST /blog-clips/{blog_clip_id}/versions/{version_id}/set-active`

Copy a completed version onto the parent row (`video_path`, script, metadata,
`active_version_id`). Response `200`: `BlogClipVersionResponse` with
`is_active: true`.

### `POST /blog-clips/{blog_clip_id}/versions/{version_id}/metadata`

GPT upload metadata for that version's narration (cached on the version row).
If the version is active, parent metadata fields are synced too.

### `GET /blog-clips/{blog_clip_id}/versions/{version_id}/download`

Streams that version's `.mp4` (`new-cut-blog-{id}-v{version_id}.mp4`).

**`BlogClipVersionResponse` shape:**

```json
{
  "id": 2,
  "blog_clip_id": 1,
  "label": "요약형",
  "source": "tone",
  "script_tone": "summary",
  "narration_script": "...",
  "video_path": "...",
  "subtitled_video_path": "...",
  "status": "completed",
  "progress_stage": "done",
  "progress_percent": 100,
  "error_message": null,
  "title_candidates": [],
  "description": null,
  "hashtags": [],
  "metadata_error": null,
  "is_active": false,
  "created_at": "...",
  "updated_at": "..."
}
```

## Voices (Stage 21)

### `GET /voices`

Authenticated. Returns the OpenAI TTS voice catalog used for board
`speaker` assignment.

Response `200`:

```json
[
  {
    "id": "alloy",
    "name": "Alloy",
    "description": "중립적이고 또렷한 기본 보이스"
  }
]
```

### `GET /voices/{voice_id}/sample`

Authenticated. Returns a cached MP3 preview for the voice (generated on first
request; requires a TTS/OpenAI API key).

Response `200`: `audio/mpeg`.

Errors: `400` unknown voice or missing TTS API key, `502` upstream TTS failure.

## Subtitle templates (Stage 22)

### `GET /subtitle-templates`

Authenticated. Lists system presets (`is_system: true`, slugs `basic` /
`bold` / `shorts`) plus the current user's custom templates.

### `POST /subtitle-templates`

Create a custom template.

Request (common fields):

```json
{
  "name": "노란 박스",
  "font_size": 70,
  "primary_color": "#FFFF00",
  "outline_color": "#000000",
  "back_color": "#000000",
  "bold": true,
  "outline": 4,
  "shadow": 1,
  "margin_v": 200,
  "border_style": 3
}
```

Colors are `#RRGGBB`. `border_style` is `1` (outline) or `3` (opaque
background box). Response `201`: `SubtitleTemplateResponse`.

### `PATCH /subtitle-templates/{template_id}`

Update a custom template (system presets return `400`).

### `POST /subtitle-templates/{template_id}/clone`

Clone a system or owned template into a new custom row. Optional body
`{ "name": "..." }`.

### `DELETE /subtitle-templates/{template_id}`

Delete a custom template (`204`). Clears `subtitle_template_id` on the
user's blog clips that pointed at it. System presets cannot be deleted.

## Audio assets (Stage 23)

### `GET /audio-assets`

Authenticated. Lists system demo tones plus the user's uploads.
Optional query `kind=bgm|sfx`.

Response `200`: array of `AudioAssetResponse`
(`id`, `kind`, `name`, `slug`, `is_system`, `duration_seconds`, …).

### `POST /audio-assets`

Multipart form upload.

- `kind`: `bgm` or `sfx`
- `name`: optional display name
- `file`: `.mp3` / `.wav` / `.m4a` / `.aac` / `.ogg` (max 20MB)

Response `201`: `AudioAssetResponse`.

### `GET /audio-assets/{asset_id}/file`

Streams the audio bytes for preview (auth + ownership / system).

### `DELETE /audio-assets/{asset_id}`

Delete a user upload (`204`). Clears references on the user's blog clips /
boards. System assets cannot be deleted.

---

## Stage 25 (Remotion evaluation)

No new HTTP endpoints. Stage 25 was documentation-only: Remotion was
evaluated against the existing FFmpeg + ASS blog-clip render path and
**deferred**. Rendering continues to use the Stage 18–24 blog-clip and
clip APIs above. Decision record: `docs/REMOTION_EVAL.md`.

## Blog shorts wizard

Design spec: `docs/WIZARD_DESIGN.md`.

**W1–W5 done** (see `docs/WIZARD_DESIGN.md`):

```text
POST /blog-clips                  -- target_length, narration_language
GET/PUT /blog-clips/{id}/images*  -- awaiting_images select
PATCH /blog-clips/{id}/default-voice
PATCH /blog-clips/{id}/audio-settings  -- also auto_bgm, auto_sfx
PATCH /blog-clips/{id}/wizard-step     -- boards|voice|style restore
blog_clips.default_voice / auto_bgm / auto_sfx / wizard_step
```

## Not Implemented Yet

These were mentioned in the original stage plan but do not exist as separate
endpoints in the current code (see `docs/ARCHITECTURE.md` Known Limitations):

```text
GET /clips/{clip_id}/preview   -- use GET /clips/{clip_id} (output_path) or
                                   GET /clips/{clip_id}/download instead
GET /clips                     -- no "list all my clips" endpoint; clips are
                                   only reachable through their highlight_id
Remotion render microservice   -- evaluated Stage 25; deferred (see
                                   docs/REMOTION_EVAL.md)
```
