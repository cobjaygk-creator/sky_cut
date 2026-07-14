# Deployment

## Current Status: Local-Only

New Cut currently runs **only as a local prototype** on a single Windows PC.
There is no hosted deployment, no Docker image, no CI/CD, and no production
database. This document describes (1) how the local setup actually runs
today, and (2) what would need to change before putting this in front of real
users.

## How It Runs Today

```text
Backend:  uvicorn app.main:app --reload --host 127.0.0.1 --port 8000
Frontend: vite --host 127.0.0.1 (dev server on port 5173)
Database: single SQLite file, backend/new_cut.db
Storage:  local folders under backend/app/storage/
Secrets:  backend/.env (not committed to Git)
```

See the README for exact commands. Both processes must be running at the
same time and they only listen on `127.0.0.1`, so nothing outside this PC can
reach them.

## Backup / Reset (Local)

- The entire app state is the SQLite file (`backend/new_cut.db`) plus the
  `backend/app/storage/` folders. Copy both to back up.
- To fully reset local data: stop the backend, delete `backend/new_cut.db`
  and the contents of `backend/app/storage/` (except `.gitkeep`-style empty
  folders if any), then start the backend again — `init_db()` recreates the
  schema on startup.
- `.venv/`, `node_modules/`, `*.db`, and `.env` are already excluded from Git
  (see `.gitignore`), so a fresh `git clone` never ships secrets or local data.

## What Real Deployment Would Require

This list is intentionally not implemented yet — it is a checklist for
"later," not a current task.

### 1. Secrets and configuration

- Replace the local `JWT_SECRET_KEY` placeholder with a strong, randomly
  generated secret stored in a real secrets manager (not `.env` in a repo).
- Set `APP_ENV=production` and re-check `cors_origins` in
  `backend/app/core/config.py` — it currently only allows
  `http://127.0.0.1:5173` / `http://localhost:5173`.

### 2. Database

- SQLite is fine for a single-user local MVP, but does not handle concurrent
  writers well. Before multiple real users hit the app at once, migrate to a
  server database (PostgreSQL is the natural choice) and rewrite
  `db/database.py` / the `services/*.py` SQL calls accordingly (they use raw
  `sqlite3`, not an ORM, so this is a real migration, not a config change).
- Plan for backups/point-in-time recovery on the production database.

### 3. File storage

- Local disk storage (`backend/app/storage/...`) does not survive container
  restarts or scale across multiple server instances. Move uploads, extracted
  audio, rendered clips, subtitles, and TTS audio to object storage (e.g. S3
  or a compatible service), and update `video_service.py`, `clip_service.py`,
  and `tts_service.py` to read/write there instead of local `Path` objects.

### 4. Video/audio processing (FFmpeg)

- FFmpeg/FFprobe must be installed on whatever server runs the backend (or
  bundled into a Docker image). Processing is currently synchronous inside
  the request (`subprocess.run` with timeouts up to 30 minutes) — this blocks
  a web worker for the whole render. For real traffic, move this to a
  background job queue (e.g. Celery/RQ/an async task runner) so uploads don't
  time out and multiple renders can run in parallel without starving the API.
- No GPU is used or required; this keeps hosting costs and complexity down,
  at the cost of slower renders on CPU-only hardware.

### 5. AI provider costs and reliability

- OpenAI calls (Whisper transcription, GPT highlights/metadata, TTS) all cost
  money per request and can fail with rate limits. The current error handling
  converts failures into clear HTTP errors already; for production, also add
  retry/backoff and per-user cost tracking/alerting.
- `TTS_PROVIDER` is already abstracted behind `tts_service.py` so an
  ElevenLabs (or other) backend can be added without touching
  `clip_service.py`.

### 6. Authentication and payments

- The custom HMAC-based JWT implementation in `core/security.py` works, but a
  production system should use a well-reviewed JWT library and add refresh
  tokens / token revocation instead of a single 24h-lived access token.
- No payment provider is integrated. Plan changes today require manually
  editing `users.plan` in SQLite (see README "Usage Plans"). A real launch
  needs a billing integration (e.g. Stripe) plus a webhook handler that
  updates `users.plan`.

### 7. Process hosting

- Package the backend (FastAPI + FFmpeg) into a container image; run
  `uvicorn`/`gunicorn` behind a reverse proxy (nginx / a managed load
  balancer) with HTTPS termination.
- Build the frontend (`npm run build`) into static files and serve them from
  a CDN or static hosting, pointing `VITE_API_BASE_URL` at the real backend
  domain.
- Add health checks (`GET /health` already exists) to your hosting platform's
  liveness/readiness probes.

### 8. Observability

- No structured logging, metrics, or error tracking exists yet. Before real
  users, add at least: request logging, error tracking (e.g. Sentry), and
  basic metrics (request latency, FFmpeg job duration/failure rate, OpenAI
  spend).

## Summary

Today this is a **local, single-user development prototype** that proves the
end-to-end feature set works. None of the above is required to keep using it
locally — it only matters if/when this moves toward a real hosted product
with multiple concurrent users.
