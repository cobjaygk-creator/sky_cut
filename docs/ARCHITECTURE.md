# Architecture

## Goal

New Cut is an AI shorts creation SaaS that starts as a local PC MVP. The current
milestone provides authentication, protected dashboard access, MP4 upload,
per-user video lists, and FFmpeg audio extraction structure.

## Current Stack

- Frontend: React + Vite + TypeScript
- Backend: Python FastAPI
- Database: SQLite
- Auth: JWT
- Password hashing: PBKDF2-SHA256 with per-password random salt
- Storage: Local file storage
- Video/audio processing: FFmpeg for audio extraction

## Future Stack

- AI: OpenAI API
- TTS: OpenAI TTS or ElevenLabs-compatible provider structure
- Billing: Plan and usage-limit structure first, real payment integration later

## High-Level Flow

```text
User browser
  -> React frontend
  -> FastAPI backend
  -> SQLite database
  -> Local file storage
  -> FFmpeg audio extraction
  -> OpenAI transcription in later stages
```

## Auth Flow

```text
Register
  -> POST /auth/register
  -> hash password
  -> insert user into SQLite users table

Login
  -> POST /auth/login
  -> verify password hash
  -> issue JWT access token

Current user
  -> GET /me
  -> Authorization: Bearer <token>
  -> verify JWT
  -> load user from SQLite
```

## Video Upload Flow

```text
Dashboard upload form
  -> POST /videos/upload with Bearer token and multipart file
  -> verify JWT
  -> validate .mp4 extension and MP4 content type
  -> enforce MAX_UPLOAD_MB
  -> save file under backend/app/storage/uploads/<user_id>/
  -> insert videos row with status uploaded
  -> show uploaded video in dashboard list
```

## Audio Extraction Flow

```text
Dashboard Analyze button
  -> POST /videos/{video_id}/analyze
  -> verify JWT and video ownership
  -> set video status to extracting_audio
  -> check FFmpeg availability
  -> extract WAV audio to backend/app/storage/temp/<user_id>/
  -> set video status to audio_extracted

On FFmpeg error
  -> set video status to failed
  -> save error_message on videos row
```

## Backend Layout

```text
backend/app/
  main.py              FastAPI app entrypoint and router registration
  api/auth.py          Register and login APIs
  api/users.py         Current user API
  api/videos.py        Upload, list, detail, analyze, and status APIs
  core/config.py       Environment settings
  core/security.py     Password hashing and JWT helpers
  db/database.py       SQLite connection, table initialization, local migrations
  db/models.py         Local model dataclasses
  db/schemas.py        Pydantic request and response schemas
  services/user_service.py
  services/video_service.py
  services/ffmpeg_service.py
```

## Frontend Layout

```text
frontend/src/
  main.tsx             Login, register, dashboard, upload, video list, analyze controls
  styles.css           Base styling
  vite-env.d.ts        Vite type declarations
```

## Database

Current tables:

```text
users
  id INTEGER PRIMARY KEY AUTOINCREMENT
  email TEXT NOT NULL UNIQUE
  password_hash TEXT NOT NULL
  created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP

videos
  id INTEGER PRIMARY KEY AUTOINCREMENT
  user_id INTEGER NOT NULL
  original_filename TEXT NOT NULL
  stored_filename TEXT NOT NULL
  storage_path TEXT NOT NULL
  content_type TEXT NOT NULL
  file_size INTEGER NOT NULL
  status TEXT NOT NULL CHECK (status IN ('uploaded', 'extracting_audio', 'audio_extracted', 'failed'))
  audio_path TEXT
  error_message TEXT
  created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
  updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
```

## Environment Plan

Backend secrets and local limits are read from `backend/.env`. The committed
`.env.example` file documents expected variables without exposing real secrets.

Current variables:

```text
DATABASE_URL=sqlite:///./new_cut.db
JWT_SECRET_KEY=change-this-before-production
JWT_ALGORITHM=HS256
JWT_EXPIRE_MINUTES=1440
MAX_UPLOAD_MB=500
```

## Storage Plan

Local media files are stored below `backend/app/storage/`:

```text
uploads/<user_id>/<generated_uuid>.mp4
temp/<user_id>/<stored_video_filename>.wav
audio/
transcripts/
subtitles/
outputs/
tts/
```

These folders are ignored by Git to avoid committing user media or generated
outputs.
