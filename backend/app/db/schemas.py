from typing import Literal

from pydantic import BaseModel, EmailStr, Field, HttpUrl


class RegisterRequest(BaseModel):
    email: EmailStr
    password: str = Field(min_length=8, max_length=128)


class LoginRequest(BaseModel):
    email: EmailStr
    password: str = Field(min_length=1, max_length=128)


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"


class UserResponse(BaseModel):
    id: int
    email: EmailStr
    plan: str
    monthly_usage: int
    usage_limit: int
    usage_month: str
    created_at: str


class UsageResponse(BaseModel):
    plan: str
    plan_name: str
    monthly_usage: int
    usage_limit: int
    remaining: int
    usage_month: str
    max_video_minutes: int


class PlanResponse(BaseModel):
    id: str
    name: str
    monthly_video_limit: int
    max_video_minutes: int
    description: str


class YoutubeImportRequest(BaseModel):
    url: HttpUrl


class VideoResponse(BaseModel):
    id: int
    original_filename: str
    stored_filename: str
    content_type: str
    file_size: int
    status: str
    audio_path: str | None = None
    error_message: str | None = None
    created_at: str
    updated_at: str


class VideoStatusResponse(BaseModel):
    id: int
    status: str
    audio_path: str | None = None
    error_message: str | None = None
    updated_at: str


class TranscriptSegmentResponse(BaseModel):
    index: int
    start: float
    end: float
    text: str


class TranscriptResponse(BaseModel):
    id: int
    video_id: int
    status: str
    text: str | None = None
    segments: list[TranscriptSegmentResponse] = []
    error_message: str | None = None
    created_at: str
    updated_at: str


class HighlightResponse(BaseModel):
    id: int
    video_id: int
    start_time: float
    end_time: float
    title: str
    reason: str
    content_type: str
    score: float
    created_at: str


class ClipCreateRequest(BaseModel):
    highlight_id: int


SubtitleStyle = Literal["basic", "bold", "shorts"]
TtsMode = Literal["original_audio", "ai_narration"]


class SubtitleCreateRequest(BaseModel):
    style: SubtitleStyle = "basic"


class NarrationRequest(BaseModel):
    mode: TtsMode = "original_audio"


class ClipResponse(BaseModel):
    id: int
    video_id: int
    highlight_id: int
    output_path: str | None = None
    subtitle_style: str | None = None
    subtitle_path: str | None = None
    subtitled_output_path: str | None = None
    tts_mode: str = "original_audio"
    narration_script: str | None = None
    narration_audio_path: str | None = None
    narrated_output_path: str | None = None
    status: str
    error_message: str | None = None
    created_at: str
    updated_at: str


class ClipMetadataResponse(BaseModel):
    id: int
    clip_id: int
    title_candidates: list[str]
    description: str
    hashtags: list[str]
    error_message: str | None = None
    created_at: str
    updated_at: str


class BlogClipCreateRequest(BaseModel):
    url: HttpUrl
    style: SubtitleStyle = "shorts"


class BlogClipResponse(BaseModel):
    id: int
    source_url: str
    blog_title: str | None = None
    narration_script: str | None = None
    subtitle_style: str = "shorts"
    video_path: str | None = None
    subtitled_video_path: str | None = None
    status: str
    error_message: str | None = None
    title_candidates: list[str] = []
    description: str | None = None
    hashtags: list[str] = []
    metadata_error: str | None = None
    created_at: str
    updated_at: str
