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
    transcription_chunk_mb: int = 24
    cors_origins: list[str] = ["http://127.0.0.1:5173", "http://localhost:5173"]

    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")


settings = Settings()
