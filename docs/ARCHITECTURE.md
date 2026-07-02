# Architecture

## Goal

New Cut is a local-first MVP for an AI shorts creation SaaS. The current system
supports auth, MP4 upload, per-user video lists, FFmpeg audio extraction wiring,
OpenAI transcription wiring, and GPT-based highlight recommendation wiring.

## Current Stack

- Frontend: React + Vite + TypeScript
- Backend: Python FastAPI
- Database: SQLite
- Auth: JWT
- Password hashing: PBKDF2-SHA256 with per-password random salt
- Storage: Local file storage
- Video/audio processing: FFmpeg
- AI transcription: OpenAI Audio Transcription API
- Highlight recommendation: OpenAI GPT API with JSON response parsing

## High-Level Flow

```text
User browser
  -> React frontend
  -> FastAPI backend
  -> SQLite database
  -> Local file storage
  -> FFmpeg audio extraction
  -> OpenAI transcription
  -> GPT highlight recommendation
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

## Backend Layout

```text
backend/app/
  main.py
  api/auth.py
  api/users.py
  api/videos.py
  core/config.py
  core/security.py
  db/database.py
  db/models.py
  db/schemas.py
  services/user_service.py
  services/video_service.py
  services/ffmpeg_service.py
  services/transcription_service.py
  services/highlight_service.py
```

## Frontend Layout

```text
frontend/src/
  main.tsx       Login, register, dashboard, upload, analyze, transcript, highlights UI
  styles.css     Base styling and dashboard controls
  vite-env.d.ts  Vite type declarations
```

## Database

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
  content_type TEXT NOT NULL
  score REAL NOT NULL
  created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
```

## Environment Variables

```text
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

## Storage

```text
backend/app/storage/uploads/<user_id>/<generated_uuid>.mp4
backend/app/storage/temp/<user_id>/<stored_video_filename>.wav
backend/app/storage/audio/
backend/app/storage/transcripts/
backend/app/storage/subtitles/
backend/app/storage/outputs/
backend/app/storage/tts/
```
