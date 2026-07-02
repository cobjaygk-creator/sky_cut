# New Cut

AI shorts creation SaaS MVP.

The current stage includes:

- FastAPI backend with health check
- SQLite users and videos tables
- Register, login, and current-user APIs
- JWT authentication
- Auth-protected MP4 upload
- My video list and video detail APIs
- FFmpeg-based audio extraction structure
- Video analysis start and status APIs
- React + Vite + TypeScript frontend
- Login, register, dashboard, upload, my video list, and analyze controls

OpenAI API calls, transcription, shorts generation, TTS, and usage plans are not implemented yet.

## Requirements

- Node.js 20 or newer
- Python 3.11 or newer
- FFmpeg for audio extraction

On this PC, use `npm.cmd` because PowerShell may block `npm.ps1`.

## Backend Setup

```powershell
cd C:\Users\stkim\Documents\Codex\new_cut\backend
.\.venv\Scripts\python.exe -m uvicorn app.main:app --reload --host 127.0.0.1 --port 8000
```

If you need to recreate the backend environment:

```powershell
cd C:\Users\stkim\Documents\Codex\new_cut\backend
C:\Users\stkim\AppData\Local\Programs\Python\Python312\python.exe -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
```

Backend health check:

```text
http://127.0.0.1:8000/health
```

API docs:

```text
http://127.0.0.1:8000/docs
```

## Frontend Setup

Open a second terminal:

```powershell
cd C:\Users\stkim\Documents\Codex\new_cut\frontend
npm.cmd install
npm.cmd run dev
```

Frontend URL:

```text
http://127.0.0.1:5173
```

## FFmpeg Setup

FFmpeg must be installed and available in PATH before audio extraction can work.

Check installation:

```powershell
ffmpeg -version
```

Install with winget:

```powershell
winget install --id Gyan.FFmpeg --source winget
```

After installation, close and reopen the terminal, then run `ffmpeg -version` again.

If FFmpeg is missing, `POST /videos/{video_id}/analyze` will mark the video as
`failed` and save the error message in the database.

## Environment Variables

Backend environment variables are stored in `backend/.env`. The file is ignored
by Git. Use `.env.example` as the reference.

Important variables:

```text
DATABASE_URL=sqlite:///./new_cut.db
JWT_SECRET_KEY=change-this-before-production
JWT_ALGORITHM=HS256
JWT_EXPIRE_MINUTES=1440
MAX_UPLOAD_MB=500
```

## Auth APIs

```text
POST /auth/register
POST /auth/login
GET /me
```

`GET /me` requires:

```text
Authorization: Bearer <access_token>
```

## Video APIs

```text
POST /videos/upload
GET /videos
GET /videos/{video_id}
POST /videos/{video_id}/analyze
GET /videos/{video_id}/status
```

All video APIs require:

```text
Authorization: Bearer <access_token>
```

Current video statuses:

```text
uploaded
extracting_audio
audio_extracted
failed
```

Extracted audio is saved under:

```text
backend/app/storage/temp/<user_id>/<stored_video_filename>.wav
```

## Verified In Stage 4

- Frontend build passed with `npm.cmd run build`
- Backend compile check passed
- Backend health check returned `status: ok`
- `GET /videos/{video_id}/status` returned the current video status
- `POST /videos/{video_id}/analyze` handles missing FFmpeg by setting `failed`
- FFmpeg missing error message is stored and returned by status API

## Current Stage

Stage 4 is complete. See `docs/PROJECT_STATUS.md` for completed items and the
next development step.
