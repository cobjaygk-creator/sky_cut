# Project Status

Last updated: 2026-07-15
Project root: `C:\Users\stkim\Documents\Codex\new_cut` (branch `sky_cut` — see
"Branching" below)

## Current Stage

**W5 (wizard polish) — complete.**

Stage 25 Remotion evaluation remains deferred. Wizard design lives in
`docs/WIZARD_DESIGN.md`. Coding stages **W1–W5** are done: create options,
image select, voice, style/audio, side stepper + `wizard_step` restore.

All 13 planned stages of the original local MVP are implemented, plus twelve
follow-up stages on the blog-clip pipeline (Stage 25 is docs-only — no
render-engine swap):

```text
Stage  0  Architecture/folder plan (no code)
Stage  1  Project skeleton (FastAPI + React/Vite/TS, docs)
Stage  2  Register/login/JWT, GET /me
Stage  3  Authenticated MP4 upload, video list/detail
Stage  4  FFmpeg audio extraction, analyze/status APIs
Stage  5  OpenAI transcription with timestamped segments
Stage  6  GPT highlight recommendation (3-5 candidates)
Stage  7  FFmpeg 9:16 center-cropped clip generation
Stage  8  ASS subtitle generation (3 styles) + burn-in
Stage  9  Clip download (see "Known Gaps" below for preview/list)
Stage 10  AI upload metadata: titles/description/hashtags + copy buttons
Stage 11  OpenAI TTS narration mode and narration MP4 output
Stage 12  Free/Lite/Pro plans, monthly usage limits, max video duration
Stage 13  Full review: bug fixes, full doc set (this file + 4 others)
Stage 14  Documented the blog-clip pipeline (built after Stage 13 but never
          recorded in these docs), cleaned up dead code
Stage 15  Async blog-clip processing: POST /blog-clips now returns in well
          under a second instead of blocking for up to a minute; the
          scrape/GPT/TTS/FFmpeg pipeline runs as a FastAPI background task
          and the frontend polls progress. See "Stage 15 details" below.
Stage 16  Source expansion: any blog/article URL is now accepted, not just
          blog.naver.com. See "Stage 16 details" below.
Stage 17  Script tone choice: generate summary/hook/detailed candidates,
          pause for user selection, then resume TTS/render. See
          "Stage 17 details" below.
Stage 18  Scene/board data model: blog_clip -> boards[] with CRUD/reorder,
          awaiting_boards pause after tone selection, render from board array.
          See "Stage 18 details" below.
Stage 19  Board editor frontend: split main.tsx, SuperShorts-style 3-pane
          editor (board list / 9:16 preview / media panel), wired to Stage 18
          APIs + image streaming. See "Stage 19 details" below.
Stage 20  Visual upgrade: Ken Burns pan/zoom in FFmpeg slideshow + Pexels
          stock search/apply in the board media panel. See "Stage 20 details"
          below.
Stage 21  Multi-voice TTS: voice catalog + samples, tts_speed, per-board
          speaker → render. See "Stage 21 details" below.
Stage 22  Subtitle templates: preset CRUD (font/color/background), apply to
          blog_clip, ASS burn-in from selected template. See "Stage 22 details"
          below.
Stage 23  BGM/SFX library + FFmpeg amix into blog render. See "Stage 23
          details" below.
Stage 24  Multi-variant versions: multiple outputs per blog_clip with list /
          download / per-version metadata. See "Stage 24 details" below.
Stage 25  Remotion vs FFmpeg evaluation (docs only): defer Remotion; keep
          FFmpeg. See "Stage 25 details" below and `docs/REMOTION_EVAL.md`.
```

### Wizard (post–Stage 25)

Spec: [`docs/WIZARD_DESIGN.md`](WIZARD_DESIGN.md). Maps reference screens
(create options → image select → voice → template/auto SFX/BGM) onto
Stages 17–24 APIs.

#### W1 details: create options

- DB: `blog_clips.target_length` (`short`\|`long`, default `short`),
  `blog_clips.narration_language` (`original`\|`ko`\|`en`\|`ja`, default
  `original`) + SQLite migrate ALTER
- API: `POST /blog-clips` body + `BlogClipResponse` expose both fields
- Backend: `generate_blog_narration_script_candidates(...)` uses length
  biases (~10–20s vs ~30–45s) and language rules
- Frontend: CreateStudio options row (length / language / subtitle style);
  App wires them into the create request

#### W2 details: image select

- DB: `blog_clip_image_candidates` table; `blog_clips.status` CHECK adds
  `awaiting_images` (SQLite rebuild migrator)
- Phase 1: scrape → download → persist candidates (all pre-selected) → GPT
  scripts → pause at `awaiting_images` (42%)
- APIs: `GET /blog-clips/{id}/images`, `PUT .../images/selection`
  (`image_ids`, enforce min/max), `GET .../images/{id}/file`
- `PUT .../selection` → `awaiting_script`; `select-script` boards use
  **selected images only**
- Frontend: `ImageSelectStep` in `BlogClipFlow` (selected grid + filmstrip);
  poll stops on `awaiting_images`

#### W3 details: voice step

- API: `PATCH /blog-clips/{id}/default-voice`
  `{ voice_id, tts_speed, apply_to_all_boards }`
- DB: `blog_clips.default_voice` (fallback when board `speaker` is null)
- Status stays `awaiting_boards`; client step `voice` in `BlogClipFlow`
- BoardEditor voice tab kept for per-board edits

#### W4 details: style / audio

- DB: `blog_clips.auto_bgm`, `blog_clips.auto_sfx` (default false)
- `PATCH .../audio-settings` accepts `auto_bgm` / `auto_sfx`; manual BGM
  clears `auto_bgm`
- `pick_default_bgm(tone, length)` / `pick_default_sfx()` applied in
  `start_blog_clip_render` (SFX on boards after the first)
- Flow: boards → voice → style; **프로젝트 만들기** = `POST .../render`
- BoardEditor primary CTA is “편집 완료”; render demoted to secondary

#### W5 details: stepper polish + restore

- DB: `blog_clips.wizard_step` (`boards`\|`voice`\|`style`)
- API: `PATCH /blog-clips/{id}/wizard-step`
- `select-script` seeds `wizard_step = boards`
- Frontend: vertical side stepper (horizontal on mobile); boards/voice/style
  clickable while `awaiting_boards`; reopen from workroom restores step
- Workroom row shows current wizard sub-step label

Out of scope still: Remotion packs, credits UI, my-voice, intro board.

## Branching

- `main` — frozen at the Stage 14 "1차 완료" demo snapshot (also tagged
  `v1-demo`). Do not commit here; it exists so a known-working demo is
  always available at `C:\Users\stkim\Documents\Codex\new_cut-demo` (a
  separate `git worktree` checked out to `main`, with its own copies of
  `.venv`, `.env`, `new_cut.db`, and `node_modules` so it runs standalone).
- `sky_cut` — active development branch (this folder). All Stage 15+ roadmap
  work happens here. Merge back to `main` only when explicitly decided.

### Stage 25 details: Remotion evaluation (deferred)

Stage 25 was always conditional: re-evaluate FFmpeg vs a Remotion
microservice only if caption animation / motion needs outgrew the filtergraph
model. This stage is **investigation only** — no Remotion service, no Player
embed, no replacement of `ffmpeg_service.py`.

**Decision: defer Remotion.** Full write-up: `docs/REMOTION_EVAL.md`.

Summary:

1. **FFmpeg UX gaps that still matter:** kinetic/word-level captions, rich
   multi-layer scene layouts, true WYSIWYG motion preview. Crossfades and
   simpler polish remain FFmpeg-reachable (`xfade`, ASS template tweaks).
2. **Remotion cost:** second Node/Chromium runtime, queueing/RAM ops, dual
   template model (ASS vs React comps), weeks of parity work for templates /
   multi-voice / BGM / versions — high fixed cost for this Python-first repo.
3. **Why defer now:** Stages 20–23 already cover Ken Burns, templates, and
   mix; no customer-backed expressiveness wall; opportunity cost favors
   queue/tests/scrape/upload/`xfade` polish first.
4. **Revisit when:** kinetic captions or layout packs are demanded *and*
   FFmpeg attempts fail, or WYSIWYG preview must match final pixels, with
   capacity to own a Node render path (see §4 in `REMOTION_EVAL.md`).

Not in scope for Stage 25: implementing Remotion, Lambda, or any render
swap.

### Stage 24 details: multi-variant versions

Stage 23 left one finished video per `blog_clip`. Stage 24 adds versioned
outputs so one project can hold several renders (other script tones, or a
board re-render) without breaking the existing single-download path.

1. **Table** `blog_clip_versions`: per-version paths, tone/label, status/
   progress, and its own metadata columns. Parent `blog_clips` keeps
   denormalized `video_path` / `subtitled_video_path` / metadata for the
   **active** version (`active_version_id`).
2. **First render** (`POST .../render`) still completes the parent as before,
   and also inserts the first completed version (source `boards`) and sets it
   active. Pre-Stage-24 completed rows are backfilled on `GET .../versions`.
3. **Additional versions** (parent must be `completed`):
   `POST /blog-clips/{id}/versions` with
   `mode: "boards" | "tone" | "all_tones"` queues background renders that
   update version rows only (parent stays `completed`). `all_tones` skips
   tones that already have a pending/processing/completed version.
4. **APIs**: list versions, create, download, per-version metadata,
   `POST .../versions/{vid}/set-active` (copies that version onto the parent
   for legacy download/metadata).
5. **UI**: completed blog cards show a version list with “다른 톤 만들기”,
   “보드 재생성”, per-version download / metadata / set-active.

Verified: completed clip → legacy version backfill → `all_tones` creates the
missing tone versions → list shows 2+ versions with downloadable paths;
parent download still returns the active version.

Not in scope: Remotion (Stage 25), parallel parent-status multi-job UI.

### Stage 23 details: BGM / SFX

Stage 22 left the BGM tab empty. Stage 23 adds an audio library and mix:

1. **Table** `audio_assets` (`kind` = `bgm` | `sfx`): system demo tones seeded
   under `storage/audio/system/` (generated sine/pad MP3s — no third-party
   music), plus user uploads under `storage/audio/users/<id>/`.
2. **Clip settings**: `blog_clips.bgm_asset_id`, `bgm_volume` (default `0.18`,
   capped at `0.5` so BGM cannot bury TTS).
3. **Board SFX**: `blog_clip_boards.sfx_asset_id` — plays at that board's
   start time during mix.
4. **APIs**: `GET/POST/DELETE /audio-assets`, `GET .../{id}/file`,
   `PATCH /blog-clips/{id}/audio-settings`, board PATCH `sfx_asset_id`.
5. **Render**: after TTS, `mix_narration_with_bed()` loops/trims BGM, delays
   SFX, `amix` with narration at volume 1.0, then slideshow uses the mixed
   track. No BGM/SFX → unchanged narration-only path.
6. **UI**: board editor BGM tab — pick/preview/upload BGM, volume, per-board
   SFX, clear.

Not in scope: Remotion (25), auto ducking beyond the fixed volume cap.
Multi-variant versions are Stage 24.

### Stage 22 details: subtitle templates

Stage 21 left three hardcoded ASS styles (`basic` / `bold` / `shorts`).
Stage 22 turns them into a template system:

1. **Table** `subtitle_templates`: system rows (`user_id NULL`, slug
   basic/bold/shorts) seeded on `init_db`, plus per-user custom presets.
2. **Fields**: font name/size, primary/outline/back colors (+ alpha), bold,
   outline, shadow, margins, `border_style` (1=outline, 3=opaque box for
   background).
3. **CRUD API**: `GET/POST /subtitle-templates`, `PATCH/DELETE .../{id}`,
   `POST .../{id}/clone` (system presets are read-only; clone then edit).
4. **Apply**: `blog_clips.subtitle_template_id` via
   `PATCH /blog-clips/{id}/template` while `awaiting_boards`. Create still
   accepts `style` and links the matching system template.
5. **Render**: `resolve_ass_params_for_blog_clip` → `write_ass_file(..., AssStyleParams)`.
6. **UI**: board editor 템플릿 tab — list/apply/create/edit/clone/delete.

Video-clip `POST /clips/{id}/subtitles` still uses the three builtin keys.
Not in scope: multi-variant (24). BGM/SFX are Stage 23.

### Stage 21 details: multi-voice TTS

Stage 20 left a single global TTS voice. Stage 21 adds a voice catalog and
per-board assignment:

1. **Catalog**: `GET /voices` returns OpenAI static catalog, or Typecast
   `/v2/voices` when `TTS_PROVIDER=typecast`. Samples cache under
   `storage/tts/samples/{provider}_{voice}.mp3`.
2. **Speed**: `blog_clips.tts_speed` (default `1.0`, range 0.25–4.0; Typecast
   tempo clamped to 0.5–2.0). `PATCH /blog-clips/{id}/tts-settings`.
3. **Per-board speaker**: `blog_clip_boards.speaker` stores a catalog voice
   id (or NULL = provider default). PATCH board accepts `speaker`.
4. **Render**: per-board TTS + concat for blog boards; `synthesize_openai_tts`
   dispatches to OpenAI or Typecast.
5. **UI**: board editor 음성 tab — list/sample/apply voice to selected board,
   speed control, clear back to default. Board list shows a speaker badge.

Video-clip narration uses the same provider switch.

### Stage 20 details: Ken Burns + stock search

Stage 19 shipped the board editor; Stage 20 upgrades visuals and media sources:

1. **Ken Burns**: `create_image_slideshow()` uses FFmpeg `zoompan` so each
   board segment slowly zooms in/out or pans (pattern cycles by board index).
   Still images are looped inputs; `d=frames` sets segment length from board
   durations (same Stage 18 timing rules).
2. **Stock provider**: free **Pexels** API (`PEXELS_API_KEY` in
   `backend/.env`; documented in root `.env.example`). Missing/invalid key
   returns a clear Korean `400` message — no silent empty results.
3. **APIs**:
   - `GET /blog-clips/{id}/stock-search?query=...`
   - `POST /blog-clips/{id}/boards/{board_id}/stock-image` with
     `{ "download_url": "https://images.pexels.com/..." }`
   Downloads land in the clip image folder; board `image_path` is updated
   under the existing awaiting_boards mutation gate.
4. **UI**: media panel stock search form → thumbnail grid → click applies to
   the selected board. Scraped-image swap and duration controls unchanged.

Not in scope for Stage 20: local file upload, multi-voice (21), templates
(22), BGM/SFX (23).

### Stage 19 details: board editor frontend

Stage 18 exposed board CRUD/reorder/render APIs with only a "바로 렌더링"
shim in the UI. Stage 19 replaces that with a full board editor:

1. **Component split**: `frontend/src/main.tsx` is now a thin entry point;
   types/constants/api client/utils and dashboard components live under
   `frontend/src/` (`App.tsx`, `components/Dashboard.tsx`,
   `components/VideoList.tsx`, `components/board/*`, etc.).
2. **Editor entry**: when a blog clip is `awaiting_boards`, the card CTA is
   "보드 편집". Opening it shows a full-panel 3-column editor
   (list / 9:16 static preview / media tabs).
3. **Editing**: inline text (PATCH on blur), HTML5 DnD + ▲▼ reorder
   (`PUT .../reorder`), add (clone an existing `image_path`), delete,
   optional duration, image swap among downloaded images.
4. **Preview images**: browser cannot load server filesystem paths, so
   Stage 19 adds one backend endpoint:
   `GET /blog-clips/{id}/boards/{board_id}/image` (auth + ownership).
   The frontend fetches with Bearer and uses blob URLs.
5. **Render**: editor header "렌더링 시작" calls `POST .../render`, closes
   the editor, and resumes Stage 15 polling.

BGM tab is Stage 23; template is Stage 22; voice is Stage 21. Stock search and
Ken Burns are Stage 20. Local *image* upload is still out of scope (audio
upload is available).

### Stage 18 details: scene/board data model

Stage 17 paused at `awaiting_script` for tone choice, then immediately ran TTS
after `select-script`. Stage 18 inserts a **board editing window** between
tone selection and rendering:

1. **Phase 1** (`run_blog_clip_pipeline`): unchanged — scrape -> images ->
   three script candidates -> `awaiting_script` (45%).
2. **Tone + board bootstrap** (`POST /blog-clips/{id}/select-script`):
   saves `script_tone` / `narration_script`, auto-creates one board per
   downloaded image (script split across boards by sentence proportion),
   then stops at `status: "awaiting_boards"`, `progress_stage:
   "awaiting_boards"` (50%). No background render is scheduled here.
3. **Board editing** (optional, via new board CRUD/reorder APIs while status
   is `awaiting_boards`): each board has `image_path`, `text`,
   `duration_seconds` (optional), `order_index`, and `speaker` (Stage 21
   voice id, or NULL for default).
4. **Phase 2** (`POST /blog-clips/{id}/render` +
   `run_blog_clip_render_pipeline`): validates at least one board exists,
   merges board texts into `narration_script`, then TTS -> slideshow (board
   order + optional per-board durations) -> board-boundary subtitles ->
   `completed`.

Schema / API changes:

- New table `blog_clip_boards` (FK to `blog_clips`, indexed by
  `blog_clip_id`).
- `blog_clips.status` CHECK rebuilt to allow `awaiting_boards`.
- New endpoints: `GET/POST /blog-clips/{id}/boards`,
  `PATCH/DELETE /blog-clips/{id}/boards/{board_id}`,
  `PUT /blog-clips/{id}/boards/reorder`, `POST /blog-clips/{id}/render`.
- `select-script` no longer schedules background render.
- `create_image_slideshow()` accepts optional `image_durations` for
  per-board timing.
- Frontend (pre-Stage 19) had a minimal `awaiting_boards` shim; Stage 19
  replaces it with the board editor.

Verified end-to-end: create -> `awaiting_script` -> `select-script` ->
`awaiting_boards` with boards == image count -> PATCH text -> DELETE one ->
reorder -> `render` -> poll to `completed`.

Not in scope for Stage 18: drag-and-drop board editor UI (Stage 19), Ken
Burns (Stage 20), per-board TTS / speaker catalog (Stage 21), templates/BGM
(Stages 22-23), multi-variant projects (Stage 24).

### Stage 17 details: script tone choice

Previously the blog-clip pipeline generated exactly one narration script and
immediately continued into TTS/FFmpeg. Stage 17 splits that into two phases
so the user can pick a tone before money is spent on TTS/render:

1. **Phase 1** (`run_blog_clip_pipeline`): scrape -> download images ->
   GPT generates three tone variants in one JSON call
   (`summary` / `hook` / `detailed`) -> save them on the row and stop at
   `status: "awaiting_script"`, `progress_stage: "awaiting_script"` (45%).
2. **Phase 2** (`POST /blog-clips/{id}/select-script` then optional board
   edits, then `POST /blog-clips/{id}/render` +
   `run_blog_clip_render_pipeline`): user picks a tone -> boards auto-created
   -> user may edit boards -> `render` resumes TTS/FFmpeg until `completed`
   or `failed`.

Schema / API changes:

- `blog_clips` gained `script_tone` and `script_candidates_json`. Existing
  DBs are migrated; the status CHECK constraint was rebuilt to allow the new
  `awaiting_script` value (SQLite cannot ALTER CHECK in place).
- `BlogClipResponse` now includes `script_tone` and `script_candidates`
  (`{ summary, hook, detailed }`).
- New endpoint: `POST /blog-clips/{id}/select-script` with
  `{ "tone": "summary" | "hook" | "detailed" }`.
- Frontend stops polling when status becomes `awaiting_script`, shows the
  three candidates with Korean labels (요약형 / 후킹형 / 상세형). After
  Stage 18, tone selection moves to `awaiting_boards` (board editor); polling
  resumes only after `POST .../render`.

Verified (tone-choice core): create -> poll to `awaiting_script` with all
three candidates -> `select-script` with `hook` sets `script_tone: "hook"`.
Full render completion is covered by Stage 18/19 (`awaiting_boards` ->
editor -> `render` -> `completed`).

Not in scope for Stage 17: editing a candidate free-form before render,
regenerating only one tone, or producing multiple finished videos from the
same request (that is Stage 24).

### Stage 16 details: source expansion beyond blog.naver.com

`backend/app/services/blog_service.py` previously had a hard `if
"blog.naver.com" not in url: raise 400` check, so any other blog/article URL
was rejected outright. This stage replaces that with a dispatcher:

- `fetch_blog_content(url)` checks the URL's host (`_is_naver_blog_url`) and
  routes to either the existing Naver-specific parser
  (`fetch_naver_blog_content`, unchanged — still targets
  `div.se-main-container` / `.se-text-paragraph` exactly) or the new
  `fetch_generic_blog_content(url)` for everything else.
- `fetch_generic_blog_content` strips non-content tags (`script`, `style`,
  `nav`, `header`, `footer`, `aside`, `form`, `iframe`, `button`, `svg`), then
  tries a prioritized list of container selectors covering common platforms
  (`article`, `[role=main]`, `main`, `.entry-content`, `.post-content`,
  Tistory/Velog-style classes, etc.). If none of those match (or match too
  little text), it falls back to "the `<div>` with the most visible text on
  the page" — a simple but effective heuristic for unfamiliar layouts.
- Title extraction tries `og:title` -> `<title>` -> first `<h1>` -> a Korean
  placeholder, in that order.
- Image extraction (`_extract_image_urls`, shared by both the Naver and
  generic paths) now resolves relative `src`/`data-src`/`data-lazy-src`/
  `data-original` attributes against the page URL with `urljoin`, since
  non-Naver sites commonly use root-relative or lazy-loaded image paths
  (Naver's CDN URLs are already absolute, so this is a no-op there). If the
  content container alone doesn't have enough images
  (`blog_image_min_count`), the search widens to the whole page as a
  fallback (e.g. a hero image rendered outside the article body).
- No API or database changes — `POST /blog-clips` still accepts any
  `HttpUrl` (Pydantic already allowed this; the restriction was enforced
  deep inside the pipeline, not at the API boundary), and a non-Naver URL
  that fails to scrape still surfaces as a `failed` blog clip with a Korean
  `error_message`, exactly like any other pipeline failure.
- Frontend copy updated: the blog form label/placeholder/helper text no
  longer says "네이버 블로그 URL" / "네이버 블로그 글만 지원" — now "블로그/글
  URL" with a note that Naver, Tistory, brunch, etc. are all supported.
- Verified end-to-end against a live non-Naver URL
  (`https://en.wikipedia.org/wiki/Short_film`): the pipeline correctly
  extracted the page title, scraped body text, generated a Korean narration
  script via GPT, synthesized TTS, rendered the slideshow, and completed
  with a working `video_path`/`subtitled_video_path` — the exact same
  progress-checkpoint flow as a Naver post from Stage 15.

Not in scope for Stage 16: the generic extractor is a best-effort heuristic,
not a true "reader mode" (e.g. Mozilla Readability). Pages that are heavily
JavaScript-rendered (content injected client-side with no server-rendered
HTML) will not scrape correctly since `requests` only fetches the initial
HTML. Sites that block scraping (paywall, bot detection, robots.txt) will
surface as a `failed` blog clip with an HTTP-error message, same as before.

### Stage 15 details: async processing

`POST /blog-clips` previously ran the entire scrape -> download images ->
GPT script -> OpenAI TTS -> FFmpeg slideshow -> subtitle burn-in pipeline
synchronously inside one HTTP request (up to ~1 minute). This was the #1
item in the Stage 14 roadmap ("Known Gaps") because every later blog-clip
feature (scene editing, multi-voice TTS, templates, etc.) needs a working
async/progress foundation first.

What changed:

- `blog_clips` gained two columns: `progress_stage` (a short machine-readable
  stage name) and `progress_percent` (0-100). Existing rows were
  backfilled (`completed` -> `done`/100) by a migration in `database.py`.
- `backend/app/services/blog_service.py` is split into `create_blog_clip_job()`
  (fast: validates the style, inserts a `pending`/`queued`/0% row, returns
  immediately) and `run_blog_clip_pipeline()` (the actual multi-step work,
  called via FastAPI's `BackgroundTasks` so it runs after the HTTP response
  is already sent). The pipeline function opens its own SQLite connection
  (the request-scoped one is already closed by the time a background task
  runs) and updates `progress_stage`/`progress_percent` at 7 checkpoints:
  `queued(0) -> scraping(10) -> downloading_images(25) ->
  generating_script(40) -> synthesizing_audio(55) -> rendering_video(75) ->
  burning_subtitles(90) -> done(100)`.
- `frontend/src/main.tsx`: `POST /blog-clips` now just adds the `pending` row
  to the list and starts a 2-second polling interval (`pollBlogClip()`)
  against `GET /blog-clips/{id}` until the row reaches `completed` or
  `failed`. `loadBlogClips()` also resumes polling for any rows that were
  still `pending`/`processing` from a previous session (e.g. after a page
  reload). `BlogClipCard` renders a progress bar + Korean stage label
  (`BLOG_PROGRESS_STAGE_LABELS`) while a clip is in progress.
- Verified end-to-end against the live OpenAI API: `POST /blog-clips`
  returned in ~79ms with `status: "pending"`, and polling `GET
  /blog-clips/{id}` showed real stage transitions
  (`synthesizing_audio(55%) -> rendering_video(75%) -> completed/done(100%)`)
  before the video finished rendering, then the completed row had a working
  `video_path`/`subtitled_video_path` exactly as before this change.

Not in scope for Stage 15 (still true after this stage, unchanged from the
Stage 14 roadmap): no retry endpoint for a `failed` blog clip (the user just
submits the URL again, creating a new row), no cancel-in-progress action,
and progress is still per-blog_clip in the same SQLite table (no separate
job-queue table/worker process — this remains an in-process background task,
which is enough for a single local server but would need Celery/RQ-style
infrastructure for multi-worker/multi-machine deployments).

Real payment integration is still intentionally not implemented (by design,
see original plan). YouTube URL import (`yt-dlp`) was added alongside Stage 3
as an extra input path, ahead of the original plan.

### Stage 14 details: the undocumented blog-clip feature

Between Stage 13 and this entry, a second content pipeline was built
directly in code — `backend/app/api/blog.py`, `backend/app/services/
blog_service.py`, `backend/app/services/subtitle_utils.py`, the `blog_clips`
table, and a full `frontend/src/main.tsx` UI section — but it was never added
to `docs/ARCHITECTURE.md`, `docs/API_SPEC.md`, or this file, and none of it
had been committed to git yet. This stage is that documentation catch-up,
plus two small cleanups:

- Removed `backend/app/services/openai_service.py` (dead placeholder file
  from the Stage 1 skeleton, confirmed unused by any import).
- Removed the stray `new_cut.zip` (~43 MB) from the project root (an
  untracked manual backup, not referenced by any code).

What the blog-clip feature actually does today: paste a `blog.naver.com`
post URL in, and in one request get back a narrated 1080x1920 slideshow
video with burned-in captions and (optionally) AI-generated title/
description/hashtags. See `docs/ARCHITECTURE.md` "Blog clips" workflow and
`docs/API_SPEC.md` "Blog Clips" for the full technical detail. This is the
first working slice of a broader "blog/text -> shorts" product direction
(benchmarked against SuperShorts-style competitors) — see "Roadmap: Blog
Clips -> SuperShorts-Level Product" below for the follow-up plan.

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

Note: the Stage 13 review also created several throwaway test accounts
(`stage13-...@example.com`, `verify-...@example.com`) directly in
`backend/new_cut.db` while exercising the API end to end. They are harmless
local-only test data (the `.db` file is gitignored) and can be deleted along
with the database file if you want a clean slate — see
`docs/DEPLOYMENT.md` "Backup / Reset (Local)".

## Environment

Runtime backend env file:

```text
backend/.env
```

Important variables (see `docs/ARCHITECTURE.md` for the full list and
`.env.example` for the template):

```text
DATABASE_URL=sqlite:///./new_cut.db
JWT_SECRET_KEY=local-dev-new-cut-change-before-production
MAX_UPLOAD_MB=500
OPENAI_API_KEY=
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
```

`TTS_API_KEY` is optional for OpenAI mode. If empty, TTS uses
`OPENAI_API_KEY`. Do not commit real API keys.

As of this review, the local `backend/.env` has `OPENAI_API_KEY` empty, and
FFmpeg/FFprobe are **not** on this PC's PATH in the shell used for testing.
Both are required for the AI/video-processing endpoints to fully succeed;
see `README.md` "Troubleshooting" and "FFmpeg Setup".

## Stage 13 Review Findings

A full pass was made over every backend module, every API endpoint, and the
frontend build, specifically looking for defects before calling the MVP done.

### Bugs found and fixed in this review

1. **`POST /auth/register` always failed with a 500 error.** The endpoint
   built its `UserResponse` with only `id`, `email`, and `created_at`, but
   the schema (updated for Stage 12's usage/plan fields) requires `plan`,
   `monthly_usage`, `usage_limit`, and `usage_month` too. Every registration
   attempt raised a pydantic validation error. Fixed in `backend/app/api/auth.py`
   by populating all required fields from the created user. Verified with a
   live `TestClient` call: before the fix this returned `500`; after the fix
   it returns `201` with the full user payload.
2. **AI narration prompts never included the original video title.**
   `generate_narration_script()` in `backend/app/services/tts_service.py` tried
   to read `highlight["user_id"]`, a column that was never selected in the
   calling query, so the lookup always silently produced `None` and the
   narration prompt's "Original video" field was always blank. Fixed by
   passing `user_id` explicitly from `clip_service.apply_clip_narration()`
   into `generate_narration_script()` instead of guessing it from the
   highlight row.

### Verified working (code review + live API calls where FFmpeg/OpenAI were not required)

- Health check, register, duplicate-register rejection, login,
  wrong-password rejection, `/me`, `/usage`, `/plans`.
- Video upload (valid mp4 extension/content-type accepted, `.txt` rejected
  with `400`), video list, video detail.
- Ownership checks: unauthenticated requests get `403`, invalid/garbage
  tokens get `401`, cross-user access to another user's video/clip returns
  `404` (not found, not "forbidden" — so it does not leak existence).
- Graceful, non-crashing error handling when FFmpeg/FFprobe are missing
  (`analyze` returns a clear `500` with an actionable message and marks the
  video `failed` instead of throwing an unhandled exception).
- Graceful error handling when `OPENAI_API_KEY` is unset: transcript,
  highlights, metadata, and AI narration all return a clear `400` instead of
  crashing.
- State-machine guards: `transcript`/`highlights`/`clips/create`/`subtitles`/
  `narration` all correctly reject with `404`/`409` when a prerequisite step
  (audio extracted / transcript completed / clip completed) has not happened
  yet, verified by seeding a transcript+highlight row directly and exercising
  `POST /clips/create` (fails cleanly with "FFmpeg is not installed...") and
  `POST /clips/{id}/metadata` (fails cleanly with "OPENAI_API_KEY is not
  configured.").
- `backend`: `python -m compileall app` passes with no syntax errors.
- `frontend`: `npm run build` (`tsc -b && vite build`) completes with no type
  errors and produces `frontend/dist/`.
- Every API path called from `frontend/src/main.tsx` has a matching backend
  route (no dead/mismatched endpoint calls found).

### Not fully verified (requires FFmpeg + a real OpenAI key, not available in this review environment)

- A real end-to-end run: upload a real short mp4 -> analyze -> transcript ->
  highlights -> create clip -> burn subtitles -> apply AI narration ->
  generate metadata -> download, all with real audio/video content.
- OpenAI rate-limit / API-error handling under real quota pressure.
- YouTube import (`yt-dlp`) against a live video.
- Over-limit behavior with real long videos across all three plan tiers.

### Known gaps vs. the original 13-stage plan (not bugs, just scope not built)

- `GET /clips/{clip_id}/preview` and `GET /clips` (list-all-my-clips) from the
  original Stage 9 plan were never implemented as separate endpoints. Preview
  today works implicitly through `GET /clips/{clip_id}` (which returns
  `output_path`) or by downloading via `GET /clips/{clip_id}/download`. There
  is no single endpoint that lists every clip a user has ever created — the
  frontend only shows clips attached to highlights currently loaded in memory.

### Known gaps in the blog-clip feature (see "Roadmap" below for the plan)

- Generic (non-Naver) scraping is a best-effort heuristic (common container
  selectors + "biggest `<div>` by text" fallback), not a true reader-mode
  parser — it can still fail on heavily JS-rendered pages or sites that
  block scraping.
- Script tone choice is summary/hook/detailed only — no free-form edit of a
  candidate before board generation, and no regenerate-one-tone action.
- Board editor: stock, voice, subtitle templates, and BGM/SFX work. Local
  image upload is not available.
- Blog clips support voice catalog / `tts_speed` / per-board `speaker`
  (Stage 21), subtitle templates (Stage 22), and BGM/SFX amix (Stage 23).
  Video-clip narration still uses the single env default voice; video-clip
  burn-in still uses the three builtin style keys.
- Slideshow includes Ken Burns pan/zoom (Stage 20); no crossfade/transitions
  library yet. Remotion was evaluated and **deferred** (Stage 25) — see
  `docs/REMOTION_EVAL.md`.
- Blog-clip create UX is still shorter than the planned wizard (no
  create-time length/language, no `awaiting_images` select, no dedicated
  pre-render voice/style steps). Spec: `docs/WIZARD_DESIGN.md`.

## Current API Summary

See `docs/API_SPEC.md` for full request/response details.

Auth and user:

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

Blog clips:

```text
POST /blog-clips
GET /blog-clips
GET /blog-clips/{blog_clip_id}
POST /blog-clips/{blog_clip_id}/select-script
GET /blog-clips/{blog_clip_id}/boards
POST /blog-clips/{blog_clip_id}/boards
PATCH /blog-clips/{blog_clip_id}/boards/{board_id}
DELETE /blog-clips/{blog_clip_id}/boards/{board_id}
GET /blog-clips/{blog_clip_id}/boards/{board_id}/image
PUT /blog-clips/{blog_clip_id}/boards/reorder
GET /blog-clips/{blog_clip_id}/stock-search
POST /blog-clips/{blog_clip_id}/boards/{board_id}/stock-image
PATCH /blog-clips/{blog_clip_id}/tts-settings
PATCH /blog-clips/{blog_clip_id}/template
PATCH /blog-clips/{blog_clip_id}/audio-settings
POST /blog-clips/{blog_clip_id}/render
POST /blog-clips/{blog_clip_id}/metadata
GET /blog-clips/{blog_clip_id}/metadata
GET /blog-clips/{blog_clip_id}/download
GET /voices
GET /voices/{voice_id}/sample
GET /subtitle-templates
POST /subtitle-templates
PATCH /subtitle-templates/{template_id}
POST /subtitle-templates/{template_id}/clone
DELETE /subtitle-templates/{template_id}
GET /audio-assets
POST /audio-assets
GET /audio-assets/{asset_id}/file
DELETE /audio-assets/{asset_id}
```

## Current Database Summary

See `docs/ARCHITECTURE.md` "Database" for full column lists. Tables:
`users`, `videos`, `transcripts`, `highlights`, `clips`, `clip_metadata`,
`blog_clips`, `blog_clip_boards`, `subtitle_templates`, `audio_assets`.

## What Works End-to-End Today (Summary)

With FFmpeg installed and a valid `OPENAI_API_KEY` set in `backend/.env`, a
user can, entirely through the local web UI:

1. Register and log in (JWT-authenticated).
2. Upload an MP4, or import a YouTube video by URL.
3. Click Analyze to extract audio (checked against their plan's monthly
   video count and per-video minute limit).
4. Fetch an AI transcript with timestamps.
5. Get 3-5 AI-recommended highlight clips (15-60s each, scored and
   categorized).
6. Generate a 9:16 vertical clip from a chosen highlight.
7. Burn in Korean-safe captions in one of three styles.
8. Choose between the clip's original audio or an AI-narrated voiceover.
9. Generate 3 title candidates, a description, and 10 hashtags, and copy
   them with one click.
10. Download the final rendered MP4.
11. See their current plan, monthly usage, and remaining quota at any time.
12. Paste a blog/article URL (Naver blog, Tistory, brunch, or most other
    blogs/news pages), wait for three narration-tone candidates
    (summary/hook/detailed), pick one, then get back a narrated 1080x1920
    slideshow video with burned-in captions; optionally generate
    title/description/hashtags for it and download it.

This is a genuinely complete MVP loop for a single local user. It is not yet
a deployable multi-user product — see `docs/DEPLOYMENT.md` for the gap
between "runs on my PC" and "runs as a real hosted service."

## Recommended Next Steps

1. Install FFmpeg and set a real `OPENAI_API_KEY` locally, then do one real
   end-to-end run with a short test video to confirm the full pipeline
   produces a correct, watchable output file (both the video-clipping
   pipeline and the blog-clip pipeline).
2. Decide whether to implement the missing `GET /clips` (list) and
   `GET /clips/{clip_id}/preview` endpoints, or intentionally drop them from
   scope.
3. Add automated tests (even a small pytest suite around the service layer)
   so future stages don't reintroduce regressions like the register bug
   found in the Stage 13 review.
4. When ready to support more than one concurrent real user, read
   `docs/DEPLOYMENT.md` and plan the database/storage/queueing migration
   before adding a payment provider.
5. Blog-clip Stages 15–25 and wizard **W1–W5** are done. Next work is
   product polish outside the wizard (tests, deploy, optional Stage 9 gaps).

## Roadmap: Blog Clips -> SuperShorts-Level Product

This roadmap was planned after benchmarking the blog-clip feature above
against SuperShorts (`supershorts.co.kr`) and similar "blog/text -> shorts"
products (Vrew, ShortsGen). The goal is not to replace the video-clipping
pipeline (Stages 1-13) but to grow the blog-clip pipeline into an equivalent
or better product, on top of the auth/plan/storage foundation both pipelines
already share. Stages are ordered so that the riskiest foundational work
(async processing, frontend componentization) happens before feature work
that depends on it.

```text
Stage 15  DONE (2026-07-14). Async processing: POST /blog-clips returns
          immediately (pending), the pipeline runs in the background,
          frontend polls status/progress. See "Stage 15 details" above.
Stage 16  DONE (2026-07-14). Source expansion: generic blog/URL scraping
          beyond blog.naver.com. See "Stage 16 details" above.
Stage 17  DONE (2026-07-14). Script tone choice: generate
          summary/hook/detailed candidates, pause at awaiting_script, let
          the user pick one, then resume TTS/render. See "Stage 17 details"
          above.
Stage 18  DONE. Scene/board data model: blog_clip -> boards[] with CRUD/
          reorder, awaiting_boards pause, POST .../render. See "Stage 18
          details" above.
Stage 19  DONE. Board editor frontend: main.tsx split, 3-pane editor
          (list / 9:16 preview / media panel), image streaming endpoint.
          See "Stage 19 details" above.
Stage 20  DONE. Ken Burns pan/zoom in FFmpeg slideshow + Pexels stock
          search/apply in the media panel. See "Stage 20 details" above.
Stage 21  DONE. Multi-voice TTS: catalog + samples, tts_speed, per-board
          speaker in render. See "Stage 21 details" above.
Stage 22  DONE. Subtitle templates: preset CRUD, apply to blog_clip, ASS
          from selected template. See "Stage 22 details" above.
Stage 23  DONE. BGM/SFX library + FFmpeg amix into blog render. See
          "Stage 23 details" above.
Stage 24  DONE. Multi-variant versions: multiple outputs per blog_clip
          (tone variants / board regenerate), list/download/metadata,
          active version. See "Stage 24 details" above.
Stage 25  DONE (eval only). Remotion deferred — keep FFmpeg. See
          "Stage 25 details" above and `docs/REMOTION_EVAL.md`.

Wizard (see docs/WIZARD_DESIGN.md):
W1        DONE. Create options: target_length, narration_language + UI
W2        DONE. Image candidates + awaiting_images select step
W3        DONE. Pre-render voice step + default-voice API
W4        DONE. Style/audio step: auto_bgm / auto_sfx + template picker
W5        DONE. Stepper polish + wizard_step restore from workroom
```

Decisions already made (do not re-litigate these without a new reason):

- **Same repo, same database.** `boards`/`projects` tables added alongside
  the existing `videos`/`clips`/`blog_clips` tables — not a separate project.
  The existing auth/plan/usage/OpenAI/FFmpeg service layers are reused, not
  rebuilt.
- **FFmpeg first; Remotion deferred after Stage 25 evaluation.** Remotion is
  not scheduled. Re-open only when the revisit triggers in
  `docs/REMOTION_EVAL.md` §4 are met (kinetic captions / layout packs with
  evidence, FFmpeg ceiling, WYSIWYG preview requirement, ops capacity).
- **UI should match SuperShorts' UX patterns/information architecture (step
  wizard, board list, tabbed media/voice/audio panel), not its visual
  identity.** Copying layout structure is fine; copying specific icons,
  colors, or copy text is not (trademark/trade-dress risk, and it forecloses
  differentiation).
