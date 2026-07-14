# Architecture

## Goal

New Cut is a local-first MVP for an AI shorts creation SaaS. It now has two
independent content pipelines that share the same auth/plan/storage
foundation:

1. **Video clipping** (Stages 1-13): upload or YouTube-import a long video,
   transcribe it, get AI highlight suggestions, generate a 9:16 clip with
   burned-in captions, optionally replace the audio with an AI narration,
   generate upload-ready metadata, and download the result.
2. **Blog clips** (added after Stage 13, see `docs/PROJECT_STATUS.md`):
   turn a blog/article post (Naver blog, Tistory, brunch, or most other
   blogs/news pages) into a narrated vertical slideshow video, submitted as
   one async job with progress polling — no source video required. This is
   the first step toward a SuperShorts-style "text/blog -> shorts" product;
   see `docs/PROJECT_STATUS.md` for the follow-up roadmap (scene/board
   editing, multi-voice TTS, templates, etc.).

## Current Stack

- Frontend: React + Vite + TypeScript
- Backend: Python FastAPI
- Database: SQLite
- Auth: JWT (self-implemented HMAC-SHA256 signing, no third-party JWT library)
- Password hashing: PBKDF2-SHA256 with per-password random salt
- Storage: Local file storage
- Video/audio processing: FFmpeg / FFprobe
- Video import: yt-dlp (YouTube URLs)
- AI transcription: OpenAI Audio Transcription API (Whisper)
- Highlight recommendation: OpenAI GPT API (JSON response parsing)
- Upload metadata generation: OpenAI GPT API (JSON response parsing)
- TTS narration: OpenAI TTS API (structured so another provider such as
  ElevenLabs could be swapped in behind `tts_service.py`)
- Blog scraping: `requests` + `BeautifulSoup` (`beautifulsoup4`) — a
  Naver-specific parser plus a generic heuristic parser (common container
  selectors, falling back to "largest `<div>` by text") for every other
  blog/article URL

## High-Level Flow

```text
User browser
  -> React frontend
  -> FastAPI backend
  -> SQLite database
  -> Local file storage
  -> FFmpeg audio extraction
  -> OpenAI transcription (Whisper)
  -> GPT highlight recommendation
  -> FFmpeg vertical clip render
  -> ASS subtitle burn-in
  -> GPT upload metadata (title/description/hashtags)
  -> OpenAI TTS narration (optional)
  -> Authenticated download
```

## Main Workflows

Auth:

```text
POST /auth/register -> hash password -> insert users row
POST /auth/login -> verify password -> issue JWT
GET /me -> verify Bearer token -> load current user
```

Upload:

```text
POST /videos/upload
  -> verify JWT
  -> validate MP4
  -> save to backend/app/storage/uploads/<user_id>/
  -> create videos row with status uploaded
```

Audio extraction:

```text
POST /videos/{video_id}/analyze
  -> verify ownership
  -> set extracting_audio
  -> run FFmpeg
  -> save WAV to backend/app/storage/temp/<user_id>/
  -> set audio_extracted or failed
```

Transcription:

```text
GET /videos/{video_id}/transcript
  -> require extracted audio
  -> set transcribing
  -> call OpenAI transcription API
  -> store text and segment timestamps
  -> set transcribed or failed
```

Highlight recommendation:

```text
GET /videos/{video_id}/highlights
  -> require completed transcript
  -> return cached highlights when present
  -> otherwise ask GPT for 3-5 JSON highlight candidates
  -> validate duration 15-60 seconds
  -> validate/normalize content_type and score
  -> save highlights rows
  -> return saved results
```

Note: `GET /videos/{video_id}/transcript` and `GET /videos/{video_id}/highlights`
currently have side effects when no cached result exists. This is acceptable for
the MVP, but later should be split into POST generate endpoints and read-only GET endpoints.

Clip generation:

```text
POST /clips/create
  -> verify ownership of the highlight (join through videos)
  -> insert clips row, status pending -> processing
  -> FFmpeg: crop original video to the highlight time range, scale/crop to 1080x1920
  -> save to backend/app/storage/outputs/<user_id>/<uuid>.mp4
  -> set completed (output_path) or failed (error_message)
```

Subtitle burn-in:

```text
POST /clips/{clip_id}/subtitles
  -> require a completed clip
  -> collect transcript segments that overlap the clip's time range
  -> wrap/split text into short lines, write an .ass file (basic/bold/shorts style)
  -> FFmpeg subtitles filter burns the .ass file into a new mp4
  -> save subtitle_path and subtitled_output_path on the clip row
```

AI narration (TTS):

```text
POST /clips/{clip_id}/narration  { "mode": "original_audio" | "ai_narration" }
  -> original_audio: just record the mode, no re-encode
  -> ai_narration:
       -> GPT summarizes the highlight+transcript into a short narration script
       -> OpenAI TTS renders the script to an mp3
       -> FFmpeg replaces the clip's audio track with the narration mp3 (video stream copied)
       -> save narration_script, narration_audio_path, narrated_output_path
```

Upload metadata generation:

```text
POST /clips/{clip_id}/metadata
  -> require an existing clip and a completed transcript
  -> build a transcript excerpt for the highlight's time range
  -> GPT returns exactly 3 title candidates, 1 description, 10 hashtags (JSON)
  -> validate/normalize hashtags, cap lengths, save to clip_metadata
  -> subsequent calls return the cached row instead of calling GPT again
```

Blog clips (blog/article URL -> narrated shorts, async job with progress polling):

```text
POST /blog-clips  { "url": "https://blog.naver.com/...", "style": "shorts" }
  -> create_blog_clip_job(): insert blog_clips row (status pending,
     progress_stage 'queued', progress_percent 0), return immediately (~ms)
  -> BackgroundTasks schedules run_blog_clip_pipeline() to run after the
     response is sent, using its own SQLite connection (opened via
     get_connection(), not the request-scoped one, which is already closed
     by the time a background task executes)

run_blog_clip_pipeline() (background, updates progress_stage/progress_percent
at each step so the frontend can poll and show a progress bar):
  -> scraping (10%): fetch_blog_content() dispatches on the URL host —
     fetch_naver_blog_content() for blog.naver.com (targets the known
     `.se-main-container`/`.se-text-paragraph` structure exactly), or
     fetch_generic_blog_content() for every other blog/article URL (tries a
     prioritized list of common container selectors — article, [role=main],
     .entry-content, etc. — then falls back to "the <div> with the most
     text" if none match). Both return title/body text/image URLs.
  -> downloading_images (25%): download up to BLOG_IMAGE_MAX_COUNT images
     (fails with 409-style error message if fewer than BLOG_IMAGE_MIN_COUNT
     usable images were found)
  -> generating_script (40%): GPT summarizes into a ~30-45s Korean narration script
  -> synthesizing_audio (55%): OpenAI TTS synthesizes the script to an mp3
  -> rendering_video (75%): FFmpeg builds a 1080x1920 image slideshow timed to
     the narration audio (create_image_slideshow(); equal duration per image,
     no pan/zoom yet)
  -> burning_subtitles (90%): split the narration script into subtitle events
     proportional to sentence length, write an .ass file, burn it into the
     slideshow
  -> done (100%): set completed (video_path, subtitled_video_path), or on any
     failure at any step above, set failed (error_message) and stop

GET /blog-clips/{id} (and GET /blog-clips list)
  -> read-only; the frontend polls this every 2s while status is
     pending/processing to drive a progress bar, and stops polling once
     status is completed or failed
```

This reuses `tts_service.py` (audio synthesis) and the ASS subtitle
conventions originally written for `clip_service.py`, which were extracted
into `subtitle_utils.py` so both pipelines share the exact same font/style/
wrapping logic instead of duplicating it.

Note: the background task above runs in-process (FastAPI `BackgroundTasks`,
not a separate worker/queue like Celery or RQ). This is sufficient for a
single local `uvicorn` process but would need a real job queue before
running multiple server processes/machines — see `docs/PROJECT_STATUS.md`
"Stage 15 details".

Usage / plan enforcement:

```text
Every authenticated request (get_current_user)
  -> sync_user_usage_policy(): reset monthly_usage if the calendar month changed,
     and recompute usage_limit from the user's current plan

POST /videos/{video_id}/analyze (only for videos not yet analyzed this cycle)
  -> ffprobe reads source duration
  -> assert_can_analyze_video(): 403 if monthly_usage >= usage_limit,
     403 if duration exceeds the plan's max_video_minutes
  -> increment_monthly_usage() only after audio extraction succeeds
```

## Backend Layout

```text
backend/app/
  main.py                       FastAPI app, router registration, CORS, DB init on startup
  api/auth.py                   POST /auth/register, POST /auth/login
  api/users.py                  GET /me, GET /usage, GET /plans, get_current_user dependency
  api/videos.py                 upload/import/list/detail/analyze/status/transcript/highlights
  api/clips.py                  create/subtitles/narration/metadata/detail/download
  api/blog.py                   POST/GET /blog-clips, metadata, detail, download
  core/config.py                pydantic-settings, reads backend/.env
  core/security.py              password hashing (PBKDF2) and self-signed JWT (HMAC-SHA256)
  db/database.py                SQLite schema creation and lightweight migrations
  db/models.py                  Plain dataclasses returned by service functions
  db/schemas.py                 Pydantic request/response models used by the API layer
  services/user_service.py      Register/login/lookup, row <-> User mapping
  services/usage_service.py     Plan policy table, usage sync/check/increment
  services/video_service.py     Upload, YouTube import, status transitions
  services/ffmpeg_service.py    All subprocess calls to ffmpeg/ffprobe
  services/transcription_service.py  Whisper call, audio chunking for large files
  services/highlight_service.py GPT highlight recommendation, JSON validation
  services/clip_service.py      Clip render, ASS subtitle build + burn-in
  services/tts_service.py       Narration script generation + OpenAI TTS synthesis
  services/metadata_service.py  Title/description/hashtag generation
  services/blog_service.py      Naver + generic blog/article scraping, image download, GPT
                                 script/metadata, slideshow + subtitle orchestration for blog clips
  services/subtitle_utils.py    Shared ASS subtitle helpers (wrap/split/timecode/style),
                                 originally part of clip_service.py, now used by both
                                 clip_service.py and blog_service.py
```

## Frontend Layout

```text
frontend/src/
  main.tsx       Single-file app: login/register, dashboard, upload, YouTube import,
                 analyze/transcript/highlights, clip creation, subtitle style picker,
                 TTS mode picker, metadata panel with copy buttons, usage/plan panel,
                 clip download
  styles.css     Base styling and dashboard controls
  vite-env.d.ts  Vite type declarations
```

## Database

```text
users
  id INTEGER PRIMARY KEY AUTOINCREMENT
  email TEXT NOT NULL UNIQUE
  password_hash TEXT NOT NULL
  plan TEXT NOT NULL DEFAULT 'free'              -- 'free' | 'lite' | 'pro'
  monthly_usage INTEGER NOT NULL DEFAULT 0
  usage_limit INTEGER NOT NULL DEFAULT 3
  usage_month TEXT                                -- 'YYYY-MM', reset trigger
  created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP

videos
  id INTEGER PRIMARY KEY AUTOINCREMENT
  user_id INTEGER NOT NULL
  original_filename TEXT NOT NULL
  stored_filename TEXT NOT NULL
  storage_path TEXT NOT NULL
  content_type TEXT NOT NULL
  file_size INTEGER NOT NULL
  status TEXT NOT NULL CHECK (status IN ('uploaded', 'extracting_audio', 'audio_extracted', 'transcribing', 'transcribed', 'failed'))
  audio_path TEXT
  error_message TEXT
  created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
  updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP

transcripts
  id INTEGER PRIMARY KEY AUTOINCREMENT
  video_id INTEGER NOT NULL UNIQUE
  status TEXT NOT NULL CHECK (status IN ('transcribing', 'transcribed', 'failed'))
  text TEXT
  segments_json TEXT NOT NULL DEFAULT '[]'
  error_message TEXT
  created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
  updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP

highlights
  id INTEGER PRIMARY KEY AUTOINCREMENT
  video_id INTEGER NOT NULL
  start_time REAL NOT NULL
  end_time REAL NOT NULL
  title TEXT NOT NULL
  reason TEXT NOT NULL
  content_type TEXT NOT NULL              -- 정보형/꿀팁형/후킹형/감정형/논쟁형/웃긴 장면
  score REAL NOT NULL                     -- 0-100
  created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP

clips
  id INTEGER PRIMARY KEY AUTOINCREMENT
  user_id INTEGER NOT NULL
  video_id INTEGER NOT NULL
  highlight_id INTEGER NOT NULL
  output_path TEXT                        -- rendered 9:16 clip (no subtitles/narration)
  subtitle_style TEXT                     -- 'basic' | 'bold' | 'shorts'
  subtitle_path TEXT                      -- generated .ass file
  subtitled_output_path TEXT              -- clip with subtitles burned in
  tts_mode TEXT NOT NULL DEFAULT 'original_audio'  -- 'original_audio' | 'ai_narration'
  narration_script TEXT
  narration_audio_path TEXT               -- generated .mp3
  narrated_output_path TEXT               -- clip with narration audio track
  status TEXT NOT NULL CHECK (status IN ('pending', 'processing', 'completed', 'failed'))
  error_message TEXT
  created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
  updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP

clip_metadata
  id INTEGER PRIMARY KEY AUTOINCREMENT
  clip_id INTEGER NOT NULL UNIQUE
  title_candidates_json TEXT NOT NULL DEFAULT '[]'   -- exactly 3 strings
  description TEXT NOT NULL DEFAULT ''
  hashtags_json TEXT NOT NULL DEFAULT '[]'           -- exactly 10 strings
  error_message TEXT
  created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
  updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP

blog_clips
  id INTEGER PRIMARY KEY AUTOINCREMENT
  user_id INTEGER NOT NULL
  source_url TEXT NOT NULL                -- blog/article post URL (Naver or generic)
  blog_title TEXT                         -- scraped post title
  narration_script TEXT                   -- GPT-generated narration script
  subtitle_style TEXT NOT NULL DEFAULT 'shorts'  -- 'basic' | 'bold' | 'shorts'
  video_path TEXT                         -- rendered slideshow (no subtitles)
  subtitled_video_path TEXT               -- slideshow with captions burned in
  status TEXT NOT NULL CHECK (status IN ('pending', 'processing', 'completed', 'failed'))
  progress_stage TEXT NOT NULL DEFAULT 'queued'    -- queued/scraping/downloading_images/
                                                     -- generating_script/synthesizing_audio/
                                                     -- rendering_video/burning_subtitles/done
  progress_percent INTEGER NOT NULL DEFAULT 0      -- 0-100, matches progress_stage
  error_message TEXT
  title_candidates_json TEXT              -- set by POST /blog-clips/{id}/metadata
  description TEXT
  hashtags_json TEXT
  metadata_error TEXT
  created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
  updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
```

Unlike `clips`, `blog_clips` has no `video_id`/`highlight_id` — the whole
video is generated from the blog post text/images in one call, with no
underlying uploaded video row. This is also why the table has its own
`title_candidates_json`/`description`/`hashtags_json`/`metadata_error`
columns instead of a separate `blog_clip_metadata` table: the metadata
generation step for blog clips has no dependency on transcript overlap logic
the way clip metadata does, so a second table would be pure duplication.

`backend/app/db/database.py` runs `ALTER TABLE`/rebuild migrations on startup
so that upgrading from an older schema (missing `plan`, `tts_mode`, etc.) does
not require deleting `new_cut.db`.

Clip lookups are keyed by `highlight_id` in the frontend's React state (a
highlight has at most one "current" clip in the UI), while the backend keys
clips by their own `id` and by `user_id` for ownership checks.

## Environment Variables

```text
# Backend
APP_ENV=local
APP_NAME=New Cut
DATABASE_URL=sqlite:///./new_cut.db
JWT_SECRET_KEY=change-this-before-production
JWT_ALGORITHM=HS256
JWT_EXPIRE_MINUTES=1440
MAX_UPLOAD_MB=500
OPENAI_API_KEY=sk-your-real-key
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
BLOG_IMAGE_MIN_COUNT=3
BLOG_IMAGE_MAX_COUNT=8
BLOG_FETCH_TIMEOUT_SECONDS=20

# Frontend
VITE_API_BASE_URL=http://127.0.0.1:8000
```

`TTS_API_KEY` is optional: if empty, `tts_service.py` falls back to
`OPENAI_API_KEY`. `TTS_PROVIDER` currently only supports `openai`; the service
function signatures are kept provider-agnostic so a future ElevenLabs backend
can be added without changing callers in `clip_service.py`.

## Storage

```text
backend/app/storage/uploads/<user_id>/<generated_uuid>.mp4      original upload/import
backend/app/storage/temp/<user_id>/<stored_video_filename>.wav  extracted audio (analyze step)
backend/app/storage/outputs/<user_id>/<uuid>.mp4                rendered 9:16 clip
backend/app/storage/outputs/<user_id>/<...>_subtitled.mp4       clip with subtitles burned in
backend/app/storage/outputs/<user_id>/<...>_ai_narration.mp4    clip with AI narration audio
backend/app/storage/subtitles/<user_id>/clip_<id>_<style>.ass   generated subtitle file
backend/app/storage/tts/<user_id>/clip_<id>_<uuid>.mp3          generated narration audio
backend/app/storage/audio/        reserved, currently unused
backend/app/storage/transcripts/  reserved, currently unused
backend/app/storage/blog/images/<user_id>/<blog_clip_id>/<uuid>.<ext>  downloaded blog images
backend/app/storage/blog/outputs/<user_id>/<uuid>.mp4                  rendered slideshow
backend/app/storage/blog/outputs/<user_id>/<...>_subtitled.mp4         slideshow with captions
backend/app/storage/blog/subtitles/<user_id>/blog_<id>_<style>.ass     generated subtitle file
```

## Known Limitations (Stage 13 review)

- `docs/API_SPEC.md` is the source of truth for exact request/response shapes;
  keep it in sync when endpoints change.
- No real payment provider; plan changes are done by editing `users.plan`
  directly in SQLite (see README "Usage Plans").
- No admin UI, no automated tests, no CI pipeline yet.
- `GET /videos/{video_id}/transcript` and `GET /videos/{video_id}/highlights`
  are GET endpoints with side effects (see note above) — acceptable for the
  MVP, worth revisiting before a public release.
- There is no dedicated "my clips" list endpoint; clips are only reachable
  through the highlight that created them.
- `POST /blog-clips` runs its pipeline asynchronously via FastAPI
  `BackgroundTasks` with `progress_stage`/`progress_percent` polling (Stage
  15), but this is still in-process background work, not a real job
  queue/worker — fine for one local server, not for multiple.
- Blog clips support Naver blog and a generic best-effort scraper for other
  blog/article URLs (Stage 16), but the generic parser is heuristic, not a
  true reader-mode extractor — it can fail on heavily JS-rendered pages or
  sites that block scraping.
- Blog clips use a single fixed narration voice/tone and a static per-image
  slideshow (no pan/zoom animation, no scene-level editing after generation).
