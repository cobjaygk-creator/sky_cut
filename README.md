# New Cut

AI shorts creation SaaS MVP. This is a local-first prototype with two content
pipelines:

1. **Video clipping**: upload or import a long video, transcribe it, get AI
   highlight suggestions, generate a vertical short with burned-in captions,
   optionally replace the audio with an AI narration, generate upload-ready
   title/description/hashtags, and download the result.
2. **Blog clips**: paste a blog/article post URL (Naver blog, Tistory,
   brunch, or most other blogs/news pages) and get back a narrated vertical
   slideshow video with burned-in captions — submitted as an async job with
   progress polling, no source video needed. See `docs/PROJECT_STATUS.md`
   "Roadmap: Blog Clips -> SuperShorts-Level Product" for where this is
   headed.

More documentation:

```text
docs/ARCHITECTURE.md    System design, data flow, database schema
docs/API_SPEC.md        Full endpoint reference (request/response examples)
docs/DEPLOYMENT.md      How this runs today and what real deployment needs
docs/PROJECT_STATUS.md  Stage-by-stage history and current status
```

Current capabilities:

- FastAPI backend with health check
- SQLite users, videos, transcripts, highlights, clips, and clip metadata tables
- Register, login, and current-user APIs
- JWT authentication
- Auth-protected MP4 upload
- YouTube URL import with yt-dlp
- FFmpeg-based audio extraction
- OpenAI transcription, highlight recommendation, metadata generation, and TTS narration structure
- Highlight-based 9:16 vertical clip generation
- ASS subtitle file generation and FFmpeg subtitle burn-in
- AI narration mode for generated clips
- Authenticated clip download
- Free/Lite/Pro plan policy and monthly analysis usage limits
- Blog-to-shorts pipeline: Naver + generic blog/article scraping, GPT
  narration script, OpenAI TTS, FFmpeg image slideshow, subtitle burn-in,
  AI metadata, download
- React + Vite + TypeScript frontend controls for upload, YouTube import, analysis, transcript, highlights, clips, subtitles, metadata, TTS mode, usage plans, blog clips, and download

## Requirements

- Node.js 20 or newer
- Python 3.11 or newer
- FFmpeg for audio extraction, YouTube MP4 merging, vertical clip rendering, subtitle burn-in, and narration audio merge
- yt-dlp for YouTube URL import
- OpenAI API key for transcription, highlight recommendation, metadata generation, and TTS narration

On this PC, use `npm.cmd` because PowerShell may block `npm.ps1`.

## Backend Setup

```powershell
cd C:\Users\stkim\Documents\Codex\new_cut\backend
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
.\.venv\Scripts\python.exe -m uvicorn app.main:app --reload --host 127.0.0.1 --port 8000
```

Backend URLs:

```text
Health: http://127.0.0.1:8000/health
API docs: http://127.0.0.1:8000/docs
```

## Frontend Setup

```powershell
cd C:\Users\stkim\Documents\Codex\new_cut\frontend
npm.cmd install
npm.cmd run dev
```

Frontend URL:

```text
http://127.0.0.1:5173
```

## Environment Variables

Backend environment variables are stored in `backend/.env`. This file is ignored
by Git. Use `.env.example` as the reference.

```text
OPENAI_API_KEY=sk-your-real-key
OPENAI_TRANSCRIPTION_MODEL=whisper-1
OPENAI_HIGHLIGHT_MODEL=gpt-4o-mini
OPENAI_METADATA_MODEL=gpt-4o-mini
TTS_PROVIDER=openai
TTS_API_KEY=
OPENAI_TTS_MODEL=gpt-4o-mini-tts
OPENAI_TTS_VOICE=alloy
```

`TTS_API_KEY` is optional for OpenAI mode. If it is empty, the app uses
`OPENAI_API_KEY` for TTS too. Keep real API keys only in `backend/.env`.


## Usage Plans

The MVP has plan limits but no real payment integration yet.

```text
Free: 3 analyzed videos/month, max 10 minutes per video
Lite: 30 analyzed videos/month, max 30 minutes per video
Pro: 150 analyzed videos/month, max 120 minutes per video
```

Usage is checked when you click `Analyze`. Uploading or importing a video does not consume usage by itself. If the month changes, `monthly_usage` is automatically reset for the current user.

To test another plan locally, stop the backend and update the user's plan in SQLite, then restart the backend:

```powershell
cd C:\Users\stkim\Documents\Codex\new_cut\backend
.\.venv\Scripts\python.exe -c "import sqlite3; conn=sqlite3.connect('new_cut.db'); conn.execute(\"UPDATE users SET plan='lite' WHERE email='stage2-test@example.com'\"); conn.commit(); conn.close()"
```

Allowed `plan` values are `free`, `lite`, and `pro`. The app recalculates `usage_limit` from `plan` automatically.

## TTS Narration

Generated clips support two audio modes:

```text
original_audio
ai_narration
```

`original_audio` keeps the generated clip's original audio. `ai_narration`
creates a short narration script from the selected highlight and transcript,
generates an MP3 voice file with OpenAI TTS, and uses FFmpeg to create a new MP4
with the AI narration audio track. This is not lip sync or full dubbing.

## FFmpeg Setup

```powershell
winget install --id Gyan.FFmpeg --source winget
ffmpeg -version
```

After installing FFmpeg, restart the terminal before running the backend again.

## Korean Subtitle Font

Burned-in subtitles use the `Malgun Gothic` font name in the ASS style line
(`backend/app/services/clip_service.py`, `_ass_style`). This font ships with
Windows by default, so Korean subtitles render correctly out of the box on
this PC. If you move the backend to a different OS (Linux/macOS/Docker),
install a Korean-capable font (for example Noto Sans KR) and update the font
name in `_ass_style`, otherwise Korean subtitle text will show as boxes or
missing glyphs in the burned-in video.

## APIs

Auth and account:

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

Blog clips (blog/article URL -> narrated shorts, no source video needed):

```text
POST /blog-clips
GET /blog-clips
GET /blog-clips/{blog_clip_id}
POST /blog-clips/{blog_clip_id}/metadata
GET /blog-clips/{blog_clip_id}/metadata
GET /blog-clips/{blog_clip_id}/download
```

All APIs except `POST /auth/register`, `POST /auth/login`, and `GET /plans` require:

```text
Authorization: Bearer <access_token>
```

See `docs/API_SPEC.md` for full request/response examples for every endpoint.

## Troubleshooting

Common local errors and what they mean:

```text
"FFmpeg is not installed or is not available in PATH."
  -> Install FFmpeg (see FFmpeg Setup above) and restart the terminal/backend.

"FFprobe is not installed or is not available in PATH."
  -> Same fix as above. FFprobe ships together with FFmpeg.

"OPENAI_API_KEY is not configured." (400 error)
  -> Set OPENAI_API_KEY in backend/.env and restart the backend. This
     affects transcript, highlights, metadata, and AI narration.

"yt-dlp is not installed."
  -> Run: .\.venv\Scripts\python.exe -m pip install -r requirements.txt

npm.ps1 cannot be loaded / npm is not recognized
  -> Always use npm.cmd on this PC (see the note above), not npm or npm.ps1.

Registering/logging in fails with a generic 500 error
  -> Make sure you pulled the latest backend code. An earlier version of
     POST /auth/register returned an incomplete response and always failed;
     this is fixed in the current code.

Korean subtitles show boxes/garbled text in the output video
  -> See "Korean Subtitle Font" above.

Video analysis fails immediately with a duration or plan-limit message
  -> The signed-in user's plan (Free/Lite/Pro) limits max video length and
     monthly analysis count. See "Usage Plans" above to change the plan
     locally for testing.

A blog clip stays stuck on "블로그 글 읽는 중" (scraping) then fails
  -> The generic scraper is a best-effort heuristic (Stage 16): it can fail
     on heavily JavaScript-rendered pages or sites that block scraping.
     Check the `error_message` on the failed row (or `GET
     /blog-clips/{id}`) for the exact reason.

"블로그에서 사용할 수 있는 이미지가 부족합니다" (blog clips)
  -> The post has fewer usable images than BLOG_IMAGE_MIN_COUNT (default 3).
     Pick a post with more images, or lower BLOG_IMAGE_MIN_COUNT in
     backend/.env for local testing.

POST /blog-clips returns "pending" but the video takes a while to finish
  -> This is expected: scraping, GPT script generation, TTS synthesis, and
     FFmpeg rendering run in the background after the request returns
     (Stage 15). Poll GET /blog-clips/{id} for progress_stage/
     progress_percent, or just watch the progress bar in the UI.
```

## Current Stage

Stage 16 is complete: the original 13-stage video-clipping MVP (project
skeleton, auth, upload, audio extraction, STT, highlight recommendation, clip
generation, subtitles, preview/download, metadata generation, TTS narration,
usage plans, and a full review) is implemented and locally verified, and the
blog-clip pipeline (built after Stage 13) now runs asynchronously with
progress polling (Stage 15) and accepts any blog/article URL, not just
Naver (Stage 16). Real payment integration is intentionally not
implemented. See `docs/PROJECT_STATUS.md` for the full stage history, known
limitations, and the roadmap for growing the blog-clip pipeline into a
SuperShorts-level product.

