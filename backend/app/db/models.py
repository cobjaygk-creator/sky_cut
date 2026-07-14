from dataclasses import dataclass


@dataclass(frozen=True)
class User:
    id: int
    email: str
    plan: str
    monthly_usage: int
    usage_limit: int
    usage_month: str
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


@dataclass(frozen=True)
class Highlight:
    id: int
    video_id: int
    start_time: float
    end_time: float
    title: str
    reason: str
    content_type: str
    score: float
    created_at: str


@dataclass(frozen=True)
class Clip:
    id: int
    user_id: int
    video_id: int
    highlight_id: int
    output_path: str | None
    subtitle_style: str | None
    subtitle_path: str | None
    subtitled_output_path: str | None
    tts_mode: str
    narration_script: str | None
    narration_audio_path: str | None
    narrated_output_path: str | None
    status: str
    error_message: str | None
    created_at: str
    updated_at: str


@dataclass(frozen=True)
class ClipMetadata:
    id: int
    clip_id: int
    title_candidates_json: str
    description: str
    hashtags_json: str
    error_message: str | None
    created_at: str
    updated_at: str


@dataclass(frozen=True)
class BlogClip:
    id: int
    user_id: int
    source_url: str
    blog_title: str | None
    narration_script: str | None
    subtitle_style: str
    video_path: str | None
    subtitled_video_path: str | None
    status: str
    progress_stage: str
    progress_percent: int
    error_message: str | None
    title_candidates_json: str | None
    description: str | None
    hashtags_json: str | None
    metadata_error: str | None
    created_at: str
    updated_at: str
