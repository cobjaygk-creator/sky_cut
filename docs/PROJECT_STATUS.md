# Project Status

## Current Stage

Stage 4: FFmpeg audio extraction from uploaded videos.

## Completed In Stage 1

- Created root project structure under `C:\Users\stkim\Documents\Codex\new_cut`
- Added FastAPI backend skeleton
- Added backend `/health` endpoint
- Added React + Vite + TypeScript frontend skeleton
- Added docs folder
- Added `README.md`
- Added `docs/ARCHITECTURE.md`
- Added `.env.example`
- Added `.gitignore`
- Installed Python 3.12 with `winget`
- Created backend virtual environment at `backend/.venv`
- Installed frontend and backend dependencies
- Verified frontend and backend local servers

## Completed In Stage 2

- Added SQLite `users` table initialization
- Added password hashing with PBKDF2-SHA256 and per-password random salt
- Added JWT creation and verification using `JWT_SECRET_KEY` from `backend/.env`
- Added `POST /auth/register`
- Added `POST /auth/login`
- Added `GET /me`
- Added frontend login screen
- Added frontend register screen
- Added frontend dashboard after successful login

## Completed In Stage 3

- Added SQLite `videos` table initialization
- Added `MAX_UPLOAD_MB` setting in `.env`
- Added MP4-only upload validation
- Added per-user local upload storage under `backend/app/storage/uploads/<user_id>/`
- Added `POST /videos/upload`
- Added `GET /videos`
- Added `GET /videos/{video_id}`
- Added frontend MP4 upload form
- Added frontend my video list in the dashboard

## Completed In Stage 4

- Added FFmpeg availability check logic
- Added FFmpeg audio extraction service
- Added `backend/app/storage/temp/` output path for extracted WAV files
- Expanded video statuses to `uploaded`, `extracting_audio`, `audio_extracted`, and `failed`
- Added `audio_path`, `error_message`, and `updated_at` columns to `videos`
- Added videos table migration for existing local data
- Added `POST /videos/{video_id}/analyze`
- Added `GET /videos/{video_id}/status`
- Added frontend Analyze and Refresh buttons
- Added dashboard display for audio extraction status and errors
- Updated `README.md` with FFmpeg installation instructions

## Not Implemented Yet

- OpenAI API integration
- AI transcription
- Highlight recommendation
- Shorts generation
- Subtitle burn-in
- TTS
- Usage limits and plan structure

## Local Verification

### Frontend

Status: Verified.

- Command used: `npm.cmd run build`
- Dev URL: `http://127.0.0.1:5173`

### Backend

Status: Partially verified because FFmpeg is not installed on this PC yet.

- Backend compile check: passed
- Health check: passed
- `GET /videos/{video_id}/status`: passed
- `POST /videos/{video_id}/analyze`: verified missing-FFmpeg failure path
- Missing FFmpeg result: video status changed from `uploaded` to `failed`
- Saved error message: `FFmpeg is not installed or is not available in PATH.`

## Next Stage

Stage 5 should add OpenAI transcription:

- Read `OPENAI_API_KEY` from `.env`
- Implement `transcription_service.py`
- Send extracted audio to OpenAI Transcription API
- Store transcript text and segment timestamps
- Add `transcripts` table
- Add transcript result API
- Show transcript status or result in the dashboard

## Notes

Install FFmpeg before testing the successful audio extraction path:

```powershell
winget install --id Gyan.FFmpeg --source winget
```

The project is intentionally local-first. Cloud storage, payment integration,
GPU processing, and production deployment are out of scope for the current MVP
stage.
