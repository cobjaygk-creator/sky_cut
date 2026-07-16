from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    app_name: str = "New Cut"
    app_env: str = "local"
    database_url: str = "sqlite:///./new_cut.db"
    jwt_secret_key: str = "change-this-local-dev-secret"
    jwt_algorithm: str = "HS256"
    jwt_expire_minutes: int = 60 * 24
    max_upload_mb: int = 500
    openai_api_key: str | None = None
    openai_transcription_model: str = "whisper-1"
    openai_highlight_model: str = "gpt-4o-mini"
    openai_metadata_model: str = "gpt-4o-mini"
    tts_provider: str = "openai"
    tts_api_key: str | None = None
    openai_tts_model: str = "gpt-4o-mini-tts"
    openai_tts_voice: str = "alloy"
    # Typecast API (https://typecast.ai/docs) — used when TTS_PROVIDER=typecast.
    typecast_api_key: str | None = None
    typecast_base_url: str = "https://api.typecast.ai"
    typecast_model: str = "ssfm-v30"
    typecast_voice_id: str | None = None
    typecast_language: str = "kor"
    transcription_chunk_mb: int = 24
    highlight_min_seconds: int = 15
    highlight_max_seconds: int = 60
    blog_image_min_count: int = 3
    blog_image_max_count: int = 8
    blog_fetch_timeout_seconds: int = 20
    # Pexels stock photos for board image search (Stage 20). Empty = search disabled (400).
    pexels_api_key: str | None = None
    stock_search_timeout_seconds: int = 15
    # Remotion R1: where to materialize board images for staticFile() (repo remotion/public).
    remotion_public_dir: str | None = None
    # Used when remotion-props is requested without materialize (auth still required on image URLs).
    public_api_base_url: str = "http://127.0.0.1:8000"
    # R3: blog final render engine — remotion (default) or ffmpeg.
    blog_render_engine: str = "remotion"
    remotion_service_url: str = "http://127.0.0.1:3100"
    remotion_service_token: str | None = None
    remotion_render_timeout_seconds: int = 600
    # If Remotion fails, fall back to FFmpeg slideshow path.
    blog_render_ffmpeg_fallback: bool = True
    # Phase-2 blog renders (TTS + Remotion/FFmpeg) in-process concurrency cap.
    blog_render_max_concurrent: int = 1
    # Vite auto-increments the port (5174, 5175, ...) when 5173 is already taken by
    # another local project, so a few fallback ports are allowlisted here to avoid
    # the frontend silently failing with CORS/"Failed to fetch" errors.
    cors_origins: list[str] = [
        "http://127.0.0.1:5173",
        "http://localhost:5173",
        "http://127.0.0.1:5174",
        "http://localhost:5174",
        "http://127.0.0.1:5175",
        "http://localhost:5175",
    ]

    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")


settings = Settings()
