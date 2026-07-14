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
    transcription_chunk_mb: int = 24
    highlight_min_seconds: int = 15
    highlight_max_seconds: int = 60
    blog_image_min_count: int = 3
    blog_image_max_count: int = 8
    blog_fetch_timeout_seconds: int = 20
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
