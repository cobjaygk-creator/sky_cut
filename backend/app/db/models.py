from dataclasses import dataclass


@dataclass(frozen=True)
class User:
    id: int
    email: str
    created_at: str


@dataclass(frozen=True)
class Video:
    id: int
    user_id: int
    original_filename: str
    stored_filename: str
    storage_path: str
    content_type: str
    file_size: int
    status: str
    audio_path: str | None
    error_message: str | None
    created_at: str
    updated_at: str


@dataclass(frozen=True)
class Transcript:
    id: int
    video_id: int
    status: str
    text: str | None
    segments_json: str
    error_message: str | None
    created_at: str
    updated_at: str
