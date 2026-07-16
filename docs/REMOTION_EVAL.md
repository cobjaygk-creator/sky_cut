# Stage 25: FFmpeg vs Remotion evaluation

**Date:** 2026-07-15  
**Branch:** `sky_cut`  
**Decision:** **Defer Remotion.** Keep the current FFmpeg blog-clip render path.  
**Scope of this stage:** Investigation / design only. No render-engine swap, no new microservice, no Remotion code.

Related docs: `docs/PROJECT_STATUS.md`, `docs/ARCHITECTURE.md`, `docs/API_SPEC.md`.

---

## Context (what we have today)

Blog-clip Phase 2 render (`run_blog_clip_render_pipeline` /
`run_blog_clip_version_pipeline`) is entirely FFmpeg + ASS + OpenAI TTS:

| Capability | Implementation | Stage |
|---|---|---|
| 9:16 slideshow from boards | `create_image_slideshow()` | 18–20 |
| Ken Burns pan/zoom | FFmpeg `zoompan` per board | 20 |
| Caption style | `subtitle_templates` → ASS `Style` + burn-in | 8, 22 |
| Multi-voice TTS | per-board `speaker` + concat | 21 |
| BGM / SFX | `mix_narration_with_bed()` / `amix` | 23 |
| Multi-output | `blog_clip_versions` | 24 |

Editor preview today is a **static** 9:16 board preview (image + text), not a
timeline playback of the final motion/captions. That gap is UX, not
necessarily a reason to change the offline renderer.

Roadmap intent for Stage 25 (from earlier planning): only introduce Remotion
if caption animation / motion needs **outgrow** FFmpeg’s filtergraph model —
not as a default upgrade.

---

## 1) UX that current FFmpeg still cannot match well

These are real product gaps relative to SuperShorts-class tools. They are
listed in priority order for *user* impact, not for how hard Remotion would
fix them.

### Hard / awkward on FFmpeg filtergraphs

1. **Word-level / kinetic captions**  
   Karaoke-style highlight, per-word pop-in, bounce, stroke pulse timed to
   TTS phonemes. ASS can do limited `\k` karaoke and transforms, but authoring
   and previewing complex motion is painful; quality ceiling is below React
   composition tools.

2. **Rich per-scene layout composition**  
   Overlay stickers, lower-thirds, dual text blocks, progress bars, emoji
   bursts, branded frames that move independently of the slide. Possible with
   layered `overlay`/`geq`/`drawtext` graphs, but each new layout becomes a
   bespoke filter string — poor iteration speed vs JSX comps.

3. **True WYSIWYG motion preview in the board editor**  
   Remotion Player can scrub the same composition that will render. Our editor
   would need either (a) a Remotion Player embed, or (b) a separate preview
   renderer. FFmpeg cannot power interactive timeline preview without
   generating throwaway MP4s (slow, expensive).

4. **Complex transitions library**  
   We have Ken Burns; we do **not** have crossfade / wipe / zoom-through
   between boards. Some of this *is* doable with FFmpeg `xfade` (see §4), so
   this alone is **not** a Remotion trigger.

### Soft gaps (often fixable without Remotion)

| Gap | FFmpeg-first option |
|---|---|
| No board-to-board crossfade | `xfade` between segments or concat with fades |
| Caption position / safe-area polish | Extend `subtitle_templates` + ASS margins |
| Preview ≠ final look | Optional short “preview render” job, or CSS mock of ASS style |
| Auto ducking BGM under speech | `sidechaincompress` / loudnorm (Stage 23 noted as out of scope) |
| Local image upload | Product/API work, engine-agnostic |

**Bottom line for §1:** The only gaps that *strongly* argue for Remotion are
**kinetic captions**, **layout-heavy motion design**, and **shared
composition preview**. Everything else can still be pushed on FFmpeg for a
while.

---

## 2) Remotion introduction cost / stack change

### What would change

```text
Today (single process):
  FastAPI → blog_service → ffmpeg_service (+ ASS) → MP4 on disk

Proposed (if adopted):
  FastAPI → blog_service → HTTP/queue → Remotion Node microservice
                                         (Chromium headless render)
                                       → MP4 returned / written to storage
  Frontend (optional): @remotion/player for WYSIWYG preview
```

| Area | Impact |
|---|---|
| **Runtime** | Add Node.js 20+ service, Chromium, `@remotion/bundler` + `@remotion/renderer`, React compositions that mirror boards/templates |
| **Repo / ops** | Second package (e.g. `renderer/` or `remotion-service/`), second process in local dev, Docker/deploy story, health checks, version pinning with FastAPI |
| **Job model** | Today: in-process `BackgroundTasks`. Remotion almost forces a real queue (or long-lived Node worker): progress callbacks, retries, memory limits (≥4GB RAM recommended for Chromium renders) |
| **Audio path** | TTS/BGM/SFX still fit better in Python/FFmpeg *or* must be reimplemented as Remotion `<Audio>` sequencing — dual maintenance if both engines stay |
| **Templates** | ASS `subtitle_templates` would need a parallel Remotion caption component model (or abandon ASS for blog clips) |
| **License** | Remotion is free for individuals / small teams under their terms; company license may apply at larger team size — check [remotion.dev/docs/license](https://www.remotion.dev/docs/license) before commercial scale |
| **Cloud cost** | Self-host Node: pay idle RAM. Remotion Lambda: pay per render + S3; scales to zero but adds AWS. Either way, cost and ops exceed “one `uvicorn` + system FFmpeg” |
| **Engineering time (rough)** | Spike composition + one board→MP4 path: ~1–2 weeks. Production-parity (templates, multi-voice timing, BGM/SFX, versions, progress, editor Player): **several weeks**, plus ongoing dual-stack maintenance |

### What would *not* automatically improve

- Scraping quality, tone candidates, board CRUD, plans/limits, SQLite scaling
- OpenAI TTS cost / latency
- Need for a real job queue when running multiple server processes (already a known gap)

Remotion replaces **visual composition expressiveness**, not the product
pipeline around it.

---

## 3) Recommendation: introduce now vs defer

### Recommendation: **Defer (do not introduce Remotion now)**

### Rationale

1. **No hard expressiveness wall yet.** Stages 20–23 delivered Ken Burns,
   templates, and mix on FFmpeg. Known visual gap is mainly transitions +
   kinetic captions — transitions are still in FFmpeg’s comfort zone
   (`xfade`); kinetic captions are desirable but not blocking the current
   blog→shorts MVP.

2. **Stack mismatch vs team/repo shape.** This codebase is Python/FastAPI +
   a Vite React UI. A Remotion microservice is a second language runtime,
   Chromium memory profile, and deploy unit — high fixed cost for a solo /
   small team that still lacks pytest/CI and a real job queue.

3. **Preview gap ≠ render-engine mandate.** Static editor preview is the
   loudest UX complaint relative to SuperShorts, but fixing it with Remotion
   Player implies committing to Remotion as the source of truth for layout.
   That is a large product bet, not a small upgrade.

4. **Opportunity cost.** Near-term value is higher in: real job queue when
   multi-user, scrape robustness, local image upload, board crossfades,
   automated tests, and polish of the existing ASS/template/BGM path.

5. **Matches prior decision.** Architecture already recorded “FFmpeg first,
   Remotion later if needed.” Stage 20/22 did not hit a wall that invalidates
   that decision.

### When “introduce now” *would* have been justified

- Paying customers churning specifically over caption motion / brand motion
  packs that FFmpeg prototypes failed to ship, **or**
- A committed design system of many animated layouts that would take longer
  to encode as filtergraphs than as React comps.

Neither condition is met today.

---

## 4) Revisit triggers (when to re-open Stage 25+)

Re-evaluate Remotion (or another composition engine) when **any two** of the
following become true, or when **one** is acute and customer-backed:

1. **Product demand:** Kinetic / word-level captions or multi-layer motion
   layouts are an explicit roadmap item with user evidence (not just
   competitive FOMO).
2. **FFmpeg ceiling hit:** A concrete feature was attempted with
   `zoompan`/`xfade`/ASS and failed quality, maintainability, or timeline
   (e.g. >1 week of filtergraph thrash for one caption style pack).
3. **Preview requirement:** WYSIWYG timeline preview must match final pixels;
   throwaway FFmpeg preview renders are too slow or too inconsistent.
4. **Capacity:** Team can own a Node render service (or Remotion Lambda) —
   including queueing, RAM, monitoring — without starving the Python app.
5. **Scale economics:** Render volume and concurrency make Chromium/Lambda
   cost modeling worthwhile (and SQLite/`BackgroundTasks` are already being
   replaced per `DEPLOYMENT.md`).

### Suggested FFmpeg-first work *before* Remotion

If visual polish is needed without a stack split:

1. Board transitions via `xfade` (or short fade-to-black).
2. One or two richer ASS presets (background box variants, larger kinetic
   `\t` experiments) still generated from `subtitle_templates`.
3. Optional “quick preview” render (lower resolution / shorter) for the
   editor — still FFmpeg.

Only after (1)–(2) feel exhausted should Remotion be spiked as a **sidecar**
(one composition, one board set → MP4) with a feature flag — not a big-bang
replacement of `ffmpeg_service.py`.

---

## Decision record

| Item | Value |
|---|---|
| Stage 25 outcome | Evaluation complete — **Remotion deferred** (historical) |
| Product decision (2026-07) | Blog→shorts visuals: **Remotion path adopted**; R0 spike in `remotion/` |
| Render engine | **R3 done:** default `BLOG_RENDER_ENGINE=remotion` → `remotion-service` `POST /render`; FFmpeg fallback via `BLOG_RENDER_FFMPEG_FALLBACK` |
| Code changes | R0–R3: `remotion/` BlogShorts + Player + `npm run service` sidecar wired from `blog_service._render_boards_media` |
| Next | TTS/BGM polish, ops/queue, billing |
| Artifact | This file + `remotion/README.md` |
