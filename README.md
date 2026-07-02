# New Cut

AI shorts creation SaaS MVP.

Current capabilities:

- FastAPI backend with health check
- SQLite users, videos, transcripts, highlights, and clips tables
- Register, login, and current-user APIs
- JWT authentication
- Auth-protected MP4 upload
- YouTube URL import with yt-dlp
- My video list and video detail APIs
- FFmpeg-based audio extraction
- OpenAI Transcription API integration structure
- Timestamped transcript storage
- GPT-based shorts highlight recommendation structure
- Highlight-based 9:16 vertical clip generation
- ASS subtitle file generation and FFmpeg subtitle burn-in
- Authenticated clip download
- React + Vite + TypeScript frontend
- Login, register, dashboard, upload, YouTube import, analyze, transcript, highlights, clip, subtitle style, and download controls

TTS, title/description/hashtag generation, billing, and usage plans are not implemented yet.

## Requirements

- Node.js 20 or newer
- Python 3.11 or newer
- FFmpeg for audio extraction, YouTube MP4 merging, vertical clip rendering, and subtitle burn-in
- yt-dlp for YouTube URL import
- OpenAI API key for transcription and highlight recommendation

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
TRANSCRIPTION_CHUNK_MB=24
HIGHLIGHT_MIN_SECONDS=15
HIGHLIGHT_MAX_SECONDS=60
```

Do not put a real OpenAI API key in code. Put it only in `backend/.env`.

## FFmpeg Setup

```powershell
winget install --id Gyan.FFmpeg --source winget
ffmpeg -version
```

After installing FFmpeg, restart the terminal before running the backend again.

## YouTube URL Import

The dashboard supports importing a YouTube URL into the same local video library
used by MP4 uploads. After importing, use the normal flow: `Analyze` ->
`Transcript` -> `Highlights` -> `Create clip` -> `Burn subtitles` -> `Download`.

Use this only for videos you own, videos you created, or videos you have
permission to process. Some YouTube videos may fail because of access
restrictions, region limits, age checks, live streams, private videos, or
YouTube download changes.

Backend dependency:

```powershell
cd C:\Users\stkim\Documents\Codex\new_cut\backend
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
```

## Korean Subtitle Font Notes

Subtitle burn-in uses ASS subtitles with the `Malgun Gothic` font name. On Korean
Windows this font is usually already installed. If Korean subtitles appear as
boxes or broken characters:

1. Confirm Windows has `Malgun Gothic` installed.
2. Confirm FFmpeg was installed with `libass` subtitle support. The Gyan FFmpeg
   build installed by `winget install --id Gyan.FFmpeg --source winget` usually
   includes it.
3. Restart the backend after installing FFmpeg or fonts.
4. Keep generated `.ass` files encoded as UTF-8. The app writes them as UTF-8
   with BOM to help FFmpeg detect Korean text correctly.

The current MVP supports three subtitle styles:

```text
basic
bold
shorts
```

## APIs

Auth:

```text
POST /auth/register
POST /auth/login
GET /me
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
GET /clips/{clip_id}
GET /clips/{clip_id}/download
```

All video and clip APIs require:

```text
Authorization: Bearer <access_token>
```

Current video statuses:

```text
uploaded
extracting_audio
audio_extracted
transcribing
transcribed
failed
```

Current clip statuses:

```text
pending
processing
completed
failed
```

## Current Stage

Stage 8 implementation is complete, with an additional YouTube URL import path
added. Real YouTube import and subtitle burn-in should be tested with a public
or authorized YouTube URL, FFmpeg, and a real OpenAI API key.
