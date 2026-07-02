# Project Status

Last updated: 2026-07-03
Project root: `C:\Users\stkim\Documents\Codex\new_cut`

## Current Stage

Stage 8 is complete, and an additional YouTube URL import feature has been added.

Users can now either upload a local MP4 or paste a YouTube URL. The backend uses
`yt-dlp` to save the YouTube video as a local MP4 record, then the existing flow
continues unchanged: Analyze -> Transcript -> Highlights -> Create clip -> Burn
subtitles -> Download.

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

## Environment

Runtime backend env file:

```text
backend/.env
```

Expected variables:

```text
APP_ENV=local
APP_NAME=New Cut
DATABASE_URL=sqlite:///./new_cut.db
JWT_SECRET_KEY=local-dev-new-cut-change-before-production
JWT_ALGORITHM=HS256
JWT_EXPIRE_MINUTES=1440
MAX_UPLOAD_MB=500
OPENAI_API_KEY=
OPENAI_TRANSCRIPTION_MODEL=whisper-1
OPENAI_HIGHLIGHT_MODEL=gpt-4o-mini
TRANSCRIPTION_CHUNK_MB=24
HIGHLIGHT_MIN_SECONDS=15
HIGHLIGHT_MAX_SECONDS=60
```

Do not commit a real OpenAI API key. Keep it only in `backend/.env`.

## Dependencies

Backend requirements include:

```text
openai==2.14.0
yt-dlp==2026.6.9
```

Install/update backend dependencies with:

```powershell
cd C:\Users\stkim\Documents\Codex\new_cut\backend
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
```

## Completed Capabilities

### Stage 1: Skeleton

- FastAPI backend
- React + Vite + TypeScript frontend
- Docs and local run instructions

### Stage 2: Auth

- SQLite `users` table
- `POST /auth/register`
- `POST /auth/login`
- `GET /me`
- JWT authentication
- Password hashing

### Stage 3: Local MP4 Upload

- SQLite `videos` table
- `POST /videos/upload`
- `GET /videos`
- `GET /videos/{video_id}`
- MP4-only validation
- Local storage under `backend/app/storage/uploads/<user_id>/`

### YouTube URL Import

Implemented after Stage 8:

- `yt-dlp==2026.6.9` added to backend requirements
- `YoutubeImportRequest` schema
- `POST /videos/import-youtube`
- Backend YouTube URL validation for `youtube.com`, `www.youtube.com`, `m.youtube.com`, and `youtu.be`
- Downloads one YouTube URL as an MP4 into the same uploads folder used by local MP4 uploads
- Creates a normal `videos` table record with status `uploaded`
- Enforces existing `MAX_UPLOAD_MB` limit after download
- Frontend YouTube URL form added to dashboard
- Imported YouTube videos appear in `My Videos` and use the existing processing buttons

Important limitations:

- Use only videos the user owns or has permission to process.
- Some YouTube URLs can fail because of private videos, age checks, region restrictions, live streams, account-only videos, or YouTube-side changes.
- Long-running downloads are currently synchronous. Move this to a background job later.

### Stage 4: FFmpeg Audio Extraction

- FFmpeg availability check
- `POST /videos/{video_id}/analyze`
- `GET /videos/{video_id}/status`
- WAV output under `backend/app/storage/temp/<user_id>/`

### Stage 5: OpenAI Transcription

- `GET /videos/{video_id}/transcript`
- `transcripts` table
- Segment timestamp storage
- Long audio chunking structure

### Stage 6: GPT Highlight Recommendation

- `GET /videos/{video_id}/highlights`
- `highlights` table
- 3 to 5 highlight candidates
- JSON parsing and validation

### Stage 7: Vertical Clip Generation

- `clips` table
- `POST /clips/create`
- `GET /clips/{clip_id}`
- 9:16 center crop with FFmpeg
- Output under `backend/app/storage/outputs/<user_id>/`

### Stage 8: Automatic Subtitles And Download

- `POST /clips/{clip_id}/subtitles`
- `GET /clips/{clip_id}/download`
- ASS subtitle generation
- Styles: `basic`, `bold`, `shorts`
- Korean subtitle notes in README
- Authenticated frontend download

## Current API Summary

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

`POST /videos/import-youtube` request body:

```json
{
  "url": "https://www.youtube.com/watch?v=..."
}
```

Clips:

```text
POST /clips/create
POST /clips/{clip_id}/subtitles
GET /clips/{clip_id}
GET /clips/{clip_id}/download
```

## Current Database Summary

No new table was added for YouTube import. YouTube videos are stored as normal
rows in `videos`.

`videos`:

```text
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
```

`clips` includes subtitle fields:

```text
subtitle_style TEXT
subtitle_path TEXT
subtitled_output_path TEXT
```

## Verified

- Backend compile passed
- Frontend build passed
- `yt-dlp` installed in backend virtual environment
- `yt_dlp` import verified, version `2026.06.09`
- FastAPI app includes `/videos/import-youtube`

## Not Verified Yet

- Real YouTube download through the UI
- Real end-to-end processing from YouTube URL to subtitled downloadable short

Reasons:

- YouTube download requires network access and a public/accessible video URL.
- FFmpeg still needs to be available in PATH for audio extraction, MP4 merging, clipping, and subtitle burn-in.
- OpenAI transcription/highlight generation requires a real `OPENAI_API_KEY`.

## Recommended Next Steps

1. Restart the backend so the new route and dependency are definitely loaded.
2. Open `http://127.0.0.1:5173`.
3. Log in.
4. Paste a YouTube URL in the dashboard YouTube URL field.
5. Click `Import YouTube video`.
6. After it appears in `My Videos`, continue with `Analyze`, `Transcript`, `Highlights`, `Create clip`, `Burn subtitles`, and `Download`.

## Future Improvements

- Add background jobs for YouTube import, transcription, clipping, and subtitle burn-in
- Add video source fields such as `source_type` and `source_url`
- Add generated clips list per video so clips remain visible after refresh
- Add preview/player for generated clips
- Split side-effecting GET transcript/highlight endpoints into POST generate and GET read-only endpoints
