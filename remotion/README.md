# Remotion spike (R0) — BlogShorts

Blog → shorts Remotion compositions.

- R0: Studio / CLI render
- R1: props from real boards (`remotion-props` / `export_from_db.py`)
- R2: `@remotion/player` in frontend `BoardEditor` (same `BlogShorts` component)
- R3: `npm run service` sidecar — FastAPI `BLOG_RENDER_ENGINE=remotion` calls `POST /render`

## Render service (R3)

From repo root (starts remotion + API + Vite):

```powershell
powershell -ExecutionPolicy Bypass -File .\scripts\dev-up.ps1
powershell -ExecutionPolicy Bypass -File .\scripts\health-check.ps1
```

Or manually — Terminal A:

```bash
cd remotion
npm install
npm run service
# http://127.0.0.1:3100/health
```

Terminal B — FastAPI (`backend/.env`):

```env
BLOG_RENDER_ENGINE=remotion
REMOTION_SERVICE_URL=http://127.0.0.1:3100
BLOG_RENDER_FFMPEG_FALLBACK=true
```

Backend `GET /ready` is 503 until this service is healthy.

Blog clip **지금 렌더링** then uses Remotion (TTS/BGM still mixed in Python with sidechain ducking; video+captions via `BlogShorts`).
On Remotion failure, FFmpeg slideshow path runs if fallback is true.

### Preview audio (Player = final mix)

- `POST /blog-clips/{id}/preview-audio` — TTS + ducked BGM (+ SFX), caches mix, writes `duration_seconds` on boards
- `GET /blog-clips/{id}/preview-audio` — serve cached mix for Remotion Player `narrationUrl`
- Composition length = sum of board TTS durations (crossfade overlaps without shortening total)

- Composition: `BlogShorts` (1080×1920, 30fps)
- Dummy boards with Ken Burns zoom, board fade overlap, caption pop-in
- FastAPI / BoardEditor integration = later steps (R1+)

## License

Remotion is **free** for individuals and companies with up to 3 employees
(including commercial use under their Free License). Larger teams / automated
user-facing render services may need a paid Company License — see
[remotion.dev/docs/license](https://www.remotion.dev/docs/license).

This folder is for **local evaluation**. Encoding still uses Remotion’s bundled
FFmpeg under the hood; we are not maintaining a parallel Python slideshow here.

## Setup

```bash
cd remotion
npm install
```

Requires Node.js 18+ (20+ recommended).

## Studio (preview)

```bash
npm run studio
```

Opens Remotion Studio. Edit default props in the right panel or change
`src/types.ts` → `DEFAULT_BLOG_SHORTS_PROPS`.

## Render MP4

```bash
npm run render
```

Writes `out/blog-shorts-spike.mp4`.

Custom props file (optional):

```bash
npx remotion render BlogShorts out/custom.mp4 --props='{"title":"테스트","transitionSec":0.4,"boards":[{"text":"안녕하세요","durationSec":2.5,"backgroundColor":"#334455"}]}'
```

## Props schema (R1)

Canonical JSON Schema: [`schemas/blog-shorts-props.schema.json`](schemas/blog-shorts-props.schema.json)

Mirrored by:

- `src/types.ts` (`BlogShortsProps`)
- Backend `BlogShortsPropsResponse` + `remotion_props_service.py`
- API: `GET /blog-clips/{id}/remotion-props?materialize=true`

`materialize=true` (default) copies board images into `public/clips/{id}/` and sets
`imageUrl` to a `staticFile` path like `clips/3/board-12.jpg`.

### Export real boards from local DB (no API)

```bash
# from remotion/ — uses backend/new_cut.db (run from repo with venv that has backend deps)
cd ../backend && .\.venv\Scripts\python.exe ../remotion/scripts/export_from_db.py --clip-id 3
```

Then:

```bash
cd ../remotion
npx remotion render BlogShorts out/blog-clip-3.mp4 --props=out/props-3.json
# or open Studio and paste props / use defaultProps override
npm run studio
```

### Export via API (backend must be running)

```bash
set NEW_CUT_EMAIL=you@example.com
set NEW_CUT_PASSWORD=your-password
npm run sync-clip -- 3
```
