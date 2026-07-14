# Project Status

Last updated: 2026-07-14
Project root: `C:\Users\stkim\Documents\Codex\new_cut`

## Current Stage

**Stage 14: Blog-clip pipeline discovered and documented — complete.**

All 13 planned stages of the original local MVP are implemented:

```text
Stage  0  Architecture/folder plan (no code)
Stage  1  Project skeleton (FastAPI + React/Vite/TS, docs)
Stage  2  Register/login/JWT, GET /me
Stage  3  Authenticated MP4 upload, video list/detail
Stage  4  FFmpeg audio extraction, analyze/status APIs
Stage  5  OpenAI transcription with timestamped segments
Stage  6  GPT highlight recommendation (3-5 candidates)
Stage  7  FFmpeg 9:16 center-cropped clip generation
Stage  8  ASS subtitle generation (3 styles) + burn-in
Stage  9  Clip download (see "Known Gaps" below for preview/list)
Stage 10  AI upload metadata: titles/description/hashtags + copy buttons
Stage 11  OpenAI TTS narration mode and narration MP4 output
Stage 12  Free/Lite/Pro plans, monthly usage limits, max video duration
Stage 13  Full review: bug fixes, full doc set (this file + 4 others)
Stage 14  This entry: documented the blog-clip pipeline (built after Stage 13
          but never recorded in these docs), cleaned up dead code
```

Real payment integration is still intentionally not implemented (by design,
see original plan). YouTube URL import (`yt-dlp`) was added alongside Stage 3
as an extra input path, ahead of the original plan.

### Stage 14 details: the undocumented blog-clip feature

Between Stage 13 and this entry, a second content pipeline was built
directly in code — `backend/app/api/blog.py`, `backend/app/services/
blog_service.py`, `backend/app/services/subtitle_utils.py`, the `blog_clips`
table, and a full `frontend/src/main.tsx` UI section — but it was never added
to `docs/ARCHITECTURE.md`, `docs/API_SPEC.md`, or this file, and none of it
had been committed to git yet. This stage is that documentation catch-up,
plus two small cleanups:

- Removed `backend/app/services/openai_service.py` (dead placeholder file
  from the Stage 1 skeleton, confirmed unused by any import).
- Removed the stray `new_cut.zip` (~43 MB) from the project root (an
  untracked manual backup, not referenced by any code).

What the blog-clip feature actually does today: paste a `blog.naver.com`
post URL in, and in one request get back a narrated 1080x1920 slideshow
video with burned-in captions and (optionally) AI-generated title/
description/hashtags. See `docs/ARCHITECTURE.md` "Blog clips" workflow and
`docs/API_SPEC.md` "Blog Clips" for the full technical detail. This is the
first working slice of a broader "blog/text -> shorts" product direction
(benchmarked against SuperShorts-style competitors) — see "Roadmap: Blog
Clips -> SuperShorts-Level Product" below for the follow-up plan.

## Run Commands

Backend:

```powershell
cd C:\Users\stkim\Documents\Codex\new_cut\backend
.\.venv\Scripts\python.exe -m uvicorn app.main:app --reload --host 127.0.0.1 --port 8000
```

Frontend:

```powershell
cd C:\Users\stkim\Documents\Codex\new_cut\frontend
npm.cmd run dev
```

URLs:

```text
Frontend: http://127.0.0.1:5173
Backend health: http://127.0.0.1:8000/health
Backend docs: http://127.0.0.1:8000/docs
```

Known local test user:

```text
Email: stage2-test@example.com
Password: Password123!
```

Note: the Stage 13 review also created several throwaway test accounts
(`stage13-...@example.com`, `verify-...@example.com`) directly in
`backend/new_cut.db` while exercising the API end to end. They are harmless
local-only test data (the `.db` file is gitignored) and can be deleted along
with the database file if you want a clean slate — see
`docs/DEPLOYMENT.md` "Backup / Reset (Local)".

## Environment

Runtime backend env file:

```text
backend/.env
```

Important variables (see `docs/ARCHITECTURE.md` for the full list and
`.env.example` for the template):

```text
DATABASE_URL=sqlite:///./new_cut.db
JWT_SECRET_KEY=local-dev-new-cut-change-before-production
MAX_UPLOAD_MB=500
OPENAI_API_KEY=
OPENAI_TRANSCRIPTION_MODEL=whisper-1
OPENAI_HIGHLIGHT_MODEL=gpt-4o-mini
OPENAI_METADATA_MODEL=gpt-4o-mini
TTS_PROVIDER=openai
TTS_API_KEY=
OPENAI_TTS_MODEL=gpt-4o-mini-tts
OPENAI_TTS_VOICE=alloy
TRANSCRIPTION_CHUNK_MB=24
HIGHLIGHT_MIN_SECONDS=15
HIGHLIGHT_MAX_SECONDS=60
```

`TTS_API_KEY` is optional for OpenAI mode. If empty, TTS uses
`OPENAI_API_KEY`. Do not commit real API keys.

As of this review, the local `backend/.env` has `OPENAI_API_KEY` empty, and
FFmpeg/FFprobe are **not** on this PC's PATH in the shell used for testing.
Both are required for the AI/video-processing endpoints to fully succeed;
see `README.md` "Troubleshooting" and "FFmpeg Setup".

## Stage 13 Review Findings

A full pass was made over every backend module, every API endpoint, and the
frontend build, specifically looking for defects before calling the MVP done.

### Bugs found and fixed in this review

1. **`POST /auth/register` always failed with a 500 error.** The endpoint
   built its `UserResponse` with only `id`, `email`, and `created_at`, but
   the schema (updated for Stage 12's usage/plan fields) requires `plan`,
   `monthly_usage`, `usage_limit`, and `usage_month` too. Every registration
   attempt raised a pydantic validation error. Fixed in `backend/app/api/auth.py`
   by populating all required fields from the created user. Verified with a
   live `TestClient` call: before the fix this returned `500`; after the fix
   it returns `201` with the full user payload.
2. **AI narration prompts never included the original video title.**
   `generate_narration_script()` in `backend/app/services/tts_service.py` tried
   to read `highlight["user_id"]`, a column that was never selected in the
   calling query, so the lookup always silently produced `None` and the
   narration prompt's "Original video" field was always blank. Fixed by
   passing `user_id` explicitly from `clip_service.apply_clip_narration()`
   into `generate_narration_script()` instead of guessing it from the
   highlight row.

### Verified working (code review + live API calls where FFmpeg/OpenAI were not required)

- Health check, register, duplicate-register rejection, login,
  wrong-password rejection, `/me`, `/usage`, `/plans`.
- Video upload (valid mp4 extension/content-type accepted, `.txt` rejected
  with `400`), video list, video detail.
- Ownership checks: unauthenticated requests get `403`, invalid/garbage
  tokens get `401`, cross-user access to another user's video/clip returns
  `404` (not found, not "forbidden" — so it does not leak existence).
- Graceful, non-crashing error handling when FFmpeg/FFprobe are missing
  (`analyze` returns a clear `500` with an actionable message and marks the
  video `failed` instead of throwing an unhandled exception).
- Graceful error handling when `OPENAI_API_KEY` is unset: transcript,
  highlights, metadata, and AI narration all return a clear `400` instead of
  crashing.
- State-machine guards: `transcript`/`highlights`/`clips/create`/`subtitles`/
  `narration` all correctly reject with `404`/`409` when a prerequisite step
  (audio extracted / transcript completed / clip completed) has not happened
  yet, verified by seeding a transcript+highlight row directly and exercising
  `POST /clips/create` (fails cleanly with "FFmpeg is not installed...") and
  `POST /clips/{id}/metadata` (fails cleanly with "OPENAI_API_KEY is not
  configured.").
- `backend`: `python -m compileall app` passes with no syntax errors.
- `frontend`: `npm run build` (`tsc -b && vite build`) completes with no type
  errors and produces `frontend/dist/`.
- Every API path called from `frontend/src/main.tsx` has a matching backend
  route (no dead/mismatched endpoint calls found).

### Not fully verified (requires FFmpeg + a real OpenAI key, not available in this review environment)

- A real end-to-end run: upload a real short mp4 -> analyze -> transcript ->
  highlights -> create clip -> burn subtitles -> apply AI narration ->
  generate metadata -> download, all with real audio/video content.
- OpenAI rate-limit / API-error handling under real quota pressure.
- YouTube import (`yt-dlp`) against a live video.
- Over-limit behavior with real long videos across all three plan tiers.

### Known gaps vs. the original 13-stage plan (not bugs, just scope not built)

- `GET /clips/{clip_id}/preview` and `GET /clips` (list-all-my-clips) from the
  original Stage 9 plan were never implemented as separate endpoints. Preview
  today works implicitly through `GET /clips/{clip_id}` (which returns
  `output_path`) or by downloading via `GET /clips/{clip_id}/download`. There
  is no single endpoint that lists every clip a user has ever created — the
  frontend only shows clips attached to highlights currently loaded in memory.

### Known gaps in the blog-clip feature (see "Roadmap" below for the plan)

- `POST /blog-clips` is fully synchronous — no background job queue, no
  progress percentage, and the HTTP request stays open for the entire
  scrape+GPT+TTS+FFmpeg pipeline.
- Only `blog.naver.com` URLs are supported; no generic blog/URL parser.
- Only one narration tone/script is generated per post (no
  summary/hook/detailed choice).
- Only one fixed TTS voice; no voice catalog, speed control, or per-scene
  speaker assignment.
- The slideshow is a static per-image cut (equal duration, no pan/zoom
  animation) with no way to edit, reorder, or replace individual scenes
  after generation — there is no scene/board data model yet, just one row
  per generated video.
- No visual template system (only the 3 subtitle styles reused from
  `clip_service.py`), no stock-image search, no sound-effect/BGM library.

## Current API Summary

See `docs/API_SPEC.md` for full request/response details.

Auth and user:

```text
POST /auth/register
POST /auth/login
GET /me
GET /usage
GET /plans
```

Videos:

```text
POST /videos/upload
POST /videos/import-youtube
GET /videos
GET /videos/{video_id}
POST /videos/{video_id}/analyze
GET /videos/{video_id}/status
GET /videos/{video_id}/transcript
GET /videos/{video_id}/highlights
```

Clips:

```text
POST /clips/create
POST /clips/{clip_id}/subtitles
POST /clips/{clip_id}/metadata
POST /clips/{clip_id}/narration
GET /clips/{clip_id}/metadata
GET /clips/{clip_id}
GET /clips/{clip_id}/download
```

Blog clips:

```text
POST /blog-clips
GET /blog-clips
GET /blog-clips/{blog_clip_id}
POST /blog-clips/{blog_clip_id}/metadata
GET /blog-clips/{blog_clip_id}/metadata
GET /blog-clips/{blog_clip_id}/download
```

## Current Database Summary

See `docs/ARCHITECTURE.md` "Database" for full column lists. Tables:
`users`, `videos`, `transcripts`, `highlights`, `clips`, `clip_metadata`,
`blog_clips`.

## What Works End-to-End Today (Summary)

With FFmpeg installed and a valid `OPENAI_API_KEY` set in `backend/.env`, a
user can, entirely through the local web UI:

1. Register and log in (JWT-authenticated).
2. Upload an MP4, or import a YouTube video by URL.
3. Click Analyze to extract audio (checked against their plan's monthly
   video count and per-video minute limit).
4. Fetch an AI transcript with timestamps.
5. Get 3-5 AI-recommended highlight clips (15-60s each, scored and
   categorized).
6. Generate a 9:16 vertical clip from a chosen highlight.
7. Burn in Korean-safe captions in one of three styles.
8. Choose between the clip's original audio or an AI-narrated voiceover.
9. Generate 3 title candidates, a description, and 10 hashtags, and copy
   them with one click.
10. Download the final rendered MP4.
11. See their current plan, monthly usage, and remaining quota at any time.
12. Paste a `blog.naver.com` post URL and, in one request, get back a
    narrated 1080x1920 slideshow video with burned-in captions, then
    optionally generate title/description/hashtags for it and download it.

This is a genuinely complete MVP loop for a single local user. It is not yet
a deployable multi-user product — see `docs/DEPLOYMENT.md` for the gap
between "runs on my PC" and "runs as a real hosted service."

## Recommended Next Steps

1. Install FFmpeg and set a real `OPENAI_API_KEY` locally, then do one real
   end-to-end run with a short test video to confirm the full pipeline
   produces a correct, watchable output file (both the video-clipping
   pipeline and the blog-clip pipeline).
2. Decide whether to implement the missing `GET /clips` (list) and
   `GET /clips/{clip_id}/preview` endpoints, or intentionally drop them from
   scope.
3. Add automated tests (even a small pytest suite around the service layer)
   so future stages don't reintroduce regressions like the register bug
   found in the Stage 13 review.
4. When ready to support more than one concurrent real user, read
   `docs/DEPLOYMENT.md` and plan the database/storage/queueing migration
   before adding a payment provider.
5. Start the "Roadmap: Blog Clips -> SuperShorts-Level Product" below at
   Stage 15 (async processing) — it is the foundation the rest of that
   roadmap depends on.

## Roadmap: Blog Clips -> SuperShorts-Level Product

This roadmap was planned after benchmarking the blog-clip feature above
against SuperShorts (`supershorts.co.kr`) and similar "blog/text -> shorts"
products (Vrew, ShortsGen). The goal is not to replace the video-clipping
pipeline (Stages 1-13) but to grow the blog-clip pipeline into an equivalent
or better product, on top of the auth/plan/storage foundation both pipelines
already share. Stages are ordered so that the riskiest foundational work
(async processing, frontend componentization) happens before feature work
that depends on it.

```text
Stage 15  Async processing: POST /blog-clips returns immediately (pending),
          the pipeline runs in the background, frontend polls status/progress.
          Prerequisite for every later stage below — do this first.
Stage 16  Source expansion: generic blog/URL scraping beyond blog.naver.com.
Stage 17  Script tone choice: generate summary/hook-driven/detailed script
          candidates and let the user pick one (currently only one script).
Stage 18  Scene/board data model: replace "one row per generated video" with
          a project -> boards[] (scene) structure (image + text + speaker +
          duration per board), with CRUD APIs.
Stage 19  Board editor frontend: split frontend/src/main.tsx into components
          first, then build the board list / inline text editing / live
          preview UI described in Stage 18's API.
Stage 20  Visual upgrade: Ken Burns pan/zoom in the FFmpeg slideshow filter,
          plus stock-image search (e.g. a free Pexels/Unsplash API) so boards
          aren't limited to images scraped from the source post.
Stage 21  Multi-voice TTS: a voice catalog (name/description/cached sample),
          speed control, and per-board speaker assignment.
Stage 22  Template system: save/reuse caption font/color/background presets,
          user-created custom templates (CRUD).
Stage 23  Sound effects + BGM library, with FFmpeg audio mixing (amix).
Stage 24  Multiple variants per project: generate more than one video (e.g.
          one per script tone) from a single blog-clip request.
Stage 25  (Optional) Re-evaluate FFmpeg vs. a Remotion-based rendering
          microservice if caption animation/motion needs outgrow FFmpeg's
          filtergraph model. Only do this if Stage 20/22 hit a real
          expressiveness wall — see the engine trade-off discussion in this
          chat's transcript for the reasoning.
```

Decisions already made (do not re-litigate these without a new reason):

- **Same repo, same database.** `boards`/`projects` tables added alongside
  the existing `videos`/`clips`/`blog_clips` tables — not a separate project.
  The existing auth/plan/usage/OpenAI/FFmpeg service layers are reused, not
  rebuilt.
- **FFmpeg first, Remotion later if needed** (Stage 25 is conditional, not
  committed). Rationale: this is a solo/small Python codebase; adding a
  Node/React rendering microservice is a bigger upfront cost than extending
  the existing FFmpeg service layer, and the MVP-level visual fidelity
  (pan/zoom, crossfade, ASS captions) does not yet require it.
- **UI should match SuperShorts' UX patterns/information architecture (step
  wizard, board list, tabbed media/voice/audio panel), not its visual
  identity.** Copying layout structure is fine; copying specific icons,
  colors, or copy text is not (trademark/trade-dress risk, and it forecloses
  differentiation).
