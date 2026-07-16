from contextlib import asynccontextmanager
from typing import Any

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from app.api import audio, auth, blog, clips, templates, users, videos, visual_styles, voices
from app.core.config import settings
from app.db.database import init_db
from app.services.remotion_render_service import check_remotion_service_health
from app.services.render_queue import render_queue_stats


@asynccontextmanager
async def lifespan(app: FastAPI):
    init_db()
    yield


app = FastAPI(title=settings.app_name, lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(auth.router)
app.include_router(users.router)
app.include_router(videos.router)
app.include_router(clips.router)
app.include_router(blog.router)
app.include_router(voices.router)
app.include_router(templates.router)
app.include_router(visual_styles.router)
app.include_router(audio.router)


@app.get("/health")
def health_check() -> dict[str, Any]:
    """Liveness: backend process is up. Includes remotion + render-queue probe."""
    from app.services.tts_service import tts_provider_name

    remotion = check_remotion_service_health()
    return {
        "status": "ok",
        "service": "new-cut-backend",
        "tts_provider": tts_provider_name(),
        "blog_render_engine": (settings.blog_render_engine or "remotion").strip().lower(),
        "blog_render_ffmpeg_fallback": bool(settings.blog_render_ffmpeg_fallback),
        "remotion": remotion,
        "render_queue": render_queue_stats(),
    }


@app.get("/ready")
def readiness_check() -> JSONResponse:
    """Readiness: when Remotion is the render engine, sidecar must be healthy."""
    remotion = check_remotion_service_health()
    engine = (settings.blog_render_engine or "remotion").strip().lower()
    ready = True
    if engine == "remotion" and not remotion.get("ok"):
        ready = False
    payload = {
        "status": "ready" if ready else "not_ready",
        "service": "new-cut-backend",
        "blog_render_engine": engine,
        "blog_render_ffmpeg_fallback": bool(settings.blog_render_ffmpeg_fallback),
        "remotion": remotion,
        "render_queue": render_queue_stats(),
    }
    return JSONResponse(status_code=200 if ready else 503, content=payload)
